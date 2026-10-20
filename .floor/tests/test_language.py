"""Tests for the language table (F9.1, F9.2), without network access or whisper-cli."""

from __future__ import annotations

import json

from floor import language, policy
from floor.cli import main

TSV = "".join(f"{i}\t{name}.wav\t{ref}\t{ref.lower()}\tx\t1000\tFEMALE\n" for i, name, ref in [
    (7, "b", "Habari ya asubuhi."), (7, "a", "Habari ya asubuhi."), (3, "c", "Ndege [inaruka] juu, sana!"),
    (9, "d", "Mvua inanyesha leo"), (12, "e", "Watoto wanacheza nje")])
SOURCE = """
    { "en",  { 0,  "english",         } },
    { "sw",  { 59,  "swahili",        } },
    { "yo",  { 66,  "yoruba",         } },
"""


def test_normalize_keeps_marks_and_drops_punctuation():
    assert language.normalize("Ndege [inaruka] juu, sana!") == "ndege juu sana"
    assert language.normalize("नमस्ते, दुनिया।") == "नमस्ते दुनिया"  # the vowel signs are marks: they stay
    assert language.normalize("Ẹ KÁÀBỌ̀ (music)") == "ẹ káàbọ̀"


def test_edits():
    assert language.edits("kitten", "sitting") == 3
    assert language.edits("a b c".split(), "a x c d".split()) == 2
    assert language.edits([], ["a"]) == 1


def test_read_hyp_joins_a_character_split_by_a_segment_break():
    data = " আমি ভাত".encode()
    assert language.read_hyp(data[:2] + b"\n" + data[2:] + b"\n") == ("আমি ভাত", False)  # the break is inside আ
    assert language.read_hyp(b" one\n two\n") == ("one two", False)
    assert language.read_hyp(b" seven\xe1\n") == ("seven�", True)


def test_choose_takes_one_recording_per_sentence(tmp_path):
    (tmp_path / "test.tsv").write_text(TSV, encoding="utf-8")
    rows = language.read_tsv(tmp_path / "test.tsv")
    assert len(rows) == 5
    clips = language.choose(rows, 3, seed=1)
    assert [c["id"] for c in clips] == sorted(c["id"] for c in clips) and len(clips) == 3
    assert all(c["file"] != "b.wav" for c in clips)  # sentence 7: the first file by name is a.wav
    assert language.choose(rows, 10) == language.choose(rows, 10, seed=5)  # all 4 sentences, any seed


def test_score_bootstrap_and_table(tmp_path):
    clips = [{"id": 1, "file": "a.wav", "ref": "one two three four"},
             {"id": 2, "file": "b.wav", "ref": "five six seven eight"}]
    hyps = {"tiny": ["one two three four", "five six seven"], "tiny-q5_1": ["one two", "five six seven eight"]}
    for model, texts in hyps.items():
        (tmp_path / model).mkdir()
        (tmp_path / model / "seconds").write_text("12\n")
        for clip, text in zip(clips, texts):
            (tmp_path / model / f"{clip['file']}.txt").write_text(f" {text}\n", encoding="utf-8")
    (tmp_path / "tiny-q5_1" / "b.wav.txt").unlink()  # no output: an empty transcript
    (tmp_path / "tiny" / "b.wav.txt").write_bytes(b" five six seven\xe1\n")  # a byte that is not UTF-8
    scores = language.score(clips, tmp_path, ["tiny", "tiny-q5_1"])
    assert scores["tiny"]["wer"] == 1 / 8 and scores["tiny"]["seconds"] == 12 and scores["tiny"]["missing"] == 0
    assert scores["tiny"]["bad_utf8"] == 1 and scores["tiny"]["clips"][1]["hyp"] == "five six seven�"
    assert scores["tiny-q5_1"]["wer"] == 6 / 8 and scores["tiny-q5_1"]["missing"] == 1
    lo, hi = language.bootstrap(scores["tiny"]["clips"], scores["tiny-q5_1"]["clips"], rounds=200)
    assert lo <= 5 / 8 <= hi
    result = {"fleurs": "sw_ke", "lang": "sw", "sizes": ["tiny"], "quant": "q5_1", "decoding": "-l sw -nf",
              "commit": "c", "evidence": "u", "models": scores}
    doc = language.table([result], 0.3, language.whisper_languages(SOURCE))
    row = doc["rows"][0]
    assert (row["name"], row["size"], row["clips"], row["words"]) == ("swahili", "tiny", 2, 8)
    assert (row["wer_f16"], row["wer_quant"], row["drift"]) == (0.125, 0.75, 0.625)
    assert row["served_f16"] and not row["served_quant"] and row["missing"] == 1 and row["bad_utf8"] == 1
    assert doc["served"] == ["swahili"] and doc["not_served"] == []
    assert doc["decoding"] == "-l <lang> -nf"  # one line for all languages
    assert doc["not_measured"] == ["english", "yoruba"]


def test_cli_choose_score_table(tmp_path, capsys):
    (tmp_path / "test.tsv").write_text(TSV, encoding="utf-8")
    assert main(["language", "choose", "--fleurs", "sw_ke", "--tsv", str(tmp_path / "test.tsv"), "--clips", "2",
                 "--out", str(tmp_path / "clips.json")]) == 0
    files = capsys.readouterr().out.split()
    assert len(files) == 2 and json.loads((tmp_path / "clips.json").read_text())["lang"] == "sw"
    # whisper-cli wrote nothing: every clip is missing, so score fails.
    args = ["language", "score", "--clips", str(tmp_path / "clips.json"), "--hyp-root", str(tmp_path / "hyp"),
            "--sizes", "tiny", "--out", str(tmp_path / "score.json")]
    assert main(args) == 1
    clips = json.loads((tmp_path / "clips.json").read_text())["clips"]
    for model in ("tiny", "tiny-q5_1"):
        (tmp_path / "hyp" / model).mkdir(parents=True)
        for clip in clips:
            (tmp_path / "hyp" / model / f"{clip['file']}.txt").write_text(clip["ref"], encoding="utf-8")
    assert main(args) == 0
    (tmp_path / "whisper.cpp").write_text(SOURCE, encoding="utf-8")
    capsys.readouterr()
    assert main(["language", "table", str(tmp_path / "score.json"), "--whisper", str(tmp_path / "whisper.cpp"),
                 "--out", str(tmp_path / "language.json")]) == 0
    out = capsys.readouterr().out
    assert "swahili" in out and "Served (f16 WER at most 30%): swahili. Not served: none. Not measured: 2" in out


def test_policy_has_the_usable_wer():
    assert policy.load()["language"]["usable_wer"] == 0.30
