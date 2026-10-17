# Leave-Behind Notices

One file per notice: `NNNN-<dimension>.md`, from `.gitlab/merge_request_templates/Leave-Behind-Notice.md`.

- `floor notice .floor/notices/*.md` checks that each notice is complete.
- `floor ratchet` accepts a looser policy only when a notice for that dimension is already on the target branch.
- A merged notice goes into the release notes and the manifest (PRD F6.2).
- `floor notice-draft` writes a draft when the agent's fix and the canned config did not hold a floor (PRD F4.5). The `notice-draft` job of a failed pipeline keeps it as `out/notice/NNNN-<dimension>.md`. To accept the change, a code owner adds the draft here in a new MR, fills the placeholders and approves the MR. Agents and the merge-bot cannot approve it (F6.1).
