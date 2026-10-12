import { BrowserRouter, HashRouter, Routes, Route, Link } from 'react-router-dom';
import { isReplay } from './replay';
const Router = isReplay ? HashRouter : BrowserRouter;
import { WebSocketProvider, useWebSocket } from './context/WebSocketContext';
import { LayoutDashboard, Bell, Activity, ActivitySquare, ShieldAlert, FileText } from 'lucide-react';

import { CommandMap } from './pages/CommandMap';

import { Alerts, Junctions, Analytics, SystemHealth, OperatorLog } from './pages/Pages';

import { useState } from 'react';

const Sidebar = () => {
  const [isHovered, setIsHovered] = useState(false);

  return (
    <div className="relative w-16 h-screen flex-shrink-0 z-[2000]">
      <div 
        className={`absolute top-0 left-0 h-screen bg-navy-800 border-r border-navy-border flex flex-col py-4 transition-all duration-300 ease-in-out overflow-hidden shadow-2xl ${isHovered ? 'w-64 px-4' : 'w-16 px-3 items-center'}`}
        onMouseEnter={() => setIsHovered(true)}
        onMouseLeave={() => setIsHovered(false)}
      >
        <div className={`flex items-center mb-8 text-white font-bold text-lg whitespace-nowrap ${isHovered ? '' : 'justify-center'}`}>
          <div className="text-blue-500">
            {isHovered ? 'PRAVAHA·AI' : 'P·'}
          </div>
        </div>
        
        <nav className="flex-1 space-y-3 w-full">
          <Link to="/" aria-label="Command Map" title="Command Map" className={`flex items-center text-gray-300 hover:bg-navy-700 hover:text-white rounded transition-colors whitespace-nowrap ${isHovered ? 'p-2 space-x-3' : 'p-2 justify-center'}`}>
            <LayoutDashboard size={20} className="flex-shrink-0" /> 
            {isHovered && <span className="animate-in fade-in duration-300">Command Map</span>}
          </Link>
          <Link to="/alerts" aria-label="Alerts" title="Alerts" className={`flex items-center text-gray-300 hover:bg-navy-700 hover:text-white rounded transition-colors whitespace-nowrap ${isHovered ? 'p-2 space-x-3' : 'p-2 justify-center'}`}>
            <Bell size={20} className="flex-shrink-0" /> 
            {isHovered && <span className="animate-in fade-in duration-300">Alerts</span>}
          </Link>
          <Link to="/junctions" aria-label="Junctions" title="Junctions" className={`flex items-center text-gray-300 hover:bg-navy-700 hover:text-white rounded transition-colors whitespace-nowrap ${isHovered ? 'p-2 space-x-3' : 'p-2 justify-center'}`}>
            <Activity size={20} className="flex-shrink-0" /> 
            {isHovered && <span className="animate-in fade-in duration-300">Junctions</span>}
          </Link>
          <Link to="/analytics" aria-label="Analytics" title="Analytics" className={`flex items-center text-gray-300 hover:bg-navy-700 hover:text-white rounded transition-colors whitespace-nowrap ${isHovered ? 'p-2 space-x-3' : 'p-2 justify-center'}`}>
            <ActivitySquare size={20} className="flex-shrink-0" /> 
            {isHovered && <span className="animate-in fade-in duration-300">Analytics</span>}
          </Link>
          <Link to="/system-health" aria-label="System Health" title="System Health" className={`flex items-center text-gray-300 hover:bg-navy-700 hover:text-white rounded transition-colors whitespace-nowrap ${isHovered ? 'p-2 space-x-3' : 'p-2 justify-center'}`}>
            <ShieldAlert size={20} className="flex-shrink-0" /> 
            {isHovered && <span className="animate-in fade-in duration-300">System Health</span>}
          </Link>
          <Link to="/operator-log" aria-label="Operator Log" title="Operator Log" className={`flex items-center text-gray-300 hover:bg-navy-700 hover:text-white rounded transition-colors whitespace-nowrap ${isHovered ? 'p-2 space-x-3' : 'p-2 justify-center'}`}>
            <FileText size={20} className="flex-shrink-0" /> 
            {isHovered && <span className="animate-in fade-in duration-300">Operator Log</span>}
          </Link>
        </nav>

        <div className={`pt-4 border-t border-navy-border flex items-center text-sm text-gray-400 whitespace-nowrap ${isHovered ? '' : 'justify-center'}`}>
          <span className="w-2 h-2 rounded-full bg-status-green flex-shrink-0"></span>
          {isHovered && <span className="ml-2 animate-in fade-in duration-300">Simulation prototype</span>}
        </div>
      </div>
    </div>
  );
};

const Topbar = () => {
  const { connected } = useWebSocket();
  return (
  <div className="min-h-10 shrink-0 border-b border-navy-border bg-navy-800 flex flex-wrap gap-2 items-center justify-between px-4 py-2">
    <h1 className="text-base font-semibold text-white">PRAVAHA AI · Traffic Simulation</h1>
    <div className="flex items-center space-x-3">
      <div className="px-2 py-0.5 bg-slate-700 text-slate-100 text-[10px] font-bold rounded-full flex items-center space-x-1.5 uppercase tracking-wide">
        <span>{isReplay ? (connected ? 'RECORDED REPLAY' : 'LOADING REPLAY') : connected ? 'SIMULATION CONNECTED' : 'CONNECTING / STALE'}</span>
      </div>
      <div className="text-xs text-gray-400">Research prototype</div>
    </div>
  </div>
  );
};

const ReplayControls = () => {
  const { state, paused, togglePause, seek } = useWebSocket();
  if (!isReplay) return null;
  return <div className="px-4 py-2 bg-blue-950 border-b border-blue-800 text-xs space-y-2">
    <p>Recorded SUMO simulation · 2× playback · Not live city traffic. Forecasts were computed during recording.</p>
    <div className="flex items-center gap-3">
      <button className="px-3 py-1 rounded bg-blue-700" onClick={togglePause}>{paused ? 'Play' : 'Pause'}</button>
      <input aria-label="Replay simulation time" className="flex-1 min-w-0" type="range" min="2" max="600" step="2" value={state?.time_s ?? 242} onChange={e => seek(Number(e.target.value))} />
      <span className="w-16">{state?.time_s ?? 0}s / 600s</span>
      <a className="underline" href="https://github.com/vedantjadhao17/PARVAHA_AI" target="_blank" rel="noreferrer">Code</a>
    </div>
  </div>;
};

function App() {
  return (
    <WebSocketProvider>
      <Router>
        <div className="flex h-screen bg-[var(--color-navy-900)] text-white font-sans overflow-hidden">
          <Sidebar />
          <div className="flex-1 flex flex-col min-w-0">
            <Topbar />
            <ReplayControls />
            <main className="flex-1 overflow-auto">
              <Routes>
                <Route path="/" element={<CommandMap />} />
                <Route path="/alerts" element={<Alerts />} />
                <Route path="/junctions" element={<Junctions />} />
                <Route path="/analytics" element={<Analytics />} />
                <Route path="/system-health" element={<SystemHealth />} />
                <Route path="/operator-log" element={<OperatorLog />} />
              </Routes>
            </main>
          </div>
        </div>
      </Router>
    </WebSocketProvider>
  )
}

export default App;
