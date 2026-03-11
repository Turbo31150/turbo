"""JARVIS Boot & Diagnostic — Script autonome pour Telegram.
Lance via: python F:/BUREAU/turbo/scripts/jarvis_boot_telegram.py
Retourne un rapport JSON compact."""

import json, subprocess, time, sqlite3, os, sys

TIMEOUT = 5
DATA = "F:/BUREAU/turbo/data"

def run(cmd, timeout=TIMEOUT):
    try:
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
        return r.stdout.strip() if r.returncode == 0 else None
    except:
        return None

def check_node(name, url):
    r = run(f'curl -s --max-time 3 {url}')
    if not r:
        return {"name": name, "status": "OFFLINE"}
    try:
        d = json.loads(r)
        if "/api/tags" in url:  # Ollama
            return {"name": name, "status": "OK", "models": len(d.get("models", []))}
        else:  # LM Studio (/api/v1/models)
            models = d.get("data", d.get("models", []))
            loaded = [m for m in models if m.get("state") == "loaded" or m.get("loaded_instances")]
            return {"name": name, "status": "OK", "loaded": len(loaded) if loaded else len(models), "available": len(models)}
    except:
        pass
    return {"name": name, "status": "OK"}

def check_gpu():
    r = run("nvidia-smi --query-gpu=name,temperature.gpu,memory.used,memory.total,utilization.gpu --format=csv,noheader")
    if not r:
        return []
    gpus = []
    for line in r.strip().split("\n"):
        parts = [p.strip() for p in line.split(",")]
        if len(parts) >= 5:
            gpus.append({
                "name": parts[0],
                "temp": parts[1].replace(" ", ""),
                "vram_used": parts[2].replace(" ", ""),
                "vram_total": parts[3].replace(" ", ""),
                "util": parts[4].replace(" ", "")
            })
    return gpus

def check_ports():
    r = run('netstat -ano | findstr "LISTENING"')
    if not r:
        return {}
    ports = {9742: False, 18800: False, 8080: False, 11434: False, 1234: False}
    for line in r.split("\n"):
        for p in ports:
            if f":{p} " in line or f":{p}\t" in line:
                ports[p] = True
    return ports

def check_db(name, path):
    if not os.path.exists(path):
        return {"name": name, "status": "MISSING"}
    try:
        conn = sqlite3.connect(path)
        cur = conn.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [r[0] for r in cur.fetchall()]
        total = 0
        for t in tables:
            try:
                cur.execute(f"SELECT COUNT(*) FROM [{t}]")
                total += cur.fetchone()[0]
            except:
                pass
        conn.close()
        size_kb = os.path.getsize(path) // 1024
        return {"name": name, "status": "OK", "tables": len(tables), "rows": total, "size_kb": size_kb}
    except Exception as e:
        return {"name": name, "status": f"ERROR: {e}"}

def grade(nodes, gpus, ports):
    score = 100
    issues = []
    # Nodes
    for n in nodes:
        if n["status"] == "OFFLINE":
            if n["name"] in ("M1", "OL1"):
                score -= 20
                issues.append(f"CRITICAL: {n['name']} OFFLINE")
            else:
                score -= 5
                issues.append(f"WARNING: {n['name']} OFFLINE")
        elif n.get("loaded", 0) == 0 and n["name"] == "M1":
            score -= 15
            issues.append("WARNING: M1 aucun modele charge")
    # GPU
    for g in gpus:
        temp = int(g["temp"].replace("C", "").replace("°", ""))
        if temp >= 85:
            score -= 10
            issues.append(f"CRITICAL: {g['name']} {temp}C")
        elif temp >= 75:
            score -= 3
            issues.append(f"WARNING: {g['name']} {temp}C")
    # Services
    svc_names = {9742: "WS", 18800: "Proxy", 8080: "Dashboard", 11434: "Ollama", 1234: "M1"}
    for p, up in ports.items():
        if not up:
            score -= 5
            issues.append(f"DOWN: {svc_names.get(p, p)} :{p}")
    # Grade
    if score >= 95: g = "A+"
    elif score >= 85: g = "A"
    elif score >= 70: g = "B"
    elif score >= 50: g = "C"
    else: g = "D"
    return g, score, issues

if __name__ == "__main__":
    t0 = time.time()

    # Cluster
    nodes = [
        check_node("M1", "http://127.0.0.1:1234/api/v1/models"),
        check_node("OL1", "http://127.0.0.1:11434/api/tags"),
        check_node("M2", "http://192.168.1.26:1234/api/v1/models"),
        check_node("M3", "http://192.168.1.113:1234/api/v1/models"),
    ]

    # GPU
    gpus = check_gpu()

    # Ports
    ports = check_ports()

    # DBs
    dbs = [
        check_db("etoile", f"{DATA}/etoile.db"),
        check_db("jarvis", f"{DATA}/jarvis.db"),
        check_db("sniper", f"{DATA}/sniper.db"),
    ]

    # Grade
    g, score, issues = grade(nodes, gpus, ports)
    elapsed = round(time.time() - t0, 1)

    # Output
    report = {
        "grade": g,
        "score": score,
        "issues": issues,
        "nodes": nodes,
        "gpus": gpus,
        "services": {k: v for k, v in sorted(ports.items())},
        "databases": dbs,
        "elapsed_s": elapsed
    }

    # Human-readable summary
    lines = [f"JARVIS DIAGNOSTIC — Grade {g} ({score}/100) — {elapsed}s"]
    lines.append("")
    lines.append("CLUSTER:")
    for n in nodes:
        extra = ""
        if "loaded" in n: extra = f" ({n['loaded']} loaded, {n['available']} available)"
        elif "models" in n: extra = f" ({n['models']} models)"
        lines.append(f"  {n['name']}: {n['status']}{extra}")
    lines.append("")
    lines.append("GPU:")
    for g in gpus:
        lines.append(f"  {g['name']}: {g['temp']}C | {g['vram_used']}/{g['vram_total']} | {g['util']}")
    lines.append("")
    lines.append("SERVICES:")
    svc_names = {1234: "M1 LMStudio", 8080: "Dashboard", 9742: "WS FastAPI", 11434: "Ollama", 18800: "Proxy"}
    for p in sorted(ports):
        status = "UP" if ports[p] else "DOWN"
        lines.append(f"  :{p} {svc_names.get(p,'')} — {status}")
    lines.append("")
    lines.append("DATABASES:")
    for d in dbs:
        if d["status"] == "OK":
            lines.append(f"  {d['name']}: {d['tables']}t, {d['rows']}r, {d['size_kb']}KB")
        else:
            lines.append(f"  {d['name']}: {d['status']}")
    if issues:
        lines.append("")
        lines.append("ISSUES:")
        for i in issues:
            lines.append(f"  - {i}")

    print("\n".join(lines))
