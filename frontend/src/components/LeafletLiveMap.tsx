import { useEffect, useMemo, useRef, useState } from 'react';
import {
  MapContainer,
  TileLayer,
  CircleMarker,
  Polyline,
  Tooltip,
  useMap,
} from 'react-leaflet';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import { useWebSocket } from '../context/WebSocketContext';
import type { VehicleState, JunctionState } from '../context/WebSocketContext';

// ─── Types ──────────────────────────────────────────────────────────────────

interface LaneShape {
  id: string;
  edge_id: string;
  shape_lonlat: [number, number][] | null;
}

interface NetworkGeometry {
  lanes: LaneShape[];
  junctions: { id: string; lon: number | null; lat: number | null; type: string }[];
  bounds_lonlat: { minLon: number; minLat: number; maxLon: number; maxLat: number } | null;
}

interface Props {
  selectedJunction: string | null;
  onJunctionSelect: (id: string) => void;
  junctionOrder: { junction_id: string; label: string }[];
}

// ─── Color helpers ───────────────────────────────────────────────────────────

const speedToColor = (speedMps: number) => {
  const kmh = speedMps * 3.6;
  if (kmh > 20) return '#10b981'; // green — moving
  if (kmh > 8)  return '#facc15'; // yellow — slowing
  if (kmh > 2)  return '#f97316'; // orange — queued
  return '#ef4444';                // red — stopped
};

const signalColor = (state: string) => {
  if (state === 'GREEN')  return '#10b981';
  if (state === 'YELLOW') return '#f59e0b';
  if (state === 'RED')    return '#ef4444';
  return '#6b7280';
};

const queueColor = (queueM: number) => {
  if (queueM < 20)  return '#10b981';
  if (queueM < 50)  return '#facc15';
  if (queueM < 100) return '#f97316';
  return '#ef4444';
};

// ─── Auto-fit bounds on first geometry load ───────────────────────────────

const AutoFit = ({ bounds }: { bounds: L.LatLngBoundsExpression | null }) => {
  const map = useMap();
  const fitted = useRef(false);
  useEffect(() => {
    if (bounds && !fitted.current) {
      map.fitBounds(bounds, { padding: [40, 40] });
      fitted.current = true;
    }
  }, [bounds, map]);
  return null;
};

// ─── Main component ──────────────────────────────────────────────────────────

export const LeafletLiveMap = ({ selectedJunction, onJunctionSelect, junctionOrder }: Props) => {
  const { state } = useWebSocket();
  const [geometry, setGeometry] = useState<NetworkGeometry | null>(null);
  const [geoError, setGeoError] = useState(false);

  const liveJunctions: Record<string, JunctionState> = state?.junctions ?? {};
  const vehicles: VehicleState[] = state?.vehicles ?? [];

  // Fetch road geometry once
  useEffect(() => {
    fetch('http://localhost:8000/api/network/geometry')
      .then((r) => r.json())
      .then(setGeometry)
      .catch(() => setGeoError(true));
  }, []);

  // Build Leaflet bounds from network extent
  const bounds = useMemo<L.LatLngBoundsExpression | null>(() => {
    if (!geometry?.bounds_lonlat) return null;
    const { minLon, minLat, maxLon, maxLat } = geometry.bounds_lonlat;
    return [
      [minLat, minLon],
      [maxLat, maxLon],
    ];
  }, [geometry]);

  // Lane polylines (lon/lat → Leaflet [lat,lon])
  const lanePolylines = useMemo(() => {
    if (!geometry?.lanes) return [];
    return geometry.lanes
      .filter((l) => l.shape_lonlat && l.shape_lonlat.length >= 2)
      .map((l) => ({
        id: l.id,
        positions: l.shape_lonlat!.map(([lon, lat]) => [lat, lon] as [number, number]),
      }));
  }, [geometry]);

  // Corridor junctions that have live data + lon/lat from geometry
  const junctionMarkers = useMemo(() => {
    if (!geometry?.junctions) return [];
    return junctionOrder
      .map((jCfg) => {
        const geoNode = geometry.junctions.find((g) => g.id === jCfg.junction_id);
        const liveData = liveJunctions[jCfg.junction_id];
        if (!geoNode?.lon || !geoNode?.lat || !liveData) return null;
        return {
          id: jCfg.junction_id,
          label: jCfg.label,
          lat: geoNode.lat,
          lon: geoNode.lon,
          signal: liveData.signal_state,
          queue: liveData.queue_m,
          vehicles: liveData.active_vehicles,
        };
      })
      .filter(Boolean) as {
        id: string; label: string; lat: number; lon: number;
        signal: string; queue: number; vehicles: number;
      }[];
  }, [geometry, junctionOrder, liveJunctions]);

  if (geoError) {
    return (
      <div className="flex items-center justify-center h-full text-gray-500 text-sm">
        ⚠️ Could not load network geometry. Is the backend running?
      </div>
    );
  }

  return (
    <div className="relative w-full h-full rounded overflow-hidden">
      {/* Simulation time badge */}
      {state?.time_s !== undefined && (
        <div className="absolute top-3 right-3 z-[500] bg-navy-900/90 border border-navy-border text-xs text-gray-300 px-2 py-1 rounded font-mono">
          T = {state.time_s.toFixed(0)}s
        </div>
      )}

      {/* Loading overlay while geometry fetches */}
      {!geometry && (
        <div className="absolute inset-0 z-[500] flex items-center justify-center bg-navy-900/80 text-gray-400 text-sm">
          Loading road network…
        </div>
      )}

      <MapContainer
        center={[18.5300, 73.8540]}
        zoom={16}
        style={{ width: '100%', height: '100%', background: '#0b1420' }}
        zoomControl={true}
        attributionControl={false}
      >
        {/* Dark tile layer using OSM with CSS filter */}
        <TileLayer
          url="https://tile.openstreetmap.org/{z}/{x}/{y}.png"
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
          maxZoom={19}
          className="dark-map-tiles"
        />

        {/* Auto-fit on first load */}
        <AutoFit bounds={bounds} />

        {/* Road network lane shapes */}
        {lanePolylines.map((lane) => (
          <Polyline
            key={lane.id}
            positions={lane.positions}
            pathOptions={{ color: '#1e3a5a', weight: 2.5, opacity: 0.85 }}
          />
        ))}

        {/* Live vehicles */}
        {vehicles
          .filter((v) => v.lat !== null && v.lon !== null)
          .map((v) => (
            <CircleMarker
              key={v.id}
              center={[v.lat!, v.lon!]}
              radius={3}
              pathOptions={{
                color: speedToColor(v.speed),
                fillColor: speedToColor(v.speed),
                fillOpacity: 0.95,
                weight: 0,
              }}
            />
          ))}

        {/* Junction markers */}
        {junctionMarkers.map((j) => {
          const isSelected = selectedJunction === j.id;
          const sigCol = signalColor(j.signal);
          const qCol = queueColor(j.queue);
          return (
            <CircleMarker
              key={j.id}
              center={[j.lat, j.lon]}
              radius={isSelected ? 14 : 11}
              pathOptions={{
                color: isSelected ? '#3b82f6' : sigCol,
                fillColor: qCol,
                fillOpacity: 0.35,
                weight: isSelected ? 3 : 2.5,
                dashArray: isSelected ? undefined : undefined,
              }}
              eventHandlers={{ click: () => onJunctionSelect(j.id) }}
            >
              <Tooltip direction="top" offset={[0, -8]} permanent={false}>
                <div className="text-xs">
                  <div className="font-bold">{j.label}</div>
                  <div>Q: {j.queue.toFixed(0)}m · {j.vehicles} veh</div>
                  <div
                    style={{ color: sigCol }}
                    className="font-semibold"
                  >
                    {j.signal}
                  </div>
                </div>
              </Tooltip>
            </CircleMarker>
          );
        })}
      </MapContainer>

      {/* Legend */}
      <div className="absolute bottom-4 left-4 z-[500] bg-navy-900/90 border border-navy-border rounded p-2 text-[10px] space-y-1">
        <div className="font-semibold text-gray-300 mb-1">Vehicles by speed</div>
        {[
          { color: '#10b981', label: '> 20 km/h' },
          { color: '#facc15', label: '8–20 km/h' },
          { color: '#f97316', label: '2–8 km/h' },
          { color: '#ef4444', label: 'Stopped' },
        ].map(({ color, label }) => (
          <div key={label} className="flex items-center gap-1.5">
            <span className="w-2.5 h-2.5 rounded-full inline-block" style={{ background: color }} />
            <span className="text-gray-400">{label}</span>
          </div>
        ))}
        <div className="mt-1 pt-1 border-t border-navy-border font-semibold text-gray-300">Junction ring</div>
        <div className="text-gray-400">Fill = congestion · Border = signal</div>
      </div>
    </div>
  );
};
