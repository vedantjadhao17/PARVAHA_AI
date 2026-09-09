# PRAVAHA-AI Architecture & Walkthrough
Status: PRAVAHA-AI Phase 8 COMPLETE — RELEASE CANDIDATE FROZEN FOR CONTROLLED SIH 2026 DEMONSTRATION AND EVALUATION.

Core PRAVAHA forecasting, decision, SafetyGate, counterfactual, approval, rollback, and benchmark pipelines remained unchanged. Only isolated SIH demonstration scenario assets and their calibration artifacts were modified. 

The system operates strictly as a simulation-backed, human-approved, SafetyGate-constrained decision support tool. It processes live SUMO data, utilizes XGBoost for near-term forecasting, evaluates bounded signal perturbations against a counterfactual baseline, and ensures no structural cycle violations before offering a reversible plan to the human operator.
