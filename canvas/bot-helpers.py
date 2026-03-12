"""Helper scripts for telegram-bot.js — avoids multiline execSync issues on Windows."""
import sys, json, os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

def domino_list():
    from src.domino_pipelines import DOMINO_PIPELINES, get_domino_stats
    stats = get_domino_stats()
    cats = {}
    for dp in DOMINO_PIPELINES:
        cats.setdefault(dp.category, []).append(dp.id.replace('domino_', ''))
    # Compact output: top 12 categories, max 4 IDs each (avoid JSON truncation)
    top = sorted(cats.items(), key=lambda x: -len(x[1]))[:12]
    out = {
        'stats': {
            'total_dominos': stats.get('total_dominos', len(DOMINO_PIPELINES)),
            'total_steps': stats.get('total_steps', 0),
            'critical_count': stats.get('critical_count', 0),
            'high_count': stats.get('high_count', 0),
            'categories_count': len(cats),
        },
        'categories': {cat: ids[:4] for cat, ids in top},
    }
    print(json.dumps(out))

def domino_find(name):
    from src.domino_pipelines import find_domino
    dp = find_domino(name)
    if dp:
        print(json.dumps({
            'found': True, 'id': dp.id, 'desc': dp.description,
            'steps': len(dp.steps), 'category': dp.category,
            'priority': dp.priority
        }))
    else:
        print(json.dumps({'found': False}))

def domino_run(name):
    from src.domino_pipelines import find_domino
    from src.domino_executor import DominoExecutor
    dp = find_domino(name)
    if not dp:
        print(json.dumps({'success': False, 'error': 'not found'}))
        return
    executor = DominoExecutor()
    result = executor.run(dp)
    print(json.dumps({
        'success': result.get('success', False),
        'passed': result.get('passed', 0),
        'failed': result.get('failed', 0),
        'skipped': result.get('skipped', 0),
        'duration': result.get('duration_s', 0),
        'steps': [
            {'name': s.get('step', '?'), 'status': s.get('status', '?')}
            for s in result.get('steps', result.get('results', []))[:20]
        ]
    }))

def scan_stats():
    import sqlite3
    db = sqlite3.connect(os.path.join(os.path.dirname(__file__), '..', 'data', 'sniper_scan.db'))
    scans = db.execute('SELECT COUNT(*) FROM scan_runs').fetchone()[0]
    snaps = db.execute('SELECT COUNT(*) FROM coin_snapshots').fetchone()[0]
    reg = db.execute('SELECT COUNT(*) FROM coin_registry').fetchone()[0]
    sigs = db.execute('SELECT COUNT(*) FROM scan_signals').fetchone()[0]
    last = db.execute(
        'SELECT id,ts,coins_scanned,signals_found,breakouts,duration_s '
        'FROM scan_runs ORDER BY id DESC LIMIT 1'
    ).fetchone()
    out = {'scans': scans, 'snapshots': snaps, 'registry': reg, 'signals': sigs}
    if last:
        out['last'] = {
            'id': last[0], 'ts': last[1], 'coins': last[2],
            'sigs': last[3], 'breaks': last[4], 'dur': last[5]
        }
    print(json.dumps(out))
    db.close()

def hot_coins(limit=10):
    import sqlite3
    db = sqlite3.connect(os.path.join(os.path.dirname(__file__), '..', 'data', 'sniper_scan.db'))
    rows = db.execute(
        'SELECT clean_name, scan_count, avg_score, best_score, best_direction, '
        'last_price, last_change FROM coin_registry '
        'WHERE best_score > 50 ORDER BY avg_score DESC LIMIT ?', (limit,)
    ).fetchall()
    print(json.dumps([{
        'name': r[0], 'scans': r[1], 'avg': r[2], 'best': r[3],
        'dir': r[4], 'price': r[5], 'chg': r[6]
    } for r in rows]))
    db.close()

def perf_stats():
    import sqlite3
    db = sqlite3.connect(os.path.join(os.path.dirname(__file__), '..', 'data', 'sniper_scan.db'))
    total = db.execute('SELECT COUNT(*) FROM signal_tracker').fetchone()[0]
    tp1 = db.execute("SELECT COUNT(*) FROM signal_tracker WHERE status='TP1_HIT'").fetchone()[0]
    tp2 = db.execute("SELECT COUNT(*) FROM signal_tracker WHERE status='TP2_HIT'").fetchone()[0]
    sl = db.execute("SELECT COUNT(*) FROM signal_tracker WHERE status='SL_HIT'").fetchone()[0]
    expired = db.execute("SELECT COUNT(*) FROM signal_tracker WHERE status='EXPIRED'").fetchone()[0]
    opn = db.execute("SELECT COUNT(*) FROM signal_tracker WHERE status='OPEN'").fetchone()[0]
    avg_pnl = db.execute('SELECT AVG(pnl_pct) FROM signal_tracker WHERE pnl_pct IS NOT NULL').fetchone()[0] or 0
    best = db.execute(
        'SELECT symbol, direction, score, pnl_pct FROM signal_tracker '
        'WHERE pnl_pct IS NOT NULL ORDER BY pnl_pct DESC LIMIT 5'
    ).fetchall()
    worst = db.execute(
        'SELECT symbol, direction, score, pnl_pct FROM signal_tracker '
        'WHERE pnl_pct IS NOT NULL ORDER BY pnl_pct ASC LIMIT 3'
    ).fetchall()
    print(json.dumps({
        'total': total, 'tp1': tp1, 'tp2': tp2, 'sl': sl,
        'expired': expired, 'open': opn, 'avg_pnl': avg_pnl,
        'best': [{'s': r[0], 'd': r[1], 'sc': r[2], 'pnl': r[3]} for r in best],
        'worst': [{'s': r[0], 'd': r[1], 'sc': r[2], 'pnl': r[3]} for r in worst],
    }))
    db.close()

def realtime_status():
    import sqlite3
    db = sqlite3.connect(os.path.join(os.path.dirname(__file__), '..', 'data', 'sniper_scan.db'))
    total = db.execute('SELECT COUNT(*) FROM signal_tracker').fetchone()[0]
    recent_open = db.execute("SELECT COUNT(*) FROM signal_tracker WHERE status='OPEN'").fetchone()[0]
    tp1 = db.execute("SELECT COUNT(*) FROM signal_tracker WHERE status='TP1_HIT'").fetchone()[0]
    sl = db.execute("SELECT COUNT(*) FROM signal_tracker WHERE status='SL_HIT'").fetchone()[0]
    expired = db.execute("SELECT COUNT(*) FROM signal_tracker WHERE status='EXPIRED'").fetchone()[0]
    last5 = db.execute(
        'SELECT symbol, direction, score, validations, status, pnl_pct '
        'FROM signal_tracker ORDER BY id DESC LIMIT 5'
    ).fetchall()
    print(json.dumps({
        'total': total, 'open': recent_open, 'tp1': tp1, 'sl': sl, 'expired': expired,
        'last5': [{'s': r[0].replace('_USDT',''), 'd': r[1], 'sc': r[2], 'v': r[3], 'st': r[4], 'pnl': r[5]} for r in last5]
    }))
    db.close()

def loop_status():
    import sqlite3
    db_path = os.path.join(os.path.dirname(__file__), '..', 'data', 'super_loop.db')
    if not os.path.exists(db_path):
        print(json.dumps({'exists': False}))
        return
    db = sqlite3.connect(db_path)
    try: cycles = db.execute('SELECT COUNT(*) FROM loop_cycles').fetchone()[0]
    except: cycles = 0
    try: issues = db.execute('SELECT COUNT(*) FROM discovered_issues WHERE fix_applied=0').fetchone()[0]
    except: issues = 0
    try: suggestions = db.execute('SELECT COUNT(*) FROM code_suggestions WHERE applied=0').fetchone()[0]
    except: suggestions = 0
    try:
        last = db.execute('SELECT cycle, domain, duration_s, ts FROM loop_cycles ORDER BY id DESC LIMIT 1').fetchone()
    except: last = None
    try:
        domains = db.execute('SELECT domain, COUNT(*), AVG(duration_s) FROM loop_cycles GROUP BY domain').fetchall()
    except: domains = []
    print(json.dumps({
        'exists': True, 'cycles': cycles, 'issues': issues, 'suggestions': suggestions,
        'last': {'cycle': last[0], 'domain': last[1], 'dur': last[2], 'ts': last[3]} if last else None,
        'domains': [{'d': r[0], 'count': r[1], 'avg_dur': r[2]} for r in domains]
    }))
    db.close()

def backtest():
    import sqlite3
    db = sqlite3.connect(os.path.join(os.path.dirname(__file__), '..', 'data', 'sniper_scan.db'))
    total = db.execute('SELECT COUNT(*) FROM scan_signals').fetchone()[0]
    bt_ok = db.execute("SELECT COUNT(*) FROM scan_signals WHERE pattern LIKE '%BACKTEST_OK%'").fetchone()[0]
    bt_warn = db.execute("SELECT COUNT(*) FROM scan_signals WHERE pattern LIKE '%BACKTEST_WARN%'").fetchone()[0]
    bt_tp1 = db.execute("SELECT COUNT(*) FROM signal_tracker st JOIN scan_signals ss ON st.symbol=ss.symbol WHERE ss.pattern LIKE '%BACKTEST_OK%' AND st.status='TP1_HIT'").fetchone()[0]
    bt_total_t = db.execute("SELECT COUNT(*) FROM signal_tracker st JOIN scan_signals ss ON st.symbol=ss.symbol WHERE ss.pattern LIKE '%BACKTEST_OK%'").fetchone()[0]
    nobt_tp1 = db.execute("SELECT COUNT(*) FROM signal_tracker st JOIN scan_signals ss ON st.symbol=ss.symbol WHERE ss.pattern NOT LIKE '%BACKTEST%' AND st.status='TP1_HIT'").fetchone()[0]
    nobt_total = db.execute("SELECT COUNT(*) FROM signal_tracker st JOIN scan_signals ss ON st.symbol=ss.symbol WHERE ss.pattern NOT LIKE '%BACKTEST%'").fetchone()[0]
    vwap = db.execute("SELECT COUNT(*) FROM scan_signals WHERE pattern LIKE '%VWAP%'").fetchone()[0]
    streak = db.execute("SELECT COUNT(*) FROM scan_signals WHERE pattern LIKE '%STREAK%' OR pattern LIKE '%streak%'").fetchone()[0]
    print(json.dumps({
        'total': total, 'bt_ok': bt_ok, 'bt_warn': bt_warn,
        'bt_tp1': bt_tp1, 'bt_total_t': bt_total_t,
        'nobt_tp1': nobt_tp1, 'nobt_total': nobt_total,
        'vwap': vwap, 'streak': streak
    }))
    db.close()

def market():
    import urllib.request
    data = json.loads(urllib.request.urlopen('https://contract.mexc.com/api/v1/contract/ticker', timeout=10).read().decode())
    tickers = [t for t in data.get('data', []) if t.get('symbol', '').endswith('_USDT')]
    tickers.sort(key=lambda t: abs(float(t.get('riseFallRate', 0))), reverse=True)
    top_movers = tickers[:10]
    up = sum(1 for t in tickers if float(t.get('riseFallRate', 0)) > 0)
    down = len(tickers) - up
    avg_change = sum(float(t.get('riseFallRate', 0)) for t in tickers) / max(len(tickers), 1) * 100
    btc = next((t for t in tickers if t['symbol'] == 'BTC_USDT'), None)
    btc_price = float(btc.get('lastPrice', 0)) if btc else 0
    btc_change = float(btc.get('riseFallRate', 0)) * 100 if btc else 0
    print(json.dumps({
        'total': len(tickers), 'up': up, 'down': down, 'avg_change': avg_change,
        'btc_price': btc_price, 'btc_change': btc_change,
        'movers': [{'s': t['symbol'].replace('_USDT',''), 'p': float(t.get('lastPrice',0)), 'c': float(t.get('riseFallRate',0))*100} for t in top_movers]
    }))

def proactive_alerts():
    import sqlite3
    db = sqlite3.connect(os.path.join(os.path.dirname(__file__), '..', 'data', 'sniper_scan.db'))
    hits = db.execute(
        "SELECT id, symbol, direction, entry_price, tp1, pnl_pct, score, status, checked_at "
        "FROM signal_tracker WHERE status IN ('TP1_HIT','TP2_HIT','TP3_HIT') "
        "AND checked_at > datetime('now', '-5 minutes') "
        "ORDER BY id DESC LIMIT 5"
    ).fetchall()
    sl_hits = db.execute(
        "SELECT id, symbol, direction, entry_price, sl, pnl_pct, score, checked_at "
        "FROM signal_tracker WHERE status = 'SL_HIT' "
        "AND checked_at > datetime('now', '-5 minutes') "
        "ORDER BY id DESC LIMIT 3"
    ).fetchall()
    print(json.dumps({
        'tp_hits': [{'id': r[0], 's': r[1].replace('_USDT',''), 'd': r[2], 'entry': r[3], 'tp1': r[4], 'pnl': r[5], 'sc': r[6], 'st': r[7]} for r in hits],
        'sl_hits': [{'id': r[0], 's': r[1].replace('_USDT',''), 'd': r[2], 'entry': r[3], 'sl': r[4], 'pnl': r[5], 'sc': r[6]} for r in sl_hits]
    }))
    db.close()

def disk_usage():
    import shutil
    c = shutil.disk_usage('/\')
    f = shutil.disk_usage('F:/')
    print(json.dumps({
        'C_free': round(c.free / 1e9), 'C_total': round(c.total / 1e9),
        'F_free': round(f.free / 1e9), 'F_total': round(f.total / 1e9)
    }))

def whales():
    import sqlite3
    db = sqlite3.connect(os.path.join(os.path.dirname(__file__), '..', 'data', 'sniper_scan.db'))
    rows = db.execute(
        'SELECT clean_name, scan_count, avg_score, best_direction, best_score, last_price '
        'FROM coin_registry WHERE best_score > 70 ORDER BY best_score DESC LIMIT 10'
    ).fetchall()
    print(json.dumps([{
        'sym': r[0], 'scans': r[1], 'avg': r[2], 'dir': r[3], 'best': r[4], 'price': r[5]
    } for r in rows]))
    db.close()

def analyze_coin_cmd(coin):
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'cowork', 'dev'))
    try:
        from sniper_scanner import fetch_klines, fetch_all_tickers, analyze_coin, format_signal
        tickers = fetch_all_tickers()
        t = next((t for t in tickers if t.get('symbol') == f'{coin}_USDT'), {})
        k = fetch_klines(f'{coin}_USDT', interval='Min15', limit=200)
        if k:
            sig = analyze_coin(f'{coin}_USDT', k, t, None)
            if sig:
                print(json.dumps({'ok': True, 'text': format_signal(sig, 1), 'score': sig.get('score', 0)}))
            else:
                print(json.dumps({'ok': True, 'text': f'Pas de signal fort pour {coin}/USDT'}))
        else:
            print(json.dumps({'ok': False, 'text': f'{coin}/USDT non trouve sur MEXC Futures'}))
    except Exception as e:
        print(json.dumps({'ok': False, 'text': f'Erreur analyse {coin}: {str(e)[:100]}'}))

def compare_coins(a, b):
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'cowork', 'dev'))
    try:
        from sniper_scanner import fetch_klines, fetch_all_tickers, analyze_coin, format_signal
        tickers = fetch_all_tickers()
        results = []
        for coin in [a, b]:
            t = next((t for t in tickers if t.get('symbol') == coin + '_USDT'), {})
            k = fetch_klines(coin + '_USDT', interval='Min15', limit=200)
            if k:
                sig = analyze_coin(coin + '_USDT', k, t, None)
                if sig:
                    results.append(sig)
        lines = []
        if len(results) == 2:
            best = results[0] if results[0]['score'] >= results[1]['score'] else results[1]
            for i, sig in enumerate(results):
                lines.append(format_signal(sig, i + 1))
            winner = results[0]['symbol'].replace('_USDT', '') if results[0]['score'] >= results[1]['score'] else results[1]['symbol'].replace('_USDT', '')
            lines.append(f"Verdict: {winner} est plus fort (score {best['score']}/100)")
        elif len(results) == 1:
            lines.append(format_signal(results[0], 1))
            lines.append("L'autre coin n'a pas de signal assez fort")
        else:
            lines.append('Aucun signal fort pour ces deux coins')
        print(json.dumps({'ok': True, 'text': '\n'.join(lines)}))
    except Exception as e:
        print(json.dumps({'ok': False, 'text': f'Erreur comparaison {a} vs {b}: {str(e)[:100]}'}))

def match_cmd(text):
    try:
        from src.commands import match_command
        cmd, p, s = match_command(text)
        print(json.dumps({
            'name': cmd.name if cmd else None,
            'action': cmd.action if cmd else None,
            'action_type': cmd.action_type if cmd else None,
            'params': p, 'score': s,
            'desc': cmd.description if cmd else None
        }))
    except Exception as e:
        print(json.dumps({'name': None, 'score': 0, 'error': str(e)[:100]}))

if __name__ == '__main__':
    cmd = sys.argv[1] if len(sys.argv) > 1 else 'help'
    if cmd == 'domino-list':
        domino_list()
    elif cmd == 'domino-find':
        domino_find(sys.argv[2] if len(sys.argv) > 2 else '')
    elif cmd == 'domino-run':
        domino_run(sys.argv[2] if len(sys.argv) > 2 else '')
    elif cmd == 'scan-stats':
        scan_stats()
    elif cmd == 'hot-coins':
        hot_coins(int(sys.argv[2]) if len(sys.argv) > 2 else 10)
    elif cmd == 'perf':
        perf_stats()
    elif cmd == 'realtime':
        realtime_status()
    elif cmd == 'loop-status':
        loop_status()
    elif cmd == 'backtest':
        backtest()
    elif cmd == 'market':
        market()
    elif cmd == 'proactive-alerts':
        proactive_alerts()
    elif cmd == 'disk':
        disk_usage()
    elif cmd == 'whales':
        whales()
    elif cmd == 'match-cmd':
        match_cmd(' '.join(sys.argv[2:]) if len(sys.argv) > 2 else '')
    elif cmd == 'analyze':
        analyze_coin_cmd((sys.argv[2] if len(sys.argv) > 2 else 'BTC').upper())
    elif cmd == 'compare':
        a = (sys.argv[2] if len(sys.argv) > 2 else 'BTC').upper()
        b = (sys.argv[3] if len(sys.argv) > 3 else 'ETH').upper()
        compare_coins(a, b)
    else:
        print(json.dumps({'error': f'Unknown command: {cmd}', 'commands': [
            'domino-list', 'domino-find <name>', 'domino-run <name>',
            'scan-stats', 'hot-coins [limit]', 'perf', 'realtime',
            'loop-status', 'backtest', 'market', 'proactive-alerts',
            'disk', 'whales', 'match-cmd <text>'
        ]}))
