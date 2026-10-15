from floor import fallback, paths
from floor.cli import main

UPSTREAM = """FROM ubuntu:22.04 AS build
WORKDIR /app

RUN apt-get update && \\
  apt-get install -y build-essential wget cmake git \\
  && rm -rf /var/lib/apt/lists/* /var/cache/apt/archives/*

COPY .. .
RUN --mount=type=secret,id=HF_TOKEN,required=false,env=HF_TOKEN make base.en

FROM ubuntu:22.04 AS runtime
"""
FLAGS = "-DGGML_NATIVE=OFF -DGGML_BACKEND_DL=ON -DGGML_CPU_ALL_VARIANTS=ON -DBUILD_SHARED_LIBS=ON"


def test_upstream_make_line():
    out = fallback.patch_dockerfile(UPSTREAM)
    assert f'env=HF_TOKEN make CMAKE_ARGS="{FLAGS}" base.en\n' in out
    assert "apt-get install -y build-essential wget cmake git \\\n" in out
    assert fallback.patch_dockerfile(out) == out  # idempotent


def test_existing_cmake_args_are_merged():
    out = fallback.patch_dockerfile('RUN make build CMAKE_ARGS="-DGGML_NATIVE=ON -DWHISPER_SDL2=ON" && echo ok\n')
    assert out == f'RUN make build CMAKE_ARGS="-DWHISPER_SDL2=ON {FLAGS}" && echo ok\n'


def test_cmake_configure_line():
    text = "RUN cmake -B build -DGGML_NATIVE=ON -DGGML_CUDA=1 && cmake --build build -j 8\n"
    out = fallback.patch_dockerfile(text)
    assert out == f"RUN cmake -B build -DGGML_CUDA=1 {FLAGS} && cmake --build build -j 8\n"
    assert fallback.patch_dockerfile(out) == out


def test_comments_untouched():
    assert fallback.patch_dockerfile("# run make base.en here\n") == "# run make base.en here\n"


def test_apply_changes_only_allowed_paths(tmp_path):
    (tmp_path / ".devops").mkdir()
    (tmp_path / ".devops" / "main.Dockerfile").write_text(UPSTREAM, encoding="utf-8")
    (tmp_path / ".devops" / "other.Dockerfile").write_text("FROM x\n", encoding="utf-8")
    changed = fallback.apply(tmp_path)
    assert changed == [".devops/main.Dockerfile", ".floor/overrides/main.flags"]
    assert paths.check(changed, "agent") == [] and paths.check(changed, "merge-bot") == []
    assert (tmp_path / ".floor/overrides/main.flags").read_text(encoding="utf-8") == FLAGS + "\n"
    assert fallback.apply(tmp_path) == []


def test_cli(tmp_path, capsys):
    (tmp_path / ".devops").mkdir()
    (tmp_path / ".devops" / "main.Dockerfile").write_text(UPSTREAM, encoding="utf-8")
    assert main(["fallback", "--root", str(tmp_path)]) == 0
    assert ".devops/main.Dockerfile" in capsys.readouterr().out
