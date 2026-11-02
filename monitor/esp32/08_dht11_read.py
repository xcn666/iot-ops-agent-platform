# 08_dht11_read.py - 读取 DHT11 温湿度 (确认版)
# 接线: VCC->3V3, DATA->GPIO5, GND->GND
import dht
from machine import Pin
import time

print("等待传感器稳定 (2秒)...")
time.sleep(2)                          # DHT 上电后需要稳定时间, 否则第一次读会超时

sensor = dht.DHT11(Pin(5))             # 你的模块是 DHT11

print("开始读取温湿度 (Ctrl+C 停止)")
print("-" * 34)
while True:
    try:
        sensor.measure()               # 触发测量
        t = sensor.temperature()       # 温度(整数, 摄氏度)
        h = sensor.humidity()          # 湿度(整数, %)
        print("温度: {} C    湿度: {} %".format(t, h))
    except OSError as e:
        print("读取失败(会自动重试):", e)
    time.sleep(2)

# 小实验: 用手握住传感器或对着它哈气, 观察湿度变化!
