---
type: object
cluster: pipeline
universe: live
paths:
  - pipeline/video_factory/vitrine.py
hits:
  - pipeline/video_factory/cli.py
  - templates/script-vitrine.md
  - tests/test_vitrine.py
---

# vitrine

Reads a showcase script (`genre: vitrine`, #28): the settings of the video in its front matter (`theme`, `bandeau`, `vignette`, `vignette_image`), then each line of the voice with its own shots (`[plan: …]`, `[jumeaux: …]`), or `[suite: …]` (it goes on in the shot of the line before) or `[fin: …]` (the end card), the offset of its voice in its shot, its delivery tags (`[ton: …]`) and the rows of the end card (`[appel: …]`, lit on the word before it). It also writes the text of the voice for ElevenLabs (`vf voix`): the tags, and `[short pause]` between lines, for Eleven v3; a break of 0.8 s and no tag for Multilingual v2.

## Why this shape

The theme, the banner, the cover and the voice are choices of each video, open to change, never constants of the chain: they live in the script, so another theme or another voice needs no code. The words and sentences are those of [script](script.md), which skips the showcase annotations, so [align](align.md) times a showcase like a face camera script. An error names the line of the file. A line that opens on a tag gets no pause before it: the tag already sets the delivery, as in the text the owner gave ElevenLabs for video 1.

## If you change this

- **Hits:** `vf voix` ([cli](cli.md)); the [showcase template](../templates/script-vitrine-template.md) and the RUNBOOK, which document the annotations; every showcase `script.md` in `video-content`; `tests/test_vitrine.py`. The montage of a showcase (#28, PR 2) will read the lines and their shots.
- **Does not hit:** the face camera scripts, whose annotations [script](script.md) reads.

## See

- [`parse`](../../../../pipeline/video_factory/vitrine.py), [`elevenlabs_text`](../../../../pipeline/video_factory/vitrine.py), [`Line`](../../../../pipeline/video_factory/vitrine.py), [`Piece`](../../../../pipeline/video_factory/vitrine.py)
