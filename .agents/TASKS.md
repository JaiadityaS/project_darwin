# TASKS: the board

Claim before you code: set `Owner` to your handle and `Status` to `doing`, then push the claim.
One owner per task. PRD references point to `docs/PRD.md`.

Status values: `ready` · `doing` · `done` · `blocked` (waits on another task) · `human` (needs a person: access, accounts, money, a decision) · `later` (SHOULD/COULD work; start only after the MUST work of its gate).

## G-0 Access and trigger chain (due Oct 14)

| ID | Task | PRD | Status | Owner | Notes |
|---|---|---|---|---|---|
| T-01 | Confirm GitLab hackathon group access and tier (Premium or Ultimate) and the Duo credit pool for service-account flows | §9.1, §19 | human | - | Access confirmed 2026-10-16 (D-010). Open: the credit pool |
| T-02 | `scripts/assemble-gitlab.sh`: clone whisper.cpp at a pinned commit, overlay the product files, push to the GitLab project | §0, D-001, D-012 | done | @JaiadityaS | First push 2026-10-17: GitLab `main` `36521198` (the import merge `c503abf1` plus one sync commit). Later syncs: run the script with `--push` again |
| T-03 | Trigger-chain test: a human tag push fails the gate; the pipeline-failed trigger starts a flow; record who counts as the actor | F4.1, §9.1 | blocked | - | Needs T-01 (T-02 is done) |
| T-04 | Duo CLI runs headless in a CI job (Herald, and the floor-repair fallback) | F4.1, F12.1 | blocked | - | Needs T-01 |
| T-05 | Auto-merge test: the flow opens a non-code-owned MR and sets auto-merge; it merges only after the gate passes; an agent change to a code-owned path cannot merge | F4.4, D-010 | blocked | - | The first T-47 pipeline ran (2958271425). Needs a fix MR that `floor fallback` makes (T-41). No project token is possible (D-010) |
| T-06 | Cloud Run hello-world with Workload Identity Federation from GitLab CI | F13.1 | human | - | GCP project and billing first |

## G-1 CPU proof (due Oct 15)

| ID | Task | PRD | Status | Owner | Notes |
|---|---|---|---|---|---|
| T-10 | Static scanner: ELF regions, iced-x86 decode, level map, allowlist, JSON report, CLI | F2.1, F2.2 | done | @JaiadityaS | `.floor/floor/isa/`, `python -m floor scan`. Checked on synthetic ELF files only; T-12 and T-15 give real binaries |
| T-11 | Scanner unit tests: synthetic ELF files and instruction encodings | F2.2 | done | @JaiadityaS | `.floor/tests/test_isa.py` (44 tests) |
| T-12 | Linux builds of whisper.cpp: native, folk fix (`GGML_NATIVE=OFF`), all-variants; scan each; check AC-F2 | AC-F2 | done | @JaiadityaS | cpu-proof run 38702242235: native v3, folk fix v3, all-variants v1. Evidence in `.floor/evidence/cpu-proof/` |
| T-13 | QEMU user-mode harness with negative and positive controls on qemu64, Nehalem, SandyBridge, EPYC-Milan | F3.1, F3.2 | done | @JaiadityaS | AC-F3 met in run 38702242235. | `floor probe` (`qemu.py`, `controls.py`) in `cpu-proof.yml`. Linux only. Also proves that loading every variant at start-up is safe (see log 2026-10-14-jaiadityas-1) |
| T-14 | Dispatch map from ggml's load log | F3.3 | later | - | |
| T-16 | False positive: LZCNT x24 in whisper-cli, whisper-server, test-vad and vad-speech-segments raises them to v3. Probably the audio decoder (dr_flac in miniaudio) behind a CPUID check. Confirm with symbols, then choose a rule (function-scoped allowlist from .symtab, or a rule for LZCNT alone) with tests | F2.2, AC-F2 | done | @JaiadityaS | `allowlist.GUARDED` (LZCNT inside `ma_dr_flac_*`). Run 38700683985: all five audio tools are now v1; only libggml-cpu.so sets the floor (v3). Blocks AC-F2 for the all-variants build. See STATE.md "Facts learned" |
| T-15 | Scan the #3510 images (`main-a1867e0` vs `main-c62adfbd`): first H-1 signal | F10.2, §3.6 | done | @JaiadityaS | Static part done (run 38537736704): a1867e0 = v4 + AVX512_VNNI, c62adfbd = v3. The QEMU part is in T-13 |

## G-2 Backtest and H-1 (due Oct 16)

| ID | Task | PRD | Status | Owner | Notes |
|---|---|---|---|---|---|
| T-20 | OCI client for ghcr.io: tags, manifests, config history, `/app` layer pull, cache by layer digest | F10.1 | done | @JaiadityaS | `.floor/floor/oci.py`, `python -m floor image`. Pull images in `.github/workflows/backtest.yml` (a home link is too slow) |
| T-21 | Backtest sampler: ≥ 30 images across the `main-<sha>` tags, plus every image within two weeks of #3510 and #3814; timeline JSON | F10.1 | done | @JaiadityaS | `floor sample`, `floor timeline`, `.github/workflows/sweep.yml`. Run 38700707825: 61 images, 9 at v4, 15 flips. Evidence in `.floor/evidence/backtest/` |
| T-22 | H-1 analysis: level per image vs changes to `.devops/` and ggml CPU code; verdict with evidence | F10.3 | done | @JaiadityaS | `floor h1`. Supported: 11 of 38 commits built twice (main, main-cuda) have different floors. Evidence: `.floor/evidence/backtest/h1-*.json` |
| T-23 | Backtest footprint (bytes downloaded, CPU time) | F14.4 | later | - | |
| T-24 | #3814: scan `main-cuda` and `main` at the same commit (a strong H-1 test) | F10.2 | done | @JaiadityaS | Run 38538051321: commit 47b9eb37, both v3. #3814 not reproduced at this commit; follow-up in STATE.md |

## G-3 Gate integrity (due Oct 18)

| ID | Task | PRD | Status | Owner | Notes |
|---|---|---|---|---|---|
| T-30 | `.floor/policy.yml` + JSON Schema + CI validation | F1.1, §11.3 | done | @JaiadityaS | `floor policy` (`policy.py`); CI step in `ci.yml`. The ratchet check (F1.2) is not done yet |
| T-31 | Ratchet check: a looser policy needs a merged notice | F1.2 | done | @JaiadityaS | `floor ratchet` (`ratchet.py`), CI step in `ci.yml`. A notice counts when it is in `.floor/notices/` on the target branch and has an `Approved by:` line. Code-owner approval itself is T-36 |
| T-32 | Judge: held / lowered / raised / inconclusive; Pareto rule; unit tests | F5.1, F5.2 | done | @JaiadityaS | `floor judge` (`judge.py`). Memory and connectivity inputs are JSON stubs until T-44 and the offline job give real files |
| T-33 | Manifest writer + diff against the previous release | F5.3, §11.1 | done | @JaiadityaS | `floor manifest`, `floor diff` (`manifest.py`). In-toto Statement only; signing is T-34 (F5.4). Footprint values stay null until measured |
| T-34 | `cosign attest` (keyless, GitLab OIDC) and `verify-attestation` | F5.4 | blocked | - | Needs GitLab |
| T-35 | Leave-Behind Notice template and MR check (agents cannot approve) | F6, §11.2 | doing | @JaiadityaS | Done: MR template `.gitlab/merge_request_templates/Leave-Behind-Notice.md`, `.floor/notices/`, `floor notice`, `notice.approval_problems` (tested on fixed data). The GitLab check job runs `floor notice` (`.gitlab/ci/check.sh`, T-47). Open: the GitLab job that reads the MR approvals API and calls it |
| T-36 | CODEOWNERS, protected branch and tag settings, path-allowlist job | F1.2, §10.1 | doing | @JaiadityaS | Done: `.gitlab/CODEOWNERS` (owner handle to confirm on GitLab), `floor paths` (`paths.py`, kept in sync with CODEOWNERS by a test). The path-allowlist check runs in the check job of every MR pipeline, deny by default (`.gitlab/ci/check.sh`, D-014). Since session 6 the MR author counts too (`floor paths --actor auto`; D-014 gap 1 closed). Open: protected branch and tag settings (our role cannot change them, D-010) |

## Release loop (Oct 19–22)

| ID | Task | PRD | Status | Owner | Notes |
|---|---|---|---|---|---|
| T-40 | floor-repair flow (AI Catalog, private): exit unless raised → diagnose → fix MR | F4.1, F4.2 | blocked | - | Needs T-03 |
| T-41 | Fallback script applies the canned inclusive config; the gate re-verifies | F4.3 | doing | @JaiadityaS | Done: `floor fallback` (`fallback.py`): adds CMAKE_ARGS to each `make` command in the RUN instructions of `.devops/*.Dockerfile` (upstream Makefile reads it), adds the flags to each `cmake -B` command, and writes `.floor/overrides/main.flags`; changes only allowlist paths. Since T-43 it reads RUN instructions as shell words (D-016): the 7 upstream Dockerfiles change in one line each, quotes stay, and a `make` package name stays. Done (D-018): `floor fallback --judge FILE --patch FILE` (a patch for `git apply`; it changes no file; it acts only when the gate failed and the policy has the canned config) and the `fallback` job of `.gitlab-ci.yml` (after a failed judge; the patch is an artifact, "Canned config patch"). CI cannot push, so the flow or a human commits the patch, and the next pipeline re-checks. Open: the first GitLab run (after the next human sync, the main pipeline fails at the judge, so the job must write `out/fallback/fallback.patch`); then T-05 with an MR that commits the patch |
| T-42 | Release job on `main`: cut `-floor.N` with `CI_JOB_TOKEN` after an auto-merge | F4.4, D-010 | blocked | - | Needs T-05 |
| T-43 | Draft notice when the fallback also fails | F4.5 | done | @JaiadityaS | `floor notice-draft` (`notice.draft`, D-016): a draft only when a floor needs a notice and the canned config is already on the branch. The `notice-draft` job (stage `repair`, `when: on_failure`) keeps `out/notice/NNNN-<dimension>.md` as an artifact in the MR widget; a code owner opens the notice MR (no CI token, D-010). Not on GitLab yet |
| T-44 | Memory floor: cgroup limits 512–4096 MB, peak RSS | F7 | done | @JaiadityaS | `floor memory`, `floors.yml`. Run 38704136185: tiny 512, base 512, small 768 MB; set in the policy. Evidence in `.floor/evidence/release/` |
| T-45 | Connectivity tripwire: `--network none` + syscall trace; download sizes | F8 | done | @JaiadityaS | `floor offline`: `unshare --net` + strace. Run 38704136185: offline proven, 0 attempts, 99.4 MB download (tiny.en) |
| T-46 | Herald CI job (Duo CLI) with a deterministic template fallback | F12.1 | blocked | - | Needs T-04 |
| T-47 | `.gitlab-ci.yml`: build → static gate → QEMU → judge → attest → herald → release → deploy | §7.1 | doing | @JaiadityaS | Step 1 done (D-014): check, build, scan, probe ×4, judge, pages; `.gitlab-ci.yml`, `.gitlab/ci/`. The first pipeline 2958271425 failed as planned: cpu raised to x86-64-v4. Step 2 done (D-014): the `memory` job (`floor memory --cgroup`: no systemd on the runner) and the `offline` job, both with chroot into the exported image. Pipeline 2958309699: memory held (tiny 512, base 512, small 768 MB), offline proven. AC-F7/F8 manifest fields written and tested locally (peak RSS and download size per model, the files of the offline run, a job link per floor); not on GitLab yet. Open: the sync and its pipeline (STATE.md "Next agent"), then attest, herald, release, deploy (T-34, T-46, T-42, T-51) |

## Deploy and sustainability

| ID | Task | PRD | Status | Owner | Notes |
|---|---|---|---|---|---|
| T-50 | OpenTofu: Cloud Run in a low-CO₂ region + WIF | F13.1 | blocked | - | Needs T-06 |
| T-51 | Staging → smoke test → production; rollback | F13.2 | blocked | - | Needs T-50 |
| T-52 | Upload page: 30 s cap, rate limit, max instances, no storage | F13.3 | ready | - | |
| T-53 | `/floor` endpoint: host level and loaded variant | F13.4 | later | - | |
| T-54 | SCI per audio-minute and per release check (Impact Framework manifests) | F14.1 | doing | @JaiadityaS | `floor footprint write|stale|check` (`footprint.py`), coefficients and sources in `.floor/impact/footprint.yml`, `floor manifest --footprint`, `floor meter start|stop|join` (`meter.py`, the R2 input; the machine and cgroup v2 scopes; tested on Linux). R2 is measured in the GitLab jobs (D-015): `.gitlab-ci.yml` meters each `.tools` job, and the judge job joins the meters. `ci.yml` runs `floor footprint stale`, and if-run plus `floor footprint check --expect` when manifests exist. R1 is done: `.floor/impact/sci-audio-minute.yml` and `.floor/evidence/footprint/sci.json` (0.00196 g CO2e per audio-minute). Open (R2): a GitLab run of the meter, then its `out/judge/meter.json` as `.floor/evidence/release/meter.json`; then the manifests and `sci.json` again. Design: `.agents/log/2026-10-16-jaiadityas-4.md` R2 done: pipeline 2960804030, `.floor/evidence/release/meter.json`, 0.36 g CO2e per release check (us-east1). The judge job passes `--footprint .floor/evidence/footprint/sci.json` (test: `test_judge_job_reads_the_committed_footprint`). Open: check the manifest footprint fields on GitLab after the next human sync |
| T-55 | Energy per audio-minute: native vs folk fix vs all-variants on the same hardware | F14.2, G7 | done | @JaiadityaS | `floor audio` (`energy.py`): the test audio. `floor energy` (`energy.measure`), tested on Linux with GNU time. `.github/workflows/energy.yml`: one runner builds native, folk fix and all-variants (`--target whisper-cli`), makes the x64-only copy, and runs `floor energy` from an empty folder. Evidence: run 39033747472 in `.floor/evidence/energy/`. all-variants against folk-fix: -0.4% CPU time, inside the 5.1% spread of the runs; x64-only: 15.1× (STATE.md "Facts learned"). Design: `.agents/log/2026-10-16-jaiadityas-4.md` |
| T-56 | ΔM calculator: range and sensitivity table | F14.3, §13.3 | done | @JaiadityaS | `floor delta-m` (`delta_m.py`), `.floor/scenarios/TEMPLATE.yml`; `floor manifest --delta-m`. Every input needs a source. Sourced values for a demo scenario are still open |

## Communication, SHOULD and COULD

| ID | Task | PRD | Status | Owner | Notes |
|---|---|---|---|---|---|
| T-60 | Floor page (title: Rieux, D-013): backtest timeline, side-by-side runs, SCI, notices | F12.2 | doing | @JaiadityaS | `floor page --out site` (`page.py`): one static HTML file from `.floor/evidence/`. It has all the F12.2 sections: H-1, backtest, CPU proof, release, languages, energy per audio-minute (with the spread of the runs), SCI and notices. The language table says "not measured yet" until T-62. Open: the next human sync, then a look at the live page. The `pages` job publishes it from `main`: https://showcase-9a1941.gitlab.io/ (first deploy: pipeline 2958271425). Title and heading are "Rieux" from dev `page.py` (live after the next sync) |
| T-61 | Pinned issue summary | F12.3 | later | - | |
| T-62 | Language served / not-served table | F9 | later | - | |
| T-63 | Field triage flow | F11 | later | - | |
| T-64 | 20-issue spot check of the keyword counts | §3.2 | later | - | |

## Submission (Oct 24–26)

| ID | Task | PRD | Status | Owner | Notes |
|---|---|---|---|---|---|
| T-90 | Final README: problem, claims, stage table, how to run, sources | §16.2 | doing | @JaiadityaS | Product name Rieux (D-013). Draft done (D-017): `README.md` is a product file and the GitLab front page; whisper.cpp's README moves to `README.whisper.cpp.md` at the next sync. Open: update the stage table and the numbers before submission, and check the page on GitLab after the sync |
| T-91 | Video, under 3:00 | §16.1 | later | - | |
| T-92 | Devpost text | §16.2 | later | - | |
| T-99 | Delete `AGENTS.md` and `.agents/`; final hygiene check (`bash scripts/guard.sh tree`) | - | later | - | Last commit before submission |
