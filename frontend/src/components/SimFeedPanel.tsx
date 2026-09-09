import { useEffect, useMemo, useRef, useState } from 'react';
import { MapContainer, TileLayer, CircleMarker, Polyline, useMap } from 'react-leaflet';
import 'leaflet/dist/leaflet.css';
import { useWebSocket } from '../context/WebSocketContext';
import type { VehicleState } from '../context/WebSocketContext';

// ─── Types ───────────────────────────────────────────────────────────────────

interface CameraConfig {
  junction_id: string;
  label: string;
  lon: number | null;
  lat: number | null;
  zoom: number;
  angle: number;
}

interface LaneShape {
  id: string;
  shape_lonlat: [number, number][] | null;
}

interface Props {
  junctionId: string;
  junctionName: string;
  queueM: number | null | undefined;
  haltingVehicles?: number;
  activeVehicles: number | null | undefined;
  rawState?: string;
  signalState?: string;
  speed: string | null | undefined;
  occupancy: string;
  predictedQueueM?: number | null;
  forecastRisk?: string;
}

// ─── Helpers ─────────────────────────────────────────────────────────────────

const speedToColor = (speedMps: number) => {
  const kmh = speedMps * 3.6;
  if (kmh > 20) return '#10b981';
  if (kmh > 8)  return '#facc15';
  if (kmh > 2)  return '#f97316';
  return '#ef4444';
};

const signalGlowColor = (state: string) => {
  if (state === 'GREEN')  return '#10b981';
  if (state === 'YELLOW') return '#f59e0b';
  if (state === 'RED')    return '#ef4444';
  return '#6b7280';
};

// Converts SUMO zoom value (pixels at ~96dpi) to Leaflet zoom level (approx)
const sumoZoomToLeaflet = (sumoZoom: number): number => {
  // SUMO zoom 4600 ≈ very close (street level). Empirically map it.
  if (sumoZoom >= 4000) return 18;
  if (sumoZoom >= 3000) return 17;
  if (sumoZoom >= 2000) return 17;
  return 16;
};

// ─── Re-center helper ────────────────────────────────────────────────────────

const RecenterMap = ({ lat, lon, zoom }: { lat: number; lon: number; zoom: number }) => {
  const map = useMap();
  const lastCenter = useRef<string>('');
  useEffect(() => {
    const key = `${lat.toFixed(5)},${lon.toFixed(5)}`;
    if (key !== lastCenter.current) {
      map.setView([lat, lon], zoom, { animate: true });
      lastCenter.current = key;
    }
  }, [lat, lon, zoom, map]);
  return null;
};

// ─── Main component ──────────────────────────────────────────────────────────

export const SimFeedPanel = ({
  junctionId,
  junctionName: _junctionName,
  queueM,
  haltingVehicles,
  /* activeVehicles */
  rawState,
  signalState,
  speed,
  /* occupancy */
  predictedQueueM,
  forecastRisk,
}: Props) => {
  const { state } = useWebSocket();
  const [camera, setCamera] = useState<CameraConfig | null>(null);
  const [lanes, setLanes] = useState<LaneShape[]>([]);
  const [cameraError, setCameraError] = useState(false);

  const vehicles: VehicleState[] = state?.vehicles ?? [];
  const sigColor = signalGlowColor(signalState || 'UNKNOWN');
  console.log("SimFeedPanel render:", { predictedQueueM, queueM });

  // Fetch camera config whenever junction changes
  useEffect(() => {
    setCameraError(false);
    setCamera(null);
    fetch(`http://localhost:8000/api/junction/camera/${junctionId}`)
      .then((r) => r.json())
      .then(setCamera)
      .catch(() => setCameraError(true));
  }, [junctionId]);

  // Fetch lane geometry once
  useEffect(() => {
    fetch('http://localhost:8000/api/network/geometry')
      .then((r) => r.json())
      .then((data) => setLanes(data.lanes ?? []))
      .catch(() => {});
  }, []);

  const lanePolylines = useMemo(() => {
    return lanes
      .filter((l) => l.shape_lonlat && l.shape_lonlat.length >= 2)
      .map((l) => ({
        id: l.id,
        positions: l.shape_lonlat!.map(([lon, lat]) => [lat, lon] as [number, number]),
      }));
  }, [lanes]);

  const center: [number, number] = camera?.lat && camera?.lon
    ? [camera.lat, camera.lon]
    : [18.5300, 73.8540];

  const leafletZoom = camera ? sumoZoomToLeaflet(camera.zoom) : 18;

  return (
    <div className="space-y-3">
      {/* Map feed */}
      <div className="relative rounded overflow-hidden border border-navy-border shadow-lg flex flex-col" style={{ height: 360 }}>
        {/* Header overlay */}
        <div className="absolute top-0 left-0 right-0 z-[500] flex justify-between items-center px-3 py-2 bg-navy-900/90 backdrop-blur-sm border-b border-navy-border">
          <span className="text-[10px] font-mono text-gray-300 uppercase tracking-widest">
            SIMULATED FEED · SUMO
          </span>
          <span className="px-2 py-0.5 bg-status-green/20 text-status-green border border-status-green/30 text-[10px] font-bold rounded flex items-center gap-1.5">
            LIVE
          </span>
        </div>

        <div className="flex-1 relative bg-navy-900">
          {cameraError || (!camera && !cameraError) ? (
            <div className="absolute inset-0 z-[500] flex items-center justify-center bg-navy-900/80 text-gray-400 text-sm">
              {cameraError ? '⚠️ Camera data unavailable' : 'Loading camera…'}
            </div>
          ) : (
            <MapContainer
              center={center}
              zoom={leafletZoom}
              style={{ width: '100%', height: '100%', background: '#0b1420' }}
              zoomControl={false}
              attributionControl={false}
              dragging={false}
              scrollWheelZoom={false}
              doubleClickZoom={false}
            >
              <TileLayer 
                url="https://tile.openstreetmap.org/{z}/{x}/{y}.png"
                className="dark-map-tiles"
                maxZoom={19} 
              />
              {camera?.lat && camera?.lon && (
                <RecenterMap lat={camera.lat} lon={camera.lon} zoom={leafletZoom} />
              )}

              {/* Lane shapes */}
              {lanePolylines.map((lane) => (
                <Polyline
                  key={lane.id}
                  positions={lane.positions}
                  pathOptions={{ color: '#1e3a5a', weight: 2.5, opacity: 0.9 }}
                />
              ))}

              {/* Live vehicles near this junction */}
              {vehicles
                .filter((v) => v.lat !== null && v.lon !== null)
                .map((v) => (
                  <CircleMarker
                    key={v.id}
                    center={[v.lat!, v.lon!]}
                    radius={3.5}
                    pathOptions={{
                      color: speedToColor(v.speed),
                      fillColor: speedToColor(v.speed),
                      fillOpacity: 1,
                      weight: 0,
                    }}
                  />
                ))}
            </MapContainer>
          )}

          {/* Camera ID footer */}
          <div className="absolute bottom-0 left-0 right-0 z-[500] flex justify-between items-end px-4 py-3 bg-gradient-to-t from-navy-900 to-transparent text-[10px] text-gray-400">
            <div>
              <div className="font-mono text-gray-200 text-sm mb-0.5">CAM-{junctionId.split('_').pop()}-E01</div>
              <div className="text-gray-400">{_junctionName} · Eastbound</div>
            </div>
            <div className="text-right flex flex-col items-end space-y-0.5">
              <span>Updated 1s ago</span>
              <span>1 FPS</span>
            </div>
          </div>
        </div>

        {/* 4-metric grid attached to bottom of map */}
        <div className="grid grid-cols-4 bg-navy-900 border-t border-navy-border">
          <div className="p-3 text-center border-r border-navy-border/50">
            <div className="text-[10px] text-gray-400 mb-1">EST. QUEUE</div>
            <div className="text-xl font-bold text-status-red">{queueM != null ? `${queueM.toFixed(0)}m` : 'N/A'}</div>
            <div className="text-[9px] text-gray-500">{haltingVehicles != null ? haltingVehicles : 'N/A'} halting veh</div>
          </div>
          <div className="p-3 text-center border-r border-navy-border/50">
            <div className="text-[10px] text-status-amber mb-1 font-bold">FORECAST +5m</div>
            <div className="text-xl font-bold text-status-amber">{predictedQueueM != null ? `${predictedQueueM.toFixed(0)}m` : 'N/A'}</div>
            <div className="text-[9px] text-gray-500">Risk: {forecastRisk || 'LOW'}</div>
          </div>
          <div className="p-3 text-center border-r border-navy-border/50">
            <div className="text-[10px] text-gray-400 mb-1">Raw Signal State</div>
            <div className="text-sm font-mono text-gray-300 truncate px-2" style={{ color: sigColor }}>{rawState || 'N/A'}</div>
          </div>
          <div className="p-3 text-center">
            <div className="text-[10px] text-gray-400 mb-1">Avg Speed</div>
            <div className="text-xl font-bold text-blue-400">{speed != null && speed !== 'N/A' ? speed : 'N/A'} <span className="text-xs font-normal">km/h</span></div>
          </div>
        </div>
      </div>
    </div>
  );
};
