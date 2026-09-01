import { useEffect, useState } from 'react';

export const SystemHealth = () => {
  const [uptime, setUptime] = useState(0);

  useEffect(() => {
    const timer = setInterval(() => setUptime(prev => prev + 1), 1000);
    return () => clearInterval(timer);
  }, []);

  const formatUptime = (seconds: number) => {
    const h = Math.floor(seconds / 3600);
    const m = Math.floor((seconds % 3600) / 60);
    const s = seconds % 60;
    return `${h}h ${m}m ${s}s`;
  };

  return (
    <div className="p-6">
      <h1 className="text-2xl font-bold mb-6">System Health</h1>
      
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
        <div className="bg-navy-800 p-6 rounded border border-navy-border">
          <div className="text-gray-400 text-sm mb-2">Simulation Engine</div>
          <div className="text-2xl font-bold text-green-400 flex items-center gap-2">
            <div className="w-3 h-3 bg-green-400 rounded-full animate-pulse"></div>
            ONLINE
          </div>
        </div>
        
        <div className="bg-navy-800 p-6 rounded border border-navy-border">
          <div className="text-gray-400 text-sm mb-2">WebSocket Feed</div>
          <div className="text-2xl font-bold text-green-400">1.0 Hz</div>
        </div>

        <div className="bg-navy-800 p-6 rounded border border-navy-border">
          <div className="text-gray-400 text-sm mb-2">ML Inference</div>
          <div className="text-2xl font-bold text-white">42ms avg</div>
        </div>

        <div className="bg-navy-800 p-6 rounded border border-navy-border">
          <div className="text-gray-400 text-sm mb-2">Session Uptime</div>
          <div className="text-2xl font-bold text-white font-mono">{formatUptime(uptime)}</div>
        </div>
      </div>

      <div className="bg-navy-800 border border-navy-border rounded overflow-hidden">
        <div className="bg-navy-900 px-6 py-4 border-b border-navy-border">
          <h2 className="font-semibold text-white">Service Matrix</h2>
        </div>
        <div className="p-6">
          <div className="space-y-4">
            <div className="flex justify-between items-center p-3 hover:bg-navy-700/50 rounded">
              <div className="flex items-center gap-3">
                <div className="w-2 h-2 bg-green-500 rounded-full"></div>
                <span className="text-gray-300">SUMO TraCI</span>
              </div>
              <span className="text-sm text-gray-500">Connected to 127.0.0.1</span>
            </div>
            <div className="flex justify-between items-center p-3 hover:bg-navy-700/50 rounded">
              <div className="flex items-center gap-3">
                <div className="w-2 h-2 bg-green-500 rounded-full"></div>
                <span className="text-gray-300">XGBoost Forecast Service</span>
              </div>
              <span className="text-sm text-gray-500">Loaded queue_5m, queue_10m</span>
            </div>
            <div className="flex justify-between items-center p-3 hover:bg-navy-700/50 rounded">
              <div className="flex items-center gap-3">
                <div className="w-2 h-2 bg-green-500 rounded-full"></div>
                <span className="text-gray-300">SQLite Log Database</span>
              </div>
              <span className="text-sm text-gray-500">Read/Write OK</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
