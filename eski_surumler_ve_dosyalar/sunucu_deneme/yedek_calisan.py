# -*- coding: utf-8 -*-
"""
OPC Gateway — Lisans Doğrulama Sunucusu
FastAPI + SQLite | Railway / Render'a deploy edilecek

Kurulum:
  pip install fastapi uvicorn sqlalchemy python-jose passlib bcrypt

Çalıştırma (geliştirme):
  uvicorn sunucu:app --host 0.0.0.0 --port 8000 --reload

Railway/Render için Procfile:
  web: uvicorn sunucu:app --host 0.0.0.0 --port $PORT
"""

import os
import uuid
import hashlib
import secrets
import datetime
from typing import Optional

from fastapi import FastAPI, HTTPException, Header, Depends, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy import (
    create_engine, Column, String, DateTime,
    Boolean, Integer, Text
)
from sqlalchemy.orm import declarative_base, sessionmaker, Session


# =====================================================================
# YAPILANDIRMA
# =====================================================================
SECRET_KEY     = os.getenv("SECRET_KEY", "BURAYA-GIZLI-ANAHTARINIZI-YAZIN")
PANEL_SIFRE    = os.getenv("PANEL_SIFRE", "admin123")   # Panel giriş şifresi
DATABASE_URL   = os.getenv("DATABASE_URL", "sqlite:///./lisanslar.db")

# =====================================================================
# VERİTABANI
# =====================================================================
engine  = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
Session_ = sessionmaker(bind=engine)
Base    = declarative_base()


class Lisans(Base):
    __tablename__ = "lisanslar"

    id             = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    lisans_kodu    = Column(String, unique=True, nullable=False, index=True)
    hwid           = Column(String, nullable=True)           # İlk aktivasyonda dolar
    musteri_adi    = Column(String, nullable=False)
    musteri_email  = Column(String, nullable=True)
    tur            = Column(String, nullable=False)           # "aylik","yillik","omur_boyu","deneme"
    aktif          = Column(Boolean, default=True)
    olusturma_tar  = Column(DateTime, default=datetime.datetime.utcnow)
    bitis_tarihi   = Column(DateTime, nullable=True)          # None = ömür boyu
    notlar         = Column(Text, nullable=True)
    son_checkin    = Column(DateTime, nullable=True)
    aktivasyon_tar = Column(DateTime, nullable=True)


class Log(Base):
    __tablename__ = "loglar"

    id          = Column(Integer, primary_key=True, autoincrement=True)
    tarih       = Column(DateTime, default=datetime.datetime.utcnow)
    islem       = Column(String)    # "aktivasyon", "kontrol", "red"
    lisans_kodu = Column(String)
    hwid        = Column(String)
    ip          = Column(String)
    mesaj       = Column(Text)


Base.metadata.create_all(engine)


def db():
    s = Session_()
    try:
        yield s
    finally:
        s.close()


# =====================================================================
# YARDIMCI FONKSİYONLAR
# =====================================================================
def lisans_kodu_uret(tur_prefix="STD"):
    """Örn: STD-A3F2-9B1C-4E7D"""
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
    s.add(Log(islem=islem, lisans_kodu=lisans_kodu,
              hwid=hwid, ip=ip, mesaj=mesaj))
    s.commit()


# =====================================================================
# FASTAPI UYGULAMASI
# =====================================================================
app = FastAPI(title="OPC Gateway Lisans Sunucusu", docs_url=None, redoc_url=None)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["POST", "GET"],
    allow_headers=["*"],
)


def app_sirri_dogrula(request: Request):
    gelen = (
        request.headers.get("x-app-secret")
        or request.headers.get("x_app_secret")
        or ""
    )
    if gelen != SECRET_KEY:
        raise HTTPException(status_code=403, detail="Yetkisiz erisim.")


def panel_dogrula(request: Request):
    auth = request.headers.get("authorization") or request.headers.get("Authorization") or ""
    if auth != f"Bearer {PANEL_SIFRE}":
        raise HTTPException(status_code=401, detail="Panel sifresi yanlis.")


# =====================================================================
# İSTEMCİ API — Gateway EXE'si bu endpointleri kullanır
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
    kod = istek.lisans_kodu.strip().upper()
    hwid = istek.hwid.strip()

    lisans = s.query(Lisans).filter_by(lisans_kodu=kod).first()

    if not lisans:
        log_yaz(s, "red", kod, hwid, ip, "Lisans kodu bulunamadi")
        raise HTTPException(status_code=404, detail="Lisans kodu bulunamadı.")

    if not lisans.aktif:
        log_yaz(s, "red", kod, hwid, ip, "Lisans deaktif")
        raise HTTPException(status_code=403, detail="Bu lisans iptal edilmiştir.")

    # Süre kontrolü
    if lisans.bitis_tarihi and datetime.datetime.utcnow() > lisans.bitis_tarihi:
        log_yaz(s, "red", kod, hwid, ip, "Lisans suresi dolmus")
        raise HTTPException(status_code=403, detail="Lisans süresi dolmuştur.")

    # HWID kontrolü
    if lisans.hwid and lisans.hwid != hwid:
        log_yaz(s, "red", kod, hwid, ip, f"HWID uyusmuyor: kayitli={lisans.hwid}")
        raise HTTPException(
            status_code=403,
            detail="Bu lisans başka bir bilgisayara kayıtlıdır. Lütfen satıcı ile iletişime geçin."
        )

    # İlk aktivasyon — HWID kaydet
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
# YÖNETİM PANELİ API — Siz bu endpointleri kullanırsınız
# =====================================================================

class LisansOlusturIstek(BaseModel):
    musteri_adi:   str
    musteri_email: Optional[str] = None
    tur:           str            # "aylik","yillik","omur_boyu","deneme"
    deneme_saat:   Optional[int] = 24   # Sadece "deneme" türü için
    notlar:        Optional[str] = None


@app.post("/panel/lisans-olustur", dependencies=[Depends(panel_dogrula)])
def lisans_olustur(istek: LisansOlusturIstek, s: Session = Depends(db)):
    turler = {"aylik", "yillik", "omur_boyu", "deneme"}
    if istek.tur not in turler:
        raise HTTPException(status_code=400, detail=f"Geçersiz tür. Seçenekler: {turler}")

    prefix_map = {"aylik": "AYL", "yillik": "YIL", "omur_boyu": "OBY", "deneme": "DEN"}
    kod    = lisans_kodu_uret(prefix_map[istek.tur])
    bitis  = bitis_tarihi_hesapla(istek.tur, istek.deneme_saat)

    yeni = Lisans(
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
    """Müşteri bilgisayarını değiştirince HWID'i sıfırla — yeniden aktivasyon yapabilsin."""
    lisans = s.query(Lisans).filter_by(lisans_kodu=lisans_kodu.upper()).first()
    if not lisans:
        raise HTTPException(status_code=404, detail="Lisans bulunamadı.")
    lisans.hwid = None
    lisans.aktivasyon_tar = None
    s.commit()
    return {"mesaj": f"{lisans_kodu} için HWID sıfırlandı. Müşteri yeniden aktive edebilir."}


@app.post("/panel/sure-uzat", dependencies=[Depends(panel_dogrula)])
def sure_uzat(lisans_kodu: str, gun: int, s: Session = Depends(db)):
    """Mevcut lisansa gün ekle."""
    lisans = s.query(Lisans).filter_by(lisans_kodu=lisans_kodu.upper()).first()
    if not lisans:
        raise HTTPException(status_code=404, detail="Lisans bulunamadı.")
    if not lisans.bitis_tarihi:
        raise HTTPException(status_code=400, detail="Ömür boyu lisansa süre eklenemez.")
    baz = max(lisans.bitis_tarihi, datetime.datetime.utcnow())
    lisans.bitis_tarihi = baz + datetime.timedelta(days=gun)
    lisans.aktif = True
    s.commit()
    return {
        "mesaj": f"{gun} gün eklendi.",
        "yeni_bitis": lisans.bitis_tarihi.strftime("%d.%m.%Y %H:%M")
    }


@app.get("/panel/loglar", dependencies=[Depends(panel_dogrula)])
def loglar(son: int = 100, s: Session = Depends(db)):
    logs = s.query(Log).order_by(Log.tarih.desc()).limit(son).all()
    return [
        {
            "tarih":       l.tarih.strftime("%d.%m.%Y %H:%M:%S"),
            "islem":       l.islem,
            "lisans_kodu": l.lisans_kodu,
            "hwid":        l.hwid,
            "ip":          l.ip,
            "mesaj":       l.mesaj,
        }
        for l in logs
    ]


# =====================================================================
# YÖNETİM PANEL ARAYÜZÜ — Tarayıcıdan kullanılır
# =====================================================================
@app.get("/panel", response_class=HTMLResponse)
def panel_html():
    return HTMLResponse(content="""
<!DOCTYPE html>
<html lang="tr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>OPC Gateway — Lisans Paneli</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: system-ui, sans-serif; background: #f0f2f5; color: #222; }
  .header { background: #1565c0; color: white; padding: 16px 24px; font-size: 18px; font-weight: bold; }
  .container { max-width: 1100px; margin: 24px auto; padding: 0 16px; }
  .card { background: white; border-radius: 8px; padding: 20px; margin-bottom: 20px; box-shadow: 0 1px 4px rgba(0,0,0,0.08); }
  h2 { font-size: 15px; font-weight: 600; margin-bottom: 14px; color: #1565c0; }
  input, select { border: 1px solid #ccc; border-radius: 4px; padding: 8px 10px; font-size: 13px; width: 100%; margin-bottom: 8px; }
  button { background: #1565c0; color: white; border: none; border-radius: 4px; padding: 9px 20px; font-size: 13px; cursor: pointer; }
  button:hover { background: #0d47a1; }
  button.red { background: #c62828; }
  button.green { background: #2e7d32; }
  button.orange { background: #e65100; }
  table { width: 100%; border-collapse: collapse; font-size: 12px; }
  th { background: #e8eaf6; text-align: left; padding: 8px 10px; font-weight: 600; }
  td { padding: 7px 10px; border-bottom: 1px solid #f0f0f0; vertical-align: top; }
  tr:hover td { background: #fafafa; }
  .badge { display: inline-block; padding: 2px 8px; border-radius: 10px; font-size: 11px; font-weight: 600; }
  .badge-aktif { background: #e8f5e9; color: #2e7d32; }
  .badge-pasif { background: #ffebee; color: #c62828; }
  .badge-aylik { background: #e3f2fd; color: #1565c0; }
  .badge-yillik { background: #e8eaf6; color: #3949ab; }
  .badge-omur { background: #e8f5e9; color: #1b5e20; }
  .badge-deneme { background: #fff3e0; color: #e65100; }
  #sifre-ekrani { position: fixed; inset: 0; background: rgba(0,0,0,0.5); display: flex; align-items: center; justify-content: center; z-index: 99; }
  #sifre-kutu { background: white; border-radius: 8px; padding: 30px; width: 320px; text-align: center; }
  #sifre-kutu h3 { margin-bottom: 16px; color: #1565c0; }
  #durum { background: #1e1e1e; color: #00ff41; font-family: monospace; font-size: 12px; padding: 12px; border-radius: 4px; min-height: 48px; white-space: pre-wrap; }
  .row { display: flex; gap: 12px; }
  .row input, .row select { flex: 1; }
</style>
</head>
<body>

<div id="sifre-ekrani">
  <div id="sifre-kutu">
    <h3>Panel Girisi</h3>
    <input type="password" id="txt_sifre" placeholder="Panel sifresi" onkeydown="if(event.key=='Enter')giris()">
    <br><br>
    <button onclick="giris()">Giris Yap</button>
    <p id="sifre_hata" style="color:red;font-size:12px;margin-top:8px;"></p>
  </div>
</div>

<div class="header">OPC Gateway — Lisans Yonetim Paneli</div>

<div class="container">

  <div class="card">
    <h2>Yeni Lisans Olustur</h2>
    <div class="row">
      <input type="text" id="musteri_adi" placeholder="Musteri adi *">
      <input type="email" id="musteri_email" placeholder="E-posta (opsiyonel)">
    </div>
    <div class="row">
      <select id="tur">
        <option value="aylik">Aylik (30 gun)</option>
        <option value="yillik">Yillik (365 gun)</option>
        <option value="omur_boyu">Omur Boyu</option>
        <option value="deneme">Deneme Suresi</option>
      </select>
      <input type="number" id="deneme_saat" placeholder="Deneme suresi (saat)" value="24" min="1" max="8760">
    </div>
    <input type="text" id="notlar" placeholder="Not (opsiyonel)">
    <button onclick="lisansOlustur()">Lisans Olustur</button>
    <div id="olustur_sonuc" style="margin-top:10px;font-size:13px;color:#2e7d32;font-weight:bold;"></div>
  </div>

  <div class="card">
    <h2>Lisans Islemleri</h2>
    <div class="row">
      <input type="text" id="islem_kod" placeholder="Lisans kodu (STD-XXXX-XXXX-XXXX)">
      <input type="number" id="uzat_gun" placeholder="Uzatma (gun)" value="30" min="1">
    </div>
    <div style="display:flex;gap:8px;flex-wrap:wrap;">
      <button class="red" onclick="iptalEt()">Lisansi Iptal Et</button>
      <button class="orange" onclick="hwIdSifirla()">HWID Sifirla</button>
      <button class="green" onclick="sureUzat()">Sure Uzat</button>
    </div>
    <div id="islem_sonuc" style="margin-top:10px;font-size:13px;"></div>
  </div>

  <div class="card">
    <h2>Tum Lisanslar</h2>
    <button onclick="lisanslariYukle()" style="margin-bottom:12px;">Yenile</button>
    <div style="overflow-x:auto;">
      <table id="tablo">
        <thead><tr>
          <th>Lisans Kodu</th><th>Musteri</th><th>Tur</th><th>Durum</th>
          <th>HWID</th><th>Bitis</th><th>Son Checkin</th><th>Aktivasyon</th>
        </tr></thead>
        <tbody id="tablo_body"></tbody>
      </table>
    </div>
  </div>

  <div class="card">
    <h2>Son Islem Loglari</h2>
    <button onclick="logYukle()" style="margin-bottom:12px;">Yenile</button>
    <div id="durum">Loglar yuklenecek...</div>
  </div>

</div>

<script>
let TOKEN = "";

function giris() {
  TOKEN = document.getElementById("txt_sifre").value;
  fetch("/panel/lisanslar", {headers: {"Authorization": "Bearer " + TOKEN}})
    .then(r => {
      if (r.ok) {
        document.getElementById("sifre-ekrani").style.display = "none";
        lisanslariYukle();
        logYukle();
      } else {
        document.getElementById("sifre_hata").textContent = "Sifre yanlis!";
      }
    });
}

function auth() { return {"Authorization": "Bearer " + TOKEN, "Content-Type": "application/json"}; }

function lisansOlustur() {
  const body = {
    musteri_adi:   document.getElementById("musteri_adi").value,
    musteri_email: document.getElementById("musteri_email").value,
    tur:           document.getElementById("tur").value,
    deneme_saat:   parseInt(document.getElementById("deneme_saat").value) || 24,
    notlar:        document.getElementById("notlar").value,
  };
  if (!body.musteri_adi) { alert("Musteri adi zorunlu!"); return; }
  fetch("/panel/lisans-olustur", {method:"POST", headers:auth(), body:JSON.stringify(body)})
    .then(r => r.json())
    .then(d => {
      document.getElementById("olustur_sonuc").textContent =
        d.lisans_kodu ? `✅ Olusturuldu: ${d.lisans_kodu} | ${d.bitis_tarihi}` : d.detail;
      lisanslariYukle();
    });
}

function iptalEt() {
  const kod = document.getElementById("islem_kod").value;
  if (!kod) { alert("Lisans kodu girin!"); return; }
  if (!confirm(`${kod} iptal edilsin mi?`)) return;
  fetch(`/panel/iptal?lisans_kodu=${encodeURIComponent(kod)}`, {method:"POST", headers:auth()})
    .then(r => r.json())
    .then(d => { document.getElementById("islem_sonuc").textContent = d.mesaj || d.detail; lisanslariYukle(); });
}

function hwIdSifirla() {
  const kod = document.getElementById("islem_kod").value;
  if (!kod) { alert("Lisans kodu girin!"); return; }
  fetch(`/panel/hwid-sifirla?lisans_kodu=${encodeURIComponent(kod)}`, {method:"POST", headers:auth()})
    .then(r => r.json())
    .then(d => { document.getElementById("islem_sonuc").textContent = d.mesaj || d.detail; lisanslariYukle(); });
}

function sureUzat() {
  const kod = document.getElementById("islem_kod").value;
  const gun = document.getElementById("uzat_gun").value;
  if (!kod) { alert("Lisans kodu girin!"); return; }
  fetch(`/panel/sure-uzat?lisans_kodu=${encodeURIComponent(kod)}&gun=${gun}`, {method:"POST", headers:auth()})
    .then(r => r.json())
    .then(d => { document.getElementById("islem_sonuc").textContent = d.mesaj || d.detail; lisanslariYukle(); });
}

function lisanslariYukle() {
  fetch("/panel/lisanslar", {headers: auth()})
    .then(r => r.json())
    .then(liste => {
      const tbody = document.getElementById("tablo_body");
      tbody.innerHTML = "";
      liste.forEach(l => {
        const turBadge = {
          "aylik":"badge-aylik", "yillik":"badge-yillik",
          "omur_boyu":"badge-omur", "deneme":"badge-deneme"
        }[l.tur] || "";
        tbody.innerHTML += `<tr>
          <td><code>${l.lisans_kodu}</code></td>
          <td>${l.musteri_adi}<br><span style="color:#888;font-size:11px;">${l.musteri_email||""}</span></td>
          <td><span class="badge ${turBadge}">${l.tur}</span></td>
          <td><span class="badge ${l.aktif?"badge-aktif":"badge-pasif"}">${l.aktif?"Aktif":"Pasif"}</span></td>
          <td style="font-family:monospace;font-size:11px;">${(l.hwid||"").substring(0,16)}...</td>
          <td>${l.bitis_tarihi}</td>
          <td>${l.son_checkin}</td>
          <td>${l.aktivasyon}</td>
        </tr>`;
      });
    });
}

function logYukle() {
  fetch("/panel/loglar?son=50", {headers: auth()})
    .then(r => r.json())
    .then(logs => {
      const el = document.getElementById("durum");
      el.textContent = logs.map(l =>
        `[${l.tarih}] ${l.islem.toUpperCase().padEnd(12)} ${l.lisans_kodu} | ${l.mesaj}`
      ).join("\\n");
    });
}

document.getElementById("txt_sifre").focus();
</script>
</body>
</html>
""")


@app.get("/")
def root():
    return {"durum": "OPC Gateway Lisans Sunucusu calisıyor.", "versiyon": "4.0"}