"""Qt models for data binding in the UI"""

from __future__ import annotations

import os
from typing import List, Dict, Optional

from PySide6 import QtCore

from .media import MediaFile, MediaInfo, Segment


class FileListModel(QtCore.QAbstractListModel):
    """Model for the list of loaded media files"""

    FileObjectRole = QtCore.Qt.UserRole + 1

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._files: List[MediaFile] = []

    def rowCount(self, parent=QtCore.QModelIndex()) -> int:
        return len(self._files)

    def data(self, index: QtCore.QModelIndex, role: int = QtCore.Qt.DisplayRole):
        if not index.isValid() or index.row() >= len(self._files):
            return None

        file = self._files[index.row()]

        if role == QtCore.Qt.DisplayRole:
            filename = os.path.basename(file.path)
            if file.info:
                badge = file.info.badge_text()
                return f"{filename}\n{badge}"
            else:
                return f"{filename}\n(Loading...)"

        elif role == self.FileObjectRole:
            return file

        return None

    def add_file(self, media_file: MediaFile) -> int:
        """Add a media file to the model"""
        row = len(self._files)
        self.beginInsertRows(QtCore.QModelIndex(), row, row)
        self._files.append(media_file)
        self.endInsertRows()
        return row

    def update_info(self, file_id: str, info: MediaInfo) -> None:
        """Update media info for a file"""
        for idx, f in enumerate(self._files):
            if f.id == file_id:
                f.info = info
                model_idx = self.index(idx)
                self.dataChanged.emit(model_idx, model_idx, [QtCore.Qt.DisplayRole])
                break

    def file_at(self, row: int) -> Optional[MediaFile]:
        """Get file at row index"""
        if 0 <= row < len(self._files):
            return self._files[row]
        return None

    def files(self) -> List[MediaFile]:
        """Get all files"""
        return self._files.copy()

    def clear(self) -> None:
        """Clear all files"""
        self.beginResetModel()
        self._files.clear()
        self.endResetModel()


class SegmentTableModel(QtCore.QAbstractTableModel):
    """Model for the segment table"""

    COLUMNS = ["#", "Start", "End", "Duration", "Order"]

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._all_segments: Dict[str, List[Segment]] = {}  # file_id -> segments
        self._current_file_id: Optional[str] = None

    def rowCount(self, parent=QtCore.QModelIndex()) -> int:
        if self._current_file_id is None:
            return 0
        return len(self._all_segments.get(self._current_file_id, []))

    def columnCount(self, parent=QtCore.QModelIndex()) -> int:
        return len(self.COLUMNS)

    def headerData(self, section: int, orientation: QtCore.Qt.Orientation, role: int = QtCore.Qt.DisplayRole):
        if role == QtCore.Qt.DisplayRole and orientation == QtCore.Qt.Horizontal:
            return self.COLUMNS[section]
        return None

    def data(self, index: QtCore.QModelIndex, role: int = QtCore.Qt.DisplayRole):
        if not index.isValid():
            return None

        if self._current_file_id is None:
            return None

        segments = self._all_segments.get(self._current_file_id, [])
        if index.row() >= len(segments):
            return None

        seg = segments[index.row()]

        if role == QtCore.Qt.DisplayRole:
            col = index.column()
            if col == 0:  # #
                return index.row() + 1
            elif col == 1:  # Start
                return self._format_time(seg.start)
            elif col == 2:  # End
                return self._format_time(seg.end)
            elif col == 3:  # Duration
                return self._format_time(seg.duration)
            elif col == 4:  # Order
                return seg.order

        return None

    def _format_time(self, seconds: float) -> str:
        """Format seconds as mm:ss.ms"""
        minutes = int(seconds // 60)
        secs = seconds % 60
        return f"{minutes:02d}:{secs:06.3f}"

    def set_current_file(self, file_id: Optional[str]) -> None:
        """Switch to segments for a different file"""
        self.beginResetModel()
        self._current_file_id = file_id
        if file_id and file_id not in self._all_segments:
            self._all_segments[file_id] = []
        self.endResetModel()

    def add_segment(self, file_id: str, segment: Segment) -> None:
        """Add a segment to a file"""
        if file_id not in self._all_segments:
            self._all_segments[file_id] = []

        segments = self._all_segments[file_id]
        if self._current_file_id == file_id:
            row = len(segments)
            self.beginInsertRows(QtCore.QModelIndex(), row, row)
            segments.append(segment)
            self.endInsertRows()
        else:
            segments.append(segment)

    def remove_rows(self, rows: List[int]) -> None:
        """Remove segments by row indices"""
        if self._current_file_id is None:
            return

        segments = self._all_segments.get(self._current_file_id, [])
        if not segments:
            return

        # Remove in reverse order to avoid index shifting
        for row in sorted(rows, reverse=True):
            if 0 <= row < len(segments):
                self.beginRemoveRows(QtCore.QModelIndex(), row, row)
                del segments[row]
                self.endRemoveRows()

    def all_segments_in_global_order(self) -> List[Segment]:
        """Get all segments across all files, sorted by global order"""
        all_segs = []
        for segments in self._all_segments.values():
            all_segs.extend(segments)
        return sorted(all_segs, key=lambda s: s.order)

    def segments_for_file(self, file_id: str) -> List[Segment]:
        """Get segments for a specific file"""
        return self._all_segments.get(file_id, []).copy()

    def has_segments(self) -> bool:
        """Check if any segments exist"""
        return any(len(segs) > 0 for segs in self._all_segments.values())
