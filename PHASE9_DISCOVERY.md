# WebSocket Discovery

## Raw WS Payloads

### Tick 1 at 352s
```json
{
  "J1_SAN": {
    "name": "Sancheti Chowk",
    "queue_m": 25,
    "halting_vehicles": 5,
    "active_vehicles": 5,
    "status": "Online",
    "predicted_queue_length_m": 19.2,
    "predicted_capacity_ratio": 0.08,
    "forecast_risk": "LOW",
    "_junction_avg_speed_kmh": 0,
    "tls_id": "cluster_13546492148_1838721956",
    "raw_state": "rrrGGG",
    "current_phase": 2,
    "next_switch": 354,
    "remaining_time": 2
  },
  "J2_SJM": {
    "name": "Shivaji Road–JM Path",
    "queue_m": 0,
    "halting_vehicles": 0,
    "active_vehicles": 3,
    "status": "Online",
    "predicted_queue_length_m": 8.1,
    "predicted_capacity_ratio": 0.04,
    "forecast_risk": "LOW",
    "_junction_avg_speed_kmh": 12.25,
    "tls_id": "cluster_2061304035_245647208",
    "raw_state": "rrGGGGGGG",
    "current_phase": 2,
    "next_switch": 354,
    "remaining_time": 2
  },
  "J3_SAP": {
    "name": "Shivaji Road–Apte Path",
    "queue_m": 175,
    "halting_vehicles": 35,
    "active_vehicles": 35,
    "status": "Online",
    "predicted_queue_length_m": 146.1,
    "predicted_capacity_ratio": 0.6,
    "forecast_risk": "MEDIUM",
    "_junction_avg_speed_kmh": 0,
    "tls_id": "cluster_245647168_3238255150_3495323634",
    "raw_state": "GGrrrrrrrrrrGGgrrrr",
    "current_phase": 6,
    "next_switch": 354,
    "remaining_time": 2
  }
}
```

### Tick 2 at 354s
```json
{
  "J1_SAN": {
    "name": "Sancheti Chowk",
    "queue_m": 25,
    "halting_vehicles": 5,
    "active_vehicles": 5,
    "status": "Online",
    "predicted_queue_length_m": 19.2,
    "predicted_capacity_ratio": 0.08,
    "forecast_risk": "LOW",
    "_junction_avg_speed_kmh": 0,
    "tls_id": "cluster_13546492148_1838721956",
    "raw_state": "rrrGGG",
    "current_phase": 2,
    "next_switch": 354,
    "remaining_time": 0
  },
  "J2_SJM": {
    "name": "Shivaji Road–JM Path",
    "queue_m": 0,
    "halting_vehicles": 0,
    "active_vehicles": 4,
    "status": "Online",
    "predicted_queue_length_m": 11.3,
    "predicted_capacity_ratio": 0.06,
    "forecast_risk": "LOW",
    "_junction_avg_speed_kmh": 14.12,
    "tls_id": "cluster_2061304035_245647208",
    "raw_state": "rrGGGGGGG",
    "current_phase": 2,
    "next_switch": 354,
    "remaining_time": 0
  },
  "J3_SAP": {
    "name": "Shivaji Road–Apte Path",
    "queue_m": 175,
    "halting_vehicles": 35,
    "active_vehicles": 36,
    "status": "Online",
    "predicted_queue_length_m": 184.7,
    "predicted_capacity_ratio": 0.76,
    "forecast_risk": "MEDIUM",
    "_junction_avg_speed_kmh": 1.39,
    "tls_id": "cluster_245647168_3238255150_3495323634",
    "raw_state": "GGrrrrrrrrrrGGgrrrr",
    "current_phase": 6,
    "next_switch": 354,
    "remaining_time": 0
  }
}
```

### Tick 3 at 356s
```json
{
  "J1_SAN": {
    "name": "Sancheti Chowk",
    "queue_m": 25,
    "halting_vehicles": 5,
    "active_vehicles": 5,
    "status": "Online",
    "predicted_queue_length_m": 19.2,
    "predicted_capacity_ratio": 0.08,
    "forecast_risk": "LOW",
    "_junction_avg_speed_kmh": 0,
    "tls_id": "cluster_13546492148_1838721956",
    "raw_state": "rrryyy",
    "current_phase": 3,
    "next_switch": 360,
    "remaining_time": 4
  },
  "J2_SJM": {
    "name": "Shivaji Road–JM Path",
    "queue_m": 0,
    "halting_vehicles": 0,
    "active_vehicles": 3,
    "status": "Online",
    "predicted_queue_length_m": 9.1,
    "predicted_capacity_ratio": 0.05,
    "forecast_risk": "LOW",
    "_junction_avg_speed_kmh": 13.57,
    "tls_id": "cluster_2061304035_245647208",
    "raw_state": "rrGyyyyGG",
    "current_phase": 3,
    "next_switch": 360,
    "remaining_time": 4
  },
  "J3_SAP": {
    "name": "Shivaji Road–Apte Path",
    "queue_m": 175,
    "halting_vehicles": 35,
    "active_vehicles": 36,
    "status": "Online",
    "predicted_queue_length_m": 175.3,
    "predicted_capacity_ratio": 0.72,
    "forecast_risk": "MEDIUM",
    "_junction_avg_speed_kmh": 0.03,
    "tls_id": "cluster_245647168_3238255150_3495323634",
    "raw_state": "GGrrrrrrrrrryyyrrrr",
    "current_phase": 7,
    "next_switch": 360,
    "remaining_time": 4
  }
}
```
