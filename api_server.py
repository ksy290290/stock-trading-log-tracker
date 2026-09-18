"""모바일 앱(iOS)용 REST API.

기존 Streamlit 웹앱(app.py)과 같은 db.py/analytics.py/price_data.py를 그대로
재사용한다 - 데이터 모델과 손익 계산 로직을 두 번 짜지 않기 위함. Turso를
사용 중이면(TURSO_DATABASE_URL/TURSO_AUTH_TOKEN 환경변수) db.py가 자동으로
그쪽에 붙으므로, 이 API 서버와 기존 Streamlit 앱이 같은 데이터를 공유한다.

MVP 범위: 매매일지(trades) CRUD + 성과분석(positions/summary).
배당금/목표가/노트는 다음 단계에서 추가.

실행: uvicorn api_server:app --host 0.0.0.0 --port 8000
"""
import os
from typing import Optional

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

import analytics
import db
import price_data

app = FastAPI(title="Stock Trading Journal API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# 배포 시 API_KEY 환경변수를 설정하면 모든 요청에 X-API-Key 헤더를 요구한다.
# 설정하지 않으면(로컬 개발) 인증 없이 열려 있다.
API_KEY = os.environ.get("API_KEY")


def require_api_key(x_api_key: Optional[str] = Header(default=None)):
    if API_KEY and x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="invalid API key")


@app.on_event("startup")
def _startup():
    db.init_db()


class TradeIn(BaseModel):
    ticker: str
    name: Optional[str] = None
    market: str  # 'KR' or 'US'
    side: str  # 'BUY' or 'SELL'
    quantity: float
    price: float
    fee: float = 0
    tax: float = 0
    fx_rate: Optional[float] = None
    trade_date: str
    strategy_tag: Optional[str] = None
    thesis: Optional[str] = None


class TradeOut(TradeIn):
    id: int
    created_at: str


def _row_to_dict(row) -> dict:
    return {k: row[k] for k in row.keys()}


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/trades", response_model=list[TradeOut])
def list_trades(_: None = Depends(require_api_key)):
    return [_row_to_dict(r) for r in db.get_trades()]


@app.get("/trades/{trade_id}", response_model=TradeOut)
def get_trade(trade_id: int, _: None = Depends(require_api_key)):
    for row in db.get_trades():
        trade = _row_to_dict(row)
        if trade["id"] == trade_id:
            return trade
    raise HTTPException(status_code=404, detail="trade not found")


@app.post("/trades", status_code=201)
def create_trade(trade: TradeIn, _: None = Depends(require_api_key)):
    db.add_trade(
        trade.ticker, trade.name, trade.market, trade.side, trade.quantity,
        trade.price, trade.fee, trade.trade_date, trade.strategy_tag, trade.thesis,
        tax=trade.tax, fx_rate=trade.fx_rate,
    )
    return {"status": "ok"}


@app.put("/trades/{trade_id}")
def edit_trade(trade_id: int, trade: TradeIn, _: None = Depends(require_api_key)):
    db.update_trade(
        trade_id, trade.ticker, trade.name, trade.market, trade.side, trade.quantity,
        trade.price, trade.fee, trade.tax, trade.fx_rate, trade.trade_date,
        trade.strategy_tag, trade.thesis,
    )
    return {"status": "ok"}


@app.delete("/trades/{trade_id}")
def remove_trade(trade_id: int, _: None = Depends(require_api_key)):
    db.delete_trade(trade_id)
    return {"status": "ok"}


def _positions_with_prices():
    trades = [_row_to_dict(r) for r in db.get_trades()]
    positions = analytics.compute_positions(trades)
    price_lookup = {
        ticker: price_data.get_current_price(ticker, pos["market"])
        for ticker, pos in positions.items()
        if pos["qty"] > 0
    }
    return positions, price_lookup


@app.get("/analytics/positions")
def get_positions(_: None = Depends(require_api_key)):
    positions, price_lookup = _positions_with_prices()
    result = []
    for ticker, pos in positions.items():
        current_price = price_lookup.get(ticker)
        unrealized = None
        if pos["qty"] > 0 and current_price is not None:
            unrealized = (current_price - pos["avg_cost"]) * pos["qty"]
        result.append(
            {
                "ticker": ticker,
                "name": pos["name"],
                "market": pos["market"],
                "qty": pos["qty"],
                "avg_cost": pos["avg_cost"],
                "current_price": current_price,
                "realized_pnl": pos["realized_pnl"],
                "unrealized_pnl": unrealized,
            }
        )
    return result


@app.get("/analytics/summary")
def get_summary(_: None = Depends(require_api_key)):
    positions, price_lookup = _positions_with_prices()
    return {
        "win_rate": analytics.win_rate(positions),
        "total_realized_pnl": analytics.total_realized_pnl(positions),
        "total_unrealized_pnl": analytics.total_unrealized_pnl(positions, price_lookup),
        "trade_count": len(db.get_trades()),
    }
