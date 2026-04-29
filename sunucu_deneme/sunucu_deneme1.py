# -*- coding: utf-8 -*-

"""
OPC Gateway Lisans Doğrulama Sunucusu v5.0 (İstihbarat Entegreli)
FastAPI + SQLite | Railway deploy
"""

import os
import uuid
import secrets
import datetime
import hmac
import urllib.request
import urllib.parse
import json
from typing import Optional, List
from functools import wraps

from fastapi import FastAPI, HTTPException, Header, Depends, Request, Form, Response, BackgroundTasks
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, FileResponse
import hashlib
import os
# =====================================================================
# YARDIMCI FONKSİYONLAR
# =====================================================================
def get_exe_hash() -> str:
  exe_path = os.path.join("dosyalar", "OPC_Gateway_Pro.exe")
  try:
    with open(exe_path, "rb") as f:
      return hashlib.sha256(f.read()).hexdigest()
  except Exception:
    return ""

def get_exe_date() -> str:
  exe_path = os.path.join("dosyalar", "OPC_Gateway_Pro.exe")
  try:
    ts = os.path.getmtime(exe_path)
    return datetime.datetime.fromtimestamp(ts).strftime("%d.%m.%Y")
  except Exception:
    return ""

def is_exe_new() -> bool:
  """EXE dosyası son 24 saat içinde mi güncellendi?"""
  exe_path = os.path.join("dosyalar", "OPC_Gateway_Pro.exe")
  try:
    ts = os.path.getmtime(exe_path)
    diff = datetime.datetime.now() - datetime.datetime.fromtimestamp(ts)
    return diff.total_seconds() < 86400  # 24 saat
  except Exception:
    return False

def telegram_bildirim_gonder(mesaj: str):
    """Genel sistem bildirimleri için Telegram fonksiyonu"""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID: return
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        data = urllib.parse.urlencode({"chat_id": TELEGRAM_CHAT_ID, "text": mesaj, "parse_mode": "HTML"}).encode("utf-8")
        req = urllib.request.Request(url, data=data)
        urllib.request.urlopen(req, timeout=4)
    except Exception:
        pass
# =====================================================================
# İSTEMCİ API (EXE kullanır)
# =====================================================================

from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr
from sqlalchemy import (
    create_engine, Column, String, DateTime,
    Boolean, Integer, Text
)
from sqlalchemy.orm import declarative_base, sessionmaker, Session
import hashlib

# =====================================================================
# YAPILANDIRMA — Railway'de Environment Variables olarak ayarlayın
# =====================================================================
SECRET_KEY         = os.getenv("SECRET_KEY", "BURAYA-GIZLI-ANAHTARINIZI-YAZIN")
PANEL_KULLANICI    = os.getenv("PANEL_KULLANICI", "admin")
PANEL_SIFRE        = os.getenv("PANEL_SIFRE", "admin123")
DATABASE_URL       = os.getenv("DATABASE_URL", "sqlite:///./lisanslar.db")
INDIRME_LINKI      = "/api/program-indir"

# TELEGRAM İSTİHBARAT AYARLARI
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID   = os.getenv("TELEGRAM_CHAT_ID", "")

if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

# Offline lisans için gömülü anahtar
_SK_P1 = bytes([0x4f, 0x50, 0x43, 0x5f, 0x47, 0x57, 0x5f, 0x4f])
_SK_P2 = bytes([0x46, 0x46, 0x4c, 0x49, 0x4e, 0x45, 0x5f, 0x4b])
_SK_P3 = hashlib.sha256(b"opcgw_offline_2026_salt_v1").digest()[:16]
OFFLINE_SECRET_KEY = _SK_P1 + _SK_P2 + _SK_P3

# =====================================================================
# VERİTABANI MODELLERİ (Aynı Kalıyor)
# =====================================================================
_db_connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine   = create_engine(DATABASE_URL, connect_args=_db_connect_args)
Session_ = sessionmaker(bind=engine)
Base     = declarative_base()

class Lisans(Base):
    __tablename__ = "lisanslar"
    id             = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    lisans_kodu    = Column(String, unique=True, nullable=False, index=True)
    hwid           = Column(String, nullable=True)
    musteri_adi    = Column(String, nullable=False)
    musteri_email  = Column(String, nullable=True)
    tur            = Column(String, nullable=False)
    aktif          = Column(Boolean, default=True)
    olusturma_tar  = Column(DateTime, default=datetime.datetime.utcnow)
    bitis_tarihi   = Column(DateTime, nullable=True)
    notlar         = Column(Text, nullable=True)
    son_checkin    = Column(DateTime, nullable=True)
    aktivasyon_tar = Column(DateTime, nullable=True)
    iptal_nedeni   = Column(Text, nullable=True)
    iptal_tarihi   = Column(DateTime, nullable=True)
    uretilen_tip   = Column(String, default="online")
    istek_kodu_db  = Column(String, nullable=True)
    sure_gun_db    = Column(Integer, nullable=True)
    yetki_seviyesi = Column(String, nullable=True)

class Log(Base):
    __tablename__ = "loglar"
    id          = Column(Integer, primary_key=True, autoincrement=True)
    tarih       = Column(DateTime, default=datetime.datetime.utcnow)
    islem       = Column(String)
    lisans_kodu = Column(String)
    hwid        = Column(String)
    ip          = Column(String)
    mesaj       = Column(Text)

class Kullanici(Base):
    __tablename__ = "kullanicilar"
    id              = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    ad_soyad        = Column(String, nullable=False)
    email           = Column(String, unique=True, nullable=False, index=True)
    sifre_hash      = Column(String, nullable=False)
    email_dogrulandi = Column(Boolean, default=False)
    dogrulama_kodu  = Column(String, nullable=True)
    kayit_tar       = Column(DateTime, default=datetime.datetime.utcnow)
    son_giris       = Column(DateTime, nullable=True)
    son_ip          = Column(String, nullable=True)

class LisansTalep(Base):
    __tablename__ = "lisans_talepler"
    id          = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    kullanici_id = Column(String, nullable=False)
    ad_soyad    = Column(String, nullable=False)
    email       = Column(String, nullable=False)
    tur         = Column(String, nullable=False)
    durum       = Column(String, default="beklemede")
    talep_tar   = Column(DateTime, default=datetime.datetime.utcnow)
    islem_tar   = Column(DateTime, nullable=True)
    ip_adresi   = Column(String, nullable=True)
    admin_notu  = Column(Text, nullable=True)
    talep_tipi  = Column(String, default="online")
    istek_kodu  = Column(String, nullable=True)
    aktivasyon_kodu = Column(String, nullable=True)

class Mesaj(Base):
    __tablename__ = "mesajlar"
    id           = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    kullanici_id = Column(String, nullable=False)
    gonderen     = Column(String, nullable=False)
    icerik       = Column(Text, nullable=False)
    tarih        = Column(DateTime, default=datetime.datetime.utcnow)
    okundu       = Column(Boolean, default=False)

class IpBan(Base):
    __tablename__ = "ip_banlar"
    id        = Column(Integer, primary_key=True, autoincrement=True)
    ip        = Column(String, unique=True, nullable=False, index=True)
    sebep     = Column(Text, nullable=True)
    tarih     = Column(DateTime, default=datetime.datetime.utcnow)
    aktif     = Column(Boolean, default=True)

class UyelikTuru(Base):
    __tablename__ = "uyelik_turleri"
    id          = Column(Integer, primary_key=True, autoincrement=True)
    kod         = Column(String, unique=True, nullable=False)
    ad          = Column(String, nullable=False)
    aciklama    = Column(Text, nullable=True)
    aktif       = Column(Boolean, default=True)
    sira        = Column(Integer, default=0)
    sure_gun    = Column(Integer, default=30)
    prefix      = Column(String, default="STD")

class PanelKullanici(Base):
    __tablename__ = "panel_kullanicilari"
    id = Column(Integer, primary_key=True, autoincrement=True)
    kullanici_adi = Column(String, unique=True, nullable=False)
    isim_soyad = Column(String, nullable=True)
    email = Column(String, unique=True, nullable=True)
    sifre_hash = Column(String, nullable=False)
    is_admin = Column(Boolean, default=False)
    yetki_lisans_olustur = Column(Boolean, default=False)
    yetki_lisans_sil = Column(Boolean, default=False)
    yetki_hwid_sifirla = Column(Boolean, default=False)
    yetki_sure_uzat = Column(Boolean, default=False)
    yetki_talep_onayla = Column(Boolean, default=False)
    yetki_kullanici_ekle = Column(Boolean, default=False)
    yetki_mesaj_yaz = Column(Boolean, default=False)
    yetki_ip_ban = Column(Boolean, default=False)
    yetki_uyelik_tur = Column(Boolean, default=False)
    yetki_offline_lisans = Column(Boolean, default=False)
    telegram_chat_id = Column(String, nullable=True)
    telegram_bildirim_alabilir = Column(Boolean, default=False)
    son_giris = Column(DateTime, nullable=True)
    son_cikis = Column(DateTime, nullable=True)

class PanelLog(Base):
    __tablename__ = "panel_loglar"
    id = Column(Integer, primary_key=True, autoincrement=True)
    tarih = Column(DateTime, default=datetime.datetime.utcnow)
    kullanici_adi = Column(String)
    islem = Column(String)
    detay = Column(Text)

class Ayarlar(Base):
    __tablename__ = "ayarlar"
    id = Column(Integer, primary_key=True)
    admin_kullanici = Column(String, nullable=True)
    admin_sifre_hash = Column(String, nullable=True)
    son_exe_hash = Column(String, nullable=True)
    son_surum_tarihi = Column(DateTime, nullable=True)

class OfflineLisansAyarlari(Base):
    __tablename__ = "offline_lisans_ayarlari"
    id = Column(Integer, primary_key=True)
    notlar = Column(Text, nullable=True)

Base.metadata.create_all(engine)

def _db_migrate():
    """
    PostgreSQL'de tek bir connection içinde bir DDL başarısız olursa
    transaction bozuk kalır; sonraki commit'ler çalışmaz.
    Çözüm: Her ALTER TABLE için bağımsız bir connection kullan.
    PostgreSQL destekliyorsa 'IF NOT EXISTS' sözdizimi kullanılır.
    """
    _is_pg = not DATABASE_URL.startswith("sqlite")
    _ifne  = "IF NOT EXISTS " if _is_pg else ""

    _migrations = [
        f"ALTER TABLE panel_kullanicilari ADD COLUMN {_ifne}yetki_offline_lisans BOOLEAN DEFAULT false",
        f"ALTER TABLE uyelik_turleri ADD COLUMN {_ifne}sure_gun INTEGER DEFAULT 30",
        f"ALTER TABLE uyelik_turleri ADD COLUMN {_ifne}prefix VARCHAR(10) DEFAULT 'STD'",
        f"ALTER TABLE ayarlar ADD COLUMN {_ifne}son_exe_hash VARCHAR(100)",
        f"ALTER TABLE ayarlar ADD COLUMN {_ifne}son_surum_tarihi TIMESTAMP",
        f"ALTER TABLE lisans_talepler ADD COLUMN {_ifne}talep_tipi VARCHAR(20) DEFAULT 'online'",
        f"ALTER TABLE lisans_talepler ADD COLUMN {_ifne}istek_kodu VARCHAR(100)",
        f"ALTER TABLE lisans_talepler ADD COLUMN {_ifne}aktivasyon_kodu VARCHAR(100)",
        f"ALTER TABLE panel_kullanicilari ADD COLUMN {_ifne}telegram_chat_id VARCHAR(100)",
        f"ALTER TABLE panel_kullanicilari ADD COLUMN {_ifne}telegram_bildirim_alabilir BOOLEAN DEFAULT false",
        f"ALTER TABLE lisanslar ADD COLUMN {_ifne}uretilen_tip VARCHAR(20) DEFAULT 'online'",
        f"ALTER TABLE lisanslar ADD COLUMN {_ifne}istek_kodu_db VARCHAR(100)",
        f"ALTER TABLE lisanslar ADD COLUMN {_ifne}sure_gun_db INTEGER",
        f"ALTER TABLE lisanslar ADD COLUMN {_ifne}yetki_seviyesi VARCHAR(50)",
    ]

    for sql in _migrations:
        try:
            with engine.connect() as conn:
                conn.execute(__import__("sqlalchemy").text(sql))
                conn.commit()
        except Exception:
            pass  # Kolon zaten varsa (IF NOT EXISTS olmayan DB) devam et

_db_migrate()


def varsayilan_turleri_ekle():
    s = Session_()
    try:
        if s.query(UyelikTuru).count() == 0:
            turler = [
                UyelikTuru(kod="aylik", ad="Aylık Lisans", aciklama="30 gün geçerli", sira=1, sure_gun=30, prefix="AYL"),
                UyelikTuru(kod="yillik", ad="Yıllık Lisans", aciklama="365 gün geçerli", sira=2, sure_gun=365, prefix="YIL"),
                UyelikTuru(kod="omur_boyu", ad="Ömür Boyu Lisans", aciklama="Süresiz geçerli", sira=3, sure_gun=0, prefix="OBY"),
                UyelikTuru(kod="deneme", ad="Deneme Sürümü", aciklama="24 saat ücretsiz deneme", sira=4, sure_gun=1, prefix="DEN"),
            ]
            for t in turler: s.add(t)
            s.commit()
    finally: s.close()

varsayilan_turleri_ekle()

def db():
    s = Session_()
    try: yield s
    finally: s.close()

# =====================================================================
# TELEGRAM İSTİHBARAT KÖPRÜSÜ (YENİ)
# =====================================================================
def get_ip_konum(ip: str) -> str:
    if ip in ("127.0.0.1", "localhost", "0.0.0.0", "") or ip.startswith("192.168.") or ip.startswith("10."):
        return "Yerel Ağ (LAN/Localhost)"
    try:
        url = f"http://ip-api.com/json/{ip}"
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=2) as response:
            data = json.loads(response.read().decode())
            if data.get("status") == "success":
                return f"{data.get('city', '?')}, {data.get('country', '?')}"
    except Exception:
        pass
    return "Bilinmeyen Konum"

def istihbarat_raporu(bg_tasks: BackgroundTasks, islem_turu: str, actor: str, detay: str, ip: str):
    """Telegrama asenkron olarak log fırlatır."""
    def gorev():
        if not TELEGRAM_BOT_TOKEN: return
        konum = get_ip_konum(ip)
        zaman = (datetime.datetime.utcnow() + datetime.timedelta(hours=3)).strftime("%d.%m.%Y - %H:%M:%S")
        
        mesaj = (
            f"🚨 <b>YENİ SİSTEM İŞLEMİ</b> 🚨\n\n"
            f"👤 <b>İşlemi Yapan:</b> {actor}\n"
            f"⚙️ <b>İşlem:</b> {islem_turu}\n"
            f"📄 <b>Detay:</b> {detay}\n\n"
            f"🌐 <b>IP & Konum:</b> {ip} ({konum})\n"
            f"🕒 <b>Tarih:</b> {zaman}"
        )
        
        chat_ids = []
        if TELEGRAM_CHAT_ID:
            chat_ids.append(TELEGRAM_CHAT_ID)
            
        s = Session_()
        try:
            users = s.query(PanelKullanici).filter_by(telegram_bildirim_alabilir=True).all()
            for u in users:
                if u.telegram_chat_id and u.telegram_chat_id not in chat_ids:
                    chat_ids.append(u.telegram_chat_id)
        except Exception:
            pass
        finally:
            s.close()

        for cid in chat_ids:
            try:
                url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
                data = urllib.parse.urlencode({"chat_id": cid, "text": mesaj, "parse_mode": "HTML"}).encode("utf-8")
                req = urllib.request.Request(url, data=data)
                urllib.request.urlopen(req, timeout=4)
            except Exception:
                pass
            
    if bg_tasks:
        bg_tasks.add_task(gorev)

# =====================================================================
# YARDIMCI FONKSİYONLAR
# =====================================================================
def sifre_hashle(sifre: str) -> str:
    return hashlib.sha256(sifre.encode()).hexdigest()

def lisans_kodu_uret(tur_prefix="STD"):
    parca = secrets.token_hex(6).upper()
    return f"{tur_prefix}-{parca[:4]}-{parca[4:8]}-{parca[8:12]}"

def bitis_tarihi_hesapla(tur: str, s: Session, saat: Optional[int] = None) -> Optional[datetime.datetime]:
    simdi = datetime.datetime.utcnow()
    
    if tur == "deneme" and saat:
        return simdi + datetime.timedelta(hours=saat)
        
    u_tur = s.query(UyelikTuru).filter_by(kod=tur).first()
    
    # Güvenlik önlemi: Tür bulunamazsa, herkese ömür boyu (None) vermek büyük bir açıktır.
    if not u_tur:
        if tur == "omur_boyu":
            return None
        if tur == "deneme":
            return simdi + datetime.timedelta(hours=24)
        # Diğer bilinmeyen türler için varsayılan olarak 30 gün ver
        return simdi + datetime.timedelta(days=30)
        
    sure = getattr(u_tur, 'sure_gun', 0)
    
    # Eğer süre None veya 0 ise, bu ancak açıkça ömür boyu olanlar için geçerli olmalı
    if sure is None or sure == 0:
        if tur == "deneme":
            return simdi + datetime.timedelta(hours=24)
        return None
        
    return simdi + datetime.timedelta(days=sure)

def log_yaz(s: Session, islem, lisans_kodu, hwid, ip, mesaj):
    s.add(Log(islem=islem, lisans_kodu=lisans_kodu, hwid=hwid, ip=ip, mesaj=mesaj))
    s.commit()

def panel_log_yaz(s: Session, kullanici_adi: str, islem: str, detay: str = ""):
    s.add(PanelLog(kullanici_adi=kullanici_adi, islem=islem, detay=detay))
    s.commit()

def get_ana_admin_creds(s: Session):
    ayar = s.query(Ayarlar).first()
    if ayar and ayar.admin_kullanici and ayar.admin_sifre_hash:
        return ayar.admin_kullanici, ayar.admin_sifre_hash
    return PANEL_KULLANICI, sifre_hashle(PANEL_SIFRE)

def ip_banlimi(s: Session, ip: str) -> bool:
    ban = s.query(IpBan).filter_by(ip=ip, aktif=True).first()
    return ban is not None

# =====================================================================
# SESSION YÖNETİMİ
# =====================================================================
_sessions = {}

def session_olustur(kullanici_id: str) -> str:
    token = secrets.token_urlsafe(32)
    _sessions[token] = {"kullanici_id": kullanici_id, "tarih": datetime.datetime.utcnow()}
    return token

def session_dogrula(token: str) -> Optional[str]:
    if not token: return None
    s = _sessions.get(token)
    if not s: return None
    if (datetime.datetime.utcnow() - s["tarih"]).days > 7:
        del _sessions[token]
        return None
    return s["kullanici_id"]

def session_sil(token: str):
    _sessions.pop(token, None)

def safe_format_date(dt) -> str:
    if not dt: return "-"
    if isinstance(dt, str): return dt.split(" ")[0].replace("-", ".")
    try: return dt.strftime("%d.%m.%Y")
    except: return str(dt)

def safe_format_datetime(dt) -> str:
    if not dt: return "-"
    if isinstance(dt, str): return dt
    try: return dt.strftime("%d.%m.%Y %H:%M")
    except: return str(dt)

def safe_days_left(dt) -> Optional[int]:
    if not dt: return None
    if isinstance(dt, str):
        try:
            d_obj = datetime.datetime.strptime(dt[:10], "%Y-%m-%d")
            return (d_obj - datetime.datetime.utcnow()).days
        except: return 0
    try:
        return (dt - datetime.datetime.utcnow()).days
    except: return 0

def get_kullanici_id(request: Request) -> Optional[str]:
    token = request.cookies.get("session")
    return session_dogrula(token) if token else None

# =====================================================================
# FASTAPI UYGULAMASI
# =====================================================================
app = FastAPI(title="OPC Gateway", docs_url=None, redoc_url=None)

# CORS configuration: set `CORS_ALLOWED_ORIGINS` env var as comma-separated list.
# If you need cookie-based sessions from a frontend on another origin, set
# CORS_ALLOWED_ORIGINS to the frontend origin(s) (not "*") and the frontend
# must send requests with `credentials: 'include'`.
_cors_origins = os.getenv("CORS_ALLOWED_ORIGINS", "http://localhost:3000")
_cors_list = [o.strip() for o in _cors_origins.split(",") if o.strip()]
# If the special value '*' is provided, keep it but browsers will ignore cookies
# for wildcard origins, so allow_credentials must be False in that case.
if len(_cors_list) == 1 and _cors_list[0] == "*":
  _allow_credentials = False
else:
  _allow_credentials = True

app.add_middleware(
  CORSMiddleware,
  allow_origins=_cors_list,
  allow_credentials=_allow_credentials,
  allow_methods=["*"],
  allow_headers=["*"],
)

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    # Kritik hataları (Crash vb.) Telegram'a bildir
    error_msg = f"❌ <b>SUNUCU HATASI (CRASH)</b>\n\n<b>Endpoint:</b> {request.url}\n<b>Hata:</b> {str(exc)}"
    telegram_bildirim_gonder(error_msg)
    return JSONResponse(status_code=500, content={"detail": "Sunucu hatası oluştu, yöneticiye bildirildi."})

@app.on_event("startup")
async def startup_event():
    # Deploy Başarılı Bildirimi
    telegram_bildirim_gonder("🚀 <b>Deploy Başarılı!</b>\nSunucu ayağa kalktı ve aktif durumda.")

    # Yeni Program Sürümü Yayınlandı Bildirimi (Hash Kontrolü)
    s = Session_()
    try:
        current_hash = get_exe_hash()
        if current_hash:
            try:
                ayar = s.query(Ayarlar).first()
                if not ayar:
                    ayar = Ayarlar(son_exe_hash=current_hash, son_surum_tarihi=datetime.datetime.utcnow())
                    s.add(ayar)
                    s.commit()
                elif ayar.son_exe_hash != current_hash:
                    ayar.son_exe_hash = current_hash
                    ayar.son_surum_tarihi = datetime.datetime.utcnow()
                    s.commit()
                    telegram_bildirim_gonder(f"🆕 <b>Yeni Program Sürümü Yayınlandı!</b>\n\nOPC Gateway Pro programı güncellendi.\n<b>Tarih:</b> {get_exe_date()}\n<b>Hash:</b> {current_hash[:16]}...")
            except Exception as e:
                s.rollback()
                telegram_bildirim_gonder(f"⚠️ <b>Startup DB Uyarısı</b>\nAyarlar sorgusu başarısız: {str(e)[:200]}")
    finally:
        s.close()

@app.on_event("shutdown")
def shutdown_event():
    # Site Bakımda / Deploy Başlıyor Bildirimi
    telegram_bildirim_gonder("🚧 <b>Sistem Kapanıyor</b>\nSunucu kapatılıyor — yeni deploy başlıyor olabilir.")

def app_sirri_dogrula(request: Request):
    gelen = request.headers.get("x-app-secret") or request.headers.get("x_app_secret") or ""
    if gelen != SECRET_KEY:
        raise HTTPException(status_code=403, detail="Yetkisiz erisim.")

class PanelUserDto:
    def __init__(self, kadi, is_admin, yetkiler, isim_soyad=None):
        self.kullanici_adi = kadi
        self.is_admin = is_admin
        self.yetkiler = yetkiler
        self.isim_soyad = isim_soyad
        self.tam_isim = f"{isim_soyad or kadi} ({kadi})"

def panel_dogrula(request: Request, s: Session = Depends(db)):
    auth = request.headers.get("authorization") or request.headers.get("Authorization") or ""
    if auth.startswith("Bearer "):
        token = auth[7:]
        parts = token.split(":", 1)
        if len(parts) == 2:
            kadi = parts[0]
            sifre = parts[1]
            kadi_gercek, sifre_hash_gercek = get_ana_admin_creds(s)
            
            if kadi == kadi_gercek and sifre_hashle(sifre) == sifre_hash_gercek:
                return PanelUserDto(kadi, True, {}, isim_soyad="Ana Admin")
                
            pk = s.query(PanelKullanici).filter_by(kullanici_adi=kadi, sifre_hash=sifre_hashle(sifre)).first()
            if pk:
                yetkiler = {
                    "lisans_olustur": pk.yetki_lisans_olustur,
                    "lisans_sil": pk.yetki_lisans_sil,
                    "hwid_sifirla": pk.yetki_hwid_sifirla,
                    "sure_uzat": pk.yetki_sure_uzat,
                    "talep_onayla": pk.yetki_talep_onayla,
                    "kullanici_ekle": pk.yetki_kullanici_ekle,
                    "mesaj_yaz": pk.yetki_mesaj_yaz,
                    "ip_ban": pk.yetki_ip_ban,
                    "uyelik_tur": pk.yetki_uyelik_tur,
                    "offline_lisans": pk.yetki_offline_lisans,
                }
                return PanelUserDto(kadi, pk.is_admin, yetkiler, isim_soyad=pk.isim_soyad)
    raise HTTPException(status_code=401, detail="Panel kullanici adi veya sifresi yanlis.")

def yetki_kontrol(istenen_yetki: str):
    def checker(user: PanelUserDto = Depends(panel_dogrula)):
        if user.is_admin: return user
        if not user.yetkiler.get(istenen_yetki, False):
            raise HTTPException(status_code=403, detail="Bu işlem için yetkiniz bulunmamaktadır.")
        return user
    return checker

# =====================================================================
# İSTEMCİ API (EXE kullanır)
# =====================================================================
class AktivasoyonIstek(BaseModel):
    hwid: str
    lisans_kodu: str

class KontrolIstek(BaseModel):
    hwid: str
    lisans_kodu: str

@app.post("/api/aktive-et", dependencies=[Depends(app_sirri_dogrula)])
def aktive_et(istek: AktivasoyonIstek, request: Request, s: Session = Depends(db)):
    ip = request.client.host
    if ip_banlimi(s, ip): raise HTTPException(status_code=403, detail="Bu IP adresi yasaklanmıştır.")
    kod = istek.lisans_kodu.strip().upper()
    hwid = istek.hwid.strip()

    lisans = s.query(Lisans).filter_by(lisans_kodu=kod).first()
    if not lisans: raise HTTPException(status_code=404, detail="Lisans kodu bulunamadı.")
    if not lisans.aktif: raise HTTPException(status_code=403, detail="Bu lisans iptal edilmiştir.")
    if lisans.bitis_tarihi and datetime.datetime.utcnow() > lisans.bitis_tarihi: raise HTTPException(status_code=403, detail="Lisans süresi dolmuştur.")
    if lisans.hwid and lisans.hwid != hwid: raise HTTPException(status_code=403, detail="Bu lisans başka bilgisayara kayıtlı.")
    
    if not lisans.hwid:
        lisans.hwid = hwid
        lisans.aktivasyon_tar = datetime.datetime.utcnow()
    lisans.son_checkin = datetime.datetime.utcnow()
    s.commit()
    log_yaz(s, "aktivasyon", kod, hwid, ip, "Basarili aktivasyon")
    return {"basarili": True, "mesaj": f"Hoş geldiniz, {lisans.musteri_adi}!", "tur": lisans.tur, "bitis_tarihi": lisans.bitis_tarihi.isoformat() if lisans.bitis_tarihi else None, "musteri_adi": lisans.musteri_adi}

@app.post("/api/kontrol", dependencies=[Depends(app_sirri_dogrula)])
def kontrol(istek: KontrolIstek, request: Request, s: Session = Depends(db)):
    ip = request.client.host
    if ip_banlimi(s, ip): return {"gecerli": False, "mesaj": "Yasaklı IP."}
    kod = istek.lisans_kodu.strip().upper()
    hwid = istek.hwid.strip()
    lisans = s.query(Lisans).filter_by(lisans_kodu=kod).first()
    if not lisans or not lisans.aktif: return {"gecerli": False, "mesaj": "Lisans geçersiz."}
    if lisans.hwid != hwid: return {"gecerli": False, "mesaj": "HWID uyuşmazlığı."}
    if lisans.bitis_tarihi and datetime.datetime.utcnow() > lisans.bitis_tarihi: return {"gecerli": False, "mesaj": "Süre dolmuştur."}
    lisans.son_checkin = datetime.datetime.utcnow()
    s.commit()
    return {"gecerli": True, "tur": lisans.tur, "bitis_tarihi": lisans.bitis_tarihi.isoformat() if lisans.bitis_tarihi else None, "musteri_adi": lisans.musteri_adi}

# =====================================================================
# KULLANICI KAYIT/GİRİŞ API
# =====================================================================
@app.post("/api/kayit")
async def kayit_ol(request: Request, bg_tasks: BackgroundTasks, s: Session = Depends(db)):
    # Accept both JSON and form-encoded submissions from various frontends
    try:
        data = await request.json()
    except Exception:
        form = await request.form()
        data = dict(form)

    ad_soyad = data.get("ad_soyad", "").strip()
    email = data.get("email", "").strip().lower()
    sifre = data.get("sifre", "")

    if not ad_soyad or not email or not sifre:
        raise HTTPException(status_code=400, detail="Eksik alan.")
    if s.query(Kullanici).filter_by(email=email).first():
        raise HTTPException(status_code=409, detail="Kayıtlı e-posta.")

    k = Kullanici(ad_soyad=ad_soyad, email=email, sifre_hash=sifre_hashle(sifre), email_dogrulandi=True, son_ip=request.client.host)
    s.add(k)
    s.commit()

    # 🕵️ İstihbarat Raporu
    istihbarat_raporu(bg_tasks, "Yeni Kullanıcı Kaydı", ad_soyad, f"E-posta: {email}", request.client.host)
    return {"basarili": True, "mesaj": "Kayıt başarılı!"}

@app.post("/api/giris")
async def giris_yap(request: Request, response: Response, bg_tasks: BackgroundTasks, s: Session = Depends(db)):
    # Accept JSON and form data
    try:
        data = await request.json()
    except Exception:
        form = await request.form()
        data = dict(form)

    email = data.get("email", "").strip().lower()
    k = s.query(Kullanici).filter_by(email=email, sifre_hash=sifre_hashle(data.get("sifre", ""))).first()
    if not k:
        raise HTTPException(status_code=401, detail="Yanlış şifre.")

    token = session_olustur(k.id)
    k.son_giris = datetime.datetime.utcnow()
    k.son_ip = request.client.host
    s.commit()

    istihbarat_raporu(bg_tasks, "Müşteri Girişi", k.ad_soyad, f"Müşteri panele giriş yaptı. ({k.email})", request.client.host)

    # Return the token in the JSON body in addition to setting a cookie so
    # frontends that cannot rely on cross-site cookies can still operate.
    resp = JSONResponse({"basarili": True, "token": token, "kullanici_id": k.id})
    resp.set_cookie("session", token, httponly=True, max_age=604800, samesite="lax")
    return resp

@app.post("/api/cikis")
def cikis_yap(request: Request, response: Response, bg_tasks: BackgroundTasks):
    token = request.cookies.get("session")
    if token: session_sil(token)
    istihbarat_raporu(bg_tasks, "Müşteri Çıkışı", "Kullanıcı", "Sistemden çıkış yapıldı.", request.client.host)
    resp = JSONResponse({"basarili": True})
    resp.delete_cookie("session")
    return resp

@app.post("/api/talep-olustur")
async def talep_olustur(request: Request, bg_tasks: BackgroundTasks, s: Session = Depends(db)):
    kullanici_id = get_kullanici_id(request)
    if not kullanici_id: raise HTTPException(status_code=401)
    data = await request.json()
    k = s.query(Kullanici).filter_by(id=kullanici_id).first()
    
    talep_tipi = data.get("talep_tipi", "online")
    istek_kodu = data.get("istek_kodu", "").strip().upper()
    if talep_tipi == "offline":
        if not istek_kodu.startswith("REQ-"):
            raise HTTPException(status_code=400, detail="Geçersiz istek kodu formatı. (REQ- ile başlamalıdır)")
        if s.query(LisansTalep).filter_by(istek_kodu=istek_kodu).first():
            raise HTTPException(status_code=409, detail="Bu istek kodu daha önce kullanılmış.")

    if s.query(LisansTalep).filter_by(kullanici_id=kullanici_id, durum="beklemede").first():
        raise HTTPException(status_code=409, detail="Zaten bekleyen talep var.")
        
    s.add(LisansTalep(kullanici_id=k.id, ad_soyad=k.ad_soyad, email=k.email, tur=data.get("tur"), ip_adresi=k.son_ip, talep_tipi=talep_tipi, istek_kodu=istek_kodu if talep_tipi=="offline" else None))
    s.commit()
    tip_str = "OFFLINE" if talep_tipi == "offline" else "ONLINE"
    ek_bilgi = f"\nİstek Kodu: {istek_kodu}" if talep_tipi == "offline" else ""
    istihbarat_raporu(bg_tasks, f"YENİ {tip_str} LİSANS TALEBİ", k.ad_soyad, f"Talep Edilen Tür: {data.get('tur')} | E-posta: {k.email}{ek_bilgi}", request.client.host)
    return {"basarili": True}

@app.get("/api/benim-taleplerim")
def benim_taleplerim(request: Request, s: Session = Depends(db)):
    kid = get_kullanici_id(request)
    if not kid: raise HTTPException(status_code=401)
    talepler = s.query(LisansTalep).filter_by(kullanici_id=kid).order_by(LisansTalep.talep_tar.desc()).all()
    return [{"id": t.id, "tur": t.tur, "durum": t.durum, "tarih": safe_format_datetime(t.talep_tar), "admin_notu": t.admin_notu, "talep_tipi": t.talep_tipi, "istek_kodu": t.istek_kodu, "aktivasyon_kodu": t.aktivasyon_kodu} for t in talepler]

@app.post("/api/mesaj-gonder")
async def mesaj_gonder(request: Request, s: Session = Depends(db)):
    kid = get_kullanici_id(request)
    if not kid: raise HTTPException(status_code=401)
    data = await request.json()
    s.add(Mesaj(kullanici_id=kid, gonderen="kullanici", icerik=data.get("icerik", "")))
    s.commit()
    return {"basarili": True}

@app.get("/api/mesajlarim")
def mesajlarim(request: Request, s: Session = Depends(db)):
    kid = get_kullanici_id(request)
    if not kid: raise HTTPException(status_code=401)
    # Okunmamış admin mesajlarını okundu yap
    s.query(Mesaj).filter_by(kullanici_id=kid, gonderen="admin", okundu=False).update({"okundu": True})
    s.commit()
    mesajlar = s.query(Mesaj).filter_by(kullanici_id=kid).order_by(Mesaj.tarih.asc()).all()
    return [{"id": m.id, "gonderen": m.gonderen, "icerik": m.icerik, "tarih": safe_format_datetime(m.tarih)} for m in mesajlar]

@app.get("/api/profil")
def profil(request: Request, s: Session = Depends(db)):
    kid = get_kullanici_id(request)
    if not kid: raise HTTPException(status_code=401)
    k = s.query(Kullanici).filter_by(id=kid).first()
    if not k: raise HTTPException(status_code=401)
    
    lisans = s.query(Lisans).filter_by(musteri_email=k.email).order_by(Lisans.olusturma_tar.desc()).first()
    l_bilgi = None
    if lisans:
        aktif = lisans.aktif
        kalan = safe_days_left(lisans.bitis_tarihi)
        durum = "aktif" if aktif and (kalan is None or kalan >= 0) else "iptal" if not aktif else "suresi_dolmus"
        if kalan is not None and kalan < 0:
            kalan = 0
        l_bilgi = {
            "kod": lisans.lisans_kodu, 
            "tur": lisans.tur, 
            "bitis": safe_format_date(lisans.bitis_tarihi) if lisans.bitis_tarihi else "Ömür Boyu", 
            "kalan_gun": kalan, 
            "aktif": aktif, 
            "durum": durum
        }
    # Yeni sürüm banner: DB'deki son_surum_tarihi üzerinden 1 gün kontrol
    try:
        _ayar = s.query(Ayarlar).first()
        _yeni_surum = bool(
            _ayar and _ayar.son_surum_tarihi and
            (datetime.datetime.utcnow() - _ayar.son_surum_tarihi).total_seconds() < 86400
        )
    except Exception:
        _yeni_surum = False

    return {
        "ad_soyad": k.ad_soyad,
        "email": k.email,
        "kayit_tar": safe_format_date(k.kayit_tar),
        "lisans": l_bilgi,
        "indirme_linki": "/api/program-indir" if (l_bilgi and l_bilgi["durum"]=="aktif") else None,
        "vt_hash": get_exe_hash(),
        "son_guncelleme": get_exe_date(),
        "yeni_surum_banner": _yeni_surum
    }

@app.post("/api/lisansimi-iptal-et")
async def lisansimi_iptal_et(request: Request, bg_tasks: BackgroundTasks, s: Session = Depends(db)):
    kid = get_kullanici_id(request)
    if not kid: raise HTTPException(status_code=401, detail="Giriş yapmalısınız.")
    k = s.query(Kullanici).filter_by(id=kid).first()
    if not k: raise HTTPException(status_code=401, detail="Geçersiz kullanıcı.")
    
    data = await request.json()
    neden = data.get("neden", "Belirtilmedi")
    
    lisans = s.query(Lisans).filter_by(musteri_email=k.email, aktif=True).order_by(Lisans.olusturma_tar.desc()).first()
    if not lisans:
        raise HTTPException(status_code=404, detail="İptal edilecek aktif lisans bulunamadı.")
        
    lisans.aktif = False
    lisans.iptal_nedeni = neden
    lisans.iptal_tarihi = datetime.datetime.utcnow()
    s.commit()
    
    istihbarat_raporu(bg_tasks, "KULLANICI LİSANS İPTALİ", k.ad_soyad, f"Kod: {lisans.lisans_kodu} | Neden: {neden}", request.client.host)
    
    return {"basarili": True, "mesaj": "Lisansınız iptal edildi."}

@app.get("/api/lisans-gecmisim")
def lisans_gecmisim(request: Request, s: Session = Depends(db)):
    kid = get_kullanici_id(request)
    if not kid: raise HTTPException(status_code=401)
    k = s.query(Kullanici).filter_by(id=kid).first()
    if not k: raise HTTPException(status_code=401)
    
    lisanslar = s.query(Lisans).filter_by(musteri_email=k.email).order_by(Lisans.olusturma_tar.desc()).all()
    sonuc = []
    for l in lisanslar:
        aktif = l.aktif
        kalan = safe_days_left(l.bitis_tarihi)
        durum = "aktif" if aktif and (kalan is None or kalan >= 0) else "iptal" if not aktif else "suresi_dolmus"
        # notlar formatı: "offline|REQ-XXX" veya "offline" veya None
        notlar = l.notlar or ""
        is_offline = notlar == "offline" or notlar.startswith("offline|")
        istek_kodu = notlar.split("|", 1)[1] if "|" in notlar else None
        sonuc.append({
            "kod": l.lisans_kodu,
            "tur": l.tur,
            "durum": durum,
            "olusturma": safe_format_date(l.olusturma_tar),
            "bitis": safe_format_date(l.bitis_tarihi) if l.bitis_tarihi else "Ömür Boyu",
            "aktivasyon": safe_format_date(l.aktivasyon_tar) if l.aktivasyon_tar else None,
            "kalan_gun": kalan,
            "tip": "offline" if is_offline else "online",
            "istek_kodu": istek_kodu
        })
    return sonuc

@app.get("/api/uyelik-turleri-public")
def uyelik_turleri_public(s: Session = Depends(db)):
    return [{"kod": t.kod, "ad": t.ad, "aciklama": t.aciklama} for t in s.query(UyelikTuru).filter_by(aktif=True).order_by(UyelikTuru.sira).all()]

@app.get("/api/program-indir")
def program_indir(request: Request, s: Session = Depends(db)):
    kid = get_kullanici_id(request)
    if not kid: raise HTTPException(status_code=401, detail="Giriş yapmalısınız.")
    k = s.query(Kullanici).filter_by(id=kid).first()
    if not k: raise HTTPException(status_code=401, detail="Geçersiz kullanıcı.")
    
    lisans = s.query(Lisans).filter_by(musteri_email=k.email).order_by(Lisans.olusturma_tar.desc()).first()
    
    kalan = safe_days_left(lisans.bitis_tarihi) if lisans else None
    aktif_mi = bool(lisans and lisans.aktif and (kalan is None or kalan >= 0))
    
    if not aktif_mi:
        raise HTTPException(status_code=403, detail="Aktif lisansınız bulunmuyor.")
        
    exe_path = os.path.join("dosyalar", "OPC_Gateway_Pro.exe")
    if not os.path.exists(exe_path):
        raise HTTPException(status_code=404, detail="Program dosyası sunucuda bulunamadı.")
        
    return FileResponse(exe_path, media_type="application/vnd.microsoft.portable-executable", filename="OPC_Gateway_Pro.exe")


# =====================================================================
# PANEL API (Admin - İstihbarat Dolu)
# =====================================================================
class LisansOlusturIstek(BaseModel):
    musteri_adi: str
    musteri_email: Optional[str] = None
    tur: str
    deneme_saat: Optional[int] = 24
    ozel_gun: Optional[int] = None
    notlar: Optional[str] = None

@app.post("/panel/lisans-olustur")
def lisans_olustur(istek: LisansOlusturIstek, request: Request, bg_tasks: BackgroundTasks, user: PanelUserDto = Depends(yetki_kontrol("lisans_olustur")), s: Session = Depends(db)):
    u_tur = s.query(UyelikTuru).filter_by(kod=istek.tur).first()
    prefix = u_tur.prefix if u_tur and hasattr(u_tur, 'prefix') and u_tur.prefix else "STD"
    kod = lisans_kodu_uret(prefix)
    
    if istek.ozel_gun is not None:
        if istek.ozel_gun == 0:
            bitis = None
        else:
            bitis = datetime.datetime.utcnow() + datetime.timedelta(days=istek.ozel_gun)
    else:
        bitis = bitis_tarihi_hesapla(istek.tur, s, istek.deneme_saat)
        
    s.add(Lisans(lisans_kodu=kod, musteri_adi=istek.musteri_adi, musteri_email=istek.musteri_email, tur=istek.tur, bitis_tarihi=bitis, notlar=istek.notlar))
    s.commit()
    istihbarat_raporu(bg_tasks, "Online Lisans Üretildi", user.tam_isim, f"Müşteri: {istek.musteri_adi}\nTür: {istek.tur}\nKod: {kod}", request.client.host)
    return {"lisans_kodu": kod, "bitis_tarihi": bitis.isoformat() if bitis else "Ömür boyu", "mesaj": f"Lisans oluşturuldu: {kod}"}

@app.post("/panel/iptal")
def iptal_et(lisans_kodu: str, request: Request, bg_tasks: BackgroundTasks, user: PanelUserDto = Depends(yetki_kontrol("lisans_sil")), s: Session = Depends(db)):
    lisans = s.query(Lisans).filter_by(lisans_kodu=lisans_kodu.upper()).first()
    lisans.aktif = False
    s.commit()
    istihbarat_raporu(bg_tasks, "Lisans İptal Edildi", user.tam_isim, f"İptal Edilen Kod: {lisans_kodu}", request.client.host)
    return {"mesaj": f"{lisans_kodu} lisansı iptal edildi."}

@app.delete("/panel/lisans-sil/{lisans_kodu}")
def lisans_sil(lisans_kodu: str, request: Request, bg_tasks: BackgroundTasks, user: PanelUserDto = Depends(yetki_kontrol("lisans_sil")), s: Session = Depends(db)):
    lisans = s.query(Lisans).filter_by(lisans_kodu=lisans_kodu.upper()).first()
    s.delete(lisans)
    s.commit()
    istihbarat_raporu(bg_tasks, "Lisans KALICI OLARAK Silindi", user.tam_isim, f"Silinen Kod: {lisans_kodu}", request.client.host)
    return {"mesaj": f"{lisans_kodu} silindi."}

@app.post("/panel/hwid-sifirla")
def hwid_sifirla(lisans_kodu: str, request: Request, bg_tasks: BackgroundTasks, user: PanelUserDto = Depends(yetki_kontrol("hwid_sifirla")), s: Session = Depends(db)):
    lisans = s.query(Lisans).filter_by(lisans_kodu=lisans_kodu.upper()).first()
    lisans.hwid = None
    lisans.aktivasyon_tar = None
    s.commit()
    istihbarat_raporu(bg_tasks, "HWID Sıfırlandı", user.tam_isim, f"İşlem Yapılan Kod: {lisans_kodu}", request.client.host)
    return {"mesaj": f"HWID sıfırlandı."}

@app.post("/panel/sure-uzat")
def sure_uzat(lisans_kodu: str, gun: int, request: Request, bg_tasks: BackgroundTasks, user: PanelUserDto = Depends(yetki_kontrol("sure_uzat")), s: Session = Depends(db)):
    lisans = s.query(Lisans).filter_by(lisans_kodu=lisans_kodu.upper()).first()
    if not lisans:
        raise HTTPException(status_code=404, detail="Lisans bulunamadı.")
    if lisans.bitis_tarihi is None:
        raise HTTPException(status_code=400, detail="Ömür boyu lisansların süresi uzatılamaz.")
        
    lisans.bitis_tarihi = max(lisans.bitis_tarihi, datetime.datetime.utcnow()) + datetime.timedelta(days=gun)
    lisans.aktif = True
    s.commit()
    istihbarat_raporu(bg_tasks, "Lisans Süresi Uzatıldı", user.tam_isim, f"Kod: {lisans_kodu}\nEklenen: +{gun} Gün", request.client.host)
    return {"mesaj": f"{gun} gün eklendi."}

@app.post("/panel/talep-guncelle")
async def talep_guncelle(request: Request, bg_tasks: BackgroundTasks, user: PanelUserDto = Depends(yetki_kontrol("talep_onayla")), s: Session = Depends(db)):
    data = await request.json()
    talep = s.query(LisansTalep).filter_by(id=data["talep_id"]).first()
    talep.durum = data["durum"]
    talep.admin_notu = data.get('admin_notu', '')
    
    if data["durum"] == "onaylandi":
        u_tur = s.query(UyelikTuru).filter_by(kod=talep.tur).first()
        prefix = u_tur.prefix if u_tur and hasattr(u_tur, 'prefix') and u_tur.prefix else "STD"
        sure = getattr(u_tur, 'sure_gun', 30) or 30
        
        if talep.talep_tipi == "offline":
            # Çevrimdışı (Offline) aktivasyon kodu üretimi
            mesaj = f"{talep.istek_kodu}|{sure}|FULL".encode("utf-8")
            imza = hmac.new(OFFLINE_SECRET_KEY, mesaj, hashlib.sha256).hexdigest()[:16].upper()
            akt_kod = f"ACT-{sure}D-FULL-{imza}"
            talep.aktivasyon_kodu = akt_kod
            # Offline lisansı Lisans tablosuna da kaydet — geçmişte görünsün
            bitis_offline = datetime.datetime.utcnow() + datetime.timedelta(days=sure)
            s.add(Lisans(
                lisans_kodu=akt_kod,
                musteri_adi=talep.ad_soyad,
                musteri_email=talep.email,
                tur=talep.tur,
                bitis_tarihi=bitis_offline,
                notlar=f"offline|{talep.istek_kodu}",
                aktif=True
            ))
            s.commit()
            istihbarat_raporu(bg_tasks, "Offline Talep Onaylandı", user.tam_isim, f"Müşteri: {talep.ad_soyad}\nİstek Kodu: {talep.istek_kodu}\nAktivasyon Kodu: {akt_kod}", request.client.host)
        else:
            # Çevrimiçi (Online) lisans kaydı
            kod = lisans_kodu_uret(prefix)
            s.add(Lisans(lisans_kodu=kod, musteri_adi=talep.ad_soyad, musteri_email=talep.email, tur=talep.tur, bitis_tarihi=bitis_tarihi_hesapla(talep.tur, s)))
            s.commit()
            istihbarat_raporu(bg_tasks, "Online Talep Onaylandı", user.tam_isim, f"Müşteri: {talep.ad_soyad} ({talep.email})\nTalep Türü: {talep.tur}\nNot: {talep.admin_notu}", request.client.host)
    else:
        s.commit()
        istihbarat_raporu(bg_tasks, "Talep REDDEDİLDİ", user.tam_isim, f"Müşteri: {talep.ad_soyad} ({talep.email})\nTalep Türü: {talep.tur}\nNot: {talep.admin_notu}", request.client.host)

    return {"basarili": True}

@app.post("/panel/admin-mesaj-gonder")
async def admin_mesaj_gonder(request: Request, bg_tasks: BackgroundTasks, user: PanelUserDto = Depends(yetki_kontrol("mesaj_yaz")), s: Session = Depends(db)):
    data = await request.json()
    s.add(Mesaj(kullanici_id=data["kullanici_id"], gonderen="admin", icerik=data.get("icerik", ""), okundu=False))
    s.commit()
    istihbarat_raporu(bg_tasks, "Kullanıcıya Mesaj Gönderildi", user.tam_isim, f"Alıcı ID: {data['kullanici_id']}\nMesaj: {data.get('icerik')}", request.client.host)
    return {"basarili": True}

@app.post("/panel/ip-ban-ekle")
async def ip_ban_ekle(request: Request, bg_tasks: BackgroundTasks, user: PanelUserDto = Depends(yetki_kontrol("ip_ban")), s: Session = Depends(db)):
    data = await request.json()
    s.add(IpBan(ip=data["ip"], sebep=data.get("sebep", "")))
    s.commit()
    istihbarat_raporu(bg_tasks, "IP Banlandı", user.tam_isim, f"Banlanan IP: {data['ip']}\nSebep: {data.get('sebep')}", request.client.host)
    return {"mesaj": f"IP banlandı."}

@app.post("/panel/ip-ban-kaldir")
async def ip_ban_kaldir(request: Request, bg_tasks: BackgroundTasks, user: PanelUserDto = Depends(yetki_kontrol("ip_ban")), s: Session = Depends(db)):
    data = await request.json()
    ban = s.query(IpBan).filter_by(ip=data["ip"]).first()
    ban.aktif = False
    s.commit()
    istihbarat_raporu(bg_tasks, "IP Banı Kaldırıldı", user.tam_isim, f"Kaldırılan IP: {data['ip']}", request.client.host)
    return {"mesaj": f"IP banı kaldırıldı."}

# Diğer get metotları (loglar, istatistikler, listeler) aynı kalıyor...
@app.get("/panel/lisanslar")
def lisanslar_listele(filtre: str = "hepsi", user: PanelUserDto = Depends(panel_dogrula), s: Session = Depends(db)):
    simdi = datetime.datetime.utcnow()
    liste = s.query(Lisans).order_by(Lisans.olusturma_tar.desc()).all()
    sonuc = []
    for l in liste:
        durum = "aktif" if l.aktif and (not l.bitis_tarihi or simdi <= l.bitis_tarihi) else "iptal" if not l.aktif else "suresi_dolmus"
        if filtre != "hepsi" and filtre != durum: continue
        sonuc.append({
            "lisans_kodu": l.lisans_kodu, "musteri_adi": l.musteri_adi, "musteri_email": l.musteri_email,
            "tur": l.tur, "aktif": l.aktif, "durum": durum, "hwid": l.hwid or "Yok",
            "bitis_tarihi": l.bitis_tarihi.strftime("%d.%m.%Y") if l.bitis_tarihi else "Ömür boyu",
            "son_checkin": l.son_checkin.strftime("%d.%m.%Y") if l.son_checkin else "Hiç",
            "aktivasyon": l.aktivasyon_tar.strftime("%d.%m.%Y") if l.aktivasyon_tar else "Yok",
            "notlar": l.notlar or "", "iptal_nedeni": l.iptal_nedeni or "",
            "uretilen_tip": getattr(l, "uretilen_tip", "online") or "online",
            "istek_kodu": getattr(l, "istek_kodu_db", "") or "",
            "sure_gun": getattr(l, "sure_gun_db", "") or "",
            "yetki": getattr(l, "yetki_seviyesi", "") or ""
        })
    return sonuc

@app.get("/panel/talepler")
def panel_talepler(user: PanelUserDto = Depends(panel_dogrula), s: Session = Depends(db)):
    return [{"id": t.id, "kullanici_id": t.kullanici_id, "ad_soyad": t.ad_soyad, "email": t.email, "tur": t.tur, "durum": t.durum, "tarih": t.talep_tar.strftime("%d.%m.%Y %H:%M"), "ip": t.ip_adresi, "admin_notu": t.admin_notu or "", "talep_tipi": t.talep_tipi, "istek_kodu": t.istek_kodu, "aktivasyon_kodu": t.aktivasyon_kodu} for t in s.query(LisansTalep).order_by(LisansTalep.talep_tar.desc()).all()]

@app.get("/panel/iptal-istatistikleri")
def iptal_istatistikleri(user: PanelUserDto = Depends(panel_dogrula), s: Session = Depends(db)):
    return {"ozet": {"toplam": s.query(Lisans).count(), "aktif": 0, "biten": 0, "iptal": 0}, "nedenler": []}

@app.get("/panel/kullanicilar")
def panel_kullanicilar(user: PanelUserDto = Depends(panel_dogrula), s: Session = Depends(db)):
    kullanicilar = s.query(Kullanici).order_by(Kullanici.kayit_tar.desc()).all()
    sonuc = []
    for k in kullanicilar:
        l = s.query(Lisans).filter_by(musteri_email=k.email, aktif=True).first()
        sonuc.append({"id": k.id, "ad_soyad": k.ad_soyad, "email": k.email, "email_dogrulandi": k.email_dogrulandi, "kayit_tar": k.kayit_tar.strftime("%d.%m.%Y"), "son_giris": k.son_giris.strftime("%d.%m.%Y") if k.son_giris else "Hiç", "son_ip": k.son_ip or "-", "lisans_kodu": l.lisans_kodu if l else None, "lisans_tur": l.tur if l else None})
    return sonuc

@app.delete("/panel/kullanici-sil/{kullanici_id}")
def kullanici_sil(kullanici_id: str, request: Request, bg_tasks: BackgroundTasks, user: PanelUserDto = Depends(panel_dogrula), s: Session = Depends(db)):
    k = s.query(Kullanici).filter_by(id=kullanici_id).first()
    s.query(Lisans).filter_by(musteri_email=k.email).update({"aktif": False})
    s.delete(k)
    s.commit()
    istihbarat_raporu(bg_tasks, "Müşteri Silindi", user.tam_isim, f"Silinen: {k.ad_soyad} ({k.email})", request.client.host)
    return {"mesaj": f"Kullanıcı silindi."}

@app.put("/panel/kullanici-duzenle/{kullanici_id}")
async def kullanici_duzenle(
    kullanici_id: str,
    request: Request,
    bg_tasks: BackgroundTasks,
    user: PanelUserDto = Depends(panel_dogrula),
    s: Session = Depends(db)
):
    """Ana Admin'in müşteri kullanıcıların şifresini sıfırlayabilmesi ve not ekleyebilmesi için."""
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="Yalnızca admin düzenleyebilir.")
    data = await request.json()
    k = s.query(Kullanici).filter_by(id=kullanici_id).first()
    if not k:
        raise HTTPException(status_code=404, detail="Kullanıcı bulunamadı.")
    degisiklik = []
    if data.get("sifre"):
        if len(data["sifre"]) < 6:
            raise HTTPException(status_code=400, detail="Şifre en az 6 karakter olmalıdır.")
        k.sifre_hash = sifre_hashle(data["sifre"])
        degisiklik.append("Şifre sıfırlandı")
    if "not" in data:
        # Notları lisans kaydına ekle (mevcut aktif lisans varsa)
        lisans = s.query(Lisans).filter_by(musteri_email=k.email, aktif=True).order_by(Lisans.olusturma_tar.desc()).first()
        if lisans:
            lisans.notlar = data["not"]
            degisiklik.append("Lisans notu güncellendi")
    s.commit()
    panel_log_yaz(s, user.kullanici_adi, "Müşteri Düzenlendi", f"ID: {kullanici_id} | {', '.join(degisiklik)}")
    istihbarat_raporu(bg_tasks, "Müşteri Bilgisi Düzenlendi", user.tam_isim, f"Kullanıcı: {k.ad_soyad} ({k.email})\n{', '.join(degisiklik)}", request.client.host)
    return {"basarili": True, "mesaj": "Değişiklikler kaydedildi."}

@app.post("/panel/uyelik-tur-ekle")
async def uyelik_tur_ekle(request: Request, bg_tasks: BackgroundTasks, user: PanelUserDto = Depends(yetki_kontrol("uyelik_tur")), s: Session = Depends(db)):
    data = await request.json()
    s.add(UyelikTuru(kod=data["kod"], ad=data["ad"], aciklama=data.get("aciklama", ""), sira=data.get("sira", 99), sure_gun=data.get("sure_gun", 30), prefix=data.get("prefix", "STD").upper()[:10]))
    s.commit()
    istihbarat_raporu(bg_tasks, "Yeni Üyelik Türü Eklendi", user.tam_isim, f"Tür: {data['ad']} ({data['kod']})", request.client.host)
    return {"basarili": True}

class GirisIstek(BaseModel):
    kullanici: str
    sifre: str

@app.post("/panel/giris")
def panel_giris_yap(istek: GirisIstek, request: Request, bg_tasks: BackgroundTasks, s: Session = Depends(db)):
    kadi_gercek, sifre_hash_gercek = get_ana_admin_creds(s)
    if istek.kullanici == kadi_gercek and sifre_hashle(istek.sifre) == sifre_hash_gercek:
        istihbarat_raporu(bg_tasks, "Admin Panel Girişi", "Ana Admin", "Sisteme giriş yapıldı.", request.client.host)
        return {"basarili": True, "is_admin": True, "kullanici_adi": kadi_gercek, "isim_soyad": "Ana Admin", "yetkiler": {}}
        
    pk = s.query(PanelKullanici).filter_by(kullanici_adi=istek.kullanici, sifre_hash=sifre_hashle(istek.sifre)).first()
    if pk:
        istihbarat_raporu(bg_tasks, "Yetkili Panel Girişi", f"{pk.isim_soyad} ({pk.kullanici_adi})", "Sisteme giriş yapıldı.", request.client.host)
        pk.son_giris = datetime.datetime.utcnow()
        s.commit()
        return {"basarili": True, "is_admin": pk.is_admin, "kullanici_adi": pk.kullanici_adi, "isim_soyad": pk.isim_soyad, "yetkiler": {}}
    raise HTTPException(status_code=401, detail="Panel kullanici adi veya sifresi yanlis.")

class YetkiliEkleIstek(BaseModel):
    kullanici_adi: str
    isim_soyad: str
    email: str
    sifre: str
    yetkiler: dict

@app.post("/panel/yetkili-ekle")
def panel_yetkili_ekle(istek: YetkiliEkleIstek, request: Request, bg_tasks: BackgroundTasks, user: PanelUserDto = Depends(yetki_kontrol("kullanici_ekle")), s: Session = Depends(db)):
    y = PanelKullanici(kullanici_adi=istek.kullanici_adi, isim_soyad=istek.isim_soyad, email=istek.email, sifre_hash=sifre_hashle(istek.sifre))
    s.add(y)
    s.commit()
    istihbarat_raporu(bg_tasks, "Yeni Alt Yetkili Eklendi", user.tam_isim, f"Eklenen Yetkili: {istek.isim_soyad} ({istek.kullanici_adi})", request.client.host)
    return {"basarili": True}

@app.delete("/panel/yetkili-sil/{yetkili_id}")
def panel_yetkili_sil(yetkili_id: int, request: Request, bg_tasks: BackgroundTasks, user: PanelUserDto = Depends(panel_dogrula), s: Session = Depends(db)):
    y = s.query(PanelKullanici).filter_by(id=yetkili_id).first()
    istihbarat_raporu(bg_tasks, "Alt Yetkili Silindi", user.tam_isim, f"Silinen Yetkili: {y.kullanici_adi}", request.client.host)
    s.delete(y)
    s.commit()
    return {"basarili": True}

class OfflineLisansIstek(BaseModel):
    istek_kodu: str
    sure_gun: int
    yetki: str
    kime_uretildi: str

@app.post("/panel/offline-lisans-uret")
def offline_lisans_uret(istek: OfflineLisansIstek, request: Request, bg_tasks: BackgroundTasks, user: PanelUserDto = Depends(yetki_kontrol("offline_lisans")), s: Session = Depends(db)):
    mesaj = f"{istek.istek_kodu}|{istek.sure_gun}|{istek.yetki}".encode("utf-8")
    imza = hmac.new(OFFLINE_SECRET_KEY, mesaj, hashlib.sha256).hexdigest()[:16].upper()
    akt_kod = f"ACT-{istek.sure_gun}D-{istek.yetki}-{imza}"
    
    bitis = datetime.datetime.utcnow() + datetime.timedelta(days=istek.sure_gun) if istek.sure_gun > 0 else None
    
    l = Lisans(
        lisans_kodu=akt_kod,
        musteri_adi=istek.kime_uretildi,
        tur="Offline",
        bitis_tarihi=bitis,
        notlar=f"offline|{istek.istek_kodu}",
        aktif=True,
        uretilen_tip="offline",
        istek_kodu_db=istek.istek_kodu,
        sure_gun_db=istek.sure_gun,
        yetki_seviyesi=istek.yetki
    )
    s.add(l)
    s.commit()
    
    detay = f"İstek Kodu: {istek.istek_kodu}\nMüşteri: {istek.kime_uretildi}\nSüre: {istek.sure_gun} Gün\nYetki: {istek.yetki}\n\nÜretilen Kod: {akt_kod}"
    istihbarat_raporu(bg_tasks, "Çevrimdışı (Offline) Lisans Üretildi", user.tam_isim, detay, request.client.host)
    return {"basarili": True, "aktivasyon_kodu": akt_kod, "istek_kodu": istek.istek_kodu, "sure_gun": istek.sure_gun, "yetki": istek.yetki}

@app.get("/panel/loglar")
def loglar(son: int = 100, user: PanelUserDto = Depends(panel_dogrula), s: Session = Depends(db)):
    logs = s.query(Log).order_by(Log.tarih.desc()).limit(son).all()
    return [{"tarih": l.tarih.strftime("%d.%m.%Y %H:%M:%S"), "islem": l.islem, "lisans_kodu": l.lisans_kodu, "hwid": l.hwid, "ip": l.ip, "mesaj": l.mesaj} for l in logs]

@app.get("/panel/mesajlar-ozet")
def panel_mesajlar_ozet(user: PanelUserDto = Depends(panel_dogrula), s: Session = Depends(db)):
    """Her kullanıcı için son mesaj ve okunmamış sayısı"""
    kullanicilar = s.query(Kullanici).all()
    sonuc = []
    for k in kullanicilar:
        toplam = s.query(Mesaj).filter_by(kullanici_id=k.id).count()
        if toplam == 0:
            continue
        okunmamis = s.query(Mesaj).filter_by(kullanici_id=k.id, gonderen="kullanici", okundu=False).count()
        son_mesaj = s.query(Mesaj).filter_by(kullanici_id=k.id).order_by(Mesaj.tarih.desc()).first()
        lisans = s.query(Lisans).filter_by(musteri_email=k.email, aktif=True).order_by(Lisans.olusturma_tar.desc()).first()
        kalan = None
        if lisans and lisans.bitis_tarihi:
            kalan = max(0, (lisans.bitis_tarihi - datetime.datetime.utcnow()).days)
        sonuc.append({
            "kullanici_id": k.id,
            "ad_soyad": k.ad_soyad,
            "email": k.email,
            "son_ip": k.son_ip,
            "okunmamis": okunmamis,
            "son_mesaj": son_mesaj.icerik[:60] if son_mesaj else "",
            "son_mesaj_tar": son_mesaj.tarih.strftime("%d.%m.%Y %H:%M") if son_mesaj else "",
            "lisans_kodu": lisans.lisans_kodu if lisans else None,
            "lisans_tur": lisans.tur if lisans else None,
            "lisans_bitis": lisans.bitis_tarihi.strftime("%d.%m.%Y") if (lisans and lisans.bitis_tarihi) else ("Ömür Boyu" if lisans else None),
            "kalan_gun": kalan,
        })
    sonuc.sort(key=lambda x: x["okunmamis"], reverse=True)
    return sonuc

@app.get("/panel/kullanici-mesajlar/{kullanici_id}")
def kullanici_mesajlari(kullanici_id: str, user: PanelUserDto = Depends(panel_dogrula), s: Session = Depends(db)):
    s.query(Mesaj).filter_by(kullanici_id=kullanici_id, gonderen="kullanici", okundu=False).update({"okundu": True})
    s.commit()
    mesajlar = s.query(Mesaj).filter_by(kullanici_id=kullanici_id).order_by(Mesaj.tarih.asc()).all()
    k = s.query(Kullanici).filter_by(id=kullanici_id).first()
    lisans = s.query(Lisans).filter_by(musteri_email=k.email if k else "", aktif=True).order_by(Lisans.olusturma_tar.desc()).first()
    kalan = None
    if lisans and lisans.bitis_tarihi:
        kalan = max(0, (lisans.bitis_tarihi - datetime.datetime.utcnow()).days)
    return {
        "kullanici": {
            "id": k.id if k else kullanici_id,
            "ad_soyad": k.ad_soyad if k else "?",
            "email": k.email if k else "?",
            "son_ip": k.son_ip if k else "?",
            "kayit_tar": k.kayit_tar.strftime("%d.%m.%Y") if k else "?",
        },
        "lisans": {
            "kod": lisans.lisans_kodu if lisans else None,
            "tur": lisans.tur if lisans else None,
            "bitis": lisans.bitis_tarihi.strftime("%d.%m.%Y") if (lisans and lisans.bitis_tarihi) else ("Ömür Boyu" if lisans else None),
            "kalan_gun": kalan,
            "aktif": lisans.aktif if lisans else False,
        } if lisans else None,
        "mesajlar": [{"id": m.id, "gonderen": m.gonderen, "icerik": m.icerik, "tarih": m.tarih.strftime("%d.%m.%Y %H:%M")} for m in mesajlar],
    }

@app.get("/panel/ip-banlar")
def ip_banlar(user: PanelUserDto = Depends(yetki_kontrol("ip_ban")), s: Session = Depends(db)):
    banlar = s.query(IpBan).order_by(IpBan.tarih.desc()).all()
    return [{"id": b.id, "ip": b.ip, "sebep": b.sebep or "", "tarih": b.tarih.strftime("%d.%m.%Y %H:%M"), "aktif": b.aktif} for b in banlar]

@app.get("/panel/uyelik-turleri")
def panel_uyelik_turleri(user: PanelUserDto = Depends(yetki_kontrol("uyelik_tur")), s: Session = Depends(db)):
    turler = s.query(UyelikTuru).order_by(UyelikTuru.sira).all()
    return [{"id": t.id, "kod": t.kod, "ad": t.ad, "aciklama": t.aciklama, "aktif": t.aktif, "sira": t.sira, "sure_gun": getattr(t, 'sure_gun', 30), "prefix": getattr(t, 'prefix', 'STD')} for t in turler]

@app.post("/panel/uyelik-tur-guncelle")
async def uyelik_tur_guncelle(request: Request, user: PanelUserDto = Depends(yetki_kontrol("uyelik_tur")), s: Session = Depends(db)):
    data = await request.json()
    t = s.query(UyelikTuru).filter_by(id=data["id"]).first()
    if not t:
        raise HTTPException(status_code=404, detail="Tür bulunamadı.")
    if "aktif" in data:
        t.aktif = data["aktif"]
    if "sure_gun" in data:
        t.sure_gun = int(data["sure_gun"])
    if "prefix" in data:
        t.prefix = str(data["prefix"]).upper()[:10]
    s.commit()
    panel_log_yaz(s, user.kullanici_adi, "Üyelik Türü Güncellendi", f"ID: {data['id']}")
    return {"basarili": True}

@app.delete("/panel/uyelik-tur-sil/{tur_id}")
def uyelik_tur_sil(tur_id: int, user: PanelUserDto = Depends(yetki_kontrol("uyelik_tur")), s: Session = Depends(db)):
    t = s.query(UyelikTuru).filter_by(id=tur_id).first()
    if not t:
        raise HTTPException(status_code=404, detail="Tür bulunamadı.")
    panel_log_yaz(s, user.kullanici_adi, "Üyelik Türü Silindi", f"Kod: {t.kod}")
    s.delete(t)
    s.commit()
    return {"basarili": True}

@app.get("/panel/yetkililer")
def panel_yetkililer_getir(user: PanelUserDto = Depends(panel_dogrula), s: Session = Depends(db)):
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="Yalnızca admin görebilir.")
    pk = s.query(PanelKullanici).all()
    return [{
        "id": p.id,
        "kullanici_adi": p.kullanici_adi,
        "isim_soyad": p.isim_soyad,
        "email": p.email,
        "is_admin": p.is_admin,
        "telegram_chat_id": p.telegram_chat_id or "",
        "telegram_bildirim_alabilir": p.telegram_bildirim_alabilir,
        "son_giris": p.son_giris.strftime("%d.%m.%Y %H:%M") if p.son_giris else "-",
        "son_cikis": p.son_cikis.strftime("%d.%m.%Y %H:%M") if p.son_cikis else "-",
        "yetkiler": {
            "lisans_olustur": p.yetki_lisans_olustur,
            "lisans_sil": p.yetki_lisans_sil,
            "hwid_sifirla": p.yetki_hwid_sifirla,
            "sure_uzat": p.yetki_sure_uzat,
            "talep_onayla": p.yetki_talep_onayla,
            "kullanici_ekle": p.yetki_kullanici_ekle,
            "mesaj_yaz": p.yetki_mesaj_yaz,
            "ip_ban": p.yetki_ip_ban,
            "uyelik_tur": p.yetki_uyelik_tur,
            "offline_lisans": p.yetki_offline_lisans,
        }
    } for p in pk]

@app.get("/panel/panel-loglari")
def panel_loglari_getir(user: PanelUserDto = Depends(panel_dogrula), s: Session = Depends(db)):
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="Yalnızca admin görebilir.")
    plogs = s.query(PanelLog).order_by(PanelLog.tarih.desc()).limit(200).all()
    return [{
        "tarih": pl.tarih.strftime("%d.%m.%Y %H:%M:%S"),
        "kullanici_adi": pl.kullanici_adi,
        "islem": pl.islem,
        "detay": pl.detay or ""
    } for pl in plogs]

@app.post("/panel/cikis")
def panel_cikis_yap(user: PanelUserDto = Depends(panel_dogrula), s: Session = Depends(db)):
    if not user.is_admin and user.kullanici_adi != PANEL_KULLANICI:
        pk = s.query(PanelKullanici).filter_by(kullanici_adi=user.kullanici_adi).first()
        if pk:
            pk.son_cikis = datetime.datetime.utcnow()
            s.commit()
    panel_log_yaz(s, user.kullanici_adi, "Çıkış Yaptı")
    return {"basarili": True}

@app.put("/panel/yetkili-guncelle/{yetkili_id}")
async def panel_yetkili_guncelle(
    yetkili_id: int,
    request: Request,
    user: PanelUserDto = Depends(panel_dogrula),
    s: Session = Depends(db)
):
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="Yalnızca admin güncelleyebilir.")
    data = await request.json()
    y = s.query(PanelKullanici).filter_by(id=yetkili_id).first()
    if not y:
        raise HTTPException(status_code=404, detail="Yetkili bulunamadı.")
    yetki_map = {
        "lisans_olustur": "yetki_lisans_olustur",
        "lisans_sil":     "yetki_lisans_sil",
        "hwid_sifirla":   "yetki_hwid_sifirla",
        "sure_uzat":      "yetki_sure_uzat",
        "talep_onayla":   "yetki_talep_onayla",
        "kullanici_ekle": "yetki_kullanici_ekle",
        "mesaj_yaz":      "yetki_mesaj_yaz",
        "ip_ban":         "yetki_ip_ban",
        "uyelik_tur":     "yetki_uyelik_tur",
        "offline_lisans": "yetki_offline_lisans",
    }
    yetkiler = data.get("yetkiler", {})
    for key, col in yetki_map.items():
        if key in yetkiler:
            setattr(y, col, bool(yetkiler[key]))
            
    if "telegram_chat_id" in data:
        y.telegram_chat_id = data["telegram_chat_id"]
    if "telegram_bildirim_alabilir" in data:
        y.telegram_bildirim_alabilir = data["telegram_bildirim_alabilir"]
    if data.get("sifre"):
        y.sifre_hash = sifre_hashle(data["sifre"])
        
    s.commit()
    panel_log_yaz(s, user.kullanici_adi, "Yetkili Güncelledi", f"ID: {yetkili_id}")
    return {"basarili": True}

class AdminGuncelleIstek(BaseModel):
    yeni_kullanici: str
    yeni_sifre: str

@app.post("/panel/admin-guncelle")
def admin_guncelle(istek: AdminGuncelleIstek, user: PanelUserDto = Depends(panel_dogrula), s: Session = Depends(db)):
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="Yalnızca ana admin değiştirebilir.")

    ayar = s.query(Ayarlar).first()
    if not ayar:
        ayar = Ayarlar()
        s.add(ayar)

    ayar.admin_kullanici = istek.yeni_kullanici
    ayar.admin_sifre_hash = sifre_hashle(istek.yeni_sifre)
    s.commit()
    panel_log_yaz(s, user.kullanici_adi, "Admin Bilgilerini Değiştirdi")
    return {"basarili": True, "mesaj": "Admin bilgileri güncellendi. Lütfen tekrar giriş yapın."}


PANEL_HTML = r"""<!DOCTYPE html>
<html lang="tr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>OPC Gateway — Lisans Paneli</title>
<style>
* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: system-ui, sans-serif; background: #0f1117; color: #e0e0e0; min-height: 100vh; }
a { color: inherit; text-decoration: none; }

/* Login overlay */
#login-overlay { position: fixed; inset: 0; background: rgba(0,0,0,0.85); display: flex; align-items: center; justify-content: center; z-index: 999; backdrop-filter: blur(6px); }
#login-box { background: #1a1d2e; border: 1px solid #2a2d3e; border-radius: 12px; padding: 36px; width: 340px; text-align: center; }
#login-box h2 { color: #5b8cff; margin-bottom: 24px; font-size: 20px; }
#login-box input { width: 100%; background: #0f1117; border: 1px solid #2a2d3e; border-radius: 6px; padding: 10px 12px; color: #e0e0e0; font-size: 14px; margin-bottom: 12px; }
#login-box input:focus { outline: none; border-color: #5b8cff; }
#login-box button { width: 100%; background: #5b8cff; color: white; border: none; border-radius: 6px; padding: 11px; font-size: 14px; font-weight: 600; cursor: pointer; }
#login-box button:hover { background: #4a7aff; }
#login-hata { color: #ff6b6b; font-size: 13px; margin-top: 8px; min-height: 20px; }

/* Layout */
.sidebar { position: fixed; left: 0; top: 0; bottom: 0; width: 220px; background: #1a1d2e; border-right: 1px solid #2a2d3e; padding: 20px 0; display: flex; flex-direction: column; overflow-y: auto; }
.sidebar-logo { padding: 0 20px 20px; border-bottom: 1px solid #2a2d3e; margin-bottom: 12px; }
.sidebar-logo h1 { font-size: 15px; font-weight: 700; color: #5b8cff; }
.sidebar-logo p { font-size: 11px; color: #666; margin-top: 2px; }
.nav-item { display: flex; align-items: center; gap: 10px; padding: 10px 20px; font-size: 13px; color: #aaa; cursor: pointer; transition: all 0.15s; position: relative; }
.nav-item:hover { background: #222540; color: #e0e0e0; }
.nav-item.active { background: #222540; color: #5b8cff; border-right: 3px solid #5b8cff; }
.nav-item .badge { background: #ff4757; color: white; border-radius: 10px; padding: 1px 7px; font-size: 11px; font-weight: 700; margin-left: auto; }
.nav-icon { font-size: 16px; width: 20px; text-align: center; }

/* Accordion Sidebar */
.acc-header { display: flex; align-items: center; gap: 10px; padding: 10px 20px; font-size: 13px; color: #aaa; cursor: pointer; transition: all 0.15s; user-select: none; }
.acc-header:hover { background: #222540; color: #e0e0e0; }
.acc-header.active { background: #222540; color: #5b8cff; border-right: 3px solid #5b8cff; }
.acc-content { display: none; background: #121420; padding: 4px 0; }
.acc-content.show { display: block; }
.acc-item { padding: 8px 20px 8px 46px; font-size: 12px; color: #888; cursor: pointer; transition: all 0.15s; display: block; position: relative; }
.acc-item:hover { color: #e0e0e0; background: #1a1d2e; }
.acc-item.active { color: #5b8cff; background: #1a1d2e; }
.acc-item.active::before { content: ''; position: absolute; left: 24px; top: 50%; transform: translateY(-50%); width: 4px; height: 4px; border-radius: 50%; background: #5b8cff; }
.acc-chevron { margin-left: auto; font-size: 10px; transition: transform 0.2s; }
.acc-header.open .acc-chevron { transform: rotate(90deg); }

/* Sub Tabs for Yeni Lisans */
.sub-tabs { display: flex; gap: 2px; background: #0f1117; padding: 4px; border-radius: 8px; margin-bottom: 16px; border: 1px solid #2a2d3e; }
.sub-tab { flex: 1; text-align: center; padding: 8px 12px; font-size: 12px; font-weight: 600; color: #888; cursor: pointer; border-radius: 6px; transition: all 0.2s; }
.sub-tab:hover { color: #e0e0e0; }
.sub-tab.active { background: #222540; color: #5b8cff; }
.sub-pane { display: none; }
.sub-pane.active { display: block; }

.main { margin-left: 220px; padding: 24px; position: relative; }
.page { display: none; }
.page.active { display: block; }
.page-title { font-size: 20px; font-weight: 700; color: #e0e0e0; margin-bottom: 20px; }

/* Greeting */
#panel-greeting { position: absolute; right: 24px; top: 24px; font-size: 14px; font-weight: 600; color: #8a9bc0; z-index: 10; }


/* Cards */
.card { background: #1a1d2e; border: 1px solid #2a2d3e; border-radius: 10px; padding: 20px; margin-bottom: 16px; }
.card h3 { font-size: 14px; font-weight: 600; color: #5b8cff; margin-bottom: 14px; }

/* Form elements */
input[type=text], input[type=email], input[type=number], input[type=password], select, textarea {
  background: #0f1117; border: 1px solid #2a2d3e; border-radius: 6px; padding: 9px 12px; color: #e0e0e0; font-size: 13px; width: 100%; margin-bottom: 8px;
}
input:focus, select:focus, textarea:focus { outline: none; border-color: #5b8cff; }
textarea { min-height: 80px; resize: vertical; }

/* Buttons */
.btn { border: none; border-radius: 6px; padding: 8px 18px; font-size: 13px; font-weight: 600; cursor: pointer; transition: all 0.15s; display: inline-flex; align-items: center; gap: 6px; }
.btn-primary { background: #5b8cff; color: white; }
.btn-primary:hover { background: #4a7aff; }
.btn-danger { background: #c62828; color: white; }
.btn-danger:hover { background: #b71c1c; }
.btn-success { background: #2e7d32; color: white; }
.btn-success:hover { background: #1b5e20; }
.btn-warning { background: #e65100; color: white; }
.btn-warning:hover { background: #bf360c; }
.btn-ghost { background: transparent; border: 1px solid #2a2d3e; color: #aaa; }
.btn-ghost:hover { border-color: #5b8cff; color: #5b8cff; }
.btn-sm { padding: 5px 12px; font-size: 12px; }
.row-btns { display: flex; gap: 8px; flex-wrap: wrap; margin-top: 4px; }

/* Tables */
.tbl-wrap { overflow-x: auto; }
table { width: 100%; border-collapse: collapse; font-size: 12px; }
th { background: #222540; color: #888; text-transform: uppercase; font-size: 11px; letter-spacing: 0.5px; padding: 10px 12px; text-align: left; }
td { padding: 10px 12px; border-bottom: 1px solid #1e2033; vertical-align: middle; color: #ccc; }
tr:hover td { background: #1e2033; }
code { font-family: monospace; font-size: 12px; background: #222540; padding: 2px 6px; border-radius: 4px; color: #7eb8ff; }

/* Badges */
.badge { display: inline-block; padding: 2px 9px; border-radius: 10px; font-size: 11px; font-weight: 600; }
.b-aktif { background: #1b5e2033; color: #4caf50; border: 1px solid #2e7d3255; }
.b-pasif { background: #b71c1c22; color: #ef9a9a; border: 1px solid #c6282833; }
.b-beklemede { background: #e65100; color: white; }
.b-onaylandi { background: #2e7d32; color: white; }
.b-reddedildi { background: #c62828; color: white; }
.b-aylik { background: #1565c033; color: #90caf9; border: 1px solid #1565c055; }
.b-yillik { background: #4a148c33; color: #ce93d8; border: 1px solid #4a148c55; }
.b-omur { background: #1b5e2033; color: #a5d6a7; border: 1px solid #2e7d3255; }
.b-deneme { background: #e6510033; color: #ffcc80; border: 1px solid #e6510055; }

/* Terminal / log */
#log-output { background: #0a0c14; color: #00e676; font-family: monospace; font-size: 11px; padding: 14px; border-radius: 6px; min-height: 120px; max-height: 360px; overflow-y: auto; white-space: pre-wrap; border: 1px solid #1e2033; }

/* Stat cards */
.stats { display: grid; grid-template-columns: repeat(auto-fill, minmax(160px, 1fr)); gap: 12px; margin-bottom: 20px; }
.stat-card { background: #1a1d2e; border: 1px solid #2a2d3e; border-radius: 10px; padding: 16px; }
.stat-card .val { font-size: 28px; font-weight: 700; color: #5b8cff; }
.stat-card .lbl { font-size: 12px; color: #666; margin-top: 4px; }

/* Messages */
.msg-list { display: flex; flex-direction: column; gap: 8px; max-height: 420px; overflow-y: auto; padding-right: 4px; }
.msg-bubble { max-width: 80%; padding: 10px 14px; border-radius: 10px; font-size: 13px; line-height: 1.6; }
.msg-bubble.kullanici { background: #222540; color: #ccc; align-self: flex-start; border-bottom-left-radius: 2px; }
.msg-bubble.admin { background: #5b8cff22; color: #90caf9; align-self: flex-end; border-bottom-right-radius: 2px; border: 1px solid #5b8cff33; }
.msg-time { font-size: 10px; color: #555; margin-top: 4px; }
.msg-sender { display: flex; flex-direction: column; }
.msg-sender.right { align-items: flex-end; }

/* User detail card */
.user-detail { background: #0f1117; border: 1px solid #2a2d3e; border-radius: 8px; padding: 14px; margin-bottom: 14px; font-size: 13px; }
.user-detail .row { display: flex; gap: 24px; flex-wrap: wrap; }
.user-detail .field { display: flex; flex-direction: column; gap: 3px; }
.user-detail .field label { font-size: 11px; color: #555; text-transform: uppercase; letter-spacing: 0.5px; }
.user-detail .field span { color: #ccc; font-weight: 500; }

/* Konuşma listesi */
.conv-list { display: flex; flex-direction: column; gap: 2px; }
.conv-item { display: flex; align-items: center; gap: 12px; padding: 12px 14px; border-radius: 8px; cursor: pointer; transition: background 0.15s; border: 1px solid transparent; }
.conv-item:hover { background: #222540; }
.conv-item.active { background: #222540; border-color: #5b8cff33; }
.conv-avatar { width: 38px; height: 38px; border-radius: 50%; background: #5b8cff33; color: #5b8cff; display: flex; align-items: center; justify-content: center; font-weight: 700; font-size: 15px; flex-shrink: 0; }
.conv-info { flex: 1; min-width: 0; }
.conv-name { font-size: 13px; font-weight: 600; color: #e0e0e0; }
.conv-preview { font-size: 12px; color: #666; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; margin-top: 2px; }
.conv-meta { display: flex; flex-direction: column; align-items: flex-end; gap: 4px; flex-shrink: 0; }
.unread-dot { background: #ff4757; color: white; border-radius: 10px; padding: 1px 7px; font-size: 11px; font-weight: 700; }

/* Split layout for messages */
.msg-split { display: grid; grid-template-columns: 280px 1fr; gap: 16px; height: calc(100vh - 140px); }
.msg-left { background: #1a1d2e; border: 1px solid #2a2d3e; border-radius: 10px; overflow-y: auto; padding: 12px; }
.msg-right { background: #1a1d2e; border: 1px solid #2a2d3e; border-radius: 10px; display: flex; flex-direction: column; }
.msg-right-header { padding: 14px 16px; border-bottom: 1px solid #2a2d3e; }
.msg-right-body { flex: 1; overflow-y: auto; padding: 16px; display: flex; flex-direction: column; gap: 10px; }
.msg-right-footer { padding: 12px 16px; border-top: 1px solid #2a2d3e; display: flex; gap: 8px; }
.msg-right-footer textarea { margin: 0; flex: 1; min-height: 44px; max-height: 120px; }

/* Notification */
.notif { position: fixed; bottom: 24px; right: 24px; background: #2e7d32; color: white; padding: 12px 20px; border-radius: 8px; font-size: 13px; font-weight: 600; z-index: 9999; transform: translateY(80px); opacity: 0; transition: all 0.3s; }
.notif.show { transform: translateY(0); opacity: 1; }
.notif.error { background: #c62828; }

/* Üyelik türleri */
.tur-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); gap: 12px; }
.tur-card { background: #0f1117; border: 1px solid #2a2d3e; border-radius: 8px; padding: 14px; }
.tur-card h4 { font-size: 14px; color: #e0e0e0; margin-bottom: 4px; }
.tur-card .tur-kod { font-size: 11px; color: #5b8cff; font-family: monospace; }
.tur-card .tur-aciklama { font-size: 12px; color: #666; margin: 8px 0; }

/* Filtre butonları */
.filtre-bar { display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 14px; }
.filtre-btn { border: 1px solid #2a2d3e; background: transparent; color: #888; border-radius: 20px; padding: 5px 16px; font-size: 12px; font-weight: 600; cursor: pointer; transition: all 0.15s; display: inline-flex; align-items: center; gap: 6px; }
.filtre-btn:hover { border-color: #5b8cff; color: #e0e0e0; }
.filtre-btn.aktif { background: #5b8cff22; border-color: #5b8cff; color: #5b8cff; }
.filtre-btn.aktif-f { background: #22c55e22; border-color: #22c55e; color: #4ade80; }
.filtre-btn.biten-f { background: #f59e0b22; border-color: #f59e0b; color: #fbbf24; }
.filtre-btn.iptal-f { background: #ef444422; border-color: #ef4444; color: #f87171; }
.cnt-badge { font-size: 11px; font-weight: 700; background: rgba(255,255,255,0.08); border-radius: 10px; padding: 1px 7px; }

/* İstatistik kartı */
.istat-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 10px; margin-bottom: 16px; }
.istat-card { background: #0f1117; border: 1px solid #2a2d3e; border-radius: 8px; padding: 14px 16px; text-align: center; }
.istat-card .i-val { font-size: 26px; font-weight: 700; }
.istat-card .i-lbl { font-size: 11px; color: #555; margin-top: 3px; text-transform: uppercase; letter-spacing: 0.5px; }
.istat-card.i-green .i-val { color: #4ade80; }
.istat-card.i-yellow .i-val { color: #fbbf24; }
.istat-card.i-red .i-val { color: #f87171; }
.istat-card.i-blue .i-val { color: #7eb8ff; }
</style>
</head>
<body>

<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.3/dist/chart.umd.min.js"></script>

<!-- Login -->
<div id="login-overlay">
  <div id="login-box">
    <h2>🔐 Panel Girişi</h2>
    <input type="text" id="inp-kullanici" placeholder="Kullanıcı adı" autocomplete="username">
    <input type="password" id="inp-sifre" placeholder="Şifre" autocomplete="current-password" onkeydown="if(event.key==='Enter')panelGiris()">
    <button onclick="panelGiris()">Giriş Yap</button>
    <div id="login-hata"></div>
  </div>
</div>

<!-- Sidebar -->
<div class="sidebar">
  <div class="sidebar-logo">
    <h1>OPC Gateway</h1>
    <p>Lisans Yönetim Paneli</p>
  </div>
  
  <div class="acc-header open" onclick="toggleAccordion(this)">
    <span class="nav-icon">🔑</span> Lisanslar <span class="acc-chevron">▶</span>
  </div>
  <div class="acc-content show">
    <div class="acc-item active" onclick="sayfaAc('yeni-lisans')" id="nav-yeni-lisans">Yeni Lisans Oluştur</div>
    <div class="acc-item" onclick="sayfaAc('tum-lisanslar')" id="nav-tum-lisanslar">Tüm Lisanslar</div>
    <div class="acc-item" onclick="sayfaAc('lisans-islemleri')" id="nav-lisans-islemleri">Lisans İşlemleri</div>
    <div class="acc-item" onclick="sayfaAc('lisans-istatistikleri')" id="nav-lisans-istatistikleri">Lisans İstatistikleri</div>
    <div class="acc-item yetki-uyelik-tur" onclick="sayfaAc('uyelik-turleri')" id="nav-uyelik-turleri" style="display:none">Lisans Türleri</div>
  </div>

  <div class="nav-item" onclick="sayfaAc('talepler')" id="nav-talepler">
    <span class="nav-icon">📋</span> Talepler
    <span class="badge" id="talep-badge" style="display:none">0</span>
  </div>
  <div class="nav-item" onclick="sayfaAc('mesajlar')" id="nav-mesajlar">
    <span class="nav-icon">💬</span> Mesajlar
    <span class="badge" id="mesaj-badge" style="display:none">0</span>
  </div>
  <div class="nav-item" onclick="sayfaAc('kullanicilar')" id="nav-kullanicilar">
    <span class="nav-icon">👥</span> Kullanıcılar
  </div>
  <div class="nav-item yetki-ip-ban" onclick="sayfaAc('ip-banlar')" id="nav-ip-banlar" style="display:none">
    <span class="nav-icon">🚫</span> IP Ban
  </div>
  <div class="nav-item" onclick="sayfaAc('loglar')" id="nav-loglar">
    <span class="nav-icon">📜</span> Loglar
  </div>
  <div class="nav-item yetki-admin-only" onclick="sayfaAc('yetkililer')" id="nav-yetkililer" style="display:none">
    <span class="nav-icon">🛡️</span> Yetkililer
  </div>
  <div class="nav-item yetki-admin-only" onclick="sayfaAc('panel-loglari')" id="nav-panel-loglari" style="display:none">
    <span class="nav-icon">📑</span> Kayıtlar
  </div>
  
  <div class="nav-item" onclick="panelCikis()" style="margin-top:auto;color:#ef4444;border-top:1px solid #2a2d3e;padding-top:14px;">
    <span class="nav-icon">🚪</span> Çıkış Yap
  </div>
</div>

<!-- Main -->
<div class="main">
  <div id="panel-greeting"></div>

  <!-- Yeni Lisans -->
  <div class="page active" id="page-yeni-lisans">
    <div class="page-title">➕ Yeni Lisans Oluştur</div>
    <div class="card" style="max-width:600px;">
      <div class="sub-tabs">
        <div class="sub-tab active" onclick="switchYeniLisansTab('online')" id="tab-yeni-online">Online Lisans</div>
        <div class="sub-tab" onclick="switchYeniLisansTab('offline')" id="tab-yeni-offline">Offline Lisans</div>
      </div>
      
      <div class="sub-pane active" id="pane-yeni-online">
        <input type="text" id="l-adi" placeholder="Müşteri adı soyadı *">
        <input type="email" id="l-email" placeholder="E-posta (teşekkür maili için)">
        <select id="l-tur">
          <option value="aylik">Aylık (30 gün)</option>
        </select>
        <div style="display:flex;gap:8px;">
          <input type="number" id="l-ozel-gun" placeholder="Özel gün sayısı (Opsiyonel)" min="0" style="flex:1;">
          <input type="number" id="l-saat" placeholder="Deneme (saat)" value="24" min="1" max="8760" style="flex:1;">
        </div>
        <textarea id="l-not" placeholder="Not"></textarea>
        <button class="btn btn-primary yetki-lisans-olustur" onclick="lisansOlustur()">✚ Oluştur</button>
        <div id="l-sonuc" style="margin-top:10px;font-size:13px;color:#4caf50;font-weight:bold;font-family:monospace;"></div>
      </div>
      
      <div class="sub-pane" id="pane-yeni-offline">
        <input type="text" id="off-kime" placeholder="Kime Üretildi (Müşteri Adı) *">
        <input type="text" id="off-istek" placeholder="İstek Kodu (REQ-...) *">
        <input type="number" id="off-sure" placeholder="Süre (Gün) *" value="30">
        <select id="off-yetki">
          <option value="FULL">Tam Yetki (FULL)</option>
          <option value="READ">Sadece Okuma (READ)</option>
          <option value="DEMO">Demo (DEMO)</option>
        </select>
        <button class="btn btn-warning yetki-offline-lisans" onclick="offlineLisansUretBtn()">🔒 Offline Lisans Üret</button>
        <div id="off-sonuc" style="margin-top:10px;font-size:13px;color:#ffb74d;font-weight:bold;font-family:monospace;"></div>
      </div>
    </div>
  </div>

  <!-- Tüm Lisanslar -->
  <div class="page" id="page-tum-lisanslar">
    <div class="page-title">📄 Tüm Lisanslar</div>
    
    <div class="card">
      <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:12px;">
        <h3 style="margin:0;color:#4ade80;">Aktif Online Lisanslar</h3>
        <button class="btn btn-ghost btn-sm" onclick="lisanslariYukle()">↻ Yenile</button>
      </div>
      <div class="filtre-bar">
        <button class="filtre-btn aktif" id="fb-hepsi" onclick="filtreAyarla('hepsi')">Tümü <span class="cnt-badge" id="fb-hepsi-cnt">—</span></button>
        <button class="filtre-btn aktif-f" id="fb-aktif" onclick="filtreAyarla('aktif')">✓ Aktif <span class="cnt-badge" id="fb-aktif-cnt">—</span></button>
        <button class="filtre-btn biten-f" id="fb-biten" onclick="filtreAyarla('biten')">⏱ Süresi Dolmuş <span class="cnt-badge" id="fb-biten-cnt">—</span></button>
        <button class="filtre-btn iptal-f" id="fb-iptal" onclick="filtreAyarla('iptal')">✗ İptal <span class="cnt-badge" id="fb-iptal-cnt">—</span></button>
      </div>
      <div class="tbl-wrap">
        <table>
          <thead><tr><th>Kod</th><th>Müşteri</th><th>Tür</th><th>Durum</th><th>HWID</th><th>Bitiş</th><th>Son Checkin</th><th>Not / İptal</th><th>İşlem</th></tr></thead>
          <tbody id="l-tablo-online"></tbody>
        </table>
      </div>
    </div>

    <div class="card">
      <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:12px;">
        <h3 style="margin:0;color:#fbbf24;">Üretilen Offline Lisanslar</h3>
      </div>
      <div class="tbl-wrap">
        <table>
          <thead><tr><th>Kod</th><th>Müşteri</th><th>Yetki</th><th>Süre</th><th>İstek Kodu</th><th>Durum</th><th>Not / İptal</th><th>İşlem</th></tr></thead>
          <tbody id="l-tablo-offline"></tbody>
        </table>
      </div>
    </div>
  </div>

  <!-- Lisans İşlemleri -->
  <div class="page" id="page-lisans-islemleri">
    <div class="page-title">⚙️ Lisans İşlemleri</div>
    <div class="card" style="max-width:500px;">
      <h3>Lisans İşlemleri</h3>
      <input type="text" id="l-islem-kod" placeholder="Lisans kodu (AYL-XXXX-XXXX-XXXX)">
      <input type="number" id="l-uzat-gun" placeholder="Uzatma (gün)" value="30" min="1">
      <div class="row-btns">
        <button class="btn btn-danger btn-sm yetki-lisans-sil" onclick="iptalEt()">✖ İptal Et</button>
        <button class="btn btn-warning btn-sm yetki-hwid-sifirla" onclick="hwIdSifirla()">↺ HWID Sıfırla</button>
        <button class="btn btn-success btn-sm yetki-sure-uzat" onclick="sureUzat()">+ Süre Uzat</button>
      </div>
      <div id="l-islem-sonuc" style="margin-top:10px;font-size:13px;"></div>
    </div>
  </div>

  <!-- Lisans İstatistikleri -->
  <div class="page" id="page-lisans-istatistikleri">
    <div class="page-title">📊 Lisans İstatistikleri</div>
    <div class="card" id="istat-card">
      <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:12px;">
        <h3 style="margin:0">İstatistikler</h3>
        <button class="btn btn-ghost btn-sm" onclick="istatistikYukle()">↻ Yenile</button>
      </div>
      <div class="istat-grid" id="istat-grid">
        <div class="istat-card i-blue"><div class="i-val" id="is-toplam">—</div><div class="i-lbl">Toplam</div></div>
        <div class="istat-card i-green"><div class="i-val" id="is-aktif">—</div><div class="i-lbl">Aktif</div></div>
        <div class="istat-card i-yellow"><div class="i-val" id="is-biten">—</div><div class="i-lbl">Süresi Dolmuş</div></div>
        <div class="istat-card i-red"><div class="i-val" id="is-iptal">—</div><div class="i-lbl">İptal</div></div>
      </div>
      <div id="neden-bolum" style="display:none;margin-top:16px;">
        <div style="font-size:12px;color:#555;text-transform:uppercase;letter-spacing:0.5px;margin-bottom:12px;">İptal Nedenleri</div>
        <div style="display:grid;grid-template-columns:1fr auto;gap:16px;align-items:start;">
          <div id="neden-bars"></div>
          <div style="width:160px;height:160px;"><canvas id="neden-chart"></canvas></div>
        </div>
      </div>
    </div>
  </div>

  <!-- Talepler -->
  <div class="page" id="page-talepler">
    <div class="page-title">📋 Lisans Talepleri</div>
    <div class="card">
      <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:14px;">
        <h3 style="margin:0">Gelen Talepler</h3>
        <button class="btn btn-ghost btn-sm" onclick="taleplerYukle()">↻ Yenile</button>
      </div>
      <div class="tbl-wrap">
        <table>
          <thead><tr><th>Tarih</th><th>Ad Soyad</th><th>E-posta</th><th>Tür</th><th>IP</th><th>Durum</th><th>İşlem</th></tr></thead>
          <tbody id="talep-tablo"></tbody>
        </table>
      </div>
    </div>
    <!-- Talep işlem modalı -->
    <div id="talep-modal" style="display:none;position:fixed;inset:0;background:rgba(0,0,0,0.7);z-index:500;align-items:center;justify-content:center;">
      <div style="background:#1a1d2e;border:1px solid #2a2d3e;border-radius:12px;padding:28px;width:480px;max-width:95vw;">
        <h3 style="color:#5b8cff;margin-bottom:16px;">Talep İşlemi</h3>
        <div id="talep-bilgi" style="background:#0f1117;border-radius:8px;padding:12px;margin-bottom:14px;font-size:13px;color:#ccc;"></div>
        <textarea id="talep-not" placeholder="Kullanıcıya mesaj (reddedilirse destek mesajı olarak iletilir, onaylanırsa lisans notuna eklenir)" style="margin-bottom:12px;"></textarea>
        <div style="display:flex;gap:10px;">
          <button class="btn btn-success" onclick="talepIsle('onaylandi')">✔ Onayla</button>
          <button class="btn btn-danger" onclick="talepIsle('reddedildi')">✖ Reddet</button>
          <button class="btn btn-ghost" onclick="talepModalKapat()">İptal</button>
        </div>
      </div>
    </div>
  </div>

  <!-- Mesajlar -->
  <div class="page" id="page-mesajlar">
    <div class="page-title">💬 Mesajlar</div>
    <div class="msg-split">
      <div class="msg-left">
        <div style="font-size:12px;color:#555;margin-bottom:10px;text-transform:uppercase;letter-spacing:0.5px;">Konuşmalar</div>
        <div class="conv-list" id="conv-list"></div>
      </div>
      <div class="msg-right" id="msg-right">
        <div style="flex:1;display:flex;align-items:center;justify-content:center;color:#444;font-size:14px;">
          Soldan bir konuşma seçin
        </div>
      </div>
    </div>
  </div>

  <!-- Kullanıcılar -->
  <div class="page" id="page-kullanicilar">
    <div class="page-title">👥 Kullanıcılar</div>
    <div class="card">
      <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:14px;">
        <h3 style="margin:0">Kayıtlı Kullanıcılar</h3>
        <button class="btn btn-ghost btn-sm" onclick="kullanicilariYukle()">↻ Yenile</button>
      </div>
      <div class="tbl-wrap">
        <table>
          <thead><tr><th>Ad Soyad</th><th>E-posta</th><th>Doğrulandı</th><th>Kayıt</th><th>Son Giriş</th><th>Son IP</th><th>Lisans</th><th>İşlem</th></tr></thead>
          <tbody id="kullanici-tablo"></tbody>
        </table>
      </div>
    </div>
  </div>

  <!-- Kullanıcı Düzenle Modal -->
  <div id="kullanici-duzenle-modal" style="display:none;position:fixed;inset:0;background:rgba(0,0,0,0.75);z-index:600;align-items:center;justify-content:center;backdrop-filter:blur(4px);">
    <div style="background:#1a1d2e;border:1px solid #2a2d3e;border-radius:14px;padding:28px;width:520px;max-width:95vw;max-height:90vh;overflow-y:auto;">
      <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:20px;">
        <h3 style="color:#5b8cff;font-size:16px;">✏️ Kullanıcı Düzenle</h3>
        <button class="btn btn-ghost btn-sm" onclick="kullaniciDuzenleModalKapat()">✕</button>
      </div>
      <div id="kd-bilgi" style="background:#0f1117;border-radius:8px;padding:12px;margin-bottom:18px;font-size:13px;color:#aaa;"></div>

      <div style="margin-bottom:14px;">
        <label style="font-size:11px;color:#666;display:block;margin-bottom:5px;text-transform:uppercase;letter-spacing:0.5px;">Yeni Şifre (boş bırakılırsa değişmez)</label>
        <input type="password" id="kd-sifre" placeholder="Yeni şifre (min. 6 karakter)" style="margin:0;">
      </div>

      <div style="border-top:1px solid #2a2d3e;padding-top:16px;margin-bottom:14px;">
        <label style="font-size:11px;color:#666;display:block;margin-bottom:10px;text-transform:uppercase;letter-spacing:0.5px;">📋 Kullanıcı Notları / Admin Notu</label>
        <textarea id="kd-not" placeholder="Bu kullanıcı hakkında not..." style="min-height:60px;margin:0;"></textarea>
      </div>

      <div style="display:flex;gap:12px;margin-top:18px;">
        <button class="btn btn-primary" style="flex:1;" onclick="kullaniciDuzenleKaydet()">💾 Kaydet</button>
        <button class="btn btn-ghost" onclick="kullaniciDuzenleModalKapat()">İptal</button>
      </div>
      <div id="kd-sonuc" style="margin-top:10px;font-size:13px;display:none;"></div>
    </div>
  </div>

  <!-- IP Ban -->
  <div class="page" id="page-ip-banlar">
    <div class="page-title">🚫 IP Ban Yönetimi</div>
    <div style="display:grid;grid-template-columns:340px 1fr;gap:16px;">
      <div class="card">
        <h3>IP Ban Ekle</h3>
        <input type="text" id="ban-ip" placeholder="IP adresi (örn: 1.2.3.4)">
        <textarea id="ban-sebep" placeholder="Ban sebebi (opsiyonel)"></textarea>
        <button class="btn btn-danger" onclick="ipBanEkle()">🚫 Banla</button>
      </div>
      <div class="card">
        <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:14px;">
          <h3 style="margin:0">Banlı IP'ler</h3>
          <button class="btn btn-ghost btn-sm" onclick="ipBanlariYukle()">↻ Yenile</button>
        </div>
        <div class="tbl-wrap">
          <table>
            <thead><tr><th>IP</th><th>Sebep</th><th>Tarih</th><th>Durum</th><th>İşlem</th></tr></thead>
            <tbody id="ban-tablo"></tbody>
          </table>
        </div>
      </div>
    </div>
  </div>

  <!-- Üyelik Türleri -->
  <div class="page" id="page-uyelik-turleri">
    <div class="page-title">⚙️ Üyelik Türleri</div>
    <div style="display:grid;grid-template-columns:320px 1fr;gap:16px;">
      <div class="card">
        <h3>Yeni Tür Ekle</h3>
        <input type="text" id="tur-kod" placeholder="Kod (örn: haftalik) *">
        <input type="text" id="tur-ad" placeholder="Görünen ad (örn: Haftalık Lisans) *">
        <textarea id="tur-aciklama" placeholder="Açıklama (opsiyonel)"></textarea>
        <input type="number" id="tur-sure" placeholder="Süre Gün (Sınırsız için 0) *" value="30">
        <input type="text" id="tur-prefix" placeholder="Lisans Ön Eki (örn: VIP) *" value="STD">
        <input type="number" id="tur-sira" placeholder="Sıra (küçük = önce)" value="99">
        <button class="btn btn-primary" onclick="turEkle()">✚ Ekle</button>
      </div>
      <div class="card">
        <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:16px;">
          <h3 style="margin:0">Mevcut Türler</h3>
          <button class="btn btn-ghost btn-sm" onclick="turleriYukle()">↻ Yenile</button>
        </div>
        <div class="tur-grid" id="tur-grid"></div>
      </div>
    </div>
  </div>

  <!-- Loglar -->
  <div class="page" id="page-loglar">
    <div class="page-title">📜 İşlem Logları</div>
    <div class="card">
      <div style="display:flex;align-items:center;gap:12px;margin-bottom:12px;">
        <button class="btn btn-ghost btn-sm" onclick="logYukle()">↻ Yenile</button>
        <select id="log-adet" style="width:auto;margin:0;" onchange="logYukle()">
          <option value="50">Son 50</option>
          <option value="100" selected>Son 100</option>
          <option value="250">Son 250</option>
        </select>
      </div>
      <div id="log-output">Loglar yükleniyor...</div>
    </div>
  </div>

  <!-- Yetkililer -->
  <div class="page" id="page-yetkililer">
    <div class="page-title">🛡️ Panel Yetkilileri</div>
    
    <div class="card yetki-admin-only" style="margin-bottom:24px;border-color:#5b8cff44;background:#131828;">
      <h3 style="color:#5b8cff">🛠️ Ana Admin Bilgilerini Güncelle</h3>
      <p style="font-size:12px;color:#aaa;margin-bottom:12px;">Sistemin ana yöneticisi (Kurucu) için giriş bilgilerini değiştirin.</p>
      <div style="display:flex;gap:12px;max-width:500px;">
        <input type="text" id="a-yeni-kadi" placeholder="Yeni Kullanıcı Adı">
        <input type="password" id="a-yeni-sifre" placeholder="Yeni Şifre">
        <button class="btn btn-warning" onclick="adminGuncelle()" style="white-space:nowrap;">Değiştir</button>
      </div>
    </div>
    
    <div style="display:grid;grid-template-columns:320px 1fr;gap:16px;">
      <div class="card">
        <h3>Yeni Yetkili Ekle</h3>
        <input type="text" id="y-kadi" placeholder="Kullanıcı Adı *">
        <input type="text" id="y-isim" placeholder="İsim Soyisim *">
        <input type="email" id="y-email" placeholder="E-posta *">
        <input type="password" id="y-sifre" placeholder="Şifre *">
        <div style="margin:14px 0;font-size:12px;color:#ccc;display:flex;flex-direction:column;gap:6px;">
          <label><input type="checkbox" id="cb-lisans_olustur"> Lisans Oluşturabilme</label>
          <label><input type="checkbox" id="cb-lisans_sil"> Lisans Silebilme / İptal</label>
          <label><input type="checkbox" id="cb-hwid_sifirla"> HWID Sıfırlama</label>
          <label><input type="checkbox" id="cb-sure_uzat"> Lisans Süre Uzatma</label>
          <label><input type="checkbox" id="cb-talep_onayla"> Lisans Taleplerini Onaylama</label>
          <label><input type="checkbox" id="cb-kullanici_ekle"> Panel Kullanıcısı (Yetkili) Ekleme</label>
          <label><input type="checkbox" id="cb-mesaj_yaz"> Mesaj Yazabilme</label>
          <label><input type="checkbox" id="cb-ip_ban"> IP Banlama & Kaldırma</label>
          <label><input type="checkbox" id="cb-uyelik_tur"> Üyelik Türleri Yönetimi</label>
          <label><input type="checkbox" id="cb-offline_lisans"> 🔒 Çevrimdışı Lisans Üretme</label>
        </div>
        <button class="btn btn-primary" onclick="yetkiliEkle()">✚ Ekle</button>
      </div>
      <div class="card">
        <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:16px;">
          <h3 style="margin:0">Mevcut Yetkililer</h3>
          <button class="btn btn-ghost btn-sm" onclick="yetkilileriYukle()">↻ Yenile</button>
        </div>
        <div class="tbl-wrap">
          <table>
            <thead><tr><th>Kullanıcı Adı</th><th>İsim Soyisim</th><th>Rol</th><th>Yetkiler</th><th>Son Giriş</th><th>Son Çıkış</th><th>İşlem</th></tr></thead>
            <tbody id="yetkili-tablo"></tbody>
          </table>
        </div>
      </div>
    </div>
  </div>

  <!-- Kayıtlar (Panel Logları) -->
  <div class="page" id="page-panel-loglari">
    <div class="page-title">📑 Panel Kayıtları</div>
    <div class="card">
      <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:14px;">
        <h3 style="margin:0">Yetkili İşlem Geçmişi</h3>
        <button class="btn btn-ghost btn-sm" onclick="panelLoglariYukle()">↻ Yenile</button>
      </div>
      <div class="tbl-wrap">
        <table>
          <thead><tr><th>Tarih</th><th>Yetkili</th><th>İşlem</th><th>Detay</th></tr></thead>
          <tbody id="panel-log-tablo"></tbody>
        </table>
      </div>
    </div>
  </div>

  <!-- Offline Lisans Üretici -->
  <div class="page" id="page-offline-lisans">
    <div class="page-title">🔒 Çevrimdışı Lisans Üretici</div>
    <div style="display:grid;grid-template-columns:380px 1fr;gap:16px;">
      <!-- Form -->
      <div class="card">
        <h3 style="margin-bottom:14px;">Aktivasyon Kodu Üret</h3>
        <label style="font-size:11px;color:#666;display:block;margin-bottom:4px;">İstek Kodu (Müşteriden alınan REQ-...):</label>
        <input type="text" id="ol-istek-kodu" placeholder="REQ-XXXXXXXXXXXXXXXXXXXX" style="font-family:Consolas;letter-spacing:1px;">
        <label style="font-size:11px;color:#666;display:block;margin:10px 0 4px;">Süre (Gün):</label>
        <input type="number" id="ol-sure" value="30" min="1" max="365">
        <label style="font-size:11px;color:#666;display:block;margin:10px 0 4px;">Yetki Seviyesi:</label>
        <select id="ol-yetki">
          <option value="FULL">FULL — Tam Erişim</option>
          <option value="READ">READ — Sadece Okuma</option>
          <option value="DEMO">DEMO — Demo Modu</option>
        </select>
        <button class="btn btn-primary" style="margin-top:14px;width:100%;" onclick="offlineLisansUret()">⚡ Aktivasyon Kodu Üret</button>
        <div id="ol-hata" style="color:#f87171;font-size:12px;margin-top:8px;display:none;"></div>
      </div>
      <!-- Sonuç -->
      <div class="card" id="ol-sonuc-kart" style="display:none;">
        <h3 style="color:#4caf50;margin-bottom:12px;">✅ Aktivasyon Kodu Üretildi</h3>
        <div style="background:#1b5e2022;border:1px solid #4caf5044;border-radius:8px;padding:18px;margin-bottom:14px;">
          <div style="font-size:10px;color:#666;margin-bottom:6px;">Aktivasyon Kodu (Müşteriye Gönder):</div>
          <div id="ol-akt-kod" style="font-family:Consolas;font-size:15px;font-weight:bold;color:#00e676;letter-spacing:1px;word-break:break-all;"></div>
        </div>
        <div style="display:flex;gap:8px;margin-bottom:14px;">
          <button class="btn btn-success" onclick="olKopyala()" id="ol-kopyala-btn">📋 Kopyala</button>
          <span id="ol-kopyala-ok" style="font-size:12px;color:#4caf50;align-self:center;display:none;">✓ Kopyalandı!</span>
        </div>
        <div style="font-size:12px;color:#888;line-height:1.8;">
          <div>İstek Kodu: <code id="ol-det-istek" style="color:#7eb8ff;"></code></div>
          <div>Süre: <b id="ol-det-sure" style="color:#e0e0e0;"></b> Gün &nbsp;|  Yetki: <b id="ol-det-yetki" style="color:#e0e0e0;"></b></div>
        </div>
      </div>
    </div>
  </div>

</div><!-- /main -->

<!-- Yetkili Düzenle Modal -->
<div id="yetkili-duzenle-modal" style="display:none;position:fixed;inset:0;background:rgba(0,0,0,0.75);z-index:600;align-items:center;justify-content:center;backdrop-filter:blur(4px);">
  <div style="background:#1a1d2e;border:1px solid #2a2d3e;border-radius:14px;padding:28px;width:540px;max-width:95vw;max-height:92vh;overflow-y:auto;">
    <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:20px;">
      <h3 style="color:#5b8cff;font-size:16px;">✏️ Yetkili Düzenle</h3>
      <button class="btn btn-ghost btn-sm" onclick="yetkiliDuzenleModalKapat()">✕</button>
    </div>
    <div id="yd-bilgi" style="background:#0f1117;border-radius:8px;padding:10px 14px;margin-bottom:16px;font-size:13px;color:#aaa;"></div>

    <div style="margin-bottom:14px;">
      <label style="font-size:11px;color:#666;display:block;margin-bottom:5px;text-transform:uppercase;letter-spacing:0.5px;">Yeni Şifre (boş bırakılırsa değişmez)</label>
      <input type="password" id="yd-sifre" placeholder="Yeni şifre..." style="margin:0;">
    </div>

    <div style="margin-bottom:16px;">
      <label style="font-size:11px;color:#666;display:block;margin-bottom:5px;text-transform:uppercase;letter-spacing:0.5px;">📱 Telegram Chat ID</label>
      <input type="text" id="yd-telegram-id" placeholder="Örn: 123456789" style="margin:0;">
      <label style="display:flex;align-items:center;gap:8px;margin-top:8px;font-size:13px;color:#aaa;cursor:pointer;">
        <input type="checkbox" id="yd-telegram-bildirim"> Telegram bildirimleri alsın
      </label>
    </div>

    <div style="border-top:1px solid #2a2d3e;padding-top:16px;margin-bottom:16px;">
      <div style="font-size:11px;color:#666;margin-bottom:10px;text-transform:uppercase;letter-spacing:0.5px;">🛡️ Yetkiler</div>
      <div style="display:flex;flex-direction:column;gap:7px;font-size:13px;color:#ccc;">
        <label style="display:flex;align-items:center;gap:8px;cursor:pointer;"><input type="checkbox" id="yd-cb-lisans_olustur"> Lisans Oluşturabilme</label>
        <label style="display:flex;align-items:center;gap:8px;cursor:pointer;"><input type="checkbox" id="yd-cb-lisans_sil"> Lisans Silebilme / İptal</label>
        <label style="display:flex;align-items:center;gap:8px;cursor:pointer;"><input type="checkbox" id="yd-cb-hwid_sifirla"> HWID Sıfırlama</label>
        <label style="display:flex;align-items:center;gap:8px;cursor:pointer;"><input type="checkbox" id="yd-cb-sure_uzat"> Lisans Süre Uzatma</label>
        <label style="display:flex;align-items:center;gap:8px;cursor:pointer;"><input type="checkbox" id="yd-cb-talep_onayla"> Lisans Taleplerini Onaylama</label>
        <label style="display:flex;align-items:center;gap:8px;cursor:pointer;"><input type="checkbox" id="yd-cb-kullanici_ekle"> Panel Kullanıcısı (Yetkili) Ekleme</label>
        <label style="display:flex;align-items:center;gap:8px;cursor:pointer;"><input type="checkbox" id="yd-cb-mesaj_yaz"> Mesaj Yazabilme</label>
        <label style="display:flex;align-items:center;gap:8px;cursor:pointer;"><input type="checkbox" id="yd-cb-ip_ban"> IP Banlama &amp; Kaldırma</label>
        <label style="display:flex;align-items:center;gap:8px;cursor:pointer;"><input type="checkbox" id="yd-cb-uyelik_tur"> Üyelik Türleri Yönetimi</label>
        <label style="display:flex;align-items:center;gap:8px;cursor:pointer;"><input type="checkbox" id="yd-cb-offline_lisans"> 🔒 Çevrimdışı Lisans Üretme</label>
      </div>
    </div>

    <div style="display:flex;gap:12px;margin-top:18px;">
      <button class="btn btn-primary" style="flex:1;" onclick="yetkiliDuzenleKaydet()">💾 Değişiklikleri Kaydet</button>
      <button class="btn btn-ghost" onclick="yetkiliDuzenleModalKapat()">İptal</button>
    </div>
    <div id="yd-sonuc" style="margin-top:10px;font-size:13px;display:none;"></div>
  </div>
</div>
<div class="notif" id="notif"></div>

<script>
let TOKEN = "";
let secilenTalepId = null;
let secilenKullaniciId = null;

function auth() {
  return {"Authorization": "Bearer " + TOKEN, "Content-Type": "application/json"};
}

function notif(msg, hata = false) {
  const el = document.getElementById("notif");
  el.textContent = msg;
  el.className = "notif" + (hata ? " error" : "") + " show";
  setTimeout(() => el.className = "notif" + (hata ? " error" : ""), 2800);
}

let _panelPollTimer = null;
let _aktifSayfa = "lisanslar";

function arayuzuYetkilendir() {
  if (window.IS_ADMIN) {
    document.querySelectorAll(".yetki-admin-only").forEach(el => el.style.display = "");
  }
  // Buton yetkileri
  const y = window.YETKILER || {};
  const goster = (cls, yetki) => {
    document.querySelectorAll("." + cls).forEach(el => {
      if (window.IS_ADMIN || y[yetki]) el.style.display = "";
      else el.style.display = "none";
    });
  };
  goster("yetki-lisans-olustur", "lisans_olustur");
  goster("yetki-lisans-sil", "lisans_sil");
  goster("yetki-hwid-sifirla", "hwid_sifirla");
  goster("yetki-sure-uzat", "sure_uzat");
  goster("yetki-ip-ban", "ip_ban");
  goster("yetki-uyelik-tur", "uyelik_tur");
  goster("yetki-offline-lisans", "offline_lisans");
  // Talep onayla butonu ve JS içi render kısımlarını ayrıca idare edeceğiz.
}

function updateGreeting() {
  const hr = new Date().getHours();
  let msj = "İyi geceler";
  if (hr >= 6 && hr < 12) msj = "Günaydın";
  else if (hr >= 12 && hr < 18) msj = "İyi günler";
  else if (hr >= 18 && hr < 24) msj = "İyi akşamlar";
  
  const el = document.getElementById("panel-greeting");
  if (!el) return;
  if (window.IS_ADMIN) {
    el.innerHTML = `<span style="color:#5b8cff">🛡️ Ana Admin Paneli</span>`;
  } else {
    el.innerHTML = `${msj}, <span style="color:#e0e0e0">${window.ISIM_SOYAD || window.KULLANICI_ADI}</span>`;
  }
}

function panelGiris() {
  const k = document.getElementById("inp-kullanici").value;
  const s = document.getElementById("inp-sifre").value;
  fetch("/panel/giris", {
    method:"POST", 
    headers:{"Content-Type":"application/json"},
    body: JSON.stringify({kullanici: k, sifre: s})
  })
    .then(r => r.json())
    .then(d => {
      if (d.basarili) {
        TOKEN = k + ":" + s;
        window.IS_ADMIN = d.is_admin;
        window.YETKILER = d.yetkiler;
        window.ISIM_SOYAD = d.isim_soyad;
        window.KULLANICI_ADI = d.kullanici_adi;
        arayuzuYetkilendir();
        updateGreeting();
        
        document.getElementById("login-overlay").style.display = "none";
        turleriYukle();
        lisanslariYukle();
        badgeGuncelle();
        // Aktif sayfayı 15 saniyede bir otomatik yenile
        _panelPollTimer = setInterval(() => {
          panelOtoPoll();
          badgeGuncelle();
        }, 15000);
        istatistikYukle();
      } else {
        document.getElementById("login-hata").textContent = d.detail || "Giriş başarısız.";
      }
    }).catch(e => {
       document.getElementById("login-hata").textContent = "Giriş yapılamadı.";
    });
}

function panelCikis() {
  fetch("/panel/cikis", {method:"POST", headers:auth()}).then(()=>{
    location.reload();
  });
}

function panelOtoPoll() {
  const yukle = {
    lisanslar:       lisanslariYukle,
    "tum-lisanslar": lisanslariYukle,
    "yeni-lisans":   turleriYukle,
    "lisans-islemleri": () => {},
    "lisans-istatistikleri": istatistikYukle,
    "uyelik-turleri": turleriYukle,
    talepler:        taleplerYukle,
    mesajlar:        mesajlariYukle,
    kullanicilar:    kullanicilariYukle,
    "ip-banlar":     ipBanlariYukle,
    loglar:          logYukle,
    yetkililer:      yetkilileriYukle,
    "panel-loglari": panelLoglariYukle,
    "offline-lisans": () => {
       const el1 = document.getElementById("ol-istek-kodu");
       const el2 = document.getElementById("ol-sonuc-kart");
       const el3 = document.getElementById("ol-hata");
       if (el1) el1.value = "";
       if (el2) el2.style.display = "none";
       if (el3) el3.style.display = "none";
    },
  };
  if (yukle[_aktifSayfa]) yukle[_aktifSayfa]();
}

function sayfaAc(sayfa) {
  document.querySelectorAll(".page").forEach(p => p.classList.remove("active"));
  document.querySelectorAll(".nav-item, .acc-item").forEach(n => n.classList.remove("active"));
  const pageEl = document.getElementById("page-" + sayfa);
  if (pageEl) pageEl.classList.add("active");
  const navEl = document.getElementById("nav-" + sayfa);
  if (navEl) navEl.classList.add("active");
  _aktifSayfa = sayfa;

  const yukle = {
    lisanslar:           lisanslariYukle,
    "tum-lisanslar":     lisanslariYukle,
    "yeni-lisans":       turleriYukle,
    "lisans-islemleri":  () => {},
    "lisans-istatistikleri": istatistikYukle,
    "uyelik-turleri":    turleriYukle,
    talepler:            taleplerYukle,
    mesajlar:            mesajlariYukle,
    kullanicilar:        kullanicilariYukle,
    "ip-banlar":         ipBanlariYukle,
    loglar:              logYukle,
    yetkililer:          yetkilileriYukle,
    "panel-loglari":     panelLoglariYukle,
  };
  if (yukle[sayfa]) yukle[sayfa]();
}

async function badgeGuncelle() {
  // Talepler
  const tr = await fetch("/panel/talepler", {headers: auth()}).then(r => r.json()).catch(() => []);
  const bekleyen = tr.filter ? tr.filter(t => t.durum === "beklemede").length : 0;
  const tb = document.getElementById("talep-badge");
  tb.textContent = bekleyen;
  tb.style.display = bekleyen > 0 ? "" : "none";

  // Mesajlar
  const mr = await fetch("/panel/mesajlar-ozet", {headers: auth()}).then(r => r.json()).catch(() => []);
  const okunmamis = mr.reduce ? mr.reduce((s, m) => s + m.okunmamis, 0) : 0;
  const mb = document.getElementById("mesaj-badge");
  mb.textContent = okunmamis;
  mb.style.display = okunmamis > 0 ? "" : "none";
}

// ===== LİSANSLAR =====
function lisansOlustur() {
  const ozel_val = document.getElementById("l-ozel-gun").value;
  const b = {
    musteri_adi: document.getElementById("l-adi").value,
    musteri_email: document.getElementById("l-email").value,
    tur: document.getElementById("l-tur").value,
    deneme_saat: parseInt(document.getElementById("l-saat").value) || 24,
    ozel_gun: ozel_val !== "" ? parseInt(ozel_val) : null,
    notlar: document.getElementById("l-not").value,
  };
  if (!b.musteri_adi) { notif("Müşteri adı zorunlu!", true); return; }
  fetch("/panel/lisans-olustur", {method:"POST", headers:auth(), body:JSON.stringify(b)})
    .then(r => r.json())
    .then(d => {
      if (d.lisans_kodu) {
        document.getElementById("l-sonuc").textContent = "✅ " + d.lisans_kodu + " | " + d.bitis_tarihi;
        notif("Lisans oluşturuldu: " + d.lisans_kodu);
        lisanslariYukle();
      } else {
        notif(d.detail || "Hata", true);
      }
    });
}

function iptalEt() {
  const k = document.getElementById("l-islem-kod").value;
  if (!k) { notif("Lisans kodu girin!", true); return; }
  if (!confirm(k + " iptal edilsin mi?")) return;
  fetch("/panel/iptal?lisans_kodu=" + encodeURIComponent(k), {method:"POST", headers:auth()})
    .then(r => r.json()).then(d => { notif(d.mesaj || d.detail, !!d.detail); lisanslariYukle(); });
}

function hwIdSifirla() {
  const k = document.getElementById("l-islem-kod").value;
  if (!k) { notif("Lisans kodu girin!", true); return; }
  fetch("/panel/hwid-sifirla?lisans_kodu=" + encodeURIComponent(k), {method:"POST", headers:auth()})
    .then(r => r.json()).then(d => { notif(d.mesaj || d.detail, !!d.detail); lisanslariYukle(); });
}

function sureUzat() {
  const k = document.getElementById("l-islem-kod").value;
  const g = document.getElementById("l-uzat-gun").value;
  if (!k) { notif("Lisans kodu girin!", true); return; }
  fetch("/panel/sure-uzat?lisans_kodu=" + encodeURIComponent(k) + "&gun=" + g, {method:"POST", headers:auth()})
    .then(r => r.json()).then(d => { notif(d.mesaj || d.detail, !!d.detail); lisanslariYukle(); });
}

function lisansSil(lisansKodu) {
  if (!confirm(lisansKodu + " lisansı kalıcı olarak silinecek. Bu işlem geri alınamaz. Emin misiniz?")) return;
  fetch("/panel/lisans-sil/" + encodeURIComponent(lisansKodu), {method: "DELETE", headers: auth()})
    .then(r => r.json())
    .then(d => { notif(d.mesaj || d.detail, !!d.detail); lisanslariYukle(); istatistikYukle(); });
}

let _aktifFiltre = "hepsi";
let _nedenChart = null;

function filtreAyarla(f) {
  _aktifFiltre = f;
  // Buton aktif/pasif güncelle
  ["hepsi","aktif","biten","iptal"].forEach(x => {
    const el = document.getElementById("fb-" + x);
    if (!el) return;
    const baseClass = x === "hepsi" ? "aktif" : x + "-f";
    if (x === f) el.className = "filtre-btn " + baseClass;
    else el.className = "filtre-btn";
  });
  lisanslariYukle();
}

function istatistikYukle() {
  fetch("/panel/iptal-istatistikleri", {headers: auth()}).then(r => r.json()).then(d => {
    const o = d.ozet;
    document.getElementById("is-toplam").textContent = o.toplam;
    document.getElementById("is-aktif").textContent  = o.aktif;
    document.getElementById("is-biten").textContent  = o.biten;
    document.getElementById("is-iptal").textContent  = o.iptal;
    // Filtre sayı badge'ları
    document.getElementById("fb-hepsi-cnt").textContent = o.toplam;
    document.getElementById("fb-aktif-cnt").textContent = o.aktif;
    document.getElementById("fb-biten-cnt").textContent = o.biten;
    document.getElementById("fb-iptal-cnt").textContent = o.iptal;
    // İptal nedenleri
    const nedenler = d.nedenler || [];
    const bolum = document.getElementById("neden-bolum");
    if (!nedenler.length) { bolum.style.display = "none"; return; }
    bolum.style.display = "";
    const toplam_iptal = nedenler.reduce((s, n) => s + n.sayi, 0);
    document.getElementById("neden-bars").innerHTML = nedenler.map(n => {
      const yuzde = Math.round((n.sayi / toplam_iptal) * 100);
      return `<div style="margin-bottom:10px;">
        <div style="display:flex;justify-content:space-between;font-size:12px;margin-bottom:4px;">
          <span style="color:#ccc;">${n.neden}</span>
          <span style="color:#888;">${n.sayi} (${yuzde}%)</span>
        </div>
        <div style="background:#1e2033;border-radius:4px;height:6px;">
          <div style="background:#ef4444;width:${yuzde}%;height:6px;border-radius:4px;transition:width 0.4s;"></div>
        </div>
      </div>`;
    }).join("");
    // Donut grafik
    const canvas = document.getElementById("neden-chart");
    if (_nedenChart) { _nedenChart.destroy(); _nedenChart = null; }
    _nedenChart = new Chart(canvas, {
      type: "doughnut",
      data: {
        labels: nedenler.map(n => n.neden),
        datasets: [{ data: nedenler.map(n => n.sayi),
          backgroundColor: ["#ef4444","#f59e0b","#3b82f6","#8b5cf6","#10b981","#ec4899","#06b6d4"],
          borderColor: "#0f1117", borderWidth: 2 }]
      },
      options: { responsive: true, maintainAspectRatio: false, plugins: {
        legend: { display: false },
        tooltip: { callbacks: { label: (c) => ` ${c.label}: ${c.raw}` } }
      }}
    });
  }).catch(() => {});
}

function lisanslariYukle() {
  fetch("/panel/lisanslar?filtre=" + _aktifFiltre, {headers: auth()}).then(r => r.json()).then(liste => {
    const turBadge = {aylik:"b-aylik",yillik:"b-yillik",omur_boyu:"b-omur",deneme:"b-deneme"};
    const durumBadge = {
      aktif:         '<span class="badge b-aktif">✓ Aktif</span>',
      suresi_dolmus: '<span class="badge" style="background:#f59e0b22;color:#fbbf24;border:1px solid #f59e0b55;">⏱ Süresi Doldu</span>',
      iptal:         '<span class="badge b-pasif">✗ İptal</span>',
    };

    // Online ve Offline lisansları ayır
    const online = liste.filter(l => {
      const tip = (l.uretilen_tip || "").toLowerCase();
      const notlar = (l.notlar || "").toLowerCase();
      return tip !== "offline" && !notlar.startsWith("offline");
    });
    const offline = liste.filter(l => {
      const tip = (l.uretilen_tip || "").toLowerCase();
      const notlar = (l.notlar || "").toLowerCase();
      return tip === "offline" || notlar.startsWith("offline");
    });

    // Online tablo
    const onlineTablo = document.getElementById("l-tablo-online");
    if (onlineTablo) {
      onlineTablo.innerHTML = online.map(l => `
        <tr>
          <td><code>${l.lisans_kodu}</code></td>
          <td>${l.musteri_adi}<br><span style="color:#555;font-size:11px;">${l.musteri_email||""}</span></td>
          <td><span class="badge ${turBadge[l.tur]||""}"> ${l.tur}</span></td>
          <td>${durumBadge[l.durum] || l.durum}</td>
          <td style="font-family:monospace;font-size:11px;color:#555;">${(l.hwid||"—").substring(0,18)}</td>
          <td>${l.bitis_tarihi}</td>
          <td>${l.son_checkin}</td>
          <td style="color:#666;font-size:11px;">${l.notlar||""}${l.iptal_nedeni ? `<br><span style="color:#f87171;">İptal: ${l.iptal_nedeni}</span>` : ""}</td>
          <td><button class="btn btn-danger btn-sm" onclick="lisansSil('${l.lisans_kodu}')">🗑 Sil</button></td>
        </tr>`).join("") || '<tr><td colspan="9" style="color:#555;text-align:center;padding:20px;">Kayıt yok</td></tr>';
    }

    // Offline tablo
    const offlineTablo = document.getElementById("l-tablo-offline");
    if (offlineTablo) {
      offlineTablo.innerHTML = offline.map(l => {
        // istek kodunu notlar'dan veya istek_kodu alanından çek
        let istekKodu = l.istek_kodu || "";
        if (!istekKodu && (l.notlar||"").includes("|")) istekKodu = l.notlar.split("|")[1] || "";
        const yetki = l.yetki || "FULL";
        const sureGun = l.sure_gun || "—";
        return `<tr>
          <td><code style="color:#a78bfa;">${l.lisans_kodu}</code></td>
          <td>${l.musteri_adi}<br><span style="color:#555;font-size:11px;">${l.musteri_email||""}</span></td>
          <td><span class="badge" style="background:#a78bfa22;color:#a78bfa;border:1px solid #a78bfa44;">${yetki}</span></td>
          <td>${sureGun !== "—" ? sureGun + " Gün" : "—"}</td>
          <td>${istekKodu ? `<code style="color:#7eb8ff;font-size:11px;">${istekKodu}</code>` : '<span style="color:#555;">—</span>'}</td>
          <td>${durumBadge[l.durum] || l.durum}</td>
          <td style="color:#666;font-size:11px;">${l.iptal_nedeni ? `<span style="color:#f87171;">İptal: ${l.iptal_nedeni}</span>` : "—"}</td>
          <td><button class="btn btn-danger btn-sm" onclick="lisansSil('${l.lisans_kodu}')">🗑 Sil</button></td>
        </tr>`;
      }).join("") || '<tr><td colspan="8" style="color:#555;text-align:center;padding:20px;">Henüz offline lisans üretilmemiş</td></tr>';
    }

    // Geriye dönük uyumluluk - eski l-tablo varsa onu da doldur
    const eskiTablo = document.getElementById("l-tablo");
    if (eskiTablo) {
      eskiTablo.innerHTML = liste.map(l => `
        <tr>
          <td><code>${l.lisans_kodu}</code></td>
          <td>${l.musteri_adi}<br><span style="color:#555;font-size:11px;">${l.musteri_email||""}</span></td>
          <td><span class="badge ${turBadge[l.tur]||""}"> ${l.tur}</span></td>
          <td>${durumBadge[l.durum] || l.durum}</td>
          <td style="font-family:monospace;font-size:11px;color:#555;">${(l.hwid||"").substring(0,18)}</td>
          <td>${l.bitis_tarihi}</td>
          <td>${l.son_checkin}</td>
          <td>${l.aktivasyon}</td>
          <td style="color:#666;font-size:11px;">${l.notlar||""}${l.iptal_nedeni ? `<br><span style="color:#f87171;">İptal: ${l.iptal_nedeni}</span>` : ""}</td>
          <td><button class="btn btn-danger btn-sm" onclick="lisansSil('${l.lisans_kodu}')">🗑 Sil</button></td>
        </tr>`).join("");
    }
  });
}

// ===== TALEPLER =====
function taleplerYukle() {
  fetch("/panel/talepler", {headers: auth()}).then(r => r.json()).then(liste => {
    const durumBadge = {beklemede:"b-beklemede",onaylandi:"b-onaylandi",reddedildi:"b-reddedildi"};
    document.getElementById("talep-tablo").innerHTML = liste.map(t => `
      <tr>
        <td>${t.tarih}</td>
        <td>${t.ad_soyad}</td>
        <td>${t.email}</td>
        <td>${t.tur} ${t.talep_tipi === "offline" ? `<br><span style="font-size:10px;padding:2px 6px;border-radius:4px;background:#3d6fff22;color:#3d6fff;border:1px solid #3d6fff44;">OFFLINE</span>` : ""}</td>
        <td><code>${t.ip||"-"}</code></td>
        <td><span class="badge ${durumBadge[t.durum]||""}">${t.durum}</span></td>
        <td>${t.durum==="beklemede" ? `<button class="btn btn-primary btn-sm" onclick="talepModalAc('${t.id}','${t.ad_soyad}','${t.email}','${t.tur}','${t.ip||''}','${t.talep_tipi||'online'}','${t.istek_kodu||''}')">İşlem</button>` : (t.admin_notu ? `<span style="color:#666;font-size:11px;">${t.admin_notu.substring(0,40)}</span>` : "—")}</td>
      </tr>`).join("");
    badgeGuncelle();
  });
}

function talepModalAc(id, ad, email, tur, ip, tip, istekKodu) {
  secilenTalepId = id;
  let ekOfflineBilgi = tip === "offline" ? `<div style="background:#3d6fff11;border:1px solid #3d6fff33;padding:8px;border-radius:6px;margin-top:8px;font-size:13px;"><b style="color:#3d6fff;">OFFLINE TALEP</b><br>İstek Kodu: <code style="color:#fff;">${istekKodu}</code><br><span style="color:#888;font-size:11px;">Onaylandığında otomatik aktivasyon kodu üretilecektir.</span></div>` : "";
  document.getElementById("talep-bilgi").innerHTML = `<b>${ad}</b> &lt;${email}&gt;<br>Tür: <b>${tur}</b> | IP: <code>${ip}</code>${ekOfflineBilgi}`;
  document.getElementById("talep-not").value = "";
  const m = document.getElementById("talep-modal");
  m.style.display = "flex";
}

function talepModalKapat() {
  document.getElementById("talep-modal").style.display = "none";
  secilenTalepId = null;
}

function talepIsle(durum) {
  if (!secilenTalepId) return;
  fetch("/panel/talep-guncelle", {method:"POST", headers:auth(), body:JSON.stringify({
    talep_id: secilenTalepId,
    durum: durum,
    admin_notu: document.getElementById("talep-not").value,
  })}).then(r => r.json()).then(d => {
    notif(durum === "onaylandi" ? "Talep onaylandı" : "Talep reddedildi");
    talepModalKapat();
    taleplerYukle();
  });
}

// ===== MESAJLAR =====
function mesajlariYukle() {
  fetch("/panel/mesajlar-ozet", {headers: auth()}).then(r => r.json()).then(liste => {
    const convList = document.getElementById("conv-list");
    convList.innerHTML = liste.map(m => `
      <div class="conv-item ${m.kullanici_id === secilenKullaniciId ? 'active' : ''}"
           onclick="konusmaSec('${m.kullanici_id}')">
        <div class="conv-avatar">${m.ad_soyad[0]}</div>
        <div class="conv-info">
          <div class="conv-name">${m.ad_soyad}</div>
          <div class="conv-preview">${m.son_mesaj || "…"}</div>
        </div>
        <div class="conv-meta">
          <span style="font-size:10px;color:#555;">${m.son_mesaj_tar}</span>
          ${m.okunmamis > 0 ? `<span class="unread-dot">${m.okunmamis}</span>` : ""}
        </div>
      </div>`).join("");
    badgeGuncelle();
  });
}

let _konusmaPollTimer = null;

function konusmaSec(kullaniciId) {
  secilenKullaniciId = kullaniciId;
  mesajlariYukle();
  // Önceki konuşma poll'unu temizle
  if (_konusmaPollTimer) { clearInterval(_konusmaPollTimer); _konusmaPollTimer = null; }
  _konusmaMesajYukle(kullaniciId);
  // Açık konuşmayı 5 saniyede bir canlı güncelle
  _konusmaPollTimer = setInterval(() => {
    if (secilenKullaniciId === kullaniciId) _konusmaMesajYukle(kullaniciId);
    else { clearInterval(_konusmaPollTimer); _konusmaPollTimer = null; }
  }, 5000);
}

function _konusmaMesajYukle(kullaniciId) {
  fetch("/panel/kullanici-mesajlar/" + kullaniciId, {headers: auth()}).then(r => r.json()).then(d => {
    const right = document.getElementById("msg-right");
    // Eğer kullanıcı mesaj kutusuna yazıyorsa sadece mesaj listesini güncelle
    const inputMevcut = document.getElementById("admin-msg-inp");
    const inputDeger = inputMevcut ? inputMevcut.value : null;

    const k = d.kullanici;
    const l = d.lisans;
    const lisansBilgi = l ?
      `<span class="badge b-aktif" style="margin-right:4px;">${l.tur}</span> ${l.kod} — ${l.bitis||"Ömür Boyu"}${l.kalan_gun != null ? ` (${l.kalan_gun} gün)` : ""}` :
      `<span class="badge b-pasif">Lisans Yok</span>`;

    const mesajlerHtml = d.mesajlar.map(m => `
      <div class="msg-sender ${m.gonderen==='admin'?'right':''}">
        <div class="msg-bubble ${m.gonderen}">${m.icerik}</div>
        <div class="msg-time">${m.gonderen==='admin'?'Siz':'Kullanıcı'} · ${m.tarih}</div>
      </div>`).join("");

    if (inputMevcut) {
      // Sadece mesaj listesini güncelle, input ve header dokunma
      const mesajEl = document.getElementById("aktif-mesajlar");
      if (mesajEl) {
        const eskiScroll = mesajEl.scrollHeight - mesajEl.scrollTop;
        mesajEl.innerHTML = mesajlerHtml;
        // Kullanıcı en alttaysa otomatik kaydır
        if (eskiScroll <= mesajEl.clientHeight + 40) mesajEl.scrollTop = mesajEl.scrollHeight;
      }
      // Input değerini koru
      const inp = document.getElementById("admin-msg-inp");
      if (inp && inputDeger !== null) inp.value = inputDeger;
    } else {
      right.innerHTML = `
        <div class="msg-right-header">
          <div style="font-size:15px;font-weight:700;color:#e0e0e0;margin-bottom:8px;">${k.ad_soyad}</div>
          <div class="user-detail">
            <div class="row">
              <div class="field"><label>E-posta</label><span>${k.email}</span></div>
              <div class="field"><label>Son IP</label><span><code>${k.son_ip||"?"}</code></span></div>
              <div class="field"><label>Kayıt Tarihi</label><span>${k.kayit_tar}</span></div>
              <div class="field"><label>Lisans</label><span>${lisansBilgi}</span></div>
            </div>
          </div>
        </div>
        <div class="msg-right-body" id="aktif-mesajlar">
          ${mesajlerHtml}
        </div>
        <div class="msg-right-footer">
          <textarea id="admin-msg-inp" placeholder="Mesajınızı yazın…" onkeydown="if(event.ctrlKey&&event.key==='Enter')adminMesajGonder()"></textarea>
          <div style="display:flex;flex-direction:column;gap:6px;">
            <button class="btn btn-primary btn-sm" onclick="adminMesajGonder()">Gönder</button>
          </div>
        </div>`;
      setTimeout(() => {
        const el = document.getElementById("aktif-mesajlar");
        if (el) el.scrollTop = el.scrollHeight;
      }, 50);
    }
  });
}

function adminMesajGonder() {
  if (!secilenKullaniciId) return;
  const icerik = document.getElementById("admin-msg-inp").value.trim();
  if (!icerik) return;
  document.getElementById("admin-msg-inp").value = "";
  fetch("/panel/admin-mesaj-gonder", {method:"POST", headers:auth(), body:JSON.stringify({
    kullanici_id: secilenKullaniciId,
    icerik: icerik,
  })}).then(r => r.json()).then(() => {
    notif("Mesaj gönderildi");
    _konusmaMesajYukle(secilenKullaniciId);
    mesajlariYukle();
  });
}

// ===== KULLANICILAR =====
let _duzenleKullanici = null;

function kullanicilariYukle() {
  fetch("/panel/kullanicilar", {headers: auth()}).then(r => r.json()).then(liste => {
    document.getElementById("kullanici-tablo").innerHTML = liste.map(k => `
      <tr>
        <td>${k.ad_soyad}</td>
        <td>${k.email}</td>
        <td><span class="badge ${k.email_dogrulandi?'b-aktif':'b-pasif'}">${k.email_dogrulandi?'✔':'✗'}</span></td>
        <td>${k.kayit_tar}</td>
        <td>${k.son_giris}</td>
        <td><code>${k.son_ip||"-"}</code></td>
        <td>${k.lisans_kodu ? `<code>${k.lisans_kodu}</code> <span class="badge">${k.lisans_tur||""}</span>` : '<span style="color:#555">Yok</span>'}</td>
        <td>
          <div style="display:flex;gap:4px;">
            <button class="btn btn-primary btn-sm" onclick="kullaniciDuzenleModalAc('${k.id}','${(k.ad_soyad||'').replace(/'/g,'&#39;')}','${k.email}')">✏️ Düzenle</button>
            <button class="btn btn-danger btn-sm" onclick="kullaniciSil('${k.id}','${(k.ad_soyad||'').replace(/'/g,'&#39;')}')">Sil</button>
          </div>
        </td>
      </tr>`).join("");
  });
}

function kullaniciDuzenleModalAc(id, ad, email) {
  _duzenleKullanici = {id, ad, email};
  document.getElementById("kd-bilgi").innerHTML = `<b style="color:#e0e0e0;">${ad}</b> &lt;${email}&gt;`;
  document.getElementById("kd-sifre").value = "";
  document.getElementById("kd-not").value = "";
  document.getElementById("kd-sonuc").style.display = "none";
  const m = document.getElementById("kullanici-duzenle-modal");
  m.style.display = "flex";
}

function kullaniciDuzenleModalKapat() {
  document.getElementById("kullanici-duzenle-modal").style.display = "none";
  _duzenleKullanici = null;
}

function kullaniciDuzenleKaydet() {
  if (!_duzenleKullanici) return;
  const sifre = document.getElementById("kd-sifre").value.trim();
  const not = document.getElementById("kd-not").value.trim();
  const sonucEl = document.getElementById("kd-sonuc");

  if (sifre && sifre.length < 6) {
    sonucEl.textContent = "❌ Şifre en az 6 karakter olmalıdır.";
    sonucEl.style.color = "#f87171";
    sonucEl.style.display = "block";
    return;
  }

  const payload = {};
  if (sifre) payload.sifre = sifre;
  if (not) payload.not = not;

  fetch("/panel/kullanici-duzenle/" + _duzenleKullanici.id, {
    method: "PUT",
    headers: auth(),
    body: JSON.stringify(payload)
  }).then(r => r.json()).then(d => {
    if (d.basarili) {
      sonucEl.textContent = "✅ Değişiklikler kaydedildi.";
      sonucEl.style.color = "#4caf50";
      sonucEl.style.display = "block";
      setTimeout(() => kullaniciDuzenleModalKapat(), 1200);
      kullanicilariYukle();
    } else {
      sonucEl.textContent = "❌ " + (d.detail || "Hata oluştu.");
      sonucEl.style.color = "#f87171";
      sonucEl.style.display = "block";
    }
  }).catch(() => {
    sonucEl.textContent = "❌ Sunucu ile iletişim kurulamadı.";
    sonucEl.style.color = "#f87171";
    sonucEl.style.display = "block";
  });
}

function kullaniciSil(id, ad) {
  if (!confirm(ad + " adlı kullanıcı ve tüm verileri (talepler, mesajlar) silinecek. Aktif lisansı varsa iptal edilecek. Emin misiniz?")) return;
  fetch("/panel/kullanici-sil/" + id, {method: "DELETE", headers: auth()})
    .then(r => r.json())
    .then(d => { notif(d.mesaj || d.detail, !!d.detail); kullanicilariYukle(); });
}

// ===== IP BAN =====
function ipBanEkle() {
  const ip = document.getElementById("ban-ip").value.trim();
  const sebep = document.getElementById("ban-sebep").value.trim();
  if (!ip) { notif("IP adresi girin!", true); return; }
  fetch("/panel/ip-ban-ekle", {method:"POST", headers:auth(), body:JSON.stringify({ip, sebep})})
    .then(r => r.json()).then(d => { notif(d.mesaj || d.detail, !!d.detail); ipBanlariYukle(); });
}

function ipBanKaldir(ip) {
  fetch("/panel/ip-ban-kaldir", {method:"POST", headers:auth(), body:JSON.stringify({ip})})
    .then(r => r.json()).then(d => { notif(d.mesaj || d.detail, !!d.detail); ipBanlariYukle(); });
}

function ipBanlariYukle() {
  fetch("/panel/ip-banlar", {headers: auth()}).then(r => r.json()).then(liste => {
    document.getElementById("ban-tablo").innerHTML = liste.map(b => `
      <tr>
        <td><code>${b.ip}</code></td>
        <td style="color:#888;">${b.sebep||"—"}</td>
        <td>${b.tarih}</td>
        <td><span class="badge ${b.aktif?'b-pasif':'b-aktif'}">${b.aktif?'Aktif Ban':'Kaldırıldı'}</span></td>
        <td>${b.aktif ? `<button class="btn btn-success btn-sm" onclick="ipBanKaldir('${b.ip}')">Kaldır</button>` : "—"}</td>
      </tr>`).join("");
  });
}

// ===== ÜYELİK TÜRLERİ =====
function turEkle() {
  const kod = document.getElementById("tur-kod").value.trim();
  const ad  = document.getElementById("tur-ad").value.trim();
  const aciklama = document.getElementById("tur-aciklama").value.trim();
  const sure_val = document.getElementById("tur-sure").value;
  if (sure_val === "") { notif("Süre (Gün) zorunludur! Sınırsız için 0 girin.", true); return; }
  const sure_gun = parseInt(sure_val) || 0;
  const prefix = document.getElementById("tur-prefix").value.trim() || "STD";
  const sira = parseInt(document.getElementById("tur-sira").value) || 99;
  if (!kod || !ad) { notif("Kod ve ad zorunlu!", true); return; }
  fetch("/panel/uyelik-tur-ekle", {method:"POST", headers:auth(), body:JSON.stringify({kod, ad, aciklama, sira, sure_gun, prefix})})
    .then(r => r.json()).then(d => { notif(d.basarili ? "Tür eklendi" : d.detail, !d.basarili); turleriYukle(); });
}

function turSil(id) {
  if (!confirm("Bu türü silmek istediğinizden emin misiniz?")) return;
  fetch("/panel/uyelik-tur-sil/" + id, {method:"DELETE", headers:auth()})
    .then(r => r.json()).then(d => { notif(d.basarili ? "Tür silindi" : d.detail, !d.basarili); turleriYukle(); });
}

function turToggle(id, aktif) {
  fetch("/panel/uyelik-tur-guncelle", {method:"POST", headers:auth(), body:JSON.stringify({id, aktif: !aktif})})
    .then(() => turleriYukle());
}

function turleriYukle() {
  fetch("/panel/uyelik-turleri", {headers: auth()}).then(r => r.json()).then(liste => {
    document.getElementById("tur-grid").innerHTML = liste.map(t => `
      <div class="tur-card" style="opacity:${t.aktif?1:0.5}">
        <div class="tur-kod">${t.kod}</div>
        <h4>${t.ad}</h4>
        <div class="tur-aciklama">${t.aciklama||"—"}</div>
        <div style="font-size:11px;color:#888;margin-top:6px;">Süre: ${t.sure_gun===0 ? 'Ömür Boyu' : t.sure_gun + ' Gün'} | Ön Ek: ${t.prefix}</div>
        <div class="row-btns" style="margin-top:8px;">
          <button class="btn btn-ghost btn-sm" onclick="turToggle(${t.id},${t.aktif})">${t.aktif?"Pasif Et":"Aktif Et"}</button>
          <button class="btn btn-danger btn-sm" onclick="turSil(${t.id})">Sil</button>
        </div>
      </div>`).join("");
      
    const ltur = document.getElementById("l-tur");
    if (ltur) {
      ltur.innerHTML = liste.filter(t => t.aktif).map(t => `<option value="${t.kod}">${t.ad} (${t.sure_gun === 0 ? 'Ömür Boyu' : t.sure_gun + ' Gün'})</option>`).join("");
    }
  });
}

// ===== LOGLAR =====
function logYukle() {
  const son = document.getElementById("log-adet").value;
  fetch("/panel/loglar?son=" + son, {headers: auth()}).then(r => r.json()).then(logs => {
    const renkler = {aktivasyon:"#00e676", kontrol:"#40c4ff", red:"#ff5252"};
    document.getElementById("log-output").innerHTML = logs.map(l =>
      `<span style="color:#555">[${l.tarih}]</span> <span style="color:${renkler[l.islem]||'#aaa'}">${l.islem.toUpperCase().padEnd(12)}</span> <span style="color:#7eb8ff">${l.lisans_kodu}</span> <span style="color:#888">IP:${l.ip}</span> ${l.mesaj}`
    ).join("\n");
  });
}

// ===== YETKİLİLER (RBAC) =====
function adminGuncelle() {
  const kadi = document.getElementById("a-yeni-kadi").value.trim();
  const sifre = document.getElementById("a-yeni-sifre").value.trim();
  if (!kadi || !sifre) { notif("Kullanıcı adı ve şifre boş olamaz!", true); return; }
  
  if (!confirm("Ana admin giriş bilgilerini değiştirmek üzeresiniz. Onaylıyor musunuz?")) return;
  
  fetch("/panel/admin-guncelle", {
    method: "POST", headers: auth(), body: JSON.stringify({yeni_kullanici: kadi, yeni_sifre: sifre})
  }).then(r => r.json()).then(d => {
    notif(d.mesaj || d.detail, !d.basarili);
    if(d.basarili) {
       setTimeout(() => panelCikis(), 1500);
    }
  });
}

function yetkilileriYukle() {
  fetch("/panel/yetkililer", {headers: auth()}).then(r => r.json()).then(liste => {
    if(liste.detail) {
        document.getElementById("yetkili-tablo").innerHTML = `<tr><td colspan="7" style="color:#f87171">${liste.detail}</td></tr>`;
        return;
    }
    const yStr = (y) => Object.entries(y).filter(([k,v]) => v).map(([k,v]) => `<span class="badge b-aktif" style="margin:2px">${k.split('_').join(' ')}</span>`).join("") || '<span style="color:#555">Yok</span>';
    document.getElementById("yetkili-tablo").innerHTML = liste.map(y => `
      <tr>
        <td>${y.kullanici_adi}</td>
        <td>${y.isim_soyad || "-"}</td>
        <td><span class="badge ${y.is_admin ? 'b-onay' : 'b-bekl'}">${y.is_admin ? 'Süper Admin' : 'Yetkili'}</span></td>
        <td style="max-width:200px;line-height:1.8">${y.is_admin ? '<span class="badge b-onay">TÜM YETKİLER</span>' : yStr(y.yetkiler)}</td>
        <td>${y.son_giris}</td>
        <td>${y.son_cikis}</td>
        <td>${!y.is_admin ? `<div style="display:flex;gap:4px;"><button class="btn btn-primary btn-sm" onclick="yetkiliDuzenleModalAc(${y.id},'${y.kullanici_adi}','${y.isim_soyad||''}','${y.telegram_chat_id||''}',${y.telegram_bildirim_alabilir},${JSON.stringify(y.yetkiler).replace(/"/g,'&quot;')})">✏️ Düzenle</button><button class="btn btn-danger btn-sm" onclick="yetkiliSil(${y.id}, '${y.kullanici_adi}')">Sil</button></div>` : "-"}</td>
      </tr>`).join("");
  }).catch(e => {
      document.getElementById("yetkili-tablo").innerHTML = `<tr><td colspan="7" style="color:#f87171">Yetkiniz yok veya yüklenemedi.</td></tr>`;
  });
}

function yetkiliEkle() {
  const kullanici_adi = document.getElementById("y-kadi").value.trim();
  const isim_soyad = document.getElementById("y-isim").value.trim();
  const email = document.getElementById("y-email").value.trim();
  const sifre = document.getElementById("y-sifre").value.trim();
  const yetkiler = {
      lisans_olustur: document.getElementById("cb-lisans_olustur").checked,
      lisans_sil: document.getElementById("cb-lisans_sil").checked,
      hwid_sifirla: document.getElementById("cb-hwid_sifirla").checked,
      sure_uzat: document.getElementById("cb-sure_uzat").checked,
      talep_onayla: document.getElementById("cb-talep_onayla").checked,
      kullanici_ekle: document.getElementById("cb-kullanici_ekle").checked,
      mesaj_yaz: document.getElementById("cb-mesaj_yaz").checked,
      ip_ban: document.getElementById("cb-ip_ban").checked,
      uyelik_tur: document.getElementById("cb-uyelik_tur").checked,
      offline_lisans: document.getElementById("cb-offline_lisans").checked,
  };
  
  if (!kullanici_adi || !email || !sifre || !isim_soyad) { notif("Tüm alanları doldurun!", true); return; }
  
  fetch("/panel/yetkili-ekle", {
      method:"POST", 
      headers:auth(), 
      body:JSON.stringify({kullanici_adi, isim_soyad, email, sifre, yetkiler})
  }).then(r => r.json()).then(d => {
      if(d.basarili) {
          notif("Yetkili başarıyla eklendi");
          document.getElementById("y-kadi").value = "";
          document.getElementById("y-isim").value = "";
          document.getElementById("y-email").value = "";
          document.getElementById("y-sifre").value = "";
          yetkilileriYukle();
      } else {
          notif(d.detail || "Eklenemedi", true);
      }
  });
}

function offlineLisansUret() {
  const req_kodu = document.getElementById("ol-istek-kodu").value.trim();
  const sure     = parseInt(document.getElementById("ol-sure").value) || 30;
  const yetki    = document.getElementById("ol-yetki").value;
  const hataEl   = document.getElementById("ol-hata");

  hataEl.style.display = "none";
  if(!req_kodu) {
     hataEl.textContent = "İstek Kodu girmeniz gerekiyor.";
     hataEl.style.display = "block";
     return;
  }
  
  fetch("/panel/offline-lisans-uret", {
      method:"POST", 
      headers:auth(),
      body: JSON.stringify({ istek_kodu: req_kodu, sure_gun: sure, yetki: yetki })
  }).then(r => r.json()).then(d => {
      if(d.basarili) {
          document.getElementById("ol-akt-kod").textContent = d.aktivasyon_kodu;
          document.getElementById("ol-det-istek").textContent = d.istek_kodu;
          document.getElementById("ol-det-sure").textContent = d.sure_gun;
          document.getElementById("ol-det-yetki").textContent = d.yetki;
          
          document.getElementById("ol-sonuc-kart").style.display = "block";
          document.getElementById("ol-kopyala-ok").style.display = "none";
          document.getElementById("ol-kopyala-btn").textContent = "📋 Kopyala";
          notif("Aktivasyon kodu üretildi.");
      } else {
          hataEl.textContent = d.detail || "Hata oluştu.";
          hataEl.style.display = "block";
          document.getElementById("ol-sonuc-kart").style.display = "none";
      }
  }).catch(e => {
      hataEl.textContent = "Sunucu ile iletişim kurulamadı.";
      hataEl.style.display = "block";
  });
}

function olKopyala() {
  const txt = document.getElementById("ol-akt-kod").textContent;
  if(!txt) return;
  navigator.clipboard.writeText(txt).then(() => {
      document.getElementById("ol-kopyala-btn").textContent = "✓ Kopyalandı";
      document.getElementById("ol-kopyala-ok").style.display = "inline";
      setTimeout(() => {
          document.getElementById("ol-kopyala-btn").textContent = "📋 Kopyala";
          document.getElementById("ol-kopyala-ok").style.display = "none";
      }, 2000);
  });
}

let _duzenleYetkili = null;

function yetkiliDuzenleModalAc(id, kadi, isim, telegramId, telegramBildirim, yetkillerJson) {
  _duzenleYetkili = id;
  let yetkiler = {};
  try { yetkiler = typeof yetkillerJson === 'string' ? JSON.parse(yetkillerJson) : yetkillerJson; } catch(e) {}
  document.getElementById("yd-bilgi").innerHTML = `<b style="color:#e0e0e0;">${isim||kadi}</b> <span style="color:#666;">(@${kadi})</span>`;
  document.getElementById("yd-sifre").value = "";
  document.getElementById("yd-telegram-id").value = telegramId || "";
  document.getElementById("yd-telegram-bildirim").checked = !!telegramBildirim;
  const cbMap = ["lisans_olustur","lisans_sil","hwid_sifirla","sure_uzat","talep_onayla","kullanici_ekle","mesaj_yaz","ip_ban","uyelik_tur","offline_lisans"];
  cbMap.forEach(k => {
    const el = document.getElementById("yd-cb-" + k);
    if (el) el.checked = !!(yetkiler[k]);
  });
  document.getElementById("yd-sonuc").style.display = "none";
  document.getElementById("yetkili-duzenle-modal").style.display = "flex";
}

function yetkiliDuzenleModalKapat() {
  document.getElementById("yetkili-duzenle-modal").style.display = "none";
  _duzenleYetkili = null;
}

function yetkiliDuzenleKaydet() {
  if (!_duzenleYetkili) return;
  const sonucEl = document.getElementById("yd-sonuc");
  const sifre = document.getElementById("yd-sifre").value.trim();
  const telegramId = document.getElementById("yd-telegram-id").value.trim();
  const telegramBildirim = document.getElementById("yd-telegram-bildirim").checked;

  const cbMap = ["lisans_olustur","lisans_sil","hwid_sifirla","sure_uzat","talep_onayla","kullanici_ekle","mesaj_yaz","ip_ban","uyelik_tur","offline_lisans"];
  const yetkiler = {};
  cbMap.forEach(k => {
    const el = document.getElementById("yd-cb-" + k);
    yetkiler[k] = el ? el.checked : false;
  });

  const payload = { yetkiler, telegram_chat_id: telegramId, telegram_bildirim_alabilir: telegramBildirim };
  if (sifre) payload.sifre = sifre;

  fetch("/panel/yetkili-guncelle/" + _duzenleYetkili, {
    method: "PUT",
    headers: auth(),
    body: JSON.stringify(payload)
  }).then(r => r.json()).then(d => {
    if (d.basarili) {
      sonucEl.textContent = "✅ Değişiklikler kaydedildi.";
      sonucEl.style.color = "#4caf50";
      sonucEl.style.display = "block";
      setTimeout(() => { yetkiliDuzenleModalKapat(); yetkilileriYukle(); }, 1200);
    } else {
      sonucEl.textContent = "❌ " + (d.detail || "Hata oluştu.");
      sonucEl.style.color = "#f87171";
      sonucEl.style.display = "block";
    }
  }).catch(() => {
    sonucEl.textContent = "❌ Sunucu ile iletişim kurulamadı.";
    sonucEl.style.color = "#f87171";
    sonucEl.style.display = "block";
  });
}

function yetkiliSil(id, kadi) {
  if (!confirm(`${kadi} adlı yetkiliyi silmek istediğinize emin misiniz?`)) return;
  fetch("/panel/yetkili-sil/" + id, {method:"DELETE", headers:auth()})
    .then(r => r.json()).then(d => {
        notif(d.mesaj || d.detail, !d.basarili);
        yetkilileriYukle();
    });
}

// ===== PANEL LOGLARI =====
function panelLoglariYukle() {
  fetch("/panel/panel-loglari", {headers: auth()}).then(r => r.json()).then(liste => {
    if(liste.detail) {
        document.getElementById("panel-log-tablo").innerHTML = `<tr><td colspan="4" style="color:#f87171">${liste.detail}</td></tr>`;
        return;
    }
    document.getElementById("panel-log-tablo").innerHTML = liste.map(l => `
      <tr>
        <td style="color:#888">${l.tarih}</td>
        <td style="font-weight:600;color:#5b8cff">${l.kullanici_adi}</td>
        <td><span class="badge b-bekl" style="background:#222540;color:#e0e0e0;border-color:#2a2d3e">${l.islem}</span></td>
        <td style="color:#aaa">${l.detay}</td>
      </tr>`).join("");
  }).catch(e => {
      document.getElementById("panel-log-tablo").innerHTML = `<tr><td colspan="4" style="color:#f87171">Yetkiniz yok veya yüklenemedi.</td></tr>`;
  });
}

// ===== ACCORDION =====
function toggleAccordion(header) {
  const content = header.nextElementSibling;
  const isOpen = content.classList.contains("show");
  if (isOpen) {
    content.classList.remove("show");
    header.classList.remove("open");
  } else {
    content.classList.add("show");
    header.classList.add("open");
  }
}

// ===== YENİ LİSANS ALT SEKMELER =====
function switchYeniLisansTab(tip) {
  document.getElementById("tab-yeni-online").classList.toggle("active", tip === "online");
  document.getElementById("tab-yeni-offline").classList.toggle("active", tip === "offline");
  document.getElementById("pane-yeni-online").classList.toggle("active", tip === "online");
  document.getElementById("pane-yeni-offline").classList.toggle("active", tip === "offline");
}

// ===== YENİ LİSANS SAYFASI - OFFLINE FORM =====
function offlineLisansUretBtn() {
  const kime = document.getElementById("off-kime").value.trim();
  const istek = document.getElementById("off-istek").value.trim();
  const sure = parseInt(document.getElementById("off-sure").value) || 30;
  const yetki = document.getElementById("off-yetki").value;
  const sonucEl = document.getElementById("off-sonuc");

  if (!kime) { sonucEl.textContent = "\u274c Kime \u00fcretildi\u011fini girin!"; sonucEl.style.color="#f87171"; return; }
  if (!istek) { sonucEl.textContent = "\u274c \u0130stek kodunu girin!"; sonucEl.style.color="#f87171"; return; }

  fetch("/panel/offline-lisans-uret", {
    method: "POST",
    headers: auth(),
    body: JSON.stringify({ istek_kodu: istek, kime_uretildi: kime, sure_gun: sure, yetki: yetki })
  }).then(r => r.json()).then(d => {
    if (d.basarili) {
      sonucEl.style.color = "#4ade80";
      const kod = d.aktivasyon_kodu || "";
      sonucEl.innerHTML = "\u2705 Aktivasyon Kodu: <b style=\"font-family:Consolas;letter-spacing:1px;\">" + kod + "</b> <button class=\"btn btn-ghost btn-sm\" style=\"margin-left:8px;\" onclick=\"navigator.clipboard.writeText('" + kod + "').then(()=>notif('Kopyaland\u0131!'))\">&#128203; Kopyala</button>";
      notif("Offline lisans \u00fcretildi.");
    } else {
      sonucEl.textContent = "\u274c " + (d.detail || "Hata olu\u015ftu.");
      sonucEl.style.color = "#f87171";
    }
  }).catch(() => {
    sonucEl.textContent = "\u274c Sunucu ile ileti\u015fim kurulamad\u0131.";
    sonucEl.style.color = "#f87171";
  });
}

// Startup
document.getElementById("inp-kullanici").focus();
document.addEventListener("keydown", e => {
  if (e.key === "Escape") {
    talepModalKapat();
    yetkiliDuzenleModalKapat();
    kullaniciDuzenleModalKapat();
  }
});
</script>
</body>
</html>"""


@app.get("/panel", response_class=HTMLResponse)
def panel_html():
    return HTMLResponse(content=PANEL_HTML)


# =====================================================================
# KULLANICI KAYIT SİTESİ HTML
# =====================================================================

SITE_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Sora:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;600&display=swap');
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
:root {
  --bg: #080b14;
  --surface: #0e1221;
  --border: #1a2040;
  --accent: #3d6fff;
  --accent2: #00d4ff;
  --text: #e2e8f8;
  --muted: #5a6a8a;
  --success: #22c55e;
  --danger: #ef4444;
  --warn: #f59e0b;
}
html, body { min-height: 100vh; font-family: 'Sora', sans-serif; background: var(--bg); color: var(--text); }
body { background-image: radial-gradient(ellipse at 20% 50%, #0d1a4020 0%, transparent 60%), radial-gradient(ellipse at 80% 10%, #0a2a5020 0%, transparent 50%); }

/* Navbar */
.nav { display: flex; align-items: center; justify-content: space-between; padding: 0 40px; height: 64px; border-bottom: 1px solid var(--border); background: rgba(8,11,20,0.9); backdrop-filter: blur(12px); position: sticky; top: 0; z-index: 100; }
.nav-brand { font-size: 16px; font-weight: 700; color: var(--text); display: flex; align-items: center; gap: 10px; }
.nav-brand .dot { width: 8px; height: 8px; border-radius: 50%; background: var(--accent); box-shadow: 0 0 12px var(--accent); }
.nav-links { display: flex; align-items: center; gap: 8px; }
.nav-btn { padding: 7px 18px; border-radius: 6px; font-size: 13px; font-weight: 600; cursor: pointer; border: none; transition: all 0.2s; font-family: 'Sora', sans-serif; }
.nav-btn-ghost { background: transparent; color: var(--muted); border: 1px solid var(--border); }
.nav-btn-ghost:hover { color: var(--text); border-color: var(--accent); }
.nav-btn-primary { background: var(--accent); color: white; }
.nav-btn-primary:hover { background: #5580ff; }

/* Hero */
.hero { text-align: center; padding: 80px 24px 60px; }
.hero-badge { display: inline-flex; align-items: center; gap: 6px; background: #3d6fff15; border: 1px solid #3d6fff33; color: var(--accent2); padding: 5px 14px; border-radius: 20px; font-size: 12px; font-weight: 600; letter-spacing: 0.5px; text-transform: uppercase; margin-bottom: 24px; }
.hero h1 { font-size: clamp(32px, 6vw, 60px); font-weight: 700; line-height: 1.1; margin-bottom: 20px; }
.hero h1 span { background: linear-gradient(135deg, var(--accent), var(--accent2)); -webkit-background-clip: text; -webkit-text-fill-color: transparent; background-clip: text; }
.hero p { color: var(--muted); font-size: 17px; max-width: 540px; margin: 0 auto 36px; line-height: 1.7; }
.hero-btns { display: flex; gap: 12px; justify-content: center; flex-wrap: wrap; }
.btn-hero { padding: 13px 28px; border-radius: 8px; font-size: 15px; font-weight: 600; cursor: pointer; border: none; font-family: 'Sora', sans-serif; transition: all 0.2s; }
.btn-hero-primary { background: linear-gradient(135deg, var(--accent), #5b8fff); color: white; box-shadow: 0 0 32px #3d6fff44; }
.btn-hero-primary:hover { transform: translateY(-2px); box-shadow: 0 0 48px #3d6fff66; }
.btn-hero-ghost { background: transparent; color: var(--text); border: 1px solid var(--border); }
.btn-hero-ghost:hover { border-color: var(--accent); color: var(--accent); }

/* Features */
.features { display: grid; grid-template-columns: repeat(auto-fill, minmax(240px, 1fr)); gap: 16px; max-width: 900px; margin: 0 auto 80px; padding: 0 24px; }
.feature { background: var(--surface); border: 1px solid var(--border); border-radius: 12px; padding: 24px; }
.feature-icon { font-size: 28px; margin-bottom: 12px; }
.feature h3 { font-size: 15px; font-weight: 600; margin-bottom: 8px; }
.feature p { font-size: 13px; color: var(--muted); line-height: 1.6; }

/* Plans */
.plans-section { padding: 0 24px 80px; max-width: 900px; margin: 0 auto; }
.section-title { text-align: center; font-size: 28px; font-weight: 700; margin-bottom: 8px; }
.section-sub { text-align: center; color: var(--muted); font-size: 15px; margin-bottom: 36px; }
.plans { display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); gap: 14px; }
.plan-card { background: var(--surface); border: 1px solid var(--border); border-radius: 12px; padding: 22px; cursor: pointer; transition: all 0.2s; position: relative; }
.plan-card:hover { border-color: var(--accent); transform: translateY(-2px); }
.plan-card.selected { border-color: var(--accent); background: #3d6fff0d; box-shadow: 0 0 24px #3d6fff22; }
.plan-card.selected::after { content: '✓'; position: absolute; top: 12px; right: 14px; color: var(--accent); font-weight: 700; font-size: 16px; }
.plan-name { font-size: 15px; font-weight: 700; margin-bottom: 6px; }
.plan-desc { font-size: 12px; color: var(--muted); line-height: 1.5; }

/* Forms */
.form-container { max-width: 440px; margin: 0 auto; padding: 0 24px 80px; }
.form-card { background: var(--surface); border: 1px solid var(--border); border-radius: 16px; padding: 32px; }
.form-title { font-size: 22px; font-weight: 700; margin-bottom: 6px; }
.form-sub { font-size: 13px; color: var(--muted); margin-bottom: 24px; }
.form-group { margin-bottom: 16px; }
.form-label { display: block; font-size: 13px; font-weight: 500; color: #8a9bc0; margin-bottom: 7px; }
.form-input { width: 100%; background: var(--bg); border: 1px solid var(--border); border-radius: 8px; padding: 11px 14px; color: var(--text); font-size: 14px; font-family: 'Sora', sans-serif; transition: border-color 0.2s; }
.form-input:focus { outline: none; border-color: var(--accent); }
.form-btn { width: 100%; background: linear-gradient(135deg, var(--accent), #5b8fff); color: white; border: none; border-radius: 8px; padding: 13px; font-size: 15px; font-weight: 700; cursor: pointer; font-family: 'Sora', sans-serif; transition: all 0.2s; margin-top: 6px; }
.form-btn:hover { opacity: 0.92; transform: translateY(-1px); }
.form-alt { text-align: center; font-size: 13px; color: var(--muted); margin-top: 16px; }
.form-alt a { color: var(--accent); cursor: pointer; font-weight: 600; }
.form-err { background: #ef444415; border: 1px solid #ef444433; color: #fca5a5; border-radius: 6px; padding: 10px 14px; font-size: 13px; margin-bottom: 14px; display: none; }
.form-ok { background: #22c55e15; border: 1px solid #22c55e33; color: #86efac; border-radius: 6px; padding: 10px 14px; font-size: 13px; margin-bottom: 14px; display: none; }

/* Dashboard */
.dashboard { max-width: 800px; margin: 0 auto; padding: 32px 24px; }
.dash-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 28px; }
.dash-title { font-size: 22px; font-weight: 700; }
.dash-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 14px; margin-bottom: 20px; }
.dash-card { background: var(--surface); border: 1px solid var(--border); border-radius: 12px; padding: 20px; }
.dash-card.full { grid-column: 1 / -1; }
.dash-card h3 { font-size: 13px; color: var(--muted); text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 12px; }
.dash-val { font-size: 20px; font-weight: 700; color: var(--text); }
.dash-sub { font-size: 12px; color: var(--muted); margin-top: 4px; }
.license-box { background: var(--bg); border: 1px solid var(--accent); border-radius: 10px; padding: 18px; text-align: center; }
.license-code { font-family: 'JetBrains Mono', monospace; font-size: 18px; font-weight: 600; color: var(--accent2); letter-spacing: 2px; }
.license-sub { font-size: 12px; color: var(--muted); margin-top: 6px; }
.status-badge { display: inline-flex; align-items: center; gap: 6px; padding: 4px 12px; border-radius: 20px; font-size: 12px; font-weight: 600; }
.status-active { background: #22c55e15; color: #4ade80; border: 1px solid #22c55e33; }
.status-none { background: #ef444415; color: #f87171; border: 1px solid #ef444433; }
.status-pending { background: #f59e0b15; color: #fbbf24; border: 1px solid #f59e0b33; }

/* Mesaj alanı */
.msg-area { display: flex; flex-direction: column; gap: 10px; max-height: 320px; overflow-y: auto; padding: 4px 0; margin-bottom: 12px; }
.msg-b { max-width: 80%; padding: 10px 14px; border-radius: 10px; font-size: 13px; line-height: 1.6; }
.msg-b.benim { background: #3d6fff22; color: #93b4ff; align-self: flex-end; border-bottom-right-radius: 2px; border: 1px solid #3d6fff33; }
.msg-b.admin { background: var(--bg); color: var(--text); align-self: flex-start; border: 1px solid var(--border); border-bottom-left-radius: 2px; }
.msg-wrap { display: flex; flex-direction: column; }
.msg-wrap.right { align-items: flex-end; }
.msg-t { font-size: 10px; color: var(--muted); margin-top: 3px; }
.msg-input { width: 100%; background: var(--bg); border: 1px solid var(--border); border-radius: 8px; padding: 10px 14px; color: var(--text); font-size: 13px; font-family: 'Sora', sans-serif; resize: vertical; min-height: 72px; }
.msg-input:focus { outline: none; border-color: var(--accent); }

/* Talepler listesi */
.talep-item { display: flex; align-items: center; justify-content: space-between; padding: 12px 16px; background: var(--bg); border: 1px solid var(--border); border-radius: 8px; margin-bottom: 8px; }
.badge-sm { padding: 3px 10px; border-radius: 10px; font-size: 11px; font-weight: 600; }
.b-bekl { background: #f59e0b20; color: #fbbf24; border: 1px solid #f59e0b44; }
.b-onay { background: #22c55e20; color: #4ade80; border: 1px solid #22c55e44; }
.b-red  { background: #ef444420; color: #f87171; border: 1px solid #ef444444; }

/* Responsive */
@media (max-width: 600px) {
  .nav { padding: 0 16px; }
  .hero { padding: 48px 16px 40px; }
  .dash-grid { grid-template-columns: 1fr; }
  .msg-split { grid-template-columns: 1fr; }
}

/* ===== ÇEREZ BANNER ===== */
#cerez-banner {
  position: fixed; bottom: 0; left: 0; right: 0; z-index: 9999;
  background: #0e1221; border-top: 1px solid #1a2040;
  padding: 20px 32px; display: flex; align-items: flex-start; gap: 24px;
  box-shadow: 0 -8px 40px rgba(0,0,0,0.5);
  animation: cerezSlideUp 0.35s cubic-bezier(.22,1,.36,1);
}
@keyframes cerezSlideUp {
  from { transform: translateY(100%); opacity: 0; }
  to   { transform: translateY(0);    opacity: 1; }
}
#cerez-banner.cerez-gizle {
  animation: cerezSlideDown 0.3s ease forwards;
}
@keyframes cerezSlideDown {
  to { transform: translateY(110%); opacity: 0; }
}
.cerez-icerik { flex: 1; }
.cerez-baslik { font-size: 15px; font-weight: 700; color: var(--text); margin-bottom: 6px; display: flex; align-items: center; gap: 8px; }
.cerez-aciklama { font-size: 13px; color: var(--muted); line-height: 1.65; max-width: 640px; }
.cerez-aciklama a { color: var(--accent); cursor: pointer; text-decoration: underline; text-underline-offset: 2px; }
.cerez-aksiyonlar { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; flex-shrink: 0; margin-top: 4px; }
.cerez-btn { padding: 9px 20px; border-radius: 7px; font-size: 13px; font-weight: 600; cursor: pointer; border: none; font-family: 'Sora', sans-serif; transition: all 0.18s; white-space: nowrap; }
.cerez-btn-tum     { background: linear-gradient(135deg, var(--accent), #5b8fff); color: #fff; }
.cerez-btn-tum:hover { opacity: 0.88; transform: translateY(-1px); }
.cerez-btn-zorunlu { background: transparent; color: var(--muted); border: 1px solid var(--border); }
.cerez-btn-zorunlu:hover { color: var(--text); border-color: var(--accent); }
.cerez-btn-reddet  { background: transparent; color: #f87171; border: 1px solid #ef444433; }
.cerez-btn-reddet:hover { background: #ef444412; border-color: #f87171; }
.cerez-btn-ayarlar { background: transparent; color: var(--accent); border: 1px solid #3d6fff44; }
.cerez-btn-ayarlar:hover { background: #3d6fff12; }

/* Çerez Tercih Modalı */
#cerez-modal-overlay {
  position: fixed; inset: 0; z-index: 10000;
  background: rgba(0,0,0,0.75); backdrop-filter: blur(6px);
  display: none; align-items: center; justify-content: center; padding: 16px;
}
#cerez-modal-overlay.aktif { display: flex; }
#cerez-modal {
  background: #0e1221; border: 1px solid #1a2040; border-radius: 16px;
  width: 100%; max-width: 520px; max-height: 90vh; overflow-y: auto;
  padding: 32px;
}
.cerez-modal-baslik { font-size: 18px; font-weight: 700; margin-bottom: 6px; }
.cerez-modal-sub { font-size: 13px; color: var(--muted); margin-bottom: 24px; line-height: 1.6; }
.cerez-kategori { background: #080b14; border: 1px solid #1a2040; border-radius: 10px; padding: 16px 18px; margin-bottom: 12px; }
.cerez-kat-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 8px; }
.cerez-kat-ad { font-size: 14px; font-weight: 600; color: var(--text); }
.cerez-kat-acik { font-size: 12px; color: var(--muted); line-height: 1.55; }
.cerez-toggle { position: relative; width: 42px; height: 24px; flex-shrink: 0; }
.cerez-toggle input { opacity: 0; width: 0; height: 0; }
.cerez-toggle-slider {
  position: absolute; inset: 0; border-radius: 24px;
  background: #1a2040; cursor: pointer; transition: background 0.2s;
}
.cerez-toggle-slider::before {
  content: ''; position: absolute; width: 18px; height: 18px; border-radius: 50%;
  background: #5a6a8a; bottom: 3px; left: 3px; transition: all 0.2s;
}
.cerez-toggle input:checked + .cerez-toggle-slider { background: #3d6fff44; border: 1px solid #3d6fff88; }
.cerez-toggle input:checked + .cerez-toggle-slider::before { transform: translateX(18px); background: var(--accent); box-shadow: 0 0 8px #3d6fff88; }
.cerez-toggle input:disabled + .cerez-toggle-slider { opacity: 0.6; cursor: not-allowed; }
.cerez-zorunlu-etiket { font-size: 11px; color: #4ade80; background: #22c55e15; border: 1px solid #22c55e33; padding: 2px 8px; border-radius: 10px; font-weight: 600; }
.cerez-modal-alt { display: flex; gap: 10px; justify-content: flex-end; margin-top: 24px; flex-wrap: wrap; }

@media (max-width: 600px) {
  #cerez-banner { flex-direction: column; padding: 16px; gap: 14px; }
  .cerez-aksiyonlar { width: 100%; justify-content: stretch; }
  .cerez-btn { flex: 1; text-align: center; }
}
</style>
"""

SITE_HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="tr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>OPC Gateway — Lisans Sistemi</title>
{CSS}
</head>
<body>

<!-- ===== ÇEREZ ONAYI BANNER ===== -->
<div id="cerez-banner" style="display:none;">
  <div class="cerez-icerik">
    <div class="cerez-baslik">🍪 Çerez Politikası</div>
    <div class="cerez-aciklama">
      Bu site yalnızca <strong>zorunlu oturum çerezleri</strong> kullanmaktadır. Oturum çerezi, giriş yaptıktan sonra kimliğinizi doğrulamak için gereklidir; reklam, izleme veya pazarlama amaçlı herhangi bir çerez kullanılmamaktadır.
      <a onclick="cerezAyarlariAc()">Çerez tercihlerini yönet →</a>
    </div>
  </div>
  <div class="cerez-aksiyonlar">
    <button class="cerez-btn cerez-btn-tum"     onclick="cerezKabulEt('tum')">Tümünü Kabul Et</button>
    <button class="cerez-btn cerez-btn-zorunlu" onclick="cerezKabulEt('zorunlu')">Yalnızca Zorunlu</button>
    <button class="cerez-btn cerez-btn-reddet"  onclick="cerezKabulEt('reddet')">Reddet</button>
    <button class="cerez-btn cerez-btn-ayarlar" onclick="cerezAyarlariAc()">Tercihler</button>
  </div>
</div>

<!-- ===== ÇEREZ TERCİH MODALI ===== -->
<div id="cerez-modal-overlay">
  <div id="cerez-modal">
    <div class="cerez-modal-baslik">🍪 Çerez Tercihleri</div>
    <div class="cerez-modal-sub">
      Aşağıdaki kategorileri dilediğiniz gibi etkinleştirip devre dışı bırakabilirsiniz.
      Zorunlu çerezler sitenin temel işlevleri için gereklidir ve devre dışı bırakılamaz.
    </div>

    <!-- Zorunlu Çerezler -->
    <div class="cerez-kategori">
      <div class="cerez-kat-header">
        <div>
          <div class="cerez-kat-ad">Zorunlu Çerezler</div>
        </div>
        <div style="display:flex;align-items:center;gap:8px;">
          <span class="cerez-zorunlu-etiket">Her Zaman Aktif</span>
          <label class="cerez-toggle">
            <input type="checkbox" checked disabled>
            <span class="cerez-toggle-slider"></span>
          </label>
        </div>
      </div>
      <div class="cerez-kat-acik">
        <strong>session</strong> — Giriş yaptıktan sonra kimliğinizi doğrulamak için kullanılır. 7 gün boyunca geçerlidir.
        Oturum kapatıldığında veya süre dolduğunda otomatik olarak silinir. Bu çerez olmadan sisteme giriş yapamazsınız.
      </div>
    </div>

    <!-- Fonksiyonel Çerezler -->
    <div class="cerez-kategori">
      <div class="cerez-kat-header">
        <div>
          <div class="cerez-kat-ad">Fonksiyonel Çerezler</div>
        </div>
        <label class="cerez-toggle">
          <input type="checkbox" id="cerez-toggle-fonk" checked>
          <span class="cerez-toggle-slider"></span>
        </label>
      </div>
      <div class="cerez-kat-acik">
        <strong>cookie_consent</strong> — Çerez tercihlerinizi hatırlamak için kullanılır (1 yıl geçerli).
        Bu çerezi devre dışı bırakırsanız her ziyarette tekrar onay kutusu görüntülenir.
      </div>
    </div>

    <!-- Analitik -->
    <div class="cerez-kategori" style="opacity:0.6;">
      <div class="cerez-kat-header">
        <div>
          <div class="cerez-kat-ad">Analitik Çerezler</div>
        </div>
        <label class="cerez-toggle">
          <input type="checkbox" id="cerez-toggle-analitik" disabled>
          <span class="cerez-toggle-slider"></span>
        </label>
      </div>
      <div class="cerez-kat-acik">
        Bu site şu an herhangi bir analitik çerez kullanmamaktadır. İleride eklenirse burada listelenecektir.
      </div>
    </div>

    <!-- Pazarlama -->
    <div class="cerez-kategori" style="opacity:0.6;">
      <div class="cerez-kat-header">
        <div>
          <div class="cerez-kat-ad">Pazarlama / Reklam Çerezleri</div>
        </div>
        <label class="cerez-toggle">
          <input type="checkbox" id="cerez-toggle-reklam" disabled>
          <span class="cerez-toggle-slider"></span>
        </label>
      </div>
      <div class="cerez-kat-acik">
        Bu site herhangi bir reklam veya izleme çerezi kullanmamaktadır.
      </div>
    </div>

    <div class="cerez-modal-alt">
      <button class="cerez-btn cerez-btn-zorunlu" onclick="cerezModalKapat()">İptal</button>
      <button class="cerez-btn cerez-btn-reddet"  onclick="cerezKabulEt('reddet')">Reddet</button>
      <button class="cerez-btn cerez-btn-tum"     onclick="cerezAyarlariKaydet()">Seçimlerimi Kaydet</button>
    </div>
  </div>
</div>

<nav class="nav">
  <div class="nav-brand">
    <div class="dot"></div>
    OPC Gateway
  </div>
  <div class="nav-links" id="nav-links">
    <button class="nav-btn nav-btn-ghost" onclick="sayfaGoster('giris')">Giriş Yap</button>
    <button class="nav-btn nav-btn-primary" onclick="sayfaGoster('kayit')">Kayıt Ol</button>
  </div>
</nav>

<!-- ANASAYFA -->
<div id="sayfa-anasayfa">
  <div class="hero">
    <div class="hero-badge">⚡ OPC Gateway Lisans Sistemi</div>
    <h1>Endüstriyel Otomasyon<br><span>Lisans Yönetimi</span></h1>
    <p>OPC Gateway yazılımı için güvenli, hızlı ve kolay lisans aktivasyon sistemi.</p>
    <div class="hero-btns">
      <button class="btn-hero btn-hero-primary" onclick="sayfaGoster('kayit')">Hemen Başla →</button>
      <button class="btn-hero btn-hero-ghost" onclick="sayfaGoster('planlar')">Planları İncele</button>
    </div>
  </div>

  <div class="features">
    <div class="feature">
      <div class="feature-icon">🔐</div>
      <h3>Güvenli Aktivasyon</h3>
      <p>HWID tabanlı lisans sistemi ile yazılımınızı yetkisiz kullanıma karşı koruyun.</p>
    </div>
    <div class="feature">
      <div class="feature-icon">⚡</div>
      <h3>Anında Aktivasyon</h3>
      <p>Lisans kodunu aldıktan sonra saniyeler içinde programınızı aktive edin.</p>
    </div>
    <div class="feature">
      <div class="feature-icon">💬</div>
      <h3>7/24 Destek</h3>
      <p>Hesabınızdaki destek sistemi üzerinden doğrudan ekibimize ulaşın.</p>
    </div>
    <div class="feature">
      <div class="feature-icon">🔄</div>
      <h3>Esnek Planlar</h3>
      <p>Aylık, yıllık veya ömür boyu seçeneklerden ihtiyacınıza uygun planı seçin.</p>
    </div>
  </div>
</div>

<!-- PLANLAR -->
<div id="sayfa-planlar" style="display:none">
  <div style="height:48px;"></div>
  <div class="plans-section">
    <div class="section-title">Lisans Planları</div>
    <div class="section-sub">İhtiyacınıza göre bir plan seçin</div>
    <div class="plans" id="plan-listesi">
      <div style="text-align:center;color:var(--muted);grid-column:1/-1;padding:40px;">Planlar yükleniyor...</div>
    </div>
    <div style="text-align:center;margin-top:32px;">
      <button class="btn-hero btn-hero-primary" onclick="sayfaGoster('kayit')">Kayıt Ol ve Talep Gönder →</button>
    </div>
  </div>
</div>

<!-- OFFLİNE AKTİVASYON -->
<div id="sayfa-offline" style="display:none">
  <div style="height:48px;"></div>
  <div class="form-container" style="max-width:520px;">
    <div class="form-card">
      <div class="form-title">🔒 Offline Aktivasyon Talebi</div>
      <div class="form-sub">İnternet bağlantısı olmayan sistemler için lisans talebinde bulunun. Giriş yapmış olmanız gerekir.</div>
      <div class="form-err" id="offline-hata"></div>
      <div class="form-ok" id="offline-ok"></div>
      <div id="offline-giris-uyari" style="display:none;background:#f59e0b15;border:1px solid #f59e0b44;color:#fbbf24;border-radius:8px;padding:12px 16px;font-size:13px;margin-bottom:16px;">
        ⚠️ Offline aktivasyon talebi göndermek için önce <a onclick="sayfaGoster('giris')" style="color:#3d6fff;cursor:pointer;font-weight:600;">giriş yapmalısınız</a>.
      </div>
      <div id="offline-form-icerik">
        <div class="form-group">
          <label class="form-label">Lisans Türü</label>
          <select class="form-input" id="off-tur-sec"><option value="">Yükleniyor...</option></select>
        </div>
        <div class="form-group">
          <label class="form-label">Gateway İstek Kodu (REQ-...)</label>
          <input class="form-input" type="text" id="off-req-kod" placeholder="REQ-XXXXXXXXXXXXXXXXXXXX" style="font-family:monospace;letter-spacing:1px;" oninput="offReqKodKontrol()">
          <div id="off-req-durum" style="font-size:12px;margin-top:4px;"></div>
        </div>
        <div style="background:#3d6fff0a;border:1px solid #3d6fff22;border-radius:8px;padding:12px 14px;font-size:12px;color:#8a9bc0;margin-bottom:16px;line-height:1.7;">
          📌 İstek kodunu almak için <b>OPC Gateway Pro</b> programını açıp <b>Offline Aktivasyon → İstek Kodu Oluştur</b> seçeneğini kullanın.
        </div>
        <button class="form-btn" id="off-talep-btn" onclick="offlineTalepGonder()">Offline Lisans Talebi Gönder</button>
      </div>
    </div>
  </div>
</div>

<!-- KAYIT -->
<div id="sayfa-kayit" style="display:none">
  <div style="height:48px;"></div>
  <div class="form-container">
    <div class="form-card">
      <div class="form-title">Hesap Oluştur</div>
      <div class="form-sub">Zaten hesabınız var mı? <a onclick="sayfaGoster('giris')">Giriş yapın</a></div>
      <div class="form-err" id="kayit-hata"></div>
      <div class="form-ok" id="kayit-ok"></div>
      <div class="form-group">
        <label class="form-label">Ad Soyad</label>
        <input class="form-input" type="text" id="r-ad" placeholder="Adınız Soyadınız">
      </div>
      <div class="form-group">
        <label class="form-label">E-posta</label>
        <input class="form-input" type="email" id="r-email" placeholder="ornek@email.com">
      </div>
      <div class="form-group">
        <label class="form-label">Şifre</label>
        <input class="form-input" type="password" id="r-sifre" placeholder="En az 6 karakter">
      </div>
      <button class="form-btn" onclick="kayitOl()">Hesap Oluştur</button>
      <div class="form-alt">Kayıt olarak <a href="#" style="color:var(--accent)">kullanım koşullarını</a> kabul etmiş olursunuz.</div>
    </div>
  </div>
</div>

<!-- GİRİŞ -->
<div id="sayfa-giris" style="display:none">
  <div style="height:48px;"></div>
  <div class="form-container">
    <div class="form-card">
      <div class="form-title">Giriş Yap</div>
      <div class="form-sub">Hesabınız yok mu? <a onclick="sayfaGoster('kayit')">Kayıt olun</a></div>
      <div class="form-err" id="giris-hata"></div>
      <div class="form-ok" id="giris-ok"></div>
      <div class="form-group">
        <label class="form-label">E-posta</label>
        <input class="form-input" type="email" id="g-email" placeholder="ornek@email.com">
      </div>
      <div class="form-group">
        <label class="form-label">Şifre</label>
        <input class="form-input" type="password" id="g-sifre" placeholder="Şifreniz" onkeydown="if(event.key==='Enter')girisYap()">
      </div>
      <button class="form-btn" onclick="girisYap()">Giriş Yap</button>
      <div class="form-alt">Hesabınız yok mu? <a onclick="sayfaGoster('kayit')">Kayıt olun</a></div>
    </div>
  </div>
</div>

<!-- DASHBOARD -->
<div id="sayfa-dashboard" style="display:none">
  <div class="dashboard">
    <div class="dash-header">
      <div class="dash-title" id="dash-hosgeldin">Hoş Geldiniz</div>
      <button class="nav-btn nav-btn-ghost" onclick="cikisYap()" style="font-size:13px;">Çıkış</button>
    </div>

    <div class="dash-grid" id="dash-grid">
      <!-- JS ile doldurulacak -->
    </div>

    <!-- Lisans Talebi -->
    <div class="dash-card full" id="talep-section">
      <h3>Lisans Talebi</h3>
      <div id="talep-icerik"></div>
    </div>

    <!-- Lisans Geçmişi -->
    <div class="dash-card full" id="gecmis-section">
      <h3 style="display:flex;align-items:center;justify-content:space-between;">
        <span>📋 Lisans Geçmişi</span>
        <button onclick="lisansGecmisiniYukle()" style="background:transparent;border:1px solid var(--border);color:var(--muted);border-radius:6px;padding:4px 12px;font-size:12px;cursor:pointer;">↻ Yenile</button>
      </h3>
      <div id="gecmis-icerik"><div style="color:var(--muted);font-size:13px;">Yükleniyor…</div></div>
    </div>

    <!-- Mesajlar -->
    <div class="dash-card full">
      <h3>Destek / Mesajlar</h3>
      <div class="msg-area" id="msg-area"></div>
      <textarea class="msg-input" id="msg-yaz" placeholder="Mesajınızı yazın… (Ctrl+Enter ile gönder)" onkeydown="if(event.ctrlKey&&event.key==='Enter')mesajGonder()"></textarea>
      <button class="form-btn" style="margin-top:8px;padding:10px;" onclick="mesajGonder()">Gönder</button>
    </div>

    <!-- Şifre Değiştirme -->
    <div style="margin-top:32px; padding-top:16px; border-top:1px solid var(--border); text-align:center;">
      <div style="display:flex; justify-content:center; align-items:center; gap:8px;">
        <input type="password" id="k-yeni-sifre" placeholder="Yeni şifreniz (en az 6 karakter)" style="background:transparent; border:1px solid var(--border); border-radius:6px; padding:6px 12px; font-size:12px; color:var(--text); width:200px;">
        <button onclick="kullaniciSifreDegistir()" style="background:transparent; border:1px solid var(--border); color:var(--muted); padding:6px 12px; border-radius:6px; font-size:12px; cursor:pointer; font-weight:600;">Şifremi Değiştir</button>
      </div>
      <div style="font-size:10px; color:var(--muted); margin-top:6px;">Hesabınızın şifresini eski şifrenizi girmeden hızlıca değiştirebilirsiniz.</div>
    </div>
  </div>
</div>

<!-- İPTAL MODALı -->
<div id="iptal-modal" style="display:none;position:fixed;inset:0;background:rgba(0,0,0,0.75);z-index:500;align-items:center;justify-content:center;backdrop-filter:blur(6px);">
  <div style="background:var(--surface);border:1px solid var(--border);border-radius:16px;padding:32px;width:480px;max-width:95vw;">
    <div style="font-size:18px;font-weight:700;color:#f87171;margin-bottom:6px;">⚠️ Lisansı İptal Et</div>
    <div style="font-size:13px;color:var(--muted);margin-bottom:20px;">Bu işlem geri alınamaz. Lisansınız iptal edildikten sonra programı kullanamazsınız.</div>
    <div style="font-size:13px;font-weight:500;margin-bottom:8px;color:#8a9bc0;">Neden iptal ediyorsunuz?</div>
    <select id="iptal-neden-sec" style="width:100%;background:var(--bg);border:1px solid var(--border);border-radius:8px;padding:10px 14px;color:var(--text);font-size:13px;font-family:'Sora',sans-serif;margin-bottom:8px;">
      <option value="">-- Neden seçin --</option>
      <option value="Artık kullanmıyorum">Artık kullanmıyorum</option>
      <option value="Fiyatı çok yüksek">Fiyatı çok yüksek</option>
      <option value="Başka bir yazılıma geçtim">Başka bir yazılıma geçtim</option>
      <option value="Teknik sorunlar">Teknik sorunlar</option>
      <option value="Geçici iptal">Geçici iptal</option>
      <option value="Diğer">Diğer</option>
    </select>
    <textarea id="iptal-aciklama" style="width:100%;background:var(--bg);border:1px solid var(--border);border-radius:8px;padding:10px 14px;color:var(--text);font-size:13px;font-family:'Sora',sans-serif;min-height:60px;resize:vertical;margin-bottom:16px;" placeholder="Ek açıklama (isteğe bağlı)"></textarea>
    <div id="iptal-hata" style="color:#f87171;font-size:13px;margin-bottom:12px;display:none;"></div>
    <div style="display:flex;gap:10px;">
      <button onclick="lisansImIptalEt()" style="flex:1;background:linear-gradient(135deg,#ef4444,#b91c1c);color:white;border:none;border-radius:8px;padding:12px;font-size:14px;font-weight:700;cursor:pointer;font-family:'Sora',sans-serif;">Evet, İptal Et</button>
      <button onclick="iptalModalKapat()" style="flex:1;background:transparent;color:var(--muted);border:1px solid var(--border);border-radius:8px;padding:12px;font-size:14px;font-weight:600;cursor:pointer;font-family:'Sora',sans-serif;">Vazgeç</button>
    </div>
  </div>
</div>

<script>
let planlar = [];

// ===== SAYFA YÖNETİMİ =====
function sayfaGoster(ad) {
  ["anasayfa","planlar","kayit","giris","dashboard","offline"].forEach(s => {
    document.getElementById("sayfa-" + s).style.display = s === ad ? "" : "none";
  });
  if (ad === "planlar") planlariYukle();
  if (ad === "dashboard") dashboardYukle();
  if (ad === "offline") offlineSayfasiYukle();
}

// ===== PLANLAR =====
async function planlariYukle() {
  const r = await fetch("/api/uyelik-turleri-public");
  planlar = await r.json();
  const el = document.getElementById("plan-listesi");
  if (!planlar.length) { el.innerHTML = '<div style="text-align:center;color:var(--muted);grid-column:1/-1;padding:40px;">Henüz plan eklenmemiş.</div>'; return; }
  el.innerHTML = planlar.map(p => `
    <div class="plan-card" id="plan-${p.kod}" onclick="planSec('${p.kod}')">
      <div class="plan-name">${p.ad}</div>
      <div class="plan-desc">${p.aciklama||""}</div>
    </div>`).join("");
}

var secilenPlan = null;
function planSec(kod) {
  secilenPlan = kod;
  document.querySelectorAll(".plan-card").forEach(c => c.classList.remove("selected"));
  const el = document.getElementById("plan-" + kod);
  if (el) el.classList.add("selected");
}

// ===== KAYIT =====
async function kayitOl() {
  const ad    = document.getElementById("r-ad").value.trim();
  const email = document.getElementById("r-email").value.trim();
  const sifre = document.getElementById("r-sifre").value;
  mesajGizle("kayit-hata"); mesajGizle("kayit-ok");

  if (!ad || !email || !sifre) {
    mesajGoster("kayit-hata", "⚠️ Tüm alanları doldurun.");
    return;
  }

  // Butonu devre dışı bırak
  const btn = document.querySelector("#sayfa-kayit .form-btn");
  if (btn) { btn.disabled = true; btn.textContent = "Kayıt yapılıyor…"; }

  const r = await fetch("/api/kayit", {method:"POST", headers:{"Content-Type":"application/json"},
    body: JSON.stringify({ad_soyad: ad, email, sifre})});
  const d = await r.json();

  if (btn) { btn.disabled = false; btn.textContent = "Hesap Oluştur"; }

  if (r.ok) {
    // Geri sayımlı yönlendirme
    let saniye = 3;
    mesajGoster("kayit-ok", `✅ Kayıt başarılı! Giriş sayfasına yönlendiriliyorsunuz (${saniye})…`);
    const sayac = setInterval(() => {
      saniye--;
      if (saniye <= 0) {
        clearInterval(sayac);
        mesajGizle("kayit-ok");
        sayfaGoster("giris");
      } else {
        mesajGoster("kayit-ok", `✅ Kayıt başarılı! Giriş sayfasına yönlendiriliyorsunuz (${saniye})…`);
      }
    }, 1000);
  } else {
    const hata = d.detail || "Bir hata oluştu.";
    mesajGoster("kayit-hata", "❌ " + hata);
  }
}

// ===== GİRİŞ =====
async function girisYap() {
  const email = document.getElementById("g-email").value.trim();
  const sifre = document.getElementById("g-sifre").value;
  mesajGizle("giris-hata"); mesajGizle("giris-ok");

  if (!email || !sifre) {
    mesajGoster("giris-hata", "⚠️ Lütfen e-posta ve şifrenizi girin.");
    return;
  }

  const btn = document.querySelector("#sayfa-giris .form-btn");
  if (btn) { btn.disabled = true; btn.textContent = "Giriş yapılıyor…"; }

  const r = await fetch("/api/giris", {method:"POST", headers:{"Content-Type":"application/json"},
    body: JSON.stringify({email, sifre})});
  const d = await r.json();

  if (btn) { btn.disabled = false; btn.textContent = "Giriş Yap"; }

  if (r.ok) {
    mesajGoster("giris-ok", "✅ Giriş başarılı! Yönlendiriliyorsunuz…");
    setTimeout(() => {
      mesajGizle("giris-ok");
      sayfaGoster("dashboard");
      baslatSitePoll();
    }, 1200);
  } else {
    // Kullanıcı dostu hata mesajları
    let hata = d.detail || "";
    if (!hata || hata.toLowerCase().includes("e-posta") || hata.toLowerCase().includes("sifre") || hata.toLowerCase().includes("şifre") || r.status === 401) {
      hata = "❌ E-posta adresi veya şifre yanlış. Lütfen tekrar deneyin.";
    } else {
      hata = "❌ " + hata;
    }
    mesajGoster("giris-hata", hata);
    // Yanlış girişte şifre alanını temizle ve odaklan
    document.getElementById("g-sifre").value = "";
    document.getElementById("g-sifre").focus();
  }
}

// ===== ÇIKIŞ & AYARLAR =====
async function kullaniciSifreDegistir() {
  const ys = document.getElementById("k-yeni-sifre").value.trim();
  if (!ys || ys.length < 6) { alert("Şifre en az 6 karakter olmalıdır."); return; }
  if (!confirm("Şifrenizi değiştirmek istediğinize emin misiniz?")) return;
  try {
    const r = await fetch("/api/sifre-degistir", {
      method: "POST", headers: {"Content-Type": "application/json"},
      body: JSON.stringify({yeni_sifre: ys})
    });
    if (r.ok) {
      alert("Şifreniz başarıyla değiştirildi.");
      document.getElementById("k-yeni-sifre").value = "";
    } else {
      const d = await r.json();
      alert("Hata: " + (d.detail || "İşlem başarısız."));
    }
  } catch(e) { alert("Sunucuyla iletişim kurulamadı."); }
}

async function cikisYap() {
  await fetch("/api/cikis", {method:"POST"});
  location.reload();
}

// ===== DASHBOARD =====
function lisansGridRender(p, grid) {
  if (!grid) return;
  const l = p.lisans;
  if (!l) {
    grid.innerHTML = `
      <div class="dash-card full">
        <h3>Lisans Durumu</h3>
        <span class="status-badge status-none">● Lisans Yok</span>
        <div class="dash-sub" style="margin-top:8px;">Aşağıdan lisans talebinde bulunabilirsiniz.</div>
      </div>`;
    return;
  }
  if (l.durum === "aktif") {
    grid.innerHTML = `
      <div class="dash-card">
        <h3>Lisans Durumu</h3>
        <span class="status-badge status-active">● Aktif</span>
        <div class="dash-sub" style="margin-top:8px;">${l.tur}</div>
      </div>
      <div class="dash-card">
        <h3>Kalan Süre</h3>
        <div class="dash-val">${l.kalan_gun != null ? l.kalan_gun + " gün" : "Ömür Boyu"}</div>
        <div class="dash-sub">Bitiş: ${l.bitis}</div>
      </div>
      <div class="dash-card full">
        <h3>Lisans Kodunuz</h3>
        <div class="license-box">
          <div class="license-code">${l.kod}</div>
          <div class="license-sub">Bu kodu program aktivasyonunda kullanın</div>
        </div>
      </div>
      ${(p.indirme_linki && p.vt_hash) ? `
      <div class="dash-card full" style="text-align:center;">
        ${(p.yeni_surum_banner && p.son_guncelleme) ? `
        <div style="margin-bottom:14px;">
          <span style="display:inline-block;background:linear-gradient(90deg,#22d3ee,#38bdf8);color:#fff;padding:8px 20px;border-radius:20px;font-size:14px;font-weight:700;box-shadow:0 4px 12px #38bdf844;letter-spacing:0.5px;border:1px solid #ffffff33;">🚀 YENİ SÜRÜM YAYINDA! (${p.son_guncelleme})</span>
        </div>` : ''}
        <h3>Program İndir</h3>
        <div class="dash-sub" style="margin-bottom:16px;">Lisansınız aktif. Programı indirip lisans kodunuzla aktive edebilirsiniz.</div>
        <a href="${p.indirme_linki}" target="_blank" style="display:inline-flex;align-items:center;gap:10px;background:linear-gradient(135deg,var(--success),#16a34a);color:white;padding:14px 32px;border-radius:10px;font-size:15px;font-weight:700;text-decoration:none;box-shadow:0 0 24px #22c55e33;transition:all 0.2s;">
          ⬇ OPC Gateway'i İndir
        </a>
        <div style="margin-top:18px;">
          <a href="https://www.virustotal.com/gui/file/${p.vt_hash}" target="_blank" style="display:inline-flex;align-items:center;gap:8px;background:linear-gradient(90deg,#22c55e,#16a34a);color:white;padding:10px 22px;border-radius:8px;font-size:14px;font-weight:600;text-decoration:none;box-shadow:0 0 12px #22c55e33;transition:all 0.2s;">
            🛡️ VirusTotal Güvenlik Raporu (0 Virüs)
          </a>
        </div>
      </div>` : ''}
      <div class="dash-card full" style="text-align:center;padding-top:8px;">
        <button onclick="iptalModalAc()" style="background:transparent;border:1px solid #ef444455;color:#f87171;border-radius:8px;padding:9px 20px;font-size:13px;font-weight:600;cursor:pointer;font-family:'Sora',sans-serif;transition:all 0.2s;" onmouseover="this.style.background='#ef444415'" onmouseout="this.style.background='transparent'">
          ⚠️ Lisansı İptal Et
        </button>
      </div>`;
  } else if (l.durum === "suresi_dolmus") {
    grid.innerHTML = `
      <div class="dash-card full">
        <h3>Lisans Durumu</h3>
        <span class="status-badge" style="background:#f59e0b15;color:#fbbf24;border:1px solid #f59e0b33;">● Süresi Dolmuş</span>
        <div class="dash-sub" style="margin-top:8px;">${l.tur} · Bitiş: ${l.bitis}</div>
        <div class="dash-sub" style="margin-top:6px;color:#7eb8ff;">Lisans kodunuz: <strong style="font-family:monospace;">${l.kod}</strong></div>
        <div class="dash-sub" style="margin-top:8px;">Süreniz dolmuş. Yenilemek için aşağıdan yeni bir talep gönderin.</div>
      </div>`;
  } else if (l.durum === "iptal") {
    grid.innerHTML = `
      <div class="dash-card full">
        <h3>Lisans Durumu</h3>
        <span class="status-badge status-none">● İptal Edildi</span>
        <div class="dash-sub" style="margin-top:8px;">${l.tur} · Lisans kodunuz: <strong style="font-family:monospace;">${l.kod}</strong></div>
        ${l.iptal_nedeni ? `<div class="dash-sub" style="margin-top:6px;">Neden: ${l.iptal_nedeni}</div>` : ''}
        <div class="dash-sub" style="margin-top:8px;">Yeni lisans için aşağıdan talep gönderebilirsiniz.</div>
      </div>`;
  }
}

async function dashboardYukle() {
  const r = await fetch("/api/profil");
  if (!r.ok) { sayfaGoster("giris"); return; }
  const p = await r.json();
  document.getElementById("dash-hosgeldin").textContent = "Merhaba, " + p.ad_soyad + " 👋";
  document.getElementById("nav-links").innerHTML = `<span style="font-size:13px;color:var(--muted);margin-right:8px;">${p.email}</span><button class="nav-btn nav-btn-ghost" onclick="cikisYap()">Cıkış</button>`;
  lisansGridRender(p, document.getElementById("dash-grid"));
  taleplerYukle();
  lisansGecmisiniYukle();
  mesajlariYukle();
}

// Dashboard lisans kartını sessizce güncelle
async function lisansKartiGuncelle() {
  const r = await fetch("/api/profil");
  if (!r.ok) return;
  const p = await r.json();
  lisansGridRender(p, document.getElementById("dash-grid"));
}

function iptalModalAc() {
  document.getElementById("iptal-neden-sec").value = "";
  document.getElementById("iptal-aciklama").value = "";
  const hataEl = document.getElementById("iptal-hata");
  if (hataEl) hataEl.style.display = "none";
  document.getElementById("iptal-modal").style.display = "flex";
}

function iptalModalKapat() {
  document.getElementById("iptal-modal").style.display = "none";
}

async function lisansImIptalEt() {
  const sec = document.getElementById("iptal-neden-sec").value;
  const aciklama = document.getElementById("iptal-aciklama").value.trim();
  const hataEl = document.getElementById("iptal-hata");
  if (!sec) {
    hataEl.textContent = "⚠️ Lütfen bir neden seçin.";
    hataEl.style.display = "block";
    return;
  }
  const neden = aciklama ? `${sec} — ${aciklama}` : sec;
  const r = await fetch("/api/lisansimi-iptal-et", {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({neden})
  });
  const d = await r.json();
  if (r.ok) {
    iptalModalKapat();
    lisansKartiGuncelle();
    lisansGecmisiniYukle();
    taleplerYukle();
  } else {
    hataEl.textContent = "❌ " + (d.detail || "Bir hata oluştu.");
    hataEl.style.display = "block";
  }
}

// Global state - poll yenilemesinde offline seçimi ve REQ kodu kaybolmasın
// var dashSecilenPlan = null;
let _dashTalepTipi  = "online";
let _dashReqKodu    = "";


async function taleplerYukle() {

  const r = await fetch("/api/benim-taleplerim");
  const talepler = await r.json();
  const durumBadge = {beklemede:"b-bekl",onaylandi:"b-onay",reddedildi:"b-red"};
  const durumYazi = {beklemede:"Beklemede",onaylandi:"Onaylandı",reddedildi:"Reddedildi"};
  let html = "";
  talepler.forEach(t => {
    let aktGosterim = (t.talep_tipi === 'offline' && t.aktivasyon_kodu) ? `<div style="font-size:11px;margin-top:6px;color:#4ade80;font-family:monospace;background:#22c55e15;padding:6px 10px;border-radius:4px;display:inline-block;border:1px solid #22c55e44;">Aktivasyon Kodunuz:<br>${t.aktivasyon_kodu}</div>` : '';
    html += `<div class="talep-item">
      <div>
        <div style="font-size:14px;font-weight:600;">${t.tur} <span style="font-size:10px;padding:2px 6px;border-radius:4px;background:#3d6fff22;color:#3d6fff;margin-left:6px;border:1px solid #3d6fff44;">${(t.talep_tipi || 'online').toUpperCase()}</span></div>
        <div style="font-size:12px;color:var(--muted);">${t.tarih}${t.admin_notu ? " · " + t.admin_notu : ""}</div>
        ${aktGosterim}
      </div>
      <span class="badge-sm ${durumBadge[t.durum]||""}">${durumYazi[t.durum]||t.durum}</span>
    </div>`;
  });

  // Yeni talep formu (lisans yoksa ve bekleyen talep yoksa)
  const bekleyen = talepler.find(t => t.durum === "beklemede");
  if (!bekleyen) {
    const planlarResp = await fetch("/api/uyelik-turleri-public");
    const planlarData = await planlarResp.json();
    html += `<div style="margin-top:16px;">
      <div style="font-size:13px;color:var(--muted);margin-bottom:12px;">Yeni lisans talep edin:</div>

      <div style="display:flex;gap:0;margin-bottom:16px;background:var(--surface);border-radius:8px;border:1px solid var(--border);overflow:hidden;">
        <label style="flex:1;font-size:13px;display:flex;align-items:center;gap:8px;cursor:pointer;padding:10px 16px;" id="lbl-online">
          <input type="radio" name="talep_tipi" value="online" ${_dashTalepTipi !== 'offline' ? 'checked' : ''} onchange="talepTipiDegisti()">
          <span>🌐</span> <span>Online Lisans</span>
        </label>
        <div style="width:1px;background:var(--border);"></div>
        <label style="flex:1;font-size:13px;display:flex;align-items:center;gap:8px;cursor:pointer;padding:10px 16px;" id="lbl-offline">
          <input type="radio" name="talep_tipi" value="offline" ${_dashTalepTipi === 'offline' ? 'checked' : ''} onchange="talepTipiDegisti()">
          <span>🔒</span> <span>Offline Lisans</span>
        </label>
      </div>

      <div style="display:flex;gap:10px;flex-wrap:wrap;margin-bottom:14px;">
        ${planlarData.map(p => `<div class="plan-card ${dashSecilenPlan === p.kod ? 'selected' : ''}" id="dp-${p.kod}" onclick="dashPlanSec('${p.kod}')" style="padding:12px 16px;min-width:140px;cursor:pointer;">
          <div style="font-size:13px;font-weight:600;">${p.ad}</div>
          <div style="font-size:11px;color:var(--muted);margin-top:3px;">${p.aciklama||""}</div>
        </div>`).join("")}
      </div>

      <div id="offline-istek-alan" style="display:${_dashTalepTipi === 'offline' ? '' : 'none'};margin-bottom:14px;background:#3d6fff08;border:1px solid #3d6fff22;border-radius:8px;padding:14px;">
        <label style="font-size:12px;color:#8a9bc0;display:block;margin-bottom:6px;font-weight:600;">Gateway İstek Kodu</label>
        <input type="text" id="talep-istek-kodu" placeholder="REQ-XXXXXXXXXXXXXXXXXXXX"
          class="form-input" style="font-family:monospace;letter-spacing:1px;max-width:360px;margin-bottom:4px;"
          value="${_dashReqKodu.replace(/"/g, '&quot;')}"
          oninput="_dashReqKodu=this.value;dashReqKodKontrol()">
        <div id="dash-req-durum" style="font-size:12px;min-height:18px;"></div>
        <div style="font-size:11px;color:var(--muted);margin-top:8px;line-height:1.6;">
          📌 İstek kodunu almak için <b>OPC Gateway Pro</b> programını açıp <b>Offline Aktivasyon → İstek Kodu Oluştur</b> seçeneğini kullanın.
        </div>
      </div>

      <button class="form-btn" id="talep-gonder-btn" style="max-width:220px;padding:10px;" onclick="talepGonder()">${_dashTalepTipi === 'offline' ? '🔒 Offline Talep Gönder' : '🌐 Online Talep Gönder'}</button>
      <div class="form-err" id="talep-hata" style="margin-top:10px;"></div>
      <div class="form-ok" id="talep-ok" style="margin-top:10px;"></div>
    </div>`;
  }
  document.getElementById("talep-icerik").innerHTML = html;
  // Re-render sonrası kaydedilen REQ kodunu input'a geri yaz (polling sırasında silinmesin)
  if (_dashTalepTipi === 'offline' && _dashReqKodu) {
    const reqEl = document.getElementById("talep-istek-kodu");
    if (reqEl && reqEl !== document.activeElement) {
      reqEl.value = _dashReqKodu;
    }
    dashReqKodKontrol();
  }
}

function talepTipiDegisti() {
  const tip = document.querySelector('input[name="talep_tipi"]:checked');
  if (!tip) return;
  _dashTalepTipi = tip.value; // Global state'i güncelle
  const alan = document.getElementById("offline-istek-alan");
  const btn  = document.getElementById("talep-gonder-btn");
  if (alan) alan.style.display = tip.value === "offline" ? "" : "none";
  if (btn)  btn.textContent   = tip.value === "offline" ? "🔒 Offline Talep Gönder" : "🌐 Online Talep Gönder";
}

function dashReqKodKontrol() {
  const val = (document.getElementById("talep-istek-kodu").value || "").trim().toUpperCase();
  const el  = document.getElementById("dash-req-durum");
  if (!el) return;
  if (!val) { el.textContent = ""; return; }
  if (!val.startsWith("REQ-") || val.length < 10) {
    el.style.color = "#f87171";
    el.textContent = "⚠️ Geçersiz format — REQ- ile başlamalı ve yeterince uzun olmalıdır.";
  } else {
    el.style.color = "#4ade80";
    el.textContent = "✓ Format geçerli.";
  }
}

var dashSecilenPlan = null;
function dashPlanSec(kod) {
  dashSecilenPlan = kod;
  document.querySelectorAll("[id^='dp-']").forEach(c => c.classList.remove("selected"));
  const el = document.getElementById("dp-" + kod);
  if (el) el.classList.add("selected");
}

// ===== OFFLİNE AKTİVASYON SAYFASI =====
async function offlineSayfasiYukle() {
  // Oturum kontrolü
  const r = await fetch("/api/profil");
  const uyariEl = document.getElementById("offline-giris-uyari");
  const formEl  = document.getElementById("offline-form-icerik");
  if (!r.ok) {
    if (uyariEl) uyariEl.style.display = "";
    if (formEl)  formEl.style.display  = "none";
    return;
  }
  if (uyariEl) uyariEl.style.display = "none";
  if (formEl)  formEl.style.display  = "";
  // Plan listesini doldur
  const pr = await fetch("/api/uyelik-turleri-public");
  const planlarData = await pr.json();
  const sel = document.getElementById("off-tur-sec");
  if (sel) sel.innerHTML = planlarData.map(p => `<option value="${p.kod}">${p.ad} — ${p.aciklama||""}</option>`).join("");
}

function offReqKodKontrol() {
  const val = (document.getElementById("off-req-kod").value || "").trim().toUpperCase();
  const durumEl = document.getElementById("off-req-durum");
  if (!val) { durumEl.textContent = ""; return; }
  if (!val.startsWith("REQ-")) {
    durumEl.style.color = "#f87171";
    durumEl.textContent = "⚠️ Geçersiz format. REQ- ile başlamalıdır.";
  } else {
    durumEl.style.color = "#4ade80";
    durumEl.textContent = "✓ Format geçerli görünüyor.";
  }
}

async function offlineTalepGonder() {
  mesajGizle("offline-hata"); mesajGizle("offline-ok");
  const tur        = document.getElementById("off-tur-sec")  ? document.getElementById("off-tur-sec").value.trim()  : "";
  const istek_kodu = (document.getElementById("off-req-kod").value || "").trim().toUpperCase();
  if (!tur)        { mesajGoster("offline-hata", "⚠️ Lütfen bir lisans türü seçin."); return; }
  if (!istek_kodu) { mesajGoster("offline-hata", "⚠️ İstek kodu zorunludur."); return; }
  if (!istek_kodu.startsWith("REQ-")) { mesajGoster("offline-hata", "❌ Geçersiz istek kodu. REQ- ile başlamalıdır."); return; }
  const btn = document.getElementById("off-talep-btn");
  if (btn) { btn.disabled = true; btn.textContent = "Gönderiliyor…"; }
  const r = await fetch("/api/talep-olustur", {
    method:"POST", headers:{"Content-Type":"application/json"},
    body: JSON.stringify({tur, talep_tipi:"offline", istek_kodu})
  });
  const d = await r.json();
  if (btn) { btn.disabled = false; btn.textContent = "Offline Lisans Talebi Gönder"; }
  if (r.ok) {
    mesajGoster("offline-ok", "✅ Talebiniz alındı! Onaylandığında aktivasyon kodunuz lisans geçmişinizde görünecektir.");
    document.getElementById("off-req-kod").value = "";
    document.getElementById("off-req-durum").textContent = "";
  } else {
    mesajGoster("offline-hata", "❌ " + (d.detail || "Bir hata oluştu."));
  }
}

async function talepGonder() {
  if (!dashSecilenPlan) { mesajGoster("talep-hata", "⚠️ Lütfen bir plan seçin."); return; }
  mesajGizle("talep-hata"); mesajGizle("talep-ok");

  const tipEl      = document.querySelector('input[name="talep_tipi"]:checked');
  const talep_tipi = tipEl ? tipEl.value : "online";
  const istekEl    = document.getElementById("talep-istek-kodu");
  const istek_kodu = istekEl ? istekEl.value.trim().toUpperCase() : _dashReqKodu.trim().toUpperCase();

  if (talep_tipi === "offline") {
    if (!istek_kodu) {
      mesajGoster("talep-hata", "⚠️ Offline lisans için Gateway İstek Kodu zorunludur.");
      return;
    }
    if (!istek_kodu.startsWith("REQ-") || istek_kodu.length < 10) {
      mesajGoster("talep-hata", "❌ Geçersiz istek kodu formatı. REQ- ile başlamalıdır.");
      return;
    }
  }

  const btn = document.getElementById("talep-gonder-btn");
  if (btn) { btn.disabled = true; btn.textContent = "Gönderiliyor…"; }

  const r = await fetch("/api/talep-olustur", {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({tur: dashSecilenPlan, talep_tipi, istek_kodu})
  });
  const d = await r.json();

  if (btn) { btn.disabled = false; btn.textContent = talep_tipi === "offline" ? "🔒 Offline Talep Gönder" : "🌐 Online Talep Gönder"; }

  if (r.ok) {
    mesajGoster("talep-ok", talep_tipi === "offline"
      ? "✅ Offline lisans talebiniz alındı! Onaylandığında lisans geçmişinizde görünecektir."
      : "✅ Talebiniz başarıyla gönderildi!"
    );
    taleplerYukle();
  } else {
    mesajGoster("talep-hata", "❌ " + (d.detail || "Hata oluştu."));
  }
}

async function lisansGecmisiniYukle() {
  const r = await fetch("/api/lisans-gecmisim");
  if (!r.ok) return;
  const liste = await r.json();
  const el = document.getElementById("gecmis-icerik");
  if (!liste.length) {
    el.innerHTML = '<div style="color:var(--muted);font-size:13px;">Henüz lisans kaydı yok.</div>';
    return;
  }
  const durumBilgi = {
    aktif:          { cls: 'b-onay',  yazi: '✓ Aktif' },
    suresi_dolmus:  { cls: 'b-red',   yazi: '✗ Süresi Doldu' },
    iptal:          { cls: 'b-red',   yazi: '✗ İptal Edildi' },
  };
  const turIkon = { aylik: '🗓', yillik: '📅', omur_boyu: '♾', deneme: '🔬' };
  el.innerHTML = `<div style="overflow-x:auto;">
    <table style="width:100%;border-collapse:collapse;font-size:13px;">
      <thead>
        <tr style="color:var(--muted);font-size:11px;text-transform:uppercase;letter-spacing:0.5px;">
          <th style="padding:8px 12px;text-align:left;">Lisans / ACT Kodu</th>
          <th style="padding:8px 12px;text-align:left;">Tür</th>
          <th style="padding:8px 12px;text-align:left;">Tip</th>
          <th style="padding:8px 12px;text-align:left;">İstek Kodu (REQ)</th>
          <th style="padding:8px 12px;text-align:left;">Durum</th>
          <th style="padding:8px 12px;text-align:left;">Oluşturulma</th>
          <th style="padding:8px 12px;text-align:left;">Bitiş</th>
        </tr>
      </thead>
      <tbody>
        ${liste.map(l => {
          const d = durumBilgi[l.durum] || { cls: '', yazi: l.durum };
          const ikon = l.tip === 'offline' ? '🔒' : (turIkon[l.tur] || '🔑');
          const kalanTxt = l.kalan_gun != null ? ` · ${l.kalan_gun} gün kaldı` : '';
          const kodRenk = l.tip === 'offline' ? '#4ade80' : '#7eb8ff';
          const tipBadge = l.tip === 'offline'
            ? `<span style="font-size:10px;padding:2px 6px;border-radius:4px;background:#22c55e15;color:#4ade80;border:1px solid #22c55e44;">🔒 OFFLİNE</span>`
            : `<span style="font-size:10px;padding:2px 6px;border-radius:4px;background:#3d6fff15;color:#7eb8ff;border:1px solid #3d6fff44;">🌐 ONLİNE</span>`;
          const istekKoduCell = l.tip === 'offline' && l.istek_kodu
            ? `<code style="font-family:monospace;font-size:11px;background:var(--bg);padding:2px 6px;border-radius:4px;color:#a78bfa;">${l.istek_kodu}</code>`
            : `<span style="color:var(--muted);">—</span>`;
          return `<tr style="border-top:1px solid var(--border);">
            <td style="padding:10px 12px;"><code style="font-family:monospace;font-size:12px;background:var(--bg);padding:3px 8px;border-radius:4px;color:${kodRenk};">${l.kod}</code></td>
            <td style="padding:10px 12px;">${ikon} ${l.tur.replace('_',' ')}</td>
            <td style="padding:10px 12px;">${tipBadge}</td>
            <td style="padding:10px 12px;">${istekKoduCell}</td>
            <td style="padding:10px 12px;"><span class="badge-sm ${d.cls}" style="white-space:nowrap;">${d.yazi}${kalanTxt}</span></td>
            <td style="padding:10px 12px;color:var(--muted);">${l.olusturma}</td>
            <td style="padding:10px 12px;color:${l.durum==='suresi_dolmus'?'#f87171':'var(--muted)'};">${l.bitis}</td>
          </tr>`;
        }).join('')}
      </tbody>
    </table>
  </div>`;
}

async function mesajlariYukle() {
  const r = await fetch("/api/mesajlarim");
  if (!r.ok) return;
  const mesajlar = await r.json();
  const el = document.getElementById("msg-area");
  if (!el) return;
  // Kullanıcı en alttaysa otomatik kaydır; yazarken konumunu koruma
  const altaYakin = (el.scrollHeight - el.scrollTop) <= (el.clientHeight + 60);
  el.innerHTML = mesajlar.map(m => `
    <div class="msg-wrap ${m.gonderen==='kullanici'?'right':''}">
      <div class="msg-b ${m.gonderen==='kullanici'?'benim':'admin'}">${m.icerik}</div>
      <div class="msg-t">${m.gonderen==='kullanici'?'Siz':'Destek'} · ${m.tarih}</div>
    </div>`).join("");
  if (altaYakin) el.scrollTop = el.scrollHeight;
}

async function mesajGonder() {
  const icerik = document.getElementById("msg-yaz").value.trim();
  if (!icerik) return;
  const r = await fetch("/api/mesaj-gonder", {method:"POST", headers:{"Content-Type":"application/json"},
    body: JSON.stringify({icerik})});
  if (r.ok) {
    document.getElementById("msg-yaz").value = "";
    mesajlariYukle();
  }
}

// ===== YARDIMCI =====
function mesajGoster(id, txt) {
  const el = document.getElementById(id);
  if (el) { el.textContent = txt; el.style.display = "block"; }
}
function mesajGizle(id) {
  const el = document.getElementById(id);
  if (el) el.style.display = "none";
}

function baslatSitePoll() {
  if (_sitePollTimer) return;
  _sitePollTimer = setInterval(async () => {
    const isDash = document.getElementById("sayfa-dashboard") &&
                   document.getElementById("sayfa-dashboard").style.display !== "none";
    if (!isDash) return;
    lisansKartiGuncelle();
    // taleplerYukle() polling'den ÇIKARILDI — form her 2 sn'de yeniden render edilince
    // kullanıcının girdiği REQ kodu siliniyor. Talepler sadece dashboard açılışında
    // ve talep gönderildiğinde yüklenir. Kullanıcı manuel "↻ Yenile" butonu kullanabilir.
    lisansGecmisiniYukle();
    mesajlariYukle();
  }, 2000);
}

// Sayfa yüklenince oturum kontrolü
let _sitePollTimer = null;
(async function() {
  const r = await fetch("/api/profil");
  if (r.ok) {
    sayfaGoster("dashboard");
    const p = await r.json();
    document.getElementById("nav-links").innerHTML = `<span style="font-size:13px;color:var(--muted);margin-right:8px;">${p.email}</span><button class="nav-btn nav-btn-ghost" onclick="sayfaGoster('offline')" style="border-color:#3d6fff44;color:#7eb8ff;">🔒 Offline</button><button class="nav-btn nav-btn-ghost" onclick="cikisYap()">Cıkış</button>`;
    baslatSitePoll();
  }
})();

// ===== ÇEREZ YÖNETİMİ =====
(function() {
  const CEREZ_ANAHTAR = 'cookie_consent';
  const CEREZ_SURE    = 365; // gün

  function cerezOku(ad) {
    const esles = document.cookie.match('(?:^|; )' + ad.replace(/([.$?*|{}()[\]\\/+^])/g, '\\\\$1') + '=([^;]*)');
    return esles ? decodeURIComponent(esles[1]) : null;
  }

  function cerezYaz(ad, deger, gun) {
    const exp = new Date(Date.now() + gun * 864e5).toUTCString();
    document.cookie = `${ad}=${encodeURIComponent(deger)}; expires=${exp}; path=/; SameSite=Lax`;
  }

  function bannerGizle() {
    const b = document.getElementById('cerez-banner');
    b.classList.add('cerez-gizle');
    setTimeout(() => { b.style.display = 'none'; }, 320);
  }

  window.cerezKabulEt = function(tip) {
    // 'reddet': sadece zorunlu çerezler aktif, fonksiyonel kaydedilmez
    // 'zorunlu': zorunlu kabul, fonksiyonel hayır
    // 'tum': hepsi kabul
    const tercih = { zorunlu: true, fonksiyonel: tip === 'tum', verilen: tip, tarih: new Date().toISOString() };
    if (tip !== 'reddet') {
      cerezYaz(CEREZ_ANAHTAR, JSON.stringify(tercih), CEREZ_SURE);
    } else {
      // Reddet: tercih çerezini kaydetme ama banner'ı kapat (session boyunca hatırla)
      sessionStorage.setItem(CEREZ_ANAHTAR, 'reddet');
    }
    bannerGizle();
    cerezModalKapat();
  };

  window.cerezAyarlariAc = function() {
    const mevcut = cerezOku(CEREZ_ANAHTAR);
    if (mevcut) {
      try {
        const t = JSON.parse(mevcut);
        const fonkEl = document.getElementById('cerez-toggle-fonk');
        if (fonkEl) fonkEl.checked = !!t.fonksiyonel;
      } catch(e) {}
    }
    document.getElementById('cerez-modal-overlay').classList.add('aktif');
  };

  window.cerezModalKapat = function() {
    document.getElementById('cerez-modal-overlay').classList.remove('aktif');
  };

  window.cerezAyarlariKaydet = function() {
    const fonk = document.getElementById('cerez-toggle-fonk').checked;
    const tip  = fonk ? 'tum' : 'zorunlu';
    cerezKabulEt(tip);
  };

  // Modal dışına tıklayınca kapat
  document.getElementById('cerez-modal-overlay').addEventListener('click', function(e) {
    if (e.target === this) cerezModalKapat();
  });

  // Banner göster/gizle kontrolü
  const kayitli = cerezOku(CEREZ_ANAHTAR);
  const sessionRed = sessionStorage.getItem(CEREZ_ANAHTAR);
  if (!kayitli && !sessionRed) {
    const banner = document.getElementById('cerez-banner');
    banner.style.display = 'flex';
  }
})();
</script>
</body>
</html>"""

# =====================================================================
# HTML ARAYÜZLERİ (Buralar Kesinlikle Aynı Kalacak)
# =====================================================================

@app.get("/panel", response_class=HTMLResponse)
def panel_html():
    return HTMLResponse(content=PANEL_HTML)

@app.get("/", response_class=HTMLResponse)
def anasayfa():
    html = SITE_HTML_TEMPLATE.replace("{CSS}", SITE_CSS)
    return HTMLResponse(content=html)

@app.get("/kayit", response_class=HTMLResponse)
def kayit_sayfasi():
    return HTMLResponse(content=SITE_HTML_TEMPLATE.replace("{CSS}", SITE_CSS) + "<script>sayfaGoster('kayit');</script>")

@app.get("/giris", response_class=HTMLResponse)
def giris_sayfasi():
    return HTMLResponse(content=SITE_HTML_TEMPLATE.replace("{CSS}", SITE_CSS) + "<script>sayfaGoster('giris');</script>")

@app.get("/dashboard", response_class=HTMLResponse)
def dashboard_sayfasi():
    return HTMLResponse(content=SITE_HTML_TEMPLATE.replace("{CSS}", SITE_CSS) + "<script>sayfaGoster('dashboard');</script>")

@app.get("/planlar", response_class=HTMLResponse)
def planlar_sayfasi():
    return HTMLResponse(content=SITE_HTML_TEMPLATE.replace("{CSS}", SITE_CSS) + "<script>sayfaGoster('planlar');</script>")

@app.get("/offline-aktivasyon", response_class=HTMLResponse)
def offline_aktivasyon_sayfasi():
    return HTMLResponse(content=SITE_HTML_TEMPLATE.replace("{CSS}", SITE_CSS) + "<script>sayfaGoster('offline');</script>")

@app.post("/api/sifre-degistir")
async def sifre_degistir(request: Request, s: Session = Depends(db)):
    kid = get_kullanici_id(request)
    if not kid: raise HTTPException(status_code=401, detail="Giriş yapmalısınız.")
    data = await request.json()
    yeni_sifre = data.get("yeni_sifre", "").strip()
    if not yeni_sifre or len(yeni_sifre) < 6:
        raise HTTPException(status_code=400, detail="Şifre en az 6 karakter olmalıdır.")
    k = s.query(Kullanici).filter_by(id=kid).first()
    if not k: raise HTTPException(status_code=401)
    k.sifre_hash = sifre_hashle(yeni_sifre)
    s.commit()
    return {"basarili": True, "mesaj": "Şifre başarıyla güncellendi."}