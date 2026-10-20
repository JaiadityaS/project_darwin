# Devpost text: draft (T-92)

Draft for the submission form. Every number comes from `README.md` or from a pipeline or MR on GitLab. Each "OPEN" item must be done, or removed from the text, before submission. Do the last pass with the README (T-90), because the two texts must agree.

## Form fields

| Field | Value |
|---|---|
| Project name | Rieux |
| Elevator pitch (200 characters) | A release gate for whisper.cpp. It proves, for every release, who can still use it: the oldest CPU, the smallest memory, no network. Agents repair, a script judges, only a human can exclude. |
| Path and category | Path B (Bring Your Own), Hands-off |
| Special prize | Most Environmentally Impactful (opt in; SCI below) |
| Original MIT project | https://github.com/ggml-org/whisper.cpp |
| GitLab project | https://gitlab.com/gitlab-ai-hackathon/transcend-october-2026/43085222/showcase |
| Deployed URL | OPEN: the Cloud Run URL (T-06, T-50, T-51). It must be live until 2026-11-16. Now: the Rieux page, https://showcase-9a1941.gitlab.io/ |
| Video | OPEN: the YouTube URL (T-91), public, under 3:00 |
| Built with | python, gitlab-ci, gitlab-duo-agent-platform, qemu, docker, sigstore, in-toto, impact-framework, gitlab-pages, opentofu, google-cloud-run |

The pitch is 190 characters. Count it again after each change.

## About the project

### The problem

Every release raises the ceiling. Nobody watches the floor: the oldest CPU, the smallest memory and the weakest connection on which a release still works.

whisper.cpp is a speech-to-text engine that runs offline on ordinary computers. Its official Docker images crash with "illegal instruction" on normal computers:

- Issue #3510: the image `main-a1867e0` exits with code 132 at startup on a 2024 laptop chip and on a 2020 desktop chip. A stale bot closed the issue. There is no fix. A user reported it again on 2026-10-03.
- Issue #3814: `main-cuda` crashes on a 2020 desktop CPU. A stale bot closed it too.
- A search for "illegal instruction" in whisper.cpp finds 39 issues and pull requests. In a seeded sample of 20, 13 are crashes from instructions that the CPU could not run.

The cause is in the build. All 7 upstream Dockerfiles use ggml's default `GGML_NATIVE=ON`, so each image gets the instructions of the CPU of the CI machine that built it. Ordinary CI cannot see this: it tests the build on the machine that built it, and that is the one CPU that always passes. The usual fix, `GGML_NATIVE=OFF`, is a trap: the binary still needs a CPU from about 2013 or later. Upstream already has the inclusive recipe (`GGML_CPU_ALL_VARIANTS`) in its release workflow, but not in its Docker workflow. Nothing checks that the two agree.

### Before and after

| | Before (upstream today) | After (with Rieux on GitLab) |
|---|---|---|
| Who can use a release | Nobody knows. The build machine decides | A Floor Manifest for each release: the CPU, memory and connectivity floors, with proof |
| A floor rises | Users find out when the image crashes. A stale bot closes the issue | The pipeline fails. A flow opens a fix MR in minutes, and the gate checks the fix again |
| The fix does not hold | No process | A script applies upstream's own inclusive config. If that fails too, a Leave-Behind Notice draft. Only a human approves it |
| Release notes | Changes to code | "Who this release serves", from the signed manifest |
| A user reports a crash | Wait for a maintainer | The field triage flow answers with the CPU model of the gate that matches the user's CPU (OPEN: AC-F11, one test issue at the end) |

### What it does

For each push, merge request and tag, the GitLab pipeline:

1. Builds the image with upstream's recipe.
2. Scans every ELF file for the highest x86-64 level in code that always loads (the static CPU floor).
3. Runs `whisper-cli` under QEMU on four CPU models (qemu64, Nehalem, SandyBridge, EPYC-Milan), with a positive and a negative control on each.
4. Runs a transcription under cgroup memory limits, and once with no network under strace.
5. Gives the results to the Judge, a script. Each floor is held, lowered, raised or inconclusive. No model output sets a floor.

When a floor rises, the floor-repair flow of the GitLab Duo Agent Platform starts from the failed pipeline. The agent reads the scan and the build files and opens a fix MR. It may change only the build overrides, the upstream Dockerfiles and `deploy/`. The policy, the tools and the pipeline have code owners. The gate checks the fix MR with the same jobs. After a passed Judge, the `attest` job signs the Floor Manifest as an in-toto attestation (keyless, with the GitLab ID token), and the `herald` job writes "Who this release serves".

Measured on GitLab:

- The first `main` pipelines are red on purpose. Upstream's recipe gives the CPU floor of the GitLab runner (x86-64-v4, AVX-512). The policy asks for x86-64-v1.
- The flow opened fix MRs !2 and !3 about 1.5 minutes after the failed pipelines 2961083963 and 2961094614, and MR !7 about 4.3 minutes after pipeline 2969163382.
- The gate of fix MR !7 (pipeline 2969259993) passed every job: the four QEMU probes, memory, offline, the Judge, attest and herald.
- The attest job signed and verified the manifest (pipeline 2961110649, job 17270217868).
- OPEN: the release loop. PRD §16.2 asks for 3 complete loops: a repair of the default flags, a repair of the folk fix, and one notice. Each needs a merged fix MR and a `-floor.N` tag (T-05, T-42).

### What we measured

- **The build machine decides.** We scanned 61 official `main-<sha>` images from 2025-04 to 2026-10. 52 have the floor x86-64-v3, and 9 have x86-64-v4. The floor changed 15 times, and 10 of these changes came with no change to the Dockerfiles, the CMake files or the ggml CPU code. For 38 commits, upstream built a `main` and a `main-cuda` image from the same source in the same workflow run. In 11 of them, the two images have different floors.
- **The folk fix does not fix it.** Under QEMU, the native build and the folk fix crash on qemu64, Nehalem and SandyBridge. The all-variants build runs on all four CPU models.
- **Inclusion costs nothing on a modern CPU.** All variants: 20.0 CPU seconds per audio-minute. Native: 20.1. The difference (0.4%) is smaller than the noise between runs (up to 5.1%).
- **Memory and network.** The smallest memory limit that transcribes: tiny 512 MB, base 512 MB, small 768 MB. Offline: 0 network attempts. The download is 81.9 MB.
- **Languages.** With 50 FLEURS test sentences per language, whisper.cpp serves English and Spanish at every model size (WER 30% or less). Hindi, Tamil, Swahili, Hausa, Bengali and Yoruba are not served.

### Environmental impact (SCI)

- SCI (ISO/IEC 21031, Impact Framework 1.1.1): 0.00196 g CO2e per audio-minute for the all-variants build in Google Cloud northamerica-northeast1. Embodied carbon is 84.6% of it. The same work in us-central1 gives 0.0131 g, 6.7 times more.
- One release check of Rieux itself gives 0.36 g CO2e on the GitLab runners: 486 vCPU-seconds, metered in the cgroup of each job. This is a lower bound.
- The real lever is the hardware that a release forces people to replace. ΔM is the embodied carbon of the devices that a floor raise could make obsolete. It is a scenario with a range, and it is never added into SCI. OPEN: give the ΔM range as one number, with its file in `.floor/scenarios/`.

### How we built it

- One Python package, `floor`, with 34 modules and 26 test files. It runs in GitLab CI.
- `.gitlab-ci.yml`: check, build, service, scan, probe ×4, memory, offline, judge, fallback, notice-draft, attest, herald, release and pages.
- Four flows in `.floor/flows/`, saved as private AI Catalog flows: floor repair (trigger: a failed pipeline), field triage (trigger: a new work item), release summary (trigger: a passed pipeline) and a trigger probe.
- The Rieux page on GitLab Pages: the backtest timeline, the floors, the languages and SCI.

### What we added after Oct 5

The GitLab project is whisper.cpp at upstream commit `0c7be696` (2026-10-12, MIT, with its full history) plus the Rieux files. We changed no whisper.cpp file. We only moved its README to `README.whisper.cpp.md`. Every Rieux file is new, made from 2026-10-14 on:

- `.floor/`: the `floor` package, its tests, the policy, the evidence, the flows, the notices, the scenarios and the build overrides.
- `.gitlab-ci.yml` and `.gitlab/`: the pipeline and the code owners.
- `deploy/` and `infra/`: the service image and the Cloud Run configuration.
- `README.md`: the Rieux README.

The git history shows where upstream ends: the first Rieux commit on GitLab is `36521198` (2026-10-17).

### Challenges

- The GitLab runner has AVX-512. So upstream's recipe gives x86-64-v4 on GitLab and x86-64-v3 on a GitHub runner. The same source gives a different floor on a different cloud machine.
- QEMU runs the image's own loader and libraries, so the probe needs the image's file system as a sysroot, with its absolute symbolic links made relative.
- The EPYC-Milan probe is slow under QEMU (1192 to 1449 seconds). We cut the audio context and kept the full 11-second sample.
- The AI Catalog does not check the tool names in a flow definition. So after each save we read the stored definition back and compare its SHA-256 with the file in `.floor/flows/`.

### What we learned

- A CPU floor is a property of the build machine, not only of the code.
- An agent is useful when a script checks its work. The Judge is a script, and the gate checks every fix MR again.
- A floor raise is not always wrong. But a human must decide it, and the release notes must say who is left behind.

### What's next

- Run the gate on llama.cpp and other ggml projects, which use the same build options.
- Add more floors: GPU drivers, ARM levels and the operating system version.
- OPEN: keep this list short and true at submission time.
