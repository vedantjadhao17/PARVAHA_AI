with open("app/sim/manager.py", "r") as f:
    content = f.read()

old_code = """            try:
                tl_state = traci.trafficlight.getRedYellowGreenState(jid)
                if 'G' in tl_state or 'g' in tl_state:
                    signal = "GREEN"
                elif 'y' in tl_state or 'Y' in tl_state:
                    signal = "YELLOW"
                else:
                    signal = "RED"
            except traci.exceptions.TraCIException:
                signal = "UNKNOWN"
                
            self.state["junctions"][jid] = {"""

new_code = """            try:
                tls_id = self._get_tls_id(jid)
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
                signal = "UNKNOWN"
                
            self.state["junctions"][jid] = {"""

content = content.replace(old_code, new_code)
with open("app/sim/manager.py", "w") as f:
    f.write(content)
