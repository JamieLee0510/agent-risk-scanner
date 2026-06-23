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
      className="hidden"
      onChange={(e) => handle(e.target.files?.[0])}
    />
  );

  if (compact) {
    return (
      <>
        {picker}
        <button className="btn btn-ghost" onClick={() => inputRef.current?.click()}>
          <Upload size={14} className="mr-1.5 -mb-0.5 inline" />
          Load report
        </button>
      </>
    );
  }

  return (
    <div
      className={`rounded-xl border-[1.5px] border-dashed p-10 text-center text-dim transition-all ${
        drag ? "border-accent bg-accent/[0.06]" : "border-line-strong"
      }`}
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
      <Upload size={28} className="mx-auto mb-2.5 opacity-70" />
      <div className="mb-1 text-[15px] text-text">Drop an agent-risk-scanner report</div>
      <div className="mb-4">
        a <span className="font-mono">*.json</span> from your scan
      </div>
      <button className="btn" onClick={() => inputRef.current?.click()}>
        Choose file
      </button>
      {err && <div className="mt-3.5 text-[12.5px] text-critical">{err}</div>}
    </div>
  );
}
