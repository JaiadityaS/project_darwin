# Evidence

Measured results that the Floor page (`python -m floor page`) and the README use. Do not edit these files by hand: run the workflow again and copy the new artifact.

| Folder | Source | What |
|---|---|---|
| `backtest/` | `sweep.yml`, `floor h1` | Timelines of published images and the H-1 verdict. See `backtest/README.md` |
| `cpu-proof/<build>/` | `cpu-proof.yml` run 38702242235 (whisper.cpp 0c7be696) | Static scan and QEMU runs with controls for the native, folk-fix and all-variants builds (AC-F2, AC-F3) |
| `release/` | `floors.yml` run 38704136185 (all-variants build) | Memory floor, offline proof, Judge output, manifest and diff of a dry-run release |
| `release/meter.json` | GitLab pipeline 2960804030 (`main` `64329927`), the judge job's `out/judge/meter.json` | CPU time and memory of one release check, R2 (D-015) |
| `energy/` | `energy.yml` run 39033747472 (whisper.cpp 0c7be696, `base.en`, 5 runs per build) | CPU time, wall time and peak memory of the native, folk-fix, all-variants and x64-only builds on the same audio (F14.2), with the CMake logs and the runner CPU |
| `language/` | `language.yml` run 39233922646 (whisper.cpp 0c7be696, FLEURS test, 50 sentences per language) | The served / not-served language table (F9.1, D-031): WER and CER of tiny, base and small at f16 and q5_1, the drift with a paired-bootstrap 95% interval, and the pinned decoding (F9.2) |
| `spotcheck/` | `floor spotcheck` on the GitHub search hits, the seed and one label per sampled hit (§3.2, D-030) | The true-positive rate of the "illegal instruction" hits of whisper.cpp. The labels are a reading of each thread, with a reason and a link |
| `footprint/` | `floor footprint check` on the if-run output of `.floor/impact/sci-*.yml` | The SCI summary (F14.1). CI runs if-run again and compares the result with this file |
| `repair/` | `floor repairs --api https://gitlab.com/api/v4 --project 87296266 --out .floor/evidence/repair/repairs.json` (the GitLab API, no token) | The repair loop on GitLab (F4): each fix MR of the floor-repair flow, its minutes and its gate. `notes.json` is a note by a person for each gate that did not pass |
| `notice/` | The log of the `notice-draft` job (MR pipeline 2970472763, job 17337464293) and MR !13 | Each Leave-Behind Notice draft of a gate (F4.5) and what a code owner did with it (F6). `drafts.json` is written by a person from the MR and the job log |

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
