import { recommendations, marketIndexes as fallbackMarketIndexes } from "./demo-data.js";
import { scoreRecommendation } from "./scoring.js";
import { drawCandles, drawIndexCandles, makeCandles, summarizeCandles } from "./chart.js";

const state = {
  tab: "today",
  view: "card",
  chartPeriod: "weekly",
  query: "",
  market: "all",
  asset: "all",
  horizon: "all",
  minScore: 70,
  marketIndexes: fallbackMarketIndexes,
  indexCandles: {},
  liveQuotes: {},
  liveAnalysis: {},
  analysisLoaded: false,
  detailChartCache: {},
  tabChartRenderId: 0,
  marketDataSource: "DEMO DATA",
  watchlist: new Set(JSON.parse(localStorage.getItem("watchlist") || "[]")),
};

const $ = (selector) => document.querySelector(selector);
const TOP_STOCK_COUNT = 5;
const TOP_ETF_COUNT = 3;

function topCountFor(assetType) {
  return assetType === "stock" ? TOP_STOCK_COUNT : TOP_ETF_COUNT;
}

function formatPercent(value) {
  const sign = value > 0 ? "+" : "";
  return `${sign}${value.toFixed(2)}%`;
}

function formatNumber(value, locale = "en-US") {
  return value.toLocaleString(locale, { maximumFractionDigits: 0 });
}

function normalizeApiCandles(candles = []) {
  return candles.map((item) => ({
    ...item,
    date: new Date(`${item.date}T00:00:00Z`),
  }));
}

async function fetchLiveChart(symbol, period) {
  const cacheKey = `${symbol}:${period}`;
  try {
    const response = await fetch(`/api/chart?symbol=${encodeURIComponent(symbol)}&period=${encodeURIComponent(period)}&t=${Date.now()}`, {
      cache: "no-store",
    });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const payload = await response.json();
    const candles = normalizeApiCandles(payload.chart?.candles || []);
    if (!candles.length) throw new Error("No chart candles");
    state.detailChartCache[cacheKey] = candles;
    return candles;
  } catch (error) {
    return state.detailChartCache[cacheKey] || null;
  }
}

async function loadLiveMarketData() {
  try {
    const response = await fetch(`/api/indices?t=${Date.now()}`, { cache: "no-store" });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const payload = await response.json();
    const nextIndexes = {};
    const nextCandles = {};
    Object.entries(payload.indices || {}).forEach(([key, item]) => {
      if (typeof item.value === "number") {
        nextIndexes[key] = {
          value: item.value,
          change: typeof item.change === "number" ? item.change : 0,
        };
      }
      if (Array.isArray(item.candles) && item.candles.length > 0) {
        nextCandles[key] = normalizeApiCandles(item.candles);
      }
    });
    if (!nextIndexes.SPX || !nextIndexes.IXIC || !nextIndexes.KOSPI) throw new Error("Missing index data");
    state.marketIndexes = nextIndexes;
    state.indexCandles = nextCandles;
    state.marketDataSource = "LIVE DATA";
    $("#dataStatus").textContent = "LIVE DATA";
  } catch (error) {
    state.marketIndexes = fallbackMarketIndexes;
    state.indexCandles = {};
    state.marketDataSource = "DEMO DATA";
    $("#dataStatus").textContent = "DEMO DATA";
  }
}

async function loadLiveQuotes() {
  try {
    const response = await fetch(`/api/quotes?t=${Date.now()}`, { cache: "no-store" });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const payload = await response.json();
    state.liveQuotes = payload.quotes || {};
  } catch (error) {
    state.liveQuotes = {};
  }
}

async function loadLiveAnalysis() {
  try {
    const response = await fetch(`/api/analysis?t=${Date.now()}`, { cache: "no-store" });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const payload = await response.json();
    state.liveAnalysis = payload.analysis || {};
    state.analysisLoaded = true;
  } catch (error) {
    state.liveAnalysis = {};
    state.analysisLoaded = false;
  }
}

function getActualScore(item) {
  const analysis = state.liveAnalysis[item.ticker];
  if (!analysis && state.analysisLoaded) return 0;
  if (!analysis) return scoreRecommendation(item);
  return item.assetType === "etf" ? analysis.etfScore : analysis.stockScore;
}

function getActualFactors(item) {
  return state.liveAnalysis[item.ticker]?.factors;
}

function getReasonScores(item) {
  const analysis = state.liveAnalysis[item.ticker];
  if (!analysis?.reasonScores) return [];
  return item.assetType === "etf" ? analysis.reasonScores.etf || [] : analysis.reasonScores.stock || [];
}

function formatLivePrice(item) {
  const quote = state.liveQuotes[item.ticker];
  if (!quote || typeof quote.price !== "number") return item.price;
  const locale = item.market === "KR" ? "ko-KR" : "en-US";
  const suffix = item.market === "KR" ? "원" : "";
  const prefix = item.market === "US" ? "$" : "";
  return `${prefix}${formatNumber(quote.price, locale)}${suffix}`;
}

function formatLiveChange(item) {
  const quote = state.liveQuotes[item.ticker];
  if (!quote || typeof quote.change !== "number") return formatPercent(item.dayChange);
  return formatPercent(quote.change);
}

function formatActualWeekReturn(item) {
  if (item.factors && typeof item.factors.return1w === "number") return formatPercent(item.factors.return1w);
  return formatPercent(item.weekReturn);
}

function formatActualMonthReturn(item) {
  if (item.factors && typeof item.factors.return1m === "number") return formatPercent(item.factors.return1m);
  return formatPercent(item.monthReturn);
}

function tabToFilter(tab) {
  const map = {
    "kr-stock": { market: "KR", asset: "stock" },
    "us-stock": { market: "US", asset: "stock" },
    "kr-etf": { market: "KR", asset: "etf" },
    "us-etf": { market: "US", asset: "etf" },
  };
  return map[tab] || {};
}

function getScoredRecommendations() {
  return recommendations
    .map((item) => ({
      ...item,
      score: getActualScore(item),
      factors: getActualFactors(item),
      reasonScores: getReasonScores(item),
    }))
    .sort((a, b) => {
      const aFactors = a.factors || {};
      const bFactors = b.factors || {};
      return (
        b.score - a.score ||
        (bFactors.return3m || 0) - (aFactors.return3m || 0) ||
        (bFactors.return1m || 0) - (aFactors.return1m || 0) ||
        (aFactors.maxDrawdown || 0) - (bFactors.maxDrawdown || 0)
      );
    });
}

function getFilteredRecommendations() {
  const tabFilter = tabToFilter(state.tab);
  return getScoredRecommendations().filter((item) => {
    const haystack = `${item.name} ${item.ticker} ${item.reasons.join(" ")} ${item.risks.join(" ")}`.toLowerCase();
    const market = tabFilter.market || state.market;
    const asset = tabFilter.asset || state.asset;
    return (
      haystack.includes(state.query.toLowerCase()) &&
      (market === "all" || item.market === market) &&
      (asset === "all" || item.assetType === asset) &&
      (state.horizon === "all" || item.horizon === state.horizon) &&
      item.score >= state.minScore
    );
  });
}

function getTabRecommendations() {
  const tabFilter = tabToFilter(state.tab);
  if (!tabFilter.market || !tabFilter.asset) return getScoredRecommendations();
  return getScoredRecommendations()
    .filter((item) => item.market === tabFilter.market && item.assetType === tabFilter.asset)
    .slice(0, topCountFor(tabFilter.asset));
}

function renderIndexMetric(config) {
  const candles = state.indexCandles[config.indexKey] || makeCandles(config.symbol, "weekly", 53);
  const stats = summarizeCandles(candles);
  $(config.valueId).textContent = formatNumber(state.marketIndexes[config.indexKey].value, config.locale);
  $(config.changeId).textContent = formatPercent(state.marketIndexes[config.indexKey].change);
  $(config.changeId).className = state.marketIndexes[config.indexKey].change < 0 ? "down" : "";
  $(config.currentId).textContent = formatNumber(stats.current, config.locale);
  $(config.highId).textContent = formatNumber(stats.high, config.locale);
  $(config.lowId).textContent = formatNumber(stats.low, config.locale);
  drawIndexCandles($(config.canvasId), candles);
}

function renderMetrics() {
  renderIndexMetric({
    symbol: "SPX",
    indexKey: "SPX",
    locale: "en-US",
    valueId: "#metricSp",
    changeId: "#metricSpChange",
    currentId: "#metricSpCurrent",
    highId: "#metricSpHigh",
    lowId: "#metricSpLow",
    canvasId: "#spChart",
  });
  renderIndexMetric({
    symbol: "IXIC",
    indexKey: "IXIC",
    locale: "en-US",
    valueId: "#metricNasdaq",
    changeId: "#metricNasdaqChange",
    currentId: "#metricNasdaqCurrent",
    highId: "#metricNasdaqHigh",
    lowId: "#metricNasdaqLow",
    canvasId: "#nasdaqChart",
  });
  renderIndexMetric({
    symbol: "KOSPI",
    indexKey: "KOSPI",
    locale: "ko-KR",
    valueId: "#metricKospi",
    changeId: "#metricKospiChange",
    currentId: "#metricKospiCurrent",
    highId: "#metricKospiHigh",
    lowId: "#metricKospiLow",
    canvasId: "#kospiChart",
  });
}

function renderTopPicks() {
  if (!state.analysisLoaded) {
    $("#briefingTopPicks").innerHTML = `<div class="loading-panel">실제 OHLCV 기반 랭킹을 계산 중입니다.</div>`;
    return;
  }
  const scored = getScoredRecommendations();
  const groups = [
    { label: "한국주식 TOP 5", market: "KR", assetType: "stock" },
    { label: "미국주식 TOP 5", market: "US", assetType: "stock" },
    { label: "한국 ETF TOP 3", market: "KR", assetType: "etf" },
    { label: "미국 ETF TOP 3", market: "US", assetType: "etf" },
  ];
  $("#briefingTopPicks").innerHTML = `
    <table>
      <thead>
        <tr>
          <th>구분</th>
          <th>1위</th>
          <th>2위</th>
          <th>3위</th>
          <th>4위</th>
          <th>5위</th>
        </tr>
      </thead>
      <tbody>
        ${groups
          .map((group) => {
            const picks = scored
              .filter((item) => item.market === group.market && item.assetType === group.assetType)
              .slice(0, topCountFor(group.assetType));
            return `
              <tr>
                <td>${group.label}</td>
                ${picks
                  .map(
                    (item) => `
                      <td>
                        <span class="pick-name">${item.name}</span>
                        <span class="pick-meta">${item.ticker} · <strong class="pick-price">${formatLivePrice(item)}</strong> · ${item.score}점 · ${item.strength}</span>
                      </td>
                    `
                  )
                  .join("")}
                ${Array.from({ length: topCountFor(group.assetType) === TOP_STOCK_COUNT ? 0 : TOP_STOCK_COUNT - TOP_ETF_COUNT })
                  .map(() => `<td class="empty-pick">-</td>`)
                  .join("")}
              </tr>
            `;
          })
          .join("")}
      </tbody>
    </table>
  `;
}

function getChartInstruments() {
  const seen = new Set();
  const indexItems = [
    { ticker: "SPX", name: "S&P 500", assetType: "index" },
    { ticker: "IXIC", name: "NASDAQ Composite", assetType: "index" },
    { ticker: "KOSPI", name: "KOSPI", assetType: "index" },
  ];
  return [...indexItems, ...getResultGroups().flatMap((group) => group.items)]
    .filter((item) => {
      if (seen.has(item.ticker)) return false;
      seen.add(item.ticker);
      return true;
    })
    .map((item) => ({
      ticker: item.ticker,
      label: item.assetType === "index" ? item.name : `${item.name} (${item.ticker})`,
    }));
}

function renderChartOptions() {
  const select = $("#chartInstrument");
  const currentValue = select.value || "SPX";
  const options = getChartInstruments();
  select.innerHTML = options.map((item) => `<option value="${item.ticker}">${item.label}</option>`).join("");
  select.value = options.some((item) => item.ticker === currentValue) ? currentValue : "SPX";
}

function getResultGroups(items = getScoredRecommendations()) {
  return [
    { title: "한국주식 TOP 5", items: items.filter((item) => item.market === "KR" && item.assetType === "stock").slice(0, TOP_STOCK_COUNT) },
    { title: "미국주식 TOP 5", items: items.filter((item) => item.market === "US" && item.assetType === "stock").slice(0, TOP_STOCK_COUNT) },
    { title: "한국 ETF TOP 3", items: items.filter((item) => item.market === "KR" && item.assetType === "etf").slice(0, 3) },
    { title: "미국 ETF TOP 3", items: items.filter((item) => item.market === "US" && item.assetType === "etf").slice(0, 3) },
  ];
}

function renderRecommendationCard(item, index) {
  const isWatched = state.watchlist.has(item.ticker);
  return `
    <article class="recommendation-card">
      <div class="card-top">
        <div class="rank">${index + 1}</div>
        <div>
          <h3>${item.name} <span class="ticker">${item.ticker}</span></h3>
          <p class="card-meta">${item.exchange} · ${item.assetType === "stock" ? "주식" : "ETF"}</p>
        </div>
        <div class="score"><strong>${item.score}</strong><span>종합점수</span></div>
      </div>
      <div class="pill-row">
        <span class="pill">${item.market === "KR" ? "한국" : "미국"}</span>
        <span class="pill">${item.horizonLabel}</span>
        <span class="pill">${item.strength}</span>
      </div>
      <div class="price-line">
        <strong>${formatLivePrice(item)}</strong>
        <span>일 ${formatLiveChange(item)} · 주 ${formatActualWeekReturn(item)} · 월 ${formatActualMonthReturn(item)}</span>
      </div>
      <div class="reason-block">
        <span>선정 근거</span>
        <ul class="reason-list">${renderActualReasons(item)}</ul>
      </div>
      <p class="risk">위험: ${item.risks[0]}</p>
      <button class="watch-button" data-watch="${item.ticker}">${isWatched ? "관심 해제" : "관심 추가"}</button>
    </article>
  `;
}

function renderActualReasons(item) {
  if (!item.factors) {
    return item.reasons.slice(0, 2).map((reason) => `<li>${reason}</li>`).join("");
  }
  if (item.reasonScores?.length) {
    return item.reasonScores
      .slice(0, 3)
      .map((reason) => `<li>${describeReason(item, reason)}</li>`)
      .join("");
  }
  return [
    `1개월 ${formatPercent(item.factors.return1m)}, 3개월 ${formatPercent(item.factors.return3m)}로 가격 추세를 반영`,
    `거래량 비율 ${item.factors.volumeRatio}배, 최대낙폭 ${item.factors.maxDrawdown}%를 점수에 반영`,
  ]
    .map((reason) => `<li>${reason}</li>`)
    .join("");
}

function describeReason(item, reason) {
  const factors = item.factors || {};
  const descriptions = {
    "모멘텀": `최근 1개월 ${formatPercent(factors.return1m || 0)}, 3개월 ${formatPercent(factors.return3m || 0)} 흐름과 10/20/60일 추세를 종합하면 ${reason.grade}입니다.`,
    "수익성": `1개월 ${formatPercent(factors.return1m || 0)}, 3개월 ${formatPercent(factors.return3m || 0)}, 6개월 ${formatPercent(factors.return6m || 0)} 수익률과 변동성 대비 수익률을 함께 보면 ${reason.grade}입니다.`,
    "성장/추세 품질": `3개월·6개월 가격 흐름, 20일/60일 평균선 방향, 상승일 비율을 함께 보면 추세 품질이 ${reason.grade}입니다.`,
    "밸류 부담": `52주 고점 대비 위치와 6개월 상승 부담을 기준으로 보면 현재 가격 부담은 ${reason.grade} 수준입니다.`,
    "품질/리스크": `연환산 변동성 ${factors.volatility ?? "-"}%, 최대낙폭 ${factors.maxDrawdown ?? "-"}%를 반영한 안정성 평가는 ${reason.grade}입니다.`,
    "수급/거래": `최근 거래량이 장기 평균 대비 ${factors.volumeRatio ?? "-"}배 수준이라 수급 강도는 ${reason.grade}입니다.`,
    "기초지수 추세": `기초자산의 3개월·6개월 추세와 평균선 방향을 기준으로 추세 평가는 ${reason.grade}입니다.`,
    "자금흐름/수급": `거래량 비율 ${factors.volumeRatio ?? "-"}배와 최근 가격 흐름을 자금 유입의 대용 지표로 보면 ${reason.grade}입니다.`,
    "유동성": `최근 거래량과 장기 평균 대비 거래 활성도를 기준으로 유동성은 ${reason.grade}입니다.`,
    "비용/추적 안정성": `실제 보수율/추적오차 직접값 대신 변동성과 낙폭을 이용한 안정성 대용 평가가 ${reason.grade}입니다.`,
    "변동성 리스크": `연환산 변동성 ${factors.volatility ?? "-"}%, 최대낙폭 ${factors.maxDrawdown ?? "-"}% 기준 리스크 관리는 ${reason.grade}입니다.`,
  };
  return `${reason.label} ${reason.grade} (${reason.score}점): ${descriptions[reason.label] || "실제 OHLCV 기반 분석 항목을 반영했습니다."}`;
}

function renderActualReasonSummary(item) {
  if (!item.factors) return item.reasons.slice(0, 2).join(" · ");
  if (item.reasonScores?.length) {
    return `
      <span class="reason-detail-list">
        ${item.reasonScores
          .slice(0, 5)
          .map(
            (reason) => `
              <em>
                <b>${reason.label}</b>
                <strong>${reason.grade} · ${reason.score}점</strong>
                <small>${describeReason(item, reason).replace(`${reason.label} ${reason.grade} (${reason.score}점): `, "")}</small>
              </em>
            `
          )
          .join("")}
      </span>
      <small>1개월 ${formatPercent(item.factors.return1m)} · 3개월 ${formatPercent(item.factors.return3m)} · 최대낙폭 ${item.factors.maxDrawdown}%</small>
    `;
  }
  return `1개월 ${formatPercent(item.factors.return1m)}, 3개월 ${formatPercent(item.factors.return3m)}, 거래량 ${item.factors.volumeRatio}배, 최대낙폭 ${item.factors.maxDrawdown}%를 반영`;
}

function renderCards(items) {
  if (!state.analysisLoaded) {
    $("#recommendationCards").innerHTML = `<div class="loading-panel">실제 분석 점수를 불러오는 중입니다.</div>`;
    return;
  }
  const groups = getResultGroups(items).filter((group) => group.items.length > 0);
  $("#recommendationCards").innerHTML = `
    <div class="result-split ${groups.length === 1 ? "result-split--single" : ""}">
      ${groups
        .map(
          (group) => `
            <section class="result-group">
              <h3>${group.title}</h3>
              <div class="result-group__cards">
                ${group.items.map((item, index) => renderRecommendationCard(item, index)).join("")}
              </div>
            </section>
          `
        )
        .join("")}
    </div>
  `;
}

function renderRecommendationRows(items) {
  return items
    .map(
      (item, index) => `
        <tr class="pick-main-row">
          <td class="rank-cell">${index + 1}</td>
          <td class="instrument-cell"><strong>${item.name}</strong><span>${item.ticker}</span></td>
          <td class="price-cell">${formatLivePrice(item)}</td>
          <td>
            <div class="change-mini">
              <span>일 ${formatLiveChange(item)}</span>
              <span>주 ${formatActualWeekReturn(item)}</span>
              <span>월 ${formatActualMonthReturn(item)}</span>
            </div>
          </td>
          <td class="score-cell">${item.score}<span>점</span></td>
        </tr>
        <tr class="reason-row">
          <td colspan="5">
            <strong>TOP Picks 선정 근거</strong>
            <span>${renderActualReasonSummary(item)}</span>
          </td>
        </tr>
      `
    )
    .join("");
}

function renderTable(items) {
  if (!state.analysisLoaded) {
    $("#recommendationTable").innerHTML = `<div class="loading-panel">실제 분석 점수를 불러오는 중입니다.</div>`;
    return;
  }
  const groups = getResultGroups(items).filter((group) => group.items.length > 0);
  $("#recommendationTable").innerHTML = `
    <div class="result-split ${groups.length === 1 ? "result-split--single" : ""}">
      ${groups
        .map(
          (group) => `
            <section class="result-group">
              <h3>${group.title}</h3>
              <div class="table-wrap table-wrap--nested">
                <table>
                  <thead>
                    <tr>
                      <th>순위</th><th>종목</th><th>현재가</th><th>변동</th><th>점수</th>
                    </tr>
                  </thead>
                  <tbody>${renderRecommendationRows(group.items)}</tbody>
                </table>
              </div>
            </section>
          `
        )
        .join("")}
    </div>
  `;
}

function renderResultTitle() {
  const titles = {
    today: "시장별 TOP Picks",
    "kr-stock": "한국 주식 TOP Picks",
    "us-stock": "미국 주식 TOP Picks",
    "kr-etf": "한국 ETF TOP Picks",
    "us-etf": "미국 ETF TOP Picks",
  };
  $("#resultTitle").textContent = titles[state.tab] || "시장별 TOP Picks";
}

function getTabLabel() {
  const labels = {
    "kr-stock": "한국 주식",
    "us-stock": "미국 주식",
    "kr-etf": "한국 ETF",
    "us-etf": "미국 ETF",
  };
  return labels[state.tab] || "";
}

function picksAssetType() {
  return tabToFilter(state.tab).asset || "stock";
}

function equalizeResultGroupHeights() {
  const groups = Array.from(document.querySelectorAll(".result-group"));
  groups.forEach((group) => {
    group.style.minHeight = "";
  });

  const visibleContainer = state.view === "card" ? $("#recommendationCards") : $("#recommendationTable");
  if (!visibleContainer || visibleContainer.classList.contains("is-hidden")) return;

  const visibleGroups = Array.from(visibleContainer.querySelectorAll(".result-group"));
  if (visibleGroups.length < 2) return;

  const columns = window.matchMedia("(min-width: 761px)").matches ? 2 : 1;
  if (columns === 1) return;

  for (let index = 0; index < visibleGroups.length; index += columns) {
    const rowGroups = visibleGroups.slice(index, index + columns);
    const maxHeight = Math.max(...rowGroups.map((group) => group.getBoundingClientRect().height));
    rowGroups.forEach((group) => {
      group.style.minHeight = `${Math.ceil(maxHeight)}px`;
    });
  }
}

async function renderTabPickCharts(items) {
  const section = $("#tabPickCharts");
  const list = $("#tabChartList");
  if (state.tab === "today") {
    section.classList.add("is-hidden");
    list.innerHTML = "";
    return;
  }

  const renderId = (state.tabChartRenderId += 1);
  const picks = items.slice(0, topCountFor(picksAssetType()));
  const label = getTabLabel();
  section.classList.remove("is-hidden");
  $("#tabChartTitle").textContent = `${label} TOP ${picks.length} 주봉 캔들차트`;
  list.innerHTML = picks
    .map(
      (item, index) => `
        <article class="tab-chart-card">
          <div class="tab-chart-card__head">
            <div>
              <span class="rank-badge">${index + 1}위</span>
              <h3>${item.name} <em>${item.ticker}</em></h3>
            </div>
            <p>주봉 · 10이평 · 거래량</p>
          </div>
          <canvas id="tabChart-${item.ticker}" width="1200" height="430" aria-label="${item.name} 주봉 캔들차트"></canvas>
        </article>
      `
    )
    .join("");

  await Promise.all(
    picks.map(async (item) => {
      const candles = (await fetchLiveChart(item.ticker, "weekly")) || makeCandles(item.ticker, "weekly", 52);
      if (renderId !== state.tabChartRenderId || state.tab === "today") return;
      const canvas = document.getElementById(`tabChart-${item.ticker}`);
      if (canvas) drawCandles(canvas, candles);
    })
  );
}

async function renderChart() {
  const symbol = $("#chartInstrument").value;
  const period = $("#chartPeriod").value || state.chartPeriod;
  const rangeByPeriod = { daily: 63, weekly: 52, monthly: 36 };
  const range = rangeByPeriod[period] || 52;
  const label = $("#chartInstrument").selectedOptions[0].textContent;
  const periodLabel = $("#chartPeriod").selectedOptions[0].textContent;
  const indexKeyBySymbol = { SPX: "SPX", IXIC: "IXIC", KOSPI: "KOSPI" };
  const liveCandles = period === "weekly" ? state.indexCandles[indexKeyBySymbol[symbol]] : null;
  $("#chartTitle").textContent = `${label} ${periodLabel}`;
  const apiCandles = liveCandles || (await fetchLiveChart(symbol, period));
  drawCandles($("#candleChart"), apiCandles || makeCandles(symbol, period, range));
}

function render() {
  const isTodayTab = state.tab === "today";
  $(".metrics-grid").classList.toggle("is-hidden", !isTodayTab);
  $(".top-picks-section").classList.toggle("is-hidden", !isTodayTab);
  $(".chart-section").classList.toggle("is-hidden", !isTodayTab);
  if (isTodayTab) {
    renderMetrics();
    renderTopPicks();
    renderChartOptions();
  }
  const items = state.tab === "today" ? getScoredRecommendations() : getTabRecommendations();
  renderResultTitle();
  renderCards(items);
  renderTable(items);
  renderTabPickCharts(items);
  if (isTodayTab) renderChart();
  $("#recommendationCards").classList.toggle("is-hidden", state.view !== "card");
  $("#recommendationTable").classList.toggle("is-hidden", state.view !== "table");
  requestAnimationFrame(equalizeResultGroupHeights);
}

function bindEvents() {
  document.querySelectorAll(".tab").forEach((tab) => {
    tab.addEventListener("click", () => {
      document.querySelectorAll(".tab").forEach((item) => item.classList.remove("is-active"));
      tab.classList.add("is-active");
      state.tab = tab.dataset.tab;
      render();
    });
  });
  $("#cardView").addEventListener("click", () => {
    state.view = "card";
    $("#cardView").classList.add("is-active");
    $("#tableView").classList.remove("is-active");
    render();
  });
  $("#tableView").addEventListener("click", () => {
    state.view = "table";
    $("#tableView").classList.add("is-active");
    $("#cardView").classList.remove("is-active");
    render();
  });
  $("#themeToggle").addEventListener("click", () => {
    document.documentElement.dataset.theme = document.documentElement.dataset.theme === "dark" ? "" : "dark";
    if (state.tab === "today") {
      renderMetrics();
      renderChart();
    }
  });
  document.body.addEventListener("click", (event) => {
    const ticker = event.target.dataset.watch;
    if (!ticker) return;
    if (state.watchlist.has(ticker)) state.watchlist.delete(ticker);
    else state.watchlist.add(ticker);
    localStorage.setItem("watchlist", JSON.stringify([...state.watchlist]));
    render();
  });
  ["chartInstrument", "chartPeriod"].forEach((id) => {
    $(`#${id}`).addEventListener("change", () => {
      state.chartPeriod = $("#chartPeriod").value;
      if (state.tab === "today") renderChart();
    });
  });
  window.addEventListener("resize", () => requestAnimationFrame(equalizeResultGroupHeights));
}

bindEvents();
$("#chartPeriod").value = state.chartPeriod;
render();
Promise.all([loadLiveMarketData(), loadLiveQuotes(), loadLiveAnalysis()]).then(render);
setInterval(() => {
  Promise.all([loadLiveMarketData(), loadLiveQuotes(), loadLiveAnalysis()]).then(render);
}, 60000);
