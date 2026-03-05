"""Test rapide du Commander V2 - 5 commandes intent + TTS"""
import sys, os, time, json
sys.path.insert(0, r'F:\BUREAU\TRADING_V2_PRODUCTION\voice_system')
sys.path.insert(0, r'F:\BUREAU\TRADING_V2_PRODUCTION\scripts')

print('=' * 60)
print('  TEST COMMANDER V2 - 5 COMMANDES')
print('=' * 60)

from commander_v2 import analyze_intent_with_m2, local_fallback, speak, TTS_OK

print(f'\nTTS disponible: {TTS_OK}')
speak('Test vocal en cours')

tests = [
    'Lance un scan du marche',
    'Ouvre le bloc-notes',
    'Mets la fenetre a gauche',
    'Donne-moi le status des positions',
    'Monte le volume',
]

results = []
for i, cmd in enumerate(tests, 1):
    print(f'\n--- TEST {i}/5: "{cmd}" ---')
    t0 = time.time()

    result = analyze_intent_with_m2(cmd)
    dt = time.time() - t0

    if result.get('action') == 'UNKNOWN':
        fb = local_fallback(cmd)
        if fb:
            result = fb
            print(f'  FALLBACK LOCAL: {result}')

    action = result.get('action', 'UNKNOWN')
    params = result.get('params', '')
    ok = action != 'UNKNOWN'
    tag = 'OK' if ok else 'FAIL'
    print(f'  -> {tag} | Action: {action} | Params: {params} | {dt:.1f}s')
    results.append((cmd, action, params, dt, ok))

print('\n' + '=' * 60)
ok_count = sum(1 for r in results if r[4])
avg_time = sum(r[3] for r in results) / len(results)
print(f'  SCORE: {ok_count}/{len(tests)} | Latence moyenne: {avg_time:.1f}s')
print('=' * 60)

if ok_count == len(tests):
    speak(f'Tous les tests passes. Latence moyenne {avg_time:.0f} secondes.')
else:
    speak(f'{ok_count} sur {len(tests)} tests reussis.')
