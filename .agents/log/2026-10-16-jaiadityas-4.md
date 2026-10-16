# Session 4 · 2026-10-16 · @JaiadityaS

## Done

- T-56: `floor delta-m` (pushed in 727b3ba).
- T-54, the SCI part (this push):
  - `.floor/impact/footprint.yml`: every coefficient, with its source. CCF watts per vCPU (by microarchitecture and the provider averages), memory 0.392 W/GB, PUE (GCP 1.1, Azure 1.185), grid intensity from Google region-carbon-info 2025, CCF embodied emissions for the n2d and e2 hosts, and the two sites (service, release check).
  - `.floor/floor/footprint.py`: `write` makes Impact Framework (IF) manifests from the evidence. `check` recomputes every if-run output with independent formulas (rel tol 1e-9). `stale` finds committed manifests that do not match the evidence. `summarize` gives the SCI summary for the manifest.
  - CLI: `floor footprint write|stale|check`, and `floor manifest --footprint sci.json`.
  - `.floor/tests/test_footprint.py`: a small Python copy of if-run for the builtins that the manifests use (Multiply, Sum, Subtract, Divide, SciEmbodied, Sci).
- Tests: 148 passed, 5 skipped (Windows).
- Real if-run (@grnsft/if@1.1.1, Node 22) on manifests made from the test evidence: `floor footprint check` says every output matches the formulas. Headline test SCI 0.002638 g per audio-minute, the same as the Python copy in the tests.

## The IF pipeline (one child per build or per site)

`vcpu-seconds` (Multiply cpu/vcpus × duration) → `watts-delta` (Subtract max − min) → `cpu-idle` → `cpu-load` → `memory` → `it-energy` (Sum) → `facility-energy` (× pue) → `energy-kwh` (Divide by 3600000; IF wants `energy` in kWh) → `operational-carbon` (× grid intensity) → `host-share` (Divide cpu/vcpus by host/vcpus → usage-ratio) → `embodied-carbon` (SciEmbodied, baseline-emissions = host TE in g, lifespan 126144000 s) → `carbon` (Sum) → `sci` (Sci, functional-unit `audio-minutes` or `release-checks`).

IF v1.1.1 facts, read from the source:

- Multiply, Sum and Subtract take `input-parameters` (a list) and `output-parameter`. Subtract is the first item minus the rest.
- Divide takes `numerator` (a field name), `denominator` (a field name or a number) and `output`. Do not name an input field `numerator` or `denominator`.
- SciEmbodied: `embodied-carbon = total × usage-ratio × time / lifespan`, with `time = input.time || input.duration`. With no `vCPUs`, `memory`, `ssd`, `hdd` or `gpu` inputs, total = `baseline-emissions`.
- Sci: `sci = carbon / input[functional-unit]`. It needs `duration >= 1`.
- Run: `if-run --manifest X --output Y` writes `Y.yaml`. Package `@grnsft/if@1.1.1`.

## Result from the test numbers

In northamerica-northeast1 (11.36 g/kWh), embodied carbon is about 85% of SCI. In us-central1 (431.95 g/kWh), SCI is about 6.6 times higher. So the region (lever 5) is large, and in a clean region the embodied share is the next lever.

## Next steps (the design is fixed; write the code)

1. **`.floor/floor/meter.py`** (Linux, whole machine, for R2):
   - Busy CPU = the user, nice, system, irq and softirq fields of the first `/proc/stat` line, divided by `os.sysconf("SC_CLK_TCK")`.
   - Memory used = MemTotal − MemAvailable from `/proc/meminfo`, in GB.
   - `start`: write a state JSON (start time, busy ticks, vCPUs, CPU model) and start a sampler process (`python -m floor meter sample --state F --interval 5`, `start_new_session=True`). The sampler adds GB-seconds with the trapezoid rule and writes `<state>.samples.json` atomically.
   - `stop`: stop the sampler (SIGTERM), add the last interval, and write `measured_at` (ISO 8601, UTC), `wall_s`, `cpu_s`, `vcpus`, `vcpu_s`, `memory_gb_s`, `memory_peak_gb`, `cpu_model`. `footprint.release_inputs` reads these fields.
   - CLI: `floor meter start|sample|stop --state FILE --interval 5 --out FILE`.
2. **`.floor/floor/energy.py`** (T-55, for R1):
   - Time each run with GNU time: `/usr/bin/time -o F -f "%e %U %S %M" -- CMD`. cpu_s = user + system. Peak RSS = %M KB / 1024.
   - `floor audio SRC OUT --copies 11 --gap 1`: repeat jfk.wav with 1 s of silence (0x00 for 16-bit, 0x80 for 8-bit). This gives about 131 s of audio.
   - `floor energy --build NAME=EXE (repeat) --audio WAV --expect TEXT --runs 5 --warmup 1 -- ARGS`. The builds take turns in each round, and the order rotates each round. Refuse to start when the cwd has `libggml-cpu-*.so` files, because ggml also loads backends from the cwd.
   - The output JSON needs `measured_at`, `vcpus`, `cpu_model`, `runs_per_build`, `audio_minutes`, `evidence` (the run URL) and, per build, the medians `wall_s`, `cpu_s` and `peak_rss_mb`. `footprint.audio_inputs` reads these fields. Also write the loaded variant (`qemu.loaded_variant` on stderr) and a transcript hash per build.
3. **`.github/workflows/energy.yml`** (workflow_dispatch: commit, model base.en, runs 5):
   - Build whisper.cpp 0c7be696 three times (native, folk fix `GGML_NATIVE=OFF`, all-variants `GGML_BACKEND_DL=ON GGML_CPU_ALL_VARIANTS=ON`) with `--target whisper-cli`.
   - x64-only: `cp -a build-all-variants/bin w/x64-only`, then delete every `libggml-cpu-*.so` except `libggml-cpu-x64.so`.
   - Run `floor energy` with absolute paths and `-m MODEL -t $(nproc) -nt -nf`. Commit the output to `.floor/evidence/energy/energy.json`.
4. **`floors.yml`**: `meter start` after the build, `meter stop --out out/meter.json` at the end, then setup-node 22, `footprint write --meter out/meter.json --out-dir out/impact-src`, if-run, `footprint check --out out/sci.json`, and `manifest --footprint out/sci.json`.
5. **`ci.yml`**: setup-node 22. Run if-run on every committed `.floor/impact/sci-*.yml`, then `floor footprint check out/impact/*.yaml --expect .floor/evidence/footprint/sci.json`, then `floor footprint stale`.
6. **Floor page (T-60)**: an energy section (the inclusion cost of each build), an SCI section (the two headline values and the region comparison) and a language section ("not measured yet"). Then change the count in `test_page_without_evidence` from 3 to 6.

## Facts to keep

- **Correction:** in cpu-proof run 38702242235, the all-variants job ran on an AMD EPYC 7763 (Zen 3). The native and folk-fix jobs ran on an EPYC 9V74 (Zen 4, AVX-512 hidden). All three runners had 2 vCPUs. STATE.md now says this.
- **Region (PRD open question, for T-50):** northamerica-northeast1 has the lowest grid intensity in the 2025 data (11.36 g/kWh). The lowest region in Tier 1 pricing is europe-west9 (15.83 g/kWh). The team decides at T-50.
- Neither Cloud Run nor GitLab-hosted runners publish their CPU platform. So the SCI manifests use the CCF GCP average watts and an n2d-standard host. The manifest descriptions say this.
