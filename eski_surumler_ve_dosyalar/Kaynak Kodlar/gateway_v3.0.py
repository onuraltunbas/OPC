# -*- coding: utf-8 -*-
"""
OPC Gateway
"""

import sys
import os
import subprocess
import threading
import asyncio
import copyreg
import datetime
import urllib.request
import tempfile
import multiprocessing
import ssl

if __name__ == '__main__':
    multiprocessing.freeze_support()

# =====================================================================
# BAĞIMLILIK YOLU - Sadece geliştirme ortamında (EXE'de gerek yok)
# =====================================================================
PYTHON32_SITE = r"C:\Python313_32\Lib\site-packages"
PYTHON32_EXE  = r"C:\Python313_32\python.exe"
PYTHON32_SCRIPTS = r"C:\Python313_32\Scripts"

def site_path_ekle():
    if os.path.exists(PYTHON32_SITE) and PYTHON32_SITE not in sys.path:
        sys.path.insert(0, PYTHON32_SITE)

site_path_ekle()

from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtCore import QThread, pyqtSignal, QObject, Qt
from PyQt5.QtWidgets import QMessageBox


# =====================================================================
# DÜZELTME 3: Thread-safe sinyal köprüsü
# UI güncellemeleri SADECE ana thread'den yapılmalı.
# Bu sınıf, herhangi bir thread'den güvenli log yazmayı sağlar.
# =====================================================================
class LogKoprusu(QObject):
    log_sinyali = pyqtSignal(str)

    def __init__(self, hedef_widget):
        super().__init__()
        self.log_sinyali.connect(self._yaz)
        self.hedef = hedef_widget

    def _yaz(self, metin):
        self.hedef.append(metin)
        self.hedef.moveCursor(QtGui.QTextCursor.End)

    def yaz(self, metin):
        """Herhangi bir thread'den güvenle çağrılabilir."""
        self.log_sinyali.emit(str(metin))


# =====================================================================
# 1. BÖLÜM: ARAYÜZ TASARIMI
# =====================================================================
class Ui_MainWindow(object):
    def setupUi(self, MainWindow):
        MainWindow.setObjectName("MainWindow")
        MainWindow.resize(820, 640)
        MainWindow.setMinimumSize(820, 640)

        self.centralwidget = QtWidgets.QWidget(MainWindow)

        # --- Sol Panel: Sunucu ---
        grp_sunucu = QtWidgets.QGroupBox("OPC DA Sunucu", self.centralwidget)
        grp_sunucu.setGeometry(20, 20, 220, 90)
        lay_sunucu = QtWidgets.QVBoxLayout(grp_sunucu)
        self.btn_sunucu_tara = QtWidgets.QPushButton("🔍 Sunucuları Tara")
        self.cb_sunucu = QtWidgets.QComboBox()
        lay_sunucu.addWidget(self.btn_sunucu_tara)
        lay_sunucu.addWidget(self.cb_sunucu)

        # --- Orta Panel: Etiket ---
        grp_etiket = QtWidgets.QGroupBox("Etiket Seçimi", self.centralwidget)
        grp_etiket.setGeometry(260, 20, 260, 130)
        lay_etiket = QtWidgets.QVBoxLayout(grp_etiket)
        self.btn_etiket_tara = QtWidgets.QPushButton("📋 Etiketleri Tara")
        self.list_etiket = QtWidgets.QListWidget()
        self.list_etiket.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)
        lay_etiket.addWidget(self.btn_etiket_tara)
        lay_etiket.addWidget(self.list_etiket)

        # --- Sağ Panel: Başlat/Durdur ---
        grp_baslat = QtWidgets.QGroupBox("Yayın Ayarları", self.centralwidget)
        grp_baslat.setGeometry(540, 20, 260, 130)
        lay_baslat = QtWidgets.QFormLayout(grp_baslat)
        self.txt_ip = QtWidgets.QLineEdit("0.0.0.0")
        self.txt_port = QtWidgets.QLineEdit("4840")
        self.btn_baslat = QtWidgets.QPushButton("▶ Başlat")
        self.btn_baslat.setStyleSheet("background-color: #2e7d32; color: white; font-weight: bold;")
        self.btn_durdur = QtWidgets.QPushButton("■ Durdur")
        self.btn_durdur.setStyleSheet("background-color: #c62828; color: white; font-weight: bold;")
        self.btn_durdur.setEnabled(False)
        lay_baslat.addRow("Yayın IP:", self.txt_ip)
        lay_baslat.addRow("Port:", self.txt_port)
        lay_baslat.addRow(self.btn_baslat)
        lay_baslat.addRow(self.btn_durdur)

        # --- Alt Panel: Kurulum ---
        grp_kurulum = QtWidgets.QGroupBox("Kurulum", self.centralwidget)
        grp_kurulum.setGeometry(20, 120, 220, 60)
        lay_k = QtWidgets.QHBoxLayout(grp_kurulum)
        self.btn_kurulum_ac = QtWidgets.QPushButton("⚙ Sistem Kurulum Merkezi")
        lay_k.addWidget(self.btn_kurulum_ac)

        # --- Konsol ---
        grp_konsol = QtWidgets.QGroupBox("Canlı Veri / Log Ekranı", self.centralwidget)
        grp_konsol.setGeometry(20, 190, 780, 425)
        lay_konsol = QtWidgets.QVBoxLayout(grp_konsol)
        self.txt_konsol = QtWidgets.QTextEdit()
        self.txt_konsol.setReadOnly(True)
        self.txt_konsol.setStyleSheet(
            "background: #0d0d0d; color: #00ff41; "
            "font-family: Consolas, 'Courier New'; font-size: 12px;"
        )
        lay_konsol.addWidget(self.txt_konsol)

        MainWindow.setCentralWidget(self.centralwidget)
        MainWindow.setWindowTitle("OPC DA → OPC UA Gateway v2.0 (Hızlandırılmış)")


# =====================================================================
# 2. BÖLÜM: KURULUM PENCERESİ
# =====================================================================
class KurulumPenceresi(QtWidgets.QWidget):
    def __init__(self, log_koprusu: LogKoprusu):
        super().__init__(None, Qt.Window)
        self.log = log_koprusu
        self.setWindowTitle("Sistem Kurulum Merkezi")
        self.resize(500, 480)
        self.setAttribute(Qt.WA_DeleteOnClose, False)
        layout = QtWidgets.QVBoxLayout(self)

        # Mimari uyarısı
        self.lbl_mimari = QtWidgets.QLabel()
        self.lbl_mimari.setAlignment(Qt.AlignCenter)
        if sys.maxsize > 2**32:
            self.lbl_mimari.setText("⚠️ UYARI: 64-Bit Python! OPC DA için 32-Bit Python gerekli.")
            self.lbl_mimari.setStyleSheet("color: #e65100; font-weight: bold; padding: 4px;")
        else:
            self.lbl_mimari.setText("✅ 32-Bit Python — OPC DA uyumlu.")
            self.lbl_mimari.setStyleSheet("color: #2e7d32; font-weight: bold; padding: 4px;")
        layout.addWidget(self.lbl_mimari)

        # Adım butonları
        self.adimlar = [
            ("0. Python 3.13 (32-bit) İndir & Kur", self.python_indir_ve_kur, "#1565c0"),
            ("1. Kütüphaneleri Kur (PIP)",           self.kutuphaneleri_kur,  "#4a148c"),
            ("2. Windows DLL'lerini Kaydet",          self.dll_kaydet,         "#1b5e20"),
        ]
        self.durum_lbller = []
        for metin, slot, renk in self.adimlar:
            h = QtWidgets.QHBoxLayout()
            btn = QtWidgets.QPushButton(metin)
            btn.setStyleSheet(f"background-color: {renk}; color: white; font-weight: bold; padding: 6px;")
            btn.clicked.connect(slot)
            lbl = QtWidgets.QLabel("⏺ Bekliyor")
            lbl.setStyleSheet("color: gray; min-width: 120px;")
            lbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.durum_lbller.append(lbl)
            h.addWidget(btn, stretch=3)
            h.addWidget(lbl, stretch=1)
            layout.addLayout(h)

        self.kurulum_log = QtWidgets.QTextEdit()
        self.kurulum_log.setReadOnly(True)
        self.kurulum_log.setStyleSheet("background-color: #1e1e1e; color: #d4d4d4; font-family: Consolas;")
        layout.addWidget(self.kurulum_log)

        # Bu pencereye özel log köprüsü (thread-safe)
        self._kendi_log = LogKoprusu(self.kurulum_log)

    def _log(self, metin):
        self._kendi_log.yaz(metin)

    def _durum_guncelle(self, idx, metin, renk):
        """Ana thread'den çağrılmalı — sinyal ile çözüldü."""
        QtCore.QMetaObject.invokeMethod(
            self.durum_lbller[idx], "setText",
            Qt.QueuedConnection,
            QtCore.Q_ARG(str, metin)
        )
        QtCore.QMetaObject.invokeMethod(
            self.durum_lbller[idx], "setStyleSheet",
            Qt.QueuedConnection,
            QtCore.Q_ARG(str, f"color: {renk}; font-weight: bold;")
        )

    def python_indir_ve_kur(self):
        url = "https://www.python.org/ftp/python/3.13.3/python-3.13.3.exe"
        path = os.path.join(tempfile.gettempdir(), "py313_32_setup.exe")

        def indir():
            self._durum_guncelle(0, "⏳ İndiriliyor...", "orange")
            self._log("📥 Python 3.13.3 (32-bit) indiriliyor...")
            try:
                ctx = ssl.create_default_context()
                ctx.check_hostname = False
                ctx.verify_mode = ssl.CERT_NONE
                with urllib.request.urlopen(url, context=ctx) as r, open(path, 'wb') as f:
                    toplam = int(r.headers.get('Content-Length', 0))
                    indirilen = 0
                    while True:
                        blok = r.read(65536)
                        if not blok:
                            break
                        f.write(blok)
                        indirilen += len(blok)
                        if toplam:
                            yuzde = int(indirilen * 100 / toplam)
                            self._log(f"  ... %{yuzde}")

                self._log("✅ İndirme tamamlandı. Sessiz kurulum başlıyor...")
                self._durum_guncelle(0, "⏳ Kuruluyor...", "orange")

                komut = (
                    f'"{path}" /quiet InstallAllUsers=1 PrependPath=1 '
                    f'Include_test=0 TargetDir="C:\\Python313_32"'
                )
                p = subprocess.Popen(komut, shell=True)
                p.wait()

                if p.returncode == 0:
                    self._durum_guncelle(0, "✅ Tamamlandı", "green")
                    self._log("✅ Python C:\\Python313_32 klasörüne kuruldu.")
                    site_path_ekle()
                else:
                    self._durum_guncelle(0, f"⚠️ Kod: {p.returncode}", "orange")
                    self._log(f"⚠️ Kurulum tamamlandı ama return code: {p.returncode}")

            except Exception as e:
                self._log(f"❌ Hata: {e}")
                self._durum_guncelle(0, "❌ Hata", "red")

        threading.Thread(target=indir, daemon=True).start()

    def _komut_calistir(self, komut, adim_idx):
        def islem():
            self._durum_guncelle(adim_idx, "⏳ Çalışıyor...", "orange")
            self._log(f"▶ Komut: {komut}")
            try:
                p = subprocess.Popen(
                    komut,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    shell=True,
                    encoding='utf-8',
                    errors='replace'
                )
                for satir in p.stdout:
                    satir = satir.strip()
                    if satir:
                        self._log(satir)
                p.wait()
                if p.returncode == 0:
                    self._durum_guncelle(adim_idx, "✅ Tamamlandı", "green")
                    self._log("✅ İşlem başarılı.")
                else:
                    self._durum_guncelle(adim_idx, "⚠️ Kontrol Et", "orange")
                    self._log(f"⚠️ Return code: {p.returncode} — Log'u kontrol edin.")
            except Exception as e:
                self._log(f"❌ Hata: {e}")
                self._durum_guncelle(adim_idx, "❌ Hata", "red")

        threading.Thread(target=islem, daemon=True).start()

    def kutuphaneleri_kur(self):
        if os.path.exists(PYTHON32_EXE):
            pip = f'"{PYTHON32_EXE}" -m pip'
        else:
            pip = "pip"
        komut = (
            f'{pip} install --upgrade pip setuptools wheel && '
            f'{pip} install OpenOPC-Python3x asyncua pywin32 pyro4'
        )
        self._komut_calistir(komut, 1)

    def dll_kaydet(self):
        if os.path.exists(PYTHON32_EXE):
            python_exe = f'"{PYTHON32_EXE}"'
            scripts_postinstall = os.path.join(PYTHON32_SCRIPTS, "pywin32_postinstall.py")
        else:
            python_exe = f'"{sys.executable}"'
            scripts_postinstall = os.path.join(
                os.path.dirname(sys.executable), "Scripts", "pywin32_postinstall.py"
            )

        if os.path.exists(scripts_postinstall):
            komut = f'{python_exe} "{scripts_postinstall}" -install'
        else:
            komut = f'{python_exe} -c "import pywin32_postinstall; pywin32_postinstall.install()"'

        self._komut_calistir(komut, 2)


# =====================================================================
# 3. BÖLÜM: GATEWAY MOTORU (KASMA VE GECİKME FİXİ EKLENDİ)
# =====================================================================
class GatewayWorker(QThread):
    log_sinyali    = pyqtSignal(str)   
    bitti_sinyali  = pyqtSignal()

    def __init__(self, prog_id, ip, port, etiketler):
        super().__init__()
        self.prog_id   = prog_id
        self.ip        = ip
        self.port      = port
        self.etiketler = etiketler
        self._calisıyor = True

    def _log(self, metin):
        self.log_sinyali.emit(str(metin))

    def run(self):
        try:
            site_path_ekle()

            import pythoncom
            import OpenOPC
            import pywintypes

            def _pickle_pytime(dt):
                return (
                    pywintypes.Time,
                    (int(dt),)
                )
            copyreg.pickle(type(pywintypes.Time(0)), _pickle_pytime)

            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            try:
                loop.run_until_complete(self._ua_dongusu(pythoncom, OpenOPC))
            finally:
                loop.close()

        except ImportError as e:
            self._log(f"❌ Eksik kütüphane: {e}")
            self._log("   → Kurulum Merkezi'nden adımları tamamlayın.")
        except Exception as e:
            self._log(f"❌ Motor hatası: {e}")
        finally:
            self.bitti_sinyali.emit()

    async def _ua_dongusu(self, pythoncom, OpenOPC):
        from asyncua import Server, ua

        srv = Server()
        await srv.init()
        endpoint = f"opc.tcp://{self.ip}:{self.port}/"
        srv.set_endpoint(endpoint)
        srv.set_server_name("OPC Gateway v2.0")
        idx = await srv.register_namespace("http://opcgateway/v2")
        kok = await srv.nodes.objects.add_object(idx, "Saha_Verileri")

        async with srv:
            self._log(f"📡 OPC UA Sunucusu yayında: {endpoint}")

            pythoncom.CoInitialize()
            try:
                opc = OpenOPC.client()
                opc.connect(self.prog_id)
                self._log(f"✅ OPC DA bağlandı: {self.prog_id}")
            except Exception as e:
                self._log(f"❌ OPC DA bağlantı hatası: {e}")
                return

            etiket_haritasi = {}
            for et in self.etiketler:
                safe = et.replace(".", "_").replace(" ", "_").replace("\\", "_")
                node = await kok.add_variable(idx, safe, 0.0, ua.VariantType.Double)
                await node.set_writable()
                etiket_haritasi[et] = node
                
            self._log(f"🔗 {len(self.etiketler)} etiket UA'ya eklendi. Döngü başlıyor...\n")

            while self._calisıyor:
                satir_parcalari = []
                yazma_gorevleri = []

                for et in self.etiketler:
                    try:
                        # HIZLANDIRMA FİXİ: Sadece properties(id=2) kullanıyoruz. read() bekleme tuzağı yok!
                        deger = opc.properties(et, id=2)
                        
                        if deger is not None:
                            node = etiket_haritasi[et]
                            try:
                                num = float(deger)
                                yazma_gorevleri.append(node.write_value(num, ua.VariantType.Double))
                                satir_parcalari.append(f"🟢 OK {et}: {num:.4f}")
                            except (ValueError, TypeError):
                                satir_parcalari.append(f"🔵 INFO {et}: {deger} (metin)")
                        else:
                            satir_parcalari.append(f"⚠️ {et}: Veri yok (Boş)")
                    except Exception:
                        pass # Okunamayan sensörü sessizce atla, sistemi dondurma

                if yazma_gorevleri:
                    await asyncio.gather(*yazma_gorevleri)

                self._log("\n".join(satir_parcalari))
                self._log("-" * 60)
                
                # ARAYÜZ KASMA FİXİ: 1 saniye bekleme eklendi (Arayüz artık boğulmayacak)
                await asyncio.sleep(1)

            try:
                opc.close()
            except Exception:
                pass
            self._log("🛑 Gateway durduruldu.")

    def durdur(self):
        self._calisıyor = False


# =====================================================================
# 4. BÖLÜM: ANA UYGULAMA
# =====================================================================
class GatewayApp(QtWidgets.QMainWindow, Ui_MainWindow):
    def __init__(self):
        super().__init__()
        self.setupUi(self)
        self.worker = None

        self._log_koprusu = LogKoprusu(self.txt_konsol)
        self._kurulum = None  # Lazy oluşturulacak

        self.btn_kurulum_ac.clicked.connect(self._kurulum_ac)
        self.btn_sunucu_tara.clicked.connect(self._sunucu_tara)
        self.btn_etiket_tara.clicked.connect(self._etiket_tara)
        self.btn_baslat.clicked.connect(self._baslat)
        self.btn_durdur.clicked.connect(self._durdur)

        self._log("🚀 OPC DA → OPC UA Gateway v2.0 (Hızlandırılmış) hazır.")
        self._log("   Adımlar: Sunucu Tara → Etiket Tara → Seç → Başlat\n")

    def _kurulum_ac(self):
        """Kurulum penceresini göster."""
        try:
            if self._kurulum is None:
                self._kurulum = KurulumPenceresi(self._log_koprusu)
            self._kurulum.show()
            self._kurulum.raise_()
            self._kurulum.activateWindow()
        except Exception as e:
            QMessageBox.critical(self, "Hata", f"Kurulum penceresi açılamadı:\n{e}")

    def _log(self, metin):
        self._log_koprusu.yaz(metin)

    def _sunucu_tara(self):
        try:
            site_path_ekle()
            import OpenOPC
            opc = OpenOPC.client()
            sunucular = opc.servers()
            self.cb_sunucu.clear()
            self.cb_sunucu.addItems(sunucular)
            self._log(f"✅ {len(sunucular)} sunucu bulundu.")
        except ImportError:
            self._log("❌ OpenOPC kurulu değil — Kurulum Merkezi'ni açın.")
        except Exception as e:
            self._log(f"❌ Sunucu tarama hatası: {e}")

    def _etiket_tara(self):
        prog_id = self.cb_sunucu.currentText().strip()
        if not prog_id:
            QMessageBox.warning(self, "Uyarı", "Önce sunucu tarayın ve seçin.")
            return
        try:
            site_path_ekle()
            import OpenOPC
            opc = OpenOPC.client()
            opc.connect(prog_id)
            self.list_etiket.clear()

            etiketler = []
            denemeler = [
                'Simulation Items.*',
                'Configured Aliases.*',
                'Channel1.Device1.*',
                '*',
            ]
            for pattern in denemeler:
                try:
                    bulunan = opc.list(pattern, flat=True)
                    if bulunan:
                        etiketler.extend(bulunan)
                        break
                except Exception:
                    continue

            if not etiketler:
                etiketler = [
                    'Random.Real8', 'Random.Int4',
                    'Bucket Brigade.Real8', 'Random.Money',
                    'Triangle Waves.Real8'
                ]
                self._log("⚠️ Otomatik etiket bulunamadı — demo etiketler gösteriliyor.")

            self.list_etiket.addItems(etiketler)
            opc.close()
            self._log(f"✅ {len(etiketler)} etiket listelendi. Okumak istediklerinizi seçin.")
        except ImportError:
            self._log("❌ OpenOPC kurulu değil — Kurulum Merkezi'ni açın.")
        except Exception as e:
            self._log(f"❌ Etiket tarama hatası: {e}")

    def _baslat(self):
        prog_id = self.cb_sunucu.currentText().strip()
        secili = [item.text() for item in self.list_etiket.selectedItems()]

        if not prog_id:
            QMessageBox.warning(self, "Hata", "Lütfen bir OPC DA sunucusu seçin.")
            return
        if not secili:
            QMessageBox.warning(self, "Hata", "Lütfen en az bir etiket seçin.")
            return

        ip   = self.txt_ip.text().strip() or "0.0.0.0"
        port = self.txt_port.text().strip() or "4840"

        self.txt_konsol.clear()
        self.btn_baslat.setEnabled(False)
        self.btn_durdur.setEnabled(True)

        self.worker = GatewayWorker(prog_id, ip, port, secili)
        self.worker.log_sinyali.connect(self._log)
        self.worker.bitti_sinyali.connect(self._bitti)
        self.worker.start()

    def _durdur(self):
        if self.worker:
            self.worker.durdur()
            self.btn_durdur.setEnabled(False)
            self._log("⏳ Durdurma sinyali gönderildi...")

    def _bitti(self):
        self.btn_baslat.setEnabled(True)
        self.btn_durdur.setEnabled(False)
        self._log("✅ Gateway durdu.")

    def closeEvent(self, event):
        if self.worker and self.worker.isRunning():
            self.worker.durdur()
            self.worker.wait(3000)
        event.accept()


# =====================================================================
if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    app.setStyle("Fusion")
    pencere = GatewayApp()
    pencere.show()
    sys.exit(app.exec_())