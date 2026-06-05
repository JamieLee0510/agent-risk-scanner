import ReactECharts from "echarts-for-react";
import type { CaseEntry } from "../types/report";
import { SEVERITY_COLOR, severityOf, severityRank } from "../lib/risk";

/**
 * Horizontal bar of fail-rate per case, worst at the top, bars colored by
 * severity. This is the "where am I exposed" view — one glance ranks every
 * case by how reliably the attack lands.
 */
export function FailRateChart({
  cases,
  onSelect,
}: {
  cases: CaseEntry[];
  onSelect?: (caseName: string) => void;
}) {
  const sorted = [...cases].sort(
    (a, b) => severityRank(b) - severityRank(a) || b.fail_rate - a.fail_rate,
  );

  const names = sorted.map((c) => c.case);
  const data = sorted.map((c) => ({
    value: +(c.fail_rate * 100).toFixed(1),
    itemStyle: { color: SEVERITY_COLOR[severityOf(c)], borderRadius: [0, 3, 3, 0] },
    kind: c.kind,
  }));

  const height = Math.max(160, sorted.length * 26 + 40);

  const option = {
    grid: { left: 4, right: 44, top: 8, bottom: 8, containLabel: true },
    tooltip: {
      trigger: "axis",
      axisPointer: { type: "shadow" },
      backgroundColor: "#181b22",
      borderColor: "#272b34",
      textStyle: { color: "#e6e8ec", fontSize: 12 },
      formatter: (ps: { dataIndex: number }[]) => {
        const c = sorted[ps[0].dataIndex];
        const vc = c.verdict_counts;
        return `<b>${c.case}</b><br/>${c.category} · ${c.kind}<br/>fail-rate ${(c.fail_rate * 100).toFixed(0)}%<br/>pass ${vc.pass} · fail ${vc.fail} · inconc ${vc.inconclusive} · err ${vc.error}`;
      },
    },
    xAxis: {
      type: "value",
      max: 100,
      axisLabel: { formatter: "{value}%", color: "#9ba1ad", fontSize: 11 },
      splitLine: { lineStyle: { color: "#1f232c" } },
    },
    yAxis: {
      type: "category",
      inverse: true,
      data: names,
      axisLabel: { color: "#c3c7cf", fontSize: 11.5 },
      axisLine: { lineStyle: { color: "#272b34" } },
      axisTick: { show: false },
    },
    series: [
      {
        type: "bar",
        data,
        barWidth: 13,
        label: {
          show: true,
          position: "right",
          formatter: (p: { value: number }) => `${p.value}%`,
          color: "#9ba1ad",
          fontSize: 11,
        },
      },
    ],
  };

  return (
    <ReactECharts
      style={{ height }}
      option={option}
      opts={{ renderer: "svg" }}
      onEvents={{
        click: (p: { name: string }) => onSelect?.(p.name),
      }}
    />
  );
}
