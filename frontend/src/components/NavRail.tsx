import { useState } from "react"
import type { CSSProperties } from "react"

export type Page = "results" | "attribution"

interface Props {
  page: Page
  onNavigate: (page: Page) => void
  onOpenLab: () => void
  labOpen: boolean
}

/**
 * Collapsible left rail. 56px of icons by default; expands to 200px on toggle.
 * "Lab" is not a page — it summons the configuration drawer. "Live" is a
 * disabled placeholder until a strategy survives the factor decomposition.
 */
export default function NavRail({ page, onNavigate, onOpenLab, labOpen }: Props) {
  const [expanded, setExpanded] = useState(false)

  const width = expanded ? 200 : 56

  return (
    <nav style={{ ...rail, width }} aria-label="Primary">
      <button
        style={toggleBtn}
        onClick={() => setExpanded(!expanded)}
        aria-label={expanded ? "Collapse navigation" : "Expand navigation"}
        title={expanded ? "Collapse" : "Expand"}
      >
        <Chevron flipped={expanded} />
      </button>

      <div style={{ height: 12 }} />

      <RailItem
        icon={<FlaskIcon />}
        label="Lab"
        expanded={expanded}
        active={labOpen}
        onClick={onOpenLab}
        title="Configure and run strategies"
      />
      <RailItem
        icon={<ChartIcon />}
        label="Results"
        expanded={expanded}
        active={page === "results" && !labOpen}
        onClick={() => onNavigate("results")}
        title="Backtest results and statistical evidence"
      />
      <RailItem
        icon={<LayersIcon />}
        label="Attribution"
        expanded={expanded}
        active={page === "attribution" && !labOpen}
        onClick={() => onNavigate("attribution")}
        title="Factor attribution over time"
      />

      <div style={{ flex: 1 }} />

      <RailItem
        icon={<PulseIcon />}
        label="Live"
        expanded={expanded}
        active={false}
        disabled
        onClick={() => {}}
        title="Paper trading — pending a strategy with verified alpha"
        badge="soon"
      />
    </nav>
  )
}

function RailItem({ icon, label, expanded, active, onClick, disabled, title, badge }: {
  icon: React.ReactNode
  label: string
  expanded: boolean
  active: boolean
  onClick: () => void
  disabled?: boolean
  title: string
  badge?: string
}) {
  return (
    <button
      style={{
        ...item,
        ...(active ? itemActive : {}),
        ...(disabled ? itemDisabled : {}),
        justifyContent: expanded ? "flex-start" : "center",
      }}
      onClick={disabled ? undefined : onClick}
      disabled={disabled}
      title={title}
      aria-label={label}
      aria-current={active ? "page" : undefined}
    >
      <span style={{ display: "inline-flex", flexShrink: 0 }}>{icon}</span>
      {expanded && <span style={itemLabel}>{label}</span>}
      {expanded && badge && <span style={badgeStyle}>{badge}</span>}
      {active && <span style={activeBar} />}
    </button>
  )
}

/* ---- inline icons (16px, stroke-based, no icon library) ---- */

function Chevron({ flipped }: { flipped: boolean }) {
  return (
    <svg width="14" height="14" viewBox="0 0 16 16" fill="none"
      style={{ transform: flipped ? "rotate(180deg)" : "none" }}>
      <path d="M6 3l5 5-5 5" stroke="#8b949e" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  )
}
function FlaskIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
      <path d="M6 2h4M7 2v4.5L3.5 12a1.5 1.5 0 001.3 2.2h6.4a1.5 1.5 0 001.3-2.2L9 6.5V2"
        stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" strokeLinejoin="round" />
      <path d="M5 10h6" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" />
    </svg>
  )
}
function ChartIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
      <path d="M2 14h12M4 11V7m4 4V4m4 7V9" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" />
    </svg>
  )
}
function LayersIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
      <path d="M8 2l6 3-6 3-6-3 6-3zM2 8l6 3 6-3M2 11l6 3 6-3"
        stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  )
}
function PulseIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
      <path d="M1 8h3l2-5 3 10 2-5h4" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  )
}

/* ---- styles ---- */

const rail: CSSProperties = {
  display: "flex",
  flexDirection: "column",
  alignItems: "stretch",
  background: "#0d1117",
  borderRight: "1px solid #2a2f3a",
  padding: "10px 8px",
  transition: "width 160ms ease",
  flexShrink: 0,
  position: "sticky",
  top: 0,
  height: "100vh",
  boxSizing: "border-box",
  zIndex: 60, 
  // zIndex: 30,
}
const toggleBtn: CSSProperties = {
  background: "none",
  border: "1px solid #2a2f3a",
  borderRadius: 6,
  height: 28,
  cursor: "pointer",
  display: "flex",
  alignItems: "center",
  justifyContent: "center",
}
const item: CSSProperties = {
  position: "relative",
  display: "flex",
  alignItems: "center",
  gap: 10,
  background: "none",
  border: "none",
  borderRadius: 6,
  color: "#8b949e",
  height: 36,
  padding: "0 10px",
  marginBottom: 2,
  cursor: "pointer",
  fontSize: 13,
  width: "100%",
  boxSizing: "border-box",
}
const itemActive: CSSProperties = { color: "#e6edf3", background: "#161b22" }
const itemDisabled: CSSProperties = { color: "#484f58", cursor: "default" }
const itemLabel: CSSProperties = { whiteSpace: "nowrap", overflow: "hidden" }
const activeBar: CSSProperties = {
  position: "absolute",
  left: -8,
  top: 8,
  bottom: 8,
  width: 2,
  background: "#3fb950",
  borderRadius: 1,
}
const badgeStyle: CSSProperties = {
  marginLeft: "auto",
  fontSize: 9,
  letterSpacing: "0.5px",
  textTransform: "uppercase",
  color: "#484f58",
  border: "1px solid #2a2f3a",
  borderRadius: 3,
  padding: "1px 5px",
}
