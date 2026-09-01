import React, { useState, useEffect, useMemo } from 'react';
import { useWebSocket } from '../context/WebSocketContext';
import {
  Activity,
  Search,
  Filter,
  AlertTriangle,
  CheckCircle,
  XCircle,
  ChevronRight,
  MapPin,
  Zap,
  Clock,
  ArrowDownUp,
} from 'lucide-react';

interface JunctionLiveData {
  id: string;
  name: string;
  queue_m: number;
  active_vehicles: number;
  signal_state: 'GREEN' | 'YELLOW' | 'RED' | 'UNKNOWN';
  status: string;
}

interface JunctionConfig {
  corridor_id: string;
  junctions: {
    junction_id: string;
    order: number;
    tls_id: string;
    label: string;
    distance_from_previous_m: number;
    downstream_junction_id: string | null;
    approaches: {
      approach_id: string;
      label: string;
      green_phases: number[];
      edges: string[];
    }[];
  }[];
}

const getStatusColor = (queueM: number, status: string) => {
  if (status === 'Severe' || queueM >= 100) return 'text-status-red';
  if (queueM >= 50) return 'text-status-orange';
  if (queueM >= 20) return 'text-status-amber';
  return 'text-status-green';
};

const getStatusBg = (queueM: number, status: string) => {
  if (status === 'Severe' || queueM >= 100) return 'bg-status-red';
  if (queueM >= 50) return 'bg-status-orange';
  if (queueM >= 20) return 'bg-status-amber';
  return 'bg-status-green';
};

const getStatusLabel = (queueM: number, status: string) => {
  if (status === 'Severe' || queueM >= 100) return 'Severe';
  if (queueM >= 50) return 'Heavy';
  if (queueM >= 20) return 'Moderate';
  return 'Normal';
};

const getSignalIcon = (signal: string) => {
  switch (signal) {
    case 'GREEN':
      return <CheckCircle size={14} className="text-status-green" />;
    case 'YELLOW':
      return <AlertTriangle size={14} className="text-status-amber" />;
    case 'RED':
      return <XCircle size={14} className="text-status-red" />;
    default:
      return <Activity size={14} className="text-gray-500" />;
  }
};

const StatCard = ({
  label,
  value,
  icon: Icon,
  color,
}: {
  label: string;
  value: string | number;
  icon: React.ElementType;
  color: string;
}) => (
  <div className="bg-navy-800 border border-navy-border rounded-lg p-4 flex items-center space-x-4">
    <div className={`p-3 rounded-lg ${color} bg-opacity-20`}>
      <Icon size={20} className={color.replace('text-', 'text-')} />
    </div>
    <div>
      <div className="text-2xl font-bold text-white">{value}</div>
      <div className="text-xs text-gray-400 uppercase tracking-wide">{label}</div>
    </div>
  </div>
);

export const Junctions = () => {
  const { state, connected } = useWebSocket();
  const [searchQuery, setSearchQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState<'all' | 'Normal' | 'Severe'>('all');
  const [selectedJunction, setSelectedJunction] = useState<string | null>(null);
  const [junctionConfig, setJunctionConfig] = useState<JunctionConfig | null>(null);

  // Fetch junction config metadata
  useEffect(() => {
    fetch('/api/junctions/config')
      .then((res) => res.json())
      .then((data) => setJunctionConfig(data))
      .catch(() => {/* config is optional */});
  }, []);

  const junctionList = useMemo(() => {
    const junctions = Object.values(state?.junctions || {}) as JunctionLiveData[];
    return junctions.filter((j) => {
      const matchesSearch =
        j.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
        j.id.toLowerCase().includes(searchQuery.toLowerCase());
      const statusLabel = getStatusLabel(j.queue_m, j.status);
      const matchesStatus =
        statusFilter === 'all' ||
        (statusFilter === 'Normal' && statusLabel === 'Normal') ||
        (statusFilter === 'Severe' && (statusLabel === 'Severe' || statusLabel === 'Heavy'));
      return matchesSearch && matchesStatus;
    });
  }, [state, searchQuery, statusFilter]);

  const stats = useMemo(() => {
    const junctions = Object.values(state?.junctions || {}) as JunctionLiveData[];
    const total = junctions.length;
    const avgQueue =
      total > 0
        ? (junctions.reduce((sum, j) => sum + j.queue_m, 0) / total).toFixed(1)
        : '0.0';
    const severe = junctions.filter(
      (j) => j.status === 'Severe' || j.queue_m >= 100
    ).length;
    const activeAlerts = state?.active_alerts?.length || 0;
    return { total, avgQueue, severe, activeAlerts };
  }, [state]);

  const selectedData = selectedJunction
    ? (state?.junctions as Record<string, JunctionLiveData>)?.[selectedJunction]
    : null;
  const selectedConfig = junctionConfig?.junctions.find(
    (j) => j.junction_id === selectedJunction
  );

  if (!connected) {
    return (
      <div className="p-6 flex items-center justify-center h-full">
        <div className="bg-navy-800 p-8 rounded border border-navy-border text-center text-gray-400">
          <Activity size={32} className="mx-auto mb-3 animate-pulse" />
          <p>Waiting for live telemetry...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex h-full">
      {/* Main Content */}
      <div className="flex-1 p-6 overflow-auto">
        {/* Stat Cards Row */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
          <StatCard
            label="Total Junctions"
            value={stats.total}
            icon={MapPin}
            color="text-blue-400"
          />
          <StatCard
            label="Avg Queue (m)"
            value={stats.avgQueue}
            icon={ArrowDownUp}
            color="text-status-amber"
          />
          <StatCard
            label="Active Alerts"
            value={stats.activeAlerts}
            icon={AlertTriangle}
            color="text-status-orange"
          />
          <StatCard
            label="Severe Junctions"
            value={stats.severe}
            icon={XCircle}
            color="text-status-red"
          />
        </div>

        {/* Filter Bar */}
        <div className="bg-navy-800 border border-navy-border rounded-lg p-4 mb-6 flex flex-col sm:flex-row items-start sm:items-center gap-4">
          <div className="relative flex-1 w-full">
            <Search
              size={16}
              className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-500"
            />
            <input
              type="text"
              placeholder="Search junctions by name or ID..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full bg-navy-900 border border-navy-border rounded-md pl-9 pr-4 py-2 text-sm text-white placeholder-gray-500 focus:outline-none focus:border-blue-500"
            />
          </div>
          <div className="flex items-center space-x-2">
            <Filter size={14} className="text-gray-500" />
            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value as any)}
              className="bg-navy-900 border border-navy-border rounded-md px-3 py-2 text-sm text-white focus:outline-none focus:border-blue-500"
            >
              <option value="all">All Status</option>
              <option value="Normal">Normal</option>
              <option value="Severe">Severe / Heavy</option>
            </select>
          </div>
        </div>

        {/* Data Table */}
        <div className="bg-navy-800 border border-navy-border rounded-lg overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-navy-900 border-b border-navy-border">
                <th className="text-left px-4 py-3 text-gray-400 font-medium uppercase text-xs tracking-wide">
                  Junction
                </th>
                <th className="text-left px-4 py-3 text-gray-400 font-medium uppercase text-xs tracking-wide">
                  Signal
                </th>
                <th className="text-right px-4 py-3 text-gray-400 font-medium uppercase text-xs tracking-wide">
                  Queue (m)
                </th>
                <th className="text-right px-4 py-3 text-gray-400 font-medium uppercase text-xs tracking-wide">
                  Vehicles
                </th>
                <th className="text-center px-4 py-3 text-gray-400 font-medium uppercase text-xs tracking-wide">
                  Status
                </th>
                <th className="px-4 py-3"></th>
              </tr>
            </thead>
            <tbody>
              {junctionList.length === 0 ? (
                <tr>
                  <td
                    colSpan={6}
                    className="px-4 py-8 text-center text-gray-500"
                  >
                    No junctions match the current filter.
                  </td>
                </tr>
              ) : (
                junctionList.map((junction) => {
                  const statusColor = getStatusColor(
                    junction.queue_m,
                    junction.status
                  );
                  const statusBg = getStatusBg(junction.queue_m, junction.status);
                  const statusLabel = getStatusLabel(
                    junction.queue_m,
                    junction.status
                  );
                  const isSelected = selectedJunction === junction.id;
                  return (
                    <tr
                      key={junction.id}
                      onClick={() => setSelectedJunction(junction.id)}
                      className={`border-b border-navy-border cursor-pointer transition-colors ${
                        isSelected
                          ? 'bg-navy-700'
                          : 'hover:bg-navy-700/50'
                      }`}
                    >
                      <td className="px-4 py-3">
                        <div className="font-medium text-white">
                          {junction.name}
                        </div>
                        <div className="text-xs text-gray-500">{junction.id}</div>
                      </td>
                      <td className="px-4 py-3">
                        <div className="flex items-center space-x-2">
                          {getSignalIcon(junction.signal_state)}
                          <span className="text-gray-300">
                            {junction.signal_state}
                          </span>
                        </div>
                      </td>
                      <td className="px-4 py-3 text-right">
                        <span className={`font-mono font-semibold ${statusColor}`}>
                          {junction.queue_m.toFixed(1)}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-right">
                        <span className="font-mono text-gray-300">
                          {junction.active_vehicles}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-center">
                        <span
                          className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium ${statusBg} bg-opacity-20 ${statusColor}`}
                        >
                          {statusLabel}
                        </span>
                      </td>
                      <td className="px-4 py-3">
                        <ChevronRight
                          size={16}
                          className={`text-gray-500 transition-transform ${
                            isSelected ? 'rotate-90 text-blue-400' : ''
                          }`}
                        />
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Right Detail Panel */}
      {selectedData && (
        <div className="w-80 border-l border-navy-border bg-navy-800 overflow-auto">
          <div className="p-4 border-b border-navy-border flex items-center justify-between">
            <h3 className="font-semibold text-white">Junction Detail</h3>
            <button
              onClick={() => setSelectedJunction(null)}
              className="text-gray-500 hover:text-white text-xs"
            >
              Close
            </button>
          </div>

          <div className="p-4 space-y-5">
            {/* Header */}
            <div>
              <h4 className="text-lg font-bold text-white">{selectedData.name}</h4>
              <p className="text-sm text-gray-400">{selectedData.id}</p>
              {selectedConfig && (
                <p className="text-xs text-gray-500 mt-1">
                  TLS: {selectedConfig.tls_id}
                </p>
              )}
            </div>

            {/* Status Badge */}
            <div>
              <span
                className={`inline-flex items-center px-3 py-1 rounded-full text-sm font-medium ${getStatusBg(selectedData.queue_m, selectedData.status)} bg-opacity-20 ${getStatusColor(selectedData.queue_m, selectedData.status)}`}
              >
                {getStatusLabel(selectedData.queue_m, selectedData.status)}
              </span>
            </div>

            {/* Key Metrics */}
            <div className="grid grid-cols-2 gap-3">
              <div className="bg-navy-900 rounded-lg p-3">
                <div className="flex items-center space-x-2 text-gray-400 text-xs mb-1">
                  <ArrowDownUp size={12} />
                  <span>Queue</span>
                </div>
                <div
                  className={`text-xl font-bold font-mono ${getStatusColor(selectedData.queue_m, selectedData.status)}`}
                >
                  {selectedData.queue_m.toFixed(1)}m
                </div>
              </div>
              <div className="bg-navy-900 rounded-lg p-3">
                <div className="flex items-center space-x-2 text-gray-400 text-xs mb-1">
                  <Zap size={12} />
                  <span>Vehicles</span>
                </div>
                <div className="text-xl font-bold font-mono text-white">
                  {selectedData.active_vehicles}
                </div>
              </div>
            </div>

            {/* Signal State */}
            <div className="bg-navy-900 rounded-lg p-3">
              <div className="flex items-center space-x-2 text-gray-400 text-xs mb-2">
                <Clock size={12} />
                <span>Signal State</span>
              </div>
              <div className="flex items-center space-x-2">
                {getSignalIcon(selectedData.signal_state)}
                <span className="text-white font-medium">
                  {selectedData.signal_state}
                </span>
              </div>
            </div>

            {/* Corridor Position */}
            {selectedConfig && (
              <div className="bg-navy-900 rounded-lg p-3">
                <div className="flex items-center space-x-2 text-gray-400 text-xs mb-2">
                  <MapPin size={12} />
                  <span>Corridor Position</span>
                </div>
                <div className="text-sm text-white">
                  Junction #{selectedConfig.order} of{' '}
                  {junctionConfig?.junctions.length}
                </div>
                {selectedConfig.distance_from_previous_m > 0 && (
                  <div className="text-xs text-gray-400 mt-1">
                    {selectedConfig.distance_from_previous_m.toFixed(1)}m from
                    previous junction
                  </div>
                )}
                {selectedConfig.downstream_junction_id && (
                  <div className="text-xs text-gray-400">
                    Downstream: {selectedConfig.downstream_junction_id}
                  </div>
                )}
              </div>
            )}

            {/* Approaches */}
            {selectedConfig && selectedConfig.approaches.length > 0 && (
              <div>
                <h5 className="text-xs uppercase text-gray-500 font-bold mb-2">
                  Approaches
                </h5>
                <div className="space-y-2">
                  {selectedConfig.approaches.map((approach) => (
                    <div
                      key={approach.approach_id}
                      className="bg-navy-900 rounded p-2"
                    >
                      <div className="text-sm text-white font-medium">
                        {approach.label}
                      </div>
                      <div className="text-xs text-gray-500">
                        {approach.approach_id} · Green phases:{' '}
                        {approach.green_phases.join(', ')}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Active Alerts for this junction */}
            {state?.active_alerts && state.active_alerts.length > 0 && (
              <div>
                <h5 className="text-xs uppercase text-gray-500 font-bold mb-2">
                  Active Alerts
                </h5>
                <div className="space-y-2">
                  {state.active_alerts.map((alert: any) => (
                    <div
                      key={alert.id}
                      className="bg-navy-900 rounded p-2 border-l-2 border-status-orange"
                    >
                      <div className="text-sm text-white">
                        {alert.incident_name}
                      </div>
                      <div className="text-xs text-gray-400">
                        Severity: {alert.severity}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
};