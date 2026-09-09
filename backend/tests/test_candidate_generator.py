import pytest
from app.sim.candidate_generator import CandidateGenerator
from app.sim.signal_plan import SourceState

@pytest.fixture
def generator():
    return CandidateGenerator()

@pytest.fixture
def dummy_state():
    return SourceState(
        junction_id="J1_SAN",
        tls_id="cluster_13546492148_1838721956",
        simulation_time_s=100.0,
        queue_m=250.0,
        predicted_queue_60s_m=300.0,
        predicted_capacity_ratio=1.2,
        vehicle_count=50,
        avg_speed_kmh=5.0
    )

def test_generate_proposal_includes_hold(generator, dummy_state):
    candidates = generator.generate_candidates(dummy_state)
    assert len(candidates) > 0
    hold = candidates[0]
    assert "HOLD" in hold.rationale

def test_generate_proposal_includes_extensions(generator, dummy_state):
    candidates = generator.generate_candidates(dummy_state)
    assert len(candidates) >= 3
    rationales = [c.rationale for c in candidates]
    assert any("+10s" in r for r in rationales)
    assert any("+5s" in r for r in rationales)

def test_unknown_tls_returns_noop(generator, dummy_state):
    dummy_state.tls_id = "unknown_tls"
    candidates = generator.generate_candidates(dummy_state)
    assert len(candidates) == 0

def test_cycle_preservation_in_candidates(generator, dummy_state):
    candidates = generator.generate_candidates(dummy_state)
    for cand in candidates:
        total_cycle = sum(p.duration for p in cand.phase_specs)
        assert abs(total_cycle - 90.0) < 0.5

def test_phase_ordering_preserved(generator, dummy_state):
    candidates = generator.generate_candidates(dummy_state)
    for cand in candidates:
        indices = [p.phase_idx for p in cand.phase_specs]
        assert indices == sorted(indices)
        assert indices == [0, 1, 2, 3] # J1 has 4 phases
