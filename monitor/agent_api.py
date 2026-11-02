#!/usr/bin/env python3
"""Authenticated HTTP API consumed by the IoT Operations Agent."""
import hmac
import math
import os

from flask import Flask, jsonify, request

import db

app = Flask(__name__)
FIELDS = {"temp", "hum"}
OPERATORS = {"gt", "gte", "lt", "lte"}


@app.before_request
def require_agent_token():
    expected = os.getenv("IOT_MONITOR_API_TOKEN", "")
    supplied = request.headers.get("Authorization", "")
    if not expected:
        return jsonify({"error": "monitor API token is not configured"}), 503
    if not hmac.compare_digest(supplied, f"Bearer {expected}"):
        return jsonify({"error": "unauthorized"}), 401


def _rule_payload(data, allow_enabled=True):
    if not isinstance(data, dict):
        raise ValueError("request body must be a JSON object")
    allowed = {"device_id", "field", "operator", "threshold", "cooldown_sec"}
    if allow_enabled:
        allowed.add("enabled")
    unknown = set(data) - allowed
    if unknown:
        raise ValueError(f"unknown fields: {', '.join(sorted(unknown))}")
    field = data.get("field")
    operator = data.get("operator")
    threshold = data.get("threshold")
    cooldown_sec = data.get("cooldown_sec", 300)
    device = data.get("device_id")
    enabled = data.get("enabled", True)
    if field not in FIELDS:
        raise ValueError("field must be temp or hum")
    if operator not in OPERATORS:
        raise ValueError("operator must be gt, gte, lt, or lte")
    if isinstance(threshold, bool) or not isinstance(threshold, (int, float)):
        raise ValueError("threshold must be a number")
    if not math.isfinite(threshold) or not -100 <= threshold <= 200:
        raise ValueError("threshold must be between -100 and 200")
    if isinstance(cooldown_sec, bool) or not isinstance(cooldown_sec, int):
        raise ValueError("cooldown_sec must be an integer")
    if not 10 <= cooldown_sec <= 86400:
        raise ValueError("cooldown_sec must be between 10 and 86400")
    if device is not None and (not isinstance(device, str) or not device.strip() or len(device) > 100):
        raise ValueError("device_id must be null or a non-empty string of at most 100 characters")
    if not isinstance(enabled, bool):
        raise ValueError("enabled must be a boolean")
    return device, field, operator, float(threshold), cooldown_sec, enabled


@app.get("/health")
def health():
    return jsonify({"status": "ok"})


@app.get("/api/agent/readings")
def api_readings():
    limit = request.args.get("limit", default=20, type=int)
    if limit is None or not 1 <= limit <= 5000:
        return jsonify({"error": "limit must be between 1 and 5000"}), 400
    try:
        rows = db.get_readings(
            device=request.args.get("device_id"),
            start=request.args.get("start"),
            end=request.args.get("end"),
            limit=limit,
        )
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify({"rows": rows, "returned": len(rows)})


@app.get("/api/agent/stats")
def api_stats():
    metric = request.args.get("metric", "max")
    field = request.args.get("field", "temp")
    try:
        result = db.sensor_stat(
            metric,
            field,
            device=request.args.get("device_id"),
            start=request.args.get("start"),
            end=request.args.get("end"),
        )
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(result)


@app.get("/api/agent/alerts")
def api_alerts():
    limit = request.args.get("limit", default=10, type=int)
    if limit is None or not 1 <= limit <= 100:
        return jsonify({"error": "limit must be between 1 and 100"}), 400
    alerts = db.recent_alerts(limit, request.args.get("device_id"))
    return jsonify({"alerts": alerts, "returned": len(alerts)})


@app.get("/api/agent/alert-rules")
def api_list_alert_rules():
    rules = db.list_alert_rules(
        enabled_only=request.args.get("enabled_only", "false").lower() == "true",
        device=request.args.get("device_id"),
    )
    return jsonify({"rules": rules, "returned": len(rules)})


@app.post("/api/agent/alert-rules")
def api_create_alert_rule():
    try:
        device, field, operator, threshold, cooldown_sec, _ = _rule_payload(
            request.get_json(silent=True), allow_enabled=False
        )
        rule = db.create_alert_rule(device, field, operator, threshold, cooldown_sec)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify({"rule": rule}), 201


@app.put("/api/agent/alert-rules/<int:rule_id>")
def api_update_alert_rule(rule_id):
    try:
        current = next((rule for rule in db.list_alert_rules() if rule["id"] == rule_id), None)
        if current is None:
            return jsonify({"error": "alert rule not found"}), 404
        merged = {
            "device_id": current["device"],
            "field": current["field"],
            "operator": current["operator"],
            "threshold": current["threshold"],
            "cooldown_sec": current["cooldown_sec"],
            "enabled": bool(current["enabled"]),
        }
        body = request.get_json(silent=True)
        if not isinstance(body, dict):
            raise ValueError("request body must be a JSON object")
        merged.update(body)
        device, field, operator, threshold, cooldown_sec, enabled = _rule_payload(merged)
        rule = db.update_alert_rule(
            rule_id, device, field, operator, threshold, cooldown_sec, enabled
        )
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    if rule is None:
        return jsonify({"error": "alert rule not found"}), 404
    return jsonify({"rule": rule})


if __name__ == "__main__":
    db.init_db()
    print("Agent API 已启动: http://localhost:5002", flush=True)
    app.run(host="0.0.0.0", port=int(os.getenv("IOT_MONITOR_API_PORT", "5002")), debug=False)
