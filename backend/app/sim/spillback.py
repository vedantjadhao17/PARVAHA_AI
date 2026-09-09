import uuid
from datetime import datetime, timezone
from typing import Dict, Optional

class SpillbackEngine:
    """
    Implements PRD FR-10: Rule-based Spillback Engine.
    Classifies spillback risk based on the queue-to-storage ratio.
    """
    def __init__(self, storage_capacities_m: Dict[str, float] = None):
        # Estimated storage capacity in meters for the approaches to each junction
        self.storage_capacities_m = storage_capacities_m or {
            "J1_SAN": 250.0, # Sancheti Chowk
            "J2_SJM": 188.0, # Shivaji Road-JM Path
            "J3_SAP": 242.0  # Shivaji Road-Apte Path
        }

    def evaluate(self, junction_id: str, junction_name: str, queue_m: float) -> Optional[dict]:
        capacity = self.storage_capacities_m.get(junction_id, 200.0)
        ratio = queue_m / capacity
        
        severity = "SAFE"
        if ratio >= 0.90:
            severity = "SPILLBACK"
        elif ratio >= 0.75:
            severity = "HIGH"
        elif ratio >= 0.40:
            severity = "WATCH"
            
        if severity == "SAFE":
            return None
            
        # Create an alert payload
        return {
            "id": f"ALT-{uuid.uuid4().hex[:6].upper()}",
            "incident_name": "Queue Buildup Detected" if severity in ["WATCH", "HIGH"] else "Active Spillback",
            "severity": severity,
            "location": junction_name,
            "affected_approach": "Main Corridor",
            "detected_time": datetime.now(timezone.utc).isoformat(),
            "status": "Active",
            "assignee": "System",
            "confidence": 95.0,
            "expected_in_s": 0,
            "predicted_impact": f"Queue has reached {int(ratio*100)}% of storage capacity.",
            "recommendation_text": "Run counterfactual test to explore coordinated offset changes."
        }
