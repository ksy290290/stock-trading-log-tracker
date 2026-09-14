import calendar as calendar_module
import concurrent.futures
import datetime as dt
import html
from collections import defaultdict

import altair as alt
import pandas as pd
import streamlit as st

import db
import price_data
from analytics import chronological_key, compute_positions, total_realized_pnl, total_unrealized_pnl, win_rate

st.set_page_config(page_title="주식 매매일지", page_icon="📈", layout="wide")
db.init_db()

st.markdown(
    """
    <style>
    div[role="tablist"] {
        position: sticky;
        top: 60px;
        z-index: 999;
        background-color: #ffffff;
    }
    @media (prefers-color-scheme: dark) {
        div[role="tablist"] {
            background-color: #0e1117;
        }
    }
    h1, h2, h3 {
        color: #000000 !important;
        font-weight: 700 !important;
    }
    .jnl-table {
        width: 100%;
        border-collapse: collapse;
        font-size: 0.9rem;
    }
    .jnl-table th {
        color: #000000 !important;
        font-weight: 700 !important;
        text-align: left;
        padding: 6px 10px;
        border-bottom: 2px solid #cccccc;
        background-color: #f7f7f7;
        position: sticky;
        top: 0;
    }
    .jnl-table td {
        padding: 5px 10px;
        border-bottom: 1px solid #eeeeee;
        white-space: nowrap;
    }
    .jnl-table-scroll {
        max-height: 480px;
        overflow-y: auto;
    }
    .jnl-table-wrap {
        overflow-x: auto;
    }
    /* 국내/해외 표가 서로 같은 컬럼 순서를 쓰므로, 폭을 완전히 고정해(table-layout:fixed)
       내용 길이와 무관하게 두 표의 가로 크기가 항상 똑같게 함 */
    .holdings-table {
        width: 1080px !important;
        table-layout: fixed;
    }
    .holdings-table td, .holdings-table th {
        padding: 3px 8px !important;
        overflow: hidden;
        text-overflow: ellipsis;
    }
    .holdings-table th:nth-child(1), .holdings-table td:nth-child(1) { width: 220px; }
    .holdings-table th:nth-child(2), .holdings-table td:nth-child(2) { width: 70px; }
    .holdings-table th:nth-child(3), .holdings-table td:nth-child(3) { width: 70px; }
    .holdings-table th:nth-child(4), .holdings-table td:nth-child(4) { width: 90px; }
    .holdings-table th:nth-child(5), .holdings-table td:nth-child(5) { width: 90px; }
    .holdings-table th:nth-child(6), .holdings-table td:nth-child(6) { width: 100px; }
    .holdings-table th:nth-child(7), .holdings-table td:nth-child(7) { width: 100px; }
    .holdings-table th:nth-child(8), .holdings-table td:nth-child(8) { width: 100px; }
    .holdings-table td:last-child, .holdings-table th:last-child {
        width: 240px;
    }
    .metric-card {
        border-radius: 14px;
        padding: 14px 16px;
        margin-bottom: 6px;
    }
    .metric-card .metric-label {
        font-size: 0.8rem;
        color: #444444;
        margin-bottom: 4px;
    }
    .metric-card .metric-value {
        font-size: 1.5rem;
        font-weight: 700;
        color: #000000;
    }
    .cal-grid {
        width: 100%;
        border-collapse: collapse;
        table-layout: fixed;
    }
    .cal-grid th {
        background-color: #f7f7f7;
        color: #000000 !important;
        font-weight: 700 !important;
        padding: 6px;
        border: 1px solid #ddd;
        text-align: center;
    }
    .cal-grid td {
        vertical-align: top;
        border: 1px solid #eee;
        height: 92px;
        padding: 4px;
        font-size: 0.72rem;
        overflow: hidden;
    }
    .cal-grid td.cal-dim {
        background-color: #fafafa;
        color: #bbbbbb;
    }
    .cal-daynum {
        font-weight: 700;
        margin-bottom: 2px;
    }
    .cal-event {
        color: #ffffff;
        border-radius: 3px;
        padding: 0px 4px;
        margin-bottom: 1px;
        font-size: 0.68rem;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
    }
    .cal-more {
        font-size: 0.68rem;
        color: #888888;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

MARKETS = ["KR", "US"]


def market_label(m):
    return "국내" if m == "KR" else "해외"


def fmt(x):
    """금액용: 1,000 단위 콤마 + 소수점 없이 표시. None/문자열은 그대로 통과."""
    if x is None:
        return "-"
    if isinstance(x, str):
        return x
    return f"{x:,.0f}"


def fmt_qty(x):
    """수량용: 1,000 단위 콤마는 넣되, 소수(분할매수 등)는 그대로 살려서 표시."""
    if x is None:
        return "-"
    if isinstance(x, str):
        return x
    if float(x).is_integer():
        return f"{x:,.0f}"
    return f"{x:,.4f}".rstrip("0").rstrip(".")


def render_table(df, scroll=False, extra_class=""):
    """검정/볼드 컬럼명을 보장하기 위해 st.dataframe 대신 스타일링된 HTML 표로 렌더링.
    (st.dataframe은 캔버스로 그려져서 CSS로 헤더 스타일을 바꿀 수 없음)
    행이 줄바꿈되지 않게 해서(white-space: nowrap) 국내/해외 표의 행 높이가 맞도록 함."""
    classes = f"jnl-table {extra_class}".strip()
    html = df.to_html(index=False, escape=True, border=0, classes=classes)
    if scroll:
        html = f'<div class="jnl-table-scroll">{html}</div>'
    st.markdown(f'<div class="jnl-table-wrap">{html}</div>', unsafe_allow_html=True)


def metric_card(label, value, color):
    st.markdown(
        f'<div class="metric-card" style="background-color:{color};">'
        f'<div class="metric-label">{html.escape(label)}</div>'
        f'<div class="metric-value">{html.escape(value)}</div>'
        f"</div>",
        unsafe_allow_html=True,
    )


@st.cache_data(ttl=300)
def cached_price(ticker, market):
    return price_data.get_current_price(ticker, market)


@st.cache_data(ttl=300)
def cached_usdkrw():
    return price_data.get_usdkrw_rate()


def price_in_krw(ticker, market):
    """평단가가 원화로 저장돼 있으므로(토스 거래내역서 기준), 비교 가능하도록
    해외 종목 현재가도 원화로 환산해서 반환. 조회 실패 시 None."""
    price = cached_price(ticker, market)
    if price is None:
        return None
    if market == "US":
        fx = cached_usdkrw()
        if fx is None:
            return None
        return price * fx
    return price


TICKER_NAME_MAP = {}
for _t in db.get_trades():
    if _t["name"] and _t["ticker"] not in TICKER_NAME_MAP:
        TICKER_NAME_MAP[_t["ticker"]] = _t["name"]


def suggest_name(ticker_raw, market):
    ticker = ticker_raw.strip().upper() if market == "US" else ticker_raw.strip()
    return TICKER_NAME_MAP.get(ticker, "")


tab_dashboard, tab_calendar, tab_trades, tab_dividends, tab_targets, tab_journal, tab_perf, tab_ai = st.tabs(
    ["📊 대시보드", "📅 캘린더", "📝 매매일지", "💰 배당금", "🎯 목표가/손절가", "📓 노트", "📈 성과분석", "🤖 AI 인사이트"]
)

# ---------------------------------------------------------------------------
# 대시보드
# ---------------------------------------------------------------------------
with tab_dashboard:
    trades = db.get_trades()
    if not trades:
        st.info("아직 매매 기록이 없습니다. '매매일지' 탭에서 첫 거래를 입력해보세요.")
    else:
        positions = compute_positions(trades)
        price_lookup = {
            ticker: price_in_krw(ticker, pos["market"])
            for ticker, pos in positions.items()
            if pos["qty"] > 0
        }
        realized = total_realized_pnl(positions)
        unrealized = total_unrealized_pnl(positions, price_lookup)
        wr = win_rate(positions)
        total_dividends = sum(d["amount"] for d in db.get_dividends())
        principal = sum(
            pos["avg_cost"] * pos["qty"] for pos in positions.values() if pos["qty"] > 0
        )

        c1, c2, c3, c4, c5 = st.columns(5)
        with c1:
            metric_card("투자금액 (원금)", f"{principal:,.0f}", "#E8F0FE")
        with c2:
            metric_card("평가 손익 (미실현)", f"{unrealized:,.0f}", "#FFF4E0")
        with c3:
            metric_card("실현 손익", f"{realized:,.0f}", "#E6F4EA")
        with c4:
            metric_card("누적 배당금", f"{total_dividends:,.0f}", "#FCE8E6")
        with c5:
            metric_card("승률 (매도 기준)", f"{wr:.0%}" if wr is not None else "-", "#F3E8FD")

        st.subheader("보유 종목")
        holding_notes = db.get_holding_notes()
        holdings_kr, holdings_us = [], []
        for ticker, pos in positions.items():
            if pos["qty"] <= 0:
                continue
            if pos["market"] == "US":
                # 해외는 원화 환산 없이 달러 그대로 (평단가도 달러 기준으로 추적됨) -
                # 오늘 환율을 곱해 KRW로 바꾸면 환율 변동분이 섞여 토스 앱 수치와 어긋남
                price = cached_price(ticker, "US")
                avg_cost = pos["avg_cost_usd"]
            else:
                price = price_lookup.get(ticker)
                avg_cost = pos["avg_cost"]
            eval_amount = price * pos["qty"] if price is not None else None
            pnl = (price - avg_cost) * pos["qty"] if price is not None else None
            pnl_pct = (price / avg_cost - 1) * 100 if price is not None and avg_cost else None
            entry = {
                "eval_amount": eval_amount,
                "market": pos["market"],
                "ticker": ticker,
                "종목": pos["name"] or ticker,
                "티커": ticker,
                "수량": fmt_qty(pos["qty"]),
                "평단가": fmt(avg_cost),
                "현재가": fmt(price) if price is not None else "조회 실패",
                "평가금": fmt(eval_amount),
                "평가손익": fmt(pnl) if pnl is not None else "-",
                "평가손익(%)": f"{pnl_pct:+.2f}%" if pnl_pct is not None else "-",
                "비고": holding_notes.get(ticker) or "",
            }
            (holdings_kr if pos["market"] == "KR" else holdings_us).append(entry)

        def render_holdings(label, entries):
            st.markdown(f"**{label}**")
            if not entries:
                st.caption("보유 종목 없음")
                return []
            entries_sorted = sorted(
                entries, key=lambda e: e["eval_amount"] if e["eval_amount"] is not None else -1, reverse=True
            )
            df = pd.DataFrame(entries_sorted).drop(columns=["eval_amount", "market", "ticker"])
            render_table(df, extra_class="holdings-table")
            return entries_sorted

        kr_sorted = render_holdings("🇰🇷 국내", holdings_kr)
        us_sorted = render_holdings("🇺🇸 해외 (USD 기준)", holdings_us)

        with st.expander("✏️ 비고 작성/수정"):
            # 평가금 내림차순 (위 표와 같은 순서): 국내 먼저, 그다음 해외
            note_options = {
                f"{'🇰🇷' if e['market'] == 'KR' else '🇺🇸'} {e['종목']} ({e['ticker']})": (e["ticker"], e["market"])
                for e in kr_sorted + us_sorted
            }
            if note_options:
                note_label = st.selectbox("종목 선택", list(note_options.keys()), key="holding_note_select")
                sel_ticker, sel_market = note_options[note_label]
                note_value = st.text_input(
                    "비고 (예: %별 판매 예약 완료 (260914))",
                    value=holding_notes.get(sel_ticker, ""),
                    key=f"note_input_{sel_ticker}",
                )
                if st.button("저장", key="save_holding_note"):
                    db.set_holding_note(sel_ticker, sel_market, note_value.strip())
                    st.success("저장했습니다.")
                    st.rerun()
            else:
                st.caption("보유 종목이 없습니다.")

        st.subheader("목표가 진행률")
        targets = db.get_targets(active_only=True)
        if not targets:
            st.caption("등록된 목표가가 없습니다.")
        for t in targets:
            price = t["manual_price"] or cached_price(t["ticker"], t["market"])
            st.write(f"**{t['name'] or t['ticker']}** ({t['ticker']})")
            if price is None:
                st.caption("현재가 조회 실패 - '목표가/손절가' 탭에서 수동 입력해주세요.")
                continue
            cols = st.columns([3, 1])
            if t["target_price"]:
                progress = max(0.0, min(price / t["target_price"], 1.0))
                cols[0].progress(progress, text=f"현재가 {price:,.0f} / 목표가 {t['target_price']:,.0f}")
            cols[1].write(f"손절가: {t['stop_loss']:,.0f}" if t["stop_loss"] else "손절가 미설정")

        usdkrw = cached_usdkrw()
        rate_text = f"환율: 1 USD = {usdkrw:,.2f} KRW" if usdkrw is not None else "환율 조회 실패"
        st.markdown(
            f"<div style='text-align:right; color:gray; font-size:0.85em;'>{rate_text}</div>",
            unsafe_allow_html=True,
        )

# ---------------------------------------------------------------------------
# 캘린더
# ---------------------------------------------------------------------------
with tab_calendar:
    st.subheader("매매 · 배당 · 실적발표 캘린더")

    cal_trades = db.get_trades()
    cal_dividends = db.get_dividends()
    events_by_date = defaultdict(list)  # date_str -> [(text, color)]

    # 매매: 같은 날짜/티커/매수·매도를 묶어서 이벤트 하나로 (하루 여러 번 자동매수 등으로 인한 난립 방지)
    trade_groups = defaultdict(lambda: {"qty": 0.0, "name": None})
    for t in cal_trades:
        key = (t["trade_date"], t["ticker"], t["side"])
        trade_groups[key]["qty"] += t["quantity"]
        trade_groups[key]["name"] = t["name"] or t["ticker"]
    for (cdate, cticker, cside), g in trade_groups.items():
        label = "매수" if cside == "BUY" else "매도"
        color = "#3D9DF3" if cside == "BUY" else "#FF6C6C"
        events_by_date[cdate].append((f"{label} {g['name']} {fmt_qty(g['qty'])}", color))

    # 배당 (같은 날짜/티커 합산)
    div_groups = defaultdict(lambda: {"amount": 0.0, "name": None})
    for d in cal_dividends:
        key = (d["pay_date"], d["ticker"])
        div_groups[key]["amount"] += d["amount"]
        div_groups[key]["name"] = d["name"] or d["ticker"]
    for (cdate, cticker), g in div_groups.items():
        events_by_date[cdate].append((f"배당 {g['name']} {fmt(g['amount'])}원", "#3DD56D"))

    # 실적발표 (해외 보유종목만 - yfinance 제공, 국내는 자동 조회 소스가 마땅치 않음)
    cal_positions = compute_positions(cal_trades) if cal_trades else {}
    us_tickers = sorted(t for t, p in cal_positions.items() if p["market"] == "US" and p["qty"] > 0)

    @st.cache_data(ttl=60 * 60 * 12)
    def cached_earnings_date(ticker):
        d = price_data.get_next_earnings_date_us(ticker)
        return d.isoformat() if d else None

    if us_tickers:
        with st.spinner(f"실적발표 일정 조회 중... ({len(us_tickers)}개 종목)"):
            with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
                future_to_ticker = {executor.submit(cached_earnings_date, t): t for t in us_tickers}
                for future in concurrent.futures.as_completed(future_to_ticker):
                    eticker = future_to_ticker[future]
                    edate = future.result()
                    if edate:
                        ename = cal_positions[eticker]["name"] or eticker
                        events_by_date[edate].append((f"실적발표 {ename}", "#B073FF"))

    if "cal_year" not in st.session_state:
        _today = dt.date.today()
        st.session_state.cal_year = _today.year
        st.session_state.cal_month = _today.month

    col_prev, col_title, col_next = st.columns([1, 4, 1])
    if col_prev.button("◀ 이전달"):
        m, y = st.session_state.cal_month - 1, st.session_state.cal_year
        if m < 1:
            m, y = 12, y - 1
        st.session_state.cal_month, st.session_state.cal_year = m, y
        st.rerun()
    col_title.markdown(
        f'<div style="text-align:center; font-size:1.5rem; font-weight:700; '
        f'color:#000000; padding-top:6px;">{st.session_state.cal_year}년 {st.session_state.cal_month}월</div>',
        unsafe_allow_html=True,
    )
    if col_next.button("다음달 ▶"):
        m, y = st.session_state.cal_month + 1, st.session_state.cal_year
        if m > 12:
            m, y = 1, y + 1
        st.session_state.cal_month, st.session_state.cal_year = m, y
        st.rerun()

    _cal = calendar_module.Calendar(firstweekday=6)  # 일요일 시작
    _weeks = _cal.monthdatescalendar(st.session_state.cal_year, st.session_state.cal_month)
    _rows = ['<table class="cal-grid">']
    _rows.append("<tr>" + "".join(f"<th>{d}</th>" for d in ["일", "월", "화", "수", "목", "금", "토"]) + "</tr>")
    for week in _weeks:
        _rows.append("<tr>")
        for day in week:
            in_month = day.month == st.session_state.cal_month
            evs = events_by_date.get(day.isoformat(), [])
            cell_class = "cal-dim" if not in_month else ""
            ev_html = "".join(
                f'<div class="cal-event" style="background:{c}" title="{html.escape(t)}">{html.escape(t)}</div>'
                for t, c in evs[:4]
            )
            if len(evs) > 4:
                ev_html += f'<div class="cal-more">+{len(evs) - 4}건 더</div>'
            _rows.append(f'<td class="{cell_class}"><div class="cal-daynum">{day.day}</div>{ev_html}</td>')
        _rows.append("</tr>")
    _rows.append("</table>")
    st.markdown("".join(_rows), unsafe_allow_html=True)

    st.caption(
        "🔵 매수 · 🔴 매도 · 🟢 배당 · 🟣 실적발표(해외 보유종목만, yfinance 기준). "
        "국내 종목 실적발표는 자동 조회 소스가 없어 표시되지 않습니다."
    )

# ---------------------------------------------------------------------------
# 매매일지
# ---------------------------------------------------------------------------
with tab_trades:
    st.subheader("매매 기록 추가")
    col_m, col_tk = st.columns(2)
    market = col_m.selectbox("시장", MARKETS, format_func=market_label, key="trade_market_outer")
    ticker = col_tk.text_input("티커/종목코드 (예: 005930, AAPL)", key="trade_ticker_outer")
    currency = "USD" if market == "US" else "원"
    if market == "US":
        st.caption("해외 종목은 체결가/수수료/거래세를 달러(USD) 기준으로 입력하세요 (원화는 자동 환산).")

    with st.form("trade_form", clear_on_submit=True):
        name = st.text_input("종목명 (선택, 보유 중인 티커면 자동완성)", value=suggest_name(ticker, market))

        col4, col5, col6 = st.columns(3)
        side = col4.selectbox("구분", ["BUY", "SELL"], format_func=lambda s: "매수" if s == "BUY" else "매도")
        quantity = col5.number_input("수량", min_value=0.0, step=1.0)
        price = col6.number_input(f"체결가 ({currency})", min_value=0.0, step=1.0)

        col7, col8 = st.columns(2)
        fee = col7.number_input(f"수수료 ({currency})", min_value=0.0, step=0.1, value=0.0)
        tax = col8.number_input(f"거래세 (매도 시, {currency})", min_value=0.0, step=0.1, value=0.0)
        trade_date = st.date_input("거래일", value=dt.date.today())
        strategy_tag = st.text_input("전략/태그 (선택)")

        thesis = st.text_area("매매 사유/근거")
        submitted = st.form_submit_button("기록 추가")
        if submitted:
            if not ticker or quantity <= 0 or price <= 0:
                st.error("티커, 수량, 체결가는 필수입니다.")
            else:
                fx_rate = None
                price_krw, fee_krw, tax_krw = price, fee, tax
                if market == "US":
                    fx_rate = cached_usdkrw()
                    if fx_rate:
                        price_krw, fee_krw, tax_krw = price * fx_rate, fee * fx_rate, tax * fx_rate
                db.add_trade(
                    ticker.strip().upper() if market == "US" else ticker.strip(),
                    name.strip() or None,
                    market,
                    side,
                    quantity,
                    price_krw,
                    fee_krw,
                    trade_date.isoformat(),
                    strategy_tag.strip() or None,
                    thesis.strip() or None,
                    tax_krw,
                    fx_rate,
                )
                st.success("기록을 추가했습니다.")
                st.rerun()

    st.subheader("전체 기록")
    trades = db.get_trades()
    if trades:
        df = pd.DataFrame([dict(t) for t in trades])
        df["side"] = df["side"].map({"BUY": "매수", "SELL": "매도"})
        df["market"] = df["market"].map(market_label)
        df["quantity"] = df["quantity"].apply(fmt_qty)
        df["price"] = df["price"].apply(fmt)
        df["fee"] = df["fee"].apply(fmt)
        df["tax"] = df["tax"].apply(fmt)
        render_table(
            df[
                ["id", "trade_date", "side", "market", "ticker", "name", "quantity", "price",
                 "fee", "tax", "strategy_tag", "thesis"]
            ],
            scroll=True,
        )
        del_id = st.number_input("삭제할 기록 ID", min_value=0, step=1, value=0)
        if st.button("선택한 ID 삭제") and del_id > 0:
            db.delete_trade(int(del_id))
            st.success(f"ID {del_id} 삭제 완료")
            st.rerun()
    else:
        st.caption("기록이 없습니다.")

# ---------------------------------------------------------------------------
# 배당금
# ---------------------------------------------------------------------------
with tab_dividends:
    st.subheader("배당금 기록 추가")
    col1, col2 = st.columns(2)
    d_market = col1.selectbox("시장", MARKETS, format_func=market_label, key="d_market")
    d_ticker = col2.text_input("티커/종목코드", key="d_ticker")
    with st.form("dividend_form", clear_on_submit=True):
        d_name = st.text_input(
            "종목명 (선택, 보유 중인 티커면 자동완성)", value=suggest_name(d_ticker, d_market), key="d_name"
        )

        col4, col5, col6 = st.columns(3)
        d_amount = col4.number_input("입금액 (세후 실수령액)", min_value=0.0, step=100.0)
        d_tax = col5.number_input("원천징수세액 (선택)", min_value=0.0, step=100.0, value=0.0)
        d_date = col6.date_input("입금일", value=dt.date.today(), key="d_date")

        d_note = st.text_input("메모 (선택)")
        submitted = st.form_submit_button("배당금 추가")
        if submitted:
            if not d_ticker or d_amount <= 0:
                st.error("티커와 입금액은 필수입니다.")
            else:
                db.add_dividend(
                    d_ticker.strip().upper() if d_market == "US" else d_ticker.strip(),
                    d_name.strip() or None,
                    d_market,
                    d_date.isoformat(),
                    d_amount,
                    d_tax,
                    d_note.strip() or None,
                )
                st.success("배당금 기록을 추가했습니다.")
                st.rerun()

    st.subheader("배당금 내역")
    dividends = db.get_dividends()
    if dividends:
        ddf = pd.DataFrame([dict(d) for d in dividends])
        ddf["market"] = ddf["market"].map(market_label)
        display_df = ddf.copy()
        display_df["amount"] = display_df["amount"].apply(fmt)
        display_df["tax"] = display_df["tax"].apply(fmt)
        render_table(
            display_df[["id", "pay_date", "market", "ticker", "name", "amount", "tax", "note"]],
            scroll=True,
        )
        del_div_id = st.number_input("삭제할 배당 기록 ID", min_value=0, step=1, value=0, key="del_div_id")
        if st.button("선택한 배당 ID 삭제") and del_div_id > 0:
            db.delete_dividend(int(del_div_id))
            st.success(f"ID {del_div_id} 삭제 완료")
            st.rerun()

        st.subheader("종목별 누적 배당금")
        by_ticker = ddf.groupby(["ticker", "name"], dropna=False)["amount"].sum().reset_index()
        by_ticker.columns = ["티커", "종목명", "누적 배당금"]
        by_ticker = by_ticker.sort_values("누적 배당금", ascending=False)
        by_ticker["누적 배당금"] = by_ticker["누적 배당금"].apply(fmt)
        render_table(by_ticker)
    else:
        st.caption("배당금 기록이 없습니다.")

# ---------------------------------------------------------------------------
# 목표가/손절가
# ---------------------------------------------------------------------------
with tab_targets:
    st.subheader("목표가/손절가 등록")
    col1, col2 = st.columns(2)
    t_market = col1.selectbox("시장", MARKETS, format_func=market_label, key="t_market")
    t_ticker = col2.text_input("티커/종목코드", key="t_ticker")
    with st.form("target_form", clear_on_submit=True):
        t_name = st.text_input(
            "종목명 (선택, 보유 중인 티커면 자동완성)", value=suggest_name(t_ticker, t_market), key="t_name"
        )

        col4, col5 = st.columns(2)
        target_price = col4.number_input("목표가", min_value=0.0, step=1.0)
        stop_loss = col5.number_input("손절가", min_value=0.0, step=1.0)
        note = st.text_area("메모 (선택)")

        submitted = st.form_submit_button("목표가 등록")
        if submitted:
            if not t_ticker or target_price <= 0:
                st.error("티커와 목표가는 필수입니다.")
            else:
                db.add_target(
                    t_ticker.strip().upper() if t_market == "US" else t_ticker.strip(),
                    t_name.strip() or None,
                    t_market,
                    target_price,
                    stop_loss or None,
                    note.strip() or None,
                    dt.date.today().isoformat(),
                )
                st.success("목표가를 등록했습니다.")
                st.rerun()

    st.subheader("등록된 목표가")
    targets = db.get_targets(active_only=True)
    for t in targets:
        with st.expander(f"{t['name'] or t['ticker']} ({t['ticker']})"):
            price = t["manual_price"] or cached_price(t["ticker"], t["market"])
            st.write(f"목표가: {t['target_price']:,.0f}" if t["target_price"] else "목표가 미설정")
            st.write(f"손절가: {t['stop_loss']:,.0f}" if t["stop_loss"] else "손절가 미설정")
            st.write(f"현재가(자동): {price:,.0f}" if price else "현재가 자동 조회 실패")
            if t["note"]:
                st.caption(t["note"])
            manual = st.number_input(
                "현재가 수동 입력 (자동 조회 실패 시)", min_value=0.0, step=1.0, key=f"manual_{t['id']}"
            )
            colA, colB = st.columns(2)
            if colA.button("수동가 저장", key=f"save_{t['id']}") and manual > 0:
                db.update_target_manual_price(t["id"], manual)
                st.success("저장했습니다.")
                st.rerun()
            if colB.button("비활성화 (달성/종료)", key=f"deact_{t['id']}"):
                db.deactivate_target(t["id"])
                st.rerun()

# ---------------------------------------------------------------------------
# 노트 (종목 무관 일반 노트)
# ---------------------------------------------------------------------------
with tab_journal:
    st.subheader("노트 작성")

    NEW_ENTRY_LABEL = "➕ 새 항목 (직접 입력)"

    if st.session_state.get("_clear_note_inputs"):
        st.session_state.note_ticker_input = ""
        st.session_state.note_name_input = ""
        st.session_state.note_holding_select = NEW_ENTRY_LABEL
        del st.session_state["_clear_note_inputs"]

    note_trades = db.get_trades()
    note_positions = compute_positions(note_trades) if note_trades else {}
    NAME_TO_TICKER_MAP = {name: ticker for ticker, name in TICKER_NAME_MAP.items()}

    def _holdings_by_market(market):
        items = []
        for ticker, pos in note_positions.items():
            if pos["market"] != market or pos["qty"] <= 0:
                continue
            price = price_in_krw(ticker, market)
            eval_amount = price * pos["qty"] if price is not None else -1
            items.append((eval_amount, ticker, pos["name"] or ticker))
        items.sort(key=lambda x: x[0], reverse=True)
        return items

    holding_options = [NEW_ENTRY_LABEL]
    holding_label_map = {}
    for flag, market in (("🇰🇷", "KR"), ("🇺🇸", "US")):
        for eval_amount, ticker, name in _holdings_by_market(market):
            label = f"{flag} {name} ({ticker})"
            holding_options.append(label)
            holding_label_map[label] = (ticker, name)

    def _apply_holding_selection():
        sel = st.session_state.note_holding_select
        if sel == NEW_ENTRY_LABEL:
            return
        ticker, name = holding_label_map[sel]
        st.session_state.note_ticker_input = ticker
        st.session_state.note_name_input = name

    def _on_note_ticker_change():
        t = st.session_state.note_ticker_input.strip()
        name = TICKER_NAME_MAP.get(t) or TICKER_NAME_MAP.get(t.upper())
        if name:
            st.session_state.note_name_input = name

    def _on_note_name_change():
        n = st.session_state.note_name_input.strip()
        ticker = NAME_TO_TICKER_MAP.get(n)
        if ticker:
            st.session_state.note_ticker_input = ticker

    st.selectbox(
        "종목 선택 (보유 종목, 평가금 높은 순)",
        holding_options,
        key="note_holding_select",
        on_change=_apply_holding_selection,
    )
    col_nt, col_nn = st.columns(2)
    col_nt.text_input("티커/종목코드 (선택)", key="note_ticker_input", on_change=_on_note_ticker_change)
    col_nn.text_input("종목명 (선택)", key="note_name_input", on_change=_on_note_name_change)

    with st.form("journal_form", clear_on_submit=True):
        j_date = st.date_input("날짜", value=dt.date.today())
        j_title = st.text_input("제목")
        j_content = st.text_area("내용")
        submitted = st.form_submit_button("저장")
        if submitted:
            if not j_title:
                st.error("제목은 필수입니다.")
            else:
                j_ticker = st.session_state.get("note_ticker_input", "")
                db.add_journal(j_date.isoformat(), j_ticker.strip() or None, j_title.strip(), j_content.strip())
                st.session_state["_clear_note_inputs"] = True
                st.success("저장했습니다.")
                st.rerun()

    st.subheader("노트 목록")
    entries = db.get_journal(category="note")
    for e in entries:
        ticker_label = e["ticker"]
        if ticker_label and TICKER_NAME_MAP.get(ticker_label):
            ticker_label = f"{TICKER_NAME_MAP[ticker_label]} ({ticker_label})"
        with st.expander(f"[{e['entry_date']}] {e['title']}" + (f" ({ticker_label})" if ticker_label else "")):
            st.write(e["content"])

# ---------------------------------------------------------------------------
# 성과분석
# ---------------------------------------------------------------------------
with tab_perf:
    trades = db.get_trades()
    if not trades:
        st.info("매매 기록이 없어 분석할 내용이 없습니다.")
    else:
        positions = compute_positions(trades)
        dividends_by_ticker = defaultdict(float)
        for d in db.get_dividends():
            dividends_by_ticker[d["ticker"]] += d["amount"]

        rows = []
        for ticker, pos in positions.items():
            realized = pos["realized_pnl"]
            price = price_in_krw(ticker, pos["market"]) if pos["qty"] > 0 else None
            unrealized = (price - pos["avg_cost"]) * pos["qty"] if price is not None and pos["qty"] > 0 else 0
            dividend = dividends_by_ticker.get(ticker, 0.0)
            total = realized + unrealized + dividend
            rows.append(
                {
                    "_sort": total,
                    "종목": pos["name"] or ticker,
                    "티커": ticker,
                    "실현손익": fmt(round(realized, 0)),
                    "평가손익": fmt(round(unrealized, 0)),
                    "배당금": fmt(round(dividend, 0)),
                    "합계": fmt(round(total, 0)),
                    "매도횟수": len(pos["sell_records"]),
                }
            )
        df = pd.DataFrame(rows).sort_values("_sort", ascending=False).drop(columns=["_sort"])
        st.subheader("종목별 손익 (배당금 포함)")
        render_table(df, scroll=True)

        st.subheader("누적 실현손익 추이")
        chrono = sorted(trades, key=chronological_key)
        cum_data = []
        running_positions = {}
        cum = 0.0
        for t in chrono:
            key = t["ticker"]
            if key not in running_positions:
                running_positions[key] = {"qty": 0.0, "avg_cost": 0.0}
            p = running_positions[key]
            if t["side"] == "BUY":
                total_cost = p["qty"] * p["avg_cost"] + t["quantity"] * t["price"] + (t["fee"] or 0)
                p["qty"] += t["quantity"]
                p["avg_cost"] = total_cost / p["qty"] if p["qty"] else 0.0
            else:
                pnl = (t["price"] - p["avg_cost"]) * t["quantity"] - (t["fee"] or 0) - (t["tax"] or 0)
                cum += pnl
                p["qty"] -= t["quantity"]
                cum_data.append({"날짜": t["trade_date"], "누적실현손익": cum})
        if cum_data:
            chart_df = pd.DataFrame(cum_data)
            chart = (
                alt.Chart(chart_df)
                .mark_line(point=True)
                .encode(
                    x=alt.X("날짜:O", title="날짜", axis=alt.Axis(labelAngle=-45)),
                    y=alt.Y("누적실현손익:Q", title="누적실현손익", axis=alt.Axis(format=",.0f")),
                    tooltip=[
                        alt.Tooltip("날짜:O", title="날짜"),
                        alt.Tooltip("누적실현손익:Q", title="누적실현손익", format=",.0f"),
                    ],
                )
                .interactive()
            )
            st.altair_chart(chart, use_container_width=True)
        else:
            st.caption("매도 기록이 없어 실현손익 추이를 표시할 수 없습니다.")

# ---------------------------------------------------------------------------
# AI 인사이트 (Claude가 조사해서 저장한 뉴스/공시/리서치)
# ---------------------------------------------------------------------------
with tab_ai:
    st.subheader("AI 인사이트")
    st.caption(
        "채팅에서 Claude에게 \"이번주 보유종목 이슈 정리해줘\" 같이 요청하면, "
        "찾은 뉴스·공시·리서치 내용을 정리해서 여기에 저장해줍니다."
    )

    ai_entries = db.get_journal(category="ai_insight")
    if not ai_entries:
        st.info("아직 저장된 AI 인사이트가 없습니다. 채팅에서 요청해보세요.")
    else:
        for e in ai_entries:
            ticker_label = e["ticker"]
            if ticker_label and TICKER_NAME_MAP.get(ticker_label):
                ticker_label = f"{TICKER_NAME_MAP[ticker_label]} ({ticker_label})"
            header = f"[{e['entry_date']}] {e['title']}" + (f" · {ticker_label}" if ticker_label else "")
            with st.expander(header):
                st.write(e["content"])
                if e["source_url"]:
                    st.markdown(f"[출처 링크]({e['source_url']})")
