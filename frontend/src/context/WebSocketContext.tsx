import { apiFetch as fetch } from '../replay';
import { createContext, useContext, useEffect, useState } from 'react';
import type { ReactNode } from 'react';
import { isReplay, loadReplay, selectReplayFrame } from '../replay';

export interface VehicleState {
  id: string;
  lon: number | null;
  lat: number | null;
  speed: number;
}
export interface JunctionState {
  id: string;
  name: string;
  queue_m: number;
  halting_vehicles?: number;
  active_vehicles: number;
  status: string;
  predicted_queue_length_m?: number;
  predicted_capacity_ratio?: number;
  forecast_risk?: string;
  _junction_avg_speed_kmh?: number;
  tls_id?: string;
  raw_state?: string;
  signal_state: 'GREEN' | 'YELLOW' | 'RED' | 'UNKNOWN';
  current_phase?: number;
  next_switch?: number;
  remaining_time?: number;
}
export interface CorridorState {
  time_s: number;
  junctions: Record<string, JunctionState>;
  vehicles: VehicleState[];
  active_alerts: { id: string; incident_name: string; severity: string }[];
  pending_recommendations?: any[];
}
interface Feed {
  state: CorridorState | null;
  connected: boolean;
  readOnly: boolean;
  paused: boolean;
  togglePause: () => void;
  seek: (seconds: number) => void;
}
const WebSocketContext = createContext<Feed>({ state: null, connected: false, readOnly: true, paused: false, togglePause: () => {}, seek: () => {} });

export const WebSocketProvider = ({ children }: { children: ReactNode }) => {
  const [state, setState] = useState<CorridorState | null>(null);
  const [connected, setConnected] = useState(false);
  const [readOnly, setReadOnly] = useState(true);

  const [paused, setPaused] = useState(false);
  const [replayIndex, setReplayIndex] = useState(120);
  useEffect(() => {
    if (!isReplay) return;
    let disposed = false;
    loadReplay().then(bundle => {
      if (disposed) return;
      const index = replayIndex % bundle.frames.length;
      selectReplayFrame(index);
      setState(bundle.frames[index]);
      setConnected(true);
    }).catch(() => { if (!disposed) setConnected(false); });
    return () => { disposed = true; };
  }, [replayIndex]);
  useEffect(() => {
    if (!isReplay || paused) return;
    const timer = setInterval(() => setReplayIndex(index => (index + 1) % 300), 1000);
    return () => clearInterval(timer);
  }, [paused]);

  useEffect(() => {
    if (isReplay) return;
    let disposed = false;
    let socket: WebSocket;
    let retry: ReturnType<typeof setTimeout>;
    let lastMessage = 0;
    let lastSimulationTime: number | null = null;
    fetch('/api/health').then(r => {
      if (!r.ok) throw new Error('Health unavailable');
      return r.json();
    }).then(data => { if (!disposed) setReadOnly(data.read_only !== false); }).catch(() => {});
    const connect = () => {
      if (disposed) return;
      socket = new WebSocket(`${location.protocol === 'https:' ? 'wss:' : 'ws:'}//${location.host}/ws/corridor`);
      socket.onmessage = event => {
        try {
          const data: CorridorState = JSON.parse(event.data);
          if (!data.junctions || typeof data.time_s !== 'number') return;
          if (data.time_s !== lastSimulationTime) {
            lastMessage = Date.now();
            lastSimulationTime = data.time_s;
          }
          setState(data);
          setConnected(Date.now() - lastMessage < 5000);
        } catch { setConnected(false); }
      };
      socket.onclose = () => {
        if (disposed) return;
        setConnected(false);
        retry = setTimeout(connect, 2000);
      };
      socket.onerror = () => socket.close();
    };
    connect();
    const staleCheck = setInterval(() => {
      if (Date.now() - lastMessage > 5000) setConnected(false);
    }, 1000);
    return () => {
      disposed = true;
      clearTimeout(retry);
      clearInterval(staleCheck);
      socket?.close();
    };
  }, []);

  return <WebSocketContext.Provider value={{ state, connected, readOnly, paused,
    togglePause: () => setPaused(value => !value),
    seek: seconds => setReplayIndex(Math.max(0, Math.min(299, Math.round(seconds / 2) - 1))),
  }}>{children}</WebSocketContext.Provider>;
};

export const useWebSocket = () => useContext(WebSocketContext);
