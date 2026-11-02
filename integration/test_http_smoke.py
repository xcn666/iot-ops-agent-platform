"""Exercise the Agent's real HTTP client against the monitor API in-process."""

from __future__ import annotations

import os
import sys
import tempfile
import threading
from pathlib import Path

from werkzeug.serving import make_server

ROOT = Path(__file__).resolve().parents[1]
AGENT_ROOT = ROOT / "agent"
MONITOR_ROOT = ROOT / "monitor"
sys.path.insert(0, str(AGENT_ROOT))
sys.path.insert(0, str(MONITOR_ROOT))

os.environ["IOT_MONITOR_API_TOKEN"] = "integration-smoke-token"

import db as monitor_db  # noqa: E402
import agent_api  # noqa: E402
from iot_agent.settings import Settings  # noqa: E402
from iot_agent.tools import build_default_registry  # noqa: E402


def main() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        monitor_db.DB_PATH = str(Path(temp_dir) / "sensor.db")
        monitor_db.init_db()
        monitor_db.insert_reading("12:00:00", 27.5, 55, "esp32-smoke")

        server = make_server("127.0.0.1", 0, agent_api.app)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            settings = Settings(
                rag_index_path=Path(temp_dir) / "rag.json",
                agent_db_path=Path(temp_dir) / "agent.db",
                notify_config_path=Path(temp_dir) / "notify.json",
                monitor_api_url=f"http://127.0.0.1:{server.server_port}",
                monitor_api_token="integration-smoke-token",
            )
            tools = build_default_registry(settings, llm=None)

            stats = tools.execute("get_sensor_stats", {"metric": "max", "field": "temp"})
            assert stats.ok and stats.data["value"] == 27.5, stats

            rules = tools.execute("list_alert_rules", {})
            assert rules.ok and rules.data["returned"] == 1, rules

            create_args = {"field": "temp", "operator": "gt", "threshold": 36, "cooldown_sec": 60}
            blocked = tools.execute("create_alert_rule", create_args.copy(), confirmed=False)
            assert not blocked.ok and "confirmation required" in blocked.error, blocked

            created = tools.execute("create_alert_rule", create_args, confirmed=True)
            assert created.ok and created.data["rule"]["threshold"] == 36, created

            updated = tools.execute(
                "update_alert_rule",
                {"rule_id": created.data["rule"]["id"], "threshold": 38},
                confirmed=True,
            )
            assert updated.ok and updated.data["rule"]["threshold"] == 38, updated
        finally:
            server.shutdown()
            thread.join(timeout=2)

    print("HTTP integration passed: GET, confirmed POST, PUT, and read-back verification.")


if __name__ == "__main__":
    main()
