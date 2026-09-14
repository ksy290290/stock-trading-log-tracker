"""Bulk-import a Toss Securities '거래내역서' (transaction statement) PDF into
the trading journal DB.

Toss has no public API, but the downloadable PDF statement is a real,
text-extractable transaction ledger, so a full history can be imported in one
shot instead of entering trades by hand one at a time.

Usage:
    python import_statement.py <path-to-statement.pdf>              # dry run, prints summary only
    python import_statement.py <path-to-statement.pdf> --commit     # actually writes to the DB

Re-running on the same (or an overlapping) statement is safe: rows are
deduped by count per (ticker, date, side, quantity, price) combo, not by
plain existence, so two genuinely separate trades that happen to share every
field (e.g. two identical auto-invest fills on the same day) both import,
while a true re-run of the same statement inserts nothing new.

Known limitations:
- Column layout is parsed by position (calibrated per-page from that page's
  own header row), not by Toss's internal export format, so a future
  statement with a different layout may need re-checking.
- Domestic (KRW) 분배금/배당금입금 rows carry no ticker name in Toss's own
  PDF, so they import with ticker="UNKNOWN" - fix them up manually in the
  배당금 tab if you want them attributed to a specific fund.
- US securities are identified by ISIN in the PDF; this script maps ISIN to
  a Yahoo Finance ticker via a small static table (ISIN_TO_TICKER below).
  A new ISIN not in that table imports with the ISIN itself as the ticker
  (live price lookup will fail until you add the mapping or override the
  price manually in the app).
"""
import argparse
import re
from collections import Counter, defaultdict

import db

NUMERIC_HEADERS = [
    "환율", "거래수량", "거래대금", "정산금액", "단가", "수수료", "거래세", "제세금", "변제/연체합", "잔고", "잔액",
]
NUMERIC_KEYS = ["fx", "qty", "amount", "settle", "unit_price", "fee", "tax", "withhold", "carry", "pos_qty", "cash"]
DATE_RE = re.compile(r"^\d{4}\.\d{2}\.\d{2}$")
CODE_RE = re.compile(r"\(([A-Za-z0-9]+)\)")
TRADE_TYPES = ("구매", "판매")
DIVIDEND_TYPES = ("분배금", "배당금입금", "외화증권배당금입금")

# ISIN -> Yahoo Finance ticker, verified by hand when first encountered.
# Add new entries here as new overseas holdings show up in future statements.
ISIN_TO_TICKER = {
    "US02079K3059": "GOOGL",
    "US30303M1027": "META",
    "US02376R1023": "AAL",
    "US40434L1052": "HPQ",
    "US1405011073": "CSWC",
    "US81369Y8030": "XLK",
    "US81369Y5069": "XLE",
    "US46269C1027": "IRDM",
    "US46138B1035": "DBC",
    "IL0065100930": "ZIM",
    "US8085247976": "SCHD",
    "US46434V6213": "DGRO",
    "US46654Q2030": "JEPQ",
    "US74743L1008": "Q",
    "US74347X8314": "TQQQ",
    "US25459W4583": "SOXL",
    "US37954Y2366": "DTCR",
    "US26922A4206": "QTUM",
    "US0321086649": "HACK",
    "US87975E7765": "NASA",
}


def num(s):
    if s is None:
        return 0.0
    return float(str(s).replace(",", ""))


def extract_rows(pdf_path):
    import pdfplumber

    rows = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            words = page.extract_words(use_text_flow=False, keep_blank_chars=False, x_tolerance=1)
            header_words = {w["text"]: w for w in words if w["text"] in NUMERIC_HEADERS}
            name_header = next((w for w in words if w["text"] == "종목명(종목코드)"), None)
            if len(header_words) < 6 or name_header is None:
                continue
            anchors = [
                (key, header_words[label]["x1"])
                for key, label in zip(NUMERIC_KEYS, NUMERIC_HEADERS)
                if label in header_words
            ]
            name_start_x = name_header["x0"]
            name_end_x = header_words["환율"]["x0"]

            rows_by_top = defaultdict(list)
            for w in words:
                rows_by_top[round(w["top"])].append(w)
            tops = sorted(rows_by_top.keys())
            used = set()
            merged = []
            for t in tops:
                if t in used:
                    continue
                group = list(rows_by_top[t])
                for t2 in tops:
                    if t2 != t and t2 not in used and abs(t2 - t) <= 3:
                        group.extend(rows_by_top[t2])
                        used.add(t2)
                used.add(t)
                group.sort(key=lambda w: w["x0"])
                merged.append(group)

            page_rows = []
            current = None
            for gs in merged:
                date_word = next((w for w in gs if DATE_RE.match(w["text"])), None)
                if date_word:
                    if current is not None:
                        page_rows.append(current)
                    current = {"words": list(gs), "extra_codes": []}
                elif current is not None:
                    code_match = next((CODE_RE.search(w["text"]) for w in gs if CODE_RE.search(w["text"])), None)
                    if code_match:
                        current["extra_codes"].append(f"({code_match.group(1)})")
            if current is not None:
                page_rows.append(current)

            for row in page_rows:
                gs = sorted(row["words"], key=lambda w: w["x0"])
                date_word = next(w for w in gs if DATE_RE.match(w["text"]))
                type_word = next((w for w in gs if date_word["x1"] <= w["x0"] < name_start_x), None)
                name_words = [w for w in gs if name_start_x <= w["x0"] < name_end_x]
                name_text = " ".join(w["text"] for w in sorted(name_words, key=lambda w: w["x0"]))
                if row["extra_codes"]:
                    name_text = f"{name_text}{row['extra_codes'][0]}"
                numeric_words = [w for w in gs if w["x0"] >= name_end_x and "$" not in w["text"]]
                values = {}
                for w in numeric_words:
                    best_key, _ = min(anchors, key=lambda c: abs(w["x1"] - c[1]))
                    values[best_key] = w["text"]
                rows.append({"date": date_word["text"], "type": type_word["text"] if type_word else None,
                             "name_raw": name_text, **values})
    return rows


def parse_name_code(name_raw):
    cleaned = re.sub(r"\s+[\d,]+\.\d{2}(?=\(|$)", "", name_raw).strip()
    m = re.search(r"^(.*?)\(([A-Za-z0-9]+)\)$", cleaned)
    if m:
        return m.group(1).strip(), m.group(2)
    return cleaned, None


def classify(code, name):
    if code and re.match(r"^A[A-Za-z0-9]{6}$", code):
        return "KR", code[1:]
    if code and re.match(r"^[A-Z]{2}[A-Za-z0-9]{10}$", code):
        ticker = ISIN_TO_TICKER.get(code, code)
        return "US", ticker
    return "KR", code or "UNKNOWN"


def build_trades(rows):
    out = []
    for r in rows:
        if r["type"] not in TRADE_TYPES:
            continue
        name, code = parse_name_code(r["name_raw"])
        market, ticker = classify(code, name)
        out.append(
            {
                "ticker": ticker,
                "name": name,
                "market": market,
                "side": "BUY" if r["type"] == "구매" else "SELL",
                "quantity": num(r.get("qty")),
                "price": num(r.get("unit_price")),
                "fee": num(r.get("fee")),
                "trade_date": r["date"].replace(".", "-"),
            }
        )
    return out


def build_dividends(rows):
    out = []
    for r in rows:
        if r["type"] not in DIVIDEND_TYPES:
            continue
        name, code = parse_name_code(r["name_raw"])
        if code:
            market, ticker = classify(code, name)
        elif r["type"] == "외화증권배당금입금":
            market, ticker = "US", name or "UNKNOWN"
        else:
            market, ticker = "KR", "UNKNOWN"
        out.append(
            {
                "ticker": ticker,
                "name": name or None,
                "market": market,
                "pay_date": r["date"].replace(".", "-"),
                "amount": num(r.get("settle") or r.get("amount")),
                "tax": num(r.get("withhold")),
                "note": "PDF 거래내역서 일괄 반영",
            }
        )
    return out


def existing_trade_keys():
    return [
        (t["ticker"], t["trade_date"], t["side"], round(t["quantity"], 4), round(t["price"], 2))
        for t in db.get_trades()
    ]


def existing_dividend_keys():
    return [
        (d["ticker"], d["pay_date"], round(d["amount"], 2))
        for d in db.get_dividends()
    ]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("pdf_path")
    ap.add_argument("--commit", action="store_true", help="actually write to the DB (default: dry run)")
    args = ap.parse_args()

    rows = extract_rows(args.pdf_path)
    trades = build_trades(rows)
    dividends = build_dividends(rows)

    by_ticker = defaultdict(lambda: {"market": None, "name": None, "buy": 0, "sell": 0})
    for t in trades:
        e = by_ticker[t["ticker"]]
        e["market"], e["name"] = t["market"], t["name"]
        e["buy" if t["side"] == "BUY" else "sell"] += 1

    print(f"parsed: {len(trades)} trades, {len(dividends)} dividends, {len(by_ticker)} distinct tickers")
    for ticker, e in sorted(by_ticker.items(), key=lambda kv: (kv[1]["market"], kv[0])):
        print(f"  [{e['market']}] {ticker:8s} {e['name']:20s} buy={e['buy']} sell={e['sell']}")

    if not args.commit:
        print("\n(dry run - pass --commit to write these into the DB)")
        return

    db.init_db()
    # counts, not sets: two genuinely separate trades can share every field
    # (same ticker/date/side/qty/price), so dedup by "how many of this exact
    # combo already exist" rather than "does this combo exist at all"
    existing_trade_counts = Counter(existing_trade_keys())
    existing_dividend_counts = Counter(existing_dividend_keys())
    seen_trades = Counter()
    seen_dividends = Counter()

    inserted_t = skipped_t = 0
    for t in trades:
        key = (t["ticker"], t["trade_date"], t["side"], round(t["quantity"], 4), round(t["price"], 2))
        seen_trades[key] += 1
        if seen_trades[key] <= existing_trade_counts[key]:
            skipped_t += 1
            continue
        db.add_trade(t["ticker"], t["name"], t["market"], t["side"], t["quantity"], t["price"],
                     t["fee"], t["trade_date"], None, None)
        inserted_t += 1

    inserted_d = skipped_d = 0
    for d in dividends:
        key = (d["ticker"], d["pay_date"], round(d["amount"], 2))
        seen_dividends[key] += 1
        if seen_dividends[key] <= existing_dividend_counts[key]:
            skipped_d += 1
            continue
        db.add_dividend(d["ticker"], d["name"], d["market"], d["pay_date"], d["amount"], d["tax"], d["note"])
        inserted_d += 1

    print(f"\ntrades: inserted {inserted_t}, skipped (already present) {skipped_t}")
    print(f"dividends: inserted {inserted_d}, skipped (already present) {skipped_d}")


if __name__ == "__main__":
    main()
