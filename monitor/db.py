#!/usr/bin/env python3
"""SQLite storage for sensor readings, alerts, and alert rules."""
import os
import sqlite3
from contextlib import closing
from datetime import datetime

DB_PATH = os.path.expanduser(os.path.expandvars(os.getenv("IOT_DB_PATH", "~/iot-lab/logs/sensor.db")))


def get_conn():
    directory = os.path.dirname(DB_PATH)
    if directory:
        os.makedirs(directory, exist_ok=True)
    connection = sqlite3.connect(DB_PATH, timeout=10)
    connection.row_factory = sqlite3.Row
    return connection


def _ensure_column(conn, table, name, definition):
    columns = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})")}
    if name not in columns:
        try:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {name} {definition}")
        except sqlite3.OperationalError as exc:
            # Two service processes can initialize the shared database together.
            if "duplicate column name" not in str(exc).lower():
                raise


def init_db():
    with closing(get_conn()) as conn, conn:
        conn.execute(
            """CREATE TABLE IF NOT EXISTS readings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                day TEXT,
                time TEXT,
                temp REAL,
                hum INTEGER,
                device TEXT
            )"""
        )
        _ensure_column(conn, "readings", "day", "TEXT")
        conn.execute(
            "UPDATE readings SET day = ? WHERE day IS NULL",
            (datetime.now().strftime("%Y-%m-%d"),),
        )
        conn.execute(
            """CREATE TABLE IF NOT EXISTS alerts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                time TEXT,
                temp REAL,
                threshold REAL,
                device TEXT
            )"""
        )
        _ensure_column(conn, "alerts", "field", "TEXT NOT NULL DEFAULT 'temp'")
        _ensure_column(conn, "alerts", "value", "REAL")
        _ensure_column(conn, "alerts", "operator", "TEXT NOT NULL DEFAULT 'gt'")
        _ensure_column(conn, "alerts", "rule_id", "INTEGER")
        conn.execute(
            """CREATE TABLE IF NOT EXISTS alert_rules (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                device TEXT,
                field TEXT NOT NULL CHECK (field IN ('temp', 'hum')),
                operator TEXT NOT NULL CHECK (operator IN ('gt', 'gte', 'lt', 'lte')),
                threshold REAL NOT NULL,
                cooldown_sec INTEGER NOT NULL CHECK (cooldown_sec BETWEEN 10 AND 86400),
                enabled INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL
            )"""
        )
        conn.execute(
            """CREATE TABLE IF NOT EXISTS alert_cooldowns (
                rule_id INTEGER NOT NULL,
                device TEXT NOT NULL,
                last_triggered_at REAL NOT NULL,
                PRIMARY KEY (rule_id, device)
            )"""
        )
        conn.execute(
            """INSERT INTO alert_rules
               (device, field, operator, threshold, cooldown_sec, enabled, created_at)
               SELECT NULL, 'temp', 'gt', 30, 10, 1, ?
               WHERE NOT EXISTS (SELECT 1 FROM alert_rules)""",
            (datetime.now().isoformat(timespec="seconds"),),
        )


def insert_reading(time_str, temp, hum, device=""):
    with closing(get_conn()) as conn, conn:
        conn.execute(
            "INSERT INTO readings (day, time, temp, hum, device) VALUES (?, ?, ?, ?, ?)",
            (datetime.now().strftime("%Y-%m-%d"), time_str, temp, hum, device),
        )


def insert_alert(time_str, value, threshold, device="", field="temp", operator="gt", rule_id=None):
    temp = value if field == "temp" else None
    with closing(get_conn()) as conn, conn:
        conn.execute(
            """INSERT INTO alerts (time, temp, threshold, device, field, value, operator, rule_id)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (time_str, temp, threshold, device, field, value, operator, rule_id),
        )


def recent(limit=30):
    with closing(get_conn()) as conn:
        rows = conn.execute(
            "SELECT day, time, temp, hum, device FROM readings ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
    rows.reverse()
    return [dict(row) for row in rows]


def all_rows():
    """Return all readings for export."""
    with closing(get_conn()) as conn:
        rows = conn.execute(
            "SELECT day, time, temp, hum, device FROM readings ORDER BY id"
        ).fetchall()
    return [dict(row) for row in rows]


def recent_alerts(limit=10, device=None):
    clauses = []
    params = []
    if device:
        clauses.append("device = ?")
        params.append(device)
    where = " WHERE " + " AND ".join(clauses) if clauses else ""
    params.append(limit)
    with closing(get_conn()) as conn:
        rows = conn.execute(
            "SELECT time, temp, threshold, device, field, value, operator, rule_id "
            f"FROM alerts{where} ORDER BY id DESC LIMIT ?",
            params,
        ).fetchall()
    return [
        {
            **dict(row),
            "value": row["value"] if row["value"] is not None else row["temp"],
        }
        for row in rows
    ]


def list_alert_rules(enabled_only=False, device=None):
    clauses = []
    params = []
    if enabled_only:
        clauses.append("enabled = 1")
    if device is not None:
        clauses.append("(device IS NULL OR device = ?)")
        params.append(device)
    where = " WHERE " + " AND ".join(clauses) if clauses else ""
    with closing(get_conn()) as conn:
        rows = conn.execute(
            "SELECT id, device, field, operator, threshold, cooldown_sec, enabled, created_at "
            f"FROM alert_rules{where} ORDER BY id",
            params,
        ).fetchall()
    return [dict(row) for row in rows]


def create_alert_rule(device, field, operator, threshold, cooldown_sec):
    with closing(get_conn()) as conn, conn:
        cursor = conn.execute(
            """INSERT INTO alert_rules
               (device, field, operator, threshold, cooldown_sec, enabled, created_at)
               VALUES (?, ?, ?, ?, ?, 1, ?)""",
            (
                device,
                field,
                operator,
                threshold,
                cooldown_sec,
                datetime.now().isoformat(timespec="seconds"),
            ),
        )
        rule_id = cursor.lastrowid
    return next(rule for rule in list_alert_rules() if rule["id"] == rule_id)


def update_alert_rule(rule_id, device, field, operator, threshold, cooldown_sec, enabled=True):
    with closing(get_conn()) as conn, conn:
        cursor = conn.execute(
            """UPDATE alert_rules
               SET device = ?, field = ?, operator = ?, threshold = ?, cooldown_sec = ?, enabled = ?
               WHERE id = ?""",
            (device, field, operator, threshold, cooldown_sec, int(enabled), rule_id),
        )
        if cursor.rowcount != 1:
            return None
    return next(rule for rule in list_alert_rules() if rule["id"] == rule_id)


def _record_rule_alert(rule, time_str, value, device, now):
    """Atomically enforce cooldown and persist one alert for a rule/device pair."""
    device_key = device or ""
    with closing(get_conn()) as conn, conn:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute(
            "SELECT last_triggered_at FROM alert_cooldowns WHERE rule_id = ? AND device = ?",
            (rule["id"], device_key),
        ).fetchone()
        if row and now - row["last_triggered_at"] < rule["cooldown_sec"]:
            return False
        conn.execute(
            """INSERT INTO alert_cooldowns(rule_id, device, last_triggered_at)
               VALUES (?, ?, ?)
               ON CONFLICT(rule_id, device) DO UPDATE SET last_triggered_at = excluded.last_triggered_at""",
            (rule["id"], device_key, now),
        )
        conn.execute(
            """INSERT INTO alerts (time, temp, threshold, device, field, value, operator, rule_id)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                time_str,
                value if rule["field"] == "temp" else None,
                rule["threshold"],
                device,
                rule["field"],
                value,
                rule["operator"],
                rule["id"],
            ),
        )
    return True


def evaluate_alert_rules(time_str, readings, device="", now=None):
    now = datetime.now().timestamp() if now is None else now
    operators = {
        "gt": lambda value, threshold: value > threshold,
        "gte": lambda value, threshold: value >= threshold,
        "lt": lambda value, threshold: value < threshold,
        "lte": lambda value, threshold: value <= threshold,
    }
    triggered = []
    for rule in list_alert_rules(enabled_only=True, device=device):
        raw_value = readings.get(rule["field"])
        if isinstance(raw_value, bool) or not isinstance(raw_value, (int, float)):
            continue
        if not operators[rule["operator"]](raw_value, rule["threshold"]):
            continue
        if _record_rule_alert(rule, time_str, raw_value, device, now):
            triggered.append({**rule, "value": raw_value, "time": time_str})
    return triggered


def _reading_filters(device=None, start=None, end=None):
    clauses = []
    params = []
    if device:
        clauses.append("device = ?")
        params.append(device)
    for value, comparison in ((start, ">="), (end, "<=")):
        if not value:
            continue
        normalized = value.strip().replace("T", " ").replace("Z", "+00:00")
        if len(normalized) == 10:
            datetime.strptime(normalized, "%Y-%m-%d")
            clauses.append(f"day {comparison} ?")
            params.append(normalized)
        else:
            parsed = datetime.fromisoformat(normalized)
            day = parsed.strftime("%Y-%m-%d")
            clock = parsed.strftime("%H:%M:%S")
            if comparison == ">=":
                clauses.append("(day > ? OR (day = ? AND time >= ?))")
            else:
                clauses.append("(day < ? OR (day = ? AND time <= ?))")
            params.extend([day, day, clock])
    return clauses, params


def get_readings(device=None, start=None, end=None, limit=100):
    clauses, params = _reading_filters(device, start, end)
    where = " WHERE " + " AND ".join(clauses) if clauses else ""
    params.append(limit)
    with closing(get_conn()) as conn:
        rows = conn.execute(
            "SELECT day, time, device, temp, hum FROM readings"
            f"{where} ORDER BY day DESC, time DESC, id DESC LIMIT ?",
            params,
        ).fetchall()
    return [dict(row) for row in rows]


def sensor_stat(metric, field, device=None, start=None, end=None):
    functions = {"max": "MAX", "min": "MIN", "avg": "AVG", "count": "COUNT"}
    if metric not in functions or field not in {"temp", "hum"}:
        raise ValueError("invalid metric or field")
    clauses, params = _reading_filters(device, start, end)
    where = " WHERE " + " AND ".join(clauses) if clauses else ""
    expression = "COUNT(*)" if metric == "count" else f"ROUND({functions[metric]}({field}), 2)"
    with closing(get_conn()) as conn:
        value, count = conn.execute(
            f"SELECT {expression}, COUNT(*) FROM readings{where}", params
        ).fetchone()
    return {"metric": metric, "field": field, "value": value, "sample_count": count}


def stats():
    with closing(get_conn()) as conn:
        row = conn.execute(
            "SELECT COUNT(*), AVG(temp), MAX(temp), MIN(temp), AVG(hum), MAX(hum), MIN(hum) FROM readings"
        ).fetchone()
        alert_cnt = conn.execute("SELECT COUNT(*) FROM alerts").fetchone()[0]
    return {
        "count": row[0] or 0,
        "avg_temp": round(row[1], 2) if row[1] is not None else None,
        "max_temp": row[2],
        "min_temp": row[3],
        "avg_hum": round(row[4], 2) if row[4] is not None else None,
        "max_hum": row[5],
        "min_hum": row[6],
        "alert_count": alert_cnt or 0,
    }


def daily_stats(day):
    with closing(get_conn()) as conn:
        row = conn.execute(
            "SELECT COUNT(*), AVG(temp), MAX(temp), MIN(temp), AVG(hum), MAX(hum), MIN(hum) "
            "FROM readings WHERE day = ?",
            (day,),
        ).fetchone()
    return {
        "count": row[0] or 0,
        "avg_temp": round(row[1], 2) if row[1] is not None else None,
        "max_temp": row[2],
        "min_temp": row[3],
        "avg_hum": round(row[4], 2) if row[4] is not None else None,
        "max_hum": row[5],
        "min_hum": row[6],
    }


if __name__ == "__main__":
    init_db()
    print("数据库初始化/迁移完成:", DB_PATH)
    print("统计:", stats())
