"""
JARVIS Fine-Tuning — Conversion GGUF
======================================
Merge les LoRA adapters dans le modele de base,
puis convertit en GGUF pour LM Studio.

Usage:
    uv run python finetuning/convert_gguf.py [QUANT_TYPE]
    uv run python finetuning/convert_gguf.py Q4_K_M
"""

import os
import sys
import shutil
import subprocess
from pathlib import Path

TURBO_DIR = Path("F:/BUREAU/turbo")
FINETUNING_DIR = TURBO_DIR / "finetuning"
OUTPUT_DIR = FINETUNING_DIR / "output"
GGUF_DIR = FINETUNING_DIR / "gguf"
LMSTUDIO_MODELS = Path("F:/models lmsqtudio")
MODEL_NAME = "Qwen/Qwen3-30B-A3B"


def find_latest_checkpoint() -> Path:
    """Trouve le dernier checkpoint final."""
    if not OUTPUT_DIR.exists():
        print("[ERREUR] Pas de dossier output. Lancez train.py d'abord.")
        sys.exit(1)

    runs = sorted(OUTPUT_DIR.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True)
    for run in runs:
        final = run / "final"
        if final.exists() and any(final.iterdir()):
            return final

    print("[ERREUR] Aucun checkpoint 'final' trouve.")
    sys.exit(1)


def merge_lora(adapter_path: Path) -> Path:
    """Merge les LoRA adapters dans le modele de base."""
    import torch
    from peft import PeftModel
    from transformers import AutoModelForCausalLM, AutoTokenizer

    merged_path = adapter_path.parent / "merged"
    if merged_path.exists() and any(merged_path.glob("*.safetensors")):
        print(f"[SKIP] Deja merge: {merged_path}")
        return merged_path

    print(f"[...] Chargement modele de base {MODEL_NAME}...")
    base = AutoModelForCausalLM.from_pretrained(
        MODEL_NAME,
        torch_dtype=torch.float16,
        device_map="auto",
        trust_remote_code=True,
    )
    tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME, trust_remote_code=True)

    print(f"[...] Chargement LoRA depuis {adapter_path}...")
    model = PeftModel.from_pretrained(base, str(adapter_path))

    print("[...] Merge des adapters...")
    model = model.merge_and_unload()

    merged_path.mkdir(parents=True, exist_ok=True)
    print(f"[...] Sauvegarde: {merged_path}")
    model.save_pretrained(str(merged_path), safe_serialization=True)
    tokenizer.save_pretrained(str(merged_path))

    size_gb = sum(f.stat().st_size for f in merged_path.rglob("*")) / 1024**3
    print(f"[OK] Modele merge: {size_gb:.1f} GB")
    return merged_path


def ensure_llama_cpp() -> Path:
    """Clone llama.cpp si necessaire et retourne le chemin."""
    llama_dir = FINETUNING_DIR / "llama.cpp"
    if not llama_dir.exists():
        print("[...] Clonage de llama.cpp (depth=1)...")
        subprocess.run(
            ["git", "clone", "--depth", "1",
             "https://github.com/ggerganov/llama.cpp", str(llama_dir)],
            check=True,
        )
    return llama_dir


def convert_to_gguf(merged_path: Path, quant_type: str = "Q4_K_M") -> Path:
    """Convertit le modele merge en GGUF."""
    GGUF_DIR.mkdir(parents=True, exist_ok=True)

    llama_dir = ensure_llama_cpp()
    convert_script = llama_dir / "convert_hf_to_gguf.py"

    if not convert_script.exists():
        print(f"[ERREUR] Script non trouve: {convert_script}")
        print("         Verifiez l'installation de llama.cpp")
        sys.exit(1)

    # Etape 1: HF -> GGUF F16
    gguf_f16 = GGUF_DIR / "jarvis-qwen3-30b-f16.gguf"
    if not gguf_f16.exists():
        print("[...] Conversion HF -> GGUF F16...")
        subprocess.run(
            [sys.executable, str(convert_script),
             str(merged_path), "--outfile", str(gguf_f16), "--outtype", "f16"],
            check=True,
        )
        print(f"[OK] GGUF F16: {gguf_f16.stat().st_size / 1024**3:.1f} GB")
    else:
        print(f"[SKIP] GGUF F16 existe deja")

    # Etape 2: Quantifier
    gguf_quant = GGUF_DIR / f"jarvis-qwen3-30b-{quant_type.lower()}.gguf"
    quantize_bin = llama_dir / "build" / "bin" / "llama-quantize.exe"

    if quantize_bin.exists():
        print(f"[...] Quantification {quant_type}...")
        subprocess.run(
            [str(quantize_bin), str(gguf_f16), str(gguf_quant), quant_type],
            check=True,
        )
        print(f"[OK] GGUF {quant_type}: {gguf_quant.stat().st_size / 1024**3:.1f} GB")
        return gguf_quant
    else:
        print(f"[WARN] llama-quantize non trouve.")
        print(f"       Pour compiler: cd {llama_dir} && cmake -B build && cmake --build build")
        print(f"       En attendant, le GGUF F16 est utilisable directement.")
        return gguf_f16


def deploy_to_lmstudio(gguf_path: Path):
    """Copie le GGUF dans le dossier LM Studio."""
    if not LMSTUDIO_MODELS.exists():
        print(f"[WARN] Dossier LM Studio non trouve: {LMSTUDIO_MODELS}")
        return

    dest_dir = LMSTUDIO_MODELS / "jarvis-qwen3-30b-finetune"
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / gguf_path.name

    print(f"[...] Copie vers LM Studio...")
    shutil.copy2(str(gguf_path), str(dest))
    print(f"[OK] Deploye: {dest}")
    print(f"     Redemarrez LM Studio et chargez: jarvis-qwen3-30b-finetune/{gguf_path.name}")


def main():
    quant = sys.argv[1] if len(sys.argv) > 1 else "Q4_K_M"

    print("=" * 60)
    print(f"JARVIS Fine-Tuning — Conversion GGUF ({quant})")
    print("=" * 60)

    # 1. Trouver checkpoint
    adapter_path = find_latest_checkpoint()
    print(f"[OK] Checkpoint: {adapter_path}")

    # 2. Merge LoRA
    merged = merge_lora(adapter_path)

    # 3. Convertir GGUF
    gguf = convert_to_gguf(merged, quant)

    # 4. Deployer
    print(f"\nDeployer dans LM Studio ? (o/n): ", end="")
    answer = input().strip().lower()
    if answer in ("o", "oui", "y", "yes"):
        deploy_to_lmstudio(gguf)

    print(f"\n[DONE] GGUF pret: {gguf}")


if __name__ == "__main__":
    main()
