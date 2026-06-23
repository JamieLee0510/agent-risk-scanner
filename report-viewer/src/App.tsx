import { useEffect, useState } from "react";
import type { Report } from "./types/report";
import { loadInitialReport } from "./lib/load";
import { Header } from "./components/Header";
import { PosturePanel } from "./components/PosturePanel";
import { FailRateChart } from "./components/FailRateChart";
import { CategoryChart } from "./components/CategoryChart";
import { CaseList } from "./components/CaseList";
import { DropZone } from "./components/DropZone";

// Page shell — centered, max-width column. Reused by every render branch.
const SHELL = "mx-auto max-w-[1180px] px-6 pt-7 pb-20";
const SECTION_TITLE = "text-[13px] font-semibold uppercase tracking-[0.06em] text-dim mb-3 mt-0";

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
    return <div className="grid h-full place-items-center text-dim">Loading report…</div>;
  }

  if (!report) {
    return (
      <div className={SHELL}>
        <h1 className="text-[19px] font-semibold">Agent Risk Scanner — Report</h1>
        {error && (
          <p className="text-[12.5px] text-faint">
            Couldn’t load <span className="font-mono">{source}</span>:{" "}
            <span className="text-[12.5px] text-critical">{error}</span>
          </p>
        )}
        <div className="mt-4">
          <DropZone onLoad={adopt} />
        </div>
      </div>
    );
  }

  return (
    <div className={SHELL}>
      <div className="flex justify-between gap-4">
        <Header report={report} source={source} />
        <DropZone onLoad={adopt} compact />
      </div>

      <div className="mt-[26px]">
        <PosturePanel report={report} />
      </div>

      <div className="mt-[26px] grid items-start gap-[14px] [grid-template-columns:1.6fr_1fr]">
        <div className="card">
          <h2 className={SECTION_TITLE}>Fail-rate by case</h2>
          <FailRateChart cases={report.results} onSelect={selectCase} />
        </div>
        <div className="card">
          <h2 className={SECTION_TITLE}>Outcome by category</h2>
          <CategoryChart cases={report.results} />
        </div>
      </div>

      <div className="mt-[26px]">
        <h2 className={SECTION_TITLE}>Cases</h2>
        <CaseList report={report} focus={focus} />
      </div>
    </div>
  );
}
