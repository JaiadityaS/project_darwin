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
- Fact (2026-10-19, project API): "Pipelines must succeed" is off (`only_allow_merge_if_pipeline_succeeds: false`). Without it, auto-merge set before the MR pipeline exists can merge at once. Turning it on is a project setting, so the user decides (T-05). The flow tools have no merge tool. The note tool (`create_merge_request_note`) posts the body as it is, so a `/merge` quick action is the candidate path.
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

## D-017 (2026-10-19) The Rieux README is the front page of the GitLab project
- `README.md` of this repo is now a product file (`PRODUCT` in `scripts/assemble-gitlab.sh`). It is the README of the GitLab project, so the judges see Rieux first.
- The first sync after this change moves whisper.cpp's `README.md` to `README.whisper.cpp.md` (`git mv`, one time). It stays in the top folder, so its relative links still work. The Rieux README links to it in its first section. This is the one change to an upstream file after the import. D-012 allowed it ("it can move the upstream README").
- whisper.cpp's `LICENSE` stays. The Rieux README states that both parts are MIT.
- The README is the same file in this repo and on GitLab. Its links point only to files that are on GitLab (product files and whisper.cpp files). The dev-only files (`docs/PRD.md`, `.github/workflows/`) are not linked. The GitHub run IDs stay in the evidence files.
- The stage table has a status column with a date. Update it before submission (T-90 stays open until then).

## D-018 (2026-10-19) F4.3: the fallback job keeps a patch; the flow or a human commits it
- F4.3 says that a CI script applies the canned inclusive config "to the same branch". CI cannot push to the branch:
  1. We have no project access token and no personal token in CI (D-010).
  2. A push with `CI_JOB_TOKEN` needs the project setting "Allow Git push requests to the repository". Only a Maintainer or Owner can turn it on, and our role is Developer+ (GitLab docs, `ci/jobs/ci_job_token`, read 2026-10-19).
  3. A push with `CI_JOB_TOKEN` starts no pipeline, so the gate would not re-verify the branch anyway (the same docs).
- Decision: the `fallback` job (stage `repair`, `needs: [judge]`, `when: on_failure`) runs `floor fallback --judge out/judge/judge.json --patch out/fallback/fallback.patch`. The patch is an artifact in the MR widget ("Canned config patch"). The flow or a human commits it with `git apply`. The push starts the next MR pipeline, and that pipeline is the gate's re-check.
- The patch is script output. The commit copies it as it is, so no LLM output decides the config (F5.1). The patch changes only allowlist paths (`.devops/*.Dockerfile`, `.floor/overrides/`), so `floor paths` passes it for an agent too.
- The order stays: the agent's fix, then the fallback, then the draft notice. When the branch already has the canned config, `floor fallback --patch` writes no patch, and `floor notice-draft` writes the draft (D-016).
- Gap: one more push is needed (by the flow or a human). The Hands-off claim holds only when the flow does it (T-40). If the flow cannot, a human commits the patch, and the demo says so.
- PRD impact: F4.3 ("applies … to the same branch" now means "makes the patch for the same branch").

## D-019 (2026-10-19) F13.3: a code-owned gateway in front of whisper-server
- Fact: whisper-server reads its parameters from the request form (for example `duration`, `beam_size`), and it has no rate limit (`examples/server/server.cpp`, `get_req_parameters`). With `--convert`, it writes each upload to a temp file. So whisper-server cannot be the public port.
- Decision: `.floor/floor/gateway.py` (standard library only) is the public port. whisper-server listens on 127.0.0.1:8081, with `-d 30000` and no `--convert`, so it decodes the audio in memory.
  - The browser makes 16 kHz mono 16-bit WAV (`gateway.html`), so the gateway can check the length from the WAV header and the data size, with no decoder.
  - Limits: at most 30 s; a body cap of 964,096 bytes (checked before the body is read); 6 requests a minute per client; 30 a minute per instance; one transcription at a time per instance.
  - The client address is the last `X-Forwarded-For` entry (Cloud Run adds it; the client can set the entries before it). The per-instance limit holds even if this address is wrong.
  - The gateway sends only fixed parameters (`response_format=json`, `temperature=0.0`) and the audio.
  - Privacy (NFR-7): no file, and the log has the method, the path and the status only.
- The gateway is code-owned (`.floor/`), so the repair agent cannot weaken the limits. `deploy/service.Dockerfile` (agent allowlist) builds FROM the held image and only adds python3 and the gateway files.
- Max instances: a Cloud Run setting in `infra/` (T-50).

## D-020 (2026-10-19) T-03: the trigger chain works; flows live in `.floor/flows/`
- Test: a person started a pipeline on `main` (UI "New pipeline", pipeline 2960962126). It failed at the judge as planned. The project trigger "Pipeline events: Failed" started the private AI Catalog flow "Rieux trigger probe" (item 1018639, session 9657595, CI job 17269341490) in about 30 s.
- The actor is the person: the session says "Triggered by @jaiadityasinghr". The flow runs as its own service account (`@ai-rieux-trigger-probe-gitlab-ai-hackathon`, Developer role, a composite identity with the person). Git commits by the flow show the flow name as the author.
- `context:goal` is the full pipeline webhook payload. The probe copied `object_attributes` (id, status, ref, sha, source `web`), `user.username` and the status of the `judge` build. So the first step of T-40 can read "judge failed" from the event, with no tool call.
- PRD §9.1 says the pipeline trigger came "behind an experimental flag, removed in 19.1". The flag was removed, not the trigger: "Pipeline events" is in the trigger list (Running, Passed, Failed, Canceled). The design of PRD §9 holds.
- Catalog limits found (GitLab.com, 2026-10-19):
  1. The create form puts an example flow in the YAML editor. Our first save kept that example below our YAML. YAML keeps the last value of a repeated key, so session 9657365 ran the example, not the probe. Check the stored definition (GraphQL `aiCatalogItem { latestVersion { ... on AiCatalogFlowVersion { definition } } }`) after each save.
  2. The catalog schema refuses `max_cycles` on a component ("a disallowed additional property"), although the runtime docs list it. The example hid this error.
  3. The editor indents typed lines again, so typed YAML breaks. A clipboard paste keeps the text, but it did not always arrive. For v1.1.0 the save request of the form (the `updateAiCatalogFlow` mutation) carried the file text, and the stored definition equals the file byte for byte.
  4. Each save makes a new version (v1.1.0 now). The project uses the latest version.
- Decision: every flow definition is a file in `.floor/flows/`, code-owned (CODEOWNERS and `paths.CODE_OWNED`), with a test. The catalog copy must equal the file. The repair agent cannot change a flow.
- Not tested yet: a human tag push (T-42). It is also an action by a person, so it should start the flow in the same way.
- PRD impact: none to the design. §9.1 wording only (see above).

## D-021 (2026-10-19) T-40: the floor-repair flow; two PRD steps are agent steps
- PRD §9 table: "Exit unless the Judge said raised (deterministic) → diagnose and propose (agent) → open the fix MR (deterministic)".
- Fact: a `DeterministicStepComponent` runs one tool with inputs taken whole from the flow state. It cannot take one field out of `context:goal` (the pipeline event is one JSON value), and a router matches exact string values only. So no deterministic step can read "the judge build failed" from the event, and none can build the commit and the MR with values from the event.
- Decision (`.floor/flows/floor-repair.yml`, code-owned, tested in `test_flows.py`):
  1. `gate`: an agent with no tools. It answers "raised" only when the event says that the pipeline and its `judge` build failed and the ref is not a `floor-fix/` branch. The router starts `repair` only on the exact string "raised"; any other answer ends the flow. A wrong answer costs one run, and it cannot weaken the gate.
  2. `repair`: an agent with five tools (`get_job_logs`, `get_repository_file`, `create_branch`, `create_commit`, `create_merge_request`). It stops unless the judge log says "Pareto: raised". It copies the patch of the `fallback` job (D-018) from the job log and applies it to the files at the pipeline commit. On an MR pipeline it commits to the MR source branch (F4.3, "the same branch"). Else it commits to `floor-fix/<pipeline>` and opens an MR into the ref (into the default branch for a tag).
- The `fallback` job now prints the patch in its log between `--- BEGIN fallback.patch ---` and `--- END fallback.patch ---`, because the flow tools read job logs and not artifacts.
- Why this still meets F5.1: the judge script sets every floor. The agent applies a patch that a script wrote. The MR pipeline runs the whole gate again, and `floor paths` refuses any path outside the allowlist for the service account (D-014). If the agent changes a line wrongly, the gate (or the reviewer) sees it in the MR.
- The order "the agent's fix, then the fallback" (D-018) becomes one step for now: the flow's fix is the canned config. A free-form agent fix is cut, because the canned config is the fix that G-1 proved.
- Auto-merge (F4.4) is T-05. The flow does not set it yet.
- PRD impact: §9 table (the exit step and the MR step are agent steps with fixed rules); F4.2 (the agent proposes the canned config only).
- First run (2026-10-19): the sync push pipeline 2960990129 failed at the judge, and session 9657869 ran `gate`, then `repair`. It read the judge and fallback logs and the 8 files, created `floor-fix/2960990129`, made commit `a8aca4ca` and opened MR !1 in about 2 minutes. The 8 files equal the output of `floor fallback` byte for byte.
  - Identity: the MR author shows as the person (composite identity). The commit author and the MR pipeline user are the service account. The `check` job counted that user as an agent and allowed the 8 paths (D-014).
  - Tool names come from the tool source, and the catalog does not check them: the job log tool is `get_job_logs`. The first save had a wrong name, and it was fixed before the run.
  - The first commit call sent "update" for the new file `.floor/overrides/main.flags` and failed. The agent then sent "create" and the commit worked. The prompt now names the action for a new file.

## D-022 (2026-10-19) The gate harness: /proc in the chroot jobs, and 2 threads under QEMU
- Evidence: MR !1 (made by the flow, D-021) ran MR pipeline 2961002610 on the image with the canned config.
  - `memory` and `offline`: each run ended with exit -11 after `GGML_ASSERT(device)`. ggml loaded 0 backends.
  - `probe`: qemu64 (297 s), Nehalem (181 s) and SandyBridge (568 s) passed. EPYC-Milan stopped at the 1800 s run limit (1816 s).
  - The judge said: CPU inconclusive, memory inconclusive, connectivity raised. So the gate failed, but the cause is the harness, not the image.
- Cause 1: the canned config sets `GGML_BACKEND_DL=ON`, so ggml loads its CPU backends from the folder of the program, which it finds through `/proc/self/exe`. A container runtime gives the image a `/proc`; `chroot` does not. The upstream image has a static CPU backend, so the main pipelines did not see this. QEMU user mode emulates `/proc/self/exe`, so `probe` was not hit.
- Cause 2: the runner has 2 vCPUs. With `-t 4`, the ggml threads spin at each barrier and use emulated CPU time for no work.
- Decision (`.gitlab-ci.yml`, tested in `test_floors_linux.py` and `test_qemu.py`):
  - `memory` and `offline` mount `/proc` in the exported image (`mount -t proc proc rootfs/proc`) after the export and before the first run.
  - `probe` runs with `-t 2` and a run limit of 2400 s. The job limit stays 50 min.
  - `memory` and `offline` keep `-t 4`; they run natively.
- No PRD impact: the measures and the floors do not change. The next MR pipeline (from the flow, on the fixed CI) is the check.
- Evidence (2026-10-19): MR !2 (pipeline 2961093570, fix of 2961083963): memory, offline, service and three probes passed; EPYC-Milan timed out at 2400 s, so the judge said cpu inconclusive and failed (D-027). MR !3 (pipeline 2961110649, fix of 2961094614): every floor held, Pareto held, gate pass. Probe job times: qemu64 259 s, Nehalem 220 s, SandyBridge 541 s, EPYC-Milan 2175 s. MR !5 (pipeline 2961210282, fix of 2961183840, with D-027): gate pass again.

## D-023 (2026-10-19) T-34: the `attest` job signs the manifest after a passed judge
- PRD F5.4: sign the manifest as an in-toto attestation (`cosign attest`, keyless with GitLab OIDC) on the image digest. AC-F5: `cosign verify-attestation` passes.
- Decision (`.gitlab-ci.yml` job `attest`, `floor attest`, tested in `test_attest.py`):
  - The job runs after `build` and `judge` and only when the judge passed (no `when`). That is each pipeline where the gate holds: merge requests, `main` and tags. The fix MR of the flow (T-40) is the first place where it can run.
  - Keyless: the job asks GitLab for an ID token with the audience `sigstore`. cosign trades it for a short-lived Sigstore certificate, and the public Rekor log records the signature. The certificate identity is the pipeline definition at the ref (`https://` and the `ci_config_ref_uri` claim). `floor attest identity` reads only that claim, because the token also has claims about the person who started the pipeline. The job never prints the token.
  - `floor attest predicate` gives cosign the predicate and its type; cosign wraps them in its own Statement on the digest. After the signature, `cosign verify-attestation` checks the exact identity and the issuer (`$CI_SERVER_URL`), and `floor attest check` compares the verified predicate with the manifest. The job keeps the verify command in `out/attest/verify.txt`.
  - cosign v2.6.5 (the v2 line, still maintained): v2 keeps the attestation next to the image as a `.att` tag, which every registry can store. The job downloads the binary from the GitHub release and checks its SHA-256 (pinned; the asset digest and `cosign_checksums.txt` agree). The tools image does not change, so no other job pulls a larger image.
- Evidence (2026-10-19): MR pipeline 2961110649, attest job 17270217868 (30 s). `cosign attest` signed with the GitLab ID token, `cosign verify-attestation` passed with identity `https://gitlab.com/gitlab-ai-hackathon/transcend-october-2026/43085222/showcase//.gitlab-ci.yml@refs/heads/floor-fix/2961094614` (the double slash is in the GitLab claim) and issuer `https://gitlab.com`, and `floor attest check` matched the signed predicate to the manifest. `out/attest/verify.txt` has the command.
- Evidence 2: MR pipeline 2961210282, attest job 17270780570 (30 s): signed and verified again.
- Not yet: attaching the attestation to the GitLab Release (T-42), and two releases with a diff (AC-F5).
- PRD impact: none.

## D-024 (2026-10-19) T-42: the release job cuts `<tag>-floor.N` only after a merged fix of a tag
- PRD F4.4 and AC-F4a: a tag built with upstream's default flags ends as a live `-floor.1` release, and no human acts after the tag push. D-010: the release job on `main` uses `CI_JOB_TOKEN`.
- Decision (`.gitlab-ci.yml` job `release`, `floor release`, tested in `test_release.py`):
  - The job runs on the default branch after `judge` and `attest`, so only when the gate held and the manifest is signed.
  - `floor release` (a script) decides. The commit must be the merge of a `floor-fix/<pipeline id>` MR into the default branch, and that pipeline must be a tag pipeline. Then the release is `<tag>-floor.N`, where N is one more than the highest N of that tag. Any other commit (a sync push, a fix of a branch pipeline) gets no release, and the job passes.
  - The job posts to the Releases API with `CI_JOB_TOKEN`; GitLab makes the tag from `ref` (the merged commit). The description has the floor diff, the fix MR and the cosign verify command. The links are the manifest (judge job) and the verify command (attest job).
  - Workflow rule: no pipeline for a `-floor.N` tag. The default-branch pipeline of the same commit already proved and signed it, and a second run would only use runner time.
- Facts still to check on the first run: whether the job token of that pipeline may create the tag (protected tags are a Maintainer setting, D-010), and who the pipeline user is after an auto-merge (T-05).
- Fact (2026-10-19, project API as the team account): the merge method is `merge` (a merge commit, so `/repository/commits/<sha>/merge_requests` finds the fix MR from the merge commit). The protected-tags API refuses the Developer role (403), so the team cannot see which tag names are protected. A refusal shows on the first release as an API error (rc 1) in the `release` job log.
- PRD impact: F4.4 (the default-branch pipeline makes the release; no merge-bot token, D-010).

## D-025 (2026-10-19) T-46: Herald starts as a template; the agent part waits for T-04
- PRD F12.1: release notes get a "Who this release serves" section from the manifest, by the Herald CI job, for every release. PRD §9.2 allows a deterministic template when the Duo CLI is not available.
- Decision (`floor herald`, `herald.py`, the `herald` job, tested in `test_herald.py`):
  - The `herald` job runs after `judge` and `attest`, so only for a signed manifest. It writes `out/herald/who.md`.
  - The text comes only from the manifest: the CPU level in plain words, the emulated CPU models that ran (with the ggml variant) or did not run, the smallest memory limit per model, the offline download and network attempts, notices, what is not measured, and SCI. If a floor rose, it says that the gate blocks the build; it never says "nobody" then.
  - The `release` job puts the section first in the release description.
- Not yet: the agent summary (Duo CLI, T-04) and the pinned issue (F12.3). If T-04 fails, the submission says that Herald is a template.
- Fact (2026-10-19, GitLab docs "Set up the GitLab Duo CLI" and the glab authentication page): headless `duo run` reads an access token from `GITLAB_TOKEN` or `GITLAB_OAUTH_TOKEN`. glab sends that value as `PRIVATE-TOKEN`, which refuses a CI job token. The documented CI pattern uses a service account's personal access token (scopes `api`, `ai_features`). D-010 forbids a personal token of a person in CI, and only a group owner can make a service account. So T-04 is blocked unless the user gives such a token; until then Herald is the template.
- Evidence (2026-10-19): the first run on GitLab, MR pipeline 2961210282, herald job 17270780571 (25 s). `out/herald/who.md` agrees with the signed manifest: `x86-64-v1` held (static), the four emulated CPU models with their variants (x64, sse42, sandybridge, haswell), memory tiny 512, base 512, small 768 MB, a download of 98.4 MB, 0 network attempts, no notice, SCI 0.00196 g CO2e per audio-minute.
- PRD impact: F12.1 runs as a template for now (§9.2 fallback).

## D-026 (2026-10-19) T-35: a notice counts only with a human code-owner approval in GitLab
- PRD F6.1: only a human code owner approves a Leave-Behind Notice; agents and the merge-bot cannot. Until now the ratchet read the "Approved by" line, which is text that an agent can write.
- Fact (2026-10-19): on this public project, `GET /merge_requests/:iid/approvals` answers with no token (checked on MR !2). So a CI job can read the approvals without a token (D-010 holds).
- Decision (`floor ratchet --approvals URL --default-branch BRANCH`, `ratchet.approval`, the check job, tested in `test_ratchet.py`):
  - The check is at the decision point: the MR or push that loosens the policy. The notice MR merged earlier, so its approvals are final.
  - For each notice that would cover a looser change, git finds the commit on the base that added the file. The API gives the merged MR into the default branch that has the commit, and its approvers.
  - Deny by default, as `floor paths` (D-014): every approver must be in `FLOOR_HUMANS`, one must own `/.floor/notices/` in CODEOWNERS (as it is on the base), and the "Approved by" line must name one of them. If git or the API gives no answer, the notice does not count.
  - A notice that fails covers nothing, and the job log says why. A stricter policy needs no notice, as before.
- Not checked on GitLab yet: no notice MR exists. The first test needs a human approval of a real notice MR (a code owner acts; the agent does not).
- PRD impact: none; this makes F6.1 true in CI and not only in the text.

## D-027 (2026-10-19) The probe uses an audio context of 768 frames
- Fact: on the GitLab runners (Intel Xeon Platinum 8581C, 2 vCPUs), the AVX variants of ggml run slowly under QEMU 8.2. Probe job times: SandyBridge 541 to 634 s and EPYC-Milan 2175 s (MR pipeline 2961110649) or more than 2400 s (timeouts in MR pipelines 2961093570 and 2961134355, so 2 of 3 gates failed as cpu inconclusive). On the 2-CPU AMD EPYC 7763 machine of `.floor/evidence/cpu-proof/all-variants` (same QEMU), EPYC-Milan took 562 s and SandyBridge 275 s, with the encoder at about 80% of the time.
- Decision: the probe runs `whisper-cli ... -ac 768`. 768 frames are 15.36 s of audio, and the sample is 11 s, so all the audio is in the context. The encoder then does about half the matrix work and about a quarter of the attention work. The binary and the kernels do not change. The run limit is 2700 s and the job limit 55 min.
- The probe now keeps the partial output and the time of a run that times out (`seconds`, `stderr_tail`), so a timeout shows how far the run got.
- Check: the next fix MR pipeline must show the four probes pass with the reference text, and their times.
- Evidence (2026-10-19): MR !5 (pipeline 2961210282, fix of 2961183840) passed the check. Each probe got the reference text, loaded the expected variant, and had correct controls. Run times (job times): qemu64 136 s (179 s), Nehalem 108 s (155 s), SandyBridge 303 s (439 s), EPYC-Milan 1413 s (1457 s). EPYC-Milan used 52% of the 2700 s limit; before it used 2175 s of 2400 s or timed out.
- PRD impact: F3 (the probe command). The measure (the right text on each CPU model) does not change.

## D-028 (2026-10-19) T-53: the service job records GET /floor until the service is deployed
- PRD F13.4: a `/floor` endpoint reports the x86-64 level of the host CPU and the ggml CPU variant that production loaded, from ggml's load log. The nightly job records it.
- Decision (`gateway.py`, tested in `test_gateway.py`):
  - The gateway reads the stderr of whisper-server, copies each line to its own stderr unchanged, and keeps the first variant that a backend-loader line names (`libggml-cpu-<variant>.so`).
  - The host level comes from the flags of `/proc/cpuinfo`, with the rule of `.gitlab/ci/facts.sh`.
  - `GET /floor` gives `host_cpu`, `host_level`, `ggml_cpu_variant` and the source. With no variant, a note says why: whisper-server is not ready, or its log has no backend-loader line (a build without `GGML_BACKEND_DL` has none).
  - The upload page shows the two values in one line.
- Deviation: there is no deployed service yet (T-06 is parked), so no nightly job. The `service` job of each pipeline asks `GET /floor` after the transcription and keeps `out/service/floor.json`. The job fails if the answer has no host level. The nightly job comes with the deploy (T-51).
- Evidence 1 (2026-10-19): main pipeline 2961779904, service job 17274060434, the upstream image: `host_level` x86-64-v4 (an 8581C, the same as `cpu.txt`), `ggml_cpu_variant` null, with the note about the backend-loader line. That is right for a static CPU backend.
- Evidence 2 (2026-10-19): fix MR !6 pipeline 2961810145, service job 17274238498, the canned image (`GGML_BACKEND_DL=ON`): `host_level` x86-64-v4 (an 8581C), `ggml_cpu_variant` `sapphirerapids`. The loader took the best variant for the host, as expected.
- PRD impact: F13.4 ("the nightly job records it" becomes "the service job of each pipeline records it" until T-51).

## D-029 (2026-10-19) T-23: the backtest footprint counts blob bytes and runner time
- PRD F14.4: the backtest's downloads and CPU time are reported as a one-off footprint.
- Decision (`floor backtest-footprint`, `backtest.footprint`, tested in `test_backtest.py`):
  - Downloads: for each image of the timelines, the sizes of the config blob and the `/app` layer, from the registry manifests. These are the two blobs that `floor image` downloads, and `pull_layer` reads a layer to its end to check its digest. Blobs are content-addressed, so a size read later is the size that the sweep downloaded. Manifests (a few kB) are not counted.
  - Time: the sum of the job times (start to end) of the sweep runs, from `gh run view <id> --json databaseId,jobs`. The job files are kept in `.floor/evidence/backtest/sweep-jobs-<run>.json`.
- Deviation: F14.4 says CPU time. The jobs do not record CPU time, so the footprint gives runner time (job wall time), which is an upper bound per vCPU. No conversion to carbon: the footprint is bytes and minutes only.
- Evidence (2026-10-19): `.floor/evidence/backtest/footprint-2026-10-15.json`: 121 images, 27,470 MB (main 61 images, 9,343 MB, about 153 MB each; main-cuda 60 images, 18,127 MB, about 302 MB each), 18.4 runner-minutes in sweep runs 38700707825 (9 jobs, 476 s) and 38701134589 (8 jobs, 625 s). The Rieux page shows it under the backtest.
- PRD impact: F14.4 (runner time in place of CPU time).

## D-030 (2026-10-19) T-64: the spot check covers the "illegal instruction" hits of whisper.cpp only
- PRD §3.2: "A 20-issue spot check will report the true-positive rate before submission."
- Decision (`floor spotcheck`, `spotcheck.py`, tested in `test_spotcheck.py`):
  - The GitHub search `repo:ggml-org/whisper.cpp "illegal instruction"` found 39 hits on 2026-10-19 (31 issues, 8 pull requests), the same count as the PRD. The sample is 20 of them, drawn with `random.Random(64)`; the command draws it again and fails if the labels are for other issues.
  - Each sampled hit has one label, read from its whole thread: `floor`, `likely`, `unknown` or `not-floor` (the rules are in `spotcheck.LABELS`). A pull request that fixes such crashes is `floor`. Every label has a reason and the issue link, so a person can check it.
- Result: 13 floor, 1 likely, 4 unknown, 2 not-floor. The true-positive rate is 65% (70% with the likely one; at most 90%). The 2 false positives are an Ascend NPU device error and a thread that names the words only in passing.
- Deviation: the labels are a reading of text, not a script result; the file says so. Only the "illegal instruction" count of whisper.cpp is checked. The other keyword counts of §3.2 (old CPU, Raspberry Pi, OOM, quantization) and the 88 llama.cpp hits are not checked, so the README and the Devpost text do not use them.
- PRD impact: §3.2 (the spot check covers one keyword).

## D-031 (2026-10-19) T-62: the language table is one GitHub Actions run per whisper.cpp commit, not a release check
- PRD F9.1: a served / not-served table of languages and model sizes with a usable f16 error rate on FLEURS, their drift at one quantization level, and the unmeasured languages. F9.2: pinned decoding. AC-F9: on the Floor page, with sample sizes and limits.
- Decision (`language.py`, `floor language choose|score|table`, `.github/workflows/language.yml`, tested in `test_language.py` and `test_page.py`):
  - Languages: English (the control), Spanish, Hindi, Bengali, Tamil, Swahili, Hausa and Yoruba (`language.FLEURS`). Sizes: tiny, base and small (multilingual). Quantization: q5_1.
  - Clips: the FLEURS test split, one recording per sentence (the first by file name), a seeded sample (`random.Random(62)`) of 50 sentences per language.
  - Decoding (F9.2): `-l <lang> -nf -bs 5 -bo 5 -t <nproc> -nt`, recorded in the result.
  - Score: corpus WER (all word edits / all reference words) and CER, after one normalizer: NFKC, lower case, no bracketed text, punctuation and symbols to spaces. Combining marks stay, because Indic vowel signs are marks (Whisper's basic normalizer removes them). A clip without a transcript counts as all words wrong. The `-otxt` file has one segment per line, and whisper tokens are bytes, so a segment can end inside a character. Then the line break splits that character, and the file is not UTF-8. `read_hyp` joins such a line to the next one without the break. This was not the main cause of the bytes that are not UTF-8: 56 of 100 Bengali small transcripts and 60 of 100 Yoruba small ones had them in run 39214706460 (before the join), and 57 and 60 in run 39233922646 (with the join). Their cause is not proven: the transcripts are in the run artifacts, and nobody has read them yet. Bytes that are not UTF-8 become U+FFFD, so a space, and the broken word counts as wrong. The result keeps the count (`bad_utf8`), and the page names it without a cause. No verdict depends on it: these rows have an f16 CER of 103% (Bengali small) and 92% (Yoruba small).
  - Drift: q5_1 WER minus f16 WER, with a paired-bootstrap 95% interval (2000 rounds, clips resampled).
  - Served: the f16 WER is at most `language.usable_wer` in the policy, 0.30: above that, about one word in three is wrong, and a reader cannot rely on the text. The table also shows when q5_1 crosses the line.
  - Not measured: every other language of whisper.cpp's `g_lang` table (`src/whisper.cpp`).
- Evidence: run 39233922646 (whisper.cpp 0c7be696, 50 sentences per language), `.floor/evidence/language/language.json`. The English control is low: f16 WER tiny 14.2%, base 9.3%, small 7.6%. Served at every size, at f16 and at q5_1: English and Spanish (f16 WER tiny 18.0%, base 12.4%, small 8.2%). Not served at any size: Hindi (small 58.6%), Tamil (small 72.9%), Swahili (small 77.4%), Hausa (small 90.6%), Bengali and Yoruba (above 100%: the transcripts have more words than the references). Not measured: 92 other whisper languages.
- Deviation: the table is not made per release. One run takes about 25 runner-minutes per language, so the gate does not run it. The manifest still lists `language` as not measured, because the release check did not measure it. The page names the commit of the run. No gate uses the table (F9.3 is a COULD).
- PRD impact: F9.1 (the table is per whisper.cpp commit, not per release).

## D-032 (2026-10-19) T-61: the release summary goes from the herald job log to the pinned issue by a flow
- PRD F12.3: a summary of at most 8 lines goes on a pinned issue after each release.
- Fact: CI has no token that can post a note (D-010, D-025). The flow tools read job logs, not artifacts (D-021).
- Decision (`herald.summary`, `floor summary`, the `herald` job, `.floor/flows/release-summary.yml`, tested in `test_herald.py` and `test_flows.py`):
  1. `floor summary` makes at most 7 lines from the signed manifest and `out/herald/who.md`: a head line (decision, commit, image digest, Pareto, SCI), one short line each for CPU, memory and connectivity from the manifest, and the Language, "Left behind" and "Not measured" lines of `who.md` as they are. More than 7 lines is an error.
  2. The `herald` job prints `summary issue: $FLOOR_SUMMARY_ISSUE` and the summary between `--- BEGIN summary ---` and `--- END summary ---`. `FLOOR_SUMMARY_ISSUE` (in `.gitlab-ci.yml`) is the IID of the pinned issue. Empty means "post nothing".
  3. The flow: the trigger "Pipeline events: Passed" starts it. `gate` (no tools) answers "passed" only for a passed default-branch pipeline whose `release` and `herald` builds passed. `post` (tools `get_job_logs`, `create_issue_note`) stops unless the release log has a `released:` line, so a pipeline that made no release posts nothing. It copies the summary as it is and adds one line with the tag: `Release: `<tag>` (pipeline <id>).` So the note has at most 8 lines.
- Why the tag line is the agent's: the release job, not the herald job, knows the tag, and it runs after herald. The agent copies the tag from the `release <tag> from` line. It writes no floor value (F5.1).
- Saved on 2026-10-20: private AI Catalog flow 1018933 "Rieux release summary" (1.0.0). Its stored definition has the same SHA-256 as `.floor/flows/release-summary.yml` at dev 9782ee2. The tool names `get_job_logs` and `create_issue_note` are in the catalog's built-in tool list (GraphQL `aiCatalogBuiltInTools`). Enabled with the one condition "Pipeline events (Passed)", on.
- Not proven yet: whether "Pipeline events: Passed" fires for a pipeline that an auto-merge started (only an action by a person fires a trigger, D-021). A local session checks both on the first release.
- Done on 2026-10-20 (owner's yes): GitLab has no pin action for issues. So "the pinned issue" is issue #2 "Rieux release summaries" of the Showcase project. `FLOOR_SUMMARY_ISSUE: "2"` is in `.gitlab-ci.yml`, and the README links the issue.
- PRD impact: F12.3 (the note is posted by a flow, not by CI; a linked issue, not a pinned one).

## D-033 (2026-10-19) T-63: the field triage flow answers from the gate's proof; it runs no new reproduction
- PRD F11.1: a flow on the work-item-created trigger classifies floor symptoms (illegal instruction, exit code 132, OOM, language accuracy). F11.2: it reproduces the problem on the matching CPU model and replies with the working artifact and proof; it asks for `ld.so --help` output when the CPU is unknown.
- Fact: a flow has no runner and no tool that runs QEMU. The gate already runs the four probe models (qemu64, Nehalem, SandyBridge, EPYC-Milan) for every release, and the signed manifest records the ggml CPU variant that ran on each (`dispatch`).
- Decision (draft, `.floor/flows/field-triage.yml`, tested in `test_flows.py`): `gate` (no tools) answers "cpu", "memory", "language" or "skip". `reply` (tool `create_issue_note` only) maps the reporter's CPU to a probe model by a fixed table, points to the latest `-floor` release and its "Who this release serves" part, and asks for `/lib64/ld-linux-x86-64.so.2 --help` and the CPU model when the CPU is unknown. It states no floor value.
- Deviation: no new reproduction per issue. The proof is the probe run of the release, not a run made for the issue.
- Checked on 2026-10-19 (local session, the new-trigger form of the Showcase project, nothing saved): the event "Work item" ("when a project-level work item is created or its status is updated") has the actions "Created" and "Status changed". So the planned trigger is "Work item: Created". The same form lists "Pipeline events" with "Running", "Passed", "Failed" and "Canceled" (T-61 uses "Passed").
- Saved on 2026-10-19: private AI Catalog flow 1018718 "Rieux field triage" (Showcase project, version 1.0.0). The stored definition has the same SHA-256 as `.floor/flows/field-triage.yml` at 5b65195. The form sends `aiCatalogFlowCreate(input: AiCatalogFlowCreateInput!)` with `projectId`, `name`, `description`, `definition` and `visibility` (PRIVATE). "Enable" in the project made the trigger "Auto-created triggers for Rieux field triage" with the one condition "Work item (Created)", and it is on. The three default conditions (Mention, Assign, Assign reviewer) were removed before Enable. The flow runs as its own service account (Developer).
- Not proven yet: the shape of the work-item event in `context:goal`, and that a component input can take `context:gate.final_answer` (the routers of `floor-repair.yml` can, D-021). AC-F11 proves both: a test issue, then the session log and the note.
- Negative check (2026-10-20): issue #2 ("Rieux release summaries", not about a floor) started session 9777724 (CI job 17329007768, about 54 s). The gate answered "skip", and `reply` did not run (no `create_issue_note`). So the router works on the work-item event. The platform posts its own note "<flow> has started" and a start and a complete system note on each new work item, also when the flow answers nothing.
- AC-F11: the owner said yes to one test issue (2026-10-20), at the end of the project, with real data (the measured crash of the upstream image under QEMU SandyBridge). No canary issues before that.
- PRD impact: F11.2 (the proof is the release's probe run).

## D-034 (2026-10-20) T-99: a public decisions file in `.floor/`; no team IDs in the GitLab files
- Fact (T-99 check, STATE item 7): 83 files that go to GitLab cited IDs that a reader there cannot open (D-0xx, PRD, T-xx, F- and AC-numbers).
- Owner decision: option (a), a short public decisions file.
- Decision: `.floor/DECISIONS.md` (public) defines every ID that a Rieux file cites: the requirements (F-numbers, NFR-7), the acceptance checks (AC-F), the plan sections (§), the plan terms (H-1, R1, R2, G7) and a short public form of the decisions D-010 to D-033 that the files cite. The T-xx task IDs, "PRD " and "DECISIONS " are removed from the product files (58 files). `.floor/tests/test_ids.py` fails when a product file cites an ID that the public file does not define, or cites a T-xx, PRD or G-n ID.
- Rule: a new D-ID cited in a product file needs its public entry in `.floor/DECISIONS.md` in the same commit. The internal records (this file, TASKS, STATE) keep their full text.
- Effect on the catalog: the four flow files changed in their header comments only. On 2026-10-20 the stored catalog definitions were updated: floor repair 1018643 is 1.3.0, field triage 1018718 is 1.1.0, trigger probe 1018639 is 1.2.0. Each has the same SHA-256 as its file at dev 9782ee2. The task IDs were also removed from the catalog descriptions of floor repair and trigger probe.
- Miss (main pipeline 2969295146, GitLab `61c5075f`): the comment change in `.gitlab/ci/tools.Dockerfile` changed its hash, so `check.sh` failed (TOOLS_TAG 348395c3ee88, recipe 7b72645f2a09). The judge failed as planned (cpu raised; memory and connectivity held). Fix: TOOLS_TAG 7b72645f2a09 and `test_tools_tag_is_the_recipe_hash` in `test_qemu.py`, so pytest catches it before a sync. The build job builds the new tools image once.
- Miss 2 (main pipeline 2969339383, GitLab `f8945f0d`, dev 146abdc): `test_no_internal_ids` failed on GitLab in `.floor/overrides/README.md` and `deploy/service.Dockerfile`. These paths are agent-owned (`AGENT_ALLOWED`), and the sync script always kept GitLab's copy there, so the cleaned dev text never arrived. Fix: the sync keeps a GitLab file there only when the last GitLab commit that changed it is not a sync commit (an agent change, such as a merged fix MR). A file that only syncs wrote now follows the dev HEAD. (A first try compared the GitLab blob with the dev blob of the last sync; that fails here, because the last sync did not write these files.) The judge failed as planned again.
- PRD impact: none (documentation).

## D-035 (2026-10-21) T-56: sourced CPU ΔM scenarios, shown on the page and filtered in notices
- Fact: ΔM (claim N4) was a calculator and a template only. No scenario had sourced values, and the page did not show ΔM.
- Decision: two scenario files, `.floor/scenarios/cpu-v3.yml` (x86-64-v1 -> v3, the folk fix) and `cpu-v4.yml` (v1 -> v4, upstream's recipe on an AVX-512 machine). N is per 10,000 x86 users (a unit, not a count of real users), from the Steam Hardware Survey (September 2026, and August from the change column): no BMI2 among SSE2 machines for v3 (245 to 286, a lower bound), no AVX512F for v4 (7207 to 7565). e is manufacture plus transport from two Dell product carbon footprints (123.4 to 230.9 kg). L is 4 to 5 years (the same sheets). Δ: v3 0.5 to 2 years (the Celeron N4020 has SSE4.2 only, Q4 2019); v4 0.5 to 5 years (the Core Ultra 7 155H, Q4 2023, has no AVX-512). p is 1%, 2%, 5%. Results: v3 30.2 to 1650.9 kg CO2e, v4 889.3 to 87,337.9 kg CO2e.
- Decision: `delta_m.fits()` keeps a cpu scenario in a notice only when its change ends at the measured level, so a notice never shows the ΔM of another level. The page has a ΔM section after SCI: each scenario with its range, the p sensitivity and its file. The README Footprint paragraph gives both ranges and the sources.
- Not done: a memory scenario. The Steam proxy (0.02% under 4 GB) does not count the 1 GB devices and small VPS that a 768 MB floor would affect, so no sourced N exists yet.
- Public entry: none needed. No product file cites D-035.
- PRD impact: F14.3, §13.3 (sourced demo values for CPU).

## D-036 (2026-10-21) The repair loop on the Rieux page
- Fact: the page (the deployed URL for now) did not show the repair loop, which is the core of the Hands-off story. The proof was only in the MR list.
- Decision: `floor repairs --api --project --out` reads the public GitLab API (no token) and writes `.floor/evidence/repair/repairs.json`: for each `floor-fix/<pipeline>` MR, the failed pipeline and its judge, the minutes from the pipeline end to the MR, and the latest MR pipeline with its judge. `notes.json` holds a note, written by a person from the job logs, for each gate that failed (MRs !1, !2, !4: harness, D-022 and D-027; !8, !9: check failures on old main commits). The page shows a table after the CPU proof.
- The file is a dated snapshot, committed like the other evidence. The pages job does not call the API.
- Measured (2026-10-21): 10 fix MRs; 8 under 3 min (median 2.2, slowest 8.9); the judge passed in 7 MR gates; none merged.
- Public entry: none needed. No product file cites D-036.
- PRD impact: F12.2 (the page shows F4 on GitLab).

## D-037 (2026-10-21) The notice path with a real trade-off (option a)
- Fact: the canned config held every floor, so `notice-draft` never wrote a notice. PRD §16.2 asks for at least one Leave-Behind Notice, and only a human may decide a raise.
- Decision (owner: option a): one MR in the owner's name removes `libggml-cpu-x64.so` (ggml's baseline variant, 985,528 bytes) from the main image, on top of the canned config. The trade-off is real: that code needs 15.1x the CPU time of the variant a modern CPU loads (energy run 39033747472), and the floor rises to x86-64-v2. The gate fails, the fallback has nothing to add, and `notice-draft` writes the notice with ΔM from `.floor/scenarios/cpu-v2.yml`. The owner refuses it by closing the MR. The MR text says why it was opened.
- `cpu-v2.yml`: N 11–12 per 10,000 x86 users (Steam September 2026: 1 - 98.21/98.32; August: 1 - 98.03/98.15), the Dell e and L values of D-035, Δ 0.25–1 year (the newest affected 64-bit CPUs are from about 2012, for example the Atom N2800, Intel ARK). ΔM 0.7–35 kg CO2e. The page shows one decimal below 10 kg.
- Outcome (2026-10-21): the gate of MR !13 (pipeline 2970472763) failed as planned, `fallback` made no patch, and `notice-draft` (job 17337464293) wrote the draft with ΔM 0.679–34.6 kg CO2e. On qemu64 the image stopped with SIGABRT, not SIGILL: without the x64 variant ggml finds no CPU backend that it can load. The owner refused: a comment, then "Close merge request" at 07:51:27Z. Recorded in `.floor/evidence/notice/` and on the page (`_section_notices`).
- Public entry: none needed. No product file cites D-037.
- PRD impact: F4.5, F6, §16.2 (loop 3: the notice).

## D-038 (2026-10-21) H-1 on GitLab: `floor runners`
- Fact: the build job of main pipeline 2970859268 (dev 7b44fab, GitLab `86e5dc5d`) ran on an AMD EPYC 7B13 (no AVX-512), so the image got x86-64-v3. The main pipelines before it ran on an Intel Xeon Platinum 8581C and got x86-64-v4. The README said "the GitLab runner has AVX-512".
- Decision: `floor runners --api --project --web --out` reads the public GitLab API and the raw job logs (no token; the trace API needs one) and writes `.floor/evidence/runners/runners.json`: for each main pipeline, the build machine ("build machine:" line of the build job) and the CPU floor (the judge table). For each floor change between two pipelines next to each other, the compare API lists the changed files in the build inputs (h1.FLOOR_PATHS plus `.gitlab-ci.yml`, a strict choice). The page shows it as a card in the H-1 section.
- Measured (2026-10-21): 21 main pipelines, 19 on the Intel runner (v4), 2 on the AMD runner (v3: 2969163382 and 2970859268). In all 21 the floor equals the level of the build machine. 3 floor changes; 1 with no change to the build inputs (0f7d064e to 86e5dc5d: 1 commit, 7 files, all in `.floor/` and `README.md`). The other 2 changed `.gitlab-ci.yml`, so the strict rule counts them as explained.
- Side fact: QEMU on the AMD runner ran the EPYC-Milan probe of MR !15 in 353 s (the Intel runners: 1156 to 1464 s).
- Public entry: none needed. No product file cites D-038.
- PRD impact: F10.3 (H-1 on the submission project itself), F12.2.
