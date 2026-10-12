// Development-only fixture: deliberately long content over the real map components.
// Open /tests/recommendation-overlay.html with Vite. Not part of the production build.
import { createRoot } from 'react-dom/client';
import '../src/index.css';
import { WebSocketProvider } from '../src/context/WebSocketContext';
import { RecommendationPanel } from '../src/components/RecommendationPanel';
import { SimFeedPanel } from '../src/components/SimFeedPanel';

const recommendation = {
  recommendation_id: 'layout-test-only-not-an-actionable-recommendation',
  safety: { passed: true },
  operator_rationale: 'Layout test: this panel must appear above the simulated feed and its controls. Scroll this content to inspect the plan; the action footer must stay visible.',
  source_states: ['J1_SAN', 'J2_SJM', 'J3_SAP'].map((id) => ({
    junction_id: id, tls_id: id, queue_m: 25,
    predicted_queue_60s_m: 40, predicted_capacity_ratio: 0.8,
  })),
  proposal: { candidates: Array.from({length: 6}, (_, i) => ({
    tls_id: 'layout-test-signal-' + i, rationale: 'HOLD baseline — layout test only',
  })) },
  evaluations: [],
};
createRoot(document.getElementById('root')!).render(
  <WebSocketProvider>
    <div className="bg-slate-950 text-white h-screen flex flex-col">
      <h1 className="p-3 shrink-0">Layout test only · Recommendation above simulated map</h1>
      <div className="relative isolate flex-1 min-h-0">
        <div className="absolute inset-4">
          <SimFeedPanel junctionId="J1_SAN" junctionName="Sancheti Chowk"
            queueM={25} haltingVehicles={5} activeVehicles={8}
            rawState="GGGrrr" signalState="GREEN" speed="12" occupancy="62.5"
            predictedQueueM={40} forecastRisk="HIGH" />
        </div>
        <RecommendationPanel recommendations={[recommendation]} />
      </div>
    </div>
  </WebSocketProvider>
);
