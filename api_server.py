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
    """price_lookup 값은 해당 종목의 원래 통화 그대로다(국내는 원화, 해외는
    달러 - price_data.get_current_price가 환산하지 않은 원가를 반환함). 해외
    종목의 평단가(avg_cost)도 매수 시점 환율로 저장돼 있어서, 오늘 가격을
    오늘 환율로 KRW 환산한 뒤 평단가와 바로 빼면 매수~오늘 사이의 환율 변동이
    주식 자체 손익에 섞여버린다 - 이 파일 안에서 그렇게 계산하지 말고
    analytics.total_unrealized_pnl(fx_rate=...)와 아래 avg_cost_usd 기반 계산을
    통해서만 미실현손익을 구할 것.
    """
    trades = [_row_to_dict(r) for r in db.get_trades()]
    positions = analytics.compute_positions(trades)
    price_lookup = {
        ticker: price_data.get_current_price(ticker, pos["market"])
        for ticker, pos in positions.items()
        if pos["qty"] > 0
    }
    fx_rate = price_data.get_usdkrw_rate()
    return positions, price_lookup, fx_rate


@app.get("/analytics/positions")
def get_positions(_: None = Depends(require_api_key)):
    positions, price_lookup, fx_rate = _positions_with_prices()
    result = []
    for ticker, pos in positions.items():
        current_price = price_lookup.get(ticker)
        unrealized = None
        if pos["qty"] > 0 and current_price is not None:
            if pos["market"] == "US" and pos.get("avg_cost_usd"):
                if fx_rate:
                    unrealized = (current_price - pos["avg_cost_usd"]) * pos["qty"] * fx_rate
            else:
                unrealized = (current_price - pos["avg_cost"]) * pos["qty"]
        result.append(
            {
                "ticker": ticker,
                "name": pos["name"],
                "market": pos["market"],
                "qty": pos["qty"],
                # avg_cost/current_price는 항상 원화. 해외 종목은 avg_cost_usd/
                # current_price_usd로 달러 기준 값도 같이 줌 (환율 섞임 없이 보려면 이쪽 사용).
                "avg_cost": pos["avg_cost"],
                "avg_cost_usd": pos.get("avg_cost_usd") if pos["market"] == "US" else None,
                "current_price": current_price * fx_rate if pos["market"] == "US" and fx_rate and current_price else current_price,
                "current_price_usd": current_price if pos["market"] == "US" else None,
                "realized_pnl": pos["realized_pnl"],
                "unrealized_pnl": unrealized,
            }
        )
    return result


@app.get("/analytics/summary")
def get_summary(_: None = Depends(require_api_key)):
    positions, price_lookup, fx_rate = _positions_with_prices()
    return {
        "win_rate": analytics.win_rate(positions),
        "total_realized_pnl": analytics.total_realized_pnl(positions),
        "total_unrealized_pnl": analytics.total_unrealized_pnl(positions, price_lookup, fx_rate=fx_rate),
        "trade_count": len(db.get_trades()),
    }
