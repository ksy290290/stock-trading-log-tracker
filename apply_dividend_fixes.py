"""export_unknown_dividends.py로 내보낸 뒤 사용자가 '정확한_티커'를 채운
엑셀을 읽어서, 해당 배당금 기록의 ticker/name/market을 업데이트한다.

Usage:
    python apply_dividend_fixes.py dividend_review.xlsx [--commit]

--commit 없이 실행하면 반영될 내용만 미리 보여주고 DB는 건드리지 않는다.
"""
import argparse

import pandas as pd

import db

ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
ap.add_argument("xlsx_path")
ap.add_argument("--commit", action="store_true")
args = ap.parse_args()

df = pd.read_excel(args.xlsx_path, sheet_name="UNKNOWN 배당금")

updates = []
for _, row in df.iterrows():
    ticker = str(row.get("정확한_티커") or "").strip()
    if not ticker or ticker.lower() == "nan":
        continue
    market = str(row.get("시장(KR/US)") or "KR").strip().upper()
    if market not in ("KR", "US"):
        market = "KR"
    ticker = ticker.upper() if market == "US" else ticker
    name = str(row.get("정확한_종목명") or "").strip()
    updates.append(
        {
            "id": int(row["id"]),
            "ticker": ticker,
            "name": name or None,
            "market": market,
            "지급일": row.get("지급일"),
            "입금액": row.get("입금액"),
        }
    )

if not updates:
    print("채워진 '정확한_티커'가 없습니다. 반영할 내용이 없어요.")
else:
    print(f"{len(updates)}건 반영 예정:")
    for u in updates:
        print(f"  id={u['id']} {u['지급일']} {u['입금액']} -> [{u['market']}] {u['ticker']} {u['name'] or ''}")

    if args.commit:
        for u in updates:
            db.update_dividend_ticker(u["id"], u["ticker"], u["name"], u["market"])
        print(f"\n{len(updates)}건 DB에 반영 완료.")
    else:
        print("\n(미리보기만 했습니다 - 실제로 반영하려면 --commit 을 붙여 다시 실행하세요)")
