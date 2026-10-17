import copy
import io
import json
import sys

import pytest
import yaml

from floor import delta_m, judge, manifest, policy
from floor.cli import main

SCENARIO = {
    "dimension": "cpu",
    "change": "x86-64-v1 -> x86-64-v3",
    "n_affected": {"low": 1000, "high": 4000, "source": "test"},
    "e_kgco2e": {"low": 200, "high": 400, "source": "test"},
    "p": [0.05, 0.01, 0.02],
    "delta_years": {"low": 1, "high": 2, "source": "test"},
    "lifespan_years": {"low": 4, "high": 5, "source": "test"},
}


def test_range_and_sensitivity():
    result = delta_m.compute(SCENARIO)
    assert result["low_kgco2e"] == 1000 * 200 * 0.01 * (1 / 5) == 400
    assert result["high_kgco2e"] == 4000 * 400 * 0.05 * (2 / 4) == 40000
    assert [row["p"] for row in result["sensitivity"]] == [0.01, 0.02, 0.05]
    assert result["sensitivity"][1] == {"p": 0.02, "low_kgco2e": 800.0, "high_kgco2e": 16000.0}
    assert "never inside" in result["note"]


def test_zero_when_floors_hold():
    result = delta_m.compute(SCENARIO, floors_held=True)
    assert result["low_kgco2e"] == result["high_kgco2e"] == 0
    assert all(row["high_kgco2e"] == 0 for row in result["sensitivity"])


def test_load_refuses_bad_yaml(tmp_path):
    for text in ("n_affected: [\n", "- 1\n"):
        (tmp_path / "s.yml").write_text(text, encoding="utf-8")
        with pytest.raises(delta_m.ScenarioError):
            delta_m.load(tmp_path / "s.yml")


def test_life_fraction_is_capped():
    doc = copy.deepcopy(SCENARIO)
    doc["delta_years"] = {"low": 9, "high": 9, "source": "test"}
    assert delta_m.compute(doc)["high_kgco2e"] == 4000 * 400 * 0.05


@pytest.mark.parametrize("change, problem", [
    (lambda d: d["n_affected"].update(source=""), "n_affected: needs a source"),
    (lambda d: d["e_kgco2e"].update(low=500), "e_kgco2e: needs 0 < low <= high"),
    (lambda d: d.update(p=[2]), "p: needs shares"),
    (lambda d: d.pop("lifespan_years"), "lifespan_years: missing"),
])
def test_bad_scenarios(change, problem):
    doc = copy.deepcopy(SCENARIO)
    change(doc)
    with pytest.raises(delta_m.ScenarioError, match=problem):
        delta_m.validate(doc)


def test_template_is_refused_until_filled():
    with pytest.raises(delta_m.ScenarioError):
        delta_m.load(policy.PACKAGE_ROOT / "scenarios" / "TEMPLATE.yml")


def test_notice_line_and_markdown():
    result = delta_m.compute(SCENARIO)
    assert delta_m.notice_line(result).startswith("400.0–40000.0 kgCO₂e (N 1000–4000")
    assert "| 2% | 800.0 | 16000.0 |" in delta_m.markdown(result)


def test_manifest_takes_the_range_only_for_a_raise():
    doc = policy.load()
    raised = judge.judge(doc, scan={"floor": {"level": "x86-64-v3"}, "files": {"errors": []}})
    scenario = delta_m.compute(SCENARIO)
    built = manifest.build(raised, subject="s", digest="a" * 64, release="r", commit="c", delta_m=scenario)
    assert built["predicate"]["delta_m_kgco2e"]["high"] == 40000
    held = judge.judge(doc, scan={"floor": {"level": "x86-64-v1"}, "files": {"errors": []}})
    built = manifest.build(held, subject="s", digest="a" * 64, release="r", commit="c", delta_m=scenario)
    assert built["predicate"]["delta_m_kgco2e"]["high"] == 0


def test_cli(tmp_path, capsys):
    path = tmp_path / "s.yml"
    path.write_text(yaml.safe_dump(SCENARIO), encoding="utf-8")
    out = tmp_path / "dm.json"
    assert main(["delta-m", str(path), "--out", str(out)]) == 0
    assert json.loads(out.read_text(encoding="utf-8"))["high_kgco2e"] == 40000
    verdict = tmp_path / "judge.json"
    verdict.write_text(json.dumps({"pareto": "held"}), encoding="utf-8")
    assert main(["delta-m", str(path), "--judge", str(verdict)]) == 0
    assert "0 when every floor holds" in capsys.readouterr().out
    assert main(["delta-m", str(policy.PACKAGE_ROOT / "scenarios" / "TEMPLATE.yml")]) == 2


def test_cli_on_a_console_without_utf8(tmp_path, monkeypatch):
    # A Windows pipe uses cp1252, which has no Δ or ₂.
    path = tmp_path / "s.yml"
    path.write_text(yaml.safe_dump(SCENARIO), encoding="utf-8")
    console = io.TextIOWrapper(io.BytesIO(), encoding="cp1252")
    monkeypatch.setattr(sys, "stdout", console)
    assert main(["delta-m", str(path)]) == 0
    console.flush()
    assert console.buffer.getvalue().decode("cp1252").startswith("?M (scenario): 400.0–40000.0 kgCO?e")
