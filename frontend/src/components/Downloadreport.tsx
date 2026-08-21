import { useState } from "react"
import type { CSSProperties } from "react"
import axios from "axios"

interface Props {
  experiment: any
  pinnedRuns?: any[]
}

/**
 * Download the Excel report for the current experiment.
 * Lives on the Results page so you can export what you're looking at without
 * reopening the Lab. Pinned runs from earlier experiments are merged into the
 * payload so the report covers everything visible in the grid.
 */
export default function DownloadReport({ experiment, pinnedRuns = [] }: Props) {
  const [progress, setProgress] = useState<number | null>(null)

  if (!experiment?.strategy_runs?.length) return null

  const download = async () => {
    setProgress(0)
    try {
      const currentRunIds = new Set(
        (experiment.strategy_runs ?? []).map((r: any) => r.run_id)
      )
      const extraPinned = pinnedRuns.filter((r: any) => !currentRunIds.has(r.run_id))
      const payload = extraPinned.length > 0
        ? { ...experiment, strategy_runs: [...(experiment.strategy_runs ?? []), ...extraPinned] }
        : experiment

      const res = await axios.post("http://localhost:8000/download", payload, {
        responseType: "blob",
        onDownloadProgress: (e) => {
          if (e.total) setProgress(Math.round((e.loaded / e.total) * 100))
          else setProgress(-1)
        },
      })
      const url = window.URL.createObjectURL(new Blob([res.data]))
      const link = document.createElement("a")
      link.href = url
      link.setAttribute("download", "backtest_report.xlsx")
      document.body.appendChild(link)
      link.click()
      link.remove()
      window.URL.revokeObjectURL(url)
    } finally {
      setProgress(null)
    }
  }

  return (
    <div style={wrap}>
      <button style={button} onClick={download} disabled={progress !== null}>
        ↓ Download Report
      </button>
      {progress !== null && (
        <>
          <style>{`@keyframes dl-indeterminate { 0% { transform: translateX(-100%); } 100% { transform: translateX(400%); } }`}</style>
          <div style={track}>
            {progress >= 0
              ? <div style={{ ...bar, width: `${progress}%` }} />
              : <div style={indeterminate} />}
          </div>
        </>
      )}
    </div>
  )
}

const wrap: CSSProperties = {
  display: "flex", flexDirection: "column", alignItems: "flex-end",
  gap: 6, minWidth: 160,
}
const button: CSSProperties = {
  padding: "6px 14px", background: "none", border: "1px solid #238636",
  color: "#3fb950", cursor: "pointer", borderRadius: 6,
  fontWeight: 600, fontSize: 12, whiteSpace: "nowrap",
}
const track: CSSProperties = {
  height: 4, width: "100%", borderRadius: 2, background: "#21262d",
  overflow: "hidden", position: "relative",
}
const bar: CSSProperties = {
  height: "100%", borderRadius: 2, background: "#3fb950", transition: "width 0.3s ease",
}
const indeterminate: CSSProperties = {
  position: "absolute", height: "100%", width: "40%", borderRadius: 2,
  background: "#3fb950", animation: "dl-indeterminate 1.2s ease infinite",
}
