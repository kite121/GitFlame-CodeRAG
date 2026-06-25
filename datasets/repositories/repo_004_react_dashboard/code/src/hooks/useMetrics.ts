import { useEffect, useState } from "react";
import { fetchMetrics, Metric } from "../api/client";

export function useMetrics(range: string) {
  const [metrics, setMetrics] = useState<Metric[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let active = true;
    fetchMetrics(range).then((data) => {
      if (active) {
        setMetrics(data);
        setLoading(false);
      }
    });
    return () => {
      active = false;
    };
  }, [range]);

  return { metrics, loading };
}
