"""Leave-Behind Notice (F6, §11.2): parse, check that it is complete, check who approved it, and
draft one when the fix and the fallback did not hold a floor (F4.5)."""

from __future__ import annotations

import html
import re

from . import delta_m

FIELDS = ("Floor change", "Reason", "Tried first", "Who is affected", "ΔM (scenario)", "Guidance", "Approved by")
HEADING = "## Leave-Behind Notice"
# The §11.2 template values. A draft keeps the value of each field that no evidence fills, for a human.
PLACEHOLDERS = {
    "Floor change": "<dimension>: <from> → <to>, or a trade-off between <A> and <B>",
    "Reason": "<why the change is needed>",
    "Tried first": "<inclusive options tried, with job links>",
    "Who is affected": "<population estimate: labelled proxy, source and range>",
    "ΔM (scenario)": "<low–high kgCO₂e with inputs; reported beside SCI, never inside it>",
    "Guidance": "<what affected users should do: artifact, model or version>",
    "Approved by": "<code owner>   (agents and the merge-bot cannot approve)",
}
SUMMARY_CHARS = 300
_ON_UNFIXABLE = {"ship_last_held": "Production keeps the last held build until a code owner decides (F6.3).",
                 "block": "No release ships until a code owner decides."}
_LINE = re.compile(r"^(" + "|".join(re.escape(f) for f in FIELDS) + r"):[ \t]*(.*?)[ \t]*$", re.MULTILINE)
_PLACEHOLDER = re.compile(r"<[^<>]+>")
_NUMBERED = re.compile(r"^(\d{4})-.+\.md$")


def parse(text: str) -> dict[str, str]:
    return {match.group(1): match.group(2) for match in _LINE.finditer(text)}


def problems(text: str, draft: bool = False) -> list[str]:
    """Empty list = complete. ``draft`` allows an empty approver (the notice MR is still open)."""
    found = []
    if HEADING not in text:
        found.append(f"no '{HEADING}' heading")
    fields = parse(text)
    for field in FIELDS:
        value = fields.get(field, "")
        if draft and field == "Approved by":
            continue
        if not value:
            found.append(f"{field}: missing")
        elif _PLACEHOLDER.search(value):
            found.append(f"{field}: still has a placeholder")
    return found


def approval_problems(approvers: list[str], code_owners: list[str], blocked: list[str]) -> list[str]:
    """F6.1: at least one code owner approved, and no agent account or merge-bot approved.

    ``approvers`` comes from the GitLab MR approvals API (usernames); ``blocked`` lists the agent
    service accounts and the merge-bot."""
    found = []
    bad = sorted(set(approvers) & set(blocked))
    if bad:
        found.append(f"approved by an agent or bot account: {', '.join(bad)}")
    if not set(approvers) & (set(code_owners) - set(blocked)):
        found.append("no code-owner approval")
    return found


def next_name(names: list[str], dimensions: list[str]) -> str:
    """NNNN-<dimension>.md, with the number after the highest one in ``names``."""
    numbers = [int(match.group(1)) for match in map(_NUMBERED.match, names) if match]
    return f"{max(numbers, default=0) + 1:04d}-{'-'.join(dimensions)}.md"


def draft(verdict: dict, policy: dict, *, diagnosis: str = "", truncated: bool = False, mr: str | None = None,
          evidence: str | None = None, flags: str | None = None, scenarios: dict[str, dict] | None = None) -> str:
    """A draft notice for the floors that still need one after the fix and the fallback (F4.5).

    ``verdict`` is `floor judge` output for the branch, ``policy`` the resolved policy, ``diagnosis`` the MR
    description (the agent states the cause there, F4.2), ``mr`` and ``evidence`` the links to the MR and
    to the gate, ``flags`` the canned config when the fallback ran, and ``scenarios`` maps a scenario file
    to its `delta_m.compute` output. A field that no evidence fills keeps its placeholder.

    The MR text is data: the summary is escaped, and the full text is an indented code block, so it
    cannot add a field line, an approver or hidden HTML."""
    dimensions = list(verdict["missing_notice"])
    floors = verdict["floors"]
    name = _mr_name(mr)
    summary = _summary(diagnosis)
    values = dict(PLACEHOLDERS)
    values["Floor change"] = "; ".join(_change(d, floors[d], policy) for d in dimensions)
    values["Reason"] = (f"No inclusive option held the {' and '.join(dimensions)} floor. "
                        + (f"Diagnosis in {name}: {summary}" if summary else f"<the cause: {name} states none>"))
    tried = [f"the fix in {name} ({mr or '<MR link>'})"]
    if flags:
        tried.append(f"the canned inclusive config ({flags})")
    values["Tried first"] = "; ".join(tried) + f"; gate: {evidence or '<job link>'}"
    if scenarios:
        values["Who is affected"] = "; ".join(_affected(file, result) for file, result in scenarios.items())
        values["ΔM (scenario)"] = "; ".join(f"{delta_m.notice_line(result)} ({file})" for file, result in scenarios.items())
    keep = _ON_UNFIXABLE.get(policy.get("on_unfixable_raise"))
    if keep:
        values["Guidance"] = f"{keep} {PLACEHOLDERS['Guidance']}"

    lines = [HEADING, *(f"{field + ':':<18}{values[field]}" for field in FIELDS), "", "### Gate result", ""]
    lines += [f"- {d}: {_floor_text(d, floor)}" for d, floor in floors.items()]
    lines += [f"- {d}: not measured" for d in verdict.get("unmeasured", [])]
    lines += ["", f"Decision: {verdict['decision']}. Pareto: {verdict['pareto']}."
              + (f" Evidence: {evidence}" if evidence else "")]
    lines += ["", "### Diagnosis", "", f"The description of {name}"
              + (" (GitLab cut it short; the MR has the full text)" if truncated else "") + ":", ""]
    lines += [f"    {line}".rstrip() for line in diagnosis.strip().splitlines()] or ["    (empty)"]
    return "\n".join(lines) + "\n"


def _mr_name(url: str | None) -> str:
    iid = (url or "").rstrip("/").rsplit("/", 1)[-1]
    return f"MR !{iid}" if iid.isdigit() else "the MR"


def _summary(text: str) -> str:
    """The first paragraph of ``text`` that is not a heading or a comment, on one line and escaped."""
    text = re.sub(r"<!--.*?-->", "", text, flags=re.DOTALL)
    for block in re.split(r"\n[ \t]*\n", text.strip()):
        one = " ".join(" ".join(line for line in block.splitlines() if not line.lstrip().startswith("#")).split())
        if one:
            if len(one) > SUMMARY_CHARS:
                one = one[:SUMMARY_CHARS].rsplit(" ", 1)[0] + " …"
            return html.escape(one, quote=False)
    return ""


def _change(dimension: str, floor: dict, policy: dict) -> str:
    """'<dimension>: <from> → <to>' against the policy. The verdict does not name the previous release,
    so <from> stays when the floor meets the policy and rose only against the previous release."""
    below = floor.get("meets_policy") is False
    if dimension == "cpu":
        return f"cpu: {floor['policy'] if below else '<from>'} → {floor['x86_64']}"
    if dimension == "memory":
        limits = policy.get("memory_mb") or {}
        rows = [f"{model} {limits[model]} → {mb} MB" for model, mb in (floor.get("smallest_passing_mb") or {}).items()
                if mb is not None and limits.get(model) is not None and mb > limits[model]]
        return "memory: " + (", ".join(rows) or "<from> → <to>")
    if dimension == "connectivity":
        attempts = floor.get("network_attempts")
        return "connectivity: offline proven → not proven" + (f" ({attempts} network attempts)" if attempts else "")
    return f"{dimension}: <from> → <to>"


def _affected(file: str, result: dict) -> str:
    n = result["inputs"]["n_affected"]
    return f"{n['low']}–{n['high']} (N_affected in {file}; source: {n['source']})"


def _floor_text(dimension: str, floor: dict) -> str:
    if dimension == "cpu":
        value = f"{floor.get('x86_64')} ({floor.get('proof')} proof; policy {floor.get('policy')})"
    elif dimension == "memory":
        value = "smallest passing limit " + ", ".join(
            f"{model} {mb} MB" if mb is not None else f"{model} not measured"
            for model, mb in (floor.get("smallest_passing_mb") or {}).items())
    elif dimension == "connectivity":
        value = f"offline {floor.get('offline')}, {floor.get('network_attempts')} network attempts"
    else:
        value = ""
    met = {True: "meets the policy", False: "below the policy floor"}.get(floor.get("meets_policy"), "")
    text = ", ".join(part for part in (floor["status"], value, met) if part)
    return text + "".join(f"\n  - {note}" for note in floor.get("notes") or [])
