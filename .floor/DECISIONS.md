# Rieux: requirements and decisions

The code, the CI file and the docs of Rieux cite short IDs in brackets, for example `(F4.3, D-018)`. This file tells what each ID means.

| ID form | Meaning |
|---|---|
| `F4.3`, `F4` | A requirement of the Rieux product plan. `F4` is the group. |
| `AC-F4a` | An acceptance check of a requirement group |
| `NFR-7` | A non-functional requirement |
| `§9.2` | A section of the product plan |
| `D-018` | A design decision: what we chose, why, and the evidence |
| `H-1`, `R1`, `R2`, `G7` | A term of the product plan |

The product plan is a working document of the team. It is not in this project, so the tables below give, in short, the parts that the files cite. The decisions are the ones that the files of this project need, so the D-numbers have gaps. `.floor/tests/test_ids.py` fails when a file of this project cites an ID that this file does not define.

## Requirements

| ID | Requirement |
|---|---|
| F1.1 | `.floor/policy.yml` sets the floors per dimension and per published artifact. CI checks it against a JSON Schema. |
| F1.2 | The policy is a ratchet: a stricter floor needs a normal MR, and a looser floor needs a merged Leave-Behind Notice. The policy, the schema, the Judge, CODEOWNERS and the gate CI need code-owner approval. |
| F2 | CPU floor: the static scan. |
| F2.1 | Scan every loadable ELF file: programs, shared libraries, and the ggml backend variants that load at run time (found by a file search, not by `ldd`). The floor is the highest x86-64 level in the code that always loads, joined with the baseline variant. |
| F2.2 | An allowlist of known false positives (for example `rep bsf`, which decodes as `tzcnt`), with tests. Record the build flags, the base-image digest and the highest level found anywhere. |
| F3 | CPU floor: runs of the image under an emulated CPU. |
| F3.2 | Each emulated CPU model gets a negative control (it must fail) and a positive control (it must pass), or the result is inconclusive. A pass gives the reference transcript. SIGILL, a glibc CPU refusal, an abort or wrong text are failures. |
| F4 | The repair loop. |
| F4.1 | The repair flow starts on the pipeline-failed trigger when the Judge marks a floor raised. The person who pushed the tag (or the MR author) is the human actor. |
| F4.2 | The agent reads the Judge's evidence and the build files, states the cause in the MR, and changes only the paths of its allowlist: `deploy/`, `.devops/*.Dockerfile` and `.floor/overrides/`. None of these paths has a code owner. |
| F4.3 | If the agent's fix fails, a script applies the canned inclusive config to the same branch: `GGML_NATIVE=OFF`, `GGML_BACKEND_DL=ON`, `GGML_CPU_ALL_VARIANTS=ON`, `BUILD_SHARED_LIBS=ON`. Then the gate checks again. |
| F4.4 | When every floor holds and no code-owned path changed, the fix merges, and a release job cuts `-floor.N` from the merged commit. (The plan had a merge-bot token for this; D-010 replaces it.) |
| F4.5 | One agent attempt per human action. If the fallback also fails, a script writes a draft Leave-Behind Notice with the agent's diagnosis, and the loop stops. |
| F5 | The Judge and the Floor Manifest. |
| F5.1 | The Judge is a tested script. It marks each floor held, lowered, raised or inconclusive. A language model never sets a status. |
| F5.2 | Pareto rule: a change is inclusive only if no floor rises on any dimension. A mixed change is a trade-off, and it needs a notice. |
| F5.3 | Write `floor-manifest.json` and a diff against the previous release, with the dimensions and languages that were not measured. |
| F5.4 | Sign the manifest as an in-toto attestation on the image digest (`cosign attest`, keyless, with the GitLab OIDC token), and attach it to the GitLab Release. |
| F6 | Leave-Behind Notices. |
| F6.1 | A raise or a trade-off that has no inclusive fix needs a notice MR from the template (§11.2). Code owners approve it. Agent accounts cannot approve or merge it. |
| F6.2 | A merged notice goes into the release notes and the manifest. |
| F6.3 | The default is `on_unfixable_raise: ship_last_held`: production keeps the last held build until a person decides. |
| F7 | Memory floor. |
| F7.1 | Transcribe with each model size under limits of 512, 768, 1024, 1536, 2048 and 4096 MB, with swap equal to the limit (that is, no swap, D-014), and record pass or fail and the peak RSS. Report a peak-RSS rise over 10%. A move past a policy limit is a raise. |
| F8 | Connectivity floor. |
| F8.1 | Transcribe with no network while the network system calls are traced. Any attempt fails the run. Record the download size of each artifact and model. |
| F9.1 | A served / not-served table: the languages and model sizes with a usable f16 error rate on FLEURS, their drift at one quantization level, and the languages that were not measured. |
| F9.2 | Pinned decoding: a forced language (`-l`), no temperature fallback (`-nf`), fixed threads and beam size. |
| F9.3 | A language gate. It is optional, and Rieux does not have it. |
| F10.1 | Scan at least 30 published upstream images (the `/app` layer): a sample of the `main-<sha>` tags, and every image near the crash reports #3510 and #3814. |
| F10.3 | Test H-1 against the changes to the Dockerfile and to ggml's CPU code, and state the verdict with the evidence. |
| F11.1 | A flow on the work-item-created trigger sorts floor symptoms: illegal instruction, exit code 132, out of memory, language accuracy. |
| F11.2 | It reproduces the problem on the matching CPU model and answers with the working artifact and the proof. It asks for the `ld.so --help` output when the CPU is not known. (D-033 changes the proof.) |
| F12.1 | The release notes get a "Who this release serves" section, made from the manifest by the Herald CI job, for every release. |
| F12.2 | A public Floor page: the floor history with the backtest and the H-1 verdict, the runs on emulated CPUs, the language table, SCI and the notices. |
| F12.3 | A summary of at most 8 lines on a pinned issue after each release. |
| F13.1 | whisper-server runs on Cloud Run in a low-CO₂ region from the signed, held image. OpenTofu is in the repo, and CI uses Workload Identity Federation. |
| F13.2 | A new revision goes to staging first, passes a smoke test, and only then takes the production traffic. A failed check leaves the previous revision in production (the rollback). |
| F13.3 | The upload page caps the audio at 30 seconds, limits the requests and the instances, and stores no audio. |
| F13.4 | A `/floor` endpoint reports the x86-64 level of the host CPU and the ggml CPU variant that loaded, from ggml's load log. |
| F14.1 | SCI per audio-minute for the service (R1) and per release check (R2), with Green Software Foundation Impact Framework manifests in the repo. |
| F14.2 | Measured levers, in this order: the energy per audio-minute of the native, folk-fix and all-variants builds on the same hardware; cheap-first probing; quantization; region. |
| F14.3 | ΔM for each notice, beside SCI, as a scenario range. |
| F14.4 | The downloads and the CPU time of the backtest, as a one-off footprint. |
| NFR-7 | Privacy: no telemetry. Uploaded audio stays in memory and is never stored. |

## Acceptance checks

| ID | Check |
|---|---|
| AC-F2 | A native build scans at v3 or above. A `GGML_NATIVE=OFF` build scans near v3. An all-variants build scans at v1 for the core code and the baseline variant. |
| AC-F3 | The default and the `GGML_NATIVE=OFF` builds fail on Nehalem and SandyBridge. The all-variants image passes on all four CPU models. The negative controls fail. |
| AC-F4a | A tag built with upstream's default flags ends as a live `-floor.1` release with the CPU floor held, and no person acts after the tag push. |
| AC-F5 | Two releases give two attestations and a readable diff, and `cosign verify-attestation` passes. |
| AC-F7 | The manifest lists the smallest passing memory limit and the peak RSS for each model size. |
| AC-F8 | The manifest states `offline: proven`, links the job, and lists the download sizes. |

## Sections of the product plan

| ID | Section |
|---|---|
| §3.2 | Evidence: the upstream crash reports, and the keyword counts of a whisper.cpp issue search. A 20-issue spot check gives the true-positive rate of the counts (D-030). |
| §3.6 | Hypothesis H-1. |
| §5 | Goals and non-goals. A non-goal: agents never change engine code (`src/`, `ggml/`, `include/`, `examples/`). |
| §7.1 | The release loop: a person pushes a tag; then the build, the static gate, the emulated runs and the Judge; then the repair, or the attestation and the release. |
| §9.1 | Platform limits. Only an action by a person fires a flow trigger; bots, service accounts and other flows cannot. So a flow makes at most one attempt per human action. |
| §9.2 | Who does what. Scripts decide: the scans, the emulated runs, the memory and offline runs, the Judge, the manifest, the attestation, the fallback config, and the SCI and ΔM arithmetic. Agents diagnose and write. No model output can change a floor status. |
| §10.1 | Gate integrity: code-owner approval for the policy, the Judge, the schema, CODEOWNERS and the CI file. The path allowlist job is defense in depth, not the main control. |
| §11.1 | The Floor Manifest, an in-toto Statement. |
| §11.2 | The Leave-Behind Notice template. |
| §11.3 | The policy file, `.floor/policy.yml`. |
| §13.1 | Standards: SCI (ISO/IEC 21031:2024), SCI = (E × I + M) / R, with Impact Framework manifests. The carbon intensity is location-based, with no offsets. |
| §13.2 | The measured levers. Lever 5 is the region: the same work in the chosen low-CO₂ region and in a common default region. |
| §13.3 | ΔM, a consequential indicator beside SCI: ΔM = N_affected × e × p × (Δ / L). |
| §13.4 | Honesty rule: small numbers stay as they are, every number comes from a script in the repo, and a scenario is never shown as a measurement. |

## Terms

| ID | Meaning |
|---|---|
| H-1 | The hypothesis that the CPU floor of an upstream image depends on the CI machine that built it. |
| R1 | The SCI functional unit "one audio-minute transcribed by the service". |
| R2 | The SCI functional unit "one release check" (all the probes of one release). |
| G7 | The goal "the cost of inclusion is known": the energy per audio-minute of the native, folk-fix and all-variants builds on the same hardware. |

## Decisions

### D-010 Merge path: GitLab auto-merge, no merge-bot token
- Fact (2026-10-16): the team role in this project is Developer+. It can push and merge to `main`, run pipelines and manage AI Catalog items. It cannot make project access tokens, change protected branches or tags, or manage runners. So the merge-bot of F4.4 (a project access token) is not possible.
- Decision: the fix MR merges by GitLab auto-merge ("merge when the pipeline succeeds"), so GitLab merges only when the gate pipeline passes. A release job on `main` cuts `-floor.N` with `CI_JOB_TOKEN` (D-024).
- No personal access token in CI. A personal token acts as the human code owner, so CI could then approve and merge a notice (against F6.1), and every merge would look human-made.
- Code-owner approval on `main` needs a Maintainer. So `floor paths` fails the MR pipeline when an agent account changes a code-owned path (D-014).
- Status on 2026-10-21: the project setting "Pipelines must succeed" is off, and the flow tools have no merge tool. So no fix MR has merged on its own yet.

### D-012 The project is whisper.cpp at a pinned commit, with its full history
- The project is whisper.cpp at commit `0c7be696371069e0baa2515ed7aa08d5a5473aa6` (2026-10-15) with its full history, plus the Rieux files. `.floor/upstream.env` holds the pin.
- Why: `git log` shows where upstream ends and Rieux starts.
- After the import, the one change to an upstream file is the move of whisper.cpp's README to `README.whisper.cpp.md`, so the Rieux README is the front page.

### D-013 Product name: Rieux
- The name comes from Dr. Bernard Rieux in Albert Camus's *The Plague* (1947). He does the work without heroics, keeps an honest record, and knows that the danger comes back.
- "Floor" is the name of what Rieux measures. The code names stay: the Python package `floor`, the `.floor/` folder and the `floor` commands.

### D-014 The GitLab gate pipeline
- Jobs: `check`, `build`, `scan`, `probe` (one job per CPU model), `memory`, `offline`, `service` and `judge`. After a failed judge: `fallback` and `notice-draft`. After a passed judge: `attest`, `herald` and `release`. Then `pages`.
- `build` builds upstream's `.devops/main.Dockerfile` with no change and pushes the image to the project registry. The later jobs use the image by its digest, so the gate checks the bytes that ship.
- The first `main` pipelines are red, and that is the honest start. Upstream's recipe keeps `GGML_NATIVE` ON, so the floor is the CPU of the runner (v3 or v4), and the policy says v1. So the Judge says "raised". The repair loop (D-021) makes the fix branch green.
- `scan`: `crane export` writes the image to `rootfs/`, and `floor scan` scans it. The build flags come from `/app/build/CMakeCache.txt` in the image (the values in effect), not from the Dockerfile text.
- `probe`: `whisper-cli` from the image runs under `qemu-x86_64 -cpu <model> -L rootfs` on qemu64, Nehalem, SandyBridge and EPYC-Milan, with the controls of F3.2. First, the absolute links in the image become relative, so QEMU cannot load a file of the host.
- `memory` and `offline` run the image's own programs natively with `chroot` into the exported image. `memory` gives each run its own child cgroup with `memory.max` and `memory.swap.max` = 0. "Swap equal to the limit" (F7.1) means no swap, as in Docker's `--memory-swap`. `offline` uses `unshare --net` (the same isolation as `--network none`) under strace.
- The manifest has `predicate.build.host_cpu`, which is not in §11.1. It records the CPU of the build machine, the cause in H-1.
- Path allowlist (F4.2, §10.1): deny by default. On an MR pipeline, the MR counts as an agent MR unless the pipeline user and the MR author (from the API, with no token) are both in `FLOOR_HUMANS`. Then `floor paths` fails the pipeline when the MR changes a path outside the agent allowlist. Known gap: an MR pipeline runs the `.gitlab-ci.yml` of the MR, so an agent MR can change the gate itself. Only code-owner approval or a pipeline execution policy can stop this, and our role can set neither. The tool limits of the flow are the main control, and the MR diff shows each such change.
- Costs: Docker-in-Docker has no layer cache, so each build compiles whisper.cpp again. Each pipeline pushes a new image (the `/app` layer is about 150 MB).

### D-015 R2: each GitLab job meters its own container
- The runner runs each job in a Kubernetes pod, and `/proc/stat` in the job shows the whole node. So `floor meter` reads the cgroup v2 group of the job: the CPU time from `usage_usec` of `cpu.stat`; the memory as `memory.current` minus `inactive_file` (as in Kubernetes); the vCPUs from `cpu.max`, or else the CPUs that the job can use.
- The jobs `scan`, `probe`, `memory`, `offline` and `judge` start the meter in `before_script`. An EXIT trap writes `out/meter/<job>.json`, also after a failed command. The judge job adds them into `out/judge/meter.json`.
- Watts: the CCF row of the CPU that the meter saw (an Intel Xeon Platinum 8581C in pipeline 2958309699), or else the GCP average.
- Not counted: `check`, `build`, `pages`, the helper container, `pip install` and the wait for a runner. So R2 is a lower bound for the pipeline.
- The meter never changes a floor or a job result.

### D-016 The draft notice is a job artifact
- CI has no token that can open an MR (D-010). So `floor notice-draft` writes the draft of F4.5 as an artifact of the `notice-draft` job, and a code owner opens the notice MR from it.
- It writes a draft only when a floor moved with no merged notice, and the canned config is already on the branch (or the policy has `repair.fallback: none`). So the order stays: the agent's fix, then the fallback, then the draft.
- The script fills a field only from evidence. The MR description is agent text: its summary is HTML-escaped and cut at 300 characters, and the full text is an indented code block, so it cannot add a field line or an approver. "Approved by" stays a placeholder (F6.1).

### D-018 F4.3: the fallback job keeps a patch, and the flow or a person commits it
- F4.3 says that a CI script applies the canned config "to the same branch". CI cannot push: there is no project or personal token in CI (D-010). A push with `CI_JOB_TOKEN` needs a setting that only a Maintainer can turn on, and it starts no pipeline.
- Decision: the `fallback` job runs `floor fallback --judge out/judge/judge.json --patch out/fallback/fallback.patch`. It keeps the patch as an artifact and prints it in its log. The flow (D-021) or a person commits it. The push starts the next MR pipeline, and that pipeline is the gate's new check.
- The patch is script output, so no model output decides the config (F5.1). It changes only allowlist paths.
- Gap: one more push is necessary. The hands-off claim holds only when the flow makes it.

### D-019 F13.3: a code-owned gateway in front of whisper-server
- whisper-server reads its parameters from the request form and has no rate limit. With `--convert`, it writes each upload to a temp file. So whisper-server cannot be the public port.
- Decision: `.floor/floor/gateway.py` (standard library only) is the public port. whisper-server listens on 127.0.0.1:8081 with no `--convert`, so it decodes the audio in memory.
- The browser makes 16 kHz mono 16-bit WAV, so the gateway checks the length from the WAV header with no decoder. Limits: at most 30 s; a body cap of 964,096 bytes, checked before the body is read; 6 requests a minute per client; 30 a minute per instance; one transcription at a time per instance.
- The gateway sends only fixed parameters and the audio. Privacy (NFR-7): no file, and the log has only the method, the path and the status.
- The gateway is code-owned (`.floor/`), so the repair agent cannot weaken the limits. `deploy/service.Dockerfile` builds FROM the held image and adds only python3 and the gateway files.

### D-020 Flows live in `.floor/flows/`, and the catalog copy equals the file
- Test (2026-10-19): a person started a pipeline on `main` (pipeline 2960962126). It failed at the judge as planned. The trigger "Pipeline events: Failed" started the private AI Catalog flow "Rieux trigger probe" in about 30 s. The session names the person as the actor, and the flow runs as its own service account.
- `context:goal` is the full pipeline event. So the first step of a flow can read "the judge failed" from the event, with no tool call.
- Catalog facts: the create form puts an example flow in the editor, and a first save kept it below our YAML. The schema refuses `max_cycles` on a component. Each save makes a new version.
- Decision: each flow definition is a file in `.floor/flows/`, code-owned, with a test (`test_flows.py`). After each save, we read the stored definition back and compare it with the file. The repair agent cannot change a flow.

### D-021 The floor-repair flow
- §9.2 wants the exit step ("exit unless the Judge said raised") and the MR step to be deterministic. A deterministic flow step runs one tool with inputs taken whole from the flow state. It cannot take one field out of the pipeline event, and a router matches exact strings only. So these two steps are agent steps with fixed rules.
- `.floor/flows/floor-repair.yml`:
  1. `gate`: an agent with no tools. It answers "raised" only when the event says that the pipeline and its `judge` build failed and the ref is not a `floor-fix/` branch. The router starts `repair` only on the exact string "raised". A wrong answer costs one run, and it cannot weaken the gate.
  2. `repair`: an agent with five tools (`get_job_logs`, `get_repository_file`, `create_branch`, `create_commit`, `create_merge_request`). It stops unless the judge log says "Pareto: raised". It copies the patch of the `fallback` job (D-018) from the job log and applies it to the files at the pipeline commit. It commits to `floor-fix/<pipeline>` and opens an MR into the ref (or it commits to the MR source branch on an MR pipeline).
- The `fallback` job prints the patch between `--- BEGIN fallback.patch ---` and `--- END fallback.patch ---`, because the flow tools read job logs, not artifacts.
- F5.1 still holds: the judge script sets every floor, the agent applies a patch that a script wrote, and the MR pipeline runs the whole gate again.
- The flow's fix is the canned config. A free-form agent fix is cut, because the canned config is the fix that the CPU proof showed to work.
- First run (2026-10-19): pipeline 2960990129 failed at the judge, and the flow opened MR !1 in about 2 minutes. Its 8 files equal the output of `floor fallback` byte for byte. The commit author and the MR pipeline user are the flow's service account, so the `check` job counted it as an agent and allowed the 8 paths (D-014).

### D-022 The gate harness: /proc in the chroot jobs, and 2 threads under QEMU
- MR !1 ran pipeline 2961002610 on the canned image. `memory` and `offline` ended with exit -11 after `GGML_ASSERT(device)`: ggml loaded 0 backends. EPYC-Milan stopped at the 1800 s run limit.
- Cause 1: with `GGML_BACKEND_DL=ON`, ggml finds its CPU backends through `/proc/self/exe`. A container runtime gives the image a `/proc`, and `chroot` does not.
- Cause 2: the runner has 2 vCPUs. With 4 threads, the threads spin at each barrier and use emulated CPU time for no work.
- Decision: `memory` and `offline` mount `/proc` in the exported image before the first run. `probe` runs with `-t 2`.
- The measures and the floors do not change. MR !3 (pipeline 2961110649) then held every floor.

### D-023 F5.4: the `attest` job signs the manifest after a passed judge
- The job runs after `build` and `judge`, only when the judge passed.
- Keyless: the job asks GitLab for an ID token with the audience `sigstore`. cosign trades it for a short-lived Sigstore certificate, and the public Rekor log records the signature. The certificate identity is the pipeline definition at the ref. The job never prints the token.
- After the signature, `cosign verify-attestation` checks the exact identity and the issuer, and `floor attest check` compares the verified predicate with the manifest. `out/attest/verify.txt` has the verify command.
- cosign v2.6.5, downloaded from its release with a pinned SHA-256 check.
- Evidence: MR pipeline 2961110649, attest job 17270217868: signed and verified. MR pipeline 2961210282, attest job 17270780570: signed and verified again.
- Not yet: the attachment to a GitLab Release, and two releases with a diff (AC-F5).

### D-024 F4.4: the release job cuts `<tag>-floor.N` only after a merged fix of a tag
- The job runs on the default branch after `judge` and `attest`, so only when the gate held and the manifest is signed.
- `floor release` (a script) decides. The commit must be the merge of a `floor-fix/<pipeline id>` MR, and that pipeline must be a tag pipeline. Then the release is `<tag>-floor.N`, where N is one more than the highest N of that tag. Any other commit gets no release, and the job passes.
- The job posts to the Releases API with `CI_JOB_TOKEN`. The description has the floor diff, the fix MR and the cosign verify command.
- No pipeline runs for a `-floor.N` tag: the default-branch pipeline of the same commit already proved and signed it.
- Not yet run: no tag pipeline has had a merged fix.

### D-025 F12.1: Herald is a template
- The `herald` job runs after `judge` and `attest`, so only for a signed manifest. It writes `out/herald/who.md`, and the `release` job puts it first in the release description.
- Every value comes from the manifest: the CPU level in plain words, the emulated CPU models that ran (with the ggml variant), the smallest memory limit per model, the offline download and the network attempts, the notices, what is not measured, and SCI. If a floor rose, it says that the gate blocks the build.
- The agent part (a short summary by the GitLab Duo CLI in CI) needs the access token of a service account. Only a group owner can make one, and a person's token in CI is against D-010. So Herald is the template of §9.2 for now.
- Evidence: MR pipeline 2961210282, herald job 17270780571. `who.md` agrees with the signed manifest.

### D-026 A notice counts only with a human code-owner approval in GitLab
- F6.1: only a human code owner approves a Leave-Behind Notice. The "Approved by" line is text that an agent can write, so it is not enough.
- On this public project, the MR approvals API answers with no token. So the check job reads the approvals with no token (D-010 holds).
- `floor ratchet --approvals URL`: for each notice that would cover a looser policy, git finds the commit that added the file, and the API gives its merged MR and the approvers. Deny by default: every approver must be in `FLOOR_HUMANS`, one must own `/.floor/notices/` in CODEOWNERS, and the "Approved by" line must name one of them. If git or the API gives no answer, the notice does not count.
- Not run on GitLab yet: no notice MR exists.

### D-027 The probe uses an audio context of 768 frames
- On the GitLab runners (Intel Xeon Platinum 8581C, 2 vCPUs), the AVX variants of ggml run slowly under QEMU 8.2. EPYC-Milan took 2175 s, or more than the 2400 s limit.
- Decision: the probe runs `whisper-cli ... -ac 768`. 768 frames are 15.36 s of audio, and the sample is 11 s, so all the audio is in the context. The binary and the kernels do not change. The run limit is 2700 s.
- Evidence: MR !5 (pipeline 2961210282): each probe got the reference text and loaded the expected variant, with correct controls. EPYC-Milan took 1413 s.

### D-028 F13.4: the service job records GET /floor
- The gateway copies each stderr line of whisper-server and keeps the first ggml CPU variant that a backend-loader line names (`libggml-cpu-<variant>.so`). The host level comes from the flags of `/proc/cpuinfo`.
- `GET /floor` gives `host_cpu`, `host_level`, `ggml_cpu_variant` and the source. With no variant, a note says why.
- There is no deployed service yet, so there is no nightly job. The `service` job of each pipeline asks `GET /floor` and keeps `out/service/floor.json`.
- Evidence: main pipeline 2961779904 (the upstream image): `host_level` x86-64-v4, `ggml_cpu_variant` null (a static CPU backend has no loader line). Fix MR !6 pipeline 2961810145 (the canned image): x86-64-v4 and `sapphirerapids`.

### D-029 F14.4: the backtest footprint counts blob bytes and runner time
- Downloads: for each image of the backtest, the sizes of the config blob and the `/app` layer, from the registry manifests.
- Time: the job times of the sweep runs. The jobs do not record CPU time, so the footprint gives runner time, an upper bound per vCPU. There is no conversion to carbon.
- Evidence: `.floor/evidence/backtest/footprint-2026-10-15.json`: 121 images, 27,470 MB, 18.4 runner-minutes.

### D-030 §3.2: the spot check covers the "illegal instruction" hits of whisper.cpp only
- The search `repo:ggml-org/whisper.cpp "illegal instruction"` found 39 hits on 2026-10-19. The sample is 20 of them, drawn with `random.Random(64)`. `floor spotcheck` draws it again and fails if the labels are for other issues.
- Each sampled hit has one label from its whole thread: `floor`, `likely`, `unknown` or `not-floor`, with a reason and the issue link.
- Result: 13 floor, 1 likely, 4 unknown, 2 not-floor. The true-positive rate is 65% (70% with the likely one).
- The labels are a reading of text, not a script result. The other keyword counts of §3.2 are not checked, so Rieux does not use them.

### D-031 F9.1: the language table is one run per whisper.cpp commit
- Languages: English (the control), Spanish, Hindi, Bengali, Tamil, Swahili, Hausa and Yoruba. Sizes: tiny, base and small. Quantization: q5_1. 50 FLEURS test sentences per language, drawn with `random.Random(62)`.
- Decoding (F9.2): `-l <lang> -nf -bs 5 -bo 5 -t <nproc> -nt`. Score: corpus WER and CER after one normalizer. Drift: q5_1 WER minus f16 WER, with a paired-bootstrap 95% interval.
- Served: the f16 WER is at most `language.usable_wer` in the policy (0.30).
- Evidence: GitHub Actions run 39233922646 of the development repository, `.floor/evidence/language/language.json`. Served at every size: English and Spanish. Not served: Hindi, Tamil, Swahili, Hausa, Bengali and Yoruba. 92 other whisper languages are not measured.
- Deviation: the table is not made per release, because each language takes about 25 runner-minutes. The manifest lists `language` as not measured, and no gate uses the table (F9.3).

### D-032 F12.3: a flow posts the release summary from the herald job log
- CI has no token that can post a note (D-010), and the flow tools read job logs, not artifacts (D-021).
- `floor summary` makes at most 7 lines from the signed manifest and `out/herald/who.md`. The `herald` job prints `summary issue: $FLOOR_SUMMARY_ISSUE` and the summary between `--- BEGIN summary ---` and `--- END summary ---`.
- The flow `.floor/flows/release-summary.yml` starts on "Pipeline events: Passed". `gate` (no tools) answers "passed" only for a passed default-branch pipeline whose `release` and `herald` builds passed. `post` (tools `get_job_logs`, `create_issue_note`) stops unless the release log has a `released:` line. It copies the summary as it is and adds one line with the tag, so the note has at most 8 lines. It writes no floor value (F5.1).
- GitLab has no action that pins an issue. So "the pinned issue" is issue #2, "Rieux release summaries": `FLOOR_SUMMARY_ISSUE` in `.gitlab-ci.yml` names it, and the README links to it. An empty value means "post nothing".
- Not proven yet: the first release proves the tool name and the trigger.

### D-033 F11.2: the field triage flow answers from the gate's proof
- A flow has no runner and no tool that runs QEMU. The gate already runs the four probe models for every release, and the signed manifest records the ggml CPU variant that ran on each.
- `.floor/flows/field-triage.yml`: `gate` (no tools) answers "cpu", "memory", "language" or "skip". `reply` (tool `create_issue_note` only) maps the reporter's CPU to a probe model by a fixed table, points to the latest `-floor` release and its "Who this release serves" part, and asks for `/lib64/ld-linux-x86-64.so.2 --help` and the CPU model when the CPU is not known. It states no floor value.
- Deviation: no new reproduction per issue. The proof is the probe run of the release.
- The trigger is "Work item: Created".

### D-040 F13.1, F13.2: Cloud Run from the signed image, with Workload Identity Federation
- `infra/main.tf` (OpenTofu; Terraform reads it too) makes the APIs, an Artifact Registry repository, a Workload Identity pool for gitlab.com, a deploy service account, a runtime service account with no roles, and the Cloud Run service `rieux` in northamerica-northeast1: 0 to 1 instances, 1 vCPU, 2 GiB, public. A project owner applies it once.
- Only pipelines of this project on `main` can deploy: the provider condition checks `project_id`, `ref_type` and `ref` of the GitLab ID token. `.gitlab/ci/gcp-token.sh` trades the ID token for a short-lived token of the deploy service account. There is no key file, and the values in `.gitlab-ci.yml` (`GCP_*`) are not secrets.
- `deploy-image` and `deploy` run on the default branch after `attest`, so only for a held and signed image. `deploy-image` pushes the service image (`deploy/service.Dockerfile` on the held image) to Artifact Registry. `deploy` makes a revision with no traffic and the tag `candidate`, runs the smoke test of the service job against it (the reference text, `GET /floor`, 400 for a body that is not WAV), and then moves all traffic to it. A failed check leaves the traffic on the previous revision.
- Deviation: OpenTofu makes the service once; the deploy jobs own the image and the traffic (`ignore_changes`).
- Empty `GCP_PROJECT_ID`: the jobs do not run.
