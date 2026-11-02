import io
import json
import os
import sqlite3
import threading
import tempfile
import unittest
from contextlib import closing
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

import db
import agent_api


class AgentApiTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        db.DB_PATH = str(Path(self.temp.name) / "sensor.db")
        db.init_db()
        self.token_patch = patch.dict(os.environ, {"IOT_MONITOR_API_TOKEN": "test-token"})
        self.token_patch.start()
        self.client = agent_api.app.test_client()
        self.headers = {"Authorization": "Bearer test-token"}

    def tearDown(self):
        self.token_patch.stop()
        self.temp.cleanup()

    def test_requires_bearer_token(self):
        response = self.client.get("/api/agent/alert-rules")
        self.assertEqual(response.status_code, 401)

    def test_fails_closed_when_token_is_not_configured(self):
        with patch.dict(os.environ, {"IOT_MONITOR_API_TOKEN": ""}):
            response = self.client.get("/api/agent/alert-rules", headers=self.headers)
        self.assertEqual(response.status_code, 503)

    def test_creates_and_lists_rule(self):
        response = self.client.post(
            "/api/agent/alert-rules",
            headers=self.headers,
            json={
                "device_id": None,
                "field": "temp",
                "operator": "gt",
                "threshold": 35,
                "cooldown_sec": 60,
            },
        )
        self.assertEqual(response.status_code, 201)
        created = response.get_json()["rule"]
        rules = self.client.get("/api/agent/alert-rules", headers=self.headers).get_json()["rules"]
        self.assertIn(created, rules)

    def test_rejects_invalid_threshold(self):
        response = self.client.post(
            "/api/agent/alert-rules",
            headers=self.headers,
            json={"field": "temp", "operator": "gt", "threshold": 500},
        )
        self.assertEqual(response.status_code, 400)

    def test_created_rule_drives_alert_and_cooldown(self):
        rules = db.list_alert_rules()
        default_rule = rules[0]
        db.update_alert_rule(
            default_rule["id"], None, "temp", "gt", 35, 60, True
        )
        self.assertEqual(
            db.evaluate_alert_rules("10:00:00", {"temp": 36, "hum": 40}, "device-1", now=100),
            [{**db.list_alert_rules()[0], "value": 36, "time": "10:00:00"}],
        )
        self.assertEqual(
            db.evaluate_alert_rules("10:00:10", {"temp": 37, "hum": 40}, "device-1", now=110),
            [],
        )
        alerts = db.recent_alerts()
        self.assertEqual(len(alerts), 1)
        self.assertEqual(alerts[0]["value"], 36)

    def test_update_rule(self):
        rule_id = db.list_alert_rules()[0]["id"]
        response = self.client.put(
            f"/api/agent/alert-rules/{rule_id}",
            headers=self.headers,
            json={"threshold": 40},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["rule"]["threshold"], 40)

    def test_mqtt_callback_applies_configured_rule_and_cooldown(self):
        import dashboard

        dashboard.db.DB_PATH = db.DB_PATH
        payload = {
            "time": "10:00:00",
            "temp": 36,
            "hum": 50,
            "device": "device-1",
        }

        class Message:
            def __init__(self, data):
                self.payload = json.dumps(data).encode("utf-8")

        with patch("dashboard.notify.push_alert") as push_alert:
            with redirect_stdout(io.StringIO()):
                dashboard.on_message(None, None, Message(payload))
                dashboard.on_message(None, None, Message(payload))

        self.assertEqual(len(db.recent_alerts()), 1)
        push_alert.assert_called_once()

    def test_migrates_existing_sensor_database(self):
        legacy_path = Path(self.temp.name) / "legacy.db"
        with closing(sqlite3.connect(legacy_path)) as connection, connection:
            connection.executescript(
                """
                CREATE TABLE readings (id INTEGER PRIMARY KEY, time TEXT, temp REAL, hum INTEGER, device TEXT);
                CREATE TABLE alerts (id INTEGER PRIMARY KEY, time TEXT, temp REAL, threshold REAL, device TEXT);
                INSERT INTO readings(time, temp, hum, device) VALUES ('10:00:00', 25.0, 50, 'device-1');
                """
            )
        previous_path = db.DB_PATH
        try:
            db.DB_PATH = str(legacy_path)
            db.init_db()
            self.assertEqual(len(db.list_alert_rules()), 1)
            self.assertEqual(db.get_readings(limit=1)[0]["temp"], 25.0)
        finally:
            db.DB_PATH = previous_path

    def test_concurrent_initialization_seeds_one_default_rule(self):
        concurrent_path = Path(self.temp.name) / "concurrent.db"
        previous_path = db.DB_PATH
        db.DB_PATH = str(concurrent_path)
        barrier = threading.Barrier(4)
        errors = []

        def initialize():
            try:
                barrier.wait()
                db.init_db()
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=initialize) for _ in range(4)]
        try:
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join()
            self.assertEqual(errors, [])
            self.assertEqual(len(db.list_alert_rules()), 1)
        finally:
            db.DB_PATH = previous_path


if __name__ == "__main__":
    unittest.main()
