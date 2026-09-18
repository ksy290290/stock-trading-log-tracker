"""1회성 마이그레이션: 로컬 stock_journal.db의 데이터를 Turso로 복사.
ID를 그대로 보존해서 옮김 (편집/삭제 UI가 ID 기준이라 유지가 중요).

이미 Turso 쪽에 데이터가 있는 테이블은 건드리지 않고 건너뜀 - 실수로 두 번
실행해도 중복 삽입되지 않게 함.

사용법: TURSO_DATABASE_URL / TURSO_AUTH_TOKEN 환경변수를 설정한 뒤 실행.
"""
import os
import sqlite3

import libsql

LOCAL_DB = "stock_journal_local_source.db"

TABLES = {
    "trades": ["id", "ticker", "name", "market", "side", "quantity", "price", "fee", "tax",
               "fx_rate", "trade_date", "strategy_tag", "thesis", "created_at"],
    "dividends": ["id", "ticker", "name", "market", "pay_date", "amount", "tax", "fx_rate",
                  "note", "created_at"],
    "journal": ["id", "entry_date", "ticker", "title", "content", "category", "source_url",
                "created_at"],
    "targets": ["id", "ticker", "name", "market", "target_price", "stop_loss", "note",
                "manual_price", "set_date", "active"],
    "holding_notes": ["ticker", "market", "note", "updated_at"],
}


def main():
    url = os.environ["TURSO_DATABASE_URL"]
    token = os.environ["TURSO_AUTH_TOKEN"]

    local = sqlite3.connect(LOCAL_DB)
    local.row_factory = sqlite3.Row

    remote = libsql.connect(database=url, auth_token=token)
    rcur = remote.cursor()

    for table, cols in TABLES.items():
        rcur.execute(f"SELECT COUNT(*) FROM {table}")
        existing = rcur.fetchone()[0]
        if existing > 0:
            print(f"{table}: Turso에 이미 {existing}건 있음 - 건너뜀")
            continue

        rows = local.execute(f"SELECT {', '.join(cols)} FROM {table}").fetchall()
        if not rows:
            print(f"{table}: 로컬에 데이터 없음")
            continue

        placeholders = ", ".join(["?"] * len(cols))
        col_list = ", ".join(cols)
        for row in rows:
            rcur.execute(f"INSERT INTO {table} ({col_list}) VALUES ({placeholders})", tuple(row))
        remote.commit()
        print(f"{table}: {len(rows)}건 이전 완료")

    local.close()
    remote.close()


if __name__ == "__main__":
    main()
