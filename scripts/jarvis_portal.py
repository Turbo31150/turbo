#!/usr/bin/env python3
"""
JARVIS Portal — Portail unifié de dashboards (port 8089)
Combine tous les dashboards en un seul point d'entrée.
Auteur : Turbo / JARVIS
"""

import http.server
import json
import os
import glob
import time
import socket
import subprocess
import threading
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import urlparse

# === Configuration ===
PORT = 8089
BIND = "0.0.0.0"
BASE_DIR = Path("/home/turbo/jarvis")
DATA_DIR = BASE_DIR / "data"
DOCS_DIR = BASE_DIR / "docs"
REPORTS_DIR = DATA_DIR / "reports"

# === Fonctions utilitaires pour les KPIs ===

def _safe_json(path):
    """Charge un fichier JSON en toute sécurité."""
    try:
        with open(path, "r") as f:
            return json.load(f)
    except Exception:
        return None


def _safe_jsonl_tail(path, n=10):
    """Lit les N dernières lignes d'un fichier JSONL."""
    try:
        lines = []
        with open(path, "r") as f:
            for line in f:
                line = line.strip()
                if line:
                    lines.append(line)
        tail = lines[-n:]
        return [json.loads(l) for l in tail]
    except Exception:
        return []


def get_skills_count():
    """Nombre de skills enregistrés."""
    data = _safe_json(DATA_DIR / "skills.json")
    if isinstance(data, list):
        return len(data)
    return 0


def get_commands_count():
    """Nombre de commandes vocales."""
    data = _safe_json(DATA_DIR / "jarvis_commands_compact.json")
    if isinstance(data, list):
        return len(data)
    if isinstance(data, dict):
        return sum(len(v) if isinstance(v, list) else 1 for v in data.values())
    # Fallback : compter depuis le rapport
    report = _get_latest_report_json()
    if report:
        vc = report.get("sections", {}).get("voice_commands", {})
        return vc.get("total_executed", 0)
    return 0


def get_dominos_count():
    """Nombre de dominos disponibles."""
    try:
        # Chercher les skills de type domino dans skills.json
        data = _safe_json(DATA_DIR / "skills.json")
        if isinstance(data, list):
            count = len([s for s in data if "domino" in json.dumps(s).lower()])
            if count > 0:
                return count
        # Fallback : fichiers domino
        dominos = list((BASE_DIR / "core").glob("*domino*")) + \
                  list((BASE_DIR / "scripts").glob("*domino*"))
        return len(dominos)
    except Exception:
        return 0


def get_services_count():
    """Nombre de services JARVIS actifs."""
    try:
        result = subprocess.run(
            ["systemctl", "list-units", "jarvis-*", "--no-pager", "--plain", "--no-legend"],
            capture_output=True, text=True, timeout=5
        )
        active = [l for l in result.stdout.strip().split("\n") if l.strip() and "active" in l]
        return len(active)
    except Exception:
        return 0


def get_gpu_temp():
    """Température GPU maximale."""
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=temperature.gpu", "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=5
        )
        temps = [int(t.strip()) for t in result.stdout.strip().split("\n") if t.strip()]
        return max(temps) if temps else 0
    except Exception:
        return 0


def get_improve_cycles():
    """Nombre de cycles mega-improve aujourd'hui."""
    cycles = _safe_jsonl_tail(DATA_DIR / "improve_cycles.jsonl", n=500)
    today = datetime.now().strftime("%Y-%m-%d")
    today_cycles = [c for c in cycles if c.get("timestamp", "").startswith(today)]
    return len(today_cycles)


def get_improve_cycles_24h():
    """Cycles mega-improve des dernières 24h pour le graphique."""
    cycles = _safe_jsonl_tail(DATA_DIR / "improve_cycles.jsonl", n=500)
    cutoff = datetime.now() - timedelta(hours=24)
    result = []
    for c in cycles:
        try:
            ts = datetime.fromisoformat(c["timestamp"])
            if ts >= cutoff:
                result.append({
                    "hour": ts.strftime("%H:%M"),
                    "gaps": c.get("gaps_found", 0),
                    "skills": c.get("skills_created", 0),
                    "duration": round(c.get("duration_s", 0), 1)
                })
        except Exception:
            continue
    return result


def get_notifications(n=10):
    """Dernières notifications."""
    notifs = _safe_jsonl_tail(DATA_DIR / "notifications.jsonl", n=n)
    result = []
    for notif in notifs:
        result.append({
            "title": notif.get("title", ""),
            "message": notif.get("message", ""),
            "level": notif.get("level", "info"),
            "source": notif.get("source", ""),
            "ts": notif.get("ts", 0),
            "time": datetime.fromtimestamp(notif.get("ts", 0)).strftime("%H:%M:%S")
                   if notif.get("ts") else ""
        })
    return result


def get_cluster_status():
    """État du cluster avec vérification de connectivité."""
    config = _safe_json(DATA_DIR / "jarvis_config.json")
    if not config:
        return []
    nodes_cfg = config.get("cluster", {}).get("nodes", {})
    nodes = []
    for name, info in nodes_cfg.items():
        host = info.get("host", "127.0.0.1")
        port = info.get("port", 1234)
        online = _check_port(host, port)
        nodes.append({
            "name": name,
            "host": host,
            "port": port,
            "online": online,
            "weight": info.get("weight", 1.0)
        })
    return nodes


def _check_port(host, port, timeout=2):
    """Vérifie si un port est ouvert."""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        result = sock.connect_ex((host, port))
        sock.close()
        return result == 0
    except Exception:
        return False


def get_voice_profile():
    """Profil vocal actif."""
    data = _safe_json(DATA_DIR / "voice_profiles.json")
    if data:
        return data.get("active_profile", "normal")
    return "normal"


def _get_latest_report_json():
    """Charge le dernier rapport quotidien JSON."""
    try:
        reports = sorted(REPORTS_DIR.glob("*.json"))
        if reports:
            return _safe_json(reports[-1])
    except Exception:
        pass
    return None


def get_report_summary():
    """Résumé du dernier rapport quotidien."""
    report = _get_latest_report_json()
    if not report:
        return {"date": "N/A", "summary": "Aucun rapport disponible"}
    sections = report.get("sections", {})
    sys_info = sections.get("system", {})
    brain = sections.get("brain", {})
    svc = sections.get("services", {})
    return {
        "date": report.get("date", "N/A"),
        "uptime": sys_info.get("uptime", "N/A"),
        "cpu_avg": sys_info.get("cpu_avg_percent", 0),
        "ram_pct": sys_info.get("ram_percent", 0),
        "active_services": svc.get("active_count", 0),
        "failed_services": svc.get("failed_count", 0),
        "brain_confidence": brain.get("brain_confidence", 0),
        "improve_cycles_today": brain.get("improve_cycles_today", 0),
        "total_skills": brain.get("total_skills", 0)
    }


def get_kpis():
    """Retourne les 6 KPIs principaux."""
    return {
        "skills": get_skills_count(),
        "commands": get_commands_count(),
        "dominos": get_dominos_count(),
        "services": get_services_count(),
        "gpu_temp": get_gpu_temp(),
        "improve_cycles": get_improve_cycles()
    }


def _html_escape(text):
    """Echappe les caractères HTML dangereux."""
    if not text:
        return ""
    return (str(text)
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
            .replace("'", "&#x27;"))


# === HTML du portail (tout embarqué) ===
# Note : le contenu dynamique est injecté via fetch/JSON côté client.
# La fonction esc() JS échappe tout contenu avant insertion dans le DOM.
# Ce dashboard est un outil d'admin local, pas exposé sur internet.

PORTAL_HTML = r"""<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>JARVIS Portal</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
:root{--bg:#0a0a0a;--bg2:#111;--bg3:#1a1a1a;--cyan:#00d4ff;--cyan2:#00a8cc;
--green:#00ff88;--red:#ff4444;--yellow:#ffaa00;--text:#e0e0e0;--dim:#666;
--font:'JetBrains Mono','Fira Code','Courier New',monospace}
body{background:var(--bg);color:var(--text);font-family:var(--font);
font-size:14px;display:flex;min-height:100vh;overflow-x:hidden}

/* Sidebar */
.sidebar{width:240px;background:var(--bg2);border-right:1px solid #222;
padding:20px 0;display:flex;flex-direction:column;position:fixed;
height:100vh;z-index:100;transition:transform .3s}
.sidebar-header{padding:0 20px 20px;border-bottom:1px solid #222;text-align:center}
.sidebar-header h1{font-size:20px;color:var(--cyan);letter-spacing:3px;
text-shadow:0 0 20px rgba(0,212,255,.3)}
.sidebar-header .subtitle{font-size:10px;color:var(--dim);margin-top:4px;letter-spacing:1px}
.nav-section{padding:15px 20px 5px;font-size:10px;color:var(--dim);
text-transform:uppercase;letter-spacing:2px}
.nav-link{display:flex;align-items:center;padding:10px 20px;color:var(--text);
text-decoration:none;transition:all .2s;border-left:3px solid transparent;font-size:13px}
.nav-link:hover,.nav-link.active{background:rgba(0,212,255,.05);
border-left-color:var(--cyan);color:var(--cyan)}
.nav-link .icon{margin-right:10px;font-size:16px;width:20px;text-align:center}
.nav-link .badge{margin-left:auto;background:var(--cyan);color:var(--bg);
padding:1px 6px;border-radius:8px;font-size:10px}

/* Main content */
.main{margin-left:240px;flex:1;padding:20px;min-height:100vh}

/* Header bar */
.topbar{display:flex;justify-content:space-between;align-items:center;
padding:10px 20px;background:var(--bg2);border-radius:8px;margin-bottom:20px;
border:1px solid #222}
.clock{font-size:24px;color:var(--cyan);font-weight:bold;
text-shadow:0 0 15px rgba(0,212,255,.4);letter-spacing:2px}
.topbar-right{display:flex;align-items:center;gap:15px}
.voice-badge{background:rgba(0,212,255,.1);border:1px solid var(--cyan);
color:var(--cyan);padding:4px 12px;border-radius:12px;font-size:11px}
.status-dot{width:8px;height:8px;border-radius:50%;display:inline-block;
animation:pulse 2s infinite}
.status-dot.online{background:var(--green);box-shadow:0 0 8px var(--green)}
.status-dot.offline{background:var(--red);box-shadow:0 0 8px var(--red);animation:none}
@keyframes pulse{0%,100%{opacity:1}50%{opacity:.5}}

/* KPI cards */
.kpi-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));
gap:15px;margin-bottom:20px}
.kpi-card{background:var(--bg2);border:1px solid #222;border-radius:8px;
padding:20px;text-align:center;transition:all .3s;position:relative;overflow:hidden}
.kpi-card:hover{border-color:var(--cyan);transform:translateY(-2px);
box-shadow:0 4px 20px rgba(0,212,255,.1)}
.kpi-card::before{content:'';position:absolute;top:0;left:0;right:0;height:2px;
background:linear-gradient(90deg,transparent,var(--cyan),transparent);opacity:0;
transition:opacity .3s}
.kpi-card:hover::before{opacity:1}
.kpi-icon{font-size:28px;margin-bottom:8px}
.kpi-value{font-size:32px;font-weight:bold;color:var(--cyan);
text-shadow:0 0 10px rgba(0,212,255,.3)}
.kpi-label{font-size:11px;color:var(--dim);text-transform:uppercase;
letter-spacing:1px;margin-top:4px}
.kpi-card.warning .kpi-value{color:var(--yellow)}
.kpi-card.danger .kpi-value{color:var(--red)}

/* Grid layout */
.grid-2{display:grid;grid-template-columns:1fr 1fr;gap:15px;margin-bottom:20px}
.grid-3{display:grid;grid-template-columns:2fr 1fr 1fr;gap:15px;margin-bottom:20px}
@media(max-width:1200px){.grid-2,.grid-3{grid-template-columns:1fr}}

/* Panel */
.panel{background:var(--bg2);border:1px solid #222;border-radius:8px;padding:20px}
.panel-title{font-size:12px;color:var(--cyan);text-transform:uppercase;
letter-spacing:2px;margin-bottom:15px;padding-bottom:8px;
border-bottom:1px solid #222;display:flex;align-items:center;gap:8px}

/* Chart container */
.chart-container{height:150px;display:flex;align-items:flex-end;gap:3px;
padding:10px 0}
.chart-bar{background:linear-gradient(to top,var(--cyan2),var(--cyan));
border-radius:2px 2px 0 0;min-width:8px;flex:1;transition:height .5s;
position:relative;cursor:pointer}
.chart-bar:hover{background:linear-gradient(to top,var(--cyan),#fff);
box-shadow:0 0 10px var(--cyan)}
.chart-bar:hover::after{content:attr(data-tip);position:absolute;bottom:105%;
left:50%;transform:translateX(-50%);background:var(--bg3);color:var(--cyan);
padding:2px 6px;border-radius:4px;font-size:10px;white-space:nowrap;
border:1px solid var(--cyan)}
.chart-empty{color:var(--dim);text-align:center;padding:40px;font-size:12px}

/* Notifications */
.notif-list{max-height:250px;overflow-y:auto}
.notif-item{display:flex;align-items:flex-start;padding:8px 0;
border-bottom:1px solid #1a1a1a;gap:10px}
.notif-item:last-child{border-bottom:none}
.notif-dot{width:6px;height:6px;border-radius:50%;margin-top:6px;flex-shrink:0}
.notif-dot.info{background:var(--cyan)}
.notif-dot.warning{background:var(--yellow)}
.notif-dot.critical{background:var(--red)}
.notif-content{flex:1;min-width:0}
.notif-title{font-size:12px;font-weight:bold;color:var(--text)}
.notif-msg{font-size:11px;color:var(--dim);margin-top:2px;
overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.notif-time{font-size:10px;color:var(--dim);flex-shrink:0}

/* Cluster nodes */
.cluster-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(130px,1fr));gap:10px}
.node-card{background:var(--bg3);border-radius:6px;padding:12px;text-align:center;
border:1px solid #222;transition:all .3s}
.node-card.online{border-color:rgba(0,255,136,.2)}
.node-card.offline{border-color:rgba(255,68,68,.2)}
.node-name{font-size:14px;font-weight:bold;color:var(--text);margin-bottom:4px}
.node-host{font-size:10px;color:var(--dim)}
.node-led{width:10px;height:10px;border-radius:50%;margin:8px auto;
transition:all .3s}
.node-led.online{background:var(--green);box-shadow:0 0 12px var(--green)}
.node-led.offline{background:var(--red);box-shadow:0 0 12px var(--red)}
.node-weight{font-size:10px;color:var(--dim)}

/* Report summary */
.report-grid{display:grid;grid-template-columns:1fr 1fr;gap:8px}
.report-item{display:flex;justify-content:space-between;padding:4px 0;
font-size:12px;border-bottom:1px solid #1a1a1a}
.report-label{color:var(--dim)}
.report-value{color:var(--text);font-weight:bold}

/* Scrollbar */
::-webkit-scrollbar{width:6px}
::-webkit-scrollbar-track{background:var(--bg)}
::-webkit-scrollbar-thumb{background:#333;border-radius:3px}
::-webkit-scrollbar-thumb:hover{background:#555}

/* Responsive */
@media(max-width:768px){
  .sidebar{transform:translateX(-100%)}
  .sidebar.open{transform:translateX(0)}
  .main{margin-left:0}
  .kpi-grid{grid-template-columns:repeat(2,1fr)}
  .menu-toggle{display:block !important}
}
.menu-toggle{display:none;position:fixed;top:10px;left:10px;z-index:200;
background:var(--bg2);border:1px solid #222;color:var(--cyan);
padding:8px 12px;border-radius:6px;cursor:pointer;font-size:18px}

/* Animation d'entrée */
@keyframes fadeIn{from{opacity:0;transform:translateY(10px)}to{opacity:1;transform:none}}
.kpi-card,.panel{animation:fadeIn .5s ease-out backwards}
.kpi-card:nth-child(2){animation-delay:.1s}
.kpi-card:nth-child(3){animation-delay:.2s}
.kpi-card:nth-child(4){animation-delay:.3s}
.kpi-card:nth-child(5){animation-delay:.4s}
.kpi-card:nth-child(6){animation-delay:.5s}

/* Iframe container pour les sous-dashboards */
.iframe-view{display:none;width:100%;height:calc(100vh - 80px);border:none;
border-radius:8px;background:var(--bg2)}
.iframe-view.active{display:block}
#home-view.active{display:block}
</style>
</head>
<body>

<button class="menu-toggle" onclick="document.querySelector('.sidebar').classList.toggle('open')">&#9776;</button>

<nav class="sidebar">
  <div class="sidebar-header">
    <h1>JARVIS</h1>
    <div class="subtitle">Unified Portal</div>
  </div>

  <div class="nav-section">Principal</div>
  <a class="nav-link active" href="#" onclick="showView('home')">
    <span class="icon">&#9673;</span> Accueil
  </a>

  <div class="nav-section">Dashboards</div>
  <a class="nav-link" href="#" onclick="showExternal('http://127.0.0.1:8088')">
    <span class="icon">&#9635;</span> Dashboard principal
  </a>
  <a class="nav-link" href="#" onclick="showDoc('/docs/voice_analytics.html')">
    <span class="icon">&#9835;</span> Voice Analytics
  </a>
  <a class="nav-link" href="#" onclick="showDoc('/docs/voice_commands_reference.html')">
    <span class="icon">&#9000;</span> Voice Commands
  </a>
  <a class="nav-link" href="#" onclick="showDoc('/docs/api_reference.html')">
    <span class="icon">&#9881;</span> API Reference
  </a>
  <a class="nav-link" href="#" onclick="showDoc('/docs/daily_report')">
    <span class="icon">&#9993;</span> Daily Report
  </a>

  <div class="nav-section">Monitoring</div>
  <a class="nav-link" href="#" onclick="showView('home')">
    <span class="icon">&#9729;</span> Cluster
    <span class="badge" id="cluster-badge">--</span>
  </a>

  <div style="margin-top:auto;padding:20px;border-top:1px solid #222">
    <div style="font-size:10px;color:var(--dim);text-align:center">
      JARVIS Portal v1.0<br>Port 8089
    </div>
  </div>
</nav>

<main class="main">
  <!-- Top bar -->
  <div class="topbar">
    <div class="clock" id="clock">--:--:--</div>
    <div class="topbar-right">
      <span class="voice-badge" id="voice-profile">&#127908; normal</span>
      <span class="status-dot online" id="system-status"></span>
      <span style="font-size:11px;color:var(--dim)" id="refresh-timer">15s</span>
    </div>
  </div>

  <!-- Home view -->
  <div id="home-view" class="active">
    <!-- KPI Cards -->
    <div class="kpi-grid" id="kpi-grid">
      <div class="kpi-card" id="kpi-skills">
        <div class="kpi-icon">&#129504;</div>
        <div class="kpi-value" id="val-skills">--</div>
        <div class="kpi-label">Skills</div>
      </div>
      <div class="kpi-card" id="kpi-commands">
        <div class="kpi-icon">&#127908;</div>
        <div class="kpi-value" id="val-commands">--</div>
        <div class="kpi-label">Commandes</div>
      </div>
      <div class="kpi-card" id="kpi-dominos">
        <div class="kpi-icon">&#127922;</div>
        <div class="kpi-value" id="val-dominos">--</div>
        <div class="kpi-label">Dominos</div>
      </div>
      <div class="kpi-card" id="kpi-services">
        <div class="kpi-icon">&#9881;</div>
        <div class="kpi-value" id="val-services">--</div>
        <div class="kpi-label">Services Actifs</div>
      </div>
      <div class="kpi-card" id="kpi-gpu">
        <div class="kpi-icon">&#128293;</div>
        <div class="kpi-value" id="val-gpu">--</div>
        <div class="kpi-label">GPU Temp Max</div>
      </div>
      <div class="kpi-card" id="kpi-cycles">
        <div class="kpi-icon">&#128260;</div>
        <div class="kpi-value" id="val-cycles">--</div>
        <div class="kpi-label">Mega-Improve Cycles</div>
      </div>
    </div>

    <!-- Charts + Notifications -->
    <div class="grid-2">
      <div class="panel">
        <div class="panel-title">&#128200; Mega-Improve Cycles (24h)</div>
        <div class="chart-container" id="chart-cycles">
          <div class="chart-empty">Chargement...</div>
        </div>
      </div>
      <div class="panel">
        <div class="panel-title">&#128276; Notifications recentes</div>
        <div class="notif-list" id="notif-list">
          <div class="chart-empty">Chargement...</div>
        </div>
      </div>
    </div>

    <!-- Cluster + Report -->
    <div class="grid-2">
      <div class="panel">
        <div class="panel-title">&#9729; Etat du Cluster</div>
        <div class="cluster-grid" id="cluster-grid">
          <div class="chart-empty">Chargement...</div>
        </div>
      </div>
      <div class="panel">
        <div class="panel-title">&#128196; Dernier Rapport Quotidien</div>
        <div class="report-grid" id="report-grid">
          <div class="chart-empty" style="grid-column:span 2">Chargement...</div>
        </div>
      </div>
    </div>
  </div>

  <!-- Iframe pour les sous-dashboards -->
  <iframe id="iframe-view" class="iframe-view"></iframe>
</main>

<script>
// === Utilitaire : création sûre d'éléments DOM ===
// Toutes les insertions de contenu dynamique utilisent textContent
// ou des attributs sûrs (pas d'injection HTML brute depuis des données externes).

function createEl(tag, attrs, children) {
  var el = document.createElement(tag);
  if (attrs) {
    for (var k in attrs) {
      if (k === 'className') el.className = attrs[k];
      else if (k === 'textContent') el.textContent = attrs[k];
      else if (k === 'style') el.setAttribute('style', attrs[k]);
      else if (k.indexOf('data-') === 0) el.setAttribute(k, attrs[k]);
      else el[k] = attrs[k];
    }
  }
  if (children) {
    children.forEach(function(c) { if (c) el.appendChild(c); });
  }
  return el;
}

// === Horloge temps réel ===
function updateClock(){
  var now=new Date();
  var h=String(now.getHours()).padStart(2,'0');
  var m=String(now.getMinutes()).padStart(2,'0');
  var s=String(now.getSeconds()).padStart(2,'0');
  document.getElementById('clock').textContent=h+':'+m+':'+s;
}
setInterval(updateClock,1000);
updateClock();

// === Navigation ===
function showView(name){
  document.getElementById('home-view').className=name==='home'?'active':'';
  document.getElementById('iframe-view').className=name==='home'?'iframe-view':'iframe-view active';
  document.querySelectorAll('.nav-link').forEach(function(l){l.classList.remove('active')});
  if(name==='home')document.querySelector('.nav-link').classList.add('active');
}

function showExternal(url){
  document.getElementById('iframe-view').src=url;
  showView('iframe');
  document.querySelectorAll('.nav-link').forEach(function(l){l.classList.remove('active')});
  event.target.closest('.nav-link').classList.add('active');
}

function showDoc(path){
  document.getElementById('iframe-view').src=path;
  showView('iframe');
  document.querySelectorAll('.nav-link').forEach(function(l){l.classList.remove('active')});
  event.target.closest('.nav-link').classList.add('active');
}

// === Chargement KPIs ===
var refreshCountdown=15;
function fetchKPIs(){
  fetch('/api/kpi').then(function(r){return r.json()}).then(function(data){
    document.getElementById('val-skills').textContent=data.skills;
    document.getElementById('val-commands').textContent=data.commands;
    document.getElementById('val-dominos').textContent=data.dominos;
    document.getElementById('val-services').textContent=data.services;
    document.getElementById('val-gpu').textContent=data.gpu_temp+'\u00B0C';
    document.getElementById('val-cycles').textContent=data.improve_cycles;
    // Colorisation GPU selon la température
    var gpuCard=document.getElementById('kpi-gpu');
    gpuCard.className='kpi-card'+(data.gpu_temp>80?' danger':data.gpu_temp>65?' warning':'');
  }).catch(function(){});
}

// === Chargement chart mega-improve (construction DOM sûre) ===
function fetchChart(){
  fetch('/api/cycles24h').then(function(r){return r.json()}).then(function(data){
    var container=document.getElementById('chart-cycles');
    container.textContent='';
    if(!data.length){
      var empty=createEl('div',{className:'chart-empty',textContent:'Aucun cycle sur 24h'});
      container.appendChild(empty);
      return;
    }
    var maxGaps=Math.max.apply(null,data.map(function(d){return d.gaps||1}).concat([1]));
    data.forEach(function(d){
      var h=Math.max(5,Math.round((d.gaps/maxGaps)*130));
      var bar=createEl('div',{
        className:'chart-bar',
        style:'height:'+h+'px',
        'data-tip':d.hour+' | gaps:'+d.gaps+' | '+d.duration+'s'
      });
      container.appendChild(bar);
    });
  }).catch(function(){});
}

// === Chargement notifications (construction DOM sûre) ===
function fetchNotifications(){
  fetch('/api/notifications').then(function(r){return r.json()}).then(function(data){
    var list=document.getElementById('notif-list');
    list.textContent='';
    if(!data.length){
      list.appendChild(createEl('div',{className:'chart-empty',textContent:'Aucune notification'}));
      return;
    }
    data.slice(0,5).forEach(function(n){
      var dot=createEl('div',{className:'notif-dot '+(n.level||'info')});
      var title=createEl('div',{className:'notif-title',textContent:n.title||''});
      var msg=createEl('div',{className:'notif-msg',textContent:n.message||''});
      var content=createEl('div',{className:'notif-content'},[ title, msg ]);
      var timeEl=createEl('div',{className:'notif-time',textContent:n.time||''});
      var item=createEl('div',{className:'notif-item'},[ dot, content, timeEl ]);
      list.appendChild(item);
    });
  }).catch(function(){});
}

// === Chargement cluster (construction DOM sûre) ===
function fetchCluster(){
  fetch('/api/cluster').then(function(r){return r.json()}).then(function(data){
    var grid=document.getElementById('cluster-grid');
    grid.textContent='';
    var onlineCount=data.filter(function(n){return n.online}).length;
    document.getElementById('cluster-badge').textContent=onlineCount+'/'+data.length;
    data.forEach(function(n){
      var status=n.online?'online':'offline';
      var name=createEl('div',{className:'node-name',textContent:n.name});
      var led=createEl('div',{className:'node-led '+status});
      var host=createEl('div',{className:'node-host',textContent:n.host+':'+n.port});
      var weight=createEl('div',{className:'node-weight',textContent:'w='+n.weight});
      var card=createEl('div',{className:'node-card '+status},[ name, led, host, weight ]);
      grid.appendChild(card);
    });
  }).catch(function(){});
}

// === Chargement rapport (construction DOM sûre) ===
function fetchReport(){
  fetch('/api/report').then(function(r){return r.json()}).then(function(data){
    var grid=document.getElementById('report-grid');
    grid.textContent='';
    var items=[
      ['Date',data.date],
      ['Uptime',data.uptime],
      ['CPU moyen',data.cpu_avg+'%'],
      ['RAM',data.ram_pct+'%'],
      ['Services actifs',''+data.active_services],
      ['Services en echec',''+data.failed_services],
      ['Confiance brain',data.brain_confidence+'%'],
      ['Total skills',''+data.total_skills]
    ];
    items.forEach(function(pair){
      var label=createEl('span',{className:'report-label',textContent:pair[0]});
      var value=createEl('span',{className:'report-value',textContent:pair[1]});
      var row=createEl('div',{className:'report-item'},[ label, value ]);
      grid.appendChild(row);
    });
  }).catch(function(){});
}

// === Auto-refresh 15s ===
function refreshAll(){
  fetchKPIs();fetchChart();fetchNotifications();fetchCluster();fetchReport();
  refreshCountdown=15;
}
refreshAll();
setInterval(function(){
  refreshCountdown--;
  document.getElementById('refresh-timer').textContent=refreshCountdown+'s';
  if(refreshCountdown<=0)refreshAll();
},1000);
</script>
</body>
</html>"""


class PortalHandler(http.server.BaseHTTPRequestHandler):
    """Gestionnaire HTTP pour le portail JARVIS."""

    def log_message(self, format, *args):
        """Log simplifié."""
        pass  # Silencieux en production

    def _send_json(self, data, status=200):
        """Envoie une réponse JSON."""
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_html(self, html, status=200):
        """Envoie une réponse HTML."""
        body = html.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_file(self, filepath, content_type="text/html"):
        """Sert un fichier statique."""
        try:
            with open(filepath, "rb") as f:
                data = f.read()
            self.send_response(200)
            self.send_header("Content-Type", f"{content_type}; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
        except FileNotFoundError:
            self._send_html("<h1>404 — Fichier introuvable</h1>", 404)

    def do_GET(self):
        """Route les requêtes GET."""
        path = urlparse(self.path).path

        # --- Page d'accueil ---
        if path == "/" or path == "/index.html":
            self._send_html(PORTAL_HTML)

        # --- API endpoints ---
        elif path == "/api/kpi":
            self._send_json(get_kpis())

        elif path == "/api/notifications":
            self._send_json(get_notifications(10))

        elif path == "/api/cluster":
            self._send_json(get_cluster_status())

        elif path == "/api/cycles24h":
            self._send_json(get_improve_cycles_24h())

        elif path == "/api/report":
            self._send_json(get_report_summary())

        # --- Fichiers docs ---
        elif path.startswith("/docs/"):
            if path == "/docs/daily_report":
                # Sert le dernier rapport HTML
                reports = sorted(REPORTS_DIR.glob("*.html"))
                if reports:
                    self._send_file(str(reports[-1]))
                else:
                    self._send_html("<h1>Aucun rapport disponible</h1>", 404)
            else:
                filename = path.replace("/docs/", "")
                filepath = DOCS_DIR / filename
                # Sécurité : interdire la traversée de répertoire
                if ".." in filename:
                    self._send_html("<h1>403 Forbidden</h1>", 403)
                else:
                    self._send_file(str(filepath))

        else:
            self._send_html("<h1>404 — Route inconnue</h1>", 404)


def main():
    """Point d'entrée principal."""
    server = http.server.HTTPServer((BIND, PORT), PortalHandler)
    print(f"[JARVIS Portal] Demarrage sur http://127.0.0.1:{PORT}")
    print(f"[JARVIS Portal] Base dir: {BASE_DIR}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[JARVIS Portal] Arret.")
        server.server_close()


if __name__ == "__main__":
    main()
