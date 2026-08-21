import { useState, useMemo } from "react"
import type { CSSProperties } from "react"
import type React from "react"
import { getEffectiveSummary } from "../utils/metricsUtils"
import type { DateWindow } from "../utils/metricsUtils"

type SortKey = "strategy_name" | "return" | "volatility" | "sharpe_ratio" | "max_drawdown" | "turnover"

const COLORS = ["#3fb950", "#1f6feb", "#d29922", "#f85149", "#a371f7", "#56d364"]

const TOOLTIPS: Record<string, string> = {
  Return: "Annualized total return over the backtest period.",
  Vol: "Annualized standard deviation of returns. Measures total variability — both up and down.",
  Sharpe: "Annualized excess return divided by annualized volatility. The primary risk-adjusted performance measure — higher is better.",
  "Max DD": "Largest peak-to-trough decline over the backtest. The worst-case loss an investor would have experienced.",
  Turnover: "Average annual portfolio turnover. High turnover increases transaction costs and drag on returns.",
}

interface Props {
  runs: any[]
  onSelect: (run: any) => void
  selectedRunId?: string | null
  pinnedIds: Set<string>
  onPin: (run: any) => void
  dateWindow: DateWindow | null
}

export default function StrategyGrid({ runs, onSelect, selectedRunId, pinnedIds, onPin, dateWindow }: Props) {
  const [sortKey, setSortKey] = useState<SortKey>("sharpe_ratio")
  const [ascending, setAscending] = useState(false)

  const handleSort = (key: SortKey) => {
    if (sortKey === key) setAscending(!ascending)
    else { setSortKey(key); setAscending(false) }
  }

  // Precompute effective summaries for all runs given current window
  const effectiveSummaries = useMemo(() => {
    const map: Record<string, any> = {}
    runs.forEach(run => {
      map[run.run_id] = getEffectiveSummary(run, dateWindow)
    })
    return map
  }, [runs, dateWindow])

  const sortedRuns = useMemo(() => {
    return [...runs].sort((a, b) => {
      const getSummaryVal = (run: any) => {
        const s = effectiveSummaries[run.run_id]
        if (sortKey === "strategy_name") return run.strategy_name
        return s?.[sortKey] ?? null
      }
      const valA = getSummaryVal(a)
      const valB = getSummaryVal(b)
      if (valA == null) return 1
      if (valB == null) return -1
      if (typeof valA === "string") return ascending ? valA.localeCompare(valB) : valB.localeCompare(valA)
      return ascending ? valA - valB : valB - valA
    })
  }, [runs, sortKey, ascending, effectiveSummaries])

  return (
    <div style={outerContainer}>
      <div style={headerBar}>
        <span style={headerLabel}>Strategy Overview</span>
        {dateWindow && (
          <span style={windowIndicator}>
            {formatDate(dateWindow.start)} – {formatDate(dateWindow.end)}
          </span>
        )}
      </div>
      <div style={innerContainer}>
        <table style={table}>
          <thead>
            <tr style={headerRow}>
              <th style={leftHeader} onClick={() => handleSort("strategy_name")}>Strategy</th>
              <SortHeader label="Return"   k="return"       sortKey={sortKey} ascending={ascending} onSort={handleSort} />
              <SortHeader label="Vol"      k="volatility"   sortKey={sortKey} ascending={ascending} onSort={handleSort} />
              <SortHeader label="Sharpe"   k="sharpe_ratio" sortKey={sortKey} ascending={ascending} onSort={handleSort} />
              <SortHeader label="Max DD"   k="max_drawdown" sortKey={sortKey} ascending={ascending} onSort={handleSort} />
              <SortHeader label="Turnover" k="turnover"     sortKey={sortKey} ascending={ascending} onSort={handleSort} />
              <th style={rightHeader}></th>
            </tr>
          </thead>
          <tbody>
            {sortedRuns.map((run: any) => {
              const s = effectiveSummaries[run.run_id]
              const colorIdx = runs.findIndex((r: any) => r.run_id === run.run_id)
              const isPinned = pinnedIds?.has(run.run_id)
              const isSelected = run.run_id === selectedRunId
              return (
                <tr
                  key={run.run_id}
                  onClick={() => onSelect(run)}
                  style={isSelected ? selectedRow : row}
                  aria-selected={isSelected}
                >
                  <td style={leftCell}>
                    <span style={{ ...colorDot, backgroundColor: COLORS[colorIdx % COLORS.length] }} />
                    {formatStrategyName(run.strategy_name)}
                    {isPinned && <span style={pinnedBadge}>pinned</span>}
                  </td>
                  <td style={rightCellGreen(s?.return)}>{formatPct(s?.return)}</td>
                  <td style={rightCell}>{formatPct(s?.volatility)}</td>
                  <td style={rightCell}>{formatNumber(s?.sharpe_ratio)}</td>
                  <td style={rightCellRed(s?.max_drawdown)}>{formatPct(s?.max_drawdown)}</td>
                  <td style={rightCell}>{formatNumber(s?.turnover)}</td>
                  <td style={rightCell}>
                    <button
                      style={isPinned ? unpinBtn : pinBtn}
                      onClick={(e) => { e.stopPropagation(); onPin(run) }}
                    >
                      {isPinned ? "unpin" : "pin"}
                    </button>
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </div>
  )
}

function SortHeader({ label, k, sortKey, ascending, onSort }: any) {
  const active = sortKey === k
  return (
    <th style={{ ...rightHeader, color: active ? "#e6edf3" : "#8b949e" }} onClick={() => onSort(k)}>
      <MetricTooltip label={label}>
        <span>
          {label}
          {TOOLTIPS[label] && <span style={dotStyle}>?</span>}
          {active && (ascending ? " ↑" : " ↓")}
        </span>
      </MetricTooltip>
    </th>
  )
}

function MetricTooltip({ label, children }: { label: string; children: React.ReactNode }) {
  const [pos, setPos] = useState<{ x: number; y: number } | null>(null)
  const tip = TOOLTIPS[label]
  return (
    <div style={{ position: "relative", display: "inline-block" }}
      onMouseEnter={(e) => tip && setPos({ x: e.clientX, y: e.clientY })}
      onMouseMove={(e) => tip && setPos({ x: e.clientX, y: e.clientY })}
      onMouseLeave={() => setPos(null)}
    >
      {children}
      {pos && tip && (
        <div style={{ ...tooltipBox, top: pos.y + 12, left: Math.min(pos.x + 8, window.innerWidth - 250) }}>
          <strong style={{ display: "block", marginBottom: 4, color: "#e6edf3" }}>{label}</strong>
          {tip}
        </div>
      )}
    </div>
  )
}

function formatDate(d: string): string {
  return new Date(d).toLocaleDateString("en-US", { year: "numeric", month: "short" })
}

function formatStrategyName(name: string) {
  return name.replace("_portfolio", "").replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase())
}
function formatPct(v: number | null | undefined) { return v == null ? "-" : (v * 100).toFixed(2) + "%" }
function formatNumber(v: number | null | undefined) { return v == null ? "-" : v.toFixed(2) }

const outerContainer: CSSProperties = { background: "#161b22", borderRadius: 8, border: "1px solid #2a2f3a", overflow: "hidden" }
const headerBar: CSSProperties = { background: "#0d1117", borderBottom: "1px solid #2a2f3a", padding: "10px 16px", display: "flex", alignItems: "center", justifyContent: "space-between" }
const headerLabel: CSSProperties = { fontSize: 12, fontWeight: 600, color: "#e6edf3", letterSpacing: "0.3px" }
const windowIndicator: CSSProperties = { fontSize: 10, color: "#388bfd", fontWeight: 500 }
const innerContainer: CSSProperties = { padding: "0" }
const table: CSSProperties = { width: "100%", borderCollapse: "collapse" }
const headerRow: CSSProperties = { borderBottom: "1px solid #2a2f3a" }
const leftHeader: CSSProperties = { padding: "8px 10px", textAlign: "left", fontSize: 12, fontWeight: 600, color: "#8b949e", cursor: "pointer", userSelect: "none" }
const rightHeader: CSSProperties = { padding: "8px 10px", textAlign: "right", fontSize: 12, fontWeight: 600, cursor: "pointer", userSelect: "none" }
const row: CSSProperties = { borderBottom: "1px solid #21262d", cursor: "pointer" }
const selectedRow: CSSProperties = {
  ...row,
  background: "rgba(56,139,253,0.10)",
  boxShadow: "inset 2px 0 0 #388bfd",
}
const leftCell: CSSProperties = { padding: "8px 10px", textAlign: "left", fontSize: 12, display: "flex", alignItems: "flex-start", gap: 6 }
const rightCell: CSSProperties = { padding: "8px 10px", textAlign: "right", fontSize: 12 }
const rightCellGreen = (val: number | null | undefined): CSSProperties => ({
  ...rightCell, color: val != null && val > 0 ? "#3fb950" : "#f85149"
})
const rightCellRed = (_: number | null | undefined): CSSProperties => ({
  ...rightCell, color: "#f85149"
})
const colorDot: CSSProperties = {
  display: "inline-block", width: 8, height: 8, borderRadius: "50%", flexShrink: 0, marginTop: 3
}
const dotStyle: CSSProperties = {
  display: "inline-flex", alignItems: "center", justifyContent: "center",
  width: 12, height: 12, borderRadius: "50%", background: "#30363d",
  color: "#8b949e", fontSize: 9, fontWeight: 700, marginLeft: 3, verticalAlign: "middle"
}
const tooltipBox: CSSProperties = {
  position: "fixed", top: "auto", left: "auto",
  width: 230, background: "#161b22", border: "1px solid #30363d",
  borderRadius: 6, padding: "10px 12px", fontSize: 12,
  color: "#8b949e", lineHeight: 1.5, zIndex: 9999,
  boxShadow: "0 4px 16px rgba(0,0,0,0.5)", pointerEvents: "none",
  textAlign: "left", fontWeight: 400
}
const pinBtn: CSSProperties = {
  background: "none", border: "1px solid #30363d", borderRadius: 3,
  color: "#8b949e", fontSize: 10, cursor: "pointer", padding: "1px 6px"
}
const unpinBtn: CSSProperties = {
  ...pinBtn, border: "1px solid #388bfd", color: "#388bfd"
}
const pinnedBadge: CSSProperties = {
  fontSize: 9, color: "#388bfd", border: "1px solid #388bfd",
  borderRadius: 3, padding: "0 4px", marginLeft: 4
}
