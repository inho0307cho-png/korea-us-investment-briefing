import json
import os
import math
import time
import urllib.parse
import urllib.request
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer


SYMBOLS = {
    "SPX": "^GSPC",
    "IXIC": "^IXIC",
    "KOSPI": "^KS11",
}

CHART_SYMBOLS = {
    **SYMBOLS,
}

QUOTE_SYMBOLS = {
    "005930": "005930.KS",
    "000660": "000660.KS",
    "035420": "035420.KS",
    "NVDA": "NVDA",
    "MSFT": "MSFT",
    "AAPL": "AAPL",
    "TIGERKR10": "133690.KS",
    "TIGER200": "102110.KS",
    "KODEX200": "069500.KS",
    "SPY": "SPY",
    "QQQ": "QQQ",
    "IWM": "IWM",
}

CHART_SYMBOLS.update(QUOTE_SYMBOLS)

PERIOD_CONFIG = {
    "daily": {"range": "3mo", "interval": "1d", "limit": 63},
    "weekly": {"range": "1y", "interval": "1wk", "limit": 53},
    "monthly": {"range": "3y", "interval": "1mo", "limit": 36},
}


def fetch_yahoo_chart(symbol, range_value="1y", interval="1wk"):
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

    return {
        "value": current,
        "change": change_percent,
        "candles": candles[-53:],
    }


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

    momentum_score = average(
        [
            scale(return_1m, -8, 12),
            scale(return_3m, -15, 25),
            scale(return_6m, -25, 40),
            scale((current / ma20 - 1) * 100, -8, 8),
            scale((ma20 / ma60 - 1) * 100, -8, 8),
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
        momentum_score * 0.20
        + trend_quality_score * 0.20
        + valuation_proxy_score * 0.15
        + quality_risk_score * 0.20
        + liquidity_score * 0.10
        + sentiment_score * 0.10
        + risk_penalty_score * 0.05
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
        },
        "reasonScores": {
            "stock": [
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


class InvestmentBriefingHandler(SimpleHTTPRequestHandler):
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
        quotes = {}
        errors = {}
        for ticker, yahoo_symbol in QUOTE_SYMBOLS.items():
            try:
                quotes[ticker] = fetch_quote(yahoo_symbol)
            except Exception as error:
                errors[ticker] = str(error)
        body = json.dumps(
            {
                "source": "Yahoo Finance chart API",
                "asOf": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "quotes": quotes,
                "errors": errors,
            }
        ).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def send_analysis(self):
        analysis = {}
        errors = {}
        for ticker in QUOTE_SYMBOLS:
            try:
                analysis[ticker] = analyze_ticker(ticker)
            except Exception as error:
                errors[ticker] = str(error)
        body = json.dumps(
            {
                "source": "Yahoo Finance OHLCV",
                "asOf": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "analysis": analysis,
                "errors": errors,
            }
        ).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)


if __name__ == "__main__":
    host = os.environ.get("HOST", "0.0.0.0")
    port = int(os.environ.get("PORT", "3000"))
    server = ThreadingHTTPServer((host, port), InvestmentBriefingHandler)
    print(f"Serving investment briefing at http://{host}:{port}")
    server.serve_forever()
