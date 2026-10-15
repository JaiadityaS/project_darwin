"""Tests for the H-1 analysis, with a small local git repository."""

from __future__ import annotations

import subprocess

from floor.h1 import analyse, changed_paths, commit_of, flips, pair_verdict, same_commit_pairs, shared_commits


def _row(ref, created, floor):
    return {"ref": ref, "created": created, "floor": floor}


def test_commit_of():
    assert commit_of("main-cuda-" + "a" * 40) == "a" * 40
    assert commit_of("main") is None


def test_flips_finds_neighbours_with_different_floors():
    rows = [_row("c", "2025-03", "x86-64-v3"), _row("a", "2025-01", "x86-64-v3"),
            _row("b", "2025-02", "x86-64-v4"), _row("d", "2025-04", "x86-64-v3")]
    assert [(a["ref"], b["ref"]) for a, b in flips(rows)] == [("a", "b"), ("b", "c")]


def test_same_commit_pairs():
    sha = "b" * 40
    rows_a = [_row(f"main-{sha}", "2025-01", "x86-64-v4"), _row("main-" + "c" * 40, "2025-02", "x86-64-v3")]
    rows_b = [_row(f"main-cuda-{sha}", "2025-01", "x86-64-v3"), _row("main-cuda-" + "c" * 40, "2025-02", "x86-64-v3")]
    pairs = same_commit_pairs(rows_a, rows_b)
    assert [(p["commit"], p["a_floor"], p["b_floor"]) for p in pairs] == [(sha, "x86-64-v4", "x86-64-v3")]
    assert shared_commits(rows_a, rows_b) == 2
    assert pair_verdict(pairs, 2).startswith("supported: 1 of 2")
    assert pair_verdict([], 2).startswith("not supported")
    assert pair_verdict([], 0) == "no shared commits"


def _git(repo, *args):
    return subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, text=True).stdout.strip()


def _commit(repo, path, text):
    (repo / path).parent.mkdir(parents=True, exist_ok=True)
    (repo / path).write_text(text, encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "-c", "user.name=t", "-c", "user.email=t@example.invalid", "commit", "-q", "-m", path)
    return _git(repo, "rev-parse", "HEAD")


def test_analyse_with_git_history(tmp_path):
    repo = tmp_path / "w"
    repo.mkdir()
    _git(repo, "init", "-q")
    c1 = _commit(repo, "README.md", "1")
    c2 = _commit(repo, "src/whisper.cpp", "2")
    c3 = _commit(repo, "ggml/src/ggml-cpu/ops.cpp", "3")
    assert changed_paths(str(repo), c1, c2) == []
    assert changed_paths(str(repo), c2, c3) == ["ggml/src/ggml-cpu/ops.cpp"]

    rows = [_row(f"main-{c1}", "2025-01", "x86-64-v3"), _row(f"main-{c2}", "2025-02", "x86-64-v4"),
            _row(f"main-{c3}", "2025-03", "x86-64-v3")]
    result = analyse(rows, str(repo))
    assert result["flips"] == 2
    assert result["flips_without_floor_path_changes"] == 1
    assert result["details"][0]["direction"] == "raised"
    assert result["verdict"].startswith("partly supported")
    assert analyse(rows[:2], str(repo))["verdict"].startswith("supported")
    assert analyse(rows, None)["verdict"] == "not checked (no git history)"
