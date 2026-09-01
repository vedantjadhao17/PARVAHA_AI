import sys
import re

with open("app/sim/manager.py", "r") as f:
    content = f.read()

# 1. Add _get_tls_id helper
if "def _get_tls_id" not in content:
    helper = """
    def _get_tls_id(self, junction_id):
        if not hasattr(self, 'config') or not self.config:
            return None
        for j in self.config.get("junctions", []):
            if j["junction_id"] == junction_id:
                return j.get("tls_id")
        return None
        
    def _update_junctions(self):"""
    content = content.replace("    def _update_junctions(self):", helper)

# 2. Fix _update_junctions
old_update = """            try:
                tl_state = traci.trafficlight.getRedYellowGreenState(jid)
                if 'G' in tl_state or 'g' in tl_state:
                    signal = "GREEN"
                elif 'y' in tl_state or 'Y' in tl_state:
                    signal = "YELLOW"
                else:
                    signal = "RED"
            except traci.exceptions.TraCIException:
                signal = "UNKNOWN" """
new_update = """            tls_id = self._get_tls_id(jid)
            try:
                if tls_id:
                    tl_state = traci.trafficlight.getRedYellowGreenState(tls_id)
                    if 'G' in tl_state or 'g' in tl_state:
                        signal = "GREEN"
                    elif 'y' in tl_state or 'Y' in tl_state:
                        signal = "YELLOW"
                    else:
                        signal = "RED"
                else:
                    signal = "UNKNOWN"
            except traci.exceptions.TraCIException:
                signal = "UNKNOWN" """
content = content.replace(old_update, new_update)

# 3. Fix _collect_raw_telemetry
old_telemetry = """        try:
            tl_state = traci.trafficlight.getRedYellowGreenState("J1_SAN")
            is_green = 1 if ('G' in tl_state or 'g' in tl_state) else 0
            is_yellow = 1 if ('Y' in tl_state or 'y' in tl_state) else 0
            is_red = 1 if all(c in ['r', 'R'] for c in tl_state) else 0
        except:
            is_green, is_yellow, is_red = 0, 0, 0"""
new_telemetry = """        try:
            tls_id = self._get_tls_id("J1_SAN")
            if tls_id:
                tl_state = traci.trafficlight.getRedYellowGreenState(tls_id)
                is_green = 1 if ('G' in tl_state or 'g' in tl_state) else 0
                is_yellow = 1 if ('Y' in tl_state or 'y' in tl_state) else 0
                is_red = 1 if all(c in ['r', 'R'] for c in tl_state) else 0
            else:
                is_green, is_yellow, is_red = 0, 0, 0
        except:
            is_green, is_yellow, is_red = 0, 0, 0"""
content = content.replace(old_telemetry, new_telemetry)

# 4. Fix _execute_plan to use _get_tls_id, return False if clearance phase, handle retries
# Since _execute_plan previously cleared self.pending_plan in the loop, we will move the clearance logic.
old_execute = """    def _execute_plan(self, plan):
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

new_execute = """    def _execute_plan(self, plan):
        import traci
        # First pass: Check if ANY junction is in a clearance phase.
        # If so, we delay applying the entire plan to keep it synchronized.
        for action in plan.junction_actions:
            tls_id = self._get_tls_id(action.junction_id)
            if not tls_id:
                continue
            try:
                tl_state = traci.trafficlight.getRedYellowGreenState(tls_id)
                if 'y' in tl_state.lower() or all(c in 'rsRS' for c in tl_state):
                    logger.info(f"Delaying signal change for plan {plan.plan_id}: {action.junction_id} is currently in a clearance phase.")
                    return False # Tell the caller to keep pending_plan and retry later
            except Exception as e:
                pass
                
        # Second pass: Apply the changes
        for action in plan.junction_actions:
            tls_id = self._get_tls_id(action.junction_id)
            if not tls_id:
                logger.error(f"Cannot find tls_id for junction {action.junction_id}")
                continue
            try:
                traci.trafficlight.setPhase(tls_id, action.phase_id)
                traci.trafficlight.setPhaseDuration(tls_id, action.target_timing)
                logger.info(f"Applied action to {action.junction_id} (TLS {tls_id}): phase {action.phase_id} duration {action.target_timing}s")
            except Exception as e:
                logger.error(f"Failed to apply signal change to {action.junction_id}: {e}")
        return True # Success"""
content = content.replace(old_execute, new_execute)

# 5. Fix the loop caller
old_loop = """                # Check for approved plans to execute
                with self.lock:
                    if self.pending_plan:
                        self._execute_plan(self.pending_plan)
                        self.pending_plan = None"""
new_loop = """                # Check for approved plans to execute
                with self.lock:
                    if self.pending_plan:
                        success = self._execute_plan(self.pending_plan)
                        if success:
                            self.pending_plan = None"""
content = content.replace(old_loop, new_loop)

with open("app/sim/manager.py", "w") as f:
    f.write(content)
