#!/usr/bin/env python3
# report.py - 生成数据日报(控制台输出 + 文本报告 + CSV 导出)
import csv
import os
from datetime import datetime
import db

db.init_db()
LOGS = os.path.expanduser("~/iot-lab/logs")
today = datetime.now().strftime("%Y-%m-%d")

s = db.daily_stats(today)
alert_cnt = db.stats()["alert_count"]

lines = [
    "===== 物联网数据日报 =====",
    f"日期     : {today}",
    f"数据条数 : {s['count']}",
    f"平均温度 : {s['avg_temp'] if s['avg_temp'] is not None else '--'} C",
    f"最高温度 : {s['max_temp'] if s['max_temp'] is not None else '--'} C",
    f"最低温度 : {s['min_temp'] if s['min_temp'] is not None else '--'} C",
    f"平均湿度 : {s['avg_hum'] if s['avg_hum'] is not None else '--'} %",
    f"告警次数 : {alert_cnt}",
    "===========================",
]
text = "\n".join(lines)
print(text)

txt_path = os.path.join(LOGS, f"report_{today}.txt")
with open(txt_path, "w", encoding="utf-8") as f:
    f.write(text + "\n")

csv_path = os.path.join(LOGS, f"export_{today}.csv")
rows = db.all_rows()
with open(csv_path, "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f)
    w.writerow(["time", "temp", "hum", "device"])
    for r in rows:
        w.writerow([r["time"], r["temp"], r["hum"], r["device"]])

print()
print("文本报告:", txt_path)
print("CSV 导出:", csv_path, f"({len(rows)} 条)")
