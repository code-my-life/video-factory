---
type: object
cluster: pipeline
universe: live
paths:
  - pipeline/video_factory/montage.py
hits:
  - pipeline/video_factory/steps.py
  - pipeline/video_factory/publish.py
  - templates/hyperframes/themes/
  - tests/test_vitrine.py
---

# montage

The montage of a showcase (#28, ADR 0007), in three parts used by three steps:
- `decide` (step `cut`): the time line of the shots (each line's pieces one after the other, then the end card until the target duration), each line's stretch of the voice (from the end of the silence before its first word to the start of the silence after its last one, both from `transcribe`) heard « voix » seconds after its shot starts, every script word at its time in the video, the caption groups and the times the end card's rows are lit;
- `voice_command` (step `voice`): the voice placed line by line, with PAD_IN and PAD_OUT kept and faded, mixed into one track of the video's length;
- `page` and `write_project` (step `compose`): the HyperFrames project in the theme the script names (`templates/hyperframes/themes/<theme>/`), its captures (copied when already 1440x2560 at 30 fps, brought to it otherwise; the twins cropped from their recording), the app's icon and the theme's fonts; `text_root` gives the page of the text pass.

## Why this shape

These rules were written from the hand-made montage of video 1 and give it back: the same 51 caption groups, the same line placements, the same page. They are constants of the code recorded as the steps' parameters, while every choice of a video (theme, banner, end card, cover, offsets) stays in its script. A capture already at the video's size and rate is copied as is, so a plan filmed by `vf capture` is not encoded twice.

## If you change this

- **Hits:** every showcase's `cut`, `voice` and `compose` (their code fingerprints), so every master; the themes, whose pages read the clips and the config it writes (ids `shot-<n>`, `twin-avant`, `twin-apres`, `cta`, `end`, `row-<n>`, `cap-<n>`); [publish](publish.md), which finds a theme by `theme_folder`; `tests/test_vitrine.py`.
- **Does not hit:** a face camera video, whose steps never call it.

## See

- [`decide`](../../../../pipeline/video_factory/montage.py), [`spoken`](../../../../pipeline/video_factory/montage.py), [`caption_groups`](../../../../pipeline/video_factory/montage.py), [`voice_command`](../../../../pipeline/video_factory/montage.py), [`page`](../../../../pipeline/video_factory/montage.py), [`place_captures`](../../../../pipeline/video_factory/montage.py)
