# Floor: Product Requirements Document v3.1

> Repository copy of PRD v3.1. The related planning files named in §0 are not in this repository.

**Every release raises the ceiling. Nobody watches the floor.**

Floor proves, for every release, who can still use it. Agents repair what they can. Only a human can sign off on leaving people behind.

## 0. Document control

| Field | Value |
|---|---|
| Product | Floor (working title) |
| Document | PRD v3.1, revising v3.0 (kept verbatim as PRD-Floor-v3.0.txt). Idea lineage: Night Shift → Inheritance → Floor |
| Date | 2026-10-13 |
| Decision | Go, on the cut scope in §5 and §17 |
| Event | GitLab Transcend "Life After Code". Deadline 2026-10-27, 13:00 UTC (18:30 IST). Internal submission: 2026-10-26 |
| Path and category | Path B (Bring Your Own) · Hands-off |
| Source project | whisper.cpp (MIT), imported to GitLab at a pinned commit |
| Prizes targeted | Path prize: Path B Hands-off. Special prize, in order: Most Environmentally Impactful · Most Creative · Most Stages Covered. A project wins at most one Path prize plus one special prize, so the three specials compete for one slot |
| Deployment | Google Cloud Run, low-CO₂ region (+0.2 bonus) |
| Related | PRD-Floor-v3.0.txt · IDEA-V3.md · RESEARCH.md · PATH-B.md. PRD.md in the planning folder is the Inheritance v2.0 PRD, not Floor |

## 1. Executive summary

The problem is invisible by design. Releases quietly stop working on older or cheaper CPUs, on new mainstream CPUs without AVX-512, on small-RAM devices and for some languages. Ordinary CI cannot see it, because a native build is tested on the machine that built it. That is the one CPU guaranteed to pass.

The evidence is real and current.

- The official whisper.cpp images crash with illegal instructions (#3510, #3814) on mainstream machines, including a 2024 laptop chip. Both issues were closed for inactivity without a fix. Someone hit #3510 again on 2026-10-03.
- Every upstream Dockerfile builds with ggml's default, `GGML_NATIVE=ON`. Each image is compiled for the CPU of whichever CI machine built it.
- Upstream already knows the inclusive recipe. Its release workflow builds x64 binaries with `GGML_CPU_ALL_VARIANTS` and `GGML_BACKEND_DL`. Its Docker workflow does not. Nothing checks that the two agree.
- The fix everyone reaches for, `GGML_NATIVE=OFF` (in 8 upstream workflow files), still switches on AVX, AVX2, FMA, F16C and BMI2. It still drops pre-Haswell and budget-laptop CPUs.

The product is a release gate plus a repair agent. The gate proves the CPU, memory and connectivity floors, then attests them. When a floor rises, an agent diagnoses the cause and proposes a fix, and the gate re-verifies. If the agent's fix fails, a script applies a known inclusive config. Any exclusion or trade-off needs a human-signed Leave-Behind Notice.

Architecture in six words: **agents propose, the Judge disposes, humans exclude.**

What is new:

- **Floor Manifest:** declared becomes proven, shipped as a signed attestation.
- **Population regression** as a release-blocking class. Its only exception is a Leave-Behind Notice.
- **Inverted autonomy** as a Pareto ratchet: agents act alone only when no floor rises.
- **ΔM:** the embodied carbon a floor raise could force, reported beside SCI.

Why it can win: a hands-off loop where the agent visibly beats the fix everyone uses, a rare environmental lever (device lifespans) backed by measured numbers, and a backtest over real upstream images that may show the floor is decided by which machine ran the build (H-1, §3.6).

## 2. Changes from v3.0

v3.0's changes from v2.0 are recorded in PRD-Floor-v3.0.txt §2.

| Area | v3.0 | v3.1 | Why |
|---|---|---|---|
| Prize emphasis | Environmental primary | Hands-off leads the video; Environmental is the first-choice special | One Path prize plus one special; Hands-off is the strongest fit |
| Evidence | #3510, #3814, Gentoo, release notes | Adds checked facts: stale-closed and re-reported issues, mainstream CPUs, Dockerfile defaults, release.yml already inclusive, 278+ images on the registry, ggml CMake lines | Judges who search will find the same facts |
| Hypothesis | — | H-1: the floor depends on which CI machine built the image; tested at G-1 and G-2 | If supported, it becomes the hook |
| Repair order | Canned inclusive config first, then agent diagnosis | Agent diagnosis first; the canned config is a deterministic fallback | The agent's work sits on the main path, so "where is the agent?" answers itself |
| AC-F4b | Seeded RHEL 10-family base image | A human tags with the folk fix (`GGML_NATIVE=OFF`); the agent explains why it fails and fixes it | No seeding: upstream ships this trap in 8 workflow files. RHEL 10 becomes a COULD (AC-F4c) |
| Herald | Flow on the pipeline-passed trigger | CI job using the Duo CLI in headless mode | A repaired release's pipelines are started by automation, which cannot fire triggers, so the flow would never run in the AC-F4a path |
| Merge and tag | Actor unspecified | A merge-bot project token in CI merges and tags; agent fixes stay outside code-owned paths | Keeps the loop hands-off without weakening code-owner gates |
| Language | Conditional gate (G-2) | Report-only served / not-served table (SHOULD); G-2 becomes the backtest gate | Baselines are weak at any precision; the statistics do not fit a 3-minute video |
| Notice beat | Language trade-off, memory as fallback | A deliberate memory raise chosen from measurement (first candidate: default model base → small) | A real maintainer decision with no statistics needed |
| Backtest | ≥ 10 images, Oct 21 | ≥ 30 images sampled from 278+, plus every image near #3510 and #3814; Oct 16; its own footprint counted | Tests H-1 early; honest footprint |
| Monitor | Nightly re-scan, health | Adds a `/floor` endpoint: the CPU variant production loaded, on its actual host | Real monitoring, not a placeholder |
| Sustainability | Four levers | Leads with portable-vs-native energy and the gate's own SCI; notes that reproducible builds are the baseline build (§13.5) | Answers "does inclusion cost energy?" first |
| Video | Five beats | Same beats; new hook; three named concepts on camera | Ten named concepts do not fit in 3 minutes |
| Odds | §15.1 | Revised, with a criteria scorecard (§15.1, §15.2) | Reflects the checked evidence and the prize rule |

## 3. Problem and evidence

Releases silently drop users, the usual fix is itself a trap, and ordinary CI is blind to the bug.

### 3.1 Problem statements

| ID | Problem | Who is harmed |
|---|---|---|
| PB-1 | Binaries and images silently need newer CPU instructions, so they crash with "illegal instruction". | Owners of older, budget or AVX-512-less hardware; schools; NGOs |
| PB-2 | Memory needs grow silently, so models stop running on small devices. | 1–2 GB devices, single-board computers, old laptops |
| PB-3 | Quantization degrades some languages while tests check only English. | Speakers of lower-resource languages; archives |
| PB-4 | "Works offline" is promised but not tested. | Privacy-sensitive and offline users |
| PB-5 | No release states who it serves, so users find out by crashing. | App developers, packagers, end users |
| PB-6 | The carbon cost of forcing new hardware appears in no release metric. | Everyone; sustainability reporting |

### 3.2 Evidence

**Checked in the v3.1 review (GitHub API, container registry and docs.gitlab.com, 2026-10-13)**

- **#3510** (opened 2025-11-10): image `main-a1867e0` exits with code 132 right after startup. Reporters' machines include a 2024 laptop chip, a 2020 desktop i3-class chip and, on 2026-10-03 with the Vulkan image and `--no-gpu`, a 2021 desktop APU. One reporter found that `main-c62adfbd`, published two weeks earlier, works. A stale bot closed the issue on 2026-09-06; there is no fix.
- **#3814** (opened 2026-05-18): `main-cuda` hits SIGILL on a 2020 16-core Zen 3 desktop CPU. The plain CPU image worked on the same machine. A stale bot closed it; there is no fix.
- **Dockerfiles:** all 7 files in `.devops/` build with `make base.en`, which runs `cmake -B build $(CMAKE_ARGS)`. The GPU images pass only GPU flags; none passes a CPU flag, so `GGML_NATIVE` stays ON. `main.Dockerfile` has not changed since 2025-04, apart from an `HF_TOKEN` secret added in 2026-06.
- **Upstream's inclusive recipe:** `release.yml` builds x64 with `GGML_NATIVE=OFF`, `GGML_BACKEND_DL=ON` and `GGML_CPU_ALL_VARIANTS=ON`. `docker.yml` uses the Dockerfiles above instead.
- **The folk fix in upstream CI:** `GGML_NATIVE=OFF` appears in 8 workflow files: build-clang, build-gcc, build-macos, build-quantize, build-sanitize, build-sycl, build-vad and release.
- **ggml/CMakeLists.txt:** the default and option logic is in §3.3.
- **Registry history:** ghcr.io lists 278 `main-<sha>` tags in its first page of 1000 tags, including both #3510 images. Each amd64 image also carries a buildx attestation manifest.
- **GitLab triggers (docs v19.5):** every trigger type needs a human actor; bot users, service accounts and other flows cannot fire one. Triggers start only flows or external agents. Tier: Premium or Ultimate.

**From the v3.0 review (not re-checked in v3.1)**

- Upstream release notes show `GGML_NATIVE=OFF` added to the sanitizer and VAD CI builds, and `GGML_NATIVE=OFF` plus `GGML_BMI2=OFF` added to the Windows BLAS build (#3891, #3920, #3966). This is consistent with the workflow files above.
- Gentoo's whisper.cpp packaging notes that `GGML_NATIVE=OFF` alone isn't enough. The same maintainers removed an arm64 keyword because no recorded build backed it: an unvalidated support claim is worse than none.
- One downstream self-hosted project rebuilds whisper.cpp with `GGML_NATIVE=OFF` to avoid illegal-instruction crashes on client servers.
- Language baselines are weak. Whisper large-v3, zero-shot, has about 48% CER on FLEURS Yoruba. A Yoruba fine-tune still reports about 60% WER. Hausa zero-shot CER is about 33%.
- Keyword counts (GitHub API): whisper.cpp has 39 "illegal instruction", 23 old-CPU, 29 Raspberry Pi, 17 OOM and 54 quantization-quality issues; llama.cpp has 88 "illegal instruction" issues. These are keyword hits, not confirmed bugs. A 20-issue spot check will report the true-positive rate before submission.

### 3.3 Root cause

Line numbers are for whisper.cpp master on 2026-10-13. Once the import commit is pinned, cite them by that commit.

- **Native by default.** `GGML_NATIVE` defaults to ON (line 123), and no `.devops/` Dockerfile overrides it. The CI machine's CPU becomes everyone's floor.
- **The folk fix is a trap.** An explicit `GGML_NATIVE=OFF`, with the default still ON, sets `INS_ENB=ON` (lines 141–144). SSE4.2, AVX, AVX2, BMI2, FMA and F16C then default to ON (lines 154–166), giving a binary near x86-64-v3. AVX-512 defaults to OFF (line 159).
- **The floor depends on an unrelated variable.** When `SOURCE_DATE_EPOCH` is set, or when cross-compiling, `GGML_NATIVE_DEFAULT` is OFF (lines 105–109) and `INS_ENB` is OFF, so every extension defaults to OFF. A reproducible-builds environment variable gives the most inclusive build.
- **The inclusive build exists, and upstream uses it for release binaries.** `GGML_CPU_ALL_VARIANTS` (which needs `GGML_BACKEND_DL`, line 183) builds variants from baseline x86-64 up to AVX-512 and picks one at runtime.

### 3.4 Who is affected

- Mainstream recent CPUs without AVX-512: AMD Zen 3 and earlier, and most Intel consumer chips from 12th gen onward. Builds made on AVX-512 CI machines crash on them. The #3510 and #3814 reporters are in this group.
- Pre-Haswell desktops and laptops (no AVX2) crash on v3 builds, including the folk fix.
- Budget Celeron and Pentium Silver laptops (Gemini Lake, Jasper Lake), sold into 2021–22, have no AVX at all.
- Raspberry Pi 3 and 4 lack the Arm dot-product instructions that native Armv8.2 builds emit. This is outside MUST scope.

### 3.5 Why ordinary CI cannot see it

A native build is tested on the machine that built it, the one CPU guaranteed to pass. The bug only appears on someone else's hardware, after release.

### 3.6 Hypothesis H-1: the build machine decides

| | |
|---|---|
| Claim | Upstream images vary in CPU floor from one build to the next, because the hosted x64 CI runners are a mixed fleet (some with AVX-512, some without) and a native build takes on whichever CPU it lands on |
| Evidence so far | `main.Dockerfile` did not change between 2025-04 and 2026-06, yet `main-a1867e0` crashes where `main-c62adfbd`, two weeks older, works. In #3814 the CPU image worked while the CUDA image crashed on the same machine |
| Alternative | A ggml change between those commits added code the reporters' CPUs lack |
| Test | The backtest (F10) records the highest x86-64 level in each image. Levels that alternate (v3, v4, v3 …) with no relevant change in the Dockerfile or ggml's CPU code support H-1. A single step that stays supports the alternative |
| If supported | The hook becomes: "Whether your computer can run tonight's release depends on which cloud machine built it." |
| If not | The hook stays "built for the CI machine's CPU", which is already proven |

## 4. Insight and novelty

Floor's novelty is the combination: a per-release, proven, multi-dimensional floor whose only exception is a signed human decision.

A release is not only a set of changes. It is also a decision about who it serves, and today that decision is made by accident.

### 4.1 Claims

| # | Claim | Pitch line |
|---|---|---|
| N1 | Floor Manifest: a per-release attestation of who can use the release, with proof per floor and a diff | "An SBOM says what is inside. VEX says if it is exploitable. A Floor Manifest says who can still use it." |
| N2 | Population regression as a release-blocking class; its only exception is a Leave-Behind Notice | "A deprecation notice for people, not APIs." |
| N3 | Inverted autonomy as a Pareto ratchet: agents act alone only when no floor rises | "A ratchet for inclusion." |
| N4 | ΔM: the embodied carbon a floor raise could force, reported beside SCI | "The carbon of the hardware your release throws away." |

### 4.2 Prior art, named

| Prior art | What it does | What Floor adds |
|---|---|---|
| AppStream `<requires>` metadata | Apps declare memory and network needs | Proof per release, not a declaration |
| glibc ISA-level markers, glibc-hwcaps | Mark or dispatch libraries by x86-64 level at load time | Release-wide proof across every artifact, plus governance |
| Go `GOAMD64=v1` default; Rust and Python platform tiers | Policy for supported targets | Per-release verification beyond CPU |
| Android minSdkVersion; browserslist | Declared floors | Proven, multi-dimensional, diffable floors |
| Model cards | Per-group results at one point in time | A per-release record of who is served |
| Accessibility CI (axe, pa11y) | Blocks releases that regress for a population | Hardware, memory and connectivity, with human-only exclusion |
| Lint and coverage ratchets | One-way quality policies | A one-way inclusion policy with a signed exception |
| Blue Angel for software | One-time audit; supports hardware at least 5 years old | Continuous proof on every release |

### 4.3 What we do not claim

- QEMU, elfx86exts, x86-64 levels, CPU dispatch, cgroups, WER, SCI, in-toto and cosign are existing tools. We combine them; we do not claim them.
- The inclusive build recipe is upstream's own. Floor adds the gate that notices when one pipeline uses it and another does not.

Pitch: "Old techniques, new question: who does this release leave behind?"

## 5. Goals and non-goals

Success means three things: every release ships with a proven floor, no floor rises silently, and impact is shown on real upstream history.

| ID | Goal | Measure | Target |
|---|---|---|---|
| G1 | Every release carries a signed Floor attestation | Releases on the fork with an attestation | 100% |
| G2 | No floor rises silently | Raises without a merged Leave-Behind Notice | 0 |
| G3 | Impact shown on real history | Upstream images backtested on a published timeline, with an H-1 verdict | ≥ 30 |
| G4 | Agents repair floor raises | Raises repaired with no human after the tag: upstream's default flags (AC-F4a), and the folk fix by the agent's own MR (AC-F4b) | 2 of 2 |
| G5 | Probing stays cheap | MR pipelines decided by the static gate alone | ≥ 90%, measured |
| G6 | Sustainability is measured | SCI per audio-minute, SCI per release check, CPU-hours saved, backtest footprint | Published every release |
| G7 | The cost of inclusion is known | Energy per audio-minute for the native, folk-fix and all-variants builds on the same hardware | Measured and published |

**Non-goals**

- Agents never change engine code (`src/`, `ggml/`, `include/`, `examples/`).
- No activity on the upstream project: no issues, MRs or comments.
- No GPU-backend floors (CUDA, Vulkan, Metal). GPU images are scanned only for their CPU code.
- No Arm in MUST scope. Arm is the fallback if x86 emulation fails G-1.
- No language gate in MUST scope. A served / not-served table is a SHOULD.
- No user telemetry, and no storage of uploaded audio.
- No research-grade language claims.
- Cut from this version: Bisector, carbon-aware scheduling, MCP/JSON query API, a public AI Catalog listing (the flows are still defined privately in the AI Catalog, §9.1), the language gate (now a COULD), the seeded RHEL 10 regression (now a COULD).

## 6. Users

Every persona's hardware matches a CPU model the demo actually emulates, so the story and the proof agree. Only three personas appear in the video; the rest live in the README.

| Persona | Context | Hardware (emulated as) | Job to be done | In the video |
|---|---|---|---|---|
| Jun, developer (story persona) | Pulled the official image onto a new machine | Recent CPU with AVX2, no AVX-512 (EPYC-Milan) | "The official image crashed on my brand-new computer." | Yes: the hook. Matches the real #3510 and #3814 reports |
| Ana, student (story persona) | Offline captions on a budget school laptop | 2020 budget laptop, SSE4.2, no AVX (Nehalem) | "Captions must keep working after an update." | Yes: the folk fix saves Jun and still fails Ana |
| Maya, maintainer | One of a few whisper.cpp maintainers; already patches build flags by hand | — | "Tell me before release if this drops anybody. Fix it if you can. Ask me only for real trade-offs." | Yes: tags the release, signs the notice |
| Ravi, app developer | Ships whisper.cpp in a school lab app | 2011-era desktops, AVX but no AVX2 (SandyBridge) | "Will the next version run on our lab machines?" | No |
| Lena, packager | Distro with an x86-64-v1 baseline; won't claim untested support | Baseline x86-64 (qemu64) | "Which artifacts meet my baseline, with proof?" | No |
| Kofi, archivist (story persona) | Transcribes local-language radio | — | "An 'optimization' must not degrade my language." | No: served / not-served table only |
| Sam, sustainability officer | Reports the software's footprint | — | "Give me SCI and the hardware-life impact per release." | No |

In the video, hardware is described generically, without brand names.

## 7. Product overview

Floor proves three floors on every release, publishes a language table when the data allows, and reports one footprint.

| Floor | Question | Proof | Status |
|---|---|---|---|
| CPU (x86) | What is the oldest x86-64 level that runs every artifact? | Static scan of every loadable ELF (the gate); QEMU runs with controls (corroboration); dispatch map | MUST |
| Memory | What is the smallest RAM in which each model size transcribes? | cgroup limits from 512 to 4096 MB, swap off; peak RSS | MUST |
| Connectivity | Does it work with no network, and how big is the download? | `--network none` with a syscall trace (a tripwire); artifact and model sizes | MUST |
| Language | Which languages are served at f16, and how far does one quantization level drift? | Served / not-served table from FLEURS | SHOULD, report-only |
| Footprint (not a floor) | What does each audio-minute and each release check cost in energy and carbon? | GSF Impact Framework with published coefficients and region intensity | MUST, report-only |

### 7.1 Release loop

```text
Human pushes a tag
  │
  ▼
Build ─► Static gate (proof) ─► QEMU corroboration
  │
  ▼
Judge (a script)
  │
  ├── all floors held ──────────────────────────────────────────────┐
  │                                                                 │
  └── a floor raised                                                │
      │                                                             │
      ▼                                                             │
      Pipeline-failed trigger (human actor) starts floor-repair:    │
      the agent reads the evidence, explains the cause,             │
      and opens a fix MR                                            │
      │                                                             │
      ▼                                                             │
      Gate re-verifies the MR with the Pareto rule (CI, no trigger) │
      │                                                             │
      ├── held ─► merge-bot merges, tags -floor.N ──────────────────┤
      │                                                             ▼
      ├── still raised ─► a script applies the canned    Attest ─► Herald job (Duo CLI)
      │   inclusive config; the gate re-verifies         ─► Release ─► Cloud Run
      │   (held ─► merge-bot path above)                 (staging ─► smoke ─► production)
      │
      └── still raised after the fallback, or a trade-off
          │
          ▼
          Leave-Behind Notice: only a human approves.
          Meanwhile, the last held build stays live.
```

Only the first step after the human's tag push is a trigger. Everything after the agent's MR runs in CI, because pipelines started by automation cannot fire triggers (§9.1).

## 8. Functional requirements

Thirty-two MUST requirements define one complete loop. Language, triage and extras are SHOULD or COULD.

### F1. Policy and gate integrity

| ID | Requirement | Priority |
|---|---|---|
| F1.1 | `.floor/policy.yml` defines floors per dimension and per published artifact, validated against a JSON Schema in CI. | MUST |
| F1.2 | The policy is a ratchet: stricter through a normal MR, looser only with a merged Leave-Behind Notice. Policy, schema, Judge, CODEOWNERS and gate CI config need code-owner approval. | MUST |
| F1.3 | A pipeline execution policy from a separate project injects the gate. | SHOULD (tier permitting) |

AC-F1: An agent MR that edits the policy or the Judge cannot merge without a code owner. A policy MR that loosens a floor without a notice fails.

### F2. CPU floor: static gate

| ID | Requirement | Priority |
|---|---|---|
| F2.1 | Scan every loadable ELF: binaries, shared libraries, and dlopen'd backend variants found by enumeration, not ldd. The floor is the highest level in always-loaded code plus the baseline variant. | MUST |
| F2.2 | Allowlist known false positives (`rep bsf` decodes as `tzcnt`), with tests. Record build flags, the base-image digest, whether `SOURCE_DATE_EPOCH` was set, and the highest level found anywhere (v4 marks AVX-512 code, which H-1 needs). | MUST |
| F2.3 | The static gate on an MR finishes in under 5 minutes. | SHOULD |

AC-F2:

- A native runner build scans at v3 or above.
- A `GGML_NATIVE=OFF` build scans near v3.
- An all-variants build scans at v1 for core code and the baseline variant.

### F3. CPU floor: dynamic corroboration

| ID | Requirement | Priority |
|---|---|---|
| F3.1 | Run whisper-cli (tiny model, fixed 11-second sample) under QEMU user-mode on qemu64, Nehalem, SandyBridge and EPYC-Milan. Extract the image filesystem (`crane export`) and run with `qemu-x86_64 -L`, without Docker-in-Docker. | MUST |
| F3.2 | Each CPU model gets a negative control (must fail) and a positive control (must pass), or the result is inconclusive. A pass reproduces the reference transcript. SIGILL, a glibc CPU refusal, an abort or wrong text all count as failures. | MUST |
| F3.3 | Record a dispatch map (CPU model → loaded variant) from ggml's load log. | SHOULD |
| F3.4 | Run Intel SDE as a second emulator if its licence allows CI use. | COULD |

AC-F3:

- The default and `GGML_NATIVE=OFF` builds fail on Nehalem and SandyBridge.
- The all-variants image passes on all four models.
- The negative controls fail.

### F4. Variant Builder (agent repair)

| ID | Requirement | Priority |
|---|---|---|
| F4.1 | Runs on the pipeline-failed trigger when the Judge marks a floor raised, with the tag pusher (or MR author) as the human actor. Fallback if the trigger chain fails at G-0: the Duo CLI inside the CI job. | MUST |
| F4.2 | The agent reads the Judge's evidence (offending instructions by file and x86-64 level, recorded build flags, base-image digest) and the build files. It states the cause in the MR description and proposes a change within its allowlist: `deploy/`, `.devops/*.Dockerfile`, `.floor/overrides/`. None of these paths has a code owner. Upstream's release.yml recipe is in its context as a known-good reference. | MUST |
| F4.3 | If the agent's MR fails the gate, or the agent errors or hits its budget, a CI script applies the canned inclusive config to the same branch: `GGML_NATIVE=OFF`, `GGML_BACKEND_DL=ON`, `GGML_CPU_ALL_VARIANTS=ON`, `BUILD_SHARED_LIBS=ON`. The gate then re-verifies. | MUST |
| F4.4 | A merge-bot (a project access token used only by the merge and tag jobs) merges when every floor holds and no code-owned path changed. A release job cuts `-floor.N` from the merged commit. | MUST |
| F4.5 | One agent attempt per human action. If the fallback also fails, a script opens a draft Leave-Behind Notice that carries the agent's diagnosis, and the loop stops. | MUST |

AC-F4a: A tag built with upstream's default flags ends as a live `-floor.1` release with the CPU floor held. No human acts after the tag push. The run records whether the agent's fix or the fallback landed.

AC-F4b: A human tags a release with the folk fix (`GGML_NATIVE=OFF`). The gate reads near x86-64-v3. The agent's MR description names the cause (an explicit `GGML_NATIVE=OFF` switches AVX, AVX2, FMA, F16C and BMI2 on by default) and proposes the variant build. The agent's own MR, not the fallback, passes the gate and merges.

AC-F4c (COULD): A RHEL 10-family base image (an x86-64-v3 toolchain baseline) defeats the canned config. The agent names the base image as the cause, and its MR passes the gate.

### F5. Judge and manifest

| ID | Requirement | Priority |
|---|---|---|
| F5.1 | The Judge is a unit-tested script that marks each floor held, lowered, raised or inconclusive. CPU held needs a static proof; dynamic-only evidence gives held (coverage-limited). An LLM never sets a status. | MUST |
| F5.2 | Pareto rule: a change is inclusive only if no floor rises on any dimension. Mixed changes are trade-offs and need a notice. | MUST |
| F5.3 | Writes `floor-manifest.json` and a diff against the previous release, listing unmeasured dimensions and languages. | MUST |
| F5.4 | Signs the manifest as an in-toto attestation (`cosign attest`, keyless with GitLab OIDC) on the image digest, and attaches it to the GitLab Release. | MUST |

AC-F5: Two releases give two attestations and a readable diff, and `cosign verify-attestation` passes.

### F6. Leave-Behind Notice

| ID | Requirement | Priority |
|---|---|---|
| F6.1 | For any raise or trade-off that cannot be fixed inclusively, a notice MR is opened from the template in §11. Code owners approve. Agent accounts and the merge-bot cannot approve or merge it. | MUST |
| F6.2 | A merged notice appears in the release notes and the manifest. | MUST |
| F6.3 | The default is `on_unfixable_raise: ship_last_held`: production keeps the last held build until a human decides. | MUST |

AC-F6: A deliberate raise that no inclusive option repairs produces a notice listing the options tried, the floor change and ΔM as a range. After approval it appears in the release notes and the manifest. The raise is chosen from memory measurements; the first candidate is changing the default model from base to small.

### F7. Memory floor

| ID | Requirement | Priority |
|---|---|---|
| F7.1 | Transcribe per model size under 512, 768, 1024, 1536, 2048 and 4096 MB, with swap equal to the limit, and record pass/fail and peak RSS. Report a peak-RSS rise over 10%. Crossing a policy limit is a raise. Policy floors come from measurement. | MUST |

AC-F7: The manifest lists the smallest passing limit and the peak RSS for each model size.

### F8. Connectivity tripwire

| ID | Requirement | Priority |
|---|---|---|
| F8.1 | Transcribe with `--network none` while tracing network syscalls; any attempt fails. Record the download size of each artifact and model. | MUST |

AC-F8: The manifest states `offline: proven`, links the job, and lists the download sizes.

### F9. Language table (report-only)

| ID | Requirement | Priority |
|---|---|---|
| F9.1 | Publish a served / not-served table: languages and model sizes with a usable f16 error rate on FLEURS, and their drift at one quantization level. List unmeasured languages. | SHOULD |
| F9.2 | Pin decoding: forced language (`-l`), no temperature fallback (`-nf`), fixed threads and beam size. | SHOULD |
| F9.3 | A language gate: drift above tolerance and a paired-bootstrap 95% interval that excludes zero, on ~100 FLEURS clips per language. | COULD, only after G-4 |

AC-F9: The table is on the Floor page, with its sample sizes and limits stated.

### F10. Backtest over real history

| ID | Requirement | Priority |
|---|---|---|
| F10.1 | Pull ≥ 30 historical upstream images: a sample spread across the 278+ `main-<sha>` tags, plus every image within two weeks of #3510 and #3814. Scan the `/app` layer (~150 MB) of every image. Scan distro-package layers for a subset, cached by layer digest. Run the static gate on all images and QEMU corroboration on a subset, without rebuilding. Publish a timeline of when floors moved and whether the release notes said so. | MUST |
| F10.2 | Reproduce #3510 (`main-a1867e0` fails on EPYC-Milan and Nehalem; `main-c62adfbd` is the comparison) and #3814 (`main-cuda`: static scan, plus QEMU if the image runs without a GPU). | MUST |
| F10.3 | Test H-1: compare the highest level found in each image against changes to the Dockerfile and to ggml's CPU code, and state the verdict with evidence. | MUST |
| F10.4 | Run the static gate on a second ggml project's published images. | SHOULD |
| F10.5 | Re-scan main and newly published upstream images nightly. | SHOULD |

AC-F10: The Floor page shows a timeline of at least 30 points, each linked to evidence, and the H-1 verdict.

### F11. Field Triage (reduced)

| ID | Requirement | Priority |
|---|---|---|
| F11.1 | A flow on the work-item-created trigger classifies floor symptoms: illegal instruction, exit code 132, OOM, language accuracy. | SHOULD |
| F11.2 | It reproduces the problem on the matching CPU model and replies with the working artifact and proof. It asks for `ld.so --help` output when the CPU is unknown. | SHOULD |

AC-F11: A test issue about a crash on a Sandy Bridge-class desktop gets the right artifact and proof in under 15 minutes.

### F12. Communication

| ID | Requirement | Priority |
|---|---|---|
| F12.1 | Release notes get a "Who this release serves" section, generated from the manifest by the Herald CI job for every release, including `-floor.N`. | MUST |
| F12.2 | A public Floor page shows the floor history with the backtest and the H-1 verdict, side-by-side runs on two emulated CPUs, the language table, SCI, and notices. | MUST |
| F12.3 | A summary of at most 8 lines goes on a pinned issue after each release. | SHOULD |

### F13. Deployment (Path B)

| ID | Requirement | Priority |
|---|---|---|
| F13.1 | whisper-server runs on Cloud Run in a low-CO₂ region from the attested, held image. OpenTofu lives in the repo, and CI uses Workload Identity Federation. | MUST |
| F13.2 | Staging, then a smoke test (transcribe the sample, compare the text), then production. Roll back on failure. | MUST |
| F13.3 | The upload page caps audio at 30 seconds, rate-limits requests and caps instances; no audio is stored. The service stays live until at least 2026-11-16. | MUST |
| F13.4 | A `/floor` endpoint reports the host CPU's x86-64 level and the ggml CPU variant production loaded, from ggml's load log. The nightly job records it. | SHOULD |

### F14. Sustainability measurement

| ID | Requirement | Priority |
|---|---|---|
| F14.1 | SCI per audio-minute for the service, and per release check for Floor's own pipeline, computed with GSF Impact Framework manifests in the repo. | MUST |
| F14.2 | Measured levers, in this order: energy per audio-minute for the native, folk-fix and all-variants builds on the same hardware (the cost of inclusion); cheap-first vs full-matrix probing (CPU-hours); quantization energy and peak RSS per level; region. | MUST |
| F14.3 | ΔM for each notice, reported beside SCI as a scenario range. | MUST |
| F14.4 | The backtest's downloads and CPU time are reported as a one-off footprint. | SHOULD |

### F15. Governance and security

| ID | Requirement | Priority |
|---|---|---|
| F15.1 | Every agent and merge-bot action leaves an audit record linked to its job. | MUST |
| F15.2 | A daily Duo credit budget (default 10); agents stop at 100%. | SHOULD |
| F15.3 | Container scanning and secret detection run on every release. Model files are pinned by SHA-256. | SHOULD |

## 9. Agents, flows and triggers

Floor runs two custom Duo Agent Platform flows started by GitLab triggers, plus one Duo CLI job inside CI. Scripts decide every floor; agents diagnose, propose and explain.

| Component | Start | Steps | Output |
|---|---|---|---|
| floor-repair (flow) | Pipeline events: Failed, on a tag or MR pipeline started by a person | Exit unless the Judge said raised (deterministic) → diagnose and propose (agent) → open the fix MR (deterministic) | A fix MR with the diagnosis |
| floor-herald (CI job, Duo CLI headless) | Every release pipeline, after attestation, including `-floor.N` | Read the manifest (deterministic) → write "Who this release serves" and a summary (agent) | Release-notes section and pinned summary |
| floor-triage (flow, SHOULD) | Work item: Created, by a person | Classify (agent) → reproduce on the matching CPU model (deterministic) → reply (agent) | A reply with the working artifact and proof |

### 9.1 Platform constraints (GitLab docs v19.5, checked 2026-10-13)

- Triggers can start flows or external agents, but not custom or foundational agents. → All triggered agent work lives inside flows.
- Every trigger type needs a human to perform the triggering action. Bots, service accounts and other flows cannot fire one. → The loop starts from a human tag push. The agent's MR pipeline, the fallback, the merge and the `-floor.N` release are all started by automation, so none of them can wake a flow. Everything after the agent's MR runs in CI, including Herald. This also caps agents at one attempt per human action.
- Pipeline events (Running, Passed, Failed, Canceled) became a trigger in 18.9 behind an experimental flag, removed in 19.1. A work-item-created trigger arrived in 19.1. → G-0 still tests the exact chain, including who counts as the actor.
- A pipeline-failed trigger fires on every failed pipeline. → The flow's first, deterministic step exits unless the Judge said raised.
- Loading a flow from a configuration path needs a flag that is off by default. → Define the two flows in the AI Catalog, private to the group. A public listing is cut.
- Triggers need the Premium or Ultimate tier. → Confirm the hackathon group's tier at G-0.
- Triggered flows run and bill as the service account. Service accounts get no included credits and draw on the namespace's pool. → Confirm the credit pool at G-0, and cap spend (F15.2).
- Flow definitions can mix agent components and deterministic step components. → If a deterministic step can run our scripts, the Judge check runs inside the flow; otherwise it runs in CI.
- Imported issues have no human actor. → The triage demo uses an issue created by a person.
- The Duo CLI runs headless in CI (19.2). → It runs Herald and is the G-0 fallback for floor-repair. If it is unavailable to the hackathon group, Herald writes notes from a deterministic template, and the submission says so.

### 9.2 Who does what

| Scripts decide | Agents do |
|---|---|
| Builds, static scans, emulation, memory limits, offline test, Judge, manifest, attestation, diff, the fallback config, merge and tag, SCI and ΔM arithmetic | Diagnose why a floor rose and propose a config change; classify issue text; write notices, release notes and summaries |

No LLM output can change a floor status. A cheaper model classifies; a stronger model diagnoses and writes.

## 10. Autonomy and governance

Agents act alone only when no floor rises. Every exclusion or trade-off waits for a signed human decision, and production never waits.

| Action | Mode |
|---|---|
| Probe, judge, write and attest the manifest | Automatic |
| Diagnose a raise and open a fix MR | Automatic (agent; one attempt per human action) |
| Apply the canned config if the agent's fix fails | Automatic (script) |
| Merge an inclusive (Pareto-improving) fix after the gate passes, and tag `-floor.N` | Automatic (merge-bot) |
| Release, deploy to staging and production, roll back on failure | Automatic |
| Keep the last held build live when a raise cannot be fixed | Automatic |
| Reply to floor issues | Automatic (SHOULD) |
| Make the policy stricter | MR with normal review |
| Accept a trade-off or raise a floor | Human only: Leave-Behind Notice with code-owner approval |
| Change policy, Judge, schema, CODEOWNERS or gate config | Human only: code-owner approval |
| Change engine code | Never |

### 10.1 Gate integrity controls

- Agent service accounts hold the Developer role and push only to unprotected branches.
- `main` is protected. Code-owner approval is required for `.floor/policy.yml`, `.floor/judge/`, the schema, `CODEOWNERS` and `.gitlab-ci.yml`.
- The merge-bot token is used only by the merge and tag jobs. Code-owner approval rules still apply to it, so it cannot merge a change to a code-owned path.
- A pipeline execution policy injects the gate from a separate project, where the tier allows.
- A path-allowlist CI job is defense in depth, not the primary control.
- Because automation cannot fire triggers, agents get one attempt per human action.
- Every agent and merge-bot action links to its job and evidence.

### 10.2 Hands-off claim

You push a tag. The next time you look, a release is live with an attestation of who it serves. In the main path no human acts after the tag: the agent diagnoses, a script verifies and merges, and the release ships. A human is needed only to leave people behind, and even then production keeps the last held build.

## 11. Artifacts

Values in angle brackets are placeholders until measured.

### 11.1 Floor Manifest (in-toto attestation)

```json
{
  "_type": "https://in-toto.io/Statement/v1",
  "subject": [{ "name": "registry.gitlab.com/<group>/whisper.cpp/server", "digest": { "sha256": "<digest>" } }],
  "predicateType": "<project-url>/floor-manifest/v0.3",
  "predicate": {
    "release": "<tag>-floor.1",
    "commit": "<sha>",
    "build": { "cmake_flags": "<flags>", "base_image": "<digest>", "source_date_epoch": false, "highest_level_found": "<level>" },
    "floors": {
      "cpu": { "x86_64": "x86-64-v1", "status": "held", "proof": "static",
               "dispatch": { "qemu64": "<variant>", "Nehalem": "<variant>", "SandyBridge": "<variant>", "EPYC-Milan": "<variant>" },
               "evidence": "<job-url>" },
      "memory": { "smallest_passing_mb": { "tiny": "<measured>", "base": "<measured>", "small": "<measured>" },
                  "peak_rss_mb": { "base": "<measured>" }, "evidence": "<job-url>" },
      "connectivity": { "offline": "proven", "network_attempts": 0, "download_mb": "<measured>", "evidence": "<job-url>" },
      "language": { "status": "table-only", "served": ["<lang>"], "not_served": ["<lang>"] }
    },
    "unmeasured": ["arm64", "gpu-backends", "<languages not tested>"],
    "diff_from": "<previous release>",
    "changes": [{ "dimension": "cpu", "from": "x86-64-v3", "to": "x86-64-v1", "status": "lowered", "fixed_by": "<agent | fallback>" }],
    "leave_behind_notices": [],
    "footprint": { "sci_gco2e_per_audio_minute": "<measured>", "sci_gco2e_per_release_check": "<measured>", "method": "GSF Impact Framework" },
    "delta_m_kgco2e": { "low": 0, "high": 0, "note": "0 when every floor holds" }
  }
}
```

### 11.2 Leave-Behind Notice template

```text
## Leave-Behind Notice
Floor change:     <dimension>: <from> → <to>, or a trade-off between <A> and <B>
Reason:           <why the change is needed>
Tried first:      <inclusive options tried, with job links>
Who is affected:  <population estimate: labelled proxy, source and range>
ΔM (scenario):    <low–high kgCO₂e with inputs; reported beside SCI, never inside it>
Guidance:         <what affected users should do: artifact, model or version>
Approved by:      <code owner>   (agents and the merge-bot cannot approve)
```

### 11.3 Policy (`.floor/policy.yml`)

```yaml
cpu:
  x86_64_min_level: x86-64-v1        # README: AVX support is optional
  emulate: [qemu64, Nehalem, SandyBridge, EPYC-Milan]
memory_mb:                           # set from measurement
  tiny: <measured>
  base: <measured>
  small: <measured>
connectivity:
  offline_required: true             # README: runs fully offline, on-device
language:
  gate: false                        # report-only table (F9.1); a gate is a COULD (F9.3)
  metric: drift_vs_f16
footprint:
  report_only: true
repair:
  agent_attempts_per_human_action: 1
  fallback: canned_inclusive_config  # F4.3
on_unfixable_raise: ship_last_held
```

## 12. DevSecOps stage coverage

Floor touches all nine stages, each through a GitLab feature doing real work in the loop.

| Stage | What Floor does | GitLab feature |
|---|---|---|
| Plan | Triage maps issues to floors (SHOULD); notices are planned, reviewed decisions | Issues, work-item-created trigger, labels |
| Create | The repair agent writes build-config MRs with its diagnosis | Merge requests, custom flows |
| Verify | Static gate, QEMU corroboration, memory limits, offline tripwire | CI/CD, child pipelines, cache |
| Secure | Offline tripwire, pinned model hashes, container scanning, secret detection, signed attestations | Security scanning templates, keyless signing |
| Package | Portable images with CPU variants; attestation on the digest | Container registry, package registry |
| Release | Floor gate, `-floor.N` tags cut by the merge-bot, "Who this release serves" notes from the Herald job | Releases, protected tags, release evidence |
| Configure | Cloud Run via OpenTofu; Workload Identity Federation | GitLab-managed OpenTofu state, environments, CI variables |
| Monitor | Nightly re-scan of published images; `/floor` reports the variant production loaded; service health and rollback | Scheduled pipelines, environments, pipeline-events trigger |
| Govern | Ratchet policy, code-owner gates, pipeline execution policy, audit trail, credit budget | CODEOWNERS, approval rules, security policies, audit events |

## 13. Sustainability method

Floor leads with measured numbers. It reports ΔM beside SCI as a labelled scenario, never inside it.

### 13.1 Standards

- SCI (ISO/IEC 21031:2024): SCI = (E × I + M) / R.
- SCI is computed with Green Software Foundation Impact Framework manifests kept in the repo.
- Agent model use is estimated per token and labelled as an estimate.
- Carbon intensity is location-based. No offsets.

| Unit | Meaning |
|---|---|
| R1 | One audio-minute transcribed by the deployed service |
| R2 | One release check (all probes) |
| R3 | One day of agent work |

| Input | Source |
|---|---|
| E (energy) | CPU-seconds and memory-hours × published per-vCPU and per-GB coefficients (Cloud Carbon Footprint method); agent tokens estimated |
| I (intensity) | Google's published grid intensity for the chosen region |
| M (embodied, own) | Time-share of server embodied emissions with standard coefficients |

### 13.2 Measured levers (lead with these, in this order)

1. **The cost of inclusion:** energy per audio-minute for the native, folk-fix and all-variants builds on the same hardware. If runtime dispatch matches the AVX2-only build, inclusion costs nothing. If it does not, the number is reported as it is.
2. **Cheap-first probing:** CPU-hours per release check, compared with running the full matrix on every MR.
3. **Floor's own footprint:** SCI per release check (R2), including estimated agent tokens.
4. **Quantization:** energy per audio-minute and peak RSS per level.
5. **Region:** the same workload in the chosen low-CO₂ region against a default region, calculated from published intensity.

### 13.3 ΔM: a consequential indicator beside SCI

ΔM(r) = N_affected(r) × e × p(r) × (Δ(r) / L)

| Symbol | Meaning |
|---|---|
| N_affected | Devices below the new floor among users in scope. A labelled proxy with a range. Hardware surveys skew toward newer machines, so it is likely understated |
| e | Embodied emissions of a replacement device (manufacturer reports, stated range) |
| p(r) | Share of affected users who replace their device because of this release (scenario, 1–5%) |
| Δ(r) | Useful life cut short, in years |
| L | Expected device lifespan, in years |

- ΔM is always a range with every input shown, plus a sensitivity table across p.
- ΔM is 0 when every floor holds.
- ΔM is never added into SCI. SCI's M covers only the hardware the software itself runs on.

### 13.4 Honesty rule

- Small numbers are reported as they are.
- Every number comes from a script in the repo.
- A scenario is never presented as a measurement.
- The backtest's downloads and CPU time are reported as a one-off footprint.
- Carbon-aware scheduling is cut: its gain on one nightly job is negligible.

### 13.5 Reproducible builds are inclusive builds

In ggml, setting `SOURCE_DATE_EPOCH` (the reproducible-builds convention) turns native off and every CPU extension off (§3.3). Floor's fix and the reproducible-builds practice point the same way: builds that do not depend on the build machine. The README states this as a design note, not as a measured gain.

## 14. Non-functional requirements

| ID | Area | Requirement |
|---|---|---|
| NFR-1 | Correctness | CPU held needs a static proof. Dynamic-only evidence gives held (coverage-limited). Failed controls give inconclusive. |
| NFR-2 | Reproducibility | Every value reproduces from pinned scripts, toolchain, image digests and decode flags. Releases are built only from committed source. |
| NFR-3 | Performance | Static gate < 5 min. MR pipeline < 10 min. Failing tag to live `-floor.N` release < 90 min. Triage reply < 15 min. The backtest is a one-off job, cached by layer digest. |
| NFR-4 | Cost | Google Cloud < $30 (scale to zero). Duo credits within the daily budget. |
| NFR-5 | Reliability | Idempotent publish steps. Retries only for infrastructure failures. Rollback < 5 min. |
| NFR-6 | Security | No secrets in probe jobs. Keyless signing. Least-privilege agent roles; the merge-bot token is scoped to the merge and tag jobs. |
| NFR-7 | Privacy | No telemetry. Uploaded audio is processed in memory and never stored. |
| NFR-8 | Licence | Our code is MIT. Upstream notices stay intact. FLEURS is credited (CC BY 4.0). |
| NFR-9 | Accessibility | The Floor page meets WCAG 2.2 AA. |
| NFR-10 | Transparency | Every agent and merge-bot action links to its job and evidence. |

## 15. Competitive positioning

Floor beats every likely rival on innovation and story. To win, it must match them on measured numbers and visible autonomy.

| Prize | Strongest rival | Where the rival is stronger | Floor's edge | Must-have for Floor |
|---|---|---|---|---|
| Path B Hands-off | Issue-to-Prod: agents fix real backlog issues and deploy | Literal fit to the category; agents visibly working | A real upstream bug, repaired with no human; the agent beats the folk fix | Agent diagnosis on screen, uncut and timestamped (AC-F4b) |
| Most Environmentally Impactful | Carbon Autopilot: measured SCI per pipeline; agent MRs that cut CI emissions | Every number measured; answers the prize text literally | Device lifespans are a bigger, rarer lever; stronger story | Lead with the cost of inclusion and Floor's own SCI (F14.2); ΔM second |
| Most Creative | Accessibility floor: agents block and fix WCAG regressions | Visual before-and-after; every web app is its audience | New question; environmental angle; human-only exclusion | The question lands in the first 20 seconds |
| Most Stages Covered | CRA compliance autopilot (EU Cyber Resilience Act) | Timely regulation; deep Secure and Govern stages | Every stage does real work in one loop | Real depth in Secure, Govern and Monitor (F1.3, F13.4, F15.3) |

### 15.1 Scorecard

Judging criteria, scored 1–5, assuming top execution.

| Criterion | v3.0 review | v3.1 target | What moves it |
|---|---|---|---|
| Technological Implementation | 4.5 | 4.5 | Static proof plus emulation with controls, attestations, OpenTofu, a real backtest |
| Design | 4.0 | 4.5 | A Floor page with the backtest timeline and side-by-side runs |
| Potential Impact | 4.5 | 4.5 | Mainstream CPUs affected, not only old ones |
| Innovation | 4.5 | 4.5 | The SBOM → VEX → Floor Manifest line; the Leave-Behind Notice |
| Presentation | 4.0 | 4.5 | Three concepts on camera; a real trap instead of a seeded one |
| Average + Google Cloud bonus | 4.5 of 5.2 | 4.7 of 5.2 | |

### 15.2 Odds

These are judgement calls; the field is unknown. Outcomes are correlated, because the same judges score every category. A project can win one Path prize plus one special prize.

| Category | v3.1, executed well | Ceiling |
|---|---|---|
| Path B Hands-off | 20–30% | 35–45% |
| Most Environmentally Impactful | 18–28% | 35–45% |
| Most Stages Covered (Path B) | 8–12% | 15–20% |
| Most Creative | 5–10% | 12–20% |
| At least one prize | 45–55% | 60–65% |

Building the full v2.0 scope and finishing half of it would cut these by about two thirds.

## 16. Demo and definition of done

### 16.1 Video (five beats, under 2:50, real runs with a visible clock)

| Time | Beat | On screen |
|---|---|---|
| 0:00–0:20 | Hook | A brand-new laptop CPU and a budget school laptop CPU, both emulated, run a real published upstream image (`main-a1867e0`). Both crash: "illegal instruction". The bug report was closed for inactivity and reported again ten days ago. "Every release raises the ceiling. Nobody watches the floor. Your CI can't see this: it tests on the machine that built it." If H-1 holds: "Whether your computer can run tonight's release depends on which cloud machine built it." |
| 0:20–1:05 | The trap and the repair | The maintainer tags a release with the fix everyone uses. The static gate reads x86-64-v3. Side by side, the new laptop now transcribes; the school laptop still crashes. The gate blocks. The agent reads the scan and the build file, explains why the obvious fix fails, and proposes the variant build that upstream already uses for its release binaries. The Judge verifies, a script merges, and `-floor.1` goes live. No human after the tag. |
| 1:05–1:40 | The human decision | The maintainer wants better transcripts and changes the default model (first candidate: base → small). The memory floor rises from `<measured>` to `<measured>` MB. The agent's inclusive options do not hold it, so a Leave-Behind Notice shows who is affected and a ΔM range. The maintainer signs, and the notice appears in the release notes. |
| 1:40–2:20 | Proof it matters | The backtest timeline across ≥ 30 real upstream images, with the H-1 verdict. #3814 is reproduced on an emulated recent CPU. Measured numbers: the energy cost of the portable build, and CPU-hours saved by cheap-first probing. |
| 2:20–2:45 | Live | Cloud Run in a low-CO₂ region, the Floor page, `/floor` showing the variant production loaded, and `cosign verify-attestation` passing. Close: "Raise the ceiling. Keep the floor." |

Video rules:

- No third-party logos or trademarks on screen or in the voice-over. Say "a brand-new laptop CPU", "a 2011 desktop CPU" or "a $35 single-board computer".
- Show issue evidence on our own Floor page, not as screenshots of a third-party site.
- Name only three concepts on camera: Floor, Floor Manifest, Leave-Behind Notice. ΔM appears once, as a number.
- Real runs only, time-lapsed with a visible clock.
- Story personas are labelled as such.

### 16.2 Definition of done

- [ ] Public GitLab repo (whisper.cpp at a pinned commit plus Floor), MIT licence visible in About
- [ ] Pipeline history with ≥ 3 complete release loops: one default-flags repair (AC-F4a), one folk-fix repair by the agent (AC-F4b) and one notice
- [ ] Attestations for ≥ 2 releases plus a diff; `cosign verify-attestation` passes
- [ ] AC-F4a and AC-F4b passed in recorded runs
- [ ] Herald output in the release notes of every release, including `-floor.N`
- [ ] Backtest timeline with ≥ 30 points and the H-1 verdict on the Floor page
- [ ] Live Cloud Run URL (until 2026-11-16) and the Floor page
- [ ] SCI write-up with measured levers and a ΔM range (environmental opt-in)
- [ ] README: problem, claims with prior art, stage table, how to run, sources
- [ ] Devpost text: Path B "what we added after Oct 5", original project URL, deployed URL
- [ ] Public YouTube video under 3:00

## 17. Plan and gates

Every kill risk is tested by Oct 16. Features freeze on Oct 24. We submit on Oct 26, which leaves a day of buffer.

### 17.1 Gates

| Gate | Date | Pass condition | If it fails |
|---|---|---|---|
| G-0 Access and trigger chain | Oct 14 | Hackathon access and tier (Premium or Ultimate); whisper.cpp imported at a pinned commit; a human tag push fails the gate and the pipeline-failed trigger starts a flow; the Duo CLI runs headless in a CI job; the merge-bot merges a non-code-owned MR and its tag starts a pipeline; credit pool confirmed | Run the agent through the Duo CLI in the CI job. If both fail, agents only triage and write, and the submission says so |
| G-1 CPU proof | Oct 15 | The static scan classifies native, folk-fix and all-variants builds as expected; QEMU controls behave on all four CPU models; the two #3510 images are scanned and compared (first H-1 signal) | Add Intel SDE; otherwise make static-only claims |
| G-2 Backtest and H-1 | Oct 16 | ≥ 30 images scanned into a timeline; an H-1 verdict with evidence | If H-1 is not supported, the hook uses "built for the CI machine's CPU"; the timeline still ships |
| G-3 Gate integrity | Oct 18 | An agent MR that touches the policy or Judge cannot merge; the merge-bot cannot merge a code-owned change; a notice needs a code owner | Drop the inverted-autonomy claims until fixed |
| G-4 Release loop | Oct 22 | One full loop: the gate blocks, the agent repairs, the attestation signs, Herald writes notes, Cloud Run serves | Cut Field Triage and the language table |

### 17.2 Schedule

| Dates | Work | Done when |
|---|---|---|
| Oct 13 | Confirm onboarding is submitted. Scan three local builds (native, folk fix, all-variants). Scan the two #3510 images (`main-a1867e0`, `main-c62adfbd`). Start screen-recording every successful run | Trap confirmed locally; first H-1 signal |
| Oct 14 | Import at a pinned commit. Trigger chain test. Duo CLI headless job. Merge-bot token. Cloud Run hello-world with WIF | G-0 |
| Oct 15 | Static scanner; QEMU harness with controls | G-1; AC-F2, AC-F3 |
| Oct 16 | Backtest sample and H-1 analysis; all-variants build in CI | G-2; AC-F10 timeline |
| Oct 17–18 | Judge, manifest, attestation, policy integrity, Leave-Behind Notice | G-3; AC-F1, AC-F5, AC-F6 |
| Oct 19–20 | floor-repair flow (diagnosis plus fallback), merge-bot, `-floor.N` tags; memory floor; offline tripwire | AC-F4a, AC-F4b, AC-F7, AC-F8 |
| Oct 21 | #3510 and #3814 reproductions under QEMU; second-project scan (SHOULD); language table (SHOULD) | AC-F10 complete |
| Oct 22 | Full loop to Cloud Run; Herald job; SCI via Impact Framework; Floor page | G-4 |
| Oct 23 | `/floor` endpoint; triage (if time); polish | AC-F11 |
| Oct 24 | Feature freeze. 3 full release loops for the pipeline history; footage | Pipeline items in §16.2 |
| Oct 25 | Video, README, Devpost text, SCI write-up | Video uploaded |
| Oct 26 | Submit | Submitted |
| Oct 27 | Buffer only (deadline 13:00 UTC) | — |

MUST work is an estimated 11 person-days: the language gate moves out, and the backtest, fallback and merge-bot move in. Solo, that leaves about two days of slack.

## 18. Risks

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Scope creep | High | High | Gates and the cut list are binding; feature freeze on Oct 24 |
| Judges ask "where is the agent?" | Medium | High | AC-F4b on screen, uncut and timestamped: the agent explains why the folk fix fails |
| The agent proposes the folk fix itself and fails | Medium | Low | The fallback lands the release (AC-F4a still passes); the diagnosis prompt carries the scan evidence and the CMake logic; AC-F4b is re-run until recorded |
| Trigger chain fails (actor rules, tier, credits) | Medium | High | G-0 on Oct 14; Duo CLI fallback |
| Herald never runs on automation-started pipelines | Was certain in v3.0 | High | Resolved: Herald is a CI job, not a triggered flow |
| H-1 not supported | Medium | Low | The hook falls back to "built for the CI machine's CPU", which is already proven |
| QEMU misses an instruction class | Medium | Medium | Static gate is the proof; controls on every run; Intel SDE |
| Static false positives (`rep bsf` as `tzcnt`) | High | Low | Allowlist with tests |
| Older upstream image tags are missing | Low | Medium | 278+ `main-<sha>` tags were listed on 2026-10-13; fall back to release binaries |
| Backtest bandwidth and footprint | Medium | Low | Scan `/app` layers on all images and package layers on a subset; cache by layer digest; count it in SCI (F14.4) |
| Upstream fixes its Docker defaults during the hackathon | Low | Medium | Pin the import commit; the backtest shows Floor would have caught it |
| Judges see a niche | Medium | Medium | The hook shows a brand-new laptop crashing, not only old hardware; second-project scan |
| Onboarding delay | Medium | High | Build the scanner and QEMU harness locally first |
| Public upload abuse or cost | Medium | Medium | Caps, max instances, budget alert |
| Trademarks in the video | Low | Medium | Generic wording; no logos; evidence shown on our own page |

## 19. Open questions (Phase 0)

| Question | Status |
|---|---|
| Does a pipeline-failed trigger fire for a tag pushed by a person, and who counts as the actor? | Docs say a human actor is required and automation cannot fire triggers; the tag pusher should count. Test at G-0 |
| Can a deterministic flow step run our Judge script, or must it run in CI? | Open |
| Can the Duo CLI run headless in CI with the hackathon credits? | Open; it now carries Herald too |
| Does the hackathon group's credit pool cover service-account flows? | Open |
| Does the hackathon group have Premium or Ultimate, and does that include pipeline execution policies? | Open |
| Can a merge-bot project token merge an MR and push a tag that starts a pipeline, under code-owner rules? | Open; test at G-0 |
| Which older upstream image tags are still on the GitHub Container Registry? | Answered: 278+ `main-<sha>` tags, including both #3510 images (2026-10-13) |
| Does `main-cuda`'s whisper-cli run under QEMU without a GPU? | Open; if not, #3814 is reproduced by static scan only |
| Which Cloud Run region has the lowest published grid intensity today? | Open |
| Which public hardware survey is the best labelled proxy for CPU-level shares, and which way does it bias? | Open |

## 20. Glossary

| Term | Meaning |
|---|---|
| Floor | The lowest CPU level, memory or connectivity a release still serves |
| Floor Manifest | A per-release statement of floors with evidence, shipped as an in-toto attestation |
| Floor diff | The change in floors between two releases |
| Population regression | A change that stops serving people the previous release served |
| Leave-Behind Notice | A human-approved, public record of an intentional floor raise or trade-off |
| Inverted autonomy | Agents act alone only in the inclusive direction |
| Pareto rule | A change is inclusive only if no floor rises on any dimension |
| Folk fix | `GGML_NATIVE=OFF` on its own: widely used, and still near x86-64-v3 |
| Fallback config | The canned inclusive config a script applies if the agent's fix fails |
| Merge-bot | The project access token that merges held fixes and cuts `-floor.N` tags |
| H-1 | The hypothesis that an image's CPU floor depends on which CI machine built it |
| Static proof | No instruction above a given level anywhere in loadable code |
| Coverage-limited | Held on dynamic evidence only; some code paths were never run |
| Negative control | A run that must fail, proving the test can detect failure |
| Dispatch map | Which CPU variant ggml loads on each emulated CPU |
| Drift | The WER of a quantized transcript against the f16 transcript of the same model |
| Backtest | Running Floor over past upstream images and releases |
| x86-64-v1 to v4 | Standard CPU levels (v3 ≈ AVX2, v4 ≈ AVX-512) |
| SIGILL | The signal a program gets when the CPU lacks an instruction it uses |
| SCI | Software Carbon Intensity (ISO/IEC 21031) |
| ΔM | A scenario estimate of the embodied carbon a floor raise could force, reported beside SCI |

## 21. Sources

**Checked in the v3.1 review (2026-10-13)**

- whisper.cpp issue #3510 and its comments: https://github.com/ggml-org/whisper.cpp/issues/3510
- whisper.cpp issue #3814: https://github.com/ggml-org/whisper.cpp/issues/3814
- `.devops/` Dockerfiles and their commit history: https://github.com/ggml-org/whisper.cpp/tree/master/.devops
- Upstream workflows (docker.yml, release.yml and the 8 files using `GGML_NATIVE=OFF`): https://github.com/ggml-org/whisper.cpp/tree/master/.github/workflows
- ggml CMake options, lines 86–183: https://github.com/ggml-org/whisper.cpp/blob/master/ggml/CMakeLists.txt
- Makefile `base.en` recipe: https://github.com/ggml-org/whisper.cpp/blob/master/Makefile
- Container image tags and manifests: ghcr.io/ggml-org/whisper.cpp
- GitLab triggers documentation (v19.5): https://docs.gitlab.com/user/duo_agent_platform/triggers/
- GitLab custom flows documentation: https://docs.gitlab.com/user/duo_agent_platform/flows/custom/

**From the v3.0 review (2026-10-13, not re-checked in v3.1)**

- whisper.cpp releases: CI flag changes #3891, #3920, #3966
- Gentoo whisper.cpp ebuild: `GGML_NATIVE=OFF` caveat; arm64 keyword removed
- Downstream rebuild with `GGML_NATIVE=OFF`
- GitLab MR 212797: pipeline-event triggers; agent and deterministic flow steps
- GitLab blog: work item created trigger
- BuzzASR Yoruba model card: Whisper large-v3 zero-shot CER on FLEURS Yoruba
- BuzzASR Hausa results (mirror)

**Carried over from v2.0 (not re-verified)**

- Qt 6.10 CPU baseline
- InfluxDB #26150
- Illegal-instruction crashes in AI tools
- QEMU baseline CI guard example
- Quantization and low-resource languages
- Per-condition ASR release criteria
- GSF: user hardware and sustainability
- GSF pattern: optimize impact on customer equipment
- LOCO 2026: software-driven obsolescence
- Blue Angel for software (KDE Okular)
- Windows 10 end of support, 240M PCs
- x86-64 microarchitecture levels
- SCI · SCI for AI
- Google Cloud region carbon data

From working knowledge, checked at G-0 and G-1: LZCNT and TZCNT behavior, CPU feature sets, RHEL 10's x86-64-v3 baseline, QEMU CPU model names, and the claim that hosted CI runners are a mixed CPU fleet (H-1). ggml's `SOURCE_DATE_EPOCH` rule is now checked (§3.3).
