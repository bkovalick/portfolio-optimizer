import { useMemo } from "react"
import type { CSSProperties } from "react"
import {
  ResponsiveContainer, BarChart, Bar, Cell, XAxis, YAxis,
  LineChart, Line, ReferenceLine, Tooltip,
} from "recharts"
import { getEffectiveSummary } from "../utils/metricsUtils"
import type { DateWindow } from "../utils/metricsUtils"

/**
 * Statistical Evidence — the section that turns a backtest viewer into a
 * research instrument. Three tiers, in the order a researcher asks:
 *
 *   1. Performance  — what happened
 *   2. Attribution  — why (factor regression; the alpha verdict)
 *   3. Robustness   — whether to believe it (bootstrap CI, deflated Sharpe,
 *                     rolling alpha, IC)
 *
 * Expected payload on the selected run (all optional; sections render an
 * empty-state invitation when absent):
 *
 * run.statistics = {
 *   factor_regression: {
 *     model: "FF5 + MOM",
 *     cov_type: "HAC (Newey-West, 7 lags)",
 *     r_squared: 0.821,
 *     alpha: { coef: 0.000096, t_stat: 0.88, p_value: 0.379 },   // per-period
 *     factors: [{ name: "Mkt-RF", beta: 0.98, t_stat: 56.5, p_value: 0.0 }, ...]
 *   },
 *   bootstrap: { metric: "Sharpe", point: 1.02, ci_low: 0.41, ci_high: 1.58,
 *                n_boot: 2000, method: "stationary block" },
 *   deflated_sharpe: { dsr: 0.62, raw_sharpe: 1.02, n_trials: 24 },
 *   rolling_alpha: [{ date: "2021-03-01", alpha: 0.0002 }, ...],  // per-period
 * }
 *
 * IC flows from the existing monitoring payload:
 *   run.monitoring_stats.ic_statistics.spearman  ({ date: value })
 *   run.monitoring_stats.ic_summary              ({ mean_ic, t_statistic, p_value, ... })
 */

interface Props {
  run: any | null
  dateWindow: DateWindow | null
}

const MONO: CSSProperties = {
  fontFamily: "ui-monospace, 'SF Mono', 'JetBrains Mono', Menlo, monospace",
  fontVariantNumeric: "tabular-nums",
}

export default function StatisticalEvidence({ run, dateWindow }: Props) {
  if (!run) {
    return (
      <section style={container}>
        <SectionHeader />
        <EmptyState line="Select a strategy in the overview table to see its evidence." />
      </section>
    )
  }

  const stats = run.statistics ?? {}
  const summary = getEffectiveSummary(run, dateWindow)

  return (
    <section style={container}>
      <SectionHeader strategy={run.strategy_name} />

      {/* ---- Tier 1: Performance — what happened ---- */}
      <Tier n={1} name="Performance" question="what happened">
        <PerformanceStrip summary={summary} />
      </Tier>

      {/* ---- Tier 2: Attribution — why ---- */}
      <Tier n={2} name="Attribution" question="why">
        {stats.factor_regression
          ? <FactorRegression reg={stats.factor_regression} />
          : <EmptyState line="Factor regression not computed for this run — POST /statistics/{run_id} with the FF5+MOM decomposition to populate." />}
      </Tier>

      {/* ---- Tier 3: Robustness — whether to believe it ---- */}
      <Tier n={3} name="Robustness" question="whether to believe it">
        <div style={robustGrid}>
          {stats.bootstrap
            ? <BootstrapInterval bs={stats.bootstrap} dsr={stats.deflated_sharpe} />
            : <EmptyCard title="Bootstrap confidence interval"
                line="Stationary block bootstrap not computed — resample the return series to put an interval around the Sharpe." />}
          {stats.rolling_alpha?.length
            ? <RollingAlpha data={stats.rolling_alpha} />
            : <EmptyCard title="Rolling alpha"
                line="Rolling factor alpha not computed — a 252-day rolling regression shows whether the edge is stable or episodic." />}
        </div>
        <IcPanel run={run} />
      </Tier>
    </section>
  )
}

/* ================= Tier scaffolding ================= */

function SectionHeader({ strategy }: { strategy?: string }) {
  return (
    <div style={headerBar}>
      <span style={headerLabel}>Statistical Evidence</span>
      {strategy && <span style={{ ...headerStrategy, ...MONO }}>{formatName(strategy)}</span>}
    </div>
  )
}

function Tier({ n, name, question, children }: {
  n: number; name: string; question: string; children: React.ReactNode
}) {
  return (
    <div style={tier}>
      <div style={tierEyebrow}>
        <span style={tierNum}>{n}</span>
        <span style={tierName}>{name}</span>
        <span style={tierQuestion}>— {question}</span>
      </div>
      {children}
    </div>
  )
}

/* ================= Tier 1: performance strip ================= */

const STRIP_METRICS: { key: string; label: string; fmt: (v: number) => string }[] = [
  { key: "return",            label: "Return",   fmt: v => (v * 100).toFixed(1) + "%" },
  { key: "volatility",        label: "Vol",      fmt: v => (v * 100).toFixed(1) + "%" },
  { key: "sharpe_ratio",      label: "Sharpe",   fmt: v => v.toFixed(2) },
  { key: "max_drawdown",      label: "Max DD",   fmt: v => (v * 100).toFixed(1) + "%" },
  { key: "information_ratio", label: "IR",       fmt: v => v.toFixed(2) },
  { key: "turnover",          label: "Turnover", fmt: v => v.toFixed(2) + "x" },
]

function PerformanceStrip({ summary }: { summary: any }) {
  return (
    <div style={strip}>
      {STRIP_METRICS.map(m => {
        const v = summary?.[m.key]
        return (
          <div key={m.key} style={stripCell}>
            <div style={stripLabel}>{m.label}</div>
            <div style={{ ...stripValue, ...MONO }}>{v == null ? "—" : m.fmt(v)}</div>
          </div>
        )
      })}
      <div style={{ ...stripCell, borderRight: "none", flex: 1.6 }}>
        <div style={stripLabel}>Depth</div>
        <div style={stripNote}>Risk, tail, and drawdown detail in the analysis panel above.</div>
      </div>
    </div>
  )
}

/* ================= Tier 2: factor regression + verdict ================= */

function stars(p: number): string {
  if (p < 0.01) return "***"
  if (p < 0.05) return "**"
  if (p < 0.10) return "*"
  return ""
}

function FactorRegression({ reg }: { reg: any }) {
  const alpha = reg.alpha ?? {}
  const factors: any[] = reg.factors ?? []

  const annualizedAlphaBp = alpha.coef != null ? alpha.coef * 252 * 10000 : null
  const perPeriodBp = alpha.coef != null ? alpha.coef * 10000 : null

  const verdict = useMemo(() => {
    if (alpha.t_stat == null) return null
    const t = alpha.t_stat
    if (t >= 2)  return { tone: "#3fb950", text: "alpha is positive and statistically significant after factor controls." }
    if (t <= -2) return { tone: "#f85149", text: "alpha is negative and statistically significant — the machinery is destroying value relative to its factor exposures." }
    return { tone: "#d29922", text: "not distinguishable from zero — the return is explained by factor exposure, not by the signal." }
  }, [alpha.t_stat])

  return (
    <div>
      <div style={regGrid}>
        {/* table */}
        <div style={regTableWrap}>
          <div style={regMeta}>
            <span>{reg.model ?? "Factor model"}</span>
            <span>{reg.cov_type ?? ""}</span>
            <span style={MONO}>R² {reg.r_squared != null ? reg.r_squared.toFixed(3) : "—"}</span>
          </div>
          <table style={regTable}>
            <thead>
              <tr>
                <th style={{ ...regTh, textAlign: "left" }}>Factor</th>
                <th style={regTh}>β</th>
                <th style={regTh}>t</th>
                <th style={{ ...regTh, width: 40 }}>sig</th>
              </tr>
            </thead>
            <tbody>
              <tr style={alphaRow}>
                <td style={{ ...regTd, textAlign: "left", fontWeight: 600, color: "#e6edf3" }}>α (intercept)</td>
                <td style={{ ...regTd, ...MONO }}>{perPeriodBp != null ? perPeriodBp.toFixed(2) + " bp" : "—"}</td>
                <td style={{ ...regTd, ...MONO }}>{alpha.t_stat != null ? alpha.t_stat.toFixed(2) : "—"}</td>
                <td style={{ ...regTd, ...MONO }}>{alpha.p_value != null ? stars(alpha.p_value) : ""}</td>
              </tr>
              {factors.map(f => (
                <tr key={f.name}>
                  <td style={{ ...regTd, textAlign: "left" }}>{f.name}</td>
                  <td style={{ ...regTd, ...MONO }}>{f.beta.toFixed(3)}</td>
                  <td style={{ ...regTd, ...MONO }}>{f.t_stat.toFixed(2)}</td>
                  <td style={{ ...regTd, ...MONO }}>{stars(f.p_value)}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <div style={sigLegend}>*** p&lt;0.01&nbsp;&nbsp;** p&lt;0.05&nbsp;&nbsp;* p&lt;0.10</div>
        </div>

        {/* loadings chart */}
        <div style={loadingsWrap}>
          <div style={cardTitle}>Factor loadings</div>
          <ResponsiveContainer width="100%" height={factors.length * 34 + 20}>
            <BarChart data={factors} layout="vertical" margin={{ top: 0, right: 12, bottom: 0, left: 8 }}>
              <XAxis type="number" tick={{ fill: "#8b949e", fontSize: 10 }} />
              <YAxis type="category" dataKey="name" width={64} tick={{ fill: "#8b949e", fontSize: 11 }} />
              <ReferenceLine x={0} stroke="#444" />
              <Bar dataKey="beta" barSize={14} radius={[0, 2, 2, 0]}>
                {factors.map(f => (
                  <Cell key={f.name}
                    fill={Math.abs(f.t_stat) >= 2 ? (f.beta >= 0 ? "#1f6feb" : "#f85149") : "#30363d"} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
          <div style={sigLegend}>Grey bars: not significant at t ≥ 2.</div>
        </div>
      </div>

      {/* the verdict — the sentence the regression exists to produce */}
      {verdict && (
        <div style={{ ...verdictBox, borderLeftColor: verdict.tone }}>
          <span style={{ ...MONO, color: verdict.tone }}>
            α = {perPeriodBp?.toFixed(1)} bp/period
            {annualizedAlphaBp != null ? ` (≈ ${(annualizedAlphaBp / 100).toFixed(1)}%/yr)` : ""},
            t = {alpha.t_stat?.toFixed(2)}
          </span>
          <span style={verdictText}> — {verdict.text}</span>
        </div>
      )}
    </div>
  )
}

/* ================= Tier 3: robustness ================= */

function BootstrapInterval({ bs, dsr }: { bs: any; dsr: any }) {
  // Layout the interval strip on a padded domain
  const lo = bs.ci_low, hi = bs.ci_high, pt = bs.point
  const pad = (hi - lo) * 0.25 || 0.5
  const min = Math.min(lo, 0) - pad
  const max = hi + pad
  const pct = (v: number) => ((v - min) / (max - min)) * 100

  const zeroInside = min < 0 && max > 0
  const ciCrossesZero = lo <= 0 && hi >= 0

  return (
    <div style={card}>
      <div style={cardTitle}>
        {bs.metric ?? "Sharpe"} — {bs.method ?? "stationary block"} bootstrap
        <span style={cardTitleMeta}>{bs.n_boot ? ` · ${bs.n_boot} resamples` : ""}</span>
      </div>

      <div style={intervalTrackWrap}>
        <div style={intervalTrack} />
        {zeroInside && <div style={{ ...zeroTick, left: `${pct(0)}%` }} />}
        <div style={{
          ...ciBand,
          left: `${pct(lo)}%`,
          width: `${pct(hi) - pct(lo)}%`,
          background: ciCrossesZero ? "rgba(210,153,34,0.25)" : "rgba(63,185,80,0.25)",
          borderColor: ciCrossesZero ? "#d29922" : "#3fb950",
        }} />
        <div style={{ ...pointMarker, left: `${pct(pt)}%` }} title={`Point estimate ${pt.toFixed(2)}`} />
        {dsr?.dsr != null && (
          <div style={{ ...dsrMarker, left: `${pct(dsr.dsr)}%` }} title={`Deflated Sharpe ${dsr.dsr.toFixed(2)}`} />
        )}
      </div>

      <div style={{ ...intervalLabels, ...MONO }}>
        <span>{lo.toFixed(2)}</span>
        <span style={{ color: "#e6edf3" }}>{pt.toFixed(2)}</span>
        <span>{hi.toFixed(2)}</span>
      </div>

      <div style={cardFoot}>
        95% CI [{lo.toFixed(2)}, {hi.toFixed(2)}]
        {ciCrossesZero ? " — interval includes zero." : " — interval excludes zero."}
        {dsr?.dsr != null && (
          <> Deflated Sharpe <span style={MONO}>{dsr.dsr.toFixed(2)}</span>
          {dsr.n_trials ? ` after ${dsr.n_trials} trials` : ""} (hollow marker).</>
        )}
      </div>
    </div>
  )
}

function RollingAlpha({ data }: { data: any[] }) {
  return (
    <div style={card}>
      <div style={cardTitle}>Rolling alpha (252d)</div>
      <ResponsiveContainer width="100%" height={140}>
        <LineChart data={data} margin={{ top: 6, right: 8, bottom: 0, left: 0 }}>
          <XAxis dataKey="date" tick={{ fill: "#8b949e", fontSize: 10 }}
            tickFormatter={(d: string) => new Date(d).getFullYear().toString()}
            minTickGap={40} />
          <YAxis tick={{ fill: "#8b949e", fontSize: 10 }} width={44}
            tickFormatter={(v: number) => (v * 10000).toFixed(0) + "bp"} />
          <ReferenceLine y={0} stroke="#444" strokeDasharray="3 3" />
          <Tooltip content={({ active, payload, label }: any) => {
            if (!active || !payload?.length) return null
            return (
              <div style={tooltipBox}>
                <div style={{ color: "#8b949e" }}>{label}</div>
                <div style={MONO}>{(payload[0].value * 10000).toFixed(1)} bp/period</div>
              </div>
            )
          }} />
          <Line type="monotone" dataKey="alpha" stroke="#a371f7" strokeWidth={1.5} dot={false} />
        </LineChart>
      </ResponsiveContainer>
      <div style={cardFoot}>Stability check: an edge that only exists in one regime shows up here.</div>
    </div>
  )
}

function IcPanel({ run }: { run: any }) {
  const spearman = run?.monitoring_stats?.ic_statistics?.spearman
  const icSummary = run?.monitoring_stats?.ic_summary

  const series = useMemo(() => {
    if (!spearman) return []
    return Object.entries(spearman)
      .map(([date, value]) => ({ date, value: Number(value) }))
      .sort((a, b) => a.date.localeCompare(b.date))
  }, [spearman])

  if (!series.length) return null   // strategy has no cross-sectional signal — IC is a category error

  return (
    <div style={{ ...card, marginTop: 12 }}>
      <div style={cardTitle}>
        Information coefficient
        {icSummary && (
          <span style={{ ...cardTitleMeta, ...MONO }}>
            {" "}· mean {icSummary.mean_ic?.toFixed(4)} · t {icSummary.t_statistic?.toFixed(2)} · hit {(icSummary.hit_rate * 100).toFixed(0)}%
            · n {icSummary.n_observations}
          </span>
        )}
      </div>
      <ResponsiveContainer width="100%" height={140}>
        <LineChart data={series} margin={{ top: 6, right: 8, bottom: 0, left: 0 }}>
          <XAxis dataKey="date" tick={{ fill: "#8b949e", fontSize: 10 }}
            tickFormatter={(d: string) => new Date(d).getFullYear().toString()}
            minTickGap={40} />
          <YAxis tick={{ fill: "#8b949e", fontSize: 10 }} width={40}
            tickFormatter={(v: number) => v.toFixed(2)} />
          <ReferenceLine y={0} stroke="#444" strokeDasharray="3 3" />
          <Tooltip content={({ active, payload, label }: any) => {
            if (!active || !payload?.length) return null
            return (
              <div style={tooltipBox}>
                <div style={{ color: "#8b949e" }}>{label}</div>
                <div style={MONO}>IC {payload[0].value.toFixed(4)}</div>
              </div>
            )
          }} />
          <Line type="monotone" dataKey="value" stroke="#56d364" strokeWidth={1.2} dot={false} />
        </LineChart>
      </ResponsiveContainer>
      <div style={cardFoot}>
        Per-date Spearman rank correlation between signal and forward returns.
        The naive t-stat overstates significance under overlapping horizons — treat it as comparative, not absolute.
      </div>
    </div>
  )
}

/* ================= empty states ================= */

function EmptyState({ line }: { line: string }) {
  return <div style={emptyBox}>{line}</div>
}

function EmptyCard({ title, line }: { title: string; line: string }) {
  return (
    <div style={card}>
      <div style={cardTitle}>{title}</div>
      <div style={emptyBox}>{line}</div>
    </div>
  )
}

/* ================= helpers & styles ================= */

function formatName(name: string) {
  return name.replace("_portfolio", "").replace(/_/g, " ")
}

const container: CSSProperties = {
  background: "#161b22",
  borderRadius: 8,
  border: "1px solid #2a2f3a",
  overflow: "hidden",
  marginTop: 16,
}
const headerBar: CSSProperties = {
  background: "#0d1117",
  borderBottom: "1px solid #2a2f3a",
  padding: "10px 16px",
  display: "flex",
  alignItems: "center",
  justifyContent: "space-between",
}
const headerLabel: CSSProperties = {
  fontSize: 12, fontWeight: 600, color: "#e6edf3", letterSpacing: "0.3px",
}
const headerStrategy: CSSProperties = { fontSize: 11, color: "#8b949e" }

const tier: CSSProperties = { padding: "14px 16px", borderBottom: "1px solid #21262d" }
const tierEyebrow: CSSProperties = {
  display: "flex", alignItems: "baseline", gap: 8, marginBottom: 10,
}
const tierNum: CSSProperties = {
  fontSize: 10, color: "#484f58", border: "1px solid #2a2f3a",
  borderRadius: 3, padding: "0 5px", lineHeight: "16px",
  fontFamily: "ui-monospace, monospace",
}
const tierName: CSSProperties = {
  fontSize: 11, fontWeight: 600, color: "#e6edf3",
  textTransform: "uppercase", letterSpacing: "0.8px",
}
const tierQuestion: CSSProperties = { fontSize: 11, color: "#8b949e", fontStyle: "italic" }

const strip: CSSProperties = {
  display: "flex", border: "1px solid #21262d", borderRadius: 6, overflow: "hidden",
}
const stripCell: CSSProperties = {
  flex: 1, padding: "8px 12px", borderRight: "1px solid #21262d", minWidth: 0,
}
const stripLabel: CSSProperties = { fontSize: 10, color: "#8b949e", marginBottom: 2 }
const stripValue: CSSProperties = { fontSize: 15, color: "#e6edf3", textAlign: "right" }
const stripNote: CSSProperties = { fontSize: 10, color: "#484f58", lineHeight: 1.4 }

const regGrid: CSSProperties = {
  display: "grid", gridTemplateColumns: "minmax(300px, 1.2fr) minmax(240px, 1fr)", gap: 16,
}
const regTableWrap: CSSProperties = { minWidth: 0 }
const regMeta: CSSProperties = {
  display: "flex", gap: 14, fontSize: 10, color: "#8b949e", marginBottom: 6,
}
const regTable: CSSProperties = { width: "100%", borderCollapse: "collapse", fontSize: 12 }
const regTh: CSSProperties = {
  textAlign: "right", padding: "5px 8px", color: "#8b949e", fontWeight: 500,
  fontSize: 10, textTransform: "uppercase", letterSpacing: "0.5px",
  borderBottom: "1px solid #2a2f3a",
}
const regTd: CSSProperties = {
  textAlign: "right", padding: "5px 8px", color: "#c9d1d9",
  borderBottom: "1px solid #21262d",
}
const alphaRow: CSSProperties = { background: "rgba(56,139,253,0.06)" }
const sigLegend: CSSProperties = { fontSize: 9, color: "#484f58", marginTop: 6 }

const loadingsWrap: CSSProperties = { minWidth: 0 }
const cardTitle: CSSProperties = {
  fontSize: 11, fontWeight: 600, color: "#e6edf3", marginBottom: 8,
}
const cardTitleMeta: CSSProperties = { fontWeight: 400, color: "#8b949e", fontSize: 10 }

const verdictBox: CSSProperties = {
  marginTop: 14,
  padding: "10px 14px",
  background: "#0d1117",
  borderRadius: 6,
  borderLeft: "3px solid",
  fontSize: 12.5,
  lineHeight: 1.5,
}
const verdictText: CSSProperties = { color: "#c9d1d9" }

const robustGrid: CSSProperties = {
  display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(300px, 1fr))", gap: 12,
}
const card: CSSProperties = {
  border: "1px solid #21262d", borderRadius: 6, padding: "12px 14px", minWidth: 0,
}
const cardFoot: CSSProperties = { fontSize: 10, color: "#8b949e", marginTop: 8, lineHeight: 1.5 }

const intervalTrackWrap: CSSProperties = {
  position: "relative", height: 28, margin: "18px 6px 4px",
}
const intervalTrack: CSSProperties = {
  position: "absolute", top: "50%", left: 0, right: 0, height: 2,
  background: "#21262d", transform: "translateY(-50%)",
}
const ciBand: CSSProperties = {
  position: "absolute", top: "50%", height: 12, transform: "translateY(-50%)",
  border: "1px solid", borderRadius: 3,
}
const pointMarker: CSSProperties = {
  position: "absolute", top: "50%", width: 8, height: 8,
  background: "#e6edf3", borderRadius: "50%",
  transform: "translate(-50%, -50%)", zIndex: 2,
}
const dsrMarker: CSSProperties = {
  position: "absolute", top: "50%", width: 8, height: 8,
  background: "#0d1117", border: "1.5px solid #e6edf3", borderRadius: "50%",
  transform: "translate(-50%, -50%)", zIndex: 2,
}
const zeroTick: CSSProperties = {
  position: "absolute", top: 2, bottom: 2, width: 1, background: "#f85149",
  opacity: 0.5,
}
const intervalLabels: CSSProperties = {
  display: "flex", justifyContent: "space-between", fontSize: 10, color: "#8b949e",
  padding: "0 2px",
}

const emptyBox: CSSProperties = {
  padding: "18px 14px",
  fontSize: 11.5,
  color: "#8b949e",
  lineHeight: 1.6,
  background: "#0d1117",
  border: "1px dashed #2a2f3a",
  borderRadius: 6,
}
const tooltipBox: CSSProperties = {
  background: "#161b22", border: "1px solid #2a2f3a",
  padding: "6px 10px", fontSize: 11, borderRadius: 6, color: "#e6edf3",
}
