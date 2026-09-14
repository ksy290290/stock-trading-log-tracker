"""토스 PDF 반영 시 종목명이 없어 'UNKNOWN'으로 들어간 배당금 기록을 엑셀로
내보낸다. 직접 확인해서 '정확한_티커' 칸을 채운 뒤 apply_dividend_fixes.py로
다시 반영하면 된다.

Usage:
    python export_unknown_dividends.py [출력파일.xlsx]
"""
import sys

import pandas as pd

import db

OUT_PATH = sys.argv[1] if len(sys.argv) > 1 else "dividend_review.xlsx"

unknown = [dict(d) for d in db.get_dividends() if d["ticker"] == "UNKNOWN"]
if not unknown:
    print("UNKNOWN 티커인 배당금 기록이 없습니다.")
    sys.exit(0)

review_rows = []
for d in unknown:
    review_rows.append(
        {
            "id": d["id"],
            "지급일": d["pay_date"],
            "입금액": d["amount"],
            "원천징수세액": d["tax"],
            "정확한_티커": "",
            "정확한_종목명": "",
            "시장(KR/US)": "KR",
        }
    )
review_df = pd.DataFrame(review_rows)

holdings = sorted({(t["ticker"], t["name"]) for t in db.get_trades() if t["name"]})
holdings_df = pd.DataFrame(holdings, columns=["티커", "종목명"])

with pd.ExcelWriter(OUT_PATH, engine="openpyxl") as writer:
    review_df.to_excel(writer, sheet_name="UNKNOWN 배당금", index=False)
    holdings_df.to_excel(writer, sheet_name="참고 - 보유종목 티커", index=False)

print(f"{len(review_df)}건을 {OUT_PATH} 에 저장했습니다.")
print("'UNKNOWN 배당금' 시트의 '정확한_티커' 칸을 채운 뒤 apply_dividend_fixes.py로 반영하세요.")
