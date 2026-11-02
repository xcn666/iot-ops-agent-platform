#!/usr/bin/env python3
# query_db.py - 在命令行执行 SQL 查询(练习用)
import sqlite3
import sys
import db

db.init_db()
sql = sys.argv[1] if len(sys.argv) > 1 else (
    "SELECT COUNT(*) AS 总条数, ROUND(AVG(temp),2) AS 平均温度, "
    "MAX(temp) AS 最高温度, MIN(temp) AS 最低温度 FROM readings"
)

conn = sqlite3.connect(db.DB_PATH)
try:
    cur = conn.execute(sql)
    cols = [d[0] for d in cur.description]
    print(" | ".join(cols))
    print("-" * 50)
    for row in cur:
        print(" | ".join(str(v) for v in row))
except sqlite3.Error as e:
    print("SQL 错误:", e)
finally:
    conn.close()
