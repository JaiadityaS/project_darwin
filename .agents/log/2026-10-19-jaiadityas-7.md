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
