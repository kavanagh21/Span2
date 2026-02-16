"""PyInstaller runtime hook to set Qt plugin paths on macOS."""

import os
import sys


def _setup_qt_paths():
    if getattr(sys, 'frozen', False):
        base = sys._MEIPASS
        plugin_path = os.path.join(base, "PyQt6", "Qt6", "plugins")
        if not os.path.isdir(plugin_path):
            plugin_path = os.path.join(base, "PyQt6", "Qt", "plugins")
        os.environ["QT_PLUGIN_PATH"] = plugin_path
        # Prevent Qt from trying to load plugins from the system
        os.environ["QT_QPA_PLATFORM_PLUGIN_PATH"] = os.path.join(
            plugin_path, "platforms"
        )


_setup_qt_paths()
