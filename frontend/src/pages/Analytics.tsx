import { apiFetch as fetch } from '../replay';
import { useEffect, useState } from 'react';
import { useWebSocket } from '../context/WebSocketContext';

interface Trend { time: string; speed: number; queue: number }
export const Analytics = () => {
  const [rows, setRows] = useState<Trend[]>([]);
  const [error, setError] = useState(false);
  const { connected } = useWebSocket();
  useEffect(() => {
    let disposed = false;
    const poll = () => fetch('/api/analytics/trend').then(r => {
      if (!r.ok) throw new Error('Analytics unavailable');
      return r.json();
    }).then(data => { if (!disposed) { setRows(data.data); setError(false); } })
      .catch(() => { if (!disposed) setError(true); });
    poll();
    const timer = setInterval(poll, 5000);
    return () => { disposed = true; clearInterval(timer); };
  }, []);
  return <div className="p-6 space-y-6">
    <h1 className="text-2xl font-bold">Traffic Analytics</h1>
    <p className="text-gray-400">Observed SUMO telemetry, sampled every 5 simulation seconds. Values are junction averages, not measured city traffic. History resets with each scenario.</p>
    {(error || !connected) && <p role="alert" className="text-amber-400">Feed unavailable or stale. Displayed history may be out of date.</p>}
    {rows.length === 0 ? <p className="text-gray-400">Collecting simulation history…</p> :
      <div className="bg-navy-800 border border-navy-border rounded-xl overflow-auto">
        <table className="w-full text-left text-sm"><thead><tr>
          <th className="p-4">Simulation time</th><th className="p-4">Mean speed (km/h)</th><th className="p-4">Mean queue estimate (m)</th>
        </tr></thead><tbody>{[...rows].reverse().map(row =>
          <tr key={row.time} className="border-t border-navy-border"><td className="p-4">{row.time}</td><td className="p-4">{row.speed}</td><td className="p-4">{row.queue}</td></tr>)}
        </tbody></table>
      </div>}
  </div>;
};
