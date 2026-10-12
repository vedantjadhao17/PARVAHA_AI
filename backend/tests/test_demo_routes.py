from pathlib import Path
import xml.etree.ElementTree as ET

import pytest


@pytest.mark.parametrize("path", sorted((Path(__file__).resolve().parents[1] / "sumo_network/routes").glob("demo_*.rou.xml")))
def test_demo_flows_are_sorted_by_departure(path):
    departures = [float(flow.attrib["begin"]) for flow in ET.parse(path).getroot().findall("flow")]
    assert departures == sorted(departures), "SUMO silently skips out-of-order flows"
