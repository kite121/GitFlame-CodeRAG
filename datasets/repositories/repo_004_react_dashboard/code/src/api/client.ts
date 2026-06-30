export interface Metric {
  name: string;
  value: number;
}

export async function fetchMetrics(range: string): Promise<Metric[]> {
  const response = await fetch(`/api/metrics?range=${range}`);
  // BUG: non-2xx responses are not checked before parsing JSON.
  return response.json();
}
