# DECISIONS

Short records, newest last. Each record: the decision, why, and the PRD impact.

## D-001 (2026-10-14) Dev repo on GitHub, submission on GitLab
- Develop in the private GitHub repo `JaiadityaS/project_darwin`.
- The submission project on GitLab is whisper.cpp at a pinned commit, plus the product files of this repo. A script assembles it (T-02).
- Why: the team can sync now, before GitLab hackathon access is confirmed. Path B also needs a clean "what we added" story.

## D-002 (2026-10-14) Layout mirrors the GitLab overlay
- Product paths in this repo are the paths they get in the whisper.cpp fork: `.floor/` (tools, policy, schemas), `.floor/overrides/`, `deploy/`, `infra/`, `.gitlab-ci.yml`, `CODEOWNERS`.
- Dev-only paths never go to GitLab: `AGENTS.md`, `.agents/`, `scripts/`, `.github/`, `docs/`.
- PRD F1.2 names `.floor/judge/`. The Judge lives in the Python package (`.floor/floor/`). CODEOWNERS must cover all of `.floor/` except `.floor/overrides/`.

## D-003 (2026-10-14) `deploy/` vs `infra/`
- `deploy/` holds the image build recipes of the service. The repair agent may change it (PRD F4.2 allowlist).
- `infra/` holds OpenTofu for Cloud Run and WIF. It is code-owned. The agent may not change it.
- Why: least privilege. The PRD allowlist names `deploy/` for build config, not for cloud config.

## D-004 (2026-10-14) Static decoder: iced-x86 and pyelftools
- iced-x86 gives the exact CPUID features of each opcode form. Capstone groups are too coarse for BMI2, F16C and MOVBE.
- Linear sweep over the executable sections. If there are no section headers, use PT_LOAD segments with the X flag.

## D-005 (2026-10-14) Level map and extras
- Levels follow the x86-64 psABI: v1 baseline, v2, v3, v4.
- A feature in no level (AES, PCLMULQDQ, AVX512_VNNI, AVX_VNNI, ...) is an "extra". No level guarantees an extra, so the Judge must treat an unexpected extra as a raise.
- Some extras imply a minimum level: `AVX512*`, `AMX*`, `AVX10*` imply v4; `AVX_*`, `VAES`, `VPCLMULQDQ` imply v3.

## D-006 (2026-10-14) Allowlist of false positives
- TZCNT (`rep bsf`), ENDBR32/64 and RDSSPD/Q (hint-NOP space), XGETBV (feature detection after a CPUID check).
- Each entry has a reason in `.floor/floor/isa/allowlist.py` and a unit test. The QEMU runs (F3) corroborate the allowlist.

## D-007 (2026-10-14) What counts toward the CPU floor
- Floor = the highest level in always-loaded app code, joined with the lowest-level ggml CPU variant (`libggml-cpu-<tag>.so`). Other variants load only on CPUs that support them.
- Files under `CMakeFiles/` are build tools. The scan reports them but does not count them.
- Distro libraries (glibc, libstdc++, ...) dispatch at run time (ifunc). A linear scan always finds AVX-512 in them, so they do not count. The scan records their GNU ISA-level note when it exists.

## D-008 (2026-10-14) Team sync
- Trunk-based on `main`. Claims live in TASKS.md. Red work goes to `wip/<handle>-<task-id>`.
- One log file per session in `.agents/log/`, so logs never cause merge conflicts.

## D-009 (2026-10-14) No AI attribution; hygiene guard
- Local hooks (`scripts/install-hooks.sh`) run `scripts/guard.sh`: no co-author trailers, no agent-tool files, no tool or vendor names.
- CI runs the same guard on every push.
- Agent-tool files go to `.git/info/exclude`, never to `.gitignore`.

## D-010 (2026-10-16) Merge path: GitLab auto-merge, no merge-bot token
- Facts (2026-10-16, read-only check of the Showcase project 87296266): the team role is "Developer+" (level 30). It can push and merge to protected `main`, run pipelines, add CI/CD variables and webhooks, manage AI Catalog items and change MR settings. It cannot create project access tokens, change protected branches or tags, or manage runners. Duo features and shared runners are on.
- So the PRD merge-bot (F4.4, a project access token) is not possible.
- Decision: the flow opens the fix MR and sets auto-merge ("merge when the pipeline succeeds"). "Pipelines must succeed" is on in the MR settings. GitLab merges only when the gate pipeline passes. A release job on `main` cuts `-floor.N` with `CI_JOB_TOKEN`. The tag pipeline is not needed: the main pipeline does the release work.
- No personal access token in CI. A personal token acts as the human code owner, so CI could then approve and merge Leave-Behind Notices (breaks F6.1), and every merge would look human-made (breaks the Hands-off claim).
- Code-owner approval on `main` needs a Maintainer. Instead, `floor paths` fails the MR pipeline when an agent account changes a code-owned path. With "pipelines must succeed", that blocks the merge.
- Open (T-05): can the flow set auto-merge on its own MR? If not, record it and choose a fallback before G-4.
- PRD impact: F4.4, §10.1, NFR-6. Glossary "Merge-bot" now means this auto-merge path.

## D-011 (2026-10-16) Special prize: Environmental
- Path B Hands-off stays the main target. The special prize is Environmental, and the pitch also uses its creative side.
- Why: Floor is the only entry with ΔM and CPU floors. The six green rivals all measure the operational SCI of pipelines only. The extra work is small (T-54, T-55, T-56, T-60).
- If time is short after Oct 22, cut ΔM polish first.

## D-012 (2026-10-16) GitLab import: full upstream history, pinned at 0c7be696
- `scripts/assemble-gitlab.sh` (T-02) merges whisper.cpp at `0c7be696371069e0baa2515ed7aa08d5a5473aa6` (the G-1 commit, 2026-10-15) into the Showcase `main`, with the full upstream history (about 50 MB). The pin lives in `.floor/upstream.env`.
- Why: Path B judges can see in `git log` where upstream ends and Floor starts. The Showcase `main` already has a template commit and force push is off, so the import is a merge, not a reset.
- whisper.cpp's README and LICENSE stay at the top level. The Floor README is T-90 (it can move the upstream README).
- Each later run adds one sync commit with the product files of dev HEAD. It never overwrites or deletes files that the agent may change (`.floor/overrides/`, `deploy/`). It never touches upstream files such as `.devops/*.Dockerfile` after the import.
- `.gitlab/CODEOWNERS` now names the GitLab handle `@jaiadityasinghr`.

## D-013 (2026-10-17) Product name: Rieux
- The product name is **Rieux**, after Dr. Bernard Rieux in Camus's *The Plague* (1947). He does the work without heroics, keeps an honest record, and knows that the danger comes back. Our floor came back 15 times in 18 months (T-21).
- "Floor" stays as the name of what Rieux measures. Tagline: "Rieux watches the floor, so no one is left behind."
- Use "Rieux" in the README, the page, the video and the Devpost text. Use "Dr. Rieux" only to explain the source. Say the name ("ree-UH") and its source one time, early in the video.
- No change to code names: the Python package `floor`, the `.floor/` folder and the `floor` commands stay. This saves about a day of rename and test work.
- The book is still under copyright in many countries: at most one short quote with attribution, or none.
- PRD impact: §0 "Floor (working title)" is now Rieux. T-60, T-90, T-91, T-92 use the new name.

## D-014 (2026-10-17) GitLab pipeline, step 1: the CPU floor of upstream's image
- `.gitlab-ci.yml` (T-47) has these jobs: check, build, scan, probe (one job per CPU model), judge and pages. Step 1 gates the CPU floor only. Memory and connectivity come in step 2 (see below). Attest, herald, release and deploy come later (T-34, T-46, T-42, T-51).
- The build job builds upstream's `.devops/main.Dockerfile` with no change and pushes the image to the project registry (`$CI_REGISTRY_IMAGE/main:<commit>`). The later jobs use the image by its digest (a dotenv artifact: `IMAGE_REF`, `IMAGE_DIGEST`, `BASE_IMAGE`). So the gate checks the bytes that ship.
- The first `main` pipelines are red, and that is the honest start. Upstream's recipe keeps `GGML_NATIVE` ON, so the floor is the CPU of the runner (v3 or v4). With no earlier release, the reference is the policy (v1). So the Judge says "raised" and the judge job fails. The repair loop (T-40, T-41) must make it green.
- check: `floor policy`, then `.gitlab/ci/check.sh` (the tools image tag, the notices, the ratchet, and the path allowlist on merge requests), then the unit tests. The ratchet base is the MR target branch, or `CI_COMMIT_BEFORE_SHA` on a push.
- scan: `crane export` writes the image to `rootfs/`, and `floor scan rootfs/app` scans it. `cmake_flags` in the manifest come from `/app/build/CMakeCache.txt` in the image (the values in effect, defaults included), not from the Dockerfile text.
- probe: `floor probe --sysroot rootfs` runs `whisper-cli` from the image under `qemu-x86_64 -cpu <model> -L rootfs`, with the controls of T-13, on qemu64, Nehalem, SandyBridge and EPYC-Milan. QEMU uses `<sysroot>/<path>` when `access()` finds it, and the host kernel resolves an absolute link from the host root. So an absolute link in the image can load a host file. `relink_sysroot` first makes these links relative (`sysroot_links_rewritten` in the probe JSON). The model file stays outside the sysroot, so QEMU opens it from the host.
- The probe uses tiny.en, as in G-1. `.gitlab/ci/model.sh` gets it from upstream's Hugging Face URL, checks the SHA-1 in upstream's `models/README.md`, and keeps it in the CI cache. (The image also has base.en, because the recipe runs `make base.en`.)
- judge: `floor judge` takes one `--probe` file per CPU model (new: `--probe` can repeat). `floor manifest` has a new option `--build-cpu` (the CPU model and x86-64 level of the build machine, from `.gitlab/ci/facts.sh --cpu`). It goes to `predicate.build.host_cpu`. This field is not in PRD §11.1. It records the H-1 cause: with `GGML_NATIVE` ON, the build machine sets the floor.
- Tools image: `.gitlab/ci/tools.Dockerfile` (Ubuntu 24.04 with QEMU 8.2, crane 0.22.1 with a SHA-256 check, strace, GNU time, a venv). QEMU 7.2 and later emulate AVX2, so EPYC-Milan can run. The tag is the first 12 hex digits of the recipe's SHA-256. The build job builds the image only when the tag is missing. `check.sh` fails when `TOOLS_TAG` does not match the recipe.
- The build job uses Docker-in-Docker with TLS. The daemon uses the registry mirror `mirror.gcr.io`, because Docker Hub limits anonymous pulls. The base image digest comes from the BuildKit log, so no extra registry request is necessary.
- Path allowlist (F4.2, §10.1, D-010): deny by default. On a merge request pipeline, a pipeline user (`GITLAB_USER_LOGIN`) who is not in `FLOOR_HUMANS` counts as an agent. Then `floor paths --actor agent` fails the pipeline when the MR changes a path outside the agent allowlist. Known gaps:
  1. When a human runs the pipeline of an agent MR again, the pipeline user is the human, so the allowlist check does not run. A possible fix: read the MR author from the API (the project is public).
     - Closed on 2026-10-17 (session 6): `check.sh` runs `floor paths --actor auto`. The MR counts as an agent MR unless the pipeline user and the MR author (from the API, with no token) are both in `FLOOR_HUMANS`. When the API gives no answer, the MR counts as an agent MR. Still open: an agent pushes to the branch of a human's MR, and then a human runs the pipeline. Code-owner approval stays the main control.
  2. An MR pipeline runs the `.gitlab-ci.yml` of the MR, so an agent MR can change the gate itself. Only code-owner approval or a pipeline execution policy can stop this, and our role cannot set either (D-010). The main control is the tool limits of the flow (T-40). The MR diff shows every such change.
- Step 2, memory and connectivity: the build and scan jobs keep the output of `.gitlab/ci/facts.sh` (`out/build/runner.txt`, `out/scan/runner.txt`): the cgroup version, whether a job can make a child cgroup, and whether `unshare --net` works. The memory and offline jobs are designed from these facts. Until then the Judge lists both floors as unmeasured.
  - Facts from pipeline 2958271425: cgroup v2 in a private namespace, root with all capabilities, no systemd, a child cgroup can be made, `unshare --net` works.
  - So the `memory` job runs `floor memory --cgroup`. It moves the job processes into the leaf `floor-job`, enables `+memory` for the children of the root (cgroup v2 allows no controller below a cgroup that has processes), and gives each run its own child cgroup with `memory.max` and `memory.swap.max` = 0. "Swap equal to the limit" (F7.1) means no swap, as in Docker's `--memory-swap`. After each run, `cgroup.kill` ends what is left, for example after a timeout.
  - The `offline` job runs `floor offline --no-sudo`: `unshare --net` gives the same isolation as `--network none` (F8.1), as on GitHub (T-45).
  - Both jobs run the image's own binaries natively with `chroot` into the exported image, so the image's libraries load. The judge job needs both jobs, so a broken measurement stops the pipeline (fail closed). Models: tiny.en, base.en and small.en (the policy keys), and tiny.en for offline.
  - Manifest fields for AC-F7 and AC-F8 (§11.1): the memory floor has `peak_rss_mb` per model. The connectivity floor has `download_mb` (the total) and `download_bytes` (the size of each file of the offline run, by file name; bytes, so a small library does not show as 0.0 MB). Each floor links the job that measured it (scan, memory, offline): each job writes `$CI_JOB_URL` to `job-url.txt`, and the judge job gives `floor manifest --floor-evidence FLOOR=URL`. The pipeline URL stays the link for a floor with no job file.
  - The download size of each model (F8.1) is in the memory floor: `download_mb` per model, next to `smallest_passing_mb` and `peak_rss_mb`. The memory job has all three model files, so no job downloads a model only to measure its size. The value is the model plus whisper-cli and its libraries, the same meaning as the connectivity `download_mb`. `floor memory --artifact FILE` (repeat) measures it before the runs, so a wrong path stops the job early.
  - A peak-RSS rise over 10% from the previous release is a Judge note, shown in the judge output and in the diff ("Judge notes"). It does not change a status: the status comes from the smallest passing limit (F7.1).
- Costs and risks:
  - NFR-3 (MR pipeline under 10 min) is at risk. Docker-in-Docker has no layer cache, so each build compiles whisper.cpp and installs ffmpeg again. EPYC-Milan runs AVX2 code in QEMU TCG. The first pipeline gives the real times.
  - Every pipeline pushes a new image (the `/app` layer is about 150 MB, T-15). A cleanup policy needs a Maintainer, so delete old tags by hand when storage gets near the limit.
  - The base images are not pinned by digest (`ubuntu:22.04` in upstream's recipe, `ubuntu:24.04` in the tools recipe). The manifest records the base image digest of each build.
  - The image includes `.git`, `.floor` and `.gitlab`, because upstream's `.dockerignore` leaves out only `build*/`, `.github/` and `.devops/`.
- PRD impact: §7.1 (the pipeline comes in steps), §11.1 (`host_cpu`), F4.2 and §10.1 (deny by default, with the gaps above), NFR-3.

## D-015 (2026-10-17) R2: each GitLab job meters its own container
- SCI per release check (R2, PRD F14.1, §13.1) needs the CPU time and the memory of one release check, that is all the probes of one release. The release check is the GitLab pipeline (D-014). `floors.yml` on GitHub is not that pipeline: it builds whisper.cpp itself and runs no QEMU probes. So R2 comes from the GitLab jobs.
- The runner `k8s.saas-linux-small-amd64` runs each job in a Kubernetes pod. In the job container, `/proc/stat` and `/proc/meminfo` show the whole node. So the machine scope of `floor meter` would also count the helper container and the processes of the node. So `floor meter` has a second scope: one cgroup v2 group (`--cgroup`, default `/sys/fs/cgroup`). The scan job of pipeline 2958309699 showed that the job container is the root of a private cgroup namespace (`0::/`), with the cpu and memory controllers. In this scope:
  - CPU time: `usage_usec` of `cpu.stat`, for the group and all its children.
  - Memory: the working set, that is `memory.current` minus `inactive_file` of `memory.stat` (as in Kubernetes). The kernel can take back the inactive file cache at any time, so it does not count.
  - vCPUs: the quota of `cpu.max`, or else the CPUs that the job can use (`sched_getaffinity`).
- The jobs: scan, the four probe jobs, memory, offline and judge, that is every job of the `.tools` template. The `.tools` `before_script` starts the meter. An EXIT trap stops it when the job shell ends (also after a failed command) and writes `out/meter/<job>.json`. `floor memory --cgroup` moves the sampler into `floor-job` with the other processes. The files of the root group count all the children, so the values stay correct.
- The judge job stops its own meter first. Then `floor meter join` adds the meters of all the jobs into `out/judge/meter.json`: the sums of the wall time, the CPU time, the vCPU-seconds and the GB-seconds, as if the jobs ran one after the other on one runner. `jobs` keeps the values and the job link of each job. When the jobs have different vCPU counts, `vcpus` is the mean weighted by time. So `vcpus × wall_s` stays the sum of the vCPU-seconds, which the idle energy and the embodied share use.
- Watts: the CCF row of the CPU that the meter saw. GitLab does not publish the CPU of its hosted runners, but a job can read it. The scan job of pipeline 2958309699 ran on an Intel Xeon Platinum 8581C (Emerald Rapids). When the jobs ran on more than one CPU model, or the table has no row for the model, R2 uses the GCP average. The n2d-standard host for the embodied carbon stays an assumption.
- Not in R2: the check job (the unit tests of the gate), the build job (it makes the release, it does not check it), pages, the helper container (git clone, cache, artifacts), `pip install`, and the wait for a runner. So R2 is a lower bound for the pipeline.
- The meter never changes a floor or a job result. When the meter cannot start, the job prints one line and continues. Then the `jobs` list of `meter.json` and the description of the R2 manifest show the missing job.
- Evidence: a human commits `out/judge/meter.json` of a `main` pipeline as `.floor/evidence/release/meter.json` (CI has no token that can push, D-010). Then `floor footprint write` makes `sci-release-check.yml` again.
- PRD impact: F14.1 and §13.1. R2 is measured in the GitLab pipeline. The release-check watts come from the metered CPU when the table has a row for it.

## D-016 (2026-10-17) F4.5: the draft notice is a job artifact, and a code owner opens the notice MR
- F4.5: when the fallback also fails, "a script opens a draft Leave-Behind Notice" with the agent's diagnosis, and the loop stops. CI has no token that can open an MR or push a branch (D-010). So the script writes the draft as a job artifact, and a code owner opens the notice MR from it.
- `floor notice-draft` writes a draft only when both are true:
  1. The judge result has a dimension in `missing_notice` (a floor moved, and no merged notice covers it).
  2. The canned config is already on the branch (`fallback.pending` finds nothing to change), or the policy has `repair.fallback: none`.
  In all other cases it prints "no draft: …" and exits 0. So the order stays: the agent's fix, then the fallback (F4.3), then the draft.
- The `notice-draft` job (stage `repair`) has `needs: [judge]` and `when: on_failure`, so it runs after a failed judge. The judge keeps its artifacts on a failure (`when: always`), so the job gets `judge.json`. When the judge wrote no result, the job prints one line and passes. On an MR pipeline, the MR description (`CI_MERGE_REQUEST_DESCRIPTION`) is the diagnosis, and `--truncated` follows `CI_MERGE_REQUEST_DESCRIPTION_IS_TRUNCATED`. The pipeline URL is the evidence. The draft is `out/notice/NNNN-<dimensions>.md`. `artifacts:expose_as` shows it in the MR widget.
- The script fills a field only from evidence:
  - Floor change: the judge result and the policy.
  - Reason: the first paragraph of the MR description.
  - Tried first: the MR, the canned flags and the pipeline.
  - Who is affected and ΔM: a valid `.floor/scenarios/*.yml` file for that dimension, if one exists.
  - Guidance: the first sentence comes from `on_unfixable_raise`.
  - The other values stay as the §11.2 placeholders. "Approved by" always stays a placeholder, because only a code owner fills it (F6.1).
- The MR description is agent text, so it must not change the notice. The Reason summary is HTML-escaped and cut at 300 characters. The full text is an indented code block under "### Diagnosis", so it cannot add a field line, an approver or hidden HTML. `notice.problems` and `ratchet.notice_dimensions` read field lines only at the start of a line. (A fix in `ratchet.py`: an empty field took the text of the next line.)
- The loop stops for three reasons. The judge failed the pipeline. The fallback has nothing left to apply. Automation cannot fire a trigger, so no new agent attempt starts (§9.1). The next step is human: a code owner opens the notice MR, or closes the agent MR.
- `floor fallback` now reads each RUN instruction as shell words. The old line regex crashed on the quoted CMAKE_ARGS of upstream's main-cuda and main-rocm Dockerfiles ("No closing quotation"). It also put CMAKE_ARGS into the dnf package list of main-rocm (the `make` package). Now only a `make` command changes, and quotes, escapes and line continuations stay.
- PRD impact: F4.5 (the script writes the draft, and a code owner opens the notice MR). F6.1 does not change.
