"""
Genere des exemples d'apprentissage vocal complets depuis les bases SQL.
Commandes, pipelines, corrections, scenarios, dominos, skills.
"""
import sqlite3
import json
import sys

sys.stdout.reconfigure(encoding='utf-8')

SYSTEM = (
    "Tu es JARVIS, un assistant vocal intelligent en francais. "
    "Tu controles un systeme Windows avec des commandes vocales, "
    "tu geres un cluster de modeles d'IA locale (LM Studio, Ollama), "
    "tu analyses les marches de trading crypto sur MEXC Futures, "
    "et tu assistes l'utilisateur dans toutes ses taches quotidiennes. "
    "Tu es concis, precis et naturel. Tu reponds toujours en francais. "
    "Tu executes les commandes sans hesiter quand tu es sur de l'intention. "
    "Tu demandes confirmation uniquement pour les actions destructives ou ambigues."
)

def mk(q, a):
    return {"messages": [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": q},
        {"role": "assistant", "content": a},
    ]}

examples = []

# === 1. COMMANDES depuis jarvis.db ===
print("[1/7] Commandes jarvis.db...")
conn = sqlite3.connect('F:/BUREAU/turbo/data/jarvis.db')
cur = conn.cursor()

rows = cur.execute(
    'SELECT name, description, triggers, category, action_type '
    'FROM commands WHERE triggers IS NOT NULL AND description IS NOT NULL'
).fetchall()

for name, desc, triggers_json, cat, action_type in rows:
    try:
        triggers = json.loads(triggers_json)
    except Exception:
        continue
    if not triggers or not desc:
        continue
    main_trigger = triggers[0]
    examples.append(mk(main_trigger, f"J'execute la commande {name}. {desc}"))
    if len(triggers) > 1:
        examples.append(mk(triggers[1], f"Compris. {desc}"))
    if cat:
        clean = main_trigger.replace('{', '').replace('}', '')
        alts = ', '.join(triggers[:3])
        examples.append(mk(
            f"comment {clean} ?",
            f'Dis simplement "{main_trigger}". Alternatives : {alts}. Categorie : {cat}.'
        ))

print(f"  -> {len(examples)} exemples")

# === 2. SKILLS depuis jarvis.db ===
print("[2/7] Skills jarvis.db...")
count_before = len(examples)
skills = cur.execute(
    'SELECT name, description, triggers, steps, category '
    'FROM skills WHERE triggers IS NOT NULL AND description IS NOT NULL'
).fetchall()

for name, desc, triggers_json, steps, cat in skills:
    try:
        triggers = json.loads(triggers_json)
    except Exception:
        continue
    if not triggers:
        continue
    main = triggers[0]
    examples.append(mk(main, f"J'active le skill {name}. {desc}"))
    if steps:
        try:
            step_list = json.loads(steps) if isinstance(steps, str) else steps
            if isinstance(step_list, list) and len(step_list) > 0:
                steps_txt = ", ".join([str(s) for s in step_list[:5]])
                examples.append(mk(
                    f"que fait {name} ?",
                    f'{desc} Etapes : {steps_txt}. Trigger : "{main}".'
                ))
        except Exception:
            pass
    for t in triggers[1:3]:
        examples.append(mk(t, f"Activation de {name}. {desc}"))

print(f"  -> {len(examples) - count_before} exemples")

# === 3. SCENARIOS depuis jarvis.db ===
print("[3/7] Scenarios jarvis.db...")
count_before = len(examples)
scenarios = cur.execute(
    'SELECT voice_input, expected_commands, category '
    'FROM scenarios WHERE voice_input IS NOT NULL AND expected_commands IS NOT NULL'
).fetchall()

for voice, commands_json, cat in scenarios:
    try:
        cmds = json.loads(commands_json) if isinstance(commands_json, str) else commands_json
    except Exception:
        cmds = [commands_json]
    if isinstance(cmds, list):
        flat = [str(c) if not isinstance(c, list) else ", ".join(c) for c in cmds[:3]]
        cmd_txt = ", ".join(flat)
    else:
        cmd_txt = str(cmds)
    examples.append(mk(voice, f"J'execute : {cmd_txt}."))

conn.close()
print(f"  -> {len(examples) - count_before} exemples")

# === 4. PIPELINES depuis etoile.db ===
print("[4/7] Pipelines etoile.db...")
count_before = len(examples)
conn2 = sqlite3.connect('F:/BUREAU/turbo/data/etoile.db')
cur2 = conn2.cursor()

pipelines = cur2.execute(
    'SELECT trigger_phrase, steps, category FROM pipeline_dictionary WHERE steps IS NOT NULL'
).fetchall()

for trigger, steps, cat in pipelines:
    if not trigger or not steps:
        continue
    clean = trigger.replace('{', '').replace('}', '')
    examples.append(mk(clean, f"Pipeline {cat or 'general'} : {steps}"))
    if cat:
        examples.append(mk(
            f"lance le pipeline {clean}",
            f"Execution du pipeline {cat} : {steps}"
        ))

print(f"  -> {len(examples) - count_before} exemples")

# === 5. CORRECTIONS VOCALES depuis etoile.db ===
print("[5/7] Corrections vocales etoile.db...")
count_before = len(examples)
corrections = cur2.execute(
    'SELECT wrong, correct, category, hit_count '
    'FROM voice_corrections WHERE hit_count >= 1 ORDER BY hit_count DESC'
).fetchall()

for wrong, correct, cat, hits in corrections:
    if not wrong or not correct:
        continue
    examples.append(mk(
        wrong,
        f'Je comprends : "{correct}". J\'execute la commande correspondante.'
    ))

print(f"  -> {len(examples) - count_before} exemples")

# === 6. DOMINOS depuis etoile.db ===
print("[6/7] Dominos etoile.db...")
count_before = len(examples)
dominos = cur2.execute(
    'SELECT trigger_cmd, condition, next_cmd, delay_ms '
    'FROM domino_chains WHERE next_cmd IS NOT NULL'
).fetchall()

for trigger, condition, next_cmd, delay in dominos[:150]:
    cond_txt = f" Si {condition}," if condition else ""
    delay_txt = f" apres {delay}ms" if delay and delay > 0 else ""
    examples.append(mk(
        f"que se passe-t-il apres {trigger} ?",
        f"Apres '{trigger}',{cond_txt} le systeme lance '{next_cmd}'{delay_txt}. Cascade domino."
    ))

conn2.close()
print(f"  -> {len(examples) - count_before} exemples")

# === 7. EXEMPLES GENERAUX VOCAL ===
print("[7/7] Exemples generaux vocal...")
count_before = len(examples)
vocal_general = [
    mk("jarvis", "Oui, je t'ecoute. Que puis-je faire pour toi ?"),
    mk("merci jarvis", "De rien ! N'hesite pas si tu as besoin d'autre chose."),
    mk("annule", "Commande annulee."),
    mk("stop", "J'arrete l'operation en cours."),
    mk("repete", "Je repete ma derniere reponse."),
    mk("c'est quoi les commandes vocales ?",
       "Tu peux me parler naturellement. J'ai plus de 1700 commandes vocales reparties en 283 pipelines. "
       "Categories : navigation, systeme, trading, dev, loisir, communication, productivite, routine. "
       "Dis 'jarvis' suivi de ta commande."),
    mk("quelles commandes tu connais ?",
       "Je connais des centaines de commandes : ouvrir des apps (chrome, vscode, discord), "
       "controler le systeme (volume, ecran, shutdown), gerer le cluster IA (health check, consensus), "
       "le trading (scan, pipeline, feedback), les modes (dev, gaming, focus, presentation), "
       "et les routines (matin, soir, pause)."),
    mk("aide",
       "Commandes principales : ouvre [app], cherche [texte], mode [nom], diagnostic, "
       "rapport matin, consensus [question], pipeline trading, volume [+/-], plein ecran, "
       "ferme tout, backup, audit systeme."),
    mk("t'es la jarvis ?", "Toujours la ! Pret a t'aider."),
    mk("qu'est-ce que tu sais faire ?",
       "Je suis JARVIS, ton assistant IA distribue. Je controle Windows par la voix, "
       "gere un cluster de 6 IA, analyse le trading crypto, ouvre des applications, "
       "diagnostique le systeme, et execute des pipelines. 76 outils MCP, 84 skills."),
    mk("comment tu marches ?",
       "Pipeline vocal : OpenWakeWord detecte 'jarvis', Whisper transcrit ta voix, "
       "le Mode Commandant classifie, puis j'execute via MCP. Latence < 2s."),
    mk("change le volume",
       "Volume ajuste. Dis 'volume plus', 'volume moins' ou 'mute'."),
    mk("mets en plein ecran", "Plein ecran active."),
    mk("ferme tout", "Je ferme toutes les fenetres non-essentielles."),
    mk("fais un backup",
       "Backup en cours : bases de donnees, configs et fichiers dans data/backups/."),
    mk("ouvre le terminal", "Terminal ouvert. Pret pour tes commandes."),
    mk("eteins le pc", "Tu es sur de vouloir eteindre le PC ? Dis 'confirme' pour valider."),
    mk("redemarre le pc", "Confirmation requise : dire 'confirme' pour redemarrer."),
    mk("quel temps fait-il ?", "Je consulte la meteo pour toi."),
    mk("quelle heure est-il ?", "Il est actuellement l'heure affichee dans la barre des taches Windows."),
    mk("mode nuit", "Mode nuit active : filtre bleu, luminosite reduite, notifications coupees."),
    mk("mode jour", "Mode jour active : luminosite normale, notifications restaurees."),
    mk("lance un diagnostic", "Diagnostic en cours : cluster, GPU, RAM, disque, reseau, services."),
    mk("comment va le cluster ?",
       "Je verifie les 6 noeuds : M1 (qwen3-8b), M2 (deepseek), M3 (mistral), "
       "OL1 (ollama), GEMINI, CLAUDE."),
    mk("lance le trading",
       "Mode trading active. Pipeline GPU v2.3 : 200 coins, 100 strategies, "
       "consensus 6 IA. Config MEXC Futures 10x."),
    mk("scan trading rapide",
       "Scan rapide en mode --quick (2 IA, 19s). Top 10 opportunites."),
]
examples.extend(vocal_general)
print(f"  -> {len(vocal_general)} exemples")

# === SAUVEGARDE ===
outfile = 'F:/BUREAU/turbo/finetuning/dataset/jarvis_vocal_teaching.jsonl'
with open(outfile, 'w', encoding='utf-8') as f:
    for ex in examples:
        f.write(json.dumps(ex, ensure_ascii=False) + '\n')

# Ajouter au dataset principal
with open('F:/BUREAU/turbo/finetuning/dataset/jarvis_final_train.jsonl', 'a', encoding='utf-8') as f:
    for ex in examples:
        f.write(json.dumps(ex, ensure_ascii=False) + '\n')

print(f"\n{'='*50}")
print(f"TOTAL: {len(examples)} exemples vocaux generes")
print(f"Fichier: {outfile}")

total = sum(1 for _ in open('F:/BUREAU/turbo/finetuning/dataset/jarvis_final_train.jsonl', encoding='utf-8'))
print(f"DATASET TOTAL: {total} exemples")
