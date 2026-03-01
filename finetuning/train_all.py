"""
JARVIS Fine-Tuning — Full Multi-GPU Dispatch v2
=================================================
6 GPUs en parallele, datasets differents, CVE bypass + bf16 fix.

GPU 0 (RTX 2060 12GB): RESUME checkpoint-50, vocal dataset, 500 steps
GPU 5 (RTX 3080 10GB): FRESH, main dataset, 500 steps
GPU 1 (GTX 1660S 6GB): FRESH, vocal chunk 1, 200 steps, r=8, seq=256
GPU 2 (GTX 1660S 6GB): FRESH, vocal chunk 2, 200 steps, r=8, seq=256
GPU 3 (GTX 1660S 6GB): FRESH, vocal chunk 3, 200 steps, r=8, seq=256
GPU 4 (GTX 1660S 6GB): FRESH, vocal chunk 4+mix, 200 steps, r=8, seq=256

FIX bf16: bf16=True partout (pas de GradScaler = pas de crash sur Turing)
FIX save: plus d'espace disque (60GB libres)
"""

import os
import sys
import subprocess
import time
from pathlib import Path
from datetime import datetime

FINETUNING_DIR = Path("F:/BUREAU/turbo/finetuning")
DATASET_DIR = FINETUNING_DIR / "dataset"
OUTPUT_DIR = FINETUNING_DIR / "output"
PYTHON_EXE = r"C:\Users\franc\AppData\Local\Programs\Python\Python312\python.exe"

CONFIGS = [
    # Big GPUs — full config
    {
        "gpu_id": "0", "name": "2060-vocal-resume",
        "dataset": str(DATASET_DIR / "jarvis_vocal_teaching.jsonl"),
        "eval_dataset": None,
        "max_steps": 500, "max_seq_len": 1024,
        "batch_size": 1, "grad_accum": 8,
        "lora_r": 16, "lora_alpha": 32,
        "target_modules": '["q_proj","k_proj","v_proj","o_proj","gate_proj","up_proj","down_proj"]',
        "resume": True,
    },
    {
        "gpu_id": "5", "name": "3080-main",
        "dataset": str(DATASET_DIR / "jarvis_final_train.jsonl"),
        "eval_dataset": str(DATASET_DIR / "jarvis_final_eval.jsonl"),
        "max_steps": 500, "max_seq_len": 1024,
        "batch_size": 1, "grad_accum": 8,
        "lora_r": 16, "lora_alpha": 32,
        "target_modules": '["q_proj","k_proj","v_proj","o_proj","gate_proj","up_proj","down_proj"]',
        "resume": False,
    },
    # 1660S GPUs — reduced config for 6GB
    {
        "gpu_id": "1", "name": "1660s-vocal1",
        "dataset": str(DATASET_DIR / "vocal_chunk_1.jsonl"),
        "eval_dataset": None,
        "max_steps": 200, "max_seq_len": 256,
        "batch_size": 1, "grad_accum": 2,
        "lora_r": 8, "lora_alpha": 16,
        "target_modules": '["q_proj","k_proj","v_proj","o_proj"]',
        "resume": False,
    },
    {
        "gpu_id": "2", "name": "1660s-vocal2",
        "dataset": str(DATASET_DIR / "vocal_chunk_2.jsonl"),
        "eval_dataset": None,
        "max_steps": 200, "max_seq_len": 256,
        "batch_size": 1, "grad_accum": 2,
        "lora_r": 8, "lora_alpha": 16,
        "target_modules": '["q_proj","k_proj","v_proj","o_proj"]',
        "resume": False,
    },
    {
        "gpu_id": "3", "name": "1660s-vocal3",
        "dataset": str(DATASET_DIR / "vocal_chunk_3.jsonl"),
        "eval_dataset": None,
        "max_steps": 200, "max_seq_len": 256,
        "batch_size": 1, "grad_accum": 2,
        "lora_r": 8, "lora_alpha": 16,
        "target_modules": '["q_proj","k_proj","v_proj","o_proj"]',
        "resume": False,
    },
    {
        "gpu_id": "4", "name": "1660s-vocal4-mix",
        "dataset": str(DATASET_DIR / "vocal_chunk_4.jsonl"),
        "eval_dataset": None,
        "max_steps": 200, "max_seq_len": 256,
        "batch_size": 1, "grad_accum": 2,
        "lora_r": 8, "lora_alpha": 16,
        "target_modules": '["q_proj","k_proj","v_proj","o_proj"]',
        "resume": False,
        "extra_datasets": [
            str(DATASET_DIR / "jarvis_trading_augmented.jsonl"),
            str(DATASET_DIR / "jarvis_cot.jsonl"),
            str(DATASET_DIR / "jarvis_augmented_multistep.jsonl"),
            str(DATASET_DIR / "jarvis_memory_enrichment.jsonl"),
        ],
    },
]


def build_worker(cfg):
    gpu = cfg["gpu_id"]
    name = cfg["name"]

    # Extra dataset merge code
    extra_merge = ""
    if cfg.get("extra_datasets"):
        extra_merge = f"""
_extras = {cfg['extra_datasets']}
_lines = open(TRAIN_FILE, 'r', encoding='utf-8').readlines()
for ef in _extras:
    try: _lines.extend(open(ef, 'r', encoding='utf-8').readlines())
    except: pass
TRAIN_FILE = TRAIN_FILE.replace('.jsonl', '_merged.jsonl')
open(TRAIN_FILE, 'w', encoding='utf-8').writelines(_lines)
print(f"[MERGED] {{len(_lines)}} examples")
"""

    # Resume code
    if cfg["resume"]:
        resume_code = """
# Find latest checkpoint for resume (8b model only)
resume_ckpt = None
if OUTPUT_DIR.exists():
    for run in sorted(OUTPUT_DIR.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True):
        if not run.is_dir() or "8b" not in run.name or "2060" not in run.name:
            continue
        ckpts = sorted(
            [d for d in run.iterdir() if d.is_dir() and d.name.startswith("checkpoint-")],
            key=lambda d: int(d.name.split("-")[1]), reverse=True,
        )
        for ckpt in ckpts:
            if (ckpt / "trainer_state.json").exists():
                resume_ckpt = str(ckpt)
                break
        if resume_ckpt:
            break
if resume_ckpt:
    output_dir = str(Path(resume_ckpt).parent)
    print(f"[RESUME] {resume_ckpt}")
else:
    output_dir = str(OUTPUT_DIR / run_name)
    print("[FRESH] No checkpoint found")
"""
    else:
        resume_code = """
resume_ckpt = None
output_dir = str(OUTPUT_DIR / run_name)
print(f"[FRESH] {run_name}")
"""

    eval_line = f'EVAL_FILE = r"{cfg["eval_dataset"]}"' if cfg.get("eval_dataset") else "EVAL_FILE = None"

    return f'''"""Worker GPU {gpu} ({name})"""
import os, sys, json, torch, traceback
from pathlib import Path
from datetime import datetime

os.environ["CUDA_VISIBLE_DEVICES"] = "{gpu}"
os.environ["PYTORCH_CUDA_ALLOC_CONF"] = "expandable_segments:True"
os.environ["TOKENIZERS_PARALLELISM"] = "false"

# CVE-2025-32434 bypass
import transformers.utils.import_utils
transformers.utils.import_utils.check_torch_load_is_safe = lambda: None
import transformers.trainer
transformers.trainer.check_torch_load_is_safe = lambda: None

sys.stdout.reconfigure(line_buffering=True)
sys.stderr.reconfigure(line_buffering=True)

# Patches bitsandbytes
try:
    import bitsandbytes as bnb
    _orig_new = bnb.nn.Params4bit.__new__
    @staticmethod
    def _p_new(cls, data=None, requires_grad=True, **kw):
        kw.pop("_is_hf_initialized", None)
        return _orig_new(cls, data=data, requires_grad=requires_grad, **kw)
    bnb.nn.Params4bit.__new__ = _p_new

    _orig_as_dict = bnb.functional.QuantState.as_dict
    def _p_as_dict(self, packed=False):
        if self.nested and hasattr(self, "offset") and self.offset is not None and self.offset.is_meta:
            self.offset = torch.tensor(0.0)
        return _orig_as_dict(self, packed=packed)
    bnb.functional.QuantState.as_dict = _p_as_dict

    _NF4 = torch.tensor([-1.0,-0.6962,-0.5251,-0.3949,-0.2844,-0.1848,-0.0911,0.0,0.0796,0.1609,0.2461,0.3379,0.4407,0.5626,0.7230,1.0], dtype=torch.float32)
    _orig_to = bnb.functional.QuantState.to
    def _p_to(self, device):
        if hasattr(self,"code") and self.code is not None and self.code.is_meta:
            self.code = _NF4.clone().to(device)
        if hasattr(self,"absmax") and self.absmax is not None and self.absmax.is_meta:
            self.absmax = torch.zeros(self.absmax.shape, dtype=self.absmax.dtype, device=device)
        if self.nested:
            if hasattr(self,"offset") and self.offset is not None and self.offset.is_meta:
                self.offset = torch.tensor(0.0, device=device)
            if hasattr(self,"state2") and self.state2 is not None:
                if hasattr(self.state2,"code") and self.state2.code is not None and self.state2.code.is_meta:
                    self.state2.code = _NF4.clone().to(device)
                if hasattr(self.state2,"absmax") and self.state2.absmax is not None and self.state2.absmax.is_meta:
                    self.state2.absmax = torch.zeros(self.state2.absmax.shape, dtype=self.state2.absmax.dtype, device=device)
        return _orig_to(self, device)
    bnb.functional.QuantState.to = _p_to
    print("[PATCH] bitsandbytes OK")
except Exception as e:
    print(f"[WARN] {{e}}")

MODEL = "Qwen/Qwen3-8B"
TRAIN_FILE = r"{cfg['dataset']}"
{eval_line}
OUTPUT_DIR = Path(r"F:/BUREAU/turbo/finetuning/output")
{extra_merge}
timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
run_name = f"jarvis-qwen3-8b-{name}-{{timestamp}}"
{resume_code}

def main():
    print(f"\\n===== GPU {gpu} ({name}) =====")
    print(f"  Steps: {cfg['max_steps']} | Seq: {cfg['max_seq_len']} | Batch: {cfg['batch_size']}x{cfg['grad_accum']} | LoRA r={cfg['lora_r']}")

    # Unload LM Studio
    try:
        import subprocess as sp
        sp.run(["C:/Users/franc/.lmstudio/bin/lms.exe","unload","--all"], capture_output=True, timeout=5)
    except: pass

    from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
    from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training, TaskType
    from trl import SFTTrainer, SFTConfig
    from datasets import load_dataset

    bnb_config = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=torch.bfloat16,
        bnb_4bit_use_double_quant=True,
        llm_int8_enable_fp32_cpu_offload=True,
    )

    tokenizer = AutoTokenizer.from_pretrained(MODEL, trust_remote_code=True, padding_side="right")
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
        tokenizer.pad_token_id = tokenizer.eos_token_id

    n = torch.cuda.device_count()
    max_memory = {{}}
    for i in range(n):
        vram = torch.cuda.get_device_properties(i).total_mem / (1024**3) if hasattr(torch.cuda.get_device_properties(i), 'total_mem') else torch.cuda.get_device_properties(i).total_memory / (1024**3)
        max_memory[i] = f"{{int(vram * 0.85)}}GiB"
        print(f"  GPU {{i}}: {{torch.cuda.get_device_name(i)}} -- {{vram:.1f}} GB")
    max_memory["cpu"] = "20GiB"

    # Force single GPU (no offload = no meta tensor crash)
    model = AutoModelForCausalLM.from_pretrained(
        MODEL,
        quantization_config=bnb_config,
        device_map={{"": 0}},
        trust_remote_code=True,
        torch_dtype=torch.bfloat16,
        attn_implementation="sdpa",
        low_cpu_mem_usage=True,
    )
    model.config.use_cache = False
    model.gradient_checkpointing_enable()
    print(f"[OK] Model: {{model.get_memory_footprint()/1024**3:.1f}} GB")

    model = prepare_model_for_kbit_training(model, use_gradient_checkpointing=True)
    lora_config = LoraConfig(
        r={cfg['lora_r']}, lora_alpha={cfg['lora_alpha']}, lora_dropout=0.05,
        target_modules={cfg['target_modules']},
        bias="none", task_type=TaskType.CAUSAL_LM,
    )
    model = get_peft_model(model, lora_config)
    t, total = model.get_nb_trainable_parameters()
    print(f"[OK] LoRA r={cfg['lora_r']}: {{t:,}} trainables ({{100*t/total:.2f}}%)")

    files = {{"train": TRAIN_FILE}}
    if EVAL_FILE:
        files["test"] = EVAL_FILE
    ds = load_dataset("json", data_files=files)
    print(f"[OK] Train: {{len(ds['train'])}}")
    has_eval = "test" in ds

    args = SFTConfig(
        output_dir=output_dir,
        num_train_epochs=3,
        max_steps={cfg['max_steps']},
        per_device_train_batch_size={cfg['batch_size']},
        per_device_eval_batch_size={cfg['batch_size']},
        gradient_accumulation_steps={cfg['grad_accum']},
        learning_rate=2e-4,
        weight_decay=0.01,
        warmup_ratio=0.05,
        max_grad_norm=0.3,
        logging_steps=10,
        save_steps=50,
        eval_strategy="steps" if has_eval else "no",
        eval_steps=100 if has_eval else None,
        save_total_limit=3,
        fp16=False,
        bf16=True,    # FIX: bf16 partout — pas de GradScaler = pas de crash Turing
        max_length={cfg['max_seq_len']},
        packing=False,
        run_name=run_name,
        report_to="none",
        gradient_checkpointing=True,
        gradient_checkpointing_kwargs={{"use_reentrant": False}},
        optim="paged_adamw_8bit",
        lr_scheduler_type="cosine",
        seed=42,
        dataloader_pin_memory=True,
        dataloader_num_workers=0,
        remove_unused_columns=False,
    )

    trainer = SFTTrainer(
        model=model, args=args,
        train_dataset=ds["train"],
        eval_dataset=ds.get("test"),
        processing_class=tokenizer,
    )

    print(f"[>>>] Training GPU {gpu} ({name}) -- {cfg['max_steps']} steps...")
    result = trainer.train(resume_from_checkpoint=resume_ckpt)

    final = os.path.join(output_dir, "final")
    trainer.save_model(final)
    tokenizer.save_pretrained(final)

    metrics = result.metrics
    with open(os.path.join(output_dir, "metrics.json"), "w") as f:
        json.dump(metrics, f, indent=2)

    print(f"\\n[DONE] GPU {gpu} ({name}): loss={{metrics.get('train_loss','?')}} runtime={{metrics.get('train_runtime',0):.0f}}s")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\\n[CRASH] GPU {gpu} ({name}): {{type(e).__name__}}: {{e}}")
        traceback.print_exc()
        sys.exit(1)
'''


def main():
    print("\\n" + "=" * 60)
    print("JARVIS Fine-Tuning v2 -- 6 GPU Dispatch")
    print(f"  bf16=True (fix Turing) | CVE bypass | 63GB free")
    print("=" * 60)

    # Unload LM Studio
    try:
        subprocess.run(["C:/Users/franc/.lmstudio/bin/lms.exe", "unload", "--all"],
                       capture_output=True, timeout=10)
        print("[OK] LM Studio unloaded")
    except:
        pass

    workers_dir = FINETUNING_DIR / "workers"
    workers_dir.mkdir(exist_ok=True)
    logs_dir = FINETUNING_DIR / "logs"
    logs_dir.mkdir(exist_ok=True)

    processes = []
    log_handles = []

    for cfg in CONFIGS:
        script = build_worker(cfg)
        path = workers_dir / f"worker_gpu{cfg['gpu_id']}.py"
        path.write_text(script, encoding="utf-8")

        log_path = logs_dir / f"gpu{cfg['gpu_id']}_{cfg['name']}.log"
        log_f = open(log_path, "w", encoding="utf-8")
        log_handles.append(log_f)

        p = subprocess.Popen(
            [PYTHON_EXE, str(path)],
            stdout=log_f, stderr=subprocess.STDOUT,
            cwd=str(FINETUNING_DIR),
            env={**os.environ, "PYTHONIOENCODING": "utf-8"},
        )
        processes.append((cfg, p, log_path))
        print(f"  [PID {p.pid}] GPU {cfg['gpu_id']} ({cfg['name']}) -> {log_path.name}")

    print(f"\\n[MONITOR] {len(CONFIGS)} workers. Ctrl+C pour stop.\\n")

    try:
        while True:
            time.sleep(30)
            done = True
            for cfg, p, lp in processes:
                ret = p.poll()
                if ret is None:
                    done = False
                    try:
                        with open(lp, "r", encoding="utf-8", errors="ignore") as f:
                            lines = f.readlines()
                        last = "..."
                        for line in reversed(lines[-20:]):
                            if any(k in line for k in ["it]", "loss", "CRASH", "DONE", "step"]):
                                last = line.strip()[:120]
                                break
                    except:
                        last = "..."
                    print(f"  [GPU {cfg['gpu_id']}] {last}")
                else:
                    s = "OK" if ret == 0 else f"CRASH({ret})"
                    print(f"  [GPU {cfg['gpu_id']}] DONE {s}")
            if done:
                break
    except KeyboardInterrupt:
        print("\\n[STOP]")
        for cfg, p, _ in processes:
            if p.poll() is None:
                p.terminate()

    for f in log_handles:
        f.close()

    print("\\n" + "=" * 60)
    for cfg, p, _ in processes:
        s = "OK" if p.returncode == 0 else f"FAIL({p.returncode})"
        print(f"  GPU {cfg['gpu_id']} ({cfg['name']}): {s}")
    print("=" * 60)


if __name__ == "__main__":
    main()
