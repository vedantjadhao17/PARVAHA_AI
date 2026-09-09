import React, { useState } from 'react';
import { AlertTriangle, Check, X, ShieldAlert, Zap, GitCommit } from 'lucide-react';

export const RecommendationPanel = ({
  recommendations,
  onActionComplete
}: {
  recommendations: any[];
  onActionComplete?: () => void;
}) => {
  const [loading, setLoading] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  if (!recommendations || recommendations.length === 0) return null;

  const rec = recommendations[0];
  const isCorridor = true; // All Phase 4+ recommendations are corridor level
  
  const handleAction = async (action: 'approve' | 'reject') => {
    setLoading(action);
    setError(null);
    
    const url = `http://localhost:8000/api/recommendations/${rec.recommendation_id}/${action}`;
    console.log(`[PRAVAHA ACTION] method=POST url=${url} recommendationId=${rec.recommendation_id}`);
    
    try {
      const res = await fetch(url, {
        method: 'POST'
      });
      const data = await res.json();
      console.log(`[PRAVAHA ACTION] response=${JSON.stringify(data)}`);
      
      if (!res.ok) {
        setError(data.detail || data.error || 'Failed to apply action');
      } else {
        if (onActionComplete) onActionComplete();
      }
    } catch (e: any) {
      console.log(`[PRAVAHA ACTION] fetch failed:`, e);
      setError(e.message);
    } finally {
      setLoading(null);
    }
  };

  const getRiskColor = (risk: string) => {
    if (risk === "SPILLBACK") return "text-purple-400 font-bold";
    if (risk === "HIGH") return "text-red-400 font-bold";
    if (risk === "MEDIUM") return "text-yellow-400";
    return "text-green-400";
  };

  return (
    <div className="absolute right-4 top-4 w-[450px] bg-slate-900 border-2 border-slate-700 shadow-2xl rounded-xl text-sm flex flex-col z-50 overflow-hidden" style={{ maxHeight: 'calc(100% - 2rem)' }}>
      <div className="bg-gradient-to-r from-blue-900 to-slate-900 p-4 border-b border-slate-700 flex justify-between items-start shrink-0">
        <div>
          <h3 className="text-blue-400 font-black tracking-wider text-xs mb-1">
            {isCorridor ? "CORRIDOR INTELLIGENCE" : "AI DECISION SUPPORT"}
          </h3>
          <div className="text-white font-bold text-lg flex items-center gap-2">
            <Zap size={18} className="text-yellow-400" />
            PENDING RECOMMENDATION
          </div>
          <div className="text-slate-400 text-xs font-mono mt-1 opacity-50">
            {rec.recommendation_id}
          </div>
        </div>
        {rec.safety?.passed && (
          <div className="bg-emerald-500/20 text-emerald-400 px-2 py-1 rounded text-xs font-bold border border-emerald-500/30 flex items-center gap-1">
            <Check size={14} /> SAFE
          </div>
        )}
      </div>

      <div className="p-4 space-y-5 flex-1 overflow-y-auto">
        {/* RATIONALE & WHY */}
        <div className="space-y-2">
          <div className="text-slate-400 text-xs font-bold tracking-wider">WHY THIS ALERT?</div>
          <div className="bg-slate-800 p-3 rounded-lg border border-slate-700/50 text-slate-300 italic">
            "{rec.operator_rationale}"
          </div>
        </div>

        {/* CURRENT STATE & FORECAST */}
        <div className="space-y-2">
          <div className="text-slate-400 text-xs font-bold tracking-wider">
            {isCorridor ? "CORRIDOR STATE (J1 → J2 → J3)" : "CURRENT STATE"}
          </div>
          <div className="bg-slate-800 p-3 rounded-lg border border-slate-700/50 space-y-3">
            {rec.source_states.map((st: any, i: number) => (
              <div key={st.tls_id} className={i > 0 ? "border-t border-slate-700 pt-2" : ""}>
                <div className="flex justify-between items-center mb-1">
                  <span className="font-bold text-white">{st.junction_id}</span>
                  <span className={getRiskColor(st.predicted_capacity_ratio >= 1.0 ? "SPILLBACK" : st.predicted_capacity_ratio >= 0.8 ? "HIGH" : "LOW")}>
                    {st.predicted_capacity_ratio >= 1.0 ? "SPILLBACK" : st.predicted_capacity_ratio >= 0.8 ? "HIGH" : "LOW"}
                  </span>
                </div>
                <div className="grid grid-cols-2 gap-2 text-xs">
                  <div>
                    <span className="text-slate-500">Current Q: </span>
                    <span className="text-white">{st.queue_m?.toFixed(1)}m</span>
                  </div>
                  <div>
                    <span className="text-slate-500">Forecast +60s: </span>
                    <span className="text-blue-400 font-bold">{st.predicted_queue_60s_m?.toFixed(1)}m</span>
                  </div>
                  <div>
                    <span className="text-slate-500">Cap Ratio: </span>
                    <span className="text-white">{st.predicted_capacity_ratio?.toFixed(2)}x</span>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* PROPOSED COORDINATED PLAN */}
        <div className="space-y-2">
          <div className="text-slate-400 text-xs font-bold tracking-wider">PROPOSED PLAN</div>
          <div className="bg-blue-900/20 p-3 rounded-lg border border-blue-500/30 space-y-2">
             {rec.proposal.candidates.map((c: any) => (
                <div key={c.tls_id} className="flex flex-col gap-1">
                  <div className="text-white font-bold text-xs">{c.tls_id}</div>
                  <div className="text-slate-300 text-xs">
                    {c.rationale.includes("HOLD") || c.rationale.includes("baseline") ? (
                      <span className="text-slate-500 italic">HOLD (No changes)</span>
                    ) : (
                      <span className="text-blue-300">{c.rationale}</span>
                    )}
                  </div>
                </div>
             ))}
             {rec.evaluations?.map((ev: any, i: number) => (
                <div key={`ev-${i}-${ev.tls_id}-${ev.candidate_id}`} className="mt-2 text-[10px] text-gray-400 border-t border-slate-700 pt-1">
                  Eval ({ev.tls_id}): {ev.safety.passed ? <span className="text-green-400">SAFE</span> : <span className="text-red-400">UNSAFE</span>} - Max Q: {ev.max_queue_m?.toFixed(1)}m
                </div>
             ))}
          </div>
        </div>

        {error && (
          <div className="bg-red-500/20 text-red-400 p-3 rounded-lg border border-red-500/50 flex gap-2 items-start text-xs">
            <AlertTriangle size={16} className="shrink-0 mt-0.5" />
            <div>{error}</div>
          </div>
        )}
      </div>

      {/* APPROVAL FOOTER */}
      <div className="p-4 bg-slate-900 border-t border-slate-700 flex gap-3 shrink-0">
        <button
          onClick={() => handleAction('reject')}
          disabled={loading !== null}
          className="flex-1 bg-slate-800 hover:bg-slate-700 text-white font-bold py-3 rounded border border-slate-600 transition disabled:opacity-50"
        >
          {loading === 'reject' ? 'REJECTING...' : 'REJECT'}
        </button>
        <button
          onClick={() => handleAction('approve')}
          disabled={loading !== null}
          className="flex-[2] bg-blue-600 hover:bg-blue-500 text-white font-black py-3 rounded shadow-[0_0_15px_rgba(37,99,235,0.5)] transition disabled:opacity-50 flex items-center justify-center gap-2"
        >
          {loading === 'approve' ? 'APPLYING...' : 'APPROVE & APPLY'}
        </button>
      </div>
    </div>
  );
};
