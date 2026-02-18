"""
JARVIS Fine-Tuning — Base de donnees memoire
=============================================
Cree et renseigne la DB SQLite qui sauvegarde tout le processus
de fine-tuning: configs, tentatives, erreurs, resultats, modeles.

Usage:
    uv run python finetuning/create_memory_db.py
"""

import sqlite3
import json
from datetime import datetime
from pathlib import Path

DB_PATH = Path("F:/BUREAU/turbo/finetuning/memoire_finetuning.db")


def create_tables(conn: sqlite3.Connection):
    """Cree toutes les tables de la DB."""
    conn.executescript("""
    -- Configuration de chaque run de fine-tuning
    CREATE TABLE IF NOT EXISTS runs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        run_name TEXT NOT NULL,
        model_name TEXT NOT NULL,
        started_at TEXT NOT NULL,
        finished_at TEXT,
        status TEXT DEFAULT 'running',  -- running, completed, failed, cancelled
        config_json TEXT,
        error_message TEXT,
        final_loss REAL,
        runtime_seconds REAL,
        output_dir TEXT,
        notes TEXT
    );

    -- GPU setup pour chaque run
    CREATE TABLE IF NOT EXISTS gpu_configs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        run_id INTEGER REFERENCES runs(id),
        gpu_index INTEGER,
        gpu_name TEXT,
        vram_total_gb REAL,
        vram_allocated_gb REAL,
        max_memory_str TEXT
    );

    -- Dataset utilise pour chaque run
    CREATE TABLE IF NOT EXISTS datasets (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        run_id INTEGER REFERENCES runs(id),
        dataset_type TEXT,  -- train, eval, cot, augmented
        file_path TEXT,
        num_examples INTEGER,
        file_size_mb REAL,
        jarvis_pct REAL,
        generic_pct REAL,
        created_at TEXT
    );

    -- Erreurs rencontrees
    CREATE TABLE IF NOT EXISTS errors (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        run_id INTEGER REFERENCES runs(id),
        error_type TEXT,
        error_message TEXT,
        layer_number INTEGER,
        weight_progress TEXT,
        fix_applied TEXT,
        occurred_at TEXT DEFAULT CURRENT_TIMESTAMP
    );

    -- Metriques de training (logs pendant l'entrainement)
    CREATE TABLE IF NOT EXISTS training_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        run_id INTEGER REFERENCES runs(id),
        step INTEGER,
        epoch REAL,
        loss REAL,
        learning_rate REAL,
        grad_norm REAL,
        vram_used_gb REAL,
        ram_free_gb REAL,
        logged_at TEXT DEFAULT CURRENT_TIMESTAMP
    );

    -- Modeles produits
    CREATE TABLE IF NOT EXISTS models (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        run_id INTEGER REFERENCES runs(id),
        model_type TEXT,  -- lora_adapter, merged, gguf
        file_path TEXT,
        file_size_mb REAL,
        format TEXT,  -- safetensors, gguf, bin
        quantization TEXT,  -- q4_k_m, q5_k_m, q8_0, etc.
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        deployed_to TEXT,  -- lm_studio, ollama
        benchmark_score REAL
    );

    -- Patches et fixes appliques
    CREATE TABLE IF NOT EXISTS patches (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        patch_name TEXT NOT NULL,
        target_library TEXT,
        target_version TEXT,
        description TEXT,
        code_snippet TEXT,
        applied_at TEXT DEFAULT CURRENT_TIMESTAMP,
        still_needed INTEGER DEFAULT 1
    );

    -- Benchmark des modeles LM Studio
    CREATE TABLE IF NOT EXISTS model_benchmarks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        model_name TEXT NOT NULL,
        category TEXT,  -- general, code, reasoning, vision
        prompt TEXT,
        response_time_s REAL,
        tokens_generated INTEGER,
        tokens_per_second REAL,
        vram_used_mb REAL,
        response_preview TEXT,
        tested_at TEXT DEFAULT CURRENT_TIMESTAMP
    );
    """)
    conn.commit()


def populate_initial_data(conn: sqlite3.Connection):
    """Renseigne les donnees du processus actuel."""

    # === Patches appliques ===
    patches = [
        {
            "patch_name": "Params4bit.__new__ patch",
            "target_library": "bitsandbytes",
            "target_version": "0.49.2",
            "description": "transformers 5.2 ajoute _is_hf_initialized aux kwargs, "
                          "bitsandbytes 0.49.2 ne l'accepte pas dans Params4bit.__new__()",
            "code_snippet": """@staticmethod
def _patched_params4bit_new(cls, data=None, requires_grad=True, **kwargs):
    kwargs.pop("_is_hf_initialized", None)
    return _original_params4bit_new(cls, data=data, requires_grad=requires_grad, **kwargs)""",
        },
        {
            "patch_name": "QuantState.as_dict meta tensor patch",
            "target_library": "bitsandbytes",
            "target_version": "0.49.2",
            "description": "Les meta tensors (offload disk) causent RuntimeError "
                          "dans QuantState.as_dict() quand bitsandbytes appelle .item() "
                          "sur self.offset",
            "code_snippet": """def _patched_as_dict(self, packed=False):
    if self.nested and hasattr(self, 'offset') and self.offset is not None:
        if self.offset.is_meta:
            self.offset = torch.tensor(0.0)
    return _original_as_dict(self, packed=packed)""",
        },
    ]
    for p in patches:
        conn.execute(
            "INSERT INTO patches (patch_name, target_library, target_version, description, code_snippet) "
            "VALUES (?, ?, ?, ?, ?)",
            (p["patch_name"], p["target_library"], p["target_version"],
             p["description"], p["code_snippet"])
        )

    # === Erreurs rencontrees ===
    errors = [
        {
            "error_type": "ImportError",
            "error_message": "flash_attn not installed",
            "layer_number": None,
            "weight_progress": "0/531",
            "fix_applied": "try: import flash_attn guard before enabling flash_attention_2",
        },
        {
            "error_type": "ValueError",
            "error_message": "Some modules dispatched on CPU or disk (sans llm_int8_enable_fp32_cpu_offload)",
            "layer_number": None,
            "weight_progress": "0/531",
            "fix_applied": "Ajoute llm_int8_enable_fp32_cpu_offload=True dans BitsAndBytesConfig",
        },
        {
            "error_type": "SilentCrash_OOM",
            "error_message": "Processus tue silencieusement pendant chargement (LM Studio occupait la VRAM)",
            "layer_number": 43,
            "weight_progress": "483/531 (91%)",
            "fix_applied": "Arreter LM Studio (15 GB VRAM) + desactiver auto-start registre",
        },
        {
            "error_type": "TypeError",
            "error_message": "Params4bit.__new__() got unexpected keyword argument '_is_hf_initialized'",
            "layer_number": 43,
            "weight_progress": "483/531 (91%)",
            "fix_applied": "Monkey-patch Params4bit.__new__ pour ignorer _is_hf_initialized",
        },
        {
            "error_type": "ValueError",
            "error_message": "MoE weights need offload_folder for re-saving (device_map offloaded to disk)",
            "layer_number": None,
            "weight_progress": "~370/531 (69%)",
            "fix_applied": "Ajoute offload_folder + reduit max_memory CPU a 8GiB",
        },
        {
            "error_type": "RuntimeError",
            "error_message": "Tensor.item() cannot be called on meta tensors (QuantState.as_dict)",
            "layer_number": None,
            "weight_progress": "531/531 (100% charge, crash au LoRA setup)",
            "fix_applied": "Monkey-patch QuantState.as_dict pour remplacer meta offset par tensor(0.0)",
        },
    ]
    for e in errors:
        conn.execute(
            "INSERT INTO errors (error_type, error_message, layer_number, weight_progress, fix_applied) "
            "VALUES (?, ?, ?, ?, ?)",
            (e["error_type"], e["error_message"], e["layer_number"],
             e["weight_progress"], e["fix_applied"])
        )

    # === Run actuel ===
    config = {
        "model": "Qwen/Qwen3-30B-A3B",
        "quantization": "NF4 + double quant",
        "lora_r": 16,
        "lora_alpha": 32,
        "lora_dropout": 0.05,
        "lora_targets": ["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"],
        "batch_size": 1,
        "grad_accum": 8,
        "effective_batch": 8,
        "lr": 2e-4,
        "epochs": 3,
        "max_seq_len": 2048,
        "optimizer": "paged_adamw_8bit",
        "scheduler": "cosine",
        "warmup_ratio": 0.05,
        "packing": True,
        "gradient_checkpointing": True,
        "fp16": True,
        "cuda_alloc_conf": "expandable_segments:True",
        "offload_folder": "F:/BUREAU/turbo/finetuning/offload",
        "offload_state_dict": True,
    }

    conn.execute(
        "INSERT INTO runs (run_name, model_name, started_at, status, config_json, notes) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        ("jarvis-qwen3-30b-qlora-20260218",
         "Qwen/Qwen3-30B-A3B",
         "2026-02-18T03:21:00",
         "running",
         json.dumps(config, indent=2),
         "Premier run reussi apres 7 tentatives. LM Studio auto-start desactive.")
    )
    run_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    # === GPU configs ===
    gpus = [
        (0, "NVIDIA GeForce RTX 2060", 12.0, 10.0, "10GiB"),
        (1, "NVIDIA GeForce GTX 1660 SUPER", 6.0, 5.0, "5GiB"),
        (2, "NVIDIA GeForce GTX 1660 SUPER", 6.0, 5.0, "5GiB"),
        (3, "NVIDIA GeForce GTX 1660 SUPER", 6.0, 5.0, "5GiB"),
        (4, "NVIDIA GeForce RTX 3080", 10.0, 8.0, "8GiB"),
    ]
    for idx, name, total, alloc, mem_str in gpus:
        conn.execute(
            "INSERT INTO gpu_configs (run_id, gpu_index, gpu_name, vram_total_gb, vram_allocated_gb, max_memory_str) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (run_id, idx, name, total, alloc, mem_str)
        )

    # === Datasets ===
    datasets = [
        ("train", "dataset/jarvis_final_train.jsonl", 44708, None, 55.3, 44.7),
        ("eval", "dataset/jarvis_final_eval.jsonl", 2845, None, None, None),
        ("cot", "dataset/jarvis_cot.jsonl", 26, None, 100.0, 0.0),
        ("augmented_multistep", "dataset/jarvis_augmented_multistep.jsonl", 50, None, 100.0, 0.0),
        ("trading_augmented", "dataset/jarvis_trading_augmented.jsonl", 100, None, 100.0, 0.0),
        ("original_train", "dataset/jarvis_finetune_train.jsonl", 54096, None, None, None),
        ("original_eval", "dataset/jarvis_finetune_eval.jsonl", 2843, None, None, None),
    ]
    for ds_type, fpath, num, size, jpct, gpct in datasets:
        full_path = f"F:/BUREAU/turbo/finetuning/{fpath}"
        file_size = None
        try:
            file_size = round(Path(full_path).stat().st_size / (1024 * 1024), 2)
        except Exception:
            pass
        conn.execute(
            "INSERT INTO datasets (run_id, dataset_type, file_path, num_examples, file_size_mb, jarvis_pct, generic_pct, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (run_id, ds_type, full_path, num, file_size or size, jpct, gpct,
             datetime.now().isoformat())
        )

    # === Modeles disponibles sur disque ===
    lm_models = [
        ("Qwen3-30B-A3B-Instruct-2507", "general", "18GB"),
        ("Qwen3-Coder-30B-A3B-Instruct", "code", "18GB"),
        ("gpt-oss-20b", "general", "12GB"),
        ("gpt-oss-120b", "general", "70GB"),
        ("Devstral-Small-2-24B-Instruct-2512", "code", "14GB"),
        ("DeepSeek-R1-0528-Qwen3-8B", "reasoning", "5GB"),
        ("gemma-3-12b-it", "general", "7GB"),
        ("Ministral-3-14B-Reasoning-2512", "reasoning", "8GB"),
        ("Qwen3-VL-8B-Instruct", "vision", "5GB"),
        ("GLM-4.6V-Flash", "vision", "5GB"),
        ("GLM-4.7-Flash", "general", "5GB"),
        ("Llama-3.2-1B-Instruct-Q8_0", "general", "1GB"),
        ("Qwen2.5-0.5B-Instruct", "general", "0.5GB"),
        ("LFM2.5-1.2B-Instruct", "general", "1GB"),
        ("NVIDIA-Nemotron-3-Nano-30B-A3B", "general", "18GB"),
    ]
    for name, cat, vram in lm_models:
        conn.execute(
            "INSERT INTO model_benchmarks (model_name, category, prompt, response_time_s, tokens_per_second) "
            "VALUES (?, ?, ?, NULL, NULL)",
            (name, cat, f"Disponible sur disque ({vram})")
        )

    conn.commit()
    return run_id


def main():
    print(f"[...] Creation de la DB: {DB_PATH}")
    conn = sqlite3.connect(str(DB_PATH))
    create_tables(conn)
    run_id = populate_initial_data(conn)

    # Stats
    tables = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
    ).fetchall()
    print(f"\n[OK] Base de donnees creee avec {len(tables)} tables:")
    for (t,) in tables:
        count = conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
        print(f"  {t}: {count} enregistrements")

    print(f"\n[OK] Run actuel: ID {run_id}")
    print(f"[OK] DB: {DB_PATH}")
    conn.close()


if __name__ == "__main__":
    main()
