# Evidence

Measured results that the Floor page (`python -m floor page`) and the README use. Do not edit these files by hand: run the workflow again and copy the new artifact.

| Folder | Source | What |
|---|---|---|
| `backtest/` | `sweep.yml`, `floor h1` | Timelines of published images and the H-1 verdict. See `backtest/README.md` |
| `cpu-proof/<build>/` | `cpu-proof.yml` run 38702242235 (whisper.cpp 0c7be696) | Static scan and QEMU runs with controls for the native, folk-fix and all-variants builds (AC-F2, AC-F3) |
| `release/` | `floors.yml` run 38704136185 (all-variants build) | Memory floor, offline proof, Judge output, manifest and diff of a dry-run release |
| `energy/` | `energy.yml` run 39033747472 (whisper.cpp 0c7be696, `base.en`, 5 runs per build) | CPU time, wall time and peak memory of the native, folk-fix, all-variants and x64-only builds on the same audio (F14.2), with the CMake logs and the runner CPU |
| `footprint/` | `floor footprint check` on the if-run output of `.floor/impact/sci-*.yml` | The SCI summary (F14.1). CI runs if-run again and compares the result with this file |

```bash
gh workflow run cpu-proof.yml
gh workflow run floors.yml
gh workflow run energy.yml
gh run download <run id>
```

After a new `energy/energy.json`, make the SCI files again (Node 22):

```bash
python -m floor footprint write
npm install -g @grnsft/if@1.1.1
if-run --manifest .floor/impact/sci-audio-minute.yml --output out/impact/sci-audio-minute
python -m floor footprint check out/impact/*.yaml --out .floor/evidence/footprint/sci.json
```
