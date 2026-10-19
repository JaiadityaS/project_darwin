"""Language table (PRD F9.1, F9.2, T-62): which languages and model sizes whisper.cpp serves, on FLEURS.

The `language` workflow runs whisper-cli on a seeded sample of FLEURS test clips per language, with each
model size at f16 and at one quantization level, and with pinned decoding (F9.2). This module chooses the
clips, scores the transcripts and makes the table:

- the word error rate (WER) and the character error rate (CER) after one simple normalizer,
- the drift: the WER of the quantized model minus the WER at f16, with a paired-bootstrap 95% interval,
- served: the f16 WER is at most `language.usable_wer` of the policy. The table is report-only (F9.1).
"""

from __future__ import annotations

import codecs
import csv
import random
import re
import unicodedata
from pathlib import Path

# FLEURS configuration -> whisper language code. The first one is the control.
FLEURS = {"en_us": "en", "es_419": "es", "hi_in": "hi", "bn_in": "bn", "ta_in": "ta",
          "sw_ke": "sw", "ha_ng": "ha", "yo_ng": "yo"}
_BRACKETS = re.compile(r"\[[^\]]*\]|\([^)]*\)")
_LANG = re.compile(r'\{\s*"([a-z]+)",\s*\{\s*\d+,\s*"([^"]+)"')


def read_tsv(path: str | Path) -> list[dict]:
    """The rows of a FLEURS split: sentence id, wav file name, raw transcription."""
    with open(path, encoding="utf-8", newline="") as f:
        return [{"id": int(row[0]), "file": row[1], "ref": row[2]}
                for row in csv.reader(f, delimiter="\t", quoting=csv.QUOTE_NONE) if len(row) > 2]


def choose(rows: list[dict], n: int, seed: int = 62) -> list[dict]:
    """One recording per sentence (the first by file name), then a seeded sample of n sentences."""
    first: dict[int, dict] = {}
    for row in sorted(rows, key=lambda r: (r["id"], r["file"])):
        first.setdefault(row["id"], row)
    ids = sorted(random.Random(seed).sample(sorted(first), min(n, len(first))))
    return [first[i] for i in ids]


def normalize(text: str) -> str:
    """NFKC, lower case, no bracketed text, punctuation and symbols to spaces. Combining marks stay,
    because the vowel signs of Indic scripts are marks."""
    text = _BRACKETS.sub(" ", unicodedata.normalize("NFKC", text).casefold())
    return " ".join("".join(" " if unicodedata.category(c)[0] in "PS" else c for c in text).split())


def edits(a: list | str, b: list | str) -> int:
    """Levenshtein distance: substitutions, deletions and insertions."""
    row = list(range(len(b) + 1))
    for i, x in enumerate(a, 1):
        prev, row[0] = row[0], i
        for j, y in enumerate(b, 1):
            prev, row[j] = row[j], min(row[j] + 1, row[j - 1] + 1, prev + (x != y))
    return row[-1]


def clip_score(ref: str, hyp: str) -> dict:
    ref, hyp = normalize(ref), normalize(hyp)
    return {"words": len(ref.split()), "word_edits": edits(ref.split(), hyp.split()),
            "chars": len(ref.replace(" ", "")), "char_edits": edits(ref.replace(" ", ""), hyp.replace(" ", ""))}


def _rates(clips: list[dict]) -> dict:
    words = sum(c["words"] for c in clips)
    chars = sum(c["chars"] for c in clips)
    return {"words": words, "wer": sum(c["word_edits"] for c in clips) / words if words else None,
            "cer": sum(c["char_edits"] for c in clips) / chars if chars else None}


def _open_tail(data: bytes) -> bool:
    """True if `data` ends inside a UTF-8 character."""
    decoder = codecs.getincrementaldecoder("utf-8")(errors="replace")
    decoder.decode(data, final=False)
    return bool(decoder.getstate()[0])


def read_hyp(raw: bytes) -> tuple[str, bool]:
    """The transcript in a whisper-cli -otxt file, and whether it had bytes that are not UTF-8.
    The file has one segment per line. Whisper tokens are bytes, so a segment can end inside a character, and
    the line break then splits that character: such a line joins the next one without the break. Bytes that are
    still not UTF-8 become U+FFFD, which `normalize` makes a space, so the broken word counts as wrong."""
    text = b""
    for line in raw.split(b"\n"):
        text += line if _open_tail(text) else (b" " if text else b"") + line
    decoded = text.decode("utf-8", errors="replace")
    return " ".join(decoded.split()), decoded != text.decode("utf-8", errors="ignore")


def score(clips: list[dict], hyp_root: str | Path, models: list[str]) -> dict:
    """Scores the whisper-cli -otxt output `<hyp_root>/<model>/<file>.txt` of every clip (`read_hyp`).
    A clip without output counts as an empty transcript (every word wrong)."""
    out = {}
    for model in models:
        base = Path(hyp_root) / model
        rows, missing, bad_utf8 = [], 0, 0
        for clip in clips:
            txt = base / f"{clip['file']}.txt"
            hyp, bad = read_hyp(txt.read_bytes()) if txt.exists() else ("", False)
            missing += not txt.exists()
            bad_utf8 += bad
            rows.append({"id": clip["id"], "hyp": hyp, **clip_score(clip["ref"], hyp)})
        seconds = base / "seconds"
        out[model] = {**_rates(rows), "missing": missing, "bad_utf8": bad_utf8,
                      "seconds": int(seconds.read_text().strip()) if seconds.exists() else None, "clips": rows}
    return out


def bootstrap(f16: list[dict], quant: list[dict], rounds: int = 2000, seed: int = 0) -> list[float]:
    """Paired-bootstrap 95% interval of the drift (quantized WER minus f16 WER), resampling clips."""
    rng = random.Random(seed)
    n, drifts = len(f16), []
    for _ in range(rounds):
        pick = [rng.randrange(n) for _ in range(n)]
        words = sum(f16[i]["words"] for i in pick) or 1
        drifts.append((sum(quant[i]["word_edits"] for i in pick) - sum(f16[i]["word_edits"] for i in pick)) / words)
    drifts.sort()
    return [round(drifts[int(0.025 * rounds)], 4), round(drifts[int(0.975 * rounds) - 1], 4)]


def whisper_languages(source: str) -> list[list[str]]:
    """[code, name] of every language in whisper.cpp's g_lang table (src/whisper.cpp)."""
    return [[code, name] for code, name in _LANG.findall(source)]


def table(results: list[dict], usable_wer: float, languages: list[list[str]]) -> dict:
    """The served / not-served table from the `floor language score` results of each language."""
    names = dict(map(tuple, languages))
    rows = []
    for result in sorted(results, key=lambda r: list(FLEURS).index(r["fleurs"]) if r["fleurs"] in FLEURS else 99):
        models = result["models"]
        for size in result["sizes"]:
            f16, quant = models[size], models[f"{size}-{result['quant']}"]
            drift = quant["wer"] - f16["wer"]
            rows.append({"language": result["lang"], "name": names.get(result["lang"], result["lang"]),
                         "fleurs": result["fleurs"], "size": size, "clips": len(f16["clips"]), "words": f16["words"],
                         "wer_f16": round(f16["wer"], 4), "cer_f16": round(f16["cer"], 4),
                         "wer_quant": round(quant["wer"], 4), "drift": round(drift, 4),
                         "drift_ci": bootstrap(f16["clips"], quant["clips"]),
                         "served_f16": f16["wer"] <= usable_wer, "served_quant": quant["wer"] <= usable_wer,
                         "missing": f16["missing"] + quant["missing"],
                         "bad_utf8": f16.get("bad_utf8", 0) + quant.get("bad_utf8", 0)})
    measured = {row["language"] for row in rows}
    first = results[0] if results else {}
    decoding = re.sub(r"-l \S+", "-l <lang>", first["decoding"]) if first.get("decoding") else None
    return {"usable_wer": usable_wer, "quant": first.get("quant"), "decoding": decoding,
            "commit": first.get("commit"), "evidence": first.get("evidence"), "rows": rows,
            "served": sorted({row["name"] for row in rows if row["served_f16"]}),
            "not_served": sorted({row["name"] for row in rows} - {row["name"] for row in rows if row["served_f16"]}),
            "not_measured": [name for code, name in languages if code not in measured]}
