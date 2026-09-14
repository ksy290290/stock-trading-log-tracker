"""CLI used by Claude to record a trade/dividend after reading a Toss
Securities screenshot dropped in screenshots_inbox/.

Workflow: user drops a screenshot in screenshots_inbox/, then asks Claude to
process it. Claude reads the image, extracts the fields, shows them back to
the user for a quick sanity check, then calls this script to write the
record and archive the source screenshot.

Usage:
    python import_from_screenshot.py trade --market KR --ticker 005930 \
        --name 삼성전자 --side BUY --quantity 10 --price 71000 --date 2026-09-14 \
        --thesis "실적 발표 후 저가 매수" --source-file screenshots_inbox/capture1.png

    python import_from_screenshot.py dividend --market US --ticker AAPL \
        --amount 12000 --date 2026-09-14 --source-file screenshots_inbox/capture2.png
"""
import argparse
import shutil
import sys
from datetime import datetime
from pathlib import Path

import db

BASE_DIR = Path(__file__).parent
PROCESSED_DIR = BASE_DIR / "screenshots_processed"


def archive_source_file(source_file: str):
    src = Path(source_file)
    if not src.is_absolute():
        src = BASE_DIR / src
    if not src.exists():
        print(f"경고: 원본 스크린샷을 찾을 수 없습니다: {src}", file=sys.stderr)
        return
    PROCESSED_DIR.mkdir(exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    dest = PROCESSED_DIR / f"{stamp}_{src.name}"
    shutil.move(str(src), str(dest))
    print(f"스크린샷 보관 완료: {dest}")


def cmd_trade(args):
    db.init_db()
    db.add_trade(
        ticker=args.ticker.strip().upper() if args.market == "US" else args.ticker.strip(),
        name=args.name,
        market=args.market,
        side=args.side,
        quantity=args.quantity,
        price=args.price,
        fee=args.fee,
        trade_date=args.date,
        strategy_tag=args.tag,
        thesis=args.thesis,
    )
    print(
        f"매매 기록 추가: [{args.market}] {args.ticker} {args.side} "
        f"{args.quantity}주 @ {args.price} ({args.date})"
    )
    if args.source_file:
        archive_source_file(args.source_file)


def cmd_dividend(args):
    db.init_db()
    db.add_dividend(
        ticker=args.ticker.strip().upper() if args.market == "US" else args.ticker.strip(),
        name=args.name,
        market=args.market,
        pay_date=args.date,
        amount=args.amount,
        tax=args.tax,
        note=args.note,
    )
    print(f"배당금 기록 추가: [{args.market}] {args.ticker} {args.amount} ({args.date})")
    if args.source_file:
        archive_source_file(args.source_file)


def build_parser():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    p_trade = sub.add_parser("trade", help="매매(매수/매도) 기록 추가")
    p_trade.add_argument("--market", choices=["KR", "US"], required=True)
    p_trade.add_argument("--ticker", required=True)
    p_trade.add_argument("--name", default=None)
    p_trade.add_argument("--side", choices=["BUY", "SELL"], required=True)
    p_trade.add_argument("--quantity", type=float, required=True)
    p_trade.add_argument("--price", type=float, required=True)
    p_trade.add_argument("--fee", type=float, default=0.0)
    p_trade.add_argument("--date", required=True, help="YYYY-MM-DD")
    p_trade.add_argument("--tag", default=None, help="전략/태그")
    p_trade.add_argument("--thesis", default=None, help="매매 사유/근거")
    p_trade.add_argument("--source-file", default=None, help="처리 후 보관할 원본 스크린샷 경로")
    p_trade.set_defaults(func=cmd_trade)

    p_div = sub.add_parser("dividend", help="배당금 기록 추가")
    p_div.add_argument("--market", choices=["KR", "US"], required=True)
    p_div.add_argument("--ticker", required=True)
    p_div.add_argument("--name", default=None)
    p_div.add_argument("--date", required=True, help="YYYY-MM-DD")
    p_div.add_argument("--amount", type=float, required=True, help="세후 실수령액")
    p_div.add_argument("--tax", type=float, default=0.0)
    p_div.add_argument("--note", default=None)
    p_div.add_argument("--source-file", default=None, help="처리 후 보관할 원본 스크린샷 경로")
    p_div.set_defaults(func=cmd_dividend)

    return parser


if __name__ == "__main__":
    parser = build_parser()
    ns = parser.parse_args()
    ns.func(ns)
