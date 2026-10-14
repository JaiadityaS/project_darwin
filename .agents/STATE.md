# STATE: the baton

Last update: 2026-10-14 08:40 UTC · @JaiadityaS · session 1 (bootstrap)

## Where we are

- PRD v3.1 is the go decision (`docs/PRD.md`). Today is build day 2 (PRD §17.2).
- Done: repo, team-sync system, hooks, CI for tests and hygiene.
- Done: the static scanner (T-10) and its tests (T-11). `python -m floor scan <path>` works on synthetic ELF files. It has not yet seen a real whisper.cpp binary.

## Gates (PRD §17.1)

| Gate | Due | Status |
|---|---|---|
| G-0 Access and trigger chain | Oct 14 | waits on humans (T-01, T-06) |
| G-1 CPU proof | Oct 15 | scanner done; needs real binaries (T-12, T-15) and QEMU (T-13) |
| G-2 Backtest and H-1 | Oct 16 | not started |
| G-3 Gate integrity | Oct 18 | not started |
| G-4 Release loop | Oct 22 | not started |

## Next agent: start here

1. T-20: the OCI client for ghcr.io (design notes in log 2026-10-14-jaiadityas-1). Then T-15: scan `main-a1867e0` and `main-c62adfbd`.
2. T-24: scan `main-cuda` and `main` at the same commit.
3. T-12: Linux builds of whisper.cpp (native, folk fix, all-variants) and scans. T-13 in parallel if you have Linux.

## Needs a human (agents cannot do these)

- [ ] T-01: confirm GitLab hackathon group access, the tier (Premium or Ultimate) and the Duo credit pool.
- [ ] T-06: Google Cloud project with billing and a budget alert, for Cloud Run and WIF.
- [ ] Add teammates as collaborators on GitHub `JaiadityaS/project_darwin`.

## Facts learned (measured)

- iced-x86 reports TZCNT as BMI1 and XGETBV as XSAVE (both level 3). Both are on the allowlist, so they do not raise a floor.
- iced-x86 reports ENDBR64/ENDBR32 as CET_IBT and RDSSPD/RDSSPQ as CET_SS. These are extras, and they are on the allowlist.

## Environment notes

- Windows (Git Bash, Python 3.13 venv) is enough for the scanner, the backtest and the tests.
- Builds, QEMU, memory and offline tests need Linux: WSL Ubuntu, a Linux machine, or a CI job.
