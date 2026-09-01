import statistics
import logging
from collections import defaultdict
from typing import Dict, Any, List

logger = logging.getLogger(__name__)

# Feature generation constants from build_forecast_dataset.py
AGG_PERIOD_S = 30
HISTORY_WINDOW_S = 150
HISTORY_STEPS = HISTORY_WINDOW_S // AGG_PERIOD_S

class LiveFeatureExtractor:
    def __init__(self, feature_names: List[str]):
        self.feature_names = feature_names
        # Buffer of 5s raw telemetry rows per junction/approach
        self.raw_buffer: List[Dict[str, Any]] = []
        # Buffer of 30s aggregated rows per junction/approach
        self.agg_buffer: List[Dict[str, Any]] = []

    def push_raw_telemetry(self, row: Dict[str, Any]):
        """Push a raw 5s telemetry row into the buffer."""
        self.raw_buffer.append(row)
        
        # Keep only the last 300 seconds (60 rows) to be safe
        if len(self.raw_buffer) > 60:
            self.raw_buffer.pop(0)

    def trigger_aggregation(self):
        """Called every 30s to aggregate the last 30s of 5s raw telemetry."""
        # Need exactly 6 rows (5,10,15,20,25,30) for a 30s window
        if len(self.raw_buffer) < 6:
            return None
            
        window_rows = self.raw_buffer[-6:]
        first = window_rows[0]
        last_row = window_rows[-1]
        
        agg_row = {
            "timestamp_s": last_row["time_s"],
            "queue_length_m": max(r["queue_length_m"] for r in window_rows),
            "vehicle_count": max(r["vehicle_count"] for r in window_rows),
            "halting_count": max(r["halting_count"] for r in window_rows),
            "downstream_junction_queue_length_m": max(r["downstream_junction_queue_length_m"] for r in window_rows),
            "mean_speed_mps": round(statistics.fmean(r["mean_speed_mps"] for r in window_rows), 4),
            "occupancy_pct": round(statistics.fmean(r["occupancy_pct"] for r in window_rows), 4),
            "platoon_eta_s": round(statistics.fmean(r["platoon_eta_s"] for r in window_rows), 4),
            "outflow_vehicles_30s": sum(r["outflow_vehicles_5s"] for r in window_rows),
            "upstream_outflow_vehicles_30s": sum(r["upstream_outflow_vehicles_5s"] for r in window_rows),
            "program_id": last_row["program_id"],
            "signal_phase_index": last_row["signal_phase_index"],
            "phase_remaining_s": last_row["phase_remaining_s"],
            "phase_elapsed_s": last_row["phase_elapsed_s"],
            "is_green": last_row["is_green"],
            "is_yellow": last_row["is_yellow"],
            "is_all_red": last_row["is_all_red"],
            "platoon_distance_m": last_row["platoon_distance_m"],
        }
        
        self.agg_buffer.append(agg_row)
        if len(self.agg_buffer) > HISTORY_STEPS + 5:
            self.agg_buffer.pop(0)
            
        return agg_row

    def extract_features(self) -> List[float]:
        """Generate the final 42-dimension feature vector for XGBoost."""
        if len(self.agg_buffer) <= HISTORY_STEPS:
            # Not enough history yet (need 150s + current = 6 rows)
            logger.warning(f"Not enough history for features. Have {len(self.agg_buffer)}/6 agg rows.")
            return [0.0] * len(self.feature_names)
            
        current = self.agg_buffer[-1]
        
        record = {
            "program_id": current["program_id"],
            "phase_elapsed_s": current["phase_elapsed_s"],
            "is_all_red": current["is_all_red"],
            "platoon_distance_m": current["platoon_distance_m"],
            "vehicle_count": current["vehicle_count"],
            "halting_count": current["halting_count"],
        }
        
        lag_cols = [
            "queue_length_m", "mean_speed_mps", "occupancy_pct",
            "outflow_vehicles_30s", "upstream_outflow_vehicles_30s",
            "downstream_junction_queue_length_m", "signal_phase_index",
            "is_green", "is_yellow", "phase_remaining_s", "platoon_eta_s"
        ]
        
        # Build Lags (from oldest to newest)
        for lag_idx in range(HISTORY_STEPS, -1, -1):
            # Index in the buffer: if we want lag_idx=5 (150s ago), it's buffer[-6]
            lag_row = self.agg_buffer[-(lag_idx + 1)]
            suffix = f"_lag_{lag_idx * AGG_PERIOD_S}s" if lag_idx > 0 else ""
            
            for col in lag_cols:
                record[f"{col}{suffix}"] = lag_row[col]
                
        # Current Net Flow
        record["upstream_arrival_minus_local_outflow"] = record["upstream_outflow_vehicles_30s"] - record["outflow_vehicles_30s"]
        
        row_150 = self.agg_buffer[-(HISTORY_STEPS + 1)]
        row_60 = self.agg_buffer[-3]
        
        record["queue_growth_150s"] = round(current["queue_length_m"] - row_150["queue_length_m"], 4)
        record["queue_growth_60s"] = round(current["queue_length_m"] - row_60["queue_length_m"], 4)
        record["speed_change_150s"] = round(current["mean_speed_mps"] - row_150["mean_speed_mps"], 4)
        record["occupancy_change_150s"] = round(current["occupancy_pct"] - row_150["occupancy_pct"], 4)
        record["downstream_queue_growth_150s"] = round(current["downstream_junction_queue_length_m"] - row_150["downstream_junction_queue_length_m"], 4)
        
        # Map exactly to feature_names list
        return [record.get(name, 0.0) for name in self.feature_names]
