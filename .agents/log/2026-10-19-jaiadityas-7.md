# 2026-10-19 @JaiadityaS session 7
- Tasks: T-90 (doing).
- Done:
  - `README.md`: the Rieux README (PRD §16.2). The problem (#3510, #3814, the cause in the build), what we measured (H-1, the folk fix under QEMU, the cost of inclusion, the other floors, SCI), the claims N1–N4 with prior art and "what we do not claim", the loop, the DevSecOps stage table with a status column, how to run, the layout and the sources. Each number comes from STATE.md "Facts learned" or a file in `.floor/evidence/`.
  - D-017: `README.md` is a product file (`scripts/assemble-gitlab.sh`). The first sync after this moves whisper.cpp's README to `README.whisper.cpp.md` (one `git mv`, same folder).
- Verified:
  - A dry run of `assemble-gitlab.sh` in a scratch copy (a clone of this repo and a bare copy of `work/gitlab` as the remote): the sync commit has `README.md` (Rieux) and `README.whisper.cpp.md` (whisper.cpp). A second run gives the same result. Nothing was pushed.
  - `python -m floor probe -h` and `python -m floor image -h` match the README commands. The image tags use the full 40-character hash.
  - `python -m pytest .floor/tests -q -p no:cacheprovider`: 193 passed, 11 skipped. `bash scripts/guard.sh tree`: no problems.
- Open:
  - The README is not on GitLab yet. It goes with the next human sync.
  - Git shows the move as a new file plus a changed `README.md`, not as a rename, because the new README is all new text.
  - The GitHub runs are in the private dev repo, so a judge cannot open them. The evidence files have the run IDs.
- Gotchas:
  - On Windows, a clone of the GitLab project needs `core.longpaths=true` (an Android example path is too long).


## After the human sync (GitLab `main` `64329927`, pipeline 2960804030)
- Verified on GitLab (public API and job logs, no token): see STATE.md "Facts learned". The judge failed as planned. The `notice-draft` job printed the expected "no draft" line. The manifest has the AC-F7 and AC-F8 fields. The README is the front page.
- Done (T-54, R2): `out/judge/meter.json` of the pipeline is now `.floor/evidence/release/meter.json`. `floor footprint write` made `.floor/impact/sci-release-check.yml`. if-run (`npx -p @grnsft/if@1.1.1`, Node 22.17) on both manifests, then `floor footprint check --out .floor/evidence/footprint/sci.json`: "6 result(s): every output matches the formulas". `floor footprint stale`: up to date. SCI per release check: 0.36 g CO2e (us-east1). The README footprint paragraph has it.
- Verified: 193 passed, 11 skipped. `floor page` shows the release-check row.
- Open: `floor manifest --footprint` in the judge job (the manifest footprint fields are still null).
- Gotcha: the GitLab job logs are public at `<project>/-/jobs/<id>/raw`, and the artifacts at `/api/v4/projects/87296266/jobs/<id>/artifacts`.
- Branch: main

## T-54: the SCI values in the judge's manifest
- Done: the judge job in `.gitlab-ci.yml` adds `--footprint .floor/evidence/footprint/sci.json` when the file exists. The file is committed, so GitLab has it.
- Test: `test_judge_job_reads_the_committed_footprint` (the CI script has the flag; a manifest made with the committed file has both SCI values above 0).
- Verified: 194 passed, 11 skipped. The guard passed.
- Open: `.gitlab-ci.yml` goes to GitLab only with a human sync. Then check the manifest footprint fields in the judge job's artifacts.

## T-41: the fallback CI job (D-018)
- Fact: CI cannot push to the branch. A `CI_JOB_TOKEN` push needs a project setting that only a Maintainer can turn on, and such a push starts no pipeline (GitLab docs, `ci/jobs/ci_job_token`).
- Done:
  - `fallback.patch` (`fallback.py`): the changes of `apply` as a patch for `git apply` (new file mode for the override, the "No newline" marker). It changes no file.
  - `floor fallback --judge FILE --policy FILE --patch FILE` (`cli.py`): with `--judge`, it acts only when the decision is `fail` and the policy has `repair.fallback: canned_inclusive_config`. When the branch has the canned config, it writes no patch.
  - The `fallback` job in `.gitlab-ci.yml`: stage `repair`, `needs: [judge]`, `when: on_failure`, artifact `out/fallback/` ("Canned config patch").
  - D-018 in DECISIONS.md.
- Tests: `test_patch_changes_nothing_and_git_applies_it` (git applies the patch, and the result is byte-equal to `apply`), `test_cli_patch_only_after_a_failed_gate`, `test_fallback_ci_job`.
- Verified: 197 passed, 11 skipped.
- Open: the first GitLab run after the next human sync. Then T-05 with an MR that commits the patch.
- Gotchas:
  - The user's home folder is a git repo. In a temp folder below it, `git apply` skips the paths outside the folder and still exits 0. The test runs `git init` first.
  - Git on this PC has `core.autocrlf=true`, so `git apply` writes CRLF. The test uses `-c core.autocrlf=false`.
  - Heredocs in this shell halve backslashes, also in quoted heredocs. Write code with backslashes through the Write or Edit tool.

## T-52: the upload page (D-019)
- Fact: whisper-server takes `duration` and other parameters from the request form and has no rate limit, so it cannot be the public port.
- Done:
  - `.floor/floor/gateway.py`: GET `/` (the page), POST `/transcribe` (a WAV body), GET `/healthz`. `python3 gateway.py --serve` starts whisper-server on 127.0.0.1:8081 (`-d 30000`), then the gateway on `$PORT`. It exits when whisper-server exits.
  - `.floor/floor/gateway.html`: record (stops at 30 s) or choose a file; the browser makes 16 kHz mono WAV with `OfflineAudioContext`.
  - `deploy/service.Dockerfile`: `ARG IMAGE` (the held image digest), python3, the two gateway files.
  - `.floor/pyproject.toml`: `gateway.html` is package data.
- Tests: `test_gateway.py` (WAV checks, the rate limiter, the client address, a fake whisper-server: fixed form fields, the limits, a 502, the image recipe, standard library only).
- Verified: 206 passed, 11 skipped. The guard passed. In the browser pane with a fake whisper-server: a 2 s 44.1 kHz stereo WAV became 16 kHz mono and got the text; a 35 s file was refused in the page; a non-WAV body got 400. Phone width (375 px) is good.
- Open: Docker is not installed on this PC, so the service image is not built yet. T-51 builds it from the held image and runs the smoke test. Max instances go in `infra/` (T-50).
- Then: the `service` job in `.gitlab-ci.yml` (stage `floors`, `needs: [build]`, Docker-in-Docker like the build job). It builds `deploy/service.Dockerfile` with `IMAGE=$IMAGE_REF`, runs it, waits for `/healthz`, posts `samples/jfk.wav` (16 kHz mono, 11 s) and greps `$EXPECT`, then posts 500,000 zero bytes and expects 400. It pushes nothing. Test: `test_service_ci_job`.
- Fix: a 413 with an unread body made the client see a reset connection (WinError 10053, a flaky test). Now the gateway reads and drops a refused body up to 2 MB (`DRAIN_BYTES`), then sends the 413. A larger body is not read.
- Verified: 207 passed, 11 skipped; `test_gateway.py` 5 runs in a row passed.
- Open: the first GitLab run of the `service` job (after the next human sync).

## T-90: the stage table
- The Create row has the `fallback` and `notice-draft` jobs. The Configure row has the service image and the `service` job. Both say "new" until a GitLab pipeline runs them.

## GitLab pipeline 2960896128 (GitLab `main` `04bddeb5` = dev `43b907a`)
- judge: failed as planned (Pareto raised, decision fail: the upstream image floor is v4).
- fallback (T-41): passed. It wrote `out/fallback/fallback.patch` (canned config `-DGGML_NATIVE=OFF -DGGML_BACKEND_DL=ON -DGGML_CPU_ALL_VARIANTS=ON -DBUILD_SHARED_LIBS=ON`). AC for the patch artifact is met.
- notice-draft: passed with no draft (the canned config is not on the branch yet), as planned.
- service (T-52): the image built and `/healthz` passed, but the jfk.wav POST got HTTP 400.
  - Cause: BusyBox wget sets Content-Length with strlen() for its post-file option, so it cut the WAV at the first zero byte. Locally `wav_seconds(jfk.wav)` = 11.0.
  - Fix: the job installs curl and posts with `--data-binary`; it checks the HTTP code (200, then 400 for a non-WAV body) and prints the service log on a failure. Test: `test_service_ci_job` refuses the post-file option.
- Open: the next GitLab run of `service`.
- Verified: pipeline 2960909623 (GitLab `main` `3c576ef4` = dev `be54960`), `service` job 17268972447 passed: jfk.wav gave "And so my fellow Americans, ask not what your country can do for you, ask what you can do for your country." (11.0 s audio, 3.31 s on the server); a non-WAV body got 400.
- T-54 done: the judge manifest of pipeline 2960896128 has both SCI fields (0.00196 g CO2e per audio-minute, 0.362 g per release check).

## T-03: the trigger chain (D-020)
- Done: `.floor/flows/trigger-probe.yml` (no tools, no clone; it copies fields of the pipeline event), code-owned (`paths.CODE_OWNED`, `.gitlab/CODEOWNERS`), test `test_flows.py`. AI Catalog item 1018639 (private), trigger "Pipeline events: Failed".
- Run 1: pipeline 2960926378 (UI "New pipeline") failed at the judge, and session 9657365 started ("Triggered by @jaiadityasinghr"). But it ran the example flow of the create form: the form had kept the example YAML below ours, and YAML keeps the last value of a repeated key. The example posted nothing.
- Fix: the stored definition now equals the file (v1.1.0). The catalog schema refused `max_cycles`, so the file has no `max_cycles` now, and the test checks it.
- Run 2: pipeline 2960962126 failed at the judge; session 9657595 (CI job 17269341490) replied `pipeline_id: 2960962126 status: failed ref: main sha: 3c576ef4… source: web user: jaiadityasinghr judge_job: failed floor_raised: yes`.
- Verified: 209 passed, 11 skipped.
- Open: T-40 (the floor-repair flow), then T-05. A tag push is not tested yet (T-42).
- Gotchas: read the stored definition back with GraphQL after every save. The editor indents typed YAML again. The default conditions of the "Enable flow" dialog (Mention, Assign, Assign reviewer) must be removed.

## T-40: the floor-repair flow (D-021, D-022)
- Done: `.floor/flows/floor-repair.yml` (a `gate` agent with no tools, then a `repair` agent with five tools), code-owned, test `test_flows.py`. AI Catalog item 1018643 (private), trigger "Pipeline events: Failed". The trigger of the probe flow (1018639) is off now.
- Catalog v2: the job log tool is `get_job_logs` (the first save had a wrong name; the catalog does not check tool names).
- Run: the sync push pipeline 2960990129 failed at the judge. Session 9657869 ran `gate`, then `repair`, and opened MR !1 (`floor-fix/2960990129`, commit `a8aca4ca`) in about 2 min. The first commit call sent "update" for a new file and failed; the second sent "create". Catalog v3: the prompt now names the action.
- MR pipeline 2961002610 failed its gate, because of the harness:
  - `memory` and `offline`: exit -11 after `GGML_ASSERT(device)`. The canned config loads the CPU backends through `/proc/self/exe`, and `chroot` gives no `/proc`. Fix: both jobs mount `/proc` in the image.
  - `probe`: EPYC-Milan stopped at 1800 s with `-t 4` on 2 vCPUs. Fix: `-t 2` and 2400 s.
- Verified: 212 passed, 11 skipped (new tests `test_chroot_jobs_mount_proc`, `test_probe_ci_job`).
- Open: the gate of the next fix MR (on the fixed CI); T-05 needs "Pipelines must succeed" (a user decision).

## T-34: the attestation (D-023)
- Done: `floor attest` (`attest.py`: predicate, identity, check) and the `attest` job of `.gitlab-ci.yml` (after a passed judge; keyless with the GitLab ID token; cosign v2.6.5 with a pinned SHA-256). Test `test_attest.py`.
- Verified: 217 passed, 11 skipped. `test_gateway.py::test_limits` failed once with a Windows socket abort and then passed 3 times; it is not related.
- Open: the first run on GitLab needs a passed judge (the next fix MR).

## T-42: the release job (D-024)
- Done: `floor release` (`release.py`) and the `release` job of `.gitlab-ci.yml`. The workflow skips `-floor.N` tag pipelines. The judge and attest jobs write `job-url.txt` for the release links.
- Verified: 223 passed, 11 skipped.
- Open: the first real run (a human tag push, then a merged fix MR); check the tag permission of the job token then.

## T-46: Herald, the template (D-025)
- Done: `floor herald` (`herald.py`) and the `herald` job; `floor release --herald` puts the section first in the notes. Test `test_herald.py`.
- Checked on the real manifest of pipeline 2961083963 (judge job 17270054359): the text matches the values.
- Verified: 227 passed, 11 skipped.
- Gotcha: the Bash heredoc turns `\n` into a newline, even with a quoted delimiter. Use the Edit tool for text with backslashes.

## T-04: the Duo CLI in CI (blocked)
- Finding: headless `duo run` needs an access token in `GITLAB_TOKEN` or `GITLAB_OAUTH_TOKEN`. The job token does not work. D-010 forbids a personal token of a person, so only a service-account token fits, and a group owner makes it. Herald stays a template (D-025). Recorded in D-025 and STATE "Needs a human".
- Fact: the merge method is `merge`, and the protected-tags API gives 403 to the Developer role (D-024).

## T-35: the notice approvals (D-026)
- Done: `floor ratchet --approvals URL --default-branch BRANCH` (`ratchet.approval`, `ratchet.approvers`, `ratchet.code_owners`); the check job passes them. The approvals API of this public project needs no token.
- Verified: 231 passed, 11 skipped.
- Open: a real notice MR with a human approval.

## T-90: README stage table
- Create now says "Runs": the flow opened fix MRs !2 and !3.

## T-52: the service job records its CPU
- Main pipeline 2961114166 (upstream image, built on a Xeon Platinum 8581C, x86-64-v4): the `service` job failed. whisper-server stopped while it loaded the model; the log has no exit code. MR pipeline 2961110649 (canned image): `service` passed.
- Done: the job writes `out/service/cpu.txt` (`facts.sh --cpu`) and, on a failed start, the container exit state and `out/service/service.log`. The gateway logs how whisper-server ended (`gateway.exit_text`, SIGILL named).
- Verified: 232 passed, 11 skipped.
- Result: main pipeline 2961183840 (the same upstream image, `build` on an 8581C, x86-64-v4) passed `service` on an 8581C (`out/service/cpu.txt`, job 17270664524). The failure did not come again, so its cause stays not proven.
- Open: if `service` fails again, read `cpu.txt` and the exit state; a SIGILL on a runner older than the build runner is H-1 evidence.

## Gate results of the fix MRs (D-022, D-023, D-027)
- MR !2 (pipeline 2961093570): memory, offline, service, qemu64, Nehalem, SandyBridge passed. EPYC-Milan timed out at 2400 s, so the judge said cpu inconclusive and failed. The probe had dropped the output of the timed-out run.
- MR !3 (pipeline 2961110649): gate pass, every floor held. Attest job 17270217868 signed and verified. Probe job times 259, 220, 541 and 2175 s. T-34 and T-40 done.
- Checked: a merged fix MR stays after the next sync. `assemble-gitlab.sh` starts from GitLab main and overlays only the product paths; `.devops/` is upstream content, and `.floor/overrides` and `deploy` are agent paths that a sync keeps.
- MR !4 (pipeline 2961134355, still the old probe): EPYC-Milan timed out at 2400 s (job 2449 s); SandyBridge 632 s, Nehalem 246 s, qemu64 294 s. The judge failed as cpu inconclusive, so attest and herald were skipped.
- MR !5 (pipeline 2961210282, fix of main 2961183840, the first gate with D-027): gate pass. Probe runs (job times): qemu64 136 s (179), Nehalem 108 s (155), SandyBridge 303 s (439), EPYC-Milan 1413 s (1457); each run had the reference text, the expected variant and correct controls. Attest job 17270780570 passed. Herald job 17270780571 passed (the first run); `who.md` agrees with the signed manifest (98.4 MB, 0 attempts, SCI 0.00196). Gotcha: many anonymous API reads in a short time gave "Rate limit exceeded"; a 10 min pause fixed it.
- Done (D-027): the probe uses `-ac 768`, a 2700 s run limit and a 55 min job limit; a timed-out run keeps its output and time (`qemu.run`, `seconds`).
- Verified: 233 passed, 11 skipped.
- README: the Verify and Secure rows now cite pipeline 2961110649.

## T-53: GET /floor (D-028)
- Done: `gateway.py` relays the whisper-server log unchanged and keeps the ggml CPU variant of the backend-loader line; `host_cpu()` reads the level from `/proc/cpuinfo` (the rule of `facts.sh`); `GET /floor` reports both; the upload page shows them; the `service` job keeps `out/service/floor.json` and fails without a host level.
- Tests: `test_host_cpu`, `test_relay_keeps_the_log_and_the_variant`, `test_floor_endpoint`, `test_page_shows_the_server_cpu`, and `test_service_ci_job`.
- Verified: 237 passed, 11 skipped.
- Result 1: main pipeline 2961779904 (sync f5f6650d), service job 17274060434: `host_level` x86-64-v4 (an 8581C, the same as `cpu.txt`), `ggml_cpu_variant` null with the note. Right for the static backend of the upstream image.
- Open: the first GitLab run. Main has the upstream image (static backend), so its `floor.json` should have no variant and the note. The next fix MR has the canned image (`GGML_BACKEND_DL=ON`), so its `floor.json` should name a variant. Check both; do not assume.
- Also checked: the live Rieux page (https://showcase-9a1941.gitlab.io/) has the title Rieux and all the F12.2 sections, so the open item of T-60 is done.
- T-14: already done in fact: `judge.py` writes `dispatch` into the signed manifest (MR !5: EPYC-Milan haswell, Nehalem sse42, SandyBridge sandybridge, qemu64 x64). Marked done.

## T-23: the backtest footprint (D-029)
- Done: `backtest.download_sizes` (config blob and `/app` layer from the registry manifests), `backtest.footprint`, `floor backtest-footprint`; the job files of the two sweep runs; `.floor/evidence/backtest/footprint-2026-10-15.json`; a line under the backtest on the Rieux page.
- Result: 121 images, 27,470 MB (CPU images about 153 MB each, CUDA images about 302 MB each), 18.4 runner-minutes. Spot check: `main-e6234cd4` app layer 148,057,889 bytes; `main-0c7be696` 158,927,554 bytes.
- Tests: `test_footprint_adds_the_downloaded_blobs_and_the_job_times`, `test_download_sizes_reads_the_manifest_and_the_config`, and a line in `test_page_from_repo_evidence`.
- Verified: 239 passed, 11 skipped.
