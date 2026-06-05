import ReactECharts from "echarts-for-react";
import type { CaseEntry } from "../types/report";

/**
 * Per-category stacked bar of case outcomes (secure vs intermittent vs
 * breached). Answers "which attack family is the agent weakest against".
 */
export function CategoryChart({ cases }: { cases: CaseEntry[] }) {
  const cats = Array.from(new Set(cases.map((c) => c.category))).sort();

  const breached: number[] = [];
  const intermittent: number[] = [];
  const secure: number[] = [];
  for (const cat of cats) {
    const inCat = cases.filter((c) => c.category === cat);
    breached.push(inCat.filter((c) => c.fail_rate >= 1).length);
    intermittent.push(inCat.filter((c) => c.fail_rate > 0 && c.fail_rate < 1).length);
    secure.push(inCat.filter((c) => c.fail_rate === 0).length);
  }

  const mkSeries = (name: string, data: number[], color: string) => ({
    name,
    type: "bar",
    stack: "total",
    data,
    barWidth: 18,
    itemStyle: { color },
  });

  const option = {
    grid: { left: 4, right: 12, top: 8, bottom: 6, containLabel: true },
    legend: {
      top: "bottom",
      textStyle: { color: "#9ba1ad", fontSize: 11 },
      itemWidth: 10,
      itemHeight: 10,
    },
    tooltip: {
      trigger: "axis",
      axisPointer: { type: "shadow" },
      backgroundColor: "#181b22",
      borderColor: "#272b34",
      textStyle: { color: "#e6e8ec", fontSize: 12 },
    },
    xAxis: {
      type: "value",
      minInterval: 1,
      axisLabel: { color: "#9ba1ad", fontSize: 11 },
      splitLine: { lineStyle: { color: "#1f232c" } },
    },
    yAxis: {
      type: "category",
      data: cats,
      axisLabel: { color: "#c3c7cf", fontSize: 11 },
      axisLine: { lineStyle: { color: "#272b34" } },
      axisTick: { show: false },
    },
    series: [
      mkSeries("Breached", breached, "#e5484d"),
      mkSeries("Intermittent", intermittent, "#ffb224"),
      mkSeries("Secure", secure, "#30a46c"),
    ],
  };

  const height = Math.max(150, cats.length * 46 + 50);
  return <ReactECharts style={{ height }} option={option} opts={{ renderer: "svg" }} />;
}
