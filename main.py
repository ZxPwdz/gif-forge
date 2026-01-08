"""GIF Forge - Video to GIF Converter

Entry point for the application.
"""

import os
import sys
from PySide6 import QtWidgets, QtCore


def _apply_high_dpi_attributes() -> None:
    """Configure high-DPI settings for Qt6"""
    # Qt6 enables high-DPI scaling by default
    return None


def locate_ff_binaries() -> dict:
    """
    Locate FFmpeg binaries in the same directory as the application.

    Returns:
        dict: Paths to ffmpeg, ffprobe, and ffplay executables
    """
    base_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
    suffix = ".exe" if os.name == "nt" else ""

    return {
        "ffmpeg": os.path.join(base_dir, f"ffmpeg{suffix}"),
        "ffprobe": os.path.join(base_dir, f"ffprobe{suffix}"),
        "ffplay": os.path.join(base_dir, f"ffplay{suffix}"),
    }


def main() -> int:
    """Main entry point"""
    _apply_high_dpi_attributes()

    app = QtWidgets.QApplication(sys.argv)
    app.setOrganizationName("GifForge")
    app.setApplicationName("GIF Forge")

    from gif_converter.ui.main_window import MainWindow

    ff_bins = locate_ff_binaries()
    window = MainWindow(ff_bins=ff_bins)
    window.resize(1400, 900)
    window.show()

    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
