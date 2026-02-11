"""Video subsampling - extract frames at inflection points via ffmpeg."""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from pathlib import Path


def find_ffmpeg() -> str | None:
    """Find ffmpeg on the system PATH."""
    return shutil.which("ffmpeg")


def subsample_video(
    video_path: str,
    frame_indices: list[int],
    output_path: str,
    progress_callback=None,
) -> str:
    """Extract frames at specified indices and reassemble into a new video.

    Args:
        video_path: Path to the source video file.
        frame_indices: List of 1-based frame numbers to include.
        output_path: Path for the output MP4 file.
        progress_callback: Optional callable(status_text) for progress updates.

    Returns:
        Path to the output video file.

    Raises:
        FileNotFoundError: If ffmpeg is not found or video file doesn't exist.
        RuntimeError: If ffmpeg commands fail.
    """
    ffmpeg = find_ffmpeg()
    if ffmpeg is None:
        raise FileNotFoundError(
            "ffmpeg not found. Please install ffmpeg and ensure it is on your PATH."
        )

    if not os.path.isfile(video_path):
        raise FileNotFoundError(f"Video file not found: {video_path}")

    if not frame_indices:
        raise ValueError("No frame indices provided")

    work_dir = os.path.join(tempfile.gettempdir(), "span_video")
    frames_dir = os.path.join(work_dir, "frames")
    selected_dir = os.path.join(work_dir, "selected")

    # Clean and create working directories
    for d in (frames_dir, selected_dir):
        if os.path.exists(d):
            shutil.rmtree(d)
        os.makedirs(d, exist_ok=True)

    if progress_callback:
        progress_callback("Extracting frames from video...")

    # Extract all frames
    result = subprocess.run(
        [
            ffmpeg, "-i", video_path,
            "-vsync", "0",
            os.path.join(frames_dir, "frame_%06d.jpg"),
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg frame extraction failed: {result.stderr}")

    if progress_callback:
        progress_callback("Selecting inflection frames...")

    # Copy selected frames with sequential numbering
    sorted_indices = sorted(set(frame_indices))
    for seq_num, frame_idx in enumerate(sorted_indices, start=1):
        src = os.path.join(frames_dir, f"frame_{frame_idx:06d}.jpg")
        dst = os.path.join(selected_dir, f"k_{seq_num:06d}.jpg")
        if os.path.exists(src):
            shutil.copy2(src, dst)

    if progress_callback:
        progress_callback("Assembling output video...")

    # Reassemble selected frames into video
    output_dir = os.path.dirname(output_path)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)

    result = subprocess.run(
        [
            ffmpeg, "-y",
            "-framerate", "10",
            "-i", os.path.join(selected_dir, "k_%06d.jpg"),
            "-c:v", "libx264",
            "-r", "25",
            "-pix_fmt", "yuv420p",
            output_path,
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg video assembly failed: {result.stderr}")

    # Clean up temp files
    shutil.rmtree(work_dir, ignore_errors=True)

    if progress_callback:
        progress_callback("Video complete.")

    return output_path
