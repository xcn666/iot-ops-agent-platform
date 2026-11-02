#!/usr/bin/env python3
# data_collector.py - 订阅设备数据, 写入 SQLite 并告警
import json
import os
import paho.mqtt.client as mqtt
import db

BROKER = os.getenv("IOT_MQTT_BROKER", "broker.emqx.io")
PORT = int(os.getenv("IOT_MQTT_PORT", "1883"))
TOPIC = os.getenv("IOT_MQTT_TOPIC", "iot/xcn666/#")
db.init_db()

def on_connect(client, userdata, flags, rc):
    print("已连接 broker, 订阅:", TOPIC, flush=True)
    client.subscribe(TOPIC)

def on_message(client, userdata, msg):
    try:
        data = json.loads(msg.payload.decode("utf-8"))
    except json.JSONDecodeError:
        return
    if "temp" not in data:
        return
    device = data.get("device", "")
    db.insert_reading(data.get("time", ""), data.get("temp"), data.get("hum", 0), device)
    print(f"[入库] temp={data['temp']}C hum={data.get('hum')}%", flush=True)
    triggered = db.evaluate_alert_rules(
        data.get("time", ""), {"temp": data.get("temp"), "hum": data.get("hum")}, device
    )
    for rule in triggered:
        print(
            f"  >>> 告警! 规则 #{rule['id']} {rule['field']} {rule['operator']} {rule['threshold']}",
            flush=True,
        )

client = mqtt.Client()
client.on_connect = on_connect
client.on_message = on_message
client.connect(BROKER, PORT)
print("监听中... Ctrl+C 退出", flush=True)
client.loop_forever()
