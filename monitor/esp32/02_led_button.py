# 02_led_button.py - 按键控制 LED (GPIO 输入 + 输出)
# 接线: LED 长脚 --220Ω-- GPIO4 ; LED 短脚 -- GND ; 按键 一脚--GPIO18, 另一脚--GND
from machine import Pin
import time

led = Pin(4, Pin.OUT)                  # GPIO4 输出(接 LED)
btn = Pin(18, Pin.IN, Pin.PULL_UP)     # GPIO18 输入 + 内部上拉电阻(按键另一端接GND)

print("就绪: 按住按键, LED 应该点亮")

while True:
    if btn.value() == 0:      # 按下时引脚被拉到 GND(低电平)
        led.value(1)          # 点亮 LED
    else:
        led.value(0)          # 松开则熄灭
    time.sleep(0.02)          # 20ms 轮询一次(也能起到一点去抖作用)
