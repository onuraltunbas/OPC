# -*- coding: utf-8 -*-
"""
OPC UA Viewer (Client)
Nautilus Technology - Kurumsal Tema Uyumlu
"""

import sys
import asyncio
import datetime
import os
import json
import hashlib
import hmac
import base64
import struct
import time
import ctypes
import winreg
import threading
import urllib.request
import urllib.error
import ssl
from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtCore import QThread, pyqtSignal, QObject, Qt, QTimer
from PyQt5.QtWidgets import QMessageBox, QDialog
from asyncua import Client

# =====================================================================
# YAPILANDIRMA
# =====================================================================
SUNUCU_URL       = "https://web-production-b5bbc.up.railway.app"
UYGULAMA_SIFRESI = "admin1234"
LISANS_DOSYASI   = os.path.join(os.getenv("APPDATA", ""), "OPCGateway", "viewer_lisans.json")
CHECKIN_ARALIK   = 7
VERSIYON         = "1.0"
URUN_TIPI        = "viewer"  # Ürün izolasyonu: bu değer lisans imzasına ve API isteklerine dahil edilir

# =====================================================================
# BÖLÜM 0: HWID ÜRETİCİ (Online Lisans için)
# =====================================================================
class HwidUretici:

    @staticmethod
    def _get_smbios_uuid():
        try:
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
                t_len  = table_data[idx+1]
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
            key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"HARDWARE\DESCRIPTION\System\CentralProcessor\0")
            return str(winreg.QueryValueEx(key, "Identifier")[0])
        except Exception:
            return ""

    @staticmethod
    def _get_machine_guid():
        try:
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
# BÖLÜM 0.5: OFFLİNE LİSANS ALTYAPISI
# =====================================================================

# --- Gömülü Offline Anahtar (parçalara bölünmüş, runtime'da birleştirilir) ---
_SK_P1 = bytes([0x4f, 0x50, 0x43, 0x5f, 0x56, 0x57, 0x5f, 0x4f])   # OPC_VW_O
_SK_P2 = bytes([0x46, 0x46, 0x4c, 0x49, 0x4e, 0x45, 0x5f, 0x4b])   # FFLINE_K
_SK_P3 = hashlib.sha256(b"opcviewer_offline_2026_salt_v1").digest()[:16]
OFFLINE_SECRET_KEY = _SK_P1 + _SK_P2 + _SK_P3

# Viewer-özel dosya ve registry yolları (ürün çakışmasını önler)
OFFLINE_LISANS_DOSYASI = os.path.join(os.getenv("APPDATA", ""), "OPCGateway", "viewer_offline_lisans.dat")
OFFLINE_BURNIN_DOSYASI = os.path.join(os.getenv("APPDATA", ""), "OPCGateway", "viewer_burnin.dat")
OFFLINE_REG_PATH       = r"Software\OPCGateway\ViewerOfflineLicense"  # Gateway'den ayrı
OFFLINE_MAX_GUN        = 365


def _debugger_kontrol():
    """IsDebuggerPresent ile debugger tespiti."""
    try:
        if ctypes.windll.kernel32.IsDebuggerPresent():
            os.abort()
    except Exception:
        pass


class OfflineHwidUretici:
    """Anti-Spoofing HWID: Anakart + Disk + MachineGuid → HMAC-SHA256"""

    @staticmethod
    def _reg_oku(hive, path, name, default=""):
        try:
            key = winreg.OpenKey(hive, path)
            val = winreg.QueryValueEx(key, name)[0]
            winreg.CloseKey(key)
            return str(val).strip()
        except Exception:
            return default

    @staticmethod
    def _disk_serial():
        try:
            vol_serial = ctypes.c_ulong(0)
            ctypes.windll.kernel32.GetVolumeInformationW(
                "C:\\", None, 0, ctypes.byref(vol_serial), None, None, None, 0
            )
            return f"{vol_serial.value:08X}"
        except Exception:
            return "00000000"

    @staticmethod
    def uret() -> str:
        mb_serial = OfflineHwidUretici._reg_oku(
            winreg.HKEY_LOCAL_MACHINE,
            r"HARDWARE\DESCRIPTION\System\BIOS",
            "BaseBoardSerialNumber"
        )
        machine_guid = OfflineHwidUretici._reg_oku(
            winreg.HKEY_LOCAL_MACHINE,
            r"SOFTWARE\Microsoft\Cryptography",
            "MachineGuid"
        )
        disk_serial = OfflineHwidUretici._disk_serial()
        raw = f"{mb_serial}|{machine_guid}|{disk_serial}".encode("utf-8")
        return hmac.new(OFFLINE_SECRET_KEY, raw, hashlib.sha256).hexdigest()


class ChallengeUretici:
    """Tek kullanımlık, zaman damgalı istek kodu. 10-dk penceresi."""

    @staticmethod
    def uret(hwid_hash: str) -> str:
        ts_slot = int(time.time()) // 600
        raw = hwid_hash[:8].encode("ascii") + struct.pack(">Q", ts_slot)
        b32 = base64.b32encode(raw).decode().rstrip("=")
        return f"REQ-{b32[:20]}"

    @staticmethod
    def gecerli_slotlar() -> list:
        now = int(time.time()) // 600
        return [now - 1, now, now + 1]


class OfflineLisansYoneticisi:
    """
    Viewer çevrimdışı lisans yönetimi:
    • XOR şifreli dosya (viewer_offline_lisans.dat) + Registry çift kayıt
    • HMAC-SHA256 imzası başına URUN_TIPI eklenerek ürün izolasyonu sağlanır
    • Dosya ve registry yolları Gateway'den tamamen bağımsız
    """

    def __init__(self):
        self.hwid_hash = OfflineHwidUretici.uret()
        os.makedirs(os.path.dirname(OFFLINE_LISANS_DOSYASI), exist_ok=True)

    # ── XOR şifreleme ──

    @staticmethod
    def _sifrele(veri: bytes) -> bytes:
        key = hashlib.sha256(OFFLINE_SECRET_KEY + b"xor_v1").digest()
        ks  = (key * (len(veri) // 32 + 1))[:len(veri)]
        return bytes(a ^ b for a, b in zip(veri, ks))

    @staticmethod
    def _coz(veri: bytes) -> bytes:
        return OfflineLisansYoneticisi._sifrele(veri)

    # ── Dosya I/O ──

    def _lisans_oku(self):
        try:
            with open(OFFLINE_LISANS_DOSYASI, "rb") as f:
                return json.loads(self._coz(f.read()).decode("utf-8"))
        except Exception:
            return None

    def _lisans_kaydet(self, veri: dict):
        raw = json.dumps(veri, ensure_ascii=False).encode("utf-8")
        with open(OFFLINE_LISANS_DOSYASI, "wb") as f:
            f.write(self._sifrele(raw))
        self._registry_kaydet(veri)

    def _lisans_sil(self):
        try:
            os.remove(OFFLINE_LISANS_DOSYASI)
        except Exception:
            pass
        self._registry_temizle()

    # ── Registry çift kayıt (Viewer-özel yol) ──

    def _registry_kaydet(self, veri: dict):
        try:
            key = winreg.CreateKey(winreg.HKEY_CURRENT_USER, OFFLINE_REG_PATH)
            for alan, deger in veri.items():
                enc = base64.b64encode(
                    self._sifrele(json.dumps(deger).encode())
                ).decode()
                winreg.SetValueEx(key, alan, 0, winreg.REG_SZ, enc)
            winreg.CloseKey(key)
        except Exception:
            pass

    def _registry_oku(self) -> dict:
        try:
            key  = winreg.OpenKey(winreg.HKEY_CURRENT_USER, OFFLINE_REG_PATH)
            veri = {}
            i    = 0
            while True:
                try:
                    name, val, _ = winreg.EnumValue(key, i)
                    dec = self._coz(base64.b64decode(val.encode())).decode()
                    veri[name] = json.loads(dec)
                    i += 1
                except OSError:
                    break
            winreg.CloseKey(key)
            return veri
        except Exception:
            return {}

    def _registry_temizle(self):
        try:
            winreg.DeleteKey(winreg.HKEY_CURRENT_USER, OFFLINE_REG_PATH)
        except Exception:
            pass

    # ── Burn-in listesi ──

    def _burnin_kontrol(self, imza: str) -> bool:
        imza_hash = hashlib.sha256(imza.encode()).hexdigest()
        try:
            with open(OFFLINE_BURNIN_DOSYASI, "r") as f:
                return imza_hash in f.read().splitlines()
        except Exception:
            return False

    def _burnin_ekle(self, imza: str):
        try:
            with open(OFFLINE_BURNIN_DOSYASI, "a") as f:
                f.write(hashlib.sha256(imza.encode()).hexdigest() + "\n")
        except Exception:
            pass

    # ── Saat geri kontrolü ──

    @staticmethod
    def _saat_geri_mi(son_giris_ts: float) -> bool:
        return time.time() < son_giris_ts - 30

    # ── ACT kodu doğrulama ve aktivasyon ──

    def aktive_et(self, act_kodu: str, challenge_kodu: str):
        """Döndürür: (basari: bool, mesaj: str, yetki: str, sure_gun: int)"""
        try:
            p = act_kodu.strip().upper().split("-")
            if len(p) != 4 or p[0] != "ACT":
                return False, "Geçersiz aktivasyon kodu formatı.", "", 0
            sure_str, yetki, imza = p[1], p[2], p[3]
            if not sure_str.endswith("D"):
                return False, "Geçersiz süre formatı.", "", 0
            sure_gun = int(sure_str[:-1])
            if not (1 <= sure_gun <= OFFLINE_MAX_GUN):
                return False, f"Geçersiz süre (1-{OFFLINE_MAX_GUN} gün).", "", 0
            if yetki not in ("FULL", "READ", "DEMO"):
                return False, "Geçersiz yetki seviyesi.", "", 0
        except Exception:
            return False, "Aktivasyon kodu ayrıştırılamadı.", "", 0

        if self._burnin_kontrol(imza):
            return False, "Bu aktivasyon kodu daha önce kullanılmış.", "", 0

        # HMAC imza doğrulama (URUN_TIPI='viewer' prefix ile ürün izolasyonu sağlanır)
        # Bir Gateway ACT kodu bu imzayı hiçbir zaman geçemez.
        mesaj = f"{URUN_TIPI}|{challenge_kodu}|{sure_gun}|{yetki}".encode("utf-8")
        beklenen = hmac.new(OFFLINE_SECRET_KEY, mesaj, hashlib.sha256).hexdigest()[:16].upper()
        if not hmac.compare_digest(imza, beklenen):
            return False, "Aktivasyon kodu imzası geçersiz.", "", 0

        # Challenge'daki HWID prefix'ini doğrula
        try:
            req_b32 = challenge_kodu.replace("REQ-", "")
            padding = "=" * ((-len(req_b32)) % 8)
            decoded = base64.b32decode(req_b32 + padding)
            if decoded[:8].decode("ascii") != self.hwid_hash[:8]:
                return False, "İstek kodu bu bilgisayara ait değil.", "", 0
        except Exception:
            return False, "İstek kodu doğrulanamadı.", "", 0

        now_ts = time.time()
        lisans = {
            "hwid_hash":    self.hwid_hash,
            "urun":         URUN_TIPI,  # Ürün tipi lisansa kaydediliyor
            "sure_gun":     sure_gun,
            "yetki":        yetki,
            "aktivasyon_ts":now_ts,
            "bitis_ts":     now_ts + sure_gun * 86400,
            "son_giris_ts": now_ts,
            "imza":         imza,
        }
        self._lisans_kaydet(lisans)
        self._burnin_ekle(imza)
        return True, f"Aktivasyon başarılı! ({sure_gun} gün, {yetki})", yetki, sure_gun

    # ── Başlangıç doğrulama ──

    def dogrula(self):
        """Döndürür: (durum: str, yetki: str)
        durum: 'gecerli' | 'aktivasyon' | 'saat_geri' | 'hata:...'"""
        _debugger_kontrol()

        lisans     = self._lisans_oku()
        reg_lisans = self._registry_oku()

        if not lisans:
            return "aktivasyon", ""

        # Ürün izolasyonu: başka ürüne ait lisansı reddet
        if lisans.get("urun") and lisans.get("urun") != URUN_TIPI:
            self._lisans_sil()
            return "hata:Bu offline lisans başka bir ürüne aittir.", ""

        # Registry vs dosya tutarlılık
        if reg_lisans:
            if reg_lisans.get("hwid_hash") != lisans.get("hwid_hash"):
                return "hata:Lisans kaydında tutarsızlık tespit edildi.", ""
            if reg_lisans.get("imza") != lisans.get("imza"):
                return "hata:Lisans kaydında tutarsızlık tespit edildi.", ""

        if lisans.get("hwid_hash") != self.hwid_hash:
            self._lisans_sil()
            return "hata:Bu offline lisans başka bir bilgisayara aittir.", ""

        if self._saat_geri_mi(lisans.get("son_giris_ts", 0)):
            return "saat_geri", ""

        if time.time() > lisans.get("bitis_ts", 0):
            self._lisans_sil()
            return "hata:Offline lisans süreniz dolmuştur.", ""

        imza = lisans.get("imza", "")
        if not imza or len(imza) != 16:
            return "hata:Lisans imzası geçersiz.", ""

        lisans["son_giris_ts"] = time.time()
        self._lisans_kaydet(lisans)
        return "gecerli", lisans.get("yetki", "FULL")

    def lisans_bilgisi(self):
        return self._lisans_oku()


# =====================================================================
# BÖLÜM 0.6: ONLİNE LİSANS YÖNETİCİSİ
# =====================================================================
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

    @staticmethod
    def _mesaj_al(yanit: dict, varsayilan="Bilinmeyen hata.") -> str:
        return yanit.get("mesaj") or yanit.get("detail") or varsayilan

    def _api_cagir(self, endpoint, veri):
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
                return True, json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            try:
                hata_govde = json.loads(e.read().decode("utf-8"))
            except Exception:
                hata_govde = {"detail": f"HTTP {e.code}: {e.reason}"}
            return False, hata_govde
        except urllib.error.URLError as e:
            return False, {"detail": f"Sunucuya ulasilamiyor: {e.reason}"}
        except Exception as e:
            return False, {"detail": str(e)}

    def aktive_et(self, lisans_kodu):
        """Döndürür: (basari: bool, mesaj: str)"""
        basari, yanit = self._api_cagir("/api/aktive-et", {
            "hwid": self.hwid,
            "lisans_kodu": lisans_kodu.strip().upper(),
            "urun": URUN_TIPI,  # Ürün izolasyonu: viewer olarak bildirilir
        })
        if basari and yanit.get("basarili"):
            self._lisans_kaydet({
                "lisans_kodu": lisans_kodu.strip().upper(),
                "hwid": self.hwid,
                "urun": URUN_TIPI,  # Ürün tipi dosyaya kaydedilir
                "tur": yanit.get("tur", "bilinmiyor"),
                "bitis_tarihi": yanit.get("bitis_tarihi") or "",
                "son_kontrol": datetime.datetime.now().isoformat(),
                "musteri_adi": yanit.get("musteri_adi", ""),
            })
            return True, self._mesaj_al(yanit, "Aktivasyon basarili.")
        else:
            return False, self._mesaj_al(yanit, "Sunucudan yanit alinamadi.")

    def dogrula(self):
        lisans = self._lisans_oku()
        if not lisans:
            return "aktivasyon"

        # Ürün izolasyonu: başka ürüne ait lisansı reddet
        if lisans.get("urun") and lisans.get("urun") != URUN_TIPI:
            self._lisans_sil()
            return f"hata:Bu lisans '{lisans.get('urun')}' ürününe aittir, 'viewer' için kullanilamaz."

        if lisans.get("hwid") != self.hwid:
            self._lisans_sil()
            return "hata:Bu lisans baska bir bilgisayara aittir."

        bitis = lisans.get("bitis_tarihi", "")
        if bitis:
            try:
                bitis_dt = datetime.datetime.fromisoformat(bitis)
                if datetime.datetime.now() > bitis_dt:
                    self._lisans_sil()
                    return "hata:Lisans sureniz dolmustur."
            except Exception:
                pass
        return "gecerli"

    def lisans_bilgisi(self):
        return self._lisans_oku()


# =====================================================================
# BÖLÜM 0.7: AKTİVASYON PENCERELERİ
# =====================================================================
class AktivasyonPenceresi(QDialog):
    aktivasyon_basarili = pyqtSignal()

    def __init__(self, lisans_yoneticisi: LisansYoneticisi):
        super().__init__()
        self.ly = lisans_yoneticisi
        self.setWindowTitle("OPC UA Viewer - Lisans Aktivasyonu")
        self.setFixedSize(480, 320)
        self.setWindowFlag(Qt.WindowContextHelpButtonHint, False)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setSpacing(14)
        layout.setContentsMargins(30, 24, 30, 24)

        lbl_baslik = QtWidgets.QLabel("Lisans Aktivasyonu Gerekli")
        lbl_baslik.setStyleSheet("font-size:16px; font-weight:bold; color:#5b8cff; background:transparent;")
        lbl_baslik.setAlignment(Qt.AlignCenter)
        layout.addWidget(lbl_baslik)

        hwid_frame = QtWidgets.QFrame()
        hwid_frame.setStyleSheet("background:#1a1d2e; border:1px solid #2a2d3e; border-radius:6px; padding:8px;")
        hwid_layout = QtWidgets.QVBoxLayout(hwid_frame)
        hwid_layout.setSpacing(4)
        lbl_hwid_acik = QtWidgets.QLabel("Bu bilgisayarın donanım kimligi (HWID):")
        lbl_hwid_acik.setStyleSheet("font-size:11px; color:#8a9bc0; background:transparent;")
        self.lbl_hwid = QtWidgets.QLabel(self.ly.hwid)
        self.lbl_hwid.setStyleSheet(
            "font-family:Consolas; font-size:12px; font-weight:bold;"
            "color:#7eb8ff; letter-spacing:1px; background:transparent; border:none;"
        )
        self.lbl_hwid.setTextInteractionFlags(Qt.TextSelectableByMouse)
        btn_kopyala = QtWidgets.QPushButton("HWID'yi Kopyala")
        btn_kopyala.setFixedHeight(28)
        btn_kopyala.clicked.connect(lambda: QtWidgets.QApplication.clipboard().setText(self.ly.hwid))
        hwid_layout.addWidget(lbl_hwid_acik)
        hwid_layout.addWidget(self.lbl_hwid)
        hwid_layout.addWidget(btn_kopyala)
        layout.addWidget(hwid_frame)

        lbl_kod = QtWidgets.QLabel("Lisans kodunuzu girin:")
        lbl_kod.setStyleSheet("font-size:12px; background:transparent;")
        layout.addWidget(lbl_kod)

        self.txt_kod = QtWidgets.QLineEdit()
        self.txt_kod.setPlaceholderText("AYL-XXXX-XXXX-XXXX")
        self.txt_kod.setFixedHeight(36)
        layout.addWidget(self.txt_kod)

        self.lbl_durum = QtWidgets.QLabel("")
        self.lbl_durum.setAlignment(Qt.AlignCenter)
        self.lbl_durum.setStyleSheet("font-size:12px; background:transparent;")
        self.lbl_durum.setWordWrap(True)
        layout.addWidget(self.lbl_durum)

        self.btn_aktive = QtWidgets.QPushButton("✔ Aktive Et")
        self.btn_aktive.setFixedHeight(40)
        self.btn_aktive.setStyleSheet("""
            QPushButton { background:#5b8cff; color:white; font-size:14px;
                font-weight:bold; border-radius:6px; border:none; }
            QPushButton:hover { background:#4a7aff; }
            QPushButton:disabled { background:#1e2033; color:#666; }
        """)
        self.btn_aktive.clicked.connect(self._aktive_et)
        layout.addWidget(self.btn_aktive)
        self.txt_kod.returnPressed.connect(self._aktive_et)

    def _aktive_et(self):
        kod = self.txt_kod.text().strip()
        if not kod:
            self.lbl_durum.setText("Lütfen lisans kodunu girin.")
            self.lbl_durum.setStyleSheet("color:#f87171; font-size:12px; background:transparent;")
            return
        self.btn_aktive.setEnabled(False)
        self.lbl_durum.setText("Sunucuya baglanılıyor...")
        self.lbl_durum.setStyleSheet("color:#f59e0b; font-size:12px; background:transparent;")
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
            self.lbl_durum.setText(f"Aktivasyon başarılı! {mesaj}")
            self.lbl_durum.setStyleSheet("color:#4ade80; font-size:12px; background:transparent;")
            QTimer.singleShot(1200, self.aktivasyon_basarili.emit)
            QTimer.singleShot(1200, self.accept)
        else:
            self.lbl_durum.setText(f"Hata: {mesaj}")
            self.lbl_durum.setStyleSheet("color:#f87171; font-size:12px; background:transparent;")
            self.btn_aktive.setEnabled(True)


class OfflineAktivasyonPenceresi(QDialog):
    aktivasyon_basarili = pyqtSignal(str)   # yetki seviyesini taşır

    def __init__(self, offline_ly: OfflineLisansYoneticisi):
        super().__init__()
        self.oly = offline_ly
        self._guncel_challenge = ""
        self.setWindowTitle("OPC UA Viewer — Çevrimdışı Aktivasyon")
        self.setFixedSize(540, 460)
        self.setWindowFlag(Qt.WindowContextHelpButtonHint, False)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(26, 20, 26, 20)

        lbl_baslik = QtWidgets.QLabel("🔒  Çevrimdışı (Air-Gapped) Aktivasyon")
        lbl_baslik.setStyleSheet("font-size:15px; font-weight:bold; color:#e65100; background:transparent;")
        lbl_baslik.setAlignment(Qt.AlignCenter)
        layout.addWidget(lbl_baslik)

        lbl_acik = QtWidgets.QLabel(
            "İnternet bağlantısı tespit edilmedi.\n"
            "Satıcıdan aldığınız aktivasyon kodunu girin."
        )
        lbl_acik.setStyleSheet("font-size:11px; color:#8a9bc0; background:transparent;")
        lbl_acik.setAlignment(Qt.AlignCenter)
        layout.addWidget(lbl_acik)

        # HWID Hash
        hwid_frame = QtWidgets.QFrame()
        hwid_frame.setStyleSheet("background:#1a1d2e; border:1px solid #2a2d3e; border-radius:6px;")
        hwid_lay = QtWidgets.QVBoxLayout(hwid_frame)
        hwid_lay.setContentsMargins(10, 8, 10, 8)
        hwid_lay.setSpacing(4)
        lbl_hw_t = QtWidgets.QLabel("Donanım Kimliği (HWID Hash):")
        lbl_hw_t.setStyleSheet("font-size:10px; color:#8a9bc0; background:transparent;")
        self.lbl_hwid = QtWidgets.QLabel(self.oly.hwid_hash)
        self.lbl_hwid.setStyleSheet(
            "font-family:Consolas; font-size:10px; color:#7eb8ff;"
            "letter-spacing:1px; background:transparent; border:none;"
        )
        self.lbl_hwid.setWordWrap(True)
        self.lbl_hwid.setTextInteractionFlags(Qt.TextSelectableByMouse)
        btn_hwid_kopyala = QtWidgets.QPushButton("Kopyala")
        btn_hwid_kopyala.setFixedHeight(24)
        btn_hwid_kopyala.clicked.connect(lambda: QtWidgets.QApplication.clipboard().setText(self.oly.hwid_hash))
        hwid_lay.addWidget(lbl_hw_t)
        hwid_lay.addWidget(self.lbl_hwid)
        hwid_lay.addWidget(btn_hwid_kopyala, alignment=Qt.AlignRight)
        layout.addWidget(hwid_frame)

        # İstek Kodu
        ch_frame = QtWidgets.QFrame()
        ch_frame.setStyleSheet("background:#1a1d2e; border:1px solid #2a2d3e; border-radius:6px;")
        ch_lay = QtWidgets.QVBoxLayout(ch_frame)
        ch_lay.setContentsMargins(10, 8, 10, 8)
        ch_lay.setSpacing(6)
        lbl_ch_t = QtWidgets.QLabel("İstek Kodu  (satıcıya gönderin):")
        lbl_ch_t.setStyleSheet("font-size:10px; color:#8a9bc0; background:transparent;")
        self.lbl_challenge = QtWidgets.QLabel("—  (Üret butonuna basın)")
        self.lbl_challenge.setStyleSheet(
            "font-family:Consolas; font-size:14px; font-weight:bold;"
            "color:#4ade80; letter-spacing:2px; background:transparent; border:none;"
        )
        self.lbl_challenge.setAlignment(Qt.AlignCenter)
        self.lbl_challenge.setTextInteractionFlags(Qt.TextSelectableByMouse)
        ch_btn_row = QtWidgets.QHBoxLayout()
        self.btn_uret = QtWidgets.QPushButton("🔄  İstek Kodu Üret")
        self.btn_uret.setFixedHeight(30)
        self.btn_uret.setStyleSheet("""
            QPushButton { background:#5b8cff; color:white; border:none;
                border-radius:5px; font-size:12px; font-weight:bold; }
            QPushButton:hover { background:#4a7aff; }
        """)
        self.btn_uret.clicked.connect(self._challenge_uret)
        self.btn_ch_kopyala = QtWidgets.QPushButton("📋 Kopyala")
        self.btn_ch_kopyala.setFixedHeight(30)
        self.btn_ch_kopyala.setEnabled(False)
        self.btn_ch_kopyala.clicked.connect(
            lambda: QtWidgets.QApplication.clipboard().setText(self._guncel_challenge)
        )
        ch_btn_row.addWidget(self.btn_uret)
        ch_btn_row.addWidget(self.btn_ch_kopyala)
        ch_lay.addWidget(lbl_ch_t)
        ch_lay.addWidget(self.lbl_challenge)
        ch_lay.addLayout(ch_btn_row)
        layout.addWidget(ch_frame)

        lbl_act = QtWidgets.QLabel("Aktivasyon Kodu  (satıcıdan alınan):")
        lbl_act.setStyleSheet("font-size:11px; color:#8a9bc0; background:transparent;")
        layout.addWidget(lbl_act)
        self.txt_act = QtWidgets.QLineEdit()
        self.txt_act.setPlaceholderText("ACT-30D-FULL-XXXXXXXXXXXXXXXX")
        self.txt_act.setFixedHeight(38)
        self.txt_act.setStyleSheet(
            "background:#0a0c14; border:1px solid #2a2d3e; border-radius:6px;"
            "color:#e0e0e0; font-family:Consolas; font-size:13px;"
            "letter-spacing:1px; padding:0 10px;"
        )
        layout.addWidget(self.txt_act)

        self.lbl_durum = QtWidgets.QLabel("")
        self.lbl_durum.setAlignment(Qt.AlignCenter)
        self.lbl_durum.setWordWrap(True)
        self.lbl_durum.setMinimumHeight(32)
        self.lbl_durum.setStyleSheet("font-size:12px; background:transparent;")
        layout.addWidget(self.lbl_durum)

        self.btn_aktive = QtWidgets.QPushButton("✔  Aktive Et")
        self.btn_aktive.setFixedHeight(42)
        self.btn_aktive.setStyleSheet("""
            QPushButton { background:#2e7d32; color:white; font-size:14px;
                font-weight:bold; border-radius:6px; border:none; }
            QPushButton:hover { background:#1b5e20; }
            QPushButton:disabled { background:#1e2033; color:#666; }
        """)
        self.btn_aktive.clicked.connect(self._aktive_et)
        layout.addWidget(self.btn_aktive)
        self.txt_act.returnPressed.connect(self._aktive_et)

    def _challenge_uret(self):
        ch = ChallengeUretici.uret(self.oly.hwid_hash)
        self._guncel_challenge = ch
        self.lbl_challenge.setText(ch)
        self.btn_ch_kopyala.setEnabled(True)
        self.lbl_durum.setText("İstek kodu üretildi. Satıcıya gönderin.")
        self.lbl_durum.setStyleSheet("color:#4ade80; font-size:11px; background:transparent;")

    def _aktive_et(self):
        act = self.txt_act.text().strip()
        if not act:
            self.lbl_durum.setText("Lütfen aktivasyon kodunu girin.")
            self.lbl_durum.setStyleSheet("color:#f87171; font-size:12px; background:transparent;")
            return
        if not self._guncel_challenge:
            self.lbl_durum.setText("Önce 'İstek Kodu Üret' butonuna basın.")
            self.lbl_durum.setStyleSheet("color:#f87171; font-size:12px; background:transparent;")
            return
        self.btn_aktive.setEnabled(False)
        self.lbl_durum.setText("Doğrulanıyor...")
        self.lbl_durum.setStyleSheet("color:#f59e0b; font-size:12px; background:transparent;")
        QtWidgets.QApplication.processEvents()
        def islem():
            basari, mesaj, yetki, sure_gun = self.oly.aktive_et(act, self._guncel_challenge)
            QtCore.QMetaObject.invokeMethod(
                self, "_aktivasyon_sonuc",
                Qt.QueuedConnection,
                QtCore.Q_ARG(bool, basari),
                QtCore.Q_ARG(str, mesaj),
                QtCore.Q_ARG(str, yetki),
            )
        threading.Thread(target=islem, daemon=True).start()

    @QtCore.pyqtSlot(bool, str, str)
    def _aktivasyon_sonuc(self, basari, mesaj, yetki):
        if basari:
            self.lbl_durum.setText(f"Aktivasyon başarılı! {mesaj}")
            self.lbl_durum.setStyleSheet("color:#4ade80; font-size:12px; background:transparent;")
            QTimer.singleShot(1200, lambda: self.aktivasyon_basarili.emit(yetki))
            QTimer.singleShot(1200, self.accept)
        else:
            self.lbl_durum.setText(f"Hata: {mesaj}")
            self.lbl_durum.setStyleSheet("color:#f87171; font-size:12px; background:transparent;")
            self.btn_aktive.setEnabled(True)


GLOBAL_STYLESHEET = """
QWidget {
    background-color: #0f1117;
    color: #e0e0e0;
    font-family: "Segoe UI", system-ui, sans-serif;
}
QGroupBox {
    background-color: #1a1d2e;
    border: 1px solid #2a2d3e;
    border-radius: 6px;
    margin-top: 14px;
    font-weight: bold;
    color: #5b8cff;
}
QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 0 5px;
    left: 10px;
}
QPushButton {
    background-color: #222540;
    color: #e0e0e0;
    border: 1px solid #2a2d3e;
    border-radius: 6px;
    padding: 8px 14px;
    font-weight: bold;
}
QPushButton:hover {
    background-color: #2a2d3e;
    border-color: #5b8cff;
}
QPushButton:pressed {
    background-color: #1a1d2e;
}
QPushButton:disabled {
    background-color: #1e2033;
    color: #666666;
    border-color: #1e2033;
}
QLineEdit, QTextEdit {
    background-color: #0a0c14;
    border: 1px solid #2a2d3e;
    border-radius: 6px;
    color: #e0e0e0;
    padding: 6px;
}
QLineEdit:focus, QTextEdit:focus {
    border-color: #5b8cff;
}
QTableWidget {
    background-color: #0a0c14;
    color: #4ade80;
    font-family: Consolas, 'Courier New';
    font-size: 13px;
    border: 1px solid #2a2d3e;
    border-radius: 6px;
    gridline-color: #1a1d2e;
}
QHeaderView::section {
    background-color: #1a1d2e;
    color: #5b8cff;
    font-weight: bold;
    border: 1px solid #2a2d3e;
    padding: 4px;
}
QTableCornerButton::section {
    background-color: #1a1d2e;
    border: 1px solid #2a2d3e;
}
"""

# =====================================================================
# BÖLÜM 1: ASYNCUA ABONELİK YAKALAYICI
# =====================================================================
class SubscriptionHandler:
    """Sunucudan gelen anlık veri değişimlerini yakalar ve GUI'ye sinyal gönderir."""
    def __init__(self, veri_sinyali):
        self.veri_sinyali = veri_sinyali

    def datachange_notification(self, node, val, data):
        node_id = str(node.nodeid.Identifier)
        # Gelen zaman damgasını formatla
        ts = data.monitored_item.Value.ServerTimestamp
        ts_str = ts.strftime("%H:%M:%S.%f")[:-3] if ts else datetime.datetime.now().strftime("%H:%M:%S")
        self.veri_sinyali.emit(node_id, str(val), ts_str)

# =====================================================================
# BÖLÜM 2: OPC UA CLIENT MOTORU (ARKA PLAN)
# =====================================================================
class UaClientWorker(QThread):
    log_sinyali    = pyqtSignal(str)
    baglan_sinyali = pyqtSignal(bool)
    veri_sinyali   = pyqtSignal(str, str, str) # NodeID, Value, Timestamp

    def __init__(self, endpoint_url):
        super().__init__()
        self.endpoint_url = endpoint_url
        self._calisiyor = True
        self.client = None

    def _log(self, metin):
        self.log_sinyali.emit(str(metin))

    def run(self):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(self._istemci_dongusu())
        except Exception as e:
            self._log(f"İstemci Hatası: {e}")
            self.baglan_sinyali.emit(False)
        finally:
            loop.close()

    async def _istemci_dongusu(self):
        from asyncua import Client, ua
        self.client = Client(url=self.endpoint_url)
        try:
            self._log(f"Bağlanılıyor: {self.endpoint_url}")
            await self.client.connect()
            self.baglan_sinyali.emit(True)
            self._log("Bağlantı başarılı. Sadece 'Saha_Verileri' taranıyor...")

            degiskenler = []
            
            # 1. Sadece "Objects" ana dizinine git
            objects_node = self.client.nodes.objects
            cocuklar = await objects_node.get_children()
            
            # 2. İçerisinde sadece Gateway'in ürettiği "Saha_Verileri" klasörünü bul
            hedef_klasor = None
            for child in cocuklar:
                bname = await child.read_browse_name()
                if bname.Name == "Saha_Verileri":
                    hedef_klasor = child
                    break
                    
            # 3. Klasör bulunduysa, içindeki değişkenleri listeye al
            if hedef_klasor:
                klasor_icindekiler = await hedef_klasor.get_children()
                for item in klasor_icindekiler:
                    node_class = await item.read_node_class()
                    if node_class == ua.NodeClass.Variable:
                        degiskenler.append(item)
            
            if not degiskenler:
                self._log("Uyarı: Sunucuda 'Saha_Verileri' bulunamadı!")
                self._log("Lütfen Gateway programında yayının başlatıldığından emin olun.")
            else:
                self._log(f"{len(degiskenler)} adet özel etiket bulundu. Akış başlıyor...")
                # Sadece senin seçtiğin etiketlere abone ol
                handler = SubscriptionHandler(self.veri_sinyali)
                sub = await self.client.create_subscription(100, handler)
                await sub.subscribe_data_change(degiskenler)

            while self._calisiyor:
                await asyncio.sleep(1)

        except asyncio.CancelledError: 
            pass
        except Exception as e:
            self._log(f"Bağlantı koptu veya hata: {e}")
            self.baglan_sinyali.emit(False)
        finally:
            if self.client:
                try: 
                    await self.client.disconnect()
                except: 
                    pass
            self._log("Bağlantı kesildi.")

    def durdur(self):
        self._calisiyor = False
        self.client = None  # Client referansını hemen bırak

# =====================================================================
# BÖLÜM 3: ARAYÜZ TASARIMI
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

class ClientApp(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.worker = None
        self.etiket_satirlari = {} # NodeID -> Tablo Satır Indexi

        self.setWindowTitle("Nautilus Technology - OPC UA Viewer")
        self.resize(780, 600)
        self.setMinimumSize(780, 600)

        self.centralwidget = QtWidgets.QWidget(self)
        self.setCentralWidget(self.centralwidget)

        # 1. Bağlantı Paneli
        grp_baglanti = QtWidgets.QGroupBox("Sunucu Bağlantısı", self.centralwidget)
        grp_baglanti.setGeometry(20, 20, 740, 80)
        lay_baglanti = QtWidgets.QHBoxLayout(grp_baglanti)
        
        self.txt_url = QtWidgets.QLineEdit("opc.tcp://127.0.0.1:4840/")
        self.btn_baglan = QtWidgets.QPushButton("Bağlan")
        self.btn_baglan.setStyleSheet("background-color: #2e7d32; color: white; border: none;")
        self.btn_kes = QtWidgets.QPushButton("Bağlantıyı Kes")
        self.btn_kes.setStyleSheet("background-color: #c62828; color: white; border: none;")
        self.btn_kes.setEnabled(False)

        lay_baglanti.addWidget(QtWidgets.QLabel("Endpoint URL:"), 0)
        lay_baglanti.addWidget(self.txt_url, 1)
        lay_baglanti.addWidget(self.btn_baglan, 0)
        lay_baglanti.addWidget(self.btn_kes, 0)

        # 2. Canlı Veri Tablosu
        grp_veri = QtWidgets.QGroupBox("Canlı Saha Verileri", self.centralwidget)
        grp_veri.setGeometry(20, 110, 740, 300)
        lay_veri = QtWidgets.QVBoxLayout(grp_veri)
        
        self.tablo = QtWidgets.QTableWidget(0, 3)
        self.tablo.setHorizontalHeaderLabels(["Etiket (NodeID)", "Değer", "Son Güncelleme"])
        header = self.tablo.horizontalHeader()
        header.setSectionResizeMode(0, QtWidgets.QHeaderView.Stretch)
        header.setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeToContents)
        header.setSectionResizeMode(2, QtWidgets.QHeaderView.ResizeToContents)
        self.tablo.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.tablo.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        lay_veri.addWidget(self.tablo)

        # 3. Log Konsolu
        grp_log = QtWidgets.QGroupBox("Sistem Logları", self.centralwidget)
        grp_log.setGeometry(20, 420, 740, 160)
        lay_log = QtWidgets.QVBoxLayout(grp_log)
        self.txt_konsol = QtWidgets.QTextEdit()
        self.txt_konsol.setReadOnly(True)
        lay_log.addWidget(self.txt_konsol)

        self._log_koprusu = LogKoprusu(self.txt_konsol)

        # Sinyal Bağlantıları
        self.btn_baglan.clicked.connect(self._baglan)
        self.btn_kes.clicked.connect(self._kes)

        self._log("OPC UA Görüntüleyici hazır. Sunucu URL'sini girip bağlanın.")

    def _log(self, metin):
        self._log_koprusu.yaz(metin)

    def _baglan(self):
        url = self.txt_url.text().strip()
        if not url:
            return

        # Eski worker varsa önce düzgünce temizle
        if self.worker is not None:
            self._worker_baglantilari_kes(self.worker)
            if self.worker.isRunning():
                self.worker.durdur()
                self.worker.wait(3000)  # En fazla 3 sn bekle
            self.worker = None

        self.btn_baglan.setEnabled(False)
        self.btn_kes.setEnabled(False)
        self.txt_url.setEnabled(False)
        self.tablo.setRowCount(0)
        self.etiket_satirlari.clear()

        self.worker = UaClientWorker(url)
        self.worker.log_sinyali.connect(self._log)
        self.worker.baglan_sinyali.connect(self._baglanti_durumu)
        self.worker.veri_sinyali.connect(self._veri_guncelle)
        # Thread bittiğinde UI'yi sıfırla
        self.worker.finished.connect(self._worker_bitti)
        self.worker.start()

    def _worker_baglantilari_kes(self, worker):
        """Eski worker sinyallerini güvenli şekilde ayır."""
        try:
            worker.log_sinyali.disconnect(self._log)
        except Exception:
            pass
        try:
            worker.baglan_sinyali.disconnect(self._baglanti_durumu)
        except Exception:
            pass
        try:
            worker.veri_sinyali.disconnect(self._veri_guncelle)
        except Exception:
            pass
        try:
            worker.finished.disconnect(self._worker_bitti)
        except Exception:
            pass

    @QtCore.pyqtSlot()
    def _worker_bitti(self):
        """Thread tamamen kapanınca Bağlan butonunu tekrar aktifleştir."""
        self.btn_baglan.setEnabled(True)
        self.btn_kes.setEnabled(False)
        self.txt_url.setEnabled(True)
        self._log("Bağlantı tamamen sonlandırıldı. Tekrar bağlanabilirsiniz.")

    def _kes(self):
        if self.worker and self.worker.isRunning():
            self.worker.durdur()
            self.btn_kes.setEnabled(False)
            self.btn_baglan.setEnabled(False)  # Worker bitmeden tekrar bağlanmayı engelle
            self._log("Durdurma sinyali gönderildi, bağlantı kapatılıyor...")

    @QtCore.pyqtSlot(bool)
    def _baglanti_durumu(self, basarili):
        if basarili:
            self.btn_baglan.setEnabled(False)
            self.btn_kes.setEnabled(True)
        else:
            # Hata durumunda worker'ın finished sinyali zaten UI'yi sıfırlayacak
            self.btn_kes.setEnabled(False)

    @QtCore.pyqtSlot(str, str, str)
    def _veri_guncelle(self, node_id, deger, zaman):
        if node_id not in self.etiket_satirlari:
            # Yeni bir etiket geldiyse tabloya satır ekle
            row_idx = self.tablo.rowCount()
            self.tablo.insertRow(row_idx)
            
            item_node = QtWidgets.QTableWidgetItem(node_id)
            item_val = QtWidgets.QTableWidgetItem(deger)
            item_time = QtWidgets.QTableWidgetItem(zaman)
            
            # Değer hücrelerini ortala
            item_val.setTextAlignment(Qt.AlignCenter)
            item_time.setTextAlignment(Qt.AlignCenter)

            self.tablo.setItem(row_idx, 0, item_node)
            self.tablo.setItem(row_idx, 1, item_val)
            self.tablo.setItem(row_idx, 2, item_time)
            
            self.etiket_satirlari[node_id] = row_idx
        else:
            # Etiket zaten varsa sadece Değer ve Zaman hücrelerini güncelle
            row_idx = self.etiket_satirlari[node_id]
            self.tablo.item(row_idx, 1).setText(deger)
            self.tablo.item(row_idx, 2).setText(zaman)

    def closeEvent(self, event):
        if self.worker and self.worker.isRunning():
            self._worker_baglantilari_kes(self.worker)
            self.worker.durdur()
            self.worker.wait(3000)
        event.accept()

# =====================================================================
# BÖLÜM 4: UYGULAMA GİRİŞİ (Hibrit: Online önce, yoksa Offline)
# =====================================================================

def internet_var_mi() -> bool:
    """Sunucuya kısa bir istek atar; başarılıysa True döner."""
    try:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode    = ssl.CERT_NONE
        urllib.request.urlopen(SUNUCU_URL, context=ctx, timeout=4)
        return True
    except Exception:
        return False


def _offline_akis(app):
    """İnternet yoksa offline lisans akışını yönetir."""
    oly = OfflineLisansYoneticisi()

    # Splash
    splash = QtWidgets.QDialog()
    splash.setWindowTitle("OPC UA Viewer - Lisans Kontrolu")
    splash.setFixedSize(340, 80)
    splash.setWindowFlag(Qt.WindowContextHelpButtonHint, False)
    lbl_s = QtWidgets.QLabel("Çevrimdışı lisans kontrol ediliyor...", splash)
    lbl_s.setAlignment(Qt.AlignCenter)
    lbl_s.setGeometry(0, 0, 340, 80)
    splash.show()
    app.processEvents()

    durum, yetki = oly.dogrula()
    splash.hide()

    if durum == "saat_geri":
        QMessageBox.warning(
            None, "Güvenlik Uyarısı - Sistem Saati",
            "Güvenlik İhlali: Sistem saati geriye alınmış veya hatalı!\n\n"
            "Lütfen bilgisayarınızın saatini güncelleyip\n"
            "(internetten eşitleyip) programı tekrar başlatın.\n\n"
            "Kalan lisans süreniz güvendedir."
        )
        sys.exit(0)

    elif durum == "aktivasyon":
        aktiv = OfflineAktivasyonPenceresi(oly)
        aktiv.setStyleSheet(GLOBAL_STYLESHEET)
        if aktiv.exec_() != QDialog.Accepted:
            sys.exit(0)
        # Aktivasyon sonrası tekrar doğrula
        durum, yetki = oly.dogrula()
        if durum != "gecerli":
            QMessageBox.critical(None, "Lisans Hatası",
                                 durum.replace("hata:", ""))
            sys.exit(1)

    elif durum.startswith("hata:"):
        QMessageBox.critical(None, "Lisans Hatası",
                             durum.replace("hata:", ""))
        sys.exit(1)

    # Offline modda sadece görüntüleyici aç
    pencere = ClientApp()
    pencere.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    import multiprocessing
    multiprocessing.freeze_support()

    app = QtWidgets.QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setStyleSheet(GLOBAL_STYLESHEET)

    # ── İnternet kontrolü (Hibrit Başlatma Akışı) ──────────────────────
    splash = QtWidgets.QDialog()
    splash.setWindowTitle("OPC UA Viewer - Baslatiliyor")
    splash.setFixedSize(300, 80)
    splash.setWindowFlag(Qt.WindowContextHelpButtonHint, False)
    lbl = QtWidgets.QLabel("Baglanti kontrol ediliyor...", splash)
    lbl.setAlignment(Qt.AlignCenter)
    lbl.setGeometry(0, 0, 300, 80)
    splash.show()
    app.processEvents()

    bagli = internet_var_mi()
    splash.hide()

    if not bagli:
        # ══ OFFLİNE AKIŞ ══ (OfflineLisansYoneticisi devreye girer)
        _offline_akis(app)
        # _offline_akis içinde sys.exit çağrılır; buraya düşmez

    # ══ ONLINE AKIŞ ══ (LisansYoneticisi devreye girer)
    ly = LisansYoneticisi()

    splash_dlg = QtWidgets.QDialog()
    splash_dlg.setWindowTitle("OPC UA Viewer - Lisans Kontrolu")
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
        aktiv_pencere.setStyleSheet(GLOBAL_STYLESHEET)
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

    pencere = ClientApp()
    pencere.show()
    sys.exit(app.exec_())