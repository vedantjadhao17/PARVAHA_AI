with open("app/sim/manager.py", "r") as f:
    content = f.read()

new_execute = """    def _execute_plan(self, plan):
        for action in plan.junction_actions:
            try:
                import traci
                
                # J1_SAN -> cluster_13546492148_1838721956
                # We need to map junction_id to tls_id from the loaded config
                tls_id = None
                for j in self.config["junctions"]:
                    if j["junction_id"] == action.junction_id:
                        tls_id = j["tls_id"]
                        break
                        
                if not tls_id:
                    logger.error(f"Cannot find tls_id for junction {action.junction_id}")
                    continue
                    
                traci.trafficlight.setPhase(tls_id, action.phase_id)
                traci.trafficlight.setPhaseDuration(tls_id, action.target_timing)
                logger.info(f"Applied action to {action.junction_id} (TLS {tls_id}): phase {action.phase_id} duration {action.target_timing}s")
            except Exception as e:
                logger.error(f"Failed to apply signal change to {action.junction_id}: {e}")"""

old_execute = """    def _execute_plan(self, plan):
        for action in plan.junction_actions:
            try:
                import traci
                traci.trafficlight.setPhase(action.junction_id, action.phase_id)
                traci.trafficlight.setPhaseDuration(action.junction_id, action.target_timing)
                logger.info(f"Applied action to {action.junction_id}: phase {action.phase_id} duration {action.target_timing}s")
            except Exception as e:
                logger.error(f"Failed to apply signal change to {action.junction_id}: {e}")"""

content = content.replace(old_execute, new_execute)

with open("app/sim/manager.py", "w") as f:
    f.write(content)
