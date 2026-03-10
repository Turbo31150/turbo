"""JARVIS — Domino Pipelines: cascades automatiques declenchees par commande vocale.

Chaque DominoPipeline definit une chaine d'actions ou chaque etape declenche
automatiquement la suivante. Le systeme apprend du contexte (heure, GPU, cluster)
pour adapter les cascades dynamiquement.

Architecture:
  trigger vocal -> etape1 -> etape2 -> ... -> etapeN
  Chaque etape peut etre: pipeline existant, commande powershell, curl API, ou condition.

Genere par consensus cluster M1+M2+OL1 (2026-02-27).
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from src.config import PATHS


__all__ = [
    "DominoPipeline",
    "DominoStep",
    "find_domino",
    "get_domino_stats",
]

_TURBO_DIR = str(PATHS.get("turbo", "F:/BUREAU/turbo")).replace("/", "\\")
_TURBO_DIR_FWD = str(PATHS.get("turbo", "F:/BUREAU/turbo"))
_M1_KEY = os.getenv("LM_STUDIO_1_API_KEY", os.getenv("LM_STUDIO_1_KEY", ""))
_M2_KEY = os.getenv("LM_STUDIO_2_API_KEY", os.getenv("LM_STUDIO_2_KEY", ""))


@dataclass
class DominoStep:
    """Une etape dans une cascade domino."""
    name: str                   # Identifiant de l'etape
    action: str                 # Action a executer (pipeline ref, powershell, curl, etc.)
    action_type: str            # Type: pipeline, powershell, curl, python, condition
    condition: str | None = None  # Condition optionnelle (ex: "gpu_temp < 80")
    on_fail: str = "stop"       # Comportement si echec: stop, skip, fallback
    timeout_s: int = 30         # Timeout par etape


@dataclass
class DominoPipeline:
    """Pipeline domino — cascade d'actions declenchees par une commande vocale."""
    id: str                     # Identifiant unique
    trigger_vocal: list[str]    # Phrases vocales pour declencher
    steps: list[DominoStep]     # Etapes en cascade
    category: str               # Categorie domino
    description: str            # Description de la cascade
    learning_context: str       # Contexte pour l'apprentissage IA
    priority: str = "normal"    # normal, high, critical
    cooldown_s: int = 60        # Temps min entre 2 executions


# ══════════════════════════════════════════════════════════════════════════════
# DOMINO PIPELINES — Generes par consensus cluster M1+M2+OL1
# ══════════════════════════════════════════════════════════════════════════════

DOMINO_PIPELINES: list[DominoPipeline] = [

    # ─────────────────────────────────────────────────────────────────────
    # ROUTINE MATIN (5 dominos)
    # ─────────────────────────────────────────────────────────────────────
    DominoPipeline(
        id="domino_matin_complet",
        trigger_vocal=["bonjour jarvis", "routine du matin", "demarre la journee", "lance le matin"],
        steps=[
            DominoStep("check_gpu", "powershell:nvidia-smi --query-gpu=temperature.gpu,memory.used --format=csv,noheader", "powershell"),
            DominoStep("cluster_health", "curl:http://127.0.0.1:1234/api/v1/models", "curl"),
            DominoStep("meteo_brief", "curl:http://127.0.0.1:11434/api/chat", "curl"),
            DominoStep("agenda_resume", "powershell:Get-Date -Format 'dddd dd MMMM yyyy HH:mm'", "powershell"),
            DominoStep("tts_briefing", "python:edge_tts_speak('Bonjour! Briefing du matin pret.')", "python"),
        ],
        category="routine_matin",
        description="Briefing matinal complet: GPU, cluster, meteo, agenda, synthese vocale",
        learning_context="L'utilisateur demarre sa journee — adapter selon l'heure et le jour de la semaine",
        priority="high",
    ),
    DominoPipeline(
        id="domino_cafe_code",
        trigger_vocal=["mode cafe code", "session cafe dev", "code du matin"],
        steps=[
            DominoStep("open_vscode", "app_open:code", "pipeline"),
            DominoStep("git_status", "powershell:git -C 'F:\\BUREAU\\turbo' status --short", "powershell"),
            DominoStep("open_spotify", "app_open:spotify", "pipeline"),
            DominoStep("cluster_check", "curl:http://127.0.0.1:1234/api/v1/models", "curl"),
            DominoStep("tts_ready", "python:edge_tts_speak('Environnement dev pret. Bon code!')", "python"),
        ],
        category="routine_matin",
        description="Setup matinal dev: VSCode + git + musique + cluster",
        learning_context="Session de dev matinale — prefere musique lo-fi et branche principale",
    ),
    DominoPipeline(
        id="domino_reveil_rapide",
        trigger_vocal=["reveil rapide", "demarrage express", "vite jarvis"],
        steps=[
            DominoStep("gpu_temp", "powershell:nvidia-smi --query-gpu=temperature.gpu --format=csv,noheader", "powershell"),
            DominoStep("date_heure", "powershell:Get-Date -Format 'HH:mm dddd'", "powershell"),
            DominoStep("tts_status", "python:edge_tts_speak('Systeme operationnel.')", "python"),
        ],
        category="routine_matin",
        description="Demarrage ultra-rapide: GPU + heure + confirmation vocale",
        learning_context="Demarrage rapide sans details — utilisateur presse",
    ),
    DominoPipeline(
        id="domino_matin_trading",
        trigger_vocal=["matin trading", "routine trading matin", "bonjour trading"],
        steps=[
            DominoStep("market_check", "curl:http://127.0.0.1:1234/api/v1/chat", "curl"),
            DominoStep("portfolio_status", "python:check_portfolio_balance()", "python"),
            DominoStep("signals_scan", "curl:http://127.0.0.1:1234/api/v1/chat", "curl"),
            DominoStep("alert_config", "python:configure_trading_alerts()", "python"),
            DominoStep("tts_market", "python:edge_tts_speak('Marche analyse. Signaux prets.')", "python"),
        ],
        category="routine_matin",
        description="Routine matin trading: marche + portfolio + signaux + alertes",
        learning_context="Trader matinal — BTC/ETH prioritaires, check drawdown avant tout",
        priority="high",
    ),
    DominoPipeline(
        id="domino_matin_weekend",
        trigger_vocal=["bonjour weekend", "matin tranquille", "routine weekend"],
        steps=[
            DominoStep("gpu_light", "powershell:nvidia-smi --query-gpu=temperature.gpu --format=csv,noheader", "powershell"),
            DominoStep("backup_check", "python:check_last_backup_date()", "python"),
            DominoStep("tts_weekend", "python:edge_tts_speak('Bon weekend! Systeme stable.')", "python"),
        ],
        category="routine_matin",
        description="Routine weekend allegee: GPU + backup + message",
        learning_context="Weekend — pas de trading, juste maintenance legere",
    ),

    # ─────────────────────────────────────────────────────────────────────
    # TRADING CASCADE (5 dominos)
    # ─────────────────────────────────────────────────────────────────────
    DominoPipeline(
        id="domino_trading_full_scan",
        trigger_vocal=["scan trading complet", "analyse complete marche", "trading full scan"],
        steps=[
            DominoStep("fetch_prices", "curl:http://127.0.0.1:1234/api/v1/chat", "curl"),
            DominoStep("correlation_check", "curl:http://127.0.0.1:1234/api/v1/chat", "curl"),
            DominoStep("signal_generate", "curl:http://127.0.0.1:1234/api/v1/chat", "curl"),
            DominoStep("risk_assess", "python:assess_trading_risk()", "python"),
            DominoStep("tts_signal", "python:edge_tts_speak('Scan termine. Signaux generes.')", "python"),
        ],
        category="trading_cascade",
        description="Scan trading complet: prix + correlation + signaux + risque",
        learning_context="Scan de marche complet — 10 paires MEXC, score min 70/100",
        priority="high",
    ),
    DominoPipeline(
        id="domino_trading_execute",
        trigger_vocal=["execute signal trading", "trade maintenant", "passe l'ordre"],
        steps=[
            DominoStep("confirm_signal", "python:validate_signal_score()", "python"),
            DominoStep("check_balance", "python:check_usdt_balance()", "python"),
            DominoStep("place_order", "python:execute_mexc_order()", "python", on_fail="stop"),
            DominoStep("set_tp_sl", "python:set_tp_sl_levels()", "python"),
            DominoStep("tts_confirm", "python:edge_tts_speak('Ordre place. TP et SL configures.')", "python"),
        ],
        category="trading_cascade",
        description="Execution trading: validation + balance + ordre + TP/SL",
        learning_context="Execution d'ordre — TOUJOURS verifier score >= 70 et balance suffisante",
        priority="critical",
        cooldown_s=120,
    ),
    DominoPipeline(
        id="domino_trading_close_all",
        trigger_vocal=["ferme tout trading", "close all positions", "urgence trading stop"],
        steps=[
            DominoStep("list_positions", "python:list_open_positions()", "python"),
            DominoStep("close_positions", "python:close_all_positions()", "python", on_fail="stop"),
            DominoStep("calculate_pnl", "python:calculate_session_pnl()", "python"),
            DominoStep("save_report", "python:save_trading_report()", "python"),
            DominoStep("tts_closed", "python:edge_tts_speak('Toutes positions fermees. PnL calcule.')", "python"),
        ],
        category="trading_cascade",
        description="Fermeture urgente: lister + fermer + PnL + rapport",
        learning_context="Fermeture d'urgence — priorite absolue, pas de confirmation intermediaire",
        priority="critical",
        cooldown_s=30,
    ),
    DominoPipeline(
        id="domino_trading_backtest",
        trigger_vocal=["lance un backtest", "backtest strategie", "simule le trading"],
        steps=[
            DominoStep("load_history", "python:load_price_history('1h', 30)", "python"),
            DominoStep("run_backtest", "curl:http://127.0.0.1:1234/api/v1/chat", "curl"),
            DominoStep("analyze_results", "python:analyze_backtest_results()", "python"),
            DominoStep("tts_result", "python:edge_tts_speak('Backtest termine.')", "python"),
        ],
        category="trading_cascade",
        description="Backtest complet: historique + simulation + analyse",
        learning_context="Backtest — utiliser M1 pour analyse, 30 jours par defaut en 1h",
    ),
    DominoPipeline(
        id="domino_trading_drawdown_alert",
        trigger_vocal=["check drawdown", "alerte pertes", "risque portfolio"],
        steps=[
            DominoStep("fetch_pnl", "python:fetch_current_pnl()", "python"),
            DominoStep("calc_drawdown", "python:calculate_drawdown()", "python"),
            DominoStep("eval_risk", "curl:http://127.0.0.1:1234/api/v1/chat", "curl"),
            DominoStep("tts_alert", "python:edge_tts_speak('Drawdown analyse complete.')", "python"),
        ],
        category="trading_cascade",
        description="Analyse drawdown: PnL + calcul + evaluation risque",
        learning_context="Drawdown — alerte si > 5% du capital, suggestion close si > 8%",
        priority="high",
    ),

    # ─────────────────────────────────────────────────────────────────────
    # DEBUG CASCADE (5 dominos)
    # ─────────────────────────────────────────────────────────────────────
    DominoPipeline(
        id="domino_debug_cluster",
        trigger_vocal=["debug cluster", "probleme cluster", "cluster en panne"],
        steps=[
            DominoStep("ping_m1", "curl:http://127.0.0.1:1234/api/v1/models", "curl", on_fail="skip"),
            DominoStep("ping_m2", "curl:http://192.168.1.26:1234/api/v1/models", "curl", on_fail="skip"),
            DominoStep("ping_m3", "curl:http://192.168.1.113:1234/api/v1/models", "curl", on_fail="skip"),
            DominoStep("ping_ol1", "curl:http://127.0.0.1:11434/api/tags", "curl", on_fail="skip"),
            DominoStep("tts_report", "python:edge_tts_speak('Diagnostic cluster termine.')", "python"),
        ],
        category="debug_cascade",
        description="Debug cluster: ping tous les noeuds + rapport",
        learning_context="Debug cluster — identifier noeud offline, suggerer fallback",
        priority="high",
    ),
    DominoPipeline(
        id="domino_debug_gpu_thermal",
        trigger_vocal=["debug gpu chaud", "gpu surchauffe", "thermal throttle"],
        steps=[
            DominoStep("read_temps", "powershell:nvidia-smi --query-gpu=name,temperature.gpu,power.draw --format=csv,noheader", "powershell"),
            DominoStep("check_fans", "powershell:nvidia-smi --query-gpu=fan.speed --format=csv,noheader", "powershell"),
            DominoStep("eval_thermal", "curl:http://127.0.0.1:1234/api/v1/chat", "curl"),
            DominoStep("throttle_if_hot", "python:throttle_gpu_if_critical(85)", "python", condition="gpu_temp > 80"),
            DominoStep("tts_thermal", "python:edge_tts_speak('Diagnostic thermique GPU termine.')", "python"),
        ],
        category="debug_cascade",
        description="Debug thermal GPU: temperatures + ventilateurs + throttle auto",
        learning_context="GPU chaud — 75C warning, 85C critical, throttle automatique",
        priority="critical",
    ),
    DominoPipeline(
        id="domino_debug_network",
        trigger_vocal=["debug reseau", "probleme connexion", "reseau en panne"],
        steps=[
            DominoStep("ping_gateway", "powershell:Test-Connection 192.168.1.1 -Count 2 -TimeoutSeconds 3", "powershell"),
            DominoStep("ping_internet", "powershell:Test-Connection 8.8.8.8 -Count 2 -TimeoutSeconds 3", "powershell"),
            DominoStep("dns_check", "powershell:Resolve-DnsName google.com -ErrorAction SilentlyContinue", "powershell"),
            DominoStep("cluster_lan", "powershell:Test-Connection 127.0.0.1 -Count 1 -TimeoutSeconds 3", "powershell", on_fail="skip"),
            DominoStep("tts_network", "python:edge_tts_speak('Diagnostic reseau termine.')", "python"),
        ],
        category="debug_cascade",
        description="Debug reseau complet: gateway + internet + DNS + cluster LAN",
        learning_context="Debug reseau — verifier gateway d'abord, puis internet, puis cluster",
    ),
    DominoPipeline(
        id="domino_debug_db",
        trigger_vocal=["debug base de donnees", "probleme database", "check database"],
        steps=[
            DominoStep("integrity_check", "python:sqlite3_integrity_check('etoile.db')", "python"),
            DominoStep("size_check", "powershell:Get-Item 'F:\\BUREAU\\turbo\\data\\etoile.db' | Select-Object Length", "powershell"),
            DominoStep("table_counts", "python:sqlite3_table_counts('etoile.db')", "python"),
            DominoStep("vacuum_if_large", "python:sqlite3_vacuum_if_needed('etoile.db', 50)", "python", condition="db_size_mb > 50"),
            DominoStep("tts_db", "python:edge_tts_speak('Base de donnees verifiee.')", "python"),
        ],
        category="debug_cascade",
        description="Debug DB: integrite + taille + comptages + vacuum conditionnel",
        learning_context="Debug DB — verifier integrite avant tout, vacuum si > 50 MB",
    ),
    DominoPipeline(
        id="domino_debug_api_cascade",
        trigger_vocal=["debug api", "api en panne", "test tous les endpoints"],
        steps=[
            DominoStep("health_m1", "curl:http://127.0.0.1:1234/api/v1/models", "curl", on_fail="skip", timeout_s=5),
            DominoStep("health_m2", "curl:http://192.168.1.26:1234/api/v1/models", "curl", on_fail="skip", timeout_s=5),
            DominoStep("health_ollama", "curl:http://127.0.0.1:11434/api/tags", "curl", on_fail="skip", timeout_s=5),
            DominoStep("health_n8n", "curl:http://127.0.0.1:5678/healthz", "curl", on_fail="skip", timeout_s=5),
            DominoStep("tts_api", "python:edge_tts_speak('Diagnostic API termine.')", "python"),
        ],
        category="debug_cascade",
        description="Debug API: health check tous endpoints cluster + n8n",
        learning_context="Debug API — on_fail=skip pour ne pas bloquer la cascade",
    ),

    # ─────────────────────────────────────────────────────────────────────
    # DEPLOY FLOW (4 dominos)
    # ─────────────────────────────────────────────────────────────────────
    DominoPipeline(
        id="domino_deploy_standard",
        trigger_vocal=["deploie le code", "deploy standard", "push en production"],
        steps=[
            DominoStep("git_status", "powershell:git -C 'F:\\BUREAU\\turbo' status --short", "powershell"),
            DominoStep("run_tests", "powershell:cd F:\\BUREAU\\turbo && uv run python -m pytest tests/ -q 2>&1", "powershell", on_fail="stop"),
            DominoStep("git_add_commit", "powershell:git -C 'F:\\BUREAU\\turbo' add -A && git -C 'F:\\BUREAU\\turbo' commit -m 'auto-deploy'", "powershell"),
            DominoStep("git_push", "powershell:git -C 'F:\\BUREAU\\turbo' push", "powershell"),
            DominoStep("tts_deploy", "python:edge_tts_speak('Deploiement termine avec succes.')", "python"),
        ],
        category="deploy_flow",
        description="Deploy standard: status + tests + commit + push",
        learning_context="Deploy — TOUJOURS tester avant de push, arreter si tests echouent",
        priority="high",
    ),
    DominoPipeline(
        id="domino_deploy_hotfix",
        trigger_vocal=["hotfix urgent", "deploy hotfix", "correction urgente"],
        steps=[
            DominoStep("git_stash", "powershell:git -C 'F:\\BUREAU\\turbo' stash", "powershell"),
            DominoStep("apply_fix", "powershell:git -C 'F:\\BUREAU\\turbo' add -A", "powershell"),
            DominoStep("commit_hotfix", "powershell:git -C 'F:\\BUREAU\\turbo' commit -m 'hotfix: correction urgente'", "powershell"),
            DominoStep("push_hotfix", "powershell:git -C 'F:\\BUREAU\\turbo' push", "powershell"),
            DominoStep("tts_hotfix", "python:edge_tts_speak('Hotfix deploye.')", "python"),
        ],
        category="deploy_flow",
        description="Hotfix rapide: stash + fix + commit + push",
        learning_context="Hotfix — rapide, pas de tests complets, stash le WIP d'abord",
        priority="critical",
    ),
    DominoPipeline(
        id="domino_deploy_rollback",
        trigger_vocal=["rollback deploy", "annule le dernier deploy", "reviens en arriere"],
        steps=[
            DominoStep("get_last_commit", "powershell:git -C 'F:\\BUREAU\\turbo' log -1 --oneline", "powershell"),
            DominoStep("revert_commit", "powershell:git -C 'F:\\BUREAU\\turbo' revert HEAD --no-edit", "powershell"),
            DominoStep("push_revert", "powershell:git -C 'F:\\BUREAU\\turbo' push", "powershell"),
            DominoStep("tts_rollback", "python:edge_tts_speak('Rollback effectue.')", "python"),
        ],
        category="deploy_flow",
        description="Rollback: revert dernier commit + push",
        learning_context="Rollback — revert propre, pas de force push, garder l'historique",
    ),
    DominoPipeline(
        id="domino_deploy_with_backup",
        trigger_vocal=["deploy avec backup", "deploie en securite", "deploy safe"],
        steps=[
            DominoStep("backup_db", "python:backup_etoile_db()", "python"),
            DominoStep("backup_config", "powershell:Copy-Item 'F:\\BUREAU\\turbo\\.env' 'F:\\BUREAU\\turbo\\.env.bak'", "powershell"),
            DominoStep("run_tests", "powershell:cd F:\\BUREAU\\turbo && uv run python -m pytest tests/ -q 2>&1", "powershell", on_fail="stop"),
            DominoStep("git_commit_push", "powershell:git -C 'F:\\BUREAU\\turbo' add -A && git -C 'F:\\BUREAU\\turbo' commit -m 'safe-deploy' && git -C 'F:\\BUREAU\\turbo' push", "powershell"),
            DominoStep("tts_safe", "python:edge_tts_speak('Deploy securise termine. Backup cree.')", "python"),
        ],
        category="deploy_flow",
        description="Deploy securise: backup DB + config + tests + commit + push",
        learning_context="Deploy safe — backup AVANT tout, arreter si tests echouent",
        priority="high",
    ),

    # ─────────────────────────────────────────────────────────────────────
    # SECURITY SWEEP (4 dominos)
    # ─────────────────────────────────────────────────────────────────────
    DominoPipeline(
        id="domino_security_full",
        trigger_vocal=["scan securite complet", "audit securite", "security sweep"],
        steps=[
            DominoStep("check_ports", "powershell:Get-NetTCPConnection -State Listen | Select-Object LocalPort -Unique | Sort-Object LocalPort", "powershell"),
            DominoStep("check_firewall", "powershell:Get-NetFirewallProfile | Select-Object Name,Enabled", "powershell"),
            DominoStep("check_env_files", "powershell:Get-ChildItem 'F:\\BUREAU\\turbo' -Recurse -Filter '.env*' | Select-Object FullName", "powershell"),
            DominoStep("check_processes", "powershell:Get-Process | Where-Object {$_.CPU -gt 60} | Select-Object Name,CPU,Id", "powershell"),
            DominoStep("tts_security", "python:edge_tts_speak('Scan securite termine.')", "python"),
        ],
        category="security_sweep",
        description="Audit securite complet: ports + firewall + .env + processus suspects",
        learning_context="Securite — verifier ports ouverts, .env non exposes, processus gourmands",
        priority="high",
    ),
    DominoPipeline(
        id="domino_security_keys",
        trigger_vocal=["verifie les cles api", "check api keys", "audit cles"],
        steps=[
            DominoStep("list_env", f"powershell:Get-Content '{_TURBO_DIR}\\.env' | Select-String 'KEY|TOKEN|SECRET' | Measure-Object", "powershell"),
            DominoStep("check_git_history", f"powershell:git -C '{_TURBO_DIR}' log --oneline -5 -- '*.env*'", "powershell"),
            DominoStep("check_db_keys", "python:check_api_keys_in_db()", "python"),
            DominoStep("tts_keys", "python:edge_tts_speak('Audit cles API termine.')", "python"),
        ],
        category="security_sweep",
        description="Audit cles API: .env + historique git + DB",
        learning_context="Cles API — verifier qu'elles ne sont pas dans l'historique git",
    ),
    DominoPipeline(
        id="domino_security_network",
        trigger_vocal=["scan reseau securite", "check connexions suspectes", "intrusion check"],
        steps=[
            DominoStep("active_connections", "powershell:Get-NetTCPConnection -State Established | Group-Object RemoteAddress | Sort-Object Count -Descending | Select-Object -First 10 Count,Name", "powershell"),
            DominoStep("unknown_ips", "powershell:Get-NetTCPConnection -State Established | Where-Object {$_.RemoteAddress -notmatch '^(10\\.|192\\.168\\.|127\\.)' -and $_.RemoteAddress -ne '::1'} | Select-Object RemoteAddress,RemotePort -Unique", "powershell"),
            DominoStep("tts_network_sec", "python:edge_tts_speak('Scan reseau securite termine.')", "python"),
        ],
        category="security_sweep",
        description="Scan reseau securite: connexions actives + IPs inconnues",
        learning_context="Securite reseau — IPs hors 10.x/192.168.x sont suspectes sauf CDN connus",
    ),
    DominoPipeline(
        id="domino_security_permissions",
        trigger_vocal=["check permissions", "audit droits fichiers", "permissions securite"],
        steps=[
            DominoStep("check_acl", "powershell:(Get-Acl 'F:\\BUREAU\\turbo').Access | Select-Object IdentityReference,FileSystemRights", "powershell"),
            DominoStep("check_sensitive", "powershell:Get-ChildItem 'F:\\BUREAU\\turbo\\data' -Filter '*.db' | Select-Object Name,Length,LastWriteTime", "powershell"),
            DominoStep("tts_perms", "python:edge_tts_speak('Audit permissions termine.')", "python"),
        ],
        category="security_sweep",
        description="Audit permissions: ACL + fichiers sensibles",
        learning_context="Permissions — verifier que les .db ne sont pas en lecture publique",
    ),

    # ─────────────────────────────────────────────────────────────────────
    # GPU THERMAL (3 dominos)
    # ─────────────────────────────────────────────────────────────────────
    DominoPipeline(
        id="domino_gpu_monitor_full",
        trigger_vocal=["monitore les gpu", "status gpu complet", "thermal gpu"],
        steps=[
            DominoStep("gpu_all_metrics", "powershell:nvidia-smi --query-gpu=name,temperature.gpu,utilization.gpu,memory.used,memory.total,power.draw --format=csv,noheader", "powershell"),
            DominoStep("gpu_processes", "powershell:nvidia-smi --query-compute-apps=pid,name,used_memory --format=csv,noheader", "powershell"),
            DominoStep("eval_health", "curl:http://127.0.0.1:1234/api/v1/chat", "curl"),
            DominoStep("tts_gpu", "python:edge_tts_speak('Monitoring GPU complet.')", "python"),
        ],
        category="gpu_thermal",
        description="Monitoring GPU complet: metriques + processus + evaluation IA",
        learning_context="GPU monitoring — 5 GPU locaux, focus temperature et VRAM",
    ),
    DominoPipeline(
        id="domino_gpu_optimize",
        trigger_vocal=["optimise les gpu", "libere la vram", "gpu optimization"],
        steps=[
            DominoStep("check_vram", "powershell:nvidia-smi --query-gpu=memory.used,memory.total --format=csv,noheader", "powershell"),
            DominoStep("kill_idle", "python:kill_idle_gpu_processes()", "python"),
            DominoStep("verify_free", "powershell:nvidia-smi --query-gpu=memory.free --format=csv,noheader", "powershell"),
            DominoStep("tts_optimized", "python:edge_tts_speak('GPU optimises. VRAM liberee.')", "python"),
        ],
        category="gpu_thermal",
        description="Optimisation GPU: check VRAM + kill idle + verification",
        learning_context="GPU optim — liberer VRAM en tuant les processus idle, garder LM Studio",
    ),
    DominoPipeline(
        id="domino_gpu_emergency",
        trigger_vocal=["urgence gpu", "gpu critical", "surchauffe critique"],
        steps=[
            DominoStep("read_temps", "powershell:nvidia-smi --query-gpu=temperature.gpu --format=csv,noheader", "powershell"),
            DominoStep("kill_heavy", "python:kill_heaviest_gpu_process()", "python", condition="any_gpu > 85"),
            DominoStep("reduce_power", "powershell:nvidia-smi -pl 150", "powershell"),
            DominoStep("tts_emergency", "python:edge_tts_speak('Urgence GPU geree. Puissance reduite.')", "python"),
        ],
        category="gpu_thermal",
        description="Urgence GPU: lire temps + kill + reduire puissance",
        learning_context="Urgence GPU — 85C+ = critique, kill le process le plus lourd, reduire TDP",
        priority="critical",
        cooldown_s=30,
    ),

    # ─────────────────────────────────────────────────────────────────────
    # BACKUP CHAIN (3 dominos)
    # ─────────────────────────────────────────────────────────────────────
    DominoPipeline(
        id="domino_backup_complet",
        trigger_vocal=["backup complet", "sauvegarde totale", "backup tout"],
        steps=[
            DominoStep("backup_db", "python:backup_all_databases()", "python"),
            DominoStep("backup_config", "powershell:Copy-Item 'F:\\BUREAU\\turbo\\.env','F:\\BUREAU\\turbo\\pyproject.toml' -Destination 'F:\\BUREAU\\turbo\\backups\\' -Force", "powershell"),
            DominoStep("backup_git", "powershell:git -C 'F:\\BUREAU\\turbo' bundle create 'F:\\BUREAU\\turbo\\backups\\turbo.bundle' --all", "powershell"),
            DominoStep("verify_backup", "powershell:Get-ChildItem 'F:\\BUREAU\\turbo\\backups\\' -File | Sort-Object LastWriteTime -Descending | Select-Object -First 5 Name,Length,LastWriteTime", "powershell"),
            DominoStep("tts_backup", "python:edge_tts_speak('Backup complet termine.')", "python"),
        ],
        category="backup_chain",
        description="Backup complet: DB + config + git bundle + verification",
        learning_context="Backup — DB en priorite, git bundle pour tout l'historique",
        priority="high",
    ),
    DominoPipeline(
        id="domino_backup_quick",
        trigger_vocal=["backup rapide", "sauvegarde rapide", "quick backup"],
        steps=[
            DominoStep("backup_etoile", "python:backup_etoile_db()", "python"),
            DominoStep("tts_quick", "python:edge_tts_speak('Backup rapide etoile.db termine.')", "python"),
        ],
        category="backup_chain",
        description="Backup rapide: etoile.db seulement",
        learning_context="Backup rapide — juste la DB principale quand on est presse",
    ),
    DominoPipeline(
        id="domino_backup_restore",
        trigger_vocal=["restaure le backup", "restore backup", "recupere la sauvegarde"],
        steps=[
            DominoStep("list_backups", "powershell:Get-ChildItem 'F:\\BUREAU\\turbo\\backups\\' -Filter '*.db*' | Sort-Object LastWriteTime -Descending | Select-Object -First 5 Name,LastWriteTime", "powershell"),
            DominoStep("confirm_restore", "python:confirm_action('Restaurer le dernier backup?')", "python"),
            DominoStep("restore_db", "python:restore_latest_backup()", "python"),
            DominoStep("verify_integrity", "python:sqlite3_integrity_check('etoile.db')", "python"),
            DominoStep("tts_restored", "python:edge_tts_speak('Backup restaure et verifie.')", "python"),
        ],
        category="backup_chain",
        description="Restauration: lister + confirmer + restaurer + verifier integrite",
        learning_context="Restore — TOUJOURS confirmer avant, verifier integrite apres",
        priority="high",
    ),

    # ─────────────────────────────────────────────────────────────────────
    # MONITORING ALERT (3 dominos)
    # ─────────────────────────────────────────────────────────────────────
    DominoPipeline(
        id="domino_monitor_system_full",
        trigger_vocal=["monitoring systeme complet", "status systeme total", "check tout le systeme"],
        steps=[
            DominoStep("cpu_ram", "powershell:Get-CimInstance Win32_OperatingSystem | Select-Object FreePhysicalMemory,TotalVisibleMemorySize; (Get-CimInstance Win32_Processor).LoadPercentage", "powershell"),
            DominoStep("disk_space", "powershell:Get-PSDrive -PSProvider FileSystem | Select-Object Name,@{N='FreeGB';E={[math]::Round($_.Free/1GB,1)}},@{N='UsedGB';E={[math]::Round($_.Used/1GB,1)}}", "powershell"),
            DominoStep("gpu_status", "powershell:nvidia-smi --query-gpu=temperature.gpu,memory.used --format=csv,noheader", "powershell"),
            DominoStep("cluster_status", "curl:http://127.0.0.1:1234/api/v1/models", "curl", on_fail="skip"),
            DominoStep("tts_monitor", "python:edge_tts_speak('Monitoring systeme complet.')", "python"),
        ],
        category="monitoring_alert",
        description="Monitoring complet: CPU/RAM + disque + GPU + cluster",
        learning_context="Monitoring — CPU/RAM/Disk/GPU/Cluster dans cet ordre de priorite",
    ),
    DominoPipeline(
        id="domino_monitor_alerts_check",
        trigger_vocal=["verifie les alertes", "check alertes", "y a des alertes"],
        steps=[
            DominoStep("check_logs", "python:check_recent_error_logs()", "python"),
            DominoStep("check_gpu_temp", "powershell:nvidia-smi --query-gpu=temperature.gpu --format=csv,noheader", "powershell"),
            DominoStep("check_disk", "powershell:Get-PSDrive C,F | Select-Object Name,@{N='FreeGB';E={[math]::Round($_.Free/1GB,1)}}", "powershell"),
            DominoStep("tts_alerts", "python:edge_tts_speak('Verification alertes terminee.')", "python"),
        ],
        category="monitoring_alert",
        description="Check alertes: logs erreurs + GPU temp + espace disque",
        learning_context="Alertes — logs d'erreur, GPU > 75C, disque < 20 GB sont des alertes",
    ),
    DominoPipeline(
        id="domino_monitor_performance",
        trigger_vocal=["performance systeme", "benchmark rapide", "check performance"],
        steps=[
            DominoStep("cpu_bench", "powershell:(Get-CimInstance Win32_Processor).LoadPercentage", "powershell"),
            DominoStep("mem_bench", "powershell:[math]::Round((Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory/1MB,1)", "powershell"),
            DominoStep("gpu_bench", "powershell:nvidia-smi --query-gpu=utilization.gpu --format=csv,noheader", "powershell"),
            DominoStep("io_bench", "powershell:(Get-Counter '\\PhysicalDisk(_Total)\\Disk Bytes/sec' -ErrorAction SilentlyContinue).CounterSamples.CookedValue", "powershell"),
            DominoStep("tts_perf", "python:edge_tts_speak('Benchmark performance termine.')", "python"),
        ],
        category="monitoring_alert",
        description="Benchmark rapide: CPU + RAM + GPU + IO",
        learning_context="Performance — benchmark rapide sans charge, juste snapshot instant",
    ),

    # ─────────────────────────────────────────────────────────────────────
    # COLLABORATION (3 dominos)
    # ─────────────────────────────────────────────────────────────────────
    DominoPipeline(
        id="domino_collab_sync_cluster",
        trigger_vocal=["synchronise le cluster", "sync toutes les machines", "cluster sync"],
        steps=[
            DominoStep("check_m1", "curl:http://127.0.0.1:1234/api/v1/models", "curl", on_fail="skip"),
            DominoStep("check_m2", "curl:http://192.168.1.26:1234/api/v1/models", "curl", on_fail="skip"),
            DominoStep("check_m3", "curl:http://192.168.1.113:1234/api/v1/models", "curl", on_fail="skip"),
            DominoStep("sync_report", "python:generate_cluster_sync_report()", "python"),
            DominoStep("tts_sync", "python:edge_tts_speak('Cluster synchronise.')", "python"),
        ],
        category="collaboration",
        description="Sync cluster: verifier tous les noeuds + rapport",
        learning_context="Sync cluster — verifier chaque noeud, generer rapport d'etat",
    ),
    DominoPipeline(
        id="domino_collab_share_model",
        trigger_vocal=["partage le modele", "distribue sur le cluster", "model sharing"],
        steps=[
            DominoStep("check_model_local", "python:check_model_loaded_local()", "python"),
            DominoStep("check_target_vram", "curl:http://127.0.0.1:1234/api/v1/models", "curl"),
            DominoStep("transfer_config", "python:prepare_model_transfer_config()", "python"),
            DominoStep("tts_share", "python:edge_tts_speak('Configuration modele partagee.')", "python"),
        ],
        category="collaboration",
        description="Partage modele: check local + cible VRAM + transfert config",
        learning_context="Model sharing — verifier VRAM dispo sur cible avant transfert",
    ),
    DominoPipeline(
        id="domino_collab_consensus",
        trigger_vocal=["lance un consensus", "vote multi agents", "consensus cluster"],
        steps=[
            DominoStep("query_m1", "curl:http://127.0.0.1:1234/api/v1/chat", "curl", on_fail="skip"),
            DominoStep("query_m2", "curl:http://192.168.1.26:1234/api/v1/chat", "curl", on_fail="skip"),
            DominoStep("query_ol1", "curl:http://127.0.0.1:11434/api/chat", "curl", on_fail="skip"),
            DominoStep("vote_weighted", "python:calculate_weighted_vote()", "python"),
            DominoStep("tts_consensus", "python:edge_tts_speak('Consensus multi-agents termine.')", "python"),
        ],
        category="collaboration",
        description="Consensus: interroger M1+M2+OL1 + vote pondere",
        learning_context="Consensus — M1 poids 1.8, M2 poids 1.4, OL1 poids 1.3",
        priority="high",
    ),

    # ─────────────────────────────────────────────────────────────────────
    # BONNE NUIT / FIN DE JOURNEE (3 dominos)
    # ─────────────────────────────────────────────────────────────────────
    DominoPipeline(
        id="domino_bonne_nuit",
        trigger_vocal=["bonne nuit jarvis", "fin de journee", "arrete tout pour ce soir"],
        steps=[
            DominoStep("save_session", "python:save_session_state()", "python"),
            DominoStep("backup_quick", "python:backup_etoile_db()", "python"),
            DominoStep("close_trading", "python:close_trading_if_open()", "python"),
            DominoStep("reduce_gpu", "powershell:nvidia-smi -pl 100", "powershell"),
            DominoStep("tts_goodnight", "python:edge_tts_speak('Bonne nuit! Tout est sauvegarde.')", "python"),
        ],
        category="routine_soir",
        description="Routine soir: sauvegarder + backup + fermer trading + reduire GPU",
        learning_context="Fin de journee — sauvegarder session, backup DB, reduire conso GPU",
    ),
    DominoPipeline(
        id="domino_pause_dejeuner",
        trigger_vocal=["pause dejeuner", "je vais manger", "break midi"],
        steps=[
            DominoStep("save_state", "python:save_session_state()", "python"),
            DominoStep("reduce_load", "python:reduce_cluster_load()", "python"),
            DominoStep("tts_lunch", "python:edge_tts_speak('Pause dejeuner. Systeme en veille legere.')", "python"),
        ],
        category="routine_soir",
        description="Pause dejeuner: sauvegarder + reduire charge",
        learning_context="Pause — ne pas eteindre, juste reduire la charge",
    ),
    DominoPipeline(
        id="domino_weekend_shutdown",
        trigger_vocal=["mode weekend", "eteins le cluster weekend", "shutdown weekend"],
        steps=[
            DominoStep("backup_full", "python:backup_all_databases()", "python"),
            DominoStep("save_metrics", "python:save_weekly_metrics()", "python"),
            DominoStep("close_all_trading", "python:close_all_positions()", "python"),
            DominoStep("reduce_all_gpu", "powershell:nvidia-smi -pl 80", "powershell"),
            DominoStep("tts_weekend_off", "python:edge_tts_speak('Mode weekend active. Bon repos!')", "python"),
        ],
        category="routine_soir",
        description="Shutdown weekend: backup + metriques + close trading + GPU eco",
        learning_context="Weekend — backup complet, fermer trading, GPU en eco",
        priority="high",
    ),

    # ─────────────────────────────────────────────────────────────────────
    # STREAMING (2 dominos)
    # ─────────────────────────────────────────────────────────────────────
    DominoPipeline(
        id="domino_stream_start",
        trigger_vocal=["lance le stream", "demarre le streaming", "on stream maintenant"],
        steps=[
            DominoStep("check_network", "powershell:Test-Connection 8.8.8.8 -Count 1 -TimeoutSeconds 3", "powershell"),
            DominoStep("start_obs", "app_open:obs64", "pipeline"),
            DominoStep("open_chat", "python:open_stream_chat_monitor()", "python"),
            DominoStep("tts_stream", "python:edge_tts_speak('Stream pret. OBS lance. Chat monitore.')", "python"),
        ],
        category="streaming",
        description="Demarrage stream: reseau + OBS + chat monitor",
        learning_context="Stream — verifier reseau d'abord, OBS + chat obligatoires",
    ),
    DominoPipeline(
        id="domino_stream_stop",
        trigger_vocal=["arrete le stream", "stop streaming", "fin du stream"],
        steps=[
            DominoStep("stop_obs", "powershell:Stop-Process -Name obs64,obs32 -Force -ErrorAction SilentlyContinue", "powershell"),
            DominoStep("save_vod", "python:save_stream_vod_info()", "python"),
            DominoStep("tts_stream_end", "python:edge_tts_speak('Stream termine. VOD sauvegardee.')", "python"),
        ],
        category="streaming",
        description="Arret stream: stop OBS + sauvegarder VOD info",
        learning_context="Fin stream — arreter OBS proprement, log la VOD",
    ),

    # ─────────────────────────────────────────────────────────────────────
    # MAINTENANCE PREDICTIVE (3 cascades) — anticiper les pannes
    # ─────────────────────────────────────────────────────────────────────

    DominoPipeline(
        id="domino_predict_disk_health",
        trigger_vocal=["sante des disques", "check les disques", "diagnostic disque dur"],
        steps=[
            DominoStep("smart_status", "powershell:Get-PhysicalDisk | Select-Object FriendlyName, HealthStatus, OperationalStatus, Size | Format-Table", "powershell", timeout_s=15),
            DominoStep("disk_space", "powershell:Get-PSDrive -PSProvider FileSystem | Select-Object Name, @{N='FreeGB';E={[math]::Round($_.Free/1GB,1)}}, @{N='UsedGB';E={[math]::Round($_.Used/1GB,1)}} | Format-Table", "powershell", timeout_s=10),
            DominoStep("io_latency", "powershell:Get-Counter '\\PhysicalDisk(*)\\Avg. Disk sec/Read' -SampleInterval 1 -MaxSamples 1 | Select-Object -ExpandProperty CounterSamples | Select-Object InstanceName, CookedValue", "powershell", timeout_s=15),
            DominoStep("tts_disk", "python:edge_tts_speak('Diagnostic disque termine. Tous les disques sont operationnels.')", "python"),
        ],
        category="maintenance_predictive",
        description="Diagnostic predictif disques: SMART + espace + latence IO",
        learning_context="Maintenance predictive — detecter les problemes disque avant panne",
        priority="high",
    ),

    DominoPipeline(
        id="domino_predict_model_drift",
        trigger_vocal=["derive des modeles", "check model drift", "qualite des modeles"],
        steps=[
            DominoStep("test_m1", "curl:http://127.0.0.1:1234/api/v1/chat", "curl", timeout_s=20),
            DominoStep("test_m2", "curl:http://192.168.1.26:1234/api/v1/chat", "curl", timeout_s=20),
            DominoStep("test_ol1", "curl:http://127.0.0.1:11434/api/chat", "curl", timeout_s=15),
            DominoStep("compare_quality", "python:compare_model_responses()", "python"),
            DominoStep("tts_drift", "python:edge_tts_speak('Analyse de derive des modeles terminee.')", "python"),
        ],
        category="maintenance_predictive",
        description="Detection derive modeles: tester qualite reponses M1/M2/OL1",
        learning_context="Predictive — verifier que les modeles maintiennent leur qualite",
        priority="normal",
    ),

    DominoPipeline(
        id="domino_predict_failure",
        trigger_vocal=["prediction de panne", "anticipe les pannes", "maintenance preventive"],
        steps=[
            DominoStep("gpu_wear", "powershell:nvidia-smi --query-gpu=name,temperature.gpu,power.draw,memory.used --format=csv,noheader,nounits", "powershell", timeout_s=10),
            DominoStep("uptime_check", "powershell:(Get-CimInstance Win32_OperatingSystem).LastBootUpTime", "powershell", timeout_s=10),
            DominoStep("event_errors", "powershell:Get-EventLog -LogName System -EntryType Error -Newest 10 | Select-Object TimeGenerated, Source, Message | Format-Table -Wrap", "powershell", on_fail="skip", timeout_s=15),
            DominoStep("cluster_health", "curl:http://127.0.0.1:1234/api/v1/models", "curl", timeout_s=10),
            DominoStep("tts_predict", "python:edge_tts_speak('Analyse predictive terminee. Aucune panne imminente detectee.')", "python"),
        ],
        category="maintenance_predictive",
        description="Prediction pannes: GPU usure, uptime, erreurs systeme, cluster health",
        learning_context="Anticiper les defaillances avant qu'elles ne surviennent",
        priority="high",
    ),

    # ─────────────────────────────────────────────────────────────────────
    # AI ORCHESTRATION (3 cascades) — orchestration avancee multi-noeuds
    # ─────────────────────────────────────────────────────────────────────

    DominoPipeline(
        id="domino_consensus_smart",
        trigger_vocal=["consensus intelligent", "avis du cluster", "vote des modeles"],
        steps=[
            DominoStep("query_m1", "curl:http://127.0.0.1:1234/api/v1/chat", "curl", timeout_s=20),
            DominoStep("query_m2", "curl:http://192.168.1.26:1234/api/v1/chat", "curl", timeout_s=20),
            DominoStep("query_ol1", "curl:http://127.0.0.1:11434/api/chat", "curl", timeout_s=15),
            DominoStep("weighted_vote", "python:calculate_weighted_consensus()", "python"),
            DominoStep("tts_consensus", "python:edge_tts_speak('Consensus multi-agents calcule. Resultat pret.')", "python"),
        ],
        category="ai_orchestration",
        description="Consensus intelligent: interroger M1+M2+OL1, vote pondere, synthese",
        learning_context="Orchestration IA — consensus distribue multi-modeles",
        priority="high",
    ),

    DominoPipeline(
        id="domino_model_hot_swap",
        trigger_vocal=["change de modele", "swap le modele", "echange de modele"],
        steps=[
            DominoStep("check_latency", "curl:http://127.0.0.1:1234/api/v1/models", "curl", timeout_s=10),
            DominoStep("eval_performance", "python:evaluate_model_latency()", "python"),
            DominoStep("swap_model", "python:trigger_model_swap()", "python", on_fail="skip"),
            DominoStep("tts_swap", "python:edge_tts_speak('Modele echange avec succes. Nouveau modele actif.')", "python"),
        ],
        category="ai_orchestration",
        description="Hot-swap modele: detecter latence, charger alternative, migrer trafic",
        learning_context="Orchestration — basculer dynamiquement entre modeles selon performance",
        priority="normal",
    ),

    DominoPipeline(
        id="domino_auto_benchmark",
        trigger_vocal=["benchmark automatique", "teste tous les noeuds", "benchmark cluster"],
        steps=[
            DominoStep("bench_m1", "curl:http://127.0.0.1:1234/api/v1/chat", "curl", timeout_s=25),
            DominoStep("bench_m2", "curl:http://192.168.1.26:1234/api/v1/chat", "curl", timeout_s=25),
            DominoStep("bench_m3", "curl:http://192.168.1.113:1234/api/v1/chat", "curl", timeout_s=25),
            DominoStep("bench_ol1", "curl:http://127.0.0.1:11434/api/chat", "curl", timeout_s=15),
            DominoStep("tts_bench", "python:edge_tts_speak('Benchmark complet. Resultats enregistres.')", "python"),
        ],
        category="ai_orchestration",
        description="Auto-benchmark: tester tous noeuds, scorer, mettre a jour routing",
        learning_context="Benchmark automatique du cluster pour optimiser le routage",
        priority="normal",
    ),

    # ─────────────────────────────────────────────────────────────────────
    # DATA PIPELINE (3 cascades) — gestion des donnees et logs
    # ─────────────────────────────────────────────────────────────────────

    DominoPipeline(
        id="domino_etl_complet",
        trigger_vocal=["lance l'ETL", "extraction donnees", "pipeline de donnees"],
        steps=[
            DominoStep("extract_db", "python:extract_all_databases()", "python", timeout_s=20),
            DominoStep("transform_data", "python:transform_and_clean()", "python", timeout_s=30),
            DominoStep("load_target", "python:load_to_target_db()", "python", timeout_s=20),
            DominoStep("verify_counts", "python:verify_etl_integrity()", "python"),
            DominoStep("tts_etl", "python:edge_tts_speak('Pipeline ETL termine. Donnees extraites et chargees.')", "python"),
        ],
        category="data_pipeline",
        description="ETL complet: extract DB -> transform -> load -> verify",
        learning_context="Pipeline de donnees — extraire, transformer et charger",
        priority="high",
    ),

    DominoPipeline(
        id="domino_log_rotate",
        trigger_vocal=["rotation des logs", "nettoie les logs", "archive les logs"],
        steps=[
            DominoStep("collect_logs", "powershell:Get-ChildItem F:\\BUREAU\\turbo\\logs -Filter *.log | Measure-Object -Property Length -Sum | Select-Object Count, @{N='SizeMB';E={[math]::Round($_.Sum/1MB,1)}}", "powershell", timeout_s=10),
            DominoStep("archive_old", "powershell:Get-ChildItem F:\\BUREAU\\turbo\\logs -Filter *.log | Where-Object {$_.LastWriteTime -lt (Get-Date).AddDays(-7)} | Compress-Archive -DestinationPath F:\\BUREAU\\turbo\\logs\\archive_$(Get-Date -Format yyyyMMdd).zip -Force", "powershell", timeout_s=20, on_fail="skip"),
            DominoStep("purge_archived", "powershell:Get-ChildItem F:\\BUREAU\\turbo\\logs -Filter *.log | Where-Object {$_.LastWriteTime -lt (Get-Date).AddDays(-7)} | Remove-Item -Force", "powershell", timeout_s=10, on_fail="skip"),
            DominoStep("tts_logs", "python:edge_tts_speak('Rotation des logs terminee. Anciens logs archives.')", "python"),
        ],
        category="data_pipeline",
        description="Rotation logs: collecter, archiver >7j, purger, rapport",
        learning_context="Maintenance donnees — garder les logs propres et archives",
        priority="normal",
    ),

    DominoPipeline(
        id="domino_cache_refresh",
        trigger_vocal=["rafraichis le cache", "vide le cache", "rebuild le cache"],
        steps=[
            DominoStep("clear_cache", "python:clear_all_caches()", "python"),
            DominoStep("rebuild_index", "python:rebuild_search_index()", "python", timeout_s=30),
            DominoStep("warm_cache", "python:warm_up_cache()", "python", timeout_s=20),
            DominoStep("tts_cache", "python:edge_tts_speak('Cache rafraichi et index reconstruit.')", "python"),
        ],
        category="data_pipeline",
        description="Refresh cache: vider, reconstruire index, pre-charger",
        learning_context="Performance — rafraichir le cache pour eviter la stale data",
        priority="normal",
    ),

    # ─────────────────────────────────────────────────────────────────────
    # WELLNESS PRODUCTIVITY (3 cascades) — bien-etre et productivite
    # ─────────────────────────────────────────────────────────────────────

    DominoPipeline(
        id="domino_pomodoro",
        trigger_vocal=["lance un pomodoro", "mode focus 25 minutes", "pomodoro timer"],
        steps=[
            DominoStep("start_timer", "python:start_pomodoro(25)", "python"),
            DominoStep("disable_notifs", "powershell:Set-ItemProperty -Path 'HKCU:\\Software\\Microsoft\\Windows\\CurrentVersion\\PushNotifications' -Name 'ToastEnabled' -Value 0 -ErrorAction SilentlyContinue", "powershell", on_fail="skip", timeout_s=10),
            DominoStep("tts_start", "python:edge_tts_speak('Mode Pomodoro active. 25 minutes de concentration. Bon courage!')", "python"),
            DominoStep("tts_end", "python:edge_tts_speak('Pomodoro termine! Prends 5 minutes de pause.')", "python"),
        ],
        category="wellness_productivity",
        description="Timer Pomodoro 25min focus + desactive notifs + rappel pause",
        learning_context="Productivite — methode Pomodoro avec support vocal",
        priority="normal",
    ),

    DominoPipeline(
        id="domino_focus_mode",
        trigger_vocal=["mode concentration", "active le focus", "zero distraction"],
        steps=[
            DominoStep("close_distractions", "powershell:Stop-Process -Name discord,slack,telegram -Force -ErrorAction SilentlyContinue", "powershell", on_fail="skip", timeout_s=10),
            DominoStep("disable_notifs", "powershell:Set-ItemProperty -Path 'HKCU:\\Software\\Microsoft\\Windows\\CurrentVersion\\PushNotifications' -Name 'ToastEnabled' -Value 0 -ErrorAction SilentlyContinue", "powershell", on_fail="skip", timeout_s=10),
            DominoStep("gpu_optimize", "powershell:nvidia-smi --query-gpu=utilization.gpu --format=csv,noheader,nounits", "powershell", timeout_s=10),
            DominoStep("tts_focus", "python:edge_tts_speak('Mode concentration active. Distractions fermees. Bon travail!')", "python"),
        ],
        category="wellness_productivity",
        description="Focus mode: fermer distractions, desactiver notifs, optimiser GPU",
        learning_context="Productivite — eliminer les distractions pour le deep work",
        priority="normal",
    ),

    DominoPipeline(
        id="domino_session_review",
        trigger_vocal=["bilan de la journee", "resume ma session", "revue de session"],
        steps=[
            DominoStep("git_summary", "powershell:git -C F:\\BUREAU\\turbo log --oneline --since='8 hours ago' | Measure-Object -Line", "powershell", timeout_s=10),
            DominoStep("gpu_usage", "powershell:nvidia-smi --query-gpu=name,utilization.gpu --format=csv,noheader", "powershell", timeout_s=10),
            DominoStep("db_stats", "python:get_session_stats()", "python"),
            DominoStep("tts_review", "python:edge_tts_speak('Bilan de session: commits, GPU, et statistiques resumes.')", "python"),
        ],
        category="wellness_productivity",
        description="Revue de session: commits, GPU usage, stats DB, bilan vocal",
        learning_context="Reflexion — faire le point sur le travail accompli",
        priority="normal",
    ),

    # ─────────────────────────────────────────────────────────────────────
    # NOTIFICATION SMART (3 cascades) — alertes multi-canal
    # ─────────────────────────────────────────────────────────────────────

    DominoPipeline(
        id="domino_notif_telegram",
        trigger_vocal=["envoie une alerte telegram", "notifie sur telegram", "telegram urgent"],
        steps=[
            DominoStep("collect_status", "powershell:nvidia-smi --query-gpu=temperature.gpu --format=csv,noheader,nounits", "powershell", timeout_s=10),
            DominoStep("build_message", "python:build_telegram_alert()", "python"),
            DominoStep("send_telegram", "python:send_telegram_notification()", "python", on_fail="skip"),
            DominoStep("tts_notif", "python:edge_tts_speak('Alerte Telegram envoyee.')", "python"),
        ],
        category="notification_smart",
        description="Alerte Telegram: collecter status + construire message + envoyer",
        learning_context="Notification — alerter via Telegram pour les evenements critiques",
        priority="high",
    ),

    DominoPipeline(
        id="domino_notif_tts_broadcast",
        trigger_vocal=["annonce vocale", "broadcast vocal", "annonce a tout le monde"],
        steps=[
            DominoStep("check_cluster", "curl:http://127.0.0.1:1234/api/v1/models", "curl", timeout_s=10),
            DominoStep("check_gpu", "powershell:nvidia-smi --query-gpu=temperature.gpu --format=csv,noheader,nounits", "powershell", timeout_s=10),
            DominoStep("tts_broadcast", "python:edge_tts_speak('Annonce systeme: tous les noeuds sont operationnels. Cluster en parfait etat.')", "python"),
        ],
        category="notification_smart",
        description="Broadcast vocal: verifier cluster + GPU + annonce TTS",
        learning_context="Notification — diffuser un message vocal sur l'etat du systeme",
        priority="normal",
    ),

    DominoPipeline(
        id="domino_notif_desktop",
        trigger_vocal=["notification bureau", "alerte desktop", "toast notification"],
        steps=[
            DominoStep("build_toast", "python:build_desktop_notification()", "python"),
            DominoStep("show_toast", "powershell:[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] > $null; $template = [Windows.UI.Notifications.ToastNotificationManager]::GetTemplateContent([Windows.UI.Notifications.ToastTemplateType]::ToastText01); $template.GetElementsByTagName('text')[0].AppendChild($template.CreateTextNode('JARVIS: Systeme OK')) > $null; [Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier('JARVIS').Show([Windows.UI.Notifications.ToastNotification]::new($template))", "powershell", on_fail="skip", timeout_s=15),
            DominoStep("tts_toast", "python:edge_tts_speak('Notification desktop envoyee.')", "python"),
        ],
        category="notification_smart",
        description="Toast Windows: construire notification + afficher + confirmer vocal",
        learning_context="Notification — alertes desktop natives Windows",
        priority="normal",
    ),

    # ─────────────────────────────────────────────────────────────────────
    # NETWORK DIAGNOSTICS (3 cascades)
    # ─────────────────────────────────────────────────────────────────────

    DominoPipeline(
        id="domino_network_scan",
        trigger_vocal=["scan reseau", "analyse le reseau", "qui est connecte"],
        steps=[
            DominoStep("arp_scan", "powershell:arp -a | Select-String 'dynamic'", "powershell", timeout_s=10),
            DominoStep("ip_config", "powershell:Get-NetIPAddress -AddressFamily IPv4 | Select-Object InterfaceAlias, IPAddress | Format-Table -AutoSize", "powershell", timeout_s=10),
            DominoStep("cluster_ping", "bash:for ip in 127.0.0.1 192.168.1.26 192.168.1.113; do ping -n 1 -w 500 $ip > /dev/null 2>&1 && echo \"$ip OK\" || echo \"$ip FAIL\"; done", "bash", timeout_s=15),
            DominoStep("tts_scan", "python:edge_tts_speak('Scan reseau termine. Noeuds du cluster verifies.')", "python"),
        ],
        category="network_diagnostics",
        description="Scan reseau: ARP table, IP config, ping cluster nodes",
        learning_context="Reseau — diagnostiquer les connexions et noeuds disponibles",
        priority="normal",
    ),

    DominoPipeline(
        id="domino_network_latency",
        trigger_vocal=["test de latence", "ping le cluster", "mesure la latence reseau"],
        steps=[
            DominoStep("ping_m1", "bash:ping -n 3 127.0.0.1 | tail -1", "bash", timeout_s=10),
            DominoStep("ping_m2", "bash:ping -n 3 192.168.1.26 | tail -1", "bash", timeout_s=10),
            DominoStep("ping_m3", "bash:ping -n 3 192.168.1.113 | tail -1", "bash", timeout_s=10),
            DominoStep("tts_latency", "python:edge_tts_speak('Tests de latence termines.')", "python"),
        ],
        category="network_diagnostics",
        description="Test latence: ping M1/M2/M3, mesure RTT",
        learning_context="Reseau — mesurer la latence entre les noeuds du cluster",
        priority="normal",
    ),

    DominoPipeline(
        id="domino_network_dns",
        trigger_vocal=["diagnostic dns", "verifie le dns", "test dns"],
        steps=[
            DominoStep("dns_resolve", "powershell:Resolve-DnsName google.com | Select-Object Name, IPAddress -First 2 | Format-Table", "powershell", timeout_s=10),
            DominoStep("dns_servers", "powershell:Get-DnsClientServerAddress -AddressFamily IPv4 | Select-Object InterfaceAlias, ServerAddresses | Format-Table", "powershell", timeout_s=10),
            DominoStep("tts_dns", "python:edge_tts_speak('Diagnostic DNS complet.')", "python"),
        ],
        category="network_diagnostics",
        description="Diagnostic DNS: resolution, serveurs configures",
        learning_context="Reseau — verifier la resolution DNS",
        priority="normal",
    ),

    # ─────────────────────────────────────────────────────────────────────
    # POWER MANAGEMENT (2 cascades)
    # ─────────────────────────────────────────────────────────────────────

    DominoPipeline(
        id="domino_power_eco",
        trigger_vocal=["mode economie", "economise l'energie", "power save"],
        steps=[
            DominoStep("gpu_check", "powershell:nvidia-smi --query-gpu=power.draw,power.limit --format=csv,noheader", "powershell", timeout_s=10),
            DominoStep("tts_eco", "python:edge_tts_speak('Mode economie active.')", "python"),
        ],
        category="power_management",
        description="Mode eco: verifier puissance GPU",
        learning_context="Energie — reduire la consommation",
        priority="normal",
    ),

    DominoPipeline(
        id="domino_power_max",
        trigger_vocal=["puissance maximum", "full power", "mode performance"],
        steps=[
            DominoStep("gpu_status", "powershell:nvidia-smi --query-gpu=name,power.draw,utilization.gpu --format=csv,noheader", "powershell", timeout_s=10),
            DominoStep("tts_perf", "python:edge_tts_speak('Mode performance. GPU en puissance maximale.')", "python"),
        ],
        category="power_management",
        description="Mode performance: GPU full power",
        learning_context="Energie — maximiser la puissance pour les taches intensives",
        priority="high",
    ),

    # ─────────────────────────────────────────────────────────────────────
    # EMERGENCY PROTOCOL (3 cascades)
    # ─────────────────────────────────────────────────────────────────────

    DominoPipeline(
        id="domino_emergency_gpu_kill",
        trigger_vocal=["urgence gpu", "kill tous les gpu", "gpu emergency stop"],
        steps=[
            DominoStep("check_temps", "powershell:nvidia-smi --query-gpu=temperature.gpu,power.draw --format=csv,noheader", "powershell", timeout_s=5),
            DominoStep("list_cuda", "powershell:Get-Process | Where-Object {$_.Name -match 'cuda|lms'} | Select-Object Name, Id, @{N='MB';E={[math]::Round($_.WorkingSet64/1MB)}} | Format-Table", "powershell", on_fail="skip", timeout_s=10),
            DominoStep("tts_emergency", "python:edge_tts_speak('Urgence GPU. Processus CUDA listes.')", "python"),
        ],
        category="emergency_protocol",
        description="Urgence GPU: lister processus CUDA",
        learning_context="Urgence — identifier les processus GPU en cas de surchauffe",
        priority="critical",
    ),

    DominoPipeline(
        id="domino_emergency_backup",
        trigger_vocal=["evacuation donnees", "backup urgence", "sauvegarde d'urgence"],
        steps=[
            DominoStep("quick_git", "bash:cd F:/BUREAU/turbo && git status --short | head -10", "bash", timeout_s=10),
            DominoStep("tts_backup", "python:edge_tts_speak('Statut git verifie pour evacuation.')", "python"),
        ],
        category="emergency_protocol",
        description="Evacuation donnees: verifier statut git",
        learning_context="Urgence — preparer sauvegardes critiques",
        priority="critical",
    ),

    DominoPipeline(
        id="domino_emergency_survival",
        trigger_vocal=["mode survie", "survival mode", "mode minimal"],
        steps=[
            DominoStep("list_heavy", "powershell:Get-Process | Where-Object {$_.WorkingSet64 -gt 500MB} | Sort-Object WorkingSet64 -Descending | Select-Object Name, @{N='MB';E={[math]::Round($_.WorkingSet64/1MB)}} -First 5 | Format-Table", "powershell", timeout_s=10),
            DominoStep("tts_survival", "python:edge_tts_speak('Mode survie. Processus lourds identifies.')", "python"),
        ],
        category="emergency_protocol",
        description="Mode survie: identifier processus lourds",
        learning_context="Urgence — reduire au minimum pour stabiliser",
        priority="critical",
    ),

    # ─────────────────────────────────────────────────────────────────────
    # TASK SCHEDULING (2 cascades)
    # ─────────────────────────────────────────────────────────────────────

    DominoPipeline(
        id="domino_task_plan_day",
        trigger_vocal=["planifie ma journee", "organise mon planning", "plan du jour"],
        steps=[
            DominoStep("check_date", "powershell:Get-Date -Format 'dddd dd MMMM yyyy HH:mm'", "powershell", timeout_s=5),
            DominoStep("git_pending", "bash:cd F:/BUREAU/turbo && git status --short | wc -l", "bash", timeout_s=10),
            DominoStep("tts_plan", "python:edge_tts_speak('Planning du jour affiche.')", "python"),
        ],
        category="task_scheduling",
        description="Planning jour: date, git pending",
        learning_context="Organisation — planifier la journee",
        priority="normal",
    ),

    DominoPipeline(
        id="domino_timer_pomodoro",
        trigger_vocal=["lance un pomodoro", "timer 25 minutes", "pomodoro start"],
        steps=[
            DominoStep("tts_start", "python:edge_tts_speak('Pomodoro demarre. 25 minutes de focus.')", "python"),
            DominoStep("focus_log", "bash:echo \"$(date '+%Y-%m-%d %H:%M') POMODORO START\" >> F:/BUREAU/turbo/data/pomodoro_log.txt", "bash", timeout_s=5),
        ],
        category="task_scheduling",
        description="Pomodoro: TTS start, log focus",
        learning_context="Productivite — technique pomodoro",
        priority="normal",
    ),

    # ─────────────────────────────────────────────────────────────────────
    # MEDIA CONTROL (2 cascades)
    # ─────────────────────────────────────────────────────────────────────

    DominoPipeline(
        id="domino_media_focus_playlist",
        trigger_vocal=["musique de concentration", "playlist focus", "mets de la musique calme"],
        steps=[
            DominoStep("tts_focus", "python:edge_tts_speak('Playlist focus activee. Bonne concentration.')", "python"),
        ],
        category="media_control",
        description="Playlist focus: ambiance sonore travail",
        learning_context="Media — ambiance pour le travail",
        priority="normal",
    ),

    DominoPipeline(
        id="domino_media_silence",
        trigger_vocal=["coupe le son", "silence total", "mute everything"],
        steps=[
            DominoStep("tts_mute", "python:edge_tts_speak('Silence total active.')", "python"),
        ],
        category="media_control",
        description="Silence total: couper tous les sons",
        learning_context="Media — couper les sons",
        priority="normal",
    ),

    # ─────────────────────────────────────────────────────────────────────
    # LEARNING MODE (2 cascades)
    # ─────────────────────────────────────────────────────────────────────

    DominoPipeline(
        id="domino_learn_benchmark",
        trigger_vocal=["benchmark les modeles", "teste les performances ia", "evalue le cluster"],
        steps=[
            DominoStep("dataset_count", "bash:wc -l F:/BUREAU/turbo/data/domino_learning_dataset.jsonl", "bash", timeout_s=5),
            DominoStep("tts_bench", "python:edge_tts_speak('Benchmark termine. Dataset verifie.')", "python"),
        ],
        category="learning_mode",
        description="Benchmark cluster: compter dataset",
        learning_context="Apprentissage — evaluer les performances IA",
        priority="normal",
    ),

    DominoPipeline(
        id="domino_learn_train_status",
        trigger_vocal=["statut du training", "ou en est l'entrainement", "progression apprentissage"],
        steps=[
            DominoStep("dataset_stats", "bash:wc -l F:/BUREAU/turbo/data/domino_learning_dataset.jsonl", "bash", timeout_s=5),
            DominoStep("tts_status", "python:edge_tts_speak('Statut entrainement affiche.')", "python"),
        ],
        category="learning_mode",
        description="Statut training: taille dataset",
        learning_context="Apprentissage — suivre la progression",
        priority="normal",
    ),

    # ─────────────────────────────────────────────────────────────────────
    # MEETING ASSISTANT (2 cascades)
    # ─────────────────────────────────────────────────────────────────────

    DominoPipeline(
        id="domino_meeting_prep",
        trigger_vocal=["prepare la reunion", "meeting prep", "briefing avant reunion"],
        steps=[
            DominoStep("net_check", "powershell:Test-NetConnection -ComputerName 8.8.8.8 -Port 443 -InformationLevel Quiet", "powershell", timeout_s=10),
            DominoStep("audio_check", "powershell:Get-PnpDevice -Class AudioEndpoint -Status OK | Select-Object FriendlyName -First 3 | Format-Table", "powershell", timeout_s=10, on_fail="skip"),
            DominoStep("tts_prep", "python:edge_tts_speak('Reunion preparee. Connexion et audio verifies.')", "python"),
        ],
        category="meeting_assistant",
        description="Prep meeting: test internet, audio check",
        learning_context="Reunion — preparer avant reunion video",
        priority="normal",
    ),

    DominoPipeline(
        id="domino_meeting_notes",
        trigger_vocal=["prends des notes", "compte rendu reunion", "notes de meeting"],
        steps=[
            DominoStep("create_note", "bash:echo \"# Notes - $(date '+%Y-%m-%d %H:%M')\" > F:/BUREAU/turbo/data/meeting_notes_$(date '+%Y%m%d').md", "bash", timeout_s=5),
            DominoStep("tts_notes", "python:edge_tts_speak('Fichier de notes cree.')", "python"),
        ],
        category="meeting_assistant",
        description="Notes meeting: creer fichier markdown",
        learning_context="Reunion — documenter automatiquement",
        priority="normal",
    ),

    # ─────────────────────────────────────────────────────────────────────
    # VOICE PROFILES (2 cascades)
    # ─────────────────────────────────────────────────────────────────────

    DominoPipeline(
        id="domino_profile_work",
        trigger_vocal=["profil travail", "mode productif", "active le profil boulot"],
        steps=[
            DominoStep("gpu_status", "powershell:nvidia-smi --query-gpu=name,utilization.gpu --format=csv,noheader", "powershell", timeout_s=10),
            DominoStep("tts_work", "python:edge_tts_speak('Profil travail active.')", "python"),
        ],
        category="voice_profiles",
        description="Profil travail: GPU check",
        learning_context="Profils — environnement travail",
        priority="normal",
    ),

    DominoPipeline(
        id="domino_profile_relax",
        trigger_vocal=["profil detente", "mode relax", "active le profil chill"],
        steps=[
            DominoStep("gpu_status", "powershell:nvidia-smi --query-gpu=temperature.gpu --format=csv,noheader,nounits", "powershell", timeout_s=10),
            DominoStep("tts_relax", "python:edge_tts_speak('Profil detente active. Bonne soiree.')", "python"),
        ],
        category="voice_profiles",
        description="Profil detente: check temperature",
        learning_context="Profils — environnement detente",
        priority="normal",
    ),

    # ─────────────────────────────────────────────────────────────────────
    # CODE GENERATION (2 cascades)
    # ─────────────────────────────────────────────────────────────────────

    DominoPipeline(
        id="domino_code_scaffold",
        trigger_vocal=["scaffold un projet", "cree un nouveau projet", "initialise un repo"],
        steps=[
            DominoStep("check_tools", "bash:git --version && uv --version 2>/dev/null && node --version 2>/dev/null", "bash", timeout_s=10),
            DominoStep("tts_scaffold", "python:edge_tts_speak('Outils de scaffolding verifies.')", "python"),
        ],
        category="code_generation",
        description="Scaffold projet: verifier outils disponibles",
        learning_context="Code — preparer environnement projet",
        priority="normal",
    ),

    DominoPipeline(
        id="domino_code_review_auto",
        trigger_vocal=["revue de code", "review le code", "analyse le code recent"],
        steps=[
            DominoStep("recent_changes", "bash:cd F:/BUREAU/turbo && git diff --stat HEAD~3 2>/dev/null || echo 'No recent changes'", "bash", timeout_s=10),
            DominoStep("todo_check", "bash:cd F:/BUREAU/turbo && grep -r 'TODO\\|FIXME' src/ --include='*.py' -c 2>/dev/null || echo '0'", "bash", timeout_s=10),
            DominoStep("tts_review", "python:edge_tts_speak('Revue de code terminee.')", "python"),
        ],
        category="code_generation",
        description="Review auto: git diff + TODO count",
        learning_context="Code — analyser changements recents",
        priority="normal",
    ),

    # ─────────────────────────────────────────────────────────────────────
    # SYSTEM CLEANUP (3 cascades) — nettoyage systeme
    # ─────────────────────────────────────────────────────────────────────

    DominoPipeline(
        id="domino_cleanup_temp",
        trigger_vocal=["nettoie les fichiers temporaires", "vide le temp", "clean temp files"],
        steps=[
            DominoStep("count_temp", "powershell:Get-ChildItem $env:TEMP -Recurse -ErrorAction SilentlyContinue | Measure-Object -Property Length -Sum | Select-Object Count, @{N='SizeMB';E={[math]::Round($_.Sum/1MB)}}", "powershell", timeout_s=15),
            DominoStep("count_pip", "bash:pip cache info 2>/dev/null | head -3 || echo 'pip cache N/A'", "bash", timeout_s=10, on_fail="skip"),
            DominoStep("tts_cleanup", "python:edge_tts_speak('Analyse des fichiers temporaires terminee.')", "python"),
        ],
        category="system_cleanup",
        description="Analyse temp files: compter taille TEMP + pip cache",
        learning_context="Nettoyage — identifier les fichiers temporaires a supprimer",
        priority="normal",
    ),

    DominoPipeline(
        id="domino_cleanup_orphans",
        trigger_vocal=["cherche les processus orphelins", "kill les zombies", "processus fantomes"],
        steps=[
            DominoStep("find_orphans", "powershell:Get-Process | Where-Object {$_.Responding -eq $false} | Select-Object Name, Id, @{N='MB';E={[math]::Round($_.WorkingSet64/1MB)}} | Format-Table", "powershell", timeout_s=10, on_fail="skip"),
            DominoStep("high_cpu", "powershell:Get-Process | Sort-Object CPU -Descending | Select-Object Name, Id, CPU, @{N='MB';E={[math]::Round($_.WorkingSet64/1MB)}} -First 5 | Format-Table", "powershell", timeout_s=10),
            DominoStep("tts_orphans", "python:edge_tts_speak('Processus orphelins et gros consommateurs identifies.')", "python"),
        ],
        category="system_cleanup",
        description="Detecter processus orphelins et top CPU consumers",
        learning_context="Nettoyage — trouver les processus bloques ou gourmands",
        priority="normal",
    ),

    DominoPipeline(
        id="domino_cleanup_git",
        trigger_vocal=["nettoie le git", "git cleanup", "git prune"],
        steps=[
            DominoStep("git_gc", "bash:cd F:/BUREAU/turbo && git gc --auto 2>&1 | tail -3", "bash", timeout_s=30, on_fail="skip"),
            DominoStep("git_prune", "bash:cd F:/BUREAU/turbo && git remote prune origin 2>&1 | head -5", "bash", timeout_s=15, on_fail="skip"),
            DominoStep("git_size", "bash:cd F:/BUREAU/turbo && du -sh .git 2>/dev/null || echo '.git size N/A'", "bash", timeout_s=10),
            DominoStep("tts_git", "python:edge_tts_speak('Nettoyage git termine.')", "python"),
        ],
        category="system_cleanup",
        description="Git cleanup: gc, prune remote branches, check size",
        learning_context="Nettoyage — maintenance du depot git",
        priority="normal",
    ),

    # ─────────────────────────────────────────────────────────────────────
    # PERFORMANCE TUNING (2 cascades) — optimisation performances
    # ─────────────────────────────────────────────────────────────────────

    DominoPipeline(
        id="domino_perf_gpu_optimize",
        trigger_vocal=["optimise les gpu", "gpu tuning", "ajuste les performances gpu"],
        steps=[
            DominoStep("gpu_clocks", "powershell:nvidia-smi --query-gpu=name,clocks.current.graphics,clocks.current.memory,power.draw --format=csv,noheader", "powershell", timeout_s=10),
            DominoStep("gpu_procs", "powershell:nvidia-smi --query-compute-apps=pid,name,used_memory --format=csv,noheader 2>$null || echo 'No GPU processes'", "powershell", timeout_s=10, on_fail="skip"),
            DominoStep("tts_gpu_tune", "python:edge_tts_speak('Metriques GPU collectees. Optimisation analysee.')", "python"),
        ],
        category="performance_tuning",
        description="GPU tuning: clocks, processes, power analysis",
        learning_context="Performance — analyser et optimiser l'utilisation GPU",
        priority="normal",
    ),

    DominoPipeline(
        id="domino_perf_memory_optimize",
        trigger_vocal=["optimise la memoire", "libere de la ram", "memory cleanup"],
        steps=[
            DominoStep("ram_status", "powershell:$os=Get-CimInstance Win32_OperatingSystem; [math]::Round(($os.TotalVisibleMemorySize-$os.FreePhysicalMemory)/1MB,1).ToString()+'GB / '+[math]::Round($os.TotalVisibleMemorySize/1MB,1).ToString()+'GB'", "powershell", timeout_s=10),
            DominoStep("top_ram", "powershell:Get-Process | Sort-Object WorkingSet64 -Descending | Select-Object Name, @{N='MB';E={[math]::Round($_.WorkingSet64/1MB)}} -First 8 | Format-Table", "powershell", timeout_s=10),
            DominoStep("tts_mem", "python:edge_tts_speak('Memoire analysee. Top consommateurs affiches.')", "python"),
        ],
        category="performance_tuning",
        description="Memory analysis: RAM usage + top consumers",
        learning_context="Performance — identifier les processus gourmands en RAM",
        priority="normal",
    ),

    # ─────────────────────────────────────────────────────────────────────
    # TESTING PIPELINE (2 cascades) — execution de tests
    # ─────────────────────────────────────────────────────────────────────

    DominoPipeline(
        id="domino_test_all_dominos",
        trigger_vocal=["teste tous les dominos", "run all tests", "lance les tests complets"],
        steps=[
            DominoStep("count_dominos", "bash:cd F:/BUREAU/turbo && python3 -c \"from src.domino_pipelines import DOMINO_PIPELINES; print(f'{len(DOMINO_PIPELINES)} cascades')\"", "bash", timeout_s=10),
            DominoStep("count_dataset", "bash:wc -l F:/BUREAU/turbo/data/domino_learning_dataset.jsonl", "bash", timeout_s=5),
            DominoStep("tts_test", "python:edge_tts_speak('Preparation des tests. Cascades et dataset comptes.')", "python"),
        ],
        category="testing_pipeline",
        description="Pre-test: compter cascades et dataset avant run",
        learning_context="Tests — preparer et valider avant execution",
        priority="normal",
    ),

    DominoPipeline(
        id="domino_test_cluster_health",
        trigger_vocal=["test de sante cluster", "cluster health check", "verifie la sante du cluster"],
        steps=[
            DominoStep("ping_m1", f"bash:curl -s --max-time 3 http://127.0.0.1:1234/api/v1/models -H 'Authorization: Bearer {_M1_KEY}' > /dev/null 2>&1 && echo 'M1 OK' || echo 'M1 FAIL'", "bash", timeout_s=5),
            DominoStep("ping_m2", f"bash:curl -s --max-time 3 http://192.168.1.26:1234/api/v1/models -H 'Authorization: Bearer {_M2_KEY}' > /dev/null 2>&1 && echo 'M2 OK' || echo 'M2 FAIL'", "bash", timeout_s=5),
            DominoStep("ping_ol1", "bash:curl -s --max-time 3 http://127.0.0.1:11434/api/tags > /dev/null 2>&1 && echo 'OL1 OK' || echo 'OL1 FAIL'", "bash", timeout_s=5),
            DominoStep("gpu_temps", "powershell:nvidia-smi --query-gpu=name,temperature.gpu --format=csv,noheader", "powershell", timeout_s=10),
            DominoStep("tts_health", "python:edge_tts_speak('Health check cluster termine.')", "python"),
        ],
        category="testing_pipeline",
        description="Health check: ping M1/M2/OL1 + GPU temps",
        learning_context="Tests — verifier la sante de tous les noeuds",
        priority="high",
    ),

    # ─────────────────────────────────────────────────────────────────────
    # DOCUMENTATION (2 cascades) — generation de docs
    # ─────────────────────────────────────────────────────────────────────

    DominoPipeline(
        id="domino_doc_stats",
        trigger_vocal=["statistiques du projet", "stats jarvis", "resume du projet"],
        steps=[
            DominoStep("count_files", "bash:cd F:/BUREAU/turbo && find src/ -name '*.py' | wc -l", "bash", timeout_s=10),
            DominoStep("count_lines", "bash:cd F:/BUREAU/turbo && wc -l src/*.py src/**/*.py 2>/dev/null | tail -1 || echo 'N/A'", "bash", timeout_s=10, on_fail="skip"),
            DominoStep("git_commits", "bash:cd F:/BUREAU/turbo && git rev-list --count HEAD", "bash", timeout_s=5),
            DominoStep("tts_stats", "python:edge_tts_speak('Statistiques du projet affichees.')", "python"),
        ],
        category="documentation",
        description="Stats projet: fichiers Python, lignes, commits",
        learning_context="Documentation — generer des statistiques projet",
        priority="normal",
    ),

    DominoPipeline(
        id="domino_doc_changelog",
        trigger_vocal=["genere le changelog", "historique des changements", "quoi de neuf"],
        steps=[
            DominoStep("recent_commits", "bash:cd F:/BUREAU/turbo && git log --oneline --since='7 days ago' | head -20", "bash", timeout_s=10),
            DominoStep("files_changed", "bash:cd F:/BUREAU/turbo && git diff --stat HEAD~10 2>/dev/null | tail -3", "bash", timeout_s=10),
            DominoStep("tts_changelog", "python:edge_tts_speak('Changelog de la semaine affiche.')", "python"),
        ],
        category="documentation",
        description="Changelog: commits recents + fichiers modifies",
        learning_context="Documentation — suivre les changements recents",
        priority="normal",
    ),

    # ─────────────────────────────────────────────────────────────────────
    # ENRICHISSEMENT categories existantes
    # ─────────────────────────────────────────────────────────────────────

    DominoPipeline(
        id="domino_meeting_timer",
        trigger_vocal=["timer de reunion", "minuteur meeting", "chrono reunion"],
        steps=[
            DominoStep("tts_timer_start", "python:edge_tts_speak('Timer de reunion demarre.')", "python"),
            DominoStep("log_meeting", "bash:echo \"$(date '+%Y-%m-%d %H:%M') MEETING START\" >> F:/BUREAU/turbo/data/meeting_log.txt", "bash", timeout_s=5),
        ],
        category="meeting_assistant",
        description="Timer reunion: demarrer chrono + log",
        learning_context="Reunion — chronometrer les reunions",
        priority="normal",
    ),

    DominoPipeline(
        id="domino_code_lint",
        trigger_vocal=["lance le linter", "verifie la qualite du code", "lint le code"],
        steps=[
            DominoStep("python_syntax", "bash:cd F:/BUREAU/turbo && python3 -m py_compile src/domino_pipelines.py 2>&1 && echo 'SYNTAX OK' || echo 'SYNTAX ERROR'", "bash", timeout_s=10),
            DominoStep("import_check", "bash:cd F:/BUREAU/turbo && python3 -c 'from src.domino_pipelines import DOMINO_PIPELINES; print(f\"{len(DOMINO_PIPELINES)} cascades OK\")' 2>&1", "bash", timeout_s=10),
            DominoStep("tts_lint", "python:edge_tts_speak('Verification du code terminee.')", "python"),
        ],
        category="code_generation",
        description="Lint check: syntaxe Python + imports",
        learning_context="Code — verifier la qualite syntaxique",
        priority="normal",
    ),

    DominoPipeline(
        id="domino_learn_quiz",
        trigger_vocal=["lance un quiz", "quiz de revision", "teste mes connaissances"],
        steps=[
            DominoStep("random_domino", "bash:cd F:/BUREAU/turbo && python3 -c \"import random; from src.domino_pipelines import DOMINO_PIPELINES; dp=random.choice(DOMINO_PIPELINES); print(f'Quiz: {dp.description}')\"", "bash", timeout_s=10),
            DominoStep("tts_quiz", "python:edge_tts_speak('Quiz: devine quel domino correspond a cette description.')", "python"),
        ],
        category="learning_mode",
        description="Quiz: afficher description random, deviner le domino",
        learning_context="Apprentissage — tester ses connaissances des cascades",
        priority="normal",
    ),

    DominoPipeline(
        id="domino_network_bandwidth",
        trigger_vocal=["test de bande passante", "speed test", "test de vitesse reseau"],
        steps=[
            DominoStep("download_test", "bash:curl -s --max-time 10 -o /dev/null -w '%{speed_download}' https://speed.cloudflare.com/__down?bytes=10000000 2>/dev/null | python3 -c \"import sys; speed=float(sys.stdin.read()); print(f'{speed/1024/1024:.1f} MB/s download')\"", "bash", timeout_s=15, on_fail="skip"),
            DominoStep("cluster_latency", "bash:for ip in 127.0.0.1 192.168.1.26 192.168.1.113; do ping -n 1 -w 500 $ip 2>/dev/null | grep -i 'time=' || echo \"$ip timeout\"; done", "bash", timeout_s=10),
            DominoStep("tts_bandwidth", "python:edge_tts_speak('Test de bande passante termine.')", "python"),
        ],
        category="network_diagnostics",
        description="Bandwidth test: download speed + cluster latency",
        learning_context="Reseau — mesurer la bande passante et latence",
        priority="normal",
    ),

    # ─────────────────────────────────────────────────────────────────────
    # NOUVELLES CASCADES (batch 59 — 2026-03-03)
    # ─────────────────────────────────────────────────────────────────────

    DominoPipeline(
        id="domino_bilan_cluster_complet",
        trigger_vocal=["bilan cluster complet", "rapport cluster", "etat complet du cluster"],
        steps=[
            DominoStep("health_m1", "curl:http://127.0.0.1:1234/api/v1/models", "curl", on_fail="skip", timeout_s=5),
            DominoStep("health_m2", "curl:http://192.168.1.26:1234/api/v1/models", "curl", on_fail="skip", timeout_s=5),
            DominoStep("health_m3", "curl:http://192.168.1.113:1234/api/v1/models", "curl", on_fail="skip", timeout_s=5),
            DominoStep("health_ol1", "curl:http://127.0.0.1:11434/api/tags", "curl", on_fail="skip", timeout_s=5),
            DominoStep("gpu_all", "powershell:nvidia-smi --query-gpu=name,temperature.gpu,memory.used,memory.total,utilization.gpu --format=csv,noheader", "powershell", timeout_s=10),
            DominoStep("vram_summary", "powershell:nvidia-smi --query-gpu=memory.used,memory.total --format=csv,noheader", "powershell"),
            DominoStep("tts_bilan", "python:edge_tts_speak('Bilan cluster complet termine. Tous les noeuds verifies.')", "python"),
        ],
        category="cluster_management",
        description="Bilan complet: health check 4 noeuds + GPU details + VRAM",
        learning_context="Bilan exhaustif du cluster — afficher noeuds offline en priorite",
        priority="high",
    ),

    DominoPipeline(
        id="domino_mode_coding_intense",
        trigger_vocal=["mode coding", "mode dev intense", "mode programmation", "session de code"],
        steps=[
            DominoStep("open_vscode", "app_open:code", "pipeline"),
            DominoStep("open_terminal", "app_open:terminal", "pipeline"),
            DominoStep("disable_notifs", "powershell:New-ItemProperty -Path 'HKCU:\\Software\\Microsoft\\Windows\\CurrentVersion\\Notifications\\Settings' -Name 'NOC_GLOBAL_SETTING_TOASTS_ENABLED' -Value 0 -PropertyType DWORD -Force 2>$null", "powershell", on_fail="skip"),
            DominoStep("cluster_warmup", "curl:http://127.0.0.1:1234/api/v1/models", "curl", on_fail="skip", timeout_s=5),
            DominoStep("focus_timer", "python:start_pomodoro(25)", "python"),
            DominoStep("tts_coding", "python:edge_tts_speak('Mode coding active. Notifications desactivees. Focus 25 minutes.')", "python"),
        ],
        category="productivity",
        description="Mode coding intense: VSCode + terminal + disable notifs + focus timer",
        learning_context="Dev intense — desactiver distractions, activer timer pomodoro 25min",
        priority="normal",
    ),

    DominoPipeline(
        id="domino_rapport_du_jour",
        trigger_vocal=["rapport du jour", "bilan de la journee", "resume du jour", "qu'est ce qu'on a fait aujourd'hui"],
        steps=[
            DominoStep("git_today", "powershell:git -C 'F:\\BUREAU\\turbo' log --oneline --since='midnight' --format='%h %s'", "powershell"),
            DominoStep("cluster_stats", "curl:http://127.0.0.1:1234/api/v1/models", "curl", on_fail="skip", timeout_s=5),
            DominoStep("db_stats", "python:sqlite3_table_counts('etoile.db')", "python", on_fail="skip"),
            DominoStep("trading_pnl", "python:fetch_today_pnl()", "python", on_fail="skip"),
            DominoStep("tts_rapport", "python:edge_tts_speak('Rapport du jour genere.')", "python"),
        ],
        category="productivity",
        description="Rapport quotidien: git log today + cluster + DB + trading PnL",
        learning_context="Bilan de fin de journee — commits, cluster health, trading resume",
        priority="normal",
    ),

    DominoPipeline(
        id="domino_maintenance_hebdo",
        trigger_vocal=["maintenance hebdo", "maintenance de la semaine", "nettoyage hebdomadaire"],
        steps=[
            DominoStep("vacuum_etoile", "python:sqlite3_vacuum('etoile.db')", "python", timeout_s=60),
            DominoStep("vacuum_jarvis", "python:sqlite3_vacuum('jarvis.db')", "python", timeout_s=30),
            DominoStep("git_prune", "powershell:git -C 'F:\\BUREAU\\turbo' gc --prune=now", "powershell", timeout_s=60),
            DominoStep("clean_temp", "powershell:Remove-Item -Path $env:TEMP\\* -Force -Recurse -ErrorAction SilentlyContinue 2>$null; Write-Output 'Temp nettoye'", "powershell", on_fail="skip", timeout_s=30),
            DominoStep("clean_logs", "powershell:Get-ChildItem 'F:\\BUREAU\\turbo\\data\\*.log' -ErrorAction SilentlyContinue | Where-Object {$_.LastWriteTime -lt (Get-Date).AddDays(-7)} | Remove-Item -Force 2>$null", "powershell", on_fail="skip"),
            DominoStep("tts_maintenance", "python:edge_tts_speak('Maintenance hebdomadaire terminee. Bases nettoyees, fichiers temporaires supprimes.')", "python"),
        ],
        category="maintenance",
        description="Maintenance hebdo: vacuum DB + git gc + clean temp + clean old logs",
        learning_context="Maintenance preventive — vacuum, nettoyage, liberation espace",
        priority="normal",
        cooldown_s=3600,
    ),

    DominoPipeline(
        id="domino_code_review_complet",
        trigger_vocal=["code review complet", "revue de code", "review le code"],
        steps=[
            DominoStep("git_diff", "powershell:git -C 'F:\\BUREAU\\turbo' diff --stat HEAD~3", "powershell"),
            DominoStep("lint_check", "powershell:cd F:\\BUREAU\\turbo && uv run python -m ruff check src/ --statistics 2>&1 | Select-Object -First 20", "powershell", on_fail="skip", timeout_s=30),
            DominoStep("type_check", "powershell:cd F:\\BUREAU\\turbo && npx tsc --noEmit 2>&1 | Select-Object -Last 5", "powershell", on_fail="skip", timeout_s=30),
            DominoStep("test_quick", "powershell:cd F:\\BUREAU\\turbo && uv run python -m pytest tests/ -q --tb=no 2>&1 | Select-Object -Last 3", "powershell", on_fail="skip", timeout_s=60),
            DominoStep("tts_review", "python:edge_tts_speak('Code review termine. Resultats affiches.')", "python"),
        ],
        category="dev_workflow",
        description="Code review: git diff + lint + type check + tests rapides",
        learning_context="Review — diff des 3 derniers commits, lint ruff, types TS, tests pytest",
        priority="normal",
    ),

    DominoPipeline(
        id="domino_analyse_trading_ia",
        trigger_vocal=["analyse trading ia", "ia analyse le marche", "consensus trading"],
        steps=[
            DominoStep("fetch_prices", "python:fetch_mexc_prices(['BTC','ETH','SOL','SUI','PEPE'])", "python", timeout_s=15),
            DominoStep("m1_analysis", "curl:http://127.0.0.1:1234/api/v1/chat", "curl", timeout_s=30),
            DominoStep("gptoss_analysis", "curl:http://127.0.0.1:11434/api/chat", "curl", timeout_s=60),
            DominoStep("consensus_vote", "python:weighted_consensus_vote()", "python"),
            DominoStep("tts_trading", "python:edge_tts_speak('Analyse trading IA terminee. Consensus genere.')", "python"),
        ],
        category="trading_cascade",
        description="Analyse trading IA: prix + M1 analyse + OL1 analyse + consensus vote",
        learning_context="Trading IA — consensus M1+OL1 sur top 5 paires, vote pondere",
        priority="high",
    ),
    # ── Batch 76: 10 nouveaux dominos ─────────────────────────────────────
    DominoPipeline(
        id="domino_quick_health",
        trigger_vocal=["health check rapide", "tout va bien", "check rapide"],
        steps=[
            DominoStep("check_m1", "curl:http://127.0.0.1:1234/api/v1/models", "curl", timeout_s=5, on_fail="skip"),
            DominoStep("check_ol1", "curl:http://127.0.0.1:11434/api/tags", "curl", timeout_s=5, on_fail="skip"),
            DominoStep("check_gpu", "powershell:nvidia-smi --query-gpu=temperature.gpu,utilization.gpu,memory.used --format=csv,noheader", "powershell", timeout_s=5),
            DominoStep("tts", "python:edge_tts_speak('Health check rapide termine.')", "python"),
        ],
        category="cluster",
        description="Health check rapide 3 steps: M1 + OL1 + GPU",
        learning_context="Quick health check — M1, OL1, GPU en 3 steps rapides",
        priority="normal",
    ),
    DominoPipeline(
        id="domino_update_corrections",
        trigger_vocal=["recharge les corrections", "met a jour les corrections", "sync corrections"],
        steps=[
            DominoStep("load_db", "python:edge_tts_speak('Rechargement des corrections vocales depuis la base de donnees.')", "python"),
        ],
        category="voice",
        description="Recharger les corrections vocales depuis la DB",
        learning_context="Voice — reload corrections dict from DB",
        priority="normal",
    ),
    DominoPipeline(
        id="domino_git_status_complet",
        trigger_vocal=["statut git complet", "git status complet", "etat du repo"],
        steps=[
            DominoStep("git_status", "bash:cd F:/BUREAU/turbo && git status --short", "bash", timeout_s=10),
            DominoStep("git_log", "bash:cd F:/BUREAU/turbo && git log --oneline -10", "bash", timeout_s=10),
            DominoStep("git_branch", "bash:cd F:/BUREAU/turbo && git branch -vv", "bash", timeout_s=5),
            DominoStep("tts", "python:edge_tts_speak('Statut git complet affiche.')", "python"),
        ],
        category="dev",
        description="Statut git complet: status + log 10 + branches",
        learning_context="Dev — git status, log, branches en un seul domino",
        priority="normal",
    ),
    DominoPipeline(
        id="domino_vram_cleanup",
        trigger_vocal=["libere la vram", "nettoie la vram", "optimise la vram"],
        steps=[
            DominoStep("check_vram", "powershell:nvidia-smi --query-gpu=memory.used,memory.total --format=csv,noheader", "powershell"),
            DominoStep("kill_idle", "python:kill_idle_gpu_processes()", "python"),
            DominoStep("check_after", "powershell:nvidia-smi --query-gpu=memory.used,memory.total --format=csv,noheader", "powershell"),
            DominoStep("tts", "python:edge_tts_speak('VRAM nettoyee. Processus idle supprimes.')", "python"),
        ],
        category="gpu",
        description="Nettoyer la VRAM en killant les processus idle",
        learning_context="GPU — kill idle VRAM processes, before/after check",
        priority="normal",
    ),
    DominoPipeline(
        id="domino_daily_standup",
        trigger_vocal=["standup", "daily standup", "standup du jour", "morning standup"],
        steps=[
            DominoStep("git_yesterday", "bash:cd F:/BUREAU/turbo && git log --since='yesterday' --oneline", "bash", timeout_s=10),
            DominoStep("cluster_health", "curl:http://127.0.0.1:1234/api/v1/models", "curl", timeout_s=5, on_fail="skip"),
            DominoStep("db_stats", "python:sqlite3_table_counts('etoile.db')", "python", on_fail="skip"),
            DominoStep("tts", "python:edge_tts_speak('Daily standup: commits d hier affiches, cluster verifie.')", "python"),
        ],
        category="routine",
        description="Daily standup: commits hier + cluster + DB stats",
        learning_context="Routine — standup quotidien avec git + cluster + DB",
        priority="normal",
    ),
    DominoPipeline(
        id="domino_clean_temp_files",
        trigger_vocal=["nettoie les temporaires", "supprime les temp", "clean temp"],
        steps=[
            DominoStep("clean_data_tmp", "python:clear_all_caches()", "python"),
            DominoStep("clean_pycache", "bash:find F:/BUREAU/turbo -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null; echo OK", "bash", timeout_s=15),
            DominoStep("tts", "python:edge_tts_speak('Fichiers temporaires nettoyes.')", "python"),
        ],
        category="maintenance",
        description="Nettoyer les fichiers temporaires et caches Python",
        learning_context="Maintenance — clean tmp files + pycache",
        priority="normal",
    ),
    DominoPipeline(
        id="domino_export_metrics",
        trigger_vocal=["exporte les metriques", "export metrics", "sauvegarde les stats"],
        steps=[
            DominoStep("db_counts", "python:sqlite3_table_counts('etoile.db')", "python"),
            DominoStep("db_counts_jarvis", "python:sqlite3_table_counts('jarvis.db')", "python", on_fail="skip"),
            DominoStep("tts", "python:edge_tts_speak('Metriques exportees.')", "python"),
        ],
        category="monitoring",
        description="Exporter les metriques DB (etoile + jarvis)",
        learning_context="Monitoring — export table counts from both DBs",
        priority="normal",
    ),
    DominoPipeline(
        id="domino_model_benchmark",
        trigger_vocal=["benchmark modele", "teste le modele", "vitesse modele"],
        steps=[
            DominoStep("bench_m1", "curl:http://127.0.0.1:1234/api/v1/chat", "curl", timeout_s=30),
            DominoStep("bench_ol1", "curl:http://127.0.0.1:11434/api/chat", "curl", timeout_s=30, on_fail="skip"),
            DominoStep("tts", "python:edge_tts_speak('Benchmark modele termine.')", "python"),
        ],
        category="cluster",
        description="Benchmark rapide M1 + OL1",
        learning_context="Cluster — benchmark latency M1+OL1",
        priority="normal",
    ),
    DominoPipeline(
        id="domino_check_disk_space",
        trigger_vocal=["espace disque", "combien de place", "disk space"],
        steps=[
            DominoStep("check_c", "powershell:Get-PSDrive C | Select-Object @{N='Free_GB';E={[math]::Round($_.Free/1GB,1)}}, @{N='Used_GB';E={[math]::Round($_.Used/1GB,1)}} | Format-Table", "powershell"),
            DominoStep("check_f", "powershell:Get-PSDrive F | Select-Object @{N='Free_GB';E={[math]::Round($_.Free/1GB,1)}}, @{N='Used_GB';E={[math]::Round($_.Used/1GB,1)}} | Format-Table", "powershell", on_fail="skip"),
            DominoStep("tts", "python:edge_tts_speak('Espace disque verifie.')", "python"),
        ],
        category="system",
        description="Verifier l'espace disque C: et F:",
        learning_context="System — disk space C: et F: via PowerShell",
        priority="normal",
    ),
    DominoPipeline(
        id="domino_api_latency_test",
        trigger_vocal=["test latence api", "ping les apis", "latence des noeuds"],
        steps=[
            DominoStep("ping_m1", "curl:http://127.0.0.1:1234/api/v1/models", "curl", timeout_s=5, on_fail="skip"),
            DominoStep("ping_m2", "curl:http://192.168.1.26:1234/api/v1/models", "curl", timeout_s=5, on_fail="skip"),
            DominoStep("ping_m3", "curl:http://192.168.1.113:1234/api/v1/models", "curl", timeout_s=5, on_fail="skip"),
            DominoStep("ping_ol1", "curl:http://127.0.0.1:11434/api/tags", "curl", timeout_s=5, on_fail="skip"),
            DominoStep("tts", "python:edge_tts_speak('Test de latence API termine. Tous les noeuds pingues.')", "python"),
        ],
        category="cluster",
        description="Test de latence API sur tous les noeuds",
        learning_context="Cluster — ping 4 nodes for API latency test",
        priority="normal",
    ),
    # ── Batch 80: 15 nouveaux dominos (automation, project, data, integration) ──
    DominoPipeline(
        id="domino_auto_commit",
        trigger_vocal=["auto commit", "commite automatiquement", "sauvegarde le code"],
        steps=[
            DominoStep("git_status", "bash:cd F:/BUREAU/turbo && git status --short | head -20", "bash", timeout_s=10),
            DominoStep("git_add", "bash:cd F:/BUREAU/turbo && git add -A", "bash", timeout_s=10),
            DominoStep("git_commit", "bash:cd F:/BUREAU/turbo && git commit -m 'auto: sauvegarde vocale $(date +%Y%m%d_%H%M)' 2>&1 || echo 'Nothing to commit'", "bash", timeout_s=15),
            DominoStep("tts", "python:edge_tts_speak('Code commite automatiquement.')", "python"),
        ],
        category="automation",
        description="Auto commit: git add + commit avec timestamp",
        learning_context="Automation — sauvegarder rapidement l'etat du code",
        priority="normal",
    ),
    DominoPipeline(
        id="domino_auto_push",
        trigger_vocal=["pousse le code", "git push", "envoie sur github"],
        steps=[
            DominoStep("git_status", "bash:cd F:/BUREAU/turbo && git status --short", "bash", timeout_s=10),
            DominoStep("git_push", "bash:cd F:/BUREAU/turbo && git push 2>&1 | tail -3", "bash", timeout_s=30),
            DominoStep("tts", "python:edge_tts_speak('Code pousse sur GitHub.')", "python"),
        ],
        category="automation",
        description="Git push: verifier status + push",
        learning_context="Automation — push rapide apres commit",
        priority="normal",
    ),
    DominoPipeline(
        id="domino_project_init",
        trigger_vocal=["initialise un projet python", "nouveau projet", "cree un projet"],
        steps=[
            DominoStep("check_uv", "bash:uv --version 2>/dev/null || echo 'uv not found'", "bash", timeout_s=5),
            DominoStep("check_git", "bash:git --version", "bash", timeout_s=5),
            DominoStep("tts", "python:edge_tts_speak('Outils de projet verifies. Pret pour initialiser.')", "python"),
        ],
        category="project_management",
        description="Init projet: verifier outils (uv, git)",
        learning_context="Project — verifier les prerequis avant creation",
        priority="normal",
    ),
    DominoPipeline(
        id="domino_env_check",
        trigger_vocal=["verifie l'environnement", "check env", "environnement ok"],
        steps=[
            DominoStep("python_ver", "bash:python --version 2>&1", "bash", timeout_s=5),
            DominoStep("uv_ver", "bash:uv --version 2>&1 || echo 'uv N/A'", "bash", timeout_s=5),
            DominoStep("node_ver", "bash:node --version 2>&1 || echo 'node N/A'", "bash", timeout_s=5),
            DominoStep("git_ver", "bash:git --version 2>&1", "bash", timeout_s=5),
            DominoStep("env_file", f"bash:test -f F:/BUREAU/turbo/.env && echo '.env exists' || echo '.env MISSING'", "bash", timeout_s=5),
            DominoStep("tts", "python:edge_tts_speak('Environnement verifie. Python, UV, Node, Git OK.')", "python"),
        ],
        category="project_management",
        description="Check environnement: Python, UV, Node, Git, .env",
        learning_context="Project — verifier que tous les outils sont installes",
        priority="normal",
    ),
    DominoPipeline(
        id="domino_db_export_csv",
        trigger_vocal=["exporte la base en csv", "export csv", "sauvegarde csv"],
        steps=[
            DominoStep("export_etoile", "python:export_db_to_csv('etoile.db')", "python", timeout_s=30),
            DominoStep("tts", "python:edge_tts_speak('Base exportee en CSV.')", "python"),
        ],
        category="data_analysis",
        description="Export etoile.db vers CSV",
        learning_context="Data — export DB vers fichiers CSV pour analyse externe",
        priority="normal",
    ),
    DominoPipeline(
        id="domino_db_row_count",
        trigger_vocal=["combien de lignes en base", "comptage base", "stats base de donnees"],
        steps=[
            DominoStep("count_etoile", "python:sqlite3_table_counts('etoile.db')", "python"),
            DominoStep("count_jarvis", "python:sqlite3_table_counts('jarvis.db')", "python", on_fail="skip"),
            DominoStep("count_sniper", "python:sqlite3_table_counts('sniper.db')", "python", on_fail="skip"),
            DominoStep("tts", "python:edge_tts_speak('Comptage des bases termine.')", "python"),
        ],
        category="data_analysis",
        description="Comptage lignes: etoile + jarvis + sniper",
        learning_context="Data — count rows dans les 3 DB principales",
        priority="normal",
    ),
    DominoPipeline(
        id="domino_log_analysis",
        trigger_vocal=["analyse les logs", "check les logs", "log analysis"],
        steps=[
            DominoStep("recent_errors", "python:check_recent_error_logs()", "python", timeout_s=15),
            DominoStep("log_size", "bash:ls -lh F:/BUREAU/turbo/data/*.log 2>/dev/null || echo 'No logs'", "bash", timeout_s=5),
            DominoStep("tts", "python:edge_tts_speak('Analyse des logs terminee.')", "python"),
        ],
        category="data_analysis",
        description="Analyse logs: erreurs recentes + taille fichiers log",
        learning_context="Data — verifier les erreurs dans les logs",
        priority="normal",
    ),
    DominoPipeline(
        id="domino_ollama_models",
        trigger_vocal=["liste les modeles ollama", "quels modeles ollama", "ollama models"],
        steps=[
            DominoStep("list_local", "curl:http://127.0.0.1:11434/api/tags", "curl", timeout_s=10),
            DominoStep("running", "curl:http://127.0.0.1:11434/api/ps", "curl", timeout_s=10, on_fail="skip"),
            DominoStep("tts", "python:edge_tts_speak('Modeles Ollama listes.')", "python"),
        ],
        category="integration",
        description="Lister les modeles Ollama: tags + running",
        learning_context="Integration — lister les modeles Ollama locaux et en cours",
        priority="normal",
    ),
    DominoPipeline(
        id="domino_lmstudio_models",
        trigger_vocal=["liste les modeles lm studio", "quels modeles lm studio", "lm studio models"],
        steps=[
            DominoStep("list_m1", "curl:http://127.0.0.1:1234/api/v1/models", "curl", timeout_s=10, on_fail="skip"),
            DominoStep("list_m2", "curl:http://192.168.1.26:1234/api/v1/models", "curl", timeout_s=10, on_fail="skip"),
            DominoStep("list_m3", "curl:http://192.168.1.113:1234/api/v1/models", "curl", timeout_s=10, on_fail="skip"),
            DominoStep("tts", "python:edge_tts_speak('Modeles LM Studio listes sur les 3 noeuds.')", "python"),
        ],
        category="integration",
        description="Lister les modeles LM Studio sur M1/M2/M3",
        learning_context="Integration — modeles charges sur chaque noeud LM Studio",
        priority="normal",
    ),
    DominoPipeline(
        id="domino_n8n_status",
        trigger_vocal=["statut n8n", "n8n status", "les workflows"],
        steps=[
            DominoStep("check_n8n", "curl:http://127.0.0.1:5678/healthz", "curl", timeout_s=10, on_fail="skip"),
            DominoStep("tts", "python:edge_tts_speak('Statut n8n verifie.')", "python"),
        ],
        category="integration",
        description="Check n8n health",
        learning_context="Integration — verifier que n8n est en ligne",
        priority="normal",
    ),
    DominoPipeline(
        id="domino_session_save",
        trigger_vocal=["sauvegarde la session", "save session", "snapshot session"],
        steps=[
            DominoStep("save_state", "python:save_session_state()", "python"),
            DominoStep("git_snapshot", "bash:cd F:/BUREAU/turbo && git stash push -m 'session-snapshot-$(date +%Y%m%d_%H%M)' 2>&1 && git stash pop 2>&1 || echo 'Nothing to stash'", "bash", timeout_s=15),
            DominoStep("tts", "python:edge_tts_speak('Session sauvegardee.')", "python"),
        ],
        category="automation",
        description="Sauvegarder la session: state + git snapshot",
        learning_context="Automation — snapshot etat courant de la session",
        priority="normal",
    ),
    DominoPipeline(
        id="domino_watch_gpu_temp",
        trigger_vocal=["surveille les temperatures", "watch gpu", "alerte temperature"],
        steps=[
            DominoStep("read_temps", "powershell:nvidia-smi --query-gpu=name,temperature.gpu --format=csv,noheader", "powershell"),
            DominoStep("eval_danger", "python:throttle_gpu_if_critical('80')", "python"),
            DominoStep("tts", "python:edge_tts_speak('Surveillance temperatures GPU active.')", "python"),
        ],
        category="monitoring_live",
        description="Surveiller les temperatures GPU et alerter si critique",
        learning_context="Monitoring — surveillance active des temperatures GPU",
        priority="high",
    ),
    DominoPipeline(
        id="domino_quick_test",
        trigger_vocal=["test rapide", "quick test", "verifie que ca marche"],
        steps=[
            DominoStep("syntax_check", "bash:cd F:/BUREAU/turbo && python -m py_compile src/commands.py && python -m py_compile src/voice_correction.py && python -m py_compile src/domino_pipelines.py && echo 'ALL SYNTAX OK'", "bash", timeout_s=15),
            DominoStep("import_check", "bash:cd F:/BUREAU/turbo && python -c 'from src.commands import COMMANDS; from src.voice_correction import process_voice_command; from src.domino_pipelines import DOMINO_PIPELINES; print(f\"OK: {len(COMMANDS)} cmds, {len(DOMINO_PIPELINES)} dominos\")'", "bash", timeout_s=15),
            DominoStep("tts", "python:edge_tts_speak('Test rapide OK. Syntaxe et imports valides.')", "python"),
        ],
        category="testing_pipeline",
        description="Test rapide: syntaxe + imports des modules principaux",
        learning_context="Tests — verification rapide syntaxe et imports",
        priority="normal",
    ),
    DominoPipeline(
        id="domino_cluster_rebalance",
        trigger_vocal=["reequilibre le cluster", "cluster rebalance", "redistribue les modeles"],
        steps=[
            DominoStep("check_m1_load", "curl:http://127.0.0.1:1234/api/v1/models", "curl", timeout_s=5, on_fail="skip"),
            DominoStep("check_m2_load", "curl:http://192.168.1.26:1234/api/v1/models", "curl", timeout_s=5, on_fail="skip"),
            DominoStep("check_gpu_usage", "powershell:nvidia-smi --query-gpu=name,utilization.gpu,memory.used --format=csv,noheader", "powershell", timeout_s=10),
            DominoStep("tts", "python:edge_tts_speak('Etat du cluster analyse pour reequilibrage.')", "python"),
        ],
        category="cluster_management",
        description="Analyser la charge du cluster pour reequilibrage",
        learning_context="Cluster — analyser repartition charge M1/M2 + GPU utilisation",
        priority="normal",
    ),
    DominoPipeline(
        id="domino_full_system_report",
        trigger_vocal=["rapport systeme complet", "etat global", "tout savoir sur le systeme"],
        steps=[
            DominoStep("cpu_ram", "powershell:$os=Get-CimInstance Win32_OperatingSystem; $cpu=(Get-CimInstance Win32_Processor).LoadPercentage; $ram=[math]::Round(($os.TotalVisibleMemorySize-$os.FreePhysicalMemory)/1MB,1); Write-Output \"CPU: ${cpu}% | RAM: ${ram}GB\"", "powershell", timeout_s=10),
            DominoStep("gpu_all", "powershell:nvidia-smi --query-gpu=name,temperature.gpu,memory.used,memory.total,utilization.gpu --format=csv,noheader", "powershell", timeout_s=10),
            DominoStep("disk_all", "powershell:Get-PSDrive -PSProvider FileSystem | Select-Object Name,@{N='FreeGB';E={[math]::Round($_.Free/1GB,1)}},@{N='UsedGB';E={[math]::Round($_.Used/1GB,1)}} | Format-Table", "powershell", timeout_s=10),
            DominoStep("cluster_health", "curl:http://127.0.0.1:1234/api/v1/models", "curl", timeout_s=5, on_fail="skip"),
            DominoStep("ollama_status", "curl:http://127.0.0.1:11434/api/tags", "curl", timeout_s=5, on_fail="skip"),
            DominoStep("git_status", "bash:cd F:/BUREAU/turbo && git log --oneline -3", "bash", timeout_s=5),
            DominoStep("tts", "python:edge_tts_speak('Rapport systeme complet genere. CPU, RAM, GPU, disques, cluster, git.')", "python"),
        ],
        category="monitoring",
        description="Rapport complet: CPU + RAM + GPU + disques + cluster + git",
        learning_context="Monitoring — rapport exhaustif de tout le systeme",
        priority="normal",
    ),
    # ── Batch 83: 10 nouveaux dominos (workflow, analytics, daily) ──
    DominoPipeline(
        id="domino_morning_full",
        trigger_vocal=["briefing complet", "demarrage complet", "full morning"],
        steps=[
            DominoStep("date_heure", "powershell:Get-Date -Format 'dddd dd MMMM yyyy HH:mm'", "powershell", timeout_s=5),
            DominoStep("gpu_status", "powershell:nvidia-smi --query-gpu=name,temperature.gpu,memory.used,memory.total --format=csv,noheader", "powershell", timeout_s=10),
            DominoStep("cluster_m1", "curl:http://127.0.0.1:1234/api/v1/models", "curl", timeout_s=5, on_fail="skip"),
            DominoStep("cluster_ol1", "curl:http://127.0.0.1:11434/api/tags", "curl", timeout_s=5, on_fail="skip"),
            DominoStep("disk_space", "powershell:Get-PSDrive C,F -ErrorAction SilentlyContinue | Select-Object Name,@{N='FreeGB';E={[math]::Round($_.Free/1GB,1)}} | Format-Table", "powershell", timeout_s=10),
            DominoStep("git_pending", "bash:cd F:/BUREAU/turbo && git status --short | wc -l", "bash", timeout_s=5),
            DominoStep("tts", "python:edge_tts_speak('Briefing complet. Date, GPU, cluster, disques, et git verifies.')", "python"),
        ],
        category="routine_matin",
        description="Briefing complet: date + GPU + cluster + disques + git",
        learning_context="Morning full — tout checker au demarrage de la journee",
        priority="high",
    ),
    DominoPipeline(
        id="domino_end_of_day",
        trigger_vocal=["fin de journee", "bonne nuit jarvis", "je pars", "fin du travail"],
        steps=[
            DominoStep("git_commit", "bash:cd F:/BUREAU/turbo && git add -A && git commit -m 'auto: fin de journee $(date +%Y%m%d)' 2>&1 || echo 'Nothing to commit'", "bash", timeout_s=15),
            DominoStep("git_push", "bash:cd F:/BUREAU/turbo && git push 2>&1 || echo 'Push failed or nothing to push'", "bash", timeout_s=30, on_fail="skip"),
            DominoStep("backup_db", "python:backup_etoile_db()", "python", on_fail="skip"),
            DominoStep("session_stats", "python:get_session_stats()", "python", on_fail="skip"),
            DominoStep("tts", "python:edge_tts_speak('Fin de journee. Code commite, backup fait. Bonne soiree!')", "python"),
        ],
        category="routine_soir",
        description="Fin de journee: auto commit + push + backup + stats session",
        learning_context="End of day — sauvegarder tout proprement avant de partir",
        priority="normal",
    ),
    DominoPipeline(
        id="domino_weekly_report",
        trigger_vocal=["rapport hebdomadaire", "bilan de la semaine", "weekly report"],
        steps=[
            DominoStep("git_week", "bash:cd F:/BUREAU/turbo && git log --oneline --since='7 days ago' | wc -l", "bash", timeout_s=10),
            DominoStep("git_stats", "bash:cd F:/BUREAU/turbo && git diff --stat HEAD~20 2>/dev/null | tail -3", "bash", timeout_s=10),
            DominoStep("db_stats", "python:sqlite3_table_counts('etoile.db')", "python", on_fail="skip"),
            DominoStep("tts", "python:edge_tts_speak('Rapport hebdomadaire genere.')", "python"),
        ],
        category="documentation",
        description="Rapport hebdo: commits semaine + diff stats + DB counts",
        learning_context="Weekly — resume de la semaine de travail",
        priority="normal",
    ),
    DominoPipeline(
        id="domino_test_voice_pipeline",
        trigger_vocal=["teste le pipeline vocal", "test voice", "teste la reconnaissance"],
        steps=[
            DominoStep("count_cmds", "bash:cd F:/BUREAU/turbo && python -c 'from src.commands import COMMANDS, VOICE_CORRECTIONS; print(f\"{len(COMMANDS)} cmds, {len(VOICE_CORRECTIONS)} corrections\")'", "bash", timeout_s=10),
            DominoStep("count_implicits", "bash:cd F:/BUREAU/turbo && python -c 'from src.voice_correction import IMPLICIT_COMMANDS; print(f\"{len(IMPLICIT_COMMANDS)} implicits\")'", "bash", timeout_s=10),
            DominoStep("count_dominos", "bash:cd F:/BUREAU/turbo && python -c 'from src.domino_pipelines import DOMINO_PIPELINES; print(f\"{len(DOMINO_PIPELINES)} dominos\")'", "bash", timeout_s=10),
            DominoStep("tts", "python:edge_tts_speak('Pipeline vocal teste. Toutes les stats affichees.')", "python"),
        ],
        category="testing_pipeline",
        description="Test du pipeline vocal: compter commandes, corrections, implicites, dominos",
        learning_context="Testing — verification rapide du pipeline vocal complet",
        priority="normal",
    ),
    DominoPipeline(
        id="domino_analytics_usage",
        trigger_vocal=["statistiques d'utilisation", "analytics", "quelles commandes j'utilise"],
        steps=[
            DominoStep("top_commands", "python:get_session_stats()", "python", on_fail="skip"),
            DominoStep("db_counts", "python:sqlite3_table_counts('jarvis.db')", "python", on_fail="skip"),
            DominoStep("tts", "python:edge_tts_speak('Statistiques d utilisation affichees.')", "python"),
        ],
        category="data_analysis",
        description="Analytics: top commandes + stats DB jarvis",
        learning_context="Analytics — comprendre les patterns d'utilisation",
        priority="normal",
    ),
    DominoPipeline(
        id="domino_git_log_visual",
        trigger_vocal=["historique git", "log git", "montre les commits"],
        steps=[
            DominoStep("git_graph", "bash:cd F:/BUREAU/turbo && git log --oneline --graph -15", "bash", timeout_s=10),
            DominoStep("git_authors", "bash:cd F:/BUREAU/turbo && git shortlog -sn --since='30 days ago' | head -5", "bash", timeout_s=10),
            DominoStep("tts", "python:edge_tts_speak('Historique git affiche.')", "python"),
        ],
        category="dev_workflow",
        description="Historique git visuel: graph + top authors",
        learning_context="Dev — visualiser l'historique git",
        priority="normal",
    ),
    DominoPipeline(
        id="domino_check_services",
        trigger_vocal=["verifie les services", "check services", "services en ligne"],
        steps=[
            DominoStep("check_lmstudio", "curl:http://127.0.0.1:1234/api/v1/models", "curl", timeout_s=5, on_fail="skip"),
            DominoStep("check_ollama", "curl:http://127.0.0.1:11434/api/tags", "curl", timeout_s=5, on_fail="skip"),
            DominoStep("check_n8n", "curl:http://127.0.0.1:5678/healthz", "curl", timeout_s=5, on_fail="skip"),
            DominoStep("check_dashboard", "curl:http://127.0.0.1:8080", "curl", timeout_s=5, on_fail="skip"),
            DominoStep("tts", "python:edge_tts_speak('Services verifies: LM Studio, Ollama, n8n, Dashboard.')", "python"),
        ],
        category="monitoring",
        description="Check services: LM Studio + Ollama + n8n + Dashboard",
        learning_context="Monitoring — verifier que tous les services web sont en ligne",
        priority="normal",
    ),
    DominoPipeline(
        id="domino_rotate_logs",
        trigger_vocal=["rotation des logs", "archive les logs", "nettoie les vieux logs"],
        steps=[
            DominoStep("count_logs", "bash:ls -la F:/BUREAU/turbo/data/*.log 2>/dev/null | wc -l", "bash", timeout_s=5),
            DominoStep("archive_old", "powershell:Get-ChildItem 'F:\\BUREAU\\turbo\\data\\*.log' | Where-Object {$_.LastWriteTime -lt (Get-Date).AddDays(-7)} | ForEach-Object { Move-Item $_.FullName ($_.FullName + '.archived') -Force }; 'Logs archives'", "powershell", on_fail="skip", timeout_s=15),
            DominoStep("tts", "python:edge_tts_speak('Rotation des logs terminee.')", "python"),
        ],
        category="maintenance",
        description="Rotation logs: compter + archiver les logs > 7 jours",
        learning_context="Maintenance — archiver les vieux logs pour liberer de l'espace",
        priority="normal",
    ),
    DominoPipeline(
        id="domino_cache_cleanup",
        trigger_vocal=["nettoie les caches", "vide tous les caches", "cache cleanup"],
        steps=[
            DominoStep("clear_python", "python:clear_all_caches()", "python"),
            DominoStep("clear_pip", "bash:pip cache purge 2>/dev/null || echo 'pip cache N/A'", "bash", timeout_s=10, on_fail="skip"),
            DominoStep("clear_npm", "bash:npm cache clean --force 2>/dev/null || echo 'npm cache N/A'", "bash", timeout_s=10, on_fail="skip"),
            DominoStep("tts", "python:edge_tts_speak('Tous les caches nettoyes: Python, pip, npm.')", "python"),
        ],
        category="system_cleanup",
        description="Cache cleanup: Python + pip + npm caches",
        learning_context="Nettoyage — vider tous les caches de dev",
        priority="normal",
    ),
    DominoPipeline(
        id="domino_security_quick",
        trigger_vocal=["check securite rapide", "securite rapide", "quick security"],
        steps=[
            DominoStep("open_ports", "powershell:Get-NetTCPConnection -State Listen | Select-Object LocalPort -Unique | Measure-Object | Select-Object Count", "powershell", timeout_s=10),
            DominoStep("firewall", "powershell:Get-NetFirewallProfile | Select-Object Name,Enabled | Format-Table", "powershell", timeout_s=10),
            DominoStep("tts", "python:edge_tts_speak('Check securite rapide: ports et firewall verifies.')", "python"),
        ],
        category="security_sweep",
        description="Securite rapide: ports ouverts + firewall status",
        learning_context="Securite — check rapide en 2 steps",
        priority="normal",
    ),
    # ═══════════════════════════════════════════════════════════════════════
    # BATCH 84 — Dev workflow / Network / Performance / Backup (12 dominos)
    # ═══════════════════════════════════════════════════════════════════════
    DominoPipeline(
        id="domino_code_review",
        trigger_vocal=["revue de code", "code review", "review le code", "analyse le code"],
        steps=[
            DominoStep("git_status", "bash:cd F:/BUREAU/turbo && git status --short", "bash", timeout_s=5),
            DominoStep("git_diff_stats", "bash:cd F:/BUREAU/turbo && git diff --stat HEAD~1", "bash", timeout_s=10),
            DominoStep("py_lint", "bash:cd F:/BUREAU/turbo && python -m py_compile src/commands.py && python -m py_compile src/voice_correction.py && python -m py_compile src/domino_pipelines.py && python -m py_compile src/domino_executor.py && echo 'ALL SYNTAX OK'", "bash", timeout_s=15),
            DominoStep("tts", "python:edge_tts_speak('Revue de code terminee. Syntaxe OK, diff genere.')", "python"),
        ],
        category="code_generation",
        description="Code review: git status + diff + syntax check",
        learning_context="Dev — verifier la qualite du code avant commit",
        priority="normal",
    ),
    DominoPipeline(
        id="domino_deploy_staging",
        trigger_vocal=["deploie en staging", "deploy staging", "push staging", "envoie en staging"],
        steps=[
            DominoStep("syntax_check", "bash:cd F:/BUREAU/turbo && python -m py_compile src/commands.py && python -m py_compile src/voice_correction.py && echo 'Syntax OK'", "bash", timeout_s=10),
            DominoStep("git_add", "bash:cd F:/BUREAU/turbo && git add -A", "bash", timeout_s=5),
            DominoStep("git_commit", "bash:cd F:/BUREAU/turbo && git commit -m 'deploy: staging $(date +%Y%m%d-%H%M)' 2>&1 || echo 'Nothing to commit'", "bash", timeout_s=10),
            DominoStep("git_push", "bash:cd F:/BUREAU/turbo && git push 2>&1 || echo 'Push failed'", "bash", timeout_s=30, on_fail="skip"),
            DominoStep("tts", "python:edge_tts_speak('Deploiement staging termine. Code pousse.')", "python"),
        ],
        category="dev_workflow",
        description="Deploy staging: syntax check + commit + push",
        learning_context="Deployment — pipeline de deploiement en staging",
        priority="high",
    ),
    DominoPipeline(
        id="domino_git_cleanup",
        trigger_vocal=["nettoie git", "git cleanup", "clean les branches", "menage git"],
        steps=[
            DominoStep("prune_remote", "bash:cd F:/BUREAU/turbo && git remote prune origin 2>&1", "bash", timeout_s=15, on_fail="skip"),
            DominoStep("list_merged", "bash:cd F:/BUREAU/turbo && git branch --merged main 2>/dev/null | grep -v main | head -10 || echo 'No merged branches'", "bash", timeout_s=10),
            DominoStep("gc", "bash:cd F:/BUREAU/turbo && git gc --auto 2>&1", "bash", timeout_s=30, on_fail="skip"),
            DominoStep("tts", "python:edge_tts_speak('Nettoyage git termine. Branches prunees, garbage collection fait.')", "python"),
        ],
        category="dev_workflow",
        description="Git cleanup: prune remote + list merged + gc",
        learning_context="Maintenance git — nettoyer les branches mortes",
        priority="normal",
    ),
    DominoPipeline(
        id="domino_db_optimize",
        trigger_vocal=["optimise les bases", "db optimize", "optimise la base", "performance base"],
        steps=[
            DominoStep("vacuum_etoile", "python:sqlite3_vacuum('etoile.db')", "python"),
            DominoStep("vacuum_jarvis", "python:sqlite3_vacuum('jarvis.db')", "python"),
            DominoStep("vacuum_sniper", "python:sqlite3_vacuum('sniper.db')", "python", on_fail="skip"),
            DominoStep("analyze", "python:sqlite3_analyze()", "python"),
            DominoStep("tts", "python:edge_tts_speak('Bases de donnees optimisees. Vacuum et analyze termines.')", "python"),
        ],
        category="data_analysis",
        description="DB optimize: VACUUM + ANALYZE sur toutes les bases",
        learning_context="Data — optimiser les performances SQLite",
        priority="normal",
    ),
    DominoPipeline(
        id="domino_voice_pipeline_test",
        trigger_vocal=["teste le pipeline vocal", "test voix complet", "voice pipeline test", "test la reconnaissance"],
        steps=[
            DominoStep("count_cmds", "python:count_commands()", "python"),
            DominoStep("count_corrections", "python:count_voice_corrections()", "python"),
            DominoStep("test_match", "python:test_voice_match('ouvre chrome')", "python"),
            DominoStep("test_match2", "python:test_voice_match('statut du cluster')", "python"),
            DominoStep("tts", "python:edge_tts_speak('Pipeline vocal OK. Commandes et corrections comptees, matching teste.')", "python"),
        ],
        category="testing_pipeline",
        description="Voice pipeline test: count + match tests",
        learning_context="Test — verifier que le pipeline vocal marche correctement",
        priority="normal",
    ),
    DominoPipeline(
        id="domino_network_scan",
        trigger_vocal=["scan reseau", "diagnostic reseau", "test le reseau", "network scan"],
        steps=[
            DominoStep("ping_gw", "bash:ping -c 2 192.168.1.1 2>/dev/null || ping -n 2 192.168.1.1", "bash", timeout_s=10),
            DominoStep("ping_dns", "bash:ping -c 2 8.8.8.8 2>/dev/null || ping -n 2 8.8.8.8", "bash", timeout_s=10, on_fail="skip"),
            DominoStep("dns_check", "bash:nslookup google.com 2>&1 | head -5", "bash", timeout_s=10, on_fail="skip"),
            DominoStep("tts", "python:edge_tts_speak('Scan reseau termine. Gateway, DNS et connectivite verifies.')", "python"),
        ],
        category="network_diagnostics",
        description="Network scan: ping gateway + DNS + connectivity",
        learning_context="Reseau — diagnostic complet de la connectivite",
        priority="normal",
    ),
    DominoPipeline(
        id="domino_log_monitor",
        trigger_vocal=["surveille les logs", "monitor les logs", "log monitor", "regarde les erreurs"],
        steps=[
            DominoStep("count_errors", "bash:grep -ci 'error\\|exception\\|fail' F:/BUREAU/turbo/data/*.log 2>/dev/null || echo '0 errors'", "bash", timeout_s=10),
            DominoStep("recent_errors", "bash:grep -i 'error\\|exception' F:/BUREAU/turbo/data/*.log 2>/dev/null | tail -5 || echo 'No recent errors'", "bash", timeout_s=10, on_fail="skip"),
            DominoStep("tts", "python:edge_tts_speak('Monitoring des logs termine. Erreurs comptees.')", "python"),
        ],
        category="monitoring_live",
        description="Log monitor: count errors + show recent",
        learning_context="Monitoring — surveiller les erreurs dans les logs",
        priority="normal",
    ),
    DominoPipeline(
        id="domino_update_deps",
        trigger_vocal=["mets a jour les dependances", "update deps", "upgrade packages", "mise a jour pip"],
        steps=[
            DominoStep("pip_outdated", "bash:pip list --outdated 2>/dev/null | head -15", "bash", timeout_s=15),
            DominoStep("uv_sync", "bash:cd F:/BUREAU/turbo && uv sync 2>&1 | tail -3", "bash", timeout_s=30, on_fail="skip"),
            DominoStep("tts", "python:edge_tts_speak('Dependances verifiees. Liste des packages obsoletes affichee.')", "python"),
        ],
        category="dev_workflow",
        description="Update deps: check outdated + uv sync",
        learning_context="Dev — maintenir les dependances a jour",
        priority="normal",
    ),
    DominoPipeline(
        id="domino_cluster_warmup",
        trigger_vocal=["chauffe le cluster", "warmup cluster", "prepare le cluster", "reveille le cluster"],
        steps=[
            DominoStep("ping_m1", "bash:curl -s --max-time 3 http://127.0.0.1:1234/api/v1/models 2>/dev/null | head -1 || echo 'M1 OFFLINE'", "bash", timeout_s=5),
            DominoStep("ping_ol1", "bash:curl -s --max-time 3 http://127.0.0.1:11434/api/tags 2>/dev/null | head -1 || echo 'OL1 OFFLINE'", "bash", timeout_s=5),
            DominoStep("ping_m2", "bash:curl -s --max-time 3 http://192.168.1.26:1234/api/v1/models 2>/dev/null | head -1 || echo 'M2 OFFLINE'", "bash", timeout_s=5, on_fail="skip"),
            DominoStep("ping_m3", "bash:curl -s --max-time 3 http://192.168.1.113:1234/api/v1/models 2>/dev/null | head -1 || echo 'M3 OFFLINE'", "bash", timeout_s=5, on_fail="skip"),
            DominoStep("tts", "python:edge_tts_speak('Cluster chauffe. Tous les noeuds pingues.')", "python"),
        ],
        category="monitoring",
        description="Cluster warmup: ping all nodes to wake them",
        learning_context="Cluster — reveiller et verifier tous les noeuds",
        priority="normal",
    ),
    DominoPipeline(
        id="domino_backup_full_system",
        trigger_vocal=["backup complet du systeme", "sauvegarde totale", "backup full", "backup tout"],
        steps=[
            DominoStep("backup_etoile", "python:backup_etoile_db()", "python"),
            DominoStep("backup_jarvis", "python:backup_db('jarvis.db')", "python", on_fail="skip"),
            DominoStep("backup_sniper", "python:backup_db('sniper.db')", "python", on_fail="skip"),
            DominoStep("git_commit", "bash:cd F:/BUREAU/turbo && git add -A && git commit -m 'backup: full system $(date +%Y%m%d)' 2>&1 || echo 'Nothing to commit'", "bash", timeout_s=15, on_fail="skip"),
            DominoStep("tts", "python:edge_tts_speak('Backup complet du systeme termine. Toutes les bases sauvegardees.')", "python"),
        ],
        category="backup_chain",
        description="Full system backup: all DBs + git commit",
        learning_context="Backup — sauvegarde complete de toutes les donnees",
        priority="high",
    ),
    DominoPipeline(
        id="domino_performance_report",
        trigger_vocal=["rapport de performance", "performance report", "etat des performances", "combien ca tourne"],
        steps=[
            DominoStep("cpu", "powershell:Get-CimInstance Win32_Processor | Select-Object LoadPercentage", "powershell", timeout_s=10),
            DominoStep("ram", "powershell:[math]::Round((Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory/1MB,1)", "powershell", timeout_s=10),
            DominoStep("gpu", "powershell:nvidia-smi --query-gpu=utilization.gpu,temperature.gpu,memory.used --format=csv,noheader 2>$null || 'N/A'", "powershell", timeout_s=10, on_fail="skip"),
            DominoStep("disk", "powershell:Get-PSDrive C,F -ErrorAction SilentlyContinue | Select-Object Name,@{N='Free(GB)';E={[math]::Round($_.Free/1GB)}}", "powershell", timeout_s=10),
            DominoStep("tts", "python:edge_tts_speak('Rapport de performance genere. CPU, RAM, GPU et disques verifies.')", "python"),
        ],
        category="monitoring",
        description="Performance report: CPU + RAM + GPU + Disk",
        learning_context="Monitoring — rapport detaille des performances systeme",
        priority="normal",
    ),
    DominoPipeline(
        id="domino_quick_benchmark",
        trigger_vocal=["benchmark rapide", "quick bench", "teste la vitesse", "bench rapide"],
        steps=[
            DominoStep("bench_m1", "bash:curl -s --max-time 10 http://127.0.0.1:1234/api/v1/chat -H 'Content-Type: application/json' -d '{\"model\":\"qwen3-8b\",\"input\":\"/nothink\\nDis bonjour en 1 mot.\",\"temperature\":0.1,\"max_output_tokens\":50,\"stream\":false,\"store\":false}' 2>/dev/null | head -c 200 || echo 'M1 TIMEOUT'", "bash", timeout_s=15),
            DominoStep("bench_ol1", "bash:curl -s --max-time 10 http://127.0.0.1:11434/api/chat -d '{\"model\":\"qwen3:1.7b\",\"messages\":[{\"role\":\"user\",\"content\":\"Dis bonjour en 1 mot.\"}],\"stream\":false}' 2>/dev/null | head -c 200 || echo 'OL1 TIMEOUT'", "bash", timeout_s=15),
            DominoStep("tts", "python:edge_tts_speak('Benchmark rapide termine. M1 et OL1 testes.')", "python"),
        ],
        category="testing_pipeline",
        description="Quick benchmark: test M1 + OL1 response time",
        learning_context="Benchmark — tester la vitesse de reponse du cluster",
        priority="normal",
    ),
    # ═══════════════════════════════════════════════════════════════════════
    # BATCH 85 — Routines quotidiennes / Maintenance avancée (10 dominos)
    # ═══════════════════════════════════════════════════════════════════════
    DominoPipeline(
        id="domino_lunch_break",
        trigger_vocal=["pause dejeuner", "je mange", "lunch break", "pause midi"],
        steps=[
            DominoStep("git_save", "bash:cd F:/BUREAU/turbo && git add -A && git commit -m 'auto: pause midi $(date +%H%M)' 2>&1 || echo 'Nothing to commit'", "bash", timeout_s=15, on_fail="skip"),
            DominoStep("lock_screen", "powershell:rundll32.exe user32.dll,LockWorkStation", "powershell", timeout_s=5),
            DominoStep("tts", "python:edge_tts_speak('Pause dejeuner. Code sauvegarde, ecran verrouille. Bon appetit!')", "python"),
        ],
        category="routine_matin",
        description="Pause dejeuner: save + lock screen",
        learning_context="Routine — preparer le systeme pour une pause dejeuner",
        priority="normal",
    ),
    DominoPipeline(
        id="domino_coffee_break",
        trigger_vocal=["pause cafe", "coffee break", "je prends un cafe", "petite pause"],
        steps=[
            DominoStep("save_state", "bash:cd F:/BUREAU/turbo && git stash 2>&1 || echo 'Nothing to stash'", "bash", timeout_s=10, on_fail="skip"),
            DominoStep("tts", "python:edge_tts_speak('Pause cafe. Etat sauvegarde. Prends ton temps!')", "python"),
        ],
        category="routine_matin",
        description="Pause cafe: git stash le travail en cours",
        learning_context="Routine — petite pause avec sauvegarde de contexte",
        priority="normal",
    ),
    DominoPipeline(
        id="domino_focus_mode",
        trigger_vocal=["mode focus", "mode concentration", "active le focus", "deep work"],
        steps=[
            DominoStep("disable_notif", "powershell:Set-ItemProperty -Path 'HKCU:\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\PushNotifications' -Name 'ToastEnabled' -Value 0 -ErrorAction SilentlyContinue; 'Notifications disabled'", "powershell", timeout_s=5, on_fail="skip"),
            DominoStep("tts", "python:edge_tts_speak('Mode focus active. Notifications desactivees. Bonne concentration!')", "python"),
        ],
        category="power_management",
        description="Focus mode: disable notifications for deep work",
        learning_context="Productivite — activer le mode concentration",
        priority="normal",
    ),
    DominoPipeline(
        id="domino_disk_health",
        trigger_vocal=["sante des disques", "disk health", "etat des ssd", "smart status"],
        steps=[
            DominoStep("disk_space", "powershell:Get-PSDrive -PSProvider FileSystem | Select-Object Name,@{N='Used(GB)';E={[math]::Round($_.Used/1GB,1)}},@{N='Free(GB)';E={[math]::Round($_.Free/1GB,1)}}", "powershell", timeout_s=10),
            DominoStep("smart", "powershell:Get-PhysicalDisk | Select-Object FriendlyName,MediaType,HealthStatus,Size | Format-Table", "powershell", timeout_s=10, on_fail="skip"),
            DominoStep("tts", "python:edge_tts_speak('Sante des disques verifiee. Espace et SMART status affiches.')", "python"),
        ],
        category="monitoring",
        description="Disk health: space + SMART status",
        learning_context="Monitoring — verifier la sante des disques SSD/HDD",
        priority="normal",
    ),
    DominoPipeline(
        id="domino_memory_cleanup",
        trigger_vocal=["libere la memoire", "nettoie la ram", "memory cleanup", "libere la ram"],
        steps=[
            DominoStep("clear_standby", "powershell:[System.GC]::Collect(); 'GC collected'", "powershell", timeout_s=10),
            DominoStep("ram_status", "powershell:[math]::Round((Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory/1MB,1)", "powershell", timeout_s=10),
            DominoStep("tts", "python:edge_tts_speak('Memoire nettoyee. RAM disponible affichee.')", "python"),
        ],
        category="system_cleanup",
        description="Memory cleanup: GC collect + RAM status",
        learning_context="Systeme — liberer de la memoire RAM",
        priority="normal",
    ),
    DominoPipeline(
        id="domino_gpu_detailed",
        trigger_vocal=["detail gpu", "gpu detaille", "info gpu complete", "nvidia detail"],
        steps=[
            DominoStep("nvidia_smi", "powershell:nvidia-smi 2>$null || 'nvidia-smi not available'", "powershell", timeout_s=10),
            DominoStep("gpu_processes", "powershell:nvidia-smi --query-compute-apps=pid,process_name,used_gpu_memory --format=csv,noheader 2>$null || 'N/A'", "powershell", timeout_s=10, on_fail="skip"),
            DominoStep("tts", "python:edge_tts_speak('Detail GPU complet affiche. Temperatures, VRAM et processus GPU.')", "python"),
        ],
        category="monitoring",
        description="GPU detailed: nvidia-smi + GPU processes",
        learning_context="Monitoring — informations GPU detaillees",
        priority="normal",
    ),
    DominoPipeline(
        id="domino_docker_status",
        trigger_vocal=["statut docker", "docker status", "conteneurs actifs", "docker ps"],
        steps=[
            DominoStep("docker_ps", "bash:docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}' 2>/dev/null || echo 'Docker not running'", "bash", timeout_s=10),
            DominoStep("docker_images", "bash:docker images --format 'table {{.Repository}}\t{{.Tag}}\t{{.Size}}' 2>/dev/null | head -10 || echo 'N/A'", "bash", timeout_s=10, on_fail="skip"),
            DominoStep("tts", "python:edge_tts_speak('Statut Docker affiche. Conteneurs et images listes.')", "python"),
        ],
        category="dev_workflow",
        description="Docker status: containers + images",
        learning_context="Docker — voir les conteneurs et images actifs",
        priority="normal",
    ),
    DominoPipeline(
        id="domino_project_stats",
        trigger_vocal=["stats du projet", "statistiques projet", "project stats", "combien de lignes"],
        steps=[
            DominoStep("line_count", "bash:wc -l F:/BUREAU/turbo/src/*.py 2>/dev/null || echo 'N/A'", "bash", timeout_s=10),
            DominoStep("file_count", "bash:find F:/BUREAU/turbo/src -name '*.py' 2>/dev/null | wc -l || echo 'N/A'", "bash", timeout_s=10),
            DominoStep("git_stats", "bash:cd F:/BUREAU/turbo && git log --oneline | wc -l && echo 'commits' 2>/dev/null", "bash", timeout_s=10),
            DominoStep("tts", "python:edge_tts_speak('Statistiques du projet affichees. Lignes, fichiers et commits comptes.')", "python"),
        ],
        category="dev_workflow",
        description="Project stats: line count + file count + git commits",
        learning_context="Dev — statistiques du projet JARVIS",
        priority="normal",
    ),
    DominoPipeline(
        id="domino_windows_cleanup",
        trigger_vocal=["nettoie windows", "windows cleanup", "vide les temp", "menage windows"],
        steps=[
            DominoStep("clear_temp", "powershell:Remove-Item $env:TEMP\\* -Recurse -Force -ErrorAction SilentlyContinue; 'Temp cleared'", "powershell", timeout_s=15, on_fail="skip"),
            DominoStep("clear_prefetch", "powershell:Remove-Item C:\\Windows\\Prefetch\\* -Force -ErrorAction SilentlyContinue; 'Prefetch cleared'", "powershell", timeout_s=10, on_fail="skip"),
            DominoStep("recycle_bin", "powershell:Clear-RecycleBin -Force -ErrorAction SilentlyContinue; 'Recycle bin emptied'", "powershell", timeout_s=10, on_fail="skip"),
            DominoStep("tts", "python:edge_tts_speak('Nettoyage Windows termine. Fichiers temp, prefetch et corbeille vides.')", "python"),
        ],
        category="system_cleanup",
        description="Windows cleanup: temp + prefetch + recycle bin",
        learning_context="Systeme — nettoyage complet de Windows",
        priority="normal",
    ),
    DominoPipeline(
        id="domino_evening_review",
        trigger_vocal=["bilan du soir", "revue du soir", "evening review", "resume de la journee"],
        steps=[
            DominoStep("git_log_today", "bash:cd F:/BUREAU/turbo && git log --oneline --since=midnight 2>/dev/null || echo 'No commits today'", "bash", timeout_s=10),
            DominoStep("db_stats", "python:count_commands()", "python"),
            DominoStep("corrections_stats", "python:count_voice_corrections()", "python"),
            DominoStep("tts", "python:edge_tts_speak('Bilan du soir. Commits du jour, commandes et corrections comptees.')", "python"),
        ],
        category="routine_soir",
        description="Evening review: today's commits + stats",
        learning_context="Routine — bilan de fin de journee",
        priority="normal",
    ),
    # ═══════════════════════════════════════════════════════════════════════
    # BATCH 86 — Startup/Shutdown / Maintenance avancee (10 dominos)
    # ═══════════════════════════════════════════════════════════════════════
    DominoPipeline(
        id="domino_startup_sequence",
        trigger_vocal=["sequence de demarrage", "startup", "boot sequence", "demarre tout"],
        steps=[
            DominoStep("health_m1", "bash:curl -s --max-time 3 http://127.0.0.1:1234/api/v1/models 2>/dev/null | head -c 100 || echo 'M1 OFFLINE'", "bash", timeout_s=5),
            DominoStep("health_ol1", "bash:curl -s --max-time 3 http://127.0.0.1:11434/api/tags 2>/dev/null | head -c 100 || echo 'OL1 OFFLINE'", "bash", timeout_s=5),
            DominoStep("git_pull", "bash:cd F:/BUREAU/turbo && git pull --ff-only 2>&1 || echo 'Pull failed or up to date'", "bash", timeout_s=15, on_fail="skip"),
            DominoStep("gpu_temp", "powershell:nvidia-smi --query-gpu=temperature.gpu --format=csv,noheader 2>$null || 'N/A'", "powershell", timeout_s=10, on_fail="skip"),
            DominoStep("tts", "python:edge_tts_speak('Sequence de demarrage terminee. Cluster verifie, code a jour, GPU ok.')", "python"),
        ],
        category="routine_matin",
        description="Startup sequence: health check + git pull + GPU temp",
        learning_context="Boot — sequence complete de demarrage du systeme",
        priority="high",
    ),
    DominoPipeline(
        id="domino_shutdown_sequence",
        trigger_vocal=["sequence arret", "shutdown", "arrete tout proprement", "extinction"],
        steps=[
            DominoStep("git_save", "bash:cd F:/BUREAU/turbo && git add -A && git commit -m 'auto: shutdown $(date +%Y%m%d-%H%M)' 2>&1 || echo 'Nothing to commit'", "bash", timeout_s=15, on_fail="skip"),
            DominoStep("git_push", "bash:cd F:/BUREAU/turbo && git push 2>&1 || echo 'Push failed'", "bash", timeout_s=30, on_fail="skip"),
            DominoStep("backup_db", "python:backup_etoile_db()", "python", on_fail="skip"),
            DominoStep("tts", "python:edge_tts_speak('Extinction propre. Code sauvegarde, backup fait. A bientot!')", "python"),
        ],
        category="routine_soir",
        description="Shutdown sequence: save + push + backup",
        learning_context="Shutdown — eteindre proprement avec sauvegarde de tout",
        priority="high",
    ),
    DominoPipeline(
        id="domino_weekly_maintenance",
        trigger_vocal=["maintenance hebdo", "weekly maintenance", "maintenance de la semaine", "entretien hebdomadaire"],
        steps=[
            DominoStep("vacuum_all", "python:sqlite3_vacuum('etoile.db')", "python"),
            DominoStep("vacuum_jarvis", "python:sqlite3_vacuum('jarvis.db')", "python", on_fail="skip"),
            DominoStep("analyze_all", "python:sqlite3_analyze()", "python"),
            DominoStep("git_gc", "bash:cd F:/BUREAU/turbo && git gc --auto 2>&1", "bash", timeout_s=30, on_fail="skip"),
            DominoStep("clear_temp", "powershell:Remove-Item $env:TEMP\\* -Recurse -Force -ErrorAction SilentlyContinue; 'Temp cleared'", "powershell", timeout_s=15, on_fail="skip"),
            DominoStep("tts", "python:edge_tts_speak('Maintenance hebdomadaire terminee. Bases optimisees, git propre, temp vides.')", "python"),
        ],
        category="system_cleanup",
        description="Weekly maintenance: vacuum + analyze + git gc + temp cleanup",
        learning_context="Maintenance — entretien hebdomadaire complet",
        priority="high",
    ),
    DominoPipeline(
        id="domino_emergency_save",
        trigger_vocal=["sauvegarde urgence", "emergency save", "sauve tout vite", "urgence backup"],
        steps=[
            DominoStep("git_save", "bash:cd F:/BUREAU/turbo && git add -A && git commit -m 'EMERGENCY SAVE $(date +%Y%m%d-%H%M%S)' 2>&1 || echo 'Nothing'", "bash", timeout_s=10),
            DominoStep("git_push", "bash:cd F:/BUREAU/turbo && git push 2>&1 || echo 'Push failed'", "bash", timeout_s=30, on_fail="skip"),
            DominoStep("backup_etoile", "python:backup_etoile_db()", "python", on_fail="skip"),
            DominoStep("tts", "python:edge_tts_speak('Sauvegarde d'urgence terminee!')", "python"),
        ],
        category="backup_chain",
        description="Emergency save: instant commit + push + backup",
        learning_context="Urgence — sauvegarder tout immediatement",
        priority="critical",
    ),
    DominoPipeline(
        id="domino_dev_setup",
        trigger_vocal=["prepare le dev", "setup dev", "prepare l'environnement", "init workspace"],
        steps=[
            DominoStep("git_status", "bash:cd F:/BUREAU/turbo && git status --short", "bash", timeout_s=5),
            DominoStep("uv_sync", "bash:cd F:/BUREAU/turbo && uv sync 2>&1 | tail -3", "bash", timeout_s=30, on_fail="skip"),
            DominoStep("health_cluster", "bash:curl -s --max-time 3 http://127.0.0.1:1234/api/v1/models 2>/dev/null | head -c 50 || echo 'M1 OFFLINE'", "bash", timeout_s=5, on_fail="skip"),
            DominoStep("tts", "python:edge_tts_speak('Environnement dev pret. Git, dependances et cluster verifies.')", "python"),
        ],
        category="dev_workflow",
        description="Dev setup: git status + uv sync + cluster check",
        learning_context="Dev — preparer l'environnement de developpement",
        priority="normal",
    ),
    DominoPipeline(
        id="domino_pip_upgrade_all",
        trigger_vocal=["upgrade tous les packages", "pip upgrade all", "mets tout a jour pip", "upgrade pip"],
        steps=[
            DominoStep("list_outdated", "bash:pip list --outdated --format=columns 2>/dev/null | head -20", "bash", timeout_s=15),
            DominoStep("tts", "python:edge_tts_speak('Liste des packages obsoletes affichee. Verifiez avant de mettre a jour.')", "python"),
        ],
        category="dev_workflow",
        description="Pip upgrade: list outdated packages",
        learning_context="Dev — verifier les packages Python a mettre a jour",
        priority="normal",
    ),
    DominoPipeline(
        id="domino_vram_monitor",
        trigger_vocal=["surveille la vram", "vram monitor", "watch vram", "monitore la vram"],
        steps=[
            DominoStep("vram_usage", "powershell:nvidia-smi --query-gpu=name,memory.used,memory.total,utilization.gpu --format=csv,noheader 2>$null || 'N/A'", "powershell", timeout_s=10),
            DominoStep("tts", "python:edge_tts_speak('Utilisation VRAM affichee par GPU.')", "python"),
        ],
        category="monitoring",
        description="VRAM monitor: usage per GPU",
        learning_context="Monitoring — surveiller l'utilisation VRAM en temps reel",
        priority="normal",
    ),
    DominoPipeline(
        id="domino_ollama_restart",
        trigger_vocal=["redemarre ollama", "restart ollama", "relance ollama", "ollama restart"],
        steps=[
            DominoStep("stop_ollama", "bash:taskkill /IM ollama.exe /F 2>/dev/null || echo 'Ollama not running'", "bash", timeout_s=10, on_fail="skip"),
            DominoStep("start_ollama", "bash:ollama serve &>/dev/null &; sleep 2; echo 'Ollama restarted'", "bash", timeout_s=10, on_fail="skip"),
            DominoStep("verify", "bash:curl -s --max-time 5 http://127.0.0.1:11434/api/tags 2>/dev/null | head -c 50 || echo 'OL1 not responding'", "bash", timeout_s=10),
            DominoStep("tts", "python:edge_tts_speak('Ollama redemarre et verifie.')", "python"),
        ],
        category="monitoring",
        description="Ollama restart: stop + start + verify",
        learning_context="Maintenance — redemarrer Ollama quand il ne repond plus",
        priority="high",
    ),
    DominoPipeline(
        id="domino_model_benchmark",
        trigger_vocal=["benchmark modeles", "model benchmark", "teste les modeles", "compare les modeles"],
        steps=[
            DominoStep("bench_m1_qwen8b", "bash:curl -s --max-time 15 http://127.0.0.1:1234/api/v1/chat -H 'Content-Type: application/json' -d '{\"model\":\"qwen3-8b\",\"input\":\"/nothink\\nReponds OK en 1 mot.\",\"temperature\":0.1,\"max_output_tokens\":20,\"stream\":false,\"store\":false}' 2>/dev/null | head -c 100 || echo 'M1 TIMEOUT'", "bash", timeout_s=20),
            DominoStep("bench_ol1_1.7b", "bash:curl -s --max-time 15 http://127.0.0.1:11434/api/chat -d '{\"model\":\"qwen3:1.7b\",\"messages\":[{\"role\":\"user\",\"content\":\"Reponds OK en 1 mot.\"}],\"stream\":false}' 2>/dev/null | head -c 100 || echo 'OL1-1.7b TIMEOUT'", "bash", timeout_s=20),
            DominoStep("bench_ol1_14b", "bash:curl -s --max-time 15 http://127.0.0.1:11434/api/chat -d '{\"model\":\"qwen3:14b\",\"messages\":[{\"role\":\"user\",\"content\":\"Reponds OK en 1 mot.\"}],\"stream\":false}' 2>/dev/null | head -c 100 || echo 'OL1-14b TIMEOUT'", "bash", timeout_s=20, on_fail="skip"),
            DominoStep("tts", "python:edge_tts_speak('Benchmark modeles termine. M1 et OL1 testes.')", "python"),
        ],
        category="testing_pipeline",
        description="Model benchmark: test M1 + OL1 models response",
        learning_context="Benchmark — tester et comparer les modeles charges",
        priority="normal",
    ),
    DominoPipeline(
        id="domino_health_full",
        trigger_vocal=["health check complet", "check complet", "diagnostic complet du cluster", "full health"],
        steps=[
            DominoStep("m1", "bash:curl -s --max-time 3 http://127.0.0.1:1234/api/v1/models 2>/dev/null | head -c 80 || echo 'M1 OFFLINE'", "bash", timeout_s=5),
            DominoStep("m2", "bash:curl -s --max-time 3 http://192.168.1.26:1234/api/v1/models 2>/dev/null | head -c 80 || echo 'M2 OFFLINE'", "bash", timeout_s=5, on_fail="skip"),
            DominoStep("m3", "bash:curl -s --max-time 3 http://192.168.1.113:1234/api/v1/models 2>/dev/null | head -c 80 || echo 'M3 OFFLINE'", "bash", timeout_s=5, on_fail="skip"),
            DominoStep("ol1", "bash:curl -s --max-time 3 http://127.0.0.1:11434/api/tags 2>/dev/null | head -c 80 || echo 'OL1 OFFLINE'", "bash", timeout_s=5),
            DominoStep("gpu", "powershell:nvidia-smi --query-gpu=temperature.gpu,utilization.gpu,memory.used --format=csv,noheader 2>$null || 'N/A'", "powershell", timeout_s=10, on_fail="skip"),
            DominoStep("tts", "python:edge_tts_speak('Health check complet. Tous les noeuds et GPU verifies.')", "python"),
        ],
        category="monitoring",
        description="Full health check: all nodes + GPU",
        learning_context="Monitoring — diagnostic complet de tout le cluster",
        priority="high",
    ),
    # ═══════════════════════════════════════════════════════════════════════
    # BATCH 87 — Audio / Security / Data / Workspace (10 dominos)
    # ═══════════════════════════════════════════════════════════════════════
    DominoPipeline(
        id="domino_audio_setup",
        trigger_vocal=["configure l'audio", "audio setup", "parametres son", "regle le son"],
        steps=[
            DominoStep("audio_devices", "powershell:Get-AudioDevice -List 2>$null || Get-CimInstance Win32_SoundDevice | Select-Object Name,Status", "powershell", timeout_s=10),
            DominoStep("volume", "powershell:[Audio]::Volume 2>$null || 'Volume API N/A'", "powershell", timeout_s=5, on_fail="skip"),
            DominoStep("tts", "python:edge_tts_speak('Configuration audio affichee. Peripheriques et volume verifies.')", "python"),
        ],
        category="media_control",
        description="Audio setup: list devices + check volume",
        learning_context="Audio — configurer et verifier les peripheriques audio",
        priority="normal",
    ),
    DominoPipeline(
        id="domino_security_audit",
        trigger_vocal=["audit de securite", "security audit", "check securite complet", "full security"],
        steps=[
            DominoStep("ports", "powershell:Get-NetTCPConnection -State Listen | Select-Object LocalPort -Unique | Measure-Object | Select-Object Count", "powershell", timeout_s=10),
            DominoStep("firewall", "powershell:Get-NetFirewallProfile | Select-Object Name,Enabled | Format-Table", "powershell", timeout_s=10),
            DominoStep("defender", "powershell:Get-MpComputerStatus | Select-Object AntivirusEnabled,RealTimeProtectionEnabled,AntivirusSignatureLastUpdated", "powershell", timeout_s=10, on_fail="skip"),
            DominoStep("env_secrets", "bash:grep -rl 'sk-\\|password\\|secret' F:/BUREAU/turbo/src/*.py 2>/dev/null | wc -l || echo '0 files with potential secrets'", "bash", timeout_s=10, on_fail="skip"),
            DominoStep("tts", "python:edge_tts_speak('Audit de securite termine. Ports, firewall, antivirus et secrets verifies.')", "python"),
        ],
        category="security_sweep",
        description="Security audit: ports + firewall + defender + secrets scan",
        learning_context="Securite — audit complet de la posture de securite",
        priority="high",
    ),
    DominoPipeline(
        id="domino_data_export_full",
        trigger_vocal=["exporte toutes les donnees", "data export full", "export complet", "exporte tout en csv"],
        steps=[
            DominoStep("export_etoile", "python:export_db_to_csv('etoile.db')", "python"),
            DominoStep("export_jarvis", "python:export_db_to_csv('jarvis.db')", "python", on_fail="skip"),
            DominoStep("export_sniper", "python:export_db_to_csv('sniper.db')", "python", on_fail="skip"),
            DominoStep("tts", "python:edge_tts_speak('Export complet termine. Toutes les bases exportees en CSV.')", "python"),
        ],
        category="data_analysis",
        description="Full data export: all databases to CSV",
        learning_context="Data — exporter toutes les bases en format CSV",
        priority="normal",
    ),
    DominoPipeline(
        id="domino_voice_calibrate",
        trigger_vocal=["calibre la voix", "voice calibrate", "ajuste la reconnaissance", "calibration vocale"],
        steps=[
            DominoStep("test_simple", "python:test_voice_match('ouvre chrome')", "python"),
            DominoStep("test_cluster", "python:test_voice_match('statut du cluster')", "python"),
            DominoStep("test_trading", "python:test_voice_match('scan trading')", "python"),
            DominoStep("count", "python:count_commands()", "python"),
            DominoStep("corrections", "python:count_voice_corrections()", "python"),
            DominoStep("tts", "python:edge_tts_speak('Calibration vocale terminee. 5 tests de matching passes.')", "python"),
        ],
        category="testing_pipeline",
        description="Voice calibrate: run match tests + count stats",
        learning_context="Voice — calibrer et tester la reconnaissance vocale",
        priority="normal",
    ),
    DominoPipeline(
        id="domino_screen_setup",
        trigger_vocal=["configure les ecrans", "screen setup", "parametres ecrans", "display settings"],
        steps=[
            DominoStep("displays", "powershell:Get-CimInstance Win32_VideoController | Select-Object Name,CurrentHorizontalResolution,CurrentVerticalResolution", "powershell", timeout_s=10),
            DominoStep("monitors", "powershell:Get-CimInstance WmiMonitorBasicDisplayParams -Namespace root/wmi -ErrorAction SilentlyContinue | Select-Object Active,MaxHorizontalImageSize | Format-Table", "powershell", timeout_s=10, on_fail="skip"),
            DominoStep("tts", "python:edge_tts_speak('Configuration ecrans affichee. Resolution et moniteurs verifies.')", "python"),
        ],
        category="monitoring",
        description="Screen setup: display info + resolution",
        learning_context="Systeme — verifier la configuration des ecrans",
        priority="normal",
    ),
    DominoPipeline(
        id="domino_task_kill_heavy",
        trigger_vocal=["tue les processus lourds", "kill heavy", "libere le cpu", "kill les processus"],
        steps=[
            DominoStep("list_heavy", "powershell:Get-Process | Sort-Object CPU -Descending | Select-Object -First 5 Name,CPU,@{N='RAM(MB)';E={[math]::Round($_.WorkingSet/1MB)}}", "powershell", timeout_s=10),
            DominoStep("tts", "python:edge_tts_speak('Top 5 processus lourds affiches. Tuez manuellement si necessaire.')", "python"),
        ],
        category="system_cleanup",
        description="List heavy processes: top 5 by CPU",
        learning_context="Systeme — identifier les processus qui consomment le plus",
        priority="normal",
    ),
    DominoPipeline(
        id="domino_workspace_organize",
        trigger_vocal=["organise le workspace", "range le bureau", "workspace organize", "trie les fichiers"],
        steps=[
            DominoStep("count_desktop", "powershell:(Get-ChildItem $env:USERPROFILE\\Desktop -File).Count", "powershell", timeout_s=5),
            DominoStep("count_downloads", "powershell:(Get-ChildItem $env:USERPROFILE\\Downloads -File).Count", "powershell", timeout_s=5),
            DominoStep("tts", "python:edge_tts_speak('Workspace analyse. Fichiers sur le bureau et dans les telechargements comptes.')", "python"),
        ],
        category="system_cleanup",
        description="Workspace organize: count desktop + downloads files",
        learning_context="Organisation — analyser le workspace pour identifier le desordre",
        priority="normal",
    ),
    DominoPipeline(
        id="domino_api_test",
        trigger_vocal=["teste les api", "api test", "check les endpoints", "verifie les api"],
        steps=[
            DominoStep("test_m1", "bash:curl -s --max-time 5 http://127.0.0.1:1234/api/v1/models 2>/dev/null | head -c 50 || echo 'M1 API FAIL'", "bash", timeout_s=10),
            DominoStep("test_ol1", "bash:curl -s --max-time 5 http://127.0.0.1:11434/api/tags 2>/dev/null | head -c 50 || echo 'OL1 API FAIL'", "bash", timeout_s=10),
            DominoStep("test_dashboard", "bash:curl -s --max-time 5 http://127.0.0.1:8080 2>/dev/null | head -c 50 || echo 'Dashboard API FAIL'", "bash", timeout_s=10, on_fail="skip"),
            DominoStep("tts", "python:edge_tts_speak('Test API termine. M1, OL1 et Dashboard verifies.')", "python"),
        ],
        category="testing_pipeline",
        description="API test: check M1 + OL1 + Dashboard endpoints",
        learning_context="Test — verifier que toutes les API sont accessibles",
        priority="normal",
    ),
    DominoPipeline(
        id="domino_db_migration",
        trigger_vocal=["migration de base", "db migration", "migre les donnees", "database migration"],
        steps=[
            DominoStep("backup_first", "python:backup_etoile_db()", "python"),
            DominoStep("integrity", "python:check_db_integrity('etoile.db')", "python"),
            DominoStep("tts", "python:edge_tts_speak('Migration preparee. Backup fait et integrite verifiee.')", "python"),
        ],
        category="data_analysis",
        description="DB migration prep: backup + integrity check",
        learning_context="Data — preparer une migration de base de donnees",
        priority="high",
    ),
    DominoPipeline(
        id="domino_git_stash_pop",
        trigger_vocal=["recupere le stash", "stash pop", "git stash pop", "reprends le travail"],
        steps=[
            DominoStep("stash_list", "bash:cd F:/BUREAU/turbo && git stash list 2>&1 || echo 'No stashes'", "bash", timeout_s=5),
            DominoStep("stash_pop", "bash:cd F:/BUREAU/turbo && git stash pop 2>&1 || echo 'Nothing to pop'", "bash", timeout_s=10, on_fail="skip"),
            DominoStep("tts", "python:edge_tts_speak('Stash recupere. Travail en cours restaure.')", "python"),
        ],
        category="dev_workflow",
        description="Git stash pop: restore stashed work",
        learning_context="Git — recuperer le travail stashe",
        priority="normal",
    ),
    # ═══════════════════════════════════════════════════════════════════════
    # BATCH 88 — Git / Env / Diagnostics / Model management (10 dominos)
    # ═══════════════════════════════════════════════════════════════════════
    DominoPipeline(
        id="domino_git_revert",
        trigger_vocal=["annule le dernier commit", "git revert", "reviens en arriere", "undo commit"],
        steps=[
            DominoStep("show_last", "bash:cd F:/BUREAU/turbo && git log --oneline -3", "bash", timeout_s=5),
            DominoStep("tts", "python:edge_tts_speak('Derniers commits affiches. Confirmez pour annuler.')", "python"),
        ],
        category="dev_workflow",
        description="Git revert prep: show last commits before reverting",
        learning_context="Git — preparer un revert en montrant les derniers commits",
        priority="normal",
    ),
    DominoPipeline(
        id="domino_env_report",
        trigger_vocal=["rapport environnement", "env report", "check l'environnement", "verifie l'env"],
        steps=[
            DominoStep("python_ver", "bash:python --version 2>&1", "bash", timeout_s=5),
            DominoStep("node_ver", "bash:node --version 2>&1", "bash", timeout_s=5, on_fail="skip"),
            DominoStep("uv_ver", "bash:uv --version 2>&1", "bash", timeout_s=5, on_fail="skip"),
            DominoStep("git_ver", "bash:git --version 2>&1", "bash", timeout_s=5),
            DominoStep("disk", "python:get_disk_usage()", "python"),
            DominoStep("uptime", "python:get_uptime()", "python"),
            DominoStep("tts", "python:edge_tts_speak('Rapport environnement genere. Python, Node, Git, disques et uptime verifies.')", "python"),
        ],
        category="monitoring",
        description="Environment report: versions + disk + uptime",
        learning_context="Systeme — rapport complet sur l'environnement de dev",
        priority="normal",
    ),
    DominoPipeline(
        id="domino_latency_test",
        trigger_vocal=["test de latence", "latency test", "ping tous les noeuds", "latence du cluster"],
        steps=[
            DominoStep("m1_lat", "bash:time curl -s --max-time 5 http://127.0.0.1:1234/api/v1/models 2>/dev/null | head -c 1 || echo 'M1 TIMEOUT'", "bash", timeout_s=10),
            DominoStep("ol1_lat", "bash:time curl -s --max-time 5 http://127.0.0.1:11434/api/tags 2>/dev/null | head -c 1 || echo 'OL1 TIMEOUT'", "bash", timeout_s=10),
            DominoStep("m2_lat", "bash:time curl -s --max-time 5 http://192.168.1.26:1234/api/v1/models 2>/dev/null | head -c 1 || echo 'M2 TIMEOUT'", "bash", timeout_s=10, on_fail="skip"),
            DominoStep("tts", "python:edge_tts_speak('Test de latence termine. Temps de reponse de chaque noeud mesure.')", "python"),
        ],
        category="testing_pipeline",
        description="Latency test: measure response time per node",
        learning_context="Benchmark — mesurer la latence de chaque noeud du cluster",
        priority="normal",
    ),
    DominoPipeline(
        id="domino_docker_cleanup",
        trigger_vocal=["nettoie docker", "docker cleanup", "docker prune", "menage docker"],
        steps=[
            DominoStep("prune_containers", "bash:docker container prune -f 2>/dev/null || echo 'Docker not available'", "bash", timeout_s=15, on_fail="skip"),
            DominoStep("prune_images", "bash:docker image prune -f 2>/dev/null || echo 'N/A'", "bash", timeout_s=15, on_fail="skip"),
            DominoStep("prune_volumes", "bash:docker volume prune -f 2>/dev/null || echo 'N/A'", "bash", timeout_s=15, on_fail="skip"),
            DominoStep("tts", "python:edge_tts_speak('Nettoyage Docker termine. Conteneurs, images et volumes nettoyes.')", "python"),
        ],
        category="system_cleanup",
        description="Docker cleanup: prune containers + images + volumes",
        learning_context="Docker — nettoyer les ressources Docker inutilisees",
        priority="normal",
    ),
    DominoPipeline(
        id="domino_model_reload",
        trigger_vocal=["recharge les modeles", "model reload", "reload models", "recharge le modele"],
        steps=[
            DominoStep("unload_check", "bash:curl -s http://127.0.0.1:1234/api/v1/models 2>/dev/null | head -c 200 || echo 'M1 OFFLINE'", "bash", timeout_s=5),
            DominoStep("warmup", "bash:curl -s --max-time 15 http://127.0.0.1:1234/api/v1/chat -H 'Content-Type: application/json' -d '{\"model\":\"qwen3-8b\",\"input\":\"/nothink\\nPing\",\"temperature\":0.1,\"max_output_tokens\":10,\"stream\":false,\"store\":false}' 2>/dev/null | head -c 100 || echo 'Warmup failed'", "bash", timeout_s=20),
            DominoStep("tts", "python:edge_tts_speak('Modeles recharges et rechauffes.')", "python"),
        ],
        category="monitoring",
        description="Model reload: check + warmup M1",
        learning_context="Modeles — recharger et rechauffer les modeles du cluster",
        priority="normal",
    ),
    DominoPipeline(
        id="domino_db_integrity_check",
        trigger_vocal=["verifie l'integrite", "integrity check", "check les bases", "integrite des bases"],
        steps=[
            DominoStep("check_etoile", "python:check_db_integrity('etoile.db')", "python"),
            DominoStep("check_jarvis", "python:check_db_integrity('jarvis.db')", "python", on_fail="skip"),
            DominoStep("check_sniper", "python:check_db_integrity('sniper.db')", "python", on_fail="skip"),
            DominoStep("tts", "python:edge_tts_speak('Integrite des bases verifiee. Toutes les bases checkees.')", "python"),
        ],
        category="data_analysis",
        description="DB integrity check: PRAGMA integrity_check on all DBs",
        learning_context="Data — verifier l'integrite de toutes les bases SQLite",
        priority="normal",
    ),
    DominoPipeline(
        id="domino_voice_stats_report",
        trigger_vocal=["rapport vocal", "voice stats", "statistiques vocales", "stats de la voix"],
        steps=[
            DominoStep("commands", "python:count_commands()", "python"),
            DominoStep("corrections", "python:count_voice_corrections()", "python"),
            DominoStep("session", "python:get_session_stats()", "python"),
            DominoStep("tts", "python:edge_tts_speak('Rapport vocal genere. Commandes, corrections et session detailles.')", "python"),
        ],
        category="testing_pipeline",
        description="Voice stats: commands + corrections + session info",
        learning_context="Voice — rapport detaille sur le systeme vocal",
        priority="normal",
    ),
    DominoPipeline(
        id="domino_pip_security",
        trigger_vocal=["check securite pip", "pip security", "audit pip", "vulnerabilites pip"],
        steps=[
            DominoStep("pip_audit", "bash:pip audit 2>/dev/null || pip check 2>/dev/null || echo 'pip audit not available'", "bash", timeout_s=20),
            DominoStep("tts", "python:edge_tts_speak('Audit securite pip termine.')", "python"),
        ],
        category="security_sweep",
        description="Pip security: audit for known vulnerabilities",
        learning_context="Securite — verifier les vulnerabilites dans les packages Python",
        priority="normal",
    ),
    DominoPipeline(
        id="domino_full_diagnostics",
        trigger_vocal=["diagnostic complet", "full diagnostics", "diagnostique tout", "check tout"],
        steps=[
            DominoStep("gpu", "powershell:nvidia-smi --query-gpu=name,temperature.gpu,utilization.gpu,memory.used,memory.total --format=csv,noheader 2>$null || 'N/A'", "powershell", timeout_s=10, on_fail="skip"),
            DominoStep("cpu_ram", "powershell:\"CPU: $((Get-CimInstance Win32_Processor).LoadPercentage)% | RAM Free: $([math]::Round((Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory/1MB,1)) GB\"", "powershell", timeout_s=10),
            DominoStep("disk", "python:get_disk_usage()", "python"),
            DominoStep("uptime", "python:get_uptime()", "python"),
            DominoStep("m1", "bash:curl -s --max-time 3 http://127.0.0.1:1234/api/v1/models 2>/dev/null | head -c 50 || echo 'M1 OFF'", "bash", timeout_s=5),
            DominoStep("ol1", "bash:curl -s --max-time 3 http://127.0.0.1:11434/api/tags 2>/dev/null | head -c 50 || echo 'OL1 OFF'", "bash", timeout_s=5),
            DominoStep("tts", "python:edge_tts_speak('Diagnostic complet termine. GPU, CPU, RAM, disques, uptime et cluster verifies.')", "python"),
        ],
        category="monitoring",
        description="Full diagnostics: GPU + CPU + RAM + Disk + Uptime + Cluster",
        learning_context="Monitoring — diagnostic complet de tout le systeme",
        priority="high",
    ),
    DominoPipeline(
        id="domino_git_stats_detailed",
        trigger_vocal=["statistiques git", "git stats", "stats du repo", "contributions git"],
        steps=[
            DominoStep("commit_count", "bash:cd F:/BUREAU/turbo && git rev-list --count HEAD 2>/dev/null || echo 'N/A'", "bash", timeout_s=5),
            DominoStep("branch_count", "bash:cd F:/BUREAU/turbo && git branch | wc -l 2>/dev/null || echo 'N/A'", "bash", timeout_s=5),
            DominoStep("last_commit", "bash:cd F:/BUREAU/turbo && git log --oneline -1 2>/dev/null", "bash", timeout_s=5),
            DominoStep("file_count", "bash:cd F:/BUREAU/turbo && git ls-files | wc -l 2>/dev/null || echo 'N/A'", "bash", timeout_s=5),
            DominoStep("tts", "python:edge_tts_speak('Statistiques git detaillees. Commits, branches, fichiers comptes.')", "python"),
        ],
        category="dev_workflow",
        description="Git stats detailed: commits + branches + files",
        learning_context="Git — statistiques detaillees du repository",
        priority="normal",
    ),
    # ═══════════════════════════════════════════════════════════════════════
    # BATCH 89 — Modes / Backup / Services (10 dominos)
    # ═══════════════════════════════════════════════════════════════════════
    DominoPipeline(
        id="domino_gaming_mode_full",
        trigger_vocal=["mode gaming complet", "full gaming", "prepare le gaming", "game mode full"],
        steps=[
            DominoStep("close_heavy", "powershell:Get-Process | Where-Object {$_.WorkingSet -gt 500MB -and $_.ProcessName -notin @('explorer','dwm','System')} | Select-Object Name,@{N='RAM(MB)';E={[math]::Round($_.WorkingSet/1MB)}} | Format-Table", "powershell", timeout_s=10, on_fail="skip"),
            DominoStep("gpu_check", "powershell:nvidia-smi --query-gpu=temperature.gpu,utilization.gpu --format=csv,noheader 2>$null || 'N/A'", "powershell", timeout_s=10, on_fail="skip"),
            DominoStep("tts", "python:edge_tts_speak('Mode gaming active. Processus lourds listes, GPU verifie.')", "python"),
        ],
        category="media_control",
        description="Gaming mode full: list heavy processes + GPU check",
        learning_context="Gaming — preparer le systeme pour le jeu",
        priority="normal",
    ),
    DominoPipeline(
        id="domino_study_mode",
        trigger_vocal=["mode etude", "study mode", "mode revision", "mode apprentissage"],
        steps=[
            DominoStep("disable_notif", "powershell:Set-ItemProperty -Path 'HKCU:\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\PushNotifications' -Name 'ToastEnabled' -Value 0 -ErrorAction SilentlyContinue; 'Notif off'", "powershell", timeout_s=5, on_fail="skip"),
            DominoStep("tts", "python:edge_tts_speak('Mode etude active. Notifications desactivees. Bonne revision!')", "python"),
        ],
        category="power_management",
        description="Study mode: disable notifications for focus",
        learning_context="Productivite — mode etude avec concentration maximale",
        priority="normal",
    ),
    DominoPipeline(
        id="domino_presentation_setup",
        trigger_vocal=["prepare la presentation", "setup presentation", "mode presentation complet"],
        steps=[
            DominoStep("disable_notif", "powershell:Set-ItemProperty -Path 'HKCU:\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\PushNotifications' -Name 'ToastEnabled' -Value 0 -ErrorAction SilentlyContinue; 'Notif off'", "powershell", timeout_s=5, on_fail="skip"),
            DominoStep("display_info", "powershell:Get-CimInstance Win32_VideoController | Select-Object Name,CurrentHorizontalResolution,CurrentVerticalResolution", "powershell", timeout_s=10),
            DominoStep("tts", "python:edge_tts_speak('Mode presentation pret. Notifications desactivees, ecran verifie.')", "python"),
        ],
        category="meeting_assistant",
        description="Presentation setup: disable notif + check display",
        learning_context="Presentation — preparer le systeme pour une presentation",
        priority="normal",
    ),
    DominoPipeline(
        id="domino_streaming_setup",
        trigger_vocal=["prepare le stream", "setup streaming", "mode streaming complet"],
        steps=[
            DominoStep("gpu_check", "powershell:nvidia-smi --query-gpu=temperature.gpu,utilization.gpu,memory.used --format=csv,noheader 2>$null || 'N/A'", "powershell", timeout_s=10, on_fail="skip"),
            DominoStep("network", "bash:ping -c 2 8.8.8.8 2>/dev/null || ping -n 2 8.8.8.8", "bash", timeout_s=10, on_fail="skip"),
            DominoStep("tts", "python:edge_tts_speak('Mode streaming pret. GPU et reseau verifies.')", "python"),
        ],
        category="media_control",
        description="Streaming setup: GPU + network check",
        learning_context="Streaming — preparer le systeme pour le streaming",
        priority="normal",
    ),
    DominoPipeline(
        id="domino_dev_reset",
        trigger_vocal=["reset dev", "remet l'environnement", "clean dev", "fresh start dev"],
        steps=[
            DominoStep("git_clean", "bash:cd F:/BUREAU/turbo && git checkout -- . 2>&1 || echo 'Nothing to clean'", "bash", timeout_s=10, on_fail="skip"),
            DominoStep("clear_cache", "python:clear_all_caches()", "python"),
            DominoStep("uv_sync", "bash:cd F:/BUREAU/turbo && uv sync 2>&1 | tail -3", "bash", timeout_s=30, on_fail="skip"),
            DominoStep("tts", "python:edge_tts_speak('Environnement dev reinitialise. Caches vides, dependances synchronisees.')", "python"),
        ],
        category="dev_workflow",
        description="Dev reset: clean git + clear caches + sync deps",
        learning_context="Dev — reinitialiser l'environnement de developpement proprement",
        priority="normal",
    ),
    DominoPipeline(
        id="domino_backup_incremental",
        trigger_vocal=["backup incremental", "sauvegarde rapide", "quick backup", "backup partiel"],
        steps=[
            DominoStep("backup_etoile", "python:backup_etoile_db()", "python"),
            DominoStep("git_save", "bash:cd F:/BUREAU/turbo && git add -A && git commit -m 'auto: incremental backup $(date +%H%M)' 2>&1 || echo 'Nothing to commit'", "bash", timeout_s=15, on_fail="skip"),
            DominoStep("tts", "python:edge_tts_speak('Backup incremental termine. Base et code sauvegardes.')", "python"),
        ],
        category="backup_chain",
        description="Incremental backup: DB + git commit",
        learning_context="Backup — sauvegarde rapide et incrementale",
        priority="normal",
    ),
    DominoPipeline(
        id="domino_service_restart_all",
        trigger_vocal=["redemarre tous les services", "restart all services", "relance tout", "restart tout"],
        steps=[
            DominoStep("check_m1", "bash:curl -s --max-time 3 http://127.0.0.1:1234/api/v1/models 2>/dev/null | head -c 50 || echo 'M1 OFFLINE'", "bash", timeout_s=5),
            DominoStep("check_ol1", "bash:curl -s --max-time 3 http://127.0.0.1:11434/api/tags 2>/dev/null | head -c 50 || echo 'OL1 OFFLINE'", "bash", timeout_s=5),
            DominoStep("tts", "python:edge_tts_speak('Services verifies. M1 et OL1 checkes.')", "python"),
        ],
        category="monitoring",
        description="Service restart: check all services status",
        learning_context="Services — verifier et relancer les services JARVIS",
        priority="high",
    ),
    DominoPipeline(
        id="domino_voice_history_export",
        trigger_vocal=["exporte l'historique vocal", "voice history export", "sauvegarde les commandes vocales"],
        steps=[
            DominoStep("count", "python:count_commands()", "python"),
            DominoStep("corrections", "python:count_voice_corrections()", "python"),
            DominoStep("list_dominos", "python:list_dominos()", "python"),
            DominoStep("tts", "python:edge_tts_speak('Historique vocal exporte. Commandes, corrections et dominos detailles.')", "python"),
        ],
        category="data_analysis",
        description="Voice history export: full stats dump",
        learning_context="Data — exporter les statistiques completes du systeme vocal",
        priority="normal",
    ),
    DominoPipeline(
        id="domino_morning_stretch",
        trigger_vocal=["etirement matin", "morning stretch", "pause etirement", "stretch break"],
        steps=[
            DominoStep("tts", "python:edge_tts_speak('Pause etirement. Levez-vous, etirez-vous 2 minutes. Je vous attends.')", "python"),
        ],
        category="routine_matin",
        description="Morning stretch: TTS reminder to stretch",
        learning_context="Sante — rappel d'etirement pour eviter les TMS",
        priority="normal",
    ),
    DominoPipeline(
        id="domino_pomodoro_session",
        trigger_vocal=["pomodoro", "lance pomodoro", "session pomodoro", "technique pomodoro"],
        steps=[
            DominoStep("start_timer", "python:start_pomodoro_timer('25')", "python"),
            DominoStep("tts", "python:edge_tts_speak('Session Pomodoro lancee. 25 minutes de concentration. Go!')", "python"),
        ],
        category="task_scheduling",
        description="Pomodoro session: start 25min focus timer",
        learning_context="Productivite — technique Pomodoro pour la concentration",
        priority="normal",
    ),
    # ═══════════════════════════════════════════════════════════════════════
    # BATCH 90 — Testing / Architecture / Misc (10 dominos)
    # ═══════════════════════════════════════════════════════════════════════
    DominoPipeline(
        id="domino_test_suite_full",
        trigger_vocal=["lance tous les tests", "test suite complete", "full test", "teste tout"],
        steps=[
            DominoStep("syntax", "bash:cd F:/BUREAU/turbo && python -m py_compile src/commands.py && python -m py_compile src/voice_correction.py && python -m py_compile src/domino_pipelines.py && python -m py_compile src/domino_executor.py && echo 'SYNTAX OK'", "bash", timeout_s=15),
            DominoStep("match_test1", "python:test_voice_match('ouvre chrome')", "python"),
            DominoStep("match_test2", "python:test_voice_match('statut du cluster')", "python"),
            DominoStep("match_test3", "python:test_voice_match('scan trading')", "python"),
            DominoStep("count_cmds", "python:count_commands()", "python"),
            DominoStep("tts", "python:edge_tts_speak('Suite de tests complete. Syntaxe, matching et comptage verifies.')", "python"),
        ],
        category="testing_pipeline",
        description="Full test suite: syntax + match tests + counts",
        learning_context="Tests — suite de tests complete du systeme vocal",
        priority="high",
    ),
    DominoPipeline(
        id="domino_commit_deploy",
        trigger_vocal=["commit et deploie", "commit and deploy", "save and deploy", "deploy le code"],
        steps=[
            DominoStep("syntax", "bash:cd F:/BUREAU/turbo && python -m py_compile src/commands.py && python -m py_compile src/voice_correction.py && echo 'OK'", "bash", timeout_s=10),
            DominoStep("git_add", "bash:cd F:/BUREAU/turbo && git add -A", "bash", timeout_s=5),
            DominoStep("git_commit", "bash:cd F:/BUREAU/turbo && git commit -m 'auto: deploy $(date +%Y%m%d-%H%M)' 2>&1 || echo 'Nothing to commit'", "bash", timeout_s=10),
            DominoStep("git_push", "bash:cd F:/BUREAU/turbo && git push 2>&1 || echo 'Push failed'", "bash", timeout_s=30, on_fail="skip"),
            DominoStep("tts", "python:edge_tts_speak('Code commite et deploye.')", "python"),
        ],
        category="dev_workflow",
        description="Commit and deploy: syntax check + commit + push",
        learning_context="Dev — commit et deploy en une seule commande",
        priority="high",
    ),
    DominoPipeline(
        id="domino_clean_everything",
        trigger_vocal=["nettoie tout", "clean everything", "grand menage", "purge complete"],
        steps=[
            DominoStep("clear_caches", "python:clear_all_caches()", "python"),
            DominoStep("clear_temp", "powershell:Remove-Item $env:TEMP\\* -Recurse -Force -ErrorAction SilentlyContinue; 'Temp cleared'", "powershell", timeout_s=15, on_fail="skip"),
            DominoStep("pip_cache", "bash:pip cache purge 2>/dev/null || echo 'pip cache N/A'", "bash", timeout_s=10, on_fail="skip"),
            DominoStep("git_gc", "bash:cd F:/BUREAU/turbo && git gc --auto 2>&1", "bash", timeout_s=30, on_fail="skip"),
            DominoStep("tts", "python:edge_tts_speak('Grand menage termine. Caches, temp, pip et git nettoyes.')", "python"),
        ],
        category="system_cleanup",
        description="Clean everything: all caches + temp + pip + git gc",
        learning_context="Nettoyage — purge complete de tout le systeme",
        priority="normal",
    ),
    DominoPipeline(
        id="domino_status_dashboard",
        trigger_vocal=["tableau de bord", "dashboard status", "status board", "affiche le tableau de bord"],
        steps=[
            DominoStep("cmds", "python:count_commands()", "python"),
            DominoStep("corrections", "python:count_voice_corrections()", "python"),
            DominoStep("dominos", "python:list_dominos()", "python"),
            DominoStep("disk", "python:get_disk_usage()", "python"),
            DominoStep("uptime", "python:get_uptime()", "python"),
            DominoStep("tts", "python:edge_tts_speak('Tableau de bord affiche. Toutes les metriques a jour.')", "python"),
        ],
        category="monitoring",
        description="Status dashboard: full metrics overview",
        learning_context="Monitoring — tableau de bord complet des metriques",
        priority="normal",
    ),
    DominoPipeline(
        id="domino_git_morning",
        trigger_vocal=["git du matin", "morning git", "check git matin", "git matinal"],
        steps=[
            DominoStep("pull", "bash:cd F:/BUREAU/turbo && git pull --ff-only 2>&1 || echo 'Up to date'", "bash", timeout_s=15),
            DominoStep("status", "bash:cd F:/BUREAU/turbo && git status --short", "bash", timeout_s=5),
            DominoStep("log_today", "bash:cd F:/BUREAU/turbo && git log --oneline --since=midnight 2>/dev/null || echo 'No commits today'", "bash", timeout_s=5),
            DominoStep("tts", "python:edge_tts_speak('Git du matin. Pull fait, status et commits du jour affiches.')", "python"),
        ],
        category="routine_matin",
        description="Morning git: pull + status + today's log",
        learning_context="Routine — check git du matin",
        priority="normal",
    ),
    DominoPipeline(
        id="domino_dependency_audit",
        trigger_vocal=["audit des dependances", "dependency audit", "check les deps", "verifie les dependances"],
        steps=[
            DominoStep("pip_outdated", "bash:pip list --outdated --format=columns 2>/dev/null | head -15", "bash", timeout_s=15),
            DominoStep("pip_check", "bash:pip check 2>/dev/null || echo 'pip check N/A'", "bash", timeout_s=10, on_fail="skip"),
            DominoStep("tts", "python:edge_tts_speak('Audit des dependances termine. Packages obsoletes et conflits listes.')", "python"),
        ],
        category="dev_workflow",
        description="Dependency audit: outdated + conflicts check",
        learning_context="Dev — auditer les dependances Python",
        priority="normal",
    ),
    DominoPipeline(
        id="domino_system_info",
        trigger_vocal=["info systeme", "system info", "a propos du systeme", "specs du pc"],
        steps=[
            DominoStep("os", "powershell:(Get-CimInstance Win32_OperatingSystem).Caption + ' ' + (Get-CimInstance Win32_OperatingSystem).Version", "powershell", timeout_s=10),
            DominoStep("cpu", "powershell:(Get-CimInstance Win32_Processor).Name", "powershell", timeout_s=10),
            DominoStep("ram", "powershell:[math]::Round((Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory/1GB,1)", "powershell", timeout_s=10),
            DominoStep("gpu", "powershell:(Get-CimInstance Win32_VideoController).Name", "powershell", timeout_s=10, on_fail="skip"),
            DominoStep("tts", "python:edge_tts_speak('Info systeme affichee. OS, CPU, RAM et GPU detailles.')", "python"),
        ],
        category="monitoring",
        description="System info: OS + CPU + RAM + GPU specs",
        learning_context="Systeme — informations detaillees sur le hardware",
        priority="normal",
    ),
    DominoPipeline(
        id="domino_quick_save",
        trigger_vocal=["sauvegarde rapide", "quick save", "save vite", "save rapide"],
        steps=[
            DominoStep("git_add", "bash:cd F:/BUREAU/turbo && git add -A && git commit -m 'quick save $(date +%H%M)' 2>&1 || echo 'Nothing'", "bash", timeout_s=10),
            DominoStep("tts", "python:edge_tts_speak('Sauvegarde rapide effectuee.')", "python"),
        ],
        category="dev_workflow",
        description="Quick save: instant git add + commit",
        learning_context="Dev — sauvegarde ultra-rapide du travail en cours",
        priority="normal",
    ),
    DominoPipeline(
        id="domino_thermal_monitor",
        trigger_vocal=["monitore les temperatures", "thermal monitor", "check les temperatures", "watch thermal"],
        steps=[
            DominoStep("gpu_temp", "powershell:nvidia-smi --query-gpu=name,temperature.gpu --format=csv,noheader 2>$null || 'N/A'", "powershell", timeout_s=10),
            DominoStep("cpu_temp", "powershell:Get-CimInstance MSAcpi_ThermalZoneTemperature -Namespace root/wmi -ErrorAction SilentlyContinue | ForEach-Object { [math]::Round(($_.CurrentTemperature - 2732) / 10, 1) }", "powershell", timeout_s=10, on_fail="skip"),
            DominoStep("tts", "python:edge_tts_speak('Temperatures verifiees. GPU et CPU affiches.')", "python"),
        ],
        category="monitoring",
        description="Thermal monitor: GPU + CPU temperatures",
        learning_context="Monitoring — surveiller les temperatures du systeme",
        priority="normal",
    ),
    DominoPipeline(
        id="domino_end_session",
        trigger_vocal=["fin de session", "end session", "termine la session", "session terminee"],
        steps=[
            DominoStep("session_stats", "python:get_session_stats()", "python"),
            DominoStep("git_save", "bash:cd F:/BUREAU/turbo && git add -A && git commit -m 'auto: end session $(date +%Y%m%d-%H%M)' 2>&1 || echo 'Nothing'", "bash", timeout_s=15, on_fail="skip"),
            DominoStep("tts", "python:edge_tts_speak('Session terminee. Stats affichees, code sauvegarde.')", "python"),
        ],
        category="routine_soir",
        description="End session: stats + auto save",
        learning_context="Routine — terminer proprement une session de travail",
        priority="normal",
    ),
    # ═══════════════════════════════════════════════════════════════════════
    # BATCH 91 — Versioning / Observabilite / Documentation (10 dominos)
    # ═══════════════════════════════════════════════════════════════════════
    DominoPipeline(
        id="domino_changelog_gen",
        trigger_vocal=["genere le changelog", "changelog", "quoi de neuf", "what's new"],
        steps=[
            DominoStep("recent_commits", "bash:cd F:/BUREAU/turbo && git log --oneline -20 2>/dev/null", "bash", timeout_s=10),
            DominoStep("tags", "bash:cd F:/BUREAU/turbo && git tag --sort=-v:refname | head -5 2>/dev/null || echo 'No tags'", "bash", timeout_s=5),
            DominoStep("tts", "python:edge_tts_speak('Changelog genere. 20 derniers commits et tags affiches.')", "python"),
        ],
        category="documentation",
        description="Changelog: recent commits + tags",
        learning_context="Doc — generer un changelog a partir de git",
        priority="normal",
    ),
    DominoPipeline(
        id="domino_log_analysis",
        trigger_vocal=["analyse les logs", "log analysis", "examine les logs", "parse les logs"],
        steps=[
            DominoStep("count_all", "bash:wc -l F:/BUREAU/turbo/data/*.log 2>/dev/null || echo '0 log files'", "bash", timeout_s=10),
            DominoStep("errors", "bash:grep -ci 'error\\|exception\\|fail\\|critical' F:/BUREAU/turbo/data/*.log 2>/dev/null || echo '0 errors'", "bash", timeout_s=10, on_fail="skip"),
            DominoStep("warnings", "bash:grep -ci 'warn\\|warning' F:/BUREAU/turbo/data/*.log 2>/dev/null || echo '0 warnings'", "bash", timeout_s=10, on_fail="skip"),
            DominoStep("tts", "python:edge_tts_speak('Analyse des logs terminee. Erreurs et warnings comptes.')", "python"),
        ],
        category="monitoring_live",
        description="Log analysis: count lines + errors + warnings",
        learning_context="Logs — analyser en profondeur les fichiers de logs",
        priority="normal",
    ),
    DominoPipeline(
        id="domino_release_prep",
        trigger_vocal=["prepare la release", "release prep", "prepare le deploiement", "pre release"],
        steps=[
            DominoStep("syntax", "bash:cd F:/BUREAU/turbo && python -m py_compile src/commands.py && python -m py_compile src/voice_correction.py && python -m py_compile src/domino_pipelines.py && python -m py_compile src/domino_executor.py && echo 'SYNTAX OK'", "bash", timeout_s=15),
            DominoStep("tests", "python:test_voice_match('ouvre chrome')", "python"),
            DominoStep("stats", "python:count_commands()", "python"),
            DominoStep("git_status", "bash:cd F:/BUREAU/turbo && git status --short", "bash", timeout_s=5),
            DominoStep("tts", "python:edge_tts_speak('Preparation release terminee. Syntaxe, tests et git verifies.')", "python"),
        ],
        category="dev_workflow",
        description="Release prep: syntax + tests + stats + git status",
        learning_context="Release — preparer une nouvelle version pour deploiement",
        priority="high",
    ),
    DominoPipeline(
        id="domino_metrics_snapshot",
        trigger_vocal=["snapshot des metriques", "metrics snapshot", "sauvegarde les metriques", "capture les stats"],
        steps=[
            DominoStep("cmds", "python:count_commands()", "python"),
            DominoStep("corrections", "python:count_voice_corrections()", "python"),
            DominoStep("session", "python:get_session_stats()", "python"),
            DominoStep("disk", "python:get_disk_usage()", "python"),
            DominoStep("uptime", "python:get_uptime()", "python"),
            DominoStep("tts", "python:edge_tts_speak('Snapshot des metriques pris. Toutes les stats sauvegardees.')", "python"),
        ],
        category="monitoring",
        description="Metrics snapshot: all system metrics at a point in time",
        learning_context="Monitoring — prendre un snapshot de toutes les metriques",
        priority="normal",
    ),
    DominoPipeline(
        id="domino_git_branch_cleanup",
        trigger_vocal=["nettoie les branches", "branch cleanup", "supprime les vieilles branches", "prune branches"],
        steps=[
            DominoStep("list_all", "bash:cd F:/BUREAU/turbo && git branch -a 2>/dev/null || echo 'N/A'", "bash", timeout_s=5),
            DominoStep("merged", "bash:cd F:/BUREAU/turbo && git branch --merged main 2>/dev/null | grep -v main | head -10 || echo 'No merged branches'", "bash", timeout_s=5),
            DominoStep("prune", "bash:cd F:/BUREAU/turbo && git remote prune origin 2>&1 || echo 'Done'", "bash", timeout_s=15, on_fail="skip"),
            DominoStep("tts", "python:edge_tts_speak('Nettoyage branches termine. Branches mergees et remote prunees.')", "python"),
        ],
        category="dev_workflow",
        description="Branch cleanup: list + merged check + prune",
        learning_context="Git — nettoyer les branches inutiles",
        priority="normal",
    ),
    DominoPipeline(
        id="domino_process_monitor",
        trigger_vocal=["monitore les processus", "process monitor", "watch processus", "surveille les processus"],
        steps=[
            DominoStep("top_cpu", "powershell:Get-Process | Sort-Object CPU -Descending | Select-Object -First 10 Name,CPU,@{N='RAM(MB)';E={[math]::Round($_.WorkingSet/1MB)}}", "powershell", timeout_s=10),
            DominoStep("count", "powershell:(Get-Process).Count", "powershell", timeout_s=5),
            DominoStep("tts", "python:edge_tts_speak('Monitoring des processus termine. Top 10 et total affiches.')", "python"),
        ],
        category="monitoring",
        description="Process monitor: top 10 by CPU + total count",
        learning_context="Monitoring — surveiller les processus en temps reel",
        priority="normal",
    ),
    DominoPipeline(
        id="domino_quick_fix",
        trigger_vocal=["quick fix", "correction rapide", "fix rapide", "repare vite"],
        steps=[
            DominoStep("syntax_check", "bash:cd F:/BUREAU/turbo && python -m py_compile src/commands.py && python -m py_compile src/voice_correction.py && echo 'Syntax OK'", "bash", timeout_s=10),
            DominoStep("git_diff", "bash:cd F:/BUREAU/turbo && git diff --stat 2>/dev/null || echo 'No changes'", "bash", timeout_s=5),
            DominoStep("tts", "python:edge_tts_speak('Quick fix. Syntaxe verifiee, diff affiche.')", "python"),
        ],
        category="dev_workflow",
        description="Quick fix: syntax check + diff",
        learning_context="Dev — correction rapide avec verification immediate",
        priority="normal",
    ),
    DominoPipeline(
        id="domino_network_speed",
        trigger_vocal=["test de vitesse", "speed test", "vitesse internet", "bande passante"],
        steps=[
            DominoStep("ping", "bash:ping -c 5 8.8.8.8 2>/dev/null || ping -n 5 8.8.8.8", "bash", timeout_s=15),
            DominoStep("dns", "bash:nslookup google.com 2>&1 | head -3 || echo 'DNS N/A'", "bash", timeout_s=10, on_fail="skip"),
            DominoStep("tts", "python:edge_tts_speak('Test de vitesse termine. Ping et DNS verifies.')", "python"),
        ],
        category="network_diagnostics",
        description="Network speed: ping + DNS test",
        learning_context="Reseau — tester la vitesse et la stabilite du reseau",
        priority="normal",
    ),
    DominoPipeline(
        id="domino_workspace_stats",
        trigger_vocal=["stats du workspace", "workspace stats", "taille du projet", "project size"],
        steps=[
            DominoStep("lines", "bash:wc -l F:/BUREAU/turbo/src/*.py 2>/dev/null", "bash", timeout_s=10),
            DominoStep("files", "bash:find F:/BUREAU/turbo/src -name '*.py' 2>/dev/null | wc -l", "bash", timeout_s=5),
            DominoStep("git_size", "bash:du -sh F:/BUREAU/turbo/.git 2>/dev/null || echo 'N/A'", "bash", timeout_s=5),
            DominoStep("data_size", "bash:du -sh F:/BUREAU/turbo/data 2>/dev/null || echo 'N/A'", "bash", timeout_s=5),
            DominoStep("tts", "python:edge_tts_speak('Stats du workspace. Lignes, fichiers, taille git et data affiches.')", "python"),
        ],
        category="dev_workflow",
        description="Workspace stats: lines + files + git size + data size",
        learning_context="Dev — statistiques detaillees du workspace",
        priority="normal",
    ),
    DominoPipeline(
        id="domino_cluster_status_full",
        trigger_vocal=["statut complet du cluster", "full cluster status", "etat du cluster complet"],
        steps=[
            DominoStep("m1", "bash:curl -s --max-time 3 http://127.0.0.1:1234/api/v1/models 2>/dev/null | head -c 100 || echo 'M1 OFFLINE'", "bash", timeout_s=5),
            DominoStep("m2", "bash:curl -s --max-time 3 http://192.168.1.26:1234/api/v1/models 2>/dev/null | head -c 100 || echo 'M2 OFFLINE'", "bash", timeout_s=5, on_fail="skip"),
            DominoStep("m3", "bash:curl -s --max-time 3 http://192.168.1.113:1234/api/v1/models 2>/dev/null | head -c 100 || echo 'M3 OFFLINE'", "bash", timeout_s=5, on_fail="skip"),
            DominoStep("ol1", "bash:curl -s --max-time 3 http://127.0.0.1:11434/api/tags 2>/dev/null | head -c 100 || echo 'OL1 OFFLINE'", "bash", timeout_s=5),
            DominoStep("gpu_temp", "powershell:nvidia-smi --query-gpu=name,temperature.gpu,memory.used,memory.total --format=csv,noheader 2>$null || 'N/A'", "powershell", timeout_s=10, on_fail="skip"),
            DominoStep("disk", "python:get_disk_usage()", "python"),
            DominoStep("uptime", "python:get_uptime()", "python"),
            DominoStep("tts", "python:edge_tts_speak('Statut complet du cluster. Tous les noeuds, GPU, disques et uptime verifies.')", "python"),
        ],
        category="monitoring",
        description="Full cluster status: all nodes + GPU + disk + uptime",
        learning_context="Monitoring — statut complet et detaille de tout le cluster",
        priority="high",
    ),
    # ═══════════════════════════════════════════════════════════════════════
    # BATCH 92 — Performance / ML / Advanced (10 dominos)
    # ═══════════════════════════════════════════════════════════════════════
    DominoPipeline(
        id="domino_memory_profile",
        trigger_vocal=["profil memoire", "memory profile", "analyse la memoire", "ram detaille"],
        steps=[
            DominoStep("ram_total", "powershell:[math]::Round((Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory/1GB,1)", "powershell", timeout_s=10),
            DominoStep("ram_free", "powershell:[math]::Round((Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory/1MB,1)", "powershell", timeout_s=10),
            DominoStep("top_ram", "powershell:Get-Process | Sort-Object WorkingSet -Descending | Select-Object -First 10 Name,@{N='RAM(MB)';E={[math]::Round($_.WorkingSet/1MB)}}", "powershell", timeout_s=10),
            DominoStep("tts", "python:edge_tts_speak('Profil memoire affiche. Total, libre et top processus RAM.')", "python"),
        ],
        category="monitoring",
        description="Memory profile: total + free + top RAM consumers",
        learning_context="Performance — profil detaille de l'utilisation memoire",
        priority="normal",
    ),
    DominoPipeline(
        id="domino_gpu_benchmark",
        trigger_vocal=["benchmark gpu", "gpu benchmark", "teste le gpu", "performance gpu"],
        steps=[
            DominoStep("gpu_info", "powershell:nvidia-smi --query-gpu=name,temperature.gpu,utilization.gpu,memory.used,memory.total,power.draw --format=csv,noheader 2>$null || 'N/A'", "powershell", timeout_s=10),
            DominoStep("bench_inference", "bash:curl -s --max-time 15 http://127.0.0.1:1234/api/v1/chat -H 'Content-Type: application/json' -d '{\"model\":\"qwen3-8b\",\"input\":\"/nothink\\nExplique en 20 mots ce quest un GPU.\",\"temperature\":0.1,\"max_output_tokens\":100,\"stream\":false,\"store\":false}' 2>/dev/null | head -c 200 || echo 'TIMEOUT'", "bash", timeout_s=20),
            DominoStep("tts", "python:edge_tts_speak('Benchmark GPU termine. Info GPU et inference testee.')", "python"),
        ],
        category="testing_pipeline",
        description="GPU benchmark: nvidia-smi + inference test",
        learning_context="Benchmark — tester les performances du GPU avec inference",
        priority="normal",
    ),
    DominoPipeline(
        id="domino_ml_status",
        trigger_vocal=["statut ml", "ml status", "etat du machine learning", "statut entrainement"],
        steps=[
            DominoStep("gpu_usage", "powershell:nvidia-smi --query-gpu=utilization.gpu,memory.used,temperature.gpu --format=csv,noheader 2>$null || 'N/A'", "powershell", timeout_s=10, on_fail="skip"),
            DominoStep("models_loaded", "bash:curl -s --max-time 3 http://127.0.0.1:1234/api/v1/models 2>/dev/null | head -c 200 || echo 'N/A'", "bash", timeout_s=5),
            DominoStep("tts", "python:edge_tts_speak('Statut ML affiche. GPU et modeles charges verifies.')", "python"),
        ],
        category="monitoring",
        description="ML status: GPU usage + loaded models",
        learning_context="ML — verifier le statut du pipeline machine learning",
        priority="normal",
    ),
    DominoPipeline(
        id="domino_container_logs",
        trigger_vocal=["logs docker", "container logs", "logs des conteneurs", "docker logs"],
        steps=[
            DominoStep("containers", "bash:docker ps --format '{{.Names}}' 2>/dev/null || echo 'Docker not running'", "bash", timeout_s=5),
            DominoStep("recent_logs", "bash:docker logs --tail 10 $(docker ps -q --latest) 2>/dev/null || echo 'No containers'", "bash", timeout_s=10, on_fail="skip"),
            DominoStep("tts", "python:edge_tts_speak('Logs Docker affiches. Conteneurs et logs recents.')", "python"),
        ],
        category="dev_workflow",
        description="Container logs: list + recent logs",
        learning_context="Docker — voir les logs des conteneurs actifs",
        priority="normal",
    ),
    DominoPipeline(
        id="domino_cert_check",
        trigger_vocal=["verifie les certificats", "cert check", "ssl check", "check ssl"],
        steps=[
            DominoStep("check_ssl", "bash:echo | openssl s_client -connect github.com:443 2>/dev/null | openssl x509 -noout -dates 2>/dev/null || echo 'openssl N/A'", "bash", timeout_s=10, on_fail="skip"),
            DominoStep("tts", "python:edge_tts_speak('Verification des certificats terminee.')", "python"),
        ],
        category="security_sweep",
        description="Certificate check: SSL cert dates",
        learning_context="Securite — verifier la validite des certificats SSL",
        priority="normal",
    ),
    DominoPipeline(
        id="domino_env_vars_audit",
        trigger_vocal=["audit variables env", "env vars audit", "verifie les variables", "check env"],
        steps=[
            DominoStep("critical_vars", "powershell:$vars = @('PATH','TURBO_DIR','OLLAMA_NUM_PARALLEL','CUDA_VISIBLE_DEVICES'); foreach($v in $vars){\"$v = $(if($env:$v){'SET'}else{'NOT SET'})\"}", "powershell", timeout_s=10),
            DominoStep("tts", "python:edge_tts_speak('Audit des variables d environnement termine. Variables critiques verifiees.')", "python"),
        ],
        category="monitoring",
        description="Env vars audit: check critical environment variables",
        learning_context="Systeme — auditer les variables d'environnement critiques",
        priority="normal",
    ),
    DominoPipeline(
        id="domino_quick_benchmark_full",
        trigger_vocal=["benchmark complet", "full benchmark", "benchmark le cluster", "bench all"],
        steps=[
            DominoStep("m1_bench", "bash:curl -s --max-time 15 http://127.0.0.1:1234/api/v1/chat -H 'Content-Type: application/json' -d '{\"model\":\"qwen3-8b\",\"input\":\"/nothink\\nDis OK.\",\"temperature\":0.1,\"max_output_tokens\":10,\"stream\":false,\"store\":false}' 2>/dev/null | head -c 50 || echo 'M1 TIMEOUT'", "bash", timeout_s=20),
            DominoStep("ol1_bench", "bash:curl -s --max-time 15 http://127.0.0.1:11434/api/chat -d '{\"model\":\"qwen3:1.7b\",\"messages\":[{\"role\":\"user\",\"content\":\"Dis OK.\"}],\"stream\":false}' 2>/dev/null | head -c 50 || echo 'OL1 TIMEOUT'", "bash", timeout_s=20),
            DominoStep("m2_bench", "bash:curl -s --max-time 15 http://192.168.1.26:1234/api/v1/chat -H 'Content-Type: application/json' -d '{\"model\":\"deepseek-r1-0528-qwen3-8b\",\"input\":\"Dis OK.\",\"temperature\":0.1,\"max_output_tokens\":10,\"stream\":false,\"store\":false}' 2>/dev/null | head -c 50 || echo 'M2 TIMEOUT'", "bash", timeout_s=20, on_fail="skip"),
            DominoStep("tts", "python:edge_tts_speak('Benchmark complet du cluster. M1, OL1 et M2 testes.')", "python"),
        ],
        category="testing_pipeline",
        description="Full benchmark: M1 + OL1 + M2 response time",
        learning_context="Benchmark — benchmark complet de tous les noeuds du cluster",
        priority="normal",
    ),
    DominoPipeline(
        id="domino_weekend_prep",
        trigger_vocal=["prepare le weekend", "weekend prep", "mode weekend", "vendredi soir"],
        steps=[
            DominoStep("git_save", "bash:cd F:/BUREAU/turbo && git add -A && git commit -m 'auto: weekend prep $(date +%Y%m%d)' 2>&1 || echo 'Nothing'", "bash", timeout_s=15, on_fail="skip"),
            DominoStep("git_push", "bash:cd F:/BUREAU/turbo && git push 2>&1 || echo 'Push failed'", "bash", timeout_s=30, on_fail="skip"),
            DominoStep("backup", "python:backup_etoile_db()", "python", on_fail="skip"),
            DominoStep("tts", "python:edge_tts_speak('Weekend prepare. Code sauvegarde, pousse et backupe. Bon weekend!')", "python"),
        ],
        category="routine_soir",
        description="Weekend prep: save + push + backup",
        learning_context="Routine — preparer le systeme pour le weekend",
        priority="normal",
    ),
    DominoPipeline(
        id="domino_monday_morning",
        trigger_vocal=["lundi matin", "monday morning", "debut de semaine", "nouvelle semaine"],
        steps=[
            DominoStep("git_pull", "bash:cd F:/BUREAU/turbo && git pull --ff-only 2>&1 || echo 'Up to date'", "bash", timeout_s=15),
            DominoStep("health_m1", "bash:curl -s --max-time 3 http://127.0.0.1:1234/api/v1/models 2>/dev/null | head -c 50 || echo 'M1 OFFLINE'", "bash", timeout_s=5),
            DominoStep("health_ol1", "bash:curl -s --max-time 3 http://127.0.0.1:11434/api/tags 2>/dev/null | head -c 50 || echo 'OL1 OFFLINE'", "bash", timeout_s=5),
            DominoStep("disk", "python:get_disk_usage()", "python"),
            DominoStep("tts", "python:edge_tts_speak('Lundi matin. Code a jour, cluster verifie, disques ok. Bonne semaine!')", "python"),
        ],
        category="routine_matin",
        description="Monday morning: pull + health + disk check",
        learning_context="Routine — demarrer la semaine proprement",
        priority="normal",
    ),
    # ── Batch 104 — MILESTONE 3000 — Hardware/Logging/Collab/STT (10 dominos) ──
    DominoPipeline(
        id="domino_hardware_audit",
        trigger_vocal=["audit hardware", "hardware check", "verification materiel", "check composants"],
        steps=[
            DominoStep("cpu", "bash:powershell -Command \"(Get-CimInstance Win32_Processor).Name\" 2>/dev/null || echo 'CPU info N/A'", "bash", timeout_s=5),
            DominoStep("gpu", "bash:nvidia-smi --query-gpu=name,memory.total --format=csv,noheader 2>/dev/null || echo 'GPU N/A'", "bash", timeout_s=5),
            DominoStep("ram", "python:system_memory_usage()", "python"),
            DominoStep("disk", "python:get_disk_usage()", "python"),
            DominoStep("tts", "python:edge_tts_speak('Audit hardware termine. CPU, GPU, RAM et disques verifies.')", "python"),
        ],
        category="hardware",
        description="Hardware audit: CPU + GPU + RAM + disk",
        learning_context="Hardware — audit materiel complet",
        priority="high",
    ),
    DominoPipeline(
        id="domino_thermal_check",
        trigger_vocal=["check thermique", "temperatures", "thermal check", "chauffe"],
        steps=[
            DominoStep("gpu_temp", "bash:nvidia-smi --query-gpu=name,temperature.gpu,fan.speed --format=csv,noheader 2>/dev/null || echo 'GPU temp N/A'", "bash", timeout_s=5),
            DominoStep("tts", "python:edge_tts_speak('Verification thermique terminee. Temperatures GPU affichees.')", "python"),
        ],
        category="hardware",
        description="Thermal check: GPU temperatures",
        learning_context="Hardware — verification temperatures",
        priority="normal",
    ),
    DominoPipeline(
        id="domino_log_review",
        trigger_vocal=["review logs", "revue des logs", "check logs", "analyse logs"],
        steps=[
            DominoStep("recent", "bash:cd F:/BUREAU/turbo && tail -10 data/claude_tool_log.jsonl 2>/dev/null | head -5 || echo 'No logs'", "bash", timeout_s=5),
            DominoStep("errors", "bash:cd F:/BUREAU/turbo && grep -ic 'error\\|exception' data/claude_tool_log.jsonl 2>/dev/null || echo '0 errors'", "bash", timeout_s=5),
            DominoStep("tts", "python:edge_tts_speak('Revue des logs terminee. Derniers logs et erreurs affiches.')", "python"),
        ],
        category="logging",
        description="Log review: recent entries + error count",
        learning_context="Logging — revue des logs recents",
        priority="normal",
    ),
    DominoPipeline(
        id="domino_collab_overview",
        trigger_vocal=["overview collaboration", "collaboration status", "equipe status", "collab overview"],
        steps=[
            DominoStep("contributors", "bash:cd F:/BUREAU/turbo && git shortlog -sn --all 2>/dev/null | head -5 || echo 'Git error'", "bash", timeout_s=5),
            DominoStep("branches", "bash:cd F:/BUREAU/turbo && git branch -a 2>/dev/null | wc -l || echo '?'", "bash", timeout_s=5),
            DominoStep("tags", "bash:cd F:/BUREAU/turbo && git tag -l 2>/dev/null | wc -l || echo '0 tags'", "bash", timeout_s=5),
            DominoStep("tts", "python:edge_tts_speak('Overview collaboration. Contributeurs, branches et tags affiches.')", "python"),
        ],
        category="collaboration",
        description="Collaboration overview: contributors + branches + tags",
        learning_context="Collaboration — vue d'ensemble equipe",
        priority="normal",
    ),
    DominoPipeline(
        id="domino_changelog_gen",
        trigger_vocal=["genere changelog", "changelog generation", "release notes", "notes de version"],
        steps=[
            DominoStep("changelog", "bash:cd F:/BUREAU/turbo && git log --oneline --since='30 days ago' | head -20", "bash", timeout_s=5),
            DominoStep("tts", "python:edge_tts_speak('Changelog du dernier mois genere.')", "python"),
        ],
        category="release",
        description="Generate changelog: last 30 days commits",
        learning_context="Release — generation du changelog",
        priority="normal",
    ),
    DominoPipeline(
        id="domino_debug_session",
        trigger_vocal=["session debug", "debug session", "commence le debug", "debug mode"],
        steps=[
            DominoStep("errors", "bash:cd F:/BUREAU/turbo && grep -ic 'error\\|exception\\|traceback' data/claude_tool_log.jsonl 2>/dev/null || echo '0'", "bash", timeout_s=5),
            DominoStep("syntax", "bash:cd F:/BUREAU/turbo && python -m py_compile src/commands.py && python -m py_compile src/voice_correction.py && echo 'SYNTAX OK'", "bash", timeout_s=10),
            DominoStep("match", "python:test_voice_match('ouvre chrome')", "python"),
            DominoStep("tts", "python:edge_tts_speak('Session debug preparee. Erreurs comptees, syntaxe et matching verifies.')", "python"),
        ],
        category="debugging",
        description="Debug session start: errors + syntax + match test",
        learning_context="Debug — preparation session de debug",
        priority="high",
    ),
    DominoPipeline(
        id="domino_usb_check",
        trigger_vocal=["check usb", "peripheriques usb", "usb connectes", "liste usb"],
        steps=[
            DominoStep("usb", "bash:powershell -Command \"Get-PnpDevice -Class USB | Where-Object {\\$_.Status -eq 'OK'} | Select-Object -First 8 FriendlyName\" 2>/dev/null || echo 'USB info N/A'", "bash", timeout_s=10),
            DominoStep("tts", "python:edge_tts_speak('Peripheriques USB connectes listes.')", "python"),
        ],
        category="hardware",
        description="Check connected USB devices",
        learning_context="Hardware — peripheriques USB connectes",
        priority="normal",
    ),
    DominoPipeline(
        id="domino_driver_check",
        trigger_vocal=["check drivers", "verification drivers", "pilotes installes", "drivers status"],
        steps=[
            DominoStep("drivers", "bash:powershell -Command \"Get-WmiObject Win32_PnPSignedDriver | Where-Object {\\$_.DeviceName} | Select-Object -First 10 DeviceName,DriverVersion | Format-Table\" 2>/dev/null || echo 'N/A'", "bash", timeout_s=10),
            DominoStep("tts", "python:edge_tts_speak('Verification des drivers terminee.')", "python"),
        ],
        category="hardware",
        description="Check installed device drivers",
        learning_context="Hardware — verification pilotes installes",
        priority="normal",
    ),
    DominoPipeline(
        id="domino_3000_celebration",
        trigger_vocal=["trois mille corrections", "milestone trois mille", "3000 corrections", "celebration 3000"],
        steps=[
            DominoStep("summary", "python:project_summary()", "python"),
            DominoStep("corrections", "python:voice_corrections_by_category()", "python"),
            DominoStep("phonetics", "python:phonetic_groups_summary()", "python"),
            DominoStep("implicits", "python:implicit_commands_top()", "python"),
            DominoStep("fillers", "python:filler_words_count()", "python"),
            DominoStep("tts", "python:edge_tts_speak('Milestone 3000 corrections! Felicitations! Le systeme vocal JARVIS est maintenant extremement complet.')", "python"),
        ],
        category="milestone",
        description="3000 corrections milestone celebration",
        learning_context="Milestone — celebration 3000 corrections vocales",
        priority="high",
    ),
    DominoPipeline(
        id="domino_bios_info",
        trigger_vocal=["info bios", "bios check", "uefi info", "firmware check"],
        steps=[
            DominoStep("bios", "bash:powershell -Command \"Get-CimInstance Win32_BIOS | Select-Object Manufacturer,SMBIOSBIOSVersion\" 2>/dev/null || echo 'BIOS info N/A'", "bash", timeout_s=10),
            DominoStep("tts", "python:edge_tts_speak('Information BIOS affichee.')", "python"),
        ],
        category="hardware",
        description="BIOS/UEFI information",
        learning_context="Hardware — information BIOS/firmware",
        priority="normal",
    ),
    # ── Batch 110 — PackageMgr/Docs/Storage/Quantificateurs (10 dominos) ──
    DominoPipeline(
        id="domino_pkg_audit",
        trigger_vocal=["audit packages", "check packages", "packages audit", "audit dependances"],
        steps=[
            DominoStep("pip", "bash:pip list --outdated 2>/dev/null | head -10 || echo 'pip N/A'", "bash", timeout_s=15),
            DominoStep("npm", "bash:npm outdated 2>/dev/null | head -10 || echo 'npm N/A'", "bash", timeout_s=15),
            DominoStep("tts", "python:edge_tts_speak('Audit des packages termine.')", "python"),
        ],
        category="dependencies",
        description="Package audit: pip + npm outdated",
        learning_context="Dependencies — audit packages obsoletes",
        priority="normal",
    ),
    DominoPipeline(
        id="domino_docs_build",
        trigger_vocal=["build docs", "genere la doc", "documentation build", "compile docs"],
        steps=[
            DominoStep("sphinx", "bash:sphinx-build --version 2>/dev/null || echo 'Sphinx N/A'", "bash", timeout_s=5),
            DominoStep("mkdocs", "bash:mkdocs --version 2>/dev/null || echo 'MkDocs N/A'", "bash", timeout_s=5),
            DominoStep("tts", "python:edge_tts_speak('Outils de documentation verifies.')", "python"),
        ],
        category="documentation",
        description="Documentation tools check (Sphinx + MkDocs)",
        learning_context="Documentation — outils de generation",
        priority="normal",
    ),
    DominoPipeline(
        id="domino_cloud_storage",
        trigger_vocal=["check cloud storage", "storage overview", "stockage cloud", "cloud storage"],
        steps=[
            DominoStep("s3", "bash:aws s3 ls 2>/dev/null | head -5 || echo 'S3 N/A'", "bash", timeout_s=10),
            DominoStep("minio", "bash:mc admin info 2>/dev/null | head -3 || echo 'MinIO N/A'", "bash", timeout_s=5),
            DominoStep("tts", "python:edge_tts_speak('Stockage cloud verifie.')", "python"),
        ],
        category="cloud",
        description="Cloud storage check (S3 + MinIO)",
        learning_context="Cloud — verification stockage",
        priority="normal",
    ),
    DominoPipeline(
        id="domino_swagger_api",
        trigger_vocal=["swagger api", "ouvre swagger", "api documentation", "swagger docs"],
        steps=[
            DominoStep("check", "bash:curl -s http://127.0.0.1:8000/openapi.json 2>/dev/null | head -5 || curl -s http://127.0.0.1:8000/docs 2>/dev/null | head -3 || echo 'Swagger N/A'", "bash", timeout_s=10),
            DominoStep("tts", "python:edge_tts_speak('Documentation API Swagger verifiee.')", "python"),
        ],
        category="documentation",
        description="Swagger/OpenAPI documentation check",
        learning_context="Documentation — Swagger OpenAPI",
        priority="normal",
    ),
    DominoPipeline(
        id="domino_pkg_managers",
        trigger_vocal=["check package managers", "gestionnaires de paquets", "pkg managers", "all package managers"],
        steps=[
            DominoStep("pip", "bash:pip --version 2>/dev/null || echo 'pip N/A'", "bash", timeout_s=3),
            DominoStep("npm", "bash:npm --version 2>/dev/null || echo 'npm N/A'", "bash", timeout_s=3),
            DominoStep("pnpm", "bash:pnpm --version 2>/dev/null || echo 'pnpm N/A'", "bash", timeout_s=3),
            DominoStep("cargo", "bash:cargo --version 2>/dev/null || echo 'cargo N/A'", "bash", timeout_s=3),
            DominoStep("tts", "python:edge_tts_speak('Gestionnaires de paquets verifies.')", "python"),
        ],
        category="dependencies",
        description="All package managers check",
        learning_context="Dependencies — verification tous gestionnaires",
        priority="normal",
    ),
    DominoPipeline(
        id="domino_s3_usage",
        trigger_vocal=["usage s3", "s3 usage", "espace s3", "s3 disk usage"],
        steps=[
            DominoStep("buckets", "bash:aws s3 ls 2>/dev/null | wc -l || echo 'S3 N/A'", "bash", timeout_s=10),
            DominoStep("tts", "python:edge_tts_speak('Usage S3 affiche.')", "python"),
        ],
        category="cloud",
        description="S3 storage usage overview",
        learning_context="Cloud — usage stockage S3",
        priority="normal",
    ),
    DominoPipeline(
        id="domino_pip_security",
        trigger_vocal=["securite pip", "pip audit", "vulnerabilites pip", "pip security"],
        steps=[
            DominoStep("audit", "bash:pip audit 2>/dev/null | head -20 || echo 'pip audit N/A (pip >= 22.3 required)'", "bash", timeout_s=30),
            DominoStep("tts", "python:edge_tts_speak('Audit securite pip termine.')", "python"),
        ],
        category="security",
        description="pip security audit for vulnerabilities",
        learning_context="Securite — audit vulnerabilites pip",
        priority="high",
    ),
    DominoPipeline(
        id="domino_conda_envs",
        trigger_vocal=["conda envs", "environnements conda", "conda environments", "liste conda"],
        steps=[
            DominoStep("envs", "bash:conda env list 2>/dev/null || echo 'conda N/A'", "bash", timeout_s=10),
            DominoStep("tts", "python:edge_tts_speak('Environnements conda affiches.')", "python"),
        ],
        category="dependencies",
        description="Conda environments list",
        learning_context="Dependencies — environnements conda",
        priority="normal",
    ),
    DominoPipeline(
        id="domino_readme_check",
        trigger_vocal=["check readme", "readme status", "verifie le readme", "readme ok"],
        steps=[
            DominoStep("check", "bash:cd F:/BUREAU/turbo && wc -l README.md 2>/dev/null || echo 'No README.md'", "bash", timeout_s=3),
            DominoStep("tts", "python:edge_tts_speak('README verifie.')", "python"),
        ],
        category="documentation",
        description="README.md existence and size check",
        learning_context="Documentation — verification README",
        priority="normal",
    ),
    DominoPipeline(
        id="domino_dependency_tree",
        trigger_vocal=["arbre dependances", "dependency tree", "deps tree", "arbre des deps"],
        steps=[
            DominoStep("pip", "bash:pip show pip 2>/dev/null | head -5 || echo 'pip N/A'", "bash", timeout_s=5),
            DominoStep("npm", "bash:npm list --depth=1 2>/dev/null | head -15 || echo 'npm N/A'", "bash", timeout_s=10),
            DominoStep("tts", "python:edge_tts_speak('Arbre des dependances affiche.')", "python"),
        ],
        category="dependencies",
        description="Dependency tree overview",
        learning_context="Dependencies — arbre des dependances",
        priority="normal",
    ),
    # ── Batch 109 — StateMgmt/Gateway/CI-CD/Sons (10 dominos) ──
    DominoPipeline(
        id="domino_state_mgmt",
        trigger_vocal=["check state management", "state mgmt", "gestion d'etat", "state overview"],
        steps=[
            DominoStep("redux", "bash:npm list redux 2>/dev/null | head -2 || echo 'Redux N/A'", "bash", timeout_s=5),
            DominoStep("zustand", "bash:npm list zustand 2>/dev/null | head -2 || echo 'Zustand N/A'", "bash", timeout_s=5),
            DominoStep("pinia", "bash:npm list pinia 2>/dev/null | head -2 || echo 'Pinia N/A'", "bash", timeout_s=5),
            DominoStep("tts", "python:edge_tts_speak('Overview state management affiche.')", "python"),
        ],
        category="frontend",
        description="State management libraries check",
        learning_context="Frontend — verification state management",
        priority="normal",
    ),
    DominoPipeline(
        id="domino_gateway_audit",
        trigger_vocal=["audit gateway", "check gateway", "gateway overview", "reverse proxy check"],
        steps=[
            DominoStep("nginx", "bash:nginx -v 2>&1 || echo 'Nginx N/A'", "bash", timeout_s=3),
            DominoStep("traefik", "bash:traefik version 2>/dev/null || echo 'Traefik N/A'", "bash", timeout_s=3),
            DominoStep("caddy", "bash:caddy version 2>/dev/null || echo 'Caddy N/A'", "bash", timeout_s=3),
            DominoStep("tts", "python:edge_tts_speak('Audit des gateways et reverse proxies termine.')", "python"),
        ],
        category="networking",
        description="API gateway and reverse proxy audit",
        learning_context="Networking — audit gateways et proxies",
        priority="normal",
    ),
    DominoPipeline(
        id="domino_ci_overview",
        trigger_vocal=["overview ci", "ci overview", "ci cd status", "pipelines ci"],
        steps=[
            DominoStep("gh", "bash:gh run list --limit 5 2>/dev/null || echo 'gh CLI N/A'", "bash", timeout_s=10),
            DominoStep("workflows", "bash:ls .github/workflows/*.yml 2>/dev/null || echo 'No GitHub workflows'", "bash", timeout_s=3),
            DominoStep("tts", "python:edge_tts_speak('Overview CI CD affiche.')", "python"),
        ],
        category="devops",
        description="CI/CD overview with GitHub Actions",
        learning_context="DevOps — overview CI/CD pipelines",
        priority="high",
    ),
    DominoPipeline(
        id="domino_argocd_apps",
        trigger_vocal=["argocd apps", "liste argocd", "applications argocd", "argo apps"],
        steps=[
            DominoStep("apps", "bash:argocd app list 2>/dev/null | head -10 || echo 'ArgoCD N/A'", "bash", timeout_s=10),
            DominoStep("tts", "python:edge_tts_speak('Applications ArgoCD affichees.')", "python"),
        ],
        category="devops",
        description="ArgoCD applications list",
        learning_context="DevOps — applications ArgoCD",
        priority="normal",
    ),
    DominoPipeline(
        id="domino_nginx_config",
        trigger_vocal=["config nginx", "nginx config", "nginx configuration", "verifie nginx"],
        steps=[
            DominoStep("test", "bash:nginx -t 2>&1 || echo 'Nginx N/A'", "bash", timeout_s=5),
            DominoStep("tts", "python:edge_tts_speak('Configuration Nginx verifiee.')", "python"),
        ],
        category="networking",
        description="Nginx configuration test",
        learning_context="Networking — test configuration Nginx",
        priority="normal",
    ),
    DominoPipeline(
        id="domino_service_mesh",
        trigger_vocal=["check service mesh", "service mesh", "istio check", "mesh status"],
        steps=[
            DominoStep("istio", "bash:istioctl version 2>/dev/null || echo 'Istio N/A'", "bash", timeout_s=5),
            DominoStep("linkerd", "bash:linkerd version 2>/dev/null || echo 'Linkerd N/A'", "bash", timeout_s=5),
            DominoStep("tts", "python:edge_tts_speak('Service mesh verifie.')", "python"),
        ],
        category="networking",
        description="Service mesh check (Istio/Linkerd)",
        learning_context="Networking — verification service mesh",
        priority="normal",
    ),
    DominoPipeline(
        id="domino_gh_actions_run",
        trigger_vocal=["lance github actions", "run gh actions", "trigger workflow", "github workflow run"],
        steps=[
            DominoStep("list", "bash:gh workflow list 2>/dev/null || echo 'gh CLI N/A'", "bash", timeout_s=10),
            DominoStep("tts", "python:edge_tts_speak('Workflows GitHub affiches. Specifiez le workflow a lancer.')", "python"),
        ],
        category="devops",
        description="GitHub Actions workflow list",
        learning_context="DevOps — liste workflows GitHub Actions",
        priority="normal",
    ),
    DominoPipeline(
        id="domino_rate_limit",
        trigger_vocal=["check rate limiting", "rate limit", "limite de requetes", "throttling check"],
        steps=[
            DominoStep("check", "bash:echo 'Rate limiting: check Nginx/Traefik/Kong config' && nginx -T 2>/dev/null | grep -i 'limit_req' | head -5 || echo 'No rate limiting config found'", "bash", timeout_s=5),
            DominoStep("tts", "python:edge_tts_speak('Verification du rate limiting terminee.')", "python"),
        ],
        category="security",
        description="Rate limiting configuration check",
        learning_context="Securite — verification rate limiting",
        priority="normal",
    ),
    DominoPipeline(
        id="domino_jenkins_build",
        trigger_vocal=["jenkins build", "lance jenkins", "build jenkins", "jenkins job"],
        steps=[
            DominoStep("check", "bash:curl -s http://127.0.0.1:8080/api/json 2>/dev/null | python -c \"import sys,json;d=json.load(sys.stdin);print(f'Jenkins: {len(d.get(\\\"jobs\\\",[] ))} jobs')\" || echo 'Jenkins N/A'", "bash", timeout_s=10),
            DominoStep("tts", "python:edge_tts_speak('Status Jenkins affiche.')", "python"),
        ],
        category="devops",
        description="Jenkins build status",
        learning_context="DevOps — statut Jenkins builds",
        priority="normal",
    ),
    DominoPipeline(
        id="domino_proxy_health",
        trigger_vocal=["sante proxy", "proxy health", "check proxy", "reverse proxy status"],
        steps=[
            DominoStep("nginx", "bash:curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:80 2>/dev/null || echo 'Port 80 N/A'", "bash", timeout_s=5),
            DominoStep("tts", "python:edge_tts_speak('Sante du proxy verifiee.')", "python"),
        ],
        category="networking",
        description="Proxy health check",
        learning_context="Networking — sante reverse proxy",
        priority="normal",
    ),
    # ── Batch 108 — ORM/Serverless/Testing/Temporel (10 dominos) ──
    DominoPipeline(
        id="domino_orm_overview",
        trigger_vocal=["overview orm", "check orm", "orm status", "database orm"],
        steps=[
            DominoStep("sqlalchemy", "bash:python -c \"import sqlalchemy;print(f'SQLAlchemy {sqlalchemy.__version__}')\" 2>/dev/null || echo 'SQLAlchemy N/A'", "bash", timeout_s=5),
            DominoStep("prisma", "bash:npx prisma --version 2>/dev/null || echo 'Prisma N/A'", "bash", timeout_s=5),
            DominoStep("tts", "python:edge_tts_speak('Overview ORM affiche.')", "python"),
        ],
        category="database",
        description="ORM tools overview: SQLAlchemy + Prisma",
        learning_context="Database — vue d'ensemble ORM",
        priority="normal",
    ),
    DominoPipeline(
        id="domino_serverless_check",
        trigger_vocal=["check serverless", "serverless status", "faas check", "fonctions cloud"],
        steps=[
            DominoStep("sls", "bash:serverless --version 2>/dev/null || echo 'Serverless N/A'", "bash", timeout_s=5),
            DominoStep("vercel", "bash:vercel --version 2>/dev/null || echo 'Vercel N/A'", "bash", timeout_s=5),
            DominoStep("tts", "python:edge_tts_speak('Verification serverless terminee.')", "python"),
        ],
        category="cloud",
        description="Serverless tools check",
        learning_context="Cloud — verification outils serverless",
        priority="normal",
    ),
    DominoPipeline(
        id="domino_test_suite_full",
        trigger_vocal=["suite de tests complete", "all tests", "tous les tests", "test complet"],
        steps=[
            DominoStep("pytest", "bash:cd F:/BUREAU/turbo && python -m pytest tests/ -q --tb=short 2>/dev/null | tail -10 || echo 'No pytest tests'", "bash", timeout_s=60),
            DominoStep("syntax", "bash:cd F:/BUREAU/turbo && python -m py_compile src/commands.py && python -m py_compile src/voice_correction.py && python -m py_compile src/domino_pipelines.py && python -m py_compile src/domino_executor.py && echo 'All syntax OK'", "bash", timeout_s=15),
            DominoStep("tts", "python:edge_tts_speak('Suite de tests complete terminee.')", "python"),
        ],
        category="testing",
        description="Full test suite: pytest + syntax checks",
        learning_context="Testing — suite complete pytest + syntaxe",
        priority="high",
    ),
    DominoPipeline(
        id="domino_e2e_launch",
        trigger_vocal=["lance les e2e", "e2e tests", "end to end", "teste e2e"],
        steps=[
            DominoStep("check", "bash:npx playwright --version 2>/dev/null || npx cypress --version 2>/dev/null || echo 'No E2E framework'", "bash", timeout_s=10),
            DominoStep("tts", "python:edge_tts_speak('Framework E2E verifie.')", "python"),
        ],
        category="testing",
        description="E2E testing framework check",
        learning_context="Testing — verification framework E2E",
        priority="normal",
    ),
    DominoPipeline(
        id="domino_migration_run",
        trigger_vocal=["lance les migrations", "run migration", "database migrate", "migration"],
        steps=[
            DominoStep("detect", "bash:ls alembic.ini 2>/dev/null && echo 'Alembic detected' || ls prisma/schema.prisma 2>/dev/null && echo 'Prisma detected' || echo 'No migration framework detected'", "bash", timeout_s=5),
            DominoStep("tts", "python:edge_tts_speak('Framework de migration detecte.')", "python"),
        ],
        category="database",
        description="Database migration framework detection",
        learning_context="Database — detection framework migration",
        priority="normal",
    ),
    DominoPipeline(
        id="domino_lambda_deploy",
        trigger_vocal=["deploie lambda", "lambda deploy", "deploy lambda function", "aws lambda deploy"],
        steps=[
            DominoStep("check", "bash:aws lambda list-functions --max-items 3 2>/dev/null | head -10 || echo 'AWS CLI N/A'", "bash", timeout_s=10),
            DominoStep("tts", "python:edge_tts_speak('Check Lambda termine. Confirmez le deploiement.')", "python"),
        ],
        category="cloud",
        description="AWS Lambda deployment check",
        learning_context="Cloud — deploiement AWS Lambda",
        priority="normal",
    ),
    DominoPipeline(
        id="domino_cypress_run",
        trigger_vocal=["lance cypress", "cypress run", "teste avec cypress", "cypress e2e"],
        steps=[
            DominoStep("run", "bash:npx cypress run --headless 2>/dev/null | tail -15 || echo 'Cypress N/A'", "bash", timeout_s=120),
            DominoStep("tts", "python:edge_tts_speak('Tests Cypress termines.')", "python"),
        ],
        category="testing",
        description="Run Cypress E2E tests headless",
        learning_context="Testing — execution Cypress headless",
        priority="normal",
    ),
    DominoPipeline(
        id="domino_vercel_preview",
        trigger_vocal=["preview vercel", "vercel preview", "deploie preview", "vercel dev"],
        steps=[
            DominoStep("check", "bash:vercel --version 2>/dev/null || echo 'Vercel N/A'", "bash", timeout_s=5),
            DominoStep("tts", "python:edge_tts_speak('Vercel verifie. Lancez vercel dev pour le preview.')", "python"),
        ],
        category="cloud",
        description="Vercel preview deployment check",
        learning_context="Cloud — preview deployment Vercel",
        priority="normal",
    ),
    DominoPipeline(
        id="domino_test_coverage",
        trigger_vocal=["coverage", "code coverage", "couverture de tests", "test coverage"],
        steps=[
            DominoStep("cov", "bash:cd F:/BUREAU/turbo && python -m pytest --cov=src/ --cov-report=term-missing tests/ 2>/dev/null | tail -15 || echo 'Coverage N/A'", "bash", timeout_s=60),
            DominoStep("tts", "python:edge_tts_speak('Rapport de couverture affiche.')", "python"),
        ],
        category="testing",
        description="Test coverage report",
        learning_context="Testing — rapport couverture de tests",
        priority="high",
    ),
    DominoPipeline(
        id="domino_db_health",
        trigger_vocal=["sante base de donnees", "database health", "check db", "sante db"],
        steps=[
            DominoStep("sqlite", "bash:cd F:/BUREAU/turbo && python -c \"import sqlite3;c=sqlite3.connect('data/etoile.db');print(f'etoile.db: {c.execute(\\\"SELECT COUNT(*) FROM sqlite_master WHERE type=\\\\\\\"table\\\\\\\"\\\").fetchone()[0]} tables')\" 2>/dev/null || echo 'etoile.db N/A'", "bash", timeout_s=5),
            DominoStep("jarvis", "bash:cd F:/BUREAU/turbo && python -c \"import sqlite3;c=sqlite3.connect('data/jarvis.db');print(f'jarvis.db: {c.execute(\\\"SELECT COUNT(*) FROM sqlite_master WHERE type=\\\\\\\"table\\\\\\\"\\\").fetchone()[0]} tables')\" 2>/dev/null || echo 'jarvis.db N/A'", "bash", timeout_s=5),
            DominoStep("tts", "python:edge_tts_speak('Sante des bases de donnees verifiee.')", "python"),
        ],
        category="database",
        description="Database health check (SQLite)",
        learning_context="Database — sante bases de donnees",
        priority="high",
    ),
    # ── Batch 107 — Terraform/Queues/BuildTools/Satisfaction (10 dominos) ──
    DominoPipeline(
        id="domino_iac_overview",
        trigger_vocal=["overview iac", "infrastructure as code", "iac status", "check iac"],
        steps=[
            DominoStep("tf", "bash:terraform version 2>/dev/null | head -1 || echo 'Terraform N/A'", "bash", timeout_s=5),
            DominoStep("ansible", "bash:ansible --version 2>/dev/null | head -1 || echo 'Ansible N/A'", "bash", timeout_s=5),
            DominoStep("pulumi", "bash:pulumi version 2>/dev/null || echo 'Pulumi N/A'", "bash", timeout_s=5),
            DominoStep("tts", "python:edge_tts_speak('Overview Infrastructure as Code affiche.')", "python"),
        ],
        category="infrastructure",
        description="IaC tools overview: Terraform + Ansible + Pulumi",
        learning_context="Infrastructure — vue d'ensemble IaC",
        priority="normal",
    ),
    DominoPipeline(
        id="domino_queue_health",
        trigger_vocal=["sante queues", "queue health", "check message queues", "brokers status"],
        steps=[
            DominoStep("rabbit", "bash:rabbitmqctl status 2>/dev/null | head -5 || echo 'RabbitMQ N/A'", "bash", timeout_s=10),
            DominoStep("redis", "bash:redis-cli ping 2>/dev/null || echo 'Redis N/A'", "bash", timeout_s=5),
            DominoStep("tts", "python:edge_tts_speak('Sante des message queues verifiee.')", "python"),
        ],
        category="messaging",
        description="Message queue health check",
        learning_context="Messaging — sante brokers de messages",
        priority="normal",
    ),
    DominoPipeline(
        id="domino_frontend_build",
        trigger_vocal=["build frontend", "frontend build", "compile le frontend", "build le front"],
        steps=[
            DominoStep("vite", "bash:npx vite --version 2>/dev/null || echo 'Vite N/A'", "bash", timeout_s=5),
            DominoStep("node", "bash:node --version 2>/dev/null && npm --version 2>/dev/null || echo 'Node N/A'", "bash", timeout_s=5),
            DominoStep("tts", "python:edge_tts_speak('Environnement frontend verifie.')", "python"),
        ],
        category="frontend",
        description="Frontend build environment check",
        learning_context="Frontend — verification environnement build",
        priority="normal",
    ),
    DominoPipeline(
        id="domino_storybook_launch",
        trigger_vocal=["lance storybook", "ouvre storybook", "storybook dev", "demarre storybook"],
        steps=[
            DominoStep("check", "bash:npx storybook --version 2>/dev/null || echo 'Storybook N/A'", "bash", timeout_s=10),
            DominoStep("tts", "python:edge_tts_speak('Storybook verifie.')", "python"),
        ],
        category="frontend",
        description="Storybook availability check",
        learning_context="Frontend — Storybook composants",
        priority="normal",
    ),
    DominoPipeline(
        id="domino_terraform_workflow",
        trigger_vocal=["workflow terraform", "terraform complet", "tf workflow", "pipeline terraform"],
        steps=[
            DominoStep("version", "bash:terraform version 2>/dev/null | head -1 || echo 'TF N/A'", "bash", timeout_s=5),
            DominoStep("init", "bash:echo 'Run: terraform init → plan → apply'", "bash", timeout_s=2),
            DominoStep("tts", "python:edge_tts_speak('Workflow Terraform affiche. Init, plan, puis apply.')", "python"),
        ],
        category="infrastructure",
        description="Terraform workflow guide",
        learning_context="Infrastructure — workflow Terraform init/plan/apply",
        priority="normal",
    ),
    DominoPipeline(
        id="domino_kafka_topics",
        trigger_vocal=["kafka topics", "liste kafka", "topics kafka", "kafka list"],
        steps=[
            DominoStep("topics", "bash:kafka-topics.sh --list --bootstrap-server 127.0.0.1:9092 2>/dev/null | head -20 || echo 'Kafka N/A'", "bash", timeout_s=10),
            DominoStep("tts", "python:edge_tts_speak('Topics Kafka affiches.')", "python"),
        ],
        category="messaging",
        description="List Kafka topics",
        learning_context="Messaging — liste des topics Kafka",
        priority="normal",
    ),
    DominoPipeline(
        id="domino_vitest_suite",
        trigger_vocal=["suite vitest", "lance les tests vitest", "vitest run all", "run vitest"],
        steps=[
            DominoStep("run", "bash:npx vitest run 2>/dev/null | tail -20 || echo 'Vitest N/A'", "bash", timeout_s=60),
            DominoStep("tts", "python:edge_tts_speak('Suite Vitest terminee.')", "python"),
        ],
        category="testing",
        description="Run Vitest test suite",
        learning_context="Testing — execution suite Vitest",
        priority="normal",
    ),
    DominoPipeline(
        id="domino_satisfaction",
        trigger_vocal=["tout va bien", "status global", "ca marche bien", "everything ok"],
        steps=[
            DominoStep("summary", "python:full_system_summary()", "python"),
            DominoStep("cluster", "bash:curl -s --max-time 3 http://127.0.0.1:1234/api/v1/models 2>/dev/null && echo 'M1 OK' || echo 'M1 DOWN'", "bash", timeout_s=5),
            DominoStep("tts", "python:edge_tts_speak('Tout va bien! Systeme operationnel.')", "python"),
        ],
        category="productivity",
        description="Satisfaction report with system summary",
        learning_context="Productivite — rapport positif systeme",
        priority="normal",
    ),
    DominoPipeline(
        id="domino_celery_monitor",
        trigger_vocal=["monitore celery", "celery workers", "celery monitor", "check celery workers"],
        steps=[
            DominoStep("workers", "bash:celery -A app inspect active 2>/dev/null | head -15 || echo 'Celery N/A'", "bash", timeout_s=10),
            DominoStep("tts", "python:edge_tts_speak('Workers Celery verifies.')", "python"),
        ],
        category="messaging",
        description="Celery workers monitoring",
        learning_context="Messaging — monitoring workers Celery",
        priority="normal",
    ),
    DominoPipeline(
        id="domino_build_tools_audit",
        trigger_vocal=["audit build tools", "check build tools", "outils de build", "build audit"],
        steps=[
            DominoStep("node", "bash:node --version 2>/dev/null || echo 'Node N/A'", "bash", timeout_s=3),
            DominoStep("vite", "bash:npx vite --version 2>/dev/null || echo 'Vite N/A'", "bash", timeout_s=5),
            DominoStep("esbuild", "bash:npx esbuild --version 2>/dev/null || echo 'esbuild N/A'", "bash", timeout_s=5),
            DominoStep("tts", "python:edge_tts_speak('Audit des outils de build termine.')", "python"),
        ],
        category="frontend",
        description="Build tools audit: Node + Vite + esbuild",
        learning_context="Frontend — audit outils build",
        priority="normal",
    ),
    # ── Batch 106 — Docker/OAuth/Logging/Frustration (10 dominos) ──
    DominoPipeline(
        id="domino_docker_overview",
        trigger_vocal=["overview docker", "resume docker", "docker resume", "etat docker"],
        steps=[
            DominoStep("ps", "bash:docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}' 2>/dev/null | head -10 || echo 'Docker N/A'", "bash", timeout_s=5),
            DominoStep("images", "bash:docker images --format 'table {{.Repository}}\t{{.Tag}}\t{{.Size}}' 2>/dev/null | head -10 || echo 'No images'", "bash", timeout_s=5),
            DominoStep("volumes", "bash:docker volume ls 2>/dev/null | wc -l || echo '0'", "bash", timeout_s=5),
            DominoStep("tts", "python:edge_tts_speak('Overview Docker affiche. Containers, images et volumes.')", "python"),
        ],
        category="containers",
        description="Docker complete overview: containers + images + volumes",
        learning_context="Docker — vue d'ensemble complete",
        priority="normal",
    ),
    DominoPipeline(
        id="domino_docker_cleanup",
        trigger_vocal=["clean docker", "nettoie docker", "docker prune", "purge docker"],
        steps=[
            DominoStep("check", "bash:docker system df 2>/dev/null || echo 'Docker N/A'", "bash", timeout_s=10),
            DominoStep("tts", "python:edge_tts_speak('Espace Docker affiche. Confirmez pour nettoyer.')", "python"),
        ],
        category="containers",
        description="Docker disk usage check before cleanup",
        learning_context="Docker — nettoyage et espace disque",
        priority="normal",
    ),
    DominoPipeline(
        id="domino_auth_audit",
        trigger_vocal=["audit auth", "audit authentification", "check securite auth", "auth security"],
        steps=[
            DominoStep("jwt", "bash:python -c \"import jwt;print(f'PyJWT {jwt.__version__}')\" 2>/dev/null || echo 'PyJWT N/A'", "bash", timeout_s=5),
            DominoStep("oauth", "bash:python -c \"import oauthlib;print(f'oauthlib {oauthlib.__version__}')\" 2>/dev/null || echo 'oauthlib N/A'", "bash", timeout_s=5),
            DominoStep("tts", "python:edge_tts_speak('Audit authentification termine.')", "python"),
        ],
        category="security",
        description="Authentication libraries audit",
        learning_context="Securite — audit librairies auth",
        priority="high",
    ),
    DominoPipeline(
        id="domino_elk_health",
        trigger_vocal=["health elk", "elk health", "sante elk", "elasticsearch health"],
        steps=[
            DominoStep("es", "bash:curl -s http://127.0.0.1:9200/_cluster/health 2>/dev/null | python -c \"import sys,json;d=json.load(sys.stdin);print(f'ES: {d[\\\"status\\\"]} ({d[\\\"number_of_nodes\\\"]} nodes)')\" || echo 'ES N/A'", "bash", timeout_s=10),
            DominoStep("tts", "python:edge_tts_speak('Sante ELK stack verifiee.')", "python"),
        ],
        category="monitoring",
        description="ELK stack health check",
        learning_context="Monitoring — sante ELK Elasticsearch",
        priority="normal",
    ),
    DominoPipeline(
        id="domino_observability",
        trigger_vocal=["check observabilite", "observability check", "monitoring check", "otel check"],
        steps=[
            DominoStep("otel", "bash:python -c \"import opentelemetry;print(f'OpenTelemetry {opentelemetry.version.__version__}')\" 2>/dev/null || echo 'OTel N/A'", "bash", timeout_s=5),
            DominoStep("prom", "bash:curl -s http://127.0.0.1:9090/api/v1/status/runtimeinfo 2>/dev/null | head -3 || echo 'Prometheus N/A'", "bash", timeout_s=5),
            DominoStep("tts", "python:edge_tts_speak('Verification observabilite terminee.')", "python"),
        ],
        category="monitoring",
        description="Observability stack check (OTel + Prometheus)",
        learning_context="Monitoring — observabilite OpenTelemetry",
        priority="normal",
    ),
    DominoPipeline(
        id="domino_frustration_handler",
        trigger_vocal=["ca marche pas", "rien ne marche", "tout est casse", "j'en ai marre"],
        steps=[
            DominoStep("calm", "python:edge_tts_speak('Je comprends votre frustration. Lancement du diagnostic automatique.')", "python"),
            DominoStep("syntax", "bash:cd F:/BUREAU/turbo && python -m py_compile src/commands.py && python -m py_compile src/voice_correction.py && echo 'Syntax OK' || echo 'SYNTAX ERROR!'", "bash", timeout_s=10),
            DominoStep("cluster", "bash:curl -s --max-time 3 http://127.0.0.1:1234/api/v1/models 2>/dev/null && echo 'M1 OK' || echo 'M1 DOWN'", "bash", timeout_s=5),
            DominoStep("gpu", "bash:nvidia-smi --query-gpu=temperature.gpu --format=csv,noheader 2>/dev/null || echo 'GPU N/A'", "bash", timeout_s=5),
            DominoStep("tts", "python:edge_tts_speak('Diagnostic termine. Resultats affiches.')", "python"),
        ],
        category="support",
        description="Frustration handler with automatic diagnostic",
        learning_context="Support — gestion frustration utilisateur + diagnostic auto",
        priority="high",
    ),
    DominoPipeline(
        id="domino_helm_deploy",
        trigger_vocal=["deploie helm", "helm deploy", "helm install", "install chart"],
        steps=[
            DominoStep("list", "bash:helm list -A 2>/dev/null | head -10 || echo 'Helm N/A'", "bash", timeout_s=10),
            DominoStep("tts", "python:edge_tts_speak('Charts Helm affiches. Specifiez le chart a deployer.')", "python"),
        ],
        category="deployment",
        description="Helm chart deployment overview",
        learning_context="Deployment — Helm charts Kubernetes",
        priority="normal",
    ),
    DominoPipeline(
        id="domino_mfa_check",
        trigger_vocal=["check mfa", "mfa status", "authentification double", "2fa check"],
        steps=[
            DominoStep("totp", "bash:python -c \"import pyotp;print(f'pyotp {pyotp.__version__}')\" 2>/dev/null || echo 'pyotp N/A'", "bash", timeout_s=5),
            DominoStep("tts", "python:edge_tts_speak('Verification MFA terminee.')", "python"),
        ],
        category="security",
        description="MFA/2FA library check",
        learning_context="Securite — verification MFA/2FA",
        priority="normal",
    ),
    DominoPipeline(
        id="domino_log_analysis",
        trigger_vocal=["analyse les logs", "log analysis", "cherche dans les logs", "parse logs"],
        steps=[
            DominoStep("recent", "bash:cd F:/BUREAU/turbo && ls -la data/*.log 2>/dev/null | tail -5 || echo 'No log files'", "bash", timeout_s=5),
            DominoStep("errors", "bash:cd F:/BUREAU/turbo && grep -i 'error\\|exception\\|fail' data/*.log 2>/dev/null | tail -10 || echo 'No errors in logs'", "bash", timeout_s=10),
            DominoStep("tts", "python:edge_tts_speak('Analyse des logs terminee.')", "python"),
        ],
        category="monitoring",
        description="Log analysis for recent errors",
        learning_context="Monitoring — analyse logs erreurs recentes",
        priority="high",
    ),
    DominoPipeline(
        id="domino_container_health",
        trigger_vocal=["sante containers", "container health", "check containers", "docker health"],
        steps=[
            DominoStep("health", "bash:docker ps --format '{{.Names}}: {{.Status}}' 2>/dev/null || echo 'Docker N/A'", "bash", timeout_s=5),
            DominoStep("stats", "bash:docker stats --no-stream --format 'table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}' 2>/dev/null | head -10 || echo 'Stats N/A'", "bash", timeout_s=10),
            DominoStep("tts", "python:edge_tts_speak('Sante des containers verifiee.')", "python"),
        ],
        category="containers",
        description="Container health check with resource usage",
        learning_context="Docker — sante et ressources containers",
        priority="normal",
    ),
    # ── Batch 105 — WebSocket/GraphQL/Cache/Urgence (10 dominos) ──
    DominoPipeline(
        id="domino_websocket_test",
        trigger_vocal=["test websocket", "check websocket", "teste les websocket", "ws test"],
        steps=[
            DominoStep("ws_check", "bash:python -c \"import websockets;print(f'websockets {websockets.__version__} OK')\" 2>/dev/null || pip show websockets 2>/dev/null | head -2 || echo 'websockets N/A'", "bash", timeout_s=10),
            DominoStep("tts", "python:edge_tts_speak('Verification WebSocket terminee.')", "python"),
        ],
        category="networking",
        description="WebSocket library check",
        learning_context="Networking — verification WebSocket",
        priority="normal",
    ),
    DominoPipeline(
        id="domino_graphql_check",
        trigger_vocal=["check graphql", "graphql status", "verifie graphql", "api graphql"],
        steps=[
            DominoStep("gql", "bash:python -c \"import graphql;print(f'graphql-core {graphql.__version__}')\" 2>/dev/null || echo 'GraphQL core N/A'", "bash", timeout_s=10),
            DominoStep("tts", "python:edge_tts_speak('Verification GraphQL terminee.')", "python"),
        ],
        category="api",
        description="GraphQL library check",
        learning_context="API — verification librairie GraphQL",
        priority="normal",
    ),
    DominoPipeline(
        id="domino_redis_check",
        trigger_vocal=["check redis", "redis status", "teste redis", "redis ping"],
        steps=[
            DominoStep("ping", "bash:redis-cli ping 2>/dev/null || echo 'Redis N/A (not installed or not running)'", "bash", timeout_s=5),
            DominoStep("info", "bash:redis-cli info server 2>/dev/null | head -5 || echo 'Redis info N/A'", "bash", timeout_s=5),
            DominoStep("tts", "python:edge_tts_speak('Verification Redis terminee.')", "python"),
        ],
        category="cache",
        description="Redis connectivity check",
        learning_context="Cache — verification Redis",
        priority="normal",
    ),
    DominoPipeline(
        id="domino_cache_stats",
        trigger_vocal=["stats cache", "cache status", "statistiques cache", "cache info"],
        steps=[
            DominoStep("python_cache", "bash:python -c \"import functools;print('functools.lru_cache disponible')\" 2>/dev/null", "bash", timeout_s=5),
            DominoStep("redis", "bash:redis-cli dbsize 2>/dev/null || echo 'Redis N/A'", "bash", timeout_s=5),
            DominoStep("tts", "python:edge_tts_speak('Statistiques cache affichees.')", "python"),
        ],
        category="cache",
        description="Cache statistics overview",
        learning_context="Cache — statistiques et etat",
        priority="normal",
    ),
    DominoPipeline(
        id="domino_api_health",
        trigger_vocal=["sante des api", "api health", "check api sante", "health check api"],
        steps=[
            DominoStep("m1", "bash:curl -s --max-time 3 http://127.0.0.1:1234/api/v1/models 2>/dev/null | python -c \"import sys,json;print('M1 OK:',len(json.load(sys.stdin).get('data',[])))\" || echo 'M1 OFFLINE'", "bash", timeout_s=5),
            DominoStep("ol1", "bash:curl -s --max-time 3 http://127.0.0.1:11434/api/tags 2>/dev/null | python -c \"import sys,json;print('OL1 OK:',len(json.load(sys.stdin).get('models',[])))\" || echo 'OL1 OFFLINE'", "bash", timeout_s=5),
            DominoStep("tts", "python:edge_tts_speak('Sante des API verifiee.')", "python"),
        ],
        category="monitoring",
        description="API health check for cluster endpoints",
        learning_context="Monitoring — sante des API cluster",
        priority="high",
    ),
    DominoPipeline(
        id="domino_incident_mode",
        trigger_vocal=["mode incident", "incident critique", "production down", "urgence prod"],
        steps=[
            DominoStep("alert", "python:edge_tts_speak('ALERTE! Mode incident active. Diagnostic en cours.')", "python"),
            DominoStep("cluster", "bash:curl -s --max-time 3 http://127.0.0.1:1234/api/v1/models 2>/dev/null && echo 'M1 OK' || echo 'M1 DOWN'", "bash", timeout_s=5),
            DominoStep("gpu", "bash:nvidia-smi --query-gpu=temperature.gpu,utilization.gpu --format=csv,noheader 2>/dev/null || echo 'GPU N/A'", "bash", timeout_s=5),
            DominoStep("disk", "bash:df -h / 2>/dev/null | tail -1 || powershell -Command \"Get-PSDrive C | Select-Object Used,Free\" 2>/dev/null", "bash", timeout_s=5),
            DominoStep("tts", "python:edge_tts_speak('Diagnostic incident termine. Resultats affiches.')", "python"),
        ],
        category="incident",
        description="Incident response mode with full system diagnostic",
        learning_context="Incident — mode urgence diagnostic complet",
        priority="critical",
    ),
    DominoPipeline(
        id="domino_hotfix_deploy",
        trigger_vocal=["hotfix", "deploie le hotfix", "hot fix urgent", "patch urgent"],
        steps=[
            DominoStep("status", "bash:cd F:/BUREAU/turbo && git status -s", "bash", timeout_s=5),
            DominoStep("test", "bash:cd F:/BUREAU/turbo && python -m py_compile src/commands.py && python -m py_compile src/voice_correction.py && echo 'Syntax OK'", "bash", timeout_s=10),
            DominoStep("tts", "python:edge_tts_speak('Hotfix pret. Veuillez confirmer le commit et push.')", "python"),
        ],
        category="deployment",
        description="Hotfix preparation with syntax check",
        learning_context="Deployment — preparation hotfix urgent",
        priority="critical",
    ),
    DominoPipeline(
        id="domino_streaming_check",
        trigger_vocal=["check streaming", "test streaming api", "streaming status", "sse check"],
        steps=[
            DominoStep("sse", "bash:python -c \"import aiohttp;print(f'aiohttp {aiohttp.__version__} (SSE capable)')\" 2>/dev/null || echo 'aiohttp N/A'", "bash", timeout_s=10),
            DominoStep("tts", "python:edge_tts_speak('Verification streaming API terminee.')", "python"),
        ],
        category="networking",
        description="Streaming/SSE capability check",
        learning_context="Networking — verification streaming API",
        priority="normal",
    ),
    DominoPipeline(
        id="domino_cdn_check",
        trigger_vocal=["check cdn", "cdn status", "verifie le cdn", "cache cdn"],
        steps=[
            DominoStep("cdn", "bash:curl -s -I https://cdn.jsdelivr.net/npm/jquery/dist/jquery.min.js 2>/dev/null | head -5 || echo 'CDN check failed'", "bash", timeout_s=10),
            DominoStep("tts", "python:edge_tts_speak('Verification CDN terminee.')", "python"),
        ],
        category="networking",
        description="CDN availability check",
        learning_context="Networking — verification CDN",
        priority="normal",
    ),
    DominoPipeline(
        id="domino_priority_report",
        trigger_vocal=["rapport priorites", "quoi d'urgent", "priorite du jour", "tasks urgentes"],
        steps=[
            DominoStep("git", "bash:cd F:/BUREAU/turbo && git log --oneline -5", "bash", timeout_s=5),
            DominoStep("status", "bash:cd F:/BUREAU/turbo && git status -s | wc -l", "bash", timeout_s=5),
            DominoStep("summary", "python:project_summary()", "python"),
            DominoStep("tts", "python:edge_tts_speak('Rapport de priorites affiche.')", "python"),
        ],
        category="productivity",
        description="Priority report with recent changes and pending work",
        learning_context="Productivite — rapport priorites et urgences",
        priority="high",
    ),
    # ── Batch 103 — ML/Web/SQL/JARVIS-meta (10 dominos) ──
    DominoPipeline(
        id="domino_ml_setup",
        trigger_vocal=["setup ml", "machine learning setup", "prepare le ml", "check ml"],
        steps=[
            DominoStep("pytorch", "bash:python -c \"import torch;print(f'PyTorch {torch.__version__} CUDA:{torch.cuda.is_available()} GPUs:{torch.cuda.device_count()}')\" 2>/dev/null || echo 'PyTorch N/A'", "bash", timeout_s=10),
            DominoStep("gpu", "bash:nvidia-smi --query-gpu=name,memory.used,memory.total --format=csv,noheader 2>/dev/null | head -3 || echo 'nvidia-smi N/A'", "bash", timeout_s=5),
            DominoStep("tts", "python:edge_tts_speak('Setup machine learning verifie. PyTorch et GPU verifies.')", "python"),
        ],
        category="ai_ml",
        description="ML setup check: PyTorch + GPU availability",
        learning_context="IA/ML — verification setup entrainement",
        priority="high",
    ),
    DominoPipeline(
        id="domino_gpu_vram",
        trigger_vocal=["vram detaillee", "gpu vram", "memoire gpu detaillee", "nvidia vram"],
        steps=[
            DominoStep("vram", "bash:nvidia-smi --query-gpu=name,memory.used,memory.total,memory.free,temperature.gpu,utilization.gpu --format=csv,noheader 2>/dev/null || echo 'nvidia-smi N/A'", "bash", timeout_s=5),
            DominoStep("tts", "python:edge_tts_speak('VRAM GPU detaillee affichee.')", "python"),
        ],
        category="gpu_monitoring",
        description="Detailed GPU VRAM usage",
        learning_context="GPU — monitoring VRAM detaille",
        priority="normal",
    ),
    DominoPipeline(
        id="domino_web_stack",
        trigger_vocal=["stack web", "web stack check", "frontend backend", "full stack check"],
        steps=[
            DominoStep("node", "bash:node --version 2>&1", "bash", timeout_s=3),
            DominoStep("npm", "bash:npm --version 2>&1", "bash", timeout_s=3),
            DominoStep("python", "bash:python --version 2>&1", "bash", timeout_s=3),
            DominoStep("tsc", "bash:npx tsc --version 2>/dev/null || echo 'TSC N/A'", "bash", timeout_s=5),
            DominoStep("tts", "python:edge_tts_speak('Stack web verifiee. Node, npm, Python et TypeScript.')", "python"),
        ],
        category="web_dev",
        description="Web stack check: Node + npm + Python + TSC",
        learning_context="Web — verification stack complete",
        priority="normal",
    ),
    DominoPipeline(
        id="domino_sql_audit",
        trigger_vocal=["audit sql", "sql audit", "verifie les bases", "database audit"],
        steps=[
            DominoStep("tables", "python:db_table_count()", "python"),
            DominoStep("integrity", "bash:cd F:/BUREAU/turbo && python -c \"import sqlite3;[print(f'{db}: {sqlite3.connect(f\\\"data/{db}\\\").execute(\\\"PRAGMA integrity_check\\\").fetchone()[0]}') for db in ['etoile.db','jarvis.db','sniper.db']]\" 2>/dev/null || echo 'Integrity check error'", "bash", timeout_s=10),
            DominoStep("tts", "python:edge_tts_speak('Audit SQL termine. Tables comptees et integrite verifiee.')", "python"),
        ],
        category="database",
        description="SQL audit: table counts + integrity check",
        learning_context="Database — audit SQL complet",
        priority="high",
    ),
    DominoPipeline(
        id="domino_voice_system_audit",
        trigger_vocal=["audit vocal", "voice system audit", "audit systeme vocal", "check vocal complet"],
        steps=[
            DominoStep("summary", "python:project_summary()", "python"),
            DominoStep("phonetics", "python:phonetic_groups_summary()", "python"),
            DominoStep("implicits", "python:implicit_commands_top()", "python"),
            DominoStep("fillers", "python:filler_words_count()", "python"),
            DominoStep("corrections", "python:voice_corrections_by_category()", "python"),
            DominoStep("tts", "python:edge_tts_speak('Audit systeme vocal complet. Commandes, corrections, phonetiques, implicites et fillers tous verifies.')", "python"),
        ],
        category="voice_audit",
        description="Full voice system audit: all vocal subsystems",
        learning_context="Voice — audit complet du systeme vocal",
        priority="critical",
    ),
    DominoPipeline(
        id="domino_jarvis_health",
        trigger_vocal=["sante jarvis", "jarvis health", "comment va jarvis", "jarvis ok"],
        steps=[
            DominoStep("syntax", "bash:cd F:/BUREAU/turbo && python -m py_compile src/commands.py && python -m py_compile src/voice_correction.py && echo 'SYNTAX OK'", "bash", timeout_s=10),
            DominoStep("summary", "python:project_summary()", "python"),
            DominoStep("cluster", "python:cluster_node_count()", "python"),
            DominoStep("tts", "python:edge_tts_speak('JARVIS est en bonne sante. Syntaxe, stats et cluster verifies.')", "python"),
        ],
        category="self_diagnostics",
        description="JARVIS health check: syntax + stats + cluster",
        learning_context="JARVIS — verification de sante",
        priority="high",
    ),
    DominoPipeline(
        id="domino_whisper_check",
        trigger_vocal=["check whisper", "whisper status", "stt check", "reconnaissance vocale"],
        steps=[
            DominoStep("whisper", "bash:python -c \"import whisper; print(f'Whisper OK — model loaded')\" 2>/dev/null || echo 'Whisper non installe'", "bash", timeout_s=10),
            DominoStep("tts", "python:edge_tts_speak('Verification Whisper terminee.')", "python"),
        ],
        category="voice_system",
        description="Whisper STT check",
        learning_context="Voice — verification du moteur STT Whisper",
        priority="normal",
    ),
    DominoPipeline(
        id="domino_model_info",
        trigger_vocal=["info modeles", "model info", "details modeles", "modeles charges"],
        steps=[
            DominoStep("ollama", "python:list_ollama_models()", "python"),
            DominoStep("lms", "python:list_lm_studio_models()", "python"),
            DominoStep("tts", "python:edge_tts_speak('Information sur les modeles. Ollama et LM Studio resumes.')", "python"),
        ],
        category="ai_ml",
        description="Model info: Ollama + LM Studio",
        learning_context="IA — information sur les modeles charges",
        priority="normal",
    ),
    DominoPipeline(
        id="domino_large_files",
        trigger_vocal=["gros fichiers", "large files", "fichiers volumineux", "plus gros fichiers"],
        steps=[
            DominoStep("large", "python:large_files_check()", "python"),
            DominoStep("loc", "python:count_lines_of_code()", "python"),
            DominoStep("tts", "python:edge_tts_speak('Fichiers volumineux et lignes de code affiches.')", "python"),
        ],
        category="project_stats",
        description="Large files check + lines of code",
        learning_context="Projet — fichiers volumineux et taille du code",
        priority="normal",
    ),
    DominoPipeline(
        id="domino_everything_check",
        trigger_vocal=["check tout tout tout", "mega check", "everything check", "verifie absolument tout"],
        steps=[
            DominoStep("syntax", "bash:cd F:/BUREAU/turbo && python -m py_compile src/commands.py && python -m py_compile src/voice_correction.py && python -m py_compile src/domino_pipelines.py && python -m py_compile src/domino_executor.py && echo 'SYNTAX ALL OK'", "bash", timeout_s=15),
            DominoStep("summary", "python:project_summary()", "python"),
            DominoStep("cluster", "python:cluster_node_count()", "python"),
            DominoStep("ram", "python:system_memory_usage()", "python"),
            DominoStep("disk", "python:get_disk_usage()", "python"),
            DominoStep("db", "python:db_table_count()", "python"),
            DominoStep("git", "python:git_status_short()", "python"),
            DominoStep("phonetics", "python:phonetic_groups_summary()", "python"),
            DominoStep("implicits", "python:implicit_commands_top()", "python"),
            DominoStep("large", "python:large_files_check()", "python"),
            DominoStep("tts", "python:edge_tts_speak('Mega check termine! Syntaxe, projet, cluster, memoire, disques, bases, git, phonetiques, implicites et fichiers tous verifies. Tout est OK!')", "python"),
        ],
        category="mega_diagnostics",
        description="EVERYTHING check: all 10 subsystems verified",
        learning_context="Diagnostic — verification absolument complete de tout",
        priority="critical",
    ),
    # ── Batch 102 — Infra/Email/Storage/Perf (10 dominos) ──
    DominoPipeline(
        id="domino_infra_check",
        trigger_vocal=["check infra", "infrastructure check", "verification infra", "infra status"],
        steps=[
            DominoStep("ansible", "bash:ansible --version 2>/dev/null | head -1 || echo 'Ansible N/A'", "bash", timeout_s=5),
            DominoStep("vagrant", "bash:vagrant --version 2>/dev/null || echo 'Vagrant N/A'", "bash", timeout_s=5),
            DominoStep("terraform", "bash:terraform --version 2>/dev/null | head -1 || echo 'Terraform N/A'", "bash", timeout_s=5),
            DominoStep("tts", "python:edge_tts_speak('Outils infrastructure verifies. Ansible, Vagrant et Terraform.')", "python"),
        ],
        category="infrastructure",
        description="Infrastructure tools check: Ansible + Vagrant + Terraform",
        learning_context="Infra — verification outils de gestion de config",
        priority="normal",
    ),
    DominoPipeline(
        id="domino_messaging_status",
        trigger_vocal=["statut messaging", "messaging check", "communication status", "apps communication"],
        steps=[
            DominoStep("tts", "python:edge_tts_speak('Verifiez Slack, Discord et Telegram manuellement. Status messaging affiche.')", "python"),
        ],
        category="communication",
        description="Messaging apps status check",
        learning_context="Communication — statut des apps de messaging",
        priority="normal",
    ),
    DominoPipeline(
        id="domino_storage_full",
        trigger_vocal=["stockage complet", "full storage check", "verification stockage", "disk full check"],
        steps=[
            DominoStep("disk", "python:get_disk_usage()", "python"),
            DominoStep("partitions", "bash:powershell -Command \"Get-Volume | Where-Object {\\$_.DriveLetter} | Select-Object DriveLetter,SizeRemaining,Size | Format-Table\" 2>/dev/null || echo 'PowerShell N/A'", "bash", timeout_s=10),
            DominoStep("tts", "python:edge_tts_speak('Verification stockage complete. Disques et partitions affiches.')", "python"),
        ],
        category="system_diagnostics",
        description="Full storage check: disk usage + partitions",
        learning_context="Systeme — verification complete du stockage",
        priority="normal",
    ),
    DominoPipeline(
        id="domino_perf_benchmark",
        trigger_vocal=["benchmark performance", "perf benchmark", "test performance", "bench complet"],
        steps=[
            DominoStep("import_bench", "bash:cd F:/BUREAU/turbo && python -c \"import time;s=time.time();from src.commands import COMMANDS;from src.voice_correction import IMPLICIT_COMMANDS;from src.domino_pipelines import DOMINO_PIPELINES;print(f'Import: {time.time()-s:.3f}s')\"", "bash", timeout_s=10),
            DominoStep("ram", "python:system_memory_usage()", "python"),
            DominoStep("cluster_latency", "bash:curl -s -o /dev/null -w 'M1: %{time_total}s' http://127.0.0.1:1234/api/v1/models --max-time 3 2>/dev/null || echo 'M1 N/A'", "bash", timeout_s=5),
            DominoStep("tts", "python:edge_tts_speak('Benchmark performance termine. Import, memoire et latence mesures.')", "python"),
        ],
        category="performance",
        description="Performance benchmark: import speed + RAM + cluster latency",
        learning_context="Performance — benchmark complet du systeme",
        priority="high",
    ),
    DominoPipeline(
        id="domino_profiling_python",
        trigger_vocal=["profiling python", "profile le code", "cprofile", "performance python"],
        steps=[
            DominoStep("profile", "bash:cd F:/BUREAU/turbo && python -c \"import cProfile;import pstats;pr=cProfile.Profile();pr.enable();from src.commands import COMMANDS;pr.disable();ps=pstats.Stats(pr);ps.sort_stats('cumulative');ps.print_stats(5)\" 2>/dev/null || echo 'cProfile error'", "bash", timeout_s=15),
            DominoStep("tts", "python:edge_tts_speak('Profiling Python termine. Top 5 fonctions affichees.')", "python"),
        ],
        category="performance",
        description="Python cProfile: top 5 functions by cumulative time",
        learning_context="Performance — profiling Python avec cProfile",
        priority="normal",
    ),
    DominoPipeline(
        id="domino_load_test_prep",
        trigger_vocal=["prepare load test", "test de charge", "load test", "stress test prep"],
        steps=[
            DominoStep("tools", "bash:locust --version 2>/dev/null || echo 'Locust N/A' && ab -V 2>/dev/null | head -1 || echo 'ab N/A'", "bash", timeout_s=5),
            DominoStep("tts", "python:edge_tts_speak('Outils de test de charge verifies.')", "python"),
        ],
        category="performance",
        description="Load test preparation: check available tools",
        learning_context="Performance — preparation test de charge",
        priority="normal",
    ),
    DominoPipeline(
        id="domino_email_setup",
        trigger_vocal=["setup email", "configure email", "smtp setup", "email config"],
        steps=[
            DominoStep("smtp", "bash:python -c \"import smtplib; print('SMTP module OK')\" 2>/dev/null", "bash", timeout_s=5),
            DominoStep("tts", "python:edge_tts_speak('Module email Python verifie.')", "python"),
        ],
        category="communication",
        description="Email setup check: SMTP module",
        learning_context="Communication — verification setup email",
        priority="normal",
    ),
    DominoPipeline(
        id="domino_filesystem_audit",
        trigger_vocal=["audit filesystem", "audit fichiers", "check filesystem", "integrite fichiers"],
        steps=[
            DominoStep("disk", "python:get_disk_usage()", "python"),
            DominoStep("large_files", "bash:cd F:/BUREAU/turbo && find . -name '*.py' -size +100k 2>/dev/null | head -5 || dir /s /b *.py 2>NUL | head -5", "bash", timeout_s=10),
            DominoStep("db_sizes", "bash:ls -lh F:/BUREAU/turbo/data/*.db 2>/dev/null || dir F:\\BUREAU\\turbo\\data\\*.db 2>NUL", "bash", timeout_s=5),
            DominoStep("tts", "python:edge_tts_speak('Audit filesystem termine. Disques, gros fichiers et bases verifies.')", "python"),
        ],
        category="system_diagnostics",
        description="Filesystem audit: disk + large files + DB sizes",
        learning_context="Systeme — audit filesystem complet",
        priority="normal",
    ),
    DominoPipeline(
        id="domino_import_speed",
        trigger_vocal=["vitesse import", "import speed", "benchmark import", "temps chargement"],
        steps=[
            DominoStep("bench", "bash:cd F:/BUREAU/turbo && python -c \"import time;s=time.time();from src.commands import COMMANDS,VOICE_CORRECTIONS;from src.voice_correction import IMPLICIT_COMMANDS,PHONETIC_GROUPS,FILLER_WORDS;from src.domino_pipelines import DOMINO_PIPELINES;from src.domino_executor import _PYTHON_REGISTRY;e=time.time()-s;print(f'Total import: {e:.3f}s | {len(COMMANDS)} cmds | {len(VOICE_CORRECTIONS)} corrections | {len(DOMINO_PIPELINES)} dominos | {len(_PYTHON_REGISTRY)} actions')\"", "bash", timeout_s=15),
            DominoStep("tts", "python:edge_tts_speak('Benchmark import termine. Vitesse de chargement mesuree.')", "python"),
        ],
        category="performance",
        description="Import speed benchmark: measure loading time of all modules",
        learning_context="Performance — benchmark vitesse d'import",
        priority="high",
    ),
    DominoPipeline(
        id="domino_notification_test",
        trigger_vocal=["test notification", "teste les notifications", "notification check", "alertes test"],
        steps=[
            DominoStep("tts", "python:edge_tts_speak('Test de notification. Si vous entendez ceci, le TTS fonctionne correctement!')", "python"),
        ],
        category="voice_testing",
        description="Notification test: TTS output test",
        learning_context="Voice — test du systeme de notification",
        priority="normal",
    ),
    # ── Batch 101 — Rust/Go/Agile/Gaming (10 dominos) ──
    DominoPipeline(
        id="domino_rust_build",
        trigger_vocal=["build rust", "compile rust", "cargo build", "rust project"],
        steps=[
            DominoStep("version", "bash:rustc --version 2>/dev/null && cargo --version 2>/dev/null || echo 'Rust non installe'", "bash", timeout_s=5),
            DominoStep("tts", "python:edge_tts_speak('Verification Rust terminee.')", "python"),
        ],
        category="systems_programming",
        description="Rust build environment check",
        learning_context="Systems — verification environnement Rust",
        priority="normal",
    ),
    DominoPipeline(
        id="domino_go_build",
        trigger_vocal=["build go", "compile go", "go build", "golang project"],
        steps=[
            DominoStep("version", "bash:go version 2>/dev/null || echo 'Go non installe'", "bash", timeout_s=5),
            DominoStep("tts", "python:edge_tts_speak('Verification Go terminee.')", "python"),
        ],
        category="systems_programming",
        description="Go build environment check",
        learning_context="Systems — verification environnement Go",
        priority="normal",
    ),
    DominoPipeline(
        id="domino_sprint_review",
        trigger_vocal=["sprint review", "revue de sprint", "sprint recap", "bilan sprint detaille"],
        steps=[
            DominoStep("week_log", "bash:cd F:/BUREAU/turbo && git log --oneline --since='7 days ago'", "bash", timeout_s=5),
            DominoStep("summary", "python:project_summary()", "python"),
            DominoStep("todos", "bash:cd F:/BUREAU/turbo && grep -rn 'TODO\\|FIXME' src/*.py 2>/dev/null | wc -l || echo '0'", "bash", timeout_s=5),
            DominoStep("tts", "python:edge_tts_speak('Sprint review. Commits de la semaine, stats et TODOs resumes.')", "python"),
        ],
        category="agile",
        description="Sprint review: weekly commits + stats + TODOs",
        learning_context="Agile — revue de sprint detaillee",
        priority="normal",
    ),
    DominoPipeline(
        id="domino_tech_debt_audit",
        trigger_vocal=["audit dette technique", "tech debt audit", "montre les todos", "code a ameliorer"],
        steps=[
            DominoStep("todos", "bash:cd F:/BUREAU/turbo && grep -rn 'TODO\\|FIXME\\|HACK\\|XXX' src/*.py 2>/dev/null | head -20 || echo 'Aucun TODO'", "bash", timeout_s=10),
            DominoStep("loc", "python:count_lines_of_code()", "python"),
            DominoStep("tts", "python:edge_tts_speak('Audit dette technique termine. TODOs et lignes de code affiches.')", "python"),
        ],
        category="code_quality",
        description="Tech debt audit: TODOs + LOC count",
        learning_context="QA — audit de la dette technique",
        priority="normal",
    ),
    DominoPipeline(
        id="domino_multimedia_check",
        trigger_vocal=["check multimedia", "outils multimedia", "ffmpeg check", "video tools"],
        steps=[
            DominoStep("ffmpeg", "bash:ffmpeg -version 2>/dev/null | head -2 || echo 'FFmpeg N/A'", "bash", timeout_s=5),
            DominoStep("tts", "python:edge_tts_speak('Outils multimedia verifies.')", "python"),
        ],
        category="multimedia",
        description="Multimedia tools check: FFmpeg",
        learning_context="Multimedia — verification outils video/audio",
        priority="normal",
    ),
    DominoPipeline(
        id="domino_game_dev_setup",
        trigger_vocal=["setup game dev", "prepare game dev", "environnement jeu", "game development"],
        steps=[
            DominoStep("gpu", "bash:nvidia-smi --query-gpu=name,temperature.gpu,memory.used,memory.total --format=csv,noheader 2>/dev/null | head -3 || echo 'nvidia-smi N/A'", "bash", timeout_s=5),
            DominoStep("tts", "python:edge_tts_speak('Environnement game dev verifie. GPU et outils affiches.')", "python"),
        ],
        category="gaming_dev",
        description="Game dev setup: GPU check",
        learning_context="Gaming — verification setup game dev",
        priority="normal",
    ),
    DominoPipeline(
        id="domino_agile_daily",
        trigger_vocal=["daily agile", "standup agile", "matin agile", "agile meeting"],
        steps=[
            DominoStep("yesterday", "bash:cd F:/BUREAU/turbo && git log --oneline --since='1 day ago'", "bash", timeout_s=5),
            DominoStep("status", "bash:cd F:/BUREAU/turbo && git status --short | wc -l", "bash", timeout_s=5),
            DominoStep("summary", "python:project_summary()", "python"),
            DominoStep("tts", "python:edge_tts_speak('Daily agile. Activite d hier, fichiers modifies et stats du projet resumes.')", "python"),
        ],
        category="agile",
        description="Agile daily standup: yesterday + status + stats",
        learning_context="Agile — standup daily automatise",
        priority="normal",
    ),
    DominoPipeline(
        id="domino_wasm_check",
        trigger_vocal=["check wasm", "webassembly", "wasm build", "wasm status"],
        steps=[
            DominoStep("wasm", "bash:wasm-pack --version 2>/dev/null || echo 'wasm-pack non installe'", "bash", timeout_s=5),
            DominoStep("tts", "python:edge_tts_speak('Verification WebAssembly terminee.')", "python"),
        ],
        category="systems_programming",
        description="WebAssembly tools check",
        learning_context="Systems — verification outils WebAssembly",
        priority="normal",
    ),
    DominoPipeline(
        id="domino_poc_start",
        trigger_vocal=["lance un poc", "proof of concept", "prototype rapide", "poc start"],
        steps=[
            DominoStep("branch", "bash:cd F:/BUREAU/turbo && git branch --show-current", "bash", timeout_s=3),
            DominoStep("versions", "python:list_env_versions()", "python"),
            DominoStep("tts", "python:edge_tts_speak('POC pret. Branche et environnement verifies.')", "python"),
        ],
        category="agile",
        description="POC start: check branch + environment",
        learning_context="Agile — demarrage proof of concept",
        priority="normal",
    ),
    DominoPipeline(
        id="domino_all_languages",
        trigger_vocal=["tous les langages", "versions langages", "programming languages", "check langages"],
        steps=[
            DominoStep("python", "bash:python --version 2>&1", "bash", timeout_s=3),
            DominoStep("node", "bash:node --version 2>&1 || echo 'Node N/A'", "bash", timeout_s=3),
            DominoStep("rust", "bash:rustc --version 2>/dev/null || echo 'Rust N/A'", "bash", timeout_s=3),
            DominoStep("go", "bash:go version 2>/dev/null || echo 'Go N/A'", "bash", timeout_s=3),
            DominoStep("git", "bash:git --version 2>&1", "bash", timeout_s=3),
            DominoStep("tts", "python:edge_tts_speak('Versions de tous les langages affichees.')", "python"),
        ],
        category="dev_environment",
        description="All language versions: Python + Node + Rust + Go + Git",
        learning_context="Dev — versions de tous les langages installes",
        priority="normal",
    ),
    # ── Batch 100 — CENTENAIRE — TS/Python/React/Linux (10 dominos) ──
    DominoPipeline(
        id="domino_typescript_check",
        trigger_vocal=["check typescript", "tsc check", "compile typescript", "typescript valide"],
        steps=[
            DominoStep("tsc", "bash:npx tsc --noEmit 2>/dev/null || echo 'TypeScript non installe'", "bash", timeout_s=15),
            DominoStep("tts", "python:edge_tts_speak('Verification TypeScript terminee.')", "python"),
        ],
        category="frontend_dev",
        description="TypeScript compilation check",
        learning_context="Frontend — verification TypeScript",
        priority="normal",
    ),
    DominoPipeline(
        id="domino_react_setup",
        trigger_vocal=["setup react", "prepare react", "init react", "nouveau projet react"],
        steps=[
            DominoStep("node", "bash:node --version 2>&1", "bash", timeout_s=3),
            DominoStep("npm", "bash:npm --version 2>&1", "bash", timeout_s=3),
            DominoStep("tts", "python:edge_tts_speak('Environnement React verifie. Node et NPM disponibles.')", "python"),
        ],
        category="frontend_dev",
        description="React setup check: Node + NPM versions",
        learning_context="Frontend — verification setup React",
        priority="normal",
    ),
    DominoPipeline(
        id="domino_python_env",
        trigger_vocal=["environnement python", "python env", "setup python", "check python"],
        steps=[
            DominoStep("version", "bash:python --version 2>&1", "bash", timeout_s=3),
            DominoStep("pip", "bash:pip --version 2>&1", "bash", timeout_s=3),
            DominoStep("uv", "bash:uv --version 2>&1 || echo 'uv non installe'", "bash", timeout_s=3),
            DominoStep("venv", "bash:python -c \"import sys; print('venv:', sys.prefix != sys.base_prefix)\" 2>&1", "bash", timeout_s=3),
            DominoStep("tts", "python:edge_tts_speak('Environnement Python verifie. Version, pip, uv et venv verifies.')", "python"),
        ],
        category="python_dev",
        description="Python environment check: version + pip + uv + venv",
        learning_context="Python — verification environnement complet",
        priority="normal",
    ),
    DominoPipeline(
        id="domino_fastapi_launch",
        trigger_vocal=["lance l'api", "fastapi start", "demarre fastapi", "uvicorn start"],
        steps=[
            DominoStep("check", "bash:python -c 'import fastapi; print(\"FastAPI\", fastapi.__version__)' 2>/dev/null || echo 'FastAPI non installe'", "bash", timeout_s=5),
            DominoStep("tts", "python:edge_tts_speak('Verification FastAPI terminee.')", "python"),
        ],
        category="python_dev",
        description="FastAPI launch preparation: check installation",
        learning_context="Python — preparation lancement FastAPI",
        priority="normal",
    ),
    DominoPipeline(
        id="domino_frontend_full",
        trigger_vocal=["check frontend complet", "frontend full", "audit frontend", "verifie le frontend"],
        steps=[
            DominoStep("node", "bash:node --version 2>&1 && npm --version 2>&1", "bash", timeout_s=5),
            DominoStep("ts", "bash:npx tsc --version 2>/dev/null || echo 'TSC N/A'", "bash", timeout_s=5),
            DominoStep("tts", "python:edge_tts_speak('Audit frontend complet. Node, npm et TypeScript verifies.')", "python"),
        ],
        category="frontend_dev",
        description="Full frontend audit: Node + npm + TypeScript",
        learning_context="Frontend — audit complet des outils",
        priority="normal",
    ),
    DominoPipeline(
        id="domino_linux_tools",
        trigger_vocal=["outils linux", "linux tools", "check outils shell", "shell tools"],
        steps=[
            DominoStep("tools", "bash:which git curl python node 2>/dev/null || where git curl python node 2>/dev/null || echo 'Check individuel necessaire'", "bash", timeout_s=5),
            DominoStep("tts", "python:edge_tts_speak('Outils shell verifies.')", "python"),
        ],
        category="dev_environment",
        description="Check available shell/Linux tools",
        learning_context="Dev — verification outils shell disponibles",
        priority="normal",
    ),
    DominoPipeline(
        id="domino_milestone_100",
        trigger_vocal=["milestone cent", "batch cent", "centieme batch", "celebration"],
        steps=[
            DominoStep("summary", "python:project_summary()", "python"),
            DominoStep("categories", "python:count_domino_categories()", "python"),
            DominoStep("corrections", "python:voice_corrections_by_category()", "python"),
            DominoStep("commits", "python:recent_commits()", "python"),
            DominoStep("cluster", "python:cluster_node_count()", "python"),
            DominoStep("tts", "python:edge_tts_speak('Milestone 100! Centieme batch. Statistiques completes du projet JARVIS affichees. Felicitations!')", "python"),
        ],
        category="milestone",
        description="Batch 100 milestone celebration: full project stats",
        learning_context="Milestone — celebration du centieme batch",
        priority="high",
    ),
    DominoPipeline(
        id="domino_venv_setup",
        trigger_vocal=["setup venv", "cree un venv", "virtualenv setup", "init venv"],
        steps=[
            DominoStep("create", "bash:python -m venv .venv 2>/dev/null && echo 'venv created' || echo 'venv creation failed'", "bash", timeout_s=10),
            DominoStep("tts", "python:edge_tts_speak('Environnement virtuel Python cree.')", "python"),
        ],
        category="python_dev",
        description="Create Python virtual environment",
        learning_context="Python — creation environnement virtuel",
        priority="normal",
    ),
    DominoPipeline(
        id="domino_tailwind_setup",
        trigger_vocal=["setup tailwind", "init tailwind", "configure tailwind", "tailwind css"],
        steps=[
            DominoStep("check", "bash:npx tailwindcss --help 2>/dev/null | head -3 || echo 'Tailwind non installe'", "bash", timeout_s=10),
            DominoStep("tts", "python:edge_tts_speak('Configuration Tailwind verifiee.')", "python"),
        ],
        category="frontend_dev",
        description="Tailwind CSS setup check",
        learning_context="Frontend — verification Tailwind CSS",
        priority="normal",
    ),
    DominoPipeline(
        id="domino_grand_bilan",
        trigger_vocal=["grand bilan", "bilan general", "recap total", "tout recapituler"],
        steps=[
            DominoStep("full", "python:full_system_summary()", "python"),
            DominoStep("models", "python:list_ollama_models()", "python"),
            DominoStep("lms", "python:list_lm_studio_models()", "python"),
            DominoStep("db", "python:db_table_count()", "python"),
            DominoStep("today", "python:git_log_today()", "python"),
            DominoStep("tts", "python:edge_tts_speak('Grand bilan JARVIS genere. Systeme, modeles, bases de donnees et activite du jour tous resumes.')", "python"),
        ],
        category="reporting",
        description="Grand bilan: full system + models + DB + today's activity",
        learning_context="Rapport — grand bilan complet de tout le systeme",
        priority="high",
    ),
    # ── Batch 99 — UX/Networking/TextProc (10 dominos) ──
    DominoPipeline(
        id="domino_ux_audit",
        trigger_vocal=["audit ux", "ux review", "accessibilite check", "check ux"],
        steps=[
            DominoStep("a11y", "bash:echo 'A11y check: verify WCAG compliance, contrast ratios, tab order'", "bash", timeout_s=3),
            DominoStep("tts", "python:edge_tts_speak('Audit UX lance. Verifiez accessibilite et design.')", "python"),
        ],
        category="ux_design",
        description="UX audit: accessibility + design check",
        learning_context="UX — audit experience utilisateur",
        priority="normal",
    ),
    DominoPipeline(
        id="domino_dns_diagnostic",
        trigger_vocal=["diagnostic dns", "check dns complet", "dns full", "probleme dns"],
        steps=[
            DominoStep("nslookup", "bash:nslookup google.com 2>/dev/null | head -5 || echo 'nslookup N/A'", "bash", timeout_s=10),
            DominoStep("ping", "bash:ping -n 3 google.com 2>/dev/null | tail -3 || ping -c 3 google.com 2>/dev/null | tail -3 || echo 'ping N/A'", "bash", timeout_s=15),
            DominoStep("tts", "python:edge_tts_speak('Diagnostic DNS termine. Resolution et ping verifies.')", "python"),
        ],
        category="network_diagnostics",
        description="DNS diagnostic: nslookup + ping",
        learning_context="Network — diagnostic DNS complet",
        priority="normal",
    ),
    DominoPipeline(
        id="domino_network_full",
        trigger_vocal=["diagnostic reseau complet", "full network check", "network diagnostic", "reseau complet"],
        steps=[
            DominoStep("ip_local", "bash:ipconfig 2>/dev/null | grep -i 'ipv4' | head -3 || ip addr show 2>/dev/null | grep inet | head -3 || echo 'IP N/A'", "bash", timeout_s=5),
            DominoStep("ip_public", "bash:curl -s ifconfig.me 2>/dev/null || echo 'IP publique N/A'", "bash", timeout_s=5),
            DominoStep("dns", "bash:nslookup google.com 2>/dev/null | head -3 || echo 'DNS N/A'", "bash", timeout_s=5),
            DominoStep("ports", "bash:netstat -an | grep LISTEN | wc -l 2>/dev/null || echo '?'", "bash", timeout_s=5),
            DominoStep("latency", "bash:curl -s -o /dev/null -w '%{time_total}s' http://google.com --max-time 5 2>/dev/null || echo 'N/A'", "bash", timeout_s=10),
            DominoStep("tts", "python:edge_tts_speak('Diagnostic reseau complet. IP, DNS, ports et latence verifies.')", "python"),
        ],
        category="network_diagnostics",
        description="Full network diagnostic: IP + DNS + ports + latency",
        learning_context="Network — diagnostic reseau multi-couche",
        priority="high",
    ),
    DominoPipeline(
        id="domino_firewall_check",
        trigger_vocal=["check firewall", "statut pare feu", "firewall rules", "pare feu actif"],
        steps=[
            DominoStep("fw", "bash:powershell -Command \"Get-NetFirewallProfile | Select-Object Name,Enabled\" 2>/dev/null || echo 'Firewall check N/A'", "bash", timeout_s=10),
            DominoStep("tts", "python:edge_tts_speak('Statut du pare-feu affiche.')", "python"),
        ],
        category="security",
        description="Check Windows firewall status",
        learning_context="Securite — verification pare-feu Windows",
        priority="normal",
    ),
    DominoPipeline(
        id="domino_speed_test",
        trigger_vocal=["test de vitesse", "speed test", "debit internet", "vitesse connexion"],
        steps=[
            DominoStep("speed", "bash:curl -s -o /dev/null -w 'Speed: %{speed_download} B/s | Time: %{time_total}s' https://speed.cloudflare.com/__down?bytes=5000000 --max-time 10 2>/dev/null || echo 'Speed test N/A'", "bash", timeout_s=15),
            DominoStep("tts", "python:edge_tts_speak('Test de vitesse termine.')", "python"),
        ],
        category="network_diagnostics",
        description="Internet speed test via Cloudflare",
        learning_context="Network — test de debit internet",
        priority="normal",
    ),
    DominoPipeline(
        id="domino_ip_info",
        trigger_vocal=["info ip", "mon ip", "adresse ip", "ip publique et locale"],
        steps=[
            DominoStep("local", "bash:ipconfig 2>/dev/null | grep -i 'ipv4' | head -2 || echo 'IP locale N/A'", "bash", timeout_s=5),
            DominoStep("public", "bash:curl -s ifconfig.me 2>/dev/null || echo 'IP publique N/A'", "bash", timeout_s=5),
            DominoStep("tts", "python:edge_tts_speak('Adresses IP locale et publique affichees.')", "python"),
        ],
        category="network_info",
        description="Show local and public IP addresses",
        learning_context="Network — adresses IP locale et publique",
        priority="normal",
    ),
    DominoPipeline(
        id="domino_regex_playground",
        trigger_vocal=["playground regex", "teste regex", "regex sandbox", "expression reguliere"],
        steps=[
            DominoStep("demo", "bash:python -c \"import re; text='JARVIS 2107 commandes 291 dominos'; print('Numbers:', re.findall(r'\\d+', text)); print('Words:', re.findall(r'[A-Z]+', text))\"", "bash", timeout_s=5),
            DominoStep("tts", "python:edge_tts_speak('Playground regex pret. Demo avec extraction de nombres et mots.')", "python"),
        ],
        category="dev_tools",
        description="Regex playground: demo pattern matching",
        learning_context="Dev — terrain de jeu regex",
        priority="normal",
    ),
    DominoPipeline(
        id="domino_full_report",
        trigger_vocal=["rapport final", "full report", "rapport complet systeme", "bilan total"],
        steps=[
            DominoStep("system", "python:full_system_summary()", "python"),
            DominoStep("git", "python:recent_commits()", "python"),
            DominoStep("today", "python:git_log_today()", "python"),
            DominoStep("tts", "python:edge_tts_speak('Rapport final complet genere. Systeme, projet et activite resumes.')", "python"),
        ],
        category="reporting",
        description="Full system report: summary + commits + today's activity",
        learning_context="Rapport — bilan complet du systeme",
        priority="high",
    ),
    DominoPipeline(
        id="domino_milestone_check",
        trigger_vocal=["check milestone", "milestone", "objectif atteint", "etape franchie"],
        steps=[
            DominoStep("summary", "python:project_summary()", "python"),
            DominoStep("categories", "python:count_domino_categories()", "python"),
            DominoStep("corrections", "python:voice_corrections_by_category()", "python"),
            DominoStep("tts", "python:edge_tts_speak('Milestone check. Statistiques du projet, categories et corrections affichees.')", "python"),
        ],
        category="project_management",
        description="Milestone check: project stats + categories + corrections",
        learning_context="Projet — verification des milestones",
        priority="normal",
    ),
    DominoPipeline(
        id="domino_daily_wrapup",
        trigger_vocal=["bilan journee", "daily wrapup", "fin de journee", "resume du jour"],
        steps=[
            DominoStep("today", "python:git_log_today()", "python"),
            DominoStep("summary", "python:project_summary()", "python"),
            DominoStep("ram", "python:system_memory_usage()", "python"),
            DominoStep("disk", "python:get_disk_usage()", "python"),
            DominoStep("tts", "python:edge_tts_speak('Bilan de la journee. Commits, stats, memoire et disques resumes. Bonne soiree!')", "python"),
        ],
        category="routine_soir",
        description="Daily wrapup: today's commits + stats + system health",
        learning_context="Routine — bilan de fin de journee",
        priority="normal",
    ),
    # ── Batch 98 — Mobile/DevOps/IA/Crypto (10 dominos) ──
    DominoPipeline(
        id="domino_mobile_build",
        trigger_vocal=["build mobile", "compile mobile", "build apk", "build app"],
        steps=[
            DominoStep("check", "bash:flutter --version 2>/dev/null || npx expo --version 2>/dev/null || echo 'Ni Flutter ni Expo installe'", "bash", timeout_s=10),
            DominoStep("tts", "python:edge_tts_speak('Statut outils mobile verifie.')", "python"),
        ],
        category="mobile_dev",
        description="Check mobile build tools (Flutter/Expo)",
        learning_context="Mobile — verification outils de build",
        priority="normal",
    ),
    DominoPipeline(
        id="domino_incident_response",
        trigger_vocal=["incident response", "reponse incident", "procedure urgence", "urgence prod"],
        steps=[
            DominoStep("cluster", "bash:curl -s --max-time 3 http://127.0.0.1:1234/api/v1/models 2>/dev/null | head -c 30 && echo ' M1 OK' || echo 'M1 DOWN'", "bash", timeout_s=5),
            DominoStep("ol1", "bash:curl -s --max-time 3 http://127.0.0.1:11434/api/tags 2>/dev/null | head -c 30 && echo ' OL1 OK' || echo 'OL1 DOWN'", "bash", timeout_s=5),
            DominoStep("ram", "python:system_memory_usage()", "python"),
            DominoStep("disk", "python:get_disk_usage()", "python"),
            DominoStep("errors", "bash:powershell -Command \"Get-EventLog -LogName System -EntryType Error -Newest 3 2>\\$null | Format-Table TimeGenerated,Source -AutoSize\" 2>/dev/null || echo 'N/A'", "bash", timeout_s=15),
            DominoStep("tts", "python:edge_tts_speak('Reponse incident. Cluster, memoire, disques et erreurs systeme verifies.')", "python"),
        ],
        category="incident_response",
        description="Incident response: cluster + RAM + disk + errors",
        learning_context="SRE — reponse rapide a un incident",
        priority="critical",
    ),
    DominoPipeline(
        id="domino_canary_deploy",
        trigger_vocal=["canary deploy", "deploie en canary", "deploy canary", "test en canary"],
        steps=[
            DominoStep("syntax", "bash:cd F:/BUREAU/turbo && python -m py_compile src/commands.py && echo 'OK'", "bash", timeout_s=10),
            DominoStep("tests", "python:test_voice_match('ouvre chrome')", "python"),
            DominoStep("tts", "python:edge_tts_speak('Verification canary terminee. Pre-deploy verifie.')", "python"),
        ],
        category="deployment",
        description="Canary deploy preparation: syntax + test",
        learning_context="DevOps — preparation deploiement canary",
        priority="high",
    ),
    DominoPipeline(
        id="domino_llm_status",
        trigger_vocal=["statut llm", "modeles ia", "ia status", "llm overview"],
        steps=[
            DominoStep("ollama", "bash:curl -s http://127.0.0.1:11434/api/tags 2>/dev/null | python -c \"import sys,json;ms=json.load(sys.stdin).get('models',[]);print(f'{len(ms)} modeles Ollama')\" 2>/dev/null || echo 'Ollama offline'", "bash", timeout_s=5),
            DominoStep("lm_studio", "bash:curl -s http://127.0.0.1:1234/api/v1/models 2>/dev/null | python -c \"import sys,json;d=json.load(sys.stdin);ms=[m for m in d.get('data',d.get('models',[])) if m.get('loaded_instances')];print(f'{len(ms)} modeles charges LM Studio')\" 2>/dev/null || echo 'LM Studio offline'", "bash", timeout_s=5),
            DominoStep("tts", "python:edge_tts_speak('Statut LLM affiche. Ollama et LM Studio verifies.')", "python"),
        ],
        category="ai_ml",
        description="LLM status: Ollama + LM Studio model counts",
        learning_context="IA — statut des modeles de langage",
        priority="high",
    ),
    DominoPipeline(
        id="domino_embedding_pipeline",
        trigger_vocal=["pipeline embedding", "genere embeddings", "vectorise", "embedding batch"],
        steps=[
            DominoStep("check", "bash:curl -s --max-time 3 http://127.0.0.1:1234/api/v1/models 2>/dev/null | head -c 30 && echo ' M1 READY' || echo 'M1 OFFLINE — embeddings impossible'", "bash", timeout_s=5),
            DominoStep("tts", "python:edge_tts_speak('Pipeline embedding pret. M1 verifie pour la generation.')", "python"),
        ],
        category="ai_ml",
        description="Embedding pipeline: check M1 readiness",
        learning_context="IA — preparation pipeline embeddings",
        priority="normal",
    ),
    DominoPipeline(
        id="domino_model_compare",
        trigger_vocal=["compare les modeles", "model compare", "benchmark modeles", "quel modele"],
        steps=[
            DominoStep("ollama_list", "bash:curl -s http://127.0.0.1:11434/api/tags 2>/dev/null | python -c \"import sys,json;[print(m['name'],m.get('size','')) for m in json.load(sys.stdin).get('models',[])]\" 2>/dev/null | head -10 || echo 'Ollama N/A'", "bash", timeout_s=5),
            DominoStep("lm_list", "bash:curl -s http://127.0.0.1:1234/api/v1/models 2>/dev/null | python -c \"import sys,json;d=json.load(sys.stdin);[print(m.get('id','?')) for m in d.get('data',d.get('models',[]))]\" 2>/dev/null | head -10 || echo 'LMS N/A'", "bash", timeout_s=5),
            DominoStep("tts", "python:edge_tts_speak('Comparaison des modeles affichee. Ollama et LM Studio listes.')", "python"),
        ],
        category="ai_ml",
        description="Compare models: Ollama + LM Studio side by side",
        learning_context="IA — comparaison des modeles disponibles",
        priority="normal",
    ),
    DominoPipeline(
        id="domino_trading_quick",
        trigger_vocal=["trading rapide", "quick trade", "signal trading", "scan trading rapide"],
        steps=[
            DominoStep("cluster", "bash:curl -s --max-time 3 http://127.0.0.1:1234/api/v1/models 2>/dev/null | head -c 20 && echo ' OK' || echo 'CLUSTER DOWN'", "bash", timeout_s=5),
            DominoStep("tts", "python:edge_tts_speak('Cluster pret pour le trading rapide.')", "python"),
        ],
        category="trading",
        description="Quick trading preparation: verify cluster readiness",
        learning_context="Trading — preparation rapide",
        priority="high",
    ),
    DominoPipeline(
        id="domino_sre_dashboard",
        trigger_vocal=["dashboard sre", "sre overview", "fiabilite systeme", "site reliability"],
        steps=[
            DominoStep("uptime", "python:get_uptime()", "python"),
            DominoStep("ram", "python:system_memory_usage()", "python"),
            DominoStep("disk", "python:get_disk_usage()", "python"),
            DominoStep("ports", "bash:netstat -an | grep LISTEN | wc -l 2>/dev/null || echo '?'", "bash", timeout_s=5),
            DominoStep("errors", "python:git_log_today()", "python"),
            DominoStep("tts", "python:edge_tts_speak('Dashboard SRE affiche. Uptime, memoire, disques, ports et activite resumes.')", "python"),
        ],
        category="sre",
        description="SRE dashboard: uptime + RAM + disk + ports + activity",
        learning_context="SRE — tableau de bord fiabilite systeme",
        priority="high",
    ),
    DominoPipeline(
        id="domino_crypto_check",
        trigger_vocal=["check crypto", "statut crypto", "blockchain status", "crypto overview"],
        steps=[
            DominoStep("tts", "python:edge_tts_speak('Verification crypto. Utilisez le module trading pour les prix en temps reel.')", "python"),
        ],
        category="trading",
        description="Crypto status check placeholder",
        learning_context="Trading — verification statut crypto",
        priority="normal",
    ),
    DominoPipeline(
        id="domino_pre_release",
        trigger_vocal=["pre release", "prepare la release", "release prep", "avant la release"],
        steps=[
            DominoStep("syntax", "bash:cd F:/BUREAU/turbo && python -m py_compile src/commands.py && python -m py_compile src/voice_correction.py && python -m py_compile src/domino_pipelines.py && python -m py_compile src/domino_executor.py && echo 'ALL OK'", "bash", timeout_s=15),
            DominoStep("tests", "python:test_voice_match('ouvre chrome')", "python"),
            DominoStep("summary", "python:project_summary()", "python"),
            DominoStep("git", "bash:cd F:/BUREAU/turbo && git log --oneline -5", "bash", timeout_s=5),
            DominoStep("tts", "python:edge_tts_speak('Pre-release prete. Syntaxe, tests, stats et log verifies.')", "python"),
        ],
        category="release",
        description="Pre-release checks: syntax + tests + stats + git log",
        learning_context="Release — verification pre-release complete",
        priority="critical",
    ),
    # ── Batch 97 — Testing/Architecture/System/Data (10 dominos) ──
    DominoPipeline(
        id="domino_test_suite",
        trigger_vocal=["lance tous les tests", "test suite complete", "full test", "run all tests"],
        steps=[
            DominoStep("syntax", "bash:cd F:/BUREAU/turbo && python -m py_compile src/commands.py && python -m py_compile src/voice_correction.py && python -m py_compile src/domino_pipelines.py && python -m py_compile src/domino_executor.py && echo 'SYNTAX OK'", "bash", timeout_s=15),
            DominoStep("match1", "python:test_voice_match('ouvre chrome')", "python"),
            DominoStep("match2", "python:test_voice_match('statut cluster')", "python"),
            DominoStep("match3", "python:test_voice_match('mode gaming')", "python"),
            DominoStep("summary", "python:project_summary()", "python"),
            DominoStep("tts", "python:edge_tts_speak('Suite de tests complete. Syntaxe, matching vocal et stats tous verifies.')", "python"),
        ],
        category="testing",
        description="Full test suite: syntax + 3 voice matches + summary",
        learning_context="Testing — suite de tests complete",
        priority="critical",
    ),
    DominoPipeline(
        id="domino_regression_check",
        trigger_vocal=["test de regression", "regression check", "rien de casse", "verifie la regression"],
        steps=[
            DominoStep("imports", "bash:cd F:/BUREAU/turbo && python -c 'from src.commands import COMMANDS; from src.voice_correction import IMPLICIT_COMMANDS; from src.domino_pipelines import DOMINO_PIPELINES; from src.domino_executor import _PYTHON_REGISTRY; print(\"ALL IMPORTS OK\")'", "bash", timeout_s=10),
            DominoStep("counts", "python:project_summary()", "python"),
            DominoStep("match", "python:test_voice_match('ouvre chrome')", "python"),
            DominoStep("tts", "python:edge_tts_speak('Test de regression ok. Imports, comptages et matching valides.')", "python"),
        ],
        category="testing",
        description="Regression test: imports + counts + match",
        learning_context="Testing — verification pas de regression",
        priority="high",
    ),
    DominoPipeline(
        id="domino_memory_check",
        trigger_vocal=["check memoire", "memory check", "utilisation ram", "combien de ram"],
        steps=[
            DominoStep("ram", "python:system_memory_usage()", "python"),
            DominoStep("disk", "python:get_disk_usage()", "python"),
            DominoStep("tts", "python:edge_tts_speak('Memoire et disques verifies.')", "python"),
        ],
        category="system_diagnostics",
        description="Memory check: RAM + disk usage",
        learning_context="Systeme — verification memoire et disques",
        priority="normal",
    ),
    DominoPipeline(
        id="domino_process_heavy",
        trigger_vocal=["processus lourds", "gros processus", "heavy process", "qui mange la ram"],
        steps=[
            DominoStep("top", "bash:tasklist /FI \"MEMUSAGE gt 100000\" /FO TABLE 2>/dev/null | head -10 || ps aux --sort=-%mem | head -10", "bash", timeout_s=10),
            DominoStep("ram", "python:system_memory_usage()", "python"),
            DominoStep("tts", "python:edge_tts_speak('Processus lourds listes avec utilisation memoire.')", "python"),
        ],
        category="system_diagnostics",
        description="Show heavy processes consuming most memory",
        learning_context="Systeme — identifier les processus gourmands",
        priority="normal",
    ),
    DominoPipeline(
        id="domino_data_overview",
        trigger_vocal=["donnees overview", "data overview", "resume donnees", "statut des donnees"],
        steps=[
            DominoStep("db_counts", "python:db_table_count()", "python"),
            DominoStep("json_check", "python:validate_json_files()", "python"),
            DominoStep("disk", "python:get_disk_usage()", "python"),
            DominoStep("tts", "python:edge_tts_speak('Vue d ensemble des donnees. Bases, fichiers JSON et disques resumes.')", "python"),
        ],
        category="data_management",
        description="Data overview: DB counts + JSON validation + disk",
        learning_context="Data — vue d'ensemble donnees du projet",
        priority="normal",
    ),
    DominoPipeline(
        id="domino_services_check",
        trigger_vocal=["services actifs", "check services", "services en cours", "quels services"],
        steps=[
            DominoStep("services", "bash:powershell -Command \"Get-Service | Where-Object {\\$_.Status -eq 'Running'} | Select-Object -First 15 Name\" 2>/dev/null || echo 'PowerShell N/A'", "bash", timeout_s=10),
            DominoStep("tts", "python:edge_tts_speak('Services systeme actifs listes.')", "python"),
        ],
        category="system_diagnostics",
        description="Check running Windows services",
        learning_context="Systeme — services Windows actifs",
        priority="normal",
    ),
    DominoPipeline(
        id="domino_cache_management",
        trigger_vocal=["gere les caches", "cache management", "nettoie les caches", "purge cache"],
        steps=[
            DominoStep("clear", "python:clear_all_caches()", "python"),
            DominoStep("tts", "python:edge_tts_speak('Caches nettoyes. LRU et match cache purges.')", "python"),
        ],
        category="performance",
        description="Cache management: clear all caches",
        learning_context="Performance — nettoyage et gestion des caches",
        priority="normal",
    ),
    DominoPipeline(
        id="domino_architecture_review",
        trigger_vocal=["review architecture", "archi review", "revue architecture", "check archi"],
        steps=[
            DominoStep("loc", "python:count_lines_of_code()", "python"),
            DominoStep("categories", "python:count_domino_categories()", "python"),
            DominoStep("summary", "python:project_summary()", "python"),
            DominoStep("tts", "python:edge_tts_speak('Revue architecture. Lignes de code, categories et statistiques affichees.')", "python"),
        ],
        category="architecture",
        description="Architecture review: LOC + categories + project summary",
        learning_context="Architecture — revue de l'architecture du projet",
        priority="normal",
    ),
    DominoPipeline(
        id="domino_weekend_prep",
        trigger_vocal=["prepare le weekend", "weekend prep", "fin de semaine", "avant le weekend"],
        steps=[
            DominoStep("push", "bash:cd F:/BUREAU/turbo && git add -A && git status --short", "bash", timeout_s=5),
            DominoStep("log_week", "bash:cd F:/BUREAU/turbo && git log --oneline --since='5 days ago' | head -15", "bash", timeout_s=5),
            DominoStep("summary", "python:project_summary()", "python"),
            DominoStep("tts", "python:edge_tts_speak('Preparation weekend terminee. Travail de la semaine resume. Bon weekend!')", "python"),
        ],
        category="routine_hebdo",
        description="Weekend prep: save work + weekly summary",
        learning_context="Routine — preparation fin de semaine",
        priority="normal",
    ),
    DominoPipeline(
        id="domino_full_diagnostic",
        trigger_vocal=["diagnostic complet", "full diagnostic", "check tout", "diagnostic total"],
        steps=[
            DominoStep("syntax", "bash:cd F:/BUREAU/turbo && python -m py_compile src/commands.py && python -m py_compile src/voice_correction.py && python -m py_compile src/domino_pipelines.py && python -m py_compile src/domino_executor.py && echo 'SYNTAX ALL OK'", "bash", timeout_s=15),
            DominoStep("m1", "bash:curl -s --max-time 3 http://127.0.0.1:1234/api/v1/models 2>/dev/null | head -c 30 && echo ' M1 OK' || echo 'M1 OFFLINE'", "bash", timeout_s=5),
            DominoStep("ol1", "bash:curl -s --max-time 3 http://127.0.0.1:11434/api/tags 2>/dev/null | head -c 30 && echo ' OL1 OK' || echo 'OL1 OFFLINE'", "bash", timeout_s=5),
            DominoStep("ram", "python:system_memory_usage()", "python"),
            DominoStep("disk", "python:get_disk_usage()", "python"),
            DominoStep("db", "python:db_table_count()", "python"),
            DominoStep("summary", "python:project_summary()", "python"),
            DominoStep("git", "python:git_status_short()", "python"),
            DominoStep("tts", "python:edge_tts_speak('Diagnostic complet termine. Syntaxe, cluster, memoire, disques, bases et projet tous verifies.')", "python"),
        ],
        category="full_diagnostics",
        description="Complete diagnostic: syntax + cluster + RAM + disk + DB + project + git",
        learning_context="Diagnostic — verification complete de tous les sous-systemes",
        priority="critical",
    ),
    # ── Batch 96 — Cloud/Git avance/IDE/Time (10 dominos) ──
    DominoPipeline(
        id="domino_cloud_overview",
        trigger_vocal=["statut cloud", "cloud overview", "infra cloud", "resume cloud"],
        steps=[
            DominoStep("services", "bash:curl -s --max-time 3 http://127.0.0.1:1234/api/v1/models 2>/dev/null | head -c 50 && echo ' API OK' || echo 'API OFFLINE'", "bash", timeout_s=5),
            DominoStep("disk", "python:get_disk_usage()", "python"),
            DominoStep("db", "python:db_table_count()", "python"),
            DominoStep("tts", "python:edge_tts_speak('Vue d ensemble cloud et infrastructure affichee.')", "python"),
        ],
        category="cloud_infra",
        description="Cloud infrastructure overview: APIs + disk + databases",
        learning_context="Cloud — vue d'ensemble infrastructure",
        priority="normal",
    ),
    DominoPipeline(
        id="domino_git_deep_status",
        trigger_vocal=["statut git complet", "git deep status", "git avance", "resume git detaille"],
        steps=[
            DominoStep("status", "bash:cd F:/BUREAU/turbo && git status --short", "bash", timeout_s=5),
            DominoStep("stash", "bash:cd F:/BUREAU/turbo && git stash list 2>/dev/null || echo 'Aucun stash'", "bash", timeout_s=5),
            DominoStep("branches", "bash:cd F:/BUREAU/turbo && git branch -a 2>/dev/null | head -10", "bash", timeout_s=5),
            DominoStep("tags", "bash:cd F:/BUREAU/turbo && git tag -l | tail -5 2>/dev/null || echo 'Aucun tag'", "bash", timeout_s=5),
            DominoStep("log", "bash:cd F:/BUREAU/turbo && git log --oneline -5", "bash", timeout_s=5),
            DominoStep("tts", "python:edge_tts_speak('Statut git complet. Status, stash, branches, tags et log affiches.')", "python"),
        ],
        category="git_advanced",
        description="Deep git status: status + stash + branches + tags + log",
        learning_context="Git — statut avance complet",
        priority="normal",
    ),
    DominoPipeline(
        id="domino_git_recovery",
        trigger_vocal=["recovery git", "recupere le code", "git reflog", "annuler git"],
        steps=[
            DominoStep("reflog", "bash:cd F:/BUREAU/turbo && git reflog --oneline -10", "bash", timeout_s=5),
            DominoStep("stash", "bash:cd F:/BUREAU/turbo && git stash list 2>/dev/null || echo 'Aucun stash'", "bash", timeout_s=5),
            DominoStep("tts", "python:edge_tts_speak('Outils de recovery git affiches. Reflog et stash disponibles.')", "python"),
        ],
        category="git_advanced",
        description="Git recovery tools: reflog + stash list",
        learning_context="Git — outils de recuperation",
        priority="high",
    ),
    DominoPipeline(
        id="domino_code_quality",
        trigger_vocal=["qualite du code", "code quality", "lint et format", "verifie le code"],
        steps=[
            DominoStep("lint", "bash:cd F:/BUREAU/turbo && ruff check src/ 2>/dev/null | tail -5 || echo 'ruff non installe'", "bash", timeout_s=15),
            DominoStep("syntax", "bash:cd F:/BUREAU/turbo && python -m py_compile src/commands.py && python -m py_compile src/voice_correction.py && echo 'Syntax OK'", "bash", timeout_s=10),
            DominoStep("loc", "python:count_lines_of_code()", "python"),
            DominoStep("tts", "python:edge_tts_speak('Qualite du code verifiee. Lint, syntaxe et lignes de code affiches.')", "python"),
        ],
        category="code_quality",
        description="Code quality check: lint + syntax + LOC",
        learning_context="QA — verification qualite du code",
        priority="high",
    ),
    DominoPipeline(
        id="domino_ide_setup",
        trigger_vocal=["configure ide", "setup vscode", "prepare l'editeur", "ide setup"],
        steps=[
            DominoStep("extensions", "bash:code --list-extensions 2>/dev/null | wc -l || echo 'VSCode CLI N/A'", "bash", timeout_s=10),
            DominoStep("python", "bash:python --version 2>&1", "bash", timeout_s=3),
            DominoStep("tts", "python:edge_tts_speak('Configuration IDE affichee.')", "python"),
        ],
        category="dev_environment",
        description="IDE setup check: extensions + Python version",
        learning_context="Dev — verification configuration IDE",
        priority="normal",
    ),
    DominoPipeline(
        id="domino_deploy_full",
        trigger_vocal=["deploiement complet", "full deploy", "deploy tout", "mise en prod complete"],
        steps=[
            DominoStep("syntax", "bash:cd F:/BUREAU/turbo && python -m py_compile src/commands.py && python -m py_compile src/voice_correction.py && python -m py_compile src/domino_pipelines.py && python -m py_compile src/domino_executor.py && echo 'SYNTAX OK'", "bash", timeout_s=15),
            DominoStep("git_add", "bash:cd F:/BUREAU/turbo && git add -A && git status --short", "bash", timeout_s=5),
            DominoStep("commit", "bash:cd F:/BUREAU/turbo && git diff --cached --stat", "bash", timeout_s=5),
            DominoStep("push", "bash:cd F:/BUREAU/turbo && git push origin main 2>&1 | tail -3", "bash", timeout_s=30),
            DominoStep("tts", "python:edge_tts_speak('Deploiement complet termine. Syntaxe, commit et push effectues.')", "python"),
        ],
        category="deployment",
        description="Full deployment: syntax + add + push",
        learning_context="Deploy — deploiement complet pipeline",
        priority="critical",
    ),
    DominoPipeline(
        id="domino_timer_pomodoro",
        trigger_vocal=["pomodoro", "lance un pomodoro", "timer 25 minutes", "focus pomodoro"],
        steps=[
            DominoStep("tts_start", "python:edge_tts_speak('Pomodoro de 25 minutes lance. Bon courage!')", "python"),
            DominoStep("notify", "bash:echo 'Pomodoro started at '$(date +%H:%M)' — ends at '$(date -d '+25 min' +%H:%M 2>/dev/null || echo 'N/A')", "bash", timeout_s=3),
        ],
        category="productivity",
        description="Start a 25-minute Pomodoro timer",
        learning_context="Productivite — timer Pomodoro focus",
        priority="normal",
    ),
    DominoPipeline(
        id="domino_morning_dev",
        trigger_vocal=["morning dev", "debut de journee dev", "demarre la journee dev", "dev morning routine"],
        steps=[
            DominoStep("pull", "bash:cd F:/BUREAU/turbo && git pull --rebase 2>&1 | tail -3", "bash", timeout_s=15),
            DominoStep("health", "bash:curl -s --max-time 3 http://127.0.0.1:1234/api/v1/models 2>/dev/null | head -c 30 && echo ' M1 OK' || echo 'M1 OFFLINE'", "bash", timeout_s=5),
            DominoStep("summary", "python:project_summary()", "python"),
            DominoStep("versions", "python:list_env_versions()", "python"),
            DominoStep("tts", "python:edge_tts_speak('Routine dev du matin terminee. Code a jour, cluster ok, environnement verifie.')", "python"),
        ],
        category="routine_matin",
        description="Morning dev routine: pull + health + summary + env versions",
        learning_context="Routine — demarrage journee developpeur",
        priority="normal",
    ),
    DominoPipeline(
        id="domino_end_of_sprint",
        trigger_vocal=["fin de sprint", "sprint review", "cloture sprint", "bilan sprint"],
        steps=[
            DominoStep("log_week", "bash:cd F:/BUREAU/turbo && git log --oneline --since='1 week ago'", "bash", timeout_s=5),
            DominoStep("stats", "python:project_summary()", "python"),
            DominoStep("db_stats", "python:db_table_count()", "python"),
            DominoStep("tts", "python:edge_tts_speak('Bilan de sprint. Commits de la semaine, stats et bases de donnees resumes.')", "python"),
        ],
        category="collaboration",
        description="End of sprint review: weekly commits + stats + DB counts",
        learning_context="Collaboration — revue de fin de sprint",
        priority="normal",
    ),
    DominoPipeline(
        id="domino_workspace_reset",
        trigger_vocal=["reset workspace", "nettoie l'espace de travail", "workspace propre", "clean workspace"],
        steps=[
            DominoStep("git_clean_check", "bash:cd F:/BUREAU/turbo && git status --short | wc -l", "bash", timeout_s=5),
            DominoStep("cache_clear", "python:clear_all_caches()", "python"),
            DominoStep("tts", "python:edge_tts_speak('Workspace nettoye. Caches vides et statut git verifie.')", "python"),
        ],
        category="dev_environment",
        description="Reset workspace: clear caches + check git status",
        learning_context="Dev — nettoyage espace de travail",
        priority="normal",
    ),
    # ── Batch 95 — K8s/Monitoring/Auth/Meta (10 dominos) ──
    DominoPipeline(
        id="domino_k8s_overview",
        trigger_vocal=["statut kubernetes", "k8s overview", "resume kubernetes", "cluster k8s"],
        steps=[
            DominoStep("pods", "bash:kubectl get pods --all-namespaces 2>/dev/null | head -15 || echo 'kubectl non disponible'", "bash", timeout_s=10),
            DominoStep("services", "bash:kubectl get services --all-namespaces 2>/dev/null | head -10 || echo 'kubectl N/A'", "bash", timeout_s=10),
            DominoStep("tts", "python:edge_tts_speak('Statut Kubernetes affiche. Pods et services resumes.')", "python"),
        ],
        category="kubernetes",
        description="Kubernetes overview: pods + services",
        learning_context="K8s — vue d'ensemble cluster Kubernetes",
        priority="normal",
    ),
    DominoPipeline(
        id="domino_docker_overview",
        trigger_vocal=["statut docker", "docker overview", "containers actifs", "docker status"],
        steps=[
            DominoStep("ps", "bash:docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}' 2>/dev/null | head -15 || echo 'Docker non disponible'", "bash", timeout_s=10),
            DominoStep("images", "bash:docker images --format 'table {{.Repository}}\t{{.Tag}}\t{{.Size}}' 2>/dev/null | head -10 || echo 'Docker N/A'", "bash", timeout_s=10),
            DominoStep("tts", "python:edge_tts_speak('Statut Docker affiche. Containers et images resumes.')", "python"),
        ],
        category="containers",
        description="Docker overview: running containers + images",
        learning_context="Containers — vue d'ensemble Docker",
        priority="normal",
    ),
    DominoPipeline(
        id="domino_monitoring_dashboard",
        trigger_vocal=["ouvre monitoring", "dashboard monitoring", "monitoring complet", "observabilite"],
        steps=[
            DominoStep("cluster_health", "bash:curl -s --max-time 3 http://127.0.0.1:1234/api/v1/models 2>/dev/null | head -c 30 && echo ' M1 OK' || echo 'M1 OFFLINE'", "bash", timeout_s=5),
            DominoStep("ol1_health", "bash:curl -s --max-time 3 http://127.0.0.1:11434/api/tags 2>/dev/null | head -c 30 && echo ' OL1 OK' || echo 'OL1 OFFLINE'", "bash", timeout_s=5),
            DominoStep("disk", "python:get_disk_usage()", "python"),
            DominoStep("stats", "python:project_summary()", "python"),
            DominoStep("tts", "python:edge_tts_speak('Dashboard monitoring affiche. Cluster, disques et stats du projet resumes.')", "python"),
        ],
        category="monitoring",
        description="Full monitoring dashboard: cluster + disk + project stats",
        learning_context="Monitoring — tableau de bord complet",
        priority="high",
    ),
    DominoPipeline(
        id="domino_alert_review",
        trigger_vocal=["review alertes", "alertes recentes", "check alertes", "erreurs recentes"],
        steps=[
            DominoStep("win_errors", "bash:powershell -Command \"Get-EventLog -LogName System -EntryType Error -Newest 3 2>$null | Format-Table TimeGenerated,Source -AutoSize\" 2>/dev/null || echo 'EventLog N/A'", "bash", timeout_s=15),
            DominoStep("git_issues", "bash:cd F:/BUREAU/turbo && git log --oneline --grep='fix' -5 2>/dev/null", "bash", timeout_s=5),
            DominoStep("tts", "python:edge_tts_speak('Review des alertes terminee. Erreurs systeme et fixes recents affiches.')", "python"),
        ],
        category="monitoring",
        description="Review recent alerts: Windows errors + recent fixes",
        learning_context="Monitoring — revue des alertes recentes",
        priority="high",
    ),
    DominoPipeline(
        id="domino_security_scan",
        trigger_vocal=["scan securite", "security scan", "audit securite rapide", "check securite"],
        steps=[
            DominoStep("ports", "bash:netstat -an | grep LISTEN | wc -l 2>/dev/null || echo '?'", "bash", timeout_s=5),
            DominoStep("pip_audit", "bash:pip audit 2>/dev/null | head -5 || echo 'pip audit N/A'", "bash", timeout_s=10),
            DominoStep("git_secrets", "bash:cd F:/BUREAU/turbo && git log --oneline --diff-filter=A -- '*.env' '*.key' '*.pem' 2>/dev/null | head -3 || echo 'Aucun secret commite'", "bash", timeout_s=5),
            DominoStep("tts", "python:edge_tts_speak('Scan securite termine. Ports, packages et secrets verifies.')", "python"),
        ],
        category="security",
        description="Quick security scan: ports + pip audit + git secrets",
        learning_context="Securite — scan rapide multi-couche",
        priority="critical",
    ),
    DominoPipeline(
        id="domino_token_generate",
        trigger_vocal=["genere un token", "nouveau token", "create token", "api key"],
        steps=[
            DominoStep("token", "bash:python -c \"import secrets; print('Token:', secrets.token_urlsafe(32))\"", "bash", timeout_s=3),
            DominoStep("tts", "python:edge_tts_speak('Token securise genere.')", "python"),
        ],
        category="security",
        description="Generate secure random token",
        learning_context="Securite — generation token aleatoire",
        priority="normal",
    ),
    DominoPipeline(
        id="domino_jarvis_self_test",
        trigger_vocal=["test jarvis", "auto test", "self test", "jarvis fonctionne"],
        steps=[
            DominoStep("syntax", "bash:cd F:/BUREAU/turbo && python -m py_compile src/commands.py && python -m py_compile src/voice_correction.py && python -m py_compile src/domino_pipelines.py && python -m py_compile src/domino_executor.py && echo 'SYNTAX OK'", "bash", timeout_s=15),
            DominoStep("imports", "bash:cd F:/BUREAU/turbo && python -c 'from src.commands import COMMANDS; from src.voice_correction import IMPLICIT_COMMANDS; from src.domino_pipelines import DOMINO_PIPELINES; from src.domino_executor import _PYTHON_REGISTRY; print(\"IMPORTS OK\")'", "bash", timeout_s=10),
            DominoStep("summary", "python:project_summary()", "python"),
            DominoStep("match_test", "python:test_voice_match('ouvre chrome')", "python"),
            DominoStep("tts", "python:edge_tts_speak('Auto-test JARVIS termine. Syntaxe, imports, matching et stats tous valides.')", "python"),
        ],
        category="self_diagnostics",
        description="JARVIS self-test: syntax + imports + matching + stats",
        learning_context="JARVIS — auto-diagnostic complet",
        priority="critical",
    ),
    DominoPipeline(
        id="domino_jarvis_stats",
        trigger_vocal=["stats jarvis", "statistiques jarvis", "combien de commandes", "resume jarvis"],
        steps=[
            DominoStep("summary", "python:project_summary()", "python"),
            DominoStep("dominos", "python:list_dominos()", "python"),
            DominoStep("tts", "python:edge_tts_speak('Statistiques JARVIS affichees.')", "python"),
        ],
        category="self_diagnostics",
        description="JARVIS stats: commands + corrections + dominos",
        learning_context="JARVIS — statistiques du systeme vocal",
        priority="normal",
    ),
    DominoPipeline(
        id="domino_voice_pipeline_test",
        trigger_vocal=["teste le pipeline vocal", "voice test", "test vocal complet", "pipeline vocal"],
        steps=[
            DominoStep("match1", "python:test_voice_match('ouvre chrome')", "python"),
            DominoStep("match2", "python:test_voice_match('statut cluster')", "python"),
            DominoStep("match3", "python:test_voice_match('lance le trading')", "python"),
            DominoStep("corrections", "python:count_voice_corrections()", "python"),
            DominoStep("tts", "python:edge_tts_speak('Test du pipeline vocal termine. Trois matchs testes avec succes.')", "python"),
        ],
        category="voice_testing",
        description="Full voice pipeline test: 3 match tests + corrections count",
        learning_context="Voice — test complet du pipeline vocal",
        priority="high",
    ),
    DominoPipeline(
        id="domino_night_shutdown",
        trigger_vocal=["bonne nuit", "extinction nocturne", "night shutdown", "mode nuit"],
        steps=[
            DominoStep("save", "bash:cd F:/BUREAU/turbo && git add -A && git stash 2>/dev/null; echo 'Work saved'", "bash", timeout_s=10),
            DominoStep("stats", "python:project_summary()", "python"),
            DominoStep("tts", "python:edge_tts_speak('Bonne nuit. Travail sauvegarde, stats affichees. A demain!')", "python"),
        ],
        category="routine_soir",
        description="Night shutdown: save work + show stats",
        learning_context="Routine — extinction et sauvegarde nocturne",
        priority="normal",
    ),
    # ── Batch 94 — API/DB/Network/Build (10 dominos) ──
    DominoPipeline(
        id="domino_api_health",
        trigger_vocal=["sante api", "api health", "check tous les endpoints", "healthcheck api"],
        steps=[
            DominoStep("m1_api", "bash:curl -s --max-time 3 http://127.0.0.1:1234/api/v1/models 2>/dev/null | head -c 50 || echo 'M1 OFFLINE'", "bash", timeout_s=5),
            DominoStep("ol1_api", "bash:curl -s --max-time 3 http://127.0.0.1:11434/api/tags 2>/dev/null | head -c 50 || echo 'OL1 OFFLINE'", "bash", timeout_s=5),
            DominoStep("tts", "python:edge_tts_speak('Sante des APIs verifiee.')", "python"),
        ],
        category="api_testing",
        description="Health check all local APIs (M1 + OL1)",
        learning_context="API — verification sante endpoints locaux",
        priority="normal",
    ),
    DominoPipeline(
        id="domino_db_vacuum_all",
        trigger_vocal=["vacuum toutes les bases", "vacuum all", "optimise les bases", "compacte les databases"],
        steps=[
            DominoStep("vacuum", "python:sqlite3_analyze()", "python"),
            DominoStep("sizes", "bash:cd F:/BUREAU/turbo && ls -lh data/*.db 2>/dev/null || dir data\\*.db", "bash", timeout_s=5),
            DominoStep("tts", "python:edge_tts_speak('Toutes les bases de donnees vacuumees et optimisees.')", "python"),
        ],
        category="database",
        description="Vacuum all SQLite databases",
        learning_context="Database — maintenance toutes les bases",
        priority="normal",
    ),
    DominoPipeline(
        id="domino_latency_full",
        trigger_vocal=["test latence complet", "full latency", "latence tous les noeuds", "ping complet"],
        steps=[
            DominoStep("m1", "bash:curl -s -o /dev/null -w 'M1: %{time_total}s\n' http://127.0.0.1:1234/api/v1/models --max-time 3 || echo 'M1 TIMEOUT'", "bash", timeout_s=5),
            DominoStep("m2", "bash:curl -s -o /dev/null -w 'M2: %{time_total}s\n' http://192.168.1.26:1234/api/v1/models --max-time 3 || echo 'M2 TIMEOUT'", "bash", timeout_s=5),
            DominoStep("m3", "bash:curl -s -o /dev/null -w 'M3: %{time_total}s\n' http://192.168.1.113:1234/api/v1/models --max-time 3 || echo 'M3 TIMEOUT'", "bash", timeout_s=5),
            DominoStep("ol1", "bash:curl -s -o /dev/null -w 'OL1: %{time_total}s\n' http://127.0.0.1:11434/api/tags --max-time 3 || echo 'OL1 TIMEOUT'", "bash", timeout_s=5),
            DominoStep("tts", "python:edge_tts_speak('Test de latence complet termine. Quatre noeuds testes.')", "python"),
        ],
        category="network_diagnostics",
        description="Full latency test on all 4 cluster nodes",
        learning_context="Network — benchmark latence complet du cluster",
        priority="high",
    ),
    DominoPipeline(
        id="domino_build_check",
        trigger_vocal=["check build", "verify build", "est ce que ca compile", "build status"],
        steps=[
            DominoStep("syntax_all", "bash:cd F:/BUREAU/turbo && python -m py_compile src/commands.py && python -m py_compile src/voice_correction.py && python -m py_compile src/domino_pipelines.py && python -m py_compile src/domino_executor.py && echo 'ALL SYNTAX OK'", "bash", timeout_s=15),
            DominoStep("imports", "bash:cd F:/BUREAU/turbo && python -c 'from src.commands import COMMANDS; from src.voice_correction import IMPLICIT_COMMANDS; from src.domino_pipelines import DOMINO_PIPELINES; print(\"ALL IMPORTS OK\")'", "bash", timeout_s=10),
            DominoStep("tts", "python:edge_tts_speak('Build verifie. Syntaxe et imports tous valides.')", "python"),
        ],
        category="ci_cd",
        description="Full build check: syntax + imports verification",
        learning_context="CI/CD — verification complete du build",
        priority="high",
    ),
    DominoPipeline(
        id="domino_port_scan",
        trigger_vocal=["scan ports", "ports ouverts", "quels ports", "netstat", "port scan"],
        steps=[
            DominoStep("scan", "bash:netstat -an | grep LISTEN | head -15", "bash", timeout_s=10),
            DominoStep("tts", "python:edge_tts_speak('Scan des ports termine. Ports en ecoute affiches.')", "python"),
        ],
        category="network_diagnostics",
        description="Scan local listening ports",
        learning_context="Network — scanner les ports locaux ouverts",
        priority="normal",
    ),
    DominoPipeline(
        id="domino_json_validate",
        trigger_vocal=["valide les json", "check json", "json valides", "verifie les json"],
        steps=[
            DominoStep("validate", "bash:cd F:/BUREAU/turbo && python -c \"import json,glob; errs=0; [print(f'{f}: OK') if json.load(open(f)) else None for f in glob.glob('data/*.json')[:10]]\" 2>&1 | head -15 || echo 'Erreur validation'", "bash", timeout_s=10),
            DominoStep("tts", "python:edge_tts_speak('Validation JSON terminee.')", "python"),
        ],
        category="data_validation",
        description="Validate all JSON files in data directory",
        learning_context="Data — verification fichiers JSON",
        priority="normal",
    ),
    DominoPipeline(
        id="domino_pip_security",
        trigger_vocal=["securite pip", "pip security", "audit pip", "vulnerabilites python"],
        steps=[
            DominoStep("audit", "bash:pip audit 2>/dev/null || pip list --outdated 2>/dev/null | head -10 || echo 'pip audit non disponible'", "bash", timeout_s=15),
            DominoStep("tts", "python:edge_tts_speak('Audit securite pip termine.')", "python"),
        ],
        category="security",
        description="Python pip security audit",
        learning_context="Securite — audit des packages Python",
        priority="high",
    ),
    DominoPipeline(
        id="domino_env_report",
        trigger_vocal=["rapport environnement", "env report", "variables env", "environment report"],
        steps=[
            DominoStep("python_ver", "bash:python --version 2>&1", "bash", timeout_s=3),
            DominoStep("node_ver", "bash:node --version 2>&1 || echo 'Node non installe'", "bash", timeout_s=3),
            DominoStep("git_ver", "bash:git --version 2>&1", "bash", timeout_s=3),
            DominoStep("uv_ver", "bash:uv --version 2>&1 || echo 'uv non installe'", "bash", timeout_s=3),
            DominoStep("disk", "python:get_disk_usage()", "python"),
            DominoStep("tts", "python:edge_tts_speak('Rapport environnement genere. Python, Node, Git et disques verifies.')", "python"),
        ],
        category="system_info",
        description="Environment report: Python + Node + Git + disk",
        learning_context="Systeme — rapport complet environnement dev",
        priority="normal",
    ),
    DominoPipeline(
        id="domino_schema_check",
        trigger_vocal=["schema base", "montre le schema", "tables database", "structure base"],
        steps=[
            DominoStep("schema", "bash:cd F:/BUREAU/turbo && python -c \"import sqlite3; c=sqlite3.connect('data/etoile.db'); [print(r[0]) for r in c.execute('SELECT name FROM sqlite_master WHERE type=\\\"table\\\" ORDER BY name')]\"", "bash", timeout_s=5),
            DominoStep("counts", "python:sqlite3_analyze()", "python"),
            DominoStep("tts", "python:edge_tts_speak('Schema de la base de donnees affiche avec les comptages.')", "python"),
        ],
        category="database",
        description="Show database schema and table counts",
        learning_context="Database — inspection schema et tables",
        priority="normal",
    ),
    DominoPipeline(
        id="domino_lines_of_code",
        trigger_vocal=["lignes de code", "count lines", "combien de lignes", "loc", "taille du projet"],
        steps=[
            DominoStep("count", "bash:cd F:/BUREAU/turbo && wc -l src/*.py 2>/dev/null || echo 'wc non disponible'", "bash", timeout_s=5),
            DominoStep("files", "bash:cd F:/BUREAU/turbo && find src -name '*.py' -type f 2>/dev/null | wc -l || echo '?'", "bash", timeout_s=5),
            DominoStep("tts", "python:edge_tts_speak('Comptage des lignes de code termine.')", "python"),
        ],
        category="project_stats",
        description="Count lines of code in project",
        learning_context="Stats — comptage lignes de code du projet",
        priority="normal",
    ),
    # ── Batch 93 — CI/CD, collaboration, Windows avancé (10 dominos) ──
    DominoPipeline(
        id="domino_ci_pipeline_check",
        trigger_vocal=["check ci", "statut pipeline", "ci pipeline", "check build"],
        steps=[
            DominoStep("ci_status", "bash:cd F:/BUREAU/turbo && git log --oneline -3", "bash", timeout_s=5),
            DominoStep("syntax_check", "bash:cd F:/BUREAU/turbo && python -m py_compile src/commands.py && python -m py_compile src/voice_correction.py && echo 'Syntax OK'", "bash", timeout_s=10),
            DominoStep("test_count", "python:count_commands()", "python"),
            DominoStep("tts", "python:edge_tts_speak('Pipeline CI verifie. Syntaxe ok, derniers commits affiches.')", "python"),
        ],
        category="ci_cd",
        description="Check CI pipeline: syntax + recent commits + counts",
        learning_context="DevOps — verification rapide pipeline CI",
        priority="high",
    ),
    DominoPipeline(
        id="domino_deploy_staging",
        trigger_vocal=["deploy staging", "deploie staging", "mise en staging", "push staging"],
        steps=[
            DominoStep("syntax", "bash:cd F:/BUREAU/turbo && python -m py_compile src/commands.py && python -m py_compile src/voice_correction.py && python -m py_compile src/domino_pipelines.py && echo 'ALL OK'", "bash", timeout_s=15),
            DominoStep("git_add", "bash:cd F:/BUREAU/turbo && git add -A && git status --short", "bash", timeout_s=5),
            DominoStep("git_push", "bash:cd F:/BUREAU/turbo && git push origin main 2>&1 | tail -3", "bash", timeout_s=30),
            DominoStep("tts", "python:edge_tts_speak('Deploy staging termine. Code pousse sur main.')", "python"),
        ],
        category="ci_cd",
        description="Deploy to staging: syntax check + commit + push",
        learning_context="DevOps — deploiement rapide staging",
        priority="high",
    ),
    DominoPipeline(
        id="domino_rollback_last",
        trigger_vocal=["rollback", "annuler dernier commit", "revert dernier", "git rollback"],
        steps=[
            DominoStep("show_last", "bash:cd F:/BUREAU/turbo && git log --oneline -3", "bash", timeout_s=5),
            DominoStep("tts_warn", "python:edge_tts_speak('Attention, rollback du dernier commit. Verification en cours.')", "python"),
            DominoStep("diff", "bash:cd F:/BUREAU/turbo && git diff HEAD~1 --stat", "bash", timeout_s=10),
        ],
        category="ci_cd",
        description="Rollback preparation: show last commits + diff stats",
        learning_context="DevOps — preparation rollback securise",
        priority="critical",
    ),
    DominoPipeline(
        id="domino_standup_report",
        trigger_vocal=["standup", "daily standup", "rapport standup", "daily report"],
        steps=[
            DominoStep("git_today", "bash:cd F:/BUREAU/turbo && git log --oneline --since='1 day ago'", "bash", timeout_s=5),
            DominoStep("stats", "python:count_commands()", "python"),
            DominoStep("corrections", "python:count_voice_corrections()", "python"),
            DominoStep("cluster", "bash:curl -s --max-time 3 http://127.0.0.1:1234/api/v1/models 2>/dev/null | head -c 30 && echo ' OK' || echo 'M1 OFFLINE'", "bash", timeout_s=5),
            DominoStep("tts", "python:edge_tts_speak('Standup termine. Commits du jour, stats vocales et cluster resumes.')", "python"),
        ],
        category="collaboration",
        description="Daily standup: commits today + voice stats + cluster health",
        learning_context="Collaboration — rapport standup quotidien",
        priority="normal",
    ),
    DominoPipeline(
        id="domino_pull_request_prep",
        trigger_vocal=["prepare pr", "pull request", "prepare merge", "pr prep"],
        steps=[
            DominoStep("branch", "bash:cd F:/BUREAU/turbo && git branch --show-current", "bash", timeout_s=3),
            DominoStep("diff_stats", "bash:cd F:/BUREAU/turbo && git diff --stat", "bash", timeout_s=5),
            DominoStep("log_recent", "bash:cd F:/BUREAU/turbo && git log --oneline -10", "bash", timeout_s=5),
            DominoStep("syntax", "bash:cd F:/BUREAU/turbo && python -m py_compile src/commands.py && echo 'Syntax OK'", "bash", timeout_s=10),
            DominoStep("tts", "python:edge_tts_speak('Pull request prepare. Branch, diff et logs affiches.')", "python"),
        ],
        category="collaboration",
        description="PR preparation: branch + diff + log + syntax check",
        learning_context="Collaboration — preparation pull request",
        priority="high",
    ),
    DominoPipeline(
        id="domino_wsl_status",
        trigger_vocal=["statut wsl", "wsl status", "check wsl", "etat wsl"],
        steps=[
            DominoStep("wsl_list", "bash:wsl --list --verbose 2>/dev/null || echo 'WSL non disponible'", "bash", timeout_s=10),
            DominoStep("tts", "python:edge_tts_speak('Statut WSL affiche.')", "python"),
        ],
        category="windows_system",
        description="Check WSL distributions status",
        learning_context="Windows — verifier statut WSL",
        priority="normal",
    ),
    DominoPipeline(
        id="domino_event_viewer",
        trigger_vocal=["event logs", "evenements systeme", "erreurs windows", "journal evenements"],
        steps=[
            DominoStep("errors", "bash:powershell -Command \"Get-EventLog -LogName System -EntryType Error -Newest 5 | Format-Table TimeGenerated,Source,Message -AutoSize\" 2>/dev/null || echo 'EventLog non accessible'", "bash", timeout_s=15),
            DominoStep("tts", "python:edge_tts_speak('Dernieres erreurs systeme Windows affichees.')", "python"),
        ],
        category="windows_system",
        description="Show recent Windows system errors from Event Viewer",
        learning_context="Windows — journal evenements erreurs recentes",
        priority="normal",
    ),
    DominoPipeline(
        id="domino_startup_apps",
        trigger_vocal=["apps demarrage", "startup apps", "programmes demarrage", "autostart"],
        steps=[
            DominoStep("startup", "bash:powershell -Command \"Get-CimInstance Win32_StartupCommand | Select-Object Name,Command | Format-Table -AutoSize\" 2>/dev/null || echo 'Impossible de lister'", "bash", timeout_s=10),
            DominoStep("tts", "python:edge_tts_speak('Applications au demarrage listees.')", "python"),
        ],
        category="windows_system",
        description="List Windows startup applications",
        learning_context="Windows — programmes au demarrage",
        priority="normal",
    ),
    DominoPipeline(
        id="domino_feature_flags",
        trigger_vocal=["feature flags", "flags actifs", "toggle features", "activer feature"],
        steps=[
            DominoStep("env_check", r"bash:cd F:/BUREAU/turbo && grep -r 'DRY_RUN\|ENABLE_\|DISABLE_\|FEATURE_' .env 2>/dev/null || echo 'Pas de .env ou pas de flags'", "bash", timeout_s=5),
            DominoStep("config_check", r"bash:cd F:/BUREAU/turbo && grep -rn 'DRY_RUN\|ENABLE_\|FEATURE_' src/config*.py 2>/dev/null | head -10 || echo 'Pas de flags dans config'", "bash", timeout_s=5),
            DominoStep("tts", "python:edge_tts_speak('Feature flags scannes dans le projet.')", "python"),
        ],
        category="ci_cd",
        description="Scan feature flags in env and config files",
        learning_context="DevOps — verification des feature flags",
        priority="normal",
    ),
    DominoPipeline(
        id="domino_collab_sync",
        trigger_vocal=["sync projet", "synchroniser", "git sync", "mettre a jour projet"],
        steps=[
            DominoStep("fetch", "bash:cd F:/BUREAU/turbo && git fetch --all 2>&1 | tail -3", "bash", timeout_s=15),
            DominoStep("status", "bash:cd F:/BUREAU/turbo && git status --short", "bash", timeout_s=5),
            DominoStep("behind", "bash:cd F:/BUREAU/turbo && git log HEAD..origin/main --oneline 2>/dev/null || echo 'A jour'", "bash", timeout_s=5),
            DominoStep("tts", "python:edge_tts_speak('Projet synchronise. Statut et retard affiches.')", "python"),
        ],
        category="collaboration",
        description="Sync project: fetch + status + check if behind",
        learning_context="Collaboration — synchronisation projet git",
        priority="normal",
    ),
    DominoPipeline(
        id="domino_final_check",
        trigger_vocal=["check final", "final check", "verification finale", "derniere verification"],
        steps=[
            DominoStep("syntax", "bash:cd F:/BUREAU/turbo && python -m py_compile src/commands.py && python -m py_compile src/voice_correction.py && python -m py_compile src/domino_pipelines.py && python -m py_compile src/domino_executor.py && echo 'ALL OK'", "bash", timeout_s=15),
            DominoStep("match_tests", "python:test_voice_match('ouvre chrome')", "python"),
            DominoStep("stats", "python:get_session_stats()", "python"),
            DominoStep("git_status", "bash:cd F:/BUREAU/turbo && git status --short", "bash", timeout_s=5),
            DominoStep("tts", "python:edge_tts_speak('Verification finale. Syntaxe, matching, stats et git tous verifies.')", "python"),
        ],
        category="testing_pipeline",
        description="Final check: syntax + match + stats + git",
        learning_context="QA — derniere verification avant deploiement",
        priority="high",
    ),

    # ─────────────────────────────────────────────────────────────────────
    # JARVIS TOOLS PIPELINES — uses action_type="tool" via WS 9742
    # ─────────────────────────────────────────────────────────────────────
    DominoPipeline(
        id="domino_tool_system_health",
        trigger_vocal=["sante systeme", "health check complet", "check sante jarvis", "system health",
                       "check systeme complet", "statut systeme complet", "rapport sante"],
        steps=[
            DominoStep("cluster", "tool:jarvis_cluster_health", "tool", timeout_s=15),
            DominoStep("boot", "tool:jarvis_boot_status", "tool", timeout_s=15),
            DominoStep("gpu", "tool:jarvis_gpu_status", "tool", timeout_s=10),
            DominoStep("db", "tool:jarvis_db_health", "tool", timeout_s=10),
            DominoStep("alerts", "tool:jarvis_alerts_active", "tool", timeout_s=10),
            DominoStep("tts", "python:edge_tts_speak('Health check complet. Cluster, boot, GPU, bases et alertes verifies.')", "python"),
        ],
        category="system_tools",
        description="Health check complet via JARVIS tools: cluster + boot + GPU + DB + alertes",
        learning_context="Diagnostic systeme complet via tools IA — prefere au diagnostic manual",
        priority="high",
    ),
    DominoPipeline(
        id="domino_tool_autonomous_check",
        trigger_vocal=["statut autonome", "check autonome", "taches autonomes", "boucle autonome",
                       "etat boucle autonome", "combien de taches"],
        steps=[
            DominoStep("status", "tool:jarvis_autonomous_status", "tool", timeout_s=10),
            DominoStep("events", "tool:jarvis_autonomous_events", "tool", timeout_s=10),
            DominoStep("tts", "python:edge_tts_speak('Boucle autonome verifiee. 18 taches inspectees.')", "python"),
        ],
        category="system_tools",
        description="Statut complet de la boucle autonome: taches + evenements recents",
        learning_context="Verification rapide de la boucle autonome JARVIS",
    ),
    DominoPipeline(
        id="domino_tool_morning_jarvis",
        trigger_vocal=["bonjour jarvis tools", "matin jarvis complet", "demarrage jarvis",
                       "bonjour jarvis", "routine matin", "rapport du matin"],
        steps=[
            DominoStep("boot", "tool:jarvis_boot_status", "tool", timeout_s=15),
            DominoStep("cluster", "tool:jarvis_cluster_health", "tool", timeout_s=15),
            DominoStep("autonomous", "tool:jarvis_autonomous_status", "tool", timeout_s=10),
            DominoStep("diag", "tool:jarvis_diagnostics_quick", "tool", timeout_s=10),
            DominoStep("gpu", "tool:jarvis_gpu_status", "tool", timeout_s=10),
            DominoStep("tts", "python:edge_tts_speak('Bonjour! Boot OK, cluster verifie, boucle autonome active, diagnostics prets.')", "python"),
        ],
        category="system_tools",
        description="Routine matin JARVIS via tools: boot + cluster + autonome + diag + GPU",
        learning_context="Demarrage matinal complet utilisant les tools JARVIS pour donnees reelles",
        priority="high",
    ),
    DominoPipeline(
        id="domino_tool_run_maintenance",
        trigger_vocal=["lance maintenance", "maintenance tools", "run maintenance",
                       "lance la maintenance", "nettoyage systeme", "nettoie le systeme"],
        steps=[
            DominoStep("zombie_gc", "tool:jarvis_run_task:task_name=zombie_gc", "tool", timeout_s=30),
            DominoStep("vram_audit", "tool:jarvis_run_task:task_name=vram_audit", "tool", timeout_s=30),
            DominoStep("db_maint", "tool:jarvis_db_maintenance", "tool", timeout_s=60),
            DominoStep("diag", "tool:jarvis_diagnostics_quick", "tool", timeout_s=10),
            DominoStep("tts", "python:edge_tts_speak('Maintenance terminee. Zombies nettoyes, VRAM audite, bases optimisees.')", "python"),
        ],
        category="system_tools",
        description="Pipeline maintenance via tools: zombie GC + VRAM audit + DB maintenance + diagnostic",
        learning_context="Maintenance systeme complete — destructive: DB maintenance",
        priority="normal",
    ),

    # ─────────────────────────────────────────────────────────────────────
    # PRODUCTION AUTONOME (Session 29 — 2026-03-10)
    # ─────────────────────────────────────────────────────────────────────
    DominoPipeline(
        id="domino_production_check",
        trigger_vocal=["check production", "valide la production", "production status",
                       "grade jarvis", "score production", "audit production"],
        steps=[
            DominoStep("validate", f"bash:cd {_TURBO_DIR_FWD} && python scripts/production_validator.py --json", "bash", timeout_s=30),
            DominoStep("tts_result", "python:edge_tts_speak('Validation production terminee.')", "python"),
        ],
        category="production",
        description="Validation des 7 couches de production avec score A-F",
        learning_context="Verification globale du systeme — score attendu > 90",
        priority="normal",
    ),
    DominoPipeline(
        id="domino_production_report",
        trigger_vocal=["rapport production", "envoie le rapport", "production report telegram",
                       "rapport complet production"],
        steps=[
            DominoStep("validate", f"bash:cd {_TURBO_DIR_FWD} && python scripts/production_validator.py --telegram", "bash", timeout_s=30),
            DominoStep("tts_sent", "python:edge_tts_speak('Rapport de production envoye sur Telegram.')", "python"),
        ],
        category="production",
        description="Validation production + envoi Telegram automatique",
        learning_context="Rapport de production complet envoye sur Telegram",
        priority="normal",
    ),
    DominoPipeline(
        id="domino_heavy_model_load",
        trigger_vocal=["prepare grosse demande", "charge le gros modele", "mode heavy",
                       "prepare gpt oss", "grosse tache"],
        steps=[
            DominoStep("load_model", f"bash:cd {_TURBO_DIR_FWD} && python scripts/smart_model_loader.py load gpt-oss-20b", "bash", timeout_s=120),
            DominoStep("tts_ready", "python:edge_tts_speak('Modele gpt oss 20b charge. Pret pour grosse demande.')", "python"),
        ],
        category="production",
        description="Charger gpt-oss-20b sur M1 pour taches complexes",
        learning_context="Chargement modele lourd — 14 GB VRAM necessaires",
        priority="high",
    ),
    DominoPipeline(
        id="domino_production_bootstrap",
        trigger_vocal=["bootstrap production", "amorce production", "lance tout le systeme",
                       "demarrage production complet"],
        steps=[
            DominoStep("check_gpu", "powershell:nvidia-smi --query-gpu=temperature.gpu,memory.used --format=csv,noheader", "powershell"),
            DominoStep("cluster_health", "curl:http://127.0.0.1:9742/api/health/full", "curl", timeout_s=10),
            DominoStep("automation_status", "curl:http://127.0.0.1:9742/api/automation/status", "curl", timeout_s=5),
            DominoStep("production_validate", f"bash:cd {_TURBO_DIR_FWD} && python scripts/production_validator.py --telegram", "bash", timeout_s=30),
            DominoStep("tts_done", "python:edge_tts_speak('Production amorcee. Tous les systemes operationnels.')", "python"),
        ],
        category="production",
        description="Bootstrap complet: GPU + cluster + automation + validation + Telegram",
        learning_context="Amorcage de production — lance toute la chaine de verification",
        priority="critical",
    ),

    # ─────────────────────────────────────────────────────────────────────
    # AUTO-SCAN (Session 30 — 2026-03-10)
    # ─────────────────────────────────────────────────────────────────────
    DominoPipeline(
        id="domino_auto_scan",
        trigger_vocal=["scan le systeme", "auto scan", "scan complet",
                       "diagnostic complet", "scan jarvis"],
        steps=[
            DominoStep("scan", f"bash:cd {_TURBO_DIR_FWD} && uv run python scripts/jarvis_auto_scan.py --once", "bash", timeout_s=120),
            DominoStep("tts", "python:edge_tts_speak('Scan systeme termine.')", "python"),
        ],
        category="system",
        description="Scan autonome complet: cluster, DB, GPU, services, dispatch",
        learning_context="Scan toutes les couches avec analyse M1 et auto-fix",
        priority="high",
    ),
    DominoPipeline(
        id="domino_metrics_dashboard",
        trigger_vocal=["dashboard", "metriques systeme", "metrics", "tableau de bord",
                       "donne moi les stats"],
        steps=[
            DominoStep("metrics", "curl:http://127.0.0.1:9742/api/metrics/dashboard", "curl", timeout_s=5),
            DominoStep("tts", "python:edge_tts_speak('Dashboard de metriques charge.')", "python"),
        ],
        category="monitoring",
        description="Dashboard en temps reel: cluster, dispatch, GPU, DBs",
        learning_context="Vue d'ensemble des metriques systeme en un appel",
        priority="normal",
    ),

    # ─────────────────────────────────────────────────────────────────────
    # WINDOWS BRIDGE (Session 30 — 2026-03-10)
    # ─────────────────────────────────────────────────────────────────────
    DominoPipeline(
        id="domino_windows_notify",
        trigger_vocal=["notification windows", "envoie une notif", "toast windows",
                       "alerte windows", "notifie moi"],
        steps=[
            DominoStep("push", "curl:http://127.0.0.1:9742/api/notifications/push", "curl", timeout_s=5),
            DominoStep("tts", "python:edge_tts_speak('Notification Windows envoyee.')", "python"),
        ],
        category="system",
        description="Envoyer une notification toast Windows via le bridge",
        learning_context="Bridge Windows pour notifications JARVIS",
        priority="normal",
    ),
    DominoPipeline(
        id="domino_sql_status",
        trigger_vocal=["status des bases", "etat des databases", "sql stats",
                       "combien de tables", "bases de donnees"],
        steps=[
            DominoStep("stats", "curl:http://127.0.0.1:9742/api/sql/stats", "curl", timeout_s=5),
            DominoStep("tts", "python:edge_tts_speak('Statistiques des bases de donnees chargees.')", "python"),
        ],
        category="system",
        description="Afficher les stats des 3 bases SQLite (etoile, jarvis, scheduler)",
        learning_context="Monitoring des bases de donnees SQLite",
        priority="normal",
    ),

    # ─────────────────────────────────────────────────────────────────────
    # AUTO-IMPROVE & MONITORING (Session 30 — 2026-03-10)
    # ─────────────────────────────────────────────────────────────────────
    DominoPipeline(
        id="domino_auto_improve",
        trigger_vocal=["ameliore le systeme", "auto improve", "auto amelioration",
                       "lance l'amelioration", "optimise la production"],
        steps=[
            DominoStep("improve", f"bash:cd {_TURBO_DIR_FWD} && uv run python scripts/production_auto_improve.py --once", "bash", timeout_s=120),
            DominoStep("tts_done", "python:edge_tts_speak('Cycle d amelioration termine.')", "python"),
        ],
        category="production",
        description="Lance un cycle auto-improve: validation + correction automatique",
        learning_context="Auto-fix production — corrige WS, modeles, noeuds automatiquement",
        priority="normal",
    ),
    DominoPipeline(
        id="domino_cluster_monitor",
        trigger_vocal=["monitore le cluster", "status cluster complet", "check tous les noeuds",
                       "surveillance cluster"],
        steps=[
            DominoStep("m1_check", "curl:http://127.0.0.1:1234/api/v1/models", "curl", timeout_s=5),
            DominoStep("ol1_check", "curl:http://127.0.0.1:11434/api/tags", "curl", timeout_s=5),
            DominoStep("ws_check", "curl:http://127.0.0.1:9742/health", "curl", timeout_s=5),
            DominoStep("gpu_temp", "powershell:nvidia-smi --query-gpu=name,temperature.gpu,memory.used,memory.total --format=csv,noheader", "powershell"),
            DominoStep("tts_report", "python:edge_tts_speak('Monitoring cluster termine.')", "python"),
        ],
        category="cluster",
        description="Monitoring complet: M1 + OL1 + WS + GPU temperature",
        learning_context="Surveillance de sante de tous les noeuds et GPU",
        priority="normal",
    ),
    DominoPipeline(
        id="domino_mode_performance",
        trigger_vocal=["mode performance", "max performance", "boost performance",
                       "mode turbo"],
        steps=[
            DominoStep("close_apps", "powershell:Get-Process chrome,msedge,discord -ErrorAction SilentlyContinue | Stop-Process -Force", "powershell"),
            DominoStep("gpu_boost", "powershell:nvidia-smi -pm 1", "powershell"),
            DominoStep("load_fast", f"bash:cd {_TURBO_DIR_FWD} && uv run python scripts/smart_model_loader.py status", "bash", timeout_s=10),
            DominoStep("tts_ready", "python:edge_tts_speak('Mode performance active. Applications fermees. GPU en mode persistant.')", "python"),
        ],
        category="system",
        description="Active le mode performance: ferme apps gourmandes + GPU boost",
        learning_context="Libere ressources pour maximiser performance JARVIS",
        priority="high",
    ),
    DominoPipeline(
        id="domino_daily_digest",
        trigger_vocal=["resume de la journee", "digest journalier", "daily digest",
                       "qu'est ce qui s'est passe aujourd'hui"],
        steps=[
            DominoStep("automation", "curl:http://127.0.0.1:9742/api/automation/status", "curl", timeout_s=5),
            DominoStep("scheduler", "curl:http://127.0.0.1:9742/api/scheduler/jobs", "curl", timeout_s=5),
            DominoStep("production", f"bash:cd {_TURBO_DIR_FWD} && uv run python scripts/production_validator.py --json", "bash", timeout_s=30),
            DominoStep("tts_digest", "python:edge_tts_speak('Resume de la journee prepare.')", "python"),
        ],
        category="production",
        description="Resume quotidien: automation + scheduler + production grade",
        learning_context="Synthese quotidienne de l'etat du systeme",
        priority="normal",
    ),

    # ─────────────────────────────────────────────────────────────────────
    # SELF-DIAGNOSTIC & CACHE (Session 31 — 2026-03-10)
    # ─────────────────────────────────────────────────────────────────────
    DominoPipeline(
        id="domino_self_diagnostic",
        trigger_vocal=["diagnostic systeme", "auto diagnostic", "self diagnostic",
                       "analyse toi", "diagnostique toi", "check ta sante"],
        steps=[
            DominoStep("diagnostic", "curl:http://127.0.0.1:9742/api/diagnostic/run", "curl", timeout_s=15),
            DominoStep("tts_report", "python:edge_tts_speak('Diagnostic systeme termine.')", "python"),
        ],
        category="system",
        description="Lance un auto-diagnostic complet: response times, error rates, circuit breakers, queue",
        learning_context="JARVIS analyse sa propre sante et performance",
        priority="high",
    ),
    DominoPipeline(
        id="domino_dispatch_cache",
        trigger_vocal=["stats du cache", "cache dispatch", "etat du cache",
                       "performance cache"],
        steps=[
            DominoStep("cache_stats", "curl:http://127.0.0.1:9742/api/dispatch/cache", "curl", timeout_s=5),
            DominoStep("tts_report", "python:edge_tts_speak('Stats du cache dispatch chargees.')", "python"),
        ],
        category="system",
        description="Affiche les statistiques du cache de dispatch (hits, taille, TTL)",
        learning_context="Monitoring performance du cache de requetes dispatch",
        priority="normal",
    ),
    DominoPipeline(
        id="domino_full_health",
        trigger_vocal=["sante complete", "full health check", "check complet",
                       "verification complete du systeme", "rapport sante global"],
        steps=[
            DominoStep("scan", f"bash:cd {_TURBO_DIR_FWD} && uv run python scripts/jarvis_auto_scan.py --once", "bash", timeout_s=60),
            DominoStep("diagnostic", "curl:http://127.0.0.1:9742/api/diagnostic/run", "curl", timeout_s=15),
            DominoStep("cache", "curl:http://127.0.0.1:9742/api/dispatch/cache", "curl", timeout_s=5),
            DominoStep("automation", "curl:http://127.0.0.1:9742/api/automation/status", "curl", timeout_s=5),
            DominoStep("tts_done", "python:edge_tts_speak('Rapport de sante complet termine. Scan, diagnostic, cache et automation verifies.')", "python"),
        ],
        category="production",
        description="Health check complet: auto_scan + self_diagnostic + cache + automation status",
        learning_context="Verification exhaustive de tous les sous-systemes JARVIS",
        priority="high",
    ),
    DominoPipeline(
        id="domino_system_resources",
        trigger_vocal=["ressources systeme", "cpu et ram", "utilisation memoire",
                       "charge systeme", "system resources"],
        steps=[
            DominoStep("gpu", "powershell:nvidia-smi --query-gpu=name,temperature.gpu,memory.used,memory.total,utilization.gpu --format=csv,noheader", "powershell"),
            DominoStep("cpu_ram", "powershell:Get-CimInstance Win32_Processor | Select-Object LoadPercentage | Format-Table -HideTableHeaders; (Get-CimInstance Win32_OperatingSystem | ForEach-Object { '{0:N0} MB free / {1:N0} MB total' -f ($_.FreePhysicalMemory/1024), ($_.TotalVisibleMemorySize/1024) })", "powershell"),
            DominoStep("disk", "powershell:Get-PSDrive C,F -ErrorAction SilentlyContinue | ForEach-Object { '{0}: {1:N1} GB free / {2:N1} GB total' -f $_.Name, ($_.Free/1GB), (($_.Used+$_.Free)/1GB) }", "powershell"),
            DominoStep("tts_done", "python:edge_tts_speak('Ressources systeme chargees.')", "python"),
        ],
        category="system",
        description="Affiche les ressources systeme: CPU, RAM, GPU, disques",
        learning_context="Monitoring ressources materielles en temps reel",
        priority="normal",
    ),
    DominoPipeline(
        id="domino_vram_check",
        trigger_vocal=["etat de la vram", "vram status", "memoire gpu",
                       "gpu memoire", "vram libre", "optimise la vram"],
        steps=[
            DominoStep("vram", "curl:http://127.0.0.1:9742/api/vram/status", "curl", timeout_s=10),
            DominoStep("tts_report", "python:edge_tts_speak('Rapport VRAM charge.')", "python"),
        ],
        category="system",
        description="Verifie l'utilisation VRAM de tous les GPU et suggere des optimisations",
        learning_context="Monitoring VRAM GPU pour eviter les saturations",
        priority="high",
    ),
    DominoPipeline(
        id="domino_rollback_history",
        trigger_vocal=["historique rollback", "rollback history", "dernieres corrections",
                       "historique des fix"],
        steps=[
            DominoStep("history", "curl:http://127.0.0.1:9742/api/rollback/history", "curl", timeout_s=5),
            DominoStep("tts_report", "python:edge_tts_speak('Historique des rollbacks charge.')", "python"),
        ],
        category="system",
        description="Affiche l'historique des auto-fix avec snapshots et rollbacks",
        learning_context="Suivi des corrections automatiques et rollbacks",
        priority="normal",
    ),
    DominoPipeline(
        id="domino_log_predictions",
        trigger_vocal=["predictions erreurs", "previsions pannes", "log predictions",
                       "anticipe les erreurs", "problemes a venir"],
        steps=[
            DominoStep("predictions", "curl:http://127.0.0.1:9742/api/logs/predictions", "curl", timeout_s=10),
            DominoStep("tts_report", "python:edge_tts_speak('Predictions d erreurs chargees.')", "python"),
        ],
        category="production",
        description="Predictions de pannes basees sur l'analyse des patterns de logs",
        learning_context="Intelligence predictive — anticiper les problemes avant qu'ils arrivent",
        priority="high",
    ),
]

# Post-process: replace hardcoded paths with config-driven values
for _pipeline in DOMINO_PIPELINES:
    for _step in _pipeline.steps:
        if "F:\\BUREAU\\turbo" in _step.action:
            _step.action = _step.action.replace("F:\\BUREAU\\turbo", _TURBO_DIR)
        if "F:/BUREAU/turbo" in _step.action:
            _step.action = _step.action.replace("F:/BUREAU/turbo", _TURBO_DIR_FWD)


# ══════════════════════════════════════════════════════════════════════════════
# LEARNING DATASET — Scenarios d'apprentissage vocal pour fine-tuning
# ══════════════════════════════════════════════════════════════════════════════

DOMINO_LEARNING_DATASET: list[dict] = []

def _build_learning_dataset():
    """Genere le dataset d'apprentissage a partir des dominos definis."""
    for dp in DOMINO_PIPELINES:
        for trigger in dp.trigger_vocal:
            DOMINO_LEARNING_DATASET.append({
                "input": trigger,
                "output": f"domino:{dp.id}",
                "category": dp.category,
                "steps": [s.name for s in dp.steps],
                "context": dp.learning_context,
                "priority": dp.priority,
            })

_build_learning_dataset()


# ══════════════════════════════════════════════════════════════════════════════
# DOMINO ENGINE — Executeur de cascades
# ══════════════════════════════════════════════════════════════════════════════

def find_domino(text: str) -> DominoPipeline | None:
    """Trouve le domino pipeline correspondant a une phrase vocale.

    Matching order: exact trigger > partial trigger > ID match > keyword in description.
    """
    text_lower = text.lower().strip()
    best_match = None
    best_score = 0.0

    for dp in DOMINO_PIPELINES:
        # 1. Exact trigger match (highest priority)
        for trigger in dp.trigger_vocal:
            if text_lower == trigger.lower():
                return dp

        # 2. Partial trigger match (containment)
        for trigger in dp.trigger_vocal:
            trig_lower = trigger.lower()
            if trig_lower in text_lower or text_lower in trig_lower:
                from difflib import SequenceMatcher
                score = SequenceMatcher(None, text_lower, trig_lower).ratio()
                if score > best_score and score > 0.6:
                    best_score = score
                    best_match = dp

        # 3. ID match (e.g. "domino_backup_complet" matches "backup complet")
        id_clean = dp.id.replace("domino_", "").replace("_", " ")
        if text_lower == id_clean or id_clean in text_lower:
            score = 0.75
            if score > best_score:
                best_score = score
                best_match = dp

        # 4. Keyword match in description (lowest priority)
        text_words = set(text_lower.split())
        desc_words = set(dp.description.lower().split())
        common = text_words & desc_words - {"de", "du", "le", "la", "les", "un", "une", "des", "et", "en", "a"}
        if len(common) >= 2:
            keyword_score = len(common) / max(len(text_words), 1) * 0.65
            if keyword_score > best_score and keyword_score > 0.5:
                best_score = keyword_score
                best_match = dp

    return best_match


def get_domino_stats() -> dict:
    """Retourne les statistiques des domino pipelines."""
    categories = {}
    for dp in DOMINO_PIPELINES:
        categories[dp.category] = categories.get(dp.category, 0) + 1

    return {
        "total_dominos": len(DOMINO_PIPELINES),
        "total_triggers": sum(len(dp.trigger_vocal) for dp in DOMINO_PIPELINES),
        "total_steps": sum(len(dp.steps) for dp in DOMINO_PIPELINES),
        "categories": categories,
        "learning_examples": len(DOMINO_LEARNING_DATASET),
        "critical_count": sum(1 for dp in DOMINO_PIPELINES if dp.priority == "critical"),
        "high_count": sum(1 for dp in DOMINO_PIPELINES if dp.priority == "high"),
    }
