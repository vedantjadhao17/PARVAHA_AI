import { useEffect, useState } from 'react';
import { useWebSocket } from '../context/WebSocketContext';

interface Health {
  simulation_connected: boolean;
  model_loaded: boolean;
  uptime_s: number;
  scenario: string;
  telemetry_age_s: number | null;
  error: string | null;
  read_only: boolean;
}
export const SystemHealth = () => {
  const [health, setHealth] = useState<Health | null>(null);
  const { connected } = useWebSocket();
  useEffect(() => {
    let disposed = false;
    const poll = () => fetch('/api/health').then(r => {
      if (!r.ok) throw new Error('Health request failed');
      return r.json();
    }).then(data => { if (!disposed) setHealth(data); }).catch(() => { if (!disposed) setHealth(null); });
    poll();
    const timer = setInterval(poll, 3000);
    return () => { disposed = true; clearInterval(timer); };
  }, []);
  const cards = [
    ['SUMO simulation', health?.simulation_connected ? 'Connected' : 'Unavailable'],
    ['Telemetry feed', connected ? 'Receiving updates' : 'Disconnected / stale'],
    ['60-second forecast model', health?.model_loaded ? 'XGBoost loaded' : 'Unavailable'],
    ['Backend uptime', health ? `${health.uptime_s}s` : 'Unavailable'],
  ];
  return <div className="p-6 space-y-6">
    <h1 className="text-2xl font-bold">System Health</h1>
    <p className="text-gray-400">Status reported by the backend and telemetry connection. All traffic is simulated.</p>
    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">{cards.map(([label, value]) =>
      <div key={label} className="p-6 rounded-xl bg-navy-800 border border-navy-border">
        <p className="text-gray-400 text-sm">{label}</p><p className="text-xl mt-2">{value}</p>
      </div>)}</div>
    {health && <p className="text-gray-400">Scenario: {health.scenario} · {health.read_only ? 'Read-only showcase' : 'Local operator mode'}</p>}
    {health?.error && <p role="alert" className="text-amber-400">{health.error}</p>}
  </div>;
};
