# TRADING V2 PRODUCTION - Pipeline CQ v3.2

## Architecture

Environnement de production isole pour le systeme de trading AI multi-IA sur MEXC Futures.

### Pipeline CQ v3.2 (Consensus Quantitatif)
- **8 modeles IA** sur 3 serveurs LM Studio (16 GPUs, 105GB VRAM)
- **3 stages**: FAST (early exit) → DEEP (analysis) → CONTRARIAN (validation)
- **Patch V3.2**: SHORT boost x1.5, LONG penalty x0.4, confidence >= 80%
- **Self-correction**: tracking WIN/LOSS a 15m/1h/4h
- **Adaptive weights**: poids par accuracy modele sur 14 jours

### Patches V3.2 appliques
| Patch | Description | Rationale |
|-------|-------------|-----------|
| SHORT_BOOST | Confidence SHORT x1.5 | SHORT WR 57.6% vs LONG WR 6.8% |
| CONFIDENCE_80 | Seuil 60 → 80 (6 locations) | 80-100% conf = 75% WR |
| TP_SL_BOTH_DIRS | TP/SL pour LONG + SHORT | Etait LONG-only |

## Structure

```
TRADING_V2_PRODUCTION/
├── config/
│   └── v2_config.json              # Config V2 avec paths et LM Studio cluster
├── database/
│   └── trading.db                  # DB SQLite isolee (17.1 MB)
│       ├── pipeline_config         # 20 parametres pipeline
│       ├── pipeline_changelog      # 8 versions V1.0 → V3.2
│       ├── monitor_sessions        # Sessions monitoring RIVER
│       ├── monitor_cycles          # 50 cycles detail par session
│       ├── audit_results           # Resultats audit performance
│       ├── predictions             # Predictions CQ + self-correction
│       ├── signals                 # Signaux trading
│       ├── consensus_responses     # Reponses par modele/serveur
│       └── ...                     # 18 tables total
├── logs/                           # Logs execution
├── scripts/
│   ├── auto_cycle_10.py            # Pipeline 10 cycles scan MEXC + DB
│   ├── execute_trident.py          # Execution multi-ordres (DRY_RUN/LIVE)
│   ├── river_scalp_1min.py         # Monitor 1min avec indicateurs
│   ├── sniper_10cycles.py          # 10 cycles sniper + focus tracking
│   └── sniper_breakout.py          # Scan pre-pump orderbook + indicateurs
├── Scanner-Pro-v2.ps1              # Scanner Pro V3.2 (patche)
└── trading_mcp_ultimate_v3.py      # MCP Server v3.7.0 (114 outils)
```

## LM Studio Cluster

| Serveur | IP | Role | Modeles |
|---------|----|------|---------|
| M1 | 192.168.1.85:1234 | Deep Analysis | qwen3-30b, qwen3-coder, gpt-oss-20b |
| M2 | 192.168.1.26:1234 | Fast Inference | gpt-oss-20b (8.3s), glm-4.7-flash |
| M3 | 192.168.1.113:1234 | Validation | mistral-7b, phi-3.1-mini, gpt-oss-20b |

## Audit Performance (2026-02-08)

- **Score global**: 85/100
- **281 predictions**: 22 WIN, 55 LOSS, 187 PENDING
- **Direction**: SHORT WR 57.6% vs LONG WR 6.8%
- **Confidence**: 80-100% = 75% WR, <60% = 6.7% WR
- **BB Squeeze**: BB < 0.7% = breakout imminent (5/5 confirmed)

## Monitor Sessions RIVER/USDT

| Session | Peak | PnL Peak | Close PnL | BB Squeeze |
|---------|------|----------|-----------|------------|
| #4 | 12.797 (+50.0%) | +14.96$ | +44.8% | 0.9% → YES |
| #5 | 12.967 (+77.2%) | +23.09$ | +68.3% | YES |
| #6 | 12.801 (+50.7%) | +15.15$ | +50.7% | 0.6% → YES |
