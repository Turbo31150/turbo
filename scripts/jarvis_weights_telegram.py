#!/usr/bin/env python3
"""JARVIS Weights & Routing — Show dispatch weights + routing table for Telegram.
Usage: python /home/turbo/jarvis-m1-ops/scripts/jarvis_weights_telegram.py
"""
import json, sys, urllib.request

WS = "http://127.0.0.1:9742"

def ws_get(path, timeout=8):
    try:
        with urllib.request.urlopen(f"{WS}{path}", timeout=timeout) as resp:
            return json.loads(resp.read().decode())
    except Exception:
        return None

if __name__ == "__main__":
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    lines = ["JARVIS WEIGHTS & ROUTING"]

    # Section 1: Node weights (from config)
    lines.append("\nNODE WEIGHTS (consensus voting)")
    try:
        sys.path.insert(0, "/home/turbo/jarvis-m1-ops")
        from src.config import JarvisConfig
        cfg = JarvisConfig()
        for node, w in sorted(cfg.node_weights.items(), key=lambda x: -x[1]):
            bar = "#" * int(w * 5)
            lines.append(f"  {node:8s} {w:.1f} {bar}")
    except Exception as e:
        lines.append(f"  Erreur config: {e}")

    # Section 2: Dispatch routing matrix (CLAUDE.md matrice)
    lines.append("\nDISPATCH ROUTING")
    routing = {
        "Code":        "M1 → OL1 → M2",
        "Bug fix":     "M1 → OL1 → M2",
        "Architecture":"M1 → OL1 → M2",
        "Raisonnement":"M1 → M2 → M3",
        "Trading":     "OL1(web) → M1",
        "Question":    "OL1 → M1",
        "Web search":  "OL1(minimax) → GEMINI",
        "Consensus":   "M1+M2+OL1+M3+GEMINI+CLAUDE",
    }
    for task, route in routing.items():
        lines.append(f"  {task:14s} → {route}")

    # Section 3: Self-improve weight adjustments
    lines.append("\nSELF-IMPROVE ADJUSTMENTS")
    si = ws_get("/api/self-improve/status")
    if si and isinstance(si, dict):
        cycles = si.get("cycles", 0)
        lines.append(f"  {cycles} cycles completed")
        last = si.get("last_report", {})
        actions = last.get("actions", [])
        weight_actions = [a for a in actions if a.get("type") == "weight_adjust"]
        if weight_actions:
            for a in weight_actions[:5]:
                lines.append(f"  {a.get('target','?')}: {a.get('desc','')[:60]}")
        else:
            lines.append("  No recent weight adjustments")
    else:
        lines.append("  Self-improve unavailable")

    # Section 4: Circuit breaker status
    lines.append("\nCIRCUIT BREAKERS")
    try:
        from src.adaptive_router import AdaptiveRouter
        router = AdaptiveRouter.__new__(AdaptiveRouter)
        if hasattr(router, '_breakers'):
            for node, cb in router._breakers.items():
                state = "OPEN" if cb.get("open") else "CLOSED"
                fails = cb.get("failures", 0)
                lines.append(f"  {node}: {state} (fails={fails})")
        else:
            lines.append("  No circuit breaker data (router not initialized)")
    except Exception:
        lines.append("  Circuit breakers unavailable (router not running)")

    # Section 5: Commander routing
    lines.append("\nCOMMANDER ROUTING")
    try:
        cfg = JarvisConfig()
        for task, agents in sorted(cfg.commander_routing.items()):
            parts = [f"{a['ia']}({a['role']})" for a in agents]
            lines.append(f"  {task:12s} → {' + '.join(parts)}")
    except Exception:
        lines.append("  Commander routing unavailable")

    print("\n".join(lines))
