"""Current price lookups.

KR stocks: Naver's unofficial mobile stock JSON endpoint (no key needed, but
undocumented and may change/break at any time).
US stocks: yfinance (Yahoo Finance).

Every function returns None on failure instead of raising, so the UI can fall
back to a manually-entered price.
"""
import requests


def get_price_kr(ticker: str):
    try:
        url = f"https://m.stock.naver.com/api/stock/{ticker}/basic"
        resp = requests.get(url, timeout=5, headers={"User-Agent": "Mozilla/5.0"})
        resp.raise_for_status()
        data = resp.json()
        price = data.get("closePrice") or data.get("now")
        if price is None:
            return None
        return float(str(price).replace(",", ""))
    except Exception:
        return None


def get_name_kr(ticker: str):
    try:
        url = f"https://m.stock.naver.com/api/stock/{ticker}/basic"
        resp = requests.get(url, timeout=5, headers={"User-Agent": "Mozilla/5.0"})
        resp.raise_for_status()
        data = resp.json()
        return data.get("stockName")
    except Exception:
        return None


def get_price_us(ticker: str):
    try:
        import yfinance as yf

        t = yf.Ticker(ticker)
        fast_info = t.fast_info
        price = fast_info.get("lastPrice") if hasattr(fast_info, "get") else fast_info.last_price
        if price is None:
            return None
        return float(price)
    except Exception:
        return None


def get_current_price(ticker: str, market: str):
    if market == "KR":
        return get_price_kr(ticker)
    return get_price_us(ticker)


def get_usdkrw_rate():
    """1 USD 당 원화 환율. 실패 시 None."""
    return get_price_us("KRW=X")
