# TASKS: the board

Claim before you code: set `Owner` to your handle and `Status` to `doing`, then push the claim.
One owner per task. PRD references point to `docs/PRD.md`.

Status values: `ready` · `doing` · `done` · `blocked` (waits on another task) · `human` (needs a person: access, accounts, money, a decision) · `later` (SHOULD/COULD work; start only after the MUST work of its gate).

## G-0 Access and trigger chain (due Oct 14)

| ID | Task | PRD | Status | Owner | Notes |
|---|---|---|---|---|---|
| T-01 | Confirm GitLab hackathon group access and tier (Premium or Ultimate) and the Duo credit pool for service-account flows | §9.1, §19 | human | - | |
| T-02 | `scripts/assemble-gitlab.sh`: clone whisper.cpp at a pinned commit, overlay the product files, push to the GitLab project | §0, D-001 | ready | - | Record the pinned commit in DECISIONS |
| T-03 | Trigger-chain test: a human tag push fails the gate; the pipeline-failed trigger starts a flow; record who counts as the actor | F4.1, §9.1 | blocked | - | Needs T-01, T-02 |
| T-04 | Duo CLI runs headless in a CI job (Herald, and the floor-repair fallback) | F4.1, F12.1 | blocked | - | Needs T-01 |
| T-05 | Merge-bot project token merges a non-code-owned MR, and its tag starts a pipeline | F4.4 | blocked | - | Needs T-02 |
| T-06 | Cloud Run hello-world with Workload Identity Federation from GitLab CI | F13.1 | human | - | GCP project and billing first |

## G-1 CPU proof (due Oct 15)

| ID | Task | PRD | Status | Owner | Notes |
|---|---|---|---|---|---|
| T-10 | Static scanner: ELF regions, iced-x86 decode, level map, allowlist, JSON report, CLI | F2.1, F2.2 | done | @JaiadityaS | `.floor/floor/isa/`, `python -m floor scan`. Checked on synthetic ELF files only; T-12 and T-15 give real binaries |
| T-11 | Scanner unit tests: synthetic ELF files and instruction encodings | F2.2 | done | @JaiadityaS | `.floor/tests/test_isa.py` (44 tests) |
| T-12 | Linux builds of whisper.cpp: native, folk fix (`GGML_NATIVE=OFF`), all-variants; scan each; check AC-F2 | AC-F2 | doing | @JaiadityaS | `.github/workflows/cpu-proof.yml` (build + scan) |
| T-13 | QEMU user-mode harness with negative and positive controls on qemu64, Nehalem, SandyBridge, EPYC-Milan | F3.1, F3.2 | doing | @JaiadityaS | `floor probe` (`qemu.py`, `controls.py`) in `cpu-proof.yml`. Linux only. Also proves that loading every variant at start-up is safe (see log 2026-10-14-jaiadityas-1) |
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
| T-31 | Ratchet check: a looser policy needs a merged notice | F1.2 | ready | - | |
| T-32 | Judge: held / lowered / raised / inconclusive; Pareto rule; unit tests | F5.1, F5.2 | done | @JaiadityaS | `floor judge` (`judge.py`). Memory and connectivity inputs are JSON stubs until T-44 and the offline job give real files |
| T-33 | Manifest writer + diff against the previous release | F5.3, §11.1 | done | @JaiadityaS | `floor manifest`, `floor diff` (`manifest.py`). In-toto Statement only; signing is T-34 (F5.4). Footprint values stay null until measured |
| T-34 | `cosign attest` (keyless, GitLab OIDC) and `verify-attestation` | F5.4 | blocked | - | Needs GitLab |
| T-35 | Leave-Behind Notice template and MR check (agents cannot approve) | F6, §11.2 | ready | - | |
| T-36 | CODEOWNERS, protected branch and tag settings, path-allowlist job | F1.2, §10.1 | ready | - | |

## Release loop (Oct 19–22)

| ID | Task | PRD | Status | Owner | Notes |
|---|---|---|---|---|---|
| T-40 | floor-repair flow (AI Catalog, private): exit unless raised → diagnose → fix MR | F4.1, F4.2 | blocked | - | Needs T-03 |
| T-41 | Fallback script applies the canned inclusive config; the gate re-verifies | F4.3 | ready | - | |
| T-42 | Merge-bot merge job and `-floor.N` tag job | F4.4 | blocked | - | Needs T-05 |
| T-43 | Draft notice when the fallback also fails | F4.5 | ready | - | |
| T-44 | Memory floor: cgroup limits 512–4096 MB, peak RSS | F7 | ready | - | Linux |
| T-45 | Connectivity tripwire: `--network none` + syscall trace; download sizes | F8 | ready | - | Linux |
| T-46 | Herald CI job (Duo CLI) with a deterministic template fallback | F12.1 | blocked | - | Needs T-04 |
| T-47 | `.gitlab-ci.yml`: build → static gate → QEMU → judge → attest → herald → release → deploy | §7.1 | ready | - | |

## Deploy and sustainability

| ID | Task | PRD | Status | Owner | Notes |
|---|---|---|---|---|---|
| T-50 | OpenTofu: Cloud Run in a low-CO₂ region + WIF | F13.1 | blocked | - | Needs T-06 |
| T-51 | Staging → smoke test → production; rollback | F13.2 | blocked | - | Needs T-50 |
| T-52 | Upload page: 30 s cap, rate limit, max instances, no storage | F13.3 | ready | - | |
| T-53 | `/floor` endpoint: host level and loaded variant | F13.4 | later | - | |
| T-54 | SCI per audio-minute and per release check (Impact Framework manifests) | F14.1 | ready | - | |
| T-55 | Energy per audio-minute: native vs folk fix vs all-variants on the same hardware | F14.2, G7 | ready | - | |
| T-56 | ΔM calculator: range and sensitivity table | F14.3, §13.3 | ready | - | |

## Communication, SHOULD and COULD

| ID | Task | PRD | Status | Owner | Notes |
|---|---|---|---|---|---|
| T-60 | Floor page: backtest timeline, side-by-side runs, SCI, notices | F12.2 | ready | - | GitLab Pages |
| T-61 | Pinned issue summary | F12.3 | later | - | |
| T-62 | Language served / not-served table | F9 | later | - | |
| T-63 | Field triage flow | F11 | later | - | |
| T-64 | 20-issue spot check of the keyword counts | §3.2 | later | - | |

## Submission (Oct 24–26)

| ID | Task | PRD | Status | Owner | Notes |
|---|---|---|---|---|---|
| T-90 | Final README: problem, claims, stage table, how to run, sources | §16.2 | ready | - | |
| T-91 | Video, under 3:00 | §16.1 | later | - | |
| T-92 | Devpost text | §16.2 | later | - | |
| T-99 | Delete `AGENTS.md` and `.agents/`; final hygiene check (`bash scripts/guard.sh tree`) | - | later | - | Last commit before submission |
