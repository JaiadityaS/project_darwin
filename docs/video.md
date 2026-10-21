# Video: script and shot list (T-91)

Draft. The target is 2:50 (the limit is under 3:00). The video must be public on YouTube and show the project working.

Rules for every shot:

- Real runs only. Each shot shows a real pipeline, job, MR or page. The "Proof" column names it.
- No third-party trademarks and no copyrighted music (the rules). Keep other companies' logos and product names off the screen: crop the logo off an issue page on the upstream host, and do not show the README "Sources" list or the scenario files, which name hardware and survey vendors. The voice-over may say "an official image" and "a 2024 laptop chip".
- No made-up people. The plan's two personas, and the claim that a "faster" setting doubles the Yoruba errors, are not measured. They are not in this script.
- Do not name a CPU model that was not measured. Say "a Sandy Bridge class desktop", which is the QEMU model `SandyBridge`.
- Voice-over: simple English, about 2.5 words per second, at most about 400 words. Burn in the captions.

Status: "Ready" means that the proof is on GitLab now. "Needs" names what must happen first.

## Beats

| Time | Screen | Voice-over | Proof | Status |
|---|---|---|---|---|
| 0:00–0:20 | The log of a QEMU probe: the upstream image stops with SIGILL on the CPU model SandyBridge. Then the text of issue #3510 (no logo) | "whisper.cpp turns speech into text, offline, on ordinary computers. Its official image does not start on a 2024 laptop chip. Illegal instruction. The computer works. The release decided that it cannot." | Probe job 17330199448 (main pipeline 2969385744): `SandyBridge x86-64-v2 fail -4 SIGILL`, controls `+v2:pass -v3:fail`; issue #3510 | Ready |
| 0:20–0:40 | The Rieux page: the backtest timeline | "We scanned 61 official images. The CPU floor changed 15 times. 10 of these changes came with no change to the build files. Nobody decided it. The build machine did." | Rieux page; `.floor/evidence/backtest/` | Ready |
| 0:40–1:20 | Main pipeline: the judge job is red. The MR list: the floor-repair flow opens the fix MR. The MR pipeline: every job green | "Rieux is a release gate. It runs the image on four CPU models under QEMU, with memory limits and no network. A script judges the floors. Here the floor rose, so the gate failed. Two minutes later, an agent flow opened a fix MR with upstream's own inclusive build config. The gate checked the fix again: every floor held, and the manifest was signed." | Main pipeline 2969385744 (judge failed), MR !10 (2.1 min later), MR pipeline 2969425658 (every job passed: 4 probes, memory, offline, judge, attest, herald) | Ready |
| 1:20–1:35 | The Rieux page: the language table | "A floor is not only a CPU. With 50 test sentences per language, English and Spanish are served at every model size. Six languages are not served. Rieux says so in every release." | `.floor/evidence/language/language.json`, run 39233922646 | Ready |
| 1:35–2:00 | The Leave-Behind Notice draft (the `notice-draft` job), then the ΔM section of the Rieux page | "Sometimes a raise is the right call. But only a human can make it. Rieux drafts a Leave-Behind Notice with ΔM: the carbon of the devices that the raise could make people throw away. For a raise to x86-64-v4, that is 889 to 87,338 kilograms of CO2 for each 10,000 users." | A notice MR from the template `Leave-Behind-Notice.md`; the ΔM section of the Rieux page | Needs: a real trade-off that the owner decides (STATE, "Needs a human"). The `notice-draft` job writes a draft only when the canned config is on the branch and the gate still fails. On main pipeline 2969385744 it wrote "no draft: the canned inclusive config is not on this branch yet". The ΔM section: after the next GitLab sync |
| 2:00–2:15 | The test issue and the field triage flow's answer | "A user reports a crash on a Sandy Bridge class desktop. The triage flow answers in minutes, with the probe that matches that CPU." | AC-F11 test issue | Needs: the first `-floor` release (T-42), then the one test issue (owner's yes, at the end) |
| 2:15–2:40 | The deployed service: `GET /floor` and one transcription. Then the SCI numbers on the Rieux page | "The checked image runs as a service in a low-carbon region. 0.002 grams of CO2 for each audio-minute. Embodied carbon is 85 percent of it." | Cloud Run URL; SCI in the README | Needs: Cloud Run (T-06, T-50, T-51). Until then, the `service` job (pipeline 2960909623: `samples/jfk.wav` in 3.3 s) |
| 2:40–2:50 | Title card: Rieux | "Raise the ceiling. Keep the floor." | - | Ready |

## Shot list (URLs)

All links are under `https://gitlab.com/gitlab-ai-hackathon/transcend-october-2026/43085222/showcase`.

1. `/-/jobs/17330199448`: the SandyBridge probe of the upstream recipe.
2. `https://showcase-9a1941.gitlab.io/`: the Rieux page (the timeline, the language table, SCI, ΔM).
3. `/-/pipelines/2969385744`: the main pipeline with the red judge.
4. `/-/merge_requests/10`: the fix MR. Show the time and the commit author "Rieux floor repair" (the flow). The MR author is the owner's account, because the flow acts for the person whose action started it.
5. `/-/pipelines/2969425658`: the MR pipeline, every job green.
6. Later: the notice MR, the test issue, the release page with "Who this release serves", the Cloud Run URL.

## Recording notes

- 1920 × 1080, browser zoom 125%, no bookmarks bar, no other tabs.
- Record the GitLab pages signed out, if the page shows the same content, so that no account menu is on screen.
- If the release loop runs before recording, replace beat 3 with the release: tag, gate, fix MR, merge, `-floor.N` release.
