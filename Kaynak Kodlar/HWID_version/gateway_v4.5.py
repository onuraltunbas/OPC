# -*- coding: utf-8 -*-
"""
OPC DA -> OPC UA Gateway v4.1
HWID + Online Aktivasyon Lisans Sistemi (Model B)
v4.1: "detail"/"mesaj" anahtar uyumsuzlugu duzeltildi
"""

import sys
import os
import subprocess
import threading
import asyncio
import copyreg
import datetime
import urllib.request
import urllib.parse
import urllib.error
import json
import hashlib
import tempfile
import multiprocessing
import ssl
import time

if __name__ == '__main__':
    multiprocessing.freeze_support()

# =====================================================================
# YAPILANDIRMA
# =====================================================================
SUNUCU_URL       = "https://web-production-b5bbc.up.railway.app"
UYGULAMA_SIFRESI = "admin1234"
LISANS_DOSYASI   = os.path.join(os.getenv("APPDATA", ""), "OPCGateway", "lisans.json")
CHECKIN_ARALIK   = 7
VERSIYON         = "4.1"

PYTHON32_SITE    = r"C:\Python313_32\Lib\site-packages"
PYTHON32_EXE     = r"C:\Python313_32\python.exe"
PYTHON32_SCRIPTS = r"C:\Python313_32\Scripts"

def site_path_ekle():
    if os.path.exists(PYTHON32_SITE) and PYTHON32_SITE not in sys.path:
        sys.path.insert(0, PYTHON32_SITE)

site_path_ekle()

from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtCore import QThread, pyqtSignal, QObject, Qt, QTimer
from PyQt5.QtWidgets import QMessageBox, QDialog


# =====================================================================
# BÖLÜM 0: HWID ÜRETİCİ
# =====================================================================
class HwidUretici:

    @staticmethod
    def _get_smbios_uuid():
        try:
            import ctypes
            import uuid
            kernel32 = ctypes.windll.kernel32
            RSMB = 0x52534D42
            size = kernel32.GetSystemFirmwareTable(RSMB, 0, None, 0)
            if size == 0: return ""
            buf = ctypes.create_string_buffer(size)
            kernel32.GetSystemFirmwareTable(RSMB, 0, buf, size)
            
            table_data = buf.raw[8:]
            idx = 0
            while idx < len(table_data):
                if idx + 4 > len(table_data): break
                t_type = table_data[idx]
                t_len = table_data[idx+1]
                
                if t_type == 1 and t_len >= 24:
                    uuid_bytes = table_data[idx+8 : idx+24]
                    return str(uuid.UUID(bytes_le=uuid_bytes)).upper()
                
                idx += t_len
                while idx < len(table_data) - 1:
                    if table_data[idx] == 0 and table_data[idx+1] == 0:
                        idx += 2
                        break
                    idx += 1
            return ""
        except Exception:
            return ""

    @staticmethod
    def _get_cpu_id():
        try:
            import winreg
            key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"HARDWARE\DESCRIPTION\System\CentralProcessor\0")
            return str(winreg.QueryValueEx(key, "Identifier")[0])
        except Exception:
            return ""

    @staticmethod
    def _get_machine_guid():
        try:
            import winreg
            key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Cryptography")
            return str(winreg.QueryValueEx(key, "MachineGuid")[0])
        except Exception:
            return "BILINMIYOR"

    @staticmethod
    def uret():
        cpu_id  = HwidUretici._get_cpu_id()
        mb_uuid = HwidUretici._get_smbios_uuid()

        if not cpu_id and not mb_uuid:
            mb_uuid = HwidUretici._get_machine_guid()

        raw = f"{cpu_id}::{mb_uuid}::{UYGULAMA_SIFRESI}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32].upper()


# =====================================================================
# BÖLÜM 1: LİSANS YÖNETİCİSİ
# =====================================================================

# Arka planda lisans geçerliliğini kontrol eden thread
# Sunucu "gecerli=False" dönünce ya da lisans iptal edilince sinyal üretir.
class LisansKontrolcusu(QThread):
    lisans_iptal_edildi = pyqtSignal()  # Lisans geçersiz → aktivasyon ekranı

    # Kaç saniyede bir sunucuya ping atacağını belirler
    KONTROL_ARALIK_SN = 10

    def __init__(self, lisans_yoneticisi):
        super().__init__()
        self.ly = lisans_yoneticisi
        self._calisıyor = True
        self._son_bagli = False  # Bir önceki döngüde internet var mıydı?

    def run(self):
        """
        Döngü:
        - İnternete bağlıysa → sunucuya kontrol isteği gönder
          • Geçersiz → sinyal gönder, thread sonlanır
          • Geçerli → KONTROL_ARALIK_SN saniye bekle
        - İnternete bağlı değilse → 10 saniye bekle, tekrar dene
          (offline → online geçişinde hemen kontrol yapar)
        """
        # İlk çalışmada KONTROL_ARALIK_SN kadar bekle (başlangıç zaten dogrula() ile yapıldı)
        bekleme = self.KONTROL_ARALIK_SN
        gecen = 0
        while self._calisıyor:
            time.sleep(1)
            gecen += 1
            if gecen < bekleme:
                continue
            gecen = 0

            lisans = self.ly._lisans_oku()
            if not lisans:
                # Dosya yoksa zaten aktivasyon ekranı gösterilecek, thread dur
                self.lisans_iptal_edildi.emit()
                return

            basari, yanit = self.ly._api_cagir("/api/kontrol", {
                "hwid": self.ly.hwid,
                "lisans_kodu": lisans.get("lisans_kodu", ""),
            })

            if not basari:
                # Sunucuya ulaşılamadı (offline) → 10 sn'de bir tekrar dene
                self._son_bagli = False
                bekleme = 10
                continue

            # Sunucuya ulaştık
            if not self._son_bagli:
                # Yeni online olduk → bir önceki offline dönemdeki iptal kontrolü
                self._son_bagli = True

            if yanit.get("gecerli"):
                # Lisans hâlâ geçerli → dosyayı güncelle, normal aralığa dön
                lisans["son_kontrol"] = datetime.datetime.now().isoformat()
                lisans["bitis_tarihi"] = yanit.get("bitis_tarihi") or lisans.get("bitis_tarihi", "")
                lisans["musteri_adi"]  = yanit.get("musteri_adi", lisans.get("musteri_adi", ""))
                self.ly._lisans_kaydet(lisans)
                bekleme = self.KONTROL_ARALIK_SN
            else:
                # LİSANS İPTAL → lisans dosyasını sil ve sinyal gönder
                self.ly._lisans_sil()
                self.lisans_iptal_edildi.emit()
                return

    def durdur(self):
        self._calisıyor = False


class LisansYoneticisi:

    def __init__(self):
        self.hwid = HwidUretici.uret()
        os.makedirs(os.path.dirname(LISANS_DOSYASI), exist_ok=True)

    def _lisans_oku(self):
        try:
            with open(LISANS_DOSYASI, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return None

    def _lisans_kaydet(self, veri):
        with open(LISANS_DOSYASI, "w", encoding="utf-8") as f:
            json.dump(veri, f, ensure_ascii=False, indent=2)

    def _lisans_sil(self):
        try:
            os.remove(LISANS_DOSYASI)
        except Exception:
            pass

    # ----------------------------------------------------------------
    # DÜZELTME: Sunucu hem "mesaj" hem "detail" dönebilir.
    # Her ikisini de kontrol eden yardımcı fonksiyon.
    # ----------------------------------------------------------------
    @staticmethod
    def _mesaj_al(yanit: dict, varsayilan="Bilinmeyen hata.") -> str:
        """
        FastAPI başarı yanıtlarında "mesaj", hata yanıtlarında "detail" döndürür.
        Her ikisini de dene, ikisi de yoksa varsayılanı döndür.
        """
        return (
            yanit.get("mesaj")
            or yanit.get("detail")
            or varsayilan
        )

    def _api_cagir(self, endpoint, veri):
        """
        Sunucuya POST atar.
        Döndürür: (basari: bool, yanit: dict)
        """
        try:
            url  = f"{SUNUCU_URL.rstrip('/')}{endpoint}"
            body = json.dumps(veri).encode("utf-8")
            ctx  = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode    = ssl.CERT_NONE

            req = urllib.request.Request(
                url, data=body,
                headers={
                    "Content-Type": "application/json",
                    "X-App-Secret": UYGULAMA_SIFRESI,
                    "X-App-Version": VERSIYON,
                },
                method="POST"
            )
            with urllib.request.urlopen(req, context=ctx, timeout=10) as r:
                yanit = json.loads(r.read().decode("utf-8"))
                return True, yanit

        except urllib.error.HTTPError as e:
            # DÜZELTME: HTTP hata kodlarını da yakala ve "detail" anahtarını oku
            try:
                hata_govde = json.loads(e.read().decode("utf-8"))
            except Exception:
                hata_govde = {"detail": f"HTTP {e.code}: {e.reason}"}
            return False, hata_govde

        except urllib.error.URLError as e:
            # Sunucuya ulaşılamıyor (internet yok, URL yanlış vb.)
            return False, {"detail": f"Sunucuya ulasilamiyor: {e.reason}"}

        except Exception as e:
            return False, {"detail": str(e)}

    # ----------------------------------------------------------------
    # Aktivasyon
    # ----------------------------------------------------------------
    def aktive_et(self, lisans_kodu):
        """
        Döndürür: (basari: bool, mesaj: str)
        """
        basari, yanit = self._api_cagir("/api/aktive-et", {
            "hwid": self.hwid,
            "lisans_kodu": lisans_kodu.strip().upper(),
        })

        if basari and yanit.get("basarili"):
            self._lisans_kaydet({
                "lisans_kodu": lisans_kodu.strip().upper(),
                "hwid": self.hwid,
                "tur": yanit.get("tur", "bilinmiyor"),
                "bitis_tarihi": yanit.get("bitis_tarihi") or "",
                "son_kontrol": datetime.datetime.now().isoformat(),
                "musteri_adi": yanit.get("musteri_adi", ""),
            })
            return True, self._mesaj_al(yanit, "Aktivasyon basarili.")
        else:
            # DÜZELTME: "detail" veya "mesaj" — hangisi varsa göster
            return False, self._mesaj_al(yanit, "Sunucudan yanit alinamadi.")

    # ----------------------------------------------------------------
    # Başlangıç doğrulaması
    # ----------------------------------------------------------------
    def dogrula(self):
        lisans = self._lisans_oku()

        if not lisans:
            return "aktivasyon"

        if lisans.get("hwid") != self.hwid:
            self._lisans_sil()
            return "hata:Bu lisans baska bir bilgisayara aittir.\nLutfen satici ile iletisime gecin."

        bitis = lisans.get("bitis_tarihi", "")
        if bitis:
            try:
                bitis_dt = datetime.datetime.fromisoformat(bitis)
                if datetime.datetime.now() > bitis_dt:
                    sonuc = self._sunucu_checkin(lisans)
                    if sonuc != "gecerli":
                        self._lisans_sil()
                        return "hata:Lisans sureniz dolmustur.\nYenilemek icin satici ile iletisime gecin."
            except Exception:
                pass

        son_kontrol_str = lisans.get("son_kontrol", "")
        try:
            son_kontrol = datetime.datetime.fromisoformat(son_kontrol_str)
            fark = (datetime.datetime.now() - son_kontrol).days
            if fark >= CHECKIN_ARALIK:
                sonuc = self._sunucu_checkin(lisans)
                if sonuc != "gecerli":
                    return sonuc
        except Exception:
            pass

        return "gecerli"

    def _sunucu_checkin(self, lisans):
        basari, yanit = self._api_cagir("/api/kontrol", {
            "hwid": self.hwid,
            "lisans_kodu": lisans.get("lisans_kodu", ""),
        })

        if not basari:
            # Sunucuya ulaşılamıyor → offline çalışmaya devam et
            return "gecerli"

        if yanit.get("gecerli"):
            lisans["son_kontrol"] = datetime.datetime.now().isoformat()
            lisans["bitis_tarihi"] = yanit.get("bitis_tarihi") or lisans.get("bitis_tarihi", "")
            lisans["musteri_adi"]  = yanit.get("musteri_adi", lisans.get("musteri_adi", ""))
            self._lisans_kaydet(lisans)
            return "gecerli"
        else:
            return f"hata:{self._mesaj_al(yanit, 'Lisans gecersiz.')}"

    def lisans_bilgisi(self):
        return self._lisans_oku()


# =====================================================================
# BÖLÜM 2: AKTİVASYON PENCERESİ
# =====================================================================
class AktivasyonPenceresi(QDialog):
    aktivasyon_basarili = pyqtSignal()

    def __init__(self, lisans_yoneticisi: LisansYoneticisi):
        super().__init__()
        self.ly = lisans_yoneticisi
        self.setWindowTitle("OPC Gateway - Lisans Aktivasyonu")
        self.setFixedSize(480, 340)
        self.setWindowFlag(Qt.WindowContextHelpButtonHint, False)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setSpacing(14)
        layout.setContentsMargins(30, 24, 30, 24)

        lbl_baslik = QtWidgets.QLabel("Lisans Aktivasyonu Gerekli")
        lbl_baslik.setStyleSheet("font-size: 16px; font-weight: bold; color: #1565c0;")
        lbl_baslik.setAlignment(Qt.AlignCenter)
        layout.addWidget(lbl_baslik)

        hwid_frame = QtWidgets.QFrame()
        hwid_frame.setStyleSheet(
            "background: #f5f5f5; border: 1px solid #ddd; "
            "border-radius: 6px; padding: 8px;"
        )
        hwid_layout = QtWidgets.QVBoxLayout(hwid_frame)
        hwid_layout.setSpacing(4)

        lbl_hwid_acik = QtWidgets.QLabel("Bu bilgisayarin donanum kimligi (HWID):")
        lbl_hwid_acik.setStyleSheet("font-size: 11px; color: #666;")

        self.lbl_hwid = QtWidgets.QLabel(self.ly.hwid)
        self.lbl_hwid.setStyleSheet(
            "font-family: Consolas, monospace; font-size: 13px; "
            "font-weight: bold; color: #333; letter-spacing: 1px;"
        )
        self.lbl_hwid.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.lbl_hwid.setCursor(Qt.IBeamCursor)

        btn_kopyala = QtWidgets.QPushButton("HWID'yi Kopyala")
        btn_kopyala.setFixedHeight(28)
        btn_kopyala.clicked.connect(self._hwid_kopyala)

        hwid_layout.addWidget(lbl_hwid_acik)
        hwid_layout.addWidget(self.lbl_hwid)
        hwid_layout.addWidget(btn_kopyala)
        layout.addWidget(hwid_frame)

        lbl_kod = QtWidgets.QLabel("Lisans kodunuzu girin:")
        lbl_kod.setStyleSheet("font-size: 12px;")
        layout.addWidget(lbl_kod)

        self.txt_kod = QtWidgets.QLineEdit()
        self.txt_kod.setPlaceholderText("AYL-XXXX-XXXX-XXXX")
        self.txt_kod.setFixedHeight(36)
        self.txt_kod.setStyleSheet(
            "font-family: Consolas; font-size: 14px; letter-spacing: 2px; "
            "border: 1px solid #aaa; border-radius: 4px; padding: 0 8px;"
        )
        layout.addWidget(self.txt_kod)

        self.lbl_durum = QtWidgets.QLabel("")
        self.lbl_durum.setAlignment(Qt.AlignCenter)
        self.lbl_durum.setStyleSheet("font-size: 12px;")
        self.lbl_durum.setWordWrap(True)
        self.lbl_durum.setMinimumHeight(36)
        layout.addWidget(self.lbl_durum)

        self.btn_aktive = QtWidgets.QPushButton("Aktive Et")
        self.btn_aktive.setFixedHeight(40)
        self.btn_aktive.setStyleSheet(
            "background-color: #1565c0; color: white; font-size: 14px; "
            "font-weight: bold; border-radius: 6px;"
        )
        self.btn_aktive.clicked.connect(self._aktive_et)
        layout.addWidget(self.btn_aktive)

        self.txt_kod.returnPressed.connect(self._aktive_et)

    def _hwid_kopyala(self):
        QtWidgets.QApplication.clipboard().setText(self.ly.hwid)
        self.lbl_durum.setText("HWID panoya kopyalandi.")
        self.lbl_durum.setStyleSheet("color: #2e7d32; font-size: 12px;")

    def _aktive_et(self):
        kod = self.txt_kod.text().strip()
        if not kod:
            self.lbl_durum.setText("Lutfen lisans kodunu girin.")
            self.lbl_durum.setStyleSheet("color: #c62828; font-size: 12px;")
            return

        self.btn_aktive.setEnabled(False)
        self.lbl_durum.setText("Sunucuya baglaniliyor...")
        self.lbl_durum.setStyleSheet("color: #e65100; font-size: 12px;")
        QtWidgets.QApplication.processEvents()

        def islem():
            basari, mesaj = self.ly.aktive_et(kod)
            QtCore.QMetaObject.invokeMethod(
                self, "_aktivasyon_sonuc",
                Qt.QueuedConnection,
                QtCore.Q_ARG(bool, basari),
                QtCore.Q_ARG(str, str(mesaj)),
            )

        threading.Thread(target=islem, daemon=True).start()

    @QtCore.pyqtSlot(bool, str)
    def _aktivasyon_sonuc(self, basari, mesaj):
        if basari:
            self.lbl_durum.setText(f"Aktivasyon basarili! {mesaj}")
            self.lbl_durum.setStyleSheet("color: #2e7d32; font-size: 12px;")
            QTimer.singleShot(1200, self.aktivasyon_basarili.emit)
            QTimer.singleShot(1200, self.accept)
        else:
            self.lbl_durum.setText(f"Hata: {mesaj}")
            self.lbl_durum.setStyleSheet("color: #c62828; font-size: 12px;")
            self.btn_aktive.setEnabled(True)


# =====================================================================
# BÖLÜM 3: THREAD-SAFE LOG KÖPRÜSÜ
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


# =====================================================================
# BÖLÜM 4: ARAYÜZ TASARIMI
# =====================================================================
class Ui_MainWindow(object):
    def setupUi(self, MainWindow):
        MainWindow.setObjectName("MainWindow")
        MainWindow.resize(820, 660)
        MainWindow.setMinimumSize(820, 660)

        self.centralwidget = QtWidgets.QWidget(MainWindow)

        grp_sunucu = QtWidgets.QGroupBox("OPC DA Sunucu", self.centralwidget)
        grp_sunucu.setGeometry(20, 20, 220, 90)
        lay_sunucu = QtWidgets.QVBoxLayout(grp_sunucu)
        self.btn_sunucu_tara = QtWidgets.QPushButton("Sunuculari Tara")
        self.cb_sunucu = QtWidgets.QComboBox()
        lay_sunucu.addWidget(self.btn_sunucu_tara)
        lay_sunucu.addWidget(self.cb_sunucu)

        grp_etiket = QtWidgets.QGroupBox("Etiket Secimi", self.centralwidget)
        grp_etiket.setGeometry(260, 20, 260, 130)
        lay_etiket = QtWidgets.QVBoxLayout(grp_etiket)
        self.btn_etiket_tara = QtWidgets.QPushButton("Etiketleri Tara")
        self.list_etiket = QtWidgets.QListWidget()
        self.list_etiket.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)
        lay_etiket.addWidget(self.btn_etiket_tara)
        lay_etiket.addWidget(self.list_etiket)

        grp_baslat = QtWidgets.QGroupBox("Yayin Ayarlari", self.centralwidget)
        grp_baslat.setGeometry(540, 20, 260, 130)
        lay_baslat = QtWidgets.QFormLayout(grp_baslat)
        self.txt_ip   = QtWidgets.QLineEdit("0.0.0.0")
        self.txt_port = QtWidgets.QLineEdit("4840")
        self.btn_baslat = QtWidgets.QPushButton("Baslat")
        self.btn_baslat.setStyleSheet("background-color: #2e7d32; color: white; font-weight: bold;")
        self.btn_durdur = QtWidgets.QPushButton("Durdur")
        self.btn_durdur.setStyleSheet("background-color: #c62828; color: white; font-weight: bold;")
        self.btn_durdur.setEnabled(False)
        lay_baslat.addRow("Yayin IP:", self.txt_ip)
        lay_baslat.addRow("Port:", self.txt_port)
        lay_baslat.addRow(self.btn_baslat)
        lay_baslat.addRow(self.btn_durdur)

        grp_alt = QtWidgets.QGroupBox("", self.centralwidget)
        grp_alt.setGeometry(20, 120, 220, 60)
        grp_alt.setStyleSheet("border: none;")
        lay_alt = QtWidgets.QHBoxLayout(grp_alt)
        self.btn_kurulum_ac = QtWidgets.QPushButton("Sistem Kurulum Merkezi")
        lay_alt.addWidget(self.btn_kurulum_ac)

        self.lbl_lisans = QtWidgets.QLabel("")
        self.lbl_lisans.setGeometry(20, 183, 780, 20)
        self.lbl_lisans.setParent(self.centralwidget)
        self.lbl_lisans.setStyleSheet("color: #555; font-size: 11px;")
        self.lbl_lisans.setAlignment(Qt.AlignRight)

        grp_konsol = QtWidgets.QGroupBox("Canli Veri / Log Ekrani", self.centralwidget)
        grp_konsol.setGeometry(20, 205, 780, 425)
        lay_konsol = QtWidgets.QVBoxLayout(grp_konsol)
        self.txt_konsol = QtWidgets.QTextEdit()
        self.txt_konsol.setReadOnly(True)
        self.txt_konsol.setStyleSheet(
            "background: #0d0d0d; color: #00ff41; "
            "font-family: Consolas, 'Courier New'; font-size: 12px;"
        )
        lay_konsol.addWidget(self.txt_konsol)

        MainWindow.setCentralWidget(self.centralwidget)
        MainWindow.setWindowTitle(f"OPC DA -> OPC UA Gateway v{VERSIYON}")


# =====================================================================
# BÖLÜM 5: KURULUM PENCERESİ
# =====================================================================
class KurulumPenceresi(QtWidgets.QWidget):
    def __init__(self, log_koprusu: LogKoprusu):
        super().__init__(None, Qt.Window)
        self.log = log_koprusu
        self.setWindowTitle("Sistem Kurulum Merkezi")
        self.resize(500, 480)
        self.setAttribute(Qt.WA_DeleteOnClose, False)
        layout = QtWidgets.QVBoxLayout(self)

        self.lbl_mimari = QtWidgets.QLabel()
        self.lbl_mimari.setAlignment(Qt.AlignCenter)
        if sys.maxsize > 2**32:
            self.lbl_mimari.setText("UYARI: 64-Bit Python! OPC DA icin 32-Bit Python gerekli.")
            self.lbl_mimari.setStyleSheet("color: #e65100; font-weight: bold; padding: 4px;")
        else:
            self.lbl_mimari.setText("32-Bit Python -- OPC DA uyumlu.")
            self.lbl_mimari.setStyleSheet("color: #2e7d32; font-weight: bold; padding: 4px;")
        layout.addWidget(self.lbl_mimari)

        self.adimlar = [
            ("0. Python 3.13 (32-bit) Indir & Kur", self.python_indir_ve_kur, "#1565c0"),
            ("1. Kutuphaneleri Kur (PIP)",            self.kutuphaneleri_kur,  "#4a148c"),
            ("2. Windows DLL'lerini Kaydet",          self.dll_kaydet,         "#1b5e20"),
        ]
        self.durum_lbller = []
        for metin, slot, renk in self.adimlar:
            h = QtWidgets.QHBoxLayout()
            btn = QtWidgets.QPushButton(metin)
            btn.setStyleSheet(f"background-color: {renk}; color: white; font-weight: bold; padding: 6px;")
            btn.clicked.connect(slot)
            lbl = QtWidgets.QLabel("Bekliyor")
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
        self._kendi_log = LogKoprusu(self.kurulum_log)

    def _log(self, metin):
        self._kendi_log.yaz(metin)

    def _durum_guncelle(self, idx, metin, renk):
        QtCore.QMetaObject.invokeMethod(
            self.durum_lbller[idx], "setText",
            Qt.QueuedConnection, QtCore.Q_ARG(str, metin))
        QtCore.QMetaObject.invokeMethod(
            self.durum_lbller[idx], "setStyleSheet",
            Qt.QueuedConnection, QtCore.Q_ARG(str, f"color: {renk}; font-weight: bold;"))

    def python_indir_ve_kur(self):
        url  = "https://www.python.org/ftp/python/3.13.3/python-3.13.3.exe"
        path = os.path.join(tempfile.gettempdir(), "py313_32_setup.exe")

        def indir():
            self._durum_guncelle(0, "Indiriliyor...", "orange")
            self._log("Python 3.13.3 (32-bit) indiriliyor...")
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
                            self._log(f"  ... %{int(indirilen * 100 / toplam)}")
                self._log("Indirme tamam. Sessiz kurulum basliyor...")
                self._durum_guncelle(0, "Kuruluyor...", "orange")
                komut = (f'"{path}" /quiet InstallAllUsers=1 PrependPath=1 '
                         f'Include_test=0 TargetDir="C:\\Python313_32"')
                p = subprocess.Popen(komut, shell=True)
                p.wait()
                if p.returncode == 0:
                    self._durum_guncelle(0, "Tamamlandi", "green")
                    self._log("Python C:\\Python313_32 klasorune kuruldu.")
                    site_path_ekle()
                else:
                    self._durum_guncelle(0, f"Kod: {p.returncode}", "orange")
            except Exception as e:
                self._log(f"Hata: {e}")
                self._durum_guncelle(0, "Hata", "red")

        threading.Thread(target=indir, daemon=True).start()

    def _komut_calistir(self, komut, adim_idx):
        def islem():
            self._durum_guncelle(adim_idx, "Calisiyor...", "orange")
            self._log(f"Komut: {komut}")
            try:
                p = subprocess.Popen(komut, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                     text=True, shell=True, encoding='utf-8', errors='replace')
                for satir in p.stdout:
                    satir = satir.strip()
                    if satir:
                        self._log(satir)
                p.wait()
                if p.returncode == 0:
                    self._durum_guncelle(adim_idx, "Tamamlandi", "green")
                    self._log("Islem basarili.")
                else:
                    self._durum_guncelle(adim_idx, "Kontrol Et", "orange")
                    self._log(f"Return code: {p.returncode}")
            except Exception as e:
                self._log(f"Hata: {e}")
                self._durum_guncelle(adim_idx, "Hata", "red")

        threading.Thread(target=islem, daemon=True).start()

    def kutuphaneleri_kur(self):
        pip = f'"{PYTHON32_EXE}" -m pip' if os.path.exists(PYTHON32_EXE) else "pip"
        komut = (f'{pip} install --upgrade pip setuptools wheel && '
                 f'{pip} install OpenOPC-Python3x asyncua pywin32 pyro4')
        self._komut_calistir(komut, 1)

    def dll_kaydet(self):
        if os.path.exists(PYTHON32_EXE):
            python_exe = f'"{PYTHON32_EXE}"'
            post = os.path.join(PYTHON32_SCRIPTS, "pywin32_postinstall.py")
        else:
            python_exe = f'"{sys.executable}"'
            post = os.path.join(os.path.dirname(sys.executable), "Scripts", "pywin32_postinstall.py")
        komut = f'{python_exe} "{post}" -install' if os.path.exists(post) else \
                f'{python_exe} -c "import pywin32_postinstall; pywin32_postinstall.install()"'
        self._komut_calistir(komut, 2)


# =====================================================================
# BÖLÜM 6: GATEWAY MOTORU
# =====================================================================
class GatewayWorker(QThread):
    log_sinyali   = pyqtSignal(str)
    bitti_sinyali = pyqtSignal()

    def __init__(self, prog_id, ip, port, etiketler):
        super().__init__()
        self.prog_id    = prog_id
        self.ip         = ip
        self.port       = port
        self.etiketler  = etiketler
        self._calisıyor = True

    def _log(self, metin):
        self.log_sinyali.emit(str(metin))

    def _toplu_oku(self, opc, etiket_listesi):
        sonuclar = {}
        try:
            ham = opc.read(etiket_listesi)
            if ham and isinstance(ham, list):
                for et, veri in zip(etiket_listesi, ham):
                    sonuclar[et] = (veri[0], veri[1], str(veri[2])) \
                        if veri and veri[0] is not None else (None, None, None)
                return sonuclar
        except Exception:
            pass
        for et in etiket_listesi:
            try:
                sonuc = opc.read(et)
                if sonuc and sonuc[0] is not None:
                    sonuclar[et] = (sonuc[0], sonuc[1], str(sonuc[2]))
                    continue
            except Exception:
                pass
            try:
                deger = opc.properties(et, id=2)
                if deger is not None:
                    sonuclar[et] = (deger, "Good", "N/A")
                    continue
            except Exception:
                pass
            sonuclar[et] = (None, None, None)
        return sonuclar

    def run(self):
        try:
            site_path_ekle()
            import pythoncom, OpenOPC, pywintypes

            def _pickle_pytime(dt):
                return (pywintypes.Time, (int(dt),))
            copyreg.pickle(type(pywintypes.Time(0)), _pickle_pytime)

            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(self._ua_dongusu(pythoncom, OpenOPC))
            finally:
                loop.close()
        except ImportError as e:
            self._log(f"Eksik kutuphane: {e}")
            self._log("Kurulum Merkezi'nden adimlari tamamlayin.")
        except Exception as e:
            self._log(f"Motor hatasi: {e}")
        finally:
            self.bitti_sinyali.emit()

    async def _ua_dongusu(self, pythoncom, OpenOPC):
        from asyncua import Server, ua

        srv = Server()
        await srv.init()
        endpoint = f"opc.tcp://{self.ip}:{self.port}/"
        srv.set_endpoint(endpoint)
        srv.set_server_name(f"OPC Gateway v{VERSIYON}")
        idx = await srv.register_namespace("http://opcgateway/v4")
        kok = await srv.nodes.objects.add_object(idx, "Saha_Verileri")

        async with srv:
            self._log(f"OPC UA Sunucusu yayinda: {endpoint}")
            pythoncom.CoInitialize()
            try:
                opc = OpenOPC.client()
                opc.connect(self.prog_id)
                self._log(f"OPC DA baglandi: {self.prog_id}")
            except Exception as e:
                self._log(f"OPC DA baglanti hatasi: {e}")
                return

            etiket_haritasi = {}
            for et in self.etiketler:
                safe = et.replace(".", "_").replace(" ", "_").replace("\\", "_")
                node = await kok.add_variable(idx, safe, 0.0, ua.VariantType.Double)
                await node.set_writable()
                etiket_haritasi[et] = node

            self._log(f"{len(self.etiketler)} etiket UA'ya eklendi. Dongu basliyor...\n")
            etiket_listesi = list(etiket_haritasi.keys())
            hata_sayaci = {}

            while self._calisıyor:
                okumalar = self._toplu_oku(opc, etiket_listesi)
                satirlar = []
                gorevler = []

                for et in etiket_listesi:
                    deger, kalite, _ = okumalar.get(et, (None, None, None))
                    node = etiket_haritasi[et]
                    if deger is None:
                        hata_sayaci[et] = hata_sayaci.get(et, 0) + 1
                        satirlar.append(f"UYARI {et}: Veri yok ({hata_sayaci[et]}x)")
                        continue
                    hata_sayaci[et] = 0
                    try:
                        num = float(deger)
                        gorevler.append(node.write_value(num, ua.VariantType.Double))
                        satirlar.append(f"OK {et}: {num:.4f} [{kalite}]")
                    except (ValueError, TypeError):
                        satirlar.append(f"INFO {et}: {deger} (metin)")

                if gorevler:
                    await asyncio.gather(*gorevler)

                self._log("\n".join(satirlar))
                self._log("-" * 60)
                await asyncio.sleep(0.1)

            try:
                opc.close()
            except Exception:
                pass
            self._log("Gateway durduruldu.")

    def durdur(self):
        self._calisıyor = False


# =====================================================================
# BÖLÜM 7: ANA UYGULAMA
# =====================================================================
class GatewayApp(QtWidgets.QMainWindow, Ui_MainWindow):
    def __init__(self, lisans_yoneticisi: LisansYoneticisi, lisans_kontrolcusu: 'LisansKontrolcusu'):
        super().__init__()
        self.ly = lisans_yoneticisi
        self.setupUi(self)
        self.worker   = None
        self._kurulum = None

        self._log_koprusu = LogKoprusu(self.txt_konsol)

        self.btn_kurulum_ac.clicked.connect(self._kurulum_ac)
        self.btn_sunucu_tara.clicked.connect(self._sunucu_tara)
        self.btn_etiket_tara.clicked.connect(self._etiket_tara)
        self.btn_baslat.clicked.connect(self._baslat)
        self.btn_durdur.clicked.connect(self._durdur)

        # Arka plan lisans kontrolcüsünü bağla
        self._lisans_kontrolcusu = lisans_kontrolcusu
        self._lisans_kontrolcusu.lisans_iptal_edildi.connect(self._lisans_iptal_islemi)

        self._lisans_bilgisi_goster()
        self._log(f"OPC DA -> OPC UA Gateway v{VERSIYON} hazir.")
        self._log("   Adimlar: Sunucu Tara -> Etiket Tara -> Sec -> Baslat\n")

    def _lisans_bilgisi_goster(self):
        bilgi = self.ly.lisans_bilgisi()
        if not bilgi:
            return
        tur     = bilgi.get("tur", "")
        bitis   = bilgi.get("bitis_tarihi", "")
        musteri = bilgi.get("musteri_adi", "")
        if bitis:
            try:
                bitis_dt = datetime.datetime.fromisoformat(bitis)
                kalan = (bitis_dt - datetime.datetime.now()).days
                self.lbl_lisans.setText(
                    f"Lisans: {tur} | Musteri: {musteri} | "
                    f"Bitis: {bitis_dt.strftime('%d.%m.%Y')} ({kalan} gun kaldi) | "
                    f"HWID: {self.ly.hwid[:8]}..."
                )
            except Exception:
                pass
        else:
            self.lbl_lisans.setText(
                f"Lisans: {tur} (omur boyu) | Musteri: {musteri} | "
                f"HWID: {self.ly.hwid[:8]}..."
            )

    def _kurulum_ac(self):
        try:
            if self._kurulum is None:
                self._kurulum = KurulumPenceresi(self._log_koprusu)
            self._kurulum.show()
            self._kurulum.raise_()
            self._kurulum.activateWindow()
        except Exception as e:
            QMessageBox.critical(self, "Hata", f"Kurulum penceresi acilamadi:\n{e}")

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
            self._log(f"{len(sunucular)} sunucu bulundu.")
        except ImportError:
            self._log("OpenOPC kurulu degil -- Kurulum Merkezi'ni acin.")
        except Exception as e:
            self._log(f"Sunucu tarama hatasi: {e}")

    def _etiket_tara(self):
        prog_id = self.cb_sunucu.currentText().strip()
        if not prog_id:
            QMessageBox.warning(self, "Uyari", "Once sunucu tarayin ve secin.")
            return
        try:
            site_path_ekle()
            import OpenOPC
            opc = OpenOPC.client()
            opc.connect(prog_id)
            self.list_etiket.clear()
            etiketler = []
            for pattern in ['Simulation Items.*', 'Configured Aliases.*',
                            'Channel1.Device1.*', '*']:
                try:
                    bulunan = opc.list(pattern, flat=True)
                    if bulunan:
                        etiketler.extend(bulunan)
                        break
                except Exception:
                    continue
            if not etiketler:
                etiketler = ['Random.Real8', 'Random.Int4', 'Bucket Brigade.Real8',
                             'Random.Money', 'Triangle Waves.Real8']
                self._log("Otomatik etiket bulunamadi -- demo etiketler gosteriliyor.")
            self.list_etiket.addItems(etiketler)
            opc.close()
            self._log(f"{len(etiketler)} etiket listelendi.")
        except ImportError:
            self._log("OpenOPC kurulu degil -- Kurulum Merkezi'ni acin.")
        except Exception as e:
            self._log(f"Etiket tarama hatasi: {e}")

    def _baslat(self):
        prog_id = self.cb_sunucu.currentText().strip()
        secili  = [item.text() for item in self.list_etiket.selectedItems()]
        if not prog_id:
            QMessageBox.warning(self, "Hata", "Lutfen bir OPC DA sunucusu secin.")
            return
        if not secili:
            QMessageBox.warning(self, "Hata", "Lutfen en az bir etiket secin.")
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
            self._log("Durdurma sinyali gonderildi...")

    def _bitti(self):
        self.btn_baslat.setEnabled(True)
        self.btn_durdur.setEnabled(False)
        self._log("Gateway durdu.")

    @QtCore.pyqtSlot()
    def _lisans_iptal_islemi(self):
        """Sunucu lisansı iptal ettiğinde çağrılır."""
        # Gateway çalışıyorsa durdur
        if self.worker and self.worker.isRunning():
            self.worker.durdur()
            self.worker.wait(3000)

        # Ana pencereyi gizle
        self.hide()

        QMessageBox.warning(
            None,
            "Lisans İptal Edildi",
            "Bu ürünün lisansı iptal edilmiştir.\n"
            "Devam etmek için geçerli bir lisans anahtarı giriniz."
        )

        # Aktivasyon penceresini göster
        aktiv_pencere = AktivasyonPenceresi(self.ly)
        if aktiv_pencere.exec_() == QDialog.Accepted:
            # Yeni lisans girildi → kontrolcüyü yeniden başlat ve pencereyi göster
            yeni_kontrolcu = LisansKontrolcusu(self.ly)
            yeni_kontrolcu.lisans_iptal_edildi.connect(self._lisans_iptal_islemi)
            self._lisans_kontrolcusu = yeni_kontrolcu
            yeni_kontrolcu.start()
            self._lisans_bilgisi_goster()
            self.show()
        else:
            # Kullanıcı aktivasyon penceresini kapattı → çıkış
            QtWidgets.QApplication.quit()

    def closeEvent(self, event):
        if self.worker and self.worker.isRunning():
            self.worker.durdur()
            self.worker.wait(3000)
        if self._lisans_kontrolcusu and self._lisans_kontrolcusu.isRunning():
            self._lisans_kontrolcusu.durdur()
            self._lisans_kontrolcusu.wait(3000)
        event.accept()


# =====================================================================
# BÖLÜM 8: UYGULAMA GİRİŞİ
# =====================================================================
def uygulamayi_baslat():
    app = QtWidgets.QApplication(sys.argv)
    app.setStyle("Fusion")

    ly = LisansYoneticisi()

    splash_dlg = QtWidgets.QDialog()
    splash_dlg.setWindowTitle("OPC Gateway - Lisans Kontrolu")
    splash_dlg.setFixedSize(300, 80)
    splash_dlg.setWindowFlag(Qt.WindowContextHelpButtonHint, False)
    splash_lbl = QtWidgets.QLabel("Lisans kontrol ediliyor...", splash_dlg)
    splash_lbl.setAlignment(Qt.AlignCenter)
    splash_lbl.setGeometry(0, 0, 300, 80)
    splash_dlg.show()
    app.processEvents()

    sonuc = ly.dogrula()
    splash_dlg.hide()

    if sonuc == "aktivasyon":
        aktiv_pencere = AktivasyonPenceresi(ly)
        if aktiv_pencere.exec_() != QDialog.Accepted:
            sys.exit(0)
        sonuc = ly.dogrula()
        if sonuc != "gecerli":
            QMessageBox.critical(None, "Lisans Hatasi",
                                 sonuc.replace("hata:", ""))
            sys.exit(1)

    elif sonuc.startswith("hata:"):
        QMessageBox.critical(None, "Lisans Hatasi",
                             sonuc.replace("hata:", ""))
        sys.exit(1)

    # Arka plan lisans kontrolcüsünü başlat
    kontrolcu = LisansKontrolcusu(ly)
    pencere = GatewayApp(ly, kontrolcu)
    pencere.show()
    kontrolcu.start()
    sys.exit(app.exec_())


if __name__ == "__main__":
    uygulamayi_baslat()