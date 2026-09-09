# Phase A: Demo Scenario Architecture Audit

## 1. Core Network & Topology (Safe for Reuse)
- **SUMO Network (`.net.xml`)**: `backend/sumo_network/network/sancheti_core.net.xml`
- **Detectors (`.add.xml`)**: `backend/sumo_network/additional/corridor_detectors.add.xml`
- **Topology Map**:
  - `J1_SAN`: `cluster_13546492148_1838721956` (Sancheti Chowk)
  - `J2_SJM`: `cluster_2061304035_245647208` (Shivaji/JM Path)
  - `J3_SAP`: `cluster_245647168_3238255150_3495323634` (Shivaji/Apte Path)
- **Finding**: The core network and TLS clusters accurately mirror the `corridor_junctions.json` backend mapping. The `.net.xml` and `.add.xml` files must be universally reused across all new demo scenarios to prevent breaking the frozen PRAVAHA logic.

## 2. Existing Scenarios & Route Generation
- **Existing Configs (`.sumocfg`)**:
  - `sancheti_congestion.sumocfg` (Currently hardcoded into `backend/app/sim/manager.py` as the startup scenario)
  - `corridor_camera.sumocfg`
  - Multiple `phase6/` training datasets (randomized procedural configs)
- **Existing Routes (`.rou.xml`)**:
  - `corridor_demo.rou.xml`
  - `congestion.rou.xml`
  - `smoke.rou.xml`
  - `camera_demo.rou.xml`
- **Route Generators**:
  - `backend/ml/phase6/generate_scenarios.py`: Creates randomized stochastic flows using `randomTrips.py`. *Conclusion: Unsuitable for the SIH demo, which requires deterministic, repeatable narrative arcs.*

## 3. Demo Scenario Strategy
To achieve the 4 requested SIH demo phases (Normal, Rising, High/Spillback, Incident) without touching backend/frontend core code:

1. **Keep Core Files**: We will reference `sancheti_core.net.xml` and `corridor_detectors.add.xml`.
2. **Create Deterministic Route Files**: We will create 4 new `.rou.xml` files using explicit `<flow>` tags (similar to `corridor_demo.rou.xml`) with the `indian_mixed_traffic` vType distribution. This allows absolute deterministic control over `vehsPerHour` propagating from J1 to J3.
3. **Create 4 Target `.sumocfg` Files**:
   - `demo_1_normal.sumocfg`
   - `demo_2_rising.sumocfg`
   - `demo_3_spillback.sumocfg`
   - `demo_4_incident.sumocfg`
4. **Implement Incidents**: As seen in the Phase 6 scripts, an incident can be deterministically triggered by inserting a stationary vehicle (using `<stop lane="..." duration="..."/>`) directly into the `.rou.xml` file. This guarantees the incident happens precisely at the same time and place every demo run.
5. **Runner Access**: Currently, `SimulationManager` hardcodes `sancheti_congestion.sumocfg`. We will either need a minor config-pointer update in `manager.py` to point to the desired demo scenario or a launcher wrapper to inject the desired `.sumocfg` at startup.

## 4. Safety Bounds Met
- No ML models or `.json` weight files will be touched.
- No `corridor_decision_engine.py` or `SafetyGate` logic will be altered.
- All telemetry will remain purely authentic TraCI readouts.
