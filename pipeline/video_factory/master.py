"""`master`: the 2K vertical master (1440x2560) and the TikTok export (1080x1920), each with its framemd5.

Both come straight from the PNG frames of `compose` (the export is not made from the master), with the pinned FFmpeg:
H.264 High in BT.709 limited range, 30 frames per second, AAC at 48 kHz in stereo. The voice and the music bed are
summed, the voice at -3 dB on each channel so the stereo master reads the loudness the voice was brought to (two equal
channels read 3 LU louder under ITU-R BS.1770); then the sound is padded or trimmed to the exact length of the frames.
Encoders get a fixed thread count and the « bitexact » flags, the container gets no metadata, x264's SEI (its version
and settings) is removed, and the index sits at the start of the file (faststart). The framemd5 hashes every decoded
frame, picture and sound, so two renders of the same inputs can be compared frame by frame (criterion C1 of #4).
"""

from __future__ import annotations

from pathlib import Path

from video_factory import media

FPS = 30
CRF = 18
PRESET = "medium"
GOP = 60
AUDIO_BITRATE = "192k"
SIZES = {"master": (1440, 2560), "tiktok": (1080, 1920)}
SAMPLES_PER_FRAME = media.SAMPLE_RATE // FPS


def video_filter(width: int, height: int) -> str:
    """RGB frames to BT.709 limited-range 4:2:0, resized with Lanczos when the size changes."""
    return (
        f"scale={width}:{height}:flags=lanczos+accurate_rnd+full_chroma_int:out_color_matrix=bt709:out_range=tv,"
        f"format=yuv420p,{media.BT709}"
    )


def audio_graph(frames: int) -> str:
    """Voice (input 1, mono) at -3 dB on both channels plus the music (input 2, stereo), to exactly frames x 1600
    samples."""
    samples = frames * SAMPLES_PER_FRAME
    return (
        "[1:a]aformat=sample_fmts=fltp:sample_rates=48000:channel_layouts=mono,"
        "pan=stereo|c0=0.70710678*c0|c1=0.70710678*c0[voice];"
        "[2:a]aformat=sample_fmts=fltp:sample_rates=48000:channel_layouts=stereo[music];"
        f"[voice][music]amix=inputs=2:normalize=0:duration=longest,apad=whole_len={samples},"
        f"atrim=end_sample={samples}[a]"
    )


def command(frames_folder: Path, voice: Path, music: Path, frames: int, name: str, output: Path) -> list[str | Path]:
    width, height = SIZES[name]
    return [
        "-framerate",
        str(FPS),
        "-start_number",
        "1",
        "-i",
        frames_folder / "frame_%06d.png",
        "-i",
        voice,
        "-i",
        music,
        "-filter_complex",
        f"[0:v]{video_filter(width, height)}[v];{audio_graph(frames)}",
        "-map",
        "[v]",
        "-map",
        "[a]",
        "-frames:v",
        str(frames),
        *media.NO_METADATA,
        *media.BITEXACT,
        "-c:v",
        "libx264",
        "-profile:v",
        "high",
        "-preset",
        PRESET,
        "-crf",
        str(CRF),
        "-g",
        str(GOP),
        "-threads",
        str(media.THREADS),
        "-pix_fmt",
        "yuv420p",
        "-color_primaries",
        "bt709",
        "-color_trc",
        "bt709",
        "-colorspace",
        "bt709",
        "-color_range",
        "tv",
        "-bsf:v",
        "filter_units=remove_types=6",
        "-c:a",
        "aac",
        "-b:a",
        AUDIO_BITRATE,
        "-ar",
        str(media.SAMPLE_RATE),
        "-ac",
        "2",
        "-movflags",
        "+faststart",
        "-f",
        "mp4",
        output,
    ]


def framemd5_command(source: Path, output: Path) -> list[str | Path]:
    """The MD5 of every decoded frame, video and audio, of a file."""
    streams = ["-map", "0:v", "-map", "0:a"]
    return ["-flags", "+bitexact", "-i", source, *streams, *media.BITEXACT, "-f", "framemd5", output]
