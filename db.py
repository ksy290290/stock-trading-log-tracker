import sqlite3
from datetime import datetime
from pathlib import Path

DB_PATH = Path(__file__).parent / "stock_journal.db"


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS trades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticker TEXT NOT NULL,
            name TEXT,
            market TEXT NOT NULL,       -- 'KR' or 'US'
            side TEXT NOT NULL,         -- 'BUY' or 'SELL'
            quantity REAL NOT NULL,
            price REAL NOT NULL,
            fee REAL DEFAULT 0,
            tax REAL DEFAULT 0,          -- 매도 시 증권거래세 등
            fx_rate REAL,                -- 해외주식 체결 시점 원/달러 환율 (국내주식은 NULL)
            trade_date TEXT NOT NULL,
            strategy_tag TEXT,
            thesis TEXT,
            created_at TEXT NOT NULL
        )
        """
    )
    existing_cols = {row["name"] for row in cur.execute("PRAGMA table_info(trades)").fetchall()}
    if "tax" not in existing_cols:
        cur.execute("ALTER TABLE trades ADD COLUMN tax REAL DEFAULT 0")
    if "fx_rate" not in existing_cols:
        cur.execute("ALTER TABLE trades ADD COLUMN fx_rate REAL")
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS targets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticker TEXT NOT NULL,
            name TEXT,
            market TEXT NOT NULL,
            target_price REAL,
            stop_loss REAL,
            note TEXT,
            manual_price REAL,          -- fallback if auto price fetch fails
            set_date TEXT NOT NULL,
            active INTEGER DEFAULT 1
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS journal (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            entry_date TEXT NOT NULL,
            ticker TEXT,
            title TEXT NOT NULL,
            content TEXT,
            category TEXT DEFAULT 'note',  -- 'note' (개인 노트) or 'ai_insight' (Claude가 조사해서 저장)
            source_url TEXT,
            created_at TEXT NOT NULL
        )
        """
    )
    existing_journal_cols = {row["name"] for row in cur.execute("PRAGMA table_info(journal)").fetchall()}
    if "category" not in existing_journal_cols:
        cur.execute("ALTER TABLE journal ADD COLUMN category TEXT DEFAULT 'note'")
    if "source_url" not in existing_journal_cols:
        cur.execute("ALTER TABLE journal ADD COLUMN source_url TEXT")
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS dividends (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticker TEXT NOT NULL,
            name TEXT,
            market TEXT NOT NULL,
            pay_date TEXT NOT NULL,
            amount REAL NOT NULL,       -- 세후 실수령액 기준
            tax REAL DEFAULT 0,
            note TEXT,
            created_at TEXT NOT NULL
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS holding_notes (
            ticker TEXT PRIMARY KEY,
            market TEXT NOT NULL,
            note TEXT,
            updated_at TEXT NOT NULL
        )
        """
    )
    conn.commit()
    conn.close()


def add_trade(ticker, name, market, side, quantity, price, fee, trade_date, strategy_tag, thesis,
              tax=0.0, fx_rate=None):
    conn = get_conn()
    conn.execute(
        """INSERT INTO trades (ticker, name, market, side, quantity, price, fee, tax, fx_rate, trade_date,
                                strategy_tag, thesis, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (ticker, name, market, side, quantity, price, fee, tax, fx_rate, trade_date, strategy_tag, thesis,
         datetime.now().isoformat()),
    )
    conn.commit()
    conn.close()


def get_trades():
    conn = get_conn()
    rows = conn.execute("SELECT * FROM trades ORDER BY trade_date DESC, id DESC").fetchall()
    conn.close()
    return rows


def delete_trade(trade_id):
    conn = get_conn()
    conn.execute("DELETE FROM trades WHERE id = ?", (trade_id,))
    conn.commit()
    conn.close()


def add_target(ticker, name, market, target_price, stop_loss, note, set_date):
    conn = get_conn()
    conn.execute(
        """INSERT INTO targets (ticker, name, market, target_price, stop_loss, note, set_date, active)
           VALUES (?, ?, ?, ?, ?, ?, ?, 1)""",
        (ticker, name, market, target_price, stop_loss, note, set_date),
    )
    conn.commit()
    conn.close()


def get_targets(active_only=True):
    conn = get_conn()
    query = "SELECT * FROM targets"
    if active_only:
        query += " WHERE active = 1"
    query += " ORDER BY set_date DESC"
    rows = conn.execute(query).fetchall()
    conn.close()
    return rows


def update_target_manual_price(target_id, manual_price):
    conn = get_conn()
    conn.execute("UPDATE targets SET manual_price = ? WHERE id = ?", (manual_price, target_id))
    conn.commit()
    conn.close()


def deactivate_target(target_id):
    conn = get_conn()
    conn.execute("UPDATE targets SET active = 0 WHERE id = ?", (target_id,))
    conn.commit()
    conn.close()


def add_journal(entry_date, ticker, title, content, category="note", source_url=None):
    conn = get_conn()
    conn.execute(
        """INSERT INTO journal (entry_date, ticker, title, content, category, source_url, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (entry_date, ticker, title, content, category, source_url, datetime.now().isoformat()),
    )
    conn.commit()
    conn.close()


def get_journal(category=None):
    conn = get_conn()
    if category:
        rows = conn.execute(
            "SELECT * FROM journal WHERE category = ? ORDER BY entry_date DESC, id DESC", (category,)
        ).fetchall()
    else:
        rows = conn.execute("SELECT * FROM journal ORDER BY entry_date DESC, id DESC").fetchall()
    conn.close()
    return rows


def add_dividend(ticker, name, market, pay_date, amount, tax, note):
    conn = get_conn()
    conn.execute(
        """INSERT INTO dividends (ticker, name, market, pay_date, amount, tax, note, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (ticker, name, market, pay_date, amount, tax, note, datetime.now().isoformat()),
    )
    conn.commit()
    conn.close()


def get_dividends():
    conn = get_conn()
    rows = conn.execute("SELECT * FROM dividends ORDER BY pay_date DESC, id DESC").fetchall()
    conn.close()
    return rows


def delete_dividend(dividend_id):
    conn = get_conn()
    conn.execute("DELETE FROM dividends WHERE id = ?", (dividend_id,))
    conn.commit()
    conn.close()


def update_dividend_ticker(dividend_id, ticker, name, market):
    conn = get_conn()
    conn.execute(
        "UPDATE dividends SET ticker = ?, name = ?, market = ? WHERE id = ?",
        (ticker, name, market, dividend_id),
    )
    conn.commit()
    conn.close()


def get_holding_notes():
    """{ticker: note} for every holding that has a saved 비고."""
    conn = get_conn()
    rows = conn.execute("SELECT ticker, note FROM holding_notes").fetchall()
    conn.close()
    return {r["ticker"]: r["note"] for r in rows}


def set_holding_note(ticker, market, note):
    conn = get_conn()
    conn.execute(
        """INSERT INTO holding_notes (ticker, market, note, updated_at) VALUES (?, ?, ?, ?)
           ON CONFLICT(ticker) DO UPDATE SET market = excluded.market, note = excluded.note,
                                              updated_at = excluded.updated_at""",
        (ticker, market, note, datetime.now().isoformat()),
    )
    conn.commit()
    conn.close()
