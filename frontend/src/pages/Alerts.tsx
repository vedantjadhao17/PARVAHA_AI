import { useEffect, useState } from 'react';

interface Alert {
  id: number;
  junction_id: string;
  severity: string;
  message: string;
  recommendation_id: number | null;
  created_at: string;
}

export const Alerts = () => {
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [loading, setLoading] = useState(true);
  
  // We can optionally use the websocket to trigger re-fetches if an alert comes through, 
  // but for now, we'll poll or fetch on mount. Let's fetch on mount and every 5 seconds.
  
  useEffect(() => {
    const fetchAlerts = async () => {
      try {
        const res = await fetch('http://localhost:8000/api/alerts');
        if (res.ok) {
          const data = await res.json();
          setAlerts(data);
        }
      } catch (err) {
        console.error("Failed to fetch alerts", err);
      } finally {
        setLoading(false);
      }
    };
    
    fetchAlerts();
    const interval = setInterval(fetchAlerts, 5000);
    return () => clearInterval(interval);
  }, []);

  const handleApprove = async (recommendationId: number | null, alertId: number) => {
    if (!recommendationId) return;
    try {
      const res = await fetch(`http://localhost:8000/api/recommendations/${recommendationId}/approve`, {
        method: 'POST'
      });
      if (res.ok) {
        // Refresh alerts
        const newAlerts = alerts.filter(a => a.id !== alertId);
        setAlerts(newAlerts);
        alert("Recommendation approved successfully");
      } else {
        alert("Failed to approve: Safety constraints may have failed.");
      }
    } catch (err) {
      console.error(err);
    }
  };

  return (
    <div className="p-6">
      <div className="flex justify-between items-center mb-6">
        <h1 className="text-2xl font-bold">Active Alerts</h1>
        <span className="bg-red-500/20 text-red-400 px-3 py-1 rounded text-sm font-medium border border-red-500/30">
          {alerts.length} Critical
        </span>
      </div>
      
      {loading ? (
        <div className="text-gray-400">Loading alerts...</div>
      ) : alerts.length === 0 ? (
        <div className="bg-navy-800 p-8 rounded border border-navy-border text-center text-gray-400">
          No active alerts. Corridor traffic is nominal.
        </div>
      ) : (
        <div className="space-y-4">
          {alerts.map(alert => (
            <div key={alert.id} className="bg-navy-800 border-l-4 border-l-red-500 border-t border-r border-b border-navy-border rounded p-5 flex flex-col md:flex-row gap-4 justify-between items-start md:items-center">
              <div>
                <div className="flex items-center gap-3 mb-2">
                  <span className="font-bold text-white">{alert.junction_id}</span>
                  <span className="text-xs text-gray-400">{new Date(alert.created_at).toLocaleTimeString()}</span>
                </div>
                <p className="text-gray-300">{alert.message}</p>
                {alert.recommendation_id && (
                  <p className="text-sm text-yellow-400 mt-2 flex items-center gap-2">
                    <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
                    </svg>
                    AI Signal Recommendation available (ID: {alert.recommendation_id})
                  </p>
                )}
              </div>
              
              <div className="flex gap-3">
                <button className="px-4 py-2 bg-navy-700 hover:bg-navy-600 border border-navy-border rounded text-sm text-white transition-colors">
                  Dismiss
                </button>
                {alert.recommendation_id && (
                  <button 
                    onClick={() => handleApprove(alert.recommendation_id, alert.id)}
                    className="px-4 py-2 bg-blue-600 hover:bg-blue-500 rounded text-sm text-white font-medium transition-colors">
                    Approve Plan
                  </button>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};
