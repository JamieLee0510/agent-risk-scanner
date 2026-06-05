import { useEffect, useState } from "react";
import type { Report } from "./types/report";
import { loadInitialReport } from "./lib/load";
import { Header } from "./components/Header";
import { PosturePanel } from "./components/PosturePanel";
import { FailRateChart } from "./components/FailRateChart";
import { CategoryChart } from "./components/CategoryChart";
import { CaseList } from "./components/CaseList";
import { DropZone } from "./components/DropZone";

export default function App() {
  const [report, setReport] = useState<Report | null>(null);
  const [source, setSource] = useState("");
  const [error, setError] = useState<string | undefined>();
  const [loading, setLoading] = useState(true);
  const [focus, setFocus] = useState<string | null>(null);

  useEffect(() => {
    loadInitialReport().then((r) => {
      setReport(r.report);
      setSource(r.source);
      setError(r.error);
      setLoading(false);
    });
  }, []);

  function adopt(r: Report) {
    setReport(r);
    setSource("uploaded");
    setError(undefined);
    setFocus(null);
  }

  // Scroll a chart-selected case into view and flag it for auto-expand.
  function selectCase(name: string) {
    setFocus(name);
    requestAnimationFrame(() => {
      document.getElementById(`case-${name}`)?.scrollIntoView({
        behavior: "smooth",
        block: "center",
      });
    });
  }

  if (loading) {
    return <div className="app empty">Loading report…</div>;
  }

  if (!report) {
    return (
      <div className="app">
        <h1 style={{ fontSize: 19 }}>Agent Risk Scanner — Report</h1>
        {error && (
          <p className="muted" style={{ fontSize: 12.5 }}>
            Couldn’t load <span className="mono">{source}</span>: <span className="err">{error}</span>
          </p>
        )}
        <div style={{ marginTop: 16 }}>
          <DropZone onLoad={adopt} />
        </div>
      </div>
    );
  }

  return (
    <div className="app">
      <div style={{ display: "flex", justifyContent: "space-between", gap: 16 }}>
        <Header report={report} source={source} />
        <DropZone onLoad={adopt} compact />
      </div>

      <div className="section">
        <PosturePanel report={report} />
      </div>

      <div
        className="section grid"
        style={{ gridTemplateColumns: "1.6fr 1fr", alignItems: "start" }}
      >
        <div className="card">
          <h2 className="section-title">Fail-rate by case</h2>
          <FailRateChart cases={report.results} onSelect={selectCase} />
        </div>
        <div className="card">
          <h2 className="section-title">Outcome by category</h2>
          <CategoryChart cases={report.results} />
        </div>
      </div>

      <div className="section">
        <h2 className="section-title">Cases</h2>
        <CaseList report={report} focus={focus} />
      </div>
    </div>
  );
}
