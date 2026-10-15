# STATE: the baton

Last update: 2026-10-15 · @JaiadityaS · session 2

## Where we are

- PRD v3.1 is the go decision (`docs/PRD.md`). Today is build day 2 (PRD §17.2).
- Done: repo, team-sync system, hooks, CI for tests and hygiene.
- Done: the static scanner (T-10, T-11) and the ghcr.io client (T-20). `python -m floor scan <path>` and `python -m floor image <ref>` work.
- Done: T-15 static part (the first H-1 signal) and T-24 for one commit. See "Facts learned".
- Done in session 2: the #3814 follow-up (H-1 signal 2), function symbols in scan evidence, the T-16 rule, the sampler and timeline (`floor sample`, `floor timeline`) and the sweep workflow (`sweep.yml`).

## Gates (PRD §17.1)

| Gate | Due | Status |
|---|---|---|
| G-0 Access and trigger chain | Oct 14 | waits on humans (T-01, T-06) |
| G-1 CPU proof | Oct 15 | scanner done; T-15 static part done; T-16 rule pushed, confirm with run 38700683985; T-12 and T-13 not started |
| G-2 Backtest and H-1 | Oct 16 | client done (T-20); sampler and sweep done (T-21); first sweep is run 38700707825 |
| G-3 Gate integrity | Oct 18 | not started |
| G-4 Release loop | Oct 22 | not started |

## Next agent: start here

1. **T-16 confirm.** Open run 38700683985 (`backtest.yml` on `main-47b9eb37…`). Expected: whisper-cli, whisper-server, test-vad, test-vad-full and whisper-vad-speech-segments are now v1, with `LZCNT: 24` under `allowlisted`, and the floor is set only by `libggml-cpu.so` (v3). If yes, set T-16 to `done`. If not, read the `functions` field of the LZCNT evidence in the JSON report.
2. **T-21 result.** Open run 38700707825 (`sweep.yml`, 30 spread images plus every image within 14 days of #3510 and #3814). Download the `timeline-<run_id>` artifact. Record the number of v3 and v4 images and the dates of each flip in "Facts learned". If a batch failed, scan its refs again with `backtest.yml`. Then set T-21 to `done`.
3. **Sweep for main-cuda too.** The #3814 evidence is in the CUDA images. Add a `--prefix` option to `floor sample` (default `main-`, so `main-cuda-` also works; `backtest.MAIN_TAG_RE` is the place) and run the sweep on `main-cuda-`.
4. **T-22: H-1 analysis.** Clone whisper.cpp (`git clone --filter=blob:none`) and compare each flip in the timeline with `git log` of `.devops/` and `ggml/src/ggml-cpu/`. If the code and the Dockerfile do not change at a flip, the build machine set the floor (H-1).
5. T-12 and T-13 need Linux: write a GitHub Actions job like `backtest.yml`. T-12 builds whisper.cpp three ways (native, `GGML_NATIVE=OFF`, all-variants) and scans each. T-13 runs the builds under `qemu-x86_64 -cpu qemu64|Nehalem|SandyBridge|EPYC-Milan`.
6. Pure Python work that needs no access: T-30 (policy file and schema), T-32 (judge), T-33 (manifest writer and diff).

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
- **#3814 follow-up (run 38543908892), H-1 signal 2.** `main-cuda` images from adjacent commits, same Dockerfile:
  - `3e9b7d0f…` (built 2026-05-13T11:33Z): v3.
  - `46ca43d6…` (built 2026-05-14T21:40Z): **v4 + AVX512_VNNI**.
  - `968eebe7…` (built 2026-05-15T14:39Z): **v4 + AVX512_BF16, AVX512_VNNI**.
  - `6227a0ef…` (built 2026-05-18T10:01Z): v3. `47b9eb37…` (2026-05-18T10:19Z): v3 (T-24).
  - The floor goes v3 → v4 → v4 → v3 in five days. A Zen 3 CPU (#3814) has no AVX-512, so the two v4 images crash on it. Check in T-22 that `.devops/main-cuda.Dockerfile` and the ggml CPU code did not change between these commits.
- **T-16 cause (run 38544501988).** All 24 LZCNT instructions in whisper-cli and the four other audio tools are in miniaudio's embedded FLAC decoder. The symbols are mangled C++ names, for example `_ZL29ma_dr_flac__decode_flac_frameP10ma_dr_flac`. The other functions are `ma_dr_flac__seek_flac_frame`, `ma_dr_flac__read_and_seek_residual` and `ma_dr_flac__decode_samples_with_residual`. `allowlist.GUARDED` now allows LZCNT only in functions whose plain name matches `^(?:ma_)?dr_?flac_`. `allowlist.base_name` takes the plain name from `_ZL<len><name>`.
- ghcr.io `ggml-org/whisper.cpp` has 1174 tags (2026-10-14). Tags use the full commit hash: `main-<40 hex>`, `main-cuda-<40 hex>`, `main-intel-<40 hex>`.
- A home link pulls ghcr.io blobs at about 108 KB/s. Pull images in GitHub Actions.

## Environment notes

- Windows (Git Bash, Python 3.13 venv) is enough for the scanner, the tests and small pulls.
- Builds, QEMU, memory and offline tests need Linux: WSL Ubuntu, a Linux machine, or a CI job.
- Private repo: GitHub Actions has 2000 free minutes per month. A backtest job of 2 images takes a few minutes.
