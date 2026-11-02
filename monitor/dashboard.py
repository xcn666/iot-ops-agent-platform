#!/usr/bin/env python3
# dashboard.py - 环境监测大屏 (MQTT + SQLite + Flask, 深色科技风)
import csv as csv_mod
import io
import json
import os
import threading
import time
from flask import Flask, Response, jsonify, render_template_string, request
import paho.mqtt.client as mqtt
import db
import notify

BROKER = os.getenv("IOT_MQTT_BROKER", "broker.emqx.io")
PORT = int(os.getenv("IOT_MQTT_PORT", "1883"))
TOPIC = os.getenv("IOT_MQTT_TOPIC", "iot/xcn666/#")
HISTORY_LIMIT = int(os.getenv("IOT_HISTORY_LIMIT", "60"))

app = Flask(__name__)
lock = threading.Lock()


def on_connect(client, userdata, flags, rc, properties=None):
    print("已连接 broker, 订阅", TOPIC, flush=True)
    client.subscribe(TOPIC)


def on_message(client, userdata, msg):
    try:
        d = json.loads(msg.payload.decode("utf-8"))
    except json.JSONDecodeError:
        return
    if "temp" not in d:
        return

    temp = d["temp"]
    device = d.get("device", "unknown")

    with lock:
        db.insert_reading(d.get("time", ""), temp, d.get("hum", 0), device)
        triggered = db.evaluate_alert_rules(
            d.get("time", ""), {"temp": temp, "hum": d.get("hum")}, device, time.time()
        )
        for rule in triggered:
            label = "温度" if rule["field"] == "temp" else "湿度"
            operator = {"gt": ">", "gte": "≥", "lt": "<", "lte": "≤"}[rule["operator"]]
            msg_txt = (
                f"[告警] {device} {label} {rule['value']} {operator} "
                f"{rule['threshold']} (规则 #{rule['id']}, 时间 {rule['time']})"
            )
            print(msg_txt, flush=True)
            notify.push_alert(msg_txt)
    print("已入库:", d, flush=True)


try:
    mqtt_client = mqtt.Client(callback_api_version=mqtt.CallbackAPIVersion.VERSION2)
except (AttributeError, TypeError):
    mqtt_client = mqtt.Client()
mqtt_client.reconnect_delay_set(min_delay=1, max_delay=10)


def on_disconnect(c, userdata, disconnect_flags, reason_code=None, properties=None):
    reason = disconnect_flags if reason_code is None else reason_code
    if hasattr(reason, "value"):
        reason = reason.value
    if reason != 0:
        print(f"[断线] 与 broker 断开(rc={reason}), 等待自动重连...", flush=True)


def start_mqtt():
    mqtt_client.on_disconnect = on_disconnect
    mqtt_client.on_connect = on_connect
    mqtt_client.on_message = on_message
    mqtt_client.connect(BROKER, PORT)
    mqtt_client.loop_start()

PAGE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>环境监测中心</title>
<script src="https://cdn.bootcdn.net/ajax/libs/Chart.js/4.4.1/chart.umd.min.js"></script>
<style>
  :root{
    --bg:#070b14; --card:rgba(255,255,255,.045); --border:rgba(255,255,255,.09);
    --text:#e8eef7; --muted:#7f8ea3; --cyan:#38bdf8; --indigo:#818cf8;
    --amber:#fbbf24; --coral:#fb7185; --green:#34d399;
  }
  *{box-sizing:border-box}
  body{overflow-x:hidden;margin:0;padding:32px 34px 44px;background:var(--bg);color:var(--text);min-height:100vh;
       font-family:"Inter",-apple-system,"Segoe UI","Microsoft YaHei",sans-serif;-webkit-font-smoothing:antialiased}
  .glow{position:fixed;inset:0;pointer-events:none;z-index:0;
    background:radial-gradient(620px 420px at 10% -6%,rgba(56,189,248,.17),transparent 70%),
               radial-gradient(720px 520px at 90% -2%,rgba(129,140,248,.15),transparent 70%),
               radial-gradient(900px 620px at 50% 112%,rgba(52,211,153,.07),transparent 70%)}
  .wrap{position:relative;z-index:1;max-width:1360px;margin:0 auto}
  header{display:flex;align-items:center;justify-content:space-between;gap:20px;flex-wrap:wrap;margin-bottom:26px}
  .brand{display:flex;align-items:center;gap:14px}
  .logo{width:46px;height:46px;border-radius:15px;display:grid;place-items:center;font-size:20px;
        background:linear-gradient(135deg,rgba(56,189,248,.26),rgba(129,140,248,.26));
        border:1px solid rgba(56,189,248,.35);box-shadow:inset 0 0 24px rgba(56,189,248,.25)}
  h1{font-size:21px;margin:0;font-weight:600;letter-spacing:.4px}
  .sub{margin:4px 0 0;font-size:12.5px;color:var(--muted);letter-spacing:.3px}
  .header-right{display:flex;align-items:center;gap:12px}
  .pill{display:flex;align-items:center;gap:8px;padding:8px 15px;border-radius:999px;font-size:12.5px;
        background:rgba(52,211,153,.1);border:1px solid rgba(52,211,153,.3);color:#a7f3d0}
  .pill.warn{background:rgba(251,113,133,.12);border-color:rgba(251,113,133,.35);color:#fecdd3}
  .dot{width:8px;height:8px;border-radius:50%;background:var(--green);animation:pulse 5s ease-in-out infinite}
  .pill.warn .dot{background:var(--coral);animation:pulseR 3.5s ease-in-out infinite}
  @keyframes pulse{0%{box-shadow:0 0 0 0 rgba(52,211,153,.40)}70%{box-shadow:0 0 0 6px rgba(52,211,153,0)}100%{box-shadow:0 0 0 0 rgba(52,211,153,0)}}
  @keyframes pulseR{0%{box-shadow:0 0 0 0 rgba(251,113,133,.45)}70%{box-shadow:0 0 0 7px rgba(251,113,133,0)}100%{box-shadow:0 0 0 0 rgba(251,113,133,0)}}
  .btn{padding:9px 17px;border-radius:12px;font-size:13px;text-decoration:none;color:#e0f2fe;
       background:linear-gradient(135deg,rgba(56,189,248,.22),rgba(129,140,248,.22));
       border:1px solid rgba(56,189,248,.35);transition:all .2s ease}
  .btn:hover{transform:translateY(-1px);border-color:rgba(56,189,248,.7);box-shadow:0 8px 24px rgba(56,189,248,.18)}
  .toggle{cursor:pointer;padding:8px 15px;border-radius:999px;font-size:12.5px;color:#c7d6ea;
    background:rgba(255,255,255,.05);border:1px solid rgba(255,255,255,.14);transition:all .2s ease}
  .toggle:hover{border-color:rgba(56,189,248,.6);color:#e0f2fe}
  .toggle.off{color:var(--muted);background:rgba(255,255,255,.02)}
  body.no-motion *,body.no-motion *::before,body.no-motion *::after{
    animation:none!important;transition:none!important}
  .card{min-width:0;background:var(--card);border:1px solid var(--border);border-radius:20px;
        backdrop-filter:blur(14px);-webkit-backdrop-filter:blur(14px);
        box-shadow:0 10px 34px rgba(0,0,0,.45);animation:fadeUp .5s ease both}
  @keyframes fadeUp{from{opacity:0;transform:translateY(10px)}to{opacity:1;transform:none}}
  .hero{display:grid;grid-template-columns:212px 212px 1fr;gap:18px;margin-bottom:18px}
  .gauge-card{padding:20px 16px;display:flex;flex-direction:column;align-items:center;justify-content:center;text-align:center}
  .ring-wrap{position:relative;width:142px;height:142px}
  svg.ring{width:142px;height:142px;transform:rotate(-90deg)}
  .ring-bg{fill:none;stroke:rgba(255,255,255,.07);stroke-width:10}
  .ring-fg{fill:none;stroke-width:10;stroke-linecap:round;
           transition:stroke-dashoffset .8s cubic-bezier(.4,0,.2,1),stroke .4s}
  .ring-fg.temp{stroke:url(#gradTemp);filter:drop-shadow(0 0 6px rgba(56,189,248,.5))}
  .ring-fg.hum{stroke:url(#gradHum);filter:drop-shadow(0 0 6px rgba(129,140,248,.5))}
  .gauge-center{position:absolute;inset:0;display:flex;flex-direction:column;align-items:center;justify-content:center}
  .gauge-value{font-size:32px;font-weight:700;letter-spacing:-1px;font-variant-numeric:tabular-nums}
  .gauge-unit{font-size:11.5px;color:var(--muted);margin-top:3px}
  .gauge-label{margin-top:12px;font-size:13px;color:var(--muted);letter-spacing:1px}
  .gauge-sub{margin-top:6px;font-size:12.5px;color:var(--muted)}
  .gauge-sub b{color:var(--indigo);font-size:14px}
  .kpi-group{display:grid;grid-template-columns:repeat(2,1fr);gap:16px}
  .kpi{padding:20px 22px;display:flex;flex-direction:column;justify-content:space-between;min-height:128px}
  .kpi-label{font-size:12.5px;color:var(--muted);letter-spacing:.6px}
  .kpi-value{font-size:30px;font-weight:700;margin-top:8px;font-variant-numeric:tabular-nums}
  .kpi-value small{font-size:13px;font-weight:500;color:var(--muted);margin-left:3px}
  .v-cyan{color:var(--cyan)}.v-indigo{color:var(--indigo)}.v-amber{color:var(--amber)}
  .v-coral{color:var(--coral)}.v-green{color:var(--green)}.v-text{color:var(--text)}
  .hum-strip{display:grid;grid-template-columns:auto repeat(3,1fr);align-items:center;padding:16px 28px;margin-bottom:18px}
  .hs-title{font-size:13px;color:var(--muted);letter-spacing:1px;padding-right:30px}
  .hum-item{display:flex;flex-direction:column;align-items:center;justify-content:center;gap:4px;
    padding:2px 10px;border-left:1px solid rgba(255,255,255,.09)}
  .hum-item .label{font-size:12.5px;color:var(--muted);letter-spacing:.5px}
  .hum-item .value{font-size:26px;font-weight:700;font-variant-numeric:tabular-nums}
  .hum-item .value small{font-size:13px;color:var(--muted);font-weight:500;margin-left:2px}
  .main-grid{display:grid;grid-template-columns:1.85fr 1fr;gap:18px}
  .main-grid>*{min-width:0}
  .card-head{display:flex;align-items:center;justify-content:space-between;padding:18px 22px 6px}
  .card-head h2{font-size:14.5px;margin:0;font-weight:600;letter-spacing:.6px}
  .hint{font-size:12px;color:var(--muted)}
  .badge{font-size:12px;padding:3px 11px;border-radius:999px;background:rgba(251,113,133,.15);
         color:#fecdd3;border:1px solid rgba(251,113,133,.3)}
  .chart-box{padding:6px 18px 18px;min-width:0;overflow:hidden}
  canvas#chart{display:block;width:100%!important;height:340px!important}
  .alert-list{padding:10px 16px 18px;max-height:372px;overflow-y:auto}
  .alert-item{display:flex;gap:12px;padding:12px 14px;margin-bottom:10px;border-radius:14px;
    background:rgba(251,113,133,.07);border:1px solid rgba(251,113,133,.18);
    border-left:3px solid var(--coral)}
  .alert-item.new{animation:slideIn .45s ease both}
  @keyframes slideIn{from{opacity:0;transform:translateX(8px)}to{opacity:1;transform:none}}
  .alert-time{font-size:12px;color:#fda4af;min-width:64px;font-variant-numeric:tabular-nums}
  .alert-body{font-size:13px;line-height:1.5}
  .alert-body b{color:#fecdd3;font-size:14px}
  .empty{color:var(--muted);font-size:13px;text-align:center;padding:28px 0}
  ::-webkit-scrollbar{width:8px}::-webkit-scrollbar-thumb{background:rgba(255,255,255,.12);border-radius:8px}
  @media(max-width:1080px){.hero{grid-template-columns:1fr 1fr}.kpi-group{grid-column:1/-1}.main-grid{grid-template-columns:1fr}}
  @media(max-width:820px){.hero{grid-template-columns:1fr}.kpi-group{grid-template-columns:repeat(2,1fr)}body{padding:16px 14px 28px}h1{font-size:19px}.header-right{width:100%;justify-content:flex-end}}
</style>
</head>
<body>
<div class="glow"></div>
<div class="wrap">
  <header>
    <div class="brand">
      <div class="logo">◈</div>
      <div>
        <h1>环境监测中心</h1>
        <p class="sub">IoT Environment Monitor · <span id="deviceInfo">模拟设备</span></p>
      </div>
    </div>
    <div class="header-right">
      <div class="pill" id="statusPill"><span class="dot"></span><span id="statusText">实时在线</span></div>
      <button class="toggle" id="motionBtn" type="button">动效 开</button>
      <a class="btn" href="/api/export">导出数据</a>
    </div>
  </header>

  <section class="hero">
    <div class="card gauge-card">
      <svg style="position:absolute;width:0;height:0">
        <defs>
          <linearGradient id="gradTemp" x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stop-color="#38bdf8"/><stop offset="100%" stop-color="#818cf8"/>
          </linearGradient>
          <linearGradient id="gradHum" x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stop-color="#34d399"/><stop offset="100%" stop-color="#38bdf8"/>
          </linearGradient>
        </defs>
      </svg>
      <div class="ring-wrap">
        <svg class="ring" viewBox="0 0 120 120">
          <circle class="ring-bg" cx="60" cy="60" r="52"/>
          <circle class="ring-fg temp" id="tempRing" cx="60" cy="60" r="52" stroke-dasharray="326.7" stroke-dashoffset="326.7"/>
        </svg>
        <div class="gauge-center">
          <div class="gauge-value v-cyan" id="temp">--</div>
          <div class="gauge-unit">摄氏度 °C</div>
        </div>
      </div>
      <div class="gauge-label">当前温度</div>
    </div>

    <div class="card gauge-card">
      <div class="ring-wrap">
        <svg class="ring" viewBox="0 0 120 120">
          <circle class="ring-bg" cx="60" cy="60" r="52"/>
          <circle class="ring-fg hum" id="humRing" cx="60" cy="60" r="52" stroke-dasharray="326.7" stroke-dashoffset="326.7"/>
        </svg>
        <div class="gauge-center">
          <div class="gauge-value v-indigo" id="hum">--</div>
          <div class="gauge-unit">相对湿度 %</div>
        </div>
      </div>
      <div class="gauge-label">当前湿度</div>
    </div>

    <div class="kpi-group">
      <div class="card kpi"><div class="kpi-label">数据总量</div><div class="kpi-value v-text" id="count">0<small>条</small></div></div>
      <div class="card kpi"><div class="kpi-label">平均温度</div><div class="kpi-value v-green" id="avg">--<small>°C</small></div></div>
      <div class="card kpi"><div class="kpi-label">最高温度</div><div class="kpi-value v-coral" id="max">--<small>°C</small></div></div>
      <div class="card kpi"><div class="kpi-label">最低温度</div><div class="kpi-value v-cyan" id="min">--<small>°C</small></div></div>
    </div>
  </section>

  <section class="card hum-strip">
    <div class="hs-title">湿度统计</div>
    <div class="hum-item"><div class="label">平均湿度</div><div class="value v-indigo" id="humAvg">--<small>%</small></div></div>
    <div class="hum-item"><div class="label">最高湿度</div><div class="value v-cyan" id="humMax">--<small>%</small></div></div>
    <div class="hum-item"><div class="label">最低湿度</div><div class="value v-green" id="humMin">--<small>%</small></div></div>
  </section>

  <section class="main-grid">
    <div class="card">
      <div class="card-head"><h2>温湿度趋势</h2><span class="hint">最近 60 条采样</span></div>
      <div class="chart-box"><canvas id="chart"></canvas></div>
    </div>
    <div class="card">
      <div class="card-head"><h2>告警记录</h2><span class="hint" style="margin-left:auto;margin-right:10px">累计 <b id="alerts" style="color:#fbbf24;font-size:13px">0</b> 次</span><span class="badge" id="alertBadge">0 条</span></div>
      <div class="alert-list" id="alertList"><div class="empty">暂无告警</div></div>
    </div>
  </section>
</div>

<script>
const motionBtn = document.getElementById('motionBtn');
let motionOn = true;

function applyMotion(on) {
  motionOn = on;
  document.body.classList.toggle('no-motion', !on);
  motionBtn.textContent = on ? '动效 开' : '动效 关';
  motionBtn.classList.toggle('off', !on);
}

const saved = localStorage.getItem('motion');
if (saved === null) {
  applyMotion(!window.matchMedia('(prefers-reduced-motion: reduce)').matches);
} else {
  applyMotion(saved === '1');
}
motionBtn.addEventListener('click', function () {
  applyMotion(!motionOn);
  localStorage.setItem('motion', motionOn ? '1' : '0');
});

const C = 326.7;
const chartEl = document.getElementById('chart');
const cctx = chartEl.getContext('2d');
const gradTemp = cctx.createLinearGradient(0, 0, 0, 320);
gradTemp.addColorStop(0, 'rgba(56,189,248,0.30)');
gradTemp.addColorStop(1, 'rgba(56,189,248,0.00)');
const gradHum = cctx.createLinearGradient(0, 0, 0, 320);
gradHum.addColorStop(0, 'rgba(129,140,248,0.26)');
gradHum.addColorStop(1, 'rgba(129,140,248,0.00)');

const chart = new Chart(cctx, {
  type: 'line',
  data: { labels: [], datasets: [
    { label: '温度 °C', data: [], borderColor: '#38bdf8', backgroundColor: gradTemp,
      fill: true, borderWidth: 2.4, pointRadius: 0, pointHoverRadius: 4, tension: 0.4 },
    { label: '湿度 %', data: [], borderColor: '#818cf8', backgroundColor: gradHum,
      fill: true, borderWidth: 2.4, pointRadius: 0, pointHoverRadius: 4, tension: 0.4 }
  ]},
  options: {
    responsive: true, maintainAspectRatio: false, animation: { duration: 600 },
    interaction: { intersect: false, mode: 'index' },
    plugins: {
      legend: { position: 'top', align: 'end',
        labels: { color: '#93a4bb', boxWidth: 10, boxHeight: 10, usePointStyle: true, font: { size: 12 } } },
      tooltip: { backgroundColor: 'rgba(8,13,24,0.94)', borderColor: 'rgba(255,255,255,0.12)',
        borderWidth: 1, titleColor: '#e8eef7', bodyColor: '#b8c6d9', padding: 12,
        cornerRadius: 10, usePointStyle: true }
    },
    scales: {
      x: { grid: { display: false }, border: { display: false },
           ticks: { color: '#64748b', maxTicksLimit: 6, font: { size: 11 },
             callback: function (v) {
               const s = this.getLabelForValue(v);
               return (typeof s === 'string' && s.length > 8) ? s.substring(0, 8) : s;
             } } },
      y: { grid: { color: 'rgba(255,255,255,0.05)' }, border: { display: false },
           ticks: { color: '#64748b', font: { size: 11 } } }
    }
  }
});

let alertSig = '';
let alertTopKey = '';

function renderAlerts(alerts, isNewTop) {
  const box = document.getElementById('alertList');
  document.getElementById('alertBadge').textContent = alerts.length + ' 条';
  if (!alerts.length) { box.innerHTML = '<div class="empty">暂无告警</div>'; return; }
  box.innerHTML = alerts.map(function (a, i) {
    const cls = (isNewTop && i === 0) ? 'alert-item new' : 'alert-item';
    const field = a.field === 'hum' ? '湿度' : '温度';
    const unit = a.field === 'hum' ? '%' : ' °C';
    const operator = ({gt: '>', gte: '≥', lt: '<', lte: '≤'})[a.operator] || '>';
    return '<div class="' + cls + '"><div class="alert-time">' + a.time + '</div>' +
      '<div class="alert-body">' + field + ' <b>' + a.value + unit + '</b> ' + operator + ' 阈值 ' + a.threshold + unit + '</div></div>';
  }).join('');
}

function setRing(el, pct) {
  const p = Math.max(0, Math.min(1, pct));
  el.style.strokeDashoffset = String(C * (1 - p));
}

async function refresh() {
  const [hRes, sRes, aRes, rRes] = await Promise.all([
    fetch('/api/history?limit=60'), fetch('/api/stats'), fetch('/api/alerts?limit=6'), fetch('/api/rules')
  ]);
  const history = await hRes.json();
  const s = await sRes.json();
  const alerts = await aRes.json();
  const rules = await rRes.json();

  if (history.length) {
    chart.data.labels = history.map(d => d.time);
    chart.data.datasets[0].data = history.map(d => d.temp);
    chart.data.datasets[1].data = history.map(d => d.hum);
    chart.update();

    const last = history[history.length - 1];
    document.getElementById('temp').textContent = last.temp;
    document.getElementById('hum').textContent = last.hum;
    document.getElementById('deviceInfo').textContent = last.device || '模拟设备';
    setRing(document.getElementById('tempRing'), (last.temp - 10) / 30);
    setRing(document.getElementById('humRing'), last.hum / 100);

    const pill = document.getElementById('statusPill');
    const warn = rules.some(function (rule) {
      if (!rule.enabled || (rule.device && rule.device !== last.device)) return false;
      const value = last[rule.field];
      if (typeof value !== 'number') return false;
      return ({
        gt: value > rule.threshold,
        gte: value >= rule.threshold,
        lt: value < rule.threshold,
        lte: value <= rule.threshold
      })[rule.operator] || false;
    });
    pill.classList.toggle('warn', warn);
    document.getElementById('statusText').textContent = warn ? '规则触发' : '实时在线';
  }

  document.getElementById('count').innerHTML = s.count + '<small>条</small>';
  document.getElementById('avg').innerHTML = (s.avg_temp === null ? '--' : s.avg_temp) + '<small>°C</small>';
  document.getElementById('max').innerHTML = (s.max_temp === null ? '--' : s.max_temp) + '<small>°C</small>';
  document.getElementById('min').innerHTML = (s.min_temp === null ? '--' : s.min_temp) + '<small>°C</small>';
  document.getElementById('humAvg').innerHTML = (s.avg_hum === null ? '--' : s.avg_hum) + '<small>%</small>';
  document.getElementById('humMax').innerHTML = (s.max_hum === null ? '--' : s.max_hum) + '<small>%</small>';
  document.getElementById('humMin').innerHTML = (s.min_hum === null ? '--' : s.min_hum) + '<small>%</small>';
  document.getElementById('alerts').textContent = s.alert_count;

  // 只有告警内容变化时才重绘(避免每2秒重放动画造成闪烁)
  const sig = JSON.stringify(alerts);
  if (sig !== alertSig) {
    const topKey = alerts.length ? (alerts[0].time + '|' + alerts[0].field + '|' + alerts[0].value) : '';
    const isNewTop = topKey !== alertTopKey;
    alertTopKey = topKey;
    alertSig = sig;
    renderAlerts(alerts, isNewTop);
  }
}
setInterval(refresh, 2000);
refresh();
</script>
</body>
</html>"""


@app.route("/")
def index():
    return render_template_string(PAGE)


@app.route("/api/history")
def api_history():
    return jsonify(db.recent(request.args.get("limit", HISTORY_LIMIT, type=int)))


@app.route("/api/stats")
def api_stats():
    return jsonify(db.stats())


@app.route("/api/alerts")
def api_alerts():
    return jsonify(db.recent_alerts(request.args.get("limit", 10, type=int)))


@app.route("/api/rules")
def api_rules():
    return jsonify(db.list_alert_rules(enabled_only=True))


@app.route("/api/export")
def api_export():
    rows = db.all_rows()
    buf = io.StringIO()
    w = csv_mod.writer(buf)
    w.writerow(["time", "temp", "hum", "device"])
    for r in rows:
        w.writerow([r["time"], r["temp"], r["hum"], r["device"]])
    return Response(buf.getvalue(), mimetype="text/csv; charset=utf-8",
                    headers={"Content-Disposition": "attachment; filename=readings.csv"})


if __name__ == "__main__":
    db.init_db()
    print("大屏已启动: http://localhost:5000", flush=True)
    start_mqtt()
    app.run(host="0.0.0.0", port=int(os.getenv("IOT_DASHBOARD_PORT", "5000")), debug=False)
