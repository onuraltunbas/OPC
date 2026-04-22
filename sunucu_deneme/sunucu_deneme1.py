# -*- coding: utf-8 -*-
"""
OPC Gateway — Lisans Doğrulama Sunucusu v5.0
FastAPI + SQLite | Railway deploy

Yeni özellikler:
  - Kullanıcı kayıt/giriş sitesi (mail doğrulama)
  - Lisans talep sistemi
  - Mesajlaşma sistemi (kullanıcı <-> admin)
  - IP ban sistemi
  - Otomatik teşekkür maili (lisans eklenince)
  - Panel: kullanıcı adı + şifre ile giriş

Kurulum:
  pip install fastapi uvicorn sqlalchemy python-jose passlib bcrypt python-multipart aiosmtplib jinja2 email-validator

Railway Procfile:
  web: uvicorn lisans_sunucu:app --host 0.0.0.0 --port $PORT
"""

import os
import uuid
import secrets
import datetime
from typing import Optional, List
from functools import wraps

from fastapi import FastAPI, HTTPException, Header, Depends, Request, Form, Response
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
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
SECRET_KEY      = os.getenv("SECRET_KEY", "BURAYA-GIZLI-ANAHTARINIZI-YAZIN")
PANEL_KULLANICI = os.getenv("PANEL_KULLANICI", "admin")          # Panel kullanıcı adı
PANEL_SIFRE     = os.getenv("PANEL_SIFRE", "admin123")           # Panel şifresi
DATABASE_URL    = os.getenv("DATABASE_URL", "sqlite:///./lisanslar.db")

# İndirme linki (Railway env var)
INDIRME_LINKI   = os.getenv("INDIRME_LINKI", "https://your-download-link.com")

# =====================================================================
# VERİTABANI
# =====================================================================
# SQLite için check_same_thread=False gerekli; PostgreSQL'de bu arg kullanılmaz
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
    """Kayıt sitesi kullanıcıları"""
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
    """Kullanıcıların lisans talepleri"""
    __tablename__ = "lisans_talepler"
    id          = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    kullanici_id = Column(String, nullable=False)
    ad_soyad    = Column(String, nullable=False)
    email       = Column(String, nullable=False)
    tur         = Column(String, nullable=False)   # aylik, yillik, omur_boyu, deneme
    durum       = Column(String, default="beklemede")  # beklemede, onaylandi, reddedildi
    talep_tar   = Column(DateTime, default=datetime.datetime.utcnow)
    islem_tar   = Column(DateTime, nullable=True)
    ip_adresi   = Column(String, nullable=True)
    admin_notu  = Column(Text, nullable=True)


class Mesaj(Base):
    """Kullanıcı <-> Admin mesajlaşma"""
    __tablename__ = "mesajlar"
    id           = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    kullanici_id = Column(String, nullable=False)
    gonderen     = Column(String, nullable=False)  # "kullanici" veya "admin"
    icerik       = Column(Text, nullable=False)
    tarih        = Column(DateTime, default=datetime.datetime.utcnow)
    okundu       = Column(Boolean, default=False)


class IpBan(Base):
    """IP ban listesi"""
    __tablename__ = "ip_banlar"
    id        = Column(Integer, primary_key=True, autoincrement=True)
    ip        = Column(String, unique=True, nullable=False, index=True)
    sebep     = Column(Text, nullable=True)
    tarih     = Column(DateTime, default=datetime.datetime.utcnow)
    aktif     = Column(Boolean, default=True)


class UyelikTuru(Base):
    """Yönetilebilir üyelik türleri"""
    __tablename__ = "uyelik_turleri"
    id          = Column(Integer, primary_key=True, autoincrement=True)
    kod         = Column(String, unique=True, nullable=False)   # aylik, yillik, vb
    ad          = Column(String, nullable=False)                 # Görünen ad
    aciklama    = Column(Text, nullable=True)
    aktif       = Column(Boolean, default=True)
    sira        = Column(Integer, default=0)


Base.metadata.create_all(engine)


# Varsayılan üyelik türlerini ekle
def varsayilan_turleri_ekle():
    s = Session_()
    try:
        if s.query(UyelikTuru).count() == 0:
            turler = [
                UyelikTuru(kod="aylik",     ad="Aylık Lisans",    aciklama="30 gün geçerli",    sira=1),
                UyelikTuru(kod="yillik",    ad="Yıllık Lisans",   aciklama="365 gün geçerli",   sira=2),
                UyelikTuru(kod="omur_boyu", ad="Ömür Boyu Lisans",aciklama="Süresiz geçerli",   sira=3),
                UyelikTuru(kod="deneme",    ad="Deneme Sürümü",   aciklama="24 saat ücretsiz deneme", sira=4),
            ]
            for t in turler:
                s.add(t)
            s.commit()
    finally:
        s.close()

varsayilan_turleri_ekle()


def db():
    s = Session_()
    try:
        yield s
    finally:
        s.close()


# =====================================================================
# YARDIMCI FONKSİYONLAR
# =====================================================================
def sifre_hashle(sifre: str) -> str:
    return hashlib.sha256(sifre.encode()).hexdigest()


def lisans_kodu_uret(tur_prefix="STD"):
    parca = secrets.token_hex(6).upper()
    return f"{tur_prefix}-{parca[:4]}-{parca[4:8]}-{parca[8:12]}"


def bitis_tarihi_hesapla(tur: str, saat: Optional[int] = None) -> Optional[datetime.datetime]:
    simdi = datetime.datetime.utcnow()
    if tur == "aylik":
        return simdi + datetime.timedelta(days=30)
    elif tur == "yillik":
        return simdi + datetime.timedelta(days=365)
    elif tur == "deneme":
        return simdi + datetime.timedelta(hours=saat or 24)
    elif tur == "omur_boyu":
        return None
    return None


def log_yaz(s: Session, islem, lisans_kodu, hwid, ip, mesaj):
    s.add(Log(islem=islem, lisans_kodu=lisans_kodu, hwid=hwid, ip=ip, mesaj=mesaj))
    s.commit()


def ip_banlimi(s: Session, ip: str) -> bool:
    ban = s.query(IpBan).filter_by(ip=ip, aktif=True).first()
    return ban is not None


# Mail gönderimi devre dışı bırakıldı.


# =====================================================================
# SESSION YÖNETİMİ (Basit token tabanlı)
# =====================================================================
# In-memory session store (Railway'de tek instance olduğu için yeterli)
_sessions = {}  # token -> kullanici_id

def session_olustur(kullanici_id: str) -> str:
    token = secrets.token_urlsafe(32)
    _sessions[token] = {"kullanici_id": kullanici_id, "tarih": datetime.datetime.utcnow()}
    return token

def session_dogrula(token: str) -> Optional[str]:
    if not token:
        return None
    s = _sessions.get(token)
    if not s:
        return None
    # 7 gün geçerli
    if (datetime.datetime.utcnow() - s["tarih"]).days > 7:
        del _sessions[token]
        return None
    return s["kullanici_id"]

def session_sil(token: str):
    _sessions.pop(token, None)

def get_kullanici_id(request: Request) -> Optional[str]:
    token = request.cookies.get("session")
    return session_dogrula(token) if token else None


# =====================================================================
# FASTAPI UYGULAMASI
# =====================================================================
app = FastAPI(title="OPC Gateway", docs_url=None, redoc_url=None)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["POST", "GET", "DELETE", "PUT"],
    allow_headers=["*"],
)


def app_sirri_dogrula(request: Request):
    gelen = request.headers.get("x-app-secret") or request.headers.get("x_app_secret") or ""
    if gelen != SECRET_KEY:
        raise HTTPException(status_code=403, detail="Yetkisiz erisim.")


def panel_dogrula(request: Request):
    auth = request.headers.get("authorization") or request.headers.get("Authorization") or ""
    # Format: "Basic base64(kullanici:sifre)" veya "Bearer kullanici:sifre"
    if auth.startswith("Bearer "):
        token = auth[7:]
        parts = token.split(":", 1)
        if len(parts) == 2 and parts[0] == PANEL_KULLANICI and parts[1] == PANEL_SIFRE:
            return
    raise HTTPException(status_code=401, detail="Panel kullanici adi veya sifresi yanlis.")


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
    ip  = request.client.host
    # IP ban kontrolü
    if ip_banlimi(s, ip):
        raise HTTPException(status_code=403, detail="Bu IP adresi yasaklanmıştır.")
    kod  = istek.lisans_kodu.strip().upper()
    hwid = istek.hwid.strip()

    lisans = s.query(Lisans).filter_by(lisans_kodu=kod).first()
    if not lisans:
        log_yaz(s, "red", kod, hwid, ip, "Lisans kodu bulunamadi")
        raise HTTPException(status_code=404, detail="Lisans kodu bulunamadı.")
    if not lisans.aktif:
        log_yaz(s, "red", kod, hwid, ip, "Lisans deaktif")
        raise HTTPException(status_code=403, detail="Bu lisans iptal edilmiştir.")
    if lisans.bitis_tarihi and datetime.datetime.utcnow() > lisans.bitis_tarihi:
        log_yaz(s, "red", kod, hwid, ip, "Lisans suresi dolmus")
        raise HTTPException(status_code=403, detail="Lisans süresi dolmuştur.")
    if lisans.hwid and lisans.hwid != hwid:
        log_yaz(s, "red", kod, hwid, ip, f"HWID uyusmuyor: kayitli={lisans.hwid}")
        raise HTTPException(status_code=403, detail="Bu lisans başka bir bilgisayara kayıtlıdır.")
    if not lisans.hwid:
        lisans.hwid = hwid
        lisans.aktivasyon_tar = datetime.datetime.utcnow()
    lisans.son_checkin = datetime.datetime.utcnow()
    s.commit()
    log_yaz(s, "aktivasyon", kod, hwid, ip, "Basarili aktivasyon")
    return {
        "basarili": True,
        "mesaj": f"Hoş geldiniz, {lisans.musteri_adi}!",
        "tur": lisans.tur,
        "musteri_adi": lisans.musteri_adi,
        "bitis_tarihi": lisans.bitis_tarihi.isoformat() if lisans.bitis_tarihi else None,
    }


@app.post("/api/kontrol", dependencies=[Depends(app_sirri_dogrula)])
def kontrol(istek: KontrolIstek, request: Request, s: Session = Depends(db)):
    ip   = request.client.host
    if ip_banlimi(s, ip):
        return {"gecerli": False, "mesaj": "Bu IP adresi yasaklanmıştır."}
    kod  = istek.lisans_kodu.strip().upper()
    hwid = istek.hwid.strip()
    lisans = s.query(Lisans).filter_by(lisans_kodu=kod).first()
    if not lisans or not lisans.aktif:
        log_yaz(s, "red", kod, hwid, ip, "Kontrol: lisans yok veya deaktif")
        return {"gecerli": False, "mesaj": "Lisans geçersiz veya iptal edilmiş."}
    if lisans.hwid != hwid:
        log_yaz(s, "red", kod, hwid, ip, "Kontrol: HWID uyusmuyor")
        return {"gecerli": False, "mesaj": "HWID uyuşmazlığı."}
    if lisans.bitis_tarihi and datetime.datetime.utcnow() > lisans.bitis_tarihi:
        log_yaz(s, "red", kod, hwid, ip, "Kontrol: sure dolmus")
        return {"gecerli": False, "mesaj": "Lisans süresi dolmuştur."}
    lisans.son_checkin = datetime.datetime.utcnow()
    s.commit()
    log_yaz(s, "kontrol", kod, hwid, ip, "Periyodik kontrol OK")
    return {
        "gecerli": True,
        "tur": lisans.tur,
        "musteri_adi": lisans.musteri_adi,
        "bitis_tarihi": lisans.bitis_tarihi.isoformat() if lisans.bitis_tarihi else None,
    }


# =====================================================================
# KULLANICI KAYIT/GİRİŞ API
# =====================================================================

@app.post("/api/kayit")
async def kayit_ol(request: Request, s: Session = Depends(db)):
    data = await request.json()
    ad_soyad = data.get("ad_soyad", "").strip()
    email    = data.get("email", "").strip().lower()
    sifre    = data.get("sifre", "")

    if not ad_soyad or not email or not sifre:
        raise HTTPException(status_code=400, detail="Tüm alanlar zorunludur.")
    if len(sifre) < 6:
        raise HTTPException(status_code=400, detail="Şifre en az 6 karakter olmalıdır.")
    if s.query(Kullanici).filter_by(email=email).first():
        raise HTTPException(status_code=409, detail="Bu e-posta zaten kayıtlı.")

    k = Kullanici(
        ad_soyad=ad_soyad,
        email=email,
        sifre_hash=sifre_hashle(sifre),
        email_dogrulandi=True,  # Doğrulama adımı kaldırıldı
        son_ip=request.client.host,
    )
    s.add(k)
    s.commit()
    return {"basarili": True, "mesaj": "Kayıt başarılı! Giriş yapabilirsiniz."}


@app.get("/dogrula")
def email_dogrula(kod: str, s: Session = Depends(db)):
    k = s.query(Kullanici).filter_by(dogrulama_kodu=kod).first()
    if not k:
        return HTMLResponse("<h2>Geçersiz veya kullanılmış doğrulama linki.</h2>")
    k.email_dogrulandi = True
    k.dogrulama_kodu = None
    s.commit()
    return RedirectResponse(url="/giris?dogrulandi=1")


@app.post("/api/giris")
async def giris_yap(request: Request, response: Response, s: Session = Depends(db)):
    data = await request.json()
    email = data.get("email", "").strip().lower()
    sifre = data.get("sifre", "")
    k = s.query(Kullanici).filter_by(email=email, sifre_hash=sifre_hashle(sifre)).first()
    if not k:
        raise HTTPException(status_code=401, detail="E-posta veya şifre yanlış.")
    # E-posta doğrulama kontrolü kaldırıldı
    k.son_giris = datetime.datetime.utcnow()
    k.son_ip = request.client.host
    s.commit()
    token = session_olustur(k.id)
    resp = JSONResponse({"basarili": True})
    resp.set_cookie("session", token, httponly=True, max_age=604800, samesite="lax")
    return resp


@app.post("/api/cikis")
def cikis_yap(request: Request, response: Response):
    token = request.cookies.get("session")
    if token:
        session_sil(token)
    resp = JSONResponse({"basarili": True})
    resp.delete_cookie("session")
    return resp


@app.post("/api/talep-olustur")
async def talep_olustur(request: Request, s: Session = Depends(db)):
    kullanici_id = get_kullanici_id(request)
    if not kullanici_id:
        raise HTTPException(status_code=401, detail="Giriş yapmanız gerekiyor.")
    data = await request.json()
    tur = data.get("tur", "")
    gecerli_turler = {t.kod for t in s.query(UyelikTuru).filter_by(aktif=True).all()}
    if tur not in gecerli_turler:
        raise HTTPException(status_code=400, detail="Geçersiz üyelik türü.")
    k = s.query(Kullanici).filter_by(id=kullanici_id).first()
    # Beklemedeki talep kontrolü
    mevcut = s.query(LisansTalep).filter_by(kullanici_id=kullanici_id, durum="beklemede").first()
    if mevcut:
        raise HTTPException(status_code=409, detail="Zaten beklemedeki bir talebiniz var.")
    talep = LisansTalep(
        kullanici_id=kullanici_id,
        ad_soyad=k.ad_soyad,
        email=k.email,
        tur=tur,
        ip_adresi=k.son_ip,
    )
    s.add(talep)
    s.commit()
    return {"basarili": True, "mesaj": "Talebiniz alındı. En kısa sürede işleme alınacak."}


@app.get("/api/benim-taleplerim")
def benim_taleplerim(request: Request, s: Session = Depends(db)):
    kullanici_id = get_kullanici_id(request)
    if not kullanici_id:
        raise HTTPException(status_code=401, detail="Giriş gerekli.")
    talepler = s.query(LisansTalep).filter_by(kullanici_id=kullanici_id).order_by(LisansTalep.talep_tar.desc()).all()
    return [{"id": t.id, "tur": t.tur, "durum": t.durum, "tarih": t.talep_tar.strftime("%d.%m.%Y %H:%M"), "admin_notu": t.admin_notu} for t in talepler]


@app.post("/api/mesaj-gonder")
async def mesaj_gonder(request: Request, s: Session = Depends(db)):
    kullanici_id = get_kullanici_id(request)
    if not kullanici_id:
        raise HTTPException(status_code=401, detail="Giriş gerekli.")
    data = await request.json()
    icerik = data.get("icerik", "").strip()
    if not icerik:
        raise HTTPException(status_code=400, detail="Mesaj boş olamaz.")
    m = Mesaj(kullanici_id=kullanici_id, gonderen="kullanici", icerik=icerik)
    s.add(m)
    s.commit()
    return {"basarili": True}


@app.get("/api/mesajlarim")
def mesajlarim(request: Request, s: Session = Depends(db)):
    kullanici_id = get_kullanici_id(request)
    if not kullanici_id:
        raise HTTPException(status_code=401, detail="Giriş gerekli.")
    # Okunmamış admin mesajlarını okundu yap
    s.query(Mesaj).filter_by(kullanici_id=kullanici_id, gonderen="admin", okundu=False).update({"okundu": True})
    s.commit()
    mesajlar = s.query(Mesaj).filter_by(kullanici_id=kullanici_id).order_by(Mesaj.tarih.asc()).all()
    return [{"gonderen": m.gonderen, "icerik": m.icerik, "tarih": m.tarih.strftime("%d.%m.%Y %H:%M")} for m in mesajlar]


@app.get("/api/profil")
def profil(request: Request, s: Session = Depends(db)):
    kullanici_id = get_kullanici_id(request)
    if not kullanici_id:
        raise HTTPException(status_code=401, detail="Giriş gerekli.")
    k = s.query(Kullanici).filter_by(id=kullanici_id).first()
    # Aktif lisans var mı?
    lisans = s.query(Lisans).filter_by(musteri_email=k.email, aktif=True).order_by(Lisans.olusturma_tar.desc()).first()
    lisans_bilgi = None
    if lisans:
        kalan = None
        if lisans.bitis_tarihi:
            kalan = max(0, (lisans.bitis_tarihi - datetime.datetime.utcnow()).days)
        lisans_bilgi = {
            "kod": lisans.lisans_kodu,
            "tur": lisans.tur,
            "bitis": lisans.bitis_tarihi.strftime("%d.%m.%Y") if lisans.bitis_tarihi else "Ömür Boyu",
            "kalan_gun": kalan,
            "aktif": lisans.aktif,
        }
    okunmamis = s.query(Mesaj).filter_by(kullanici_id=kullanici_id, gonderen="admin", okundu=False).count()
    return {
        "ad_soyad": k.ad_soyad,
        "email": k.email,
        "kayit_tar": k.kayit_tar.strftime("%d.%m.%Y"),
        "lisans": lisans_bilgi,
        "okunmamis_mesaj": okunmamis,
        "indirme_linki": INDIRME_LINKI if lisans_bilgi else None,
    }


@app.get("/api/uyelik-turleri-public")
def uyelik_turleri_public(s: Session = Depends(db)):
    turler = s.query(UyelikTuru).filter_by(aktif=True).order_by(UyelikTuru.sira).all()
    return [{"kod": t.kod, "ad": t.ad, "aciklama": t.aciklama} for t in turler]


# =====================================================================
# PANEL API (Admin)
# =====================================================================

class LisansOlusturIstek(BaseModel):
    musteri_adi:   str
    musteri_email: Optional[str] = None
    tur:           str
    deneme_saat:   Optional[int] = 24
    notlar:        Optional[str] = None


@app.post("/panel/lisans-olustur", dependencies=[Depends(panel_dogrula)])
def lisans_olustur(istek: LisansOlusturIstek, s: Session = Depends(db)):
    turler = {"aylik", "yillik", "omur_boyu", "deneme"}
    if istek.tur not in turler:
        raise HTTPException(status_code=400, detail=f"Geçersiz tür.")
    prefix_map = {"aylik": "AYL", "yillik": "YIL", "omur_boyu": "OBY", "deneme": "DEN"}
    kod   = lisans_kodu_uret(prefix_map[istek.tur])
    bitis = bitis_tarihi_hesapla(istek.tur, istek.deneme_saat)
    yeni  = Lisans(
        lisans_kodu=kod,
        musteri_adi=istek.musteri_adi,
        musteri_email=istek.musteri_email,
        tur=istek.tur,
        bitis_tarihi=bitis,
        notlar=istek.notlar,
    )
    s.add(yeni)
    s.commit()
    return {
        "lisans_kodu": kod,
        "musteri_adi": istek.musteri_adi,
        "tur": istek.tur,
        "bitis_tarihi": bitis.isoformat() if bitis else "Ömür boyu",
        "mesaj": f"Lisans oluşturuldu: {kod}"
    }


@app.get("/panel/lisanslar", dependencies=[Depends(panel_dogrula)])
def lisanslar_listele(s: Session = Depends(db)):
    liste = s.query(Lisans).order_by(Lisans.olusturma_tar.desc()).all()
    return [
        {
            "lisans_kodu":   l.lisans_kodu,
            "musteri_adi":   l.musteri_adi,
            "musteri_email": l.musteri_email,
            "tur":           l.tur,
            "aktif":         l.aktif,
            "hwid":          l.hwid or "Henüz aktive edilmedi",
            "bitis_tarihi":  l.bitis_tarihi.strftime("%d.%m.%Y %H:%M") if l.bitis_tarihi else "Ömür boyu",
            "son_checkin":   l.son_checkin.strftime("%d.%m.%Y %H:%M") if l.son_checkin else "Hiç",
            "aktivasyon":    l.aktivasyon_tar.strftime("%d.%m.%Y %H:%M") if l.aktivasyon_tar else "Henüz yok",
            "notlar":        l.notlar or "",
        }
        for l in liste
    ]


@app.post("/panel/iptal", dependencies=[Depends(panel_dogrula)])
def iptal_et(lisans_kodu: str, s: Session = Depends(db)):
    lisans = s.query(Lisans).filter_by(lisans_kodu=lisans_kodu.upper()).first()
    if not lisans:
        raise HTTPException(status_code=404, detail="Lisans bulunamadı.")
    lisans.aktif = False
    s.commit()
    return {"mesaj": f"{lisans_kodu} lisansı iptal edildi."}


@app.post("/panel/hwid-sifirla", dependencies=[Depends(panel_dogrula)])
def hwid_sifirla(lisans_kodu: str, s: Session = Depends(db)):
    lisans = s.query(Lisans).filter_by(lisans_kodu=lisans_kodu.upper()).first()
    if not lisans:
        raise HTTPException(status_code=404, detail="Lisans bulunamadı.")
    lisans.hwid = None
    lisans.aktivasyon_tar = None
    s.commit()
    return {"mesaj": f"{lisans_kodu} için HWID sıfırlandı."}


@app.post("/panel/sure-uzat", dependencies=[Depends(panel_dogrula)])
def sure_uzat(lisans_kodu: str, gun: int, s: Session = Depends(db)):
    lisans = s.query(Lisans).filter_by(lisans_kodu=lisans_kodu.upper()).first()
    if not lisans:
        raise HTTPException(status_code=404, detail="Lisans bulunamadı.")
    if not lisans.bitis_tarihi:
        raise HTTPException(status_code=400, detail="Ömür boyu lisansa süre eklenemez.")
    baz = max(lisans.bitis_tarihi, datetime.datetime.utcnow())
    lisans.bitis_tarihi = baz + datetime.timedelta(days=gun)
    lisans.aktif = True
    s.commit()
    return {"mesaj": f"{gun} gün eklendi.", "yeni_bitis": lisans.bitis_tarihi.strftime("%d.%m.%Y %H:%M")}


@app.get("/panel/loglar", dependencies=[Depends(panel_dogrula)])
def loglar(son: int = 100, s: Session = Depends(db)):
    logs = s.query(Log).order_by(Log.tarih.desc()).limit(son).all()
    return [{"tarih": l.tarih.strftime("%d.%m.%Y %H:%M:%S"), "islem": l.islem, "lisans_kodu": l.lisans_kodu, "hwid": l.hwid, "ip": l.ip, "mesaj": l.mesaj} for l in logs]


# Panel: Talepler
@app.get("/panel/talepler", dependencies=[Depends(panel_dogrula)])
def panel_talepler(s: Session = Depends(db)):
    talepler = s.query(LisansTalep).order_by(LisansTalep.talep_tar.desc()).all()
    return [
        {
            "id": t.id, "kullanici_id": t.kullanici_id,
            "ad_soyad": t.ad_soyad, "email": t.email,
            "tur": t.tur, "durum": t.durum,
            "tarih": t.talep_tar.strftime("%d.%m.%Y %H:%M"),
            "ip": t.ip_adresi, "admin_notu": t.admin_notu or "",
        }
        for t in talepler
    ]


@app.post("/panel/talep-guncelle", dependencies=[Depends(panel_dogrula)])
async def talep_guncelle(request: Request, s: Session = Depends(db)):
    data = await request.json()
    talep = s.query(LisansTalep).filter_by(id=data["talep_id"]).first()
    if not talep:
        raise HTTPException(status_code=404, detail="Talep bulunamadı.")
    talep.durum = data["durum"]  # onaylandi / reddedildi
    talep.islem_tar = datetime.datetime.utcnow()
    if data.get("admin_notu"):
        talep.admin_notu = data["admin_notu"]
    s.commit()

    k = s.query(Kullanici).filter_by(id=talep.kullanici_id).first()

    # Onay durumunda otomatik lisans oluştur
    if data["durum"] == "onaylandi":
        prefix_map = {"aylik": "AYL", "yillik": "YIL", "omur_boyu": "OBY", "deneme": "DEN"}
        prefix = prefix_map.get(talep.tur, "STD")
        kod = lisans_kodu_uret(prefix)
        bitis = bitis_tarihi_hesapla(talep.tur)
        yeni_lisans = Lisans(
            lisans_kodu=kod,
            musteri_adi=talep.ad_soyad,
            musteri_email=talep.email,
            tur=talep.tur,
            bitis_tarihi=bitis,
            notlar=data.get("admin_notu") or None,
        )
        s.add(yeni_lisans)
        s.commit()
    return {"basarili": True}


# Panel: Mesajlar
@app.get("/panel/mesajlar-ozet", dependencies=[Depends(panel_dogrula)])
def panel_mesajlar_ozet(s: Session = Depends(db)):
    """Her kullanıcı için son mesaj ve okunmamış sayısı"""
    kullanicilar = s.query(Kullanici).all()
    sonuc = []
    for k in kullanicilar:
        toplam = s.query(Mesaj).filter_by(kullanici_id=k.id).count()
        if toplam == 0:
            continue
        okunmamis = s.query(Mesaj).filter_by(kullanici_id=k.id, gonderen="kullanici", okundu=False).count()
        son_mesaj = s.query(Mesaj).filter_by(kullanici_id=k.id).order_by(Mesaj.tarih.desc()).first()
        # Kullanıcının lisans bilgisi
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


@app.get("/panel/kullanici-mesajlar/{kullanici_id}", dependencies=[Depends(panel_dogrula)])
def kullanici_mesajlari(kullanici_id: str, s: Session = Depends(db)):
    # Okunmamış kullanıcı mesajlarını okundu yap
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


@app.post("/panel/admin-mesaj-gonder", dependencies=[Depends(panel_dogrula)])
async def admin_mesaj_gonder(request: Request, s: Session = Depends(db)):
    data = await request.json()
    kullanici_id = data.get("kullanici_id")
    icerik = data.get("icerik", "").strip()
    if not kullanici_id or not icerik:
        raise HTTPException(status_code=400, detail="Eksik veri.")
    m = Mesaj(kullanici_id=kullanici_id, gonderen="admin", icerik=icerik, okundu=False)
    s.add(m)
    s.commit()
    return {"basarili": True}


# Panel: IP Ban
@app.get("/panel/ip-banlar", dependencies=[Depends(panel_dogrula)])
def ip_banlar(s: Session = Depends(db)):
    banlar = s.query(IpBan).order_by(IpBan.tarih.desc()).all()
    return [{"id": b.id, "ip": b.ip, "sebep": b.sebep or "", "tarih": b.tarih.strftime("%d.%m.%Y %H:%M"), "aktif": b.aktif} for b in banlar]


@app.post("/panel/ip-ban-ekle", dependencies=[Depends(panel_dogrula)])
async def ip_ban_ekle(request: Request, s: Session = Depends(db)):
    data = await request.json()
    ip    = data.get("ip", "").strip()
    sebep = data.get("sebep", "")
    if not ip:
        raise HTTPException(status_code=400, detail="IP zorunlu.")
    mevcut = s.query(IpBan).filter_by(ip=ip).first()
    if mevcut:
        mevcut.aktif = True
        mevcut.sebep = sebep
        s.commit()
        return {"mesaj": f"{ip} tekrar banlandı."}
    s.add(IpBan(ip=ip, sebep=sebep))
    s.commit()
    return {"mesaj": f"{ip} banlandı."}


@app.post("/panel/ip-ban-kaldir", dependencies=[Depends(panel_dogrula)])
async def ip_ban_kaldir(request: Request, s: Session = Depends(db)):
    data = await request.json()
    ip = data.get("ip", "").strip()
    ban = s.query(IpBan).filter_by(ip=ip).first()
    if not ban:
        raise HTTPException(status_code=404, detail="Ban bulunamadı.")
    ban.aktif = False
    s.commit()
    return {"mesaj": f"{ip} banı kaldırıldı."}


# Panel: Üyelik türleri yönetimi
@app.get("/panel/uyelik-turleri", dependencies=[Depends(panel_dogrula)])
def panel_uyelik_turleri(s: Session = Depends(db)):
    turler = s.query(UyelikTuru).order_by(UyelikTuru.sira).all()
    return [{"id": t.id, "kod": t.kod, "ad": t.ad, "aciklama": t.aciklama, "aktif": t.aktif, "sira": t.sira} for t in turler]


@app.post("/panel/uyelik-tur-ekle", dependencies=[Depends(panel_dogrula)])
async def uyelik_tur_ekle(request: Request, s: Session = Depends(db)):
    data = await request.json()
    if s.query(UyelikTuru).filter_by(kod=data["kod"]).first():
        raise HTTPException(status_code=409, detail="Bu kod zaten mevcut.")
    t = UyelikTuru(kod=data["kod"], ad=data["ad"], aciklama=data.get("aciklama", ""), sira=data.get("sira", 99))
    s.add(t)
    s.commit()
    return {"basarili": True}


@app.post("/panel/uyelik-tur-guncelle", dependencies=[Depends(panel_dogrula)])
async def uyelik_tur_guncelle(request: Request, s: Session = Depends(db)):
    data = await request.json()
    t = s.query(UyelikTuru).filter_by(id=data["id"]).first()
    if not t:
        raise HTTPException(status_code=404, detail="Tür bulunamadı.")
    if "ad" in data: t.ad = data["ad"]
    if "aciklama" in data: t.aciklama = data["aciklama"]
    if "aktif" in data: t.aktif = data["aktif"]
    if "sira" in data: t.sira = data["sira"]
    s.commit()
    return {"basarili": True}


@app.delete("/panel/uyelik-tur-sil/{tur_id}", dependencies=[Depends(panel_dogrula)])
def uyelik_tur_sil(tur_id: int, s: Session = Depends(db)):
    t = s.query(UyelikTuru).filter_by(id=tur_id).first()
    if not t:
        raise HTTPException(status_code=404, detail="Tür bulunamadı.")
    s.delete(t)
    s.commit()
    return {"basarili": True}


# Panel: Kullanıcılar listesi
@app.get("/panel/kullanicilar", dependencies=[Depends(panel_dogrula)])
def panel_kullanicilar(s: Session = Depends(db)):
    kullanicilar = s.query(Kullanici).order_by(Kullanici.kayit_tar.desc()).all()
    sonuc = []
    for k in kullanicilar:
        lisans = s.query(Lisans).filter_by(musteri_email=k.email, aktif=True).order_by(Lisans.olusturma_tar.desc()).first()
        sonuc.append({
            "id": k.id,
            "ad_soyad": k.ad_soyad,
            "email": k.email,
            "email_dogrulandi": k.email_dogrulandi,
            "kayit_tar": k.kayit_tar.strftime("%d.%m.%Y %H:%M"),
            "son_giris": k.son_giris.strftime("%d.%m.%Y %H:%M") if k.son_giris else "Hiç",
            "son_ip": k.son_ip or "-",
            "lisans_kodu": lisans.lisans_kodu if lisans else None,
            "lisans_tur": lisans.tur if lisans else None,
        })
    return sonuc


@app.delete("/panel/kullanici-sil/{kullanici_id}", dependencies=[Depends(panel_dogrula)])
def kullanici_sil(kullanici_id: str, s: Session = Depends(db)):
    """Kullanıcıyı ve varsa aktif lisansını siler."""
    k = s.query(Kullanici).filter_by(id=kullanici_id).first()
    if not k:
        raise HTTPException(status_code=404, detail="Kullanıcı bulunamadı.")
    # Aktif lisanslarını iptal et
    s.query(Lisans).filter_by(musteri_email=k.email, aktif=True).update({"aktif": False})
    # Taleplerini ve mesajlarını sil
    s.query(LisansTalep).filter_by(kullanici_id=kullanici_id).delete()
    s.query(Mesaj).filter_by(kullanici_id=kullanici_id).delete()
    # Kullanıcıyı sil
    s.delete(k)
    s.commit()
    return {"mesaj": f"{k.ad_soyad} ({k.email}) silindi, aktif lisansları iptal edildi."}


# =====================================================================
# PANEL HTML ARAYÜZÜ
# =====================================================================

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
.sidebar { position: fixed; left: 0; top: 0; bottom: 0; width: 220px; background: #1a1d2e; border-right: 1px solid #2a2d3e; padding: 20px 0; display: flex; flex-direction: column; }
.sidebar-logo { padding: 0 20px 20px; border-bottom: 1px solid #2a2d3e; margin-bottom: 12px; }
.sidebar-logo h1 { font-size: 15px; font-weight: 700; color: #5b8cff; }
.sidebar-logo p { font-size: 11px; color: #666; margin-top: 2px; }
.nav-item { display: flex; align-items: center; gap: 10px; padding: 10px 20px; font-size: 13px; color: #aaa; cursor: pointer; transition: all 0.15s; position: relative; }
.nav-item:hover { background: #222540; color: #e0e0e0; }
.nav-item.active { background: #222540; color: #5b8cff; border-right: 3px solid #5b8cff; }
.nav-item .badge { background: #ff4757; color: white; border-radius: 10px; padding: 1px 7px; font-size: 11px; font-weight: 700; margin-left: auto; }
.nav-icon { font-size: 16px; width: 20px; text-align: center; }

.main { margin-left: 220px; padding: 24px; }
.page { display: none; }
.page.active { display: block; }
.page-title { font-size: 20px; font-weight: 700; color: #e0e0e0; margin-bottom: 20px; }

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
</style>
</head>
<body>

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
  <div class="nav-item active" onclick="sayfaAc('lisanslar')" id="nav-lisanslar">
    <span class="nav-icon">🔑</span> Lisanslar
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
  <div class="nav-item" onclick="sayfaAc('ip-banlar')" id="nav-ip-banlar">
    <span class="nav-icon">🚫</span> IP Ban
  </div>
  <div class="nav-item" onclick="sayfaAc('uyelik-turleri')" id="nav-uyelik-turleri">
    <span class="nav-icon">⚙️</span> Üyelik Türleri
  </div>
  <div class="nav-item" onclick="sayfaAc('loglar')" id="nav-loglar">
    <span class="nav-icon">📜</span> Loglar
  </div>
</div>

<!-- Main -->
<div class="main">

  <!-- Lisanslar -->
  <div class="page active" id="page-lisanslar">
    <div class="page-title">🔑 Lisans Yönetimi</div>
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:16px;">
      <div class="card">
        <h3>Yeni Lisans Oluştur</h3>
        <input type="text" id="l-adi" placeholder="Müşteri adı soyadı *">
        <input type="email" id="l-email" placeholder="E-posta (teşekkür maili için)">
        <select id="l-tur">
          <option value="aylik">Aylık (30 gün)</option>
          <option value="yillik">Yıllık (365 gün)</option>
          <option value="omur_boyu">Ömür Boyu</option>
          <option value="deneme">Deneme</option>
        </select>
        <input type="number" id="l-saat" placeholder="Deneme süresi (saat)" value="24" min="1" max="8760">
        <textarea id="l-not" placeholder="Not"></textarea>
        <button class="btn btn-primary" onclick="lisansOlustur()">✚ Oluştur</button>
        <div id="l-sonuc" style="margin-top:10px;font-size:13px;color:#4caf50;font-weight:bold;font-family:monospace;"></div>
      </div>
      <div class="card">
        <h3>Lisans İşlemleri</h3>
        <input type="text" id="l-islem-kod" placeholder="Lisans kodu (AYL-XXXX-XXXX-XXXX)">
        <input type="number" id="l-uzat-gun" placeholder="Uzatma (gün)" value="30" min="1">
        <div class="row-btns">
          <button class="btn btn-danger btn-sm" onclick="iptalEt()">✖ İptal Et</button>
          <button class="btn btn-warning btn-sm" onclick="hwIdSifirla()">↺ HWID Sıfırla</button>
          <button class="btn btn-success btn-sm" onclick="sureUzat()">+ Süre Uzat</button>
        </div>
        <div id="l-islem-sonuc" style="margin-top:10px;font-size:13px;"></div>
      </div>
    </div>
    <div class="card">
      <h3>Tüm Lisanslar <button class="btn btn-ghost btn-sm" onclick="lisanslariYukle()" style="margin-left:10px;">↻ Yenile</button></h3>
      <div class="tbl-wrap">
        <table>
          <thead><tr><th>Kod</th><th>Müşteri</th><th>Tür</th><th>Durum</th><th>HWID</th><th>Bitiş</th><th>Son Checkin</th><th>Aktivasyon</th><th>Not</th></tr></thead>
          <tbody id="l-tablo"></tbody>
        </table>
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
        <textarea id="talep-not" placeholder="Admin notu (reddedilirse mail olarak gönderilir)" style="margin-bottom:12px;"></textarea>
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
          <thead><tr><th>Ad Soyad</th><th>E-posta</th><th>Doğrulandı</th><th>Kayıt</th><th>Son Giriş</th><th>Son IP</th><th>Lisans</th></tr></thead>
          <tbody id="kullanici-tablo"></tbody>
        </table>
      </div>
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

</div><!-- /main -->

<!-- Notification -->
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

function panelGiris() {
  const k = document.getElementById("inp-kullanici").value;
  const s = document.getElementById("inp-sifre").value;
  TOKEN = k + ":" + s;
  fetch("/panel/lisanslar", {headers: auth()})
    .then(r => {
      if (r.ok) {
        document.getElementById("login-overlay").style.display = "none";
        lisanslariYukle();
        badgeGuncelle();
        setInterval(badgeGuncelle, 30000);
      } else {
        document.getElementById("login-hata").textContent = "Kullanıcı adı veya şifre yanlış!";
      }
    });
}

function sayfaAc(sayfa) {
  document.querySelectorAll(".page").forEach(p => p.classList.remove("active"));
  document.querySelectorAll(".nav-item").forEach(n => n.classList.remove("active"));
  document.getElementById("page-" + sayfa).classList.add("active");
  document.getElementById("nav-" + sayfa).classList.add("active");

  const yukle = {
    lisanslar: lisanslariYukle,
    talepler: taleplerYukle,
    mesajlar: mesajlariYukle,
    kullanicilar: kullanicilariYukle,
    "ip-banlar": ipBanlariYukle,
    "uyelik-turleri": turleriYukle,
    loglar: logYukle,
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
  const b = {
    musteri_adi: document.getElementById("l-adi").value,
    musteri_email: document.getElementById("l-email").value,
    tur: document.getElementById("l-tur").value,
    deneme_saat: parseInt(document.getElementById("l-saat").value) || 24,
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

function lisanslariYukle() {
  fetch("/panel/lisanslar", {headers: auth()}).then(r => r.json()).then(liste => {
    const turBadge = {aylik:"b-aylik",yillik:"b-yillik",omur_boyu:"b-omur",deneme:"b-deneme"};
    document.getElementById("l-tablo").innerHTML = liste.map(l => `
      <tr>
        <td><code>${l.lisans_kodu}</code></td>
        <td>${l.musteri_adi}<br><span style="color:#555;font-size:11px;">${l.musteri_email||""}</span></td>
        <td><span class="badge ${turBadge[l.tur]||""}">${l.tur}</span></td>
        <td><span class="badge ${l.aktif?"b-aktif":"b-pasif"}">${l.aktif?"Aktif":"Pasif"}</span></td>
        <td style="font-family:monospace;font-size:11px;color:#555;">${(l.hwid||"").substring(0,18)}…</td>
        <td>${l.bitis_tarihi}</td>
        <td>${l.son_checkin}</td>
        <td>${l.aktivasyon}</td>
        <td style="color:#666;font-size:11px;">${l.notlar||""}</td>
      </tr>`).join("");
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
        <td>${t.tur}</td>
        <td><code>${t.ip||"-"}</code></td>
        <td><span class="badge ${durumBadge[t.durum]||""}">${t.durum}</span></td>
        <td>${t.durum==="beklemede" ? `<button class="btn btn-primary btn-sm" onclick="talepModalAc('${t.id}','${t.ad_soyad}','${t.email}','${t.tur}','${t.ip||''}')">İşlem</button>` : (t.admin_notu ? `<span style="color:#666;font-size:11px;">${t.admin_notu.substring(0,40)}</span>` : "—")}</td>
      </tr>`).join("");
    badgeGuncelle();
  });
}

function talepModalAc(id, ad, email, tur, ip) {
  secilenTalepId = id;
  document.getElementById("talep-bilgi").innerHTML = `<b>${ad}</b> &lt;${email}&gt;<br>Tür: <b>${tur}</b> | IP: <code>${ip}</code>`;
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

function konusmaSec(kullaniciId) {
  secilenKullaniciId = kullaniciId;
  mesajlariYukle();
  fetch("/panel/kullanici-mesajlar/" + kullaniciId, {headers: auth()}).then(r => r.json()).then(d => {
    const right = document.getElementById("msg-right");
    const k = d.kullanici;
    const l = d.lisans;
    const lisansBilgi = l ?
      `<span class="badge b-aktif" style="margin-right:4px;">${l.tur}</span> ${l.kod} — ${l.bitis||"Ömür Boyu"}${l.kalan_gun != null ? ` (${l.kalan_gun} gün)` : ""}` :
      `<span class="badge b-pasif">Lisans Yok</span>`;

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
        ${d.mesajlar.map(m => `
          <div class="msg-sender ${m.gonderen==='admin'?'right':''}">
            <div class="msg-bubble ${m.gonderen}">${m.icerik}</div>
            <div class="msg-time">${m.gonderen==='admin'?'Siz':'Kullanıcı'} · ${m.tarih}</div>
          </div>`).join("")}
      </div>
      <div class="msg-right-footer">
        <textarea id="admin-msg-inp" placeholder="Mesajınızı yazın…" onkeydown="if(event.ctrlKey&&event.key==='Enter')adminMesajGonder()"></textarea>
        <div style="display:flex;flex-direction:column;gap:6px;">
          <button class="btn btn-primary btn-sm" onclick="adminMesajGonder()">Gönder</button>
        </div>
      </div>`;
    // Scroll to bottom
    setTimeout(() => {
      const el = document.getElementById("aktif-mesajlar");
      if (el) el.scrollTop = el.scrollHeight;
    }, 50);
  });
}

function adminMesajGonder() {
  if (!secilenKullaniciId) return;
  const icerik = document.getElementById("admin-msg-inp").value.trim();
  if (!icerik) return;
  fetch("/panel/admin-mesaj-gonder", {method:"POST", headers:auth(), body:JSON.stringify({
    kullanici_id: secilenKullaniciId,
    icerik: icerik,
  })}).then(r => r.json()).then(() => {
    notif("Mesaj gönderildi");
    konusmaSec(secilenKullaniciId);
  });
}

// ===== KULLANICILAR =====
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
        <td><button class="btn btn-danger btn-sm" onclick="kullaniciSil('${k.id}','${k.ad_soyad}')">Sil</button></td>
      </tr>`).join("");
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
  const sira = parseInt(document.getElementById("tur-sira").value) || 99;
  if (!kod || !ad) { notif("Kod ve ad zorunlu!", true); return; }
  fetch("/panel/uyelik-tur-ekle", {method:"POST", headers:auth(), body:JSON.stringify({kod, ad, aciklama, sira})})
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
        <div class="row-btns" style="margin-top:8px;">
          <button class="btn btn-ghost btn-sm" onclick="turToggle(${t.id},${t.aktif})">${t.aktif?"Pasif Et":"Aktif Et"}</button>
          <button class="btn btn-danger btn-sm" onclick="turSil(${t.id})">Sil</button>
        </div>
      </div>`).join("");
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

// Startup
document.getElementById("inp-kullanici").focus();
document.addEventListener("keydown", e => {
  if (e.key === "Escape") talepModalKapat();
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

    <!-- Mesajlar -->
    <div class="dash-card full">
      <h3>Destek / Mesajlar</h3>
      <div class="msg-area" id="msg-area"></div>
      <textarea class="msg-input" id="msg-yaz" placeholder="Mesajınızı yazın… (Ctrl+Enter ile gönder)" onkeydown="if(event.ctrlKey&&event.key==='Enter')mesajGonder()"></textarea>
      <button class="form-btn" style="margin-top:8px;padding:10px;" onclick="mesajGonder()">Gönder</button>
    </div>
  </div>
</div>

<script>
let planlar = [];

// ===== SAYFA YÖNETİMİ =====
function sayfaGoster(ad) {
  ["anasayfa","planlar","kayit","giris","dashboard"].forEach(s => {
    document.getElementById("sayfa-" + s).style.display = s === ad ? "" : "none";
  });
  if (ad === "planlar") planlariYukle();
  if (ad === "dashboard") dashboardYukle();
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

let secilenPlan = null;
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
  const r = await fetch("/api/kayit", {method:"POST", headers:{"Content-Type":"application/json"},
    body: JSON.stringify({ad_soyad: ad, email, sifre})});
  const d = await r.json();
  if (r.ok) {
    mesajGoster("kayit-ok", "✅ " + d.mesaj);
  } else {
    mesajGoster("kayit-hata", d.detail || "Bir hata oluştu.");
  }
}

// ===== GİRİŞ =====
async function girisYap() {
  const email = document.getElementById("g-email").value.trim();
  const sifre = document.getElementById("g-sifre").value;
  mesajGizle("giris-hata");
  const r = await fetch("/api/giris", {method:"POST", headers:{"Content-Type":"application/json"},
    body: JSON.stringify({email, sifre})});
  const d = await r.json();
  if (r.ok) {
    sayfaGoster("dashboard");
    document.getElementById("nav-links").innerHTML = `<button class="nav-btn nav-btn-ghost" onclick="cikisYap()">Çıkış</button>`;
  } else {
    mesajGoster("giris-hata", d.detail || "Giriş başarısız.");
  }
}

// ===== ÇIKIŞ =====
async function cikisYap() {
  await fetch("/api/cikis", {method:"POST"});
  location.reload();
}

// ===== DASHBOARD =====
async function dashboardYukle() {
  const r = await fetch("/api/profil");
  if (!r.ok) { sayfaGoster("giris"); return; }
  const p = await r.json();

  document.getElementById("dash-hosgeldin").textContent = "Merhaba, " + p.ad_soyad + " 👋";
  document.getElementById("nav-links").innerHTML = `<span style="font-size:13px;color:var(--muted);margin-right:8px;">${p.email}</span><button class="nav-btn nav-btn-ghost" onclick="cikisYap()">Çıkış</button>`;

  // Lisans bilgisi kartları
  const grid = document.getElementById("dash-grid");
  if (p.lisans) {
    grid.innerHTML = `
      <div class="dash-card">
        <h3>Lisans Durumu</h3>
        <span class="status-badge status-active">● Aktif</span>
        <div class="dash-sub" style="margin-top:8px;">${p.lisans.tur}</div>
      </div>
      <div class="dash-card">
        <h3>Kalan Süre</h3>
        <div class="dash-val">${p.lisans.kalan_gun != null ? p.lisans.kalan_gun + " gün" : "Ömür Boyu"}</div>
        <div class="dash-sub">Bitiş: ${p.lisans.bitis}</div>
      </div>
      <div class="dash-card full">
        <h3>Lisans Kodunuz</h3>
        <div class="license-box">
          <div class="license-code">${p.lisans.kod}</div>
          <div class="license-sub">Bu kodu program aktivasyonunda kullanın</div>
        </div>
      </div>
      <div class="dash-card full" style="text-align:center;">
        <h3>Program İndir</h3>
        <div class="dash-sub" style="margin-bottom:16px;">Lisansınız aktif. Programı indirip lisans kodunuzla aktive edebilirsiniz.</div>
        <a href="${p.indirme_linki}" target="_blank" style="display:inline-flex;align-items:center;gap:10px;background:linear-gradient(135deg,var(--success),#16a34a);color:white;padding:14px 32px;border-radius:10px;font-size:15px;font-weight:700;text-decoration:none;box-shadow:0 0 24px #22c55e33;transition:all 0.2s;" onmouseover="this.style.transform='translateY(-2px)';this.style.boxShadow='0 0 40px #22c55e55'" onmouseout="this.style.transform='';this.style.boxShadow='0 0 24px #22c55e33'">
          ⬇ OPC Gateway'i İndir
        </a>
      </div>`;
  } else {
    grid.innerHTML = `
      <div class="dash-card full">
        <h3>Lisans Durumu</h3>
        <span class="status-badge status-none">● Lisans Yok</span>
        <div class="dash-sub" style="margin-top:8px;">Aşağıdan lisans talebinde bulunabilirsiniz.</div>
      </div>`;
  }

  // Talepler
  taleplerYukle();
  // Mesajlar
  mesajlariYukle();
}

async function taleplerYukle() {
  const r = await fetch("/api/benim-taleplerim");
  const talepler = await r.json();
  const durumBadge = {beklemede:"b-bekl",onaylandi:"b-onay",reddedildi:"b-red"};
  const durumYazi = {beklemede:"Beklemede",onaylandi:"Onaylandı",reddedildi:"Reddedildi"};
  let html = "";
  talepler.forEach(t => {
    html += `<div class="talep-item">
      <div>
        <div style="font-size:14px;font-weight:600;">${t.tur}</div>
        <div style="font-size:12px;color:var(--muted);">${t.tarih}${t.admin_notu ? " · " + t.admin_notu : ""}</div>
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
      <div style="display:flex;gap:10px;flex-wrap:wrap;margin-bottom:12px;">
        ${planlarData.map(p => `<div class="plan-card" id="dp-${p.kod}" onclick="dashPlanSec('${p.kod}')" style="padding:12px 16px;min-width:140px;cursor:pointer;">
          <div style="font-size:13px;font-weight:600;">${p.ad}</div>
          <div style="font-size:11px;color:var(--muted);margin-top:3px;">${p.aciklama||""}</div>
        </div>`).join("")}
      </div>
      <button class="form-btn" style="max-width:200px;padding:10px;" onclick="talepGonder()">Talep Gönder</button>
      <div class="form-err" id="talep-hata" style="margin-top:10px;"></div>
      <div class="form-ok" id="talep-ok" style="margin-top:10px;"></div>
    </div>`;
  }
  document.getElementById("talep-icerik").innerHTML = html;
}

let dashSecilenPlan = null;
function dashPlanSec(kod) {
  dashSecilenPlan = kod;
  document.querySelectorAll("[id^='dp-']").forEach(c => c.classList.remove("selected"));
  const el = document.getElementById("dp-" + kod);
  if (el) el.classList.add("selected");
}

async function talepGonder() {
  if (!dashSecilenPlan) { mesajGoster("talep-hata", "Lütfen bir plan seçin."); return; }
  mesajGizle("talep-hata"); mesajGizle("talep-ok");
  const r = await fetch("/api/talep-olustur", {method:"POST", headers:{"Content-Type":"application/json"},
    body: JSON.stringify({tur: dashSecilenPlan})});
  const d = await r.json();
  if (r.ok) {
    mesajGoster("talep-ok", "✅ " + d.mesaj);
    taleplerYukle();
  } else {
    mesajGoster("talep-hata", d.detail || "Hata.");
  }
}

async function mesajlariYukle() {
  const r = await fetch("/api/mesajlarim");
  const mesajlar = await r.json();
  const el = document.getElementById("msg-area");
  el.innerHTML = mesajlar.map(m => `
    <div class="msg-wrap ${m.gonderen==='kullanici'?'right':''}">
      <div class="msg-b ${m.gonderen==='kullanici'?'benim':'admin'}">${m.icerik}</div>
      <div class="msg-t">${m.gonderen==='kullanici'?'Siz':'Destek'} · ${m.tarih}</div>
    </div>`).join("");
  el.scrollTop = el.scrollHeight;
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
  if (el) { el.textContent = txt; el.style.display = ""; }
}
function mesajGizle(id) {
  const el = document.getElementById(id);
  if (el) el.style.display = "none";
}

// Sayfa yüklenince oturum kontrolü
(async function() {
  const r = await fetch("/api/profil");
  if (r.ok) {
    sayfaGoster("dashboard");
    document.getElementById("nav-links").innerHTML = `<button class="nav-btn nav-btn-ghost" onclick="cikisYap()">Çıkış</button>`;
  }
})();
</script>
</body>
</html>"""


@app.get("/", response_class=HTMLResponse)
def anasayfa():
    html = SITE_HTML_TEMPLATE.replace("{CSS}", SITE_CSS)
    return HTMLResponse(content=html)

@app.get("/kayit", response_class=HTMLResponse)
def kayit_sayfasi():
    html = SITE_HTML_TEMPLATE.replace("{CSS}", SITE_CSS)
    return HTMLResponse(content=html + "<script>sayfaGoster('kayit');</script>")

@app.get("/giris", response_class=HTMLResponse)
def giris_sayfasi():
    q = ""
    html = SITE_HTML_TEMPLATE.replace("{CSS}", SITE_CSS)
    return HTMLResponse(content=html + "<script>sayfaGoster('giris');</script>")

@app.get("/dashboard", response_class=HTMLResponse)
def dashboard_sayfasi():
    html = SITE_HTML_TEMPLATE.replace("{CSS}", SITE_CSS)
    return HTMLResponse(content=html + "<script>sayfaGoster('dashboard');</script>")

@app.get("/planlar", response_class=HTMLResponse)
def planlar_sayfasi():
    html = SITE_HTML_TEMPLATE.replace("{CSS}", SITE_CSS)
    return HTMLResponse(content=html + "<script>sayfaGoster('planlar');</script>")