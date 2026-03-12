"""Scan MEXC Futures + Index dans KB en une commande"""
import requests, json, time, sqlite3, os
from datetime import datetime

DB_PATH = r"/home/turbo\TRADING_V2_PRODUCTION\database\trading.db"
LOGS_DIR = r"/home/turbo\TRADING_V2_PRODUCTION\logs"

def scan_mexc():
    """Scan tous les contrats MEXC futures"""
    r = requests.get("https://contract.mexc.com/api/v1/contract/ticker", timeout=15)
    tickers = r.json().get("data", [])

    futures = []
    for t in tickers:
        sym = t.get("symbol", "")
        if not sym.endswith("_USDT"):
            continue
        vol24 = float(t.get("volume24", 0))
        change = float(t.get("riseFallRate", 0)) * 100
        price = float(t.get("lastPrice", 0))
        high24 = float(t.get("high24Price", 0))
        low24 = float(t.get("low24Price", 0))
        funding = float(t.get("fundingRate", 0))

        if vol24 < 100000 or price <= 0 or high24 <= low24:
            continue

        range_pos = (price - low24) / (high24 - low24)

        score = 0
        direction = "WAIT"
        if range_pos > 0.85 and change > 2:
            score = range_pos * (1 + abs(change) / 100) * min(vol24 / 1_000_000, 5) * 20
            direction = "LONG"
        elif range_pos < 0.15 and change < -2:
            score = (1 - range_pos) * (1 + abs(change) / 100) * min(vol24 / 1_000_000, 5) * 20
            direction = "SHORT"
        elif range_pos > 0.80 and change > 0:
            score = range_pos * min(vol24 / 1_000_000, 3) * 10
            direction = "LONG"
        elif range_pos < 0.20 and change < 0:
            score = (1 - range_pos) * min(vol24 / 1_000_000, 3) * 10
            direction = "SHORT"

        futures.append({
            "symbol": sym, "price": price, "change24": round(change, 2),
            "volume24": vol24, "high24": high24, "low24": low24,
            "range_pos": round(range_pos, 3), "funding": round(funding, 6),
            "score": round(score, 1), "direction": direction,
        })

    futures.sort(key=lambda x: x["score"], reverse=True)
    return futures


def build_report(futures):
    """Genere le rapport markdown"""
    top_pump = sorted([f for f in futures if f["change24"] > 0], key=lambda x: x["change24"], reverse=True)[:10]
    top_dump = sorted([f for f in futures if f["change24"] < 0], key=lambda x: x["change24"])[:10]
    top_breakout = [f for f in futures if f["score"] > 10][:15]

    lines = []
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    lines.append(f"# SCAN MEXC FUTURES - {now}")
    lines.append(f"")
    lines.append(f"## Stats")
    lines.append(f"- Contrats scannes: {len(futures)}")
    lines.append(f"- Breakout signals: {len(top_breakout)}")
    lines.append(f"")
    lines.append(f"## TOP 10 PUMPS (+24h)")
    lines.append(f"| Symbol | Prix | Change | Volume | Range | Funding |")
    lines.append(f"|--------|------|--------|--------|-------|---------|")
    for f in top_pump:
        lines.append(f"| {f['symbol']} | {f['price']} | +{f['change24']}% | {f['volume24']:,.0f} | {f['range_pos']} | {f['funding']} |")
    lines.append(f"")
    lines.append(f"## TOP 10 DUMPS (-24h)")
    lines.append(f"| Symbol | Prix | Change | Volume | Range | Funding |")
    lines.append(f"|--------|------|--------|--------|-------|---------|")
    for f in top_dump:
        lines.append(f"| {f['symbol']} | {f['price']} | {f['change24']}% | {f['volume24']:,.0f} | {f['range_pos']} | {f['funding']} |")
    lines.append(f"")
    lines.append(f"## BREAKOUT SIGNALS (score > 10)")
    lines.append(f"| Symbol | Dir | Score | Prix | Change | Range | Volume | Funding |")
    lines.append(f"|--------|-----|-------|------|--------|-------|--------|---------|")
    for f in top_breakout:
        lines.append(f"| {f['symbol']} | {f['direction']} | {f['score']} | {f['price']} | {f['change24']}% | {f['range_pos']} | {f['volume24']:,.0f} | {f['funding']} |")

    return "\n".join(lines), top_pump, top_dump, top_breakout


def index_in_kb(report, report_path, top_pump, top_dump, top_breakout, futures_count):
    """Indexe le scan dans la Knowledge Base"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    title = f"Scan MEXC {datetime.now().strftime('%Y-%m-%d %H:%M')}"
    summary = (
        f"{futures_count} contrats, {len(top_breakout)} breakouts. "
        f"Top pump: {top_pump[0]['symbol']} +{top_pump[0]['change24']}%. "
        f"Top dump: {top_dump[0]['symbol']} {top_dump[0]['change24']}%."
    )
    tags = "mexc, scan, breakout, trading, futures, live"
    keywords = ", ".join([f["symbol"].replace("_USDT", "").lower() for f in top_breakout[:10]])

    c.execute("SELECT id FROM kb_categories WHERE name = ?", ("market_data",))
    cat_row = c.fetchone()
    cat_id = cat_row[0] if cat_row else 1

    c.execute(
        """INSERT INTO kb_documents
        (title, content, summary, category_id, source_path, source_type, file_type, file_size, tags, keywords, indexed_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)""",
        (title, report, summary, cat_id, report_path, "scan", ".md", len(report), tags, keywords),
    )
    doc_id = c.lastrowid

    # Chunks
    chunk_size = 1000
    chunk_count = 0
    for i in range(0, len(report), chunk_size):
        chunk = report[i : i + chunk_size]
        c.execute(
            "INSERT INTO kb_chunks (doc_id, chunk_text, chunk_index, chunk_size) VALUES (?, ?, ?, ?)",
            (doc_id, chunk, chunk_count, len(chunk)),
        )
        chunk_count += 1

    # Tags
    for tag_name in [t.strip() for t in tags.split(",") if t.strip()]:
        c.execute("INSERT OR IGNORE INTO kb_tags (name) VALUES (?)", (tag_name,))
        c.execute("SELECT id FROM kb_tags WHERE name = ?", (tag_name,))
        tag_id = c.fetchone()[0]
        c.execute("INSERT OR IGNORE INTO kb_doc_tags (doc_id, tag_id) VALUES (?, ?)", (doc_id, tag_id))

    # Counters
    c.execute(
        "UPDATE kb_categories SET doc_count = (SELECT COUNT(*) FROM kb_documents WHERE category_id = kb_categories.id AND is_active = 1)"
    )
    c.execute("UPDATE kb_tags SET doc_count = (SELECT COUNT(*) FROM kb_doc_tags WHERE tag_id = kb_tags.id)")
    conn.commit()

    c.execute("SELECT COUNT(*) FROM kb_documents WHERE is_active = 1")
    total = c.fetchone()[0]
    conn.close()

    return doc_id, chunk_count, total


def main():
    print("=" * 65)
    print("  SCAN MEXC + INDEX KB")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 65)

    # 1. Scan
    print("\n  [1/3] Scan MEXC Futures...")
    t0 = time.time()
    futures = scan_mexc()
    print(f"        {len(futures)} contrats en {time.time()-t0:.1f}s")

    # 2. Report
    print("  [2/3] Generation rapport...")
    report, top_pump, top_dump, top_breakout = build_report(futures)

    print(f"\n  TOP 5 PUMPS:")
    for f in top_pump[:5]:
        print(f"    {f['symbol']:20s} +{f['change24']:>6.1f}%  |  ${f['price']:<12}  |  vol {f['volume24']:>12,.0f}")
    print(f"\n  TOP 5 DUMPS:")
    for f in top_dump[:5]:
        print(f"    {f['symbol']:20s} {f['change24']:>6.1f}%  |  ${f['price']:<12}  |  vol {f['volume24']:>12,.0f}")
    print(f"\n  BREAKOUT SIGNALS ({len(top_breakout)}):")
    for f in top_breakout[:10]:
        print(f"    {f['direction']:5s} {f['symbol']:20s} score={f['score']:>6.1f}  |  {f['change24']:>+6.1f}%  |  range={f['range_pos']}  |  fund={f['funding']}")

    # 3. Save + Index
    print(f"\n  [3/3] Sauvegarde + indexation KB...")
    os.makedirs(LOGS_DIR, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_path = os.path.join(LOGS_DIR, f"scan_mexc_{ts}.md")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report)

    doc_id, chunks, total_kb = index_in_kb(report, report_path, top_pump, top_dump, top_breakout, len(futures))

    print(f"        Rapport: {report_path}")
    print(f"        KB: Doc #{doc_id} | {chunks} chunks | indexe")
    print(f"        KB total: {total_kb} documents")
    print(f"\n  DONE!")


if __name__ == "__main__":
    main()
