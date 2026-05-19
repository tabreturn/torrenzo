#!/usr/bin/env python3
"""Torrenzo GUI -- point, click, build."""

import sys

if __name__ == '__main__' and '--cli' in sys.argv:
    from torrenzo.__main__ import main as cli_main
    sys.argv = [a for a in sys.argv if a != '--cli']
    cli_main()
    sys.exit(0)

import re
import webbrowser
from pathlib import Path

from PySide6.QtCore import QProcess, QSettings, Qt, QUrl
from PySide6.QtGui import QColor, QDesktopServices, QFont, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

TORRENZO_DIR = Path(__file__).resolve().parents[1]


def _find_browser() -> str | None:
    """Find Chrome/Chromium/Firefox for preview."""
    import shutil
    if sys.platform == 'win32':
        candidates = [
            r'C:\Program Files\Mozilla Firefox\firefox.exe',
            r'C:\Program Files\Google\Chrome\Application\chrome.exe',
            r'C:\Program Files (x86)\Google\Chrome\Application\chrome.exe',
        ]
        for p in candidates:
            if Path(p).exists():
                return p
    elif sys.platform == 'darwin':
        candidates = [
            '/Applications/Firefox.app/Contents/MacOS/firefox',
            '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
        ]
        for p in candidates:
            if Path(p).exists():
                return p
    else:
        for name in ('firefox', 'google-chrome', 'chromium'):
            found = shutil.which(name)
            if found:
                return found
    return None
ANSI_RE = re.compile(r'\x1b\[[0-9;]*m')


def _strip(text: str) -> str:
    return ANSI_RE.sub('', text)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('Torrenzo')
        self.setMinimumSize(800, 600)
        self._process: QProcess | None = None
        self._build_ok = False
        self._settings = QSettings('torrenzo', 'gui')
        self._setup_ui()
        self._load_history()

    def _setup_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setSpacing(10)

        # --- Subject directory ---
        dir_layout = QHBoxLayout()
        dir_layout.addWidget(QLabel('Subject:'))
        self._dir_combo = QComboBox()
        self._dir_combo.setEditable(True)
        self._dir_combo.setInsertPolicy(QComboBox.NoInsert)
        self._dir_combo.setMinimumWidth(300)
        self._dir_combo.setSizePolicy(
            self._dir_combo.sizePolicy().horizontalPolicy(),
            self._dir_combo.sizePolicy().verticalPolicy(),
        )
        self._dir_combo.lineEdit().setPlaceholderText('Path to subject root (folder with outline.md/.yaml)')
        self._dir_combo.currentTextChanged.connect(self._on_dir_changed)
        dir_layout.addWidget(self._dir_combo, stretch=1)
        browse_btn = QPushButton('Browse…')
        browse_btn.clicked.connect(self._browse_dir)
        dir_layout.addWidget(browse_btn)
        layout.addLayout(dir_layout)

        # --- Build options ---
        opts_group = QGroupBox('Options')
        opts_layout = QHBoxLayout(opts_group)
        self._opt_cc = QCheckBox('--cc')
        self._opt_cc.setToolTip('Export a Common Cartridge (.imscc) package after building')
        self._opt_clean = QCheckBox('--clean')
        self._opt_clean.setToolTip('Wipe the build/ directory first, then rebuild all files')
        self._opt_force = QCheckBox('--force')
        self._opt_force.setToolTip('Rebuild all files even if outputs are up-to-date')
        self._opt_optimize = QCheckBox('--optimize-assets')
        self._opt_optimize.setToolTip('Optimize PNG and SVG assets in the build output')
        opts_layout.addWidget(self._opt_cc)
        opts_layout.addWidget(self._opt_clean)
        opts_layout.addWidget(self._opt_force)
        opts_layout.addWidget(self._opt_optimize)
        opts_layout.addStretch()
        layout.addWidget(opts_group)

        # --- Action buttons ---
        btn_layout = QHBoxLayout()
        self._build_btn = QPushButton('Build')
        self._build_btn.clicked.connect(self._start_build)
        btn_layout.addWidget(self._build_btn)
        self._preview_btn = QPushButton('Preview in Browser')
        self._preview_btn.setEnabled(False)
        self._preview_btn.clicked.connect(self._preview_in_browser)
        btn_layout.addWidget(self._preview_btn)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        # --- Log output ---
        log_label = QLabel('Build log:')
        layout.addWidget(log_label)
        self._log = QPlainTextEdit()
        self._log.setReadOnly(True)
        self._log.setFont(QFont('monospace', 10))
        self._log.setStyleSheet('QPlainTextEdit { background-color: #1e1e1e; color: #d4d4d4; }')
        layout.addWidget(self._log, stretch=1)

        # --- Status bar ---
        self.statusBar().showMessage('Ready')

    # --- slots ---

    def _load_history(self):
        paths = self._settings.value('subject_paths', [])
        if isinstance(paths, str):
            paths = [paths]
        for p in (paths or []):
            if p and Path(p).is_dir():
                self._dir_combo.addItem(p)
        if self._dir_combo.count() > 0:
            self._dir_combo.setCurrentIndex(0)

    def _save_history(self, path: str):
        existing = []
        for i in range(self._dir_combo.count()):
            existing.append(self._dir_combo.itemText(i))
        if path in existing:
            existing.remove(path)
        existing.insert(0, path)
        # keep last 20
        existing = existing[:20]
        self._settings.setValue('subject_paths', existing)
        # rebuild combo
        self._dir_combo.blockSignals(True)
        self._dir_combo.clear()
        self._dir_combo.addItems(existing)
        self._dir_combo.setCurrentIndex(0)
        self._dir_combo.blockSignals(False)

    def _browse_dir(self):
        path = QFileDialog.getExistingDirectory(self, 'Select Subject Directory')
        if path:
            self._dir_combo.setEditText(path)

    def _on_dir_changed(self, text: str):
        self._build_btn.setEnabled(bool(text.strip()) and Path(text.strip()).is_dir())

    def _start_build(self):
        subject = self._dir_combo.currentText().strip()
        if not subject:
            return

        self._log.clear()
        self._build_ok = False
        self._preview_btn.setEnabled(False)
        self._build_btn.setEnabled(False)
        self.statusBar().showMessage('Building…')

        if getattr(sys, 'frozen', False):
            args = [sys.executable, '--cli', subject]
        else:
            args = [sys.executable, '-m', 'torrenzo', subject]
        if self._opt_force.isChecked():
            args.append('--force')
        if self._opt_clean.isChecked():
            args.append('--clean')
        if self._opt_optimize.isChecked():
            args.append('--optimize-assets')
        if self._opt_cc.isChecked():
            args.append('--cc')

        self._process = QProcess()
        self._process.setWorkingDirectory(str(TORRENZO_DIR))
        self._process.readyReadStandardOutput.connect(self._on_stdout)
        self._process.readyReadStandardError.connect(self._on_stderr)
        self._process.finished.connect(self._on_finished)
        self._process.start(args[0], args[1:])

    def _on_stdout(self):
        text = self._process.readAllStandardOutput().data().decode(errors='replace')
        self._log.appendPlainText(_strip(text).rstrip())

    def _on_stderr(self):
        text = self._process.readAllStandardError().data().decode(errors='replace')
        self._log.appendPlainText(_strip(text).rstrip())

    def _on_finished(self, exit_code: int):
        self._build_btn.setEnabled(True)
        if exit_code == 0:
            self._build_ok = True
            self._preview_btn.setEnabled(True)
            self.statusBar().showMessage('Build complete ✓')
            self._save_history(self._dir_combo.currentText().strip())
        else:
            self.statusBar().showMessage(f'Build failed (exit code {exit_code})')

    def _preview_in_browser(self):
        subject = self._dir_combo.currentText().strip()
        build_dir = Path(subject) / 'build'
        if build_dir.is_dir():
            url = build_dir.resolve().as_uri()
            chrome = _find_browser()
            if chrome:
                import subprocess
                subprocess.Popen([chrome, url])
            else:
                webbrowser.open(url)


def _make_app_icon(size: int = 256) -> QIcon:
    """Draw an orange circle with a white T."""
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    painter.setBrush(QColor(0xFF, 0x6A, 0x00))  # orange
    painter.setPen(Qt.NoPen)
    painter.drawEllipse(20, 20, size - 40, size - 40)
    painter.setPen(Qt.white)
    font = QFont('sans-serif', int(size * 0.55), QFont.Bold)
    painter.setFont(font)
    painter.drawText(pixmap.rect(), Qt.AlignCenter, 'T')
    painter.end()
    return QIcon(pixmap)


def main():
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    app.setWindowIcon(_make_app_icon())
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == '__main__':
    main()
