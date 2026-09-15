"""Curated large-cap ticker lists for the 히트맵 tab, plus sector tags (for
grouping) and a ticker -> company-domain map used to pull a logo via
Clearbit's free logo API (https://logo.clearbit.com/<domain>).

Not every ticker has a mapped domain - tiles without one just render
without a logo. Sector tags are hand-assigned approximations of GICS
sectors (KOSPI names use informal Korean sector labels), not sourced from
an official classification feed - good enough for a personal at-a-glance
grouping, not for anything that needs to be authoritative.

These lists intentionally aren't the full index (500+ names) - fetching
market cap for every constituent daily is slow and not worth it for what's
meant to be an at-a-glance view. Rank/size within the tab is always computed
from live data, so this list only decides *which* large caps appear and
which sector bucket they're drawn in.
"""

# (ticker, domain, sector) - 미국 대형주 (S&P500 시가총액 상위권 위주)
SP500_STOCKS = [
    ("AAPL", "apple.com", "기술"),
    ("MSFT", "microsoft.com", "기술"),
    ("NVDA", "nvidia.com", "기술"),
    ("GOOGL", "abc.xyz", "커뮤니케이션"),
    ("AMZN", "amazon.com", "임의소비재"),
    ("META", "meta.com", "커뮤니케이션"),
    ("BRK-B", "berkshirehathaway.com", "금융"),
    ("AVGO", "broadcom.com", "기술"),
    ("TSLA", "tesla.com", "임의소비재"),
    ("LLY", "lilly.com", "의료"),
    ("JPM", "jpmorganchase.com", "금융"),
    ("V", "visa.com", "금융"),
    ("XOM", "exxonmobil.com", "에너지"),
    ("UNH", "unitedhealthgroup.com", "의료"),
    ("MA", "mastercard.com", "금융"),
    ("PG", "pg.com", "필수소비재"),
    ("JNJ", "jnj.com", "의료"),
    ("HD", "homedepot.com", "임의소비재"),
    ("COST", "costco.com", "필수소비재"),
    ("MRK", "merck.com", "의료"),
    ("ABBV", "abbvie.com", "의료"),
    ("CVX", "chevron.com", "에너지"),
    ("NFLX", "netflix.com", "커뮤니케이션"),
    ("CRM", "salesforce.com", "기술"),
    ("BAC", "bankofamerica.com", "금융"),
    ("KO", "coca-cola.com", "필수소비재"),
    ("AMD", "amd.com", "기술"),
    ("PEP", "pepsico.com", "필수소비재"),
    ("TMO", "thermofisher.com", "의료"),
    ("LIN", "linde.com", "소재"),
    ("WMT", "walmart.com", "필수소비재"),
    ("MCD", "mcdonalds.com", "임의소비재"),
    ("CSCO", "cisco.com", "기술"),
    ("ABT", "abbott.com", "의료"),
    ("ORCL", "oracle.com", "기술"),
    ("ACN", "accenture.com", "기술"),
    ("ADBE", "adobe.com", "기술"),
    ("DHR", "danaher.com", "의료"),
    ("WFC", "wellsfargo.com", "금융"),
    ("QCOM", "qualcomm.com", "기술"),
    ("TXN", "ti.com", "기술"),
    ("INTC", "intel.com", "기술"),
    ("IBM", "ibm.com", "기술"),
    ("CAT", "caterpillar.com", "산업재"),
    ("GE", "ge.com", "산업재"),
    ("NOW", "servicenow.com", "기술"),
    ("PM", "pmi.com", "필수소비재"),
    ("UBER", "uber.com", "산업재"),
    ("DIS", "disney.com", "커뮤니케이션"),
    ("VZ", "verizon.com", "커뮤니케이션"),
    ("PFE", "pfizer.com", "의료"),
]

# (ticker, name, domain-or-None, sector) - 코스피 시가총액 상위권 위주
KOSPI_STOCKS = [
    ("005930", "삼성전자", "samsung.com", "전자기술"),
    ("000660", "SK하이닉스", "skhynix.com", "전자기술"),
    ("373220", "LG에너지솔루션", "lgensol.com", "2차전지"),
    ("207940", "삼성바이오로직스", "samsungbiologics.com", "의료"),
    ("005380", "현대차", "hyundai.com", "자동차"),
    ("000270", "기아", "kia.com", "자동차"),
    ("068270", "셀트리온", "celltrion.com", "의료"),
    ("035420", "NAVER", "navercorp.com", "인터넷/게임"),
    ("005490", "POSCO홀딩스", "posco-holdings.com", "화학/소재"),
    ("105560", "KB금융", "kbfg.com", "금융"),
    ("055550", "신한지주", "shinhangroup.com", "금융"),
    ("051910", "LG화학", "lgchem.com", "화학/소재"),
    ("006400", "삼성SDI", "samsungsdi.com", "2차전지"),
    ("096770", "SK이노베이션", "skinnovation.com", "2차전지"),
    ("012330", "현대모비스", "mobis.co.kr", "자동차"),
    ("028260", "삼성물산", "samsungcnt.com", "유통/상사"),
    ("086790", "하나금융지주", "hanafn.com", "금융"),
    ("035720", "카카오", "kakaocorp.com", "인터넷/게임"),
    ("066570", "LG전자", "lge.com", "전자기술"),
    ("010130", "고려아연", None, "화학/소재"),
    ("034730", "SK", "sk.com", "유통/상사"),
    ("015760", "한국전력", "kepco.co.kr", "유틸리티"),
    ("032830", "삼성생명", "samsunglife.com", "금융"),
    ("018260", "삼성에스디에스", "samsungsds.com", "전자기술"),
    ("010950", "S-Oil", "s-oil.com", "에너지"),
    ("011200", "HMM", "hmm21.com", "유틸리티"),
    ("009150", "삼성전기", "samsungsem.com", "전자기술"),
    ("000810", "삼성화재", "samsungfire.com", "금융"),
    ("024110", "기업은행", "ibk.co.kr", "금융"),
    ("316140", "우리금융지주", "woorifg.com", "금융"),
    ("259960", "크래프톤", "krafton.com", "인터넷/게임"),
    ("352820", "하이브", "hybecorp.com", "인터넷/게임"),
    ("090430", "아모레퍼시픽", "apgroup.com", "필수소비재"),
]
