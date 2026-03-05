#!/usr/bin/env python3
"""
api_monitor.py

Moniteur d'APIs pour le cluster JARVIS.

Fonctionnalités:
- Vérifie la latence (HTTP GET) des endpoints du cluster (M1, M2, M3, OL1, Gateway).
- Vérifie la disponibilité d'une base SQLite locale pour chaque nœud (optionnel).
- Mode "--once" : exécute une vérification unique.
- Mode "--loop" : boucle indéfiniment (intervalle configurable).
- Flags "--endpoints" et "--latency" permettent de sélectionner les actions.

Utilise uniquement la bibliothèque standard Python.
"""

import argparse
import time
import sys
import json
import sqlite3
from urllib.parse import urlparse

# Import requests si disponible, sinon fallback to urllib
try:
    import requests
except ImportError:
    requests = None
    import urllib.request
    import urllib.error
    import urllib.parse

# Configuration des endpoints du cluster
ENDPOINTS = {
    "M1": "http://10.5.0.2:1234/v1/chat/completions",
    "M2": "http://192.168.1.26:1234/v1/chat/completions",
    "M3": "http://192.168.1.113:1234/v1/chat/completions",
    "OL1": "http://127.0.0.1:11434/api/chat",
    "Gateway": "http://127.0.0.1:8000/health",
}

# Chemins SQLite (exemple, à adapter)
SQLITE_PATHS = {
    "M1": "C:/path/to/m1.db",
    "M2": "C:/path/to/m2.db",
    "M3": "C:/path/to/m3.db",
    "OL1": "C:/path/to/ol1.db",
    "Gateway": "C:/path/to/gateway.db",
}


def check_latency(url: str, timeout: float = 3.0) -> float:
    """Retourne la latence en secondes, ou None en cas d'échec."""
    start = time.time()
    try:
        if requests:
            r = requests.get(url, timeout=timeout)
            r.raise_for_status()
        else:
            with urllib.request.urlopen(url, timeout=timeout) as resp:
                resp.read(1)
        return time.time() - start
    except Exception:
        return None


def check_sqlite(path: str) -> bool:
    """Teste l'accès à une base SQLite en exécutant SELECT 1."""
    try:
        conn = sqlite3.connect(path)
        cur = conn.cursor()
        cur.execute("SELECT 1")
        cur.fetchone()
        conn.close()
        return True
    except Exception:
        return False


def list_endpoints():
    for name, url in ENDPOINTS.items():
        print(f"{name}: {url}")


def monitor_once(args):
    results = {}
    if args.endpoints:
        results["endpoints"] = list(ENDPOINTS.keys())
        print("Endpoints disponibles:")
        list_endpoints()
    if args.latency:
        latencies = {}
        print("\nLatence des endpoints (seconds):")
        for name, url in ENDPOINTS.items():
            lat = check_latency(url)
            latencies[name] = lat
            print(f"  {name}: {lat if lat is not None else 'FAIL'}")
        results["latency"] = latencies
    if args.sqlite:
        sqlite_status = {}
        print("\nVérification des bases SQLite:")
        for name, path in SQLITE_PATHS.items():
            ok = check_sqlite(path)
            sqlite_status[name] = ok
            print(f"  {name}: {'OK' if ok else 'FAIL'}")
        results["sqlite"] = sqlite_status
    return results


def monitor_loop(args, interval: int = 60):
    while True:
        print("\n=== Vérification du cluster (" + time.strftime('%Y-%m-%d %H:%M:%S') + ") ===")
        monitor_once(args)
        print(f"\nAttente {interval}s avant la prochaine vérification...\n")
        time.sleep(interval)


def parse_args():
    parser = argparse.ArgumentParser(description="Moniteur d'APIs et SQLite du cluster JARVIS.")
    parser.add_argument("--once", action="store_true", help="Effectuer une vérification unique et quitter.")
    parser.add_argument("--loop", action="store_true", help="Boucler indéfiniment (intervalle 60s).")
    parser.add_argument("--endpoints", action="store_true", help="Lister les endpoints configurés.")
    parser.add_argument("--latency", action="store_true", help="Mesurer la latence HTTP des endpoints.")
    parser.add_argument("--sqlite", action="store_true", help="Vérifier l'accès aux bases SQLite.")
    parser.add_argument("--interval", type=int, default=60, help="Intervalle (s) entre les vérifications en mode --loop.")
    return parser.parse_args()


def main():
    args = parse_args()
    if not any([args.endpoints, args.latency, args.sqlite]):
        # Par défaut, faire tout
        args.endpoints = args.latency = args.sqlite = True
    if args.once:
        monitor_once(args)
    elif args.loop:
        monitor_loop(args, args.interval)
    else:
        # Si aucun mode spécifié, on exécute une fois.
        monitor_once(args)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(0)
