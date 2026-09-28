"""Position & performance calculations using the average-cost method.

Note: holding-period and win/loss stats are computed per SELL trade against
the running average cost at the time of sale, not true FIFO lot-matching.
Good enough for a personal journal; not tax-accurate.
"""
from collections import defaultdict

_SIDE_ORDER = {"BUY": 0, "SELL": 1}


def chronological_key(t):
    # Toss's statement doesn't include time-of-day, and same-day rows aren't
    # always printed in execution order (a same-day SELL can be listed before
    # its matching BUY) - process all buys before sells on a given date since
    # a long-only retail account can't sell what it hasn't bought yet.
    return (t["trade_date"], _SIDE_ORDER[t["side"]], t["id"])


def _sorted_trades(trades):
    return sorted(trades, key=chronological_key)


def compute_positions(trades):
    """Returns {ticker: {name, market, qty, avg_cost, avg_cost_usd, realized_pnl, sell_records:[...]}}

    avg_cost is always in KRW. avg_cost_usd is only meaningful for market=="US"
    positions with fx_rate recorded on their BUY trades (Toss's own statement
    conversion rate at execution time) - it lets US holdings be shown in their
    native currency instead of round-tripping through today's FX rate, which
    would mix in currency movement and no longer match what Toss itself shows.
    """
    state = {}
    for t in _sorted_trades(trades):
        key = t["ticker"]
        if key not in state:
            state[key] = {
                "name": t["name"],
                "market": t["market"],
                "qty": 0.0,
                "avg_cost": 0.0,
                "avg_cost_usd": 0.0,
                "realized_pnl": 0.0,
                "sell_records": [],
            }
        pos = state[key]
        if t["side"] == "BUY":
            total_cost = pos["qty"] * pos["avg_cost"] + t["quantity"] * t["price"] + (t["fee"] or 0)
            fx = t["fx_rate"] if t["market"] == "US" else None
            if fx:
                price_usd = t["price"] / fx
                fee_usd = (t["fee"] or 0) / fx
                total_cost_usd = pos["qty"] * pos["avg_cost_usd"] + t["quantity"] * price_usd + fee_usd
            else:
                total_cost_usd = pos["avg_cost_usd"] * pos["qty"]
            pos["qty"] += t["quantity"]
            pos["avg_cost"] = total_cost / pos["qty"] if pos["qty"] else 0.0
            pos["avg_cost_usd"] = total_cost_usd / pos["qty"] if pos["qty"] else 0.0
        else:  # SELL
            pnl = (t["price"] - pos["avg_cost"]) * t["quantity"] - (t["fee"] or 0) - (t["tax"] or 0)
            pos["realized_pnl"] += pnl
            pos["qty"] -= t["quantity"]
            pos["sell_records"].append(
                {
                    "date": t["trade_date"],
                    "quantity": t["quantity"],
                    "sell_price": t["price"],
                    "cost_basis": pos["avg_cost"],
                    "pnl": pnl,
                }
            )
    return state


def win_rate(positions):
    all_sells = [s for pos in positions.values() for s in pos["sell_records"]]
    if not all_sells:
        return None
    wins = sum(1 for s in all_sells if s["pnl"] > 0)
    return wins / len(all_sells)


def total_realized_pnl(positions):
    return sum(pos["realized_pnl"] for pos in positions.values())


def total_unrealized_pnl(positions, price_lookup, fx_rate=None):
    """price_lookup: dict ticker -> current price in the position's OWN market
    currency (KRW for KR tickers, USD for US tickers - NOT pre-converted to
    KRW). For US positions the price is converted to KRW with the current
    fx_rate and compared against avg_cost (KRW, blended from each purchase's
    own historical fx rate) - by user decision this INCLUDES the currency
    gain/loss since purchase as part of the position's return, on the
    reasoning that money actually sitting in USD really is worth more or
    less KRW today depending on where the rate has moved. US positions are
    skipped if fx_rate isn't provided.
    """
    total = 0.0
    for ticker, pos in positions.items():
        if pos["qty"] <= 0:
            continue
        price = price_lookup.get(ticker)
        if price is None:
            continue
        if pos["market"] == "US":
            if not fx_rate:
                continue
            price = price * fx_rate
        total += (price - pos["avg_cost"]) * pos["qty"]
    return total


def compute_holding_episodes(trades, today_iso, price_lookup=None, fx_rate=None, dividends=None):
    """Groups each ticker's trades into holding episodes: a continuous span
    from a fresh BUY (starting from zero shares) to full liquidation (or,
    if still held, to `today_iso`). A ticker that was fully sold and later
    bought again gets two separate episodes instead of one span that
    would silently include the gap where nothing was held.

    price_lookup (optional): dict ticker -> current price in that ticker's own
    market currency (KRW for KR, USD for US), same convention as
    total_unrealized_pnl. If given (with fx_rate for any US ticker), each
    episode also gets a `return_pct`, always in KRW terms:
    - closed episode: real cash flow (buy cost vs sell proceeds, each at its
      own trade's own fx rate) - matches what actually happened to the won.
    - open episode: remaining qty x avg_cost (KRW; US prices/costs are
      converted with fx_rate) vs today's value. By user decision this
      INCLUDES currency movement since purchase as part of the return -
      money sitting in USD really is worth more or less KRW today depending
      on where the rate moved, so it counts.
    Without price_lookup, `return_pct` is omitted from open episodes only
    (closed episodes never need a live price, so they always get it).

    dividends (optional): list of dividend rows (ticker, pay_date, amount -
    already KRW). Any dividend whose pay_date falls within an episode's
    [start_date, end_date] is added to that episode's pnl_krw/return_pct -
    a holding's total return should count income it paid out, not just
    price movement.

    Returns a list of {ticker, name, market, start_date, end_date, is_open,
    return_pct, pnl_krw}. pnl_krw is the same figure in absolute won (same
    fx handling as return_pct), for when the money amount matters more than
    the percentage - a huge % gain on a tiny position is a rounding error
    next to a small % gain on a large one.
    """
    price_lookup = price_lookup or {}
    div_by_ticker = defaultdict(list)
    for d in dividends or []:
        div_by_ticker[d["ticker"]].append((d["pay_date"], d["amount"] or 0.0))

    def _dividends_in_range(ticker, start_date, end_date):
        return sum(amt for pay_date, amt in div_by_ticker.get(ticker, []) if start_date <= pay_date <= end_date)

    by_ticker = defaultdict(list)
    for t in _sorted_trades(trades):
        by_ticker[t["ticker"]].append(t)

    episodes = []
    for ticker, tlist in by_ticker.items():
        qty = 0.0
        start_date = None
        # 청산 완료 구간의 수익률은 그 구간에 산 전체 원가(cost_krw_total) 대비
        # 그 구간에 판 전체 매도대금(proceeds_krw)으로 계산 - 청산 완료란 정의상
        # 그 구간에 산 걸 전부 팔았다는 뜻이라 1:1로 맞음.
        # 반면 아직 보유중인 구간은 중간에 일부만 판 적이 있을 수 있어서(예: 재매수
        # 없이 쭉 사모으다 일부 차익실현), 남은 수량의 원가를 "평단가 x 남은 수량"으로
        # 다시 계산해야 함 - 평단가법(avg-cost)에서는 일부 매도가 평단가 자체를
        # 바꾸지 않으므로, compute_positions와 똑같이 평단가를 증분 계산해서 씀.
        avg_cost_krw = 0.0
        cost_krw_total = 0.0
        proceeds_krw = 0.0
        name = tlist[0]["name"]
        market = tlist[0]["market"]
        for t in tlist:
            name = t["name"] or name
            if t["side"] == "BUY":
                if qty <= 1e-9:
                    start_date = t["trade_date"]
                    avg_cost_krw = 0.0
                    cost_krw_total = 0.0
                    proceeds_krw = 0.0
                buy_cost_krw = t["quantity"] * t["price"] + (t["fee"] or 0)
                new_total_cost_krw = qty * avg_cost_krw + buy_cost_krw
                cost_krw_total += buy_cost_krw
                qty += t["quantity"]
                avg_cost_krw = new_total_cost_krw / qty
            else:  # SELL
                proceeds_krw += t["quantity"] * t["price"] - (t["fee"] or 0) - (t["tax"] or 0)
                qty -= t["quantity"]
                if qty <= 1e-9 and start_date is not None:
                    ep_dividends = _dividends_in_range(ticker, start_date, t["trade_date"])
                    pnl_krw = proceeds_krw - cost_krw_total + ep_dividends
                    episodes.append(
                        {
                            "ticker": ticker,
                            "name": name,
                            "market": market,
                            "start_date": start_date,
                            "end_date": t["trade_date"],
                            "is_open": False,
                            "return_pct": pnl_krw / cost_krw_total if cost_krw_total else None,
                            "pnl_krw": pnl_krw,
                        }
                    )
                    qty = 0.0
                    start_date = None
        if qty > 1e-9 and start_date is not None:
            return_pct = None
            pnl_krw = None
            price = price_lookup.get(ticker)
            if price is not None:
                price_krw = price * fx_rate if market == "US" else price
                if market != "US" or fx_rate:
                    cost_basis = avg_cost_krw * qty
                    ep_dividends = _dividends_in_range(ticker, start_date, today_iso)
                    pnl_krw = (price_krw - avg_cost_krw) * qty + ep_dividends
                    return_pct = pnl_krw / cost_basis if cost_basis else None
            episodes.append(
                {
                    "ticker": ticker,
                    "name": name,
                    "market": market,
                    "start_date": start_date,
                    "end_date": today_iso,
                    "is_open": True,
                    "return_pct": return_pct,
                    "pnl_krw": pnl_krw,
                }
            )
    return episodes
