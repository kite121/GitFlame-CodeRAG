import { useState } from "react";
import { useMetrics } from "../hooks/useMetrics";
import { MetricCard } from "./MetricCard";

export function Dashboard() {
  const [range, setRange] = useState("7d");
  const { metrics, loading } = useMetrics(range);

  if (loading) {
    return <div>Loading...</div>;
  }
  return (
    <div className="dashboard">
      <select value={range} onChange={(e) => setRange(e.target.value)}>
        <option value="7d">7 days</option>
        <option value="30d">30 days</option>
      </select>
      {metrics.map((metric) => (
        <MetricCard key={metric.name} metric={metric} />
      ))}
    </div>
  );
}
