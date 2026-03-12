#!/usr/bin/env python3
"""Signal tracker API — retourne JSON des signaux pour le proxy."""
import sqlite3, json, os, sys

db_path = os.path.join(os.path.dirname(__file__), '..', 'data', 'sniper_scan.db')
if not os.path.exists(db_path):
    print(json.dumps({'total':0,'open':0,'tp1':0,'tp2':0,'sl':0,'expired':0,'avg_pnl':0,'open_signals':[],'recent':[]}))
    sys.exit(0)

db = sqlite3.connect(db_path)
try:
    total = db.execute('SELECT COUNT(*) FROM signal_tracker').fetchone()[0]
    opened = db.execute("SELECT COUNT(*) FROM signal_tracker WHERE status='OPEN'").fetchone()[0]
    tp1 = db.execute('SELECT COUNT(*) FROM signal_tracker WHERE tp1_hit=1').fetchone()[0]
    tp2 = db.execute('SELECT COUNT(*) FROM signal_tracker WHERE tp2_hit=1').fetchone()[0]
    sl = db.execute('SELECT COUNT(*) FROM signal_tracker WHERE sl_hit=1').fetchone()[0]
    expired = db.execute("SELECT COUNT(*) FROM signal_tracker WHERE status='EXPIRED'").fetchone()[0]
    avg_pnl = db.execute("SELECT AVG(pnl_pct) FROM signal_tracker WHERE status != 'OPEN'").fetchone()[0] or 0
    open_sigs = db.execute("SELECT symbol, direction, score, validations, entry_price, tp1, sl, emitted_at FROM signal_tracker WHERE status='OPEN' ORDER BY id DESC LIMIT 10").fetchall()
    recent = db.execute('SELECT symbol, direction, score, status, pnl_pct FROM signal_tracker ORDER BY id DESC LIMIT 5').fetchall()
    print(json.dumps({
        'total': total, 'open': opened, 'tp1': tp1, 'tp2': tp2, 'sl': sl,
        'expired': expired, 'avg_pnl': avg_pnl,
        'open_signals': [{'s':r[0],'d':r[1],'sc':r[2],'v':r[3],'entry':r[4],'tp1':r[5],'sl':r[6],'at':r[7]} for r in open_sigs],
        'recent': [{'s':r[0],'d':r[1],'sc':r[2],'st':r[3],'pnl':r[4]} for r in recent]
    }))
except Exception as e:
    print(json.dumps({'total':0,'open':0,'tp1':0,'tp2':0,'sl':0,'expired':0,'avg_pnl':0,'open_signals':[],'recent':[],'error':str(e)}))
finally:
    db.close()
