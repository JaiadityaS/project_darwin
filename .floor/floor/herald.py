"""Herald, the template part (PRD F12.1, T-46): "Who this release serves", from the Floor Manifest.

Every value in the text comes from the manifest, so a script (the Judge) set it. The agent part of Herald
(T-04: a short summary with the Duo CLI) is optional. When it is not there, this section is the whole
Herald output (PRD §9.2), and the release says so.
"""

from __future__ import annotations

LEVEL_TEXT = {
    "x86-64-v1": "any 64-bit x86 PC: the first AMD64 CPUs of 2003 and every x86-64 CPU since",
    "x86-64-v2": "64-bit x86 PCs with SSE4.2 and POPCNT: Intel Nehalem (2008), AMD Bulldozer (2011) and newer",
    "x86-64-v3": "64-bit x86 PCs with AVX2: Intel Haswell (2013), AMD Excavator (2015) and newer, but not many later "
                 "Pentium, Celeron and Atom chips",
    "x86-64-v4": "64-bit x86 PCs with AVX-512: mostly servers; most laptops and desktops have none",
}
# The CPU models of the QEMU probe (F3), oldest first.
MODELS = {
    "qemu64": "a generic x86-64 CPU",
    "Nehalem": "Intel, 2008",
    "SandyBridge": "Intel, 2011: AVX, no AVX2",
    "EPYC-Milan": "AMD, 2021",
}
SIZES = ("tiny", "base", "small", "medium", "large")
NOT_MEASURED = {"arm64": "Arm CPUs", "gpu-backends": "GPU backends", "language": "languages other than English"}


def _cpu(cpu: dict) -> str:
    level = cpu.get("x86_64") or "?"
    text = f"**CPU:** {LEVEL_TEXT.get(level, level)} (floor `{level}`, {cpu.get('status', '?')}"
    text += ", static proof of every ELF file)." if cpu.get("proof") == "static" else ")."
    dispatch = cpu.get("dispatch") or {}
    ran = [f"{m} ({MODELS[m]}: `{dispatch[m]}`)" for m in MODELS if dispatch.get(m)]
    failed = [f"{m} ({MODELS[m]})" for m in MODELS if m in dispatch and not dispatch[m]]
    if ran:
        text += " Under emulation it ran on " + ", ".join(ran) + "."
    if failed:
        text += " It did not run on " + ", ".join(failed) + "."
    return text


def _memory(memory: dict) -> str:
    passing = memory.get("smallest_passing_mb") or {}
    if not passing:
        return f"**Memory:** not measured ({memory.get('status', 'no result')})."
    sizes = sorted(passing, key=lambda s: SIZES.index(s) if s in SIZES else len(SIZES))
    parts = [f"{s} in {passing[s]} MB" for s in sizes]
    return ("**Memory:** each model transcribed the sample within this memory limit (no swap): "
            + ", ".join(parts) + ".")


def _connectivity(conn: dict) -> str:
    if conn.get("offline") != "proven":
        return f"**Connectivity:** offline use is not proven ({conn.get('status', 'no result')})."
    return (f"**Connectivity:** works with no network after one download of {conn.get('download_mb', '?')} MB "
            f"(the program and the smallest model); the offline run made {conn.get('network_attempts', '?')} "
            "network attempts.")


def who(statement: dict) -> str:
    """The "Who this release serves" section, as Markdown."""
    pred = statement.get("predicate") or {}
    floors = pred.get("floors") or {}
    lines = ["## Who this release serves", "",
             f"Measured by the Rieux gate for `{pred.get('release', '?')}` (commit `{(pred.get('commit') or '?')[:8]}`). "
             "Scripts set every value here.", ""]
    if "cpu" in floors:
        lines.append("- " + _cpu(floors["cpu"]))
    if "memory" in floors:
        lines.append("- " + _memory(floors["memory"]))
    if "connectivity" in floors:
        lines.append("- " + _connectivity(floors["connectivity"]))
    language = floors.get("language") or {}
    if language.get("served"):
        lines.append("- **Language:** served: " + ", ".join(language["served"]) + "."
                     + (" Not served: " + ", ".join(language["not_served"]) + "." if language.get("not_served") else ""))
    notices = pred.get("leave_behind_notices") or []
    raised = [name for name, floor in floors.items() if isinstance(floor, dict) and floor.get("status") == "raised"]
    if notices:
        left = "; ".join(str(n) for n in notices) + " (Leave-Behind Notice)."
    elif raised:
        left = f"the {', '.join(raised)} floor rose and no notice allows it, so the gate blocks this build."
    else:
        left = "nobody: this release has no Leave-Behind Notice."
    lines.append("- **Left behind:** " + left)
    unmeasured = [NOT_MEASURED.get(u, u) for u in pred.get("unmeasured") or []]
    if unmeasured:
        lines.append("- **Not measured:** " + ", ".join(unmeasured) + ".")
    sci = (pred.get("footprint") or {}).get("sci_gco2e_per_audio_minute")
    if isinstance(sci, (int, float)):
        lines.append(f"- **Footprint:** {sci:.3g} g CO2e per audio-minute (SCI).")
    return "\n".join(lines) + "\n"
