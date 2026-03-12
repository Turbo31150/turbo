#!/usr/bin/env python3
"""ia_data_synthesizer.py — Realistic data synthesizer with French locale.
COWORK #236 — Batch 106: IA Generative

Usage:
    python dev/ia_data_synthesizer.py --generate '{"nom":"str","email":"str","age":"int","ville":"str"}' --rows 10
    python dev/ia_data_synthesizer.py --format csv
    python dev/ia_data_synthesizer.py --validate
    python dev/ia_data_synthesizer.py --once
"""
import argparse, json, sqlite3, time, subprocess, os, random, string, hashlib
from datetime import datetime, timedelta
from pathlib import Path

DEV = Path(__file__).parent
DB_PATH = DEV / "data" / "data_synthesizer.db"

# French data pools
PRENOMS_H = ["Jean", "Pierre", "Michel", "Andre", "Philippe", "Jacques", "Bernard", "Alain",
             "Francois", "Robert", "Louis", "Thomas", "Nicolas", "Julien", "Antoine",
             "Alexandre", "Maxime", "Hugo", "Lucas", "Mathieu", "Gabriel", "Leo"]
PRENOMS_F = ["Marie", "Jeanne", "Catherine", "Nathalie", "Isabelle", "Sylvie", "Sophie",
             "Monique", "Christine", "Valerie", "Camille", "Lea", "Chloe", "Emma",
             "Julie", "Clara", "Manon", "Sarah", "Alice", "Louise", "Jade"]
NOMS = ["Martin", "Bernard", "Dubois", "Thomas", "Robert", "Richard", "Petit", "Durand",
        "Leroy", "Moreau", "Simon", "Laurent", "Lefebvre", "Michel", "Garcia", "David",
        "Bertrand", "Roux", "Vincent", "Fournier", "Morel", "Girard", "Andre", "Mercier",
        "Dupont", "Lambert", "Bonnet", "Fontaine", "Rousseau", "Blanc"]
VILLES = ["Paris", "Marseille", "Lyon", "Toulouse", "Nice", "Nantes", "Strasbourg",
          "Montpellier", "Bordeaux", "Lille", "Rennes", "Reims", "Le Havre", "Toulon",
          "Grenoble", "Dijon", "Angers", "Nimes", "Clermont-Ferrand", "Tours"]
CODES_POSTAUX = {"Paris": "75001", "Marseille": "13001", "Lyon": "69001", "Toulouse": "31000",
                 "Nice": "06000", "Nantes": "44000", "Strasbourg": "67000", "Montpellier": "34000",
                 "Bordeaux": "33000", "Lille": "59000", "Rennes": "35000", "Reims": "51100",
                 "Le Havre": "76600", "Toulon": "83000", "Grenoble": "38000", "Dijon": "21000",
                 "Angers": "49000", "Nimes": "30000", "Clermont-Ferrand": "63000", "Tours": "37000"}
RUES = ["Rue de la Paix", "Avenue des Champs-Elysees", "Boulevard Haussmann",
        "Rue du Faubourg Saint-Honore", "Rue de Rivoli", "Avenue Victor Hugo",
        "Rue Pasteur", "Boulevard Voltaire", "Rue de la Republique", "Avenue Jean Jaures",
        "Rue Gambetta", "Place de la Mairie", "Impasse des Lilas", "Chemin du Moulin"]
ENTREPRISES = ["Societe Generale", "TotalEnergies", "LVMH", "Carrefour", "Orange",
               "Renault", "BNP Paribas", "AXA", "Danone", "Air France",
               "Michelin", "Bouygues", "Capgemini", "Dassault", "Thales"]
DOMAINES = ["gmail.com", "orange.fr", "free.fr", "outlook.com", "yahoo.fr",
            "hotmail.fr", "laposte.net", "sfr.fr", "wanadoo.fr"]

def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(DB_PATH))
    db.execute("""CREATE TABLE IF NOT EXISTS generation_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts TEXT NOT NULL,
        schema_json TEXT NOT NULL,
        rows_generated INTEGER,
        format TEXT DEFAULT 'json',
        output_file TEXT,
        duration_ms INTEGER
    )""")
    db.execute("""CREATE TABLE IF NOT EXISTS validation_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts TEXT NOT NULL,
        generation_id INTEGER,
        total_rows INTEGER,
        valid_rows INTEGER,
        issues TEXT
    )""")
    db.commit()
    return db

def generate_value(field_type, field_name=""):
    """Generate a realistic value based on type and field name."""
    fname = field_name.lower()

    if field_type == "str":
        if "prenom" in fname or "first" in fname:
            return random.choice(PRENOMS_H + PRENOMS_F)
        elif "nom" in fname or "last" in fname or "name" in fname:
            if "complet" in fname or "full" in fname:
                prenom = random.choice(PRENOMS_H + PRENOMS_F)
                nom = random.choice(NOMS)
                return f"{prenom} {nom}"
            return random.choice(NOMS)
        elif "email" in fname or "mail" in fname:
            prenom = random.choice(PRENOMS_H + PRENOMS_F).lower()
            nom = random.choice(NOMS).lower()
            domaine = random.choice(DOMAINES)
            sep = random.choice([".", "_", ""])
            return f"{prenom}{sep}{nom}@{domaine}"
        elif "ville" in fname or "city" in fname:
            return random.choice(VILLES)
        elif "adresse" in fname or "address" in fname or "rue" in fname:
            num = random.randint(1, 150)
            rue = random.choice(RUES)
            return f"{num} {rue}"
        elif "code_postal" in fname or "zip" in fname:
            return random.choice(list(CODES_POSTAUX.values()))
        elif "tel" in fname or "phone" in fname:
            return f"06{random.randint(10000000, 99999999)}"
        elif "entreprise" in fname or "company" in fname:
            return random.choice(ENTREPRISES)
        elif "pays" in fname or "country" in fname:
            return "France"
        elif "url" in fname or "site" in fname:
            return f"https://www.{random.choice(NOMS).lower()}.fr"
        else:
            return ''.join(random.choices(string.ascii_lowercase, k=random.randint(5, 15)))

    elif field_type == "int":
        if "age" in fname:
            return random.randint(18, 85)
        elif "annee" in fname or "year" in fname:
            return random.randint(1960, 2025)
        elif "montant" in fname or "amount" in fname or "prix" in fname or "price" in fname:
            return random.randint(10, 50000)
        elif "quantite" in fname or "qty" in fname:
            return random.randint(1, 100)
        elif "id" in fname:
            return random.randint(1000, 99999)
        else:
            return random.randint(0, 1000)

    elif field_type == "float":
        if "montant" in fname or "amount" in fname or "prix" in fname:
            return round(random.uniform(1.0, 10000.0), 2)
        elif "note" in fname or "score" in fname:
            return round(random.uniform(0, 20), 1)
        elif "lat" in fname:
            return round(random.uniform(42.0, 51.0), 6)
        elif "lon" in fname:
            return round(random.uniform(-5.0, 8.0), 6)
        else:
            return round(random.uniform(0, 100), 2)

    elif field_type == "date":
        base = datetime(2020, 1, 1)
        delta = random.randint(0, 2000)
        return (base + timedelta(days=delta)).strftime("%Y-%m-%d")

    elif field_type == "datetime":
        base = datetime(2020, 1, 1)
        delta = random.randint(0, 2000 * 24 * 60)
        return (base + timedelta(minutes=delta)).strftime("%Y-%m-%d %H:%M:%S")

    elif field_type == "bool":
        return random.choice([True, False])

    elif field_type == "uuid":
        return hashlib.md5(f"{time.time()}_{random.random()}".encode()).hexdigest()

    else:
        return f"unknown_type_{field_type}"

def do_generate(schema_str, rows=10, fmt="json"):
    db = init_db()
    start = time.time()

    try:
        schema = json.loads(schema_str)
    except json.JSONDecodeError:
        return {"error": f"Invalid JSON schema: {schema_str[:100]}"}

    data = []
    for _ in range(rows):
        row = {}
        for field_name, field_type in schema.items():
            row[field_name] = generate_value(field_type, field_name)
        data.append(row)

    elapsed = int((time.time() - start) * 1000)

    # Save to DB
    db.execute("INSERT INTO generation_log (ts, schema_json, rows_generated, format, duration_ms) VALUES (?,?,?,?,?)",
               (datetime.now().isoformat(), json.dumps(schema), rows, fmt, elapsed))
    db.commit()

    # Format output
    if fmt == "csv":
        lines = [",".join(schema.keys())]
        for row in data:
            lines.append(",".join(str(row.get(k, "")) for k in schema.keys()))
        output = "\n".join(lines)
        result = {
            "action": "generate",
            "format": "csv",
            "schema": schema,
            "rows": rows,
            "csv_output": output,
            "duration_ms": elapsed,
            "ts": datetime.now().isoformat()
        }
    else:
        result = {
            "action": "generate",
            "format": "json",
            "schema": schema,
            "rows": rows,
            "data": data,
            "duration_ms": elapsed,
            "ts": datetime.now().isoformat()
        }

    db.close()
    return result

def do_format(fmt):
    return {
        "action": "format_info",
        "supported_formats": ["json", "csv"],
        "supported_types": {
            "str": "String — auto-detects by field name (nom, email, ville, tel, etc.)",
            "int": "Integer — auto-detects (age, montant, quantite, id)",
            "float": "Float — auto-detects (prix, note, score, lat, lon)",
            "date": "Date — format YYYY-MM-DD",
            "datetime": "DateTime — format YYYY-MM-DD HH:MM:SS",
            "bool": "Boolean — True/False",
            "uuid": "UUID — MD5-based unique ID"
        },
        "smart_fields": [
            "nom/name → French surname", "prenom/first → French first name",
            "email → realistic FR email", "ville/city → French city",
            "adresse/address → French street address", "tel/phone → FR mobile",
            "entreprise/company → French company", "code_postal/zip → FR postal code"
        ],
        "ts": datetime.now().isoformat()
    }

def do_validate():
    db = init_db()
    last = db.execute("SELECT id, schema_json, rows_generated FROM generation_log ORDER BY id DESC LIMIT 1").fetchone()
    if not last:
        db.close()
        return {"action": "validate", "message": "No generations to validate"}

    schema = json.loads(last[1])
    issues = []

    # Validate schema types
    valid_types = {"str", "int", "float", "date", "datetime", "bool", "uuid"}
    for field, ftype in schema.items():
        if ftype not in valid_types:
            issues.append(f"Unknown type '{ftype}' for field '{field}'")

    result = {
        "action": "validate",
        "generation_id": last[0],
        "schema": schema,
        "rows_generated": last[2],
        "schema_valid": len(issues) == 0,
        "issues": issues,
        "ts": datetime.now().isoformat()
    }
    db.close()
    return result

def do_once():
    db = init_db()
    total = db.execute("SELECT COUNT(*) FROM generation_log").fetchone()[0]
    total_rows = db.execute("SELECT SUM(rows_generated) FROM generation_log").fetchone()[0] or 0
    result = {
        "status": "ok",
        "total_generations": total,
        "total_rows_generated": total_rows,
        "supported_types": ["str", "int", "float", "date", "datetime", "bool", "uuid"],
        "smart_fields": ["nom", "prenom", "email", "ville", "adresse", "tel", "entreprise", "code_postal"],
        "locale": "fr-FR",
        "ts": datetime.now().isoformat()
    }
    db.close()
    return result

def main():
    parser = argparse.ArgumentParser(description="IA Data Synthesizer — COWORK #236")
    parser.add_argument("--generate", type=str, metavar="SCHEMA", help="Generate data from JSON schema")
    parser.add_argument("--rows", type=int, default=10, help="Number of rows (default: 10)")
    parser.add_argument("--format", type=str, default="json", help="Output format (json/csv)")
    parser.add_argument("--validate", action="store_true", help="Validate last generation")
    parser.add_argument("--once", action="store_true", help="One-shot status check")
    args = parser.parse_args()

    if args.generate:
        print(json.dumps(do_generate(args.generate, args.rows, args.format), ensure_ascii=False, indent=2))
    elif args.validate:
        print(json.dumps(do_validate(), ensure_ascii=False, indent=2))
    elif args.format and not args.generate:
        print(json.dumps(do_format(args.format), ensure_ascii=False, indent=2))
    else:
        print(json.dumps(do_once(), ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
