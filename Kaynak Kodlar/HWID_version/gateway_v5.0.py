# -*- coding: utf-8 -*-
"""
OPC DA - OPC UA Gateway v4.1
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
import heapq
import hmac
import base64
import struct
import winreg
import ctypes

if __name__ == '__main__':
    multiprocessing.freeze_support()

# =====================================================================
# YAPILANDIRMA
# =====================================================================
SUNUCU_URL       = "https://web-production-b5bbc.up.railway.app"
UYGULAMA_SIFRESI = "admin1234"
LISANS_DOSYASI   = os.path.join(os.getenv("APPDATA", ""), "OPCGateway", "gateway_lisans.json")
CHECKIN_ARALIK   = 7
VERSIYON         = "4.1"
URUN_TIPI        = "gateway"  # Ürün izolasyonu: bu değer lisans imzasına ve API isteklerine dahil edilir

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
QLineEdit, QComboBox, QListWidget, QTextEdit {
    background-color: #0a0c14;
    border: 1px solid #2a2d3e;
    border-radius: 6px;
    color: #e0e0e0;
    padding: 6px;
}
QLineEdit:focus, QComboBox:focus, QListWidget:focus, QTextEdit:focus {
    border-color: #5b8cff;
}
QListWidget::item:selected {
    background-color: #5b8cff;
    color: white;
    border-radius: 4px;
}
QScrollBar:vertical {
    border: none;
    background: transparent;
    width: 10px;
    margin: 0;
}
QScrollBar::handle:vertical {
    background: #2a2d3e;
    min-height: 20px;
    border-radius: 5px;
}
QScrollBar::handle:vertical:hover {
    background: #3a3d4e;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}
QScrollBar:horizontal {
    border: none;
    background: transparent;
    height: 10px;
    margin: 0;
}
QScrollBar::handle:horizontal {
    background: #2a2d3e;
    min-width: 20px;
    border-radius: 5px;
}
QScrollBar::handle:horizontal:hover {
    background: #3a3d4e;
}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
    width: 0px;
}
"""

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
# BÖLÜM 0.5: OFFLİNE LİSANS ALTYAPISI (Mevcut online sisteme dokunulmaz)
# =====================================================================

# --- Gömülü Offline Anahtar (parçalara bölünmüş, runtime'da birleştirilir) ---
_SK_P1 = bytes([0x4f, 0x50, 0x43, 0x5f, 0x47, 0x57, 0x5f, 0x4f])
_SK_P2 = bytes([0x46, 0x46, 0x4c, 0x49, 0x4e, 0x45, 0x5f, 0x4b])
_SK_P3 = hashlib.sha256(b"opcgw_offline_2026_salt_v1").digest()[:16]
OFFLINE_SECRET_KEY = _SK_P1 + _SK_P2 + _SK_P3

OFFLINE_LISANS_DOSYASI = os.path.join(os.getenv("APPDATA", ""), "OPCGateway", "gateway_offline_lisans.dat")
OFFLINE_BURNIN_DOSYASI = os.path.join(os.getenv("APPDATA", ""), "OPCGateway", "gateway_burnin.dat")
OFFLINE_REG_PATH      = r"Software\OPCGateway\GatewayOfflineLicense"  # Viewer'dan ayrı
OFFLINE_MAX_GUN       = 365


def _debugger_kontrol():
    """IsDebuggerPresent ile anlık debugger tespiti — tespit edilirse anında çık."""
    try:
        if ctypes.windll.kernel32.IsDebuggerPresent():
            os.abort()
    except Exception:
        pass


class OfflineHwidUretici:
    """
    Anti-Spoofing HWID:
    Anakart Seri No + Disk Volume Serial + MachineGuid → HMAC-SHA256 → hwid_hash
    """

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
    """Tek kullanımlık, zaman damgalı istek kodu. Her tıklamada 10-dk penceresi değişir."""

    @staticmethod
    def uret(hwid_hash: str) -> str:
        ts_slot = int(time.time()) // 600  # 10 dakikalık dilim
        raw = hwid_hash[:8].encode("ascii") + struct.pack(">Q", ts_slot)
        b32 = base64.b32encode(raw).decode().rstrip("=")
        return f"REQ-{b32[:20]}"

    @staticmethod
    def gecerli_slotlar() -> list:
        now = int(time.time()) // 600
        return [now - 1, now, now + 1]


class OfflineLisansYoneticisi:
    """
    Çevrimdışı lisans yönetimi:
    • XOR şifreli yerel dosya + Registry çift kayıt
    • Burn-in (tek kullanımlık şifre) koruma
    • Zaman hilesi tespiti (takvim geri alma + GetTickCount64)
    • HMAC-SHA256 imza doğrulaması
    """

    def __init__(self):
        self.hwid_hash = OfflineHwidUretici.uret()
        os.makedirs(os.path.dirname(OFFLINE_LISANS_DOSYASI), exist_ok=True)

    # ── XOR şifreleme (simetrik, anahtar OFFLINE_SECRET_KEY'den türetilmiş) ──

    @staticmethod
    def _sifrele(veri: bytes) -> bytes:
        key = hashlib.sha256(OFFLINE_SECRET_KEY + b"xor_v1").digest()
        ks  = (key * (len(veri) // 32 + 1))[:len(veri)]
        return bytes(a ^ b for a, b in zip(veri, ks))

    @staticmethod
    def _coz(veri: bytes) -> bytes:
        return OfflineLisansYoneticisi._sifrele(veri)  # XOR simetriktir

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

    # ── Registry çift kayıt ──

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

    # ── Saat geri kontrolü (Soft-Lock) ──

    @staticmethod
    def _saat_geri_mi(son_giris_ts: float) -> bool:
        """Sistem saati son kayıtlı girişten 30 saniyeden fazla geriye alındıysa True döner.
        Tespit edildiğinde dosyaya DOKUNULMAZ; sadece geçici uyarı gösterilir."""
        now = time.time()
        if now < son_giris_ts - 30:   # Takvim/saat geriye alındı
            return True
        return False

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

        # HMAC imza doğrulama (URUN_TIPI prefix ile ürün izolasyonu sağlanır)
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
        durum: 'gecerli' | 'aktivasyon' | 'saat_geri' | 'hata:...'

        NOT: 'tampered' (kalıcı kilit) artık KULLANILMAZ.
        Saat geriye alınmışsa yalnızca 'saat_geri' döner; lisans dosyasına
        dokunulmaz. Saat düzeltilince program kaldığı yerden devam eder.
        """
        _debugger_kontrol()

        lisans     = self._lisans_oku()
        reg_lisans = self._registry_oku()

        if not lisans:
            return "aktivasyon", ""

        # Geçiş uyumluluğu: eski sürümlerde 'tampered' alanı kalıcı kilitleme yapıyordu.
        # Yeni soft-lock mimarisinde bu alan anlamlı değil; varsa temizle ve devam et.
        if lisans.get("tampered"):
            lisans.pop("tampered", None)
            lisans.pop("tampered_ts", None)
            self._lisans_kaydet(lisans)

        # Registry vs dosya tutarlılık — uyumsuzlukta dosyaya dokunmadan hata dön
        if reg_lisans:
            if reg_lisans.get("hwid_hash") != lisans.get("hwid_hash"):
                return "hata:Lisans kaydında tutarsızlık tespit edildi. Lütfen satıcıyla iletişime geçin.", ""
            if reg_lisans.get("imza") != lisans.get("imza"):
                return "hata:Lisans kaydında tutarsızlık tespit edildi. Lütfen satıcıyla iletişime geçin.", ""

        # HWID eşleşmesi
        if lisans.get("hwid_hash") != self.hwid_hash:
            self._lisans_sil()
            return "hata:Bu offline lisans başka bir bilgisayara aittir.", ""

        # ── Saat geri kontrolü (Soft-Lock) ──
        # Tespit edilirse dosyaya DOKUNULMAZ; kullanıcı saati düzeltince devam eder.
        if self._saat_geri_mi(lisans.get("son_giris_ts", 0)):
            return "saat_geri", ""

        # Süre kontrolü — yalnızca bitis_ts geçtiyse lisans dolmuş sayılır
        if time.time() > lisans.get("bitis_ts", 0):
            self._lisans_sil()
            return "hata:Offline lisans süreniz dolmuştur.", ""

        # İmza bütünlük kontrolü — uyumsuzlukta dosyaya dokunmadan hata dön
        imza = lisans.get("imza", "")
        if not imza or len(imza) != 16:
            return "hata:Lisans imzası geçersiz. Lütfen satıcıyla iletişime geçin.", ""

        # Son girişi güncelle (sadece doğrulama başarılıysa)
        lisans["son_giris_ts"] = time.time()
        self._lisans_kaydet(lisans)

        return "gecerli", lisans.get("yetki", "FULL")

    def lisans_bilgisi(self):
        return self._lisans_oku()


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
                "urun": URUN_TIPI,  # Ürün izolasyonu: periyodik kontrol isteğine ürün tipi eklendi
            })

            if not basari:
                # Sunucuya ulaşılamadı (offline)
                # → Yerel bitis_tarihi kontrolü yap
                self._son_bagli = False
                bitis = lisans.get("bitis_tarihi", "")
                if bitis:
                    try:
                        bitis_dt = datetime.datetime.fromisoformat(bitis)
                        if datetime.datetime.now() > bitis_dt:
                            # Süre dolmuş, offline olsa bile lisansı iptal et
                            self.ly._lisans_sil()
                            self.lisans_iptal_edildi.emit()
                            return
                    except Exception:
                        pass
                # Süre dolmamış → 10 sn'de bir tekrar dene
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
            "urun": URUN_TIPI,  # Ürün izolasyonu: hangi ürün için aktivasyon yapıldığını bildirir
        })

        if basari and yanit.get("basarili"):
            self._lisans_kaydet({
                "lisans_kodu": lisans_kodu.strip().upper(),
                "hwid": self.hwid,
                "urun": URUN_TIPI,  # Ürün tipi lisans dosyasına kaydedilir
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

        # Ürün izolasyonu: lisans başka bir ürüne aitse reddet
        if lisans.get("urun") and lisans.get("urun") != URUN_TIPI:
            self._lisans_sil()
            return f"hata:Bu lisans '{lisans.get('urun')}' ürününe aittir, '{URUN_TIPI}' için kullanilamaz."

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
            "urun": URUN_TIPI,  # Ürün izolasyonu: kontrol isteğine ürün tipi eklendi
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
        lbl_baslik.setStyleSheet("font-size: 16px; font-weight: bold; color: #5b8cff; background: transparent;")
        lbl_baslik.setAlignment(Qt.AlignCenter)
        layout.addWidget(lbl_baslik)

        hwid_frame = QtWidgets.QFrame()
        hwid_frame.setStyleSheet(
            "background: #1a1d2e; border: 1px solid #2a2d3e; "
            "border-radius: 6px; padding: 8px;"
        )
        hwid_layout = QtWidgets.QVBoxLayout(hwid_frame)
        hwid_layout.setSpacing(4)

        lbl_hwid_acik = QtWidgets.QLabel("Bu bilgisayarin donanum kimligi (HWID):")
        lbl_hwid_acik.setStyleSheet("font-size: 11px; color: #8a9bc0; background: transparent;")

        self.lbl_hwid = QtWidgets.QLabel(self.ly.hwid)
        self.lbl_hwid.setStyleSheet(
            "font-family: Consolas, monospace; font-size: 13px; "
            "font-weight: bold; color: #7eb8ff; letter-spacing: 1px; background: transparent; border: none;"
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
        lbl_kod.setStyleSheet("font-size: 12px; background: transparent;")
        layout.addWidget(lbl_kod)

        self.txt_kod = QtWidgets.QLineEdit()
        self.txt_kod.setPlaceholderText("AYL-XXXX-XXXX-XXXX")
        self.txt_kod.setFixedHeight(36)
        self.txt_kod.setStyleSheet(
            "font-family: Consolas; font-size: 14px; letter-spacing: 2px; "
            "background: #0a0c14; border: 1px solid #2a2d3e; border-radius: 6px; padding: 0 8px; color: #e0e0e0;"
        )
        layout.addWidget(self.txt_kod)

        self.lbl_durum = QtWidgets.QLabel("")
        self.lbl_durum.setAlignment(Qt.AlignCenter)
        self.lbl_durum.setStyleSheet("font-size: 12px; background: transparent;")
        self.lbl_durum.setWordWrap(True)
        self.lbl_durum.setMinimumHeight(36)
        layout.addWidget(self.lbl_durum)

        self.btn_aktive = QtWidgets.QPushButton("Aktive Et")
        self.btn_aktive.setFixedHeight(40)
        self.btn_aktive.setStyleSheet("""
            QPushButton {
                background-color: #5b8cff; color: white; font-size: 14px; 
                font-weight: bold; border-radius: 6px; border: none;
            }
            QPushButton:hover { background-color: #4a7aff; }
            QPushButton:disabled { background-color: #1e2033; color: #666; }
        """)
        self.btn_aktive.clicked.connect(self._aktive_et)
        layout.addWidget(self.btn_aktive)

        self.txt_kod.returnPressed.connect(self._aktive_et)

    def _hwid_kopyala(self):
        QtWidgets.QApplication.clipboard().setText(self.ly.hwid)
        self.lbl_durum.setText("HWID panoya kopyalandi.")
        self.lbl_durum.setStyleSheet("color: #4ade80; font-size: 12px; background: transparent;")

    def _aktive_et(self):
        kod = self.txt_kod.text().strip()
        if not kod:
            self.lbl_durum.setText("Lutfen lisans kodunu girin.")
            self.lbl_durum.setStyleSheet("color: #f87171; font-size: 12px; background: transparent;")
            return

        self.btn_aktive.setEnabled(False)
        self.lbl_durum.setText("Sunucuya baglaniliyor...")
        self.lbl_durum.setStyleSheet("color: #f59e0b; font-size: 12px; background: transparent;")
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
            self.lbl_durum.setStyleSheet("color: #4ade80; font-size: 12px; background: transparent;")
            QTimer.singleShot(1200, self.aktivasyon_basarili.emit)
            QTimer.singleShot(1200, self.accept)
        else:
            self.lbl_durum.setText(f"Hata: {mesaj}")
            self.lbl_durum.setStyleSheet("color: #f87171; font-size: 12px; background: transparent;")
            self.btn_aktive.setEnabled(True)


# =====================================================================
# BÖLÜM 2.5: OFFLİNE AKTİVASYON PENCERESİ
# =====================================================================
class OfflineAktivasyonPenceresi(QDialog):
    aktivasyon_basarili = pyqtSignal(str)   # yetki seviyesini taşır

    def __init__(self, offline_ly: OfflineLisansYoneticisi):
        super().__init__()
        self.oly = offline_ly
        self._guncel_challenge = ""
        self.setWindowTitle("OPC Gateway — Çevrimdışı Aktivasyon")
        self.setFixedSize(540, 500)
        self.setWindowFlag(Qt.WindowContextHelpButtonHint, False)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(26, 20, 26, 20)

        # — Başlık —
        lbl_baslik = QtWidgets.QLabel("🔒  Çevrimdışı (Air-Gapped) Aktivasyon")
        lbl_baslik.setStyleSheet(
            "font-size:15px; font-weight:bold; color:#e65100;"
            "background:transparent;"
        )
        lbl_baslik.setAlignment(Qt.AlignCenter)
        layout.addWidget(lbl_baslik)

        lbl_acik = QtWidgets.QLabel(
            "İnternet bağlantısı tespit edilmedi.\n"
            "Satıcıdan aldığınız aktivasyon kodunu girin."
        )
        lbl_acik.setStyleSheet("font-size:11px; color:#8a9bc0; background:transparent;")
        lbl_acik.setAlignment(Qt.AlignCenter)
        layout.addWidget(lbl_acik)

        # — HWID Hash —
        hwid_frame = QtWidgets.QFrame()
        hwid_frame.setStyleSheet(
            "background:#1a1d2e; border:1px solid #2a2d3e; border-radius:6px;"
        )
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
        btn_hwid_kopyala.clicked.connect(
            lambda: QtWidgets.QApplication.clipboard().setText(self.oly.hwid_hash)
        )

        hwid_lay.addWidget(lbl_hw_t)
        hwid_lay.addWidget(self.lbl_hwid)
        hwid_lay.addWidget(btn_hwid_kopyala, alignment=Qt.AlignRight)
        layout.addWidget(hwid_frame)

        # — İstek Kodu (Challenge) —
        ch_frame = QtWidgets.QFrame()
        ch_frame.setStyleSheet(
            "background:#1a1d2e; border:1px solid #2a2d3e; border-radius:6px;"
        )
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
            QPushButton {
                background:#5b8cff; color:white; border:none;
                border-radius:5px; font-size:12px; font-weight:bold;
            }
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

        # — Aktivasyon Kodu girişi —
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

        # — Durum mesajı —
        self.lbl_durum = QtWidgets.QLabel("")
        self.lbl_durum.setAlignment(Qt.AlignCenter)
        self.lbl_durum.setWordWrap(True)
        self.lbl_durum.setMinimumHeight(32)
        self.lbl_durum.setStyleSheet("font-size:12px; background:transparent;")
        layout.addWidget(self.lbl_durum)

        # — Aktive Et butonu —
        self.btn_aktive = QtWidgets.QPushButton("✔  Aktive Et")
        self.btn_aktive.setFixedHeight(42)
        self.btn_aktive.setStyleSheet("""
            QPushButton {
                background:#2e7d32; color:white; font-size:14px;
                font-weight:bold; border-radius:6px; border:none;
            }
            QPushButton:hover { background:#1b5e20; }
            QPushButton:disabled { background:#1e2033; color:#666; }
        """)
        self.btn_aktive.clicked.connect(self._aktive_et)
        layout.addWidget(self.btn_aktive)

        self.txt_act.returnPressed.connect(self._aktive_et)

    # ── Challenge üret ──
    def _challenge_uret(self):
        ch = ChallengeUretici.uret(self.oly.hwid_hash)
        self._guncel_challenge = ch
        self.lbl_challenge.setText(ch)
        self.btn_ch_kopyala.setEnabled(True)
        self.lbl_durum.setText("İstek kodu üretildi. Satıcıya gönderin.")
        self.lbl_durum.setStyleSheet("color:#4ade80; font-size:11px; background:transparent;")

    # ── Aktivasyon ──
    def _aktive_et(self):
        act = self.txt_act.text().strip()
        if not act:
            self._durum_hata("Lütfen aktivasyon kodunu girin.")
            return
        if not self._guncel_challenge:
            self._durum_hata("Önce 'İstek Kodu Üret' butonuna basın.")
            return

        self.btn_aktive.setEnabled(False)
        self.lbl_durum.setText("Doğrulanıyor...")
        self.lbl_durum.setStyleSheet("color:#f59e0b; font-size:12px; background:transparent;")
        QtWidgets.QApplication.processEvents()

        def islem():
            basari, mesaj, yetki, sure_gun = self.oly.aktive_et(
                act, self._guncel_challenge
            )
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
            self.lbl_durum.setText(f"✅  {mesaj}")
            self.lbl_durum.setStyleSheet("color:#4ade80; font-size:12px; background:transparent;")
            QTimer.singleShot(1000, lambda: self.aktivasyon_basarili.emit(yetki))
            QTimer.singleShot(1000, self.accept)
        else:
            self._durum_hata(mesaj)
            self.btn_aktive.setEnabled(True)

    def _durum_hata(self, mesaj):
        self.lbl_durum.setText(f"❌  {mesaj}")
        self.lbl_durum.setStyleSheet("color:#f87171; font-size:12px; background:transparent;")


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
        self.btn_baslat.setStyleSheet("""
            QPushButton {
                background-color: #2e7d32; color: white; font-weight: bold; border-radius: 6px; padding: 6px; border: none;
            }
            QPushButton:hover { background-color: #1b5e20; }
            QPushButton:disabled { background-color: #1e2033; color: #666; }
        """)
        self.btn_durdur = QtWidgets.QPushButton("Durdur")
        self.btn_durdur.setStyleSheet("""
            QPushButton {
                background-color: #c62828; color: white; font-weight: bold; border-radius: 6px; padding: 6px; border: none;
            }
            QPushButton:hover { background-color: #b71c1c; }
            QPushButton:disabled { background-color: #1e2033; color: #666; }
        """)
        self.btn_durdur.setEnabled(False)
        lay_baslat.addRow("Yayin IP:", self.txt_ip)
        lay_baslat.addRow("Port:", self.txt_port)
        lay_baslat.addRow(self.btn_baslat)
        lay_baslat.addRow(self.btn_durdur)

        grp_alt = QtWidgets.QGroupBox("", self.centralwidget)
        grp_alt.setGeometry(20, 120, 220, 60)
        grp_alt.setStyleSheet("border: none; background: transparent;")
        lay_alt = QtWidgets.QHBoxLayout(grp_alt)
        self.btn_kurulum_ac = QtWidgets.QPushButton("Sistem Kurulum Merkezi")
        self.btn_kurulum_ac.setStyleSheet("""
            QPushButton {
                background-color: #5b8cff; color: white; font-weight: bold; padding: 8px; border-radius: 6px; border: none;
            }
            QPushButton:hover { background-color: #4a7aff; }
        """)
        lay_alt.addWidget(self.btn_kurulum_ac)

        self.lbl_lisans = QtWidgets.QLabel("")
        self.lbl_lisans.setGeometry(20, 183, 780, 20)
        self.lbl_lisans.setParent(self.centralwidget)
        self.lbl_lisans.setStyleSheet("color: #8a9bc0; font-size: 11px; background: transparent;")
        self.lbl_lisans.setAlignment(Qt.AlignRight)

        grp_konsol = QtWidgets.QGroupBox("Canli Veri / Log Ekrani", self.centralwidget)
        grp_konsol.setGeometry(20, 205, 780, 425)
        lay_konsol = QtWidgets.QVBoxLayout(grp_konsol)
        self.txt_konsol = QtWidgets.QTextEdit()
        self.txt_konsol.setReadOnly(True)
        self.txt_konsol.setStyleSheet(
            "background: #0a0c14; color: #4ade80; "
            "font-family: Consolas, 'Courier New'; font-size: 12px; border: 1px solid #2a2d3e; border-radius: 6px;"
        )
        lay_konsol.addWidget(self.txt_konsol)

        # ── Tepsiye Küçült butonu (sağ üst köşe) ──
        self.btn_tepsi = QtWidgets.QPushButton("⬇  Tepsiye Küçült", self.centralwidget)
        self.btn_tepsi.setGeometry(660, 4, 150, 26)
        self.btn_tepsi.setStyleSheet("""
            QPushButton {
                background-color: #1a1d2e;
                color: #8a9bc0;
                border: 1px solid #2a2d3e;
                border-radius: 5px;
                font-size: 11px;
                padding: 0 6px;
            }
            QPushButton:hover {
                background-color: #222540;
                color: #5b8cff;
                border-color: #5b8cff;
            }
        """)

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
            self.lbl_mimari.setStyleSheet("color: #f59e0b; font-weight: bold; padding: 4px; background: transparent;")
        else:
            self.lbl_mimari.setText("32-Bit Python -- OPC DA uyumlu.")
            self.lbl_mimari.setStyleSheet("color: #4ade80; font-weight: bold; padding: 4px; background: transparent;")
        layout.addWidget(self.lbl_mimari)

        self.adimlar = [
            ("0. Python 3.13 (32-bit) Indir & Kur", self.python_indir_ve_kur, "#5b8cff", "#4a7aff"),
            ("1. Kutuphaneleri Kur (PIP)",            self.kutuphaneleri_kur,  "#5b8cff", "#4a7aff"),
            ("2. Windows DLL'lerini Kaydet",          self.dll_kaydet,         "#5b8cff", "#4a7aff"),
        ]
        self.durum_lbller = []
        for metin, slot, renk, hover_renk in self.adimlar:
            h = QtWidgets.QHBoxLayout()
            btn = QtWidgets.QPushButton(metin)
            btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {renk}; color: white; font-weight: bold; padding: 8px; border-radius: 6px; border: none;
                }}
                QPushButton:hover {{ background-color: {hover_renk}; }}
            """)
            btn.clicked.connect(slot)
            lbl = QtWidgets.QLabel("Bekliyor")
            lbl.setStyleSheet("color: #8a9bc0; min-width: 120px; background: transparent;")
            lbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.durum_lbller.append(lbl)
            h.addWidget(btn, stretch=3)
            h.addWidget(lbl, stretch=1)
            layout.addLayout(h)

        self.kurulum_log = QtWidgets.QTextEdit()
        self.kurulum_log.setReadOnly(True)
        self.kurulum_log.setStyleSheet("background-color: #0a0c14; color: #e0e0e0; font-family: Consolas; border: 1px solid #2a2d3e; border-radius: 6px; padding: 4px;")
        layout.addWidget(self.kurulum_log)
        self._kendi_log = LogKoprusu(self.kurulum_log)

    def _log(self, metin):
        self._kendi_log.yaz(metin)

    def _durum_guncelle(self, idx, metin, renk):
        if renk == "orange": renk = "#f59e0b"
        elif renk == "green": renk = "#4ade80"
        elif renk == "red": renk = "#f87171"
        QtCore.QMetaObject.invokeMethod(
            self.durum_lbller[idx], "setText",
            Qt.QueuedConnection, QtCore.Q_ARG(str, metin))
        QtCore.QMetaObject.invokeMethod(
            self.durum_lbller[idx], "setStyleSheet",
            Qt.QueuedConnection, QtCore.Q_ARG(str, f"color: {renk}; font-weight: bold; background: transparent;"))

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

    def __init__(self, prog_id, ip, port, etiketler, yetki="FULL"): # yetki eklendi
        super().__init__()
        self.prog_id    = prog_id
        self.ip         = ip
        self.port       = port
        self.etiketler  = etiketler
        self.yetki      = yetki # yetki kaydedildi
        self._calisıyor = True
        # Optional CSV logging path (None = disabled)
        self.csv_path = None
        # Performance tuning knobs (STA-safe: single COM worker stays unchanged)
        self.read_timeout_sec = 1.8
        self.chunk_read_timeout_sec = 0.8
        self.chunk_size = 30
        self.verbose_data_log = False
        self._last_read_stats = {}

    def _log(self, metin):
        self.log_sinyali.emit(str(metin))

    async def _toplu_oku(self, etiket_listesi):
        """
        Robust bulk read helper using a dedicated single-thread executor
        for OpenOPC COM calls. This ensures all COM interactions happen on
        the same thread where the client was created (mitigates DCOM/COM
        threading issues that cause "poisoned" connections).
        """
        import functools

        sonuclar = {}
        loop = asyncio.get_running_loop()
        executor = getattr(self, "_opc_executor", None)

        # local reference to current client (may be replaced on reconnect)
        opc = getattr(self, "_opc", None)

        def _flatten(v):
            while isinstance(v, (list, tuple)) and v:
                v = v[0]
            return v

        def _normalize_read(et, rec):
            """
            Normalize OpenOPC read outputs.
            Supports both:
              - single tag tuple: (value, quality, timestamp)
              - bulk tag tuple:   (tag, value, quality, timestamp)
            """
            try:
                if not rec:
                    return (None, None, None)
                if isinstance(rec, (list, tuple)):
                    if len(rec) >= 4 and isinstance(rec[0], str) and rec[0].strip() == et.strip():
                        val = _flatten(rec[1])
                        return (val, rec[2], str(rec[3]))
                    val = _flatten(rec[0])
                    qual = rec[1] if len(rec) > 1 else None
                    ts = str(rec[2]) if len(rec) > 2 else str(qual)
                    return (val, qual, ts)
                return (_flatten(rec), "Good", "N/A")
            except Exception:
                return (None, None, None)

        def _set_read_stats(local_mode, local_timeouts):
            self._last_read_stats = {
                "mode": local_mode,
                "timeouts": local_timeouts,
                "elapsed_ms": int((time.monotonic() - read_started) * 1000),
                "tag_count": len(etiket_listesi),
            }

        # timing + diagnostics
        read_started = time.monotonic()
        timeout_count = 0
        mode = "bulk"

        # 1) Try one-shot bulk read in the OPC executor (fastest when supported)
        ham = None
        try:
            if opc is not None:
                ham = await asyncio.wait_for(
                    loop.run_in_executor(executor, opc.read, etiket_listesi),
                    timeout=self.read_timeout_sec
                )
        except asyncio.TimeoutError:
            timeout_count += 1
            ham = None
        except Exception:
            ham = None

        # If we got a list, inspect for excessive missing values (poisoned connection)
        try:
            if ham and isinstance(ham, list):
                missing = sum(1 for v in ham if (not v) or v[0] is None)
                # If a large portion of the bulk read is missing, assume connection
                # was poisoned and try to recreate the client once (in the same executor)
                if missing and missing >= max(1, len(ham) // 2):
                    try:
                        await loop.run_in_executor(executor, getattr(opc, "close", lambda: None))
                    except Exception:
                        pass
                    try:
                        def _recreate():
                            try:
                                import pythoncom as _pythoncom
                                _pythoncom.CoInitialize()
                            except Exception:
                                pass
                            import OpenOPC as _OpenOPC
                            c = _OpenOPC.client()
                            c.connect(self.prog_id)
                            return c

                        new_opc = await loop.run_in_executor(executor, _recreate)
                        self._opc = new_opc
                        opc = new_opc
                        self._log("OPC bağlantısı yeniden kuruldu (yeniden deneme).")
                        # try bulk read again once
                        try:
                            ham = await asyncio.wait_for(
                                loop.run_in_executor(executor, opc.read, etiket_listesi),
                                timeout=self.read_timeout_sec
                            )
                        except asyncio.TimeoutError:
                            timeout_count += 1
                            ham = None
                        except Exception:
                            ham = None
                        await asyncio.sleep(0.2)
                    except Exception:
                        ham = None

            # If bulk read returned usable data, normalize and return
            if ham and isinstance(ham, list):
                for et, veri in zip(etiket_listesi, ham):
                    try:
                        nval, nqual, nts = _normalize_read(et, veri)
                        if nval is not None:
                            raw_val = nval

                            # If the server returned the tag name as the value
                            # (e.g. 'Random.Real8'), try a quick per-tag reread
                            # in the same executor to obtain the real value.
                            if isinstance(raw_val, str) and raw_val.strip() == et.strip() and executor is not None and opc is not None:
                                try:
                                    retry = await loop.run_in_executor(executor, opc.read, et)
                                    rval, rqual, rts = _normalize_read(et, retry)
                                    if rval is not None:
                                        if not (isinstance(rval, str) and rval.strip() == et.strip()):
                                            sonuclar[et] = (rval, rqual, rts)
                                            continue
                                except Exception:
                                    pass

                            sonuclar[et] = (raw_val, nqual, nts)
                        else:
                            sonuclar[et] = (None, None, None)
                    except Exception:
                        sonuclar[et] = (None, None, None)
                _set_read_stats(mode, timeout_count)
                return sonuclar
        except Exception:
            # fall through to per-tag reads on any unexpected error
            pass

        # 2) Fallback: split-and-read.
        # If a group fails as bulk, split it and retry; isolate bad tags instead of
        # dropping to per-tag for the whole batch.
        mode = "split_fallback"
        client = getattr(self, "_opc", opc)
        if client is None:
            for et in etiket_listesi:
                sonuclar[et] = (None, None, None)
            _set_read_stats(mode, timeout_count)
            return sonuclar

        def _group_timeout(n):
            return max(0.25, min(2.5, 0.10 + 0.035 * max(1, int(n))))

        pending = [list(etiket_listesi)]
        while pending:
            group = pending.pop(0)
            if not group:
                continue
            try:
                res = await asyncio.wait_for(
                    loop.run_in_executor(executor, client.read, group),
                    timeout=_group_timeout(len(group))
                )
                if isinstance(res, list) and len(res) == len(group):
                    for et, veri in zip(group, res):
                        nval, nqual, nts = _normalize_read(et, veri)
                        sonuclar[et] = (nval, nqual, nts) if nval is not None else (None, None, None)
                else:
                    raise RuntimeError("bulk-length-mismatch")
            except asyncio.TimeoutError:
                timeout_count += 1
                if len(group) == 1:
                    sonuclar[group[0]] = (None, None, None)
                else:
                    mid = len(group) // 2
                    pending.append(group[:mid])
                    pending.append(group[mid:])
            except Exception:
                if len(group) == 1:
                    et = group[0]
                    try:
                        tag_res = await asyncio.wait_for(
                            loop.run_in_executor(executor, client.read, et),
                            timeout=max(0.20, min(1.0, self.chunk_read_timeout_sec))
                        )
                        tval, tqual, tts = _normalize_read(et, tag_res)
                        sonuclar[et] = (tval, tqual, tts) if tval is not None else (None, None, None)
                    except Exception:
                        try:
                            prop_call = functools.partial(getattr(client, "properties", lambda *a, **k: None), et, id=2)
                            prop = await loop.run_in_executor(executor, prop_call)
                            sonuclar[et] = (prop, "Good", "N/A") if prop is not None else (None, None, None)
                        except Exception:
                            sonuclar[et] = (None, None, None)
                else:
                    mid = len(group) // 2
                    pending.append(group[:mid])
                    pending.append(group[mid:])

        _set_read_stats(mode, timeout_count)
        return sonuclar

    def run(self):
        try:
            site_path_ekle()
            import pythoncom, OpenOPC, pywintypes

            def _pickle_pytime(dt):
                """Make pywintypes time objects picklable for multiprocessing queues.

                The incoming `dt` can be numeric, a Python datetime, or a
                pywintypes.datetime. Try several conversions and fall back
                to epoch 0 if all fail to avoid exceptions during pickling.
                """
                try:
                    # numeric-like (already seconds)
                    return (pywintypes.Time, (int(dt),))
                except Exception:
                    pass
                try:
                    # datetime-like objects often have timestamp()
                    if hasattr(dt, "timestamp"):
                        return (pywintypes.Time, (int(dt.timestamp()),))
                except Exception:
                    pass
                try:
                    # fallback: use timetuple -> epoch
                    import time as _time
                    return (pywintypes.Time, (int(_time.mktime(dt.timetuple())),))
                except Exception:
                    # last resort: zero epoch
                    return (pywintypes.Time, (0,))
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
            loop = asyncio.get_running_loop()
            self._log(f"OPC UA Sunucusu yayinda: {endpoint}")
            # Create a dedicated single-thread executor for OpenOPC COM interactions
            # so that the client is always accessed from the same thread.
            from concurrent.futures import ThreadPoolExecutor
            self._opc_executor = ThreadPoolExecutor(max_workers=1)
            try:
                def _create_client():
                    try:
                        import pythoncom as _pythoncom
                        _pythoncom.CoInitialize()
                    except Exception:
                        pass
                    import OpenOPC as _OpenOPC
                    c = _OpenOPC.client()
                    c.connect(self.prog_id)
                    return c

                opc = await loop.run_in_executor(self._opc_executor, _create_client)
                self._opc = opc
                self._log(f"OPC DA baglandi: {self.prog_id}")
            except Exception as e:
                self._log(f"OPC DA baglanti hatasi: {e}")
                try:
                    self._opc_executor.shutdown(wait=False)
                except Exception:
                    pass
                return

            etiket_haritasi = {}
            for et in self.etiketler:
                safe = et.replace(".", "_").replace(" ", "_").replace("\\", "_")
                node = await kok.add_variable(idx, safe, 0.0, ua.VariantType.Double)
                
                # --- EKLENEN KISIM: READ YETKİ KONTROLÜ ---
                if self.yetki != "READ":
                    await node.set_writable()
                # ------------------------------------------
                
                etiket_haritasi[et] = node

            self._log(f"{len(self.etiketler)} etiket UA'ya eklendi. Dongu basliyor...\n")
            etiket_listesi = list(etiket_haritasi.keys())
            hata_sayaci = {}
            son_okuma = {}

            # Batching & throttling parameters
            GUI_INTERVAL = 0.5    # max GUI updates per second (2 Hz)
            CSV_INTERVAL = 1.0    # write CSV once per second
            SLEEP_INTERVAL = 0.05 # 50 ms throttle to avoid 100% CPU
            BASE_POLL_INTERVAL = 0.20   # default per-tag poll target
            MAX_POLL_INTERVAL = 10.0    # backoff ceiling for problematic tags
            MIN_POLLED_PER_CYCLE = 6
            MAX_POLLED_PER_CYCLE = 120

            gui_buffer = []
            csv_buffer = []
            last_gui_send = time.monotonic()
            last_csv_write = time.monotonic()
            last_perf_log = time.monotonic()
            cycle_index = 0
            now0 = time.monotonic()
            tag_state = {
                et: {
                    "next_due": now0,
                    "interval": BASE_POLL_INTERVAL,
                    "fail_streak": 0,
                    "seq": 0,
                }
                for et in etiket_listesi
            }
            schedule_heap = []
            for et in etiket_listesi:
                st = tag_state[et]
                heapq.heappush(schedule_heap, (st["next_due"], st["seq"], et))
            self._log(
                f"Adaptif poll aktif: tags={len(etiket_listesi)} "
                f"base={BASE_POLL_INTERVAL}s max={MAX_POLL_INTERVAL}s"
            )
            poll_cap = min(MAX_POLLED_PER_CYCLE, max(MIN_POLLED_PER_CYCLE, len(etiket_listesi) // 5 or 1))

            def _coerce_numeric(v):
                try:
                    if v is None:
                        return None
                    if isinstance(v, bool):
                        return 1.0 if v else 0.0
                    if isinstance(v, (int, float)):
                        return float(v)
                    if isinstance(v, str):
                        s = v.strip()
                        if not s:
                            return None
                        sl = s.lower()
                        if sl in ("true", "1", "yes"):
                            return 1.0
                        if sl in ("false", "0", "no"):
                            return 0.0
                        # try normalized numeric (comma -> dot)
                        s2 = s.replace(' ', '').replace(',', '.')
                        try:
                            return float(s2)
                        except Exception:
                            return None
                    return None
                except Exception:
                    return None

            while self._calisıyor:
                cycle_started = time.monotonic()
                cycle_index += 1
                now_due = time.monotonic()
                due_entries = []
                while schedule_heap and len(due_entries) < poll_cap:
                    due_ts, seq, et = heapq.heappop(schedule_heap)
                    st = tag_state.get(et)
                    if st is None:
                        continue
                    # stale heap entry: skip
                    if seq != st["seq"] or due_ts != st["next_due"]:
                        continue
                    if due_ts > now_due:
                        heapq.heappush(schedule_heap, (due_ts, seq, et))
                        break
                    lag_ms = max(0.0, (now_due - due_ts) * 1000.0)
                    due_entries.append((et, lag_ms))

                # If nothing is due yet, opportunistically poll one nearest tag.
                if not due_entries and schedule_heap:
                    due_ts, seq, et = heapq.heappop(schedule_heap)
                    st = tag_state.get(et)
                    if st is not None and seq == st["seq"] and due_ts == st["next_due"]:
                        due_entries.append((et, max(0.0, (now_due - due_ts) * 1000.0)))
                    else:
                        heapq.heappush(schedule_heap, (due_ts, seq, et))

                okunacak_etiketler = [et for et, _ in due_entries]
                queue_lags_ms = [lag for _, lag in due_entries]
                due_count = len(okunacak_etiketler)
                # Non-blocking bulk read
                okumalar = await self._toplu_oku(okunacak_etiketler)
                son_okuma.update(okumalar)
                read_elapsed_ms = int((time.monotonic() - cycle_started) * 1000)
                satirlar = []
                gorevler = []
                now_iso = datetime.datetime.now().isoformat()

                for et in okunacak_etiketler:
                    deger, kalite, _ = son_okuma.get(et, (None, None, None))
                    node = etiket_haritasi[et]
                    if deger is None:
                        st = tag_state[et]
                        st["fail_streak"] = min(8, st["fail_streak"] + 1)
                        st["interval"] = min(MAX_POLL_INTERVAL, BASE_POLL_INTERVAL * (2 ** st["fail_streak"]))
                        st["next_due"] = now_due + st["interval"]
                        st["seq"] += 1
                        heapq.heappush(schedule_heap, (st["next_due"], st["seq"], et))
                        hata_sayaci[et] = hata_sayaci.get(et, 0) + 1
                        satirlar.append(f"UYARI {et}: Veri yok ({hata_sayaci[et]}x)")
                        # record missing value as row if CSV enabled
                        if self.csv_path:
                            csv_buffer.append((now_iso, et, "", "NO_DATA"))
                        continue
                    hata_sayaci[et] = 0
                    st = tag_state[et]
                    st["fail_streak"] = 0
                    st["interval"] = BASE_POLL_INTERVAL
                    st["next_due"] = now_due + st["interval"]
                    st["seq"] += 1
                    heapq.heappush(schedule_heap, (st["next_due"], st["seq"], et))
                    num = _coerce_numeric(deger)
                    if num is not None:
                        try:
                            gorevler.append(node.write_value(num, ua.VariantType.Double))
                            if self.verbose_data_log:
                                satirlar.append(f"OK {et}: {num:.4f} [{kalite}]")
                            if self.csv_path:
                                csv_buffer.append((now_iso, et, num, str(kalite)))
                        except Exception:
                            satirlar.append(f"ERROR {et}: Yazma hatasi")
                    else:
                        if self.verbose_data_log:
                            satirlar.append(f"INFO {et}: {deger} (metin)")
                        if self.csv_path:
                            csv_buffer.append((now_iso, et, str(deger), str(kalite)))

                write_started = time.monotonic()
                if gorevler:
                    await asyncio.gather(*gorevler)
                write_elapsed_ms = int((time.monotonic() - write_started) * 1000)

                # Auto-tune poll cap by measured read latency (hardware-agnostic behavior)
                if read_elapsed_ms > 900:
                    poll_cap = max(MIN_POLLED_PER_CYCLE, poll_cap - 8)
                elif read_elapsed_ms > 700:
                    poll_cap = max(MIN_POLLED_PER_CYCLE, poll_cap - 4)
                elif read_elapsed_ms < 250 and due_count >= poll_cap:
                    poll_cap = min(MAX_POLLED_PER_CYCLE, poll_cap + 3)
                elif read_elapsed_ms < 450 and due_count >= poll_cap:
                    poll_cap = min(MAX_POLLED_PER_CYCLE, poll_cap + 1)

                # Buffer GUI lines and send at most 2 Hz
                if satirlar:
                    gui_buffer.extend(satirlar)

                now_mon = time.monotonic()
                if (now_mon - last_gui_send) >= GUI_INTERVAL and gui_buffer:
                    try:
                        self._log("\n".join(gui_buffer))
                        self._log("-" * 60)
                    except Exception:
                        pass
                    gui_buffer.clear()
                    last_gui_send = now_mon

                # Perf summary log every 2 seconds (readable cadence)
                if (now_mon - last_perf_log) >= 2.0:
                    stats = getattr(self, "_last_read_stats", {}) or {}
                    cycle_elapsed_ms = int((time.monotonic() - cycle_started) * 1000)
                    avg_queue_lag_ms = int(sum(queue_lags_ms) / len(queue_lags_ms)) if queue_lags_ms else 0
                    max_queue_lag_ms = int(max(queue_lags_ms)) if queue_lags_ms else 0
                    est_ua_delivery_ms = avg_queue_lag_ms + read_elapsed_ms + write_elapsed_ms
                    self._log(
                        "METRIK "
                        f"tags={len(etiket_listesi)} "
                        f"polled={len(okunacak_etiketler)} "
                        f"cap={poll_cap} "
                        f"read={read_elapsed_ms}ms "
                        f"write={write_elapsed_ms}ms "
                        f"cycle={cycle_elapsed_ms}ms "
                        f"queueLagAvg={avg_queue_lag_ms}ms "
                        f"queueLagMax={max_queue_lag_ms}ms "
                        f"uaDeliveryEst={est_ua_delivery_ms}ms "
                        f"timeouts={stats.get('timeouts', 0)} "
                        f"mode={stats.get('mode', 'n/a')}"
                    )
                    last_perf_log = now_mon

                # Flush CSV buffer once per second (append mode)
                if self.csv_path and (now_mon - last_csv_write) >= CSV_INTERVAL and csv_buffer:
                    try:
                        import csv as _csv
                        os.makedirs(os.path.dirname(self.csv_path), exist_ok=True)
                        with open(self.csv_path, "a", newline='', encoding="utf-8") as f:
                            writer = _csv.writer(f)
                            for r in csv_buffer:
                                writer.writerow(r)
                    except Exception as e:
                        try:
                            self._log(f"CSV yazma hatasi: {e}")
                        except Exception:
                            pass
                    csv_buffer.clear()
                    last_csv_write = now_mon

                await asyncio.sleep(SLEEP_INTERVAL)

            try:
                client = getattr(self, "_opc", None)
                executor = getattr(self, "_opc_executor", None)
                if client is not None:
                    await loop.run_in_executor(executor, getattr(client, "close", lambda: None))
            except Exception:
                pass
            try:
                exe = getattr(self, "_opc_executor", None)
                if exe is not None:
                    exe.shutdown(wait=False)
            except Exception:
                pass
            self._log("Gateway durduruldu.")

    def durdur(self):
        self._calisıyor = False


# =====================================================================
# BÖLÜM 7: ANA UYGULAMA
# =====================================================================
class GatewayApp(QtWidgets.QMainWindow, Ui_MainWindow):
    def __init__(self, lisans_yoneticisi: LisansYoneticisi,
                 lisans_kontrolcusu: 'LisansKontrolcusu',
                 offline_yetki: str = ""):
        super().__init__()
        self.ly = lisans_yoneticisi
        self._offline_yetki = offline_yetki  # "" = online mod, "FULL"/"READ"/"DEMO" = offline
        self.setupUi(self)
        self.worker   = None
        self._kurulum = None

        self._log_koprusu = LogKoprusu(self.txt_konsol)

        self.btn_kurulum_ac.clicked.connect(self._kurulum_ac)
        self.btn_sunucu_tara.clicked.connect(self._sunucu_tara)
        self.btn_etiket_tara.clicked.connect(self._etiket_tara)
        self.btn_baslat.clicked.connect(self._baslat)
        self.btn_durdur.clicked.connect(self._durdur)
        self.btn_tepsi.clicked.connect(self._tepsiye_kukult)

        # Sistem tepsisi kurulumu
        self._tray_kur()

        # Arka plan lisans kontrolcüsünü bağla (sadece online modda aktif)
        self._lisans_kontrolcusu = lisans_kontrolcusu
        if self._lisans_kontrolcusu:
            self._lisans_kontrolcusu.lisans_iptal_edildi.connect(self._lisans_iptal_islemi)

        # Debugger periyodik kontrol (her 3 saniyede bir)
        self._debugger_timer = QTimer(self)
        self._debugger_timer.timeout.connect(_debugger_kontrol)
        self._debugger_timer.start(3000)

        self._lisans_bilgisi_goster()
        self._log(f"OPC DA -> OPC UA Gateway v{VERSIYON} hazir.")
        if self._offline_yetki:
            self._log(f"[OFFLİNE MOD] Yetki seviyesi: {self._offline_yetki}")
        self._log("   Adimlar: Sunucu Tara -> Etiket Tara -> Sec -> Baslat\n")
        baslik = f"OPC DA -> OPC UA Gateway v{VERSIYON}"
        if self._offline_yetki == "DEMO":
            baslik += "   [ ⚠️ DEMO SÜRÜM - TİCARİ KULLANILAMAZ ]"
            self._log("!!! DİKKAT: DEMO SÜRÜM KULLANIYORSUNUZ !!!")
        elif self._offline_yetki == "READ":
            baslik += "   [ 👁️ SADECE İZLEME (READ-ONLY) MODU ]"
            self._log("!!! DİKKAT: YAZMA YETKİSİ KAPALI !!!")
        self.setWindowTitle(baslik)

    def _lisans_bilgisi_goster(self):
        # Offline modda self.ly = None; offline lisans bilgisini göster
        if self.ly is None:
            try:
                oly = OfflineLisansYoneticisi()
                bilgi = oly.lisans_bilgisi()
                if bilgi:
                    bitis_ts = bilgi.get("bitis_ts", 0)
                    yetki    = bilgi.get("yetki", self._offline_yetki)
                    if bitis_ts > 0:
                        bitis_dt = datetime.datetime.fromtimestamp(bitis_ts)
                        kalan = max(0, int((bitis_ts - time.time()) / 86400))
                        self.lbl_lisans.setText(
                            f"[OFFLİNE] Yetki: {yetki} | "
                            f"Bitis: {bitis_dt.strftime('%d.%m.%Y')} ({kalan} gun kaldi)"
                        )
                    else:
                        self.lbl_lisans.setText(f"[OFFLİNE] Yetki: {yetki}")
            except Exception:
                self.lbl_lisans.setText(f"[OFFLİNE] Yetki: {self._offline_yetki}")
            return

        # Online mod
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
        # --- Dağıtık lisans kontrolü (A8) ---
        _debugger_kontrol()
        if self._offline_yetki:
            oly_check = OfflineLisansYoneticisi()
            durum, _ = oly_check.dogrula()
            if durum != "gecerli":
                QMessageBox.critical(self, "Lisans Hatası",
                    "Offline lisans geçersiz veya süresi dolmuş.\nProgram kapatılıyor.")
                QtWidgets.QApplication.quit()
                return

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

        self.worker = GatewayWorker(prog_id, ip, port, secili, self._offline_yetki)
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

    # ── Sistem Tepsisi ──

    def _tray_kur(self):
        """QSystemTrayIcon oluşturur; mevcut uygulama ikonunu veya fallback ikonu kullanır."""
        from PyQt5.QtWidgets import QSystemTrayIcon, QMenu, QAction
        from PyQt5.QtGui import QIcon

        # İkon: varsa logo.ico, yoksa Qt'nin dahili bir ikonu
        if hasattr(sys, '_MEIPASS'):
            icon_path = os.path.join(sys._MEIPASS, 'logo.ico')
        else:
            icon_path = 'logo.ico'

        if os.path.exists(icon_path):
            tray_icon = QIcon(icon_path)
        else:
            tray_icon = self.style().standardIcon(
                QtWidgets.QStyle.SP_ComputerIcon
            )

        self._tray = QSystemTrayIcon(tray_icon, self)
        self._tray.setToolTip(f"OPC DA → OPC UA Gateway v{VERSIYON}")

        # Tray menüsü
        menu = QMenu()
        menu.setStyleSheet("""
            QMenu {
                background-color: #1a1d2e;
                color: #e0e0e0;
                border: 1px solid #2a2d3e;
                border-radius: 4px;
                padding: 4px;
            }
            QMenu::item { padding: 6px 18px; border-radius: 3px; }
            QMenu::item:selected { background-color: #5b8cff; color: white; }
            QMenu::separator { height: 1px; background: #2a2d3e; margin: 4px 6px; }
        """)

        act_goster = menu.addAction("⬆  Pencereyi Göster")
        act_goster.triggered.connect(self._pencereye_geri_al)
        menu.addSeparator()
        act_cikis = menu.addAction("✕  Çıkış")
        act_cikis.triggered.connect(self._gercek_cikis)

        self._tray.setContextMenu(menu)
        # Tray ikonuna çift tıklayınca pencereyi geri aç
        self._tray.activated.connect(self._tray_tikla)
        self._tray.show()

    def _tray_tikla(self, reason):
        from PyQt5.QtWidgets import QSystemTrayIcon
        if reason == QSystemTrayIcon.DoubleClick:
            self._pencereye_geri_al()

    def _tepsiye_kukult(self):
        """Pencereyi gizler, program sistem tepsisinde çalışmaya devam eder."""
        self.hide()
        if hasattr(self, '_tray'):
            self._tray.showMessage(
                "OPC Gateway",
                "Program sistem tepsisinde çalışıyor. Geri almak için çift tıklayın.",
                self.style().standardIcon(QtWidgets.QStyle.SP_ComputerIcon),
                3000
            )

    def _pencereye_geri_al(self):
        """Pencereyi tepsiden geri açar, öne getirir."""
        self.showNormal()
        self.raise_()
        self.activateWindow()

    def _gercek_cikis(self):
        """Tray menüsündeki Çıkış — tüm kaynakları temizler ve programı kapatır."""
        self._tray_cikis = True   # closeEvent'in tepsiye gitmesini engelle
        self.close()

    def closeEvent(self, event):
        # X butonuna basınca direkt kapat — tepsiye küçülme SADECE btn_tepsi ile yapılır.
        if self.worker and self.worker.isRunning():
            self.worker.durdur()
            self.worker.wait(3000)
        if self._lisans_kontrolcusu and self._lisans_kontrolcusu.isRunning():
            self._lisans_kontrolcusu.durdur()
            self._lisans_kontrolcusu.wait(3000)
        if hasattr(self, "_debugger_timer"):
            self._debugger_timer.stop()
        if hasattr(self, "_tray"):
            self._tray.hide()
        event.accept()



# =====================================================================
# BÖLÜM 8: UYGULAMA GİRİŞİ (Hibrit: Online önce, yoksa Offline)
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
    splash.setWindowTitle("OPC Gateway - Lisans Kontrolu")
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

    # Offline modda LisansKontrolcusu yok (internet yok)
    pencere = GatewayApp(None, None, offline_yetki=yetki)
    pencere.show()
    sys.exit(app.exec_())


def uygulamayi_baslat():
    app = QtWidgets.QApplication(sys.argv)
    try:
        from PyQt5.QtGui import QIcon
        import ctypes
        
        # 1. PyInstaller Gizli Klasör Yolunu Çözücü
        if hasattr(sys, '_MEIPASS'):
            icon_path = os.path.join(sys._MEIPASS, 'logo.ico')
        else:
            icon_path = 'logo.ico'
            
        # 2. Windows Görev Çubuğu (Taskbar) İkon Sabitleyici (ŞART)
        myappid = 'sirket.opcgateway.pro.v5' # Windows bu ID'ye göre ikonu ayırır
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
        
        # 3. İkonu Tüm Uygulama Pencerelerine Uygula
        app.setWindowIcon(QIcon(icon_path))
    except Exception as e:
        print("Ikon hatasi:", e)
        pass

    app.setStyle("Fusion")
    app.setStyleSheet(GLOBAL_STYLESHEET)

    # ── İnternet kontrolü ──
    splash = QtWidgets.QDialog()
    splash.setWindowTitle("OPC Gateway - Baslaniyor")
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
        # ══ OFFLİNE AKIŞ ══
        _offline_akis(app)
        return  # sys.exit içinde zaten biter

    # ══ ONLINE AKIŞ (mevcut kod — tek karakter bile değişmedi) ══
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