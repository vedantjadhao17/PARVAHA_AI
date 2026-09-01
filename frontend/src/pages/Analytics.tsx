import { useEffect, useState } from 'react';

interface TrendData {
  time: string;
  speed: number;
  queue: number;
}

interface AnalyticsResponse {
  is_sample: boolean;
  data: TrendData[];
}

export const Analytics = () => {
  const [data, setData] = useState<AnalyticsResponse | null>(null);
  
  useEffect(() => {
    fetch('http://localhost:8000/api/analytics/trend')
      .then(res => res.json())
      .then(setData)
      .catch(console.error);
  }, []);

  return (
    <div className="p-6">
      <h1 className="text-2xl font-bold mb-6">Traffic Analytics</h1>
      
      {!data ? (
        <div className="text-gray-400">Loading analytics...</div>
      ) : (
        <div className="space-y-6">
          {data.is_sample && (
            <div className="bg-blue-500/10 border border-blue-500/20 text-blue-400 p-4 rounded text-sm">
              Note: Displaying sample data for demonstration.
            </div>
          )}
          
          <div className="bg-navy-800 border border-navy-border p-6 rounded">
            <h2 className="text-lg font-medium text-white mb-4">Historical Queue & Speed Trends</h2>
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm text-gray-400">
                <thead className="text-xs uppercase bg-navy-900 text-gray-500 border-b border-navy-border">
                  <tr>
                    <th className="px-6 py-3 font-medium">Time</th>
                    <th className="px-6 py-3 font-medium">Mean Speed (km/h)</th>
                    <th className="px-6 py-3 font-medium">Queue Length (m)</th>
                  </tr>
                </thead>
                <tbody>
                  {data.data.map((row, i) => (
                    <tr key={i} className="border-b border-navy-border hover:bg-navy-700/50">
                      <td className="px-6 py-4 font-mono text-white">{row.time}</td>
                      <td className="px-6 py-4 font-mono">{row.speed}</td>
                      <td className="px-6 py-4 font-mono">{row.queue}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
