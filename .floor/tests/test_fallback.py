import pytest

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


# Real lines from upstream .devops/main-cuda, main-rocm and main-intel.Dockerfile.
CUDA = ("RUN --mount=type=secret,id=HF_TOKEN,required=false,env=HF_TOKEN make base.en "
        "CMAKE_ARGS=\"-DGGML_CUDA=1 -DCMAKE_CUDA_ARCHITECTURES='75;80;86;90'\"\n")
ROCM = """RUN dnf -y --nodocs --setopt=install_weak_deps=False \\
  install \\
  make gcc gcc-c++ cmake git ninja-build rdma-core-devel \\
  amdrocm-core-devel7.14-gfx1151 \\
  && dnf clean all && rm -rf /var/cache/dnf/*

COPY .. .
RUN make base.en CMAKE_ARGS="-DGGML_HIP=1 -DAMDGPU_TARGETS=\\"gfx1100;gfx1101;gfx1102;gfx1103;gfx1150;gfx1151;gfx1152;gfx1200;gfx1201\\""
"""
INTEL = """RUN if [ "${GGML_SYCL_F16}" = "ON" ]; then \\
        echo "GGML_SYCL_F16 is set" \\
        && export OPT_SYCL_F16="-DGGML_SYCL_F16=ON"; \\
    fi && \\
    make base.en CMAKE_ARGS="-DGGML_SYCL=1 -DCMAKE_C_COMPILER=icx -DCMAKE_CXX_COMPILER=icpx ${OPT_SYCL_F16}"
"""


@pytest.mark.parametrize("text, kept", [
    (CUDA, "-DGGML_CUDA=1 -DCMAKE_CUDA_ARCHITECTURES='75;80;86;90'"),
    (ROCM, '-DGGML_HIP=1 -DAMDGPU_TARGETS=\\"gfx1100;gfx1101;gfx1102;gfx1103;gfx1150;gfx1151;gfx1152;gfx1200;gfx1201\\"'),
    (INTEL, "-DGGML_SYCL=1 -DCMAKE_C_COMPILER=icx -DCMAKE_CXX_COMPILER=icpx ${OPT_SYCL_F16}"),
])
def test_quoted_cmake_args_keep_their_text(text, kept):
    # Only the make command changes: the quotes, the escapes and the dnf package list stay.
    out = fallback.patch_dockerfile(text)
    assert out == text.replace(kept, f"{kept} {FLAGS}")
    assert fallback.patch_dockerfile(out) == out


def test_make_as_a_package_name_is_not_a_command():
    out = fallback.patch_dockerfile("RUN apt-get install -y make && make base.en\n")
    assert out == f'RUN apt-get install -y make && make CMAKE_ARGS="{FLAGS}" base.en\n'


def test_environment_prefix_and_substitution():
    out = fallback.patch_dockerfile('RUN CMAKE_ARGS="-DGGML_VULKAN=1" make -j$(nproc) base.en\n')
    assert out == f'RUN CMAKE_ARGS="-DGGML_VULKAN=1 {FLAGS}" make -j$(nproc) base.en\n'
    out = fallback.patch_dockerfile("RUN make -j$(nproc) base.en CMAKE_ARGS='-DGGML_NATIVE=ON' > log 2>&1\n")
    assert out == f"RUN make -j$(nproc) base.en CMAKE_ARGS='{FLAGS}' > log 2>&1\n"


def test_cmake_configure_over_lines():
    text = "RUN cmake -B build \\\n    -DGGML_NATIVE=ON \\\n    -DGGML_CUDA=1 \\\n    && cmake --build build\n"
    out = fallback.patch_dockerfile(text)
    assert out == f"RUN cmake -B build \\\n    -DGGML_CUDA=1 {FLAGS} \\\n    && cmake --build build\n"
    assert fallback.patch_dockerfile(out) == out


def test_apply_changes_only_allowed_paths(tmp_path):
    (tmp_path / ".devops").mkdir()
    (tmp_path / ".devops" / "main.Dockerfile").write_text(UPSTREAM, encoding="utf-8")
    (tmp_path / ".devops" / "other.Dockerfile").write_text("FROM x\n", encoding="utf-8")
    changed = fallback.apply(tmp_path)
    assert changed == [".devops/main.Dockerfile", ".floor/overrides/main.flags"]
    assert paths.check(changed, "agent") == [] and paths.check(changed, "merge-bot") == []
    assert (tmp_path / ".floor/overrides/main.flags").read_text(encoding="utf-8") == FLAGS + "\n"
    assert fallback.apply(tmp_path) == []


def test_pending_writes_nothing(tmp_path):
    (tmp_path / ".devops").mkdir()
    (tmp_path / ".devops" / "main.Dockerfile").write_text(UPSTREAM, encoding="utf-8")
    assert fallback.pending(tmp_path) == [".devops/main.Dockerfile", ".floor/overrides/main.flags"]
    assert not (tmp_path / ".floor").exists()
    assert (tmp_path / ".devops" / "main.Dockerfile").read_text(encoding="utf-8") == UPSTREAM
    fallback.apply(tmp_path)
    assert fallback.pending(tmp_path) == []


def test_cli(tmp_path, capsys):
    (tmp_path / ".devops").mkdir()
    (tmp_path / ".devops" / "main.Dockerfile").write_text(UPSTREAM, encoding="utf-8")
    assert main(["fallback", "--root", str(tmp_path)]) == 0
    assert ".devops/main.Dockerfile" in capsys.readouterr().out
