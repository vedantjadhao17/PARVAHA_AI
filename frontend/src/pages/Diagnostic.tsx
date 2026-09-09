import React, { useEffect, useState } from 'react';
import { useWebSocket } from '../context/WebSocketContext';

export const Diagnostic = () => {
  const { state } = useWebSocket();
  const [ticks, setTicks] = useState(0);

  useEffect(() => {
    if (state && ticks < 3) {
      console.log(`[Diagnostic] Tick ${ticks}`);
      console.log(JSON.stringify(state.junctions, null, 2));
      setTicks(t => t + 1);
    }
  }, [state]);

  return <div>Diagnostic Mode</div>;
};
