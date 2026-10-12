import pytest
from pathlib import Path
from app.sim.manager import SimulationManager

def test_manager_initialization():
    project_dir = Path(__file__).resolve().parents[1]
    manager = SimulationManager(project_dir)
    assert hasattr(manager, 'lock'), "SimulationManager is missing 'lock'"
    assert hasattr(manager, 'pending_plan'), "SimulationManager is missing 'pending_plan'"
    assert hasattr(manager, 'state'), "SimulationManager is missing 'state'"
    assert manager.forecaster.model is not None, "Forecast model must load"
