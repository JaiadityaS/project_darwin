"""Tests for the spot check of the keyword counts (PRD §3.2)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from floor import spotcheck
from floor.cli import main

EVIDENCE = Path(__file__).resolve().parents[1] / "evidence" / "spotcheck" / "illegal-instruction-2026-10-19.json"


def _doc(labels):
    hits = list(range(1, 41))
    numbers = spotcheck.sample(hits, 4, 1)
    return {"query": "q", "total_count": 40, "hits": [{"number": n} for n in hits], "n": 4, "seed": 1,
            "labels": [{"number": n, "label": label, "reason": "r"} for n, label in zip(numbers, labels)]}


def test_sample_is_seeded_and_sorted():
    assert spotcheck.sample(list(range(100, 0, -1)), 5, 7) == spotcheck.sample(list(range(1, 101)), 5, 7)
    assert spotcheck.sample(list(range(1, 101)), 5, 7) == sorted(spotcheck.sample(list(range(1, 101)), 5, 7))


def test_summary_counts_the_labels():
    result = spotcheck.summary(_doc(["floor", "floor", "unknown", "not-floor"]))
    assert result["counts"] == {"floor": 2, "likely": 0, "unknown": 1, "not-floor": 1}
    assert (result["true_positive_rate"], result["with_likely"], result["upper_bound"]) == (0.5, 0.5, 0.75)


def test_summary_needs_the_seeded_sample_and_a_reason():
    doc = _doc(["floor"] * 4)
    doc["labels"][0]["number"] = 99  # not in the sample
    with pytest.raises(ValueError, match="sample"):
        spotcheck.summary(doc)
    doc = _doc(["floor", "floor", "maybe", "floor"])
    with pytest.raises(ValueError, match="#"):
        spotcheck.summary(doc)
    doc = _doc(["floor"] * 4)
    doc["total_count"] = 41
    with pytest.raises(ValueError, match="41"):
        spotcheck.summary(doc)


def test_spot_check_from_repo_evidence(capsys):
    doc = json.loads(EVIDENCE.read_text(encoding="utf-8"))
    assert doc["total_count"] == 39 and doc["n"] == 20
    assert all(row["url"].endswith(f"/issues/{row['number']}") for row in doc["labels"])
    assert main(["spotcheck", str(EVIDENCE)]) == 0
    assert capsys.readouterr().out.strip() == (
        "Spot check of 20 of 39 hits: 13 floor, 1 likely, 4 unknown, 2 not-floor. True positives: 65% "
        "(70% with the likely one; 90% if every unknown is a floor crash)")
