import json
import math
from pathlib import Path

DATA = Path(__file__).resolve().parents[2] / "frontend/public/replay.json"


def test_replay_is_observed_read_only_simulation():
    bundle = json.loads(DATA.read_text())
    assert bundle["metadata"]["mode"] == "recorded_simulation"
    assert len(bundle["frames"]) == 300
    assert [frame["time_s"] for frame in bundle["frames"]] == list(range(2, 601, 2))
    assert len(bundle["trend"]) == 120
    assert set(bundle["cameras"]) == {"J1_SAN", "J2_SJM", "J3_SAP"}
    assert bundle["geometry"]["lanes"]
    for frame in bundle["frames"]:
        assert frame["pending_recommendations"] == []
        assert len(frame["junctions"]) == 3
        for junction in frame["junctions"].values():
            assert math.isfinite(junction["queue_m"])
            assert math.isfinite(junction["predicted_queue_length_m"])
        for vehicle in frame["vehicles"]:
            assert 18 < vehicle["lat"] < 19
            assert 73 < vehicle["lon"] < 74
