#!/usr/bin/env python3
"""Test rapide: query 1 symbole sur les 4 IAs en parallele"""
import urllib.request, json, sys, time, subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.stdout.reconfigure(encoding='utf-8')
sys.stdout = open(sys.stdout.fileno(), mode='w', encoding='utf-8', buffering=1)

LM_SERVERS = {
    'M1': {'url': 'http://192.168.1.85:1234', 'model': 'qwen3-30b-a3b-128k'},
    'M2': {'url': 'http://192.168.1.26:1234', 'model': 'gpt-oss-20b'},
    'M3': {'url': 'http://192.168.1.113:1234', 'model': 'mistral-7b-instruct-v0.3'},
}
GEMINI_CLI = r'/home/turbo\AppData\Roaming\npm\gemini.cmd'

prompt = 'BTC_USDT prix 97500, change +2.1%, RSI 62, OB 1.3x BUY. Direction LONG SHORT ou NEUTRAL? Reponds JSON: {"direction":"...","confidence":0-100,"reason":"..."}'

def ask_lm(key):
    srv = LM_SERVERS[key]
    body = json.dumps({
        "model": srv['model'],
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.65, "max_tokens": 150
    }).encode('utf-8')
    t0 = time.time()
    try:
        req = urllib.request.Request(f"{srv['url']}/v1/chat/completions", data=body, headers={'Content-Type': 'application/json'})
        resp = urllib.request.urlopen(req, timeout=45)
        data = json.loads(resp.read())
        content = data['choices'][0]['message'].get('content', '')
        if not content:
            content = data['choices'][0]['message'].get('reasoning', '(empty)')
        return key, round(time.time()-t0, 1), content[:200]
    except Exception as e:
        return key, round(time.time()-t0, 1), f'ERROR: {e}'

def ask_gem():
    t0 = time.time()
    try:
        proc = subprocess.run([GEMINI_CLI, '-p', prompt], capture_output=True, text=True, timeout=25)
        out = (proc.stdout or proc.stderr or '').strip()[:200]
        return 'GEMINI', round(time.time()-t0, 1), out
    except Exception as e:
        return 'GEMINI', round(time.time()-t0, 1), f'ERROR: {e}'

print('=== TEST CLUSTER 4 IAs EN PARALLELE ===\n')
t_start = time.time()

with ThreadPoolExecutor(max_workers=4) as pool:
    futs = [pool.submit(ask_lm, k) for k in LM_SERVERS] + [pool.submit(ask_gem)]
    for f in as_completed(futs):
        key, elapsed, resp = f.result()
        status = 'OK' if 'ERROR' not in resp else 'FAIL'
        print(f'[{key:6}] {elapsed:5.1f}s {status} | {resp[:120]}')
        print()

print(f'\nTotal: {round(time.time()-t_start, 1)}s (parallele)')
