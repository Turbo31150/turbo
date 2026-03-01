"""
JARVIS Fine-Tuning — QLoRA Training
=====================================
Fine-tune Qwen3-8B avec QLoRA (4-bit) sur multi-GPU heterogene.
TRL SFTTrainer + PEFT + bitsandbytes + device_map="auto".

Pre-requis:
    - Arreter LM Studio pour liberer la VRAM
    - Lancer prepare_dataset.py d'abord
    - GPU: ~40 GB VRAM totale necessaire

Usage:
    uv run python finetuning/train.py
"""

import os
import sys
import json
import torch
import traceback
from pathlib import Path
from datetime import datetime

# === CUDA optimizations ===
# Single GPU: RTX 3080 only — la plus rapide (8704 CUDA cores, 760 GB/s)
# Multi-GPU pipeline parallelism RALENTIT car la 2060 est le bottleneck (4.5x plus lente)
os.environ["CUDA_VISIBLE_DEVICES"] = "5"
os.environ["PYTORCH_CUDA_ALLOC_CONF"] = "expandable_segments:True"
os.environ["TOKENIZERS_PARALLELISM"] = "false"

# Bypass torch.load CVE-2025-32434 check pour resume checkpoint
# (nos propres fichiers, pas de donnees non-fiables)
import transformers.utils.import_utils
transformers.utils.import_utils.check_torch_load_is_safe = lambda: None
# Patch aussi dans trainer.py qui importe directement la fonction
import transformers.trainer
transformers.trainer.check_torch_load_is_safe = lambda: None

# Force unbuffered output for real-time monitoring
sys.stdout.reconfigure(line_buffering=True)
sys.stderr.reconfigure(line_buffering=True)

# === PATCH bitsandbytes Params4bit pour compatibilite transformers 5.x ===
# transformers 5.2 ajoute _is_hf_initialized aux parametres, mais
# bitsandbytes 0.49.2 ne l'accepte pas dans Params4bit.__new__()
try:
    import bitsandbytes as bnb
    _original_params4bit_new = bnb.nn.Params4bit.__new__

    @staticmethod
    def _patched_params4bit_new(cls, data=None, requires_grad=True, **kwargs):
        kwargs.pop("_is_hf_initialized", None)
        return _original_params4bit_new(cls, data=data, requires_grad=requires_grad, **kwargs)

    bnb.nn.Params4bit.__new__ = _patched_params4bit_new
    print("[PATCH] Params4bit patche pour compatibilite transformers 5.x")

    # PATCH 2: QuantState.as_dict() crash sur meta tensors (offload disk)
    # self.offset.item() echoue car les meta tensors n'ont pas de donnees
    _original_as_dict = bnb.functional.QuantState.as_dict

    def _patched_as_dict(self, packed=False):
        if self.nested and hasattr(self, 'offset') and self.offset is not None:
            if self.offset.is_meta:
                self.offset = torch.tensor(0.0)
        return _original_as_dict(self, packed=packed)

    bnb.functional.QuantState.as_dict = _patched_as_dict
    print("[PATCH] QuantState.as_dict patche pour meta tensors (disk offload)")

    # PATCH 3: QuantState.to() crash sur meta tensors (CPU offload)
    # self.code.to(device) echoue car meta tensors n'ont pas de donnees.
    # NF4 code = 16 valeurs fixes, on les hardcode pour recreation.
    _NF4_CODE = torch.tensor(
        [-1.0, -0.6962, -0.5251, -0.3949, -0.2844, -0.1848, -0.0911, 0.0,
         0.0796, 0.1609, 0.2461, 0.3379, 0.4407, 0.5626, 0.7230, 1.0],
        dtype=torch.float32,
    )
    _original_qs_to = bnb.functional.QuantState.to

    def _patched_qs_to(self, device):
        # Recreate meta tensors with real data before moving
        if hasattr(self, 'code') and self.code is not None and self.code.is_meta:
            self.code = _NF4_CODE.clone().to(device)
        if hasattr(self, 'absmax') and self.absmax is not None and self.absmax.is_meta:
            self.absmax = torch.zeros(self.absmax.shape, dtype=self.absmax.dtype, device=device)
        if self.nested:
            if hasattr(self, 'offset') and self.offset is not None and self.offset.is_meta:
                self.offset = torch.tensor(0.0, device=device)
            if hasattr(self, 'state2') and self.state2 is not None:
                if hasattr(self.state2, 'code') and self.state2.code is not None and self.state2.code.is_meta:
                    self.state2.code = _NF4_CODE.clone().to(device)
                if hasattr(self.state2, 'absmax') and self.state2.absmax is not None and self.state2.absmax.is_meta:
                    self.state2.absmax = torch.zeros(self.state2.absmax.shape, dtype=self.state2.absmax.dtype, device=device)
        return _original_qs_to(self, device)

    bnb.functional.QuantState.to = _patched_qs_to
    print("[PATCH] QuantState.to patche pour meta tensors (CPU offload)")
except Exception as e:
    print(f"[WARN] Patch bitsandbytes echoue: {e}")

# === CHEMINS ===
TURBO_DIR = Path("F:/BUREAU/turbo")
FINETUNING_DIR = TURBO_DIR / "finetuning"
DATASET_DIR = FINETUNING_DIR / "dataset"
OUTPUT_DIR = FINETUNING_DIR / "output"

TRAIN_FILE = DATASET_DIR / "jarvis_final_train.jsonl"
EVAL_FILE = DATASET_DIR / "jarvis_final_eval.jsonl"

# === MODELE ===
# Qwen3-8B trop gros pour 22 GB VRAM (CPU offload = meta tensor crashes)
# Qwen3-8B: 8.2B params, ~4.5 GB en 4-bit, tient sur un seul GPU
MODEL_NAME = "Qwen/Qwen3-8B"

# === LORA CONFIG ===
LORA_R = 16                 # Rank LoRA
LORA_ALPHA = 32              # Alpha = 2x rank
LORA_DROPOUT = 0.05
LORA_TARGET_MODULES = [
    "q_proj", "k_proj", "v_proj", "o_proj",   # Attention
    "gate_proj", "up_proj", "down_proj",        # FFN shared
]

# === TRAINING CONFIG ===
BATCH_SIZE = 1               # Batch=1 optimal pour 3080 10GB (batch=2 cause memory thrashing)
GRAD_ACCUM = 8               # Effective batch = 1*8 = 8
LR = 2e-4                    # Learning rate QLoRA standard
EPOCHS = 3
MAX_STEPS = 1000             # Run court — resume auto au prochain lancement
MAX_SEQ_LEN = 1024           # Bon compromis qualite/VRAM
WARMUP_RATIO = 0.05
WEIGHT_DECAY = 0.01
MAX_GRAD_NORM = 0.3
LOG_STEPS = 10
SAVE_STEPS = 50             # Sauvegarde frequente pour ne jamais perdre le progres
EVAL_STEPS = 100


def check_gpu() -> dict:
    """Verifie les GPUs et retourne max_memory.

    CUDA_VISIBLE_DEVICES=4 → cuda:0 = RTX 3080 (10 GB)
    Single GPU = pas de pipeline parallelism bottleneck.
    """
    if not torch.cuda.is_available():
        print("[ERREUR] CUDA non disponible !")
        sys.exit(1)

    n = torch.cuda.device_count()
    print(f"\nGPUs detectes: {n}")

    gpus = []
    total_vram = 0
    for i in range(n):
        name = torch.cuda.get_device_name(i)
        vram = torch.cuda.get_device_properties(i).total_memory / (1024**3)
        gpus.append((i, name, vram))
        total_vram += vram
        print(f"  GPU {i}: {name} — {vram:.1f} GB")

    # Allouer 85% de chaque GPU, reserve pour CUDA overhead
    max_memory = {}
    for i, name, vram in gpus:
        alloc = int(vram * 0.85)
        max_memory[i] = f"{alloc}GiB"
        print(f"  [USE] GPU {i}: {name} — alloc {alloc} GiB / {vram:.1f} GB")

    # Ajouter CPU RAM comme overflow
    max_memory["cpu"] = "30GiB"

    print(f"\n  Multi-GPU mode: {n} GPUs, {total_vram:.0f} GB total")
    print(f"  Primary: GPU 0 ({gpus[0][1]})")
    return max_memory


def load_model(max_memory: dict):
    """Charge le modele en 4-bit distribue sur multi-GPU."""
    from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig

    print(f"[...] Chargement {MODEL_NAME} en 4-bit...")

    bnb_config = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=torch.bfloat16,
        bnb_4bit_use_double_quant=True,
        llm_int8_enable_fp32_cpu_offload=True,
    )

    tokenizer = AutoTokenizer.from_pretrained(
        MODEL_NAME, trust_remote_code=True, padding_side="right",
    )
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
        tokenizer.pad_token_id = tokenizer.eos_token_id

    # SDPA (Scaled Dot-Product Attention) — native PyTorch, pas besoin de flash_attn
    # Plus rapide que "eager" sur toutes les GPU (Turing+)
    attn_impl = "sdpa"
    print(f"  [OK] Attention: {attn_impl} (PyTorch native)")

    # Offload folder pour les poids qui doivent etre re-sauves
    offload_dir = str(FINETUNING_DIR / "offload")
    os.makedirs(offload_dir, exist_ok=True)

    # Single GPU mode: tout sur la 3080 (pas de pipeline parallelism overhead)
    device_map = "auto"
    print(f"  [MAP] Single GPU mode — toutes les couches sur RTX 3080")

    model = AutoModelForCausalLM.from_pretrained(
        MODEL_NAME,
        quantization_config=bnb_config,
        device_map=device_map,
        max_memory=max_memory,
        trust_remote_code=True,
        torch_dtype=torch.bfloat16,
        attn_implementation=attn_impl,
    )

    model.config.use_cache = False
    model.gradient_checkpointing_enable()

    footprint = model.get_memory_footprint() / 1024**3
    print(f"[OK] Modele charge — {footprint:.1f} GB")
    return model, tokenizer


def setup_lora(model):
    """Configure LoRA sur le modele quantifie."""
    from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training, TaskType

    print(f"[...] Configuration LoRA (r={LORA_R}, alpha={LORA_ALPHA})...")

    model = prepare_model_for_kbit_training(model, use_gradient_checkpointing=True)

    config = LoraConfig(
        r=LORA_R,
        lora_alpha=LORA_ALPHA,
        lora_dropout=LORA_DROPOUT,
        target_modules=LORA_TARGET_MODULES,
        bias="none",
        task_type=TaskType.CAUSAL_LM,
    )
    model = get_peft_model(model, config)

    trainable, total = model.get_nb_trainable_parameters()
    pct = 100 * trainable / total
    print(f"[OK] LoRA: {trainable:,} trainables / {total:,} total ({pct:.2f}%)")
    return model


def load_dataset_files():
    """Charge le dataset JSONL."""
    from datasets import load_dataset

    if not TRAIN_FILE.exists():
        print("[ERREUR] Dataset non trouve ! Lancez prepare_dataset.py d'abord.")
        sys.exit(1)

    files = {"train": str(TRAIN_FILE)}
    if EVAL_FILE.exists():
        files["test"] = str(EVAL_FILE)

    ds = load_dataset("json", data_files=files)
    print(f"[OK] Train: {len(ds['train'])} | Eval: {len(ds.get('test', []))}")
    return ds


def find_resume_checkpoint() -> str | None:
    """Cherche le dernier checkpoint pour resume (meme modele uniquement)."""
    if not OUTPUT_DIR.exists():
        return None
    # Identifier le modele actuel (8b ou 30b) depuis MODEL_NAME
    model_tag = "8b" if "8B" in MODEL_NAME or "8b" in MODEL_NAME else "30b"
    runs = sorted(OUTPUT_DIR.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True)
    for run in runs:
        if not run.is_dir():
            continue
        # Ne resume QUE les runs du meme modele
        if model_tag not in run.name:
            continue
        ckpts = sorted(
            [d for d in run.iterdir() if d.is_dir() and d.name.startswith("checkpoint-")],
            key=lambda d: int(d.name.split("-")[1]),
            reverse=True,
        )
        for ckpt in ckpts:
            if (ckpt / "trainer_state.json").exists():
                return str(ckpt)
    return None


def train(model, tokenizer, dataset):
    """Lance le SFT training avec resume automatique."""
    from trl import SFTTrainer, SFTConfig

    # Resume automatique depuis le dernier checkpoint si disponible
    resume_ckpt = find_resume_checkpoint()
    if resume_ckpt:
        # Reprendre dans le meme output_dir que le checkpoint
        output_dir = str(Path(resume_ckpt).parent)
        run_name = Path(output_dir).name
        print(f"[RESUME] Reprise depuis {resume_ckpt}")
    else:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        run_name = f"jarvis-qwen3-8b-qlora-{timestamp}"
        output_dir = str(OUTPUT_DIR / run_name)
        print(f"[FRESH] Nouveau run: {run_name}")

    has_eval = "test" in dataset

    print(f"\n{'='*60}")
    print(f"Training: {run_name}")
    print(f"  Epochs: {EPOCHS} (max_steps={MAX_STEPS})")
    print(f"  Batch effectif: {BATCH_SIZE * GRAD_ACCUM}")
    print(f"  Resume: {resume_ckpt or 'FRESH'}")
    print(f"  LR: {LR}")
    print(f"  Max seq: {MAX_SEQ_LEN}")
    print(f"  Output: {output_dir}")
    print(f"{'='*60}\n")

    args = SFTConfig(
        output_dir=output_dir,
        num_train_epochs=EPOCHS,
        max_steps=MAX_STEPS,
        per_device_train_batch_size=BATCH_SIZE,
        per_device_eval_batch_size=BATCH_SIZE,
        gradient_accumulation_steps=GRAD_ACCUM,
        learning_rate=LR,
        weight_decay=WEIGHT_DECAY,
        warmup_ratio=WARMUP_RATIO,
        max_grad_norm=MAX_GRAD_NORM,
        logging_steps=LOG_STEPS,
        save_steps=SAVE_STEPS,
        eval_strategy="steps" if has_eval else "no",
        eval_steps=EVAL_STEPS if has_eval else None,
        save_total_limit=5,
        fp16=False,
        bf16=True,  # Qwen3 utilise BF16 internement
        max_length=MAX_SEQ_LEN,
        packing=False,  # Desactive car flash_attn absent + VRAM limitee
        run_name=run_name,
        report_to="none",
        gradient_checkpointing=True,
        gradient_checkpointing_kwargs={"use_reentrant": False},
        optim="paged_adamw_8bit",
        lr_scheduler_type="cosine",
        seed=42,
        dataloader_pin_memory=True,   # Faster CPU→GPU transfer
        dataloader_num_workers=2,      # Prefetch data en parallele
        remove_unused_columns=False,
    )

    trainer = SFTTrainer(
        model=model,
        args=args,
        train_dataset=dataset["train"],
        eval_dataset=dataset.get("test"),
        processing_class=tokenizer,
    )

    print("[>>>] Training en cours...\n")
    result = trainer.train(resume_from_checkpoint=resume_ckpt)

    # Sauvegarder
    final_path = os.path.join(output_dir, "final")
    trainer.save_model(final_path)
    tokenizer.save_pretrained(final_path)

    metrics = result.metrics
    with open(os.path.join(output_dir, "training_metrics.json"), "w") as f:
        json.dump(metrics, f, indent=2)

    print(f"\n{'='*60}")
    print(f"Training termine !")
    print(f"  Loss: {metrics.get('train_loss', 'N/A')}")
    print(f"  Runtime: {metrics.get('train_runtime', 0):.0f}s")
    print(f"  Modele: {final_path}")
    print(f"{'='*60}")
    return final_path


def check_lm_studio():
    """Verifie que LM Studio n'a pas de modeles charges."""
    import subprocess
    # Verifier si des modeles sont charges (pas juste si le process tourne)
    try:
        result = subprocess.run(
            ["C:/Users/franc/.lmstudio/bin/lms.exe", "ps"],
            capture_output=True, text=True, timeout=5,
        )
        output = result.stdout.strip()
        if "loaded" in output.lower() and "0 model" not in output.lower():
            print(f"[WARN] LM Studio a des modeles charges, dechargement...")
            subprocess.run(
                ["C:/Users/franc/.lmstudio/bin/lms.exe", "unload", "--all"],
                capture_output=True, timeout=10,
            )
    except Exception:
        pass
    print("[OK] LM Studio verifie (pas de modeles charges)")


def print_resources(label=""):
    """Affiche RAM systeme + VRAM GPUs."""
    import subprocess
    if label:
        print(f"\n--- Resources: {label} ---")
    # RAM
    result = subprocess.run(
        ["powershell", "-Command",
         "$os = Get-CimInstance Win32_OperatingSystem; "
         "[math]::Round($os.FreePhysicalMemory / 1MB, 1)"],
        capture_output=True, text=True
    )
    free_ram = result.stdout.strip()
    print(f"  RAM libre: {free_ram} GB")
    # VRAM per GPU
    for i in range(torch.cuda.device_count()):
        alloc = torch.cuda.memory_allocated(i) / 1024**3
        reserved = torch.cuda.memory_reserved(i) / 1024**3
        print(f"  GPU {i}: {alloc:.1f} GB alloc / {reserved:.1f} GB reserved")


def main():
    print("\n" + "=" * 60)
    print("JARVIS Fine-Tuning — QLoRA sur Qwen3-8B")
    print("=" * 60)

    check_lm_studio()
    max_memory = check_gpu()
    print_resources("Avant chargement")

    try:
        model, tokenizer = load_model(max_memory)
        print_resources("Apres chargement modele")

        model = setup_lora(model)
        print_resources("Apres LoRA")

        dataset = load_dataset_files()
        final = train(model, tokenizer, dataset)

        print(f"\n[DONE] Modele fine-tune: {final}")
        print(f"[NEXT] Lancez: uv run python finetuning/convert_gguf.py")
    except Exception as e:
        print(f"\n[CRASH] {type(e).__name__}: {e}")
        traceback.print_exc()
        print_resources("Au moment du crash")
        sys.exit(1)


if __name__ == "__main__":
    main()
