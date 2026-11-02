# 10_wifi_test.py - WiFi 诊断: 先扫描, 再连接(带状态清理)
import network
import time

WIFI_SSID = "iQOO Neo9"
WIFI_PASSWORD = "qwert8389875"

print("=" * 46)
print("步骤1: 扫描附近的 WiFi 网络")
print("=" * 46)
wlan = network.WLAN(network.STA_IF)
wlan.active(False)
time.sleep(0.5)
wlan.active(True)
time.sleep(1)

try:
    nets = wlan.scan()
    print("找到 {} 个网络:".format(len(nets)))
    print("  {:<24} {:>6} {:>6}".format("SSID", "信号", "通道"))
    for n in nets:
        ssid = n[0].decode("utf-8", "ignore")
        ch = n[2]
        rssi = n[3]
        band = "2.4G" if ch <= 14 else "5G"
        mark = "  <== 你要连的" if ssid == WIFI_SSID else ""
        print("  {:<24} {:>6} {:>4}({}){}".format(ssid, rssi, ch, band, mark))
except Exception as e:
    print("扫描失败:", e)

print()
print("=" * 46)
print("步骤2: 尝试连接 '{}'".format(WIFI_SSID))
print("=" * 46)

# 清理可能残留的连接状态
try:
    wlan.disconnect()
except Exception:
    pass
wlan.active(False)
time.sleep(1)
wlan.active(True)
time.sleep(1)

ok = False
try:
    wlan.connect(WIFI_SSID, WIFI_PASSWORD)
except OSError as e:
    print("第一次 connect 报错:", e)
    print("等待 2 秒后重试...")
    time.sleep(2)
    try:
        wlan.disconnect()
    except Exception:
        pass
    time.sleep(0.5)
    try:
        wlan.connect(WIFI_SSID, WIFI_PASSWORD)
        print("重试已发出连接请求")
    except OSError as e2:
        print("重试仍失败:", e2)

for i in range(30):
    if wlan.isconnected():
        ok = True
        break
    time.sleep(1)
    print(".", end="")

print()
if ok:
    ip, mask, gw, dns = wlan.ifconfig()
    print("WiFi 连接成功!")
    print("  IP地址: {}".format(ip))
    print("  网关:   {}".format(gw))
    print("  DNS:    {}".format(dns))
else:
    print("WiFi 连接失败")
    print("  status() =", wlan.status())
    print("  提示: status 常见值 1001=连接中 1000=未连接 201=无AP 202=认证失败")
    print("  如果是 202 -> 密码错误; 如果扫描不到该网络 -> 可能是 5GHz(ESP32不支持)")
