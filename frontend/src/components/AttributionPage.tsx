import { useMemo } from "react"
import type { CSSProperties } from "react"
import {
  ResponsiveContainer, LineChart, Line, XAxis, YAxis, ReferenceLine,
  BarChart, Bar, Cell, Tooltip, Legend,
} from "recharts"

/**
 * Performance Attribution — where the return came from, over time.
 *
 * Expected payload on the selected run:
 *
 * run.statistics.attribution = {
 *   contributions: [                       // full-period return decomposition
 *     { name: "Market",   value: 0.142 },  // annualized contribution
 *     { name: "Value",    value: 0.048 },
 *     { name: "Quality",  value: 0.021 },
 *     { name: "Residual", value: 0.009 },
 *   ],
 *   rolling_loadings: [                    // 252d rolling betas
 *     { date: "2021-06-01", "Mkt-RF": 0.97, "HML": 0.21, "RMW": 0.08, ... },
 *   ],
 * }
 */

const FACTOR_COLORS = ["#1f6feb", "#3fb950", "#d29922", "#a371f7", "#56d364", "#f85149"]

const MONO: CSSProperties = {
  fontFamily: "ui-monospace, 'SF Mono', 'JetBrains Mono', Menlo, monospace",
  fontVariantNumeric: "tabular-nums",
}

interface Props {
  runs: any[]
  selectedRun: any | null
  onSelectRun: (run: any) => void
}

export default function AttributionPage({ runs, selectedRun, onSelectRun }: Props) {
  const attribution = selectedRun?.statistics?.attribution
  const contributions: any[] = attribution?.contributions ?? []
  const rolling: any[] = attribution?.rolling_loadings ?? []

  const factorKeys = useMemo(() => {
    if (!rolling.length) return []
    return Object.keys(rolling[0]).filter(k => k !== "date")
  }, [rolling])

  const totalReturn = contributions.reduce((s, c) => s + c.value, 0)

  return (
    <div style={page}>
      <div style={pageHeader}>
        <div>
          <h1 style={pageTitle}>Performance Attribution</h1>
          <p style={pageSub}>
            Return decomposed into factor contributions and residual. What you're paying the machinery for
            is the residual — everything else is purchasable exposure.
          </p>
        </div>
        {runs.length > 0 && (
          <select
            style={runSelect}
            value={selectedRun?.run_id ?? ""}
            onChange={e => {
              const run = runs.find(r => r.run_id === e.target.value)
              if (run) onSelectRun(run)
            }}
          >
            {runs.map(r => (
              <option key={r.run_id} value={r.run_id}>{formatName(r.strategy_name)}</option>
            ))}
          </select>
        )}
      </div>

      {!selectedRun && (
        <div style={emptyBox}>Run a strategy suite in the Lab, then select a run to attribute.</div>
      )}

      {selectedRun && !attribution && (
        <div style={emptyBox}>
          Attribution not computed for {formatName(selectedRun.strategy_name)} —
          extend /statistics/{"{run_id}"} with the rolling regression and contribution decomposition to populate this page.
        </div>
      )}

      {contributions.length > 0 && (
        <div style={card}>
          <div style={cardTitle}>
            Full-period return decomposition
            <span style={{ ...cardMeta, ...MONO }}> · total {(totalReturn * 100).toFixed(1)}%</span>
          </div>
          <ResponsiveContainer width="100%" height={contributions.length * 40 + 30}>
            <BarChart data={contributions} layout="vertical" margin={{ top: 4, right: 24, bottom: 0, left: 8 }}>
              <XAxis type="number" tick={{ fill: "#8b949e", fontSize: 10 }}
                tickFormatter={(v: number) => (v * 100).toFixed(0) + "%"} />
              <YAxis type="category" dataKey="name" width={76} tick={{ fill: "#8b949e", fontSize: 11 }} />
              <ReferenceLine x={0} stroke="#444" />
              <Tooltip content={({ active, payload }: any) => {
                if (!active || !payload?.length) return null
                const p = payload[0]
                return (
                  <div style={tooltipBox}>
                    <div>{p.payload.name}</div>
                    <div style={MONO}>{(p.value * 100).toFixed(2)}% of return</div>
                  </div>
                )
              }} />
              <Bar dataKey="value" barSize={16} radius={[0, 2, 2, 0]}>
                {contributions.map((c, i) => (
                  <Cell key={c.name}
                    fill={c.name.toLowerCase() === "residual" ? "#e6edf3" : FACTOR_COLORS[i % FACTOR_COLORS.length]} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
          <div style={cardFoot}>
            The residual bar (white) is the part no factor explains — the strategy's own contribution.
          </div>
        </div>
      )}

      {rolling.length > 0 && (
        <div style={card}>
          <div style={cardTitle}>Rolling factor loadings (252d)</div>
          <ResponsiveContainer width="100%" height={260}>
            <LineChart data={rolling} margin={{ top: 8, right: 12, bottom: 0, left: 0 }}>
              <XAxis dataKey="date" tick={{ fill: "#8b949e", fontSize: 10 }}
                tickFormatter={(d: string) => new Date(d).getFullYear().toString()} minTickGap={50} />
              <YAxis tick={{ fill: "#8b949e", fontSize: 10 }} width={40}
                tickFormatter={(v: number) => v.toFixed(1)} />
              <ReferenceLine y={0} stroke="#444" strokeDasharray="3 3" />
              <Tooltip content={({ active, payload, label }: any) => {
                if (!active || !payload?.length) return null
                return (
                  <div style={tooltipBox}>
                    <div style={{ color: "#8b949e", marginBottom: 4 }}>{label}</div>
                    {payload.map((e: any) => (
                      <div key={e.dataKey} style={{ color: e.stroke, ...MONO }}>
                        {e.dataKey}: {e.value?.toFixed(3)}
                      </div>
                    ))}
                  </div>
                )
              }} />
              <Legend wrapperStyle={{ fontSize: 11 }} />
              {factorKeys.map((k, i) => (
                <Line key={k} type="monotone" dataKey={k}
                  stroke={FACTOR_COLORS[i % FACTOR_COLORS.length]}
                  strokeWidth={1.4} dot={false} connectNulls />
              ))}
            </LineChart>
          </ResponsiveContainer>
          <div style={cardFoot}>
            Drifting loadings mean the strategy's factor identity changes over time —
            a value tilt that appears only after 2020 is a regime artifact, not a design.
          </div>
        </div>
      )}
    </div>
  )
}

function formatName(name: string) {
  return name.replace("_portfolio", "").replace(/_/g, " ")
}

const page: CSSProperties = { padding: "20px 24px", maxWidth: 1200, margin: "0 auto" }
const pageHeader: CSSProperties = {
  display: "flex", alignItems: "flex-start", justifyContent: "space-between",
  gap: 16, marginBottom: 16,
}
const pageTitle: CSSProperties = {
  fontSize: 18, fontWeight: 600, color: "#e6edf3", margin: 0, letterSpacing: "0.2px",
}
const pageSub: CSSProperties = {
  fontSize: 12, color: "#8b949e", margin: "6px 0 0", maxWidth: 560, lineHeight: 1.5,
}
const runSelect: CSSProperties = {
  background: "#161b22", color: "#e6edf3", border: "1px solid #2a2f3a",
  borderRadius: 6, padding: "6px 10px", fontSize: 12, flexShrink: 0,
}
const card: CSSProperties = {
  background: "#161b22", border: "1px solid #2a2f3a", borderRadius: 8,
  padding: "14px 16px", marginBottom: 16,
}
const cardTitle: CSSProperties = { fontSize: 12, fontWeight: 600, color: "#e6edf3", marginBottom: 10 }
const cardMeta: CSSProperties = { fontWeight: 400, color: "#8b949e", fontSize: 11 }
const cardFoot: CSSProperties = { fontSize: 10.5, color: "#8b949e", marginTop: 8, lineHeight: 1.5 }
const emptyBox: CSSProperties = {
  padding: "28px 20px", fontSize: 12.5, color: "#8b949e", lineHeight: 1.6,
  background: "#161b22", border: "1px dashed #2a2f3a", borderRadius: 8,
}
const tooltipBox: CSSProperties = {
  background: "#161b22", border: "1px solid #2a2f3a",
  padding: "6px 10px", fontSize: 11, borderRadius: 6, color: "#e6edf3",
}
