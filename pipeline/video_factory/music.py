"""The music bed of `compose`: synthesized in code with a fixed seed, so it is the same on every render.

A slow progression of four chords (A minor, F, C, G) played by a soft pad, and a quiet arpeggio whose notes a seeded
random generator picks among the chord's notes. No sample and no third-party audio: only sines and envelopes (each
note fades in and out, so nothing clicks). The bed is written at a fixed low level (RMS_DBFS) under the voice, with a
fade in and a fade out.
"""

from __future__ import annotations

import wave
from pathlib import Path

import numpy as np

SEED = 20261104
SAMPLE_RATE = 48000
TEMPO = 84  # beats per minute
BEATS_PER_CHORD = 8
RMS_DBFS = -30.0
FADE_IN, FADE_OUT = 1.0, 2.0
CHORDS = ((57, 60, 64), (53, 57, 60), (48, 52, 55), (55, 59, 62))  # MIDI notes: Am, F, C, G


def frequency(note: int) -> float:
    return 440.0 * 2.0 ** ((note - 69) / 12)


def envelope(length: int, attack: int, release: int) -> np.ndarray:
    shape = np.ones(length)
    attack, release = min(attack, length // 2), min(release, length // 2)
    shape[:attack] = np.linspace(0.0, 1.0, attack, endpoint=False)
    shape[length - release :] = np.linspace(1.0, 0.0, release)
    return shape


def bed(duration: float, seed: int = SEED) -> np.ndarray:
    """The stereo bed, duration seconds long, as float samples in [-1, 1] (shape: samples x 2)."""
    rng = np.random.default_rng(seed)
    total = round(duration * SAMPLE_RATE)
    beat = 60.0 / TEMPO
    chord_length = round(BEATS_PER_CHORD * beat * SAMPLE_RATE)
    time = np.arange(chord_length) / SAMPLE_RATE
    left, right = np.zeros(total), np.zeros(total)
    position, index = 0, 0
    while position < total:
        chord = CHORDS[index % len(CHORDS)]
        pad = sum(np.sin(2 * np.pi * frequency(note) * time) for note in chord) / len(chord)
        pad *= envelope(chord_length, SAMPLE_RATE // 2, SAMPLE_RATE // 2)
        notes = np.zeros(chord_length)
        step = round(beat / 2 * SAMPLE_RATE)
        pluck = np.exp(-np.arange(step) / (0.25 * SAMPLE_RATE)) * envelope(step, SAMPLE_RATE // 200, SAMPLE_RATE // 50)
        for start in range(0, chord_length - step + 1, step):
            note = chord[int(rng.integers(len(chord)))] + 12
            notes[start : start + step] += 0.35 * np.sin(2 * np.pi * frequency(note) * time[:step]) * pluck
        end = min(total, position + chord_length)
        span = end - position
        left[position:end] += pad[:span] + 0.8 * notes[:span]
        right[position:end] += pad[:span] + 1.2 * np.roll(notes, step // 3)[:span]
        position, index = end, index + 1
    stereo = np.stack([left, right], axis=1)
    rms = float(np.sqrt(np.mean(stereo**2))) or 1.0
    stereo *= 10 ** (RMS_DBFS / 20) / rms
    stereo *= envelope(total, round(FADE_IN * SAMPLE_RATE), round(FADE_OUT * SAMPLE_RATE))[:, None]
    return np.clip(stereo, -1.0, 1.0)


def write(path: Path, samples: np.ndarray) -> None:
    """16-bit stereo WAV at 48 kHz, rounded, never dithered."""
    pcm = np.round(samples * 32767.0).astype("<i2")
    with wave.open(str(path), "wb") as out:
        out.setnchannels(2)
        out.setsampwidth(2)
        out.setframerate(SAMPLE_RATE)
        out.writeframes(pcm.tobytes())
