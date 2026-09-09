import traci
from typing import Dict, Any

class BaselineController:
    """
    Takes over a traffic light in SUMO and manages its signal timing plan.
    Provides methods to modify phase durations dynamically (which the AI will use later).
    """
    def __init__(self, tls_id: str, label: str, traci_conn=None):
        self.traci_conn = traci_conn or traci
        self.tls_id = tls_id
        self.label = label
        self.active = False
        
        # Load the default logic from the .net.xml file to use as our baseline
        logics = self.traci_conn.trafficlight.getCompleteRedYellowGreenDefinition(self.tls_id)
        if not logics:
            raise ValueError(f"No traffic light logic found for {self.tls_id}")
            
        self.baseline_logic = logics[0]
        self.current_logic = self.baseline_logic
        self.active = True

    def get_current_plan(self) -> list:
        """Returns the current cycle plan (list of phase dictionaries)."""
        phases = []
        for i, phase in enumerate(self.current_logic.phases):
            phases.append({
                "phase_idx": i,
                "duration": phase.duration,
                "state": phase.state
            })
        return phases

    def deploy_new_plan(self, phase_durations: Dict[int, float]):
        """
        Takes a dictionary of {phase_idx: new_duration} and deploys a new 
        timing plan to the physical intersection in SUMO.
        """
        # Create a new Logic object based on the baseline
        new_logic = self.traci_conn.trafficlight.Logic(
            programID="AI_ADAPTIVE",
            type=0, # static
            currentPhaseIndex=self.traci_conn.trafficlight.getPhase(self.tls_id),
            phases=list(self.baseline_logic.phases)
        )
        
        # Override the specific phase durations
        for idx, new_dur in phase_durations.items():
            if 0 <= idx < len(new_logic.phases):
                # Create a new phase object because they are immutable in some TraCI versions
                old_p = new_logic.phases[idx]
                new_p = self.traci_conn.trafficlight.Phase(
                    duration=new_dur,
                    state=old_p.state,
                    minDur=old_p.minDur,
                    maxDur=old_p.maxDur,
                    next=old_p.next
                )
                new_logic.phases[idx] = new_p

        # Push to SUMO
        self.traci_conn.trafficlight.setProgramLogic(self.tls_id, new_logic)
        self.current_logic = new_logic
        
    def reset_to_baseline(self):
        """Restores the original SUMO default timing plan."""
        self.baseline_logic.programID = "BASELINE"
        self.traci_conn.trafficlight.setProgramLogic(self.tls_id, self.baseline_logic)
        self.current_logic = self.baseline_logic
