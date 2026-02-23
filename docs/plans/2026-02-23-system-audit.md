# System Audit Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build `scripts/system_audit.py` — an async parallel cluster diagnostic that produces a 10-section structured report with readiness scores, integrable as CLI, voice command, and MCP tool.

**Architecture:** Single Python script using asyncio.gather for parallel health checks on all 5 nodes (M1/M2/M3/OL1/GEMINI) + local system info. Data collection layer separated from analysis layer separated from output layer. Reuses `src/config.py` for node definitions.

**Tech Stack:** Python 3.13, httpx (async), asyncio, subprocess (nvidia-smi/PowerShell), json. Zero new dependencies.

---

### Task 1: Core data collection — Node health checks

**Files:**
- Create: `scripts/system_audit.py`
- Create: `test_system_audit.py`
- Reference: `src/config.py` (node definitions)
- Reference: `src/tools.py:87-109` (_get_client, _retry_request patterns)

**Step 1: Write the test file**

Create `test_system_audit.py` — standalone async test (same pattern as existing test_voice_v2.py):

- Test 1: `check_lm_node(M2)` returns dict with keys: name, status, models_loaded, latency_ms
- Test 2: `check_ollama(OL1)` returns dict with keys: name, status, models_available
- Test 3: `check_gemini(config.gemini_node)` returns dict with keys: name, status

**Step 2: Run test — expect ImportError (module does not exist yet)**

Run: `cd F:/BUREAU/turbo && uv run python test_system_audit.py`
Expected: FAIL — ModuleNotFoundError

**Step 3: Create `scripts/system_audit.py` with 3 async functions**

- `check_lm_node(node)`: GET /api/v1/models with auth headers, extract loaded models, measure latency. 5s timeout.
- `check_ollama(node)`: GET /api/tags, extract models available, measure latency. 5s timeout.
- `check_gemini(gemini_node)`: asyncio.create_subprocess_exec "node gemini-proxy.js ping", measure latency. 5s timeout.

All return dicts with: name, url, role, status (ONLINE/OFFLINE/TIMEOUT), latency_ms, error, models data.

**Step 4: Run test**

Run: `cd F:/BUREAU/turbo && uv run python test_system_audit.py`
Expected: PASS (at least 2/3 if M2 and OL1 are up)

**Step 5: Commit**

```
git add scripts/system_audit.py test_system_audit.py
git commit -m "feat(audit): add node health check functions — M1/M2/M3/OL1/GEMINI"
```

---

### Task 2: System info collection — GPU, OS, ports

**Files:**
- Modify: `scripts/system_audit.py` (append 3 new functions)
- Modify: `test_system_audit.py` (add tests 4-6)

**Step 1: Add tests 4-6 to test file**

- Test 4: `check_gpu_local()` returns list of dicts with: name, temperature_c, vram_used_mb, vram_total_mb
- Test 5: `check_system_info()` returns dict with: os_version, ram_total_gb, ram_free_gb, disks
- Test 6: `check_ports()` returns dict of host -> list of {port, open}

**Step 2: Run test — expect ImportError on new functions**

**Step 3: Implement 3 functions**

- `check_gpu_local()`: nvidia-smi --query-gpu=index,name,temperature.gpu,memory.used,memory.total,utilization.gpu --format=csv,noheader,nounits. Parse CSV output.
- `check_system_info()`: PowerShell Get-CimInstance Win32_OperatingSystem + Get-PSDrive. Parse JSON output.
- `check_ports()`: asyncio.open_connection with 2s timeout on KNOWN_PORTS dict ({host: [ports]}).

All use asyncio.create_subprocess_exec (not subprocess.run) for non-blocking execution.

**Step 4: Run tests**

Expected: PASS (6/6)

**Step 5: Commit**

```
git commit -m "feat(audit): add system info collection — GPU, OS, RAM, disks, ports"
```

---

### Task 3: Analysis layer — SPOF, security, scores

**Files:**
- Modify: `scripts/system_audit.py` (append analysis + orchestrator)
- Modify: `test_system_audit.py` (add test 7)

**Step 1: Add test 7**

- Test 7: `run_audit()` returns dict with keys: scores, risks, nodes, gpus, system, ports, persistence. All 6 scores in 0-100 range.

**Step 2: Run test — expect ImportError**

**Step 3: Implement 5 functions**

- `analyze_spof(nodes)`: Detect SPOFs — single LM node, GEMINI single proxy, M1 sole embedding, OL1 sole web, master sole orchestrator. Returns list of {severity, category, detail}.
- `analyze_security(nodes, ports)`: Check exposed ports on non-localhost, API key hardcoding. Returns list of {severity, category, detail}.
- `analyze_persistence()`: Check Path existence for data/, LMSTUDIO_BACKUP/, etoile.db, jarvis.db, logs/. Returns dict.
- `compute_scores(nodes, gpus, ports, persistence)`: Calculate 6 scores using weighted formulas from design doc. Returns dict of 6 int scores.
- `run_audit()`: asyncio.gather all Phase 1+2 checks, unpack results, run Phase 3-4 analysis, assemble report dict. Returns complete report dict.

**Step 4: Run tests**

Expected: PASS (7/7)

**Step 5: Commit**

```
git commit -m "feat(audit): add analysis layer — SPOF, security, scores, orchestrator"
```

---

### Task 4: Report formatter — 10 sections + CLI

**Files:**
- Modify: `scripts/system_audit.py` (append formatter + CLI main)
- Modify: `test_system_audit.py` (add test 8)

**Step 1: Add test 8**

- Test 8: `format_report(report)` returns string containing "EXECUTIVE SUMMARY", "ARCHITECTURE MAP", "READINESS SCORES", length > 500 chars.

**Step 2: Run test — expect ImportError**

**Step 3: Implement 3 functions**

- `format_report(report)`: Build 10-section text report:
  - Header box with status/duration
  - S1 Executive Summary: version, nodes status, latencies
  - S2 Architecture Map: ASCII tree with machines, IPs, models
  - S3 Node Health Table: formatted table with columns
  - S4 Topology & Dependencies: routing rules, failover paths
  - S5 Multimodal Capability Matrix: text/embedding/vision/audio status
  - S6 Critical Risks: sorted by severity
  - S7 Security Assessment: auth, ports, exposure
  - S8 Performance & Scaling: GPU stats, latencies, bottlenecks
  - S9 Persistence & Recovery: backup/log status, RTO/RPO estimates
  - S10 Readiness Scores: 6 scores with visual bars + OVERALL average

- `save_report(report)`: Write JSON to data/audit_YYYY-MM-DD_HHmm.json

- `main()`: CLI with argparse: --json (JSON only), --quick (health only), --save (persist). Default = console report + auto-save.

**Step 4: Run tests**

Expected: PASS (8/8)

**Step 5: Run the actual CLI**

Run: `cd F:/BUREAU/turbo && uv run python scripts/system_audit.py`
Expected: Full 10-section report

**Step 6: Commit**

```
git commit -m "feat(audit): add report formatter (10 sections) + CLI entry point"
```

---

### Task 5: Integration — MCP tool + voice command

**Files:**
- Modify: `src/tools.py:~480` (after lm_cluster_status tool)
- Modify: `src/mcp_server.py:~136` (after handle_lm_cluster_status) + `~1010` (TOOL_DEFINITIONS)
- Modify: `src/commands.py` (add 2 voice commands in systeme category)

**Step 1: Add MCP tool to `src/tools.py`**

After `lm_cluster_status` tool (~line 480), add `system_audit` tool. Uses importlib.util to import scripts/system_audit.py, calls run_audit() + format_report(), returns text.

**Step 2: Add handler + registration to `src/mcp_server.py`**

- New handler `handle_system_audit(args)` after line 136 — same importlib pattern
- Register in TOOL_DEFINITIONS after lm_cluster_status entry (~line 1010)

**Step 3: Add voice commands to `src/commands.py`**

Two new JarvisCommand entries in systeme category:
- "audit_systeme": triggers ["audit systeme", "audit cluster", "diagnostic cluster", "verification systeme"], action="script", script="system_audit"
- "check_cluster_rapide": triggers ["check cluster", "sante cluster", "health check"], action="script", script="system_audit --quick"

**Step 4: Run CLI audit end-to-end**

Run: `cd F:/BUREAU/turbo && uv run python scripts/system_audit.py --save`
Expected: Full report + JSON saved

**Step 5: Commit**

```
git commit -m "feat(audit): integrate as MCP tool + voice commands"
```

---

### Task 6: Final validation

**Step 1: Run full test suite**

Run: `cd F:/BUREAU/turbo && uv run python test_system_audit.py`
Expected: 8/8 PASS

**Step 2: Run CLI with all modes**

Run: `uv run python scripts/system_audit.py` (console)
Run: `uv run python scripts/system_audit.py --json` (JSON)
Run: `uv run python scripts/system_audit.py --save` (persist)

**Step 3: Verify JSON output is valid**

**Step 4: Final commit**

```
git commit -m "feat(audit): complete system audit v1 — tests, CLI, MCP, voice"
```
