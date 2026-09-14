import datetime as dt
from collections import defaultdict

import pandas as pd
import streamlit as st

import db
import price_data
from analytics import compute_positions, total_realized_pnl, total_unrealized_pnl, win_rate

st.set_page_config(page_title="주식 매매일지", page_icon="📈", layout="wide")
db.init_db()

MARKETS = ["KR", "US"]


def market_label(m):
    return "국내" if m == "KR" else "해외"


@st.cache_data(ttl=300)
def cached_price(ticker, market):
    return price_data.get_current_price(ticker, market)


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
            ticker: cached_price(ticker, pos["market"])
            for ticker, pos in positions.items()
            if pos["qty"] > 0
        }
        realized = total_realized_pnl(positions)
        unrealized = total_unrealized_pnl(positions, price_lookup)
        wr = win_rate(positions)
        total_dividends = sum(d["amount"] for d in db.get_dividends())

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("실현 손익", f"{realized:,.0f}")
        c2.metric("평가 손익 (미실현)", f"{unrealized:,.0f}")
        c3.metric("누적 배당금", f"{total_dividends:,.0f}")
        c4.metric("승률 (매도 기준)", f"{wr:.0%}" if wr is not None else "-")

        st.subheader("보유 종목")
        rows = []
        for ticker, pos in positions.items():
            if pos["qty"] <= 0:
                continue
            price = price_lookup.get(ticker)
            rows.append(
                {
                    "종목": pos["name"] or ticker,
                    "티커": ticker,
                    "시장": market_label(pos["market"]),
                    "수량": pos["qty"],
                    "평단가": round(pos["avg_cost"], 2),
                    "현재가": price if price is not None else "조회 실패",
                    "평가손익": round((price - pos["avg_cost"]) * pos["qty"], 0)
                    if price is not None
                    else "-",
                }
            )
        if rows:
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
        else:
            st.caption("현재 보유 중인 종목이 없습니다 (전량 매도됨).")

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

        col7, col8, col9 = st.columns(3)
        fee = col7.number_input("수수료", min_value=0.0, step=0.1, value=0.0)
        trade_date = col8.date_input("거래일", value=dt.date.today())
        strategy_tag = col9.text_input("전략/태그 (선택)")

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
                )
                st.success("기록을 추가했습니다.")
                st.rerun()

    st.subheader("전체 기록")
    trades = db.get_trades()
    if trades:
        df = pd.DataFrame([dict(t) for t in trades])
        df["side"] = df["side"].map({"BUY": "매수", "SELL": "매도"})
        df["market"] = df["market"].map(market_label)
        st.dataframe(
            df[
                ["id", "trade_date", "market", "ticker", "name", "side", "quantity", "price",
                 "fee", "strategy_tag", "thesis"]
            ],
            use_container_width=True,
            hide_index=True,
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
        st.dataframe(
            ddf[["id", "pay_date", "market", "ticker", "name", "amount", "tax", "note"]],
            use_container_width=True,
            hide_index=True,
        )
        del_div_id = st.number_input("삭제할 배당 기록 ID", min_value=0, step=1, value=0, key="del_div_id")
        if st.button("선택한 배당 ID 삭제") and del_div_id > 0:
            db.delete_dividend(int(del_div_id))
            st.success(f"ID {del_div_id} 삭제 완료")
            st.rerun()

        st.subheader("종목별 누적 배당금")
        by_ticker = ddf.groupby(["ticker", "name"], dropna=False)["amount"].sum().reset_index()
        by_ticker.columns = ["티커", "종목명", "누적 배당금"]
        st.dataframe(by_ticker.sort_values("누적 배당금", ascending=False), use_container_width=True, hide_index=True)
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
            price = cached_price(ticker, pos["market"]) if pos["qty"] > 0 else None
            unrealized = (price - pos["avg_cost"]) * pos["qty"] if price is not None and pos["qty"] > 0 else 0
            dividend = dividends_by_ticker.get(ticker, 0.0)
            rows.append(
                {
                    "종목": pos["name"] or ticker,
                    "티커": ticker,
                    "실현손익": round(realized, 0),
                    "평가손익": round(unrealized, 0),
                    "배당금": round(dividend, 0),
                    "합계": round(realized + unrealized + dividend, 0),
                    "매도횟수": len(pos["sell_records"]),
                }
            )
        df = pd.DataFrame(rows).sort_values("합계", ascending=False)
        st.subheader("종목별 손익 (배당금 포함)")
        st.dataframe(df, use_container_width=True, hide_index=True)

        st.subheader("누적 실현손익 추이")
        chrono = sorted(trades, key=lambda t: (t["trade_date"], t["id"]))
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
                pnl = (t["price"] - p["avg_cost"]) * t["quantity"] - (t["fee"] or 0)
                cum += pnl
                p["qty"] -= t["quantity"]
                cum_data.append({"날짜": t["trade_date"], "누적실현손익": cum})
        if cum_data:
            chart_df = pd.DataFrame(cum_data).set_index("날짜")
            st.line_chart(chart_df)
        else:
            st.caption("매도 기록이 없어 실현손익 추이를 표시할 수 없습니다.")
