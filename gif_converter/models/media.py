from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional
from enum import Enum
import uuid


class ExportMode(Enum):
    """Export mode for GIF generation"""
    SINGLE_SEGMENT = "single_segment"      # One segment → One GIF
    FULL_VIDEO = "full_video"              # Entire video → One GIF
    MERGED_SEGMENTS = "merged_segments"    # Multiple segments → One merged GIF
    BATCH = "batch"                        # Multiple videos/segments → Multiple GIFs


class TextPosition(Enum):
    """Text overlay position presets"""
    BOTTOM_LEFT = "bottom_left"
    BOTTOM_CENTER = "bottom_center"
    BOTTOM_RIGHT = "bottom_right"
    CENTER_LEFT = "center_left"
    CENTER = "center"
    CENTER_RIGHT = "center_right"
    TOP_LEFT = "top_left"
    TOP_CENTER = "top_center"
    TOP_RIGHT = "top_right"
    CUSTOM = "custom"


@dataclass(slots=True)
class MediaInfo:
    """Media file information extracted from ffprobe"""
    width: int
    height: int
    fps_num: int
    fps_den: int
    duration: float
    codec: str
    pix_fmt: str
    bitrate: Optional[int] = None

    @property
    def fps(self) -> float:
        """Calculate actual FPS from numerator and denominator"""
        try:
            return self.fps_num / self.fps_den if self.fps_den else float(self.fps_num)
        except Exception:
            return 0.0

    @property
    def aspect_ratio(self) -> float:
        """Calculate aspect ratio"""
        return self.width / self.height if self.height else 0.0

    def badge_text(self) -> str:
        """Format media info for UI display"""
        fps_value = f"{self.fps:.2f}" if self.fps else "?"
        minutes = int(self.duration // 60) if self.duration else 0
        seconds = int(round(self.duration % 60)) if self.duration else 0
        dur_text = f"{minutes}m{seconds:02d}s"
        br_text = f" • {int(self.bitrate/1000)} kbps" if self.bitrate else ""
        return f"{self.width}×{self.height} • {fps_value} fps • {self.codec} • {dur_text}{br_text}"


@dataclass(slots=True)
class MediaFile:
    """Represents a loaded media file"""
    id: str
    path: str
    info: Optional[MediaInfo] = None


@dataclass(slots=True)
class Segment:
    """Represents a time segment to be extracted from a video"""
    id: str
    file_id: str
    start: float
    end: float
    order: int  # Global order for merging

    @property
    def duration(self) -> float:
        """Calculate segment duration"""
        return max(0.0, self.end - self.start)

    @staticmethod
    def new(file_id: str, start: float, end: float, order: int) -> "Segment":
        """Create a new segment with auto-generated UUID"""
        return Segment(id=str(uuid.uuid4()), file_id=file_id, start=start, end=end, order=order)


@dataclass(slots=True)
class TextOverlay:
    """Text overlay configuration"""
    enabled: bool = False
    text: str = ""
    position: TextPosition = TextPosition.BOTTOM_LEFT
    custom_x: int = 10  # For CUSTOM position
    custom_y: int = 10  # For CUSTOM position
    padding_x: int = 16
    padding_y: int = 16
    font_size: int = 24
    font_color: str = "white"
    font_family: str = "Arial"
    bold: bool = False
    outline_enabled: bool = True
    outline_color: str = "black"
    outline_width: int = 2
    background_enabled: bool = False
    background_color: str = "black"
    background_opacity: float = 0.5

    def get_ffmpeg_position(self, video_width: int, video_height: int) -> tuple[str, str]:
        """Calculate FFmpeg x,y expressions based on position preset and video dimensions"""
        if self.position == TextPosition.CUSTOM:
            return str(self.custom_x), str(self.custom_y)

        # Calculate positions with padding
        px, py = self.padding_x, self.padding_y

        position_map = {
            TextPosition.BOTTOM_LEFT: (f"{px}", f"h-th-{py}"),
            TextPosition.BOTTOM_CENTER: ("(w-tw)/2", f"h-th-{py}"),
            TextPosition.BOTTOM_RIGHT: (f"w-tw-{px}", f"h-th-{py}"),
            TextPosition.CENTER_LEFT: (f"{px}", "(h-th)/2"),
            TextPosition.CENTER: ("(w-tw)/2", "(h-th)/2"),
            TextPosition.CENTER_RIGHT: (f"w-tw-{px}", "(h-th)/2"),
            TextPosition.TOP_LEFT: (f"{px}", f"{py}"),
            TextPosition.TOP_CENTER: ("(w-tw)/2", f"{py}"),
            TextPosition.TOP_RIGHT: (f"w-tw-{px}", f"{py}"),
        }

        return position_map.get(self.position, (f"{px}", f"h-th-{py}"))


@dataclass(slots=True)
class GifExportProfile:
    """GIF export configuration profile"""
    # Basic settings
    preset_name: str = "Medium"
    export_mode: ExportMode = ExportMode.SINGLE_SEGMENT

    # Size and quality
    target_max_size_mb: Optional[float] = None  # Target max file size in MB
    width: Optional[int] = None  # Target width (None = auto/source)
    fps: int = 15  # Frame rate
    colors: int = 256  # Number of colors in palette (32, 64, 128, 256)

    # Quality settings
    dither: str = "sierra2_4a"  # none, bayer, sierra2_4a, floyd_steinberg
    quality: int = 85  # Quality 1-100 (for lossy GIF compression if supported)

    # Playback options
    loop_count: int = 0  # 0 = infinite, -1 = no loop, >0 = loop N times
    speed_multiplier: float = 1.0  # Speed adjustment (0.25x - 4x)
    reverse: bool = False
    boomerang: bool = False  # Play forward then backward

    # Optimization
    optimize_palette: bool = True  # Use stats_mode for better palette
    optimize_size: bool = True  # Try to reduce file size

    # Text overlay
    text_overlay: Optional[TextOverlay] = None

    # Advanced
    scale_filter: str = "lanczos"  # Scaling algorithm: lanczos, bicubic, bilinear
    lossy_compression: Optional[int] = None  # Lossy compression value (0-200, lower is better quality)


# Preset configurations
GIF_PRESETS = {
    "Tiny (<1MB)": GifExportProfile(
        preset_name="Tiny (<1MB)",
        target_max_size_mb=1.0,
        width=640,  # 360p
        fps=10,
        colors=128,
        dither="sierra2_4a",
        lossy_compression=80,
    ),
    "Small (<2MB)": GifExportProfile(
        preset_name="Small (<2MB)",
        target_max_size_mb=2.0,
        width=854,  # 480p
        fps=12,
        colors=256,
        dither="sierra2_4a",
        lossy_compression=40,
    ),
    "Medium (<5MB)": GifExportProfile(
        preset_name="Medium (<5MB)",
        target_max_size_mb=5.0,
        width=1280,  # 720p
        fps=15,
        colors=256,
        dither="sierra2_4a",
    ),
    "Large (<10MB)": GifExportProfile(
        preset_name="Large (<10MB)",
        target_max_size_mb=10.0,
        width=1920,  # 1080p
        fps=20,
        colors=256,
        dither="floyd_steinberg",
    ),
    "High Quality": GifExportProfile(
        preset_name="High Quality",
        target_max_size_mb=None,
        width=None,  # Source resolution
        fps=24,
        colors=256,
        dither="floyd_steinberg",
        optimize_palette=True,
    ),
    "Custom": GifExportProfile(
        preset_name="Custom",
    ),
}
