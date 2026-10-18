from pathlib import Path

import yaml

from floor import paths

FLOWS = Path(__file__).resolve().parents[1] / "flows"


def test_trigger_probe_flow():
    """T-03: the probe flow (AI Catalog flow 1018639) has no tools and no clone, and only reads the event."""
    flow = yaml.safe_load((FLOWS / "trigger-probe.yml").read_text(encoding="utf-8"))
    assert flow["version"] == "v1" and flow["environment"] == "ambient" and flow["coding_environment"] == "none"
    for key in ("name", "description", "product_group"):
        assert key not in flow  # custom flows reject these top-level keys
    [probe] = flow["components"]
    assert probe["toolset"] == [] and probe["inputs"] == [{"from": "context:goal", "as": "event"}]
    assert "max_cycles" not in probe  # the catalog schema rejects it (a disallowed additional property)
    [prompt] = flow["prompts"]
    assert prompt["prompt_id"] == probe["prompt_id"] and "model" not in prompt
    assert "{{event}}" in prompt["prompt_template"]["user"]
    assert flow["routers"] == [{"from": "probe", "to": "end"}] and flow["flow"]["entry_point"] == "probe"


def test_flow_definitions_are_code_owned():
    assert paths.matches(".floor/flows/trigger-probe.yml", paths.CODE_OWNED)
    assert not paths.matches(".floor/flows/trigger-probe.yml", paths.AGENT_ALLOWED)
