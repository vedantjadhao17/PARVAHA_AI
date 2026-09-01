import sys
import os

with open("app/main.py", "r") as f:
    content = f.read()

# Add plan application to main.py
new_approve = """    alert.status = "Resolved"
    db.add(log_entry)
    db.commit()
    
    # 2. ACTUALLY EXECUTE THE PLAN IN THE SIMULATION
    sim_manager.apply_plan(plan)
    
    return {"status": "success", "log_id": log_entry.id}"""
content = content.replace("""    alert.status = "Resolved"
    db.add(log_entry)
    db.commit()
    
    return {"status": "success", "log_id": log_entry.id}""", new_approve)

with open("app/main.py", "w") as f:
    f.write(content)


with open("app/sim/manager.py", "r") as f:
    sim_content = f.read()

sim_init = """        self.feature_extractor = LiveFeatureExtractor(self.feature_names)
        self.pending_plan = None"""
sim_content = sim_content.replace("""        self.feature_extractor = LiveFeatureExtractor(self.feature_names)""", sim_init)

sim_apply = """    def apply_plan(self, plan):
        with self.lock:
            self.pending_plan = plan
            
    def _execute_plan(self, plan):
        for action in plan.junction_actions:
            try:
                import traci
                traci.trafficlight.setPhase(action.junction_id, action.phase_id)
                traci.trafficlight.setPhaseDuration(action.junction_id, action.target_timing)
                logger.info(f"Applied action to {action.junction_id}: phase {action.phase_id} duration {action.target_timing}s")
            except Exception as e:
                logger.error(f"Failed to apply signal change to {action.junction_id}: {e}")
                
    def _run_pipeline(self):"""
sim_content = sim_content.replace("""    def _run_pipeline(self):""", sim_apply)

sim_loop = """                # Check for approved plans to execute
                with self.lock:
                    if self.pending_plan:
                        self._execute_plan(self.pending_plan)
                        self.pending_plan = None

                # Collect 5s Raw Telemetry for J1_SAN_GANESHKHIND"""
sim_content = sim_content.replace("""                # Collect 5s Raw Telemetry for J1_SAN_GANESHKHIND""", sim_loop)

with open("app/sim/manager.py", "w") as f:
    f.write(sim_content)
