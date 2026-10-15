# Leave-Behind Notices

One file per notice: `NNNN-<dimension>.md`, from `.gitlab/merge_request_templates/Leave-Behind-Notice.md`.

- `floor notice .floor/notices/*.md` checks that each notice is complete.
- `floor ratchet` accepts a looser policy only when a notice for that dimension is already on the target branch.
- A merged notice goes into the release notes and the manifest (PRD F6.2).
