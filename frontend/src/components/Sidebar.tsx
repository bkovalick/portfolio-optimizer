import axios from "axios"
import { useState } from "react"
import type { CSSProperties } from "react"

type Tab = "experiment" | "lab"

export default function Sidebar({ setExperiment, experiment }: any) {
  const [tab, setTab] = useState<Tab>("experiment")
  const [loading, setLoading] = useState(false)
  const [runError, setRunError] = useState<string | null>(null)
  const [startDate, setStartDate] = useState("2005-01-01")
  const [endDate, setEndDate] = useState("2020-12-31")
  const [transactionCost, setTransactionCost] = useState(0)
  const [benchmark, setBenchmark] = useState("SPY")
  const [riskFreeRate, setRiskFreeRate] = useState(0.03)
  const [strategySet, setStrategySet] = useState<any>(null)
  const [selectedIdx, setSelectedIdx] = useState(0)
  const [editedStrategies, setEditedStrategies] = useState<any[]>([])
  const [jsonMode, setJsonMode] = useState(false)
  const [jsonText, setJsonText] = useState("")
  const [jsonError, setJsonError] = useState<string | null>(null)

  const handleUpload = async (e: any) => {
    const file = e.target.files[0]
    if (!file) return
    e.target.value = ""
    const text = await file.text()
    const json = JSON.parse(text)
    setStrategySet(json)
    setEditedStrategies(JSON.parse(JSON.stringify(json.strategies)))
    setSelectedIdx(0)
    if (json.market_store_config) {
      if (json.market_store_config.start_date) setStartDate(json.market_store_config.start_date)
      if (json.market_store_config.end_date) setEndDate(json.market_store_config.end_date)
      if (json.market_store_config?.benchmark) setBenchmark(json.market_store_config.benchmark)
      if (json.market_store_config?.transaction_cost) setTransactionCost(json.market_store_config.transaction_cost)
      if (json.market_store_config?.risk_free_rate) setRiskFreeRate(json.market_store_config.risk_free_rate)
    }
  }

  const downloadReport = async () => {
    if (!experiment) return
    const res = await axios.post("http://localhost:8000/download", experiment, {
      responseType: "blob"
    })
    const url = window.URL.createObjectURL(new Blob([res.data]))
    const link = document.createElement("a")
    link.href = url
    link.setAttribute("download", "backtest_report.xlsx")
    document.body.appendChild(link)
    link.click()
    link.remove()
    window.URL.revokeObjectURL(url)
  }

  const runExperiment = async () => {
    if (!strategySet) return

    // Validate fixed weight strategies
    for (const s of editedStrategies) {
      if (s.rebalance_problem?.strategy_type === "fwp_strategy") {
        const tickers = s.market_state_config?.investment_universe ?? []
        const w = s.rebalance_problem?.initial_weights
        const dict = Array.isArray(w)
          ? Object.fromEntries(tickers.map((t: string, i: number) => [t, w[i] ?? 0]))
          : (w ?? {})
        const total = Object.values(dict).reduce((a: number, b) => a + (b as number), 0)
        if (Math.abs(total - 1) > 0.0001) {
          alert(`Fixed weights for "${s.name}" must sum to 1. Current sum: ${total.toFixed(4)}`)
          return
        }
      }
    }

    const config = {
      ...strategySet,
      market_store_config: {
        ...strategySet.market_store_config,
        start_date: startDate,
        end_date: endDate,
        transaction_cost: transactionCost,
        benchmark: benchmark
      },
      strategies: editedStrategies.length ? editedStrategies : strategySet.strategies
    }

    setLoading(true)
    setRunError(null)
    try {
      const res = await axios.post("http://localhost:8000/run-experiment", config)
      setExperiment(res.data)
    } catch (err: any) {
      const detail = err?.response?.data?.detail ?? err?.message ?? "Unknown error"
      setRunError(detail)
    } finally {
      setLoading(false)
    }
  }

  const currentStrategy = editedStrategies[selectedIdx]

  const updateField = (path: string[], value: any) => {
    const updated = JSON.parse(JSON.stringify(editedStrategies))
    let node = updated[selectedIdx]
    for (let i = 0; i < path.length - 1; i++) node = node[path[i]]
    node[path[path.length - 1]] = value
    setEditedStrategies(updated)
  }

  const openJsonEditor = () => {
    setJsonText(JSON.stringify(currentStrategy, null, 2))
    setJsonError(null)
    setJsonMode(true)
  }

  const applyJson = () => {
    try {
      const parsed = JSON.parse(jsonText)
      const updated = JSON.parse(JSON.stringify(editedStrategies))
      updated[selectedIdx] = parsed
      setEditedStrategies(updated)
      setJsonMode(false)
      setJsonError(null)
    } catch (e: any) {
      setJsonError(e.message)
    }
  }

  const quickStats = (() => {
    if (!experiment?.strategy_runs?.length) return null
    const runs = experiment.strategy_runs
    const best = (key: string, higher = true) => {
      const sorted = [...runs].sort((a, b) => {
        const va = a.result.summary[key] ?? (higher ? -Infinity : Infinity)
        const vb = b.result.summary[key] ?? (higher ? -Infinity : Infinity)
        return higher ? vb - va : va - vb
      })
      return { name: formatName(sorted[0].strategy_name), value: sorted[0].result.summary[key] }
    }
    return {
      sharpe:   best("sharpe_ratio"),
      ret:      best("return"),
      drawdown: best("max_drawdown", false),
      vol:      best("volatility", false)
    }
  })()

  const rebalanceOptions = ["daily", "weekly", "monthly", "quarterly"]
  const strategyTypes = ["mean_variance_strategy","mean_reversion_strategy","fwp_strategy","ewp_strategy"]

  return (
    <div style={container}>
      <div style={tabBar}>
        <button style={tab === "experiment" ? activeTab : inactiveTab} onClick={() => setTab("experiment")}>
          Experiment
        </button>
        <button style={tab === "lab" ? activeTab : inactiveTab} onClick={() => setTab("lab")}>
          Strategy Lab
        </button>
      </div>

      {tab === "experiment" && (
        <>
        <Section title="Strategy Set">
          <input id="strategy-file-input" type="file" accept=".json" onChange={handleUpload} onClick={(e: any) => e.target.value = null} style={{ display: "none" }} />
          {strategySet 
            ? <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                <div style={pill}>{editedStrategies.length} strategies loaded</div>
                <button style={changeLinkBtn} onClick={() => document.getElementById("strategy-file-input")?.click()}>change</button>
              </div>
            : null}
        </Section>

          <Section title="Market Configuration">
            <Row label="Start">
              <input type="date" value={startDate} onChange={(e) => setStartDate(e.target.value)} style={inputStyle} />
            </Row>
            <Row label="End">
              <input type="date" value={endDate} onChange={(e) => setEndDate(e.target.value)} style={inputStyle} />
            </Row>
            <Row label="Benchmark">
              <input type="text" value={benchmark} onChange={(e) => setBenchmark(e.target.value)} style={inputStyle} />
            </Row>            
            <Row label="Txn Cost">
              <input type="number" value={transactionCost} step={0.001}
                onChange={(e) => setTransactionCost(Number(e.target.value))} style={inputStyle} />
            </Row>
            <Row label="Risk Free Rate">
              <input type="number" value={riskFreeRate} step={0.005}
                onChange={(e) => setRiskFreeRate(Number(e.target.value))} style={inputStyle} />
            </Row>            
          </Section>

          <button
            style={strategySet && !loading ? runButton : loadButton}
            disabled={loading}
            onClick={strategySet ? runExperiment : () => document.getElementById("strategy-file-input")?.click()}
          >
            {loading ? `Running ${editedStrategies.length || strategySet?.strategies?.length || 0} strategies…` : strategySet ? "Run Experiment" : "Load a Strategy Set"}
          </button>
          {runError && <div style={{ marginTop: 6, padding: "6px 10px", background: "#2d1215", border: "1px solid #f85149", borderRadius: 6, color: "#f85149", fontSize: 11 }}>{runError}</div>}

          {quickStats && (
            <>
              <hr style={divider} />
              <div style={quickStatsTitle}>Last Run · Best</div>
              <div style={statsGrid}>
                <StatCard label="Sharpe"   value={quickStats.sharpe.value?.toFixed(2)}   name={quickStats.sharpe.name} />
                <StatCard label="Return"   value={(quickStats.ret.value != null ? (quickStats.ret.value * 100).toFixed(1) + "%" : "-")} name={quickStats.ret.name} positive />
                <StatCard label="Min DD"   value={(quickStats.drawdown.value != null ? (quickStats.drawdown.value * 100).toFixed(1) + "%" : "-")} name={quickStats.drawdown.name} negative />
                <StatCard label="Low Vol"  value={(quickStats.vol.value != null ? (quickStats.vol.value * 100).toFixed(1) + "%" : "-")} name={quickStats.vol.name} />
              </div>
              <button style={exportButton} onClick={downloadReport}>↓ Download Report</button>
            </>
          )}
        </>
      )}

      {tab === "lab" && (
        <>
          {!strategySet ? (
            <div style={emptyState}>Load a strategy set in the Experiment tab first.</div>
          ) : (
            <>
            <div style={strategyNav}>
              {editedStrategies.map((s: any, i: number) => {
                const isNew = !strategySet.strategies.find((orig: any) => orig.name === s.name)
                return (
                  <div key={i} style={{ display: "flex", gap: 4 }}>
                    <button
                      style={{ ...(i === selectedIdx ? activeStrategyBtn : strategyBtn), flex: 1 }}
                      onClick={() => { setSelectedIdx(i); setJsonMode(false) }}>
                      {s.name}
                      {isNew && <span style={newBadge}>new</span>}
                    </button>
                    <button
                      style={{ ...removeStrategyBtn, opacity: editedStrategies.length <= 1 ? 0.5 : 1, cursor: editedStrategies.length <= 1 ? "not-allowed" : "pointer" }}
                      disabled={editedStrategies.length <= 1}
                      onClick={() => {
                        if (editedStrategies.length <= 1) return
                        const updated = editedStrategies.filter((_: any, idx: number) => idx !== i)
                        setEditedStrategies(updated)
                        setSelectedIdx(Math.min(i, updated.length - 1))
                        setJsonMode(false)
                      }}
                      title={editedStrategies.length <= 1 ? "At least one strategy is required" : "Delete strategy"}
                    >✕</button>
                    </div>
                )
              })}
              <button style={addStrategyBtn} onClick={() => {
                const template = JSON.parse(JSON.stringify(editedStrategies[0]))
                template.name = `custom_strategy_${editedStrategies.length + 1}`
                const updated = [...editedStrategies, template]
                setEditedStrategies(updated)
                setSelectedIdx(updated.length - 1)
                setJsonMode(false)
              }}>
                + Add Strategy
              </button>
            </div>

              {jsonMode ? (
                <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                  <textarea value={jsonText} onChange={(e) => setJsonText(e.target.value)}
                    style={jsonEditor} spellCheck={false} />
                  {jsonError && <div style={errorMsg}>{jsonError}</div>}
                  <div style={{ display: "flex", gap: 6 }}>
                    <button style={applyBtn} onClick={applyJson}>Apply</button>
                    <button style={cancelBtn} onClick={() => { setJsonMode(false); setJsonError(null) }}>Cancel</button>
                  </div>
                </div>
              ) : currentStrategy ? (
                <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
                  <Section title="Identity">
                    <Row label="Name">
                      <input style={inputStyle} value={currentStrategy.name}
                        onChange={(e) => updateField(["name"], e.target.value)} />
                    </Row>
                  </Section>

                  <Section title="Market State">
                    <Row label="Lookback">
                      <input style={inputStyle} value={currentStrategy.market_state_config?.lookback_window_key ?? ""}
                        onChange={(e) => updateField(["market_state_config", "lookback_window_key"], e.target.value)} />
                    </Row>
                    <Row label="Cash Alloc">
                      <input type="number" step={0.01} style={inputStyle}
                        value={currentStrategy.market_state_config?.cash_allocation ?? 0}
                        onChange={(e) => updateField(["market_state_config", "cash_allocation"], Number(e.target.value))} />
                    </Row>
                    <label style={labelStyle}>Universe Tickers</label>
                      <div style={{ display: "flex", gap: 6, marginBottom: 4, alignItems: "center" }}>
                        <button style={smallBtn} onClick={() => {
                          const allTickers = (strategySet.market_store_config.tickers ?? []).filter(
                            (t: string) => t !== strategySet.market_store_config.benchmark
                          )
                          if (currentStrategy.rebalance_problem?.strategy_type === "fwp_strategy") {
                            const rawWeights = currentStrategy.rebalance_problem?.initial_weights
                            const currentWeights: Record<string, number> = Array.isArray(rawWeights)
                              ? Object.fromEntries((currentStrategy.market_state_config?.investment_universe ?? []).map((t: string, i: number) => [t, rawWeights[i] ?? 0]))
                              : (rawWeights ?? {})
                            const newWeights = Object.fromEntries(allTickers.map((t: string) => [t, currentWeights[t] ?? 0]))
                            const updatedStrategies = JSON.parse(JSON.stringify(editedStrategies))
                            updatedStrategies[selectedIdx].market_state_config.investment_universe = allTickers
                            updatedStrategies[selectedIdx].rebalance_problem.initial_weights = newWeights
                            setEditedStrategies(updatedStrategies)
                            return
                          }
                          updateField(["market_state_config", "investment_universe"], allTickers)
                        }}>All</button>

                        <button style={smallBtn} onClick={() => {
                          if (currentStrategy.rebalance_problem?.strategy_type === "fwp_strategy") {
                            const updatedStrategies = JSON.parse(JSON.stringify(editedStrategies))
                            updatedStrategies[selectedIdx].market_state_config.investment_universe = []
                            updatedStrategies[selectedIdx].rebalance_problem.initial_weights = {}
                            setEditedStrategies(updatedStrategies)
                            return
                          }
                          updateField(["market_state_config", "investment_universe"], [])
                        }}>Clear</button>
                        <span style={{ fontSize: 10, color: "#8b949e" }}>
                          {(currentStrategy.market_state_config?.investment_universe ?? []).length} selected
                        </span>
                      </div>
                      <div style={tickerGrid}>
                        {(strategySet.market_store_config.tickers ?? [])
                          .filter((t: string) => t !== strategySet.market_store_config.benchmark)
                          .map((ticker: string) => {
                            const selected = (currentStrategy.market_state_config?.investment_universe ?? []).includes(ticker)
                            return (
                              <button
                                key={ticker}
                                style={selected ? tickerChipActive : tickerChip}
                                onClick={() => {
                                  const current = currentStrategy.market_state_config?.investment_universe ?? []
                                  const updated = selected
                                    ? current.filter((t: string) => t !== ticker)
                                    : [...current, ticker]
                                  
                                  // If fwp strategy, sync initial_weights dict with new ticker list
                                  if (currentStrategy.rebalance_problem?.strategy_type === "fwp_strategy") {
                                    const rawWeights = currentStrategy.rebalance_problem?.initial_weights
                                    const currentWeights: Record<string, number> = Array.isArray(rawWeights)
                                      ? Object.fromEntries(current.map((t: string, i: number) => [t, rawWeights[i] ?? 0]))
                                      : (rawWeights ?? {})
                                    
                                    const newWeights = Object.fromEntries(
                                      updated.map((t: string) => [t, currentWeights[t] ?? 0])
                                    )
                                    
                                    const updatedStrategies = JSON.parse(JSON.stringify(editedStrategies))
                                    updatedStrategies[selectedIdx].market_state_config.investment_universe = updated
                                    updatedStrategies[selectedIdx].rebalance_problem.initial_weights = newWeights
                                    setEditedStrategies(updatedStrategies)
                                    return
                                  }

                                  updateField(["market_state_config", "investment_universe"], updated)
                                }}
                              >{ticker}</button>
                            )
                          })}
                      </div>
                    <Row label="Exogenous">
                      <input
                        style={inputStyle}
                        placeholder="e.g. ^VIX, ^TNX"
                        value={(currentStrategy.market_state_config?.exogenous_tickers ?? []).join(", ")}
                        onChange={(e) => {
                          const tickers = e.target.value
                            .split(",")
                            .map((t: string) => t.trim())
                            .filter((t: string) => t.length > 0)
                          updateField(["market_state_config", "exogenous_tickers"], tickers)
                        }}
                      />
                    </Row>
                  </Section>
                  
                  <Section title="Strategy Type">
                    <Row label="Strategy">
                      <input style={inputStyle} 
                        value={currentStrategy.rebalance_problem?.strategy_type ?? ""}
                        onChange={(e) => updateField(["rebalance_problem", "strategy_type"], e.target.value)}/>                      
                    </Row>
                  </Section>

                  <Section title="Rebalance">
                    <Row label="Frequency">
                      <select style={inputStyle}
                        value={currentStrategy.rebalance_problem?.rebalance_frequency ?? "weekly"}
                        onChange={(e) => updateField(["rebalance_problem", "rebalance_frequency"], e.target.value)}>
                        {rebalanceOptions.map(o => <option key={o} value={o}>{o}</option>)}
                      </select>
                    </Row>
                  </Section>

                  {currentStrategy.rebalance_problem?.strategy_type === "fwp_strategy" && (() => {
                    const tickers: string[] = currentStrategy.market_state_config?.investment_universe ?? []
                    const rawWeights = currentStrategy.rebalance_problem?.initial_weights
                    
                    // Normalize to dict
                    const weightsDict: Record<string, number> = Array.isArray(rawWeights)
                      ? Object.fromEntries(tickers.map((t, i) => [t, rawWeights[i] ?? 0]))
                      : (rawWeights ?? {})

                    const total = Object.values(weightsDict).reduce((s, v) => s + v, 0)
                    const valid = Math.abs(total - 1) < 0.0001

                    const updateWeight = (ticker: string, val: number) => {
                      const updated = { ...weightsDict, [ticker]: val }
                      // Store as dict
                      updateField(["rebalance_problem", "initial_weights"], updated)
                    }

                    const equalise = () => {
                      if (tickers.length === 0) return
                      const base = 1 / tickers.length
                      const updated = Object.fromEntries(
                        tickers.map((t: string, i: number) => [
                          t,
                          i === tickers.length - 1
                            ? 1 - base * (tickers.length - 1)
                            : base
                        ])
                      )
                      updateField(["rebalance_problem", "initial_weights"], updated)
                    }

                    return (
                      <Section title="Fixed Weights">
                        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 4 }}>
                          <span style={{ fontSize: 10, color: valid ? "#3fb950" : "#f85149" }}>
                            Sum: {(total * 100).toFixed(1)}% {valid ? "✓" : "— must equal 100%"}
                          </span>
                          <button style={smallBtn} onClick={equalise}>Equalise</button>
                        </div>
                        {tickers.map(ticker => (
                          <Row key={ticker} label={ticker}>
                            <input
                              type="number" step={0.005} min={0} max={1} style={inputStyle}
                              value={+((weightsDict[ticker] ?? 0).toFixed(6))}
                              onChange={(e) => updateWeight(ticker, Number(e.target.value))}
                            />
                          </Row>
                        ))}
                      </Section>
                    )
                  })()}
                  {currentStrategy.rebalance_problem?.constraints && (
                    <Section title="Constraints">
                      {[
                        ["Max Pos", "max_position_size", undefined],
                        ["Min Pos", "min_position_size", undefined],
                        ["Max #", "max_positions", undefined],
                        ["Turnover", "turnover_limit", undefined],
                        ["Risk Aversion", "risk_aversion", "0.10 — barely penalizes risk, near pure return maximization\n1.0 — balanced, textbook mean-variance\n2.5 — moderately risk averse, common in institutional settings\n5.0+ — conservative, heavily penalizes variance"],
                        ["Vol Limit", "optimizer_vol_constraint", undefined],
                      ].map(([labelText, key, tooltip]) => (
                        <Row key={key} label={labelText}>
                          <input type="number" step={0.01} style={inputStyle}
                            title={tooltip}
                            value={currentStrategy.rebalance_problem.constraints[key] ?? ""}
                            onChange={(e) => updateField(["rebalance_problem", "constraints", key], Number(e.target.value))} />
                        </Row>
                      ))}
                    </Section>
                  )}

                  {currentStrategy.signals_config && Object.keys(currentStrategy.signals_config).length > 0 && (
                    <Section title="Signals">
                      <Row label="Winsorize">
                        <select
                          style={inputStyle}
                          value={currentStrategy.signals_config.apply_winsorizing ? "true" : "false"}
                          onChange={(e) => updateField(["signals_config", "apply_winsorizing"], e.target.value === "true")}
                        >
                          <option value="false">Off</option>
                          <option value="true">On</option>
                        </select>
                      </Row>  

                      {currentStrategy.signals_config.apply_winsorizing && (
                        <>
                          <Row label="Lower %">
                            <input
                              type="number" step={0.01} min={0} max={1} style={inputStyle}
                              value={currentStrategy.signals_config.windsor_percentiles?.lower ?? 0.05}
                              onChange={(e) => updateField(["signals_config", "windsor_percentiles", "lower"], Number(e.target.value))}
                            />
                          </Row>
                          <Row label="Upper %">
                            <input
                              type="number" step={0.01} min={0} max={1} style={inputStyle}
                              value={currentStrategy.signals_config.windsor_percentiles?.upper ?? 0.95}
                              onChange={(e) => updateField(["signals_config", "windsor_percentiles", "upper"], Number(e.target.value))}
                            />
                          </Row>
                        </>
                      )}                      
                      {currentStrategy.signals_config.momentum_skip_periods !== undefined && (
                        <Row label="Mom Skip">
                          <input type="number" style={inputStyle}
                            value={currentStrategy.signals_config.momentum_skip_periods}
                            onChange={(e) => updateField(["signals_config", "momentum_skip_periods"], Number(e.target.value))} />
                        </Row>
                      )}
                      {currentStrategy.signals_config.mean_reversion_window !== undefined && (
                        <Row label="MR Window">
                          <input type="number" style={inputStyle}
                            value={currentStrategy.signals_config.mean_reversion_window}
                            onChange={(e) => updateField(["signals_config", "mean_reversion_window"], Number(e.target.value))} />
                        </Row>
                      )}

                      {/* Black-Litterman block */}
                      <div style={blHeader}>
                        <span style={blLabel}>Black-Litterman</span>
                        {currentStrategy.signals_config.black_litterman ? (
                          <button style={blRemoveBtn} onClick={() => {
                            const updated = JSON.parse(JSON.stringify(editedStrategies))
                            delete updated[selectedIdx].signals_config.black_litterman
                            setEditedStrategies(updated)
                          }}>Remove ✕</button>
                        ) : (
                          <button style={blAddBtn} onClick={() => {
                            updateField(["signals_config", "black_litterman"], 
                              { delta: 2.5, tau: 0.05, reversion_view: 0.03, ml_view_spread: 0.03, view_direction: "momentum" })
                          }}>+ Add</button>
                        )}
                      </div>

                      {currentStrategy.signals_config.black_litterman && (
                        <div style={blBlock}>
                          {([
                            ["Delta", "delta", 0.1],
                            ["Tau", "tau", 0.01],
                            ["Reversion View", "reversion_view", 0.01],
                            ["ML View Spread", "ml_view_spread", 0.01],
                          ] as [string, string, number][]).map(([labelText, key, step]) => (
                            <Row key={key} label={labelText}>
                              <input type="number" step={step} style={inputStyle}
                                value={currentStrategy.signals_config.black_litterman[key] ?? ""}
                                onChange={(e) => updateField(["signals_config", "black_litterman", key], Number(e.target.value))} />
                            </Row>
                          ))}
                          <Row label="View Dir">
                            <select style={inputStyle}
                              value={currentStrategy.signals_config.black_litterman.view_direction ?? "momentum"}
                              onChange={(e) => updateField(["signals_config", "black_litterman", "view_direction"], e.target.value)}>
                              <option value="momentum">momentum</option>
                              <option value="mean_reversion">mean_reversion</option>
                            </select>
                          </Row>
                        </div>
                      )}

                      {/* ML Signals block */}
                      {currentStrategy.signals_config.ml_signals_config?.enabled && (
                        <>
                          <div style={blHeader}>
                            <span style={blLabel}>ML Signals</span>
                          </div>
                          <div style={blBlock}>
                            <Row label="Training">
                              <select style={inputStyle}
                                value={currentStrategy.signals_config.ml_signals_config.training_window ?? "2y"}
                                onChange={(e) => updateField(["signals_config", "ml_signals_config", "training_window"], e.target.value)}>
                                {["6m", "1y", "2y", "3y", "5y"].map(o => <option key={o} value={o}>{o}</option>)}
                              </select>
                            </Row>
                            <Row label="Horizon">
                              <select style={inputStyle}
                                value={currentStrategy.signals_config.ml_signals_config.horizon ?? "1m"}
                                onChange={(e) => updateField(["signals_config", "ml_signals_config", "horizon"], e.target.value)}>
                                {["1w", "2w", "1m", "3m"].map(o => <option key={o} value={o}>{o}</option>)}
                              </select>
                            </Row>
                            <Row label="Rebal Cadence">
                              <select style={inputStyle}
                                value={currentStrategy.signals_config.ml_signals_config.rebal_cadence ?? "1m"}
                                onChange={(e) => updateField(["signals_config", "ml_signals_config", "rebal_cadence"], e.target.value)}>
                                {["1w", "2w", "1m", "3m"].map(o => <option key={o} value={o}>{o}</option>)}
                              </select>
                            </Row>
                            <Row label="Sample Stride">
                              <select style={inputStyle}
                                value={currentStrategy.signals_config.ml_signals_config.sample_stride ?? "1w"}
                                onChange={(e) => updateField(["signals_config", "ml_signals_config", "sample_stride"], e.target.value)}>
                                {["1d", "1w", "2w", "1m"].map(o => <option key={o} value={o}>{o}</option>)}
                              </select>
                            </Row>
                            <Row label="Alpha">
                              <input type="number" step={0.1} style={inputStyle}
                                value={currentStrategy.signals_config.ml_signals_config.alpha ?? 1.0}
                                onChange={(e) => updateField(["signals_config", "ml_signals_config", "alpha"], Number(e.target.value))} />
                            </Row>
                          </div>
                        </>
                      )}
                    </Section>
                  )}

                  <button style={jsonToggleBtn} onClick={openJsonEditor}>Edit Raw JSON ↗</button>
                </div>
              ) : null}
            </>
          )}

          <hr style={divider} />
          <button style={loading ? loadButton : runButton} disabled={loading} onClick={runExperiment}>
            {loading ? "Running…" : "Run Experiment"}
          </button>
        </>
      )}
    </div>
  )
}

function StatCard({ label, name, value, positive, negative }: any) {
  const valueColor = positive ? "#3fb950" : negative ? "#f85149" : "#e6edf3"
  return (
    <div style={statCard}>
      <div style={statLabel}>{label}</div>
      <div style={{ ...statValue, color: valueColor }}>{value ?? "-"}</div>
      <div style={statName}>{name}</div>
    </div>
  )
}

function Section({ title, children }: any) {
  return (
    <div style={sectionStyle}>
      <h4 style={sectionTitle}>{title}</h4>
      {children}
    </div>
  )
}

// Inline label+input row to halve vertical space vs stacked label/input
function Row({ label, children }: any) {
  return (
    <div style={rowStyle}>
      <span style={rowLabel}>{label}</span>
      <div style={rowInput}>{children}</div>
    </div>
  )
}

function formatName(name: string) {
  return name.replace("_portfolio", "").replace(/_/g, " ").replace(/\b\w/g, c => c.toUpperCase())
}

const container: CSSProperties = { display: "flex", flexDirection: "column", gap: 10, height: "100%", overflowY: "auto" }
const tabBar: CSSProperties = { display: "flex", borderBottom: "1px solid #2a2f3a", marginBottom: 2 }
const baseTab: CSSProperties = { flex: 1, padding: "6px 0", background: "none", border: "none", cursor: "pointer", fontSize: 12, fontWeight: 600, letterSpacing: "0.3px" }
const activeTab: CSSProperties = { ...baseTab, color: "#e6edf3", borderBottom: "2px solid #238636" }
const inactiveTab: CSSProperties = { ...baseTab, color: "#8b949e", borderBottom: "2px solid transparent" }
const sectionStyle: CSSProperties = { display: "flex", flexDirection: "column", gap: 4 }
const sectionTitle: CSSProperties = { fontSize: 10, textTransform: "uppercase", color: "#8b949e", letterSpacing: "0.6px", margin: 0, marginBottom: 1 }
const labelStyle: CSSProperties = { fontSize: 10, color: "#8b949e" }
const inputStyle: CSSProperties = { background: "#161b22", border: "1px solid #30363d", borderRadius: 4, color: "#e6edf3", padding: "3px 6px", fontSize: 11, width: "100%", boxSizing: "border-box" }
const fileInput: CSSProperties = { fontSize: 11, color: "#8b949e" }
const pill: CSSProperties = { fontSize: 10, color: "#3fb950", background: "#0f2b14", border: "1px solid #238636", borderRadius: 20, padding: "1px 8px", display: "inline-block" }
const runButton: CSSProperties = { padding: "8px 12px", background: "#238636", border: "none", color: "white", cursor: "pointer", borderRadius: 6, fontWeight: 600, fontSize: 12, width: "100%" }
const divider: CSSProperties = { borderColor: "#2a2f3a", margin: "2px 0" }
const quickStatsTitle: CSSProperties = { fontSize: 10, textTransform: "uppercase", letterSpacing: "0.6px", color: "#8b949e", fontWeight: 600 }
const statsGrid: CSSProperties = { display: "grid", gridTemplateColumns: "1fr 1fr", gap: 6 }
const statCard: CSSProperties = { background: "#0d1117", border: "1px solid #21262d", borderRadius: 6, padding: "6px 8px" }
const statLabel: CSSProperties = { fontSize: 9, color: "#8b949e", textTransform: "uppercase", letterSpacing: "0.4px", marginBottom: 1 }
const statValue: CSSProperties = { fontSize: 14, fontWeight: 700, lineHeight: 1.2 }
const statName: CSSProperties = { fontSize: 9, color: "#8b949e", marginTop: 1, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }
const strategyNav: CSSProperties = { display: "flex", flexDirection: "column", gap: 3 }
const strategyBtn: CSSProperties = { background: "none", border: "1px solid #30363d", borderRadius: 4, color: "#8b949e", padding: "4px 8px", fontSize: 11, cursor: "pointer", textAlign: "left" }
const activeStrategyBtn: CSSProperties = { ...strategyBtn, background: "#161b22", border: "1px solid #388bfd", color: "#e6edf3" }
const jsonEditor: CSSProperties = { background: "#0d1117", border: "1px solid #30363d", borderRadius: 4, color: "#e6edf3", padding: 8, fontSize: 11, fontFamily: "monospace", height: 320, resize: "vertical", width: "100%", boxSizing: "border-box" }
const jsonToggleBtn: CSSProperties = { background: "none", border: "1px solid #30363d", borderRadius: 4, color: "#8b949e", padding: "4px 8px", fontSize: 11, cursor: "pointer", textAlign: "left" }
const applyBtn: CSSProperties = { flex: 1, padding: "5px 0", background: "#238636", border: "none", borderRadius: 4, color: "white", fontSize: 11, cursor: "pointer" }
const cancelBtn: CSSProperties = { flex: 1, padding: "5px 0", background: "#21262d", border: "1px solid #30363d", borderRadius: 4, color: "#e6edf3", fontSize: 11, cursor: "pointer" }
const errorMsg: CSSProperties = { color: "#f85149", fontSize: 10, fontFamily: "monospace" }
const emptyState: CSSProperties = { color: "#8b949e", fontSize: 12, lineHeight: 1.6 }
const rowStyle: CSSProperties = { display: "flex", alignItems: "center", gap: 6 }
const rowLabel: CSSProperties = { fontSize: 10, color: "#8b949e", width: 68, flexShrink: 0 }
const rowInput: CSSProperties = { flex: 1, minWidth: 0 }
const blHeader: CSSProperties = { display: "flex", alignItems: "center", justifyContent: "space-between", marginTop: 6 }
const blLabel: CSSProperties = { fontSize: 10, color: "#8b949e", textTransform: "uppercase", letterSpacing: "0.4px" }
const blAddBtn: CSSProperties = { background: "none", border: "1px solid #238636", borderRadius: 3, color: "#3fb950", fontSize: 10, cursor: "pointer", padding: "1px 6px" }
const blRemoveBtn: CSSProperties = { background: "none", border: "1px solid #6e3535", borderRadius: 3, color: "#f85149", fontSize: 10, cursor: "pointer", padding: "1px 6px" }
const blBlock: CSSProperties = { display: "flex", flexDirection: "column", gap: 4, paddingLeft: 8, borderLeft: "2px solid #21262d", marginTop: 4 }
const tickerGrid: CSSProperties = { display: "flex", flexWrap: "wrap", gap: 4 }
const tickerChip: CSSProperties = { background: "none", border: "1px solid #30363d", borderRadius: 3, color: "#8b949e", fontSize: 10, cursor: "pointer", padding: "2px 5px" }
const tickerChipActive: CSSProperties = { ...tickerChip, background: "#0f2b14", border: "1px solid #238636", color: "#3fb950" }
const smallBtn: CSSProperties = { background: "none", border: "1px solid #30363d", borderRadius: 3, color: "#8b949e", fontSize: 10, cursor: "pointer", padding: "2px 6px" }
const loadButton: CSSProperties = { padding: "8px 12px", background: "#1f6feb", border: "none", color: "white", cursor: "pointer", borderRadius: 6, fontWeight: 600, fontSize: 12, width: "100%" }
const exportButton: CSSProperties = { padding: "8px 12px", background: "none", border: "1px solid #238636", color: "#3fb950", cursor: "pointer", borderRadius: 6, fontWeight: 600, fontSize: 12, width: "100%" }
const changeLinkBtn: CSSProperties = { background: "none", border: "none", color: "#8b949e", fontSize: 10, cursor: "pointer", padding: 0, textDecoration: "underline" }
const addStrategyBtn: CSSProperties = {
  background: "none", border: "1px dashed #30363d", borderRadius: 4,
  color: "#8b949e", padding: "4px 8px", fontSize: 11, cursor: "pointer",
  textAlign: "left", marginTop: 2
}
const newBadge: CSSProperties = {
  fontSize: 9, color: "#3fb950", border: "1px solid #238636",
  borderRadius: 3, padding: "0 4px", marginLeft: 6
}
const removeStrategyBtn: CSSProperties = {
  background: "none", border: "1px solid #30363d", borderRadius: 4,
  color: "#8b949e", fontSize: 10, cursor: "pointer", padding: "2px 6px"
}