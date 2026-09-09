from abc import ABC, abstractmethod
from typing import Dict, List
from app.models.schemas import LinkState, SignalPlan

class Controller(ABC):
    """
    PRD 10.2 Controller Interface.
    Every controller must implement these methods, consuming and returning the 
    same typed objects regardless of the underlying logic (Baseline or PRAVAHA).
    """

    @abstractmethod
    def reset(self, scenario_id: str) -> None:
        """
        Resets the controller state for a new simulation scenario.
        """
        pass

    @abstractmethod
    def decide(self, state: Dict[str, LinkState]) -> SignalPlan:
        """
        Takes the current aggregated network state and returns a coordinated SignalPlan.
        """
        pass
