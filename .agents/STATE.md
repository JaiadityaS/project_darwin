# STATE: the baton

Last update: 2026-10-14 09:20 UTC · @JaiadityaS · session 1 (bootstrap)

## Where we are

- PRD v3.1 is the go decision (`docs/PRD.md`). Today is build day 2 (PRD §17.2).
- Done: repo, team-sync system, hooks, CI for tests and hygiene.
- Done: the static scanner (T-10, T-11) and the ghcr.io client (T-20). `python -m floor scan <path>` and `python -m floor image <ref>` work.
- Done: T-15 static part (the first H-1 signal) and T-24 for one commit. See "Facts learned".

## Gates (PRD §17.1)

| Gate | Due | Status |
|---|---|---|
| G-0 Access and trigger chain | Oct 14 | waits on humans (T-01, T-06) |
| G-1 CPU proof | Oct 15 | scanner done; T-15 static part done; T-16 false positive open; T-12 and T-13 not started |
| G-2 Backtest and H-1 | Oct 16 | client done (T-20); sampler (T-21) not started |
| G-3 Gate integrity | Oct 18 | not started |
| G-4 Release loop | Oct 22 | not started |

## Next agent: start here

1. #3814 follow-up (part of T-21): run `backtest.yml` on `main-cuda-<sha>` for the other commits of 2026-05-13 to 2026-05-18 (6227a0ef73, 968eebe772, 46ca43d639, 3e9b7d0fef). Get the full hashes with `gh api "repos/ggml-org/whisper.cpp/commits?since=2026-05-01T00:00:00Z&until=2026-05-18T23:59:59Z"`. Look for a v4 build: the reporter's Zen 3 CPU runs v3 code.
2. T-16: fix the LZCNT false positive. Pull one image locally once (`python -m floor image <ref> --verbose`, about 23 minutes on a home link), map the LZCNT addresses to symbols (`.symtab`), then write the rule and its tests.
3. T-21: sampler that picks ≥ 30 `main-<sha>` tags across time (use the config `created` date), plus every image within two weeks of #3510 (opened 2025-11-10) and #3814 (2026-05-18). Run batches of about 10 refs per job.
4. T-12 and T-13 need Linux (WSL Ubuntu, or a GitHub Actions job like `backtest.yml`).

## Needs a human (agents cannot do these)

- [ ] T-01: confirm GitLab hackathon group access, the tier (Premium or Ultimate) and the Duo credit pool.
- [ ] T-06: Google Cloud project with billing and a budget alert, for Cloud Run and WIF.
- [ ] Add teammates as collaborators on GitHub `JaiadityaS/project_darwin`.

## Facts learned (measured)

- iced-x86 reports TZCNT as BMI1 and XGETBV as XSAVE (both level 3). Both are on the allowlist, so they do not raise a floor.
- iced-x86 reports ENDBR64/ENDBR32 as CET_IBT and RDSSPD/RDSSPQ as CET_SS. These are extras, and they are on the allowlist.
- **T-15 (run 38537736704), first H-1 signal.** Both images come from the same `main.Dockerfile` (GGML_NATIVE default ON):
  - `main-a1867e0…` (built 2025-11-09T21:41Z, crashes in #3510): floor **x86-64-v4 + AVX512_VNNI**. `app/build/ggml/src/libggml-cpu.so` has EVEX code (VPSHUFD ×560, VPMADDUBSW ×384, VMOVDQA32 ×379). A machine with AVX-512 and VNNI built it.
  - `main-c62adfbd…` (built 2025-10-28T20:48Z, works): floor **x86-64-v3**. `libggml-cpu.so` is AVX2 code.
  - Both: 19 ELF files below `app/` (13 core, 6 CMake build tools); the `/app` layer is about 152 MB; no OCI revision label.
- **False positive (T-16).** whisper-cli, whisper-server, test-vad, test-vad-full and vad-speech-segments show v3 only because of LZCNT ×24. bench, main, quantize and libggml-base are v1. The LZCNT is probably the CPUID-guarded path of the FLAC decoder in miniaudio. It does not change T-15, but it breaks AC-F2 for the all-variants build until T-16 is fixed.
- **T-24 (run 38538051321).** Commit 47b9eb37 (2026-05-18): `main-<sha>` and `main-cuda-<sha>` both have floor x86-64-v3 and the same `libggml-cpu.so` profile (VMOVSS x1508). This pair does not reproduce #3814, because a Zen 3 CPU runs v3 code. The reporter's `main-cuda` image probably came from another commit, built on an AVX-512 runner. The CUDA image has no CMakeFiles probe binaries. Its `/app` layer is about 316 MB.
- ghcr.io `ggml-org/whisper.cpp` has 1174 tags (2026-10-14). Tags use the full commit hash: `main-<40 hex>`, `main-cuda-<40 hex>`, `main-intel-<40 hex>`.
- A home link pulls ghcr.io blobs at about 108 KB/s. Pull images in GitHub Actions.

## Environment notes

- Windows (Git Bash, Python 3.13 venv) is enough for the scanner, the tests and small pulls.
- Builds, QEMU, memory and offline tests need Linux: WSL Ubuntu, a Linux machine, or a CI job.
- Private repo: GitHub Actions has 2000 free minutes per month. A backtest job of 2 images takes a few minutes.
