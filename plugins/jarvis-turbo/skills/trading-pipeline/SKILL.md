---
name: Trading Pipeline
description: Use when running or interpreting trading pipeline results, configuring trading parameters, or analyzing crypto market signals from the GPU pipeline v2.3.
version: 1.0.0
---

# Trading Pipeline GPU v2.3

## Lancement

```bash
cd "F:/BUREAU/turbo/scripts/trading_v2"
python3 gpu_pipeline.py --coins 100 --top 10 --json [OPTIONS]
```

### Modes

| Mode | Flag | IAs | Duree | Usage |
|------|------|-----|-------|-------|
| Quick | `--quick` | 2 (OL1+M2) | ~19s | Scan rapide, validation |
| Fast | `--no-gemini` | 5 | ~30s | Production quotidienne |
| Full | (rien) | 6 | ~90s | Decision critique |
| No AI | `--no-ai` | 0 | ~5s | Analyse technique pure |

### Options

- `--coins N` — nombre de coins a scanner (defaut 100)
- `--top N` — top N resultats affiches (defaut 10)
- `--json` — sortie JSON machine-readable
- `--cycles N` — boucle continue N cycles

## Interpretation des signaux

### Score de confiance
- **90-100**: Signal tres fort — consensus unanime
- **70-89**: Signal bon — majorite d'accord
- **50-69**: Signal faible — divergences entre IAs
- **<50**: Pas de signal — skip

### Permission de trade
Trois conditions REQUISES simultanement :
1. Consensus >= 60%
2. Confiance >= 50%
3. Spread > 20% (ecart entre bull et bear)

### Market Regime
- **Trend** (>80%): Suivre la tendance, TP large
- **Range** (60-80%): Mean reversion, TP court
- **Transition** (<60%): Prudence, reduire taille

## Parametres actifs

- Exchange: MEXC Futures
- Levier: 10x
- Taille: 10 USDT par trade
- TP: 0.4% | SL: 0.25%
- ATR dynamique: SL=entry-1.5*ATR, TP1=entry+2.25*ATR, TP2=entry+4.5*ATR
- 10 paires: BTC ETH SOL SUI PEPE DOGE XRP ADA AVAX LINK

## Consensus 6 IAs (poids)

| IA | Machine | Poids | Role |
|----|---------|-------|------|
| OL1-local | 127.0.0.1:11434 | 0.8 | Rapide, premiere passe |
| OL1-cloud | minimax-m2.5 | 1.3 | Web search, contexte |
| M2/deepseek | 192.168.1.26 | 1.2 | Analyse technique |
| M3/mistral | 192.168.1.113 | 1.0 | Validation |
| M1/qwen3-30b | 10.5.0.2 | 1.5 | Raisonnement profond |
| GEMINI | proxy | 1.1 | Vision macro (bottleneck 60-90s) |

## Dashboard

- URL: ouvrir `F:\BUREAU\turbo\scripts\trading_v2\dashboard_pro.html`
- Donnees: chargement JSON depuis pipeline
- WS: port 9742 pour real-time

## Troubleshooting

- **GEMINI bottleneck**: Utiliser `--no-gemini` en production
- **CuPy NVRTC manquant**: Fallback NumPy automatique (75ms/100 coins)
- **M1 timeout**: Normal sur 7/10 requetes, le pipeline gere
- **DRY_RUN**: Verifier `DRY_RUN=false` dans config avant trades reels
