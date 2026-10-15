from pathlib import Path

from floor import paths
from floor.cli import main

ROOT = Path(__file__).resolve().parents[2]


def test_agent_allowlist():
    assert paths.check(["deploy/main.tf", ".devops/main.Dockerfile", ".floor/overrides/cmake.txt"], "agent") == []
    found = paths.check([".devops/sub/x.Dockerfile", "ggml/src/ggml-cpu/ggml-cpu.c", ".floor/policy.yml"], "agent")
    assert found == [
        ".devops/sub/x.Dockerfile: outside the agent allowlist",
        ".floor/policy.yml: outside the agent allowlist",
        "ggml/src/ggml-cpu/ggml-cpu.c: engine code (agents never change it)",
    ]


def test_merge_bot():
    assert paths.check(["deploy/main.tf", "README.md"], "merge-bot") == []
    found = paths.check([".floor/floor/judge.py", ".gitlab-ci.yml", ".floor/notices/0001-cpu.md"], "merge-bot")
    assert len(found) == 3 and all("code-owned" in line for line in found)


def test_agent_paths_have_no_owner():
    for allowed in ["deploy/x", ".devops/main.Dockerfile", ".floor/overrides/x"]:
        assert not paths.matches(allowed, paths.CODE_OWNED)


def test_codeowners_matches_code_owned():
    owned = set()
    for line in (ROOT / ".gitlab" / "CODEOWNERS").read_text(encoding="utf-8").splitlines():
        if line.startswith("/"):
            path = line.split()[0].lstrip("/")
            owned.add(path + "**" if path.endswith("/") else path)
    assert owned == set(paths.CODE_OWNED)


def test_cli(capsys):
    assert main(["paths", "--actor", "agent", "deploy/x.tf"]) == 0
    assert main(["paths", "--actor", "agent", "src/whisper.cpp"]) == 1
    assert "NOT allowed" in capsys.readouterr().out
