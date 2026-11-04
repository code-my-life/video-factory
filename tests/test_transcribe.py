"""transcribe: whisper-cli's settings, and the words and times read from its full JSON and the silences."""

from __future__ import annotations

from pathlib import Path

import pytest

from video_factory import transcribe

# The shape of whisper.cpp 1.9.5's « -ojf » output, cut down: DTW times in centiseconds mark the end of each token.
DOCUMENT = {
    "transcription": [
        {
            "offsets": {"from": 0, "to": 2000},
            "tokens": [
                {"text": "[_BEG_]", "offsets": {"from": 0, "to": 0}, "t_dtw": -1, "p": 0.8},
                {"text": " Bonjour", "offsets": {"from": 100, "to": 400}, "t_dtw": 50, "p": 0.9},
                {"text": ",", "offsets": {"from": 400, "to": 500}, "t_dtw": 60, "p": 0.9},
                {"text": " euh", "offsets": {"from": 500, "to": 600}, "t_dtw": 80, "p": 0.7},
                {"text": " rap", "offsets": {"from": 900, "to": 1000}, "t_dtw": 130, "p": 1.0},
                {"text": "ide", "offsets": {"from": 1000, "to": 1100}, "t_dtw": 150, "p": 1.0},
                {"text": "[_TT_100]", "offsets": {"from": 2000, "to": 2000}, "t_dtw": -1, "p": 0.5},
            ],
        }
    ]
}


def test_whisper_runs_in_french_at_temperature_0_without_fallback_with_dtw_and_fixed_threads():
    command = transcribe.whisper_command(Path("cli"), Path("model.bin"), Path("a.wav"), Path("out"))
    for setting in (["-l", "fr"], ["-tp", "0"], ["-nf"], ["-dtw", "large.v3.turbo"], ["-nfa"], ["-t", "8"]):
        index = command.index(setting[0])
        assert command[index : index + len(setting)] == setting
    assert command[command.index("--prompt") + 1].startswith("Euh")


def test_tokens_become_words_with_their_punctuation_and_dtw_end():
    words = transcribe.tokens_to_words(DOCUMENT)
    assert [(w["text"], w["end"]) for w in words] == [("Bonjour,", 0.5), ("euh", 0.8), ("rapide", 1.5)]


def test_words_are_held_in_their_stretch_of_speech():
    silences = [(0.62, 1.05)]
    placed = transcribe.place(transcribe.tokens_to_words(DOCUMENT), silences, 2.0)
    assert [(w["text"], w["start"], w["end"]) for w in placed] == [
        ("Bonjour,", 0.0, 0.5),
        ("euh", 0.5, 0.62),
        ("rapide", 1.05, 2.0),
    ]
    assert placed[0]["p"] == pytest.approx(0.9)


def test_the_silences_come_from_ffmpeg(tools, tmp_path):
    box = tools("ffmpeg")
    audio = tmp_path / "a.wav"
    from conftest import ffmpeg

    ffmpeg(
        box,
        "-f",
        "lavfi",
        "-i",
        "sine=f=300:d=1,apad=pad_dur=0.6",
        "-f",
        "lavfi",
        "-i",
        "sine=f=300:d=0.5",
        "-filter_complex",
        "[0][1]concat=n=2:v=0:a=1",
        "-ar",
        "16000",
        audio,
    )
    found = transcribe.silences(box.ffmpeg, audio, 2.1)
    assert len(found) == 1
    assert found[0][0] == pytest.approx(1.0, abs=0.02)
    assert found[0][1] == pytest.approx(1.6, abs=0.02)
