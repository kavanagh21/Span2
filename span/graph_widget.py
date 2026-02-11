"""Custom graph widget for rendering flux time-series data."""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPainter, QColor, QPen, QFont, QPixmap
from PyQt6.QtWidgets import QWidget

from span.inflection import InflectionType


# Default colours matching the original VB6 app
DEFAULT_COLORS = {
    "background": QColor(0, 0, 0),
    "grid_lines": QColor(80, 80, 80),
    "grid_text": QColor(200, 200, 200),
    "line_up": QColor(255, 255, 0),         # Yellow - rising
    "line_down": QColor(255, 0, 0),         # Red - falling
    "marker_down_to_up": QColor(0, 100, 255),  # Blue circle
    "marker_up_to_down": QColor(0, 200, 0),    # Green circle
    "point_marker": QColor(255, 255, 255),  # White
}


class GraphWidget(QWidget):
    """Custom widget that draws the flux time-series graph."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.flux: list[float] = []
        self.labels: list[InflectionType] = []

        # Display settings
        self.y_low: float = 0
        self.y_high: float = 5000
        self.x_step: int = 5
        self.grid_x: int = 25
        self.grid_y: int = 100
        self.grid_font_size: int = 10
        self.line_thickness: int = 1

        # Toggles
        self.show_x_grid: bool = True
        self.show_y_grid: bool = True
        self.highlight_inversions: bool = True
        self.draw_slice_number: bool = False
        self.draw_point_marker: bool = False
        self.show_down_to_up: bool = True
        self.show_up_to_down: bool = True

        # Colours (instance copies so each widget can be customised)
        self.colors: dict[str, QColor] = {
            k: QColor(v) for k, v in DEFAULT_COLORS.items()
        }

        # Scroll offset (number of data points to skip)
        self.scroll_offset: int = 0

        # Cached range info set after each paint
        self.visible_start: int = 0
        self.visible_end: int = 0

        self.setMinimumHeight(200)
        self._apply_bg_style()

    def _apply_bg_style(self):
        c = self.colors["background"]
        self.setStyleSheet(f"background-color: {c.name()};")

    def set_data(self, flux: list[float], labels: list[InflectionType]):
        self.flux = flux
        self.labels = labels
        self.scroll_offset = 0
        self.update()

    def points_per_screen(self) -> int:
        if self.x_step <= 0:
            return 1
        return max(1, self.width() // self.x_step)

    def max_scroll(self) -> int:
        return max(0, len(self.flux) - self.points_per_screen())

    def to_pixmap(self) -> QPixmap:
        """Render the current graph to a QPixmap for clipboard/export."""
        pixmap = QPixmap(self.size())
        pixmap.fill(self.colors["background"])
        painter = QPainter(pixmap)
        self._paint(painter)
        painter.end()
        return pixmap

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), self.colors["background"])
        self._paint(painter)
        painter.end()

    def _paint(self, painter: QPainter):
        w = self.width()
        h = self.height()
        if w <= 0 or h <= 0:
            return

        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        y_range = self.y_high - self.y_low
        if y_range <= 0:
            return

        col_grid = self.colors["grid_lines"]
        col_grid_text = self.colors["grid_text"]
        col_up = self.colors["line_up"]
        col_down = self.colors["line_down"]
        col_dtu = self.colors["marker_down_to_up"]
        col_utd = self.colors["marker_up_to_down"]
        col_marker = self.colors["point_marker"]

        def flux_to_y(val: float) -> int:
            """Map a flux value to a pixel Y coordinate."""
            normalized = (val - self.y_low) / y_range
            return int(h - normalized * h)

        # --- Draw Y grid ---
        if self.show_y_grid and self.grid_y > 0:
            font = QFont("Segoe UI", self.grid_font_size)
            painter.setFont(font)

            grid_val = self.y_low - (self.y_low % self.grid_y)
            if grid_val < self.y_low:
                grid_val += self.grid_y

            while grid_val <= self.y_high:
                y = flux_to_y(grid_val)
                if 0 <= y <= h:
                    painter.setPen(QPen(col_grid, 1, Qt.PenStyle.DotLine))
                    painter.drawLine(0, y, w, y)
                    painter.setPen(QPen(col_grid_text))
                    painter.drawText(4, y - 3, f"{grid_val:.0f}")
                grid_val += self.grid_y

        # --- Draw X grid ---
        if self.show_x_grid and self.grid_x > 0 and self.x_step > 0:
            pen = QPen(col_grid, 1, Qt.PenStyle.DotLine)
            painter.setPen(pen)
            pixel_spacing = self.grid_x * self.x_step
            if pixel_spacing > 0:
                x = pixel_spacing
                while x < w:
                    painter.drawLine(x, 0, x, h)
                    x += pixel_spacing

        # --- Draw data ---
        n = len(self.flux)
        if n == 0:
            return

        start = max(0, self.scroll_offset)
        fpr = self.points_per_screen()
        end = min(n, start + fpr + 1)

        self.visible_start = start
        self.visible_end = end - 1

        prev_x = 0
        prev_y = flux_to_y(self.flux[start]) if start < n else 0

        inflection_markers: list[tuple[int, int, InflectionType]] = []

        for i in range(start, end):
            px = (i - start) * self.x_step
            py = flux_to_y(self.flux[i])

            if i > start:
                # Determine line colour
                if self.flux[i] >= self.flux[i - 1]:
                    color = col_up
                else:
                    color = col_down
                painter.setPen(QPen(color, self.line_thickness))
                painter.drawLine(prev_x, prev_y, px, py)

            # Check for inflection markers
            if self.highlight_inversions and i < len(self.labels):
                lbl = self.labels[i]
                if lbl == InflectionType.DOWN_TO_UP and self.show_down_to_up:
                    inflection_markers.append((px, py, lbl))
                elif lbl == InflectionType.UP_TO_DOWN and self.show_up_to_down:
                    inflection_markers.append((px, py, lbl))

            # Point marker
            if self.draw_point_marker:
                painter.setPen(QPen(col_marker, 1))
                painter.drawEllipse(px - 2, py - 2, 4, 4)

            # Slice number
            if self.draw_slice_number and self.x_step >= 10:
                painter.setPen(QPen(col_grid_text))
                font = QFont("Segoe UI", 7)
                painter.setFont(font)
                painter.drawText(px - 5, py - 8, str(i + 1))

            prev_x = px
            prev_y = py

        # Draw inflection circles on top
        for mx, my, mtype in inflection_markers:
            if mtype == InflectionType.DOWN_TO_UP:
                color = col_dtu
            else:
                color = col_utd
            painter.setPen(QPen(color, 2))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawEllipse(mx - 6, my - 6, 12, 12)
