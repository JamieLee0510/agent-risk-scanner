import { useRef, useState } from "react";
import { Upload } from "lucide-react";
import { parseReportFile } from "../lib/load";
import type { Report } from "../types/report";

/**
 * Drag-drop / file-pick loader. Used both as the empty state and as a small
 * "load another report" button in the header area.
 */
export function DropZone({
  onLoad,
  compact = false,
}: {
  onLoad: (report: Report) => void;
  compact?: boolean;
}) {
  const [drag, setDrag] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  async function handle(file: File | undefined) {
    if (!file) return;
    setErr(null);
    try {
      onLoad(await parseReportFile(file));
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    }
  }

  const picker = (
    <input
      ref={inputRef}
      type="file"
      accept="application/json,.json"
      style={{ display: "none" }}
      onChange={(e) => handle(e.target.files?.[0])}
    />
  );

  if (compact) {
    return (
      <>
        {picker}
        <button className="btn ghost" onClick={() => inputRef.current?.click()}>
          <Upload size={14} style={{ verticalAlign: "-2px", marginRight: 6 }} />
          Load report
        </button>
      </>
    );
  }

  return (
    <div
      className={`dropzone ${drag ? "drag" : ""}`}
      onDragOver={(e) => {
        e.preventDefault();
        setDrag(true);
      }}
      onDragLeave={() => setDrag(false)}
      onDrop={(e) => {
        e.preventDefault();
        setDrag(false);
        handle(e.dataTransfer.files?.[0]);
      }}
    >
      {picker}
      <Upload size={28} style={{ marginBottom: 10, opacity: 0.7 }} />
      <div style={{ fontSize: 15, color: "var(--text)", marginBottom: 4 }}>
        Drop an agent-risk-scanner report
      </div>
      <div style={{ marginBottom: 16 }}>a <span className="mono">*.json</span> from your scan</div>
      <button className="btn" onClick={() => inputRef.current?.click()}>
        Choose file
      </button>
      {err && <div className="err" style={{ marginTop: 14 }}>{err}</div>}
    </div>
  );
}
