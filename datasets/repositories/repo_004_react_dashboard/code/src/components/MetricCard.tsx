import { Metric } from "../api/client";

export function MetricCard({ metric }: { metric: Metric }) {
  // NOTE: large numbers are not formatted with separators.
  return (
    <div className="metric-card">
      <span className="metric-name">{metric.name}</span>
      <span className="metric-value">{metric.value}</span>
    </div>
  );
}
