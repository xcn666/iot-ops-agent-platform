#!/usr/bin/env python3
# sensor_lib.py - 传感器工具函数(自己的模块)
import random
from datetime import datetime

def make_record():
    """生成一条模拟传感器记录(字典)"""
    return {
        "time": datetime.now().strftime("%H:%M:%S.%f")[:-3],
        "temp": round(random.uniform(20, 35), 1),
        "hum": random.randint(40, 80),
    }

def is_alert(temp, threshold=26):
    """温度超过阈值返回 True"""
    return temp > threshold

def average(values):
    """求平均值"""
    total = 0
    for v in values:
        total = total + v
    return total / len(values)
