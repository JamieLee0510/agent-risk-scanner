/**
 * Loading a report into the dashboard. Three sources, in priority order:
 *   1. a global `window.__REPORT__` injected by a self-contained export
 *      (so `arscan report --html` can ship one clickable file)
 *   2. a `?report=<url>` query param
 *   3. the bundled public/sample-report.json fallback
 * The user can also drop or pick a file at runtime (parseReportFile).
 */
import { assertReport, type Report } from "../types/report";

declare global {
  interface Window {
    __REPORT__?: unknown;
  }
}

export function parseReport(text: string): Report {
  const value = JSON.parse(text);
  assertReport(value);
  return value;
}

export async function parseReportFile(file: File): Promise<Report> {
  return parseReport(await file.text());
}

export interface InitialLoad {
  report: Report | null;
  source: string;
  error?: string;
}

export async function loadInitialReport(): Promise<InitialLoad> {
  if (window.__REPORT__ !== undefined) {
    try {
      assertReport(window.__REPORT__);
      return { report: window.__REPORT__, source: "embedded" };
    } catch (e) {
      return { report: null, source: "embedded", error: errMsg(e) };
    }
  }

  const params = new URLSearchParams(window.location.search);
  const url = params.get("report") ?? "./sample-report.json";
  try {
    const res = await fetch(url);
    if (!res.ok) throw new Error(`HTTP ${res.status} fetching ${url}`);
    const report = parseReport(await res.text());
    return { report, source: url };
  } catch (e) {
    return { report: null, source: url, error: errMsg(e) };
  }
}

function errMsg(e: unknown): string {
  return e instanceof Error ? e.message : String(e);
}
