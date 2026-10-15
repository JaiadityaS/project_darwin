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
