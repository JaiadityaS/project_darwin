# Rieux

**Rieux watches the floor, so no one is left behind.**

Every release raises the ceiling. Nobody watches the floor: the oldest CPU, the smallest memory and the weakest connection on which the release still works. Rieux is a release gate for [whisper.cpp](https://github.com/ggml-org/whisper.cpp). For every release, it proves the CPU, memory and connectivity floors and writes them into a Floor Manifest. When a floor rises, a repair step proposes a fix and the gate checks it again. Only a human can approve a release that leaves people behind.

The name comes from Dr. Bernard Rieux in Albert Camus's *The Plague* (1947). He does the work without heroics, keeps an honest record, and knows that the danger comes back. In our backtest, the floor of the official images changed 15 times in 18 months.

Built for the GitLab Transcend "Life After Code" hackathon (Path B, Hands-off). This project is whisper.cpp at commit [`0c7be696`](https://github.com/ggml-org/whisper.cpp/commit/0c7be696371069e0baa2515ed7aa08d5a5473aa6) (MIT, with its full history), plus the Rieux files. The whisper.cpp README is in [README.whisper.cpp.md](README.whisper.cpp.md).

- Live page: https://showcase-9a1941.gitlab.io/
- Architecture in six words: **agents propose, the Judge disposes, humans exclude.**

## The problem

The official whisper.cpp images crash with "illegal instruction" on normal computers:

- [#3510](https://github.com/ggml-org/whisper.cpp/issues/3510): the image `main-a1867e0` exits with code 132 at startup. Reporters had a 2024 laptop chip and a 2020 desktop chip. An image from two weeks before works. A stale bot closed the issue. There is no fix, and a user reported it again on 2026-10-03.
- [#3814](https://github.com/ggml-org/whisper.cpp/issues/3814): `main-cuda` crashes on a 2020 desktop CPU, and the CPU image works on the same machine. A stale bot closed it too.
- These two are not alone. A GitHub search for "illegal instruction" in whisper.cpp finds 39 issues and pull requests. We read a seeded sample of 20: 13 are crashes from instructions that the CPU could not run (65%), 4 do not show the cause, and 2 are about other things ([`spotcheck/`](.floor/evidence/spotcheck/illegal-instruction-2026-10-19.json)).

The cause is in the build:

- All 7 upstream Dockerfiles in `.devops/` build with ggml's default `GGML_NATIVE=ON`. So each image gets the instructions of the CPU of the CI machine that built it.
- Ordinary CI cannot see this. It tests a native build on the machine that built it, and that is the one CPU that always passes.
- The usual fix, `GGML_NATIVE=OFF` (in 8 upstream workflow files), is a trap. ggml then turns on AVX, AVX2, FMA, F16C and BMI2 by default, so the binary still needs a CPU from about 2013 or later.
- Upstream already has the inclusive recipe. Its release workflow builds x64 binaries with `GGML_CPU_ALL_VARIANTS` and `GGML_BACKEND_DL`. Its Docker workflow does not. Nothing checks that the two agree.

## What we measured

Every number here comes from a script in this project. The outputs are in [`.floor/evidence/`](.floor/evidence/README.md). The GitHub Actions runs are in our private development repository; the run IDs are in the evidence files.

**The build machine decides (hypothesis H-1, supported).** We scanned 61 official `main-<sha>` images from 2025-04 to 2026-10. 52 have the floor x86-64-v3, and 9 have x86-64-v4 (AVX-512). The floor changed 15 times, and 10 of these changes came with no change to the Dockerfiles, the CMake files or the ggml CPU code. For 38 commits, upstream built both a `main` and a `main-cuda` image from the same source, in the same workflow run. In 11 of them, the two images have different floors. Only the runner was different.

- The #3510 pair: `main-a1867e0` is x86-64-v4 + AVX512_VNNI (its `libggml-cpu.so` has EVEX code). `main-c62adfbd` is x86-64-v3.
- The same recipe gave x86-64-v3 on a GitHub runner (AMD EPYC, no AVX-512 visible) and x86-64-v4 on a GitLab runner (Intel Xeon Platinum 8581C, AVX-512). So the image that you download depends on which cloud machine built it.
- It happens on GitLab too. Of the 21 `main` pipelines of this project, 19 built the image on an Intel Xeon Platinum 8581C (x86-64-v4) and 2 on an AMD EPYC 7B13 (x86-64-v3). In each one, the judge found the level of the build machine. `main-0f7d064e` (pipeline 2970462438) is x86-64-v4. The next commit changed 7 files, all in `.floor/` and `README.md`, and `main-86e5dc5d` (pipeline 2970859268) is x86-64-v3 ([`runners/`](.floor/evidence/runners/runners.json)).

**The folk fix does not fix it.** We built whisper.cpp three ways and ran each `whisper-cli` under QEMU on four CPU models, with positive and negative controls:

| Build | Static floor | qemu64 | Nehalem | SandyBridge | EPYC-Milan |
|---|---|---|---|---|---|
| Native (upstream default) | x86-64-v3 | crash | crash | crash | runs |
| Folk fix (`GGML_NATIVE=OFF`) | x86-64-v3 | crash | crash | crash | runs |
| All variants (`GGML_CPU_ALL_VARIANTS`) | x86-64-v1 | runs | runs | runs | runs |

**Inclusion costs nothing on a modern CPU.** On one AVX2 runner (median of 5 runs, the same transcript from all builds):

| Build | CPU seconds per audio-minute |
|---|---|
| Native | 20.1 |
| Folk fix | 20.1 |
| All variants | 20.0 |
| Baseline x86-64 code only (what an old CPU loads) | 301.9 |

The difference between all-variants and the folk fix (0.4%) is smaller than the noise between runs (up to 5.1%). The image costs a little more to download: 518.7 MB for all variants and 506.4 MB for native, 12.3 MB (2.4%) more (the compressed size in the container registry, images `8db56978` and `40cc4d9b`, the fix MR !10 and its main pipeline).

**The other floors.** The smallest cgroup memory limit that transcribes: tiny 512 MB, base 512 MB, small 768 MB (peak RSS 177, 284 and 750 MB on GitLab). Offline: 0 network attempts in a new network namespace under strace. The download is 81.9 MB (the tiny.en model, `whisper-cli` and its libraries).

**Languages.** whisper.cpp at `0c7be696` transcribed 50 FLEURS test sentences per language with the tiny, base and small models ([`language.json`](.floor/evidence/language/language.json), GitHub Actions run 39233922646). A language is served when its word error rate (WER) with the f16 model is 30% or less (`language.usable_wer` in the policy). f16 WER:

| Language | tiny | base | small | Served |
|---|---|---|---|---|
| English (the control) | 14.2% | 9.3% | 7.6% | yes, at every size |
| Spanish | 18.0% | 12.4% | 8.2% | yes, at every size |
| Hindi | 134.7% | 108.7% | 58.6% | no |
| Tamil | 131.4% | 103.4% | 72.9% | no |
| Swahili | 127.9% | 95.3% | 77.4% | no |
| Hausa | 121.7% | 190.3% | 90.6% | no |
| Bengali | 166.6% | 127.9% | 221.5% | no |
| Yoruba | 202.0% | 115.7% | 199.9% | no |

- A WER above 100% is possible: the transcript has many more words than the reference.
- The q5_1 models (the smaller download) serve the same two languages at every size. Their WER differs from f16 by at most 1.5 points. Only for Spanish tiny is the difference larger than the noise: +1.5 points (paired-bootstrap 95% interval +0.1 to +3.0).
- 92 other whisper languages are not measured. The table is one run for this whisper.cpp commit. The release pipeline does not make it again, because each language takes about 25 runner-minutes.

**Footprint.** SCI (ISO/IEC 21031, Green Software Foundation Impact Framework 1.1.1): 0.00196 g CO2e per audio-minute for the all-variants build in Google Cloud northamerica-northeast1. Embodied carbon is 84.6% of it. The same work in us-central1 gives 0.0131 g, 6.7 times more. One release check of Rieux itself (the scan, the 4 QEMU probes, the memory, offline and judge jobs of GitLab pipeline 2960804030) gives 0.36 g CO2e on the GitLab runners in us-east1: 486 vCPU-seconds, metered in the cgroup of each job. This is a lower bound, because the build and the unit tests are not in it. The backtest itself downloaded 27,470 MB (the config blob and the `/app` layer of 121 images) and used 18.4 runner-minutes in two sweep runs ([`footprint-2026-10-15.json`](.floor/evidence/backtest/footprint-2026-10-15.json)). We give it in bytes and minutes only, with no carbon value. ΔM, the embodied carbon of the devices that a floor raise could force people to replace, is a separate scenario with a range ([`.floor/scenarios/`](.floor/scenarios/)). Per 10,000 x86 users, a raise from x86-64-v1 to x86-64-v2 (a build without the baseline CPU variant) gives 0.7 to 35 kg CO2e, a raise to x86-64-v3 (the folk fix) gives 30 to 1,651 kg CO2e, and a raise to x86-64-v4 (upstream's recipe on an AVX-512 build machine) gives 889 to 87,338 kg CO2e. The inputs are the CPU features in the Steam Hardware Survey (September 2026), two Dell product carbon footprints, and a share p of 1% to 5% of affected people who replace their device. ΔM is never added into SCI.

## What Rieux adds

| # | Claim | In one line |
|---|---|---|
| N1 | **Floor Manifest:** a per-release in-toto statement of who can use the release, with proof per floor and a diff to the last release | An SBOM says what is inside. VEX says if it is exploitable. A Floor Manifest says who can still use it. |
| N2 | **Population regression** blocks a release. The only exception is a Leave-Behind Notice that a human approves | A deprecation notice for people, not for APIs. |
| N3 | **Inverted autonomy** as a Pareto ratchet: automation acts alone only when no floor rises | A ratchet for inclusion. |
| N4 | **ΔM:** the embodied carbon that a floor raise could force, beside SCI | The carbon of the hardware that your release throws away. |

What we do not claim: QEMU, elfx86exts-style instruction scans, x86-64 levels, CPU dispatch, cgroups, SCI and in-toto are existing tools. We combine them. The inclusive build recipe is upstream's own. Rieux adds the gate that sees when one pipeline uses it and another does not.

Prior art:

| Prior art | What it does | What Rieux adds |
|---|---|---|
| AppStream `<requires>` | Apps declare memory and network needs | Proof per release, not a declaration |
| glibc ISA-level markers, glibc-hwcaps | Mark or pick libraries by x86-64 level at load time | Proof over every artifact of a release, plus governance |
| Go `GOAMD64=v1`; Rust and Python platform tiers | A policy for supported targets | A check on each release, and more than the CPU |
| Android minSdkVersion; browserslist | Declared floors | Proven floors with several dimensions and a diff |
| Accessibility CI (axe, pa11y) | Blocks releases that regress for a population | Hardware, memory and connectivity, and only a human can exclude |
| Lint and coverage ratchets | One-way quality policies | A one-way inclusion policy with a signed exception |
| Blue Angel for software | A one-time audit; supports hardware at least 5 years old | A proof on every release |

## How it works

```text
Push to main, a merge request or a tag
  │
  ▼
check ─► build ─► scan (static CPU floor) ─► probe ×4 (QEMU, with controls)
                  memory (cgroup limits)  ─► offline (no network, strace)
  │
  ▼
judge (a script): each floor held, lowered, raised or inconclusive
  │
  ├── all held ──► manifest ─► page
  │
  └── a floor raised
        ├── repair: an agent proposes a fix MR; the gate checks it again
        ├── still raised: a script applies upstream's inclusive config; the gate checks it again
        └── still raised: draft a Leave-Behind Notice. Only a human approves it.
```

- The policy is [`.floor/policy.yml`](.floor/policy.yml): CPU x86-64-v1, the memory limits, offline required. A looser policy needs a merged and approved notice (`floor ratchet`).
- Code owners own the gate: the policy, the tools, `.gitlab-ci.yml` and `.gitlab/ci/` ([`.gitlab/CODEOWNERS`](.gitlab/CODEOWNERS)). An agent MR may change only `.devops/*.Dockerfile`, `deploy/` and `.floor/overrides/` (`floor paths`).
- The judge is a script, not a model. Scripts decide floors.
- Two more flows use the proof and never set a floor ([`.floor/flows/`](.floor/flows/)). Field triage answers a new issue about a CPU, memory or language problem with one note: the CPU model of the gate's probe that matches the reporter's CPU, and where the proof is. Release summary posts the "Who this release serves" lines of each release as one note on the issue [Rieux release summaries](https://gitlab.com/gitlab-ai-hackathon/transcend-october-2026/43085222/showcase/-/issues/2).

## DevSecOps stages

Status on 2026-10-21. "Runs" means that it runs in this project's GitLab pipeline. "Local" means that it is written and tested, but has not run on GitLab yet.

| Stage | What Rieux does | GitLab feature | Status |
|---|---|---|---|
| Plan | Leave-Behind Notices are planned, reviewed decisions. The field triage flow answers each new floor issue | MR templates, labels, issues, flow triggers | Runs (`floor notice` in the check job). The field triage flow is saved and on, with the trigger "Work item: Created". On issue [#2](https://gitlab.com/gitlab-ai-hackathon/transcend-october-2026/43085222/showcase/-/issues/2), which is not a floor report, its gate answered "skip" and it posted no reply, as planned. It has not answered a floor issue yet |
| Create | After a failed Judge, a script makes the canned build-config patch (`fallback` job), then the notice draft (`notice-draft` job). CI cannot push, so the floor-repair flow commits the patch and opens the fix MR | Merge requests, MR widget artifacts, flows | Runs: on 2026-10-21, the flow had opened 14 fix MRs (!1 to !12, !14 and !15) for 14 failed `main` pipelines. 12 came 1.6 to 2.9 min after the failed pipeline ended, and the other two after 4.3 and 8.9 min ([`repairs.json`](.floor/evidence/repair/repairs.json), from the GitLab API). The notice path ran on [!13](https://gitlab.com/gitlab-ai-hackathon/transcend-october-2026/43085222/showcase/-/merge_requests/13), a proposal by the owner to remove the baseline CPU variant: the gate raised the CPU floor to x86-64-v2, `fallback` had no patch, and `notice-draft` wrote the draft (job 17337464293; ΔM 0.7 to 35 kg CO2e per 10,000 x86 users). The owner refused it and closed the MR ([`notice/`](.floor/evidence/notice/drafts.json)) |
| Verify | Static CPU gate, QEMU on 4 CPU models, memory limits, offline tripwire, the Judge | CI/CD, cache, artifacts | Runs. The gates of fix MRs !3, !5, !6, !7, !10, !11, !12, !14 and !15 held every floor (pipelines 2961110649, 2961210282, 2961810145, 2969259993, 2969425658, 2970335928, 2970418568, 2970478794 and 2970973362) |
| Secure | Offline tripwire, pinned model hash, the image by digest; the Floor Manifest signed as an attestation | Container registry, keyless signing (GitLab ID token, Sigstore) | Runs: the attest job signed and verified the manifest (pipeline 2961110649, job 17270217868) |
| Package | The image of the release, checked by its digest | Container registry | Runs |
| Release | `-floor.N` tags and "Who this release serves" notes | Releases, protected tags | Partly: the herald job wrote the "Who this release serves" text from the signed manifest (pipeline 2961210282, job 17270780571). The tag and the release have not run yet. The release summary goes to issue [#2](https://gitlab.com/gitlab-ai-hackathon/transcend-october-2026/43085222/showcase/-/issues/2) after the first release; it has not run yet |
| Configure | The service image (the checked image plus an upload gateway: 30 s cap, rate limits, no storage) with a smoke test; Cloud Run in a low-carbon region | Container registry, OpenTofu state, environments | The `service` job transcribes `samples/jfk.wav` in 3.3 s (pipeline 2960909623). Its `GET /floor` gives the host level and the ggml CPU variant that loaded: x86-64-v4 and `sapphirerapids` for the canned image (pipeline 2961810145, job 17274238498). Cloud Run is planned |
| Monitor | The Rieux page with the backtest, the floors, the languages, SCI, ΔM and the repair loop | Pages | Runs |
| Govern | The ratchet, code owners, the agent path allowlist, the human-only notice | CODEOWNERS, approval rules | Runs (`floor ratchet`, `floor paths`) |

The first `main` pipelines are red on purpose. Upstream's recipe gives the CPU floor of the GitLab runner (x86-64-v4 in 19 of 21 `main` pipelines, x86-64-v3 in 2), and the policy asks for x86-64-v1. The repair loop must make it green.

## How to run

The tools are one Python package, `floor` (Python 3.10 or later). Most commands work on any OS. `probe`, `memory`, `offline`, `energy` and `meter` need Linux.

```bash
python -m venv .venv
source .venv/bin/activate              # Windows Git Bash: source .venv/Scripts/activate
pip install -e "./.floor[dev]"
python -m pytest .floor/tests -q
```

Scan the two #3510 images. The tags use the full commit hash. This pulls only the `/app` layer from ghcr.io:

```bash
python -m floor image main-a1867e0dad0b21b35afa43fc815dae60c9a139d6 main-c62adfbd1ecdaea9e295c72d672992514a2d887c
```

Scan your own build, and run it on an old CPU model (Linux, QEMU 7.2 or later). In a whisper.cpp checkout, after `cmake -B build && cmake --build build` and `sh ./models/download-ggml-model.sh tiny.en`:

```bash
python -m floor scan build/bin
python -m floor probe --cpu Nehalem -- build/bin/whisper-cli -m models/ggml-tiny.en.bin -f samples/jfk.wav
```

Read the repair loop and the build machines of a GitLab project from its public API and job logs (no token), then make the Rieux page from the evidence:

```bash
python -m floor repairs --api https://gitlab.com/api/v4 --project 87296266 --out .floor/evidence/repair/repairs.json
python -m floor runners --api https://gitlab.com/api/v4 --project 87296266 --web https://gitlab.com/gitlab-ai-hackathon/transcend-october-2026/43085222/showcase --out .floor/evidence/runners/runners.json
python -m floor page --out site
```

On GitLab, the pipeline in [`.gitlab-ci.yml`](.gitlab-ci.yml) runs on each push to `main`, on each merge request, on each tag and when you run it from the web page. Run `python -m floor <command> -h` for each command.

## Layout

| Path | Contents |
|---|---|
| `.floor/floor/` | The `floor` Python package |
| `.floor/tests/` | Unit tests |
| `.floor/policy.yml` | The floor policy and its JSON Schema |
| `.floor/evidence/` | Measured results, with the run that made each file |
| `.floor/evidence/repair/` | The repair loop on GitLab: each fix MR, its time and its gate (`floor repairs`), with a note for each gate that failed |
| `.floor/evidence/runners/` | H-1 on GitLab: the build machine and the CPU floor of each `main` pipeline (`floor runners`) |
| `.floor/impact/` | Impact Framework manifests and the coefficients for SCI |
| `.floor/notices/` | Approved Leave-Behind Notices |
| `.floor/scenarios/` | ΔM scenarios |
| `.floor/overrides/` | Build overrides that the repair step may change |
| `.floor/flows/` | The flow definitions: floor repair, field triage, release summary and the trigger probe |
| `.floor/DECISIONS.md` | What the IDs in brackets mean, such as `F4.3` or `D-018`: the requirements, the plan sections and the design decisions |
| `.gitlab-ci.yml`, `.gitlab/ci/` | The GitLab pipeline |
| Everything else | whisper.cpp at `0c7be696` |

## Sources

- whisper.cpp issues [#3510](https://github.com/ggml-org/whisper.cpp/issues/3510) and [#3814](https://github.com/ggml-org/whisper.cpp/issues/3814)
- Upstream [`.devops/` Dockerfiles](https://github.com/ggml-org/whisper.cpp/tree/master/.devops) and [workflows](https://github.com/ggml-org/whisper.cpp/tree/master/.github/workflows) (`docker.yml`, `release.yml`)
- [ggml CMake options](https://github.com/ggml-org/whisper.cpp/blob/master/ggml/CMakeLists.txt) (`GGML_NATIVE`, `GGML_CPU_ALL_VARIANTS`, `GGML_BACKEND_DL`)
- Official images: `ghcr.io/ggml-org/whisper.cpp`
- [x86-64 microarchitecture levels](https://gitlab.com/x86-psABIs/x86-64-ABI)
- [FLEURS](https://huggingface.co/datasets/google/fleurs) speech dataset (test split), for the language table
- [Software Carbon Intensity (SCI)](https://sci.greensoftware.foundation/) and the [Impact Framework](https://if.greensoftware.foundation/)
- [Google Cloud region carbon data](https://cloud.google.com/sustainability/region-carbon)
- For ΔM: the [Steam Hardware & Software Survey](https://store.steampowered.com/hwsurvey/) (CPU features), the Dell product carbon footprints of the [Latitude 3550](https://i.dell.com/sites/csdocuments/CorpComm_Docs/en/carbon-footprint-latitude-3550.pdf) and the [Latitude 7300 25th Anniversary Edition](https://www.delltechnologies.com/asset/zh-tw/products/laptops-and-2-in-1s/technical-support/latitude-7300-25th-anniversary-edition-pcf-datasheet.pdf), and Intel ARK ([Celeron N4020](https://www.intel.com/content/www/us/en/products/sku/197310/intel-celeron-processor-n4020-4m-cache-up-to-2-80-ghz/specifications.html), [Core Ultra 7 155H](https://www.intel.com/content/www/us/en/products/sku/236847/intel-core-ultra-7-processor-155h-24m-cache-up-to-4-80-ghz/specifications.html), [Atom N2800](https://www.intel.com/content/www/us/en/products/sku/58917/intel-atom-processor-n2800-1m-cache-1-86-ghz/specifications.html))
- [in-toto attestation framework](https://github.com/in-toto/attestation)
- GitLab docs: [Duo Agent Platform triggers](https://docs.gitlab.com/user/duo_agent_platform/triggers/) and [custom flows](https://docs.gitlab.com/user/duo_agent_platform/flows/custom/)

## License

whisper.cpp is MIT ([LICENSE](LICENSE), the ggml authors). The Rieux files are MIT too.
