"""GIF export engine using FFmpeg"""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from typing import List, Dict, Optional

from PySide6 import QtCore

from gif_converter.models.media import (
    Segment,
    GifExportProfile,
    TextOverlay,
    TextPosition,
    ExportMode,
)


@dataclass(slots=True)
class GifExportTask:
    """GIF export task configuration"""
    ffmpeg: str
    segments: List[Segment]
    file_lookup: Dict[str, str]  # file_id -> path
    profile: GifExportProfile
    output_path: str
    mode: ExportMode = ExportMode.SINGLE_SEGMENT


class GifExporter(QtCore.QObject, QtCore.QRunnable):
    """
    GIF exporter that runs in a separate thread.

    Signals:
        progressChanged(int, str): Progress percentage (0-100) and stage description
        logLine(str): Log message from FFmpeg
        finished(bool, str, float): Success status, message, and actual file size in MB
        sizeEstimateUpdated(float): Updated size estimate in MB
    """

    progressChanged = QtCore.Signal(int, str)
    logLine = QtCore.Signal(str)
    finished = QtCore.Signal(bool, str, float)
    sizeEstimateUpdated = QtCore.Signal(float)

    def __init__(self, task: GifExportTask) -> None:
        QtCore.QObject.__init__(self)
        QtCore.QRunnable.__init__(self)
        self.setAutoDelete(True)
        self._task = task
        self._cancelled = False

    @QtCore.Slot()
    def cancel(self) -> None:
        """Cancel the export operation"""
        self._cancelled = True

    def run(self) -> None:
        """Execute the export task"""
        ok, msg, size = self._run()
        self.finished.emit(ok, msg, size)

    def _run(self) -> tuple[bool, str, float]:
        """Main export logic"""
        tmp_dir = tempfile.mkdtemp(prefix="gifforge_")
        try:
            profile = self._task.profile

            # Step 1: Extract and prepare video segments
            if self._cancelled:
                return False, "Cancelled", 0.0

            self.progressChanged.emit(5, "Preparing video segments...")
            video_clips = self._extract_segments(tmp_dir)
            if not video_clips:
                return False, "Failed to extract video segments", 0.0

            # Step 2: Generate optimized palette
            if self._cancelled:
                return False, "Cancelled", 0.0

            self.progressChanged.emit(30, "Generating color palette...")
            palette_path = os.path.join(tmp_dir, "palette.png")
            ok, err = self._generate_palette(video_clips, palette_path)
            if not ok:
                return False, f"Palette generation failed: {err}", 0.0

            # Step 3: Create GIF using palette
            if self._cancelled:
                return False, "Cancelled", 0.0

            self.progressChanged.emit(60, "Creating GIF...")
            ok, err = self._create_gif(video_clips, palette_path, self._task.output_path)
            if not ok:
                return False, f"GIF creation failed: {err}", 0.0

            # Step 4: Verify and get file size
            if not os.path.exists(self._task.output_path):
                return False, "Output file was not created", 0.0

            file_size_bytes = os.path.getsize(self._task.output_path)
            file_size_mb = file_size_bytes / (1024 * 1024)

            self.progressChanged.emit(100, "Done")
            return True, self._task.output_path, file_size_mb

        except Exception as e:
            return False, f"Export error: {str(e)}", 0.0
        finally:
            try:
                shutil.rmtree(tmp_dir, ignore_errors=True)
            except Exception:
                pass

    def _extract_segments(self, tmp_dir: str) -> List[str]:
        """Extract video segments and apply basic filters"""
        output_clips = []
        total = len(self._task.segments)

        for idx, seg in enumerate(self._task.segments, start=1):
            if self._cancelled:
                return []

            self.progressChanged.emit(
                5 + int((idx - 1) / max(1, total) * 20),
                f"Extracting segment {idx}/{total}..."
            )

            src = self._task.file_lookup.get(seg.file_id)
            if not src:
                self.logLine.emit(f"Warning: Missing source for segment {seg.id}")
                continue

            clip_path = os.path.join(tmp_dir, f"clip_{idx:03d}.mp4")
            ok, err = self._extract_segment(src, seg, clip_path)
            if not ok:
                self.logLine.emit(f"Failed to extract segment {idx}: {err}")
                return []

            output_clips.append(clip_path)

        return output_clips

    def _extract_segment(self, src: str, seg: Segment, output: str) -> tuple[bool, str]:
        """Extract a single segment with filters applied"""
        profile = self._task.profile

        # Build filter chain
        filters = []

        # Speed adjustment
        if profile.speed_multiplier != 1.0:
            speed = profile.speed_multiplier
            filters.append(f"setpts={1.0/speed}*PTS")

        # Scaling
        if profile.width:
            scale_algo = profile.scale_filter
            filters.append(f"scale={profile.width}:-1:flags={scale_algo}")

        # FPS
        filters.append(f"fps={profile.fps}")

        # Text overlay
        if profile.text_overlay and profile.text_overlay.enabled and profile.text_overlay.text:
            text_filter = self._build_text_filter(profile.text_overlay)
            if text_filter:
                filters.append(text_filter)

        # Combine filters
        filter_str = ",".join(filters) if filters else None

        # Build FFmpeg command
        cmd = [
            self._task.ffmpeg,
            "-y",
            "-ss", f"{seg.start}",
            "-to", f"{seg.end}",
            "-i", src,
        ]

        if filter_str:
            cmd += ["-vf", filter_str]

        cmd += [
            "-c:v", "libx264",
            "-preset", "ultrafast",
            "-crf", "18",
            "-pix_fmt", "yuv420p",
            "-an",  # No audio for intermediate files
            output
        ]

        return self._run_cmd(cmd)

    def _build_text_filter(self, overlay: TextOverlay) -> Optional[str]:
        """Build FFmpeg drawtext filter for text overlay"""
        if not overlay.text:
            return None

        # Escape text for FFmpeg
        text = overlay.text.replace(":", r"\:").replace("'", r"\'")

        # Get position
        x, y = overlay.get_ffmpeg_position(0, 0)  # Dimensions don't matter for expressions

        # Build drawtext filter
        parts = [
            f"text='{text}'",
            f"fontsize={overlay.font_size}",
            f"fontcolor={overlay.font_color}",
            f"x={x}",
            f"y={y}",
        ]

        # Font family
        if overlay.font_family:
            parts.append(f"font='{overlay.font_family}'")

        # Bold
        if overlay.bold:
            parts.append("bold=1")

        # Outline/border
        if overlay.outline_enabled:
            parts.append(f"borderw={overlay.outline_width}")
            parts.append(f"bordercolor={overlay.outline_color}")

        # Background box
        if overlay.background_enabled:
            # Convert opacity (0.0-1.0) to alpha (0-255)
            alpha = int(overlay.background_opacity * 255)
            bg_color = overlay.background_color
            parts.append(f"box=1")
            parts.append(f"boxcolor={bg_color}@{alpha/255:.2f}")
            parts.append(f"boxborderw={overlay.padding_x//2}")

        return "drawtext=" + ":".join(parts)

    def _generate_palette(self, video_clips: List[str], palette_path: str) -> tuple[bool, str]:
        """Generate optimized color palette for GIF"""
        profile = self._task.profile

        # Concatenate clips if multiple (for merged mode)
        if len(video_clips) > 1:
            # Create concat file
            concat_file = palette_path + ".concat.txt"
            with open(concat_file, "w", encoding="utf-8") as f:
                for clip in video_clips:
                    f.write(f"file '{clip}'\n")

            input_args = ["-f", "concat", "-safe", "0", "-i", concat_file]
        else:
            input_args = ["-i", video_clips[0]]

        # Build palette generation filter
        palette_filter = f"palettegen=max_colors={profile.colors}"
        if profile.optimize_palette:
            palette_filter += ":stats_mode=diff"

        cmd = [
            self._task.ffmpeg,
            "-y",
        ] + input_args + [
            "-vf", palette_filter,
            palette_path
        ]

        ok, err = self._run_cmd(cmd)

        # Clean up concat file
        if len(video_clips) > 1:
            try:
                os.remove(concat_file)
            except:
                pass

        return ok, err

    def _create_gif(self, video_clips: List[str], palette_path: str, output: str) -> tuple[bool, str]:
        """Create GIF using video clips and palette"""
        profile = self._task.profile

        # Prepare input
        if len(video_clips) > 1:
            # Create concat file
            concat_file = output + ".concat.txt"
            with open(concat_file, "w", encoding="utf-8") as f:
                for clip in video_clips:
                    f.write(f"file '{clip}'\n")
            input_args = ["-f", "concat", "-safe", "0", "-i", concat_file]
        else:
            input_args = ["-i", video_clips[0]]

        # Build paletteuse filter
        dither_map = {
            "none": "none",
            "bayer": "bayer:bayer_scale=5",
            "sierra2_4a": "sierra2_4a",
            "floyd_steinberg": "floyd_steinberg",
        }
        dither = dither_map.get(profile.dither, "sierra2_4a")

        paletteuse_filter = f"paletteuse=dither={dither}"

        # Reverse/Boomerang handling
        if profile.reverse or profile.boomerang:
            # We need to apply reverse at the filter level
            reverse_filter = "[0:v]reverse[r];" if profile.reverse else ""
            if profile.boomerang:
                # Boomerang: play forward, then backward
                filter_complex = f"[0:v]split[a][b];[b]reverse[r];[a][r]concat=n=2:v=1[v];[v][1:v]{paletteuse_filter}"
            else:
                # Just reverse
                filter_complex = f"[0:v]reverse[v];[v][1:v]{paletteuse_filter}"
        else:
            # Normal playback
            filter_complex = f"[0:v][1:v]{paletteuse_filter}"

        cmd = [
            self._task.ffmpeg,
            "-y",
        ] + input_args + [
            "-i", palette_path,
            "-filter_complex", filter_complex,
        ]

        # Loop settings
        if profile.loop_count == 0:
            cmd += ["-loop", "0"]  # Infinite loop
        elif profile.loop_count > 0:
            cmd += ["-loop", str(profile.loop_count)]
        else:
            cmd += ["-loop", "-1"]  # No loop

        # Lossy compression (if supported by FFmpeg build)
        if profile.lossy_compression is not None:
            cmd += ["-lossy", str(profile.lossy_compression)]

        cmd += [output]

        ok, err = self._run_cmd(cmd)

        # Clean up concat file
        if len(video_clips) > 1:
            try:
                os.remove(concat_file)
            except:
                pass

        return ok, err

    def _run_cmd(self, cmd: List[str]) -> tuple[bool, str]:
        """Run FFmpeg command and capture output"""
        try:
            self.logLine.emit(f"Running: {' '.join(cmd)}")

            with subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                universal_newlines=True,
            ) as proc:
                while True:
                    if self._cancelled:
                        proc.terminate()
                        return False, "Cancelled"

                    line = proc.stderr.readline()
                    if not line:
                        if proc.poll() is not None:
                            break
                    else:
                        self.logLine.emit(line.rstrip())

                code = proc.wait()
                return (code == 0), (f"exit code {code}" if code else "")

        except Exception as e:
            return False, str(e)
