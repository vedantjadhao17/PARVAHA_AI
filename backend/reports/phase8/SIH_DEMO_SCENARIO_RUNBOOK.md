# PRAVAHA-AI SIH 2026 DEMONSTRATION RUNBOOK

This runbook documents the exact procedures to reliably execute the four designated demonstration scenarios for the SIH 2026 finals. 
These scenarios are powered by physically simulated TraCI/SUMO traffic without any simulated backend mocking or frontend fake data.

## 1. Prerequisites
- The Asteria Command Center backend must NOT be running.
- Terminal 1 (Backend/Scenario Manager)
- Terminal 2 (Frontend React App)

## 2. Launching Scenarios
A dedicated `scripts/run_demo.sh` wrapper handles scenario orchestration while preserving the original Release Candidate server architecture.

### 2.1 Default System (No Scenario)
To prove the system's baseline authenticity, or run the standard Phase 8 benchmarks:
```bash
./scripts/run_demo.sh
```
*Effect: Loads the canonical `sancheti_congestion.sumocfg` baseline.*

### 2.2 Scenario: NORMAL
```bash
./scripts/run_demo.sh NORMAL
```
*Effect: Injects `demo_1_normal.sumocfg`. Demonstrates a free-flowing to moderate traffic baseline (~1000 vph).*

### 2.3 Scenario: RISING CONGESTION
```bash
./scripts/run_demo.sh RISING_CONGESTION
```
*Effect: Injects `demo_2_rising.sumocfg`. Temporally increases demand from 1000vph to 2900vph over 600 seconds to demonstrate progressive queue buildup and XGBoost forecast extrapolation.*

### 2.4 Scenario: SPILLBACK
```bash
./scripts/run_demo.sh SPILLBACK
```
*Effect: Injects `demo_3_spillback.sumocfg`. Introduces a sustained 3400 vph capacity overload resulting in major arterial collapse, triggering native PRAVAHA candidate generation and counterfactual gating.*

### 2.5 Scenario: INCIDENT STRESS
```bash
./scripts/run_demo.sh INCIDENT_STRESS
```
*Effect: Injects `demo_4_incident.sumocfg`. A vehicle physically halts on lane `229904828#1_0` feeding J2, demonstrating bottleneck-driven localized queue growth against nominal (~1000 vph) background demand.*

## 3. Launching Frontend
In a separate terminal:
```bash
cd frontend
npm run dev
```

## 4. Reset & Rollback
To terminate a scenario, press `Ctrl+C` in the backend terminal. The system is stateless. Re-running the script with a different argument immediately transitions the physics model without corrupting the historical Phase 6/8 datasets.
