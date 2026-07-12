function seededNoise(seed) {
  const x = Math.sin(seed) * 10000;
  return x - Math.floor(x);
}

export function makeCandles(symbol, period, count) {
  const baseMap = {
    SPX: 7575,
    IXIC: 26282,
    KOSPI: 3240,
    "005930": 82400,
    "000660": 238000,
    "035420": 226500,
    NVDA: 165,
    MSFT: 506,
    AAPL: 226,
    TIGERKR10: 124600,
    TIGER200: 44210,
    KODEX200: 44180,
    SPY: 621,
    QQQ: 542,
    IWM: 225,
  };
  const volatilityMap = { daily: 0.012, weekly: 0.025, monthly: 0.055 };
  const base = baseMap[symbol] || 100;
  const volatility = volatilityMap[period] || 0.012;
  const stepDaysMap = { daily: 1, weekly: 7, monthly: 30 };
  const stepDays = stepDaysMap[period] || 7;
  const endDate = new Date();
  endDate.setHours(0, 0, 0, 0);
  const startDate = new Date(endDate);
  if (period === "monthly") {
    startDate.setMonth(endDate.getMonth() - (count - 1));
  } else {
    startDate.setDate(endDate.getDate() - stepDays * (count - 1));
  }
  let close = base * 0.86;
  return Array.from({ length: count }, (_, index) => {
    const date = new Date(startDate);
    if (period === "monthly") {
      date.setMonth(startDate.getMonth() + index);
    } else {
      date.setDate(startDate.getDate() + stepDays * index);
    }
    const drift = 0.002 + (seededNoise(index + symbol.length) - 0.45) * volatility;
    const open = close;
    close = Math.max(base * 0.55, open * (1 + drift));
    const high = Math.max(open, close) * (1 + seededNoise(index + 4) * volatility);
    const low = Math.min(open, close) * (1 - seededNoise(index + 8) * volatility);
    const volume = Math.round(1000000 + seededNoise(index + 12) * 6000000);
    return { date, open, high, low, close, volume };
  });
}

export function summarizeCandles(candles) {
  return {
    current: candles[candles.length - 1].close,
    high: Math.max(...candles.map((item) => item.high)),
    low: Math.min(...candles.map((item) => item.low)),
  };
}

function movingAverage(candles, period, key = "close") {
  return candles.map((item, index) => {
    if (index < period - 1) return null;
    const slice = candles.slice(index - period + 1, index + 1);
    const value = slice.reduce((total, candle) => total + candle[key], 0) / period;
    return { index, value };
  });
}

function formatAxis(value) {
  return value.toLocaleString(undefined, { maximumFractionDigits: 0 });
}

function formatFullDate(date) {
  return `${date.getFullYear()}/${String(date.getMonth() + 1).padStart(2, "0")}`;
}

function formatMonthTick(date, showYear) {
  return showYear ? formatFullDate(date) : String(date.getMonth() + 1).padStart(2, "0");
}

function getHtsColors() {
  return {
    background: "#ffffff",
    grid: "#d8d8d8",
    border: "#222222",
    text: "#5b5b5b",
    up: "#ff1717",
    down: "#001cff",
    volume: "#06477f",
    ma5: "#ffe100",
    ma10: "#2848ff",
    ma20: "#f39c12",
    ma60: "#39a96b",
  };
}

function makeConfig(canvas, candles, options) {
  const width = canvas.width;
  const height = canvas.height;
  const pad = options.pad;
  const panelGap = options.panelGap || 14;
  const max = Math.max(...candles.map((item) => item.high));
  const min = Math.min(...candles.map((item) => item.low));
  const xStep = (width - pad.left - pad.right) / candles.length;
  return {
    ...getHtsColors(),
    width,
    height,
    pad,
    max,
    min,
    priceTop: pad.top,
    priceBottom: options.priceBottom,
    volumeTop: options.volumeTop + panelGap,
    volumeBottom: height - pad.bottom,
    xStep,
    candleWidth: Math.max(4, xStep * 0.58),
  };
}

function priceY(config, price) {
  const h = config.priceBottom - config.priceTop;
  return config.priceTop + ((config.max - price) / (config.max - config.min)) * h;
}

function volumeY(config, volume, maxVolume) {
  const h = config.volumeBottom - config.volumeTop;
  return config.volumeBottom - (volume / maxVolume) * h;
}

function drawPanelFrame(ctx, config, options = {}) {
  ctx.fillStyle = config.background;
  ctx.fillRect(0, 0, config.width, config.height);
  ctx.strokeStyle = config.border;
  ctx.lineWidth = 1;
  ctx.strokeRect(0.5, 0.5, config.width - 1, config.height - 1);
  ctx.beginPath();
  ctx.moveTo(0, config.priceBottom + 0.5);
  ctx.lineTo(config.width, config.priceBottom + 0.5);
  ctx.stroke();

  ctx.strokeStyle = config.grid;
  ctx.setLineDash([4, 4]);
  ctx.lineWidth = 1;
  for (let i = 1; i <= 4; i += 1) {
    const y = config.priceTop + ((config.priceBottom - config.priceTop) * i) / 5;
    ctx.beginPath();
    ctx.moveTo(config.pad.left, y);
    ctx.lineTo(config.width - config.pad.right, y);
    ctx.stroke();
  }
  for (let i = 1; i <= 7; i += 1) {
    const x = config.pad.left + ((config.width - config.pad.left - config.pad.right) * i) / 8;
    ctx.beginPath();
    ctx.moveTo(x, config.priceTop);
    ctx.lineTo(x, config.volumeBottom);
    ctx.stroke();
  }
  for (let i = 1; i <= 2; i += 1) {
    const y = config.volumeTop + ((config.volumeBottom - config.volumeTop) * i) / 3;
    ctx.beginPath();
    ctx.moveTo(config.pad.left, y);
    ctx.lineTo(config.width - config.pad.right, y);
    ctx.stroke();
  }
  ctx.setLineDash([]);

  if (options.axis !== false) drawRightAxis(ctx, config);
}

function drawRightAxis(ctx, config) {
  ctx.font = "13px Arial";
  ctx.textAlign = "left";
  for (let i = 0; i <= 4; i += 1) {
    const price = config.max - ((config.max - config.min) * i) / 4;
    const y = priceY(config, price);
    const label = formatAxis(price);
    const labelX = config.width - config.pad.right + 8;
    const labelY = i === 4 ? y - 8 : y + 4;
    const labelWidth = ctx.measureText(label).width;
    ctx.fillStyle = "rgba(255, 255, 255, 0.94)";
    ctx.fillRect(labelX - 2, labelY - 13, labelWidth + 5, 17);
    ctx.fillStyle = config.text;
    ctx.fillText(label, labelX, labelY);
    ctx.strokeStyle = config.border;
    ctx.beginPath();
    ctx.moveTo(config.width - config.pad.right - 4, y);
    ctx.lineTo(config.width - config.pad.right, y);
    ctx.stroke();
  }
}

function drawCandlestickSeries(ctx, candles, config) {
  candles.forEach((item, index) => {
    const x = config.pad.left + index * config.xStep + config.xStep / 2;
    const color = item.close >= item.open ? config.up : config.down;
    ctx.strokeStyle = color;
    ctx.fillStyle = color;
    ctx.lineWidth = 1.6;
    ctx.beginPath();
    ctx.moveTo(x, priceY(config, item.high));
    ctx.lineTo(x, priceY(config, item.low));
    ctx.stroke();

    const top = priceY(config, Math.max(item.open, item.close));
    const bottom = priceY(config, Math.min(item.open, item.close));
    ctx.fillRect(x - config.candleWidth / 2, top, config.candleWidth, Math.max(3, bottom - top));
  });
}

function drawPriceMa(ctx, candles, config, period, color, width = 1.2) {
  const points = movingAverage(candles, period).filter(Boolean);
  ctx.strokeStyle = color;
  ctx.lineWidth = width;
  ctx.beginPath();
  points.forEach((point, pointIndex) => {
    const x = config.pad.left + point.index * config.xStep + config.xStep / 2;
    const y = priceY(config, point.value);
    if (pointIndex === 0) ctx.moveTo(x, y);
    else ctx.lineTo(x, y);
  });
  ctx.stroke();
}

function drawVolumePanel(ctx, candles, config) {
  const maxVolume = Math.max(...candles.map((item) => item.volume));
  const barTop = config.volumeTop + 26;
  const barHeight = config.volumeBottom - barTop;
  candles.forEach((item, index) => {
    const x = config.pad.left + index * config.xStep + config.xStep / 2;
    const y = config.volumeBottom - (item.volume / maxVolume) * barHeight;
    ctx.fillStyle = config.volume;
    ctx.fillRect(x - config.candleWidth / 2, y, config.candleWidth, config.volumeBottom - y);
  });

  ctx.fillStyle = config.text;
  ctx.font = "13px Arial";
  ctx.textAlign = "right";
  ctx.fillText(`${Math.round(maxVolume / 1000).toLocaleString()}K`, config.width - 8, config.volumeTop + 18);
  ctx.fillText("0K", config.width - 8, config.volumeBottom - 6);
  ctx.textAlign = "left";
}

function drawLegend(ctx, config, label) {
  ctx.font = "bold 13px Arial";
  ctx.fillStyle = "#111111";
  ctx.fillText("■", 9, 18);
  ctx.fillStyle = config.up;
  ctx.fillText(`1Q ${label}`, 25, 18);
  ctx.fillStyle = config.ma10;
  ctx.fillText("10", 125, 18);

  ctx.fillStyle = "#111111";
  ctx.fillText("■", 9, config.volumeTop + 15);
  ctx.fillStyle = config.volume;
  ctx.fillText("거래량", 25, config.volumeTop + 15);
}

function drawCurrentPriceLabel(ctx, candles, config) {
  const last = candles[candles.length - 1];
  const y = priceY(config, last.close);
  const text = `${formatAxis(last.close)}\n(${last.close >= last.open ? "+" : ""}${(((last.close - last.open) / last.open) * 100).toFixed(2)}%)`;
  const x = config.width - config.pad.right + 17;
  ctx.fillStyle = config.up;
  ctx.fillRect(x, y - 18, 58, 38);
  ctx.fillStyle = "#ffffff";
  ctx.font = "bold 13px Arial";
  ctx.textAlign = "center";
  text.split("\n").forEach((line, index) => ctx.fillText(line, x + 29, y - 4 + index * 16));
  ctx.fillStyle = config.up;
  ctx.beginPath();
  ctx.moveTo(config.width - config.pad.right + 2, y);
  ctx.lineTo(config.width - config.pad.right + 14, y - 7);
  ctx.lineTo(config.width - config.pad.right + 14, y + 7);
  ctx.closePath();
  ctx.fill();
  ctx.textAlign = "left";
}

function drawExtremaLabels(ctx, candles, config) {
  const highIndex = candles.findIndex((item) => item.high === config.max);
  const lowIndex = candles.findIndex((item) => item.low === config.min);
  const highX = config.pad.left + highIndex * config.xStep + config.xStep / 2;
  const lowX = config.pad.left + lowIndex * config.xStep + config.xStep / 2;
  const highY = priceY(config, config.max);
  const lowY = priceY(config, config.min);
  ctx.font = "13px Arial";
  ctx.fillStyle = config.up;
  ctx.textAlign = "right";
  ctx.fillText(`${formatAxis(config.max)} ${formatFullDate(candles[highIndex].date)}`, Math.min(highX + 90, config.width - config.pad.right - 4), highY - 12);
  ctx.strokeStyle = config.up;
  ctx.beginPath();
  ctx.moveTo(highX, highY - 4);
  ctx.lineTo(highX + 24, highY - 4);
  ctx.lineTo(highX + 24, highY + 4);
  ctx.stroke();

  ctx.fillStyle = config.down;
  ctx.textAlign = "left";
  const lowText = `${formatAxis(config.min)} ${formatFullDate(candles[lowIndex].date)}`;
  const lowLabelX = Math.max(Math.min(lowX - 40, config.width - config.pad.right - 150), config.pad.left + 6);
  const lowLabelY = Math.max(config.priceTop + 18, Math.min(lowY - 18, config.priceBottom - 22));
  const lowTextWidth = ctx.measureText(lowText).width;
  ctx.fillStyle = "rgba(255, 255, 255, 0.96)";
  ctx.fillRect(lowLabelX - 4, lowLabelY - 14, lowTextWidth + 8, 18);
  ctx.fillStyle = config.down;
  ctx.fillText(lowText, lowLabelX, lowLabelY);
  ctx.strokeStyle = config.down;
  ctx.beginPath();
  ctx.moveTo(lowLabelX + lowTextWidth / 2, lowLabelY + 3);
  ctx.lineTo(lowX, lowY - 8);
  ctx.lineTo(lowX, lowY + 3);
  ctx.stroke();
  ctx.textAlign = "left";
}

function drawMonthAxis(ctx, candles, config) {
  const tickCount = 7;
  ctx.fillStyle = config.text;
  ctx.font = "13px Arial";
  ctx.textAlign = "center";
  for (let index = 0; index < tickCount; index += 1) {
    const candleIndex = Math.round(((candles.length - 1) * index) / (tickCount - 1));
    const candle = candles[candleIndex];
    const x = config.pad.left + candleIndex * config.xStep + config.xStep / 2;
    const showYear = index === 0 || candle.date.getMonth() === 0 || index === tickCount - 1;
    ctx.fillText(formatMonthTick(candle.date, showYear), x, config.height - 5);
  }
  ctx.textAlign = "left";
}

function drawHtsChart(canvas, candles, label, compact = false) {
  const ctx = canvas.getContext("2d");
  const config = makeConfig(canvas, candles, {
    pad: compact ? { top: 26, right: 98, bottom: 24, left: 8 } : { top: 28, right: 98, bottom: 24, left: 8 },
    priceBottom: compact ? Math.round(canvas.height * 0.58) : Math.round(canvas.height * 0.6),
    volumeTop: compact ? Math.round(canvas.height * 0.58) : Math.round(canvas.height * 0.6),
    panelGap: compact ? 34 : 28,
  });
  ctx.clearRect(0, 0, config.width, config.height);
  drawPanelFrame(ctx, config);
  drawCandlestickSeries(ctx, candles, config);
  drawPriceMa(ctx, candles, config, 10, config.ma10, 1.5);
  drawVolumePanel(ctx, candles, config);
  drawLegend(ctx, config, label);
  drawCurrentPriceLabel(ctx, candles, config);
  drawExtremaLabels(ctx, candles, config);
  drawMonthAxis(ctx, candles, config);
}

export function drawCandles(canvas, candles) {
  drawHtsChart(canvas, candles, "상세", false);
}

export function drawIndexCandles(canvas, candles) {
  drawHtsChart(canvas, candles, "지수", true);
}
