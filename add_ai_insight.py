"""CLI used by Claude to save researched news/공시/analysis into the
"AI 인사이트" tab, when the user asks in chat (e.g. "이번주 보유종목 이슈
정리해줘"). Claude does the actual web search / DART lookup itself and
writes the summary here - the app has no LLM wired into it.

Usage:
    python add_ai_insight.py --title "SCHD 배당 정책 변경" --ticker SCHD \
        --content "요약 내용..." --source-url https://example.com/article \
        --date 2026-09-14
"""
import argparse
from datetime import date

import db

ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
ap.add_argument("--title", required=True)
ap.add_argument("--content", required=True)
ap.add_argument("--ticker", default=None, help="관련 종목 티커 (선택)")
ap.add_argument("--source-url", default=None)
ap.add_argument("--date", default=None, help="YYYY-MM-DD (생략 시 오늘)")
args = ap.parse_args()

db.init_db()
entry_date = args.date or date.today().isoformat()
db.add_journal(
    entry_date,
    args.ticker,
    args.title,
    args.content,
    category="ai_insight",
    source_url=args.source_url,
)
print(f"AI 인사이트 저장 완료: [{entry_date}] {args.title}" + (f" ({args.ticker})" if args.ticker else ""))
