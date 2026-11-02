#!/usr/bin/env python3
# sensor_publisher.py - 设备端: 采集+发布(支持离线缓存与补发)
import json
import os
import sys
import time
import paho.mqtt.client as mqtt
import sensor_lib

BROKER = os.getenv("IOT_MQTT_BROKER", "broker.emqx.io")
PORT = int(os.getenv("IOT_MQTT_PORT", "1883"))
TOPIC = os.getenv("IOT_MQTT_PUBLISH_TOPIC", "iot/xcn666/sensor")
QUEUE = os.path.expanduser("~/iot-lab/logs/offline_queue.jsonl")

count = int(sys.argv[1]) if len(sys.argv) > 1 else 5
interval = float(sys.argv[2]) if len(sys.argv) > 2 else 1

os.makedirs(os.path.dirname(QUEUE), exist_ok=True)

def make_text():
    r = sensor_lib.make_record()
    r["device"] = "xcn666-sim"
    return json.dumps(r, ensure_ascii=False)

def save_offline(text):
    with open(QUEUE, "a", encoding="utf-8") as f:
        f.write(text + "\n")

def load_queue():
    if not os.path.exists(QUEUE):
        return []
    with open(QUEUE, "r", encoding="utf-8") as f:
        return [line.strip() for line in f if line.strip()]

client = mqtt.Client()
client.reconnect_delay_set(min_delay=1, max_delay=10)   # 断线重连: 1~10秒退避

def on_disconnect(c, userdata, rc):
    if rc != 0:
        print(f"[断线] 与 broker 断开(rc={rc}), 正在自动重连...", flush=True)

client.on_disconnect = on_disconnect

# 尝试连接
try:
    client.connect(BROKER, PORT, keepalive=10)
    client.loop_start()
    online = True
    print("已连接 broker", flush=True)
except Exception as e:
    online = False
    print(f"[离线] 连不上 broker, 数据将存入本地队列", flush=True)

# 在线时先补发离线队列
if online:
    queued = load_queue()
    if queued:
        print(f"[补发] 发现 {len(queued)} 条离线数据, 正在补发...", flush=True)
        for text in queued:
            client.publish(TOPIC, text)
            print("[补发]", text, flush=True)
        os.remove(QUEUE)
        print("[补发] 完成, 队列已清空", flush=True)

print(f"开始采集 {count} 次, 间隔 {interval} 秒", flush=True)
for i in range(count):
    text = make_text()
    if online:
        client.publish(TOPIC, text)
        print("[发布]", text, flush=True)
    else:
        save_offline(text)
        print("[离线存储]", text, flush=True)
    if i < count - 1:
        time.sleep(interval)

if online:
    client.loop_stop()
    client.disconnect()
    print("发布完成", flush=True)
else:
    print(f"离线模式结束, 数据已存入: {QUEUE}", flush=True)
