import { useEffect } from "react"
import type { CSSProperties } from "react"
import Sidebar from "./Sidebar"

interface Props {
  open: boolean
  onClose: () => void
  experiment: any
  setExperiment: (e: any) => void
}

/**
 * The Strategy Lab as a summonable drawer. Hosts the existing Sidebar
 * (configuration + upload + run) unchanged; slides over the results page
 * instead of permanently occupying it. Esc or backdrop click closes.
 */
export default function LabDrawer({ open, onClose, experiment, setExperiment }: Props) {
  useEffect(() => {
    if (!open) return
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") onClose() }
    window.addEventListener("keydown", onKey)
    return () => window.removeEventListener("keydown", onKey)
  }, [open, onClose])

  const reduceMotion =
    typeof window !== "undefined" &&
    window.matchMedia?.("(prefers-reduced-motion: reduce)").matches

  return (
    <>
      {open && <div style={backdrop} onClick={onClose} aria-hidden="true" />}
      <aside
        style={{
          ...drawer,
          transform: open ? "translateX(0)" : "translateX(-105%)",
          transition: reduceMotion ? "none" : "transform 200ms ease",
        }}
        aria-hidden={!open}
        aria-label="Strategy Lab"
      >
        <div style={drawerHeader}>
          <span style={drawerTitle}>Strategy Lab</span>
          <button style={closeBtn} onClick={onClose} aria-label="Close lab">✕</button>
        </div>
        <div style={drawerBody}>
          <Sidebar experiment={experiment} setExperiment={setExperiment} />
        </div>
      </aside>
    </>
  )
}

const backdrop: CSSProperties = {
  position: "fixed",
  inset: 0,
  background: "rgba(1, 4, 9, 0.6)",
  zIndex: 40,
}
const drawer: CSSProperties = {
  position: "fixed",
  top: 0,
  left: 56,
  bottom: 0,
  width: 420,
  maxWidth: "calc(100vw - 56px)",
  background: "#0d1117",
  borderRight: "1px solid #2a2f3a",
  zIndex: 50,
  display: "flex",
  flexDirection: "column",
  boxShadow: "8px 0 24px rgba(0,0,0,0.4)",
}
const drawerHeader: CSSProperties = {
  display: "flex",
  alignItems: "center",
  justifyContent: "space-between",
  padding: "12px 16px",
  borderBottom: "1px solid #2a2f3a",
  flexShrink: 0,
}
const drawerTitle: CSSProperties = {
  fontSize: 13,
  fontWeight: 600,
  color: "#e6edf3",
  letterSpacing: "0.3px",
}
const closeBtn: CSSProperties = {
  background: "none",
  border: "none",
  color: "#8b949e",
  cursor: "pointer",
  fontSize: 14,
  padding: 4,
}
const drawerBody: CSSProperties = {
  overflowY: "auto",
  flex: 1,
}
