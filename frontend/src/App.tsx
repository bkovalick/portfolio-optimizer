import { useState, useMemo } from "react"
import type { CSSProperties } from "react"
import Sidebar from "./components/Sidebar"
import StrategyGrid from "./components/StrategyGrid"
import StrategyDetails from "./components/StrategyDetails"
import AnalysisPanel from "./components/AnalysisPanel"
import type { DateWindow } from "./utils/metricsUtils"

type AppTab = "dashboard" | "statistics" | "validation" | "live"

export default function App() {
  const [experiment, setExperiment] = useState<any>(null)
  const [selectedRun, setSelectedRun] = useState<any>(null)
  const [pinnedRuns, setPinnedRuns] = useState<any[]>([])
  const [dateWindow, setDateWindow] = useState<DateWindow | null>(null)
  const [activeTab, setActiveTab] = useState<AppTab>("dashboard")

  const handlePin = (run: any) => {
    setPinnedRuns(prev =>
      prev.some(r => r.run_id === run.run_id)
        ? prev.filter(r => r.run_id !== run.run_id)
        : [...prev, run]
    )
  }

  // Reset window when new experiment runs
  const handleSetExperiment = (exp: any) => {
    setExperiment(exp)
    setDateWindow(null)
  }

  const pinnedIds = useMemo(() => new Set(pinnedRuns.map(r => r.run_id)), [pinnedRuns])
  const allRuns = useMemo(() => {
    const currentRuns = experiment?.strategy_runs ?? []
    const extraPinned = pinnedRuns.filter(r => !currentRuns.some((cr: any) => cr.run_id === r.run_id))
    return [...currentRuns, ...extraPinned]
  }, [experiment, pinnedRuns])

  return (
    <div style={styles.app}>
      <div style={styles.sidebar}>
        <Sidebar
          setExperiment={handleSetExperiment}
          experiment={experiment}
          pinnedRuns={pinnedRuns}
          onClearPinned={() => setPinnedRuns([])}
        />
      </div>

      <div style={styles.main}>
        {allRuns.length > 0 ? (
          <div style={styles.mainContent}>
            <div style={styles.tabStrip}>
              <button
                style={activeTab === "dashboard" ? styles.activeTab : styles.inactiveTab}
                onClick={() => setActiveTab("dashboard")}
              >
                Dashboard
              </button>
              <button
                style={activeTab === "statistics" ? styles.activeTab : styles.inactiveTab}
                onClick={() => setActiveTab("statistics")}
              >
                Statistics
              </button>
              <button
                style={activeTab === "validation" ? styles.activeTab : styles.inactiveTab}
                onClick={() => setActiveTab("validation")}
              >
                Validation
              </button>
              <button
                style={activeTab === "live" ? styles.activeTab : styles.inactiveTab}
                onClick={() => setActiveTab("live")}
              >
                Live Trading
              </button>
            </div>

            <div style={styles.tabContent}>
              {activeTab === "dashboard" && (
                <div style={styles.twoCol}>
                  <div style={styles.leftCol}>
                    <StrategyGrid
                      runs={allRuns}
                      onSelect={setSelectedRun}
                      pinnedIds={pinnedIds}
                      onPin={handlePin}
                      dateWindow={dateWindow}
                    />
                    <StrategyDetails
                      runs={allRuns}
                      onWindowChange={setDateWindow}
                      dateWindow={dateWindow}
                    />
                  </div>
                  <div style={styles.rightCol}>
                    <AnalysisPanel
                      runs={allRuns}
                      selectedRun={selectedRun}
                      dateWindow={dateWindow}
                    />
                  </div>
                </div>
              )}

              {activeTab === "statistics" && (
                <div style={styles.fullWidthCol}>
                  <AnalysisPanel
                    runs={allRuns}
                    selectedRun={selectedRun}
                    dateWindow={dateWindow}
                  />
                </div>
              )}

              {activeTab === "validation" && (
                <div style={styles.fullWidthCol}>
                  <div style={styles.comingSoon}>Advanced validation panels (bootstrapping and CV) will appear here.</div>
                </div>
              )}

              {activeTab === "live" && (
                <div style={styles.fullWidthCol}>
                  <div style={styles.comingSoon}>Live trading and performance attribution panels will appear here.</div>
                </div>
              )}
            </div>
          </div>
        ) : (
          <div style={styles.empty}>
            <div style={styles.emptyText}>Load a strategy set and run an experiment to get started.</div>
          </div>
        )}
      </div>
    </div>
  )
}

const styles: { [key: string]: CSSProperties } = {
  app: {
    display: "flex",
    height: "100vh",
    backgroundColor: "#0e1117",
    color: "#e6edf3",
    fontFamily: "Inter, sans-serif",
    overflow: "hidden"
  },
  sidebar: {
    width: 380,
    minWidth: 330,
    height: "100vh",
    boxSizing: "border-box",
    overflow: "hidden"
  },
  main: {
    flex: 1,
    overflowY: "auto",
    minWidth: 0,
    boxSizing: "border-box",
    display: "flex",
    flexDirection: "column"
  },
  mainContent: {
    display: "flex",
    flexDirection: "column",
    height: "100%",
    width: "100%"
  },
  tabStrip: {
    display: "flex",
    borderBottom: "1px solid #2a2f3a",
    background: "#0d1117",
    padding: "12px 20px 0"
  },
  activeTab: {
    padding: "12px 18px",
    background: "none",
    border: "none",
    borderBottom: "2px solid #238636",
    cursor: "pointer",
    fontSize: 13,
    fontWeight: 700,
    letterSpacing: "0.2px",
    color: "#e6edf3"
  },
  inactiveTab: {
    padding: "12px 18px",
    background: "none",
    border: "none",
    borderBottom: "2px solid transparent",
    cursor: "pointer",
    fontSize: 13,
    fontWeight: 600,
    letterSpacing: "0.2px",
    color: "#8b949e"
  },
  tabContent: {
    flex: 1,
    padding: "20px",
    overflowY: "auto"
  },
  twoCol: {
    display: "flex",
    gap: 16,
    alignItems: "flex-start",
    width: "100%",
    boxSizing: "border-box"
  },
  leftCol: {
    flex: "1 1 0",
    minWidth: 0
  },
  rightCol: {
    flex: "1 1 0",
    minWidth: 0,
    alignSelf: "flex-start"
  },
  fullWidthCol: {
    width: "100%",
    minWidth: 0
  },
  empty: {
    display: "flex",
    flex: 1,
    height: "100%",
    alignItems: "center",
    justifyContent: "center"
  },
  emptyText: {
    color: "#8b949e",
    fontSize: 14
  },
  comingSoon: {
    padding: "40px",
    textAlign: "center",
    color: "#8b949e",
    fontSize: 14,
    border: "1px dashed #30363d",
    borderRadius: 8,
    background: "#161b22"
  }
}
