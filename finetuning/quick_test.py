#!/usr/bin/env python3
"""
Test rapide du benchmark JARVIS
Lance 3 tests seulement pour verifier la configuration
"""

import sys
import torch
from pathlib import Path

print("=" * 100)
print("QUICK TEST - BENCHMARK JARVIS")
print("=" * 100)
print()

# Verifications rapides
print("[1/4] Verification des dependances...")
try:
    from transformers import AutoTokenizer, AutoModelForCausalLM, BitsAndBytesConfig
    from peft import PeftModel
    from sklearn.metrics.pairwise import cosine_similarity
    import numpy as np
    print("  OK Tous les imports OK")
except ImportError as e:
    print(f"  ERREUR Import manquant: {e}")
    sys.exit(1)

print()
print("[2/4] Configuration GPU...")
if torch.cuda.is_available():
    print(f"  OK GPU detecte: {torch.cuda.device_count()} device(s)")
    for i in range(torch.cuda.device_count()):
        props = torch.cuda.get_device_properties(i)
        total = props.total_memory / 1e9
        print(f"    - GPU {i}: {props.name} ({total:.1f}GB)")
else:
    print("  AVERTISSEMENT GPU non disponible, CPU uniquement")

print()
print("[3/4] Chargement du modele de base...")

try:
    # Configuration quantization
    bnb_config = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_use_double_quant=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=torch.bfloat16,
    )

    # Charger tokenizer
    print("  Chargement tokenizer...", end="", flush=True)
    tokenizer = AutoTokenizer.from_pretrained("Qwen/Qwen3-30B-A3B")
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
    print(" OK")

    # Charger modele
    print("  Chargement modele de base...", end="", flush=True)
    base_model = AutoModelForCausalLM.from_pretrained(
        "Qwen/Qwen3-30B-A3B",
        quantization_config=bnb_config,
        device_map="auto",
        torch_dtype=torch.bfloat16,
    )
    base_model.eval()
    print(" OK")

    print("  OK Modele charge avec succes")

except Exception as e:
    print(f"\n  ERREUR Chargement: {e}")
    sys.exit(1)

print()
print("[4/4] Test de generation...")

try:
    # Test prompt
    test_prompt = "ouvre chrome"
    print(f"  Prompt test: '{test_prompt}'")

    # Generer reponse
    print("  Generation...", end="", flush=True)
    device = "cuda" if torch.cuda.is_available() else "cpu"
    inputs = tokenizer(test_prompt, return_tensors="pt", truncation=True, max_length=512).to(device)

    with torch.no_grad():
        outputs = base_model.generate(
            **inputs,
            max_new_tokens=64,
            temperature=0.7,
            top_p=0.9,
            do_sample=True,
            pad_token_id=tokenizer.pad_token_id,
        )

    response = tokenizer.decode(outputs[0], skip_special_tokens=True)
    if test_prompt in response:
        response = response.replace(test_prompt, "", 1).strip()

    print(" OK")
    print(f"  Reponse: {response[:100]}...")

except Exception as e:
    print(f"\n  ERREUR Generation: {e}")
    sys.exit(1)

print()
print("=" * 100)
print("OK QUICK TEST REUSSI - Configuration OK")
print()
print("Vous pouvez maintenant lancer le benchmark complet:")
print("  uv run python finetuning/benchmark.py")
print()
print("=" * 100)
