# -*- coding: utf-8 -*-
"""
OPC DA -> OPC UA Gateway
Versiyon: 4.1 (Gerçek Zamanlı HWID Korumalı & Arka Plan Ajanlı Sürüm)
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
import json
import time
import hashlib

try:
    import requests
except ImportError:
    pass # Kurulum merkezinden kurulacak

if __name__ == '__main__':
    multiprocessing.freeze_support()

# =====================================================================
# YAPILANDIRMA VE LİSANS AYARLARI
# =====================================================================
SUNUCU_URL       = "https://web-production-b5bbc.up.railway.app" 
UYGULAMA_SIFRESI = "ViyaKilit2026"  # Kendi Railway SECRET_KEY'in ile değiştir
LISANS_DOSYASI   = os.path.join(os.getenv("APPDATA", ""), "OPCGateway", "lisans.json")
CHECKIN_ARALIK   = 7 # Çevrimdışı (İnternetsiz) çalışma izni (Gün)

PYTHON32_SITE = r"C:\Python313_32\Lib\site-packages"
PYTHON32_EXE  = r"C:\Python313_32\python.exe"
PYTHON32_SCRIPTS = r"C:\Python313_32\Scripts"

def site_path_ekle():
    if os.path.exists(PYTHON32_SITE) and PYTHON32_SITE not in sys.path:
        sys.path.insert(0, PYTHON32_SITE)

site_path_ekle()

from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtCore import QThread, pyqtSignal, QObject, Qt
from PyQt5.QtWidgets import QMessageBox, QDialog, QVBoxLayout, QLabel, QLineEdit, QPushButton


# =====================================================================
# 1. BÖLÜM: LİSANS YÖNETİCİSİ VE ARKA PLAN AJANI
# =====================================================================
class LisansYoneticisi:
    def hwid_olustur(self):
        try:
            cikti = subprocess.check_output('wmic csproduct get uuid', shell=True).decode()
            anakart_id = cikti.split('\n')[1].strip()
            hash_obj = hashlib.sha256(anakart_id.encode())
            hash_hex = hash_obj.hexdigest().upper()
            return f"KATOT-{hash_hex[:4]}-{hash_hex[4:8]}-{hash_hex[8:12]}"
        except:
            return "HWID_OKUNAMADI"

    def lisans_kaydet(self, lisans_anahtari, hwid):
        os.makedirs(os.path.dirname(LISANS_DOSYASI), exist_ok=True)
        veri = {
            "hwid": hwid,
            "lisans_anahtari": lisans_anahtari,
            "son_kontrol": datetime.datetime.now().isoformat()
        }
        with open(LISANS_DOSYASI, 'w') as f:
            json.dump(veri, f)

    def lisans_kontrol(self):
        if not os.path.exists(LISANS_DOSYASI):
            return False, "Lisans dosyası bulunamadı."

        try:
            with open(LISANS_DOSYASI, 'r') as f:
                kayit = json.load(f)
            
            kayitli_hwid = kayit.get("hwid")
            lisans_anahtari = kayit.get("lisans_anahtari")
            son_kontrol_str = kayit.get("son_kontrol")
            
            guncel_hwid = self.hwid_olustur()
            if kayitli_hwid != guncel_hwid:
                return False, "Donanım kimliği (HWID) değişmiş! Lisans geçersiz."

            # ZIRH 1: Önce her zaman internete bağlanmayı dene!
            payload = {
                "hwid": guncel_hwid,
                "lisans_anahtari": lisans_anahtari,
                "uygulama_sifresi": UYGULAMA_SIFRESI
            }
            try:
                import requests
                # 3 saniyede cevap gelmezse offline say
                response = requests.post(f"{SUNUCU_URL}/verify", json=payload, timeout=3)
                if response.status_code == 200:
                    veri = response.json()
                    if veri.get("durum") == "aktif":
                        self.lisans_kaydet(lisans_anahtari, guncel_hwid) # Ön belleği tazele
                        return True, "Lisans çevrimiçi doğrulandı."
                    else:
                        # İnternet var ve lisans İPTAL EDİLMİŞ! Sil ve at!
                        os.remove(LISANS_DOSYASI)
                        return False, "Lisansınız iptal edilmiş veya süresi dolmuş."
            except (requests.ConnectionError, requests.Timeout, ImportError):
                # ZIRH 2: İNTERNET YOKSA 7 Günlük Çevrimdışı İzne Bak
                if not son_kontrol_str:
                    return False, "Çevrimdışı veri eksik."
                
                son_k = datetime.datetime.fromisoformat(son_kontrol_str)
                gecen_sure = (datetime.datetime.now() - son_k).days
                
                if gecen_sure <= CHECKIN_ARALIK:
                    return True, f"Çevrimdışı mod. Kalan süre: {CHECKIN_ARALIK - gecen_sure} gün."
                else:
                    return False, "Çevrimdışı kullanım süreniz (7 gün) doldu. Lütfen internete bağlanın."
                    
        except Exception as e:
            return False, f"Lisans hatası: {e}"

# --- GÖLGE AJAN: İnternet geldiği an lisans iptalini yakalayan arka plan sistemi ---
class ArkaplanLisansKontrol(QThread):
    iptal_sinyali = pyqtSignal(str)

    def __init__(self, hwid, lisans_anahtari):
        super().__init__()
        self.hwid = hwid
        self.lisans_anahtari = lisans_anahtari
        self.calisiyor = True

    def run(self):
        time.sleep(10) # Program açılır açılmaz yorma, 10 saniye bekle
        while self.calisiyor:
            try:
                import requests
                payload = {
                    "hwid": self.hwid,
                    "lisans_anahtari": self.lisans_anahtari,
                    "uygulama_sifresi": UYGULAMA_SIFRESI
                }
                # 5 saniye bekleme süresiyle sunucuyu yokla
                res = requests.post(f"{SUNUCU_URL}/verify", json=payload, timeout=5)
                if res.status_code == 200:
                    veri = res.json()
                    if veri.get("durum") != "aktif":
                        # YAKALANDI! LİSANS İPTAL EDİLMİŞ
                        self.iptal_sinyali.emit("Güvenlik Uyarısı: Lisansınız sunucu tarafından iptal edilmiştir!")
                        break
            except:
                pass # İnternet yoksa sessizce kal
            
            # 30 saniyede bir kontrol döngüsü (Hemen kapanabilmesi için 1'er saniyelik adımlar)
            for _ in range(30):
                if not self.calisiyor: break
                time.sleep(1)

    def durdur(self):
        self.calisiyor = False

class AktivasyonPenceresi(QDialog):
    basarili_sinyali = pyqtSignal()

    def __init__(self, yonetici):
        super().__init__()
        self.yonetici = yonetici
        self.setWindowTitle("Viya Endüstriyel - Lisans Aktivasyonu")
        self.setFixedSize(400, 250)
        self.setStyleSheet("background-color: #f4f4f4;")

        layout = QVBoxLayout(self)
        
        lbl_baslik = QLabel("SİSTEM LİSANSLI DEĞİL")
        lbl_baslik.setStyleSheet("color: red; font-size: 16px; font-weight: bold;")
        lbl_baslik.setAlignment(Qt.AlignCenter)
        layout.addWidget(lbl_baslik)

        self.cihaz_hwid = self.yonetici.hwid_olustur()
        lbl_hwid = QLabel(f"Donanım Kimliğiniz (HWID):\n{self.cihaz_hwid}")
        lbl_hwid.setAlignment(Qt.AlignCenter)
        lbl_hwid.setStyleSheet("font-family: Consolas; background: #e0e0e0; padding: 10px; border-radius: 5px;")
        lbl_hwid.setTextInteractionFlags(Qt.TextSelectableByMouse)
        layout.addWidget(lbl_hwid)

        self.txt_lisans = QLineEdit()
        self.txt_lisans.setPlaceholderText("Lisans Kodunuzu Buraya Girin...")
        self.txt_lisans.setStyleSheet("padding: 8px; font-size: 14px;")
        layout.addWidget(self.txt_lisans)

        btn_etkinlestir = QPushButton("Sistemi Etkinleştir")
        btn_etkinlestir.setStyleSheet("background-color: #2e7d32; color: white; padding: 10px; font-weight: bold;")
        btn_etkinlestir.clicked.connect(self.etkinlestir)
        layout.addWidget(btn_etkinlestir)

    def etkinlestir(self):
        lisans_kodu = self.txt_lisans.text().strip()
        if not lisans_kodu:
            QMessageBox.warning(self, "Hata", "Lütfen bir lisans kodu girin.")
            return

        payload = {
            "hwid": self.cihaz_hwid,
            "lisans_anahtari": lisans_kodu,
            "uygulama_sifresi": UYGULAMA_SIFRESI
        }
        
        try:
            import requests
            response = requests.post(f"{SUNUCU_URL}/activate", json=payload, timeout=5)
            if response.status_code == 200:
                veri = response.json()
                if veri.get("basarili"):
                    self.yonetici.lisans_kaydet(lisans_kodu, self.cihaz_hwid)
                    QMessageBox.information(self, "Başarılı", "Lisans doğrulandı! Sistem açılıyor.")
                    self.basarili_sinyali.emit() # Ana ekrana geçiş sinyali
                else:
                    QMessageBox.warning(self, "Hata", veri.get("mesaj", "Lisans doğrulanamadı."))
            else:
                QMessageBox.critical(self, "Hata", "Sunucuya ulaşılamadı. İnternet bağlantınızı kontrol edin.")
        except Exception as e:
            QMessageBox.critical(self, "Hata", f"Bağlantı hatası: {e}")

# =====================================================================
# 2. BÖLÜM: THREAD-SAFE LOG VE KURULUM SİSTEMİ
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
        self.log_sinyali.emit(str(metin))

class Ui_MainWindow(object):
    def setupUi(self, MainWindow):
        MainWindow.setObjectName("MainWindow")
        MainWindow.resize(820, 640)
        self.centralwidget = QtWidgets.QWidget(MainWindow)
        
        grp_sunucu = QtWidgets.QGroupBox("OPC DA Sunucu", self.centralwidget)
        grp_sunucu.setGeometry(20, 20, 220, 90)
        lay_sunucu = QtWidgets.QVBoxLayout(grp_sunucu)
        self.btn_sunucu_tara = QtWidgets.QPushButton("🔍 Sunucuları Tara")
        self.cb_sunucu = QtWidgets.QComboBox()
        lay_sunucu.addWidget(self.btn_sunucu_tara)
        lay_sunucu.addWidget(self.cb_sunucu)

        grp_etiket = QtWidgets.QGroupBox("Etiket Seçimi", self.centralwidget)
        grp_etiket.setGeometry(260, 20, 260, 130)
        lay_etiket = QtWidgets.QVBoxLayout(grp_etiket)
        self.btn_etiket_tara = QtWidgets.QPushButton("📋 Etiketleri Tara")
        self.list_etiket = QtWidgets.QListWidget()
        self.list_etiket.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)
        lay_etiket.addWidget(self.btn_etiket_tara)
        lay_etiket.addWidget(self.list_etiket)

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

        grp_kurulum = QtWidgets.QGroupBox("Kurulum", self.centralwidget)
        grp_kurulum.setGeometry(20, 120, 220, 40)
        lay_k = QtWidgets.QHBoxLayout(grp_kurulum)
        self.btn_kurulum_ac = QtWidgets.QPushButton("⚙ Sistem Kurulum Merkezi")
        lay_k.addWidget(self.btn_kurulum_ac)

        grp_konsol = QtWidgets.QGroupBox("Canlı Veri / Log Ekranı", self.centralwidget)
        grp_konsol.setGeometry(20, 175, 780, 440)
        lay_konsol = QtWidgets.QVBoxLayout(grp_konsol)
        self.txt_konsol = QtWidgets.QTextEdit()
        self.txt_konsol.setReadOnly(True)
        self.txt_konsol.setStyleSheet("background: #0d0d0d; color: #00ff41; font-family: Consolas; font-size: 12px;")
        lay_konsol.addWidget(self.txt_konsol)

        MainWindow.setCentralWidget(self.centralwidget)
        MainWindow.setWindowTitle("OPC DA → OPC UA Gateway v4.1 (Ticari Sürüm)")

class KurulumPenceresi(QtWidgets.QDialog):
    def __init__(self, log_koprusu):
        super().__init__()
        self.log = log_koprusu
        self.setWindowTitle("Sistem Kurulum Merkezi")
        self.resize(500, 480)
        layout = QtWidgets.QVBoxLayout(self)

        self.lbl_mimari = QtWidgets.QLabel("✅ 32-Bit Python — OPC DA uyumlu.")
        self.lbl_mimari.setAlignment(Qt.AlignCenter)
        self.lbl_mimari.setStyleSheet("color: #2e7d32; font-weight: bold; padding: 4px;")
        layout.addWidget(self.lbl_mimari)

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
        self.kurulum_log.setStyleSheet("background-color: #1e1e1e; color: #d4d4d4;")
        layout.addWidget(self.kurulum_log)
        self._kendi_log = LogKoprusu(self.kurulum_log)

    def _log(self, metin): self._kendi_log.yaz(metin)

    def _durum_guncelle(self, idx, metin, renk):
        QtCore.QMetaObject.invokeMethod(self.durum_lbller[idx], "setText", Qt.QueuedConnection, QtCore.Q_ARG(str, metin))
        QtCore.QMetaObject.invokeMethod(self.durum_lbller[idx], "setStyleSheet", Qt.QueuedConnection, QtCore.Q_ARG(str, f"color: {renk}; font-weight: bold;"))

    def python_indir_ve_kur(self):
        url = "https://www.python.org/ftp/python/3.13.3/python-3.13.3.exe"
        path = os.path.join(tempfile.gettempdir(), "py313_32_setup.exe")
        def indir():
            self._durum_guncelle(0, "⏳ Kuruluyor...", "orange")
            try:
                ctx = ssl.create_default_context(); ctx.check_hostname = False; ctx.verify_mode = ssl.CERT_NONE
                urllib.request.urlretrieve(url, path)
                p = subprocess.Popen(f'"{path}" /quiet InstallAllUsers=1 PrependPath=1 Include_test=0 TargetDir="C:\\Python313_32"', shell=True)
                p.wait()
                self._durum_guncelle(0, "✅ Tamamlandı", "green")
                site_path_ekle()
            except Exception as e:
                self._durum_guncelle(0, "❌ Hata", "red")
        threading.Thread(target=indir, daemon=True).start()

    def _komut_calistir(self, komut, adim_idx):
        def islem():
            self._durum_guncelle(adim_idx, "⏳ Çalışıyor...", "orange")
            try:
                p = subprocess.Popen(komut, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, shell=True, encoding='utf-8', errors='replace')
                for satir in p.stdout: self._log(satir.strip())
                p.wait()
                self._durum_guncelle(adim_idx, "✅ Tamamlandı", "green")
            except:
                self._durum_guncelle(adim_idx, "❌ Hata", "red")
        threading.Thread(target=islem, daemon=True).start()

    def kutuphaneleri_kur(self):
        pip = f'"{PYTHON32_EXE}" -m pip' if os.path.exists(PYTHON32_EXE) else "pip"
        self._komut_calistir(f'{pip} install --upgrade pip setuptools wheel requests && {pip} install OpenOPC-Python3x asyncua pywin32 pyro4', 1)

    def dll_kaydet(self):
        komut = f'"{PYTHON32_EXE}" "{os.path.join(PYTHON32_SCRIPTS, "pywin32_postinstall.py")}" -install' if os.path.exists(PYTHON32_EXE) else f'"{sys.executable}" -c "import pywin32_postinstall; pywin32_postinstall.install()"'
        self._komut_calistir(komut, 2)

# =====================================================================
# 3. BÖLÜM: ZIRHLI GATEWAY MOTORU
# =====================================================================
class GatewayWorker(QThread):
    log_sinyali    = pyqtSignal(str)   
    bitti_sinyali  = pyqtSignal()

    def __init__(self, prog_id, ip, port, etiketler):
        super().__init__()
        self.prog_id, self.ip, self.port, self.etiketler = prog_id, ip, port, etiketler
        self._calisıyor = True

    def _log(self, metin): self.log_sinyali.emit(str(metin))

    def run(self):
        try:
            site_path_ekle()
            import pythoncom, OpenOPC, pywintypes
            copyreg.pickle(type(pywintypes.Time(0)), lambda dt: (pywintypes.Time, (int(dt),)))
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try: loop.run_until_complete(self._ua_dongusu(pythoncom, OpenOPC))
            finally: loop.close()
        except Exception as e: self._log(f"❌ Motor hatası: {e}")
        finally: self.bitti_sinyali.emit()

    async def _ua_dongusu(self, pythoncom, OpenOPC):
        from asyncua import Server, ua
        import re
        srv = Server(); await srv.init(); srv.set_endpoint(f"opc.tcp://{self.ip}:{self.port}/")
        idx = await srv.register_namespace("http://opcgateway/v2")
        kok = await srv.nodes.objects.add_object(idx, "Saha_Verileri")
        
        try:
            async with srv:
                self._log(f"📡 Yayın: opc.tcp://{self.ip}:{self.port}/")
                pythoncom.CoInitialize(); opc = OpenOPC.client(); opc.connect(self.prog_id)
                
                etiket_haritasi = {}
                for et in self.etiketler:
                    safe = re.sub(r'[^a-zA-Z0-9_]', '_', et)
                    if not safe or safe[0].isdigit(): safe = "Tag_" + safe
                    node = await kok.add_variable(idx, safe, 0.0, ua.VariantType.Double)
                    await node.set_writable(); etiket_haritasi[et] = node

                while self._calisıyor:
                    parcalar, gorevler = [], []
                    for et in self.etiketler:
                        try:
                            deger = opc.properties(et, id=2)
                            if deger is not None and et in etiket_haritasi:
                                try:
                                    num = float(deger)
                                    gorevler.append(etiket_haritasi[et].write_value(num, ua.VariantType.Double))
                                    parcalar.append(f"🟢 OK {et}: {num:.4f}")
                                except: parcalar.append(f"🔵 INFO {et}: {deger}")
                            else: parcalar.append(f"⚠️ {et}: Boş")
                        except: pass
                    
                    if gorevler: await asyncio.gather(*gorevler, return_exceptions=True)
                    self._log("\n".join(parcalar)); self._log("-" * 60)
                    await asyncio.sleep(1)
                opc.close()
        except Exception as e: self._log(f"❌ Döngü Hatası: {e}")

    def durdur(self): self._calisıyor = False

# =====================================================================
# 4. BÖLÜM: ANA EKRAN VE YÖNLENDİRİCİ
# =====================================================================
class GatewayApp(QtWidgets.QMainWindow, Ui_MainWindow):
    lisans_iptal_sinyali = pyqtSignal()

    def __init__(self, hwid, lisans_anahtari):
        super().__init__()
        self.setupUi(self)
        self.worker = None
        self.arkaplan_ajan = None
        self.cihaz_hwid = hwid
        self.lisans_kodu = lisans_anahtari

        self._log_koprusu = LogKoprusu(self.txt_konsol)
        self._kurulum = KurulumPenceresi(self._log_koprusu)

        self.btn_kurulum_ac.clicked.connect(self._kurulum.show)
        self.btn_sunucu_tara.clicked.connect(self._sunucu_tara)
        self.btn_etiket_tara.clicked.connect(self._etiket_tara)
        self.btn_baslat.clicked.connect(self._baslat)
        self.btn_durdur.clicked.connect(self._durdur)
        
        self._log("🚀 Viya IIoT Gateway v4.1 Hazır.")
        
        # Gölge ajanı (arka plan kontrolünü) başlat
        self._ajan_baslat()

    def _ajan_baslat(self):
        if self.cihaz_hwid and self.lisans_kodu:
            self.arkaplan_ajan = ArkaplanLisansKontrol(self.cihaz_hwid, self.lisans_kodu)
            self.arkaplan_ajan.iptal_sinyali.connect(self._ajan_yakaladi)
            self.arkaplan_ajan.start()

    def _ajan_yakaladi(self, mesaj):
        self._log(f"❌ {mesaj}")
        self._durdur() # Sensör akışını anında kes
        
        # Lisans dosyasını imha et
        if os.path.exists(LISANS_DOSYASI):
            os.remove(LISANS_DOSYASI)
            
        QMessageBox.critical(self, "LİSANS İPTAL EDİLDİ", mesaj)
        
        # Ana pencereyi kapat ve Aktivasyon ekranına dön
        self.lisans_iptal_sinyali.emit()
        self.close()

    def _log(self, metin): self._log_koprusu.yaz(metin)

    def _sunucu_tara(self):
        try:
            site_path_ekle(); import OpenOPC; opc = OpenOPC.client()
            self.cb_sunucu.clear(); self.cb_sunucu.addItems(opc.servers())
        except Exception as e: self._log("❌ Tarama hatası.")

    def _etiket_tara(self):
        prog_id = self.cb_sunucu.currentText().strip()
        try:
            site_path_ekle(); import OpenOPC; opc = OpenOPC.client(); opc.connect(prog_id)
            self.list_etiket.clear()
            for pattern in ['Simulation Items.*', 'Configured Aliases.*', '*']:
                try:
                    bulunan = opc.list(pattern, flat=True)
                    if bulunan: self.list_etiket.addItems(bulunan); break
                except: continue
            opc.close()
        except: self._log("❌ Etiket bulunamadı.")

    def _baslat(self):
        prog_id = self.cb_sunucu.currentText().strip()
        secili = [item.text() for item in self.list_etiket.selectedItems()]
        if not prog_id or not secili: return
        self.txt_konsol.clear(); self.btn_baslat.setEnabled(False); self.btn_durdur.setEnabled(True)
        ip, port = self.txt_ip.text().strip() or "0.0.0.0", self.txt_port.text().strip() or "4840"
        self.worker = GatewayWorker(prog_id, ip, port, secili)
        self.worker.log_sinyali.connect(self._log); self.worker.bitti_sinyali.connect(self._bitti)
        self.worker.start()

    def _durdur(self):
        if self.worker: self.worker.durdur(); self.btn_durdur.setEnabled(False)

    def _bitti(self):
        self.btn_baslat.setEnabled(True); self.btn_durdur.setEnabled(False)

    def closeEvent(self, event):
        if self.arkaplan_ajan:
            self.arkaplan_ajan.durdur()
            self.arkaplan_ajan.wait(2000)
        if self.worker and self.worker.isRunning():
            self.worker.durdur(); self.worker.wait(3000)
        event.accept()

# =====================================================================
# SİSTEM YÖNETİCİSİ (EKRANLAR ARASI GEÇİŞİ SAĞLAR)
# =====================================================================
class ViyaController(QObject):
    def __init__(self):
        super().__init__()
        self.yonetici = LisansYoneticisi()
        self.ana_ekran = None
        self.akt_ekran = None

    def baslat(self):
        durum, mesaj = self.yonetici.lisans_kontrol()
        if durum:
            self.ana_ekrani_goster()
        else:
            self.aktivasyon_goster()

    def ana_ekrani_goster(self):
        try:
            with open(LISANS_DOSYASI, 'r') as f:
                kayit = json.load(f)
            hwid = kayit.get("hwid")
            lisans = kayit.get("lisans_anahtari")
        except:
            hwid, lisans = "", ""

        self.ana_ekran = GatewayApp(hwid, lisans)
        self.ana_ekran.lisans_iptal_sinyali.connect(self.lisans_dustu)
        self.ana_ekran.show()

    def aktivasyon_goster(self):
        self.akt_ekran = AktivasyonPenceresi(self.yonetici)
        self.akt_ekran.basarili_sinyali.connect(self.aktivasyondan_anaya)
        self.akt_ekran.show()

    def aktivasyondan_anaya(self):
        self.akt_ekran.close()
        self.ana_ekrani_goster()

    def lisans_dustu(self):
        # Arka plan ajanı lisansı iptal ederse tekrar aktivasyona dön
        self.aktivasyon_goster()


if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    app.setStyle("Fusion")
    
    kontrolor = ViyaController()
    kontrolor.baslat()
    
    sys.exit(app.exec_())