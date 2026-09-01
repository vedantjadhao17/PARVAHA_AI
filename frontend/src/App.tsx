import { BrowserRouter as Router, Routes, Route, Link } from 'react-router-dom';
import { WebSocketProvider } from './context/WebSocketContext';
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
          <Link to="/" className={`flex items-center text-gray-300 hover:bg-navy-700 hover:text-white rounded transition-colors whitespace-nowrap ${isHovered ? 'p-2 space-x-3' : 'p-2 justify-center'}`}>
            <LayoutDashboard size={20} className="flex-shrink-0" /> 
            {isHovered && <span className="animate-in fade-in duration-300">Command Map</span>}
          </Link>
          <Link to="/alerts" className={`flex items-center text-gray-300 hover:bg-navy-700 hover:text-white rounded transition-colors whitespace-nowrap ${isHovered ? 'p-2 space-x-3' : 'p-2 justify-center'}`}>
            <Bell size={20} className="flex-shrink-0" /> 
            {isHovered && <span className="animate-in fade-in duration-300">Alerts</span>}
          </Link>
          <Link to="/junctions" className={`flex items-center text-gray-300 hover:bg-navy-700 hover:text-white rounded transition-colors whitespace-nowrap ${isHovered ? 'p-2 space-x-3' : 'p-2 justify-center'}`}>
            <Activity size={20} className="flex-shrink-0" /> 
            {isHovered && <span className="animate-in fade-in duration-300">Junctions</span>}
          </Link>
          <Link to="/analytics" className={`flex items-center text-gray-300 hover:bg-navy-700 hover:text-white rounded transition-colors whitespace-nowrap ${isHovered ? 'p-2 space-x-3' : 'p-2 justify-center'}`}>
            <ActivitySquare size={20} className="flex-shrink-0" /> 
            {isHovered && <span className="animate-in fade-in duration-300">Analytics</span>}
          </Link>
          <Link to="/system-health" className={`flex items-center text-gray-300 hover:bg-navy-700 hover:text-white rounded transition-colors whitespace-nowrap ${isHovered ? 'p-2 space-x-3' : 'p-2 justify-center'}`}>
            <ShieldAlert size={20} className="flex-shrink-0" /> 
            {isHovered && <span className="animate-in fade-in duration-300">System Health</span>}
          </Link>
          <Link to="/operator-log" className={`flex items-center text-gray-300 hover:bg-navy-700 hover:text-white rounded transition-colors whitespace-nowrap ${isHovered ? 'p-2 space-x-3' : 'p-2 justify-center'}`}>
            <FileText size={20} className="flex-shrink-0" /> 
            {isHovered && <span className="animate-in fade-in duration-300">Operator Log</span>}
          </Link>
        </nav>

        <div className={`pt-4 border-t border-navy-border flex items-center text-sm text-gray-400 whitespace-nowrap ${isHovered ? '' : 'justify-center'}`}>
          <span className="w-2 h-2 rounded-full bg-status-green flex-shrink-0"></span>
          {isHovered && <span className="ml-2 animate-in fade-in duration-300">All Systems Operational</span>}
        </div>
      </div>
    </div>
  );
};

const Topbar = () => (
  <div className="h-10 border-b border-navy-border bg-navy-800 flex items-center justify-between px-4">
    <h1 className="text-base font-semibold text-white">Asteria Corridor Command Center</h1>
    <div className="flex items-center space-x-3">
      <div className="px-2 py-0.5 bg-status-red bg-opacity-20 text-status-red text-[10px] font-bold rounded-full flex items-center space-x-1.5 uppercase tracking-wide">
        <span className="w-1.5 h-1.5 rounded-full bg-status-red animate-pulse"></span> <span>LIVE</span>
      </div>
      <div className="text-xs text-gray-400">Operator 07</div>
    </div>
  </div>
);

function App() {
  return (
    <WebSocketProvider>
      <Router>
        <div className="flex h-screen bg-[var(--color-navy-900)] text-white font-sans overflow-hidden">
          <Sidebar />
          <div className="flex-1 flex flex-col min-w-0">
            <Topbar />
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
