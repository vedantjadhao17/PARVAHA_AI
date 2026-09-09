import { useState, useMemo, useEffect } from 'react';
import { useWebSocket } from '../context/WebSocketContext';
import {
  Activity,
  AlertCircle,
  CheckCircle2,
  X,
  Clock,
  TrendingUp,
  Maximize2,
  RotateCcw,
  Flag,
  Wifi,
  WifiOff,
  Radio,
} from 'lucide-react';
import { MapContainer, TileLayer, CircleMarker, Polyline, useMap } from 'react-leaflet';
import { LeafletLiveMap } from '../components/LeafletLiveMap';
import { SimFeedPanel } from '../components/SimFeedPanel';
import { SignalStateVisualizer } from '../components/SignalStateVisualizer';
import { RecommendationPanel } from '../components/RecommendationPanel';

// ─── Color & status helpers ──────────────────────────────────────────────────

const getCongestionColor = (queue: number) => {
  if (queue < 20) return '#10b981';
  if (queue < 50) return '#facc15';
  if (queue < 100) return '#f97316';
  return '#ef4444';
};

const speedToColor = (speedMps: number) => {
  const kmh = speedMps * 3.6;
  if (kmh > 20) return '#10b981';
  if (kmh > 8) return '#facc15';
  if (kmh > 2) return '#f97316';
  return '#ef4444';
};

const getStatusBadge = (queue: number) => {
  if (queue >= 100) return { label: 'Severe', cls: 'bg-status-red text-red-100' };
  if (queue >= 50) return { label: 'Heavy', cls: 'bg-status-orange text-orange-100' };
  if (queue >= 20) return { label: 'Moderate', cls: 'bg-status-amber text-amber-100' };
  return { label: 'Normal', cls: 'bg-status-green text-green-100' };
};

const deriveMetrics = (_queueM: number, vehicles: number) => {
  const occupancy = Math.min(100, (vehicles / 50) * 100);
  return { occupancy: occupancy.toFixed(1) };
};

// ─── Stat Card ───────────────────────────────────────────────────────────────

const StatCard = ({
  label,
  value,
  unit,
  icon: Icon,
  iconColor,
  sub,
}: {
  label: string;
  value: string | number;
  unit?: string;
  icon: React.ElementType;
  iconColor: string;
  sub?: string;
}) => (
  <div className="bg-navy-800 border border-navy-border rounded-lg p-3 flex items-center space-x-3">
    <div className={`p-2 rounded-lg bg-opacity-20 ${iconColor}`}>
      <Icon size={18} className={iconColor} />
    </div>

    <div>
      <div className="text-xl font-bold text-white">
        {value}
        {unit && (
          <span className="text-xs font-normal text-gray-500 ml-1">
            {unit}
          </span>
        )}
      </div>

      <div className="text-[10px] text-gray-400 uppercase tracking-wide">
        {label}
      </div>

      {sub && (
        <div className="text-[10px] text-gray-500 mt-0.5">
          {sub}
        </div>
      )}
    </div>
  </div>
);

// ─── Map recenter helper ─────────────────────────────────────────────────────

const RecenterMap = ({
  lat,
  lon,
  zoom,
}: {
  lat: number;
  lon: number;
  zoom: number;
}) => {
  const map = useMap();

  useEffect(() => {
    map.setView([lat, lon], zoom, { animate: false });
  }, [lat, lon, zoom, map]);

  return null;
};

// ─── Compact junction thumbnail ──────────────────────────────────────────────

const LiveJunctionThumb = ({
  junctionId,
  selected,
  label,
  connected,
  onClick,
}: {
  junctionId: string;
  selected: boolean;
  label: string;
  connected: boolean;
  onClick: () => void;
}) => {
  const { state } = useWebSocket();
  const [camera, setCamera] = useState<any>(null);
  const [lanes, setLanes] = useState<any[]>([]);

  useEffect(() => {
    fetch(`http://localhost:8000/api/junction/camera/${junctionId}`)
      .then((r) => r.json())
      .then(setCamera)
      .catch(() => {});
  }, [junctionId]);

  useEffect(() => {
    fetch('http://localhost:8000/api/network/geometry')
      .then((r) => r.json())
      .then((data) => setLanes(data.lanes ?? []))
      .catch(() => {});
  }, []);

  const lanePolylines = useMemo(() => {
    return lanes
      .filter(
        (l) => l.shape_lonlat && l.shape_lonlat.length >= 2
      )
      .map((l) => ({
        id: l.id,
        positions: l.shape_lonlat!.map(
          ([lon, lat]: [number, number]) =>
            [lat, lon] as [number, number]
        ),
      }));
  }, [lanes]);

  const vehicles = state?.vehicles ?? [];

  const center: [number, number] =
    camera?.lat != null && camera?.lon != null
      ? [camera.lat, camera.lon]
      : [18.5300, 73.8540];

  const zoom = 16;

  return (
    <div
      onClick={onClick}
      className={`flex-shrink-0 flex flex-col items-center p-2 rounded border cursor-pointer transition-colors ${
        selected
          ? 'border-blue-500 bg-navy-800'
          : 'border-navy-border bg-navy-800/50 hover:bg-navy-800'
      }`}
    >
      <div className="relative w-14 h-14 rounded overflow-hidden mb-1 pointer-events-none border border-navy-border/50">
        <MapContainer
          center={center}
          zoom={zoom}
          style={{
            width: '100%',
            height: '100%',
            background: '#0b1420',
          }}
          zoomControl={false}
          attributionControl={false}
          dragging={false}
          scrollWheelZoom={false}
          doubleClickZoom={false}
        >
          <TileLayer
            url="https://tile.openstreetmap.org/{z}/{x}/{y}.png"
            className="dark-map-tiles"
          />

          {camera?.lat != null && camera?.lon != null && (
            <RecenterMap
              lat={camera.lat}
              lon={camera.lon}
              zoom={zoom}
            />
          )}

          {lanePolylines.map((lane) => (
            <Polyline
              key={lane.id}
              positions={lane.positions}
              pathOptions={{
                color: '#1e3a5a',
                weight: 1.5,
                opacity: 0.8,
              }}
            />
          ))}

          {vehicles
            .filter(
              (v: any) =>
                v.lat !== null &&
                v.lon !== null
            )
            .map((v: any) => (
              <CircleMarker
                key={v.id}
                center={[v.lat, v.lon]}
                radius={2}
                pathOptions={{
                  color: speedToColor(v.speed),
                  fillColor: speedToColor(v.speed),
                  fillOpacity: 1,
                  weight: 0,
                }}
              />
            ))}
        </MapContainer>
      </div>

      <span className="text-[9px] text-gray-400 mt-0.5 truncate max-w-[56px]">
        {label}
      </span>

      <div className="flex items-center space-x-1 mt-0.5">
        {connected ? (
          <Wifi size={8} className="text-status-green" />
        ) : (
          <WifiOff size={8} className="text-status-red" />
        )}

        <span
          className={`text-[8px] ${
            connected
              ? 'text-status-green'
              : 'text-status-red'
          }`}
        >
          {connected ? 'Online' : 'Offline'}
        </span>
      </div>
    </div>
  );
};

// ─── Main component ──────────────────────────────────────────────────────────

export const CommandMap = () => {
  const { state, connected } = useWebSocket();

  const liveJunctions = state?.junctions ?? {};
  const wsAlerts = state?.active_alerts ?? [];

  /*
   * Recommendation source:
   * WebSocket -> state.pending_recommendations
   *
   * Keep this directly connected to the RecommendationPanel so
   * realtime recommendations appear without polling.
   */
  const wsPendingRecommendations =
    state?.pending_recommendations ?? [];

  // Temporary runtime diagnostic.
  // This confirms whether the browser is receiving pending recommendations.
  useEffect(() => {
    console.log(
      '[PRAVAHA] pending recommendations:',
      wsPendingRecommendations
    );
  }, [wsPendingRecommendations]);

  const [selectedJunction, setSelectedJunction] =
    useState<string | null>(null);

  const [activeTab, setActiveTab] =
    useState<'overview' | 'simulated' | 'history'>(
      'overview'
    );

  const [junctionConfig, setJunctionConfig] =
    useState<any>(null);

  const [dbAlerts, setDbAlerts] =
    useState<any[]>([]);

  const [isFullscreen, setIsFullscreen] =
    useState(false);

  // ─── Fetch junction topology ──────────────────────────────────────────────

  useEffect(() => {
    fetch('http://localhost:8000/api/junctions/config')
      .then((r) => r.json())
      .then(setJunctionConfig)
      .catch(() => {});
  }, []);

  // ─── Poll alerts every 10s ────────────────────────────────────────────────

  useEffect(() => {
    const fetchAlerts = () => {
      fetch('http://localhost:8000/api/alerts')
        .then((r) => r.json())
        .then(setDbAlerts)
        .catch(() => {});
    };

    fetchAlerts();

    const id = setInterval(fetchAlerts, 10000);

    return () => clearInterval(id);
  }, []);

  // ─── Ordered junction list ────────────────────────────────────────────────

  const junctionOrder = useMemo(() => {
    if (junctionConfig?.junctions) {
      return junctionConfig.junctions
        .filter(
          (j: any) =>
            liveJunctions[j.junction_id]
        )
        .sort(
          (a: any, b: any) =>
            a.order - b.order
        );
    }

    return Object.keys(liveJunctions).map(
      (id, i) => ({
        junction_id: id,
        label: liveJunctions[id].name,
        order: i + 1,
      })
    );
  }, [junctionConfig, liveJunctions]);

  // ─── Auto-select first junction ───────────────────────────────────────────

  useEffect(() => {
    if (
      !selectedJunction &&
      junctionOrder.length > 0
    ) {
      setSelectedJunction(
        junctionOrder[0].junction_id
      );
    }
  }, [junctionOrder, selectedJunction]);

  // ─── Top KPIs ─────────────────────────────────────────────────────────────

  const stats = useMemo(() => {
    const jList =
      Object.values(liveJunctions) as any[];

    const totalQueue = jList.reduce(
      (s, j) => s + (j.queue_m || 0),
      0
    );

    const activeJunctions = jList.filter(
      (j) =>
        j._junction_avg_speed_kmh != null &&
        j._junction_avg_speed_kmh > 0
    );

    const avgSpeed =
      activeJunctions.length > 0
        ? activeJunctions.reduce(
            (sum, j) =>
              sum + j._junction_avg_speed_kmh,
            0
          ) / activeJunctions.length
        : 0;

    const riskPct = Math.min(
      100,
      (totalQueue / 200) * 100
    );

    const avgOccupancy =
      jList.length > 0
        ? jList.reduce(
            (s: number, j: any) =>
              s +
              parseFloat(
                deriveMetrics(
                  j.queue_m,
                  j.active_vehicles
                ).occupancy
              ),
            0
          ) / jList.length
        : 0;

    return {
      avgSpeed:
        jList.length > 0
          ? avgSpeed.toFixed(1)
          : 'N/A',

      activeAlerts:
        wsAlerts.length,

      riskPct:
        jList.length > 0
          ? riskPct.toFixed(0)
          : 'N/A',

      controllerCount:
        junctionOrder.length,

      avgOccupancy:
        jList.length > 0
          ? avgOccupancy.toFixed(1)
          : 'N/A',
    };
  }, [
    liveJunctions,
    wsAlerts,
    junctionOrder,
  ]);

  const selectedData = selectedJunction
    ? liveJunctions[selectedJunction]
    : null;

  const selectedConfig =
    junctionConfig?.junctions?.find(
      (j: any) =>
        j.junction_id === selectedJunction
    );

  const selectedMetrics = selectedData
    ? deriveMetrics(
        selectedData.queue_m,
        selectedData.active_vehicles
      )
    : null;

  const selectedAlert = useMemo(() => {
    if (!selectedConfig) return null;

    return dbAlerts.find(
      (a: any) =>
        a.location === selectedConfig.label ||
        a.location === selectedJunction
    );
  }, [
    dbAlerts,
    selectedConfig,
    selectedJunction,
  ]);

  // ─── Render ──────────────────────────────────────────────────────────────

  return (
    <div className="flex h-full w-full relative">

      {/* Realtime recommendation overlay */}
      {wsPendingRecommendations.length > 0 && (
        <RecommendationPanel
          recommendations={
            wsPendingRecommendations
          }
          onActionComplete={() => {}}
        />
      )}

      {/* ── Left: KPIs + Live Map + Summary ── */}

      <div className="flex-1 p-4 flex flex-col space-y-3 overflow-y-auto min-w-0">

        {/* 1. Top KPI strip */}

        <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">

          <StatCard
            label="Average Speed"
            value={stats.avgSpeed}
            unit="km/h"
            icon={Activity}
            iconColor="text-status-green"
          />

          <StatCard
            label="Active Alerts"
            value={stats.activeAlerts}
            icon={AlertCircle}
            iconColor="text-status-amber"
          />

          <StatCard
            label="Predicted Risk"
            value={stats.riskPct}
            unit="%"
            icon={TrendingUp}
            iconColor="text-status-red"
          />

          <StatCard
            label="Controllers"
            value={`${stats.controllerCount}/${stats.controllerCount}`}
            icon={Radio}
            iconColor="text-status-green"
            sub={
              connected
                ? 'All Online'
                : 'Offline'
            }
          />

        </div>

        {/* 2. Live SUMO map */}

        <div
          className={`bg-navy-800 rounded-lg border border-navy-border relative overflow-hidden transition-all ${
            isFullscreen
              ? 'fixed inset-4 z-[1000]'
              : 'flex-1 min-h-[200px]'
          }`}
        >

          {isFullscreen && (
            <button
              onClick={() =>
                setIsFullscreen(false)
              }
              className="absolute top-3 right-3 z-[600] text-white bg-navy-900/80 hover:bg-navy-700 border border-navy-border rounded p-1.5"
            >
              <X size={16} />
            </button>
          )}

          <LeafletLiveMap
            selectedJunction={
              selectedJunction
            }
            onJunctionSelect={
              setSelectedJunction
            }
            junctionOrder={
              junctionOrder
            }
          />

        </div>

        {/* 3. Bottom corridor summary row */}

        <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 shrink-0">

          {/* Corridor Avg */}

          <div className="bg-navy-900 border border-navy-border p-3 rounded-lg flex flex-col justify-between">

            <span className="text-gray-400 font-semibold text-xs">
              Corridor Avg
            </span>

            <div className="flex justify-between items-end mt-1">

              <div>

                <div className="text-lg font-bold text-white">
                  {stats.avgSpeed}{' '}
                  <span className="text-[10px] font-normal text-gray-500">
                    km/h
                  </span>
                </div>

                <div className="text-xs text-gray-500">
                  {stats.avgOccupancy}% occ
                </div>

              </div>

            </div>

          </div>

          {/* Per-junction cards */}

          {junctionOrder.map((j: any) => {

            const d =
              liveJunctions[
                j.junction_id
              ];

            if (!d) return null;

            const q =
              d.queue_m ?? null;

            const v =
              d.active_vehicles ?? null;

            const occupancy =
              q != null && v != null
                ? deriveMetrics(
                    q,
                    v
                  ).occupancy
                : 'N/A';

            const speed =
              d._junction_avg_speed_kmh != null &&
              d._junction_avg_speed_kmh > 0
                ? d._junction_avg_speed_kmh.toFixed(1)
                : 'N/A';

            const badge =
              q != null
                ? getStatusBadge(q)
                : {
                    label: 'N/A',
                    cls: 'bg-gray-600',
                  };

            return (
              <div
                key={j.junction_id}
                className="bg-navy-800 border border-navy-border p-3 rounded-lg flex flex-col justify-between hover:bg-navy-700 cursor-pointer transition-colors"
                onClick={() =>
                  setSelectedJunction(
                    j.junction_id
                  )
                }
              >

                <div className="flex justify-between items-start mb-1">

                  <span
                    className="text-gray-200 text-sm font-semibold truncate max-w-[100px]"
                    title={
                      j.label ||
                      d.name
                    }
                  >
                    {j.label ||
                      d.name}
                  </span>

                  <span
                    className={`text-[9px] px-1.5 py-0.5 rounded-full font-bold uppercase ${badge.cls}`}
                  >
                    {badge.label}
                  </span>

                </div>

                <div className="flex justify-between items-end">

                  <div>

                    <div className="text-base font-bold text-white">
                      {speed}{' '}
                      <span className="text-[10px] font-normal text-gray-500">
                        km/h
                      </span>
                    </div>

                    <div className="text-[10px] text-gray-400">
                      {occupancy !== 'N/A'
                        ? `${occupancy}% occ`
                        : 'N/A occ'}
                    </div>

                  </div>

                  <div className="text-right">

                    <div className="text-sm font-semibold text-white">
                      {q != null
                        ? `${q.toFixed(0)}m`
                        : 'N/A'}{' '}
                      <span className="text-[10px] text-gray-500 font-normal">
                        Q
                      </span>
                    </div>

                    <div className="text-[10px] text-gray-400">
                      {v != null
                        ? `${v} veh`
                        : 'N/A veh'}
                    </div>

                  </div>

                </div>

              </div>
            );
          })}

        </div>
      </div>

      {/* ── Right: Detail panel ── */}

      <div className="w-[420px] bg-navy-800 border-l border-navy-border flex flex-col overflow-hidden shrink-0">

        {selectedJunction ? (

          <>
            {/* Header */}

            <div className="p-4 border-b border-navy-border flex justify-between items-center bg-navy-900">

              <h3 className="text-lg font-bold text-white">
                {selectedConfig?.label ||
                  selectedData?.name ||
                  selectedJunction}
              </h3>

              <button
                onClick={() =>
                  setSelectedJunction(null)
                }
                className="text-gray-400 hover:text-white p-1"
              >
                <X size={18} />
              </button>

            </div>

            {/* Tabs */}

            <div className="flex border-b border-navy-border">

              {(
                [
                  'overview',
                  'simulated',
                  'history',
                ] as const
              ).map((tab) => (

                <button
                  key={tab}
                  className={`flex-1 py-3 text-sm font-medium border-b-2 transition-colors ${
                    activeTab === tab
                      ? 'border-blue-500 text-blue-400'
                      : 'border-transparent text-gray-400 hover:text-gray-200'
                  }`}
                  onClick={() =>
                    setActiveTab(tab)
                  }
                >
                  {tab === 'overview'
                    ? 'Overview'
                    : tab === 'simulated'
                    ? 'Simulated Feed'
                    : 'History'}
                </button>

              ))}

            </div>

            {/* Tab content */}

            <div className="flex-1 overflow-y-auto">

              {/* Overview */}

              {activeTab ===
                'overview' && (

                <div className="p-4 space-y-4">

                  <div className="grid grid-cols-2 gap-3">

                    <div className="bg-navy-900 p-3 rounded border border-navy-border">

                      <div className="text-xs text-gray-400 mb-1">
                        EST. QUEUE
                      </div>

                      <div className="text-xl font-bold text-white">
                        {selectedData?.queue_m != null
                          ? `${selectedData.queue_m.toFixed(1)}m`
                          : 'N/A'}
                      </div>

                    </div>

                    <div className="bg-navy-900 p-3 rounded border border-navy-border">

                      <div className="text-xs text-gray-400 mb-1">
                        Active Vehicles
                      </div>

                      <div className="text-xl font-bold text-white">
                        {selectedData?.active_vehicles != null
                          ? selectedData.active_vehicles
                          : 'N/A'}
                      </div>

                    </div>

                  </div>

                  <SignalStateVisualizer
                    rawState={
                      selectedData?.raw_state
                    }
                  />

                  {selectedMetrics && (
                    <div className="grid grid-cols-2 gap-3">

                      <div className="bg-navy-900 p-3 rounded border border-navy-border">

                        <div className="text-xs text-gray-400 mb-1">
                          Est. Speed
                        </div>

                        <div className="text-lg font-bold text-white">
                          {selectedData?._junction_avg_speed_kmh != null &&
                          selectedData._junction_avg_speed_kmh > 0
                            ? `${selectedData._junction_avg_speed_kmh.toFixed(1)} km/h`
                            : 'N/A'}
                        </div>

                      </div>

                      <div className="bg-navy-900 p-3 rounded border border-navy-border">

                        <div className="text-xs text-gray-400 mb-1">
                          Occupancy
                        </div>

                        <div className="text-lg font-bold text-white">
                          {selectedMetrics
                            ? `${selectedMetrics.occupancy}%`
                            : 'N/A'}
                        </div>

                      </div>

                    </div>
                  )}

                </div>
              )}

              {/* Simulated Feed */}

              {activeTab ===
                'simulated' &&
                selectedMetrics && (

                <div className="space-y-4">

                  <SimFeedPanel
                    junctionId={
                      selectedJunction
                    }
                    junctionName={
                      selectedConfig?.label ||
                      selectedData?.name ||
                      selectedJunction
                    }
                    queueM={
                      selectedData?.queue_m
                    }
                    haltingVehicles={
                      selectedData?.halting_vehicles
                    }
                    activeVehicles={
                      selectedData?.active_vehicles
                    }
                    rawState={
                      selectedData?.raw_state
                    }
                    signalState={
                      selectedData?.raw_state
                        ? (
                            selectedData.raw_state.includes(
                              'y'
                            ) ||
                            selectedData.raw_state.includes(
                              'Y'
                            )
                          )
                          ? 'YELLOW'
                          : (
                              selectedData.raw_state.includes(
                                'g'
                              ) ||
                              selectedData.raw_state.includes(
                                'G'
                              )
                            )
                            ? 'GREEN'
                            : 'RED'
                        : 'UNKNOWN'
                    }
                    speed={
                      selectedData?._junction_avg_speed_kmh != null &&
                      selectedData._junction_avg_speed_kmh > 0
                        ? selectedData._junction_avg_speed_kmh.toFixed(1)
                        : 'N/A'
                    }
                    occupancy={
                      selectedMetrics?.occupancy
                    }
                    predictedQueueM={
                      selectedData?.predicted_queue_length_m
                    }
                    forecastRisk={
                      selectedData?.forecast_risk
                    }
                  />

                  {/* Alert callout */}

                  {selectedAlert && (
                    <div className="mx-4 bg-[#1f1717] border border-status-red rounded-lg flex items-center p-3 gap-3">

                      <AlertCircle
                        size={28}
                        className="text-status-red flex-shrink-0"
                      />

                      <div>

                        <div className="text-sm font-bold text-gray-200">
                          Predicted onset:{' '}
                          <span className="text-status-red">
                            {Math.max(0, selectedAlert.expected_in_s)}s after detection
                          </span>
                        </div>

                        <div className="text-xs text-gray-400">
                          Queue may spill back toward{' '}
                          {selectedConfig?.label ||
                            selectedJunction}
                          .
                        </div>

                      </div>

                    </div>
                  )}

                  {/* Action buttons */}

                  <div className="grid grid-cols-3 gap-3 px-4 pb-6 mt-2">

                    <button
                      onClick={() =>
                        setIsFullscreen(
                          !isFullscreen
                        )
                      }
                      className="flex flex-col items-center justify-center space-y-1.5 p-3 bg-navy-900 hover:bg-navy-700 border border-cyan-600/50 hover:border-cyan-500 rounded-xl text-cyan-400 transition-colors shadow-lg"
                    >
                      <Maximize2 size={20} />
                      <span className="text-xs font-semibold tracking-wide">
                        Full Screen
                      </span>
                    </button>

                    <button
                      disabled
                      title="Per-approach data not available from live state"
                      className="flex flex-col items-center justify-center space-y-1.5 p-3 bg-navy-900 border border-cyan-600/30 rounded-xl text-cyan-400/50 cursor-not-allowed shadow-lg"
                    >
                      <RotateCcw size={20} />
                      <span className="text-xs font-semibold tracking-wide">
                        Other Approach
                      </span>
                    </button>

                    <button
                      onClick={() =>
                        alert(
                          'Create Incident endpoint not yet implemented in backend.'
                        )
                      }
                      className="flex flex-col items-center justify-center space-y-1.5 p-3 bg-navy-900 hover:bg-navy-700 border border-cyan-600/50 hover:border-cyan-500 rounded-xl text-cyan-400 transition-colors shadow-lg"
                    >
                      <Flag size={20} />
                      <span className="text-xs font-semibold tracking-wide">
                        Create Incident
                      </span>
                    </button>

                  </div>

                </div>
              )}

              {/* History */}

              {activeTab ===
                'history' && (

                <div className="flex flex-col items-center justify-center h-48 text-gray-500">

                  <Clock
                    size={32}
                    className="mb-2 opacity-50"
                  />

                  <p className="text-sm">
                    History tracking starts on approval.
                  </p>

                  <p className="text-xs text-gray-600 mt-1">
                    No historical data endpoint yet.
                  </p>

                </div>
              )}

            </div>

            {/* Camera Selector */}

            <div className="border-t border-navy-border p-4 bg-navy-900">

              <h5 className="text-xs uppercase text-gray-500 font-bold mb-3">
                Camera Selector
              </h5>

              <div className="flex space-x-3 overflow-x-auto pb-1">

                {junctionOrder.map(
                  (j: any) => {

                    const d =
                      liveJunctions[
                        j.junction_id
                      ];

                    if (!d) return null;

                    return (
                      <LiveJunctionThumb
                        key={j.junction_id}
                        junctionId={
                          j.junction_id
                        }
                        selected={
                          selectedJunction ===
                          j.junction_id
                        }
                        label={
                          j.label ||
                          d.name
                        }
                        connected={
                          connected
                        }
                        onClick={() =>
                          setSelectedJunction(
                            j.junction_id
                          )
                        }
                      />
                    );
                  }
                )}

              </div>

            </div>
          </>

        ) : (

          /* No junction selected — show active alerts */

          <div className="flex flex-col h-full p-6">

            <h3 className="text-xl font-bold mb-4 flex items-center">
              <AlertCircle className="mr-2 text-status-amber" />
              Active Alerts
            </h3>

            <div className="flex-1 overflow-y-auto space-y-4 pr-2">

              {wsAlerts.length === 0 ? (

                <div className="flex flex-col items-center justify-center h-48 text-gray-500">

                  <CheckCircle2
                    size={48}
                    className="mb-4 text-status-green opacity-50"
                  />

                  <p>
                    No active anomalies.
                  </p>

                </div>

              ) : (

                wsAlerts.map(
                  (alert: any) => (

                    <div
                      key={alert.id}
                      className="bg-navy-900 border border-status-red/30 rounded p-4 relative overflow-hidden shadow-lg"
                    >

                      <div className="absolute top-0 left-0 w-1 h-full bg-status-red" />

                      <div className="flex justify-between items-start mb-2">

                        <h4 className="font-bold text-red-400 truncate pr-2">
                          {alert.incident_name ||
                            'Signal Anomaly'}
                        </h4>

                        <span className="text-[10px] bg-red-900/50 text-red-300 px-2 py-1 rounded font-mono shrink-0">
                          {alert.id.split('-').pop()}
                        </span>

                      </div>

                      <p className="text-sm text-gray-300 mb-4 font-medium">
                        Severity: {alert.severity}
                      </p>

                      <div className="flex space-x-2">

                        <button className="flex-1 bg-status-green hover:bg-green-600 text-white font-bold py-2 rounded text-sm transition-colors shadow">
                          Review Plan
                        </button>

                        <button className="flex-1 bg-navy-700 hover:bg-navy-600 text-white font-medium py-2 rounded text-sm transition-colors border border-navy-border">
                          Dismiss
                        </button>

                      </div>

                    </div>
                  )
                )

              )}

            </div>
          </div>
        )}

      </div>
    </div>
  );
};