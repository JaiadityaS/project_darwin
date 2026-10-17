# AGENTS.md: start here

> Temporary file for coding agents and teammates. Delete it, and the `.agents/` folder, before submission (task T-99).

You work on **Floor** (repo `project_darwin`): a release gate plus a repair agent for whisper.cpp. Floor proves, for every release, who can still use it.
Hackathon deadline: **2026-10-27 13:00 UTC**. Team submission target: **2026-10-26**.

## 1. Read first, in this order

1. This file.
2. `.agents/STATE.md`: live status, blockers, and "Next agent: start here".
3. `.agents/TASKS.md`: the task board. Claim a task before you start.
4. The newest 2–3 files in `.agents/log/`.
5. `docs/PRD.md`: read only the sections that your task cites (requirement IDs such as F2.1, gates such as G-1).
6. `.agents/DECISIONS.md` before you change a design choice.

## 2. Hard rules

1. **No AI attribution, anywhere.** No co-author trailers, no "generated with" lines, and no agent, assistant or vendor names in code, comments, docs, commit messages, PR text, branch names or file names. The local hooks block most cases. Never bypass them: `--no-verify` is forbidden.
2. **Human identity only.** Commit and push with the teammate's own git identity. Never change `user.name` or `user.email`, and never use `--author`.
3. **No tool files in git.** Agent-tool settings and memory files stay local. `scripts/install-hooks.sh` lists the common ones in `.git/info/exclude`. If your tool does not read `AGENTS.md` by itself, make a local pointer file for it and add that file to `.git/info/exclude`. Never add tool names to `.gitignore`.
4. **No upstream activity.** Never open issues, MRs, PRs or comments on whisper.cpp or ggml (PRD §5).
5. **Scripts decide floors.** No LLM output may set a floor status (PRD F5.1, §9.2).
6. **Main stays green.** Push to `main` only when the tests pass. Push red work to `wip/<handle>-<task-id>`.
7. **The PRD is the source of truth.** Record every deviation in `.agents/DECISIONS.md`.
8. **Never fake a result.** Every number comes from a script in the repo (PRD §13.4). Never stage demo output.
9. **Write docs in simple English:** short sentences, active voice, one idea per sentence (ASD-STE100 style).

## 3. Session protocol

### Start

```bash
git pull --rebase
bash scripts/install-hooks.sh        # safe to repeat
```

In a fresh clone (a new machine, a container or a remote sandbox), check the git identity before your first commit: `git config user.name` and `git config user.email`. It must be the human who runs the session, as in their earlier commits (`git log --format='%an <%ae>' | sort -u`). If it is empty or another name, stop and ask that human (rule 2). Some tools add their own trailer or session link to commit messages, or a branch prefix with the tool name. Rule 1 wins: remove them.

Read §1. Take the top task with Status `ready` in `.agents/TASKS.md` (or the one that STATE.md names). Claim it: set `Owner` to your handle and `Status` to `doing`. Then push the claim at once:

```bash
bash scripts/checkpoint.sh "chore(tasks): claim T-xx"
```

Claim before you code, so that two people do not build the same thing.

### While you work

- Make small commits. Run the tests before each push: `python -m pytest .floor/tests -q`
- Push after every finished step, and at least every 30–45 minutes: `bash scripts/checkpoint.sh "feat(scan): <what>"`
- Use Conventional Commit prefixes: `feat`, `fix`, `test`, `docs`, `chore`, `ci`, `refactor`.
- If you need a person (an account, access, money, a decision), add it to "Needs a human" in STATE.md and take the next ready task.

### Handoff: before your usage limit or session ends

Plan for the limit. Do not wait for it. If your tool shows plan usage, check it after each task. At about **80%**, or when the session may end soon:

1. Stop new work. Finish or park the current step.
2. Write a session log: `.agents/log/YYYY-MM-DD-<handle>-<n>.md` (template below). One file per session, so logs never conflict.
3. Update `.agents/STATE.md`: "Next agent: start here", gate status, blockers, facts learned.
4. Update `.agents/TASKS.md`: status, owner, branch. If you will not finish a task, release it (`Owner` = `-`, `Status` = `ready`) and say in your log exactly where you stopped.
5. Push: `bash scripts/checkpoint.sh "chore(handoff): <summary>"`. Red work goes to a `wip/` branch; write the branch name in STATE.md.

The next agent must be able to continue from STATE.md and your log alone, without asking anyone.

### Session log template

```markdown
# <date> <handle> session <n>
- Tasks: T-xx
- Done: <what changed, with paths>
- Verified: <commands run and results>
- Open: <what remains; the exact next step>
- Gotchas: <traps, wrong turns, facts learned>
- Branch: main | wip/<handle>-<task-id>
```

If a rebase stops on a conflict in STATE.md or TASKS.md, keep both sides by hand, then `git add`, `git rebase --continue`, and push again.

## 4. Repo map

| Path | Contents | GitLab fork |
|---|---|---|
| `.floor/floor/` | Python package `floor` (the gate tools) | code-owned |
| `.floor/floor/isa/` | Static CPU-floor scanner: levels, allowlist, decoder, ELF, scan | code-owned |
| `.floor/tests/` | pytest suite | code-owned |
| `.floor/overrides/` | Build overrides that the repair agent may change | not code-owned |
| `deploy/` (planned) | Service image recipes; the repair agent may change them | not code-owned |
| `infra/` (planned) | OpenTofu for Cloud Run and WIF | code-owned |
| `docs/PRD.md` | PRD v3.1, the source of truth | not copied |
| `scripts/` | `checkpoint.sh`, `install-hooks.sh`, `guard.sh` (dev only) | not copied |
| `.github/workflows/` | Dev CI on GitHub: tests and hygiene guard (dev only) | not copied |
| `.agents/` | STATE, TASKS, DECISIONS, log/ (temporary) | not copied |

The submission project on GitLab is whisper.cpp at a pinned commit plus the product files of this repo (DECISIONS D-001, D-002).

## 5. Commands

```bash
# Setup, once per clone (Python 3.10+)
python -m venv .venv
source .venv/Scripts/activate        # Windows Git Bash. Linux/macOS: source .venv/bin/activate
pip install -e "./.floor[dev]"
bash scripts/install-hooks.sh

# Tests
python -m pytest .floor/tests -q

# Static CPU-floor scan of a file or a directory of ELF files
python -m floor scan <path> [--json out/scan.json]

# Save and share work (installs the hooks, commits, rebases, pushes)
bash scripts/checkpoint.sh "type(scope): summary"
```

## 6. Definition of done for a task

- Code and tests. `pytest` is green locally and in CI.
- The PRD acceptance criterion (AC-*) for the task is shown with evidence (output file, job link).
- TASKS.md, STATE.md and a session log are up to date and pushed.

## 7. Domain notes (read before you touch the scanner)

- x86-64 levels: v1 = baseline (SSE2). v2 adds SSE3, SSSE3, SSE4.1, SSE4.2, POPCNT, CMPXCHG16B. v3 adds AVX, AVX2, BMI1, BMI2, F16C, FMA, LZCNT, MOVBE, XSAVE. v4 adds AVX-512 F, BW, CD, DQ, VL.
- A feature in no level (AES, PCLMULQDQ, AVX512_VNNI, AVX_VNNI, ...) is an "extra". No level guarantees an extra.
- ggml: `GGML_NATIVE` defaults to ON, so a build targets the CPU of the build machine. `GGML_NATIVE=OFF` alone still turns on AVX, AVX2, FMA, F16C and BMI2 (near v3). The inclusive build is `GGML_NATIVE=OFF GGML_BACKEND_DL=ON GGML_CPU_ALL_VARIANTS=ON BUILD_SHARED_LIBS=ON`.
- The CPU floor is the highest level in always-loaded code, joined with the lowest ggml CPU variant (`libggml-cpu-x64.so`). Other variants load only on CPUs that support them (DECISIONS D-007).
- Allowlisted false positives live in `.floor/floor/isa/allowlist.py`. Each entry has a reason and a test.
- Distro libraries (glibc and others) dispatch at run time. A linear scan of them always finds AVX-512, so they do not count toward the floor.
