import pytest
from app.sim.spillback import SpillbackEngine

def test_spillback_engine_safe():
    engine = SpillbackEngine({"J1": 100.0})
    result = engine.evaluate("J1", "Junction 1", 30.0) # 30%
    assert result is None

def test_spillback_engine_watch():
    engine = SpillbackEngine({"J1": 100.0})
    result = engine.evaluate("J1", "Junction 1", 45.0) # 45%
    assert result is not None
    assert result["severity"] == "WATCH"

def test_spillback_engine_high():
    engine = SpillbackEngine({"J1": 100.0})
    result = engine.evaluate("J1", "Junction 1", 80.0) # 80%
    assert result is not None
    assert result["severity"] == "HIGH"

def test_spillback_engine_spillback():
    engine = SpillbackEngine({"J1": 100.0})
    result = engine.evaluate("J1", "Junction 1", 95.0) # 95%
    assert result is not None
    assert result["severity"] == "SPILLBACK"

def test_spillback_engine_default_capacity():
    engine = SpillbackEngine()
    # default is 200.0
    result = engine.evaluate("UNKNOWN", "Unknown", 160.0) # 160/200 = 80%
    assert result is not None
    assert result["severity"] == "HIGH"
