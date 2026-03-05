"""JARVIS Cowork Executor - Appelle Perplexity pour générer du code.

Exécute les tâches cowork en utilisant Perplexity pour générer le code.

Usage:
    from src.cowork_perplexity_executor import execute_task_with_perplexity
    result = await execute_task_with_perplexity(task)
"""

from __future__ import annotations

import asyncio
import logging
import re
import time
from pathlib import Path
from typing import Any

logger = logging.getLogger("jarvis.cowork.executor")


async def execute_task_with_perplexity(task) -> dict[str, Any]:
    """Exécute une tâche en appelant Perplexity pour générer le code.
    
    Args:
        task: CoworkTask à exécuter
        
    Returns:
        Dictionnaire avec:
        - success: bool
        - file_path: str (chemin fichier créé)
        - code: str (code généré)
        - error: str (si échec)
    """
    start = time.time()
    
    # 1. Construire le prompt pour Perplexity
    prompt = _build_prompt(task)
    
    # 2. Appeler Perplexity via bridge_query
    try:
        from src.bridge import bridge
        
        logger.info(f"Calling Perplexity for task {task.id}...")
        response = await bridge.query(
            prompt=prompt,
            task_type="coding",
            preferred_node="gemini"  # Gemini meilleur pour code
        )
        
        code = _extract_code_from_response(response)
        if not code:
            return {
                "success": False,
                "error": "No Python code found in Perplexity response"
            }
        
        # 3. Extraire le chemin fichier suggéré
        file_path = _extract_file_path(task, response)
        
        # 4. Valider le code (syntaxe)
        if not _validate_python_syntax(code):
            return {
                "success": False,
                "error": "Generated code has syntax errors"
            }
        
        # 5. Écrire le fichier
        full_path = Path(f"F:/BUREAU/turbo/{file_path}")
        full_path.parent.mkdir(parents=True, exist_ok=True)
        full_path.write_text(code, encoding="utf-8")
        
        duration = time.time() - start
        logger.info(f"Task {task.id} completed in {duration:.1f}s - File: {file_path}")
        
        return {
            "success": True,
            "file_path": str(file_path),
            "code": code,
            "duration_s": duration,
            "lines_of_code": len(code.splitlines())
        }
        
    except Exception as e:
        logger.error(f"Task {task.id} execution failed: {e}", exc_info=True)
        return {
            "success": False,
            "error": str(e)
        }


def _build_prompt(task) -> str:
    """Construit le prompt pour Perplexity."""
    return f"""Tu es un développeur senior Python spécialisé dans les systèmes autonomes.

Crée le module suivant pour JARVIS (assistant IA Windows):

## Tâche: {task.title}

**Catégorie**: {task.category}
**Priorité**: {task.priority}/10
**Durée estimée**: {task.estimated_duration_min} min

## Description détaillée:

{task.description}

## Exigences techniques:

1. **Langage**: Python 3.11+ avec type hints complets
2. **Logging**: Utiliser `logger = logging.getLogger("jarvis.{task.category}")`
3. **Documentation**: Docstrings complètes (module, classes, fonctions)
4. **Robustesse**: Gestion d'erreurs avec try/except, logging des erreurs
5. **Intégration**:
   - Émettre événements via `event_bus.emit()` si pertinent
   - S'intégrer avec modules existants (brain, orchestrator, etc.)
6. **Async**: Utiliser asyncio pour opérations I/O
7. **Configuration**: Paramètres configurables (pas de hardcode)
8. **Tests**: Inclure au moins 3 tests unitaires basiques

## Structure attendue:

```python
\"\"\"Module docstring.\"\"\"

from __future__ import annotations

import asyncio
import logging
# autres imports...

logger = logging.getLogger("jarvis.{task.category}")

# Classes et fonctions...

if __name__ == "__main__":
    # Tests rapides
    pass
```

## Contraintes:

- **OBLIGATOIRE**: Le code doit être prêt à être déployé sans modification
- **OBLIGATOIRE**: Aucune dépendance externe non installée (utiliser stdlib max)
- **OBLIGATOIRE**: Compatible Windows 10/11
- **RECOMMANDÉ**: Réutiliser modules JARVIS existants plutôt que réinventer

## Livrables:

1. Code Python complet du module
2. Chemin fichier suggéré (ex: `src/windows/registry_monitor.py`)
3. Instructions d'intégration rapides (2-3 lignes)

Génère maintenant le code complet, prêt à l'emploi.
"""


def _extract_code_from_response(response: str) -> str:
    """Extrait le code Python de la réponse Perplexity."""
    # Chercher blocs code marqués ```python
    pattern = r"```python\s*\n(.*?)\n```"
    matches = re.findall(pattern, response, re.DOTALL | re.IGNORECASE)
    
    if matches:
        # Prendre le plus long bloc (code principal)
        return max(matches, key=len)
    
    # Fallback: chercher blocs ```
    pattern = r"```\s*\n(.*?)\n```"
    matches = re.findall(pattern, response, re.DOTALL)
    
    if matches:
        # Vérifier si c'est du Python
        for code in matches:
            if "import" in code or "def " in code or "class " in code:
                return code
    
    return ""


def _extract_file_path(task, response: str) -> str:
    """Extrait le chemin fichier de la réponse ou génère un défaut."""
    # Chercher mentions de chemin fichier
    pattern = r"src/[a-z_/]+\.py"
    matches = re.findall(pattern, response)
    
    if matches:
        return matches[0]
    
    # Générer chemin par défaut basé sur task
    category_map = {
        "windows": "src/windows",
        "ia": "src/ai",
        "cluster": "src/cluster",
        "trading": "src/trading",
        "optimization": "src/optimization"
    }
    
    folder = category_map.get(task.category, "src")
    # Convertir titre en snake_case
    filename = task.title.lower().replace(" ", "_").replace("-", "_")
    filename = re.sub(r"[^a-z0-9_]", "", filename)
    
    return f"{folder}/{filename}.py"


def _validate_python_syntax(code: str) -> bool:
    """Vérifie que le code Python est syntaxiquement valide."""
    try:
        compile(code, "<string>", "exec")
        return True
    except SyntaxError as e:
        logger.warning(f"Syntax error in generated code: {e}")
        return False


async def test_task_execution() -> None:
    """Test rapide de l'exécution."""
    from src.cowork_agent_config import CoworkTask
    
    test_task = CoworkTask(
        id="TEST-001",
        title="Simple Logger",
        description="Créer un module qui log 'Hello JARVIS'.",
        category="optimization",
        priority=1,
        estimated_duration_min=5
    )
    
    result = await execute_task_with_perplexity(test_task)
    print(f"Result: {result}")


if __name__ == "__main__":
    asyncio.run(test_task_execution())

