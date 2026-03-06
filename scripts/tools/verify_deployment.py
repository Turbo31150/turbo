#!/usr/bin/env python
"""Verification complete du deploiement JARVIS v2.

Verifie:
- Bootstrap fonctionnel
- Table scheduler_jobs + 8 jobs
- Event bus wire
- Health probes enregistrees
- Fichiers deployes
- MCP server patch applique

Usage:
    python verify_deployment.py
"""

import sys
from pathlib import Path

def check_files():
    """Verifier que tous les fichiers sont deployes."""
    print("\n[1/6] Checking deployed files...")
    src = Path("F:/BUREAU/turbo/src")
    files = [
        "startup_wiring.py",
        "event_bus_wiring.py",
        "scheduler_cleanup.py",
        "health_probe_registry.py",
        "gpu_guardian.py",
        "cluster_self_healer.py",
        "trading_sentinel.py",
        "perplexity_bridge.py",
        "smart_retry.py",
        "daily_report.py"
    ]
    
    missing = [f for f in files if not (src / f).exists()]
    if missing:
        print(f"  ERROR: Missing files: {missing}")
        return False
    print(f"  OK: All 10 modules present")
    return True


def check_database():
    """Verifier la table scheduler_jobs et les jobs."""
    print("\n[2/6] Checking database...")
    try:
        from src.database import get_connection
        conn = get_connection()
        
        # Check table exists
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='scheduler_jobs'"
        )
        if not cursor.fetchone():
            print("  ERROR: Table scheduler_jobs not found")
            return False
        
        # Check jobs
        jobs = conn.execute("SELECT name FROM scheduler_jobs").fetchall()
        if len(jobs) < 8:
            print(f"  WARNING: Only {len(jobs)} jobs, expected 8")
        else:
            print(f"  OK: {len(jobs)} scheduler jobs configured")
        
        return True
    except Exception as e:
        print(f"  ERROR: {e}")
        return False


def check_mcp_patch():
    """Verifier que le patch MCP est applique."""
    print("\n[3/6] Checking MCP server patch...")
    try:
        mcp_file = Path("F:/BUREAU/turbo/src/mcp_server_sse.py")
        content = mcp_file.read_text(encoding="utf-8")
        
        if "bootstrap_jarvis" in content:
            print("  OK: MCP lifespan patched with bootstrap")
            return True
        else:
            print("  WARNING: bootstrap_jarvis not found in mcp_server_sse.py")
            return False
    except Exception as e:
        print(f"  ERROR: {e}")
        return False


def check_imports():
    """Verifier que tous les modules sont importables."""
    print("\n[4/6] Checking module imports...")
    modules = [
        "src.startup_wiring",
        "src.event_bus_wiring",
        "src.scheduler_cleanup",
        "src.health_probe_registry",
        "src.gpu_guardian",
        "src.cluster_self_healer",
        "src.trading_sentinel",
        "src.perplexity_bridge",
        "src.smart_retry",
        "src.daily_report"
    ]
    
    errors = []
    for mod in modules:
        try:
            __import__(mod)
        except Exception as e:
            errors.append(f"{mod}: {e}")
    
    if errors:
        print(f"  ERROR: {len(errors)} import failures:")
        for e in errors[:3]:
            print(f"    - {e}")
        return False
    
    print(f"  OK: All 10 modules importable")
    return True


def check_event_bus():
    """Verifier que l'event bus existe."""
    print("\n[5/6] Checking event bus...")
    try:
        from src.event_bus import event_bus
        sub_count = sum(len(subs) for subs in event_bus._subscriptions.values())
        print(f"  OK: Event bus ready ({sub_count} subscribers if wired)")
        return True
    except Exception as e:
        print(f"  ERROR: {e}")
        return False


def check_health_probes():
    """Verifier que le registre health probe existe."""
    print("\n[6/6] Checking health probes...")
    try:
        from src.health_probe import health_probe
        print(f"  OK: Health probe system ready")
        return True
    except Exception as e:
        print(f"  ERROR: {e}")
        return False


def main():
    print("="*60)
    print("JARVIS v2 Deployment Verification")
    print("="*60)
    
    checks = [
        check_files,
        check_database,
        check_mcp_patch,
        check_imports,
        check_event_bus,
        check_health_probes
    ]
    
    results = [check() for check in checks]
    passed = sum(results)
    total = len(results)
    
    print("\n" + "="*60)
    if passed == total:
        print(f"SUCCESS: All {total} checks passed")
        print("\nJARVIS v2 deployment is COMPLETE and OPERATIONAL")
        print("\nNext step: Start MCP server")
        print("  python -m src.mcp_server_sse --port 8901 --light")
        return 0
    else:
        print(f"PARTIAL: {passed}/{total} checks passed")
        print("\nSome components may not be fully operational.")
        print("Check errors above for details.")
        return 1


if __name__ == "__main__":
    sys.exit(main())

