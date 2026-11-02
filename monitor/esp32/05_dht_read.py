# 05_dht_read.py - 读取温湿度传感器 (DHT11 版, 带预热等待)
import dht
from machine import Pin
import time

SENSOR_TYPE = dht.DHT11     # 你的模块是 DHT11 (如换成 DHT22 请改这行)
DATA_PIN = 5                # 数据脚接在 GPIO5

print("等待传感器稳定 (2秒)...")
time.sleep(2)

sensor = SENSOR_TYPE(Pin(DATA_PIN))

print("开始读取温湿度 (Ctrl+C 可停止)")
while True:
    try:
        sensor.measure()
        print("温度: {} C    湿度: {} %".format(sensor.temperature(), sensor.humidity()))
    except OSError as e:
        print("读取失败(会自动重试):", e)
    time.sleep(2)
