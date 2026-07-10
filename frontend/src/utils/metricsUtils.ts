export interface ComputedMetrics {
  return: number | null
  volatility: number | null
  sharpe_ratio: number | null
  sortino_ratio: number | null
  calmar_ratio: number | null
  max_drawdown: number | null
  avg_drawdown: number | null
  max_drawdown_duration: number | null
  turnover: number | null
  win_rate: number | null
  loss_rate: number | null
  average_win: number | null
  average_loss: number | null
  skewness: number | null
  kurtosis: number | null
  var_95: number | null
  cvar_95: number | null
  alpha: null
  tracking_error: null
}

export interface DateWindow {
  start: string
  end: string
}

export interface DeserializedSeries {
  returns: { date: string; value: number }[]
  turnover: { date: string; value: number }[]
  wealth: { date: string; value: number }[]
  benchmark: { date: string; value: number }[]
  benchmark_returns: { date: string; value: number }[]
}

export interface DeserializedIcSeries {
  ic_series: { date: string; value: number }[]
}

/** Deserialize a series from JSON round-trip into {date, value} pairs */
export function deserializeToArray(data: any): { date: string; value: number }[] {
  if (!data) return []
  if (typeof data === "object" && "index" in data && "values" in data) {
    return (data.index as string[]).map((d: string, i: number) => ({ date: d, value: data.values[i] }))
  }
  if (typeof data === "object" && !Array.isArray(data)) {
    return Object.entries(data).map(([date, value]) => ({ date, value: value as number }))
  }
  return []
}

/**
 * Cache deserialized series on the run object itself.
 * This means deserialization only happens once per run regardless of
 * how many times getEffectiveSummary is called.
 */
const seriesCache = new WeakMap<object, DeserializedSeries>()

export function getCachedSeries(run: any): DeserializedSeries {
  if (seriesCache.has(run)) {
    return seriesCache.get(run)!
  }
  const series: DeserializedSeries = {
    returns: deserializeToArray(run.result.series?.portfolio_returns),
    turnover: deserializeToArray(run.result.series?.portfolio_turnover),
    wealth: deserializeToArray(run.result.series?.portfolio_wealth_factors),
    benchmark: deserializeToArray(run.result.series?.benchmark_wealth_factors),
    benchmark_returns: deserializeToArray(run.result.series?.benchmark_returns),
  }
  seriesCache.set(run, series)
  return series
}

const icSeriesCache = new WeakMap<object, DeserializedIcSeries>()

export function getCachedIcSeries(run: any): DeserializedIcSeries {
  if (icSeriesCache.has(run)) {
    return icSeriesCache.get(run)!
  }
  const ic_series: DeserializedIcSeries = {
    ic_series: deserializeToArray(run.monitoring_stats?.ic_statistics)
  }
  icSeriesCache.set(run, ic_series)
  return ic_series
}

/** Slice a series array to a date window */
export function sliceSeries(
  series: { date: string; value: number }[],
  window: DateWindow | null
): { date: string; value: number }[] {
  if (!window) return series
  return series.filter(p => p.date >= window.start && p.date <= window.end)
}

function guessAnnualFactor(series: { date: string; value: number }[]): number {
  if (series.length < 2) return 252
  const first = new Date(series[0].date).getTime()
  const last = new Date(series[series.length - 1].date).getTime()
  const years = (last - first) / (1000 * 60 * 60 * 24 * 365.25)
  const periodsPerYear = series.length / years
  if (periodsPerYear < 60) return 52
  if (periodsPerYear < 200) return 12
  return 252
}

function mean(arr: number[]): number {
  return arr.reduce((a, b) => a + b, 0) / arr.length
}

function std(arr: number[], ddof = 1): number {
  const m = mean(arr)
  const variance = arr.reduce((a, b) => a + (b - m) ** 2, 0) / (arr.length - ddof)
  return Math.sqrt(variance)
}

function skewness(arr: number[]): number {
  const m = mean(arr)
  const s = std(arr)
  if (s === 0) return 0
  return arr.reduce((a, b) => a + ((b - m) / s) ** 3, 0) / arr.length
}

function kurtosis(arr: number[]): number {
  const m = mean(arr)
  const s = std(arr)
  if (s === 0) return 0
  return arr.reduce((a, b) => a + ((b - m) / s) ** 4, 0) / arr.length - 3
}

function quantile(sorted: number[], q: number): number {
  const idx = q * (sorted.length - 1)
  const lo = Math.floor(idx)
  const hi = Math.ceil(idx)
  return sorted[lo] + (sorted[hi] - sorted[lo]) * (idx - lo)
}

function maxDrawdown(wealthFactors: number[]): number {
  let peak = wealthFactors[0]
  let maxDD = 0
  for (const wf of wealthFactors) {
    if (wf > peak) peak = wf
    const dd = peak > 0 ? (wf - peak) / peak : 0
    if (dd < maxDD) maxDD = dd
  }
  return Math.abs(maxDD)
}

function avgDrawdown(wealthFactors: number[]): number {
  let peak = wealthFactors[0]
  const drawdowns: number[] = []
  for (const wf of wealthFactors) {
    if (wf > peak) peak = wf
    if (peak > 0) {
      const dd = (wf - peak) / peak
      if (dd < 0) drawdowns.push(dd)
    }
  }
  if (drawdowns.length === 0) return 0
  return Math.abs(mean(drawdowns))
}

function maxDrawdownDays(wealthFactors: number[]): number {
  let peak = wealthFactors[0]
  let maxStreak = 0
  let streak = 0
  for (const wf of wealthFactors) {
    if (wf >= peak) {
      peak = wf
      streak = 0
    } else {
      streak++
      if (streak > maxStreak) maxStreak = streak
    }
  }
  return maxStreak
}

export function computeMetrics(
  returnSeries: { date: string; value: number }[],
  turnoverSeries: { date: string; value: number }[],
  wealthSeries: { date: string; value: number }[]
): ComputedMetrics {
  if (returnSeries.length < 2) {
    return {
      return: null, volatility: null, sharpe_ratio: null, sortino_ratio: null,
      calmar_ratio: null, max_drawdown: null, avg_drawdown: null,
      max_drawdown_duration: null, turnover: null, win_rate: null, loss_rate: null,
      average_win: null, average_loss: null, skewness: null, kurtosis: null,
      var_95: null, cvar_95: null, alpha: null, tracking_error: null
    }
  }

  const returns = returnSeries.map(p => p.value)
  const wf = wealthSeries.map(p => p.value)
  const af = guessAnnualFactor(returnSeries)
  const n = returns.length
  const years = n / af

  const wfBase = wf[0]
  const rebasedWf = wf.map(v => v / wfBase)

  const annReturn = rebasedWf[rebasedWf.length - 1] ** (1 / years) - 1
  const annVol = std(returns) * Math.sqrt(af)
  const sharpe = annVol !== 0 ? annReturn / annVol : 0

  const downReturns = returns.filter(r => r < 0)
  const downVol = downReturns.length > 1 ? std(downReturns) * Math.sqrt(af) : null
  const sortino = downVol && downVol !== 0 ? annReturn / downVol : null

  const maxDD = maxDrawdown(rebasedWf)
  const calmar = maxDD !== 0 ? annReturn / maxDD : null

  const sortedReturns = [...returns].sort((a, b) => a - b)
  const var95 = quantile(sortedReturns, 0.05)
  const cvarReturns = returns.filter(r => r < var95)
  const cvar95 = cvarReturns.length > 0 ? mean(cvarReturns) : var95

  const wins = returns.filter(r => r > 0)
  const losses = returns.filter(r => r < 0)

  const turnoverVals = turnoverSeries.map(p => p.value)
  const annTurnover = turnoverVals.length > 0 ? mean(turnoverVals) * af : null

  return {
    return: annReturn,
    volatility: annVol,
    sharpe_ratio: sharpe,
    sortino_ratio: sortino,
    calmar_ratio: calmar,
    max_drawdown: maxDD,
    avg_drawdown: avgDrawdown(rebasedWf),
    max_drawdown_duration: maxDrawdownDays(rebasedWf),
    turnover: annTurnover,
    win_rate: n > 0 ? wins.length / n : null,
    loss_rate: n > 0 ? losses.length / n : null,
    average_win: wins.length > 0 ? mean(wins) : null,
    average_loss: losses.length > 0 ? mean(losses) : null,
    skewness: skewness(returns),
    kurtosis: kurtosis(returns),
    var_95: var95,
    cvar_95: cvar95,
    alpha: null,
    tracking_error: null
  }
}

/** Get effective summary for a run — recomputed if window set, original otherwise */
export function getEffectiveSummary(run: any, window: DateWindow | null): any {
  if (!window) return run.result.summary

  // Use cached deserialized series — avoids re-parsing on every render
  const cached = getCachedSeries(run)

  const slicedReturns = sliceSeries(cached.returns, window)
  const slicedTurnover = sliceSeries(cached.turnover, window)
  const slicedWealth = sliceSeries(cached.wealth, window)

  if (slicedReturns.length < 2) return run.result.summary

  const recomputed = computeMetrics(slicedReturns, slicedTurnover, slicedWealth)

  return {
    ...run.result.summary,
    ...recomputed
  }
}