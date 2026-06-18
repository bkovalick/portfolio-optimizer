import { useState, useMemo, useRef } from "react"
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  ResponsiveContainer,
  Tooltip,
  ReferenceLine
} from "recharts"
import type { CSSProperties } from "react"
import { getCachedSeries } from "../utils/metricsUtils"
import { getCachedIcSeries } from "../utils/metricsUtils"
import type { DateWindow } from "../utils/metricsUtils"

const COLORS = [
  "#3fb950",
  "#1f6feb",
  "#d29922",
  "#f85149",
  "#a371f7",
  "#56d364"
]

interface Props {
  runs: any[]
  onWindowChange: (window: DateWindow | null) => void
  dateWindow: DateWindow | null
}

export default function StrategyDetails({ runs, onWindowChange, dateWindow }: Props) {
  const [sliderStart, setSliderStart] = useState(0)
  const [sliderEnd, setSliderEnd] = useState(100)
  const trackRef = useRef<HTMLDivElement>(null)
  const dragging = useRef<"start" | "end" | null>(null)

  if (!runs || runs.length === 0) return null

  // Build unified date index across all runs — uses cache, no repeated deserialization
  const allDates = useMemo(() => {
    const dateSet = new Set<string>()
    runs.forEach(run => {
      getCachedSeries(run).wealth.forEach(p => dateSet.add(p.date))
    })
    return Array.from(dateSet).sort()
  }, [runs])

  const allIcDates = useMemo(() => {
    const dateSet = new Set<string>()
    runs.forEach(run => {
      getCachedIcSeries(run).ic_series.forEach(p => dateSet.add(p.date))
    })
    return Array.from(dateSet).sort()
  }, [runs])  

  // Build chart data — each run rebases to its own first available date
  const data = useMemo(() => {
    const runMaps: Record<string, Record<string, number>> = {}
    const rebaseDates: Record<string, string> = {}

    runs.forEach(run => {
      const map: Record<string, number> = {}
      getCachedSeries(run).wealth.forEach(p => { map[p.date] = p.value })
      runMaps[run.run_id] = map
      const sortedDates = Object.keys(map).sort()
      rebaseDates[run.run_id] = dateWindow?.start
        ? (sortedDates.find(d => d >= dateWindow.start) ?? sortedDates[0])
        : sortedDates[0]
    })

    return allDates.map(date => {
      const row: any = { date }
      runs.forEach(run => {
        const map = runMaps[run.run_id]
        if (!map) return
        const rebaseValue = map[rebaseDates[run.run_id]] ?? null
        const currentValue = map[date] ?? null
        if (rebaseValue && currentValue) row[run.run_id] = currentValue / rebaseValue
      })
      return row
    })
  }, [runs, allDates, dateWindow])

    // Build ic chart data — each run rebases to its own first available date
  const icData = useMemo(() => {
    const runMaps: Record<string, Record<string, number>> = {}
    const rebaseDates: Record<string, string> = {}

    runs.forEach(run => {
      const map: Record<string, number> = {}
      getCachedIcSeries(run).ic_series.forEach(p => { map[p.date] = p.value })
      runMaps[run.run_id] = map
      const sortedDates = Object.keys(map).sort()
      rebaseDates[run.run_id] = dateWindow?.start
        ? (sortedDates.find(d => d >= dateWindow.start) ?? sortedDates[0])
        : sortedDates[0]
    })

    return allIcDates.map(date => {
      const row: any = { date }
      runs.forEach(run => {
        const map = runMaps[run.run_id]
        if (!map) return
        const rebaseValue = map[rebaseDates[run.run_id]] ?? null
        const currentValue = map[date] ?? null
        if (rebaseValue && currentValue) row[run.run_id] = currentValue / rebaseValue
      })
      return row
    })
  }, [runs, allIcDates, dateWindow])

  // Downsample for chart rendering — max 500 points
  const chartData = useMemo(() => {
    if (data.length <= 500) return data
    const step = Math.ceil(data.length / 500)
    return data.filter((_: any, i: number) => i % step === 0 || i === data.length - 1)
  }, [data])

  const icChartData = useMemo(() => {
    if (icData.length <= 500) return icData
    const step = Math.ceil(icData.length / 500)
    return icData.filter((_: any, i: number) => i % step === 0 || i === icData.length - 1)
  }, [icData])

  const visibleData = useMemo(() => {
    if (!dateWindow) return chartData
    return chartData.filter((d: any) => d.date >= dateWindow.start && d.date <= dateWindow.end)
  }, [chartData, dateWindow])

  const icVisibleData = icChartData

  const getDateAtPct = (pct: number) => {
    const idx = Math.round(pct / 100 * (allDates.length - 1))
    return allDates[Math.min(Math.max(idx, 0), allDates.length - 1)]
  }

  const getPctFromMouseX = (clientX: number) => {
    if (!trackRef.current) return 0
    const rect = trackRef.current.getBoundingClientRect()
    return Math.min(100, Math.max(0, ((clientX - rect.left) / rect.width) * 100))
  }

  const handleThumbMouseDown = (e: React.MouseEvent, thumb: "start" | "end") => {
    e.preventDefault()
    dragging.current = thumb

    const onMove = (ev: MouseEvent) => {
      const pct = getPctFromMouseX(ev.clientX)
      if (dragging.current === "start") {
        const val = Math.min(pct, sliderEnd - 5)
        setSliderStart(val)
        onWindowChange({ start: getDateAtPct(val), end: getDateAtPct(sliderEnd) })
      } else {
        const val = Math.max(pct, sliderStart + 5)
        setSliderEnd(val)
        onWindowChange({ start: getDateAtPct(sliderStart), end: getDateAtPct(val) })
      }
    }

    const onUp = () => {
      dragging.current = null
      window.removeEventListener("mousemove", onMove)
      window.removeEventListener("mouseup", onUp)
    }

    window.addEventListener("mousemove", onMove)
    window.addEventListener("mouseup", onUp)
  }

  const handleTrackMouseDown = (e: React.MouseEvent) => {
    const pct = getPctFromMouseX(e.clientX)
    const distStart = Math.abs(pct - sliderStart)
    const distEnd = Math.abs(pct - sliderEnd)
    handleThumbMouseDown(e, distStart < distEnd ? "start" : "end")
  }

  const handleReset = () => {
    setSliderStart(0)
    setSliderEnd(100)
    onWindowChange(null)
  }

  const isWindowed = sliderStart > 0 || sliderEnd < 100

  return (
    <div style={container}>
      {/* Header */}
      <div style={headerBar}>
        <span style={headerLabel}>Cumulative Performance (Log Scale)</span>
        {isWindowed ? (
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <span style={windowBadge}>
              {formatDate(getDateAtPct(sliderStart))} → {formatDate(getDateAtPct(sliderEnd))}
            </span>
            <span style={rebaseNote}>Rebased</span>
            <button style={resetBtn} onClick={handleReset}>Reset</button>
          </div>
        ) : (
          <span style={hintText}>Drag sliders below to zoom</span>
        )}
      </div>

      {/* Chart */}
      <div style={{ height: 300, padding: "12px 16px 0" }}>
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={visibleData} margin={{ top: 4, right: 8, bottom: 0, left: 0 }}>
            <XAxis
              dataKey="date"
              tickFormatter={(d: string) => new Date(d).getFullYear().toString()}
              interval="preserveStartEnd"
              tick={{ fill: "#8b949e", fontSize: 11 }}
              minTickGap={50}
            />
            <YAxis
              scale="log"
              domain={["auto", "auto"]}
              tickFormatter={(v) => v.toFixed(1) + "x"}
              tick={{ fill: "#8b949e", fontSize: 11 }}
              width={40}
            />
            <Tooltip
              content={({ active, payload, label }: any) => {
                if (!active || !payload?.length) return null
                return (
                  <div style={{
                    background: "#161b22", border: "1px solid #2a2f3a",
                    padding: "8px 12px", fontSize: 12, borderRadius: 6
                  }}>
                    <div style={{ color: "#8b949e", marginBottom: 6 }}>{formatDate(label)}</div>
                    {payload.map((entry: any) => {
                      const run = runs.find((r: any) => r.run_id === entry.dataKey)
                      const name = run ? formatStrategyName(run.strategy_name) : entry.dataKey
                      return (
                        <div key={entry.dataKey} style={{ color: entry.stroke, marginBottom: 2 }}>
                          {name}: {entry.value?.toFixed(3)}x
                        </div>
                      )
                    })}
                  </div>
                )
              }}
            />
            {runs.map((run: any, i: number) => (
              <Line
                key={run.run_id}
                type="monotone"
                dataKey={run.run_id}
                stroke={COLORS[i % COLORS.length]}
                strokeWidth={1.5}
                dot={false}
                connectNulls={false}
              />
            ))}
          </LineChart>
        </ResponsiveContainer>
      </div>

      {runs.some((run: any) => getCachedIcSeries(run).ic_series.length > 0) &&  (<>
      {/* Header */}
      <div style={headerBar}>
        <span style={headerLabel}>Information Coefficient Analysis</span>
        {isWindowed ? (
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <span style={windowBadge}>
              {formatDate(getDateAtPct(sliderStart))} → {formatDate(getDateAtPct(sliderEnd))}
            </span>
            <span style={rebaseNote}>Rebased</span>
            <button style={resetBtn} onClick={handleReset}>Reset</button>
          </div>
        ) : (
          <span style={hintText}>Drag sliders below to zoom</span>
        )}
      </div>

      {/* Place new chart here */}
      <div style={{ height: 300, padding: "12px 16px 0" }}>
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={icVisibleData} margin={{ top: 4, right: 8, bottom: 0, left: 0 }}>
            <XAxis
              dataKey="date"
              tickFormatter={(d: string) => new Date(d).getFullYear().toString()}
              interval="preserveStartEnd"
              tick={{ fill: "#8b949e", fontSize: 11 }}
              minTickGap={50}
            />
            <YAxis
              domain={["auto", "auto"]}
              tickFormatter={(v) => v.toFixed(2)}
              tick={{ fill: "#8b949e", fontSize: 11 }}
              width={40}
            />
            <Tooltip
              content={({ active, payload, label }: any) => {
                if (!active || !payload?.length) return null
                return (
                  <div style={{
                    background: "#161b22", border: "1px solid #2a2f3a",
                    padding: "8px 12px", fontSize: 12, borderRadius: 6
                  }}>
                    <div style={{ color: "#8b949e", marginBottom: 6 }}>{formatDate(label)}</div>
                    {payload.map((entry: any) => {
                      const run = runs.find((r: any) => r.run_id === entry.dataKey)
                      const name = run ? formatStrategyName(run.strategy_name) : entry.dataKey
                      return (
                        <div key={entry.dataKey} style={{ color: entry.stroke, marginBottom: 2 }}>
                          {name}: {entry.value?.toFixed(3)}
                        </div>
                      )
                    })}
                  </div>
                )
              }}
            />
            <ReferenceLine y={0} stroke="#444" strokeDasharray="3 3" />
            {runs.map((run: any, i: number) => (
              <Line
                key={run.run_id}
                type="monotone"
                dataKey={run.run_id}
                stroke={COLORS[i % COLORS.length]}
                strokeWidth={1.5}
                dot={false}
                connectNulls={false}
              />
            ))}            
          </LineChart>
        </ResponsiveContainer>
      </div>
      </>)}

      {/* Dual drag slider */}
      <div style={sliderContainer}>
        <div
          ref={trackRef}
          style={sliderTrackWrapper}
          onMouseDown={handleTrackMouseDown}
        >
          {/* Background track */}
          <div style={sliderTrackBg} />
          {/* Active range fill */}
          <div style={{
            position: "absolute",
            height: 4,
            background: "#238636",
            borderRadius: 2,
            pointerEvents: "none",
            zIndex: 2,
            left: `${sliderStart}%`,
            width: `${sliderEnd - sliderStart}%`
          }} />
          {/* Start thumb */}
          <div
            style={{ ...thumbStyle, left: `${sliderStart}%` }}
            onMouseDown={(e) => { e.stopPropagation(); handleThumbMouseDown(e, "start") }}
          />
          {/* End thumb */}
          <div
            style={{ ...thumbStyle, left: `${sliderEnd}%` }}
            onMouseDown={(e) => { e.stopPropagation(); handleThumbMouseDown(e, "end") }}
          />
        </div>
        <div style={sliderLabels}>
          <span style={sliderLabelText}>{formatDate(allDates[0])}</span>
          <span style={sliderLabelText}>{formatDate(allDates[allDates.length - 1])}</span>
        </div>
      </div>

      {/* Legend */}
      <div style={legendContainer}>
        {runs.map((run: any, i: number) => (
          <div key={run.run_id} style={legendItem}>
            <span style={{ ...legendDot, backgroundColor: COLORS[i % COLORS.length] }} />
            <span style={legendText}>{formatStrategyName(run.strategy_name)}</span>
          </div>
        ))}
      </div>
    </div>
  )
}

function formatDate(d: string): string {
  if (!d) return ""
  return new Date(d).toLocaleDateString("en-US", { year: "numeric", month: "short" })
}

function formatStrategyName(name: string) {
  return name.replace("_portfolio", "").replace(/_/g, " ").replace(/\b\w/g, c => c.toUpperCase())
}

const container: CSSProperties = {
  background: "#161b22", borderRadius: 8,
  border: "1px solid #2a2f3a", overflow: "hidden", marginTop: 16
}
const headerBar: CSSProperties = {
  background: "#0d1117", borderBottom: "1px solid #2a2f3a",
  padding: "10px 16px", display: "flex", alignItems: "center", justifyContent: "space-between"
}
const headerLabel: CSSProperties = {
  fontSize: 12, fontWeight: 600, color: "#e6edf3", letterSpacing: "0.3px"
}
const windowBadge: CSSProperties = { fontSize: 11, color: "#388bfd", fontWeight: 600 }
const rebaseNote: CSSProperties = { fontSize: 10, color: "#8b949e", fontStyle: "italic" }
const resetBtn: CSSProperties = {
  background: "none", border: "1px solid #30363d", borderRadius: 3,
  color: "#8b949e", fontSize: 10, cursor: "pointer", padding: "1px 8px"
}
const hintText: CSSProperties = { fontSize: 10, color: "#8b949e", fontStyle: "italic" }
const sliderContainer: CSSProperties = { padding: "16px 20px 4px" }
const sliderTrackWrapper: CSSProperties = {
  position: "relative",
  height: 20,
  cursor: "pointer",
  userSelect: "none"
}
const sliderTrackBg: CSSProperties = {
  position: "absolute",
  top: "50%",
  transform: "translateY(-50%)",
  width: "100%",
  height: 4,
  background: "#2a2f3a",
  borderRadius: 2,
  pointerEvents: "none",
  zIndex: 1
}
const thumbStyle: CSSProperties = {
  position: "absolute",
  top: "50%",
  transform: "translate(-50%, -50%)",
  width: 16,
  height: 16,
  borderRadius: "50%",
  background: "#388bfd",
  border: "2px solid #0d1117",
  cursor: "grab",
  zIndex: 5,
  boxSizing: "border-box"
}
const sliderLabels: CSSProperties = {
  display: "flex", justifyContent: "space-between", marginTop: 6
}
const sliderLabelText: CSSProperties = { fontSize: 10, color: "#8b949e" }
const legendContainer: CSSProperties = {
  display: "flex", justifyContent: "center", alignItems: "center",
  gap: 24, padding: "10px 16px", flexWrap: "wrap"
}
const legendItem: CSSProperties = { display: "flex", alignItems: "center", gap: 6, whiteSpace: "nowrap" }
const legendDot: CSSProperties = { width: 8, height: 8, borderRadius: "50%", display: "inline-block" }
const legendText: CSSProperties = { fontSize: 11, color: "#8b949e" }
