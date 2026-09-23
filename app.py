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
from analytics import (
    chronological_key,
    compute_holding_episodes,
    compute_positions,
    total_realized_pnl,
    total_unrealized_pnl,
    win_rate,
)
import treemap
from heatmap_data import KOSPI_STOCKS, SP500_STOCKS

st.set_page_config(page_title="주식 매매일지", page_icon="assets/app_icon.png", layout="wide")
db.init_db()

st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@400;500;700;900&display=swap');

    :root {
        --canvas: #EEF1F5;
        --app-bg: #F7F9FC;
        --surface: #FFFFFF;
        --surface-2: #F1F4F8;
        --text: #191F28;
        --text-dim: #8B95A1;
        --text-faint: #B0B8C1;
        --border: #EDF0F4;
        --accent: #3182F6;
        --accent-soft: #EAF2FE;
        --up: #F04452;
        --up-soft: #FDEDEE;
        --down: #3182F6;
        --down-soft: #EAF2FE;
        --shadow: 0 1px 2px rgba(25,31,40,0.04), 0 8px 20px rgba(25,31,40,0.05);
    }
    .stApp {
        background: var(--app-bg);
        font-family: 'Noto Sans KR', 'Apple SD Gothic Neo', 'Malgun Gothic', -apple-system, BlinkMacSystemFont, sans-serif;
        font-variant-numeric: tabular-nums;
    }
    div[role="tablist"] {
        position: sticky;
        top: 60px;
        z-index: 999;
        background-color: var(--app-bg);
    }
    h1, h2, h3 {
        color: var(--text) !important;
        font-weight: 900 !important;
        letter-spacing: -0.01em;
    }
    .jnl-table {
        width: 100%;
        border-collapse: collapse;
        font-size: 0.88rem;
    }
    .jnl-table th {
        color: var(--text) !important;
        font-weight: 700 !important;
        text-align: left;
        padding: 10px 12px;
        border-bottom: 1px solid var(--border);
        background-color: var(--surface);
        position: sticky;
        top: 0;
        font-size: 0.78rem;
    }
    .jnl-table td {
        padding: 9px 12px;
        border-bottom: 1px solid var(--border);
        white-space: nowrap;
        color: var(--text);
    }
    .jnl-table tr:hover td {
        background-color: var(--surface-2);
    }
    .jnl-table-scroll {
        max-height: 480px;
        overflow-y: auto;
    }
    .jnl-table-wrap {
        overflow-x: auto;
        background: var(--surface);
        border-radius: 16px;
        box-shadow: var(--shadow);
        padding: 4px 6px;
    }
    /* 국내/해외 표가 서로 같은 컬럼 순서를 쓰므로, 폭을 완전히 고정해(table-layout:fixed)
       내용 길이와 무관하게 두 표의 가로 크기가 항상 똑같게 함 */
    .holdings-table {
        width: 1440px !important;
        table-layout: fixed;
    }
    .holdings-table td, .holdings-table th {
        padding: 8px 8px !important;
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
        width: 600px;
        white-space: normal;
        overflow: visible;
        text-overflow: clip;
        word-break: break-word;
    }
    .metric-card {
        background: var(--surface);
        border: 1px solid var(--border);
        border-radius: 18px;
        box-shadow: var(--shadow);
        padding: 16px 18px;
        margin-bottom: 6px;
    }
    .metric-card .metric-label {
        display: flex;
        align-items: center;
        gap: 6px;
        font-size: 0.78rem;
        color: var(--text);
        font-weight: 700;
        margin-bottom: 8px;
    }
    .metric-card .metric-label::before {
        content: "";
        width: 8px;
        height: 8px;
        border-radius: 50%;
        background: var(--dot-color, var(--accent));
        flex: 0 0 auto;
    }
    .metric-card .metric-value {
        font-size: 1.4rem;
        font-weight: 900;
        color: var(--text);
        letter-spacing: -0.01em;
    }
    .metric-card .metric-sub {
        margin-top: 10px;
        padding-top: 8px;
        border-top: 1px solid var(--border);
        font-size: 0.76rem;
        color: #4B5563;
    }
    .metric-card .metric-sub div {
        margin-bottom: 3px;
    }
    .cal-grid {
        width: 100%;
        border-collapse: collapse;
        table-layout: fixed;
    }
    .cal-grid th {
        background-color: var(--surface);
        color: var(--text-dim) !important;
        font-weight: 700 !important;
        padding: 8px;
        border: 1px solid var(--border);
        text-align: center;
        font-size: 0.76rem;
    }
    .cal-grid td {
        vertical-align: top;
        border: 1px solid var(--border);
        background-color: var(--surface);
        height: 112px;
        padding: 4px;
        font-size: 0.72rem;
        /* overflow:hidden was clipping the "+N건 더" popup, since it's a
           descendant even though position:absolute - popups need a
           non-clipping ancestor to be able to float over neighboring rows */
        position: relative;
        cursor: pointer;
    }
    .cal-grid td.cal-dim {
        background-color: var(--surface-2);
        color: var(--text-faint);
    }
    .cal-daynum {
        font-weight: 700;
        color: var(--text);
        margin-bottom: 2px;
    }
    .cal-tot-buy {
        color: var(--accent);
        font-size: 0.64rem;
        font-weight: 700;
    }
    .cal-tot-sell {
        color: var(--up);
        font-size: 0.64rem;
        font-weight: 700;
    }
    .cal-tot-div {
        color: #16A34A;
        font-size: 0.64rem;
        font-weight: 700;
    }
    .cal-event strong {
        font-weight: 800;
    }
    .cal-event {
        color: #ffffff;
        border-radius: 4px;
        padding: 0px 4px;
        margin-bottom: 1px;
        font-size: 0.68rem;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
    }
    .cal-details {
        position: relative;
        margin-top: 1px;
    }
    .cal-details summary {
        font-size: 0.68rem;
        color: var(--text-faint);
        cursor: pointer;
        list-style: none;
    }
    .cal-details summary::-webkit-details-marker {
        display: none;
    }
    .cal-details[open] summary {
        color: var(--text-dim);
        font-weight: 700;
    }
    .cal-full {
        /* details 요소 기준 바로 아래에 뜨게 해서 summary(토글 버튼)를 안 가리게 함
           - 안 그러면 팝업이 summary를 덮어버려서 다시 클릭해도 안 닫힘 */
        position: absolute;
        top: 100%;
        left: 0;
        margin-top: 2px;
        min-width: 220px;
        max-width: 320px;
        max-height: 280px;
        overflow-y: auto;
        background-color: var(--surface);
        border: 1px solid var(--border);
        border-radius: 12px;
        box-shadow: 0 4px 20px rgba(25,31,40,0.14);
        padding: 8px;
        z-index: 1000;
        cursor: default;
        white-space: normal;
    }
    .cal-full-title {
        font-weight: 700;
        color: var(--text);
        margin-bottom: 4px;
        font-size: 0.75rem;
    }
    .cal-full .cal-event {
        white-space: normal;
    }
    .tm-canvas {
        position: relative;
        background: var(--surface);
        border-radius: 16px;
        box-shadow: var(--shadow);
        /* overflow를 auto/hidden으로 두면 CSS 스펙상 overflow-x/y가 서로 묶여서
           타일 hover 툴팁(position:absolute, 타일 바깥으로 튀어나옴)이 잘림 ->
           캘린더 팝업 때와 동일한 문제라 데스크톱 너비에서는 일부러 overflow를
           지정하지 않음(기본 visible). */
    }
    /* 폰 너비에서는 터치라 hover 툴팁 자체가 의미 없으니(터치로는 :hover가 안 걸림),
       대신 좌우 스크롤이 되게 함 - 안 그러면 조상 요소의 overflow:hidden 때문에
       캔버스 오른쪽이 그냥 잘려서 아예 안 보이는 채로 스크롤도 안 됨. */
    @media (max-width: 640px) {
        .tm-canvas {
            overflow-x: auto;
            -webkit-overflow-scrolling: touch;
            max-width: 100%;
            /* 기본값(pan-x pan-y)은 두 손가락 제스처를 스크롤로만 먹어서 브라우저
               자체 핀치줌이 안 먹힘 - pinch-zoom을 같이 허용해서 확대/축소도 되게 함 */
            touch-action: pan-x pinch-zoom;
        }
    }
    .tm-sector-header {
        position: absolute;
        box-sizing: border-box;
        background: var(--surface-2);
        color: var(--text-dim);
        font-weight: 700;
        font-size: 0.68rem;
        display: flex;
        align-items: center;
        padding-left: 6px;
        border-radius: 8px 8px 0 0;
        overflow: hidden;
        white-space: nowrap;
    }
    .tm-tile {
        position: absolute;
        box-sizing: border-box;
        cursor: default;
    }
    .tm-tile-box {
        position: absolute;
        inset: 0;
        box-sizing: border-box;
        border: 1px solid rgba(255,255,255,0.5);
        display: flex;
        flex-direction: column;
        justify-content: center;
        align-items: center;
        text-align: center;
        overflow: hidden;
        line-height: 1.15;
    }
    .tm-tooltip {
        display: none;
        position: absolute;
        bottom: 100%;
        left: 50%;
        transform: translateX(-50%);
        margin-bottom: 5px;
        background: var(--text);
        color: #ffffff;
        padding: 4px 9px;
        border-radius: 8px;
        font-size: 0.72rem;
        font-weight: 600;
        white-space: nowrap;
        z-index: 2000;
        pointer-events: none;
        box-shadow: 0 2px 8px rgba(25,31,40,0.25);
    }
    .tm-tile:hover .tm-tooltip {
        display: block;
    }
    .tm-tile:hover .tm-tile-box {
        outline: 2px solid rgba(25,31,40,0.55);
        outline-offset: -2px;
    }
    .tm-logo {
        margin-bottom: 2px;
        border-radius: 6px;
        /* 배경색을 두지 않음: 로고 로드에 실패해도(예: 로고 CDN 접속 차단) 빈 흰 사각형이
           아니라 그냥 아무것도 안 보이게 하기 위함 */
        background-size: contain;
        background-repeat: no-repeat;
        background-position: center;
    }
    .tm-name {
        max-width: 100%;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
    }
    .tm-ticker {
        font-weight: 700;
    }
    .tm-pct {
        font-weight: 700;
    }

    /* 폰 화면(가로 640px 이하): 데스크톱 밀도로 짜인 표/카드가 그대로 축소되면서
       가독성이 떨어지는 문제를 완화. 특히 holdings-table은 국내/해외 표 폭을
       맞추려고 1440px로 고정해뒀던 값이라 폰에서는 그냥 옆으로 전부 밀려나가는
       원인이었음 - 폰에서는 그 고정폭을 풀고 글자를 키우는 쪽으로 전환. */
    @media (max-width: 640px) {
        .jnl-table {
            font-size: 0.98rem;
        }
        .jnl-table th {
            font-size: 0.82rem;
            padding: 10px 10px;
        }
        .jnl-table td {
            padding: 11px 10px;
        }
        .holdings-table {
            width: max-content !important;
            min-width: 100%;
        }
        .holdings-table th, .holdings-table td {
            padding: 10px 12px !important;
        }
        .holdings-table td:last-child, .holdings-table th:last-child {
            width: 220px;
        }
        .metric-card {
            padding: 14px 16px;
        }
        .metric-card .metric-value {
            font-size: 1.55rem;
        }
        .metric-card .metric-label {
            font-size: 0.82rem;
        }
        .cal-grid th {
            font-size: 0.82rem;
            padding: 6px 4px;
        }
        .cal-grid td {
            height: 92px;
            font-size: 0.78rem;
            padding: 5px;
        }
        .cal-tot-buy, .cal-tot-sell, .cal-tot-div {
            font-size: 0.7rem;
        }
        .cal-event {
            font-size: 0.72rem;
            padding: 1px 5px;
        }
        button[data-baseweb="tab"] {
            font-size: 0.86rem !important;
            padding: 10px 12px !important;
        }
        /* 캘린더 이전달/제목/다음달 행은 st.columns가 폰 폭에서 기본적으로
           세로로 쌓아버려서(◀이전달, 제목, 다음달▶ 순으로 3줄) 망가지는 걸
           막기 위해 한 줄 유지 + 버튼을 작게 축소 */
        .st-key-cal_nav_row div[data-testid="stHorizontalBlock"] {
            flex-wrap: nowrap !important;
            gap: 6px !important;
            align-items: center !important;
        }
        .st-key-cal_nav_row div[data-testid="stColumn"] {
            min-width: 0 !important;
        }
        .st-key-cal_nav_row button {
            font-size: 0.72rem !important;
            padding: 6px 8px !important;
            white-space: nowrap;
        }
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


def fmt_signed(x):
    """손익용: fmt과 동일하되 양수에도 +를 붙여서 +/- 정렬이 맞도록 함."""
    if x is None:
        return "-"
    if isinstance(x, str):
        return x
    return f"{x:+,.0f}"


def fmt_qty(x):
    """수량용: 1,000 단위 콤마는 넣되, 소수(분할매수 등)는 그대로 살려서 표시."""
    if x is None:
        return "-"
    if isinstance(x, str):
        return x
    if float(x).is_integer():
        return f"{x:,.0f}"
    return f"{x:,.4f}".rstrip("0").rstrip(".")


def render_table(df, scroll=False, extra_class="", raw_html_columns=None):
    """검정/볼드 컬럼명을 보장하기 위해 st.dataframe 대신 스타일링된 HTML 표로 렌더링.
    (st.dataframe은 캔버스로 그려져서 CSS로 헤더 스타일을 바꿀 수 없음)
    행이 줄바꿈되지 않게 해서(white-space: nowrap) 국내/해외 표의 행 높이가 맞도록 함.

    raw_html_columns: 이미 안전하게 이스케이프된 HTML(예: colorize_pnl 결과)을 담고 있어
    추가 이스케이프하면 안 되는 컬럼명 목록. 그 외 컬럼은 전부 이스케이프됨."""
    raw_html_columns = set(raw_html_columns or [])
    classes = f"jnl-table {extra_class}".strip()
    header_html = "".join(f"<th>{html.escape(str(c))}</th>" for c in df.columns)
    body_rows = []
    for _, row in df.iterrows():
        cells = []
        for col in df.columns:
            val = row[col]
            text = "" if val is None else str(val)
            cells.append(f"<td>{text if col in raw_html_columns else html.escape(text)}</td>")
        body_rows.append(f"<tr>{''.join(cells)}</tr>")
    table_html = f'<table border="0" class="{classes}"><thead><tr>{header_html}</tr></thead><tbody>{"".join(body_rows)}</tbody></table>'
    if scroll:
        table_html = f'<div class="jnl-table-scroll">{table_html}</div>'
    st.markdown(f'<div class="jnl-table-wrap">{table_html}</div>', unsafe_allow_html=True)


def colorize_pnl(text, value):
    """양수면 빨간색, 음수면 파란색으로 감싼 안전한(escape된) HTML 문자열 반환.
    value가 None/0이면 색 없이 그대로."""
    escaped = html.escape(text)
    if value is None or value == 0:
        return escaped
    color = "#F04452" if value > 0 else "#3182F6"
    return f'<span style="color:{color};font-weight:700;">{escaped}</span>'


def metric_card(label, value, color, sublines=None):
    """color는 이제 카드 배경이 아니라 라벨 앞 작은 포인트(닷) 색상으로만 씀
    (토스 스타일: 카드는 흰 배경 통일, 색은 포인트로만 절제해서 사용)."""
    sub_html = ""
    if sublines:
        sub_html = '<div class="metric-sub">' + "".join(f"<div>{html.escape(s)}</div>" for s in sublines) + "</div>"
    st.markdown(
        f'<div class="metric-card" style="--dot-color:{color};">'
        f'<div class="metric-label">{html.escape(label)}</div>'
        f'<div class="metric-value">{html.escape(value)}</div>'
        f"{sub_html}"
        f"</div>",
        unsafe_allow_html=True,
    )


_CAL_LABEL_PREFIXES = ("매수", "매도", "배당", "실적발표")


def render_cal_event(text, color, css_class="cal-event"):
    """캘린더 이벤트 한 줄을 렌더링, 앞의 매수/매도/배당/실적발표 라벨만 볼드 처리."""
    for prefix in _CAL_LABEL_PREFIXES:
        if text.startswith(prefix + " "):
            rest = text[len(prefix):]
            return (
                f'<div class="{css_class}" style="background:{color}" title="{html.escape(text)}">'
                f"<strong>{prefix}</strong>{html.escape(rest)}</div>"
            )
    return f'<div class="{css_class}" style="background:{color}" title="{html.escape(text)}">{html.escape(text)}</div>'


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


def compute_perf_rows(trades, all_dividends, period, selected_month):
    """성과분석 표에 쓰이는 종목별 행을 계산 (데스크톱 tab_perf와 모바일 성과분석 화면이
    공유). 반환값의 숫자는 포맷팅 전 원시 값 - 표시 직전에 각자 fmt()/fmt_signed() 적용."""
    positions = compute_positions(trades)
    rows = []
    if period == "전체":
        dividends_by_ticker = defaultdict(float)
        for d in all_dividends:
            dividends_by_ticker[d["ticker"]] += d["amount"]
        for ticker, pos in positions.items():
            realized = pos["realized_pnl"]
            unrealized = 0
            if pos["qty"] > 0:
                if pos["market"] == "US" and pos.get("avg_cost_usd"):
                    # 해외 종목은 매수 시점 환율로 저장된 avg_cost(KRW)를 지금 환율로 환산된
                    # 현재가와 바로 비교하면 "그때 환율 vs 지금 환율" 차이가 주식 자체 수익률에
                    # 섞여버림(대시보드에서 이미 겪은 문제와 동일) - USD 기준으로 먼저 손익을
                    # 계산한 뒤 지금 환율 하나만 곱해서 원화 환산 (대시보드와 같은 방식으로 통일).
                    usd_price = cached_price(ticker, "US")
                    fx = cached_usdkrw()
                    if usd_price is not None and fx is not None:
                        unrealized = (usd_price - pos["avg_cost_usd"]) * pos["qty"] * fx
                else:
                    price = price_in_krw(ticker, pos["market"])
                    if price is not None:
                        unrealized = (price - pos["avg_cost"]) * pos["qty"]
            dividend = dividends_by_ticker.get(ticker, 0.0)
            total = realized + unrealized + dividend
            rows.append(
                {
                    "_sort": total,
                    "종목": pos["name"] or ticker,
                    "티커": ticker,
                    "실현손익": realized,
                    "평가손익": unrealized,
                    "배당금": dividend,
                    "합계": total,
                    "매도횟수": len(pos["sell_records"]),
                }
            )
    else:
        # 월별 뷰: 평가손익은 "그 달의 실적"이라는 개념이 없어(항상 현재 시점 스냅샷) 제외하고,
        # 그 달에 실제로 발생한 실현손익/배당만 집계. 평단가(원가)는 전체 이력 기준 positions를
        # 그대로 참조하므로, 이전 달 매수분을 이번 달에 판 경우도 원가가 정확함.
        realized_by_ticker = defaultdict(float)
        sell_count_by_ticker = defaultdict(int)
        for ticker, pos in positions.items():
            for s in pos["sell_records"]:
                if s["date"].startswith(selected_month):
                    realized_by_ticker[ticker] += s["pnl"]
                    sell_count_by_ticker[ticker] += 1
        dividends_by_ticker = defaultdict(float)
        for d in all_dividends:
            if d["pay_date"].startswith(selected_month):
                dividends_by_ticker[d["ticker"]] += d["amount"]
        for ticker in sorted(set(realized_by_ticker) | set(dividends_by_ticker)):
            pos = positions.get(ticker, {})
            realized = realized_by_ticker.get(ticker, 0.0)
            dividend = dividends_by_ticker.get(ticker, 0.0)
            total = realized + dividend
            rows.append(
                {
                    "_sort": total,
                    "종목": pos.get("name") or ticker,
                    "티커": ticker,
                    "실현손익": realized,
                    "배당금": dividend,
                    "합계": total,
                    "매도횟수": sell_count_by_ticker.get(ticker, 0),
                }
            )
    return rows


def compute_perf_cum_data(trades, period, selected_month):
    """누적 실현손익 추이 차트용 데이터 (데스크톱/모바일 공유)."""
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
            p["qty"] -= t["quantity"]
            # 월별 뷰에서는 선택한 달의 매도만 누적해서, "이번 달 실현손익이 어떻게 쌓였는지"를
            # 보여줌 (전체 이력 누적값이 아니라 그 달 시작을 0으로 보는 누적)
            if period == "전체" or t["trade_date"].startswith(selected_month):
                cum += pnl
                cum_data.append({"날짜": t["trade_date"], "누적실현손익": cum})
    return cum_data


# ---------------------------------------------------------------------------
# 폰 전용 UI - PC는 기존 대시보드(위 탭 9개) 그대로, 폰은 핵심 4개(매매일지/캘린더/
# 성과분석/설정)만 네이티브 앱처럼 카드 + 하단 탭바로 재구성. User-Agent로 서버에서
# 바로 분기해서 PC/폰이 서로 다른 화면을 받도록 함 (같은 URL, 같은 데이터).
# ---------------------------------------------------------------------------
MOBILE_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@400;500;600;700;800&display=swap');
.stApp { background: #F7F5F2; font-family: 'Noto Sans KR', -apple-system, BlinkMacSystemFont, sans-serif; }
.block-container { padding: 0 12px 110px 12px !important; max-width: 100% !important; }
header[data-testid="stHeader"] { background: transparent; }
.stock-m-header { padding: 8px 4px 14px 4px; }
.stock-m-header h1 { margin: 0; font-size: 22px; font-weight: 800; color: #14151A; letter-spacing: -0.3px; }
.stock-m-header span { font-size: 13px; color: #6B7280; }
.stock-m-card { background: #FFFFFF; border: 1px solid #ECEBE7; border-radius: 14px; padding: 14px 16px; margin-bottom: 10px; }
.stock-m-card-head { display: flex; justify-content: space-between; align-items: center; gap: 8px; }
.stock-m-card-title { font-size: 15px; font-weight: 700; color: #14151A; }
.stock-m-badge { font-size: 12px; font-weight: 700; padding: 3px 10px; border-radius: 20px; flex-shrink: 0; }
.stock-m-card-detail { display: block; font-size: 13px; color: #6B7280; margin-top: 6px; }
.stock-m-tag { display: block; font-size: 12px; font-weight: 600; color: #4F46E5; margin-top: 4px; }
.stock-m-section-title { font-size: 14px; font-weight: 700; color: #374151; margin: 4px 0 10px 4px; }
.stock-m-summary-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 10px; margin-bottom: 18px; }
.stock-m-summary-card { background: #FFFFFF; border: 1px solid #ECEBE7; border-radius: 14px; padding: 14px 16px; }
.stock-m-summary-label { display: block; font-size: 12px; color: #6B7280; font-weight: 600; margin-bottom: 6px; }
.stock-m-summary-value { display: block; font-size: 19px; font-weight: 800; }
.stock-m-perf-row { display: flex; align-items: center; justify-content: space-between; gap: 10px; background: #FFFFFF; border: 1px solid #ECEBE7; border-radius: 12px; padding: 14px 16px; margin-bottom: 8px; }
.stock-m-perf-name { font-size: 14px; font-weight: 700; color: #14151A; }
.stock-m-perf-detail { font-size: 12px; color: #6B7280; margin-top: 4px; }
.stock-m-perf-total { font-size: 14px; font-weight: 800; flex-shrink: 0; }
.stock-m-cal-title { text-align: center; font-size: 17px; font-weight: 800; color: #14151A; padding-top: 4px; }
.stock-m-cal-grid { display: grid; grid-template-columns: repeat(7, 1fr); border: 1px solid #ECEBE7; border-radius: 12px; overflow: hidden; background: #FFFFFF; margin-top: 12px; }
.stock-m-cal-head { border-right: 1px solid #ECEBE7; border-bottom: 1px solid #ECEBE7; padding: 8px 0; text-align: center; font-size: 12px; font-weight: 700; color: #9CA3AF; background: #FAFAF8; }
.stock-m-cal-cell { border-right: 1px solid #ECEBE7; border-bottom: 1px solid #ECEBE7; padding: 6px 4px; min-height: 58px; display: flex; flex-direction: column; gap: 3px; }
.stock-m-cal-day { font-size: 12px; font-weight: 700; color: #14151A; }
.stock-m-cal-dim { background: #FAFAF8; }
.stock-m-cal-dim .stock-m-cal-day { color: #C7C5C0; }
.stock-m-cal-tag { font-size: 9px; font-weight: 700; color: #FFFFFF; border-radius: 5px; padding: 1px 4px; text-align: center; line-height: 1.5; }
.stock-m-cal-legend { display: flex; gap: 14px; padding: 12px 4px 0 4px; }
.stock-m-cal-legend span { display: flex; align-items: center; gap: 5px; font-size: 12px; color: #6B7280; }
.stock-m-cal-legend i { width: 8px; height: 8px; border-radius: 2px; display: inline-block; }
.st-key-mobile_cal_nav div[data-testid="stHorizontalBlock"] { flex-wrap: nowrap !important; align-items: center !important; gap: 6px !important; }
.st-key-mobile_cal_nav div[data-testid="stColumn"] { min-width: 0 !important; }
.st-key-mobile_cal_nav button { padding: 6px 10px !important; }
.st-key-mobile_fab_wrap { position: fixed; right: 18px; bottom: 92px; z-index: 999; width: 56px; }
.st-key-mobile_fab_wrap button { width: 56px !important; height: 56px !important; border-radius: 28px !important;
    background: #4F46E5 !important; color: #FFFFFF !important; font-size: 15px !important; border: none !important;
    box-shadow: 0 6px 14px rgba(79,70,229,0.35) !important; padding: 0 !important; }
.st-key-mobile_bottom_nav { position: fixed; left: 0; right: 0; bottom: 0; background: #FFFFFF;
    border-top: 1px solid #E8E6E1; padding: 6px 6px calc(env(safe-area-inset-bottom) + 6px) 6px; z-index: 1000; }
.st-key-mobile_bottom_nav div[data-testid="stHorizontalBlock"] { flex-wrap: nowrap !important; gap: 4px !important; }
.st-key-mobile_bottom_nav div[data-testid="stColumn"] { min-width: 0 !important; }
.st-key-mobile_bottom_nav button { font-size: 10px !important; padding: 8px 2px !important; white-space: nowrap; }
</style>
"""


def mobile_header(title, subtitle):
    st.markdown(
        f'<div class="stock-m-header"><h1>{html.escape(title)}</h1><span>{html.escape(subtitle)}</span></div>',
        unsafe_allow_html=True,
    )


@st.dialog("매매 기록 추가")
def mobile_add_trade_dialog():
    market = st.radio("시장", ["국내", "해외"], horizontal=True, key="madd_market")
    side = st.radio("매매 구분", ["매수", "매도"], horizontal=True, key="madd_side")
    ticker = st.text_input("종목 코드", key="madd_ticker")
    market_code = "KR" if market == "국내" else "US"
    name = st.text_input("종목명", value=suggest_name(ticker, market_code), key="madd_name")
    c1, c2 = st.columns(2)
    qty = c1.number_input("수량", min_value=0.0, step=1.0, key="madd_qty")
    price = c2.number_input("가격 (1주당)", min_value=0.0, step=1.0, key="madd_price")
    total_amount = st.number_input(
        "또는 총 매수금액 (선택 - 가격 대신 이 값을 넣으면 수량으로 나눠서 가격을 자동 계산)",
        min_value=0.0, step=1.0, key="madd_total_amount",
    )
    c3, c4 = st.columns(2)
    fee = c3.number_input("수수료", min_value=0.0, step=1.0, key="madd_fee")
    tax = c4.number_input("세금", min_value=0.0, step=1.0, key="madd_tax")
    fx_rate = None
    if market == "해외":
        fx_rate = st.number_input("체결 시점 환율 (선택, 0=미입력)", min_value=0.0, step=0.1, key="madd_fx")
    trade_date = st.date_input("거래일", key="madd_date")
    strategy_tag = st.text_input("전략 태그 (선택)", key="madd_tag")
    thesis = st.text_area("매매 사유 (선택)", key="madd_thesis")

    col_submit, col_cancel = st.columns(2)
    if col_submit.button("추가", type="primary", use_container_width=True, key="madd_submit"):
        if price <= 0 and qty > 0 and total_amount > 0:
            price = total_amount / qty
        if not ticker.strip() or qty <= 0 or price <= 0:
            st.warning("종목 코드, 수량, 가격(또는 총 매수금액)을 확인해주세요.")
        else:
            db.add_trade(
                ticker.strip(), name.strip() or None, market_code,
                "BUY" if side == "매수" else "SELL", qty, price, fee, trade_date.isoformat(),
                strategy_tag.strip() or None, thesis.strip() or None,
                tax=tax, fx_rate=(fx_rate if fx_rate else None),
            )
            st.session_state.mobile_add_open = False
            st.rerun()
    if col_cancel.button("취소", use_container_width=True, key="madd_cancel"):
        st.session_state.mobile_add_open = False
        st.rerun()


@st.dialog("매매 기록 수정")
def mobile_edit_trade_dialog(trade_id):
    t = next((x for x in db.get_trades() if x["id"] == trade_id), None)
    if t is None:
        st.warning("기록을 찾을 수 없습니다.")
        return
    market = st.radio("시장", ["국내", "해외"], horizontal=True, index=0 if t["market"] == "KR" else 1, key="medit_market")
    side = st.radio("매매 구분", ["매수", "매도"], horizontal=True, index=0 if t["side"] == "BUY" else 1, key="medit_side")
    ticker = st.text_input("종목 코드", value=t["ticker"], key="medit_ticker")
    name = st.text_input("종목명", value=t["name"] or "", key="medit_name")
    c1, c2 = st.columns(2)
    qty = c1.number_input("수량", min_value=0.0, value=float(t["quantity"]), step=1.0, key="medit_qty")
    price = c2.number_input("가격", min_value=0.0, value=float(t["price"]), step=1.0, key="medit_price")
    c3, c4 = st.columns(2)
    fee = c3.number_input("수수료", min_value=0.0, value=float(t["fee"] or 0), step=1.0, key="medit_fee")
    tax = c4.number_input("세금", min_value=0.0, value=float(t["tax"] or 0), step=1.0, key="medit_tax")
    fx_rate = None
    if market == "해외":
        fx_rate = st.number_input(
            "체결 시점 환율 (선택, 0=미입력)", min_value=0.0, value=float(t["fx_rate"] or 0), step=0.1, key="medit_fx"
        )
    trade_date = st.date_input("거래일", value=dt.date.fromisoformat(t["trade_date"]), key="medit_date")
    strategy_tag = st.text_input("전략 태그 (선택)", value=t["strategy_tag"] or "", key="medit_tag")
    thesis = st.text_area("매매 사유 (선택)", value=t["thesis"] or "", key="medit_thesis")

    col_save, col_delete, col_cancel = st.columns(3)
    if col_save.button("저장", type="primary", use_container_width=True, key="medit_save"):
        db.update_trade(
            trade_id, ticker.strip(), name.strip() or None, "KR" if market == "국내" else "US",
            "BUY" if side == "매수" else "SELL", qty, price, fee, tax,
            (fx_rate if fx_rate else None), trade_date.isoformat(),
            strategy_tag.strip() or None, thesis.strip() or None,
        )
        st.session_state.mobile_edit_trade_id = None
        st.rerun()
    if col_delete.button("삭제", use_container_width=True, key="medit_delete"):
        db.delete_trade(trade_id)
        st.session_state.mobile_edit_trade_id = None
        st.rerun()
    if col_cancel.button("취소", use_container_width=True, key="medit_cancel"):
        st.session_state.mobile_edit_trade_id = None
        st.rerun()


def render_mobile_trades():
    trades = db.get_trades()
    positions = compute_positions(trades)
    holding_count = sum(1 for p in positions.values() if p["qty"] > 0)
    this_month = dt.date.today().isoformat()[:7]
    month_trade_count = sum(1 for t in trades if t["trade_date"].startswith(this_month))
    mobile_header("매매일지", f"보유 {holding_count}종목 · 이번 달 거래 {month_trade_count}건")

    if not trades:
        st.info("아직 기록이 없습니다. 오른쪽 아래 + 버튼으로 첫 매매를 기록해보세요.")
    else:
        for t in trades[:30]:
            side_label = "매수" if t["side"] == "BUY" else "매도"
            badge_bg, badge_fg = ("#FEE2E2", "#B91C1C") if t["side"] == "BUY" else ("#DBEAFE", "#1D4ED8")
            price_unit = "$" if t["market"] == "US" else "원"
            name_label = f"{t['name']} ({t['ticker']})" if t["name"] else t["ticker"]
            tag_html = (
                f'<span class="stock-m-tag">#{html.escape(t["strategy_tag"])}</span>' if t["strategy_tag"] else ""
            )
            card_col, btn_col = st.columns([5, 1])
            with card_col:
                st.markdown(
                    f'<div class="stock-m-card">'
                    f'<div class="stock-m-card-head">'
                    f'<span class="stock-m-card-title">{html.escape(name_label)}</span>'
                    f'<span class="stock-m-badge" style="background:{badge_bg};color:{badge_fg};">{side_label}</span>'
                    f"</div>"
                    f'<span class="stock-m-card-detail">{t["trade_date"]} · {fmt_qty(t["quantity"])}주 · '
                    f'{fmt(t["price"])}{price_unit}</span>{tag_html}</div>',
                    unsafe_allow_html=True,
                )
            with btn_col:
                if st.button("", icon=":material/edit:", key=f"mobile_edit_{t['id']}", help="수정"):
                    st.session_state.mobile_edit_trade_id = t["id"]
                    st.rerun()
        if len(trades) > 30:
            st.caption(f"최근 30건만 표시 중 (전체 {len(trades)}건 - PC에서 전체 조회 가능)")

    with st.container(key="mobile_fab_wrap"):
        if st.button("＋", key="mobile_fab_btn", help="매매 기록 추가"):
            st.session_state.mobile_add_open = True
            st.rerun()

    if st.session_state.get("mobile_add_open"):
        mobile_add_trade_dialog()
    if st.session_state.get("mobile_edit_trade_id"):
        mobile_edit_trade_dialog(st.session_state.mobile_edit_trade_id)


def render_mobile_calendar():
    if "mobile_cal_year" not in st.session_state:
        _today = dt.date.today()
        st.session_state.mobile_cal_year = _today.year
        st.session_state.mobile_cal_month = _today.month

    mobile_header("캘린더", "매매 · 배당 일정을 한눈에")

    day_totals = defaultdict(lambda: {"buy": 0.0, "sell": 0.0, "div": 0.0})
    for t in db.get_trades():
        key = "buy" if t["side"] == "BUY" else "sell"
        day_totals[t["trade_date"]][key] += t["quantity"] * t["price"]
    for d in db.get_dividends():
        day_totals[d["pay_date"]]["div"] += d["amount"]

    with st.container(key="mobile_cal_nav"):
        c1, c2, c3 = st.columns([1, 3, 1])
        if c1.button("◀", key="mobile_cal_prev"):
            m, y = st.session_state.mobile_cal_month - 1, st.session_state.mobile_cal_year
            if m < 1:
                m, y = 12, y - 1
            st.session_state.mobile_cal_month, st.session_state.mobile_cal_year = m, y
            st.rerun()
        c2.markdown(
            f'<div class="stock-m-cal-title">{st.session_state.mobile_cal_year}년 '
            f'{st.session_state.mobile_cal_month}월</div>',
            unsafe_allow_html=True,
        )
        if c3.button("▶", key="mobile_cal_next"):
            m, y = st.session_state.mobile_cal_month + 1, st.session_state.mobile_cal_year
            if m > 12:
                m, y = 1, y + 1
            st.session_state.mobile_cal_month, st.session_state.mobile_cal_year = m, y
            st.rerun()

    weeks = calendar_module.Calendar(firstweekday=6).monthdatescalendar(
        st.session_state.mobile_cal_year, st.session_state.mobile_cal_month
    )
    cells = ['<div class="stock-m-cal-grid">']
    for wd in ["일", "월", "화", "수", "목", "금", "토"]:
        cells.append(f'<div class="stock-m-cal-head">{wd}</div>')
    for week in weeks:
        for day in week:
            in_month = day.month == st.session_state.mobile_cal_month
            tot = day_totals.get(day.isoformat())
            tag = ""
            if tot:
                if tot["buy"] > 0:
                    tag = '<span class="stock-m-cal-tag" style="background:#3182F6;">매수</span>'
                elif tot["sell"] > 0:
                    tag = '<span class="stock-m-cal-tag" style="background:#F04452;">매도</span>'
                elif tot["div"] > 0:
                    tag = '<span class="stock-m-cal-tag" style="background:#16A34A;">배당</span>'
            dim_class = " stock-m-cal-dim" if not in_month else ""
            cells.append(f'<div class="stock-m-cal-cell{dim_class}"><span class="stock-m-cal-day">{day.day}</span>{tag}</div>')
    cells.append("</div>")
    st.markdown("".join(cells), unsafe_allow_html=True)

    st.markdown(
        '<div class="stock-m-cal-legend">'
        '<span><i style="background:#3182F6;"></i>매수</span>'
        '<span><i style="background:#F04452;"></i>매도</span>'
        '<span><i style="background:#16A34A;"></i>배당</span>'
        "</div>",
        unsafe_allow_html=True,
    )


def render_mobile_perf():
    mobile_header("성과분석", "내 투자 성과를 한눈에")
    trades = db.get_trades()
    if not trades:
        st.info("매매 기록이 없어 분석할 내용이 없습니다.")
        return

    all_dividends = db.get_dividends()
    month_options = sorted(
        {t["trade_date"][:7] for t in trades} | {d["pay_date"][:7] for d in all_dividends},
        reverse=True,
    )
    period = st.radio("기간", ["전체", "월별"], horizontal=True, key="mobile_perf_period")
    selected_month = st.selectbox("월 선택", month_options, key="mobile_perf_month") if period == "월별" else None

    rows = compute_perf_rows(trades, all_dividends, period, selected_month)
    total_realized = sum(r["실현손익"] for r in rows)
    total_dividend = sum(r["배당금"] for r in rows)
    total_sum = sum(r["합계"] for r in rows)
    sell_count = sum(r["매도횟수"] for r in rows)

    def summary_card(label, value_html):
        return (
            f'<div class="stock-m-summary-card"><span class="stock-m-summary-label">{label}</span>'
            f'<span class="stock-m-summary-value">{value_html}</span></div>'
        )

    def signed_html(x):
        color = "#DC2626" if x >= 0 else "#2563EB"
        return f'<span style="color:{color};">{fmt_signed(round(x, 0))}원</span>'

    if period == "전체":
        positions = compute_positions(trades)
        total_unrealized = sum(r.get("평가손익", 0) for r in rows)
        wr = win_rate(positions)
        cards_html = (
            summary_card("총 실현손익", signed_html(total_realized))
            + summary_card("총 평가손익", signed_html(total_unrealized))
            + summary_card("승률", f"{wr:.0%}" if wr is not None else "-")
            + summary_card("총 거래 건수", f"{len(trades)}건")
        )
    else:
        cards_html = (
            summary_card("이 달 실현손익", signed_html(total_realized))
            + summary_card("이 달 배당금", signed_html(total_dividend))
            + summary_card("이 달 합계", signed_html(total_sum))
            + summary_card("이 달 매도 건수", f"{sell_count}건")
        )
    st.markdown(f'<div class="stock-m-summary-grid">{cards_html}</div>', unsafe_allow_html=True)

    title_suffix = f" ({selected_month})" if selected_month else ""
    st.markdown(f'<div class="stock-m-section-title">종목별 손익{title_suffix}</div>', unsafe_allow_html=True)
    if not rows:
        st.caption("해당 기간에 표시할 데이터가 없습니다.")
    else:
        for r in sorted(rows, key=lambda r: -r["_sort"]):
            detail_bits = [f'실현손익 {fmt_signed(round(r["실현손익"], 0))}원']
            if "평가손익" in r:
                detail_bits.append(f'평가손익 {fmt_signed(round(r["평가손익"], 0))}원')
            detail_bits.append(f'배당금 {fmt(round(r["배당금"], 0))}원')
            total_color = "#DC2626" if r["합계"] >= 0 else "#2563EB"
            st.markdown(
                f'<div class="stock-m-perf-row"><div>'
                f'<div class="stock-m-perf-name">{html.escape(r["종목"])} ({html.escape(r["티커"])})</div>'
                f'<div class="stock-m-perf-detail">{" · ".join(detail_bits)}</div></div>'
                f'<div class="stock-m-perf-total" style="color:{total_color};">'
                f'{fmt_signed(round(r["합계"], 0))}원</div></div>',
                unsafe_allow_html=True,
            )


def render_mobile_settings():
    mobile_header("설정", "앱 정보 및 추가 기능")
    st.markdown(
        '<div class="stock-m-card">'
        '<span class="stock-m-card-title">더 많은 기능은 PC에서</span>'
        '<span class="stock-m-card-detail">히트맵, 배당금, 목표가/손절가, 노트, AI 인사이트는 '
        "아직 폰 화면에 없어요. 같은 주소를 PC 브라우저로 열면 전체 기능을 쓸 수 있습니다."
        "</span></div>",
        unsafe_allow_html=True,
    )


def render_mobile_app():
    st.markdown(MOBILE_CSS, unsafe_allow_html=True)
    if "mobile_tab" not in st.session_state:
        st.session_state.mobile_tab = "trades"

    current_tab = st.session_state.mobile_tab
    if current_tab == "trades":
        render_mobile_trades()
    elif current_tab == "calendar":
        render_mobile_calendar()
    elif current_tab == "perf":
        render_mobile_perf()
    else:
        render_mobile_settings()

    with st.container(key="mobile_bottom_nav"):
        nav_items = [
            ("trades", "매매일지", ":material/receipt_long:"),
            ("calendar", "캘린더", ":material/calendar_month:"),
            ("perf", "성과분석", ":material/insights:"),
            ("settings", "설정", ":material/settings:"),
        ]
        nav_cols = st.columns(4)
        for col, (key, label, icon) in zip(nav_cols, nav_items):
            with col:
                if st.button(
                    label,
                    key=f"mobile_nav_{key}",
                    icon=icon,
                    type="primary" if current_tab == key else "secondary",
                    use_container_width=True,
                ):
                    st.session_state.mobile_tab = key
                    st.rerun()


def _detect_mobile():
    try:
        ua = (st.context.headers.get("User-Agent") or "").lower()
    except Exception:
        return False
    return any(k in ua for k in ("iphone", "android", "mobile", "ipad"))


if _detect_mobile():
    render_mobile_app()
    st.stop()


(
    tab_heatmap, tab_dashboard, tab_calendar, tab_trades, tab_dividends, tab_targets, tab_journal, tab_perf,
    tab_holding, tab_ai,
) = st.tabs(
    ["🔥 히트맵", "📊 대시보드", "📅 캘린더", "📝 매매일지", "💰 배당금", "🎯 목표가/손절가", "📓 노트", "📈 성과분석",
     "⏳ 보유기간", "🤖 AI 인사이트"]
)


# ---------------------------------------------------------------------------
# 히트맵 (S&P500 / KOSPI, 섹터별 트리맵, 일 1회 자동 갱신)
# ---------------------------------------------------------------------------
TM_CANVAS_W, TM_CANVAS_H = 1150, 620
TM_FALLBACK_CAP = 5_000_000_000  # 시가총액 조회 실패 시 대체값 (5B) - 타일이 거의 안 보이게 찌그러지는 것 방지


@st.cache_data(ttl=3600 * 12)
def get_heatmap_changes(cache_key: str, tickers: tuple):
    """cache_key에 오늘 날짜를 넣어서 하루 지나면 자동으로 새로 불러옴."""
    return price_data.get_daily_change_batch(list(tickers))


@st.cache_data(ttl=3600 * 12)
def get_heatmap_caps(cache_key: str, tickers: tuple):
    return price_data.get_market_caps_batch(list(tickers))


def _heatmap_color(pct):
    """상승은 빨강, 하락은 파랑 (국내 증권 관례 - 대시보드/캘린더와 동일한 색 규칙)."""
    if pct is None:
        return "#e0e0e0", "#888"
    pct = max(-4.0, min(4.0, pct))
    if pct >= 0:
        alpha = 0.15 + (pct / 4.0) * 0.85
        return f"rgba(240,68,82,{alpha:.2f})", "#ffffff" if alpha > 0.45 else "#B23140"
    alpha = 0.15 + (abs(pct) / 4.0) * 0.85
    return f"rgba(49,130,246,{alpha:.2f})", "#ffffff" if alpha > 0.45 else "#1F5FC4"


def render_treemap(title, items):
    """items: list of dicts {ticker, name, domain, sector, pct, cap}"""
    sector_rects, item_rects = treemap.layout_grouped(
        items,
        key_size=lambda i: i["cap"] or TM_FALLBACK_CAP,
        key_group=lambda i: i["sector"],
        canvas_w=TM_CANVAS_W,
        canvas_h=TM_CANVAS_H,
    )

    parts = []
    for s in sector_rects:
        if s["w"] < 1 or s["h"] < 1:
            continue
        header_h = min(20, s["h"] * 0.4)
        parts.append(
            f'<div class="tm-sector-header" style="left:{s["x"]:.1f}px;top:{s["y"]:.1f}px;'
            f'width:{s["w"]:.1f}px;height:{header_h:.1f}px;">{html.escape(s["name"])}</div>'
        )

    for item, x, y, w, h in item_rects:
        if w < 1 or h < 1:
            continue
        pct = item["pct"]
        bg, fg = _heatmap_color(pct)
        pct_txt = f"{pct:+.2f}%" if pct is not None else "N/A"
        min_side = min(w, h)
        show_ticker = min_side >= 18
        show_pct = min_side >= 26
        show_name = w >= 75 and h >= 60 and item["name"] != item["ticker"]
        show_logo = item["domain"] and w >= 52 and h >= 52

        inner = ""
        if show_logo:
            logo_size = max(16, min(28, min_side * 0.28))
            inner += (
                f'<div class="tm-logo" style="width:{logo_size:.0f}px;height:{logo_size:.0f}px;'
                f'background-image:url(https://logo.clearbit.com/{item["domain"]})"></div>'
            )
        if show_name:
            inner += f'<div class="tm-name" style="font-size:{min(11, min_side * 0.09):.1f}px">{html.escape(item["name"])}</div>'
        if show_ticker:
            inner += f'<div class="tm-ticker" style="font-size:{max(9, min(18, min_side * 0.17)):.1f}px">{html.escape(item["ticker"])}</div>'
        if show_pct:
            inner += f'<div class="tm-pct" style="font-size:{max(8, min(13, min_side * 0.13)):.1f}px">{pct_txt}</div>'

        tooltip = f'{item["name"]} ({item["ticker"]}) {pct_txt}' if item["name"] != item["ticker"] else f'{item["ticker"]} {pct_txt}'
        tooltip_esc = html.escape(tooltip)
        parts.append(
            f'<div class="tm-tile" style="left:{x:.1f}px;top:{y:.1f}px;width:{w:.1f}px;height:{h:.1f}px;" title="{tooltip_esc}">'
            f'<div class="tm-tile-box" style="background:{bg};color:{fg};">{inner}</div>'
            f'<div class="tm-tooltip">{tooltip_esc}</div>'
            f'</div>'
        )

    st.markdown(f"#### {title}")
    st.markdown(
        f'<div class="tm-canvas" style="width:{TM_CANVAS_W}px;height:{TM_CANVAS_H}px;">{"".join(parts)}</div>',
        unsafe_allow_html=True,
    )


with tab_heatmap:
    today_key = dt.date.today().isoformat()
    st.caption(f"기준일: {today_key} (전일 종가 대비 등락률 · 섹터별 트리맵, 타일 크기 = 시가총액 · 하루 한 번 자동 갱신)")

    sp_tickers = tuple(t for t, _, _ in SP500_STOCKS)
    kr_tickers = tuple(f"{code}.KS" for code, _, _, _ in KOSPI_STOCKS)

    with st.spinner("히트맵 데이터 불러오는 중... (시가총액 포함이라 첫 로딩은 다소 걸릴 수 있어요)"):
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as ex:
            fut_sp_chg = ex.submit(get_heatmap_changes, today_key, sp_tickers)
            fut_kr_chg = ex.submit(get_heatmap_changes, today_key, kr_tickers)
            fut_sp_cap = ex.submit(get_heatmap_caps, today_key, sp_tickers)
            fut_kr_cap = ex.submit(get_heatmap_caps, today_key, kr_tickers)
            sp_changes = fut_sp_chg.result()
            kr_changes = fut_kr_chg.result()
            sp_caps = fut_sp_cap.result()
            kr_caps = fut_kr_cap.result()

    sp_items = [
        {"ticker": t, "name": t, "domain": dom, "sector": sector, "pct": sp_changes.get(t), "cap": sp_caps.get(t)}
        for t, dom, sector in SP500_STOCKS
    ]
    kr_items = [
        {
            "ticker": code,
            "name": name,
            "domain": dom,
            "sector": sector,
            "pct": kr_changes.get(f"{code}.KS"),
            "cap": kr_caps.get(f"{code}.KS"),
        }
        for code, name, dom, sector in KOSPI_STOCKS
    ]

    render_treemap("🇺🇸 S&P500 (전일 대비, 섹터/시가총액별)", sp_items)
    st.markdown("<div style='height:24px'></div>", unsafe_allow_html=True)
    render_treemap("🇰🇷 KOSPI (전일 대비, 섹터/시가총액별)", kr_items)

# ---------------------------------------------------------------------------
# 대시보드
# ---------------------------------------------------------------------------
with tab_dashboard:
    trades = db.get_trades()
    if not trades:
        st.info("아직 매매 기록이 없습니다. '매매일지' 탭에서 첫 거래를 입력해보세요.")
    else:
        positions = compute_positions(trades)
        # 종목 자체 통화 기준 가격(국내는 원화, 해외는 달러) - 미실현손익 합계에서
        # 해외 종목을 오늘 환율로 환산한 값을 매수시점 환율 기준 평단가와 바로 빼면
        # 환차 변동이 섞여버리므로(위 compute_perf_rows와 동일한 문제), total_unrealized_pnl이
        # 내부적으로 avg_cost_usd + 환율을 따로 적용하도록 통화 그대로 넘긴다.
        price_lookup = {
            ticker: cached_price(ticker, pos["market"])
            for ticker, pos in positions.items()
            if pos["qty"] > 0
        }
        realized = total_realized_pnl(positions)
        unrealized = total_unrealized_pnl(positions, price_lookup, fx_rate=cached_usdkrw())
        wr = win_rate(positions)
        total_dividends = sum(d["amount"] for d in db.get_dividends())
        principal = sum(
            pos["avg_cost"] * pos["qty"] for pos in positions.values() if pos["qty"] > 0
        )

        c1, c2, c3, c4, c5 = st.columns(5)
        with c1:
            metric_card("투자금액 (원금)", f"{principal:,.0f}", "#3182F6")
        with c2:
            metric_card("평가 손익 (미실현)", f"{unrealized:,.0f}", "#F59E0B")
        with c3:
            metric_card("실현 손익", f"{realized:,.0f}", "#16A34A")
        with c4:
            metric_card("누적 배당금", f"{total_dividends:,.0f}", "#F04452")
        with c5:
            metric_card("승률 (매도 기준)", f"{wr:.0%}" if wr is not None else "-", "#8B5CF6")

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
                "평가손익": colorize_pnl(fmt_signed(pnl) if pnl is not None else "-", pnl),
                "평가손익(%)": colorize_pnl(f"{pnl_pct:+.2f}%" if pnl_pct is not None else "-", pnl_pct),
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
            render_table(df, extra_class="holdings-table", raw_html_columns=["평가손익", "평가손익(%)"])
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
    events_by_date = defaultdict(list)  # date_str -> [(text, color, amount_krw)] - amount는 정렬용

    # 매매: 같은 날짜/티커/매수·매도를 묶어서 이벤트 하나로 (하루 여러 번 자동매수 등으로 인한 난립 방지)
    trade_groups = defaultdict(lambda: {"qty": 0.0, "amount": 0.0, "name": None})
    # 날짜별 매수/매도/배당 합계 (원화는 항상 있음, 달러는 해외 거래에 fx_rate가 있을 때만)
    day_totals = defaultdict(
        lambda: {"buy_krw": 0.0, "sell_krw": 0.0, "buy_usd": 0.0, "sell_usd": 0.0, "div_krw": 0.0}
    )
    for t in cal_trades:
        key = (t["trade_date"], t["ticker"], t["side"])
        trade_groups[key]["qty"] += t["quantity"]
        trade_groups[key]["name"] = t["name"] or t["ticker"]
        side_key = "buy" if t["side"] == "BUY" else "sell"
        amount_krw = t["quantity"] * t["price"]
        trade_groups[key]["amount"] += amount_krw
        day_totals[t["trade_date"]][f"{side_key}_krw"] += amount_krw
        if t["market"] == "US" and t["fx_rate"]:
            day_totals[t["trade_date"]][f"{side_key}_usd"] += amount_krw / t["fx_rate"]
    for (cdate, cticker, cside), g in trade_groups.items():
        label = "매수" if cside == "BUY" else "매도"
        color = "#3182F6" if cside == "BUY" else "#F04452"
        events_by_date[cdate].append((f"{label} {g['name']} {fmt_qty(g['qty'])}", color, g["amount"]))

    # 배당 (같은 날짜/티커 합산)
    div_groups = defaultdict(lambda: {"amount": 0.0, "name": None})
    for d in cal_dividends:
        key = (d["pay_date"], d["ticker"])
        div_groups[key]["amount"] += d["amount"]
        div_groups[key]["name"] = d["name"] or d["ticker"]
    for (cdate, cticker), g in div_groups.items():
        events_by_date[cdate].append((f"배당 {g['name']} {fmt(g['amount'])}원", "#16A34A", g["amount"]))
        day_totals[cdate]["div_krw"] += g["amount"]

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
                        events_by_date[edate].append((f"실적발표 {ename}", "#8B5CF6", 0.0))

    if "cal_year" not in st.session_state:
        _today = dt.date.today()
        st.session_state.cal_year = _today.year
        st.session_state.cal_month = _today.month

    with st.container(key="cal_nav_row"):
        col_prev, col_title, col_next = st.columns([1, 4, 1])
        if col_prev.button("◀", help="이전달"):
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
        if col_next.button("▶", help="다음달"):
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
            evs = sorted(events_by_date.get(day.isoformat(), []), key=lambda e: -e[2])
            cell_class = "cal-dim" if not in_month else ""
            ev_html = "".join(render_cal_event(t, c) for t, c, _ in evs[:4])
            details_html = ""
            if len(evs) > 4:
                full_items = "".join(render_cal_event(t, c) for t, c, _ in evs)
                details_html = (
                    f"<details class=\"cal-details\"><summary>+{len(evs) - 4}건 더</summary>"
                    f'<div class="cal-full">'
                    f'<div class="cal-full-title">{day.month}월 {day.day}일 전체 내역 ({len(evs)}건)</div>'
                    f"{full_items}</div></details>"
                )

            dtot = day_totals.get(day.isoformat())
            tot_html = ""
            if dtot:
                lines = []
                if dtot["buy_krw"] > 0:
                    usd = f" (${dtot['buy_usd']:,.0f})" if dtot["buy_usd"] > 0 else ""
                    lines.append(f'<span class="cal-tot-buy"><strong>매수</strong> {fmt(dtot["buy_krw"])}{usd}</span>')
                if dtot["sell_krw"] > 0:
                    usd = f" (${dtot['sell_usd']:,.0f})" if dtot["sell_usd"] > 0 else ""
                    lines.append(f'<span class="cal-tot-sell"><strong>매도</strong> {fmt(dtot["sell_krw"])}{usd}</span>')
                if dtot["div_krw"] > 0:
                    lines.append(f'<span class="cal-tot-div"><strong>배당</strong> {fmt(dtot["div_krw"])}</span>')
                tot_html = "".join(f"<div>{line}</div>" for line in lines)

            _rows.append(
                f'<td class="{cell_class}">'
                f"<div class=\"cal-daynum\">{day.day}</div>{tot_html}{ev_html}{details_html}</td>"
            )
        _rows.append("</tr>")
    _rows.append("</table>")
    st.markdown("".join(_rows), unsafe_allow_html=True)

    month_prefix = f"{st.session_state.cal_year}-{st.session_state.cal_month:02d}"
    month_buy_krw = sum(v["buy_krw"] for k, v in day_totals.items() if k.startswith(month_prefix))
    month_sell_krw = sum(v["sell_krw"] for k, v in day_totals.items() if k.startswith(month_prefix))
    month_buy_usd = sum(v["buy_usd"] for k, v in day_totals.items() if k.startswith(month_prefix))
    month_sell_usd = sum(v["sell_usd"] for k, v in day_totals.items() if k.startswith(month_prefix))
    month_div_krw = sum(v["div_krw"] for k, v in day_totals.items() if k.startswith(month_prefix))

    # 이번 달 매수/매도 종목별 합계 (종목명, 수량, 금액)
    month_buy_by_ticker = defaultdict(lambda: {"qty": 0.0, "krw": 0.0, "usd": 0.0, "name": None})
    month_sell_by_ticker = defaultdict(lambda: {"qty": 0.0, "krw": 0.0, "usd": 0.0, "name": None})
    for t in cal_trades:
        if not t["trade_date"].startswith(month_prefix):
            continue
        bucket = (month_buy_by_ticker if t["side"] == "BUY" else month_sell_by_ticker)[t["ticker"]]
        bucket["qty"] += t["quantity"]
        bucket["krw"] += t["quantity"] * t["price"]
        bucket["name"] = t["name"] or t["ticker"]
        if t["market"] == "US" and t["fx_rate"]:
            bucket["usd"] += (t["quantity"] * t["price"]) / t["fx_rate"]

    def _ticker_amount_lines(bucket):
        lines = []
        for b in sorted(bucket.values(), key=lambda b: -b["krw"]):
            usd_txt = f" (${b['usd']:,.0f})" if b["usd"] else ""
            lines.append(f"{b['name']} {fmt_qty(b['qty'])}주 {fmt(b['krw'])}원{usd_txt}")
        return lines

    buy_ticker_lines = _ticker_amount_lines(month_buy_by_ticker)
    sell_ticker_lines = _ticker_amount_lines(month_sell_by_ticker)

    # 이번 달 배당금 종목별 합계
    month_div_by_ticker = defaultdict(lambda: {"krw": 0.0, "usd": 0.0, "name": None})
    for d in cal_dividends:
        if not d["pay_date"].startswith(month_prefix):
            continue
        bucket = month_div_by_ticker[d["ticker"]]
        bucket["krw"] += d["amount"]
        bucket["name"] = d["name"] or d["ticker"]
        if d["market"] == "US" and d["fx_rate"]:
            bucket["usd"] += d["amount"] / d["fx_rate"]

    div_ticker_lines = []
    for b in sorted(month_div_by_ticker.values(), key=lambda b: -b["krw"]):
        usd_txt = f" (${b['usd']:,.2f})" if b["usd"] else ""
        div_ticker_lines.append(f"{b['name']} {fmt(b['krw'])}원{usd_txt}")

    # 이번 달 판매(매도) 손익: 종목별 sell_records를 이번 달 것만 모아 손익/원가 합산
    month_sell_pnl = defaultdict(lambda: {"pnl": 0.0, "cost": 0.0, "name": None})
    for ticker, pos in cal_positions.items():
        for sr in pos["sell_records"]:
            if sr["date"].startswith(month_prefix):
                bucket = month_sell_pnl[ticker]
                bucket["pnl"] += sr["pnl"]
                bucket["cost"] += sr["cost_basis"] * sr["quantity"]
                bucket["name"] = pos["name"] or ticker
    total_sell_pnl = sum(v["pnl"] for v in month_sell_pnl.values())
    total_sell_cost = sum(v["cost"] for v in month_sell_pnl.values())
    total_sell_pct = (total_sell_pnl / total_sell_cost * 100) if total_sell_cost else None

    sell_pnl_val = f"{total_sell_pnl:+,.0f}원" if month_sell_pnl else "0원"
    if total_sell_pct is not None:
        sell_pnl_val += f" ({total_sell_pct:+.1f}%)"
    sell_pnl_lines = []
    for v in sorted(month_sell_pnl.values(), key=lambda v: -v["pnl"]):
        pct = (v["pnl"] / v["cost"] * 100) if v["cost"] else None
        pct_txt = f" ({pct:+.1f}%)" if pct is not None else ""
        sell_pnl_lines.append(f"{v['name']} {v['pnl']:+,.0f}{pct_txt}")

    mcol1, mcol2, mcol3, mcol4 = st.columns(4)
    with mcol1:
        buy_val = fmt(month_buy_krw) + (f" (${month_buy_usd:,.0f})" if month_buy_usd else "")
        metric_card("매수", buy_val, "#3182F6", sublines=buy_ticker_lines)
    with mcol2:
        sell_val = fmt(month_sell_krw) + (f" (${month_sell_usd:,.0f})" if month_sell_usd else "")
        metric_card("매도", sell_val, "#F04452", sublines=sell_ticker_lines)
    with mcol3:
        metric_card("판매 수익", sell_pnl_val, "#8B5CF6", sublines=sell_pnl_lines)
    with mcol4:
        metric_card("배당금", fmt(month_div_krw), "#16A34A", sublines=div_ticker_lines)

    st.caption(
        "🔵 매수 · 🔴 매도 · 🟢 배당 · 🟣 실적발표(해외 보유종목만, yfinance 기준). "
        "국내 종목 실적발표는 자동 조회 소스가 없어 표시되지 않습니다. '+N건 더'를 클릭하면 전체 내역이 펼쳐집니다 "
        "(더블클릭은 Streamlit 보안 정책상 지원되지 않아 클릭으로 대체했습니다)."
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
        price = col6.number_input(f"체결가 ({currency}, 1주당)", min_value=0.0, step=1.0)
        total_amount = st.number_input(
            f"또는 총 매수금액 ({currency}, 선택 - 체결가 대신 이 값을 넣으면 수량으로 나눠서 체결가를 자동 계산)",
            min_value=0.0, step=1.0, value=0.0,
        )

        col7, col8 = st.columns(2)
        fee = col7.number_input(f"수수료 ({currency})", min_value=0.0, step=0.1, value=0.0)
        tax = col8.number_input(f"거래세 (매도 시, {currency})", min_value=0.0, step=0.1, value=0.0)
        trade_date = st.date_input("거래일", value=dt.date.today())
        strategy_tag = st.text_input("전략/태그 (선택)")

        thesis = st.text_area("매매 사유/근거")
        submitted = st.form_submit_button("기록 추가")
        if submitted:
            if price <= 0 and quantity > 0 and total_amount > 0:
                price = total_amount / quantity
            if not ticker or quantity <= 0 or price <= 0:
                st.error("티커, 수량, 체결가(또는 총 매수금액)는 필수입니다.")
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

        st.markdown("**기록 수정**")
        edit_trade_id = st.number_input("수정할 기록 ID", min_value=0, step=1, value=0, key="edit_trade_id")
        if edit_trade_id > 0:
            target = next((t for t in trades if t["id"] == int(edit_trade_id)), None)
            if target is None:
                st.warning(f"ID {int(edit_trade_id)} 기록을 찾을 수 없습니다.")
            else:
                e_currency = "USD" if target["market"] == "US" else "원"
                st.caption(f"시장: {market_label(target['market'])} (수정 불가 - 시장을 바꾸려면 삭제 후 다시 등록해주세요)")
                if target["market"] == "US" and target["fx_rate"]:
                    disp_price = target["price"] / target["fx_rate"]
                    disp_fee = (target["fee"] or 0) / target["fx_rate"]
                    disp_tax = (target["tax"] or 0) / target["fx_rate"]
                else:
                    disp_price, disp_fee, disp_tax = target["price"], target["fee"] or 0, target["tax"] or 0
                with st.form(f"edit_trade_form_{int(edit_trade_id)}"):
                    e_ticker = st.text_input("티커/종목코드", value=target["ticker"])
                    e_name = st.text_input("종목명", value=target["name"] or "")
                    ecol1, ecol2, ecol3 = st.columns(3)
                    e_side = ecol1.selectbox(
                        "구분", ["BUY", "SELL"], index=0 if target["side"] == "BUY" else 1,
                        format_func=lambda s: "매수" if s == "BUY" else "매도",
                    )
                    e_quantity = ecol2.number_input("수량", min_value=0.0, value=float(target["quantity"]), step=1.0)
                    e_price = ecol3.number_input(f"체결가 ({e_currency})", min_value=0.0, value=float(disp_price), step=1.0)
                    ecol4, ecol5 = st.columns(2)
                    e_fee = ecol4.number_input(f"수수료 ({e_currency})", min_value=0.0, value=float(disp_fee), step=0.1)
                    e_tax = ecol5.number_input(f"거래세 ({e_currency})", min_value=0.0, value=float(disp_tax), step=0.1)
                    e_trade_date = st.date_input("거래일", value=dt.date.fromisoformat(target["trade_date"]))
                    e_strategy_tag = st.text_input("전략/태그", value=target["strategy_tag"] or "")
                    e_thesis = st.text_area("매매 사유/근거", value=target["thesis"] or "")
                    save_trade = st.form_submit_button("수정 저장")
                    if save_trade:
                        e_market = target["market"]
                        fx_rate = None
                        price_krw, fee_krw, tax_krw = e_price, e_fee, e_tax
                        if e_market == "US":
                            fx_rate = cached_usdkrw()
                            if fx_rate:
                                price_krw, fee_krw, tax_krw = e_price * fx_rate, e_fee * fx_rate, e_tax * fx_rate
                        db.update_trade(
                            int(edit_trade_id),
                            e_ticker.strip().upper() if e_market == "US" else e_ticker.strip(),
                            e_name.strip() or None,
                            e_market,
                            e_side,
                            e_quantity,
                            price_krw,
                            fee_krw,
                            tax_krw,
                            fx_rate,
                            e_trade_date.isoformat(),
                            e_strategy_tag.strip() or None,
                            e_thesis.strip() or None,
                        )
                        st.success(f"ID {int(edit_trade_id)} 수정 완료")
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
    d_currency = "USD" if d_market == "US" else "원"
    if d_market == "US":
        st.caption("해외 종목은 입금액/원천징수세액을 달러(USD) 기준으로 입력하세요 (원화는 자동 환산).")

    with st.form("dividend_form", clear_on_submit=True):
        d_name = st.text_input(
            "종목명 (선택, 보유 중인 티커면 자동완성)", value=suggest_name(d_ticker, d_market), key="d_name"
        )

        col4, col5, col6 = st.columns(3)
        d_amount = col4.number_input(f"입금액 (세후 실수령액, {d_currency})", min_value=0.0, step=100.0)
        d_tax = col5.number_input(f"원천징수세액 (선택, {d_currency})", min_value=0.0, step=100.0, value=0.0)
        d_date = col6.date_input("입금일", value=dt.date.today(), key="d_date")

        d_note = st.text_input("메모 (선택)")
        submitted = st.form_submit_button("배당금 추가")
        if submitted:
            if not d_ticker or d_amount <= 0:
                st.error("티커와 입금액은 필수입니다.")
            else:
                fx_rate = None
                amount_krw, tax_krw = d_amount, d_tax
                if d_market == "US":
                    fx_rate = cached_usdkrw()
                    if fx_rate:
                        amount_krw, tax_krw = d_amount * fx_rate, d_tax * fx_rate
                db.add_dividend(
                    d_ticker.strip().upper() if d_market == "US" else d_ticker.strip(),
                    d_name.strip() or None,
                    d_market,
                    d_date.isoformat(),
                    amount_krw,
                    tax_krw,
                    d_note.strip() or None,
                    fx_rate,
                )
                st.success("배당금 기록을 추가했습니다.")
                st.rerun()

    st.subheader("배당금 내역")
    dividends = db.get_dividends()
    if dividends:
        ddf = pd.DataFrame([dict(d) for d in dividends])
        display_df = ddf.copy()
        display_df["market"] = display_df["market"].map(market_label)

        def _amount_with_usd(row):
            text = fmt(row["amount"])
            if row["market"] == market_label("US") and row.get("fx_rate"):
                text += f" (${row['amount'] / row['fx_rate']:,.2f})"
            return text

        display_df["amount"] = display_df.apply(_amount_with_usd, axis=1)
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

        st.markdown("**배당 기록 수정**")
        edit_div_id = st.number_input("수정할 배당 기록 ID", min_value=0, step=1, value=0, key="edit_div_id")
        if edit_div_id > 0:
            d_target = next((d for d in dividends if d["id"] == int(edit_div_id)), None)
            if d_target is None:
                st.warning(f"ID {int(edit_div_id)} 기록을 찾을 수 없습니다.")
            else:
                ed_currency = "USD" if d_target["market"] == "US" else "원"
                st.caption(f"시장: {market_label(d_target['market'])} (수정 불가 - 시장을 바꾸려면 삭제 후 다시 등록해주세요)")
                if d_target["market"] == "US" and d_target["fx_rate"]:
                    disp_amount = d_target["amount"] / d_target["fx_rate"]
                    disp_tax = (d_target["tax"] or 0) / d_target["fx_rate"]
                else:
                    disp_amount, disp_tax = d_target["amount"], d_target["tax"] or 0
                with st.form(f"edit_dividend_form_{int(edit_div_id)}"):
                    ed_ticker = st.text_input("티커/종목코드", value=d_target["ticker"])
                    ed_name = st.text_input("종목명", value=d_target["name"] or "")
                    ecol1, ecol2, ecol3 = st.columns(3)
                    ed_amount = ecol1.number_input(
                        f"입금액 ({ed_currency})", min_value=0.0, value=float(disp_amount), step=100.0
                    )
                    ed_tax = ecol2.number_input(
                        f"원천징수세액 ({ed_currency})", min_value=0.0, value=float(disp_tax), step=100.0
                    )
                    ed_date = ecol3.date_input("입금일", value=dt.date.fromisoformat(d_target["pay_date"]))
                    ed_note = st.text_input("메모", value=d_target["note"] or "")
                    save_div = st.form_submit_button("수정 저장")
                    if save_div:
                        ed_market = d_target["market"]
                        fx_rate = None
                        amount_krw, tax_krw = ed_amount, ed_tax
                        if ed_market == "US":
                            fx_rate = cached_usdkrw()
                            if fx_rate:
                                amount_krw, tax_krw = ed_amount * fx_rate, ed_tax * fx_rate
                        db.update_dividend(
                            int(edit_div_id),
                            ed_ticker.strip().upper() if ed_market == "US" else ed_ticker.strip(),
                            ed_name.strip() or None,
                            ed_market,
                            ed_date.isoformat(),
                            amount_krw,
                            tax_krw,
                            ed_note.strip() or None,
                            fx_rate,
                        )
                        st.success(f"ID {int(edit_div_id)} 수정 완료")
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
        all_dividends = db.get_dividends()
        month_options = sorted(
            {t["trade_date"][:7] for t in trades} | {d["pay_date"][:7] for d in all_dividends},
            reverse=True,
        )

        period = st.radio("기간", ["전체", "월별"], horizontal=True, key="perf_period")
        selected_month = st.selectbox("월 선택", month_options, key="perf_month") if period == "월별" else None
        title_suffix = f" ({selected_month})" if selected_month else ""

        rows = compute_perf_rows(trades, all_dividends, period, selected_month)
        for r in rows:
            r["실현손익"] = fmt(round(r["실현손익"], 0))
            if "평가손익" in r:
                r["평가손익"] = fmt(round(r["평가손익"], 0))
            r["배당금"] = fmt(round(r["배당금"], 0))
            r["합계"] = fmt(round(r["합계"], 0))

        st.subheader(f"종목별 손익{title_suffix}" + (" (배당금 포함)" if period == "전체" else ""))
        if not rows:
            st.caption("해당 월에 실현손익/배당 기록이 없습니다.")
        else:
            df = pd.DataFrame(rows).sort_values("_sort", ascending=False).drop(columns=["_sort"])
            render_table(df, scroll=True)

        st.subheader(f"누적 실현손익 추이{title_suffix}")
        cum_data = compute_perf_cum_data(trades, period, selected_month)
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
            no_sell_msg = (
                "매도 기록이 없어 실현손익 추이를 표시할 수 없습니다."
                if period == "전체"
                else "해당 월에 매도 기록이 없어 실현손익 추이를 표시할 수 없습니다."
            )
            st.caption(no_sell_msg)

# ---------------------------------------------------------------------------
# 보유기간 (종목별 첫 매수~매도/현재까지, 장투/스윙/단타 파악용)
# ---------------------------------------------------------------------------
HOLDING_SHORT_DAYS = 30   # 이 미만이면 단타
HOLDING_LONG_DAYS = 180   # 이 이상이면 장투 (그 사이는 스윙)
HOLDING_COLORS = {"단타": "#F59E0B", "스윙": "#3182F6", "장투": "#16A34A"}


def classify_holding_days(days):
    if days < HOLDING_SHORT_DAYS:
        return "단타"
    if days < HOLDING_LONG_DAYS:
        return "스윙"
    return "장투"


with tab_holding:
    st.subheader("보유기간 분석")
    st.caption(
        f"종목별로 첫 매수일부터 완전히 청산한 날(또는 아직 보유 중이면 오늘)까지의 기간을 보여줍니다. "
        f"{HOLDING_SHORT_DAYS}일 미만은 단타, {HOLDING_SHORT_DAYS}~{HOLDING_LONG_DAYS}일은 스윙, "
        f"{HOLDING_LONG_DAYS}일 이상은 장투로 분류했어요. 한 종목을 완전히 팔았다가 나중에 다시 산 경우는 "
        "별개의 보유 구간으로 따로 표시됩니다. 수익률은 청산된 구간은 실제 매도 현금흐름 기준(환율 포함), "
        "보유중인 구간은 환율 변동을 뺀 주식 자체 평가수익률 기준이에요. 연환산 수익률은 보유기간이 다른 "
        "구간끼리도 공정하게 비교할 수 있게 1년 기준으로 환산한 값인데, 며칠 안 되는 초단타는 값이 "
        "과장되게 커질 수 있으니 참고만 하세요."
    )

    holding_trades = db.get_trades()
    if not holding_trades:
        st.info("매매 기록이 없습니다.")
    else:
        holding_positions = compute_positions(holding_trades)
        holding_price_lookup = {
            ticker: cached_price(ticker, pos["market"]) for ticker, pos in holding_positions.items()
        }
        holding_fx_rate = cached_usdkrw()
        episodes = compute_holding_episodes(
            holding_trades, dt.date.today().isoformat(),
            price_lookup=holding_price_lookup, fx_rate=holding_fx_rate,
        )
        if not episodes:
            st.info("보유 구간을 계산할 매매 기록이 없습니다.")
        else:
            for ep in episodes:
                start = dt.date.fromisoformat(ep["start_date"])
                end = dt.date.fromisoformat(ep["end_date"])
                ep["days"] = max((end - start).days, 0)
                ep["classification"] = classify_holding_days(ep["days"])
                if ep["return_pct"] is not None and ep["days"] > 0:
                    ep["annualized_pct"] = (1 + ep["return_pct"]) ** (365 / ep["days"]) - 1
                else:
                    ep["annualized_pct"] = None

            episodes.sort(key=lambda e: e["start_date"])

            total_days = sum(e["days"] for e in episodes)
            avg_days = total_days / len(episodes)
            n_short = sum(1 for e in episodes if e["classification"] == "단타")
            n_swing = sum(1 for e in episodes if e["classification"] == "스윙")
            n_long = sum(1 for e in episodes if e["classification"] == "장투")
            n = len(episodes)

            c1, c2, c3, c4 = st.columns(4)
            with c1:
                metric_card("평균 보유일수", f"{avg_days:,.0f}일", "#3182F6")
            with c2:
                metric_card("단타", f"{n_short}건 ({n_short / n:.0%})", HOLDING_COLORS["단타"])
            with c3:
                metric_card("스윙", f"{n_swing}건 ({n_swing / n:.0%})", HOLDING_COLORS["스윙"])
            with c4:
                metric_card("장투", f"{n_long}건 ({n_long / n:.0%})", HOLDING_COLORS["장투"])

            chart_rows = []
            for ep in episodes:
                label = f"{ep['name'] or ep['ticker']} ({ep['ticker']})"
                if sum(1 for e in episodes if e["ticker"] == ep["ticker"]) > 1:
                    label += f" · {ep['start_date']}"
                chart_rows.append(
                    {
                        "종목": label,
                        "시작": ep["start_date"],
                        "종료": ep["end_date"],
                        "분류": ep["classification"],
                        "보유일수": ep["days"],
                        "상태": "보유중" if ep["is_open"] else "청산완료",
                    }
                )
            chart_df = pd.DataFrame(chart_rows)

            gantt = (
                alt.Chart(chart_df)
                .mark_bar(height=14)
                .encode(
                    x=alt.X("시작:T", title=None),
                    x2=alt.X2("종료:T"),
                    y=alt.Y("종목:N", sort=list(chart_df.sort_values("시작")["종목"]), title=None),
                    color=alt.Color(
                        "분류:N",
                        scale=alt.Scale(domain=list(HOLDING_COLORS.keys()), range=list(HOLDING_COLORS.values())),
                        legend=alt.Legend(title="분류"),
                    ),
                    tooltip=[
                        alt.Tooltip("종목:N", title="종목"),
                        alt.Tooltip("시작:T", title="시작일"),
                        alt.Tooltip("종료:T", title="종료일"),
                        alt.Tooltip("보유일수:Q", title="보유일수"),
                        alt.Tooltip("분류:N", title="분류"),
                        alt.Tooltip("상태:N", title="상태"),
                    ],
                )
                .properties(height=max(24 * len(chart_df), 200))
            )
            st.altair_chart(gantt, use_container_width=True)

            st.subheader("기간 대비 수익률")
            scatter_rows = [
                {
                    "종목": f"{ep['name'] or ep['ticker']} ({ep['ticker']})",
                    "보유일수": ep["days"],
                    "수익률": ep["return_pct"] * 100,
                    "연환산수익률": ep["annualized_pct"] * 100 if ep["annualized_pct"] is not None else None,
                    "분류": ep["classification"],
                    "상태": "보유중" if ep["is_open"] else "청산완료",
                }
                for ep in episodes
                if ep["return_pct"] is not None
            ]
            if not scatter_rows:
                st.caption("수익률을 계산할 수 있는 보유 구간이 없습니다.")
            else:
                scatter_df = pd.DataFrame(scatter_rows)
                scatter = (
                    alt.Chart(scatter_df)
                    .mark_circle(size=90, opacity=0.75)
                    .encode(
                        x=alt.X("보유일수:Q", title="보유일수"),
                        y=alt.Y("수익률:Q", title="수익률 (%)", axis=alt.Axis(format=".1f")),
                        color=alt.Color(
                            "분류:N",
                            scale=alt.Scale(domain=list(HOLDING_COLORS.keys()), range=list(HOLDING_COLORS.values())),
                            legend=alt.Legend(title="분류"),
                        ),
                        shape=alt.Shape("상태:N", legend=alt.Legend(title="상태")),
                        tooltip=[
                            alt.Tooltip("종목:N", title="종목"),
                            alt.Tooltip("보유일수:Q", title="보유일수"),
                            alt.Tooltip("수익률:Q", title="수익률(%)", format="+.1f"),
                            alt.Tooltip("연환산수익률:Q", title="연환산(%)", format="+.1f"),
                            alt.Tooltip("분류:N", title="분류"),
                            alt.Tooltip("상태:N", title="상태"),
                        ],
                    )
                    .properties(height=420)
                )
                zero_line = alt.Chart(pd.DataFrame({"y": [0]})).mark_rule(color="#9CA3AF", strokeDash=[4, 4]).encode(y="y:Q")
                st.altair_chart(scatter + zero_line, use_container_width=True)

            st.subheader("전체 보유 구간")
            table_df = pd.DataFrame(
                [
                    {
                        "종목명": ep["name"] or ep["ticker"],
                        "티커": ep["ticker"],
                        "시장": market_label(ep["market"]),
                        "시작일": ep["start_date"],
                        "종료일": "보유중" if ep["is_open"] else ep["end_date"],
                        "보유일수": ep["days"],
                        "분류": ep["classification"],
                        "수익률": f"{ep['return_pct'] * 100:+.1f}%" if ep["return_pct"] is not None else "-",
                        "연환산수익률": f"{ep['annualized_pct'] * 100:+.1f}%" if ep["annualized_pct"] is not None else "-",
                    }
                    for ep in sorted(episodes, key=lambda e: e["days"], reverse=True)
                ]
            )
            render_table(table_df, scroll=True)

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
