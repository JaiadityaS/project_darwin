"""The 20-issue spot check of the keyword counts (PRD §3.2, T-64).

A keyword hit is not a confirmed bug. The spot check takes a seeded sample of the GitHub search hits and
gives each sampled hit one label, read from its thread. This module draws the sample again, checks that
the labels are for that sample and counts them. The labels are a reading of each thread, so every label
has a reason that a person can check against the issue.
"""

from __future__ import annotations

import random

# What each label means. "floor" is a true positive.
LABELS = {
    "floor": "the thread shows a crash from an instruction that the CPU (or the CPU and its OS) cannot run, "
             "because the build used it: a missing CPU feature, or a fix that removes it from the build. "
             "A pull request that fixes such crashes counts too",
    "likely": "the CPU lacks an instruction set that builds of that time used, but nobody confirmed the fix",
    "unknown": "an illegal-instruction crash, but the thread does not show the cause",
    "not-floor": "not a CPU illegal-instruction crash: another device's error, or the words only in passing",
}


def sample(numbers: list[int], n: int = 20, seed: int = 64) -> list[int]:
    """The issue numbers of the spot check: a seeded random sample, in number order."""
    return sorted(random.Random(seed).sample(sorted(numbers), n))


def summary(doc: dict) -> dict:
    """Counts and rates of the labels. Fails if the labels are not exactly the seeded sample."""
    hits = [hit["number"] for hit in doc["hits"]]
    if len(hits) != doc["total_count"]:
        raise ValueError(f"{len(hits)} hits listed, but the search found {doc['total_count']}")
    expected = sample(hits, doc["n"], doc["seed"])
    labelled = sorted(row["number"] for row in doc["labels"])
    if labelled != expected:
        raise ValueError(f"the labels are for {labelled}, but the sample is {expected}")
    for row in doc["labels"]:
        if row["label"] not in LABELS or not row.get("reason"):
            raise ValueError(f"#{row['number']}: needs a label from {sorted(LABELS)} and a reason")
    counts = {label: sum(row["label"] == label for row in doc["labels"]) for label in LABELS}
    n = doc["n"]
    return {"query": doc["query"], "hits": len(hits), "sampled": n, "counts": counts,
            "true_positive_rate": counts["floor"] / n,
            "with_likely": (counts["floor"] + counts["likely"]) / n,
            "upper_bound": (n - counts["not-floor"]) / n}


def text(result: dict) -> str:
    c = result["counts"]
    return (f"Spot check of {result['sampled']} of {result['hits']} hits: {c['floor']} floor, {c['likely']} likely, "
            f"{c['unknown']} unknown, {c['not-floor']} not-floor. True positives: {result['true_positive_rate']:.0%} "
            f"({result['with_likely']:.0%} with the likely one{'s' if c['likely'] != 1 else ''}; "
            f"{result['upper_bound']:.0%} if every unknown is a floor crash)")
