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


MR_ENV = {"FLOOR_HUMANS": "alice bob", "GITLAB_USER_LOGIN": "alice", "CI_MERGE_REQUEST_IID": "7",
          "CI_API_V4_URL": "https://gitlab.example/api/v4", "CI_MERGE_REQUEST_PROJECT_ID": "42"}


def test_pipeline_actor():
    def author(name):
        return lambda api, project, iid: name

    assert paths.pipeline_actor({**MR_ENV, "CI_MERGE_REQUEST_IID": ""}) == (
        "human", ["pipeline user alice: a human (FLOOR_HUMANS)"])
    assert paths.pipeline_actor(MR_ENV, author("bob"))[0] == "human"
    # A human runs the pipeline of an agent MR again (D-014, gap 1).
    assert paths.pipeline_actor(MR_ENV, author("floor-agent")) == (
        "agent", ["pipeline user alice: a human (FLOOR_HUMANS)", "MR author floor-agent: counts as an agent"])
    # Deny by default: no answer from the API, or no pipeline user.
    assert paths.pipeline_actor(MR_ENV, author(None))[1][-1] == "MR author: unknown, counts as an agent"
    assert paths.pipeline_actor({**MR_ENV, "GITLAB_USER_LOGIN": ""}, author("bob"))[0] == "agent"
    assert paths.pipeline_actor({"GITLAB_USER_LOGIN": "alice"})[0] == "agent"


def test_mr_author(monkeypatch):
    class Response:
        def __init__(self, body):
            self.body = body

        def raise_for_status(self):
            if self.body is None:
                raise paths.requests.HTTPError("404")

        def json(self):
            return self.body

    calls = []

    def get(url, timeout):
        calls.append(url)
        return Response(bodies.pop(0))

    bodies = [{"author": {"username": "floor-agent"}}, None, {"author": None}]
    monkeypatch.setattr(paths.requests, "get", get)
    assert paths.mr_author("https://gitlab.example/api/v4", "42", "7") == "floor-agent"
    assert calls == ["https://gitlab.example/api/v4/projects/42/merge_requests/7"]
    assert paths.mr_author("https://gitlab.example/api/v4", "42", "7") is None
    assert paths.mr_author("https://gitlab.example/api/v4", "42", "7") is None


def test_cli_auto(monkeypatch, capsys):
    for name, value in MR_ENV.items():
        monkeypatch.setenv(name, value)
    monkeypatch.setattr(paths, "mr_author", lambda api, project, iid: "bob")
    assert main(["paths", "--actor", "auto", "src/whisper.cpp"]) == 0
    assert "human: code-owner review applies" in capsys.readouterr().out
    monkeypatch.setattr(paths, "mr_author", lambda api, project, iid: "floor-agent")
    assert main(["paths", "--actor", "auto", "src/whisper.cpp"]) == 1
    out = capsys.readouterr().out
    assert "MR author floor-agent: counts as an agent" in out and "agent: NOT allowed" in out
    assert main(["paths", "--actor", "auto", ".devops/main.Dockerfile"]) == 0
