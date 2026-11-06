---
type: object
cluster: pipeline
universe: live
paths:
  - pipeline/video_factory/align.py
hits:
  - pipeline/video_factory/cut.py
  - pipeline/video_factory/steps.py
  - tests/test_align.py
  - tests/test_vitrine.py
---

# align

`align`: dynamic programming over (transcript word, script position) with match, join (two or three spoken words that, put end to end, are exactly one written word: « Factory » « Live » for « factory-live », each piece then kept for that word and every piece after the first marked `joined`), insertion, deletion, restart (back into the current or previous sentence) and abandon (to the end of a sentence); the cheapest path splits the take into attempts, the last complete attempt of each sentence is kept, and each word becomes `kept`, `retake`, `filler` (French lexicon `FILLERS`) or `off_script`. The document also times each word of the script (`script_words`) in its written form, whatever whisper heard; a word no spoken word was kept for (« l'EPR » heard for « les PR ») shares the silence where it was said, or else the span of the neighbour heard longer than written. A showcase's captions will be read from them (#28).

## Why this shape

Restarts and abandons make retakes, stutters and unfinished sentences cheaper to explain than inserted words, so they are found without any model; the costs are constants recorded as the step's parameters, so tuning them makes the step stale. A lexicon word the script itself says stays kept.

## If you change this

- **Hits:** [cut](cut.md), which reads the labels and lists the pieces of a word (`joined`) as one said word; the `align` parameters in `state.json` (every video's align becomes stale when a cost or the lexicon changes); `tests/test_align.py` and `tests/test_cut.py`.
- **Does not hit:** the transcript itself ([transcribe](transcribe.md)).

## See

- [`path`](../../../../pipeline/video_factory/align.py), [`attempts`](../../../../pipeline/video_factory/align.py), [`labels`](../../../../pipeline/video_factory/align.py), [`script_times`](../../../../pipeline/video_factory/align.py), [`align`](../../../../pipeline/video_factory/align.py)
