import argparse
import json
import os
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime

def parse_log_line(line):
    # Simple parser: assume format "[YYYY-MM-DD HH:MM:SS] LEVEL message"
    match = re.match(r"\[(?P<ts>[^\]]+)\]\s+(?P<level>\w+)\s+(?P<msg>.*)", line)
    if not match:
        return None
    ts_str = match.group('ts')
    try:
        ts = datetime.strptime(ts_str, "%Y-%m-%d %H:%M:%S")
    except ValueError:
        ts = None
    return {
        'timestamp': ts_str,
        'datetime': ts,
        'level': match.group('level'),
        'message': match.group('msg')
    }

def analyze_log(path, include_errors=False, detect_trends=False):
    if not os.path.isfile(path):
        raise FileNotFoundError(f"Log file not found: {path}")
    with open(path, 'r', encoding='utf-8', errors='ignore') as f:
        lines = f.readlines()
    entries = []
    for line in lines:
        parsed = parse_log_line(line.strip())
        if parsed:
            entries.append(parsed)
    result = {}
    if include_errors:
        errors = [e for e in entries if e['level'].upper() in ('ERROR', 'CRITICAL', 'FAIL')]
        result['errors'] = [{'timestamp': e['timestamp'], 'message': e['message']} for e in errors]
    if detect_trends:
        # Simple trend: count occurrences of words in error messages over time (by hour)
        trend = defaultdict(Counter)
        for e in entries:
            if e['level'].upper() in ('ERROR', 'CRITICAL', 'FAIL'):
                hour = e['timestamp'][:13] if e['timestamp'] else 'unknown'
                words = re.findall(r"\b\w{4,}\b", e['message'].lower())
                trend[hour].update(words)
        # Convert to dict of hour -> most common words
        trend_summary = {hour: cnt.most_common(5) for hour, cnt in trend.items()}
        result['trends'] = trend_summary
    return result

def main():
    parser = argparse.ArgumentParser(description='Analyseur de logs simple.')
    parser.add_argument('logfile', help='Chemin vers le fichier .log à analyser')
    parser.add_argument('--analyze', action='store_true', help='Effectuer l\'analyse (par défaut)')
    parser.add_argument('--errors', action='store_true', help='Inclure les erreurs dans le rapport')
    parser.add_argument('--trends', action='store_true', help='Détecter les tendances d\'erreurs')
    parser.add_argument('--report', action='store_true', help='Sortie du rapport au format JSON')
    args = parser.parse_args()
    # Default behavior is analysis
    if not any([args.errors, args.trends, args.report]):
        args.errors = args.trends = args.report = True
    try:
        data = analyze_log(args.logfile, include_errors=args.errors, detect_trends=args.trends)
        if args.report:
            json.dump(data, sys.stdout, ensure_ascii=False, indent=2, default=str)
        else:
            # pretty print simple summary
            if args.errors:
                print(f"Found {len(data.get('errors', []))} error entries.")
            if args.trends:
                print(f"Detected trends for {len(data.get('trends', {}))} time buckets.")
    except Exception as e:
        parser.error(str(e))

if __name__ == '__main__':
    main()
