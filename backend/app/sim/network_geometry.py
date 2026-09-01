"""Extract lane shapes and junction coordinates from a SUMO network.

Handles two cases:
1. pyproj/proj.db available  → use sumolib's convertXY2LonLat (most accurate)
2. proj.db missing (common on macOS Homebrew)  → fall back to a manual UTM
   inverse using the network's own netOffset + projParameter string so we
   still get correct lon/lat without requiring proj.db.
"""
from typing import Any, Dict, List, Optional
import math
import re
import sumolib

# Cached Net objects keyed by path.
_net_cache: Dict[str, Any] = {}


def get_net(net_path: str) -> Any:
    """Load and cache a sumolib Net object for the given path."""
    if net_path not in _net_cache:
        _net_cache[net_path] = sumolib.net.readNet(net_path)
    return _net_cache[net_path]


# ─── Manual UTM → lon/lat fallback ──────────────────────────────────────────

def _parse_utm_zone(proj_str: str):
    """Extract UTM zone number and hemisphere from a +proj=utm string."""
    m = re.search(r'\+zone=(\d+)', proj_str or '')
    zone = int(m.group(1)) if m else 43          # default: UTM 43N (Pune)
    south = '+south' in (proj_str or '')
    return zone, south


def _utm_to_lonlat(easting: float, northing: float, zone: int, south: bool):
    """Inverse UTM projection (WGS-84).  Accurate to ~1 m for our use-case."""
    # WGS-84 ellipsoid constants
    a  = 6378137.0
    f  = 1 / 298.257223563
    b  = a * (1 - f)
    e2 = 1 - (b / a) ** 2
    e  = math.sqrt(e2)
    ep2 = e2 / (1 - e2)
    k0 = 0.9996

    x = easting  - 500000.0
    y = northing if south else northing
    if not south:
        y -= 0.0   # northern hemisphere: no offset needed

    M = y / k0
    mu = M / (a * (1 - e2/4 - 3*e2**2/64 - 5*e2**3/256))

    e1 = (1 - math.sqrt(1 - e2)) / (1 + math.sqrt(1 - e2))
    phi1 = (mu
            + (3*e1/2 - 27*e1**3/32) * math.sin(2*mu)
            + (21*e1**2/16 - 55*e1**4/32) * math.sin(4*mu)
            + (151*e1**3/96) * math.sin(6*mu)
            + (1097*e1**4/512) * math.sin(8*mu))

    N1   = a / math.sqrt(1 - e2 * math.sin(phi1)**2)
    T1   = math.tan(phi1)**2
    C1   = ep2 * math.cos(phi1)**2
    R1   = a * (1 - e2) / (1 - e2 * math.sin(phi1)**2)**1.5
    D    = x / (N1 * k0)

    lat = phi1 - (N1 * math.tan(phi1) / R1) * (
        D**2/2
        - (5 + 3*T1 + 10*C1 - 4*C1**2 - 9*ep2) * D**4/24
        + (61 + 90*T1 + 298*C1 + 45*T1**2 - 252*ep2 - 3*C1**2) * D**6/720
    )
    lon0 = math.radians((zone - 1) * 6 - 180 + 3)
    lon  = lon0 + (
        D
        - (1 + 2*T1 + C1) * D**3/6
        + (5 - 2*C1 + 28*T1 - 3*C1**2 + 8*ep2 + 24*T1**2) * D**5/120
    ) / math.cos(phi1)

    return math.degrees(lon), math.degrees(lat)


class _GeoConverter:
    """Wraps either sumolib geo conversion or the manual UTM fallback."""

    def __init__(self, net):
        self._net   = net
        self._has   = net.hasGeoProj()
        self._zone  = 43
        self._south = False
        self._ox    = 0.0
        self._oy    = 0.0

        if not self._has:
            # Read raw location element directly from the net XML
            try:
                loc = net.getLocationOffset()      # (xOff, yOff)
                self._ox, self._oy = loc
            except Exception:
                self._ox, self._oy = 0.0, 0.0

            try:
                proj_str = net._location.get("projParameter", "")
                self._zone, self._south = _parse_utm_zone(proj_str)
            except Exception:
                pass   # keep defaults (UTM 43N)

    def convert(self, x: float, y: float):
        if self._has:
            lon, lat = self._net.convertXY2LonLat(x, y)
            return lon, lat
        # Manual: undo netOffset, then inverse UTM
        easting  = x + self._ox
        northing = y + self._oy
        return _utm_to_lonlat(easting, northing, self._zone, self._south)

    @property
    def available(self):
        return True   # always available now


# ─── Public API ──────────────────────────────────────────────────────────────

def extract_network_geometry(net_path: str) -> Dict[str, Any]:
    """Extract lane shapes and junction coordinates from a SUMO network.

    Returns a dict with:
        lanes: [{id, edge_id, shape_xy, shape_lonlat}]
        junctions: [{id, x, y, lon, lat, type}]
        bounds_lonlat: {minLon, minLat, maxLon, maxLat}
    """
    net  = get_net(net_path)
    conv = _GeoConverter(net)

    # --- Lanes ---
    lanes: List[Dict[str, Any]] = []
    for edge in net.getEdges():
        edge_id = edge.getID()
        for lane in edge.getLanes():
            shape_xy  = lane.getShape()
            try:
                shape_lonlat = [list(conv.convert(x, y)) for x, y in shape_xy]
            except Exception:
                shape_lonlat = None
            lanes.append({
                "id":          lane.getID(),
                "edge_id":     edge_id,
                "shape_xy":    [list(p) for p in shape_xy],
                "shape_lonlat": shape_lonlat,
            })

    # --- Junctions ---
    junctions: List[Dict[str, Any]] = []
    for node in net.getNodes():
        x, y = node.getCoord()
        try:
            lon, lat = conv.convert(x, y)
        except Exception:
            lon, lat = None, None
        junctions.append({
            "id":   node.getID(),
            "x":    x,
            "y":    y,
            "lon":  lon,
            "lat":  lat,
            "type": node.getType(),
        })

    # --- Bounds ---
    valid = [j for j in junctions if j["lon"] is not None]
    bounds_lonlat: Optional[Dict[str, float]] = None
    if valid:
        bounds_lonlat = {
            "minLon": min(j["lon"] for j in valid),
            "minLat": min(j["lat"] for j in valid),
            "maxLon": max(j["lon"] for j in valid),
            "maxLat": max(j["lat"] for j in valid),
        }

    return {
        "lanes":        lanes,
        "junctions":    junctions,
        "bounds_lonlat": bounds_lonlat,
    }