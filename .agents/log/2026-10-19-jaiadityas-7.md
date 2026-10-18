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
