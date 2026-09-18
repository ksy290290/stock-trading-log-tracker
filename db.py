import os
import sqlite3
from datetime import datetime
from pathlib import Path

DB_PATH = Path(__file__).parent / "stock_journal.db"


def _turso_config():
    """(url, token) - Streamlit secrets(배포 환경)나 환경변수(로컬 스크립트용) 중
    설정된 쪽에서 읽어옴. 둘 다 없으면 (None, None) -> 로컬 SQLite 파일로 동작
    (지금까지의 로컬 개발/테스트 방식 그대로)."""
    try:
        import streamlit as st

        turso = st.secrets.get("turso")
        if turso and turso.get("url") and turso.get("token"):
            return turso["url"], turso["token"]
    except Exception:
        pass
    url = os.environ.get("TURSO_DATABASE_URL")
    token = os.environ.get("TURSO_AUTH_TOKEN")
    if url and token:
        return url, token
    return None, None


class _Row(tuple):
    """sqlite3.Row 대체품 (libsql은 row_factory를 지원하지 않아서 직접 구현) -
    row['col']과 row[0] 둘 다 되고 dict(row)도 되게 해서, 로컬/Turso 어느 쪽으로
    연결되든 db.py 나머지 함수와 app.py가 코드 변경 없이 그대로 동작하게 함."""

    def __new__(cls, values, cols):
        obj = super().__new__(cls, values)
        obj._cols = cols
        return obj

    def __getitem__(self, key):
        if isinstance(key, str):
            return tuple.__getitem__(self, self._cols.index(key))
        return tuple.__getitem__(self, key)

    def keys(self):
        return list(self._cols)


class _TursoCursor:
    def __init__(self, raw_cursor):
        self._cur = raw_cursor

    def execute(self, sql, params=()):
        self._cur.execute(sql, params)
        return self

    def executemany(self, sql, seq_of_params):
        self._cur.executemany(sql, seq_of_params)
        return self

    def executescript(self, sql):
        self._cur.executescript(sql)
        return self

    def _row(self, raw):
        cols = tuple(d[0] for d in self._cur.description)
        return _Row(raw, cols)

    def fetchall(self):
        return [self._row(r) for r in self._cur.fetchall()]

    def fetchone(self):
        r = self._cur.fetchone()
        return self._row(r) if r is not None else None

    @property
    def rowcount(self):
        return self._cur.rowcount

    @property
    def lastrowid(self):
        return self._cur.lastrowid


class _TursoConnection:
    """libsql 연결을 sqlite3.Connection과 거의 같은 인터페이스로 감싸서, 이 파일의
    나머지 코드가 로컬 SQLite인지 Turso인지 신경 쓸 필요 없게 함."""

    def __init__(self, url, token):
        import libsql

        self._conn = libsql.connect(database=url, auth_token=token)

    def cursor(self):
        return _TursoCursor(self._conn.cursor())

    def execute(self, sql, params=()):
        return self.cursor().execute(sql, params)

    def executemany(self, sql, seq_of_params):
        return self.cursor().executemany(sql, seq_of_params)

    def commit(self):
        self._conn.commit()

    def close(self):
        self._conn.close()


def get_conn():
    url, token = _turso_config()
    if url and token:
        return _TursoConnection(url, token)
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
            amount REAL NOT NULL,       -- 세후 실수령액, 항상 KRW 기준
            tax REAL DEFAULT 0,         -- 항상 KRW 기준
            fx_rate REAL,               -- 해외 배당 입금 시점 원/달러 환율 (국내는 NULL)
            note TEXT,
            created_at TEXT NOT NULL
        )
        """
    )
    existing_div_cols = {row["name"] for row in cur.execute("PRAGMA table_info(dividends)").fetchall()}
    if "fx_rate" not in existing_div_cols:
        cur.execute("ALTER TABLE dividends ADD COLUMN fx_rate REAL")
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


def update_trade(trade_id, ticker, name, market, side, quantity, price, fee, tax, fx_rate, trade_date,
                  strategy_tag, thesis):
    conn = get_conn()
    conn.execute(
        """UPDATE trades SET ticker = ?, name = ?, market = ?, side = ?, quantity = ?, price = ?,
                              fee = ?, tax = ?, fx_rate = ?, trade_date = ?, strategy_tag = ?, thesis = ?
           WHERE id = ?""",
        (ticker, name, market, side, quantity, price, fee, tax, fx_rate, trade_date, strategy_tag, thesis,
         trade_id),
    )
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


def add_dividend(ticker, name, market, pay_date, amount, tax, note, fx_rate=None):
    conn = get_conn()
    conn.execute(
        """INSERT INTO dividends (ticker, name, market, pay_date, amount, tax, fx_rate, note, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (ticker, name, market, pay_date, amount, tax, fx_rate, note, datetime.now().isoformat()),
    )
    conn.commit()
    conn.close()


def update_dividend(dividend_id, ticker, name, market, pay_date, amount, tax, note, fx_rate=None):
    conn = get_conn()
    conn.execute(
        """UPDATE dividends SET ticker = ?, name = ?, market = ?, pay_date = ?, amount = ?,
                                 tax = ?, fx_rate = ?, note = ?
           WHERE id = ?""",
        (ticker, name, market, pay_date, amount, tax, fx_rate, note, dividend_id),
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
