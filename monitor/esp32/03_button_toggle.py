# 03_button_toggle.py - 按一下切换 LED 状态(带简单去抖) —— 进阶版
from machine import Pin
import time

led = Pin(4, Pin.OUT)
btn = Pin(18, Pin.IN, Pin.PULL_UP)

state = 0                      # 0=灭, 1=亮
last = 1                       # 上一次按键读数
print("按一下按键切换 LED 开关状态")

while True:
    now = btn.value()
    if last == 1 and now == 0:        # 检测"按下"这一刻(下降沿)
        time.sleep_ms(30)             # 去抖: 等 30ms 再确认
        if btn.value() == 0:
            state = 1 - state         # 状态翻转 0<->1
            led.value(state)
            print("LED", "亮" if state else "灭")
    last = now
    time.sleep(0.01)
