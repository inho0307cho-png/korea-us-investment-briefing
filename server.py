import json
import os
import math
import smtplib
import time
import urllib.parse
import urllib.request
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer


APP_BASE_URL = os.environ.get("APP_BASE_URL", "https://web-production-ca090.up.railway.app/")
SEOUL_TZ = timezone(timedelta(hours=9))
YAHOO_CACHE = {}
YAHOO_CACHE_TTL_SECONDS = int(os.environ.get("YAHOO_CACHE_TTL_SECONDS", "300"))
MARKET_DATA_WORKERS = int(os.environ.get("MARKET_DATA_WORKERS", "12"))

SYMBOLS = {
    "SPX": "^GSPC",
    "IXIC": "^IXIC",
    "KOSPI": "^KS11",
}

CHART_SYMBOLS = {
    **SYMBOLS,
}

KR_STOCK_POOL = [
    ("005930", "005930.KS", "Samsung Electronics"),
    ("000660", "000660.KS", "SK hynix"),
    ("373220", "373220.KS", "LG Energy Solution"),
    ("207940", "207940.KS", "Samsung Biologics"),
    ("005380", "005380.KS", "Hyundai Motor"),
    ("000270", "000270.KS", "Kia"),
    ("068270", "068270.KS", "Celltrion"),
    ("105560", "105560.KS", "KB Financial Group"),
    ("055550", "055550.KS", "Shinhan Financial Group"),
    ("035420", "035420.KS", "NAVER"),
    ("012450", "012450.KS", "Hanwha Aerospace"),
    ("329180", "329180.KS", "HD Hyundai Heavy Industries"),
    ("005490", "005490.KS", "POSCO Holdings"),
    ("066570", "066570.KS", "LG Electronics"),
    ("051910", "051910.KS", "LG Chem"),
    ("006400", "006400.KS", "Samsung SDI"),
    ("028260", "028260.KS", "Samsung C&T"),
    ("032830", "032830.KS", "Samsung Life Insurance"),
    ("086790", "086790.KS", "Hana Financial Group"),
    ("138040", "138040.KS", "Meritz Financial Group"),
    ("015760", "015760.KS", "Korea Electric Power"),
    ("034020", "034020.KS", "Doosan Enerbility"),
    ("009540", "009540.KS", "HD Korea Shipbuilding & Offshore Engineering"),
    ("011200", "011200.KS", "HMM"),
    ("042660", "042660.KS", "Hanwha Ocean"),
    ("267260", "267260.KS", "HD Hyundai Electric"),
    ("010130", "010130.KS", "Korea Zinc"),
    ("259960", "259960.KS", "Krafton"),
    ("035720", "035720.KS", "Kakao"),
    ("003550", "003550.KS", "LG"),
]

US_STOCK_POOL = [
    ("NVDA", "NVDA", "NVIDIA"),
    ("MSFT", "MSFT", "Microsoft"),
    ("AAPL", "AAPL", "Apple"),
    ("GOOGL", "GOOGL", "Alphabet"),
    ("AMZN", "AMZN", "Amazon"),
    ("META", "META", "Meta Platforms"),
    ("AVGO", "AVGO", "Broadcom"),
    ("TSLA", "TSLA", "Tesla"),
    ("BRK-B", "BRK-B", "Berkshire Hathaway"),
    ("LLY", "LLY", "Eli Lilly"),
    ("JPM", "JPM", "JPMorgan Chase"),
    ("V", "V", "Visa"),
    ("MA", "MA", "Mastercard"),
    ("UNH", "UNH", "UnitedHealth Group"),
    ("XOM", "XOM", "Exxon Mobil"),
    ("COST", "COST", "Costco"),
    ("WMT", "WMT", "Walmart"),
    ("HD", "HD", "Home Depot"),
    ("PG", "PG", "Procter & Gamble"),
    ("JNJ", "JNJ", "Johnson & Johnson"),
    ("ORCL", "ORCL", "Oracle"),
    ("NFLX", "NFLX", "Netflix"),
    ("BAC", "BAC", "Bank of America"),
    ("KO", "KO", "Coca-Cola"),
    ("PLTR", "PLTR", "Palantir"),
    ("AMD", "AMD", "AMD"),
    ("CRM", "CRM", "Salesforce"),
    ("ADBE", "ADBE", "Adobe"),
    ("CSCO", "CSCO", "Cisco"),
    ("MCD", "MCD", "McDonald's"),
]

KR_ETF_POOL = [
    ("KODEX200", "069500.KS", "KODEX 200"),
    ("TIGER200", "102110.KS", "TIGER 200"),
    ("KBSTAR200", "148020.KS", "KBSTAR 200"),
    ("ARIRANG200", "152100.KS", "ARIRANG 200"),
    ("KODEXKOSDAQ150", "229200.KS", "KODEX KOSDAQ150"),
    ("TIGERKOSDAQ150", "232080.KS", "TIGER KOSDAQ150"),
    ("KODEXLEVERAGE", "122630.KS", "KODEX Leverage"),
    ("KODEXINVERSE", "114800.KS", "KODEX Inverse"),
    ("KODEX200TR", "278530.KS", "KODEX 200TR"),
    ("TIGERTOP10", "292150.KS", "TIGER TOP10"),
    ("TIGERKR10", "133690.KS", "TIGER US Nasdaq 100"),
    ("KODEXUSSP500", "379800.KS", "KODEX US S&P500TR"),
    ("TIGERUSSP500", "360750.KS", "TIGER US S&P500"),
    ("ACEUSSP500", "360200.KS", "ACE US S&P500"),
    ("KODEXUSNASDAQ100", "379810.KS", "KODEX US Nasdaq 100TR"),
    ("TIGERUSNASDAQ100", "133690.KS", "TIGER US Nasdaq 100"),
    ("ACEUSNASDAQ100", "367380.KS", "ACE US Nasdaq 100"),
    ("TIGERUSPHLXSOLACTIVE", "381180.KS", "TIGER US PHLX Semiconductor Nasdaq"),
    ("KODEXUSSEMICONDUCTOR", "390390.KS", "KODEX US Semiconductor MV"),
    ("KODEX2NDARYBATTERY", "305720.KS", "KODEX Secondary Battery Industry"),
    ("TIGER2NDARYBATTERY", "305540.KS", "TIGER Secondary Battery Theme"),
    ("KODEXBANK", "091170.KS", "KODEX Banks"),
    ("KODEXAUTOS", "091180.KS", "KODEX Autos"),
    ("KODEXSEMICON", "091160.KS", "KODEX Semiconductors"),
    ("TIGERSEMICON", "091230.KS", "TIGER Semiconductors"),
    ("TIGERDIVIDEND", "161510.KS", "TIGER Dividend Growth"),
    ("KODEXDIVIDEND", "279530.KS", "KODEX Dividend Growth"),
    ("TIGERREIT", "329200.KS", "TIGER Real Estate Infra"),
    ("KODEXGOLD", "132030.KS", "KODEX Gold Futures"),
    ("KODEXDOLLAR", "261240.KS", "KODEX USD Futures"),
]

US_ETF_POOL = [
    ("SPY", "SPY", "SPDR S&P 500 ETF"),
    ("IVV", "IVV", "iShares Core S&P 500 ETF"),
    ("VOO", "VOO", "Vanguard S&P 500 ETF"),
    ("VTI", "VTI", "Vanguard Total Stock Market ETF"),
    ("QQQ", "QQQ", "Invesco QQQ Trust"),
    ("QQQM", "QQQM", "Invesco NASDAQ 100 ETF"),
    ("IWM", "IWM", "iShares Russell 2000 ETF"),
    ("DIA", "DIA", "SPDR Dow Jones Industrial Average ETF"),
    ("SCHD", "SCHD", "Schwab US Dividend Equity ETF"),
    ("VIG", "VIG", "Vanguard Dividend Appreciation ETF"),
    ("VYM", "VYM", "Vanguard High Dividend Yield ETF"),
    ("XLK", "XLK", "Technology Select Sector SPDR Fund"),
    ("SMH", "SMH", "VanEck Semiconductor ETF"),
    ("SOXX", "SOXX", "iShares Semiconductor ETF"),
    ("XLF", "XLF", "Financial Select Sector SPDR Fund"),
    ("XLE", "XLE", "Energy Select Sector SPDR Fund"),
    ("XLV", "XLV", "Health Care Select Sector SPDR Fund"),
    ("XLY", "XLY", "Consumer Discretionary Select Sector SPDR Fund"),
    ("XLP", "XLP", "Consumer Staples Select Sector SPDR Fund"),
    ("XLI", "XLI", "Industrial Select Sector SPDR Fund"),
    ("ARKK", "ARKK", "ARK Innovation ETF"),
    ("IBIT", "IBIT", "iShares Bitcoin Trust ETF"),
    ("GLD", "GLD", "SPDR Gold Shares"),
    ("TLT", "TLT", "iShares 20+ Year Treasury Bond ETF"),
    ("IEF", "IEF", "iShares 7-10 Year Treasury Bond ETF"),
    ("HYG", "HYG", "iShares iBoxx High Yield Corporate Bond ETF"),
    ("LQD", "LQD", "iShares iBoxx Investment Grade Corporate Bond ETF"),
    ("EFA", "EFA", "iShares MSCI EAFE ETF"),
    ("EEM", "EEM", "iShares MSCI Emerging Markets ETF"),
    ("VEA", "VEA", "Vanguard FTSE Developed Markets ETF"),
]

POOLS = [
    ("KR", "stock", KR_STOCK_POOL),
    ("US", "stock", US_STOCK_POOL),
    ("KR", "etf", KR_ETF_POOL),
    ("US", "etf", US_ETF_POOL),
]

QUOTE_SYMBOLS = {
    ticker: yahoo_symbol
    for _, _, pool in POOLS
    for ticker, yahoo_symbol, _ in pool
}

INSTRUMENTS = {
    ticker: {"name": name, "market": market, "assetType": asset_type}
    for market, asset_type, pool in POOLS
    for ticker, _, name in pool
}

GROUPS = [
    ("kr_stock", "한국 주식 TOP 5", "KR", "stock", 5),
    ("us_stock", "미국 주식 TOP 5", "US", "stock", 5),
    ("kr_etf", "한국 ETF TOP 5", "KR", "etf", 5),
    ("us_etf", "미국 ETF TOP 5", "US", "etf", 5),
]
CHART_SYMBOLS.update(QUOTE_SYMBOLS)

PERIOD_CONFIG = {
    "daily": {"range": "3mo", "interval": "1d", "limit": 63},
    "weekly": {"range": "1y", "interval": "1wk", "limit": 53},
    "monthly": {"range": "3y", "interval": "1mo", "limit": 36},
}


def fetch_yahoo_chart(symbol, range_value="1y", interval="1wk"):
    cache_key = (symbol, range_value, interval)
    cached = YAHOO_CACHE.get(cache_key)
    now = time.time()
    if cached and now - cached["time"] < YAHOO_CACHE_TTL_SECONDS:
        return cached["data"]

    encoded_symbol = urllib.parse.quote(symbol, safe="")
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{encoded_symbol}?range={range_value}&interval={interval}"
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 investment-briefing-local-preview",
            "Accept": "application/json",
        },
    )
    with urllib.request.urlopen(request, timeout=10) as response:
        payload = json.loads(response.read().decode("utf-8"))

    result = payload["chart"]["result"][0]
    meta = result.get("meta", {})
    timestamps = result.get("timestamp", [])
    quote = result.get("indicators", {}).get("quote", [{}])[0]
    closes = quote.get("close", [])
    previous = next((value for value in reversed(closes[:-1]) if value is not None), None)
    current = meta.get("regularMarketPrice") or next((value for value in reversed(closes) if value is not None), None)
    change_percent = 0
    if current is not None and previous:
        change_percent = ((current - previous) / previous) * 100

    candles = []
    for index, timestamp in enumerate(timestamps):
        open_value = quote.get("open", [None] * len(timestamps))[index]
        high_value = quote.get("high", [None] * len(timestamps))[index]
        low_value = quote.get("low", [None] * len(timestamps))[index]
        close_value = quote.get("close", [None] * len(timestamps))[index]
        volume_value = quote.get("volume", [0] * len(timestamps))[index] or 0
        if None in (open_value, high_value, low_value, close_value):
            continue
        candles.append(
            {
                "date": time.strftime("%Y-%m-%d", time.gmtime(timestamp)),
                "open": open_value,
                "high": high_value,
                "low": low_value,
                "close": close_value,
                "volume": volume_value,
            }
        )

    result_data = {
        "value": current,
        "change": change_percent,
        "candles": candles,
    }
    YAHOO_CACHE[cache_key] = {"time": now, "data": result_data}
    return result_data


def fetch_index(symbol):
    weekly = fetch_yahoo_chart(symbol, "1y", "1wk")
    daily = fetch_yahoo_chart(symbol, "5d", "1d")
    if len(daily["candles"]) >= 2:
        current = daily["candles"][-1]["close"]
        previous = daily["candles"][-2]["close"]
        weekly["value"] = current
        weekly["change"] = ((current - previous) / previous) * 100 if previous else 0
    return weekly


def fetch_chart(ticker, period):
    if ticker not in CHART_SYMBOLS:
        raise ValueError(f"Unsupported ticker: {ticker}")
    config = PERIOD_CONFIG.get(period)
    if not config:
        raise ValueError(f"Unsupported period: {period}")
    chart = fetch_yahoo_chart(CHART_SYMBOLS[ticker], config["range"], config["interval"])
    chart["candles"] = chart["candles"][-config["limit"] :]
    return chart


def fetch_quote(symbol):
    daily = fetch_yahoo_chart(symbol, "5d", "1d")
    candles = daily["candles"]
    if not candles:
        raise ValueError(f"No quote data for {symbol}")
    current = candles[-1]["close"]
    previous = candles[-2]["close"] if len(candles) >= 2 else candles[-1]["open"]
    return {
        "price": current,
        "change": ((current - previous) / previous) * 100 if previous else 0,
        "asOf": candles[-1]["date"],
    }


def clamp(value, low=0, high=100):
    return max(low, min(high, value))


def scale(value, low, high):
    if value is None or math.isnan(value):
        return 50
    if high == low:
        return 50
    return clamp(((value - low) / (high - low)) * 100)


def max_drawdown(closes):
    peak = closes[0]
    worst = 0
    for close in closes:
        peak = max(peak, close)
        if peak:
            worst = min(worst, (close - peak) / peak)
    return abs(worst) * 100


def pct_change(closes, periods):
    if len(closes) <= periods or closes[-periods - 1] == 0:
        return 0
    return ((closes[-1] - closes[-periods - 1]) / closes[-periods - 1]) * 100


def average(values):
    clean = [value for value in values if value is not None]
    return sum(clean) / len(clean) if clean else 0


def trend_consistency(closes):
    if len(closes) < 30:
        return 50
    recent = closes[-60:] if len(closes) >= 60 else closes
    up_days = sum(1 for index in range(1, len(recent)) if recent[index] > recent[index - 1])
    return (up_days / max(1, len(recent) - 1)) * 100


def analysis_grade(score):
    if score >= 75:
        return "강함"
    if score >= 60:
        return "양호"
    if score >= 45:
        return "중립"
    return "약함"


def format_number(value):
    if value is None:
        return "-"
    return f"{value:,.0f}"


def format_price(ticker, value):
    if value is None:
        return "-"
    prefix = "$" if INSTRUMENTS.get(ticker, {}).get("market") == "US" else ""
    suffix = "원" if INSTRUMENTS.get(ticker, {}).get("market") == "KR" else ""
    return f"{prefix}{format_number(value)}{suffix}"


def format_percent(value):
    if value is None:
        return "-"
    sign = "+" if value > 0 else ""
    return f"{sign}{value:.2f}%"


def html_escape(value):
    return (
        str(value)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def reason_sentence(item):
    factors = item.get("analysis", {}).get("factors", {})
    parts = []
    if factors.get("momentum") is not None:
        parts.append(f"모멘텀 {factors['momentum']}점")
    if factors.get("profitability") is not None:
        parts.append(f"수익성 {factors['profitability']}점")
    if factors.get("trendGrowth") is not None:
        parts.append(f"추세 품질 {factors['trendGrowth']}점")
    if factors.get("liquidity") is not None:
        parts.append(f"유동성 {factors['liquidity']}점")
    if factors.get("return3m") is not None:
        parts.append(f"3개월 수익률 {format_percent(factors['return3m'])}")
    if factors.get("maxDrawdown") is not None:
        parts.append(f"최대낙폭 {factors['maxDrawdown']:.1f}%")
    return " / ".join(parts) if parts else "실제 OHLCV 데이터를 기준으로 점수를 산정했습니다."


def analyze_ticker(ticker):
    yahoo_symbol = CHART_SYMBOLS[ticker]
    daily = fetch_yahoo_chart(yahoo_symbol, "1y", "1d")
    candles = daily["candles"]
    if len(candles) < 30:
        raise ValueError(f"Not enough analysis data for {ticker}")

    closes = [candle["close"] for candle in candles]
    volumes = [candle["volume"] for candle in candles]
    current = closes[-1]
    ma20 = average(closes[-20:])
    ma60 = average(closes[-60:]) if len(closes) >= 60 else ma20
    high_52w = max(candle["high"] for candle in candles)
    low_52w = min(candle["low"] for candle in candles)

    return_1w = pct_change(closes, min(5, len(closes) - 1))
    return_1m = pct_change(closes, min(21, len(closes) - 1))
    return_3m = pct_change(closes, min(63, len(closes) - 1))
    return_6m = pct_change(closes, min(126, len(closes) - 1))
    day_returns = [
        ((closes[index] - closes[index - 1]) / closes[index - 1]) * 100
        for index in range(1, len(closes))
        if closes[index - 1]
    ]
    volatility = math.sqrt(252) * (sum((value - average(day_returns)) ** 2 for value in day_returns) / max(1, len(day_returns) - 1)) ** 0.5
    drawdown = max_drawdown(closes)
    volume_ratio = average(volumes[-20:]) / average(volumes[-120:]) if len(volumes) >= 120 and average(volumes[-120:]) else 1
    high_position = ((current - low_52w) / (high_52w - low_52w)) * 100 if high_52w != low_52w else 50
    avg_daily_return = average(day_returns)
    positive_day_ratio = sum(1 for value in day_returns[-60:] if value > 0) / max(1, len(day_returns[-60:])) * 100
    risk_adjusted_return = return_3m / volatility if volatility else 0

    momentum_score = average(
        [
            scale(return_1m, -8, 12),
            scale(return_3m, -15, 25),
            scale(return_6m, -25, 40),
            scale((current / ma20 - 1) * 100, -8, 8),
            scale((ma20 / ma60 - 1) * 100, -8, 8),
        ]
    )
    profitability_score = average(
        [
            scale(return_1m, -6, 14),
            scale(return_3m, -10, 30),
            scale(return_6m, -15, 45),
            scale(avg_daily_return, -0.25, 0.35),
            scale(risk_adjusted_return, -0.25, 0.75),
            positive_day_ratio,
        ]
    )
    trend_quality_score = average(
        [
            scale(return_3m, -10, 25),
            scale(return_6m, -15, 35),
            scale((ma20 / ma60 - 1) * 100, -8, 8),
            trend_consistency(closes),
        ]
    )
    valuation_proxy_score = average([scale(-return_6m, -45, 15), scale(100 - high_position, 0, 100)])
    quality_risk_score = average(
        [
            100 - scale(volatility, 10, 55),
            100 - scale(drawdown, 5, 45),
            trend_consistency(closes),
        ]
    )
    liquidity_score = average([scale(average(volumes[-20:]), 100000, 10000000), scale(volume_ratio, 0.6, 1.8)])
    sentiment_score = average([scale(return_1m, -8, 12), scale(volume_ratio, 0.7, 1.7)])
    risk_penalty_score = average([100 - scale(drawdown, 5, 45), 100 - scale(volatility, 10, 55)])
    expense_tracking_proxy_score = average([100 - scale(volatility, 8, 45), 100 - scale(drawdown, 4, 35)])
    fund_flow_proxy_score = average([scale(volume_ratio, 0.7, 1.8), scale(return_1m, -8, 12)])

    stock_score = (
        profitability_score * 0.30
        + momentum_score * 0.18
        + trend_quality_score * 0.20
        + valuation_proxy_score * 0.07
        + quality_risk_score * 0.12
        + liquidity_score * 0.10
        + risk_penalty_score * 0.03
    )
    etf_score = (
        momentum_score * 0.25
        + fund_flow_proxy_score * 0.20
        + liquidity_score * 0.15
        + expense_tracking_proxy_score * 0.10
        + trend_quality_score * 0.20
        + risk_penalty_score * 0.10
    )

    return {
        "stockScore": round(stock_score),
        "etfScore": round(etf_score),
        "factors": {
            "momentum": round(momentum_score),
            "profitability": round(profitability_score),
            "trendGrowth": round(trend_quality_score),
            "valuationProxy": round(valuation_proxy_score),
            "qualityRisk": round(quality_risk_score),
            "liquidity": round(liquidity_score),
            "sentiment": round(sentiment_score),
            "risk": round(risk_penalty_score),
            "expenseTrackingProxy": round(expense_tracking_proxy_score),
            "fundFlowProxy": round(fund_flow_proxy_score),
            "trendConsistency": round(trend_consistency(closes)),
            "highPosition": round(high_position, 2),
            "return1w": round(return_1w, 2),
            "return1m": round(return_1m, 2),
            "return3m": round(return_3m, 2),
            "return6m": round(return_6m, 2),
            "volatility": round(volatility, 2),
            "maxDrawdown": round(drawdown, 2),
            "volumeRatio": round(volume_ratio, 2),
            "positiveDayRatio": round(positive_day_ratio, 2),
            "riskAdjustedReturn": round(risk_adjusted_return, 2),
        },
        "reasonScores": {
            "stock": [
                {"label": "수익성", "score": round(profitability_score), "grade": analysis_grade(profitability_score)},
                {"label": "모멘텀", "score": round(momentum_score), "grade": analysis_grade(momentum_score)},
                {"label": "성장/추세 품질", "score": round(trend_quality_score), "grade": analysis_grade(trend_quality_score)},
                {"label": "밸류 부담", "score": round(valuation_proxy_score), "grade": analysis_grade(valuation_proxy_score)},
                {"label": "품질/리스크", "score": round(quality_risk_score), "grade": analysis_grade(quality_risk_score)},
                {"label": "수급/거래", "score": round(liquidity_score), "grade": analysis_grade(liquidity_score)},
            ],
            "etf": [
                {"label": "기초지수 추세", "score": round(trend_quality_score), "grade": analysis_grade(trend_quality_score)},
                {"label": "자금흐름/수급", "score": round(fund_flow_proxy_score), "grade": analysis_grade(fund_flow_proxy_score)},
                {"label": "유동성", "score": round(liquidity_score), "grade": analysis_grade(liquidity_score)},
                {"label": "비용/추적 안정성", "score": round(expense_tracking_proxy_score), "grade": analysis_grade(expense_tracking_proxy_score)},
                {"label": "변동성 리스크", "score": round(risk_penalty_score), "grade": analysis_grade(risk_penalty_score)},
            ],
        },
        "asOf": candles[-1]["date"],
        "source": "Yahoo Finance OHLCV",
    }


def load_instrument_item(ticker, meta):
    quote = fetch_quote(QUOTE_SYMBOLS[ticker])
    analysis = analyze_ticker(ticker)
    score = analysis["etfScore"] if meta["assetType"] == "etf" else analysis["stockScore"]
    return {
        "ticker": ticker,
        "name": meta["name"],
        "market": meta["market"],
        "assetType": meta["assetType"],
        "quote": quote,
        "analysis": analysis,
        "score": score,
        "reason": reason_sentence({"analysis": analysis}),
    }


def collect_parallel(values, worker):
    results = {}
    errors = {}
    with ThreadPoolExecutor(max_workers=MARKET_DATA_WORKERS) as executor:
        future_map = {executor.submit(worker, key, value): key for key, value in values.items()}
        for future in as_completed(future_map):
            key = future_map[future]
            try:
                results[key] = future.result()
            except Exception as error:
                errors[key] = str(error)
    return results, errors


def pool_size_for(market, asset_type):
    return sum(1 for meta in INSTRUMENTS.values() if meta["market"] == market and meta["assetType"] == asset_type)


def build_report_data():
    indices = {key: fetch_index(symbol) for key, symbol in SYMBOLS.items()}
    item_map, quote_errors = collect_parallel(INSTRUMENTS, load_instrument_item)
    items = list(item_map.values())

    ranked_groups = {}
    for key, label, market, asset_type, limit in GROUPS:
        ranked_groups[key] = {
            "label": label,
            "poolSize": pool_size_for(market, asset_type),
            "limit": limit,
            "items": sorted(
                [item for item in items if item["market"] == market and item["assetType"] == asset_type],
                key=lambda item: (
                    item["score"],
                    item["analysis"]["factors"].get("return3m", 0),
                    -item["analysis"]["factors"].get("maxDrawdown", 0),
                ),
                reverse=True,
            )[:limit],
        }

    return {
        "asOf": datetime.now(SEOUL_TZ).strftime("%Y-%m-%d %H:%M:%S"),
        "indices": indices,
        "groups": ranked_groups,
        "errors": quote_errors,
    }


def build_html_email(report):
    index_rows = []
    for key, label in [("SPX", "S&P 500"), ("IXIC", "NASDAQ"), ("KOSPI", "KOSPI")]:
        item = report["indices"].get(key, {})
        candles = item.get("candles", [])
        high = max((candle["high"] for candle in candles), default=None)
        low = min((candle["low"] for candle in candles), default=None)
        index_rows.append(
            f"""
            <tr>
              <td>{label}</td>
              <td style="text-align:right">{format_number(item.get("value"))}</td>
              <td style="text-align:right">{format_percent(item.get("change"))}</td>
              <td style="text-align:right">{format_number(high)}</td>
              <td style="text-align:right">{format_number(low)}</td>
            </tr>
            """
        )

    group_sections = []
    for group in report["groups"].values():
        rows = []
        for rank, item in enumerate(group["items"], 1):
            rows.append(
                f"""
                <tr>
                  <td style="text-align:center;font-weight:700">{rank}</td>
                  <td><b>{html_escape(item["name"])}</b><br><span style="color:#64748b">{item["ticker"]}</span></td>
                  <td style="text-align:right">{format_price(item["ticker"], item["quote"].get("price"))}</td>
                  <td style="text-align:right">{format_percent(item["quote"].get("change"))}</td>
                  <td>{html_escape(item["reason"])}</td>
                  <td style="text-align:right;font-weight:700">{item["score"]}</td>
                </tr>
                """
            )
        group_sections.append(
            f"""
            <h3 style="margin:18px 0 8px;color:#0f766e">{html_escape(group["label"])}</h3>
            <table width="100%" cellpadding="8" cellspacing="0" style="border-collapse:collapse;border:1px solid #dbe3ea">
              <thead>
                <tr style="background:#eef7f5;color:#0f766e">
                  <th align="center">순위</th>
                  <th align="left">종목</th>
                  <th align="right">현재가</th>
                  <th align="right">변동</th>
                  <th align="left">선정 근거</th>
                  <th align="right">점수</th>
                </tr>
              </thead>
              <tbody>{''.join(rows)}</tbody>
            </table>
            """
        )

    return f"""
    <!doctype html>
    <html lang="ko">
      <body style="font-family:Arial,'Malgun Gothic',sans-serif;color:#17202a;line-height:1.55">
        <h1 style="color:#0f766e;margin-bottom:4px">오늘의 투자 브리핑 - Korea &amp; US Investment Briefing</h1>
        <p style="margin-top:0;color:#64748b">작성 시각: {report["asOf"]} (Asia/Seoul)</p>
        <p><a href="{APP_BASE_URL}">{APP_BASE_URL}</a></p>

        <h2 style="color:#0f766e">시장 지표</h2>
        <table width="100%" cellpadding="8" cellspacing="0" style="border-collapse:collapse;border:1px solid #dbe3ea">
          <thead>
            <tr style="background:#0f766e;color:#ffffff">
              <th align="left">지표</th>
              <th align="right">현재가</th>
              <th align="right">등락률</th>
              <th align="right">1년 최고</th>
              <th align="right">1년 최저</th>
            </tr>
          </thead>
          <tbody>{''.join(index_rows)}</tbody>
        </table>

        <h2 style="color:#0f766e;margin-top:22px">오늘의 TOP Picks 및 선정 결과</h2>
        {''.join(group_sections)}

        <h2 style="color:#0f766e;margin-top:22px">상세 캔들차트</h2>
        <p>
          이메일 본문에서는 보안 및 호환성 문제로 캔들차트를 직접 실행하지 않습니다.
          상세 캔들차트는 대시보드에서 바로 확인해 주세요.
        </p>
        <p><a href="{APP_BASE_URL}" style="display:inline-block;background:#0f766e;color:#fff;padding:10px 14px;text-decoration:none;border-radius:6px">대시보드에서 차트 보기</a></p>

        <p style="margin-top:24px;color:#64748b;font-size:12px">
          본 메일은 정보 제공 목적이며 투자 권유나 수익 보장을 의미하지 않습니다.
          투자 결정과 그 결과에 대한 책임은 투자자 본인에게 있으며, 시장 데이터는 지연되거나 오류가 발생할 수 있습니다.
        </p>
      </body>
    </html>
    """


def send_email_message(subject, html_body):
    recipients = [item.strip() for item in os.environ.get("BRIEFING_RECIPIENTS", "").split(",") if item.strip()]
    if not recipients:
        raise ValueError("BRIEFING_RECIPIENTS is not configured")

    provider = os.environ.get("EMAIL_PROVIDER", "smtp").lower()
    sender = os.environ.get("EMAIL_FROM") or os.environ.get("SMTP_USERNAME")
    if not sender:
        raise ValueError("EMAIL_FROM or SMTP_USERNAME is not configured")

    if provider == "resend":
        api_key = os.environ.get("RESEND_API_KEY") or os.environ.get("EMAIL_PROVIDER_API_KEY")
        if not api_key:
            raise ValueError("RESEND_API_KEY is not configured")
        payload = json.dumps(
            {
                "from": sender,
                "to": recipients,
                "subject": subject,
                "html": html_body,
            }
        ).encode("utf-8")
        request = urllib.request.Request(
            "https://api.resend.com/emails",
            data=payload,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=20) as response:
            return response.read().decode("utf-8")

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = sender
    message["To"] = ", ".join(recipients)
    message.set_content("HTML 메일을 지원하는 클라이언트에서 오늘의 투자 브리핑을 확인해 주세요.")
    message.add_alternative(html_body, subtype="html")

    host = os.environ.get("SMTP_HOST")
    username = os.environ.get("SMTP_USERNAME")
    password = os.environ.get("SMTP_PASSWORD")
    port = int(os.environ.get("SMTP_PORT", "587"))
    if not host or not username or not password:
        raise ValueError("SMTP_HOST, SMTP_USERNAME, SMTP_PASSWORD must be configured")

    if port == 465:
        with smtplib.SMTP_SSL(host, port, timeout=20) as smtp:
            smtp.login(username, password)
            smtp.send_message(message)
    else:
        with smtplib.SMTP(host, port, timeout=20) as smtp:
            smtp.starttls()
            smtp.login(username, password)
            smtp.send_message(message)
    return "sent"


def send_daily_briefing():
    report = build_report_data()
    subject = "오늘의 투자 브리핑 - Korea & US Investment Briefing"
    html_body = build_html_email(report)
    result = send_email_message(subject, html_body)
    print(f"[briefing-email] sent at {report['asOf']}: {result}")
    return result


def seconds_until_next_run(hour=7, minute=30):
    now = datetime.now(SEOUL_TZ)
    target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if target <= now:
        target += timedelta(days=1)
    return (target - now).total_seconds()


def start_email_scheduler():
    if os.environ.get("BRIEFING_EMAIL_ENABLED", "").lower() not in ("1", "true", "yes"):
        print("[briefing-email] scheduler disabled; set BRIEFING_EMAIL_ENABLED=true to enable")
        return

    def run_loop():
        while True:
            wait_seconds = seconds_until_next_run()
            print(f"[briefing-email] next run in {int(wait_seconds)} seconds")
            time.sleep(wait_seconds)
            try:
                send_daily_briefing()
            except Exception as error:
                print(f"[briefing-email] failed: {error}")

    thread = threading.Thread(target=run_loop, daemon=True)
    thread.start()


class InvestmentBriefingHandler(SimpleHTTPRequestHandler):
    def end_headers(self):
        if not self.path.startswith("/api/"):
            self.send_header("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")
            self.send_header("Pragma", "no-cache")
            self.send_header("Expires", "0")
        super().end_headers()

    def do_GET(self):
        if self.path.startswith("/healthz"):
            self.send_health()
            return
        if self.path.startswith("/api/indices"):
            self.send_indices()
            return
        if self.path.startswith("/api/quotes"):
            self.send_quotes()
            return
        if self.path.startswith("/api/chart"):
            self.send_chart()
            return
        if self.path.startswith("/api/analysis"):
            self.send_analysis()
            return
        if self.path.startswith("/api/email/test"):
            self.send_test_email()
            return
        super().do_GET()

    def send_health(self):
        body = json.dumps(
            {
                "status": "ok",
                "asOf": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            }
        ).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def send_indices(self):
        try:
            indices = {key: fetch_index(symbol) for key, symbol in SYMBOLS.items()}
            body = json.dumps(
                {
                    "source": "Yahoo Finance chart API",
                    "asOf": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                    "indices": indices,
                }
            ).encode("utf-8")
            self.send_response(200)
        except Exception as error:
            body = json.dumps({"error": str(error)}).encode("utf-8")
            self.send_response(502)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def send_chart(self):
        parsed = urllib.parse.urlparse(self.path)
        params = urllib.parse.parse_qs(parsed.query)
        ticker = params.get("symbol", ["SPX"])[0]
        period = params.get("period", ["weekly"])[0]
        try:
            chart = fetch_chart(ticker, period)
            body = json.dumps(
                {
                    "source": "Yahoo Finance chart API",
                    "asOf": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                    "symbol": ticker,
                    "period": period,
                    "chart": chart,
                }
            ).encode("utf-8")
            self.send_response(200)
        except Exception as error:
            body = json.dumps({"error": str(error), "symbol": ticker, "period": period}).encode("utf-8")
            self.send_response(502)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def send_quotes(self):
        quotes, errors = collect_parallel(QUOTE_SYMBOLS, lambda _ticker, yahoo_symbol: fetch_quote(yahoo_symbol))
        body = json.dumps(
            {
                "source": "Yahoo Finance chart API",
                "asOf": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "quotes": quotes,
                "instruments": INSTRUMENTS,
                "errors": errors,
            }
        ).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def send_analysis(self):
        analysis, errors = collect_parallel(QUOTE_SYMBOLS, lambda ticker, _yahoo_symbol: analyze_ticker(ticker))
        body = json.dumps(
            {
                "source": "Yahoo Finance OHLCV",
                "asOf": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "analysis": analysis,
                "instruments": INSTRUMENTS,
                "groups": {
                    key: {"label": label, "market": market, "assetType": asset_type, "poolSize": pool_size_for(market, asset_type), "limit": limit}
                    for key, label, market, asset_type, limit in GROUPS
                },
                "errors": errors,
            }
        ).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def send_test_email(self):
        parsed = urllib.parse.urlparse(self.path)
        params = urllib.parse.parse_qs(parsed.query)
        admin_token = os.environ.get("BRIEFING_ADMIN_TOKEN")
        if admin_token and params.get("token", [""])[0] != admin_token:
            body = json.dumps({"error": "Unauthorized"}).encode("utf-8")
            self.send_response(401)
        else:
            try:
                result = send_daily_briefing()
                body = json.dumps({"status": "sent", "result": result}).encode("utf-8")
                self.send_response(200)
            except Exception as error:
                body = json.dumps({"error": str(error)}).encode("utf-8")
                self.send_response(500)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)


if __name__ == "__main__":
    host = os.environ.get("HOST", "0.0.0.0")
    port = int(os.environ.get("PORT", "3000"))
    start_email_scheduler()
    server = ThreadingHTTPServer((host, port), InvestmentBriefingHandler)
    print(f"Serving investment briefing at http://{host}:{port}")
    server.serve_forever()

