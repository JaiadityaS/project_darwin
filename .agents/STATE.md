# STATE: the baton

Last update: 2026-10-19 · @JaiadityaS · session 7 (after the GitLab sync)

## Where we are

- Product name: **Rieux** (D-013). Code names (`floor`, `.floor/`) do not change.
- PRD v3.1 is the go decision (`docs/PRD.md`). The plan for Oct 17–18 is G-3 (PRD §17.2).
- Done: repo, team-sync system, hooks, CI for tests and hygiene.
- Done: the static scanner (T-10, T-11) and the ghcr.io client (T-20). `python -m floor scan <path>` and `python -m floor image <ref>` work.
- Done: T-15 static part (the first H-1 signal) and T-24 for one commit. See "Facts learned".
- Done in session 2: the #3814 follow-up (H-1 signal 2), function symbols in scan evidence, the T-16 rule, the sampler and timeline (`floor sample`, `floor timeline`) and the sweep workflow (`sweep.yml`).
- Done in session 3: G-1 (T-12, T-13), the policy and its ratchet (T-30, T-31), the Judge (T-32), the manifest and diff (T-33), memory and offline floors (T-44, T-45). Partly done, the parts that need no GitLab: T-35 notices, T-36 CODEOWNERS and path allowlist, T-41 fallback script, T-60 Floor page.
- Done in session 4: T-56 (ΔM calculator) and the SCI part of T-54 (`floor footprint`, the Impact Framework manifests, the coefficients in `.floor/impact/footprint.yml`). See `.agents/log/2026-10-16-jaiadityas-4.md`.
- Done in session 5: T-02 (first GitLab push: `main` is `36521198`), the name (D-013), and T-47 step 1 (`.gitlab-ci.yml`, `.gitlab/ci/`, D-014). The first GitLab pipeline (2958271425) failed as planned: the CPU floor of upstream's image is x86-64-v4. T-47 step 2 (the memory and offline jobs) ran in pipeline 2958309699 (see "Facts learned"). T-55 is done (energy run 39033747472). The R1 SCI files are committed (`.floor/impact/sci-audio-minute.yml`, `.floor/evidence/footprint/sci.json`). The Rieux page has the language, energy and SCI sections (T-60). See `.agents/log/2026-10-17-jaiadityas-5.md`.
- Done in session 6: T-43 (D-016). `floor notice-draft` writes the draft Leave-Behind Notice when the agent's fix and the canned config did not hold a floor, and the `notice-draft` job of `.gitlab-ci.yml` keeps it as an artifact. `floor fallback` now reads RUN instructions as shell words (the old regex broke 2 of the 7 upstream Dockerfiles). D-014 gap 1 is closed: the MR author counts too (`floor paths --actor auto`). See `.agents/log/2026-10-17-jaiadityas-6.md`.
- Done in session 7: the T-90 README draft (D-017). See `.agents/log/2026-10-19-jaiadityas-7.md`.
- CLI: `floor scan | image | sample | timeline | h1 | probe | policy | ratchet | judge | memory | offline | audio | energy | meter | notice | notice-draft | paths | fallback | page | manifest | diff | delta-m | footprint`. Run `python -m floor <command> -h`.

## Gates (PRD §17.1)

| Gate | Due | Status |
|---|---|---|
| G-0 Access and trigger chain | Oct 14 | waits on humans (T-01, T-06) |
| G-1 CPU proof | Oct 15 | **met**: cpu-proof run 38702242235 (AC-F2, AC-F3); see "Facts learned" |
| G-2 Backtest and H-1 | Oct 16 | client done (T-20); T-21 and T-22 done. H-1 is supported: 11 of 38 commits built as both `main` and `main-cuda` have different floors |
| G-3 Gate integrity | Oct 18 | code ready (`floor ratchet`, `floor paths`, `floor notice`, `.gitlab/CODEOWNERS`). The check job of `.gitlab-ci.yml` runs them (D-014), and the first pipeline ran (2958271425). Open: the proof MRs (T-05). Protected settings need a Maintainer (D-010) |
| G-4 Release loop | Oct 22 | started: `floor fallback` (T-41) and `floor notice-draft` with its CI job (T-43, D-016), both tested locally. T-41 CI job done (D-018; not on GitLab yet). Open: the flow (T-40), auto-merge (T-05), the release job (T-42) |

## Next agent: start here

1. Done on GitLab (pipeline 2960804030, GitLab `main` `64329927` = dev `a26571f`): AC-F7 and AC-F8 fields, the `notice-draft` job, the R2 meter and the README front page. See "Facts learned". Nothing in item 1 is open now.
2. T-41: the `fallback` job is done (D-018: CI cannot push, so the job keeps `out/fallback/fallback.patch`, and the flow or a human commits it). After the next human sync, the main pipeline fails at the judge, so check that the job writes the patch. Then T-05 (auto-merge test, D-010): an MR that commits the patch.
3. T-54: R2 is done (`.floor/evidence/release/meter.json`, `sci-release-check.yml`, `sci.json`). The judge job now passes `--footprint` (on GitHub main; not on GitLab yet). Open: after the next human sync, check that the GitLab manifest footprint fields are not null.
4. T-90 README: the draft is on GitLab (D-017). Update the stage table (status column) when a stage starts to run, and the numbers before submission.
5. T-52 (upload page) needs no GitLab.

## Needs a human (agents cannot do these)

- [ ] T-01: access is confirmed (D-010). Still open: the Duo credit pool.
- [ ] Sync to GitLab after each finished step. In PowerShell, from `project_darwin`: `& "C:\Program Files\Git\bin\bash.exe" scripts/assemble-gitlab.sh --push` (plain `bash` there is WSL). The push is in your name. The Showcase project is public, so a push is publishing: an agent pushes there only after a clear yes in that session. Never push this repo itself to GitLab.
- [ ] Add the GitLab usernames of teammates to `FLOOR_HUMANS` in `.gitlab-ci.yml`. Every other pipeline user counts as an agent (D-014).
- [ ] T-06: Google Cloud project with billing and a budget alert, for Cloud Run and WIF.
- [ ] Add teammates as collaborators on GitHub `JaiadityaS/project_darwin`.

## Facts learned (measured)

- **Energy run (energy.yml run 39033747472, whisper.cpp `0c7be696`, `base.en`).** One GitHub runner: AMD EPYC 7763 (Zen 3), 2 vCPUs, AVX2, no AVX-512. Each run transcribes 2.1833 audio-minutes (11 copies of the JFK sample). Median of 5 runs per build after 1 warm-up round. All four builds give the same transcript (one SHA-256).
  - CPU s per audio-minute: native 20.1, folk-fix 20.1, all-variants 20.0 (it loads haswell), x64-only 301.9 (it loads x64). Peak RSS: 386 MB, x64-only 409 MB.
  - The cost of inclusion: all-variants needs 0.4% less CPU time than folk-fix. The runs of one build differ by up to 5.1%, so the difference is noise. On an AVX2 machine, the inclusive build costs no measurable CPU time.
  - x64-only (the CPU code that ggml loads on an x86-64-v1 CPU) needs 15.1× the CPU time of all-variants. Wall time: 151.7 s per audio-minute on 2 vCPUs, slower than the audio.
  - SCI (Impact Framework 1.1.1, `.floor/evidence/footprint/sci.json`): all-variants in northamerica-northeast1 gives 0.00196 g CO2e per audio-minute (0.0266 Wh per audio-minute). Embodied carbon is 84.6% of it. The same work in us-central1 gives 0.0131 g, 6.7 times more.
- **First GitLab pipeline (2958271425, GitLab `main` `6d9de13d`, whisper.cpp `0c7be696`).** It failed as planned (D-014) in 310 s. Jobs: check 38 s, build 241 s, scan 41 s, probe 39–46 s each, judge 23 s (exit 1), pages 21 s. No job waited in a queue. The page is live at https://showcase-9a1941.gitlab.io/.
  - Runner `k8s.saas-linux-small-amd64`: Intel Xeon Platinum 8581C, x86-64-v4 with AVX-512 (also BF16, VNNI, FP16), 2 vCPUs, 8 GB RAM, 2 GB swap, kernel 5.15. Docker-in-Docker with TLS works.
  - Job container: root with all capabilities, no seccomp, no systemd. cgroup v2 in a private namespace (`0::/`), controllers include `memory`, `subtree_control` is empty, a child cgroup can be made. `unshare --net` works.
  - Static: floor x86-64-v4 + AVX512_BF16, AVX512_VNNI, AVX_VNNI, GFNI, set by `libggml-cpu.so.0.26.0` (`GGML_NATIVE=ON`). Every other ELF file in `/app` is v1.
  - QEMU: whisper-cli crashes with SIGILL on all four models, EPYC-Milan too. Every control passed. The relink made 202 absolute links relative.
  - So the same recipe gives v3 on the GitHub runner (G-1) and v4 on the GitLab runner: the build machine sets the floor.
  - Image `main@sha256:7e756879…` (full digest in the judge job's `floor-manifest.json`), base `ubuntu:22.04@sha256:0a988793…`.

- **Pipeline 2960804030 (GitLab `main` `64329927`, the sync of dev `a26571f`, 2026-10-18).** It failed as planned at the judge (cpu raised to x86-64-v4; memory and connectivity held). Build 208 s, memory 190 s.
  - The manifest has a job link per floor, `peak_rss_mb` (tiny 177, base 284, small 751), `download_mb` per model (tiny 81.9, base 152.1, small 491.8) and `download_bytes` per file (AC-F7, AC-F8 on GitLab).
  - `notice-draft` ran after the failed judge and printed "no draft: the canned inclusive config is not on this branch yet (…7 Dockerfiles, .floor/overrides/main.flags)". It passed. GitLab warns "out/notice/: no matching files" for the artifact, and that is correct when there is no draft.
  - R2 meter: 8 jobs (scan, 4 probes, memory, offline, judge), 243 s wall, 388 CPU s, 486 vCPU-s, 96.6 GB-s, peak 0.89 GB, all on an Intel Xeon Platinum 8581C. SCI per release check: 0.36 g CO2e in us-east1 (0.32 operational, 0.04 embodied). A lower bound (D-015).
  - The README shows as the project front page, and `README.whisper.cpp.md` is there (D-017).
  - `floor paths --actor auto` prints nothing on a push pipeline. It runs on the first MR pipeline.
- **Step 2 pipeline (2958309699, GitLab `main` `84388f56`).** It failed as planned in 405 s (cpu raised). Judge: memory held, connectivity held, policy met for both. `floor memory --cgroup` and chroot work on the runner.
  - memory (181 s): smallest passing limit tiny 512 MB (peak RSS 177), base 512 (284), small 768 (750). The GitHub run gave 179, 290 and 758.
  - offline (43 s): 0 network attempts, offline proven, download 81.9 MB (the tiny.en model, whisper-cli and the `.so` files in `/app/build/bin`).
  - build 200 s: the tools image was already in the registry.
- **Region data (for T-50).** Lowest grid intensity in Google's 2025 region data: northamerica-northeast1, 11.36 gCO2e/kWh. Lowest in Tier 1 pricing: europe-west9, 15.83. us-central1 is 431.95. With the test numbers, SCI per audio-minute is about 6.6 times higher in us-central1, and embodied carbon is about 85% of SCI in northamerica-northeast1.
- **G-1 met (cpu-proof run 38702242235, whisper.cpp 0c7be696).** Runners (2 vCPUs each): the native and folk-fix jobs ran on an AMD EPYC 9V74 (Zen 4), and the VM hides AVX-512, so `-march=native` gives v3 there. The all-variants job ran on an AMD EPYC 7763 (Zen 3).
  - Static (AC-F2): native v3; folk fix (`GGML_NATIVE=OFF`) v3, because ggml then turns on AVX, AVX2, FMA, F16C and BMI2 by default; all-variants v1 (highest level found v4, only in variants).
  - QEMU (AC-F3): native and folk fix crash with SIGILL on qemu64, Nehalem and SandyBridge, and pass on EPYC-Milan. All-variants passes on all four and loads x64, sse42, sandybridge and haswell. Every positive control passed and every negative control crashed.
  - So the folk fix does not fix #3510-type crashes on pre-AVX2 CPUs. Only the all-variants build holds the v1 floor.
- **Floors run 38704136185 (all-variants build).** Smallest passing cgroup limit: tiny 512 MB (peak RSS 179), base 512 (290), small 768 (758; out of memory at 512). Offline proven: 0 network attempts in a new network namespace under strace. Download 99.4 MB (tiny.en model + binary + libraries). Judge: all held, decision pass. `.floor/evidence/release/` has the manifest and the diff.

- iced-x86 reports TZCNT as BMI1 and XGETBV as XSAVE (both level 3). Both are on the allowlist, so they do not raise a floor.
- iced-x86 reports ENDBR64/ENDBR32 as CET_IBT and RDSSPD/RDSSPQ as CET_SS. These are extras, and they are on the allowlist.
- **T-15 (run 38537736704), first H-1 signal.** Both images come from the same `main.Dockerfile` (GGML_NATIVE default ON):
  - `main-a1867e0…` (built 2025-11-09T21:41Z, crashes in #3510): floor **x86-64-v4 + AVX512_VNNI**. `app/build/ggml/src/libggml-cpu.so` has EVEX code (VPSHUFD ×560, VPMADDUBSW ×384, VMOVDQA32 ×379). A machine with AVX-512 and VNNI built it.
  - `main-c62adfbd…` (built 2025-10-28T20:48Z, works): floor **x86-64-v3**. `libggml-cpu.so` is AVX2 code.
  - Both: 19 ELF files below `app/` (13 core, 6 CMake build tools); the `/app` layer is about 152 MB; no OCI revision label.
- **False positive (T-16).** whisper-cli, whisper-server, test-vad, test-vad-full and vad-speech-segments show v3 only because of LZCNT ×24. bench, main, quantize and libggml-base are v1. The LZCNT is probably the CPUID-guarded path of the FLAC decoder in miniaudio. It does not change T-15, but it breaks AC-F2 for the all-variants build until T-16 is fixed.
- **T-24 (run 38538051321).** Commit 47b9eb37 (2026-05-18): `main-<sha>` and `main-cuda-<sha>` both have floor x86-64-v3 and the same `libggml-cpu.so` profile (VMOVSS x1508). This pair does not reproduce #3814, because a Zen 3 CPU runs v3 code. The reporter's `main-cuda` image probably came from another commit, built on an AVX-512 runner. The CUDA image has no CMakeFiles probe binaries. Its `/app` layer is about 316 MB.
- **T-22 verdict: H-1 is supported** (`.floor/evidence/backtest/h1-*.json`, from `python -m floor h1`).
  - Same source, two builds: 38 commits have both a `main` and a `main-cuda` image in the sweeps. 11 of them have different floors (v3 in one image, v4 in the other). The two jobs run the same `make` on `ubuntu-24.04` GitHub-hosted runners, in the same workflow run. Only the runner differs.
  - Flips over time: `main` has 15 flips, and 10 of them have no change in any floor path (`.devops/`, `docker.yml`, CMake files, `ggml/src/ggml-cpu/`). `main-cuda` has 15 flips, and 5 have no change. The other flips come with ggml syncs, which touch the CMake files every time, so they prove nothing either way.
  - Cause in the upstream recipe: `.devops/main.Dockerfile` runs `make base.en`, so `GGML_NATIVE` is ON (the default), and the build targets whatever CPU the hosted runner has.
  - `main-cuda` sweep (run 38701134589): 60 images from 2025-06-25 to 2026-10-15, 48 at v3 and 12 at v4. Extras seen: AVX512_BF16, AVX512_VNNI, AVX_VNNI, GFNI.
- **T-21 sweep (run 38700707825), H-1 signal 3.** 61 `main-<sha>` images from 2025-04-04 to 2026-10-15 (`.floor/evidence/backtest/main-2026-10-15.json`). 52 are v3 and 9 are v4 (all with AVX512_VNNI). The floor flips 15 times. Flips happen within hours, faster than code can change:
  - 2026-05-25: v4 at 10:56Z (`b3877e10`), v3 at 18:57Z (`865ec171`), v4 at 21:04Z (`44a50ca4`), v3 at 23:24Z (`f14ae77f`).
  - 2026-05-31: v4 at 12:47Z (`f39cc712`), v3 at 13:11Z (`2e045a96`).
  - The newest image, `main-0c7be696…` (2026-10-15T04:29Z), is v4 + AVX512_BF16, AVX512_VNNI, GFNI. Today's published `main` crashes on every CPU without AVX-512.
- **Same commit, different floors (H-1 signal 4).** The CPU image and the CUDA image of one commit can have different floors:
  - `6227a0ef`: `main` v4, `main-cuda` v3.
  - `46ca43d6` and `968eebe7`: `main` v3, `main-cuda` v4.
  - The source is the same, so the build machine set the floor. This is the most direct H-1 evidence so far.
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

- Windows (Git Bash, Python 3.13 venv) is enough for the scanner, the tests and small pulls. When the console cannot show a character (→, Δ, ₂ in cp1252), the `floor` CLI prints "?" in its place. Files that it writes are always UTF-8.
- Upstream's `.devops/` (whisper.cpp `0c7be696`) has 7 Dockerfiles. main-cuda and main-rocm have quoted CMAKE_ARGS, and main-rocm installs a `make` package with dnf. Do not read RUN text with `shlex`: it stops at those quotes.
- Builds, QEMU, memory and offline tests need Linux: WSL Ubuntu, a Linux machine, or a CI job.
- Private repo: GitHub Actions has 2000 free minutes per month. A backtest job of 2 images takes a few minutes.
