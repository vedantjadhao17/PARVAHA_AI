import { useWebSocket } from '../context/WebSocketContext';

export const Alerts = () => {
  const { state, connected } = useWebSocket();
  const alerts = state?.active_alerts ?? [];
  return <div className="p-6 space-y-6">
    <h1 className="text-2xl font-bold">Simulation Alerts</h1>
    <p className="text-gray-400">Queue thresholds flag congestion in the simulated corridor. Signal proposals appear on the Command Map only after evaluation.</p>
    {!connected ? <p role="status" className="text-amber-400">Waiting for fresh telemetry…</p>
      : alerts.length === 0 ? <p className="text-gray-400">No active queue alerts.</p>
      : alerts.map(item => <div key={item.id} className="p-5 bg-navy-800 border border-navy-border rounded-xl">
          <div className="flex justify-between gap-4"><h2 className="font-semibold">{item.incident_name}</h2><span className="text-amber-400">{item.severity}</span></div>
          <p className="text-gray-400 mt-2 text-sm">{item.id}</p>
        </div>)}
  </div>;
};
