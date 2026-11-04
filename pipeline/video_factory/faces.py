"""The face detector of `scan` and `qc`: MediaPipe BlazeFace short range (the pinned model), on CPU, through LiteRT.

The model is MediaPipe's; LiteRT (ai-edge-litert) is the TensorFlow Lite runtime MediaPipe itself runs on, used directly
because the mediapipe wheel needs an OpenGL ES library even on CPU. The pre- and post-processing follow MediaPipe's face
detector graph for this model: a black letterbox to a square, bilinear sampling to 128x128 RGB in [-1, 1], 896 SSD
anchors (strides 8, 16, 16, 16, fixed size), boxes relative to their anchor, scores through a sigmoid clipped at 100.
On MediaPipe's own test images, this gives the scores of mediapipe 1.1.1 to within 0.01.

A frame is read at 144x256 (9:16) and looked at through three windows, so a face is seen whatever its place: the whole
frame letterboxed into a square, its top square and its bottom square. Its score is the best score of the three; a
score at THRESHOLD or above is a face. Nothing of the image is kept: only frame numbers, times and scores leave here.
"""

from __future__ import annotations

import math
from functools import cache
from pathlib import Path

import numpy as np
from ai_edge_litert.interpreter import Interpreter

# Provisional: the score at which a frame counts as showing a face (MediaPipe's default for this model). Its calibration
# on labelled takes, masked and unmasked, belongs to the mask issue (#3); it is set here and nowhere else.
THRESHOLD = 0.5

WIDTH, HEIGHT = 144, 256  # the size frames are read at, 9:16 like the takes and the master
INPUT = 128
STRIDES = (8, 16, 16, 16)
SCORE_CLIP = 100.0


@cache
def anchors() -> np.ndarray:
    """The 896 anchor centres (x, y) of BlazeFace short range, in [0, 1], in the model's output order."""
    centres = []
    layer = 0
    while layer < len(STRIDES):
        stride, last = STRIDES[layer], layer
        while last < len(STRIDES) and STRIDES[last] == stride:
            last += 1
        per_cell = 2 * (last - layer)  # one anchor of ratio 1 and one interpolated scale, per layer of this stride
        cells = math.ceil(INPUT / stride)
        for y in range(cells):
            for x in range(cells):
                centres += [((x + 0.5) / cells, (y + 0.5) / cells)] * per_cell
        layer = last
    return np.array(centres, dtype=np.float32)


@cache
def resize_weights(source: int, target: int) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Bilinear sampling of a source axis onto a target axis, as MediaPipe's image-to-tensor step does it (output
    pixel u reads source position u x source / target): low indices, high indices and weights of the high."""
    position = np.arange(target, dtype=np.float64) * source / target
    low = np.floor(position).astype(np.int64)
    high = np.minimum(low + 1, source - 1)
    return low, high, (position - low).astype(np.float32)


def resize(image: np.ndarray, size: int) -> np.ndarray:
    """A square float image resized to size x size by bilinear sampling, rounded to whole levels like 8-bit pixels."""
    rows = resize_weights(image.shape[0], size)
    cols = resize_weights(image.shape[1], size)
    vertical = image[rows[0]] * (1 - rows[2])[:, None, None] + image[rows[1]] * rows[2][:, None, None]
    return np.round(vertical[:, cols[0]] * (1 - cols[2])[None, :, None] + vertical[:, cols[1]] * cols[2][None, :, None])


def windows(frame: np.ndarray) -> list[tuple[np.ndarray, tuple[float, float]]]:
    """The model inputs of a 144x256 RGB frame, each with the range of x (in [0, 1]) its picture covers."""
    pixels = frame.astype(np.float32)
    height, width = pixels.shape[:2]
    side = max(width, height)
    square = np.zeros((side, side, 3), dtype=np.float32)
    left = (side - width) // 2
    square[:, left : left + width] = pixels
    found = [(resize(square, INPUT), (left / side, (left + width) / side))]
    found.append((resize(pixels[:width], INPUT), (0.0, 1.0)))
    found.append((resize(pixels[height - width :], INPUT), (0.0, 1.0)))
    return found


class Detector:
    """BlazeFace short range on one CPU thread (one thread keeps the arithmetic order, hence the scores, fixed)."""

    def __init__(self, model: Path):
        self.interpreter = Interpreter(model_path=str(model), num_threads=1)
        self.interpreter.allocate_tensors()
        self.input = self.interpreter.get_input_details()[0]["index"]
        outputs = {detail["name"]: detail["index"] for detail in self.interpreter.get_output_details()}
        self.boxes, self.scores = outputs["regressors"], outputs["classificators"]

    def window_score(self, picture: np.ndarray, covered: tuple[float, float]) -> float:
        """The best face score in one model input, counting only boxes centred on the picture, not on its padding."""
        tensor = (picture / 127.5 - 1.0).astype(np.float32)[None]
        self.interpreter.set_tensor(self.input, tensor)
        self.interpreter.invoke()
        raw = self.interpreter.get_tensor(self.scores)[0, :, 0]
        boxes = self.interpreter.get_tensor(self.boxes)[0]
        centre_x = boxes[:, 0] / INPUT + anchors()[:, 0]
        scores = 1.0 / (1.0 + np.exp(-np.clip(raw, -SCORE_CLIP, SCORE_CLIP).astype(np.float64)))
        inside = (centre_x >= covered[0]) & (centre_x <= covered[1])
        return float(scores[inside].max()) if inside.any() else 0.0

    def score(self, frame: np.ndarray) -> float:
        """The face score of a 144x256 RGB frame: the best of its three windows."""
        return max(self.window_score(picture, covered) for picture, covered in windows(frame))
