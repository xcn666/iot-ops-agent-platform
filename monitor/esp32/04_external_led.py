# 04_external_led.py - 外接 LED 闪烁 (接在 GPIO4 上)
# 接线: GPIO4 --220Ω-- LED长脚(+) ; LED短脚(-) -- GND
from machine import Pin
import time

led = Pin(4, Pin.OUT)          # GPIO4 设为输出
print("外接 LED 闪烁开始 (GPIO4)")

while True:
    led.value(1)               # 点亮
    time.sleep(0.5)
    led.value(0)               # 熄灭
    time.sleep(0.5)
