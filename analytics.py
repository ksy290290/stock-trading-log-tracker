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
    KRW). For US positions this is compared against avg_cost_usd, not the
    KRW-denominated avg_cost, so currency movement since purchase isn't mixed
    into the stock's own return; the USD result is converted to KRW with a
    single current fx_rate at the end. Same convention as the dashboard's
    per-holding table and app.py's compute_perf_rows. US positions are
    skipped if fx_rate isn't provided.
    """
    total = 0.0
    for ticker, pos in positions.items():
        if pos["qty"] <= 0:
            continue
        price = price_lookup.get(ticker)
        if price is None:
            continue
        if pos["market"] == "US" and pos.get("avg_cost_usd"):
            if not fx_rate:
                continue
            total += (price - pos["avg_cost_usd"]) * pos["qty"] * fx_rate
        else:
            total += (price - pos["avg_cost"]) * pos["qty"]
    return total


def compute_holding_episodes(trades, today_iso, price_lookup=None, fx_rate=None):
    """Groups each ticker's trades into holding episodes: a continuous span
    from a fresh BUY (starting from zero shares) to full liquidation (or,
    if still held, to `today_iso`). A ticker that was fully sold and later
    bought again gets two separate episodes instead of one span that
    would silently include the gap where nothing was held.

    price_lookup (optional): dict ticker -> current price in that ticker's own
    market currency (KRW for KR, USD for US), same convention as
    total_unrealized_pnl. If given (with fx_rate for any US ticker), each
    episode also gets a `return_pct`:
    - closed episode: real KRW cash flow (buy cost vs sell proceeds, each at
      its own trade's own fx rate) - matches what actually happened to the
      won in the account.
    - open episode on a US ticker: computed in USD (cost vs current value)
      before converting, so currency movement since purchase isn't mixed
      into the stock's own return - same convention as the dashboard/
      compute_perf_rows. KR tickers have no such split since there's no FX.
    Without price_lookup, `return_pct` is omitted from open episodes only
    (closed episodes never need a live price, so they always get it).

    Returns a list of {ticker, name, market, start_date, end_date, is_open,
    return_pct, pnl_krw}. pnl_krw is the same figure in absolute won (same
    fx handling as return_pct), for when the money amount matters more than
    the percentage - a huge % gain on a tiny position is a rounding error
    next to a small % gain on a large one.
    """
    price_lookup = price_lookup or {}
    by_ticker = defaultdict(list)
    for t in _sorted_trades(trades):
        by_ticker[t["ticker"]].append(t)

    episodes = []
    for ticker, tlist in by_ticker.items():
        qty = 0.0
        start_date = None
        cost_krw = 0.0
        cost_usd = 0.0
        proceeds_krw = 0.0
        name = tlist[0]["name"]
        market = tlist[0]["market"]
        for t in tlist:
            name = t["name"] or name
            if t["side"] == "BUY":
                if qty <= 1e-9:
                    start_date = t["trade_date"]
                    cost_krw = 0.0
                    cost_usd = 0.0
                    proceeds_krw = 0.0
                cost_krw += t["quantity"] * t["price"] + (t["fee"] or 0)
                if market == "US" and t["fx_rate"]:
                    cost_usd += t["quantity"] * (t["price"] / t["fx_rate"]) + (t["fee"] or 0) / t["fx_rate"]
                qty += t["quantity"]
            else:  # SELL
                proceeds_krw += t["quantity"] * t["price"] - (t["fee"] or 0) - (t["tax"] or 0)
                qty -= t["quantity"]
                if qty <= 1e-9 and start_date is not None:
                    episodes.append(
                        {
                            "ticker": ticker,
                            "name": name,
                            "market": market,
                            "start_date": start_date,
                            "end_date": t["trade_date"],
                            "is_open": False,
                            "return_pct": (proceeds_krw - cost_krw) / cost_krw if cost_krw else None,
                            "pnl_krw": proceeds_krw - cost_krw,
                        }
                    )
                    qty = 0.0
                    start_date = None
        if qty > 1e-9 and start_date is not None:
            return_pct = None
            pnl_krw = None
            price = price_lookup.get(ticker)
            if price is not None:
                if market == "US":
                    if cost_usd and fx_rate:
                        return_pct = (qty * price - cost_usd) / cost_usd
                        pnl_krw = (qty * price - cost_usd) * fx_rate
                elif cost_krw:
                    return_pct = (qty * price - cost_krw) / cost_krw
                    pnl_krw = qty * price - cost_krw
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
