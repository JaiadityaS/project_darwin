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

## D-010 (2026-10-16) Merge path: GitLab auto-merge, no merge-bot token
- Facts (2026-10-16, read-only check of the Showcase project 87296266): the team role is "Developer+" (level 30). It can push and merge to protected `main`, run pipelines, add CI/CD variables and webhooks, manage AI Catalog items and change MR settings. It cannot create project access tokens, change protected branches or tags, or manage runners. Duo features and shared runners are on.
- So the PRD merge-bot (F4.4, a project access token) is not possible.
- Decision: the flow opens the fix MR and sets auto-merge ("merge when the pipeline succeeds"). "Pipelines must succeed" is on in the MR settings. GitLab merges only when the gate pipeline passes. A release job on `main` cuts `-floor.N` with `CI_JOB_TOKEN`. The tag pipeline is not needed: the main pipeline does the release work.
- No personal access token in CI. A personal token acts as the human code owner, so CI could then approve and merge Leave-Behind Notices (breaks F6.1), and every merge would look human-made (breaks the Hands-off claim).
- Code-owner approval on `main` needs a Maintainer. Instead, `floor paths` fails the MR pipeline when an agent account changes a code-owned path. With "pipelines must succeed", that blocks the merge.
- Open (T-05): can the flow set auto-merge on its own MR? If not, record it and choose a fallback before G-4.
- PRD impact: F4.4, §10.1, NFR-6. Glossary "Merge-bot" now means this auto-merge path.

## D-011 (2026-10-16) Special prize: Environmental
- Path B Hands-off stays the main target. The special prize is Environmental, and the pitch also uses its creative side.
- Why: Floor is the only entry with ΔM and CPU floors. The six green rivals all measure the operational SCI of pipelines only. The extra work is small (T-54, T-55, T-56, T-60).
- If time is short after Oct 22, cut ΔM polish first.

## D-013 (2026-10-17) Product name: Rieux
- The product name is **Rieux**, after Dr. Bernard Rieux in Camus's *The Plague* (1947). He does the work without heroics, keeps an honest record, and knows that the danger comes back. Our floor came back 15 times in 18 months (T-21).
- "Floor" stays as the name of what Rieux measures. Tagline: "Rieux watches the floor, so no one is left behind."
- Use "Rieux" in the README, the page, the video and the Devpost text. Use "Dr. Rieux" only to explain the source. Say the name ("ree-UH") and its source one time, early in the video.
- No change to code names: the Python package `floor`, the `.floor/` folder and the `floor` commands stay. This saves about a day of rename and test work.
- The book is still under copyright in many countries: at most one short quote with attribution, or none.
- PRD impact: §0 "Floor (working title)" is now Rieux. T-60, T-90, T-91, T-92 use the new name.
