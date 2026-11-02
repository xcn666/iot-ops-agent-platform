#!/bin/bash
# start_broker.sh - 一键启动本地 MQTT broker(学习用)
if pgrep -x mosquitto > /dev/null; then
  echo "broker 已在运行 (PID: 704)"
else
  mosquitto -c /etc/mosquitto/local-learning.conf -d
  sleep 0.5
  if pgrep -x mosquitto > /dev/null; then
    echo "broker 启动成功 (PID: 704)"
  else
    echo "启动失败, 请检查配置"
  fi
fi
ss -tln | grep 1883 && echo "1883 端口监听中 OK"
