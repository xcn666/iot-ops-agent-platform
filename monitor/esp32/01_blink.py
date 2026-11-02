# 01_blink.py - 让板载 LED 闪烁 (ESP32 + MicroPython)
# 运行方法: Thonny 里打开本文件 -> 按 F5 (或点绿色运行按钮)
from machine import Pin
import time

led = Pin(2, Pin.OUT)      # GPIO2 设为输出模式 (多数 ESP32 开发板的板载 LED)

print("LED 闪烁开始! 按 Thonny 的红色停止按钮可停止")

while True:
    led.value(1)           # 输出高电平(3.3V) -> 点亮
    time.sleep(0.5)        # 亮 0.5 秒
    led.value(0)           # 输出低电平(0V) -> 熄灭
    time.sleep(0.5)        # 灭 0.5 秒
