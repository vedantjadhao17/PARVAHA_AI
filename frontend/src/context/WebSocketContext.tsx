import { createContext, useContext, useEffect, useState } from 'react';
import type { ReactNode } from 'react';

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
}
const WebSocketContext = createContext<Feed>({ state: null, connected: false, readOnly: true });

export const WebSocketProvider = ({ children }: { children: ReactNode }) => {
  const [state, setState] = useState<CorridorState | null>(null);
  const [connected, setConnected] = useState(false);
  const [readOnly, setReadOnly] = useState(true);

  useEffect(() => {
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

  return <WebSocketContext.Provider value={{ state, connected, readOnly }}>{children}</WebSocketContext.Provider>;
};

export const useWebSocket = () => useContext(WebSocketContext);
