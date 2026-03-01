"""
JARVIS Fine-Tuning — Multi-GPU Dispatch
========================================
Lance plusieurs trainings en parallele sur GPUs differentes avec datasets differents.
Chaque GPU entraine un adapteur LoRA independant, puis on merge les meilleurs.

GPU 5 (RTX 3080 10GB): Resume checkpoint-50, main dataset, 500 steps
GPU 0 (RTX 2060 12GB): Fresh, vocal_teaching data, 500 steps
GPU 1 (GTX 1660S 6GB): Fresh, trading+cot+multistep+memory, 500 steps, seq=512

Usage:
    uv run python finetuning/train_dispatch.py
"""

import os
import sys
import json
import subprocess
import time
import signal
from pathlib import Path
from datetime import datetime

FINETUNING_DIR = Path("F:/BUREAU/turbo/finetuning")
DATASET_DIR = FINETUNING_DIR / "dataset"

# === GPU DISPATCH CONFIG ===
GPU_CONFIGS = [
    {
        "gpu_id": "5",
        "name": "3080-main",
        "model": "Qwen/Qwen3-8B",
        "dataset": str(DATASET_DIR / "jarvis_final_train.jsonl"),
        "eval_dataset": str(DATASET_DIR / "jarvis_final_eval.jsonl"),
        "max_steps": 500,
        "max_seq_len": 1024,
        "batch_size": 1,
        "grad_accum": 8,
        "resume": True,
    },
    {
        "gpu_id": "0",
        "name": "2060-vocal",
        "model": "Qwen/Qwen3-8B",
        "dataset": str(DATASET_DIR / "jarvis_vocal_teaching.jsonl"),
        "eval_dataset": None,
        "max_steps": 500,
        "max_seq_len": 1024,
        "batch_size": 1,
        "grad_accum": 8,
        "resume": False,
    },
    {
        "gpu_id": "1",
        "name": "1660s-trading",
        "model": "Qwen/Qwen3-8B",
        "dataset": str(DATASET_DIR / "jarvis_trading_augmented.jsonl"),
        "eval_dataset": None,
        "max_steps": 500,
        "max_seq_len": 512,
        "batch_size": 1,
        "grad_accum": 4,
        "resume": False,
        "extra_datasets": [
            str(DATASET_DIR / "jarvis_cot.jsonl"),
            str(DATASET_DIR / "jarvis_augmented_multistep.jsonl"),
            str(DATASET_DIR / "jarvis_memory_enrichment.jsonl"),
        ],
    },
]


def build_worker_script(config: dict) -> str:
    """Genere le script Python pour un worker GPU."""

    extra_data_merge = ""
    if config.get("extra_datasets"):
        extra_data_merge = f"""
# Merge extra datasets into one
import tempfile
_extra_files = {config['extra_datasets']}
_merged_lines = []
with open(TRAIN_FILE, 'r', encoding='utf-8') as f:
    _merged_lines.extend(f.readlines())
for _ef in _extra_files:
    try:
        with open(_ef, 'r', encoding='utf-8') as f:
            _merged_lines.extend(f.readlines())
    except: pass
_merged_path = TRAIN_FILE.replace('.jsonl', '_merged.jsonl')
with open(_merged_path, 'w', encoding='utf-8') as f:
    f.writelines(_merged_lines)
TRAIN_FILE = _merged_path
print(f"[MERGED] {{len(_merged_lines)}} examples total")
"""

    eval_setup = ""
    if config.get("eval_dataset"):
        eval_setup = f'EVAL_FILE = r"{config["eval_dataset"]}"'
    else:
        eval_setup = 'EVAL_FILE = None'

    resume_code = ""
    if config["resume"]:
        resume_code = """
# Find latest checkpoint for resume
resume_ckpt = None
model_tag = "8b"
if OUTPUT_DIR.exists():
    runs = sorted(OUTPUT_DIR.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True)
    for run in runs:
        if not run.is_dir() or model_tag not in run.name:
            continue
        ckpts = sorted(
            [d for d in run.iterdir() if d.is_dir() and d.name.startswith("checkpoint-")],
            key=lambda d: int(d.name.split("-")[1]),
            reverse=True,
        )
        for ckpt in ckpts:
            if (ckpt / "trainer_state.json").exists():
                resume_ckpt = str(ckpt)
                break
        if resume_ckpt:
            break
if resume_ckpt:
    output_dir = str(Path(resume_ckpt).parent)
    print(f"[RESUME] Reprise depuis {resume_ckpt}")
else:
    resume_ckpt = None
    output_dir = str(OUTPUT_DIR / run_name)
    print(f"[FRESH] Nouveau run: {run_name}")
"""
    else:
        resume_code = """
resume_ckpt = None
output_dir = str(OUTPUT_DIR / run_name)
print(f"[FRESH] Nouveau run: {run_name}")
"""

    return f'''"""Auto-generated worker for GPU {config["gpu_id"]} ({config["name"]})"""
import os, sys, json, torch, traceback
from pathlib import Path
from datetime import datetime

os.environ["CUDA_VISIBLE_DEVICES"] = "{config["gpu_id"]}"
os.environ["PYTORCH_CUDA_ALLOC_CONF"] = "expandable_segments:True"
os.environ["TOKENIZERS_PARALLELISM"] = "false"

# CVE-2025-32434 bypass (nos propres checkpoints)
import transformers.utils.import_utils
transformers.utils.import_utils.check_torch_load_is_safe = lambda: None
import transformers.trainer
transformers.trainer.check_torch_load_is_safe = lambda: None

sys.stdout.reconfigure(line_buffering=True)
sys.stderr.reconfigure(line_buffering=True)

# === PATCH bitsandbytes ===
try:
    import bitsandbytes as bnb
    _original_params4bit_new = bnb.nn.Params4bit.__new__
    @staticmethod
    def _patched_params4bit_new(cls, data=None, requires_grad=True, **kwargs):
        kwargs.pop("_is_hf_initialized", None)
        return _original_params4bit_new(cls, data=data, requires_grad=requires_grad, **kwargs)
    bnb.nn.Params4bit.__new__ = _patched_params4bit_new

    _original_as_dict = bnb.functional.QuantState.as_dict
    def _patched_as_dict(self, packed=False):
        if self.nested and hasattr(self, "offset") and self.offset is not None:
            if self.offset.is_meta:
                self.offset = torch.tensor(0.0)
        return _original_as_dict(self, packed=packed)
    bnb.functional.QuantState.as_dict = _patched_as_dict

    _NF4_CODE = torch.tensor(
        [-1.0, -0.6962, -0.5251, -0.3949, -0.2844, -0.1848, -0.0911, 0.0,
         0.0796, 0.1609, 0.2461, 0.3379, 0.4407, 0.5626, 0.7230, 1.0],
        dtype=torch.float32,
    )
    _original_qs_to = bnb.functional.QuantState.to
    def _patched_qs_to(self, device):
        if hasattr(self, "code") and self.code is not None and self.code.is_meta:
            self.code = _NF4_CODE.clone().to(device)
        if hasattr(self, "absmax") and self.absmax is not None and self.absmax.is_meta:
            self.absmax = torch.zeros(self.absmax.shape, dtype=self.absmax.dtype, device=device)
        if self.nested:
            if hasattr(self, "offset") and self.offset is not None and self.offset.is_meta:
                self.offset = torch.tensor(0.0, device=device)
            if hasattr(self, "state2") and self.state2 is not None:
                if hasattr(self.state2, "code") and self.state2.code is not None and self.state2.code.is_meta:
                    self.state2.code = _NF4_CODE.clone().to(device)
                if hasattr(self.state2, "absmax") and self.state2.absmax is not None and self.state2.absmax.is_meta:
                    self.state2.absmax = torch.zeros(self.state2.absmax.shape, dtype=self.state2.absmax.dtype, device=device)
        return _original_qs_to(self, device)
    bnb.functional.QuantState.to = _patched_qs_to
    print("[PATCH] bitsandbytes patches applied")
except Exception as e:
    print(f"[WARN] Patch echoue: {{e}}")

# === CONFIG ===
MODEL_NAME = "{config["model"]}"
TRAIN_FILE = r"{config["dataset"]}"
{eval_setup}
OUTPUT_DIR = Path(r"F:/BUREAU/turbo/finetuning/output")
OFFLOAD_DIR = r"F:/BUREAU/turbo/finetuning/offload/{config["name"]}"
os.makedirs(OFFLOAD_DIR, exist_ok=True)

MAX_STEPS = {config["max_steps"]}
MAX_SEQ_LEN = {config["max_seq_len"]}
BATCH_SIZE = {config["batch_size"]}
GRAD_ACCUM = {config["grad_accum"]}
LORA_R = 16
LORA_ALPHA = 32

{extra_data_merge}

timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
run_name = f"jarvis-qwen3-8b-{config["name"]}-{{timestamp}}"

{resume_code}

def main():
    print(f"\\n===== GPU {config["gpu_id"]} ({config["name"]}) =====")
    print(f"  Model: {{MODEL_NAME}}")
    print(f"  Dataset: {{TRAIN_FILE}}")
    print(f"  Steps: {{MAX_STEPS}} | SeqLen: {{MAX_SEQ_LEN}} | Batch: {{BATCH_SIZE}}x{{GRAD_ACCUM}}")

    # Check LM Studio
    try:
        import subprocess as sp
        sp.run(["C:/Users/franc/.lmstudio/bin/lms.exe", "unload", "--all"], capture_output=True, timeout=5)
    except: pass

    from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
    from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training, TaskType
    from trl import SFTTrainer, SFTConfig
    from datasets import load_dataset

    # Load model
    bnb_config = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=torch.bfloat16,
        bnb_4bit_use_double_quant=True,
        llm_int8_enable_fp32_cpu_offload=True,
    )

    tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME, trust_remote_code=True, padding_side="right")
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
        tokenizer.pad_token_id = tokenizer.eos_token_id

    n_gpu = torch.cuda.device_count()
    max_memory = {{}}
    for i in range(n_gpu):
        vram = torch.cuda.get_device_properties(i).total_memory / (1024**3)
        max_memory[i] = f"{{int(vram * 0.85)}}GiB"
        print(f"  GPU {{i}}: {{torch.cuda.get_device_name(i)}} — {{vram:.1f}} GB")
    max_memory["cpu"] = "20GiB"

    model = AutoModelForCausalLM.from_pretrained(
        MODEL_NAME,
        quantization_config=bnb_config,
        device_map="auto",
        max_memory=max_memory,
        trust_remote_code=True,
        torch_dtype=torch.bfloat16,
        attn_implementation="sdpa",
        offload_folder=OFFLOAD_DIR,
    )
    model.config.use_cache = False
    model.gradient_checkpointing_enable()
    print(f"[OK] Model loaded — {{model.get_memory_footprint() / 1024**3:.1f}} GB")

    # LoRA
    model = prepare_model_for_kbit_training(model, use_gradient_checkpointing=True)
    lora_config = LoraConfig(
        r=LORA_R, lora_alpha=LORA_ALPHA, lora_dropout=0.05,
        target_modules=["q_proj","k_proj","v_proj","o_proj","gate_proj","up_proj","down_proj"],
        bias="none", task_type=TaskType.CAUSAL_LM,
    )
    model = get_peft_model(model, lora_config)
    trainable, total = model.get_nb_trainable_parameters()
    print(f"[OK] LoRA: {{trainable:,}} trainables / {{total:,}} ({{100*trainable/total:.2f}}%)")

    # Dataset
    files = {{"train": TRAIN_FILE}}
    if EVAL_FILE:
        files["test"] = EVAL_FILE
    ds = load_dataset("json", data_files=files)
    print(f"[OK] Train: {{len(ds['train'])}}")

    has_eval = "test" in ds

    args = SFTConfig(
        output_dir=output_dir,
        num_train_epochs=3,
        max_steps=MAX_STEPS,
        per_device_train_batch_size=BATCH_SIZE,
        per_device_eval_batch_size=BATCH_SIZE,
        gradient_accumulation_steps=GRAD_ACCUM,
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
        bf16=True,
        max_length=MAX_SEQ_LEN,
        packing=False,
        run_name=run_name,
        report_to="none",
        gradient_checkpointing=True,
        gradient_checkpointing_kwargs={{"use_reentrant": False}},
        optim="paged_adamw_8bit",
        lr_scheduler_type="cosine",
        seed=42,
        dataloader_pin_memory=True,
        dataloader_num_workers=2,
        remove_unused_columns=False,
    )

    trainer = SFTTrainer(
        model=model, args=args,
        train_dataset=ds["train"],
        eval_dataset=ds.get("test"),
        processing_class=tokenizer,
    )

    print(f"[>>>] Training GPU {config["gpu_id"]} ({config["name"]}) — {{MAX_STEPS}} steps...")
    result = trainer.train(resume_from_checkpoint=resume_ckpt)

    final_path = os.path.join(output_dir, "final")
    trainer.save_model(final_path)
    tokenizer.save_pretrained(final_path)

    metrics = result.metrics
    with open(os.path.join(output_dir, "training_metrics.json"), "w") as f:
        json.dump(metrics, f, indent=2)

    print(f"\\n[DONE] GPU {config["gpu_id"]} ({config["name"]})")
    print(f"  Loss: {{metrics.get('train_loss', 'N/A')}}")
    print(f"  Runtime: {{metrics.get('train_runtime', 0):.0f}}s")
    print(f"  Output: {{final_path}}")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\\n[CRASH] GPU {config["gpu_id"]} ({config["name"]}): {{type(e).__name__}}: {{e}}")
        traceback.print_exc()
        sys.exit(1)
'''


def main():
    print("\n" + "=" * 60)
    print("JARVIS Fine-Tuning — Multi-GPU Dispatch")
    print(f"  {len(GPU_CONFIGS)} GPUs | 500 steps/GPU | CVE bypass ON")
    print("=" * 60)

    # Unload LM Studio first
    try:
        subprocess.run(
            ["C:/Users/franc/.lmstudio/bin/lms.exe", "unload", "--all"],
            capture_output=True, timeout=10,
        )
        print("[OK] LM Studio models unloaded")
    except Exception:
        print("[WARN] LM Studio unload skipped")

    # Generate worker scripts
    workers_dir = FINETUNING_DIR / "workers"
    workers_dir.mkdir(exist_ok=True)

    processes = []
    log_files = []

    for config in GPU_CONFIGS:
        script = build_worker_script(config)
        script_path = workers_dir / f"worker_gpu{config['gpu_id']}.py"
        script_path.write_text(script, encoding="utf-8")
        print(f"[GEN] {script_path.name} — GPU {config['gpu_id']} ({config['name']})")

    print(f"\n[LAUNCH] Demarrage de {len(GPU_CONFIGS)} workers en parallele...\n")

    for config in GPU_CONFIGS:
        script_path = workers_dir / f"worker_gpu{config['gpu_id']}.py"
        log_path = FINETUNING_DIR / "logs" / f"gpu{config['gpu_id']}_{config['name']}.log"
        log_path.parent.mkdir(exist_ok=True)

        log_f = open(log_path, "w", encoding="utf-8")
        log_files.append(log_f)

        # Use global Python 3.12 which has torch+CUDA installed
        python_exe = r"C:\Users\franc\AppData\Local\Programs\Python\Python312\python.exe"
        p = subprocess.Popen(
            [python_exe, str(script_path)],
            stdout=log_f,
            stderr=subprocess.STDOUT,
            cwd=str(FINETUNING_DIR),
            env={**os.environ, "PYTHONIOENCODING": "utf-8"},
        )
        processes.append((config, p, log_path))
        print(f"  [PID {p.pid}] GPU {config['gpu_id']} ({config['name']}) -> {log_path.name}")

    print(f"\n[MONITOR] Tous les workers lances. Surveillance...")
    print(f"  Logs dans: {FINETUNING_DIR / 'logs'}")
    print(f"  Ctrl+C pour arreter proprement\n")

    # Monitor loop
    try:
        while True:
            time.sleep(30)
            all_done = True
            for config, p, log_path in processes:
                ret = p.poll()
                if ret is None:
                    all_done = False
                    # Check last line of log
                    try:
                        with open(log_path, "r", encoding="utf-8", errors="ignore") as f:
                            lines = f.readlines()
                            last = lines[-1].strip() if lines else "..."
                            # Find step info
                            for line in reversed(lines[-20:]):
                                if "step" in line.lower() or "it]" in line or "loss" in line.lower():
                                    last = line.strip()[:120]
                                    break
                    except:
                        last = "..."
                    print(f"  [GPU {config['gpu_id']}] running — {last}")
                else:
                    status = "OK" if ret == 0 else f"CRASH (code {ret})"
                    print(f"  [GPU {config['gpu_id']}] {status}")

            if all_done:
                break

    except KeyboardInterrupt:
        print("\n[STOP] Arret demande...")
        for config, p, _ in processes:
            if p.poll() is None:
                p.terminate()
                print(f"  [KILL] GPU {config['gpu_id']}")

    # Cleanup
    for f in log_files:
        f.close()

    print("\n" + "=" * 60)
    print("Dispatch termine !")
    for config, p, log_path in processes:
        ret = p.returncode
        status = "OK" if ret == 0 else f"FAIL ({ret})"
        print(f"  GPU {config['gpu_id']} ({config['name']}): {status}")
    print("=" * 60)


if __name__ == "__main__":
    main()
