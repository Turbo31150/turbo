"""Inject wave 4 tasks into the production queue."""
import json
import urllib.request

tasks = [
    # === P1 — BUG TEST FAILING ===
    {"task_type": "code_fix", "priority": 1, "prompt": "Fix test_phase25.py::TestScreenCapture::test_get_screen_size line 186. TypeError: > not supported between MagicMock and int. The mock for screen size returns MagicMock instead of int. Fix: mock.return_value should be (1920, 1080) tuple of ints, not bare MagicMock."},

    # === P1 — HARDCODED IPS ===
    {"task_type": "code_fix", "priority": 1, "prompt": "Refactor 19 hardcoded IPs in src/ files (config_manager.py:30-33, domino_executor.py:156-162, health_probe_registry.py:164). All cluster IPs should come from src/config.py JarvisConfig, not be hardcoded. Create get_node_url(name) helper."},

    # === P2 — API ROUTES TOO LARGE ===
    {"task_type": "code_improve", "priority": 2, "prompt": "Split python_ws/routes/chat.py from 1025 lines. Extract chat_dispatch.py (cluster dispatch), chat_streaming.py (SSE), chat_history.py (storage). Single file handles 3 concerns."},
    {"task_type": "code_improve", "priority": 2, "prompt": "Split python_ws/routes/voice.py from 528 lines. Extract voice_transcription.py (whisper/STT) and voice_tts.py (Edge TTS/SAPI synthesis)."},
    {"task_type": "code_improve", "priority": 2, "prompt": "Split python_ws/routes/system.py from 508 lines. Extract system_health.py and system_config.py."},

    # === P2 — TOO MANY PARAMS ===
    {"task_type": "code_improve", "priority": 2, "prompt": "Refactor audit_trail.py:56 log() (10 params) into AuditEntry dataclass. Same for agent_feedback_loop.py:165 record_feedback(9 params) into FeedbackRecord dataclass."},
    {"task_type": "code_improve", "priority": 2, "prompt": "Refactor collab_bridge.py:47 create_task(9 params) and conversation_store.py:79 add_turn(9 params). Group into CollabTask and ConversationTurn dataclasses."},

    # === P2 — DOCSTRINGS ===
    {"task_type": "code_improve", "priority": 2, "prompt": "Add one-line docstrings to 12 undocumented public functions: agent_episodic_memory (store_episode, recall, store_fact, get_pattern_memory, learn_from_history), command_registry (execute), health_probe (run_check, get_stats), event_store (append), feature_flags (create), backup_manager (delete_backup), agent_factory (main)."},

    # === P2 — OL1 SATURATION ===
    {"task_type": "code_fix", "priority": 2, "prompt": "Fix OL1 saturation in task queue. OLLAMA_NUM_PARALLEL=3 but queue sends 5+ concurrent tasks to OL1. Add asyncio.Semaphore(2) per node in task_queue.py to limit concurrency."},
    {"task_type": "code_fix", "priority": 2, "prompt": "Add connection retry with exponential backoff to task_queue._execute_on_node() for OL1. 3 retries (1s/2s/4s) on httpx.ConnectError before failing."},

    # === P2 — TEST GAPS ===
    {"task_type": "test", "priority": 2, "prompt": "Write 5 tests for python_ws/routes/chat.py (1025 lines, 0 tests). Test /api/chat with mocked M1, SSE streaming, history. Use FastAPI TestClient."},
    {"task_type": "test", "priority": 2, "prompt": "Write 4 tests for src/domino_executor.py — action parsing, node detection from URLs, execution with mocked httpx."},
    {"task_type": "test", "priority": 2, "prompt": "Write 4 tests for src/config_manager.py — node CRUD, weight updates, config persistence, default validation."},

    # === P3 — PERFORMANCE ===
    {"task_type": "code_improve", "priority": 3, "prompt": "Implement lazy imports for heavy modules in python_ws/server.py. Use importlib.import_module() on first request. Reduce cold start time."},
    {"task_type": "code_improve", "priority": 3, "prompt": "Add 30s response caching to /api/cluster/health. Called every 2min by scheduler + every page load. Simple dict+timestamp cache reduces redundant health pings."},
    {"task_type": "code_improve", "priority": 3, "prompt": "Optimize agent_episodic_memory.py recall() with SQLite FTS5 index on episode content. O(n) scan to O(log n)."},
    {"task_type": "code_improve", "priority": 3, "prompt": "Profile src/mcp_server.py (6283 lines). Find: dead MCP tools never called, duplicated handlers, unused imports. Generate cleanup report."},

    # === P3 — RESILIENCE ===
    {"task_type": "code_improve", "priority": 3, "prompt": "Add graceful shutdown to background asyncio tasks. automation_hub loop and autonomous_loop need signal handlers (SIGTERM/SIGINT) that set _running=False and await completion with 10s timeout."},
    {"task_type": "code_improve", "priority": 3, "prompt": "Create /api/system/full-health that aggregates ALL subsystem health: /health + singletons + automation + queue + self-improve into one response with green/yellow/red status."},

    # === P3 — SECURITY ===
    {"task_type": "security", "priority": 3, "prompt": "Audit domino_executor.py for command injection. Lines 156-162 parse URLs from user input. Verify action strings are validated before HTTP requests or subprocess calls."},
    {"task_type": "security", "priority": 3, "prompt": "Add rate limiting to /api/chat (10 req/s) and /api/queue/enqueue (5 req/s). Token bucket per IP. Currently no rate limit."},

    # === P4 — EVOLUTION ===
    {"task_type": "architecture", "priority": 4, "prompt": "Design auto-scaling: when pending > 20, load models on M3. When < 5, unload. Use queue stats + M3 model API."},
    {"task_type": "architecture", "priority": 4, "prompt": "Design task result learning: after 100 tasks, analyze success patterns per node/type. Auto-adjust routing weights from empirical data."},
    {"task_type": "architecture", "priority": 4, "prompt": "Design code quality dashboard: test pass rate, audit metrics (82 long funcs, 34 many-param, 62 undocumented, 19 hardcoded IPs), queue throughput, dispatch reliability. /api/quality/dashboard endpoint."},
    {"task_type": "architecture", "priority": 4, "prompt": "Design self-healing queue watchdog: detect stuck tasks (running > 5min), restart queue processor if unresponsive. 60s check cycle in automation_hub."},
]

enqueued = 0
for t in tasks:
    data = json.dumps(t).encode()
    req = urllib.request.Request(
        "http://127.0.0.1:9742/api/queue/enqueue",
        data=data,
        headers={"Content-Type": "application/json"},
    )
    try:
        urllib.request.urlopen(req, timeout=5)
        enqueued += 1
    except Exception as e:
        print(f"FAIL [{t['task_type']}]: {e}")

print(f"\nWave 4: {enqueued}/{len(tasks)} tasks enqueued")
