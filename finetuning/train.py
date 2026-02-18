"""
JARVIS Fine-Tuning — QLoRA Training
=====================================
Fine-tune Qwen3-30B-A3B avec QLoRA (4-bit) sur multi-GPU heterogene.
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
os.environ["PYTORCH_CUDA_ALLOC_CONF"] = "expandable_segments:True"
os.environ["TOKENIZERS_PARALLELISM"] = "false"

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
MODEL_NAME = "Qwen/Qwen3-30B-A3B"

# === LORA CONFIG ===
LORA_R = 16                 # Rank LoRA
LORA_ALPHA = 32              # Alpha = 2x rank
LORA_DROPOUT = 0.05
LORA_TARGET_MODULES = [
    "q_proj", "k_proj", "v_proj", "o_proj",   # Attention
    "gate_proj", "up_proj", "down_proj",        # FFN shared
]

# === TRAINING CONFIG ===
BATCH_SIZE = 1               # Micro batch (limite VRAM)
GRAD_ACCUM = 8               # Effective batch = 8
LR = 2e-4                    # Learning rate QLoRA standard
EPOCHS = 3
MAX_SEQ_LEN = 2048           # Longueur max sequences
WARMUP_RATIO = 0.05
WEIGHT_DECAY = 0.01
MAX_GRAD_NORM = 0.3
LOG_STEPS = 10
SAVE_STEPS = 200
EVAL_STEPS = 200


def check_gpu() -> dict:
    """Verifie les GPUs et retourne max_memory pour les 2 plus gros GPUs.

    Strategie: n'utiliser que les GPUs avec >= 10 GB VRAM pour eviter
    les problemes de fragmentation VRAM avec bitsandbytes 4-bit.
    Les petits GPUs (GTX 1660 Super, 6GB) causent des crashes.
    """
    if not torch.cuda.is_available():
        print("[ERREUR] CUDA non disponible !")
        sys.exit(1)

    n = torch.cuda.device_count()
    print(f"\nGPUs detectes: {n}")

    # Lister tous les GPUs
    gpus = []
    for i in range(n):
        name = torch.cuda.get_device_name(i)
        vram = torch.cuda.get_device_properties(i).total_memory / (1024**3)
        gpus.append((i, name, vram))
        print(f"  GPU {i}: {name} — {vram:.1f} GB")

    # IMPORTANT: Exclure les petits GPUs (< 10 GB) — causent fragmentation
    # et OOM. Garder aussi de la VRAM libre sur le GPU d'affichage (3080)
    # pour eviter de perdre le bureau Windows.
    MIN_VRAM_GB = 10.0
    max_memory = {}
    total_used = 0.0
    for i, name, vram in gpus:
        if vram < MIN_VRAM_GB:
            print(f"  [SKIP] GPU {i}: {name} — {vram:.1f} GB (< {MIN_VRAM_GB} GB)")
            continue
        # GPU d'affichage (3080) = 55% pour laisser Windows respirer
        # Autres GPUs (2060 12GB) = 85%
        if "3080" in name:
            factor = 0.55
        else:
            factor = 0.85
        alloc = max(int(vram * factor), 1)
        max_memory[i] = f"{alloc}GiB"
        total_used += vram
        print(f"  [USE] GPU {i}: {name} — {vram:.1f} GB (alloc: {alloc} GiB)")

    if not max_memory:
        print("[ERREUR] Aucun GPU avec >= 10 GB VRAM !")
        sys.exit(1)

    max_memory["cpu"] = "24GiB"
    print(f"  VRAM utilisee: {total_used:.1f} GB | CPU offload: 24 GiB\n")
    return max_memory


def load_model(max_memory: dict):
    """Charge le modele en 4-bit distribue sur multi-GPU."""
    from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig

    print(f"[...] Chargement {MODEL_NAME} en 4-bit...")

    bnb_config = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=torch.float16,
        bnb_4bit_use_double_quant=True,
        llm_int8_enable_fp32_cpu_offload=True,
    )

    tokenizer = AutoTokenizer.from_pretrained(
        MODEL_NAME, trust_remote_code=True, padding_side="right",
    )
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
        tokenizer.pad_token_id = tokenizer.eos_token_id

    # Flash attention 2: seulement si le package est installe ET GPU capable
    use_fa2 = False
    try:
        import flash_attn  # noqa: F401
        for i in range(torch.cuda.device_count()):
            if torch.cuda.get_device_capability(i)[0] >= 8:
                use_fa2 = True
                break
        if use_fa2:
            print("  [OK] Flash Attention 2 active")
    except ImportError:
        print("  [INFO] flash_attn non installe, utilisation de 'eager' attention")

    # Offload folder pour les poids MoE qui doivent etre re-sauves
    offload_dir = str(FINETUNING_DIR / "offload")
    os.makedirs(offload_dir, exist_ok=True)

    model = AutoModelForCausalLM.from_pretrained(
        MODEL_NAME,
        quantization_config=bnb_config,
        device_map="auto",
        max_memory=max_memory,
        trust_remote_code=True,
        torch_dtype=torch.float16,
        attn_implementation="flash_attention_2" if use_fa2 else "eager",
        offload_folder=offload_dir,
        offload_state_dict=True,
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


def train(model, tokenizer, dataset):
    """Lance le SFT training."""
    from trl import SFTTrainer, SFTConfig

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_name = f"jarvis-qwen3-30b-qlora-{timestamp}"
    output_dir = str(OUTPUT_DIR / run_name)

    has_eval = "test" in dataset

    print(f"\n{'='*60}")
    print(f"Training: {run_name}")
    print(f"  Epochs: {EPOCHS}")
    print(f"  Batch effectif: {BATCH_SIZE * GRAD_ACCUM}")
    print(f"  LR: {LR}")
    print(f"  Max seq: {MAX_SEQ_LEN}")
    print(f"  Output: {output_dir}")
    print(f"{'='*60}\n")

    args = SFTConfig(
        output_dir=output_dir,
        num_train_epochs=EPOCHS,
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
        save_total_limit=3,
        fp16=True,
        bf16=False,
        max_seq_length=MAX_SEQ_LEN,
        packing=True,
        run_name=run_name,
        report_to="none",
        gradient_checkpointing=True,
        gradient_checkpointing_kwargs={"use_reentrant": False},
        optim="paged_adamw_8bit",
        lr_scheduler_type="cosine",
        seed=42,
        dataloader_pin_memory=False,
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
    result = trainer.train()

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
    """Verifie que LM Studio n'est pas en cours."""
    import subprocess
    result = subprocess.run(
        ["powershell", "-Command", "(Get-Process 'LM Studio' -ErrorAction SilentlyContinue).Count"],
        capture_output=True, text=True
    )
    count = result.stdout.strip()
    if count and int(count) > 0:
        print(f"[ERREUR] LM Studio tourne ({count} processus) !")
        print("  Arretez LM Studio pour liberer la VRAM.")
        sys.exit(1)
    print("[OK] LM Studio arrete")


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
    print("JARVIS Fine-Tuning — QLoRA sur Qwen3-30B-A3B")
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
