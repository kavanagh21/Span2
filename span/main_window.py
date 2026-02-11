"""Main application window for SpAN."""

from __future__ import annotations

import os
from pathlib import Path

from PyQt6.QtCore import Qt, QSettings
from PyQt6.QtGui import QColor, QGuiApplication
from PyQt6.QtWidgets import (
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QGroupBox,
    QLabel,
    QLineEdit,
    QCheckBox,
    QComboBox,
    QPushButton,
    QListWidget,
    QScrollBar,
    QFileDialog,
    QMessageBox,
    QSplitter,
    QFormLayout,
    QSizePolicy,
    QColorDialog,
)

from span.data_parser import parse_flux_file
from span.graph_widget import GraphWidget, DEFAULT_COLORS
from span.inflection import (
    InflectionType,
    detect_inflections,
    get_inflection_points,
)
from span.video_sampler import subsample_video, find_ffmpeg

# Mapping from colour key to user-friendly label
COLOR_LABELS = {
    "background": "Background",
    "grid_lines": "Grid Lines",
    "grid_text": "Grid Text",
    "line_up": "Line Up (rising)",
    "line_down": "Line Down (falling)",
    "marker_down_to_up": "Marker Down\u2192Up",
    "marker_up_to_down": "Marker Up\u2192Down",
    "point_marker": "Point Marker",
}


def _color_swatch_style(color: QColor) -> str:
    """Return a stylesheet that shows the colour as a swatch button."""
    # Choose contrasting text
    luma = 0.299 * color.red() + 0.587 * color.green() + 0.114 * color.blue()
    text = "#000" if luma > 140 else "#fff"
    return (
        f"background-color: {color.name()}; color: {text}; "
        "border: 1px solid #888; padding: 2px 8px; min-width: 60px;"
    )


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("SpAN - Speckle Analysis")
        self.setMinimumSize(900, 600)
        self.resize(1200, 700)

        self.flux: list[float] = []
        self.labels: list[InflectionType] = []
        self.video_path: str = ""

        self.settings = QSettings("DeanKavanagh", "SpAN")

        # Colour swatch buttons keyed by colour name
        self._color_buttons: dict[str, QPushButton] = {}

        self._build_ui()
        self._restore_settings()
        self._connect_signals()

    # -----------------------------------------------------------------
    # UI Construction
    # -----------------------------------------------------------------

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(6, 6, 6, 6)
        main_layout.setSpacing(4)

        # Top panel: settings + colours + data side by side
        top_splitter = QSplitter(Qt.Orientation.Horizontal)
        top_splitter.addWidget(self._build_display_settings_panel())
        top_splitter.addWidget(self._build_colours_panel())
        top_splitter.addWidget(self._build_data_panel())
        top_splitter.setSizes([300, 250, 500])
        top_splitter.setMaximumHeight(320)
        main_layout.addWidget(top_splitter)

        # Graph area
        self.graph = GraphWidget()
        self.graph.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        main_layout.addWidget(self.graph, stretch=1)

        # Bottom bar: scrollbar + range labels
        bottom_layout = QHBoxLayout()
        bottom_layout.setSpacing(4)
        self.lbl_range_start = QLabel("0")
        self.lbl_range_start.setStyleSheet("font-size: 14px; font-weight: bold;")
        self.scrollbar = QScrollBar(Qt.Orientation.Horizontal)
        self.scrollbar.setMinimum(0)
        self.scrollbar.setMaximum(0)
        self.lbl_range_end = QLabel("0")
        self.lbl_range_end.setStyleSheet("font-size: 14px; font-weight: bold;")
        self.lbl_range_end.setAlignment(Qt.AlignmentFlag.AlignRight)
        bottom_layout.addWidget(self.lbl_range_start)
        bottom_layout.addWidget(self.scrollbar, stretch=1)
        bottom_layout.addWidget(self.lbl_range_end)
        main_layout.addLayout(bottom_layout)

    def _build_display_settings_panel(self) -> QGroupBox:
        group = QGroupBox("Display Settings")
        layout = QFormLayout()
        layout.setSpacing(4)

        self.txt_low = QLineEdit("0")
        self.txt_low.setMaximumWidth(80)
        layout.addRow("Y Low:", self.txt_low)

        self.txt_high = QLineEdit("5000")
        self.txt_high.setMaximumWidth(80)
        layout.addRow("Y High:", self.txt_high)

        self.txt_xstep = QLineEdit("5")
        self.txt_xstep.setMaximumWidth(80)
        layout.addRow("X Step:", self.txt_xstep)

        self.txt_grid_y = QLineEdit("100")
        self.txt_grid_y.setMaximumWidth(80)
        layout.addRow("Grid Y:", self.txt_grid_y)

        self.txt_grid_x = QLineEdit("25")
        self.txt_grid_x.setMaximumWidth(80)
        layout.addRow("Grid X:", self.txt_grid_x)

        self.cmb_font_size = QComboBox()
        self.cmb_font_size.addItems(["10", "12", "14", "16", "18"])
        self.cmb_font_size.setMaximumWidth(80)
        layout.addRow("Grid Font:", self.cmb_font_size)

        self.chk_x_grid = QCheckBox("Show X grid")
        self.chk_x_grid.setChecked(True)
        layout.addRow(self.chk_x_grid)

        self.chk_y_grid = QCheckBox("Show Y grid")
        self.chk_y_grid.setChecked(True)
        layout.addRow(self.chk_y_grid)

        self.chk_highlight = QCheckBox("Highlight inversions")
        self.chk_highlight.setChecked(True)
        layout.addRow(self.chk_highlight)

        self.chk_slice_num = QCheckBox("Draw slice number")
        layout.addRow(self.chk_slice_num)

        self.chk_point_marker = QCheckBox("Draw point marker")
        layout.addRow(self.chk_point_marker)

        self.btn_update = QPushButton("Update")
        layout.addRow(self.btn_update)

        group.setLayout(layout)
        return group

    def _build_colours_panel(self) -> QGroupBox:
        group = QGroupBox("Colours")
        layout = QFormLayout()
        layout.setSpacing(4)

        for key, label in COLOR_LABELS.items():
            btn = QPushButton(DEFAULT_COLORS[key].name())
            btn.setStyleSheet(_color_swatch_style(DEFAULT_COLORS[key]))
            btn.clicked.connect(lambda checked, k=key: self._pick_color(k))
            self._color_buttons[key] = btn
            layout.addRow(f"{label}:", btn)

        self.btn_reset_colours = QPushButton("Reset to Defaults")
        layout.addRow(self.btn_reset_colours)

        group.setLayout(layout)
        return group

    def _build_data_panel(self) -> QGroupBox:
        group = QGroupBox("Data")
        layout = QVBoxLayout()
        layout.setSpacing(4)

        # Data file row
        file_row = QHBoxLayout()
        file_row.addWidget(QLabel("Data file:"))
        self.txt_data_file = QLineEdit("Not set")
        self.txt_data_file.setReadOnly(True)
        file_row.addWidget(self.txt_data_file, stretch=1)
        self.btn_find_data = QPushButton("Find...")
        file_row.addWidget(self.btn_find_data)
        layout.addLayout(file_row)

        # Video file row
        vid_row = QHBoxLayout()
        vid_row.addWidget(QLabel("Video file:"))
        self.txt_video_file = QLineEdit("Not set")
        self.txt_video_file.setReadOnly(True)
        vid_row.addWidget(self.txt_video_file, stretch=1)
        self.btn_find_video = QPushButton("Find...")
        vid_row.addWidget(self.btn_find_video)
        layout.addLayout(vid_row)

        # Stats row
        stats_row = QHBoxLayout()
        self.lbl_dp_count = QLabel("Data points in memory: 0")
        stats_row.addWidget(self.lbl_dp_count)
        stats_row.addStretch()
        self.lbl_inflection_count = QLabel("Points: 0")
        stats_row.addWidget(self.lbl_inflection_count)
        stats_row.addSpacing(12)
        self.lbl_avg_flux = QLabel("Average flux: 0")
        stats_row.addWidget(self.lbl_avg_flux)
        layout.addLayout(stats_row)

        # Filter row
        filter_row = QHBoxLayout()
        filter_row.addWidget(QLabel("Show:"))
        self.cmb_show = QComboBox()
        self.cmb_show.addItems(["Down points", "Up points"])
        filter_row.addWidget(self.cmb_show)
        self.chk_filter_down_up = QCheckBox("Hide down->up")
        filter_row.addWidget(self.chk_filter_down_up)
        self.chk_filter_up_down = QCheckBox("Hide up->down")
        filter_row.addWidget(self.chk_filter_up_down)
        filter_row.addStretch()
        layout.addLayout(filter_row)

        # Inflection list
        self.list_inflections = QListWidget()
        layout.addWidget(self.list_inflections, stretch=1)

        # Action buttons
        btn_row = QHBoxLayout()
        self.btn_copy_data = QPushButton("Copy Data")
        btn_row.addWidget(self.btn_copy_data)
        self.btn_copy_graph = QPushButton("Copy Graph")
        btn_row.addWidget(self.btn_copy_graph)
        self.btn_save_graph = QPushButton("Save Graph...")
        btn_row.addWidget(self.btn_save_graph)
        self.btn_subsample = QPushButton("Subsample Video")
        btn_row.addWidget(self.btn_subsample)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        group.setLayout(layout)
        return group

    # -----------------------------------------------------------------
    # Signal Connections
    # -----------------------------------------------------------------

    def _connect_signals(self):
        self.btn_find_data.clicked.connect(self._on_find_data)
        self.btn_find_video.clicked.connect(self._on_find_video)
        self.btn_update.clicked.connect(self._update_graph)
        self.btn_copy_data.clicked.connect(self._copy_data_to_clipboard)
        self.btn_copy_graph.clicked.connect(self._copy_graph_to_clipboard)
        self.btn_save_graph.clicked.connect(self._save_graph_to_file)
        self.btn_subsample.clicked.connect(self._on_subsample_video)
        self.btn_reset_colours.clicked.connect(self._reset_colours)
        self.scrollbar.valueChanged.connect(self._on_scroll)
        self.cmb_show.currentIndexChanged.connect(self._update_inflection_list)

        # Checkboxes that affect graph display
        for chk in (
            self.chk_x_grid,
            self.chk_y_grid,
            self.chk_highlight,
            self.chk_slice_num,
            self.chk_point_marker,
            self.chk_filter_down_up,
            self.chk_filter_up_down,
        ):
            chk.stateChanged.connect(self._update_graph)

    # -----------------------------------------------------------------
    # Colour Picker
    # -----------------------------------------------------------------

    def _pick_color(self, key: str):
        current = self.graph.colors[key]
        color = QColorDialog.getColor(current, self, f"Choose {COLOR_LABELS[key]}")
        if color.isValid():
            self.graph.colors[key] = color
            self._color_buttons[key].setText(color.name())
            self._color_buttons[key].setStyleSheet(_color_swatch_style(color))
            if key == "background":
                self.graph._apply_bg_style()
            self._save_settings()
            self.graph.update()

    def _reset_colours(self):
        for key, default in DEFAULT_COLORS.items():
            self.graph.colors[key] = QColor(default)
            self._color_buttons[key].setText(default.name())
            self._color_buttons[key].setStyleSheet(_color_swatch_style(default))
        self.graph._apply_bg_style()
        self._save_settings()
        self.graph.update()

    # -----------------------------------------------------------------
    # Settings Persistence
    # -----------------------------------------------------------------

    def _restore_settings(self):
        # Text fields
        self.txt_low.setText(self.settings.value("y_low", "0"))
        self.txt_high.setText(self.settings.value("y_high", "5000"))
        self.txt_xstep.setText(self.settings.value("x_step", "5"))
        self.txt_grid_y.setText(self.settings.value("grid_y", "100"))
        self.txt_grid_x.setText(self.settings.value("grid_x", "25"))

        # Combo boxes
        font_idx = self.cmb_font_size.findText(
            self.settings.value("grid_font_size", "10")
        )
        if font_idx >= 0:
            self.cmb_font_size.setCurrentIndex(font_idx)

        # Checkboxes (stored as "true"/"false" strings for cross-platform compat)
        self.chk_x_grid.setChecked(
            self.settings.value("show_x_grid", "true") == "true"
        )
        self.chk_y_grid.setChecked(
            self.settings.value("show_y_grid", "true") == "true"
        )
        self.chk_highlight.setChecked(
            self.settings.value("highlight_inversions", "true") == "true"
        )
        self.chk_slice_num.setChecked(
            self.settings.value("draw_slice_number", "false") == "true"
        )
        self.chk_point_marker.setChecked(
            self.settings.value("draw_point_marker", "false") == "true"
        )
        self.chk_filter_down_up.setChecked(
            self.settings.value("hide_down_to_up", "false") == "true"
        )
        self.chk_filter_up_down.setChecked(
            self.settings.value("hide_up_to_down", "false") == "true"
        )

        # Colours
        for key, default in DEFAULT_COLORS.items():
            saved = self.settings.value(f"color_{key}", default.name())
            color = QColor(saved)
            if color.isValid():
                self.graph.colors[key] = color
                self._color_buttons[key].setText(color.name())
                self._color_buttons[key].setStyleSheet(_color_swatch_style(color))
        self.graph._apply_bg_style()

    def _save_settings(self):
        # Text fields
        self.settings.setValue("y_low", self.txt_low.text())
        self.settings.setValue("y_high", self.txt_high.text())
        self.settings.setValue("x_step", self.txt_xstep.text())
        self.settings.setValue("grid_y", self.txt_grid_y.text())
        self.settings.setValue("grid_x", self.txt_grid_x.text())

        # Combo boxes
        self.settings.setValue("grid_font_size", self.cmb_font_size.currentText())

        # Checkboxes
        self.settings.setValue(
            "show_x_grid", "true" if self.chk_x_grid.isChecked() else "false"
        )
        self.settings.setValue(
            "show_y_grid", "true" if self.chk_y_grid.isChecked() else "false"
        )
        self.settings.setValue(
            "highlight_inversions",
            "true" if self.chk_highlight.isChecked() else "false",
        )
        self.settings.setValue(
            "draw_slice_number",
            "true" if self.chk_slice_num.isChecked() else "false",
        )
        self.settings.setValue(
            "draw_point_marker",
            "true" if self.chk_point_marker.isChecked() else "false",
        )
        self.settings.setValue(
            "hide_down_to_up",
            "true" if self.chk_filter_down_up.isChecked() else "false",
        )
        self.settings.setValue(
            "hide_up_to_down",
            "true" if self.chk_filter_up_down.isChecked() else "false",
        )

        # Colours
        for key, color in self.graph.colors.items():
            self.settings.setValue(f"color_{key}", color.name())

    # -----------------------------------------------------------------
    # Data Loading
    # -----------------------------------------------------------------

    def _on_find_data(self):
        filepath, _ = QFileDialog.getOpenFileName(
            self,
            "Open moorFLPI Data File",
            "",
            "Text Files (*.txt *.csv);;All Files (*)",
        )
        if not filepath:
            return

        try:
            self.flux = parse_flux_file(filepath)
        except (FileNotFoundError, ValueError) as e:
            QMessageBox.warning(self, "Error Loading Data", str(e))
            return

        self.txt_data_file.setText(filepath)
        self.labels = detect_inflections(self.flux).labels
        self.lbl_dp_count.setText(f"Data points in memory: {len(self.flux)}")

        self._update_graph()
        self.cmb_show.setCurrentIndex(1)  # "Up points"
        self._update_inflection_list()

    def _on_find_video(self):
        filepath, _ = QFileDialog.getOpenFileName(
            self,
            "Open Video File",
            "",
            "Video Files (*.mp4 *.avi *.mkv *.mov);;All Files (*)",
        )
        if filepath:
            self.video_path = filepath
            self.txt_video_file.setText(filepath)

    # -----------------------------------------------------------------
    # Graph Rendering
    # -----------------------------------------------------------------

    def _apply_settings_to_graph(self):
        try:
            self.graph.y_low = float(self.txt_low.text())
        except ValueError:
            pass
        try:
            self.graph.y_high = float(self.txt_high.text())
        except ValueError:
            pass
        try:
            self.graph.x_step = max(1, int(self.txt_xstep.text()))
        except ValueError:
            pass
        try:
            self.graph.grid_y = max(1, int(self.txt_grid_y.text()))
        except ValueError:
            pass
        try:
            self.graph.grid_x = max(1, int(self.txt_grid_x.text()))
        except ValueError:
            pass
        try:
            self.graph.grid_font_size = int(self.cmb_font_size.currentText())
        except ValueError:
            pass

        self.graph.show_x_grid = self.chk_x_grid.isChecked()
        self.graph.show_y_grid = self.chk_y_grid.isChecked()
        self.graph.highlight_inversions = self.chk_highlight.isChecked()
        self.graph.draw_slice_number = self.chk_slice_num.isChecked()
        self.graph.draw_point_marker = self.chk_point_marker.isChecked()
        self.graph.show_down_to_up = not self.chk_filter_down_up.isChecked()
        self.graph.show_up_to_down = not self.chk_filter_up_down.isChecked()

    def _update_graph(self):
        self._apply_settings_to_graph()
        self._save_settings()

        self.graph.set_data(self.flux, self.labels)

        # Configure scrollbar
        max_scroll = self.graph.max_scroll()
        self.scrollbar.setMaximum(max_scroll)
        if max_scroll > 0:
            self.scrollbar.setSingleStep(max(1, max_scroll // 500))
            self.scrollbar.setPageStep(max(1, max_scroll // 10))
        self.scrollbar.setEnabled(max_scroll > 0)

        self._update_range_labels()

    def _on_scroll(self, value: int):
        self.graph.scroll_offset = value
        self.graph.update()
        self._update_range_labels()

    def _update_range_labels(self):
        if not self.flux:
            self.lbl_range_start.setText("0")
            self.lbl_range_end.setText("0")
            return
        start = self.graph.visible_start + 1  # 1-based display
        end = min(self.graph.visible_end + 1, len(self.flux))
        self.lbl_range_start.setText(str(start))
        self.lbl_range_end.setText(str(end))

    # -----------------------------------------------------------------
    # Inflection List
    # -----------------------------------------------------------------

    def _update_inflection_list(self):
        self.list_inflections.clear()

        if not self.flux:
            self.lbl_inflection_count.setText("Points: 0")
            self.lbl_avg_flux.setText("Average flux: 0")
            return

        # Determine filter
        if self.cmb_show.currentIndex() == 0:
            filter_type = InflectionType.UP_TO_DOWN  # "Down points"
        else:
            filter_type = InflectionType.DOWN_TO_UP  # "Up points"

        points = get_inflection_points(self.flux, self.labels, filter_type)

        total_flux = 0.0
        for idx, val, itype in points:
            self.list_inflections.addItem(f"{idx + 1}\t{val:.2f}\t{itype.value}")
            total_flux += val

        count = len(points)
        avg = total_flux / count if count > 0 else 0.0
        self.lbl_inflection_count.setText(f"Points: {count}")
        self.lbl_avg_flux.setText(f"Average flux: {avg:.2f}")

    # -----------------------------------------------------------------
    # Export / Actions
    # -----------------------------------------------------------------

    def _copy_data_to_clipboard(self):
        lines = []
        for i in range(self.list_inflections.count()):
            lines.append(self.list_inflections.item(i).text())
        text = "\n".join(lines)

        clipboard = QGuiApplication.clipboard()
        if clipboard:
            clipboard.setText(text)

    def _copy_graph_to_clipboard(self):
        pixmap = self.graph.to_pixmap()
        clipboard = QGuiApplication.clipboard()
        if clipboard:
            clipboard.setPixmap(pixmap)

    def _save_graph_to_file(self):
        filepath, selected_filter = QFileDialog.getSaveFileName(
            self,
            "Save Graph Image",
            os.path.join(str(Path.home()), "Desktop", "SpAN Graph.png"),
            "PNG Image (*.png);;JPEG Image (*.jpg);;BMP Image (*.bmp);;All Files (*)",
        )
        if not filepath:
            return

        pixmap = self.graph.to_pixmap()
        # Determine format from extension, default to PNG
        ext = os.path.splitext(filepath)[1].lower()
        fmt_map = {".png": "PNG", ".jpg": "JPEG", ".jpeg": "JPEG", ".bmp": "BMP"}
        fmt = fmt_map.get(ext, "PNG")

        if pixmap.save(filepath, fmt):
            self.statusBar().showMessage(f"Graph saved to {filepath}", 4000)
        else:
            QMessageBox.warning(self, "Save Error", f"Failed to save image to:\n{filepath}")

    def _on_subsample_video(self):
        if not self.video_path:
            QMessageBox.warning(
                self, "No Video", "Please select a video file first."
            )
            return

        if self.list_inflections.count() == 0:
            QMessageBox.warning(
                self,
                "No Inflection Points",
                "Load data and generate inflection points first.",
            )
            return

        if find_ffmpeg() is None:
            QMessageBox.warning(
                self,
                "ffmpeg Not Found",
                "ffmpeg is required for video subsampling.\n"
                "Please install ffmpeg and ensure it is on your PATH.",
            )
            return

        # Collect frame indices from list (1-based)
        frame_indices = []
        for i in range(self.list_inflections.count()):
            text = self.list_inflections.item(i).text()
            try:
                idx = int(text.split("\t")[0])
                frame_indices.append(idx)
            except (ValueError, IndexError):
                continue

        if not frame_indices:
            return

        output_path = os.path.join(
            str(Path.home()), "Desktop", "SpAN Video.mp4"
        )

        try:
            self.statusBar().showMessage("Subsampling video...")
            subsample_video(
                self.video_path,
                frame_indices,
                output_path,
                progress_callback=lambda msg: self.statusBar().showMessage(msg),
            )
            QMessageBox.information(
                self,
                "Video Complete",
                f"Subsampled video saved to:\n{output_path}",
            )
        except (FileNotFoundError, RuntimeError, ValueError) as e:
            QMessageBox.warning(self, "Video Error", str(e))
        finally:
            self.statusBar().clearMessage()
