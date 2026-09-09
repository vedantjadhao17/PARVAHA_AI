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
  halting_vehicles?: number;
  active_vehicles: number;
  status: string;
  predicted_queue_length_m?: number;
  predicted_capacity_ratio?: number;
  forecast_risk?: string;
  _junction_avg_speed_kmh?: number;
  tls_id?: string;
  raw_state?: string;
  current_phase?: number;
  next_switch?: number;
  remaining_time?: number;
}

export interface CorridorState {
  time_s: number;
  junctions: Record<string, JunctionState>;
  vehicles: VehicleState[];
  active_alerts: {
    id: string;
    incident_name: string;
    severity: string;
  }[];
  pending_recommendations?: any[];
}

interface WebSocketContextType {
  state: CorridorState | null;
  connected: boolean;
}

const WebSocketContext = createContext<WebSocketContextType>({
  state: null,
  connected: false,
});

export const WebSocketProvider: React.FC<{
  children: React.ReactNode;
}> = ({ children }) => {
  const [state, setState] = useState<CorridorState | null>(null);
  const [connected, setConnected] = useState(false);

  useEffect(() => {
    const ws = new WebSocket('ws://localhost:8000/ws/corridor');

    ws.onopen = () => {
      console.log('[PRAVAHA WS] Connected');
      setConnected(true);
    };

    ws.onclose = (event) => {
      // In React StrictMode dev, code 1006 without reason is typical when a component unmounts mid-connection
      const isExpectedDevClose = event.code === 1006 && event.reason === '';
      if (!isExpectedDevClose) {
        console.log(`[PRAVAHA WS] Disconnected. Code: ${event.code}, Reason: ${event.reason || 'None'}`);
      }
      setConnected(false);
    };

    ws.onerror = (error: Event) => {
      // The error event doesn't have a message property. If the socket is closing/closed, it's likely a normal StrictMode cleanup or network drop.
      if (ws.readyState === WebSocket.CLOSING || ws.readyState === WebSocket.CLOSED) {
        console.log('[PRAVAHA WS] WebSocket connection closed unexpectedly (expected in StrictMode dev).');
      } else {
        console.error('[PRAVAHA WS] WebSocket error occurred while connected.');
      }
    };

    ws.onmessage = (event) => {
      try {
        const parsed: CorridorState = JSON.parse(event.data);

        console.log(
          '[PRAVAHA WS] time:',
          parsed.time_s,
          '| alerts:',
          parsed.active_alerts?.length ?? 0,
          '| recommendations:',
          parsed.pending_recommendations?.length ?? 0
        );

        console.log(
          '[PRAVAHA WS] pending_recommendations:',
          parsed.pending_recommendations
        );

        setState(parsed);
      } catch (e) {
        console.error(
          '[PRAVAHA WS] Failed to parse websocket message:',
          e
        );
      }
    };

    return () => {
      ws.close();
    };
  }, []);

  return (
    <WebSocketContext.Provider
      value={{
        state,
        connected,
      }}
    >
      {children}
    </WebSocketContext.Provider>
  );
};

export const useWebSocket = () => useContext(WebSocketContext);