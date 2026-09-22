# -*- coding: utf-8 -*-
"""
Nautilus Technology - Dağıtım ve Sürüm Yöneticisi (Release Manager)
Telif Hakkı (C) 2026 Nautilus Technology
"""

import sys
import os
import subprocess
import shutil
import time

from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtCore import QThread, pyqtSignal, Qt
from PyQt5.QtGui import QTextCursor, QIcon, QFont
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout,
    QHBoxLayout, QPushButton, QTextEdit, QLabel, QGroupBox, QMessageBox
)

# ---------------------------------------------------------------------
# DİZİN YAPILANDIRMASI
# ---------------------------------------------------------------------
DESKTOP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if not os.path.exists(os.path.join(DESKTOP_DIR, "OPC")):
    # Fallback to standard Desktop
    DESKTOP_DIR = os.path.join(os.path.expanduser("~"), "Desktop")

OPC_DIR    = os.path.join(DESKTOP_DIR, "OPC")
SERVER_DIR = os.path.join(DESKTOP_DIR, "opc-lisans-sunucu")
ISCC_PATH  = r"C:\Program Files (x86)\Inno Setup 6\ISCC.exe"

DARK_STYLESHEET = """
QWidget {
    background-color: #0f1117;
    color: #e0e0e0;
    font-family: "Segoe UI", system-ui, sans-serif;
    font-size: 13px;
}
QGroupBox {
    background-color: #161926;
    border: 1px solid #2a2d3e;
    border-radius: 8px;
    margin-top: 14px;
    font-weight: bold;
    color: #5b8cff;
    padding-top: 14px;
}
QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 0 8px;
    left: 12px;
}
QPushButton {
    background-color: #1e2235;
    color: #ffffff;
    border: 1px solid #333852;
    border-radius: 6px;
    padding: 10px 16px;
    font-weight: bold;
    font-size: 13px;
}
QPushButton:hover {
    background-color: #2a304a;
    border-color: #5b8cff;
}
QPushButton:pressed {
    background-color: #161926;
}
QPushButton:disabled {
    background-color: #151722;
    color: #555a72;
    border-color: #202336;
}
QTextEdit {
    background-color: #08090f;
    color: #4ade80;
    font-family: "Consolas", "Courier New", monospace;
    font-size: 12px;
    border: 1px solid #232738;
    border-radius: 8px;
    padding: 8px;
}
QScrollBar:vertical {
    border: none;
    background: #0f1117;
    width: 10px;
    margin: 0;
}
QScrollBar::handle:vertical {
    background: #2a2d3e;
    min-height: 20px;
    border-radius: 5px;
}
QScrollBar::handle:vertical:hover {
    background: #5b8cff;
}
"""


# ---------------------------------------------------------------------
# ARKA PLAN İŞÇİ THREAD'İ (UI Donmasını Önler)
# ---------------------------------------------------------------------
class TaskWorker(QThread):
    log_signal      = pyqtSignal(str)
    finished_signal = pyqtSignal(bool, str)

    def __init__(self, gorev_tipi: str):
        super().__init__()
        self.gorev_tipi = gorev_tipi

    def _log(self, text: str):
        self.log_signal.emit(text)

    def _run_cmd(self, cmd, cwd):
        """Komutu çalıştırır, çıktıyı anlık olarak loglar."""
        self._log(f"\n[KOMUT] {cmd}")
        self._log(f"[DİZİN] {cwd}")
        
        proc = subprocess.Popen(
            cmd,
            shell=True,
            cwd=cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            encoding="utf-8",
            errors="replace"
        )

        for line in proc.stdout:
            clean = line.rstrip()
            if clean:
                self._log(clean)

        proc.wait()
        return proc.returncode

    def run(self):
        try:
            if self.gorev_tipi == "setup_olustur":
                self._islem_setup_olustur()
            elif self.gorev_tipi == "push_sunucu":
                self._islem_push_sunucu()
            elif self.gorev_tipi == "push_opc":
                self._islem_push_opc()
        except Exception as e:
            self._log(f"\n❌ [BEKLENMEYEN HATA] {str(e)}")
            self.finished_signal.emit(False, str(e))

    # --- 1. GÖREV: SETUP OLUŞTUR VE SUNUCUYA TAŞI ---
    def _islem_setup_olustur(self):
        self._log("=" * 65)
        self._log("🚀 ADIM 1/4: Python Kodları Şifreleniyor & EXE'ler Derleniyor...")
        self._log("=" * 65)

        builder_script = os.path.join(OPC_DIR, "sifreleme", "builder.py")
        if not os.path.exists(builder_script):
            self.finished_signal.emit(False, f"builder.py bulunamadı: {builder_script}")
            return

        ret = self._run_cmd(f'"{sys.executable}" "{builder_script}"', cwd=OPC_DIR)
        if ret != 0:
            self.finished_signal.emit(False, "builder.py derlemesi hata ile sonuçlandı!")
            return

        self._log("\n" + "=" * 65)
        self._log("📦 ADIM 2/4: Normal Lisanslı Setup Derleniyor (Inno Setup)...")
        self._log("=" * 65)

        iss_pro = os.path.join(OPC_DIR, "setup", "kurulum_scripti.iss")
        if not os.path.exists(iss_pro):
            self.finished_signal.emit(False, f"kurulum_scripti.iss bulunamadı: {iss_pro}")
            return

        ret = self._run_cmd(f'"{ISCC_PATH}" "{iss_pro}"', cwd=OPC_DIR)
        if ret != 0:
            self.finished_signal.emit(False, "Lisanslı setup derlenirken hata oluştu!")
            return

        self._log("\n" + "=" * 65)
        self._log("🔓 ADIM 3/4: Unlocked (Lisanssız) Setup Derleniyor (Inno Setup)...")
        self._log("=" * 65)

        iss_unlocked = os.path.join(OPC_DIR, "setup", "kurulum_scripti_unlocked.iss")
        if not os.path.exists(iss_unlocked):
            self.finished_signal.emit(False, f"kurulum_scripti_unlocked.iss bulunamadı: {iss_unlocked}")
            return

        ret = self._run_cmd(f'"{ISCC_PATH}" "{iss_unlocked}"', cwd=OPC_DIR)
        if ret != 0:
            self.finished_signal.emit(False, "Unlocked setup derlenirken hata oluştu!")
            return

        self._log("\n" + "=" * 65)
        self._log("🚚 ADIM 4/4: Setup Dosyası opc-lisans-sunucu Klasörüne Aktarılıyor...")
        self._log("=" * 65)

        src_setup = os.path.join(OPC_DIR, "setup", "Output", "Nautilus_Gateway_v5_Setup.exe")
        if not os.path.exists(src_setup):
            self.finished_signal.emit(False, f"Kaynak setup bulunamadı: {src_setup}")
            return

        dest_folder = os.path.join(SERVER_DIR, "dosyalar")
        os.makedirs(dest_folder, exist_ok=True)

        # dosyalar/ klasöründeki eski .exe dosyalarını temizle
        for dosya in os.listdir(dest_folder):
            if dosya.lower().endswith(".exe"):
                eski_yol = os.path.join(dest_folder, dosya)
                try:
                    os.remove(eski_yol)
                    self._log(f"[*] Eski dosya temizlendi: {dosya}")
                except Exception as e:
                    self._log(f"[-] Eski dosya silinemedi ({dosya}): {e}")

        # Yeni setup'ı nautilus_setup.exe olarak kopyala
        dest_setup = os.path.join(dest_folder, "nautilus_setup.exe")
        shutil.copy2(src_setup, dest_setup)
        boyut_mb = os.path.getsize(dest_setup) / (1024 * 1024)

        self._log(f"✅ Yeni setup başarıyla yerleştirildi: {dest_setup} ({boyut_mb:.2f} MB)")
        self._log("\n🎉 [TAMAMLANDI] Tüm setup'lar üretildi ve sunucuya hazırlandı!")
        self.finished_signal.emit(True, "Setup paketleri başarıyla oluşturuldu ve sunucuya aktarıldı!")

    # --- 2. GÖREV: LİSANS SUNUCUSUNU PUSHLA ---
    def _islem_push_sunucu(self):
        self._log("=" * 65)
        self._log("🌐 LİSANS SUNUCUSU GITHUB'A PUSHLANIYOR...")
        self._log("=" * 65)

        if not os.path.exists(SERVER_DIR):
            self.finished_signal.emit(False, f"Sunucu klasörü bulunamadı: {SERVER_DIR}")
            return

        self._run_cmd("git add -A", cwd=SERVER_DIR)
        self._run_cmd('git commit -m "Sürüm güncellemesi"', cwd=SERVER_DIR)
        ret = self._run_cmd("git push origin main", cwd=SERVER_DIR)

        if ret == 0:
            self._log("\n✅ [BAŞARILI] opc-lisans-sunucu GitHub'a pushlandı!")
            self.finished_signal.emit(True, "Lisans sunucusu başarıyla GitHub'a pushlandı!")
        else:
            self.finished_signal.emit(False, "Sunucu pushlanırken hata oluştu (yukarıdaki logu inceleyin).")

    # --- 3. GÖREV: OPC PROJESİNİ PUSHLA ---
    def _islem_push_opc(self):
        self._log("=" * 65)
        self._log("🏭 OPC PROJESİ GITHUB'A PUSHLANIYOR...")
        self._log("=" * 65)

        if not os.path.exists(OPC_DIR):
            self.finished_signal.emit(False, f"OPC klasörü bulunamadı: {OPC_DIR}")
            return

        self._run_cmd("git add -A", cwd=OPC_DIR)
        self._run_cmd('git commit -m "Sürüm güncellemesi"', cwd=OPC_DIR)
        ret = self._run_cmd("git push origin main", cwd=OPC_DIR)

        if ret == 0:
            self._log("\n✅ [BAŞARILI] OPC Projesi GitHub'a pushlandı!")
            self.finished_signal.emit(True, "OPC projesi başarıyla GitHub'a pushlandı!")
        else:
            self.finished_signal.emit(False, "OPC pushlanırken hata oluştu (yukarıdaki logu inceleyin).")


# ---------------------------------------------------------------------
# ANA ARAYÜZ (GUI)
# ---------------------------------------------------------------------
class ReleaseManagerApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Nautilus Technology — Dağıtım ve Sürüm Yöneticisi")
        self.resize(920, 680)
        self.setMinimumSize(800, 560)
        self.setStyleSheet(DARK_STYLESHEET)

        # İkon yükle (varsa)
        icon_path = os.path.join(OPC_DIR, "logo", "logo.ico")
        if not os.path.exists(icon_path):
            icon_path = os.path.join(OPC_DIR, "sifreleme", "logo.ico")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))

        self.worker = None
        self._init_ui()

    def _init_ui(self):
        central_widget = QWidget(self)
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(18, 18, 18, 18)
        main_layout.setSpacing(14)

        # Üst Başlık Bilgisi
        header_box = QHBoxLayout()
        lbl_title = QLabel("NAUTILUS OPC SUITE — DAĞITIM VE SÜRÜM KONTROL")
        lbl_title.setStyleSheet("font-size: 16px; font-weight: bold; color: #5b8cff;")
        header_box.addWidget(lbl_title)

        self.lbl_status = QLabel("Durum: Hazır")
        self.lbl_status.setStyleSheet("color: #4ade80; font-weight: bold;")
        self.lbl_status.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        header_box.addWidget(self.lbl_status)
        main_layout.addLayout(header_box)

        # 3 Ana Buton Paneli
        grp_actions = QGroupBox("Hızlı İşlemler")
        btn_layout = QHBoxLayout(grp_actions)
        btn_layout.setSpacing(12)
        btn_layout.setContentsMargins(14, 14, 14, 14)

        # Buton 1: Setup Oluştur
        self.btn_setup = QPushButton("🛠️ 1. Setup Oluştur & Sunucuya Taşı")
        self.btn_setup.setMinimumHeight(48)
        self.btn_setup.setStyleSheet("""
            QPushButton {
                background-color: #1e3a8a; color: white; border: 1px solid #3b82f6; border-radius: 6px;
            }
            QPushButton:hover { background-color: #2563eb; }
            QPushButton:disabled { background-color: #18233c; color: #52607a; border-color: #1f2d48; }
        """)
        self.btn_setup.clicked.connect(lambda: self._start_task("setup_olustur"))
        btn_layout.addWidget(self.btn_setup)

        # Buton 2: Lisans Sunucusunu Pushla
        self.btn_push_server = QPushButton("🌐 2. Lisans Sunucusunu Pushla")
        self.btn_push_server.setMinimumHeight(48)
        self.btn_push_server.setStyleSheet("""
            QPushButton {
                background-color: #431407; color: white; border: 1px solid #ea580c; border-radius: 6px;
            }
            QPushButton:hover { background-color: #c2410c; }
            QPushButton:disabled { background-color: #2b1812; color: #664d45; border-color: #382018; }
        """)
        self.btn_push_server.clicked.connect(lambda: self._start_task("push_sunucu"))
        btn_layout.addWidget(self.btn_push_server)

        # Buton 3: OPC Projesini Pushla
        self.btn_push_opc = QPushButton("🏭 3. OPC Projesini Pushla")
        self.btn_push_opc.setMinimumHeight(48)
        self.btn_push_opc.setStyleSheet("""
            QPushButton {
                background-color: #14532d; color: white; border: 1px solid #16a34a; border-radius: 6px;
            }
            QPushButton:hover { background-color: #15803d; }
            QPushButton:disabled { background-color: #162a1e; color: #4e6b57; border-color: #1e3d29; }
        """)
        self.btn_push_opc.clicked.connect(lambda: self._start_task("push_opc"))
        btn_layout.addWidget(self.btn_push_opc)

        main_layout.addWidget(grp_actions)

        # Konsol / Log Alanı
        grp_log = QGroupBox("Canlı İşlem Konsolu / Terminal Çıktıları")
        log_layout = QVBoxLayout(grp_log)
        log_layout.setContentsMargins(14, 14, 14, 14)

        self.txt_console = QTextEdit()
        self.txt_console.setReadOnly(True)
        log_layout.addWidget(self.txt_console)

        # Konsol Alt Butonu (Temizle)
        bottom_box = QHBoxLayout()
        btn_clear = QPushButton("Konsolu Temizle")
        btn_clear.setMaximumWidth(150)
        btn_clear.clicked.connect(self.txt_console.clear)
        bottom_box.addStretch()
        bottom_box.addWidget(btn_clear)
        log_layout.addLayout(bottom_box)

        main_layout.addWidget(grp_log)

        # Başlangıç Karşılama Logu
        self._append_log("Nautilus Technology Dağıtım Yöneticisi başlatıldı.")
        self._append_log(f"OPC Dizini: {OPC_DIR}")
        self._append_log(f"Sunucu Dizini: {SERVER_DIR}")
        self._append_log("İşlem yapmak için yukarıdaki butonlardan birine tıklayın.\n" + "-" * 70)

    def _append_log(self, text: str):
        self.txt_console.append(text)
        self.txt_console.moveCursor(QTextCursor.End)

    def _set_buttons_enabled(self, enabled: bool):
        self.btn_setup.setEnabled(enabled)
        self.btn_push_server.setEnabled(enabled)
        self.btn_push_opc.setEnabled(enabled)

    def _start_task(self, gorev_tipi: str):
        if self.worker and self.worker.isRunning():
            return

        self._set_buttons_enabled(False)
        self.lbl_status.setText("Durum: İşlem yapılıyor...")
        self.lbl_status.setStyleSheet("color: #f59e0b; font-weight: bold;")

        self.worker = TaskWorker(gorev_tipi)
        self.worker.log_signal.connect(self._append_log)
        self.worker.finished_signal.connect(self._on_task_finished)
        self.worker.start()

    def _on_task_finished(self, success: bool, message: str):
        self._set_buttons_enabled(True)
        if success:
            self.lbl_status.setText("Durum: Tamamlandı")
            self.lbl_status.setStyleSheet("color: #4ade80; font-weight: bold;")
            QMessageBox.information(self, "Başarılı", message)
        else:
            self.lbl_status.setText("Durum: Hata Oluştu")
            self.lbl_status.setStyleSheet("color: #f87171; font-weight: bold;")
            QMessageBox.critical(self, "Hata", message)


# ---------------------------------------------------------------------
# GİRİŞ NOKTASI
# ---------------------------------------------------------------------
def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    win = ReleaseManagerApp()
    win.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
