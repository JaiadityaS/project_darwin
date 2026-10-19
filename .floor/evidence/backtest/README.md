# Backtest evidence

`<prefix>-<date>.json` is the output of `python -m floor timeline` from one run of `.github/workflows/sweep.yml`.
`h1-<prefix>-<date>.json` is the output of `python -m floor h1` on that timeline (PRD F10.3).
Do not edit these files by hand. Run the sweep again and add new files.

To make the H-1 files again:

```bash
git clone --filter=blob:none --no-checkout https://github.com/ggml-org/whisper.cpp ../whisper.cpp
python -m floor h1 .floor/evidence/backtest/main-2026-10-15.json --git ../whisper.cpp --pair .floor/evidence/backtest/main-cuda-2026-10-15.json --out .floor/evidence/backtest/h1-main-2026-10-15.json
```

| File | Run | Images |
|---|---|---|
| `main-2026-10-15.json` | sweep run 38700707825 (`main-` tags) | 61 |
| `main-cuda-2026-10-15.json` | sweep run 38701134589 (`main-cuda-` tags) | 60 |
| `h1-main-2026-10-15.json`, `h1-main-cuda-2026-10-15.json` | `floor h1` on the two timelines above | - |
| `sweep-jobs-38700707825.json`, `sweep-jobs-38701134589.json` | the job times of the two sweep runs (`gh run view <id> --json databaseId,jobs`) | - |
| `footprint-2026-10-15.json` | `floor backtest-footprint` (PRD F14.4): the downloaded bytes and the runner time of the backtest | 121 |

To make the footprint again (PRD F14.4). It reads the blob sizes from the registry and the job times from the two files:

```bash
python -m floor backtest-footprint .floor/evidence/backtest/main-2026-10-15.json .floor/evidence/backtest/main-cuda-2026-10-15.json --runs .floor/evidence/backtest/sweep-jobs-38700707825.json .floor/evidence/backtest/sweep-jobs-38701134589.json --out .floor/evidence/backtest/footprint-2026-10-15.json
```
