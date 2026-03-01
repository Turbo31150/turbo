"""
JARVIS Fine-Tuning — Conversion GGUF
======================================
Merge les LoRA adapters dans le modele de base Qwen3-8B,
puis convertit en GGUF pour LM Studio.

Pipeline: checkpoint LoRA -> merge -> HF safetensors -> GGUF F16 -> GGUF quantifie

Usage:
    python finetuning/convert_gguf.py [QUANT_TYPE]
    python finetuning/convert_gguf.py Q4_K_M
    python finetuning/convert_gguf.py Q8_0
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
MODEL_NAME = "Qwen/Qwen3-8B"
MODEL_SHORT = "jarvis-qwen3-8b"


def find_latest_checkpoint() -> Path:
    """Trouve le dernier checkpoint (final > checkpoint-N > adapter)."""
    if not OUTPUT_DIR.exists():
        print("[ERREUR] Pas de dossier output. Lancez train.py d'abord.")
        sys.exit(1)

    runs = sorted(OUTPUT_DIR.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True)
    for run in runs:
        if not run.is_dir():
            continue
        # Priorite 1: dossier "final"
        final = run / "final"
        if final.exists() and any(final.glob("adapter_model*")):
            return final
        # Priorite 2: dernier checkpoint-N
        ckpts = sorted(
            [d for d in run.iterdir() if d.is_dir() and d.name.startswith("checkpoint-")],
            key=lambda d: int(d.name.split("-")[1]),
            reverse=True,
        )
        for ckpt in ckpts:
            if any(ckpt.glob("adapter_model*")):
                return ckpt
        # Priorite 3: adapter directement dans le run
        if any(run.glob("adapter_model*")):
            return run

    print("[ERREUR] Aucun checkpoint avec adapter_model trouve.")
    print(f"         Contenu de {OUTPUT_DIR}:")
    for p in OUTPUT_DIR.iterdir():
        print(f"           {p.name}/")
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
        torch_dtype=torch.bfloat16,
        device_map="auto",
        trust_remote_code=True,
    )
    tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME, trust_remote_code=True)

    print(f"[...] Chargement LoRA depuis {adapter_path}...")
    model = PeftModel.from_pretrained(base, str(adapter_path))

    print("[...] Merge des adapters...")
    model = model.merge_and_unload()

    merged_path.mkdir(parents=True, exist_ok=True)
    print(f"[...] Sauvegarde modele merge: {merged_path}")
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

    # Etape 1: HF -> GGUF BF16
    gguf_bf16 = GGUF_DIR / f"{MODEL_SHORT}-bf16.gguf"
    if not gguf_bf16.exists():
        print("[...] Conversion HF -> GGUF BF16...")
        subprocess.run(
            [sys.executable, str(convert_script),
             str(merged_path), "--outfile", str(gguf_bf16), "--outtype", "bf16"],
            check=True,
        )
        print(f"[OK] GGUF BF16: {gguf_bf16.stat().st_size / 1024**3:.1f} GB")
    else:
        print(f"[SKIP] GGUF BF16 existe deja: {gguf_bf16.stat().st_size / 1024**3:.1f} GB")

    # Etape 2: Quantifier
    gguf_quant = GGUF_DIR / f"{MODEL_SHORT}-{quant_type.lower()}.gguf"
    quantize_bin = llama_dir / "build" / "bin" / "llama-quantize.exe"

    if not quantize_bin.exists():
        # Chercher aussi dans d'autres emplacements
        alt_paths = [
            llama_dir / "build" / "Release" / "llama-quantize.exe",
            llama_dir / "build" / "llama-quantize.exe",
        ]
        for alt in alt_paths:
            if alt.exists():
                quantize_bin = alt
                break

    if quantize_bin.exists():
        print(f"[...] Quantification {quant_type}...")
        subprocess.run(
            [str(quantize_bin), str(gguf_bf16), str(gguf_quant), quant_type],
            check=True,
        )
        print(f"[OK] GGUF {quant_type}: {gguf_quant.stat().st_size / 1024**3:.1f} GB")
        return gguf_quant
    else:
        print(f"[WARN] llama-quantize non trouve. Tentative via pip gguf...")
        try:
            subprocess.run(
                [sys.executable, "-m", "pip", "install", "gguf", "--quiet"],
                check=True,
            )
            # Utiliser llama-quantize de gguf package si disponible
            print(f"[INFO] Le GGUF BF16 est utilisable directement dans LM Studio.")
            print(f"       Pour quantifier manuellement:")
            print(f"       cd {llama_dir} && cmake -B build -DCMAKE_BUILD_TYPE=Release && cmake --build build --config Release")
            print(f"       .\\build\\bin\\llama-quantize {gguf_bf16} {gguf_quant} {quant_type}")
        except Exception:
            pass
        return gguf_bf16


def deploy_to_lmstudio(gguf_path: Path):
    """Copie le GGUF dans le dossier LM Studio."""
    if not LMSTUDIO_MODELS.exists():
        print(f"[WARN] Dossier LM Studio non trouve: {LMSTUDIO_MODELS}")
        print(f"       Copiez manuellement: {gguf_path}")
        return

    dest_dir = LMSTUDIO_MODELS / f"{MODEL_SHORT}-finetune"
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / gguf_path.name

    if dest.exists():
        print(f"[WARN] Fichier existant sera ecrase: {dest}")

    print(f"[...] Copie vers LM Studio ({gguf_path.stat().st_size / 1024**3:.1f} GB)...")
    shutil.copy2(str(gguf_path), str(dest))
    print(f"[OK] Deploye: {dest}")
    print(f"     Dans LM Studio, chargez: {MODEL_SHORT}-finetune/{gguf_path.name}")
    print(f"     Ou via CLI: lms load {MODEL_SHORT}-finetune/{gguf_path.name}")


def main():
    quant = sys.argv[1] if len(sys.argv) > 1 else "Q4_K_M"

    auto_deploy = "--deploy" in sys.argv

    print("=" * 60)
    print(f"JARVIS Fine-Tuning — Conversion GGUF ({quant})")
    print(f"  Base: {MODEL_NAME}")
    print(f"  Output: {GGUF_DIR}")
    print(f"  LM Studio: {LMSTUDIO_MODELS}")
    print("=" * 60)

    # 1. Trouver checkpoint
    adapter_path = find_latest_checkpoint()
    print(f"[OK] Checkpoint: {adapter_path}")

    # 2. Merge LoRA
    merged = merge_lora(adapter_path)

    # 3. Convertir GGUF
    gguf = convert_to_gguf(merged, quant)

    # 4. Deployer
    if auto_deploy:
        deploy_to_lmstudio(gguf)
    else:
        print(f"\nDeployer dans LM Studio ? (o/n): ", end="")
        answer = input().strip().lower()
        if answer in ("o", "oui", "y", "yes"):
            deploy_to_lmstudio(gguf)

    print(f"\n{'='*60}")
    print(f"[DONE] GGUF pret: {gguf}")
    print(f"  Taille: {gguf.stat().st_size / 1024**3:.1f} GB")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
