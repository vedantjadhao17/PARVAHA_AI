import type { CorridorState } from './context/WebSocketContext';

export const isReplay = import.meta.env.VITE_DEMO_MODE === 'replay';
interface Bundle {
  metadata: { scenario: string; sample_interval_s: number; duration_s: number; note: string };
  frames: CorridorState[];
  trend: { time: string; simulation_time_s: number; speed: number; queue: number }[];
  config: unknown;
  geometry: unknown;
  cameras: Record<string, unknown>;
}
let bundlePromise: Promise<Bundle> | undefined;
let frameIndex = 0;
export function loadReplay(): Promise<Bundle> {
  return bundlePromise ??= globalThis.fetch(import.meta.env.BASE_URL + 'replay.json')
    .then(response => {
      if (!response.ok) throw new Error('Replay could not load');
      return response.json();
    });
}
export function selectReplayFrame(index: number) { frameIndex = index; }

// Only static demo builds use recorded endpoints. Live builds use the real API.
export async function apiFetch(url: string, init?: RequestInit): Promise<Response> {
  if (!isReplay) return globalThis.fetch(url, init);
  if (init?.method && init.method !== 'GET') {
    return Response.json({ detail: 'Recorded showcase: signal controls are disabled.' }, { status: 403 });
  }
  const bundle = await loadReplay();
  const current = bundle.frames[frameIndex];
  const routes: Record<string, unknown> = {
    '/api/corridor/state': current,
    '/api/junctions/config': bundle.config,
    '/api/network/geometry': bundle.geometry,
    '/api/alerts': current.active_alerts,
    '/api/operator-log': [],
    '/api/health': { mode: 'recorded_simulation', read_only: true, scenario: bundle.metadata.scenario },
    '/api/analytics/trend': {
      is_sample: false, source: 'Recorded SUMO simulation',
      data: bundle.trend.filter(row => row.simulation_time_s <= current.time_s),
    },
  };
  if (url.startsWith('/api/junction/camera/')) {
    const camera = bundle.cameras[url.split('/').pop()!];
    return Response.json(camera ?? { detail: 'Unknown junction' }, { status: camera ? 200 : 404 });
  }
  return Response.json(routes[url] ?? { detail: 'Unavailable in replay' }, { status: url in routes ? 200 : 404 });
}
