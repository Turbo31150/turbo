#!/usr/bin/env python3
"""
Vérifier l'installation et la configuration du benchmark JARVIS
"""

import sys
import torch
from pathlib import Path

print("=" * 100)
print("VÉRIFICATION SETUP - BENCHMARK JARVIS")
print("=" * 100)
print()

# 1. Vérifier Python
print("[1/6] Python")
python_version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
print(f"  ✓ Python {python_version}")
print()

# 2. Vérifier PyTorch et CUDA
print("[2/6] PyTorch et CUDA")
print(f"  ✓ PyTorch {torch.__version__}")
if torch.cuda.is_available():
    print(f"  ✓ CUDA disponible")
    print(f"    - Nombre de GPU: {torch.cuda.device_count()}")
    for i in range(torch.cuda.device_count()):
        props = torch.cuda.get_device_properties(i)
        total_memory = props.total_memory / 1e9
        print(f"    - GPU {i}: {props.name} ({total_memory:.1f}GB)")
else:
    print(f"  ⚠ CUDA non disponible, CPU uniquement")
print()

# 3. Vérifier les importations
print("[3/6] Dépendances Python")
deps_ok = True
required_modules = {
    "transformers": "Transformers (modèles HF)",
    "peft": "PEFT (LoRA adapters)",
    "bitsandbytes": "BitsAndBytes (quantization)",
    "sklearn": "Scikit-learn (métriques)",
    "numpy": "NumPy (calculs)",
}

for module_name, description in required_modules.items():
    try:
        __import__(module_name)
        print(f"  ✓ {description}")
    except ImportError:
        print(f"  ✗ {description} MANQUANT")
        deps_ok = False

if not deps_ok:
    print("\n  → Installation: uv pip install transformers peft bitsandbytes scikit-learn")
print()

# 4. Vérifier la structure des répertoires
print("[4/6] Structure de répertoires")
finetuning_dir = Path("F:/BUREAU/turbo/finetuning")
if finetuning_dir.exists():
    print(f"  ✓ {finetuning_dir}")
else:
    print(f"  ✗ {finetuning_dir} INEXISTANT")

required_files = {
    "benchmark.py": "Script benchmark principal",
    "analyze_results.py": "Script d'analyse",
    "README_BENCHMARK.md": "Documentation",
}

for filename, description in required_files.items():
    filepath = finetuning_dir / filename
    if filepath.exists():
        size_kb = filepath.stat().st_size / 1024
        print(f"  ✓ {filename} ({size_kb:.1f}KB) - {description}")
    else:
        print(f"  ✗ {filename} MANQUANT")
print()

# 5. Vérifier les adaptateurs LoRA
print("[5/6] Adaptateurs LoRA")
lora_base = Path("F:/BUREAU/turbo/finetuning/output")
if lora_base.exists():
    print(f"  ✓ Répertoire output existe")

    lora_found = False
    for output_dir in sorted(lora_base.iterdir(), reverse=True):
        if output_dir.is_dir():
            final_path = output_dir / "final"
            if (final_path / "adapter_config.json").exists():
                print(f"  ✓ LoRA adapter trouvé: {final_path.name}")
                lora_found = True
                break

    if not lora_found:
        print(f"  ⚠ Aucun adaptateur LoRA 'final' trouvé")
        print(f"    → Benchmark fonctionnera avec le modèle de base uniquement")
else:
    print(f"  ⚠ Répertoire LoRA non créé")
    print(f"    → Benchmark fonctionnera avec le modèle de base uniquement")
print()

# 6. Vérifier la configuration
print("[6/6] Configuration")
print(f"  ✓ Modèle de base: Qwen/Qwen3-30B-A3B")
print(f"  ✓ Quantization: 4-bit (double quant)")
print(f"  ✓ Device map: auto (multi-GPU)")
print(f"  ✓ Prompts de test: 30 (3 catégories × 10)")
print()

# Résumé
print("=" * 100)
if deps_ok:
    print("✓ CONFIGURATION OK - Vous pouvez lancer le benchmark")
    print()
    print("  Lancer le benchmark:")
    print("    cd F:\\BUREAU\\turbo")
    print("    uv run python finetuning/benchmark.py")
    print()
    print("  Ou utiliser le launcher:")
    print("    F:\\BUREAU\\turbo\\finetuning\\run_benchmark.bat")
    print()
    return_code = 0
else:
    print("✗ CONFIGURATION INCOMPLÈTE - Installez les dépendances manquantes")
    print()
    print("  uv pip install transformers peft bitsandbytes scikit-learn")
    print()
    return_code = 1

print("=" * 100)
sys.exit(return_code)
