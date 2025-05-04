import os
import sys
from PyQt6.QtWidgets import QSplashScreen
from PyQt6.QtGui import QPixmap
from PyQt6.QtCore import Qt, QTimer

class SplashScreen(QSplashScreen):
    def __init__(self):
        # Determine the correct path to splash.png for PyInstaller onefile compatibility
        if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
            splash_path = os.path.join(sys._MEIPASS, 'splash.png')
        else:
            # Assume splash.png is in the main directory (same as main.py)
            splash_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'splash.png')
        pixmap = QPixmap(splash_path)
        super().__init__(pixmap)
        self.setWindowFlags(Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.FramelessWindowHint)
        self.setEnabled(False)

    def show_for(self, msecs, on_finish):
        self.show()
        QTimer.singleShot(msecs, lambda: (self.close(), on_finish()))
