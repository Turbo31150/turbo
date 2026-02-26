#!/usr/bin/env python3
"""Populate etoile.db with pipeline dictionary, agent keywords, scenario weights, domino chains."""
import sqlite3, json, re, sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

try:
    from src.config import PATHS
    DB_PATH = str(PATHS["etoile_db"])
except ImportError:
    DB_PATH = os.path.join(os.path.dirname(__file__), "data", "etoile.db")

def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def create_tables():
    conn = get_conn()
    c = conn.cursor()

    c.execute('''CREATE TABLE IF NOT EXISTS agent_keywords (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        agent TEXT NOT NULL,
        keyword TEXT NOT NULL,
        domain TEXT NOT NULL,
        weight REAL DEFAULT 1.0,
        scenario TEXT DEFAULT 'default',
        hit_count INTEGER DEFAULT 0,
        created_at TEXT DEFAULT (datetime('now')),
        UNIQUE(agent, keyword, scenario)
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS pipeline_dictionary (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        pipeline_id TEXT NOT NULL UNIQUE,
        trigger_phrase TEXT NOT NULL,
        steps TEXT,
        category TEXT NOT NULL,
        action_type TEXT,
        agents_involved TEXT,
        avg_duration_ms INTEGER DEFAULT 0,
        usage_count INTEGER DEFAULT 0,
        created_at TEXT DEFAULT (datetime('now'))
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS scenario_weights (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        scenario TEXT NOT NULL,
        agent TEXT NOT NULL,
        weight REAL DEFAULT 1.0,
        priority INTEGER DEFAULT 1,
        chain_next TEXT,
        description TEXT,
        UNIQUE(scenario, agent)
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS domino_chains (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        trigger_cmd TEXT NOT NULL,
        condition TEXT DEFAULT 'always',
        next_cmd TEXT NOT NULL,
        delay_ms INTEGER DEFAULT 0,
        auto INTEGER DEFAULT 1,
        description TEXT,
        UNIQUE(trigger_cmd, condition, next_cmd)
    )''')

    c.execute('CREATE INDEX IF NOT EXISTS idx_agent_kw ON agent_keywords(agent, domain)')
    c.execute('CREATE INDEX IF NOT EXISTS idx_pipeline_cat ON pipeline_dictionary(category)')
    c.execute('CREATE INDEX IF NOT EXISTS idx_scenario ON scenario_weights(scenario)')
    conn.commit()
    conn.close()
    print("Tables created OK")

def populate_scenario_weights():
    """From config.py routing rules."""
    scenarios = [
        # Standard routing (14 rules)
        ("short_answer",    [("OL1", 1.5, 1), ("M3", 1.0, 2)]),
        ("deep_analysis",   [("M2", 1.4, 1), ("GEMINI", 1.2, 2)]),
        ("code_generation", [("M2", 1.6, 1), ("M3", 1.0, 2), ("OL1", 0.5, 3)]),
        ("trading_signal",  [("OL1", 1.5, 1), ("M2", 1.2, 2)]),
        ("reasoning",       [("CLAUDE", 1.4, 1), ("M2", 1.2, 2)]),
        ("validation",      [("M2", 1.4, 1), ("OL1", 1.0, 2)]),
        ("critical",        [("M2", 1.5, 1), ("OL1", 1.3, 2), ("GEMINI", 1.2, 3)]),
        ("web_research",    [("OL1", 1.5, 1), ("GEMINI", 1.0, 2)]),
        ("embedding",       [("M1", 2.0, 1)]),
        ("consensus",       [("M2", 1.4, 1), ("OL1", 1.3, 2), ("M3", 1.0, 3), ("M1", 0.7, 4), ("GEMINI", 1.2, 5), ("CLAUDE", 1.2, 6)]),
        ("architecture",    [("GEMINI", 1.5, 1), ("CLAUDE", 1.2, 2), ("M2", 1.0, 3)]),
        ("voice_correction",[("OL1", 1.5, 1)]),
        ("auto_learn",      [("OL1", 1.3, 1), ("M2", 1.0, 2)]),
        ("bridge",          [("M2", 1.4, 1), ("OL1", 1.3, 2), ("M3", 1.0, 3), ("GEMINI", 1.2, 4), ("CLAUDE", 1.2, 5)]),
        # Commander routing (8 rules)
        ("cmd_code",        [("M2", 1.6, 1), ("M3", 0.8, 2)]),
        ("cmd_analyse",     [("M2", 1.4, 1), ("GEMINI", 1.0, 2)]),
        ("cmd_trading",     [("OL1", 1.5, 1), ("M2", 1.0, 2)]),
        ("cmd_systeme",     [("OL1", 1.0, 1)]),
        ("cmd_web",         [("OL1", 1.3, 1), ("M2", 1.0, 2)]),
        ("cmd_simple",      [("OL1", 1.5, 1)]),
        ("cmd_architecture",[("GEMINI", 1.5, 1), ("CLAUDE", 1.2, 2)]),
        ("cmd_consensus",   [("M2", 1.4, 1), ("OL1", 1.3, 2), ("M3", 1.0, 3)]),
    ]

    conn = get_conn()
    count = 0
    for scenario, agents in scenarios:
        for agent, weight, priority in agents:
            chain = agents[agents.index((agent, weight, priority)) + 1][0] if agents.index((agent, weight, priority)) < len(agents) - 1 else None
            try:
                conn.execute(
                    "INSERT OR REPLACE INTO scenario_weights (scenario, agent, weight, priority, chain_next, description) VALUES (?,?,?,?,?,?)",
                    (scenario, agent, weight, priority, chain, f"Routing {scenario} → {agent}")
                )
                count += 1
            except Exception as e:
                print(f"  SKIP {scenario}/{agent}: {e}")
    conn.commit()
    conn.close()
    print(f"Scenario weights: {count} entries")

def populate_domino_chains():
    """Predefined domino chains."""
    chains = [
        ("status",    "node_fail",    "heal --status",  0,    1, "Auto-diagnostic quand noeud en panne"),
        ("ask",       "timeout",      "ask_fallback",   0,    1, "Fallback auto sur timeout"),
        ("ask",       "success",      "log_metric",     0,    1, "Log metrique apres chaque ask"),
        ("consensus", "complete",     "log_consensus",  0,    1, "Log consensus dans etoile.db"),
        ("heal",      "node_repaired","status",         5000, 1, "Re-check status apres reparation"),
        ("bench",     "complete",     "scores",         0,    0, "Afficher scores apres benchmark"),
        ("arena",     "new_champion", "export",         0,    1, "Export config si nouveau champion"),
        ("status",    "all_ok",       "log_health",     0,    1, "Log sante quand tout va bien"),
        ("mode_trading", "start",     "trading_scan",   2000, 1, "Scan trading apres mode trading"),
        ("mode_code",    "start",     "cluster_check",  1000, 1, "Check cluster apres mode code"),
        ("routine_matin","start",     "status",         0,    1, "Status cluster dans routine matin"),
        ("routine_matin","start",     "scores",         3000, 0, "Scores apres status dans routine"),
    ]

    conn = get_conn()
    count = 0
    for trigger, cond, nxt, delay, auto, desc in chains:
        try:
            conn.execute(
                "INSERT OR REPLACE INTO domino_chains (trigger_cmd, condition, next_cmd, delay_ms, auto, description) VALUES (?,?,?,?,?,?)",
                (trigger, cond, nxt, delay, auto, desc)
            )
            count += 1
        except Exception as e:
            print(f"  SKIP {trigger}: {e}")
    conn.commit()
    conn.close()
    print(f"Domino chains: {count} entries")

def populate_agent_keywords():
    """Keywords per agent with domain mapping."""
    keywords = {
        "M1": {
            "raisonnement": ["logique", "si", "conclusion", "deduction", "reflechis", "syllogisme", "premisse"],
            "math": ["calcul", "calcule", "derive", "equation", "racine", "pourcentage", "nombre", "combien", "integrale", "matrice"],
            "embedding": ["embedding", "vecteur", "similarite", "cosine"],
            "code": ["architecture", "design", "pattern", "refactoring", "optimisation"],
        },
        "M2": {
            "code": ["code", "fonction", "function", "class", "def", "sql", "python", "javascript", "script", "ecris", "programme",
                     "debug", "bug", "fix", "erreur", "exception", "test", "unittest", "pytest", "review", "refactor",
                     "api", "endpoint", "crud", "database", "query", "migration", "schema", "type", "interface",
                     "git", "commit", "branch", "merge", "docker", "deploy", "ci", "cd", "pipeline", "build"],
            "securite": ["injection", "xss", "ssl", "ssh", "https", "vulnerabilite", "port", "header", "cve",
                         "firewall", "scan", "nmap", "pentest", "audit", "hash", "chiffrement", "token"],
        },
        "M3": {
            "general": ["explique", "resume", "compare", "decris", "liste", "enumere", "definis"],
            "traduction": ["traduis", "translate", "anglais", "francais", "espagnol", "english", "french"],
            "validation": ["verifie", "valide", "confirme", "correct", "review"],
            "systeme": ["powershell", "bash", "cmd", "processus", "disque", "port", "service", "registre"],
        },
        "OL1": {
            "rapide": ["bonjour", "salut", "merci", "oui", "non", "ok", "heure", "date", "meteo"],
            "math": ["plus", "moins", "fois", "divise", "somme", "moyenne", "total"],
            "trading": ["rsi", "btc", "eth", "signal", "long", "short", "bull", "bear", "sma", "volume", "breakout",
                        "prix", "cours", "marche", "crypto", "action", "bourse", "analyse_technique"],
            "web": ["cherche", "google", "web", "recherche", "trouve", "actualite", "news", "article"],
        },
        "GEMINI": {
            "architecture": ["architecture", "design", "systeme", "infrastructure", "scalabilite", "microservice",
                             "monolithe", "pattern", "diagramme", "uml", "plan"],
            "vision": ["image", "screenshot", "capture", "photo", "visuel", "ocr", "pdf"],
        },
        "CLAUDE": {
            "raisonnement": ["raisonnement", "complexe", "analyse", "profonde", "philosophie", "ethique", "debat",
                             "argumentation", "critique", "nuance", "paradoxe"],
            "code_review": ["review", "revue", "qualite", "best_practice", "clean_code", "solid", "dry"],
        },
    }

    conn = get_conn()
    count = 0
    for agent, domains in keywords.items():
        for domain, kws in domains.items():
            # Map domain to scenario
            domain_to_scenario = {
                "code": "code_generation", "securite": "critical", "math": "short_answer",
                "raisonnement": "reasoning", "trading": "trading_signal", "web": "web_research",
                "general": "short_answer", "traduction": "short_answer", "rapide": "short_answer",
                "validation": "validation", "systeme": "cmd_systeme", "embedding": "embedding",
                "architecture": "architecture", "vision": "architecture", "code_review": "validation",
            }
            scenario = domain_to_scenario.get(domain, "default")
            # Get weight from scenario_weights if exists
            row = conn.execute("SELECT weight FROM scenario_weights WHERE scenario=? AND agent=?", (scenario, agent)).fetchone()
            weight = row["weight"] if row else 1.0

            for kw in kws:
                try:
                    conn.execute(
                        "INSERT OR REPLACE INTO agent_keywords (agent, keyword, domain, weight, scenario) VALUES (?,?,?,?,?)",
                        (agent, kw, domain, weight, scenario)
                    )
                    count += 1
                except Exception as e:
                    pass
    conn.commit()
    conn.close()
    print(f"Agent keywords: {count} entries")

def populate_pipeline_dictionary():
    """Extract from commands.py and commands_pipelines.py."""
    # Import command modules
    try:
        from commands import COMMANDS
        from commands_pipelines import PIPELINE_COMMANDS
        all_cmds = COMMANDS + PIPELINE_COMMANDS
    except ImportError:
        # Fallback: parse files directly
        print("Direct import failed, parsing files...")
        all_cmds = parse_commands_from_files()

    conn = get_conn()
    count = 0
    for cmd in all_cmds:
        name = cmd.name if hasattr(cmd, 'name') else cmd.get('name', '')
        trigger = cmd.triggers[0] if hasattr(cmd, 'triggers') and cmd.triggers else cmd.get('triggers', [''])[0]
        steps = cmd.action if hasattr(cmd, 'action') else cmd.get('action', '')
        category = cmd.category if hasattr(cmd, 'category') else cmd.get('category', '')
        action_type = cmd.action_type if hasattr(cmd, 'action_type') else cmd.get('action_type', '')

        # Determine agents involved based on action type
        agents = []
        if 'cluster' in str(steps).lower() or 'lm_query' in str(steps).lower():
            agents = ["M1", "M2", "M3", "OL1"]
        elif 'ollama' in str(steps).lower():
            agents = ["OL1"]
        elif 'trading' in str(steps).lower():
            agents = ["OL1", "M2"]
        elif action_type == 'pipeline':
            agents = []  # System-level pipelines

        try:
            conn.execute(
                "INSERT OR REPLACE INTO pipeline_dictionary (pipeline_id, trigger_phrase, steps, category, action_type, agents_involved) VALUES (?,?,?,?,?,?)",
                (name, trigger, steps, category, action_type, ",".join(agents) if agents else None)
            )
            count += 1
        except Exception as e:
            pass
    conn.commit()
    conn.close()
    print(f"Pipeline dictionary: {count} entries")

def parse_commands_from_files():
    """Fallback parser for commands.py if import fails."""
    import ast

    cmds = []
    for filepath in [r"F:\BUREAU\turbo\src\commands.py", r"F:\BUREAU\turbo\src\commands_pipelines.py"]:
        if not os.path.exists(filepath):
            continue
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()

        # Find all JarvisCommand(...) calls via regex
        pattern = r'JarvisCommand\(\s*"([^"]+)"\s*,\s*"([^"]+)"\s*,\s*"([^"]+)"\s*,\s*\[(.*?)\]\s*,\s*"([^"]+)"\s*,\s*"(.*?)"\s*'
        for m in re.finditer(pattern, content, re.DOTALL):
            name, category, desc, triggers_raw, action_type, action = m.groups()
            # Parse trigger list
            triggers = re.findall(r'"([^"]+)"', triggers_raw)
            cmds.append({
                'name': name,
                'category': category,
                'triggers': triggers,
                'action_type': action_type,
                'action': action,
            })
    return cmds

def show_stats():
    conn = get_conn()
    tables = ['agent_keywords', 'pipeline_dictionary', 'scenario_weights', 'domino_chains']
    print("\n=== ETOILE.DB — Pipeline Dictionary Stats ===")
    for t in tables:
        try:
            count = conn.execute(f"SELECT COUNT(*) FROM [{t}]").fetchone()[0]
            print(f"  {t}: {count} rows")
        except:
            print(f"  {t}: NOT FOUND")

    # Agent keyword distribution
    print("\n  Keywords per agent:")
    for row in conn.execute("SELECT agent, COUNT(*) as cnt, COUNT(DISTINCT domain) as doms FROM agent_keywords GROUP BY agent ORDER BY cnt DESC"):
        print(f"    {row[0]}: {row[1]} keywords, {row[2]} domains")

    # Scenario count
    print(f"\n  Scenarios: {conn.execute('SELECT COUNT(DISTINCT scenario) FROM scenario_weights').fetchone()[0]}")
    print(f"  Domino chains: {conn.execute('SELECT COUNT(*) FROM domino_chains').fetchone()[0]}")

    # Pipeline categories
    print("\n  Pipeline categories:")
    for row in conn.execute("SELECT category, COUNT(*) FROM pipeline_dictionary GROUP BY category ORDER BY COUNT(*) DESC LIMIT 10"):
        print(f"    {row[0]}: {row[1]}")

    conn.close()

if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "all"
    if cmd == "all":
        create_tables()
        populate_scenario_weights()
        populate_domino_chains()
        populate_agent_keywords()
        populate_pipeline_dictionary()
        show_stats()
    elif cmd == "tables":
        create_tables()
    elif cmd == "scenarios":
        populate_scenario_weights()
    elif cmd == "keywords":
        populate_agent_keywords()
    elif cmd == "pipelines":
        populate_pipeline_dictionary()
    elif cmd == "dominos":
        populate_domino_chains()
    elif cmd == "stats":
        show_stats()
    else:
        print(f"Usage: {sys.argv[0]} [all|tables|scenarios|keywords|pipelines|dominos|stats]")
