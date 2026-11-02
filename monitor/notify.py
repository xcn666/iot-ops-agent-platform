#!/usr/bin/env python3
# notify.py - 告警推送模块(通用 Webhook: 钉钉/企业微信/Server酱/PushPlus 等)
import json
import os
import urllib.request

CONFIG = os.path.expanduser("~/iot-lab/notify_config.json")

def load_config():
    if not os.path.exists(CONFIG):
        return {}
    with open(CONFIG, encoding="utf-8") as f:
        return json.load(f)

def send_webhook(url, text, timeout=5):
    """向 webhook 地址 POST 一段 JSON"""
    payload = json.dumps({"msgtype": "text", "text": {"content": text}, "content": text}).encode("utf-8")
    req = urllib.request.Request(url, data=payload,
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status
    except Exception as e:
        print(f"[推送失败] {e}", flush=True)
        return None

def push_alert(text):
    url = load_config().get("webhook_url", "").strip()
    if not url:
        print("[推送] 未配置 webhook_url, 跳过(仅本地告警)", flush=True)
        return None
    status = send_webhook(url, text)
    print(f"[推送] webhook 已发送, 状态={status}", flush=True)
    return status

if __name__ == "__main__":
    push_alert("测试消息: 来自 notify.py")
