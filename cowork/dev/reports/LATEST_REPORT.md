# JARVIS Cowork Report — 2026-03-07 15:29

## Summary

| Metric | Value |
|--------|-------|
| Cowork scripts | 435 |
| Source modules (src/) | 229 |
| Test files | 294 |
| Test functions | 8529 |
| OpenClaw agents | 40 |
| Agents with IDENTITY | 40/40 |
| Intent routes | 37 |
| Agents routed | 23 |

## Cowork Scripts by Category

| Category | Count |
|----------|-------|
| other | 301 |
| monitoring | 26 |
| cluster | 19 |
| testing | 19 |
| voice | 14 |
| automation | 13 |
| web | 10 |
| intelligence | 9 |
| communication | 9 |
| security | 5 |
| pipeline | 4 |
| reporting | 3 |
| devops | 2 |
| trading | 1 |

## Top 20 Scripts by Size

| Script | Lines | Category |
|--------|-------|----------|
| sniper_scanner | 1949 | other |
| voice_computer_control | 1405 | voice |
| memory_optimizer | 1068 | intelligence |
| network_optimizer | 1032 | other |
| telegram_cowork_dashboard | 964 | communication |
| gpu_optimizer | 935 | other |
| agent_orchestrator | 922 | other |
| strategy_evolution_loop | 922 | other |
| autonomous_orchestrator | 849 | other |
| misc_tools_runner | 800 | other |
| autonomous_cluster_pipeline | 778 | cluster |
| code_generator | 754 | other |
| jarvis_super_loop | 729 | other |
| jarvis_master_autonome | 676 | other |
| telegram_stats | 652 | communication |
| autonomous_orchestrator_v3 | 643 | other |
| cross_script_integration_tester | 595 | testing |
| node_failover_simulator | 593 | cluster |
| linkedin_scheduler | 588 | web |
| dispatch_realtime_monitor | 569 | monitoring |

## OpenClaw Agents (40)

| Agent | IDENTITY | Models |
|-------|----------|--------|
| analysis-engine | OK | --- |
| claude-reasoning | OK | --- |
| code-champion | OK | --- |
| coding | OK | OK |
| consensus-master | OK | OK |
| creative-brainstorm | OK | OK |
| data-analyst | OK | OK |
| debug-detective | OK | OK |
| deep-reasoning | OK | --- |
| deep-work | OK | OK |
| devops-ci | OK | OK |
| doc-writer | OK | OK |
| fast-chat | OK | OK |
| gemini-flash | OK | OK |
| gemini-pro | OK | OK |
| m1-deep | OK | OK |
| m1-reason | OK | --- |
| m2-code | OK | OK |
| m2-review | OK | OK |
| m3-general | OK | --- |
| main | OK | OK |
| ol1-fast | OK | OK |
| ol1-reasoning | OK | OK |
| ol1-web | OK | OK |
| pipeline-comet | OK | --- |
| pipeline-maintenance | OK | OK |
| pipeline-modes | OK | --- |
| pipeline-monitor | OK | OK |
| pipeline-routines | OK | OK |
| pipeline-trading | OK | --- |
| quick-dispatch | OK | --- |
| recherche-synthese | OK | OK |
| securite-audit | OK | OK |
| system-ops | OK | --- |
| task-router | OK | --- |
| trading | OK | OK |
| trading-scanner | OK | OK |
| translator | OK | OK |
| voice-assistant | OK | OK |
| windows | OK | OK |

## Database Stats

- Tool calls tracked: 12
- Top tools:
  - jarvis_boot_status: 4 calls
  - jarvis_cluster_health: 4 calls
  - jarvis_alerts_active: 1 calls
  - jarvis_autonomous_status: 1 calls
  - jarvis_diagnostics_quick: 1 calls
- Dispatch log entries: 373

## Architecture

```
Message → Intent Classifier → OpenClaw Bridge → Agent Selection
                                    ↓
                            Dispatch Engine → Node Selection (M1/M2/M3/OL1)
                                    ↓
                            Quality Gate → Feedback Loop → Episodic Memory
```

## Generated

- Date: 2026-03-07T15:29:10.357252
- Generator: scripts/cowork_github_report.py
- JARVIS v12.4 — Turbo Cluster
