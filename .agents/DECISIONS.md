# DECISIONS

Short records, newest last. Each record: the decision, why, and the PRD impact.

## D-001 (2026-10-14) Dev repo on GitHub, submission on GitLab
- Develop in the private GitHub repo `JaiadityaS/project_darwin`.
- The submission project on GitLab is whisper.cpp at a pinned commit, plus the product files of this repo. A script assembles it (T-02).
- Why: the team can sync now, before GitLab hackathon access is confirmed. Path B also needs a clean "what we added" story.

## D-002 (2026-10-14) Layout mirrors the GitLab overlay
- Product paths in this repo are the paths they get in the whisper.cpp fork: `.floor/` (tools, policy, schemas), `.floor/overrides/`, `deploy/`, `infra/`, `.gitlab-ci.yml`, `CODEOWNERS`.
- Dev-only paths never go to GitLab: `AGENTS.md`, `.agents/`, `scripts/`, `.github/`, `docs/`.
- PRD F1.2 names `.floor/judge/`. The Judge lives in the Python package (`.floor/floor/`). CODEOWNERS must cover all of `.floor/` except `.floor/overrides/`.

## D-003 (2026-10-14) `deploy/` vs `infra/`
- `deploy/` holds the image build recipes of the service. The repair agent may change it (PRD F4.2 allowlist).
- `infra/` holds OpenTofu for Cloud Run and WIF. It is code-owned. The agent may not change it.
- Why: least privilege. The PRD allowlist names `deploy/` for build config, not for cloud config.

## D-004 (2026-10-14) Static decoder: iced-x86 and pyelftools
- iced-x86 gives the exact CPUID features of each opcode form. Capstone groups are too coarse for BMI2, F16C and MOVBE.
- Linear sweep over the executable sections. If there are no section headers, use PT_LOAD segments with the X flag.

## D-005 (2026-10-14) Level map and extras
- Levels follow the x86-64 psABI: v1 baseline, v2, v3, v4.
- A feature in no level (AES, PCLMULQDQ, AVX512_VNNI, AVX_VNNI, ...) is an "extra". No level guarantees an extra, so the Judge must treat an unexpected extra as a raise.
- Some extras imply a minimum level: `AVX512*`, `AMX*`, `AVX10*` imply v4; `AVX_*`, `VAES`, `VPCLMULQDQ` imply v3.

## D-006 (2026-10-14) Allowlist of false positives
- TZCNT (`rep bsf`), ENDBR32/64 and RDSSPD/Q (hint-NOP space), XGETBV (feature detection after a CPUID check).
- Each entry has a reason in `.floor/floor/isa/allowlist.py` and a unit test. The QEMU runs (F3) corroborate the allowlist.

## D-007 (2026-10-14) What counts toward the CPU floor
- Floor = the highest level in always-loaded app code, joined with the lowest-level ggml CPU variant (`libggml-cpu-<tag>.so`). Other variants load only on CPUs that support them.
- Files under `CMakeFiles/` are build tools. The scan reports them but does not count them.
- Distro libraries (glibc, libstdc++, ...) dispatch at run time (ifunc). A linear scan always finds AVX-512 in them, so they do not count. The scan records their GNU ISA-level note when it exists.

## D-008 (2026-10-14) Team sync
- Trunk-based on `main`. Claims live in TASKS.md. Red work goes to `wip/<handle>-<task-id>`.
- One log file per session in `.agents/log/`, so logs never cause merge conflicts.

## D-009 (2026-10-14) No AI attribution; hygiene guard
- Local hooks (`scripts/install-hooks.sh`) run `scripts/guard.sh`: no co-author trailers, no agent-tool files, no tool or vendor names.
- CI runs the same guard on every push.
- Agent-tool files go to `.git/info/exclude`, never to `.gitignore`.
