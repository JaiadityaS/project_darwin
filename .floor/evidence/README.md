# Evidence

Measured results that the Floor page (`python -m floor page`) and the README use. Do not edit these files by hand: run the workflow again and copy the new artifact.

| Folder | Source | What |
|---|---|---|
| `backtest/` | `sweep.yml`, `floor h1` | Timelines of published images and the H-1 verdict. See `backtest/README.md` |
| `cpu-proof/<build>/` | `cpu-proof.yml` run 38702242235 (whisper.cpp 0c7be696) | Static scan and QEMU runs with controls for the native, folk-fix and all-variants builds (AC-F2, AC-F3) |
| `release/` | `floors.yml` run 38704136185 (all-variants build) | Memory floor, offline proof, Judge output, manifest and diff of a dry-run release |

```bash
gh workflow run cpu-proof.yml
gh workflow run floors.yml
gh run download <run id>
```
