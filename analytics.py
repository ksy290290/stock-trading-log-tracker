"""Position & performance calculations using the average-cost method.

Note: holding-period and win/loss stats are computed per SELL trade against
the running average cost at the time of sale, not true FIFO lot-matching.
Good enough for a personal journal; not tax-accurate.
"""
from collections import defaultdict


def _sorted_trades(trades):
    return sorted(trades, key=lambda t: (t["trade_date"], t["id"]))


def compute_positions(trades):
    """Returns {ticker: {name, market, qty, avg_cost, realized_pnl, sell_records:[...]}}"""
    state = {}
    for t in _sorted_trades(trades):
        key = t["ticker"]
        if key not in state:
            state[key] = {
                "name": t["name"],
                "market": t["market"],
                "qty": 0.0,
                "avg_cost": 0.0,
                "realized_pnl": 0.0,
                "sell_records": [],
            }
        pos = state[key]
        if t["side"] == "BUY":
            total_cost = pos["qty"] * pos["avg_cost"] + t["quantity"] * t["price"] + (t["fee"] or 0)
            pos["qty"] += t["quantity"]
            pos["avg_cost"] = total_cost / pos["qty"] if pos["qty"] else 0.0
        else:  # SELL
            pnl = (t["price"] - pos["avg_cost"]) * t["quantity"] - (t["fee"] or 0)
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


def total_unrealized_pnl(positions, price_lookup):
    """price_lookup: dict ticker -> current_price (or None)"""
    total = 0.0
    for ticker, pos in positions.items():
        if pos["qty"] <= 0:
            continue
        price = price_lookup.get(ticker)
        if price is None:
            continue
        total += (price - pos["avg_cost"]) * pos["qty"]
    return total
