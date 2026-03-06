# INSTRUCTIONS OPENCLAW — JARVIS Workspace

## COMMANDES TELEGRAM PRIORITAIRES

Quand l'utilisateur demande quelque chose sur Telegram, utilise les scripts dans `dev/` :

### EMAILS (mots-clés: mail, mails, email, emails, inbox, boite, courrier, lis mes mails)
```bash
python C:/Users/franc/.openclaw/workspace/dev/telegram_commander.py --cmd emails
```
OU directement en Python :
```python
import imaplib, email, json
from email.header import decode_header as dh
accounts = [
    {"email": "miningexpert31@gmail.com", "password": "ipicqcsimiitoxwj", "label": "mining"},
    {"email": "franckdelmas00@gmail.com", "password": "oetexwzoxuukjrgk", "label": "perso"},
]
# IMAP4_SSL('imap.gmail.com'), login, select INBOX, search ALL, fetch last 5-10
```
**Config complète** : `dev/email_config.json` (2 comptes Gmail avec app passwords)

### STATUS (mots-clés: status, état, système)
```bash
python C:/Users/franc/.openclaw/workspace/dev/telegram_commander.py --cmd status
```

### TRADING (mots-clés: trading, trade, signal, crypto)
```bash
python C:/Users/franc/.openclaw/workspace/dev/telegram_commander.py --cmd trading
```

### HEALTH (mots-clés: health, santé, check)
```bash
python C:/Users/franc/.openclaw/workspace/dev/telegram_commander.py --cmd health
```

### WORKSPACE (mots-clés: workspace, cowork, scripts)
```bash
python C:/Users/franc/.openclaw/workspace/dev/telegram_commander.py --cmd workspace
```

### REPORT (mots-clés: rapport, report, résumé)
```bash
python C:/Users/franc/.openclaw/workspace/dev/telegram_commander.py --cmd report
```

## RÉPONSES TELEGRAM
- Formate TOUJOURS les réponses avec des emojis
- Utilise les scripts existants dans dev/ plutôt que réinventer
- Ne demande JAMAIS de configuration — tout est déjà configuré
- Les credentials email sont dans `dev/email_config.json` et `jarvis_mail.py`

## SCRIPTS DISPONIBLES (64 dans dev/)
Voir `COWORK_TASKS.md` pour la liste complète.
