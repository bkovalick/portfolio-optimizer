import { Component, useEffect, useRef, useState } from "react"
import type { CSSProperties, ReactNode } from "react"

import NavRail from "./components/NavRail"
import type { Page } from "./components/NavRail"
import LabDrawer from "./components/LabDrawer"
import StrategyGrid from "./components/StrategyGrid"
import StrategyDetails from "./components/StrategyDetails"
import AnalysisPanel from "./components/AnalysisPanel"
import StatisticalEvidence from "./components/StatisticalEvidence"
import DownloadReport from "./components/Downloadreport"
import AttributionPage from "./components/AttributionPage"
import type { DateWindow } from "./utils/metricsUtils"

/**
 * App shell.
 *
 * INTEGRATION NOTES — adapting to your existing App.tsx:
 *  - `experiment` / `setExperiment` are the same pair your Sidebar already
 *    receives. If your runs live somewhere other than `experiment.runs`,
 *    change the one line marked RUNS-SOURCE below.
 *  - The drawer auto-closes when a run completes (runs arriving), landing
 *    you on Results. Remove that effect if you'd rather close manually.
 *  - Everything below the shell is your existing components, unchanged.
 */

export default function App() {
  const [experiment, setExperiment] = useState<any>(null)
  const [page, setPage] = useState<Page>("results")
  const [labOpen, setLabOpen] = useState(true)   // first visit: the Lab is the invitation

  const [selectedRun, setSelectedRun] = useState<any>(null)
  const [pinnedIds, setPinnedIds] = useState<Set<string>>(new Set())
  const [dateWindow, setDateWindow] = useState<DateWindow | null>(null)

  const runs: any[] = experiment?.runs ?? []     // RUNS-SOURCE

  // When a suite finishes (runs appear or change), close the Lab and show Results.
  const prevRunCount = useRef(0)
  useEffect(() => {
    if (runs.length > 0 && runs.length !== prevRunCount.current) {
      setLabOpen(false)
      setPage("results")
      if (!selectedRun || !runs.some(r => r.run_id === selectedRun.run_id)) {
        setSelectedRun(runs[0])
      }
    }
    prevRunCount.current = runs.length
  }, [runs.length])   // eslint-disable-line react-hooks/exhaustive-deps

  const togglePin = (run: any) => {
    setPinnedIds(prev => {
      const next = new Set(prev)
      next.has(run.run_id) ? next.delete(run.run_id) : next.add(run.run_id)
      return next
    })
  }

  return (
    <div style={shell}>
      <NavRail
        page={page}
        onNavigate={p => { setPage(p); setLabOpen(false) }}
        onOpenLab={() => setLabOpen(true)}
        labOpen={labOpen}
      />

      <LabDrawer
        open={labOpen}
        onClose={() => setLabOpen(false)}
        experiment={experiment}
        setExperiment={setExperiment}
      />

      <main style={main}>
        <ErrorBoundary>
          {page === "results" && (
            runs.length === 0 ? (
              <EmptyResults onOpenLab={() => setLabOpen(true)} />
            ) : (
              <div style={resultsPage}>
                <div style={resultsHeader}>
                  <h1 style={resultsTitle}>Results</h1>
                  <DownloadReport experiment={experiment} />
                </div>
                <StrategyGrid
                  runs={runs}
                  onSelect={setSelectedRun}
                  pinnedIds={pinnedIds}
                  onPin={togglePin}
                  dateWindow={dateWindow}
                />
                <StrategyDetails
                  runs={runs}
                  onWindowChange={setDateWindow}
                  dateWindow={dateWindow}
                />
                <AnalysisPanel
                  runs={runs}
                  selectedRun={selectedRun}
                  dateWindow={dateWindow}
                />
                <StatisticalEvidence
                  run={selectedRun}
                  dateWindow={dateWindow}
                />
              </div>
            )
          )}

          {page === "attribution" && (
            <AttributionPage
              runs={runs}
              selectedRun={selectedRun}
              onSelectRun={setSelectedRun}
            />
          )}
        </ErrorBoundary>
      </main>
    </div>
  )
}

function EmptyResults({ onOpenLab }: { onOpenLab: () => void }) {
  return (
    <div style={emptyResults}>
      <div style={emptyTitle}>No results yet</div>
      <div style={emptyLine}>
        Configure a strategy suite in the Lab and run it. Results, factor
        attribution, and robustness evidence land here.
      </div>
      <button style={emptyCta} onClick={onOpenLab}>Open the Lab</button>
    </div>
  )
}

/**
 * Error boundary — a render throw becomes a readable message instead of a
 * white screen. The three Sidebar crashes this project has eaten would each
 * have been a five-second diagnosis with this in place.
 */
class ErrorBoundary extends Component<{ children: ReactNode }, { error: Error | null }> {
  state = { error: null as Error | null }
  static getDerivedStateFromError(error: Error) { return { error } }
  render() {
    if (this.state.error) {
      return (
        <div style={errorBox}>
          <div style={errorTitle}>A component crashed while rendering</div>
          <pre style={errorPre}>{String(this.state.error)}</pre>
          <button style={emptyCta} onClick={() => this.setState({ error: null })}>
            Try again
          </button>
        </div>
      )
    }
    return this.props.children
  }
}

/* ---- styles ---- */

const shell: CSSProperties = {
  display: "flex",
  minHeight: "100vh",
  background: "#0d1117",
  color: "#e6edf3",
  fontFamily: "-apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif",
}
const main: CSSProperties = { flex: 1, minWidth: 0 }
const resultsPage: CSSProperties = { padding: "16px 20px" }
const resultsHeader: CSSProperties = {
  display: "flex", alignItems: "center", justifyContent: "space-between",
  marginBottom: 12, gap: 16,
}
const resultsTitle: CSSProperties = {
  fontSize: 16, fontWeight: 600, color: "#e6edf3", margin: 0, letterSpacing: "0.2px",
}

const emptyResults: CSSProperties = {
  display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center",
  minHeight: "70vh", textAlign: "center", padding: 24,
}
const emptyTitle: CSSProperties = { fontSize: 16, fontWeight: 600, color: "#e6edf3", marginBottom: 8 }
const emptyLine: CSSProperties = { fontSize: 12.5, color: "#8b949e", maxWidth: 380, lineHeight: 1.6, marginBottom: 18 }
const emptyCta: CSSProperties = {
  background: "#238636", color: "#fff", border: "none", borderRadius: 6,
  padding: "8px 16px", fontSize: 13, cursor: "pointer",
}
const errorBox: CSSProperties = { padding: 32, maxWidth: 720, margin: "0 auto" }
const errorTitle: CSSProperties = { fontSize: 14, fontWeight: 600, color: "#f85149", marginBottom: 10 }
const errorPre: CSSProperties = {
  background: "#161b22", border: "1px solid #2a2f3a", borderRadius: 6,
  padding: 14, fontSize: 12, color: "#c9d1d9", whiteSpace: "pre-wrap",
  marginBottom: 16,
}
