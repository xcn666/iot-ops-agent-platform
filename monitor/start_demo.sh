#!/bin/bash
# start_demo.sh - Start broker, dashboard, Agent API, and a simulated device.
cd ~/iot-lab
if [ -z "$IOT_MONITOR_API_TOKEN" ]; then
  echo "请先设置 IOT_MONITOR_API_TOKEN，并在 Agent 项目设置相同的令牌。" >&2
  exit 1
fi
export IOT_MQTT_BROKER="${IOT_MQTT_BROKER:-localhost}"
export IOT_MQTT_PORT="${IOT_MQTT_PORT:-1883}"
./start_broker.sh

# 关掉旧的服务进程(如果还在)
pkill -f "python3 dashboard.py" 2>/dev/null
pkill -f "python3 agent_api.py" 2>/dev/null
sleep 0.5

nohup python3 dashboard.py > /tmp/dashboard.log 2>&1 &
nohup python3 agent_api.py > /tmp/agent-api.log 2>&1 &
sleep 2
echo "大屏地址: http://localhost:5000  (请在浏览器打开)"
echo "Agent API: http://localhost:5002"

# 后台模拟设备上报 60 秒
python3 sensor_publisher.py 60 1 > /tmp/publisher.log 2>&1 &
echo "已在后台模拟设备上报(60秒), 打开浏览器即可看到曲线"
