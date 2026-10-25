# Remaining work, in order

Written 2026-10-25 19:45 UTC. Deadline: **2026-10-27 13:00 UTC** (Devpost form submitted). About 41 hours.
Read this file first. STATE.md and TASKS.md have the history; this file has only what remains and how to do it.
This file is dev only. It never goes to GitLab, and T-99 deletes it.

Who: **owner** = the human (GitLab UI, GCP, public text, the video). **agent** = a local coding session.
Rules that still hold: AGENTS.md §2 (no AI attribution, human identity, no `--no-verify`), and "every number comes from a script".

## Status at a glance

| # | Item | Who | Needed for | State |
|---|---|---|---|---|
| 1 | GitLab sync of the new page (dev `c188b55`) and the evidence commit `2c4e51e` | agent | the live page | done (4bebbbac, pages job 17451675267) |
| 2 | Release loop 1: tag `v1.9.5-rieux.1`, merge its fix MR, get `-floor.1` | owner + agent | PRD §16.2, video, AC-F11 | done (MR !18, pipeline 2987186947, `v1.9.5-rieux.1-floor.1`). Open: `floor runners` refresh (needs the artifacts CDN; run it locally), then a sync |
| 3 | AC-F11: one field-test issue with real data | owner yes + agent | F11 | after 2 |
| 4 | T-61 check: the release summary note on issue #2 | agent | F12.3 | flow ran, note posted 21:53:43; owner to read it |
| 5 | Cloud Run deployed URL (T-06, T-50, T-51) | owner + agent | Path B rule: a live deployed URL | not started |
| 6 | Video under 3:00 (T-91, `docs/video.md`) | owner | submission | after 2 |
| 7 | Release loop 2: the folk fix (optional) | owner + agent | PRD §16.2 (3 loops) | after 2, if time |
| 8 | Open MRs !1 to !16: close or leave | owner | a clean project | after 2 |
| 9 | GitLab project description, `FLOOR_HUMANS` | owner | front page | any time |
| 10 | Last pass: README (T-90) and `docs/devpost.md` (T-92), remove every OPEN | agent + owner | submission | after 2, 5, 6 |
| 11 | T-99: delete `AGENTS.md` and `.agents/` in this repo; guard | agent | hygiene | last commit |
| 12 | Submit the Devpost form | owner | submission | before 2026-10-27 13:00 UTC |

Suggested order: 1 → 2 → 3 and 4 → 6 → 5 (start the GCP project early, in parallel) → 7 if time → 8, 9 → 10 → 11 → 12.
If Cloud Run is not live by 2026-10-27 06:00 UTC, stop item 5 and say in devpost.md that the deployed URL is the GitLab Pages page.

## 1. GitLab sync (agent)

The owner gave a standing yes for the sync script, after a dry run and a residue check.

```bash
cd /d/VibeCodingProjects/gitLabHackathon/project_darwin && source .venv/Scripts/activate
python -m pytest .floor/tests -q -p no:cacheprovider     # expect 275 passed, 11 skipped
bash scripts/guard.sh tree
bash scripts/assemble-gitlab.sh                           # dry run: read the file list and the diff
```

Residue check on the dry run: author and committer are the owner; no trailer; no tool or vendor names in the diff
or in the paths. Then `bash scripts/assemble-gitlab.sh --push` (in PowerShell: `& "C:\Program Files\Git\bin\bash.exe" scripts/assemble-gitlab.sh --push`).

Done when: the `pages` job of the new `main` pipeline passes and https://showcase-9a1941.gitlab.io/ shows the new
layout (Ubuntu Mono, Mochi the cat, 9 numbered sections) with `assets/` served (fonts and sprites load, no 404).
Each sync starts a judge failure and a fix MR on `main`; that is expected.

## 2. Release loop 1 (owner, then agent)

Do NOT merge any open fix MR before this tag (STATE "Needs a human", order rule).

1. Owner: GitLab → Code → Tags → New tag. Name `v1.9.5-rieux.1`, from `main` (after item 1).
2. The tag pipeline fails at the judge. The floor-repair flow opens a fix MR in about 2 min.
3. Agent: check the MR pipeline (all jobs pass, the judge holds every floor). Use the commands of
   `python -m floor repairs --api https://gitlab.com/api/v4 --project 87296266 --out .floor/evidence/repair/repairs.json`.
4. Owner: merge that fix MR (the one whose failed pipeline is the TAG pipeline).
5. The `main` pipeline of the merge commit: judge passes, `attest` signs, `herald` writes, `release` cuts
   `v1.9.5-rieux.1-floor.1`. Risk (D-024): the job token may not create a protected tag. Then the `release` job log
   shows an API error. Fix: Settings → Repository → Protected tags, allow the tag pattern, or make the tag by hand
   from the merge commit and record it as a deviation in DECISIONS.md.
6. Agent: refresh the evidence (`floor repairs`, `floor runners`, see the session-10 log for the full commands), update
   README, devpost.md and STATE with the release, the pipeline ids and the manifest. Commit and sync.

Done when: the release `v1.9.5-rieux.1-floor.1` exists with a signed manifest, and the README links it.

## 3. AC-F11 field-test issue (owner yes, agent)

Only after item 2, because the reply points to the latest release. ONE issue only. The owner already said yes to one
issue with real data; confirm once more just before posting, because it is public.
Text: STATE "Next agent" item 3 has the draft (title, body, probe job 17329574751, pipeline 2969295146,
ggml-org/whisper.cpp#3510). Say in the body that it is a test.
Done when: the field-triage flow replies in under 15 min with the matching gate CPU model and the latest release.
Record the issue, the reply time and the session id in README and devpost.md.

## 4. T-61 check (agent)

After the release pipeline of item 2: issue #2 must get a note of at most 8 lines, the same text as the `herald` log
between `--- BEGIN summary ---` and `--- END summary ---`, with the tag line. Record the note link in STATE.

## 5. Cloud Run deployed URL (owner first, then agent)

Path B needs a public deployed URL that stays live until about 2026-11-16. Now only GitLab Pages is live.
`infra/` does not exist yet. `deploy/service.Dockerfile` and the `service` image job exist (gateway.py, 30 s cap).

1. Owner (T-06): a Google Cloud project with billing and a budget alert (for example 10 USD). Enable Cloud Run,
   Artifact Registry, IAM Credentials. Give the agent the project id. No keys in the repo or in chat.
2. Owner: set up Workload Identity Federation for GitLab (pool + provider for `gitlab.com`, attribute condition on
   project 87296266), and a deploy service account with `roles/run.admin`, `roles/artifactregistry.writer`,
   `roles/iam.serviceAccountUser`. Put the provider name and the SA email as CI variables (not secret).
3. Agent (T-50): `infra/` OpenTofu for the service in a low-CO₂ region (`northamerica-northeast1`, as in the SCI
   evidence), max instances 1, min 0, 1 vCPU, 1 GiB. Add a `deploy` job in `.gitlab-ci.yml` after `release`:
   push the `service` image, then `gcloud run deploy` with WIF (no key file).
4. Agent (T-51, short form): a smoke test job (POST the JFK sample, expect the known words). Rollback = the previous
   revision (`gcloud run services update-traffic --to-revisions`).
5. Fallback: if steps 1–2 are not done by 2026-10-27 06:00 UTC, drop items 3–4, keep the Pages URL, and remove
   `opentofu` and `google-cloud-run` from "Built with" in devpost.md.

Done when: the URL answers, the smoke test passes, and README and devpost.md give the URL.

## 6. Video (owner)

Script and shot list: `docs/video.md`. Beats 1 to 5 are ready on GitLab. It needs the release of item 2 (and the
Cloud Run URL if live). Under 3:00, public on YouTube. Show the new page with Mochi at the start or the end.
Put the URL in devpost.md.

## 7. Release loop 2, the folk fix (optional)

Only if items 2–6 are done. A person commits `CMAKE_ARGS="-DGGML_NATIVE=OFF"` in `.devops/main.Dockerfile` on `main`
(floor becomes x86-64-v3), then tags `v1.9.5-rieux.2` from `main`. Merge the fix MR of the TAG pipeline. Result:
release 2 and the manifest diff between two releases (AC-F5). If skipped, devpost.md says 2 loops ran
(1 repair, 1 notice), not 3.

## 8. Open MRs (owner)

MRs !1 to !16 are open fix MRs of branch pipelines (all listed in `.floor/evidence/repair/repairs.json`). After item 2,
close them with a short comment ("evidence of the repair loop; kept as a record") or leave them open. Do not merge
them: a merge without a tag gives no release. The page and README count them as opened, not merged.

## 9. Project settings (owner)

- Project description: the proposed text is in STATE "Needs a human" (public text: the owner posts it).
- `FLOOR_HUMANS` in `.gitlab-ci.yml`: add teammates' GitLab usernames, if any (D-014). Agent edits the file on request.

## 10. Last pass on the texts (agent, owner reads)

- `README.md` (T-90) and `docs/devpost.md` (T-92) must agree. Every number names a file, a run or a pipeline.
- Remove every `OPEN` in devpost.md: the deployed URL, the video URL, the release loops, AC-F11, "Built with".
- Positioning (competitor scans of Oct 16 and Oct 22): pitch the question "Which machines does this release still run
  on?" and the hardware floors (CPU, memory, offline). Do not lead with "release gate": many entries use that label.
- Check the live page once more after the last sync.

## 11. T-99 hygiene (agent, last commit)

In this repo only: delete `AGENTS.md` and `.agents/` (this file too), run `bash scripts/guard.sh tree`, run the tests,
commit, push. These files never went to GitLab (`assemble-gitlab.sh` copies only `.floor`, `.gitlab`,
`.gitlab-ci.yml`, `deploy`, `infra`, `README.md`). Keep a local copy of this file until the form is submitted.

## 12. Submit (owner)

Devpost form from `docs/devpost.md`: GitLab project link, deployed URL, video URL, text. Before 2026-10-27 13:00 UTC.
Aim for the team target of 2026-10-26.

## Done in the last session (2026-10-25)

- Page redesign from the owner's design (dev `c188b55`): Ubuntu Mono (bundled, Ubuntu Font Licence), Mochi the cat
  (pixel sprites in `.floor/floor/page_assets/`, copied to `assets/` by `build()`), one small inline script for Mochi
  and the language filter, 9 numbered sections, the hero card from `release/diff.md`. Tests changed to match:
  one inline script, no external script, no network request in the head. 275 passed, 11 skipped; guard passes.
- Evidence of MR !16 and main pipeline 2973711384 (dev `2c4e51e`): 15 fix MRs, 22 main pipelines. Not synced yet.
