const STOCK_WEIGHTS = {
  momentum: 20,
  growth: 25,
  valuation: 15,
  quality: 15,
  liquidity: 10,
  sentiment: 10,
  risk: 5,
};

const ETF_WEIGHTS = {
  momentum: 25,
  flow: 20,
  liquidity: 15,
  cost: 10,
  holdings: 20,
  risk: 10,
};

export function scoreRecommendation(item) {
  const weights = item.assetType === "etf" ? ETF_WEIGHTS : STOCK_WEIGHTS;
  const weightedScore = Object.entries(weights).reduce((total, [key, weight]) => {
    const raw = item.metrics[key] ?? 50;
    const normalized = key === "risk" ? 100 - raw : raw;
    return total + normalized * (weight / 100);
  }, 0);
  return Math.round(weightedScore);
}

export const scoringModelVersion = "demo-score-v0.1";
