import React, { createContext, useContext, useEffect, useState } from 'react';

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
  active_vehicles: number;
  signal_state: 'GREEN' | 'YELLOW' | 'RED' | 'UNKNOWN';
  status: string;
}

export interface CorridorState {
  time_s: number;
  junctions: Record<string, JunctionState>;
  vehicles: VehicleState[];
  active_alerts: { id: string; incident_name: string; severity: string }[];
}

interface WebSocketContextType {
  state: CorridorState | null;
  connected: boolean;
}

const WebSocketContext = createContext<WebSocketContextType>({ state: null, connected: false });

export const WebSocketProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [state, setState] = useState<CorridorState | null>(null);
  const [connected, setConnected] = useState(false);

  useEffect(() => {
    const ws = new WebSocket('ws://localhost:8000/ws/corridor');
    ws.onopen = () => setConnected(true);
    ws.onclose = () => setConnected(false);
    ws.onmessage = (event) => {
      try {
        setState(JSON.parse(event.data));
      } catch (e) {
        console.error('Failed to parse websocket message', e);
      }
    };
    return () => ws.close();
  }, []);

  return (
    <WebSocketContext.Provider value={{ state, connected }}>
      {children}
    </WebSocketContext.Provider>
  );
};

export const useWebSocket = () => useContext(WebSocketContext);
