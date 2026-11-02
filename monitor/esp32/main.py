# main.py - ESP32 温湿度监测与 MQTT 上报 (MicroPython)
#
# 使用前:
#   1) 把 wifi_config.example.py 复制为 wifi_config.py, 填入你的 WiFi 名称和密码
#   2) 确认 simple.py (umqtt 库) 已上传到开发板
#   3) 运行本文件
import network
import time
import json
import dht
from machine import Pin
from simple import MQTTClient
from wifi_config import WIFI_SSID, WIFI_PASSWORD

MQTT_HOST = "broker.emqx.io"      # 公共 MQTT broker(可换成自己的服务器)
MQTT_PORT = 1883
CLIENT_ID = "esp32-xcn666"
TOPIC = "iot/xcn666/esp32/sensor"
DEVICE = "esp32-dht11"
DATA_PIN = 5                       # DHT11 数据脚 -> GPIO5

sensor = dht.DHT11(Pin(DATA_PIN))


def connect_wifi():
    wlan = network.WLAN(network.STA_IF)
    try:
        wlan.disconnect()
    except Exception:
        pass
    wlan.active(False)
    time.sleep(0.5)
    wlan.active(True)
    time.sleep(1)

    if wlan.isconnected():
        print("WiFi 已连接, IP:", wlan.ifconfig()[0])
        return True

    print("正在连接 WiFi:", WIFI_SSID)
    wlan.connect(WIFI_SSID, WIFI_PASSWORD)
    for _ in range(20):
        if wlan.isconnected():
            break
        time.sleep(1)
        print(".", end="")
    print()
    if wlan.isconnected():
        print("WiFi 连接成功! IP:", wlan.ifconfig()[0])
        return True
    print("WiFi 连接失败, status =", wlan.status())
    return False


def sync_time():
    try:
        import ntptime
        ntptime.settime()
        print("NTP 时间同步成功")
        return True
    except Exception as e:
        print("NTP 同步失败(改用开机计时):", e)
        return False


def now_str(synced, t0):
    t = time.localtime(time.time() + 8 * 3600) if synced else time.localtime(t0)
    return "{:02d}:{:02d}:{:02d}".format(t[3], t[4], t[5])


if connect_wifi():
    synced = sync_time()
    t0 = time.time()

    client = MQTTClient(CLIENT_ID, MQTT_HOST, MQTT_PORT, keepalive=30)
    client.connect()
    print("MQTT 已连接:", MQTT_HOST)
    print("上报主题:", TOPIC)
    print("-" * 44)

    time.sleep(2)
    while True:
        try:
            sensor.measure()
            payload = json.dumps({
                "time": now_str(synced, t0),
                "temp": sensor.temperature(),
                "hum": sensor.humidity(),
                "device": DEVICE,
            })
            client.publish(TOPIC, payload)
            print("[已上报]", payload)
        except OSError as e:
            print("传感器读取失败:", e)
        except Exception as e:
            print("MQTT 异常, 尝试重连:", e)
            try:
                client.connect()
            except Exception as e2:
                print("重连失败:", e2)
        time.sleep(3)
