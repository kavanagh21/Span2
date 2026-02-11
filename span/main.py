"""Entry point for the SpAN application."""

import sys

from PyQt6.QtWidgets import QApplication

from span.main_window import MainWindow


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("SpAN")
    app.setOrganizationName("DeanKavanagh")

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
