#!/usr/bin/env python3
"""
Benchmark comparatif : Modèle Qwen3-30B de base vs Fine-tuné avec LoRA
Compare les réponses sur 30 prompts JARVIS avec métriques de similarité et pertinence.
"""

import os
import sys
import json
import time
import torch
import numpy as np
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass, asdict
from datetime import datetime
import warnings

warnings.filterwarnings("ignore")

# Import transformers, peft, sklearn pour embeddings
try:
    from transformers import (
        AutoTokenizer,
        AutoModelForCausalLM,
        BitsAndBytesConfig,
    )
    from peft import PeftModel
    from sklearn.metrics.pairwise import cosine_similarity
except ImportError as e:
    print(f"[ERREUR] Import manquant: {e}")
    print("Installez avec: uv pip install transformers peft bitsandbytes scikit-learn")
    sys.exit(1)


@dataclass
class BenchmarkResult:
    """Résultat d'un test benchmark"""
    prompt_id: str
    category: str
    prompt: str
    keywords_expected: List[str]
    base_model_response: str
    finetuned_response: str
    base_embedding: Optional[np.ndarray] = None
    finetuned_embedding: Optional[np.ndarray] = None
    cosine_similarity_score: float = 0.0
    keyword_match_base: int = 0
    keyword_match_finetuned: int = 0
    jarvis_relevance_base: float = 0.0
    jarvis_relevance_finetuned: float = 0.0
    timestamp: str = ""

    def to_dict(self):
        data = asdict(self)
        data.pop("base_embedding", None)
        data.pop("finetuned_embedding", None)
        return data


class JARVISBenchmark:
    """Benchmark JARVIS : modèle base vs fine-tuné"""

    # Définir les 30 prompts de test
    TEST_PROMPTS = {
        "commandes_vocales": [
            {
                "prompt": "ouvre chrome",
                "keywords": ["chrome", "navigateur", "open", "lancer"],
            },
            {
                "prompt": "status cluster",
                "keywords": ["cluster", "gpu", "vram", "status", "modele"],
            },
            {
                "prompt": "scan MEXC",
                "keywords": ["mexc", "scan", "trading", "positions", "marche"],
            },
            {
                "prompt": "lance jarvis voice",
                "keywords": ["jarvis", "voice", "micro", "audio", "ecoute"],
            },
            {
                "prompt": "check GPU",
                "keywords": ["gpu", "vram", "memoire", "charge", "utilisation"],
            },
            {
                "prompt": "active ollama",
                "keywords": ["ollama", "server", "modele", "local", "qwen"],
            },
            {
                "prompt": "affiche temps",
                "keywords": ["heure", "time", "date", "timestamp"],
            },
            {
                "prompt": "redemarrage cluster",
                "keywords": ["restart", "reboot", "cluster", "reload"],
            },
            {
                "prompt": "close pipeline",
                "keywords": ["close", "pipeline", "stop", "arreter"],
            },
            {
                "prompt": "listez les positions",
                "keywords": ["positions", "trading", "portefeuille", "list"],
            },
        ],
        "corrections_vocales": [
            {
                "prompt": "ouvres crom",
                "keywords": ["chrome", "navigateur", "ouvre"],
            },
            {
                "prompt": "statu cluteur",
                "keywords": ["status", "cluster"],
            },
            {
                "prompt": "skan mexik",
                "keywords": ["scan", "mexc"],
            },
            {
                "prompt": "lance jarvi voix",
                "keywords": ["jarvis", "voice"],
            },
            {
                "prompt": "chek geeypee",
                "keywords": ["check", "gpu"],
            },
            {
                "prompt": "activ olamo",
                "keywords": ["activate", "ollama"],
            },
            {
                "prompt": "affiche tamps",
                "keywords": ["time", "affiche"],
            },
            {
                "prompt": "redemaraje cluter",
                "keywords": ["redemarrage", "cluster"],
            },
            {
                "prompt": "clos pipelan",
                "keywords": ["close", "pipeline"],
            },
            {
                "prompt": "listé les pozision",
                "keywords": ["list", "positions"],
            },
        ],
        "tool_routing": [
            {
                "prompt": "monte le son",
                "keywords": ["volume", "volume_up", "audio", "son"],
            },
            {
                "prompt": "baisse le volume",
                "keywords": ["volume", "volume_down", "baisse", "son"],
            },
            {
                "prompt": "redemarrer la machine",
                "keywords": ["restart", "reboot", "windows", "system"],
            },
            {
                "prompt": "affiche les fichiers",
                "keywords": ["fichiers", "list", "directory", "ls"],
            },
            {
                "prompt": "execute le script trading",
                "keywords": ["trading", "script", "execute", "run"],
            },
            {
                "prompt": "active le cache micro",
                "keywords": ["cache", "microphone", "audio", "voice"],
            },
            {
                "prompt": "affiche la température GPU",
                "keywords": ["temperature", "gpu", "thermal", "moniteur"],
            },
            {
                "prompt": "cherche dans les logs",
                "keywords": ["search", "logs", "find", "grep"],
            },
            {
                "prompt": "envoie un message",
                "keywords": ["send", "message", "notification"],
            },
            {
                "prompt": "charge le modele qwen",
                "keywords": ["load", "qwen", "model", "lm_studio"],
            },
        ],
    }

    JARVIS_TOOLS = {
        "chrome": ["ouvre chrome", "navigate"],
        "cluster_status": ["status cluster", "gpu", "vram"],
        "trading": ["scan mexc", "trading", "positions"],
        "voice": ["jarvis voice", "micro", "audio"],
        "gpu": ["check gpu", "vram"],
        "ollama": ["ollama", "local model"],
        "time": ["heure", "time"],
        "restart": ["redemarrage", "restart"],
        "pipeline": ["close pipeline", "stop"],
        "positions": ["positions", "portefeuille"],
        "volume": ["volume", "son"],
        "system": ["redemarrer", "reboot"],
        "files": ["fichiers", "ls"],
    }

    def __init__(self, base_model_id: str = "Qwen/Qwen3-30B-A3B"):
        """
        Initialiser le benchmark

        Args:
            base_model_id: ID du modèle de base HuggingFace
        """
        self.base_model_id = base_model_id
        self.lora_adapter_path = self._find_lora_adapter()

        print(f"[INFO] Initialisation benchmark JARVIS")
        print(f"  - Modèle de base: {self.base_model_id}")
        print(f"  - Adaptateur LoRA: {self.lora_adapter_path}")

        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        print(f"  - Device: {self.device}")

        self.tokenizer = None
        self.base_model = None
        self.finetuned_model = None
        self.results: List[BenchmarkResult] = []

    def _find_lora_adapter(self) -> Optional[Path]:
        """Trouver le dernier dossier d'adaptateur LoRA"""
        lora_base = Path("F:/BUREAU/turbo/finetuning/output")
        if not lora_base.exists():
            print(f"[AVERTISSEMENT] Chemin LoRA inexistant: {lora_base}")
            return None

        # Chercher le dernier dossier avec un adaptateur 'final'
        for output_dir in sorted(lora_base.iterdir(), reverse=True):
            if output_dir.is_dir():
                final_path = output_dir / "final"
                if (final_path / "adapter_config.json").exists():
                    print(f"[OK] Adaptateur LoRA trouvé: {final_path}")
                    return final_path

        print(f"[AVERTISSEMENT] Aucun adaptateur LoRA trouvé dans {lora_base}")
        return None

    def load_models(self) -> bool:
        """Charger le modèle de base et fine-tuné"""
        try:
            print("\n[CHARGEMENT] Modèles...")

            # Config quantization pour économiser la mémoire
            bnb_config = BitsAndBytesConfig(
                load_in_4bit=True,
                bnb_4bit_use_double_quant=True,
                bnb_4bit_quant_type="nf4",
                bnb_4bit_compute_dtype=torch.bfloat16,
            )

            # Charger tokenizer
            print(f"  [1/3] Tokenizer: {self.base_model_id}")
            self.tokenizer = AutoTokenizer.from_pretrained(self.base_model_id)
            if self.tokenizer.pad_token is None:
                self.tokenizer.pad_token = self.tokenizer.eos_token

            # Charger modèle de base
            print(f"  [2/3] Modèle de base: {self.base_model_id}")
            self.base_model = AutoModelForCausalLM.from_pretrained(
                self.base_model_id,
                quantization_config=bnb_config,
                device_map="auto",
                torch_dtype=torch.bfloat16,
            )
            self.base_model.eval()

            # Charger modèle fine-tuné (avec LoRA)
            if self.lora_adapter_path:
                print(f"  [3/3] Adaptateur LoRA: {self.lora_adapter_path}")
                self.finetuned_model = PeftModel.from_pretrained(
                    self.base_model,
                    str(self.lora_adapter_path),
                    device_map="auto",
                )
                self.finetuned_model.eval()
            else:
                print("  [3/3] Pas d'adaptateur LoRA, utilisation du modèle de base uniquement")
                self.finetuned_model = None

            print("[OK] Modèles chargés")
            self._print_gpu_memory()
            return True

        except Exception as e:
            print(f"[ERREUR] Chargement des modèles: {e}")
            return False

    def _print_gpu_memory(self):
        """Afficher l'utilisation GPU"""
        if torch.cuda.is_available():
            for i in range(torch.cuda.device_count()):
                props = torch.cuda.get_device_properties(i)
                allocated = torch.cuda.memory_allocated(i) / 1e9
                reserved = torch.cuda.memory_reserved(i) / 1e9
                total = props.total_memory / 1e9
                print(f"    GPU {i}: {allocated:.1f}GB / {reserved:.1f}GB reserved / {total:.1f}GB total")

    def generate_response(
        self,
        model,
        prompt: str,
        max_new_tokens: int = 128,
    ) -> str:
        """Générer une réponse du modèle"""
        inputs = self.tokenizer(
            prompt,
            return_tensors="pt",
            truncation=True,
            max_length=512,
        ).to(self.device)

        with torch.no_grad():
            outputs = model.generate(
                **inputs,
                max_new_tokens=max_new_tokens,
                temperature=0.7,
                top_p=0.9,
                do_sample=True,
                pad_token_id=self.tokenizer.pad_token_id,
            )

        response = self.tokenizer.decode(outputs[0], skip_special_tokens=True)
        # Enlever le prompt de la réponse
        if prompt in response:
            response = response.replace(prompt, "", 1).strip()

        return response[:500]  # Limiter la longueur

    def get_embeddings(self, text: str) -> np.ndarray:
        """Obtenir l'embedding d'un texte (utiliser le modèle pour générer)"""
        inputs = self.tokenizer(
            text,
            return_tensors="pt",
            truncation=True,
            max_length=512,
        ).to(self.device)

        with torch.no_grad():
            # Utiliser les hidden states comme embedding
            outputs = self.base_model(**inputs, output_hidden_states=True)
            # Moyenne des hidden states du dernier layer
            embeddings = outputs.hidden_states[-1].mean(dim=1)

        return embeddings.cpu().numpy()[0]

    def compute_cosine_similarity(
        self,
        response1: str,
        response2: str,
    ) -> float:
        """Calculer la similarité cosinus entre deux réponses"""
        emb1 = self.get_embeddings(response1)
        emb2 = self.get_embeddings(response2)

        similarity = cosine_similarity([emb1], [emb2])[0][0]
        return float(similarity)

    def count_keyword_matches(self, response: str, keywords: List[str]) -> int:
        """Compter les mots-clés présents dans la réponse"""
        response_lower = response.lower()
        count = 0
        for keyword in keywords:
            if keyword.lower() in response_lower:
                count += 1
        return count

    def compute_jarvis_relevance(self, response: str) -> float:
        """
        Calculer un score de pertinence JARVIS
        Mesure si la réponse mentionne des outils ou commandes JARVIS valides
        """
        response_lower = response.lower()
        relevant_terms_found = 0
        total_terms = 0

        for tool_name, terms in self.JARVIS_TOOLS.items():
            for term in terms:
                total_terms += 1
                if term.lower() in response_lower:
                    relevant_terms_found += 1

        if total_terms == 0:
            return 0.0

        return min(1.0, relevant_terms_found / (total_terms * 0.3))  # Normalisé

    def run_benchmark(self) -> bool:
        """Lancer le benchmark complet"""
        if not self.load_models():
            return False

        print(f"\n[DÉMARRAGE] Benchmark sur {sum(len(v) for v in self.TEST_PROMPTS.values())} prompts")
        print(f"{'='*100}")

        test_id = 0
        for category, prompts in self.TEST_PROMPTS.items():
            print(f"\n### {category.upper()} ({len(prompts)} tests)")
            print("-" * 100)

            for idx, test in enumerate(prompts, 1):
                test_id += 1
                prompt = test["prompt"]
                keywords = test["keywords"]

                print(f"\n[Test {test_id}/30] {category} - '{prompt}'")
                print(f"  Mots-clés attendus: {', '.join(keywords)}")

                # Générer réponses
                print(f"  [1/4] Génération réponse modèle de base...", end="", flush=True)
                start = time.time()
                base_response = self.generate_response(self.base_model, prompt)
                base_time = time.time() - start
                print(f" ({base_time:.2f}s)")

                print(f"  [2/4] Génération réponse modèle fine-tuné...", end="", flush=True)
                if self.finetuned_model:
                    start = time.time()
                    finetuned_response = self.generate_response(self.finetuned_model, prompt)
                    ft_time = time.time() - start
                    print(f" ({ft_time:.2f}s)")
                else:
                    finetuned_response = base_response
                    ft_time = 0.0

                # Calculer métriques
                print(f"  [3/4] Calcul des métriques...", end="", flush=True)

                try:
                    cosine_sim = self.compute_cosine_similarity(
                        base_response,
                        finetuned_response,
                    )
                except Exception as e:
                    print(f"\n    [WARN] Erreur cosine: {e}")
                    cosine_sim = 0.0

                kw_match_base = self.count_keyword_matches(base_response, keywords)
                kw_match_ft = self.count_keyword_matches(finetuned_response, keywords)

                rel_base = self.compute_jarvis_relevance(base_response)
                rel_ft = self.compute_jarvis_relevance(finetuned_response)

                print(f" OK")

                # Créer résultat
                result = BenchmarkResult(
                    prompt_id=f"test_{test_id:02d}",
                    category=category,
                    prompt=prompt,
                    keywords_expected=keywords,
                    base_model_response=base_response[:200],
                    finetuned_response=finetuned_response[:200],
                    cosine_similarity_score=cosine_sim,
                    keyword_match_base=kw_match_base,
                    keyword_match_finetuned=kw_match_ft,
                    jarvis_relevance_base=rel_base,
                    jarvis_relevance_finetuned=rel_ft,
                    timestamp=datetime.now().isoformat(),
                )

                self.results.append(result)

                # Afficher résultat
                print(f"  [4/4] Résultats:")
                print(f"      Cosine similarity: {cosine_sim:.3f}")
                print(f"      Mots-clés (base): {kw_match_base}/{len(keywords)}")
                print(f"      Mots-clés (FT):   {kw_match_ft}/{len(keywords)}")
                print(f"      Relevance JARVIS (base): {rel_base:.3f}")
                print(f"      Relevance JARVIS (FT):   {rel_ft:.3f}")

        print(f"\n{'='*100}")
        print(f"[OK] Benchmark terminé - {len(self.results)} résultats")
        return True

    def generate_report(self, output_file: Optional[str] = None) -> str:
        """Générer un rapport comparatif"""
        if not self.results:
            return "Aucun résultat à afficher"

        if output_file is None:
            output_file = "benchmark_results.json"

        # Préparation statistiques
        stats = {
            "total_tests": len(self.results),
            "avg_cosine_similarity": np.mean([r.cosine_similarity_score for r in self.results]),
            "avg_keyword_match_base": np.mean([r.keyword_match_base for r in self.results]),
            "avg_keyword_match_finetuned": np.mean([r.keyword_match_finetuned for r in self.results]),
            "avg_relevance_base": np.mean([r.jarvis_relevance_base for r in self.results]),
            "avg_relevance_finetuned": np.mean([r.jarvis_relevance_finetuned for r in self.results]),
            "timestamp": datetime.now().isoformat(),
        }

        # Par catégorie
        by_category = {}
        for category in self.TEST_PROMPTS.keys():
            cat_results = [r for r in self.results if r.category == category]
            by_category[category] = {
                "count": len(cat_results),
                "avg_cosine": np.mean([r.cosine_similarity_score for r in cat_results]),
                "avg_keyword_base": np.mean([r.keyword_match_base for r in cat_results]),
                "avg_keyword_ft": np.mean([r.keyword_match_finetuned for r in cat_results]),
                "avg_relevance_base": np.mean([r.jarvis_relevance_base for r in cat_results]),
                "avg_relevance_ft": np.mean([r.jarvis_relevance_finetuned for r in cat_results]),
            }

        report_data = {
            "metadata": {
                "base_model": self.base_model_id,
                "lora_adapter": str(self.lora_adapter_path) if self.lora_adapter_path else None,
                "device": self.device,
                "timestamp": datetime.now().isoformat(),
            },
            "statistics": stats,
            "by_category": by_category,
            "results": [r.to_dict() for r in self.results],
        }

        # Sauvegarder JSON
        output_path = Path(output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(report_data, f, indent=2, ensure_ascii=False)

        # Afficher tableau
        print("\n" + "="*100)
        print("RAPPORT BENCHMARK COMPARATIF")
        print("="*100)

        print(f"\n[Metadata]")
        print(f"  Modèle de base: {self.base_model_id}")
        print(f"  LoRA adapters: {self.lora_adapter_path or 'Aucun'}")
        print(f"  Device: {self.device}")
        print(f"  Timestamp: {datetime.now().isoformat()}")

        print(f"\n[Statistiques globales]")
        print(f"  Total tests: {stats['total_tests']}")
        print(f"  Similarité cosinus moyenne: {stats['avg_cosine_similarity']:.3f}")
        print(f"  Correspondance mots-clés (base): {stats['avg_keyword_match_base']:.2f}")
        print(f"  Correspondance mots-clés (FT): {stats['avg_keyword_match_finetuned']:.2f}")
        print(f"  Pertinence JARVIS (base): {stats['avg_relevance_base']:.3f}")
        print(f"  Pertinence JARVIS (FT): {stats['avg_relevance_finetuned']:.3f}")

        print(f"\n[Par catégorie]")
        print(f"{'Catégorie':<25} {'Tests':<8} {'Cosine':<10} {'KW(B)':<8} {'KW(FT)':<8} {'Rel(B)':<8} {'Rel(FT)':<8}")
        print("-" * 100)
        for category, cat_stats in by_category.items():
            print(
                f"{category:<25} {cat_stats['count']:<8} "
                f"{cat_stats['avg_cosine']:<10.3f} "
                f"{cat_stats['avg_keyword_base']:<8.2f} "
                f"{cat_stats['avg_keyword_ft']:<8.2f} "
                f"{cat_stats['avg_relevance_base']:<8.3f} "
                f"{cat_stats['avg_relevance_ft']:<8.3f}"
            )

        print(f"\n[Fichier de sortie] {output_path}")
        print("="*100)

        return str(output_path)


def main():
    """Point d'entrée principal"""
    output_dir = Path("F:/BUREAU/turbo/finetuning")
    output_dir.mkdir(parents=True, exist_ok=True)

    benchmark = JARVISBenchmark(base_model_id="Qwen/Qwen3-30B-A3B")

    success = benchmark.run_benchmark()

    if success:
        output_file = output_dir / "benchmark_results.json"
        benchmark.generate_report(str(output_file))
        print(f"\n[SUCCÈS] Benchmark terminé!")
        return 0
    else:
        print(f"\n[ERREUR] Benchmark échoué")
        return 1


if __name__ == "__main__":
    sys.exit(main())
