# 2026-10-19 jaiadityas session 9
- Tasks: T-62, then the local items of STATE.md (T-61 catalog work, T-63 trigger check, GitLab sync).
- Run 39214706460 (8 languages, 50 clips, 0c7be696): all jobs passed. English is the control: f16 WER tiny 14.2%, base 9.3%, small 7.6%. Spanish small 8.2%. The other six languages are not served (small f16 WER 58% to 200%).
- Fault found: 56 of 100 Bengali small transcripts and 60 of 100 Yoruba small ones had bytes that are not UTF-8. The `-otxt` file has one segment per line, and a segment can end inside a character. `read_hyp` now joins such a line to the next one without the break (D-031). The table also gives the decoding as `-l <lang>`, not the flags of the first language.
- Not committed: the table of run 39214706460, because the fault changes the Bengali, Hindi and Yoruba rows. A new run with the fix follows.
- T-63: the new-trigger form has the event "Work item" with the actions "Created" and "Status changed". Nothing saved (D-033). Pipeline events have "Running", "Passed", "Failed" and "Canceled".
