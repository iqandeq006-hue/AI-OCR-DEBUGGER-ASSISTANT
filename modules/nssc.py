import sys
import os
import time

from PyQt6.QtWidgets import QApplication, QWidget
from PyQt6.QtGui import QPainter, QPen, QColor, QGuiApplication
from PyQt6.QtCore import Qt, QRect, QPoint

from config import save_region

TEMP_DIR = "temp"


class ScreenCapture(QWidget):

    def __init__(self, save_mode=False):
        super().__init__()

        self.start = QPoint()
        self.end = QPoint()

        self.dragging = False
        self.has_selection = False
        self.save_mode = save_mode

        self.setWindowOpacity(0.25)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )

        self.setWindowState(Qt.WindowState.WindowFullScreen)
        self.setCursor(Qt.CursorShape.CrossCursor)

        self.show()

    def paintEvent(self, event):
        if self.has_selection or self.dragging:
            painter = QPainter(self)
            pen = QPen(QColor(0, 255, 150))
            pen.setWidth(3)
            painter.setPen(pen)

            rect = QRect(self.start, self.end)
            painter.drawRect(rect)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.dragging = True

            if not self.has_selection:
                self.start = event.pos()

            self.end = event.pos()
            self.update()

        elif event.button() == Qt.MouseButton.RightButton:
            if self.has_selection:
                self.capture_screen()

    def mouseMoveEvent(self, event):
        if self.dragging:
            self.end = event.pos()
            self.update()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.end = event.pos()
            self.dragging = False
            self.has_selection = True
            self.update()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            print("Capture cancelled.")
            self.close()
            QApplication.quit()

    def capture_screen(self):
        x1 = min(self.start.x(), self.end.x())
        y1 = min(self.start.y(), self.end.y())
        x2 = max(self.start.x(), self.end.x())
        y2 = max(self.start.y(), self.end.y())

        if x2 - x1 == 0 or y2 - y1 == 0:
            print("Invalid selection. Capture aborted.")
            return

        if self.save_mode:
            save_region(x1, y1, x2, y2)
            print("Region saved for future use.")
            self.close()
            QApplication.quit()
            return

        self.close()
        QApplication.processEvents()

        # ✅ FIX: ensure overlay disappears before capture
        time.sleep(0.05)

        if not os.path.exists(TEMP_DIR):
            os.makedirs(TEMP_DIR)

        timestamp = int(time.time())
        output = os.path.join(TEMP_DIR, f"capture_{timestamp}.png")

        screen = QGuiApplication.primaryScreen()
        if screen is None:
            print("No screen found.")
            return

        screenshot = screen.grabWindow(
            0, x1, y1, x2 - x1, y2 - y1
        )

        screenshot.save(output)

        print("Screenshot saved:", output)

        QApplication.quit()


# ✅ SAFE START FUNCTIONS
def start_capture():
    try:
        app = QApplication.instance()
        if not app:
            app = QApplication(sys.argv)

        window = ScreenCapture(save_mode=False)
        app.exec()
    except Exception as e:
        print("UI crash (capture):", e)


def start_region_selection():
    try:
        app = QApplication.instance()
        if not app:
            app = QApplication(sys.argv)

        window = ScreenCapture(save_mode=True)
        app.exec()
    except Exception as e:
        print("UI crash (region):", e)


def capture_from_region(region):
    try:
        app = QApplication.instance()
        if not app:
            app = QApplication(sys.argv)

        x1, y1, x2, y2 = region

        if not os.path.exists(TEMP_DIR):
            os.makedirs(TEMP_DIR)

        timestamp = int(time.time())
        output = os.path.join(TEMP_DIR, f"capture_{timestamp}.png")

        screen = QGuiApplication.primaryScreen()
        screenshot = screen.grabWindow(
            0, x1, y1, x2 - x1, y2 - y1
        )

        screenshot.save(output)

        print("Captured using saved region:", output)

        QApplication.quit()
    except Exception as e:
        print("Region capture crash:", e)