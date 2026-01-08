"""Main window UI for GIF Forge"""

from __future__ import annotations

import os
import uuid
from typing import Dict, Optional, List

from PySide6 import QtWidgets, QtCore, QtGui

from gif_converter.models.media import (
    MediaFile,
    Segment,
    GifExportProfile,
    TextOverlay,
    TextPosition,
    ExportMode,
    GIF_PRESETS,
)
from gif_converter.models.qt_models import FileListModel, SegmentTableModel
from gif_converter.ffmpeg.gif_exporter import GifExporter, GifExportTask
from gif_converter.ffmpeg.utils import estimate_gif_size, format_size_mb


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self, ff_bins: Dict[str, str], parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("GIF Forge - Video to GIF Converter")
        self._ff_bins = ff_bins

        self._thread_pool = QtCore.QThreadPool.globalInstance()
        self._global_order_counter = 0

        self._build_ui()
        self._connect_actions()
        self._restore_theme()
        self._update_size_estimate()

    # --- UI Building ---
    def _build_ui(self) -> None:
        """Build the main UI"""
        # Toolbar
        toolbar = QtWidgets.QToolBar()
        toolbar.setMovable(False)
        toolbar.setIconSize(QtCore.QSize(20, 20))
        toolbar.setToolButtonStyle(QtCore.Qt.ToolButtonTextBesideIcon)
        self.addToolBar(QtCore.Qt.TopToolBarArea, toolbar)

        self.actionLoad = QtGui.QAction(
            self.style().standardIcon(QtWidgets.QStyle.SP_DialogOpenButton),
            "Load Files",
            self
        )
        self.actionClear = QtGui.QAction(
            self.style().standardIcon(QtWidgets.QStyle.SP_TrashIcon),
            "Clear All",
            self
        )
        self.actionExport = QtGui.QAction(
            self.style().standardIcon(QtWidgets.QStyle.SP_DialogSaveButton),
            "Export GIF",
            self
        )
        self.actionTheme = QtGui.QAction(
            self.style().standardIcon(QtWidgets.QStyle.SP_DesktopIcon),
            "Theme",
            self
        )

        toolbar.addAction(self.actionLoad)
        toolbar.addAction(self.actionClear)
        toolbar.addSeparator()
        toolbar.addAction(self.actionExport)
        toolbar.addSeparator()
        toolbar.addAction(self.actionTheme)

        # Main layout
        main_splitter = QtWidgets.QSplitter(QtCore.Qt.Vertical)

        # Top section: Files and Segments
        top_widget = self._build_top_section()
        main_splitter.addWidget(top_widget)

        # Bottom section: Export Settings
        bottom_widget = self._build_bottom_section()
        main_splitter.addWidget(bottom_widget)

        main_splitter.setStretchFactor(0, 2)
        main_splitter.setStretchFactor(1, 1)

        self.setCentralWidget(main_splitter)

        # Log dock
        self._log_dock = QtWidgets.QDockWidget("Export Log")
        self._log_edit = QtWidgets.QPlainTextEdit()
        self._log_edit.setReadOnly(True)
        self._log_edit.setMaximumBlockCount(1000)
        self._log_dock.setWidget(self._log_edit)
        self.addDockWidget(QtCore.Qt.BottomDockWidgetArea, self._log_dock)
        self._log_dock.hide()  # Hidden by default

        # Keyboard shortcuts
        QtGui.QShortcut(QtGui.QKeySequence("Ctrl+O"), self, activated=self._on_load_files)
        QtGui.QShortcut(QtGui.QKeySequence("Delete"), self, activated=self._on_delete_selected_segments)
        QtGui.QShortcut(QtGui.QKeySequence("Ctrl+E"), self, activated=self._on_export)

    def _build_top_section(self) -> QtWidgets.QWidget:
        """Build top section with files and segments"""
        widget = QtWidgets.QWidget()
        layout = QtWidgets.QHBoxLayout(widget)
        layout.setContentsMargins(8, 8, 8, 8)

        # Left: Files
        left_widget = QtWidgets.QWidget()
        left_layout = QtWidgets.QVBoxLayout(left_widget)
        left_layout.setSpacing(8)

        left_layout.addWidget(QtWidgets.QLabel("<b>Media Files</b>"))

        self.filesView = QtWidgets.QListView()
        self.filesView.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self.fileModel = FileListModel()
        self.filesView.setModel(self.fileModel)
        self.filesView.setMaximumHeight(150)
        left_layout.addWidget(self.filesView)

        # Export mode selector
        mode_group = QtWidgets.QGroupBox("Export Mode")
        mode_layout = QtWidgets.QVBoxLayout(mode_group)
        mode_layout.setSpacing(4)

        self.radioFullVideo = QtWidgets.QRadioButton("Full Video → GIF")
        self.radioSegment = QtWidgets.QRadioButton("Single Segment → GIF")
        self.radioMerged = QtWidgets.QRadioButton("All Segments → Merged GIF")
        self.radioBatch = QtWidgets.QRadioButton("Batch (Multiple GIFs)")

        self.radioFullVideo.setToolTip("Convert entire video to GIF")
        self.radioSegment.setToolTip("Convert selected segment to GIF")
        self.radioMerged.setToolTip("Merge all segments into one GIF")
        self.radioBatch.setToolTip("Create separate GIF for each segment")

        self.radioSegment.setChecked(True)

        mode_layout.addWidget(self.radioFullVideo)
        mode_layout.addWidget(self.radioSegment)
        mode_layout.addWidget(self.radioMerged)
        mode_layout.addWidget(self.radioBatch)

        left_layout.addWidget(mode_group)
        left_layout.addStretch()

        # Middle: Segments
        middle_widget = QtWidgets.QWidget()
        middle_layout = QtWidgets.QVBoxLayout(middle_widget)
        middle_layout.setSpacing(8)

        seg_header = QtWidgets.QHBoxLayout()
        self.segments_label = QtWidgets.QLabel("<b>Time Ranges</b>")
        self.current_file_label = QtWidgets.QLabel("<i>No file selected</i>")
        self.current_file_label.setStyleSheet("color: #666;")
        seg_header.addWidget(self.segments_label)
        seg_header.addStretch(1)
        seg_header.addWidget(self.current_file_label)
        middle_layout.addLayout(seg_header)

        seg_actions = QtWidgets.QHBoxLayout()
        seg_actions.setSpacing(6)
        self.btnAddRange = QtWidgets.QPushButton("+ Add Range")
        self.btnDelete = QtWidgets.QPushButton("Delete Selected")
        self.btnClearRanges = QtWidgets.QPushButton("Clear All")
        seg_actions.addWidget(self.btnAddRange)
        seg_actions.addWidget(self.btnDelete)
        seg_actions.addWidget(self.btnClearRanges)
        seg_actions.addStretch(1)
        middle_layout.addLayout(seg_actions)

        self.segmentModel = SegmentTableModel()
        self.segmentsView = QtWidgets.QTableView()
        self.segmentsView.setModel(self.segmentModel)
        self.segmentsView.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.segmentsView.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)
        self.segmentsView.setAlternatingRowColors(True)
        header = self.segmentsView.horizontalHeader()
        header.setStretchLastSection(True)
        middle_layout.addWidget(self.segmentsView, 1)

        # Right: Quick Range Builder
        right_widget = QtWidgets.QWidget()
        right_layout = QtWidgets.QVBoxLayout(right_widget)
        right_layout.setSpacing(8)

        quick_group = QtWidgets.QGroupBox("Quick Range Builder")
        quick_group_layout = QtWidgets.QVBoxLayout(quick_group)

        info_label = QtWidgets.QLabel("<i>Add ranges to the selected file</i>")
        info_label.setStyleSheet("color: #666; font-size: 9pt;")
        quick_group_layout.addWidget(info_label)

        self.quickRowsContainer = QtWidgets.QVBoxLayout()
        self.quickRowsContainer.setSpacing(6)
        quick_group_layout.addLayout(self.quickRowsContainer)
        self._add_quick_rows(3)

        row_buttons = QtWidgets.QHBoxLayout()
        self.btnAddThree = QtWidgets.QPushButton("+ 3 Rows")
        self.btnClearRows = QtWidgets.QPushButton("Clear Rows")
        row_buttons.addWidget(self.btnAddThree)
        row_buttons.addWidget(self.btnClearRows)
        row_buttons.addStretch(1)
        quick_group_layout.addLayout(row_buttons)

        right_layout.addWidget(quick_group)
        right_layout.addStretch()

        # Add to splitter
        splitter = QtWidgets.QSplitter()
        splitter.addWidget(left_widget)
        splitter.addWidget(middle_widget)
        splitter.addWidget(right_widget)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 2)
        splitter.setStretchFactor(2, 1)
        splitter.setSizes([250, 500, 350])

        layout.addWidget(splitter)
        return widget

    def _build_bottom_section(self) -> QtWidgets.QWidget:
        """Build bottom section with export settings"""
        widget = QtWidgets.QWidget()
        main_layout = QtWidgets.QVBoxLayout(widget)
        main_layout.setContentsMargins(8, 8, 8, 8)
        main_layout.setSpacing(8)

        # Create tab widget for settings
        tabs = QtWidgets.QTabWidget()

        # Tab 1: Basic Settings
        basic_tab = self._build_basic_settings_tab()
        tabs.addTab(basic_tab, "Basic Settings")

        # Tab 2: Text Overlay
        text_tab = self._build_text_overlay_tab()
        tabs.addTab(text_tab, "Text Overlay")

        # Tab 3: Advanced Settings
        advanced_tab = self._build_advanced_settings_tab()
        tabs.addTab(advanced_tab, "Advanced")

        main_layout.addWidget(tabs)

        # Size estimate and export controls
        controls_widget = self._build_export_controls()
        main_layout.addWidget(controls_widget)

        return widget

    def _build_basic_settings_tab(self) -> QtWidgets.QWidget:
        """Build basic settings tab"""
        widget = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(widget)
        layout.setSpacing(12)

        # Preset selector
        preset_layout = QtWidgets.QHBoxLayout()
        preset_layout.addWidget(QtWidgets.QLabel("<b>Preset:</b>"))
        self.cmbPreset = QtWidgets.QComboBox()
        self.cmbPreset.addItems(list(GIF_PRESETS.keys()))
        self.cmbPreset.setCurrentText("Medium (<5MB)")
        preset_layout.addWidget(self.cmbPreset, 1)
        layout.addLayout(preset_layout)

        # Resolution, FPS, Colors
        grid = QtWidgets.QGridLayout()
        grid.setSpacing(8)

        grid.addWidget(QtWidgets.QLabel("Resolution:"), 0, 0)
        self.cmbResolution = QtWidgets.QComboBox()
        self.cmbResolution.addItems([
            "Auto (Source)",
            "2160p (4K)",
            "1440p (2K)",
            "1080p (FHD)",
            "720p (HD)",
            "480p (SD)",
            "360p",
            "Custom"
        ])
        self.cmbResolution.setCurrentText("720p (HD)")
        grid.addWidget(self.cmbResolution, 0, 1)

        # Custom width spinner (hidden by default)
        self.spinWidth = QtWidgets.QSpinBox()
        self.spinWidth.setRange(100, 4000)
        self.spinWidth.setValue(640)
        self.spinWidth.setSuffix(" px")
        self.spinWidth.setVisible(False)
        grid.addWidget(self.spinWidth, 0, 1)

        grid.addWidget(QtWidgets.QLabel("FPS:"), 0, 2)
        self.spinFps = QtWidgets.QSpinBox()
        self.spinFps.setRange(5, 60)
        self.spinFps.setValue(15)
        grid.addWidget(self.spinFps, 0, 3)

        grid.addWidget(QtWidgets.QLabel("Colors:"), 1, 0)
        self.cmbColors = QtWidgets.QComboBox()
        self.cmbColors.addItems(["32", "64", "128", "256"])
        self.cmbColors.setCurrentText("256")
        grid.addWidget(self.cmbColors, 1, 1)

        grid.addWidget(QtWidgets.QLabel("Dithering:"), 1, 2)
        self.cmbDither = QtWidgets.QComboBox()
        self.cmbDither.addItems(["None", "Bayer", "Sierra2_4a", "Floyd-Steinberg"])
        self.cmbDither.setCurrentText("Sierra2_4a")
        grid.addWidget(self.cmbDither, 1, 3)

        layout.addLayout(grid)

        # Target file size
        size_group = QtWidgets.QGroupBox("File Size Target")
        size_layout = QtWidgets.QHBoxLayout(size_group)

        self.chkTargetSize = QtWidgets.QCheckBox("Limit size to:")
        self.spinTargetSize = QtWidgets.QSpinBox()
        self.spinTargetSize.setRange(1, 500)  # Support up to 500MB target
        self.spinTargetSize.setValue(5)
        self.spinTargetSize.setSuffix(" MB")
        self.spinTargetSize.setEnabled(False)

        size_layout.addWidget(self.chkTargetSize)
        size_layout.addWidget(self.spinTargetSize)
        size_layout.addStretch()

        layout.addWidget(size_group)

        layout.addStretch()
        return widget

    def _build_text_overlay_tab(self) -> QtWidgets.QWidget:
        """Build text overlay settings tab"""
        widget = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(widget)
        layout.setSpacing(12)

        # Enable checkbox
        self.chkTextOverlay = QtWidgets.QCheckBox("Enable Text Overlay")
        layout.addWidget(self.chkTextOverlay)

        # Text input
        text_layout = QtWidgets.QHBoxLayout()
        text_layout.addWidget(QtWidgets.QLabel("Text:"))
        self.txtOverlayText = QtWidgets.QLineEdit()
        self.txtOverlayText.setPlaceholderText("Enter text to overlay...")
        self.txtOverlayText.setEnabled(False)
        text_layout.addWidget(self.txtOverlayText, 1)
        layout.addLayout(text_layout)

        # Position and style
        grid = QtWidgets.QGridLayout()
        grid.setSpacing(8)

        grid.addWidget(QtWidgets.QLabel("Position:"), 0, 0)
        self.cmbTextPosition = QtWidgets.QComboBox()
        self.cmbTextPosition.addItems([
            "Bottom Left", "Bottom Center", "Bottom Right",
            "Center Left", "Center", "Center Right",
            "Top Left", "Top Center", "Top Right", "Custom"
        ])
        self.cmbTextPosition.setCurrentText("Bottom Left")
        self.cmbTextPosition.setEnabled(False)
        grid.addWidget(self.cmbTextPosition, 0, 1)

        grid.addWidget(QtWidgets.QLabel("Font Size:"), 0, 2)
        self.spinFontSize = QtWidgets.QSpinBox()
        self.spinFontSize.setRange(8, 200)
        self.spinFontSize.setValue(24)
        self.spinFontSize.setEnabled(False)
        grid.addWidget(self.spinFontSize, 0, 3)

        grid.addWidget(QtWidgets.QLabel("Font Color:"), 1, 0)
        self.cmbFontColor = QtWidgets.QComboBox()
        self.cmbFontColor.addItems(["white", "black", "yellow", "red", "green", "blue"])
        self.cmbFontColor.setEnabled(False)
        grid.addWidget(self.cmbFontColor, 1, 1)

        grid.addWidget(QtWidgets.QLabel("Padding:"), 1, 2)
        self.spinTextPadding = QtWidgets.QSpinBox()
        self.spinTextPadding.setRange(0, 100)
        self.spinTextPadding.setValue(16)
        self.spinTextPadding.setSuffix(" px")
        self.spinTextPadding.setEnabled(False)
        grid.addWidget(self.spinTextPadding, 1, 3)

        layout.addLayout(grid)

        # Style options
        style_layout = QtWidgets.QHBoxLayout()
        self.chkBold = QtWidgets.QCheckBox("Bold")
        self.chkBold.setEnabled(False)
        self.chkOutline = QtWidgets.QCheckBox("Outline")
        self.chkOutline.setChecked(True)
        self.chkOutline.setEnabled(False)
        self.chkBackground = QtWidgets.QCheckBox("Background Box")
        self.chkBackground.setEnabled(False)

        style_layout.addWidget(self.chkBold)
        style_layout.addWidget(self.chkOutline)
        style_layout.addWidget(self.chkBackground)
        style_layout.addStretch()

        layout.addLayout(style_layout)
        layout.addStretch()

        return widget

    def _build_advanced_settings_tab(self) -> QtWidgets.QWidget:
        """Build advanced settings tab"""
        widget = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(widget)
        layout.setSpacing(12)

        # Playback options
        playback_group = QtWidgets.QGroupBox("Playback Options")
        playback_layout = QtWidgets.QGridLayout(playback_group)
        playback_layout.setSpacing(8)

        playback_layout.addWidget(QtWidgets.QLabel("Speed:"), 0, 0)
        self.cmbSpeed = QtWidgets.QComboBox()
        self.cmbSpeed.addItems(["0.25x", "0.5x", "0.75x", "1x", "1.5x", "2x", "3x", "4x"])
        self.cmbSpeed.setCurrentText("1x")
        playback_layout.addWidget(self.cmbSpeed, 0, 1)

        playback_layout.addWidget(QtWidgets.QLabel("Loop:"), 0, 2)
        self.cmbLoop = QtWidgets.QComboBox()
        self.cmbLoop.addItems(["Forever", "Once", "2 times", "3 times", "5 times", "10 times"])
        self.cmbLoop.setCurrentText("Forever")
        playback_layout.addWidget(self.cmbLoop, 0, 3)

        self.chkReverse = QtWidgets.QCheckBox("Reverse")
        playback_layout.addWidget(self.chkReverse, 1, 0, 1, 2)

        self.chkBoomerang = QtWidgets.QCheckBox("Boomerang (Forward + Backward)")
        playback_layout.addWidget(self.chkBoomerang, 1, 2, 1, 2)

        layout.addWidget(playback_group)

        # Optimization
        opt_group = QtWidgets.QGroupBox("Optimization")
        opt_layout = QtWidgets.QVBoxLayout(opt_group)

        self.chkOptimizePalette = QtWidgets.QCheckBox("Optimize Palette (Better quality)")
        self.chkOptimizePalette.setChecked(True)
        opt_layout.addWidget(self.chkOptimizePalette)

        lossy_layout = QtWidgets.QHBoxLayout()
        lossy_layout.addWidget(QtWidgets.QLabel("Lossy Compression:"))
        self.spinLossy = QtWidgets.QSpinBox()
        self.spinLossy.setRange(0, 200)
        self.spinLossy.setValue(0)
        self.spinLossy.setSpecialValueText("None")
        self.spinLossy.setToolTip("Lower = better quality, higher = smaller size")
        lossy_layout.addWidget(self.spinLossy)
        lossy_layout.addStretch()
        opt_layout.addLayout(lossy_layout)

        layout.addWidget(opt_group)
        layout.addStretch()

        return widget

    def _build_export_controls(self) -> QtWidgets.QWidget:
        """Build export controls and progress"""
        widget = QtWidgets.QFrame()
        widget.setFrameShape(QtWidgets.QFrame.StyledPanel)
        layout = QtWidgets.QVBoxLayout(widget)
        layout.setSpacing(8)

        # Size estimate
        estimate_layout = QtWidgets.QHBoxLayout()
        estimate_layout.addWidget(QtWidgets.QLabel("<b>Estimated Size:</b>"))
        self.lblEstimatedSize = QtWidgets.QLabel("0 MB")
        self.lblEstimatedSize.setStyleSheet("font-size: 12pt; color: #0066cc;")
        estimate_layout.addWidget(self.lblEstimatedSize)
        estimate_layout.addStretch()

        self.btnPreview = QtWidgets.QPushButton("Preview GIF")
        self.btnPreview.setEnabled(False)
        estimate_layout.addWidget(self.btnPreview)

        layout.addLayout(estimate_layout)

        # Progress and export
        progress_layout = QtWidgets.QHBoxLayout()

        self.lblStage = QtWidgets.QLabel("Idle")
        self.lblStage.setMinimumWidth(100)

        self.progress = QtWidgets.QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setTextVisible(True)

        self.btnCancel = QtWidgets.QPushButton("Cancel")
        self.btnCancel.setEnabled(False)

        self.btnExport = QtWidgets.QPushButton("Export GIF")
        self.btnExport.setEnabled(False)
        self.btnExport.setMinimumHeight(32)
        self.btnExport.setMinimumWidth(120)

        progress_layout.addWidget(self.lblStage)
        progress_layout.addWidget(self.progress, 1)
        progress_layout.addWidget(self.btnCancel)
        progress_layout.addWidget(self.btnExport)

        layout.addLayout(progress_layout)

        return widget

    def _add_quick_rows(self, count: int) -> None:
        """Add quick range input rows"""
        for _ in range(count):
            row = self._make_quick_row()
            self.quickRowsContainer.addLayout(row)

    def _make_quick_row(self) -> QtWidgets.QHBoxLayout:
        """Create a quick range input row"""
        row = QtWidgets.QHBoxLayout()
        row.setSpacing(4)

        m_start = QtWidgets.QSpinBox()
        m_start.setRange(0, 24 * 60)
        m_start.setSuffix(" m")
        m_start.setMaximumWidth(70)

        s_start = QtWidgets.QSpinBox()
        s_start.setRange(0, 59)
        s_start.setSuffix(" s")
        s_start.setMaximumWidth(60)

        m_end = QtWidgets.QSpinBox()
        m_end.setRange(0, 24 * 60)
        m_end.setSuffix(" m")
        m_end.setMaximumWidth(70)

        s_end = QtWidgets.QSpinBox()
        s_end.setRange(0, 59)
        s_end.setSuffix(" s")
        s_end.setMaximumWidth(60)

        btn_add = QtWidgets.QPushButton("Add")
        btn_add.setMinimumWidth(50)
        btn_clear = QtWidgets.QPushButton("×")
        btn_clear.setMaximumWidth(30)

        def on_add():
            self._quick_add_segment(m_start.value(), s_start.value(), m_end.value(), s_end.value())

        def on_clear():
            m_start.setValue(0)
            s_start.setValue(0)
            m_end.setValue(0)
            s_end.setValue(0)

        btn_add.clicked.connect(on_add)
        btn_clear.clicked.connect(on_clear)

        row.addWidget(QtWidgets.QLabel("Start:"))
        row.addWidget(m_start)
        row.addWidget(s_start)
        row.addWidget(QtWidgets.QLabel("End:"))
        row.addWidget(m_end)
        row.addWidget(s_end)
        row.addWidget(btn_add)
        row.addWidget(btn_clear)
        row.addStretch()

        return row

    # --- Actions and Connections ---
    def _connect_actions(self) -> None:
        """Connect UI actions and signals"""
        self.actionLoad.triggered.connect(self._on_load_files)
        self.actionClear.triggered.connect(self._on_clear_all)
        self.actionExport.triggered.connect(self._on_export)
        self.actionTheme.triggered.connect(self._toggle_theme)

        self.filesView.selectionModel().selectionChanged.connect(self._on_file_selected)
        self.btnAddRange.clicked.connect(self._on_add_range_dialog)
        self.btnDelete.clicked.connect(self._on_delete_selected_segments)
        self.btnClearRanges.clicked.connect(self._on_clear_ranges)
        self.btnAddThree.clicked.connect(lambda: self._add_quick_rows(3))
        self.btnClearRows.clicked.connect(self._on_clear_quick_rows)
        self.btnCancel.clicked.connect(self._on_cancel_export)
        self.btnPreview.clicked.connect(self._on_preview)

        # Settings change handlers
        self.cmbPreset.currentTextChanged.connect(self._on_preset_changed)
        self.cmbResolution.currentTextChanged.connect(self._on_resolution_changed)
        self.spinWidth.valueChanged.connect(self._update_size_estimate)
        self.spinFps.valueChanged.connect(self._update_size_estimate)
        self.cmbColors.currentTextChanged.connect(self._update_size_estimate)
        self.cmbDither.currentTextChanged.connect(self._update_size_estimate)
        self.chkTargetSize.toggled.connect(self.spinTargetSize.setEnabled)
        self.chkTargetSize.toggled.connect(self._on_target_size_changed)
        self.spinTargetSize.valueChanged.connect(self._on_target_size_changed)

        # Text overlay enable/disable
        self.chkTextOverlay.toggled.connect(self._on_text_overlay_toggled)

        # Enable export when segments exist
        self.segmentModel.dataChanged.connect(self._check_export_enabled)
        self.segmentModel.rowsInserted.connect(self._check_export_enabled)
        self.segmentModel.rowsRemoved.connect(self._check_export_enabled)

    def _on_text_overlay_toggled(self, enabled: bool) -> None:
        """Enable/disable text overlay controls"""
        self.txtOverlayText.setEnabled(enabled)
        self.cmbTextPosition.setEnabled(enabled)
        self.spinFontSize.setEnabled(enabled)
        self.cmbFontColor.setEnabled(enabled)
        self.spinTextPadding.setEnabled(enabled)
        self.chkBold.setEnabled(enabled)
        self.chkOutline.setEnabled(enabled)
        self.chkBackground.setEnabled(enabled)

    def _check_export_enabled(self) -> None:
        """Enable/disable export button based on content"""
        has_files = self.fileModel.rowCount() > 0
        has_segments = self.segmentModel.has_segments()

        # Enable if we have files (for full video mode) or segments
        enable = has_files if self.radioFullVideo.isChecked() else has_segments

        self.btnExport.setEnabled(enable)
        self.btnPreview.setEnabled(enable)
        self._update_size_estimate()

    def _on_load_files(self) -> None:
        """Load video files"""
        last_dir = QtCore.QSettings().value("last_dir", os.path.expanduser("~"))
        files, _ = QtWidgets.QFileDialog.getOpenFileNames(
            self,
            "Load Video Files",
            last_dir,
            "Videos (*.mp4 *.mov *.avi *.mkv *.webm *.flv)"
        )

        if not files:
            return

        QtCore.QSettings().setValue("last_dir", os.path.dirname(files[0]))

        for path in files:
            mf = MediaFile(id=str(uuid.uuid4()), path=path, info=None)
            row = self.fileModel.add_file(mf)
            if self.fileModel.rowCount() == 1:
                self.filesView.setCurrentIndex(self.fileModel.index(row))
            # Probe asynchronously
            self._probe_file_async(mf)

        self._check_export_enabled()

    def _probe_file_async(self, media_file: MediaFile) -> None:
        """Probe media file asynchronously"""
        from gif_converter.ffmpeg.utils import probe_media_info

        class _ProbeWorker(QtCore.QObject):
            done = QtCore.Signal(object)

            def __init__(self, path: str, ffprobe: str):
                super().__init__()
                self._path = path
                self._ffprobe = ffprobe

        worker = _ProbeWorker(media_file.path, self._ff_bins["ffprobe"])

        if not hasattr(self, "_active_probe_workers"):
            self._active_probe_workers = []
        self._active_probe_workers.append(worker)

        class _ProbeRunnable(QtCore.QRunnable):
            def __init__(self, w: _ProbeWorker):
                super().__init__()
                self._w = w

            def run(self):
                info = probe_media_info(self._w._ffprobe, self._w._path)
                self._w.done.emit(info)

        def on_done_and_cleanup(info):
            try:
                if info is None:
                    QtWidgets.QMessageBox.warning(
                        self, "Probe failed",
                        f"Could not read media info for:\n{media_file.path}"
                    )
                else:
                    self.fileModel.update_info(media_file.id, info)
                    self._update_size_estimate()
            finally:
                try:
                    self._active_probe_workers.remove(worker)
                except:
                    pass

        worker.done.connect(on_done_and_cleanup)
        self._thread_pool.start(_ProbeRunnable(worker))

    def _on_clear_all(self) -> None:
        """Clear all files and segments"""
        self.fileModel.clear()
        self.segmentModel.set_current_file(None)
        self._check_export_enabled()

    def _on_file_selected(self) -> None:
        """Handle file selection"""
        idxs = self.filesView.selectionModel().selectedIndexes()
        file = self.fileModel.file_at(idxs[0].row()) if idxs else None
        self.segmentModel.set_current_file(file.id if file else None)

        if file:
            filename = QtCore.QFileInfo(file.path).fileName()
            self.current_file_label.setText(f"<i>Editing: {filename}</i>")
            self.current_file_label.setStyleSheet("color: #0066cc; font-weight: bold;")
        else:
            self.current_file_label.setText("<i>No file selected</i>")
            self.current_file_label.setStyleSheet("color: #666;")

    def _quick_add_segment(self, m_start: int, s_start: int, m_end: int, s_end: int) -> None:
        """Add segment from quick builder"""
        idxs = self.filesView.selectionModel().selectedIndexes()
        if not idxs:
            QtWidgets.QMessageBox.information(self, "No file selected", "Select a file to add ranges.")
            return

        file = self.fileModel.file_at(idxs[0].row())
        if not file or not file.info:
            QtWidgets.QMessageBox.information(self, "Not ready", "File info not ready yet.")
            return

        start = m_start * 60 + s_start
        end = m_end * 60 + s_end

        if end <= start or start < 0 or end > file.info.duration:
            QtWidgets.QMessageBox.warning(self, "Invalid range", "Check start/end and ensure within duration.")
            return

        self._global_order_counter += 1
        seg = Segment.new(file.id, float(start), float(end), self._global_order_counter)
        self.segmentModel.add_segment(file.id, seg)
        self._check_export_enabled()

    def _on_add_range_dialog(self) -> None:
        """Show add range dialog"""
        dlg = QtWidgets.QDialog(self)
        dlg.setWindowTitle("Add Time Range")
        layout = QtWidgets.QFormLayout(dlg)

        m_start = QtWidgets.QSpinBox()
        m_start.setRange(0, 24 * 60)
        s_start = QtWidgets.QSpinBox()
        s_start.setRange(0, 59)
        m_end = QtWidgets.QSpinBox()
        m_end.setRange(0, 24 * 60)
        s_end = QtWidgets.QSpinBox()
        s_end.setRange(0, 59)

        layout.addRow("Start (minutes):", m_start)
        layout.addRow("Start (seconds):", s_start)
        layout.addRow("End (minutes):", m_end)
        layout.addRow("End (seconds):", s_end)

        btns = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel)
        layout.addRow(btns)
        btns.accepted.connect(dlg.accept)
        btns.rejected.connect(dlg.reject)

        if dlg.exec() == QtWidgets.QDialog.Accepted:
            self._quick_add_segment(m_start.value(), s_start.value(), m_end.value(), s_end.value())

    def _on_delete_selected_segments(self) -> None:
        """Delete selected segments"""
        rows = sorted({i.row() for i in self.segmentsView.selectionModel().selectedIndexes()})
        if rows:
            self.segmentModel.remove_rows(rows)

    def _on_clear_ranges(self) -> None:
        """Clear all ranges for current file"""
        rows = list(range(self.segmentModel.rowCount()))
        if rows:
            self.segmentModel.remove_rows(rows)

    def _on_clear_quick_rows(self) -> None:
        """Clear quick entry rows"""
        for i in range(self.quickRowsContainer.count()):
            item = self.quickRowsContainer.itemAt(i)
            if not item:
                continue
            layout = item.layout()
            if not layout:
                continue
            for j in range(layout.count()):
                w = layout.itemAt(j).widget()
                if isinstance(w, QtWidgets.QSpinBox):
                    w.setValue(0)

    def _on_preset_changed(self, preset_name: str) -> None:
        """Apply preset settings"""
        if preset_name not in GIF_PRESETS:
            return

        preset = GIF_PRESETS[preset_name]

        # Apply preset resolution
        if preset.width:
            # Map width to resolution preset
            res_map = {
                640: "360p",
                854: "480p (SD)",
                1280: "720p (HD)",
                1920: "1080p (FHD)",
                2560: "1440p (2K)",
                3840: "2160p (4K)",
            }
            res_text = res_map.get(preset.width, "Custom")
            self.cmbResolution.setCurrentText(res_text)
            if res_text == "Custom":
                self.spinWidth.setValue(preset.width)
        else:
            self.cmbResolution.setCurrentText("Auto (Source)")

        self.spinFps.setValue(preset.fps)
        self.cmbColors.setCurrentText(str(preset.colors))

        dither_map = {
            "none": "None",
            "bayer": "Bayer",
            "sierra2_4a": "Sierra2_4a",
            "floyd_steinberg": "Floyd-Steinberg",
        }
        self.cmbDither.setCurrentText(dither_map.get(preset.dither, "Sierra2_4a"))

        if preset.target_max_size_mb:
            self.chkTargetSize.setChecked(True)
            self.spinTargetSize.setValue(int(preset.target_max_size_mb))
        else:
            self.chkTargetSize.setChecked(False)

        if preset.lossy_compression is not None:
            self.spinLossy.setValue(preset.lossy_compression)
        else:
            self.spinLossy.setValue(0)

        self._update_size_estimate()

    def _on_resolution_changed(self, resolution_text: str) -> None:
        """Handle resolution preset change"""
        if resolution_text == "Custom":
            # Show the custom width spinner
            self.spinWidth.setVisible(True)
        else:
            self.spinWidth.setVisible(False)
        self._update_size_estimate()

    def _get_resolution_width(self) -> Optional[int]:
        """Get width from resolution selection"""
        res_text = self.cmbResolution.currentText()

        if res_text == "Auto (Source)":
            return None
        elif res_text == "2160p (4K)":
            return 3840
        elif res_text == "1440p (2K)":
            return 2560
        elif res_text == "1080p (FHD)":
            return 1920
        elif res_text == "720p (HD)":
            return 1280
        elif res_text == "480p (SD)":
            return 854
        elif res_text == "360p":
            return 640
        elif res_text == "Custom":
            return self.spinWidth.value()
        return 640  # Default

    def _on_target_size_changed(self) -> None:
        """Handle target file size change - auto-adjust settings"""
        if not self.chkTargetSize.isChecked():
            self._update_size_estimate()
            return

        # Auto-adjust settings to meet target
        target_mb = self.spinTargetSize.value()

        # Get estimated size with current settings
        self._update_size_estimate()

        # Parse current estimate
        estimate_text = self.lblEstimatedSize.text()
        if "MB" in estimate_text or "KB" in estimate_text:
            # Extract number
            import re
            match = re.search(r'([\d.]+)\s*(MB|KB)', estimate_text)
            if match:
                current_size = float(match.group(1))
                unit = match.group(2)
                if unit == "KB":
                    current_size /= 1024

                # If over target, suggest adjustments
                if current_size > target_mb:
                    self._auto_adjust_for_size(target_mb, current_size)

    def _auto_adjust_for_size(self, target_mb: float, current_mb: float) -> None:
        """Auto-adjust settings to meet target file size"""
        # Calculate how much we need to reduce
        ratio = target_mb / current_mb

        # Strategy: Reduce resolution, FPS, and colors progressively
        if ratio < 0.3:  # Need 70%+ reduction
            # Aggressive: Reduce resolution significantly
            self.cmbResolution.setCurrentText("360p")
            self.spinFps.setValue(10)
            self.cmbColors.setCurrentText("128")
            self.spinLossy.setValue(min(100, int(80 * (1 - ratio))))
        elif ratio < 0.5:  # Need 50-70% reduction
            # Moderate: Reduce to 480p
            self.cmbResolution.setCurrentText("480p (SD)")
            self.spinFps.setValue(12)
            self.cmbColors.setCurrentText("256")
            self.spinLossy.setValue(min(80, int(60 * (1 - ratio))))
        elif ratio < 0.7:  # Need 30-50% reduction
            # Light: Reduce to 720p
            current_res = self.cmbResolution.currentText()
            if "1080p" in current_res or "1440p" in current_res or "2160p" in current_res:
                self.cmbResolution.setCurrentText("720p (HD)")
            self.spinFps.setValue(15)
            self.spinLossy.setValue(min(60, int(40 * (1 - ratio))))
        else:  # Need <30% reduction
            # Minor: Just add lossy compression
            self.spinLossy.setValue(min(40, int(30 * (1 - ratio))))

        # Update estimate to reflect changes
        QtCore.QTimer.singleShot(100, self._update_size_estimate)

    def _update_size_estimate(self) -> None:
        """Update estimated file size"""
        # Get first file info for estimation
        if self.fileModel.rowCount() == 0:
            self.lblEstimatedSize.setText("No files loaded")
            return

        file = self.fileModel.file_at(0)
        if not file or not file.info:
            self.lblEstimatedSize.setText("Loading...")
            return

        # Calculate duration based on mode
        if self.radioFullVideo.isChecked():
            duration = file.info.duration
        else:
            segments = self.segmentModel.all_segments_in_global_order()
            if not segments:
                self.lblEstimatedSize.setText("No segments")
                return
            duration = sum(seg.duration for seg in segments)

        if self.chkBoomerang.isChecked():
            duration *= 2  # Boomerang plays forward and backward

        # Get settings
        width = self._get_resolution_width() or file.info.width
        height = int(width / file.info.aspect_ratio) if file.info.aspect_ratio else file.info.height
        fps = self.spinFps.value()
        colors = int(self.cmbColors.currentText())

        dither_map = {
            "None": "none",
            "Bayer": "bayer",
            "Sierra2_4a": "sierra2_4a",
            "Floyd-Steinberg": "floyd_steinberg",
        }
        dither = dither_map.get(self.cmbDither.currentText(), "sierra2_4a")

        # Estimate size
        estimated_mb = estimate_gif_size(duration, width, height, fps, colors, dither)

        # Apply lossy compression reduction (rough estimate)
        lossy = self.spinLossy.value()
        if lossy > 0:
            # Lossy compression can reduce size by 20-50%
            reduction = min(0.5, lossy / 400)  # Max 50% reduction
            estimated_mb *= (1 - reduction)

        # Show estimate
        size_str = format_size_mb(estimated_mb)

        # Check against target
        if self.chkTargetSize.isChecked():
            target_mb = self.spinTargetSize.value()
            if estimated_mb > target_mb:
                self.lblEstimatedSize.setText(f"{size_str} (⚠ Over target of {target_mb} MB)")
                self.lblEstimatedSize.setStyleSheet("font-size: 12pt; color: #cc6600;")
            else:
                self.lblEstimatedSize.setText(f"{size_str} (✓ Under target)")
                self.lblEstimatedSize.setStyleSheet("font-size: 12pt; color: #00aa00;")
        else:
            self.lblEstimatedSize.setText(size_str)
            self.lblEstimatedSize.setStyleSheet("font-size: 12pt; color: #0066cc;")

    def _build_export_profile(self) -> GifExportProfile:
        """Build export profile from UI settings"""
        # Dithering
        dither_map = {
            "None": "none",
            "Bayer": "bayer",
            "Sierra2_4a": "sierra2_4a",
            "Floyd-Steinberg": "floyd_steinberg",
        }
        dither = dither_map.get(self.cmbDither.currentText(), "sierra2_4a")

        # Speed
        speed_map = {
            "0.25x": 0.25, "0.5x": 0.5, "0.75x": 0.75, "1x": 1.0,
            "1.5x": 1.5, "2x": 2.0, "3x": 3.0, "4x": 4.0
        }
        speed = speed_map.get(self.cmbSpeed.currentText(), 1.0)

        # Loop
        loop_map = {
            "Forever": 0, "Once": -1, "2 times": 2, "3 times": 3,
            "5 times": 5, "10 times": 10
        }
        loop = loop_map.get(self.cmbLoop.currentText(), 0)

        # Text overlay
        text_overlay = None
        if self.chkTextOverlay.isChecked() and self.txtOverlayText.text().strip():
            pos_map = {
                "Bottom Left": TextPosition.BOTTOM_LEFT,
                "Bottom Center": TextPosition.BOTTOM_CENTER,
                "Bottom Right": TextPosition.BOTTOM_RIGHT,
                "Center Left": TextPosition.CENTER_LEFT,
                "Center": TextPosition.CENTER,
                "Center Right": TextPosition.CENTER_RIGHT,
                "Top Left": TextPosition.TOP_LEFT,
                "Top Center": TextPosition.TOP_CENTER,
                "Top Right": TextPosition.TOP_RIGHT,
                "Custom": TextPosition.CUSTOM,
            }
            position = pos_map.get(self.cmbTextPosition.currentText(), TextPosition.BOTTOM_LEFT)

            text_overlay = TextOverlay(
                enabled=True,
                text=self.txtOverlayText.text(),
                position=position,
                font_size=self.spinFontSize.value(),
                font_color=self.cmbFontColor.currentText(),
                padding_x=self.spinTextPadding.value(),
                padding_y=self.spinTextPadding.value(),
                bold=self.chkBold.isChecked(),
                outline_enabled=self.chkOutline.isChecked(),
                background_enabled=self.chkBackground.isChecked(),
            )

        # Build profile
        profile = GifExportProfile(
            preset_name=self.cmbPreset.currentText(),
            target_max_size_mb=self.spinTargetSize.value() if self.chkTargetSize.isChecked() else None,
            width=self._get_resolution_width(),
            fps=self.spinFps.value(),
            colors=int(self.cmbColors.currentText()),
            dither=dither,
            loop_count=loop,
            speed_multiplier=speed,
            reverse=self.chkReverse.isChecked(),
            boomerang=self.chkBoomerang.isChecked(),
            optimize_palette=self.chkOptimizePalette.isChecked(),
            lossy_compression=self.spinLossy.value() if self.spinLossy.value() > 0 else None,
            text_overlay=text_overlay,
        )

        return profile

    def _on_export(self) -> None:
        """Export GIF"""
        # Determine export mode
        if self.radioFullVideo.isChecked():
            mode = ExportMode.FULL_VIDEO
        elif self.radioSegment.isChecked():
            mode = ExportMode.SINGLE_SEGMENT
        elif self.radioMerged.isChecked():
            mode = ExportMode.MERGED_SEGMENTS
        else:
            mode = ExportMode.BATCH

        # Get segments
        segments = self.segmentModel.all_segments_in_global_order()

        # For full video mode, create a segment covering entire video
        if mode == ExportMode.FULL_VIDEO:
            if self.fileModel.rowCount() == 0:
                return
            file = self.fileModel.file_at(0)
            if not file or not file.info:
                QtWidgets.QMessageBox.warning(self, "Not ready", "File info not ready yet.")
                return
            segments = [Segment.new(file.id, 0.0, file.info.duration, 1)]

        if not segments:
            QtWidgets.QMessageBox.information(self, "No segments", "No segments to export.")
            return

        # Choose destination
        default_name = QtCore.QDateTime.currentDateTime().toString("yyyyMMdd_hhmmss")
        out_name = f"gif_{default_name}.gif"
        dest, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, "Export GIF To", out_name, "GIF (*.gif)"
        )

        if not dest:
            return

        # Build profile
        profile = self._build_export_profile()

        # Build file lookup
        lookup = {f.id: f.path for f in self.fileModel.files()}

        # Create export task
        task = GifExportTask(
            ffmpeg=self._ff_bins["ffmpeg"],
            segments=segments,
            file_lookup=lookup,
            profile=profile,
            output_path=dest,
            mode=mode,
        )

        # Start export
        self._exporter = GifExporter(task)
        self._exporter.progressChanged.connect(self._on_export_progress)
        self._exporter.logLine.connect(self._append_log)
        self._exporter.finished.connect(self._on_export_finished)

        self.progress.setValue(0)
        self.lblStage.setText("Starting...")
        self.btnCancel.setEnabled(True)
        self.btnExport.setEnabled(False)
        self._log_dock.show()

        self._thread_pool.start(self._exporter)

    def _on_export_progress(self, value: int, stage: str) -> None:
        """Update export progress"""
        self.progress.setValue(value)
        self.lblStage.setText(stage)

    def _on_export_finished(self, ok: bool, message: str, size_mb: float) -> None:
        """Handle export completion"""
        self.btnCancel.setEnabled(False)
        self.btnExport.setEnabled(True)
        self.lblStage.setText("Done" if ok else "Failed")

        if ok:
            size_str = format_size_mb(size_mb)
            QtWidgets.QMessageBox.information(
                self, "Export complete",
                f"GIF saved to:\n{message}\n\nFile size: {size_str}"
            )
        else:
            QtWidgets.QMessageBox.warning(self, "Export failed", message)

    def _on_cancel_export(self) -> None:
        """Cancel export"""
        exp = getattr(self, "_exporter", None)
        if exp:
            exp.cancel()

    def _append_log(self, line: str) -> None:
        """Append log line"""
        if hasattr(self, "_log_edit"):
            self._log_edit.appendPlainText(line)

    def _on_preview(self) -> None:
        """Preview GIF (simplified - just show message for now)"""
        QtWidgets.QMessageBox.information(
            self, "Preview",
            "Preview functionality will create a short sample GIF.\nThis feature is coming soon!"
        )

    # --- Theme ---
    def _toggle_theme(self) -> None:
        """Toggle light/dark theme"""
        settings = QtCore.QSettings()
        theme = settings.value("theme", "light")
        new_theme = "dark" if theme == "light" else "light"
        settings.setValue("theme", new_theme)
        self._apply_theme(new_theme)

    def _restore_theme(self) -> None:
        """Restore saved theme"""
        self._apply_theme(QtCore.QSettings().value("theme", "light"))

    def _apply_theme(self, theme: str) -> None:
        """Apply theme"""
        if theme == "dark":
            self._set_dark_palette()
        else:
            self._set_light_palette()

    def _set_dark_palette(self) -> None:
        """Set dark theme palette"""
        palette = QtGui.QPalette()
        palette.setColor(QtGui.QPalette.Window, QtGui.QColor(37, 37, 38))
        palette.setColor(QtGui.QPalette.WindowText, QtCore.Qt.white)
        palette.setColor(QtGui.QPalette.Base, QtGui.QColor(30, 30, 30))
        palette.setColor(QtGui.QPalette.AlternateBase, QtGui.QColor(45, 45, 48))
        palette.setColor(QtGui.QPalette.ToolTipBase, QtCore.Qt.white)
        palette.setColor(QtGui.QPalette.ToolTipText, QtCore.Qt.white)
        palette.setColor(QtGui.QPalette.Text, QtCore.Qt.white)
        palette.setColor(QtGui.QPalette.Button, QtGui.QColor(45, 45, 48))
        palette.setColor(QtGui.QPalette.ButtonText, QtCore.Qt.white)
        palette.setColor(QtGui.QPalette.BrightText, QtCore.Qt.red)
        palette.setColor(QtGui.QPalette.Highlight, QtGui.QColor(38, 79, 120))
        palette.setColor(QtGui.QPalette.HighlightedText, QtCore.Qt.white)
        self.setPalette(palette)

    def _set_light_palette(self) -> None:
        """Set light theme palette"""
        self.setPalette(self.style().standardPalette())
