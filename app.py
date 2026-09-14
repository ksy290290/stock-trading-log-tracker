import datetime as dt
from collections import defaultdict

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
    }
    .jnl-table-scroll {
        max-height: 480px;
        overflow-y: auto;
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


def render_table(df, scroll=False):
    """검정/볼드 컬럼명을 보장하기 위해 st.dataframe 대신 스타일링된 HTML 표로 렌더링.
    (st.dataframe은 캔버스로 그려져서 CSS로 헤더 스타일을 바꿀 수 없음)"""
    html = df.to_html(index=False, escape=True, border=0, classes="jnl-table")
    if scroll:
        html = f'<div class="jnl-table-scroll">{html}</div>'
    st.markdown(html, unsafe_allow_html=True)


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


tab_dashboard, tab_trades, tab_dividends, tab_targets, tab_journal, tab_perf = st.tabs(
    ["📊 대시보드", "📝 매매일지", "💰 배당금", "🎯 목표가/손절가", "📓 노트", "📈 성과분석"]
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
        c1.metric("투자금액 (원금)", f"{principal:,.0f}")
        c2.metric("평가 손익 (미실현)", f"{unrealized:,.0f}")
        c3.metric("실현 손익", f"{realized:,.0f}")
        c4.metric("누적 배당금", f"{total_dividends:,.0f}")
        c5.metric("승률 (매도 기준)", f"{wr:.0%}" if wr is not None else "-")

        st.subheader("보유 종목")
        holdings_kr, holdings_us = [], []
        for ticker, pos in positions.items():
            if pos["qty"] <= 0:
                continue
            price = price_lookup.get(ticker)
            eval_amount = price * pos["qty"] if price is not None else None
            entry = {
                "eval_amount": eval_amount,
                "종목": pos["name"] or ticker,
                "티커": ticker,
                "수량": fmt_qty(pos["qty"]),
                "평단가": fmt(pos["avg_cost"]),
                "현재가": fmt(price) if price is not None else "조회 실패",
                "평가금": fmt(eval_amount),
                "평가손익": fmt((price - pos["avg_cost"]) * pos["qty"]) if price is not None else "-",
            }
            (holdings_kr if pos["market"] == "KR" else holdings_us).append(entry)

        def render_holdings(label, entries):
            st.markdown(f"**{label}**")
            if not entries:
                st.caption("보유 종목 없음")
                return
            entries_sorted = sorted(
                entries, key=lambda e: e["eval_amount"] if e["eval_amount"] is not None else -1, reverse=True
            )
            df = pd.DataFrame(entries_sorted).drop(columns=["eval_amount"])
            render_table(df)

        col_kr, col_us = st.columns(2)
        with col_kr:
            render_holdings("🇰🇷 국내", holdings_kr)
        with col_us:
            render_holdings("🇺🇸 해외", holdings_us)

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
# 매매일지
# ---------------------------------------------------------------------------
with tab_trades:
    st.subheader("매매 기록 추가")
    with st.form("trade_form", clear_on_submit=True):
        col1, col2, col3 = st.columns(3)
        market = col1.selectbox("시장", MARKETS, format_func=market_label)
        ticker = col2.text_input("티커/종목코드 (예: 005930, AAPL)")
        name = col3.text_input("종목명 (선택)")

        col4, col5, col6 = st.columns(3)
        side = col4.selectbox("구분", ["BUY", "SELL"], format_func=lambda s: "매수" if s == "BUY" else "매도")
        quantity = col5.number_input("수량", min_value=0.0, step=1.0)
        price = col6.number_input("체결가", min_value=0.0, step=1.0)

        col7, col8 = st.columns(2)
        fee = col7.number_input("수수료", min_value=0.0, step=0.1, value=0.0)
        tax = col8.number_input("거래세 (매도 시)", min_value=0.0, step=0.1, value=0.0)
        trade_date = st.date_input("거래일", value=dt.date.today())
        strategy_tag = st.text_input("전략/태그 (선택)")

        thesis = st.text_area("매매 사유/근거")
        submitted = st.form_submit_button("기록 추가")
        if submitted:
            if not ticker or quantity <= 0 or price <= 0:
                st.error("티커, 수량, 체결가는 필수입니다.")
            else:
                db.add_trade(
                    ticker.strip().upper() if market == "US" else ticker.strip(),
                    name.strip() or None,
                    market,
                    side,
                    quantity,
                    price,
                    fee,
                    trade_date.isoformat(),
                    strategy_tag.strip() or None,
                    thesis.strip() or None,
                    tax,
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
                ["id", "trade_date", "market", "ticker", "name", "side", "quantity", "price",
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
    with st.form("dividend_form", clear_on_submit=True):
        col1, col2, col3 = st.columns(3)
        d_market = col1.selectbox("시장", MARKETS, format_func=market_label, key="d_market")
        d_ticker = col2.text_input("티커/종목코드", key="d_ticker")
        d_name = col3.text_input("종목명 (선택)", key="d_name")

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
    with st.form("target_form", clear_on_submit=True):
        col1, col2, col3 = st.columns(3)
        t_market = col1.selectbox("시장", MARKETS, format_func=market_label, key="t_market")
        t_ticker = col2.text_input("티커/종목코드", key="t_ticker")
        t_name = col3.text_input("종목명 (선택)", key="t_name")

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
    with st.form("journal_form", clear_on_submit=True):
        j_date = st.date_input("날짜", value=dt.date.today())
        j_ticker = st.text_input("관련 종목 (선택)")
        j_title = st.text_input("제목")
        j_content = st.text_area("내용")
        submitted = st.form_submit_button("저장")
        if submitted:
            if not j_title:
                st.error("제목은 필수입니다.")
            else:
                db.add_journal(j_date.isoformat(), j_ticker.strip() or None, j_title.strip(), j_content.strip())
                st.success("저장했습니다.")
                st.rerun()

    st.subheader("노트 목록")
    entries = db.get_journal()
    for e in entries:
        with st.expander(f"[{e['entry_date']}] {e['title']}" + (f" ({e['ticker']})" if e["ticker"] else "")):
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
        render_table(df)

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
            chart_df = pd.DataFrame(cum_data).set_index("날짜")
            st.line_chart(chart_df)
        else:
            st.caption("매도 기록이 없어 실현손익 추이를 표시할 수 없습니다.")
