import { useEffect, useState } from 'react';

interface LogEntry {
  id: string;
  operator_id: string;
  action: string;
  resource_id: number;
  location: string;
  reason: string;
  outcome: string;
  audit_hash: string;
  created_at: string;
}

export const OperatorLog = () => {
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch('http://localhost:8000/api/operator-log')
      .then(res => res.json())
      .then(data => {
        if (Array.isArray(data)) setLogs(data); else setLogs([]);
        setLoading(false);
      })
      .catch(err => {
        console.error(err);
        setLoading(false);
      });
  }, []);

  return (
    <div className="p-6">
      <div className="flex justify-between items-center mb-6">
        <h1 className="text-2xl font-bold">Operator Audit Log</h1>
        <span className="text-sm text-gray-500 flex items-center gap-2">
          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
          </svg>
          Immutable Ledger
        </span>
      </div>

      {loading ? (
        <div className="text-gray-400">Loading audit logs...</div>
      ) : logs.length === 0 ? (
        <div className="bg-navy-800 p-8 rounded border border-navy-border text-center text-gray-400">
          No operator actions recorded yet.
        </div>
      ) : (
        <div className="space-y-4">
          {logs.map(log => (
            <div key={log.id} className="bg-navy-800 border border-navy-border rounded p-5">
              <div className="flex justify-between items-start mb-4 border-b border-navy-700 pb-4">
                <div>
                  <div className="flex items-center gap-3">
                    <span className="font-bold text-white text-lg">{log.action}</span>
                    <span className="bg-blue-500/20 text-blue-400 px-2 py-0.5 rounded text-xs font-medium border border-blue-500/30">
                      Recommendation #{log.resource_id}
                    </span>
                  </div>
                  <div className="text-sm text-gray-400 mt-1">
                    {log.location} &bull; Operator: {log.operator_id}
                  </div>
                </div>
                <div className="text-right">
                  <div className="text-sm text-gray-300 font-mono">
                    {log.created_at ? new Date(log.created_at).toLocaleString() : 'Unknown'}
                  </div>
                  <div className="text-xs text-gray-500 font-mono mt-1" title={log.audit_hash}>
                    Hash: {log.audit_hash.substring(0, 16)}...
                  </div>
                </div>
              </div>
              
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <div className="text-xs text-gray-500 uppercase font-bold mb-1">Reason</div>
                  <div className="text-sm text-gray-300">{log.reason}</div>
                </div>
                <div>
                  <div className="text-xs text-gray-500 uppercase font-bold mb-1">Outcome</div>
                  <div className="text-sm text-green-400">{log.outcome}</div>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};
