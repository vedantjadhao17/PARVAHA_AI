import { useEffect, useState, useMemo } from 'react';
import { MapContainer, TileLayer, Polyline, Marker, Popup } from 'react-leaflet';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';

// Fix leaflet's default marker icon paths (otherwise 404s in bundlers)
import markerIcon2x from 'leaflet/dist/images/marker-icon-2x.png';
import markerIcon from 'leaflet/dist/images/marker-icon.png';
import markerShadow from 'leaflet/dist/images/marker-shadow.png';

// eslint-disable-next-line @typescript-eslint/no-explicit-any
delete (L.Icon.Default.prototype as any)._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl: markerIcon2x,
  iconUrl: markerIcon,
  shadowUrl: markerShadow,
});

// ─── Corridor junction config (from corridor_junctions.json) ────────────────
const CONTROLLED_JUNCTIONS = [
  { id: 'cluster_13546492148_1838721956', corridorId: 'J1_SAN', label: 'Sancheti Chowk' },
  { id: 'cluster_2061304035_245647208', corridorId: 'J2_SJM', label: 'Shivaji Road–JM Path' },
  { id: 'cluster_245647168_3238255150_3495323634', corridorId: 'J3_SAP', label: 'Shivaji Road–Apte Path' },
];

const CONTROLLED_IDS = new Set(CONTROLLED_JUNCTIONS.map((j) => j.id));

// ~550m padding in degrees (corridor is ~500m long, so this gives headroom)
const BBOX_PADDING_DEG = 0.005;

interface Lane {
  id: string;
  edge_id: string;
  shape_xy: [number, number][];
  shape_lonlat: [number, number][] | null;
}

interface Junction {
  id: string;
  x: number;
  y: number;
  lon: number;
  lat: number;
  type: string;
}

interface GeometryResponse {
  lanes: Lane[];
  junctions: Junction[];
  bounds_lonlat: { minLon: number; minLat: number; maxLon: number; maxLat: number } | null;
}

export const CorridorMap = () => {
  const [geometry, setGeometry] = useState<GeometryResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Fetch network geometry once on mount
  useEffect(() => {
    fetch('/api/network/geometry')
      .then((res) => {
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        return res.json();
      })
      .then((data: GeometryResponse) => setGeometry(data))
      .catch((err) => setError(err.message));
  }, []);

  // Compute bounding box around the 3 controlled junctions
  const bbox = useMemo(() => {
    if (!geometry) return null;
    const controlled = geometry.junctions.filter((j) => CONTROLLED_IDS.has(j.id));
    if (controlled.length === 0) return null;
    const lons = controlled.map((j) => j.lon);
    const lats = controlled.map((j) => j.lat);
    return {
      minLon: Math.min(...lons) - BBOX_PADDING_DEG,
      maxLon: Math.max(...lons) + BBOX_PADDING_DEG,
      minLat: Math.min(...lats) - BBOX_PADDING_DEG,
      maxLat: Math.max(...lats) + BBOX_PADDING_DEG,
    };
  }, [geometry]);

  // Filter lanes to those with at least one point inside the bounding box
  const filteredLanes = useMemo(() => {
    if (!geometry || !bbox) return [];
    return geometry.lanes.filter((lane) => {
      if (!lane.shape_lonlat) return false;
      return lane.shape_lonlat.some(
        ([lon, lat]) =>
          lon >= bbox.minLon && lon <= bbox.maxLon && lat >= bbox.minLat && lat <= bbox.maxLat
      );
    });
  }, [geometry, bbox]);

  // Map of controlled junctions with their data
  const controlledJunctions = useMemo(() => {
    if (!geometry) return [];
    return geometry.junctions.filter((j) => CONTROLLED_IDS.has(j.id));
  }, [geometry]);

  // Map junction id → label
  const idToLabel = useMemo(() => {
    const m: Record<string, string> = {};
    CONTROLLED_JUNCTIONS.forEach((j) => {
      m[j.id] = j.label;
    });
    return m;
  }, []);

  // Center = average of controlled junctions
  const center = useMemo(() => {
    if (controlledJunctions.length === 0) return { lon: 73.8523, lat: 18.5274 };
    const avgLon = controlledJunctions.reduce((s, j) => s + j.lon, 0) / controlledJunctions.length;
    const avgLat = controlledJunctions.reduce((s, j) => s + j.lat, 0) / controlledJunctions.length;
    return { lon: avgLon, lat: avgLat };
  }, [controlledJunctions]);

  if (error) {
    return (
      <div className="flex items-center justify-center h-full text-status-red">
        Failed to load network geometry: {error}
      </div>
    );
  }

  if (!geometry || !bbox) {
    return (
      <div className="flex items-center justify-center h-full text-gray-400">
        Loading corridor map…
      </div>
    );
  }

  return (
    <div className="h-full w-full relative">
      <MapContainer
        center={[center.lat, center.lon]}
        zoom={16}
        className="h-full w-full"
        style={{ background: 'var(--color-navy-900)' }}
      >
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />

        {/* Filtered lane polylines */}
        {filteredLanes.map((lane) => (
          <Polyline
            key={lane.id}
            positions={lane.shape_lonlat!}
            pathOptions={{
              color: 'var(--color-navy-700)',
              weight: 3,
              opacity: 0.8,
            }}
          />
        ))}

        {/* Controlled junction markers */}
        {controlledJunctions.map((j) => (
          <Marker key={j.id} position={[j.lat, j.lon]}>
            <Popup>
              <span className="font-semibold">{idToLabel[j.id] || j.id}</span>
              <br />
              <span className="text-xs text-gray-500">
                {j.lat.toFixed(5)}, {j.lon.toFixed(5)}
              </span>
            </Popup>
          </Marker>
        ))}
      </MapContainer>

      {/* Overlay info */}
      <div className="absolute bottom-4 left-4 bg-navy-900/90 border border-navy-border rounded px-3 py-2 text-xs text-gray-300 z-[1000]">
        {filteredLanes.length} lanes · {controlledJunctions.length} junctions
      </div>
    </div>
  );
};