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


def get_daily_change_batch(tickers: list):
    """여러 티커의 전일 대비 등락률(%)을 한 번에 조회.

    yf.download 배치 호출 하나로 처리해서 종목별 순차 조회보다 훨씬 빠름
    (히트맵처럼 수십 개 종목을 한 번에 그려야 할 때 사용).
    Returns {ticker: pct_change_float_or_None}.
    """
    import yfinance as yf

    result = {t: None for t in tickers}
    if not tickers:
        return result
    try:
        data = yf.download(tickers, period="5d", progress=False, threads=True, group_by="ticker")
    except Exception:
        return result

    for t in tickers:
        try:
            closes = data[t]["Close"].dropna() if len(tickers) > 1 else data["Close"].dropna()
            if len(closes) < 2:
                continue
            prev, last = closes.iloc[-2], closes.iloc[-1]
            if prev:
                result[t] = float((last - prev) / prev * 100)
        except Exception:
            continue
    return result


def get_market_caps_batch(tickers: list, max_workers: int = 8):
    """여러 티커의 시가총액을 병렬로 조회 (히트맵 트리맵 타일 크기 계산용).
    Returns {ticker: market_cap_float_or_None}."""
    import concurrent.futures

    import yfinance as yf

    def _one(t):
        try:
            cap = yf.Ticker(t).fast_info.get("marketCap")
            return t, (float(cap) if cap else None)
        except Exception:
            return t, None

    result = {t: None for t in tickers}
    if not tickers:
        return result
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as ex:
        for t, cap in ex.map(_one, tickers):
            result[t] = cap
    return result


def get_next_earnings_date_us(ticker: str):
    """다음 실적발표일 (US 종목만 - yfinance 제공). 실패/없음 시 None.
    Returns a datetime.date or None."""
    try:
        import yfinance as yf

        t = yf.Ticker(ticker)
        cal = t.calendar
        dates = cal.get("Earnings Date") if isinstance(cal, dict) else None
        if not dates:
            return None
        return dates[0]
    except Exception:
        return None
