"""FFmpeg utilities for media probing and information extraction"""

from __future__ import annotations

import json
import subprocess
from typing import Optional

from gif_converter.models.media import MediaInfo


def probe_media_info(ffprobe_path: str, media_path: str) -> Optional[MediaInfo]:
    """
    Probe media file using ffprobe and extract video stream information.

    Args:
        ffprobe_path: Path to ffprobe executable
        media_path: Path to media file to probe

    Returns:
        MediaInfo object if successful, None otherwise
    """
    cmd = [
        ffprobe_path,
        "-v", "error",
        "-show_streams",
        "-select_streams", "v:0",  # First video stream only
        "-show_format",
        "-of", "json",
        media_path,
    ]

    try:
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=30,
        )

        if result.returncode != 0:
            return None

        data = json.loads(result.stdout)
        streams = data.get("streams", [])
        if not streams:
            return None

        stream = streams[0]
        format_info = data.get("format", {})

        # Parse frame rate (can be "30/1" or "30")
        fps_str = stream.get("r_frame_rate", "30/1")
        if "/" in fps_str:
            fps_num, fps_den = map(int, fps_str.split("/"))
        else:
            fps_num = int(float(fps_str))
            fps_den = 1

        # Extract dimensions
        width = int(stream.get("width", 0))
        height = int(stream.get("height", 0))

        # Duration (prefer stream duration, fallback to format duration)
        duration = float(stream.get("duration", format_info.get("duration", 0)))

        # Codec info
        codec = stream.get("codec_name", "unknown")
        pix_fmt = stream.get("pix_fmt", "unknown")

        # Bitrate
        bitrate = None
        if "bit_rate" in stream:
            try:
                bitrate = int(stream["bit_rate"])
            except (ValueError, TypeError):
                pass
        elif "bit_rate" in format_info:
            try:
                bitrate = int(format_info["bit_rate"])
            except (ValueError, TypeError):
                pass

        return MediaInfo(
            width=width,
            height=height,
            fps_num=fps_num,
            fps_den=fps_den,
            duration=duration,
            codec=codec,
            pix_fmt=pix_fmt,
            bitrate=bitrate,
        )

    except (subprocess.TimeoutExpired, json.JSONDecodeError, ValueError, KeyError) as e:
        return None


def estimate_gif_size(
    duration: float,
    width: int,
    height: int,
    fps: int,
    colors: int,
    dither: str = "sierra2_4a",
) -> float:
    """
    Estimate GIF file size in MB based on parameters.

    This is a rough estimation formula based on typical GIF compression ratios.

    Args:
        duration: Duration in seconds
        width: Width in pixels
        height: Height in pixels
        fps: Frames per second
        colors: Number of colors in palette
        dither: Dithering algorithm

    Returns:
        Estimated file size in MB
    """
    # Total frames
    total_frames = duration * fps

    # Bytes per pixel (depends on color count)
    # GIF uses LZW compression, typical compression ratio is 3-5x
    bits_per_pixel = {32: 5, 64: 6, 128: 7, 256: 8}.get(colors, 8)

    # Base size calculation (uncompressed)
    base_size = total_frames * width * height * (bits_per_pixel / 8)

    # Compression ratio (dithering affects this)
    compression_ratio = {
        "none": 3.5,
        "bayer": 4.0,
        "sierra2_4a": 4.5,
        "floyd_steinberg": 4.0,
    }.get(dither, 4.0)

    # Apply compression
    compressed_size = base_size / compression_ratio

    # Add overhead (headers, color tables, etc.) - roughly 5%
    overhead = compressed_size * 0.05

    # Convert to MB
    size_mb = (compressed_size + overhead) / (1024 * 1024)

    return size_mb


def format_time(seconds: float) -> str:
    """Format seconds as HH:MM:SS.mmm for FFmpeg"""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = seconds % 60
    return f"{hours:02d}:{minutes:02d}:{secs:06.3f}"


def format_size_mb(size_mb: float) -> str:
    """Format file size for display"""
    if size_mb < 0.01:
        return f"{size_mb * 1024:.1f} KB"
    elif size_mb < 1:
        return f"{size_mb * 1024:.0f} KB"
    else:
        return f"{size_mb:.2f} MB"
