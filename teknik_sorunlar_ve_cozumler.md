# 🔴 5 Kritik Teknik Sorun — Tam Analiz ve Düzeltme Kodları

> Her sorun **koddan birebir satır gösterimi**, **neden problem olduğu**, **gerçek saldırı/arıza senaryosu** ve **hazır düzeltme kodu** ile açıklanmıştır.

---

## ❶ SSL Doğrulama Kapalı — `CERT_NONE`

### Kodda Nerede?

**3 farklı yerde** aynı hata var:

**Yer 1 — API isteği** ([gateway_v5.0.py satır 665-667](file:///c:/Users/onnur/Desktop/OPC/Kaynak%20Kodlar/HWID_version/gateway_v5.0.py#L665-L667)):
```python
ctx  = ssl.create_default_context()
ctx.check_hostname = False      # ← BU SATIR
ctx.verify_mode    = ssl.CERT_NONE  # ← BU SATIR
```
Bu kod her lisans aktivasyonunda ve `LisansYoneticisi._api_iste()` içinde çalışır.

**Yer 2 — Python indirme** ([satır 1315-1317](file:///c:/Users/onnur/Desktop/OPC/Kaynak%20Kodlar/HWID_version/gateway_v5.0.py#L1315-L1317)):
```python
ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE
```
Kurulum Merkezi'nden `python-3.13.3.exe` indirirken kullanılıyor.

**Yer 3 — İnternet kontrol** ([satır 2289-2291](file:///c:/Users/onnur/Desktop/OPC/Kaynak%20Kodlar/HWID_version/gateway_v5.0.py#L2289-L2291)):
```python
ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode    = ssl.CERT_NONE
urllib.request.urlopen(SUNUCU_URL, context=ctx, timeout=4)
```

---

### Bu Neden Problem?

**SSL/TLS sertifikası doğrulama**, "bağlandığım sunucu gerçekten benim sunucum mu?" sorusunu cevaplar. `CERT_NONE` ile bu kontrol tamamen **devre dışı** bırakılıyor.

**Açık kapı bıraktığı saldırı: Man-in-the-Middle (MitM)**

```
Normal akış:
  EXE ──HTTPS──► Railway.app (gerçek lisans sunucusu)

CERT_NONE ile saldırı mümkün:
  EXE ──HTTPS──► [Sahte Sunucu] ──► Railway.app
                   (araya girdi)

Sahte sunucu ne yapabilir?
  1. Lisans doğrulamayı her zaman "geçerli" döndür → ücret ödemeden kullanım
  2. Aktivasyon isteklerini kaydet → HWID + lisans kodları ele geçirilir
  3. Kötü amaçlı JSON döndür → EXE içinde json.loads() farklı davranır
```

**Pratik senaryo:**
- Müşteri fabrika ağında. Ağ yöneticisi (veya kötü niyetli bir kişi) DNS veya ARP manipülasyonu yapar.
- `web-production-b5bbc.up.railway.app` adresi yerel sahte bir sunucuya yönlendirilir.
- EXE sertifika kontrolü yapmadığı için bu bağlantıyı kabul eder.
- Sahte sunucu `{"durum": "gecerli", "musteri_adi": "Test"}` döndürür.
- **EXE lisanssız açılır.**

**Python indirme özelinde ek risk:**
- Sahte sunucu `python-3.13.3.exe` yerine **zararlı yazılım içeren bir EXE** gönderebilir.
- Bu EXE müşterinin bilgisayarına kurulur (`subprocess.Popen(komut, shell=True)`).

---

### Risk Seviyesi ve Neden Şimdiye Kadar Sorun Olmadı?

Şu an sorun yaşanmıyor çünkü:
1. Railway **zaten HTTPS** kullanıyor (HTTP değil).
2. Fabrika ağları genellikle dışarıya kapalı, MitM zor.
3. Müşteri sayısı henüz az.

Ama büyüdükçe hedef haline gelirsiniz.

---

### Düzeltme

**Yer 1 ve 3 (API + İnternet kontrol):**

```python
# ❌ ESKİ KOD (3 yerde aynı hata)
ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode    = ssl.CERT_NONE

# ✅ YENİ KOD — Sadece bu kadar
ctx = ssl.create_default_context()
# check_hostname varsayılan True → değiştirme
# verify_mode varsayılan CERT_REQUIRED → değiştirme
```

**Yer 2 (Python indirme) — Python.org zaten güvenilir CA'ya sahip:**
```python
# ❌ ESKİ
ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

# ✅ YENİ
ctx = ssl.create_default_context()
# Sadece Python.org fingerprint kontrolü eklenebilir (opsiyonel ama iyi pratik):
# ctx.load_verify_locations(...)  # veya varsayılan CA store yeterli
```

**Neden Railway için SSL CERT_NONE gerekmiyordu?**
Railway, Let's Encrypt CA sertifikası kullanır. Bu sertifika Python'ın varsayılan CA store'unda zaten tanımlı. `CERT_NONE` hiçbir zaman gerekmiyordu — muhtemelen geliştirme sırasında test için eklendi ve üretimde unutuldu.

---

## ❷ Session In-Memory — Sunucu Restart = Tüm Oturumlar Kapanır

### Kodda Nerede?

**[helpers.py satır 185-202](file:///c:/Users/onnur/Desktop/opc-lisans-sunucu/helpers.py#L185-L202)**:

```python
# ← BU BİR GLOBAL PYTHON DİCT — RAM'de yaşıyor
_sessions = {}

def session_olustur(kullanici_id: str) -> str:
    token = secrets.token_urlsafe(32)
    _sessions[token] = {
        "kullanici_id": kullanici_id,
        "tarih": datetime.datetime.utcnow()
    }
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
```

---

### Bu Neden Problem?

`_sessions = {}` — bu bir Python dictionary, yani **sadece RAM'de** yaşıyor.

**Senaryo 1: Railway otomatik restart**
```
Müşteri giriş yaptı → token aldı → dashboard açık
    │
Railway monthly maintenance → Pod restart
    │
_sessions = {}  ← SIFIRDI
    │
Müşteri sayfayı yeniledi → "Oturum bulunamadı" → Logout
```

**Senaryo 2: Yeni kod deploy**
Railway'e her `git push` yaptığında pod yeniden başlıyor. Deployment süresi ~30 saniye bile olsa bu 30 saniye içinde tüm aktif oturumlar kayboluyor.

**Senaryo 3: Ölçeklendirme (scale-out)**
```
Kullanıcı → Load Balancer → Pod A (session var)
                          → Pod B (session yok!)
```
Railway ücretsiz plan tek pod. Ama Pro plana geçersen ve 2 pod çalıştırırsan, kullanıcılar sürekli login/logout sorunuyla karşılaşır.

**Senaryo 4: Bellek sızıntısı**
7 günlük token temizleme sadece `session_dogrula()` çağrıldığında yapılıyor. Kimse giriş yapmadan token birikirse (bot saldırısı gibi) `_sessions` dict sonsuza büyür → **Railway bellek limitini aşar → pod crash → tüm oturumlar gider**.

---

### Ek Sorun: Session Fixation Riski

Token oluşturma `secrets.token_urlsafe(32)` → Bu kısım iyi. Ama:
- Token cookie'de `httponly` ayarlanıyor mu? → Kontrol edilmeli.
- Oturum `login` sırasında **yeniden üretilmiyor** → Session fixation açığı mevcut olabilir.

---

### Düzeltme Seçenekleri

#### Seçenek A: SQLite'a Session Kaydet (Çok Kolay, Ücretsiz)

```python
# database.py'e ekle:
class Session(Base):
    __tablename__ = "sessions"
    token        = Column(String, primary_key=True)
    kullanici_id = Column(String, nullable=False)
    olusturma    = Column(DateTime, default=datetime.datetime.utcnow)
    bitis        = Column(DateTime, nullable=False)

# helpers.py — tamamen değiştir:
from database import SessionLocal, Session as SessionModel
import datetime, secrets

def session_olustur(kullanici_id: str) -> str:
    token = secrets.token_urlsafe(32)
    bitis = datetime.datetime.utcnow() + datetime.timedelta(days=7)
    db = SessionLocal()
    try:
        db.add(SessionModel(token=token, kullanici_id=kullanici_id, bitis=bitis))
        db.commit()
    finally:
        db.close()
    return token

def session_dogrula(token: str):
    if not token: return None
    db = SessionLocal()
    try:
        s = db.query(SessionModel).filter(
            SessionModel.token == token,
            SessionModel.bitis > datetime.datetime.utcnow()
        ).first()
        return s.kullanici_id if s else None
    finally:
        db.close()

def session_sil(token: str):
    db = SessionLocal()
    try:
        db.query(SessionModel).filter(SessionModel.token == token).delete()
        db.commit()
    finally:
        db.close()
```

**Artısı:** Sıfır ek maliyet, Railway'de SQLite zaten var.  
**Eksisi:** SQLite'ta concurrent yazma kilitlenebilir (çok kullanıcılı prod için PostgreSQL daha iyi).

#### Seçenek B: Redis (Güçlü, Ölçeklenebilir)

```python
# requirements.txt'e ekle: redis

import redis, os, secrets, datetime

_r = redis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379"))
SESSION_TTL = 7 * 24 * 3600  # 7 gün, saniye cinsinden

def session_olustur(kullanici_id: str) -> str:
    token = secrets.token_urlsafe(32)
    _r.setex(f"session:{token}", SESSION_TTL, kullanici_id)
    return token

def session_dogrula(token: str):
    if not token: return None
    val = _r.get(f"session:{token}")
    return val.decode() if val else None

def session_sil(token: str):
    _r.delete(f"session:{token}")
```

**Railway'de Redis ekle:** Railway dashboard → Add Service → Redis → `REDIS_URL` otomatik environment variable olarak eklenir.

---

## ❸ OPC UA Namespace Hâlâ `v4`

### Kodda Nerede?

**[gateway_v5.0.py satır 1677-1678](file:///c:/Users/onnur/Desktop/OPC/Kaynak%20Kodlar/HWID_version/gateway_v5.0.py#L1677-L1678)**:

```python
srv.set_server_name(f"OPC Gateway v{VERSIYON}")  # VERSIYON = "4.1"
idx = await srv.register_namespace("http://opcgateway/v4")  # ← YANLIŞ
```

Aynı satırda: `VERSIYON = "4.1"` ([satır 41](file:///c:/Users/onnur/Desktop/OPC/Kaynak%20Kodlar/HWID_version/gateway_v5.0.py#L41)) ama dosya adı `gateway_v5.0.py`.

---

### Bu Neden Problem?

OPC UA namespace URI'si (`http://opcgateway/v4`), OPC UA sunucusunda her node'un "adresi"nin bir parçasıdır.

**OPC UA node adresi şu şekilde oluşur:**
```
NodeId = (namespace_index, identifier)

Müşterinin SCADA/ERP sistemi bağlandığında şunu kaydeder:
  ns=2;s=Saha_Verileri.Motor_Hizi
  
Bu "ns=2" aslında "http://opcgateway/v4" anlamına gelir.
```

**Sorun şu:**
```
Bugün:    namespace = "http://opcgateway/v4"
          SCADA bağlıyor, tag adresleri: ns=2;s=Motor_Hizi

Yarın v5.0 deploy:
          namespace = "http://opcgateway/v5"  (düzeltilirse)
          ns=2;s=Motor_Hizi → ARTIK YOK (ns değeri değişti)

SCADA sistemi tüm tag'leri kaybeder!
Operatör ekranı boş kalır.
Alarm ve izleme sistemleri çalışmaz.
```

**Gerçek endüstriyel sonuç:** Bir petrokimya veya enerji tesisinde bu olmak demek, saatler süren SCADA yeniden konfigürasyonu demektir. Uygulamanın güvenilirliğine zarar verir.

---

### Ek Sorun: VERSIYON değişkeni

```python
VERSIYON = "4.1"  # satır 41 — dosya adı gateway_v5.0.py ama versiyon 4.1!
```

Bu durum:
- `srv.set_server_name("OPC Gateway v4.1")` → OPC UA browser'da eski versiyon görünür
- Loglar: `OPC DA -> OPC UA Gateway v4.1 hazir.` → Kafa karışıklığı
- EXE metadata: `ver.txt`'de `FileVersion=1.0.0` ama koda `4.1` yazıyor

---

### Düzeltme

```python
# ❌ ESKİ — satır 38-41
SUNUCU_URL       = "https://web-production-b5bbc.up.railway.app"
UYGULAMA_SIFRESI = "admin1234"
LISANS_DOSYASI   = ...
CHECKIN_ARALIK   = 7
VERSIYON         = "4.1"   # ← HATALI

# ✅ YENİ
VERSIYON         = "5.0"   # dosya adıyla tutarlı

# ❌ ESKİ — satır 1678
idx = await srv.register_namespace("http://opcgateway/v4")

# ✅ YENİ — namespace URI'yi VERSIYON değişkenine bağla
# VE bir kez belirlendikten sonra asla değiştirme!
NAMESPACE_URI = "http://opcgateway/v5"  # satır 41 civarına ekle
...
idx = await srv.register_namespace(NAMESPACE_URI)
```

> ⚠️ **Kritik Kural:** Namespace URI bir kez belirlendikten sonra, gelecekteki versiyonlarda bile `v5` olarak kalmalı. Ancak büyük protokol değişikliklerinde (ör. tamamen farklı node yapısı) `v6`'ya geçilebilir. Her minor güncellemede değiştirmek büyük hasara yol açar.

---

## ❹ `poll_cap` Hardcoded = 120

### Kodda Nerede?

**[gateway_v5.0.py satır 1734-1735](file:///c:/Users/onnur/Desktop/OPC/Kaynak%20Kodlar/HWID_version/gateway_v5.0.py#L1734-L1735)**:

```python
MIN_POLLED_PER_CYCLE = 6
MAX_POLLED_PER_CYCLE = 120   # ← BU SABIT
```

**Kullanıldığı yerler:**
```python
# satır 1761 — başlangıç değeri:
poll_cap = min(MAX_POLLED_PER_CYCLE, max(MIN_POLLED_PER_CYCLE, len(etiket_listesi) // 5 or 1))

# satır 1875 — auto-tune düşürme:
poll_cap = max(MIN_POLLED_PER_CYCLE, poll_cap - 8)

# satır 1879 — auto-tune artırma:
poll_cap = min(MAX_POLLED_PER_CYCLE, poll_cap + 3)  # ← 120'yi geçemez!
```

---

### Bu Neden Problem?

`poll_cap = 120` demek, her döngüde en fazla 120 etiket okunabilir demek.

**Büyük tesis senaryosu:**
```
Tesis: 2000 etiket, 10s yenileme hedefi

poll_cap = 120 ile:
  Bir tam tur = 2000 / 120 = 17 döngü
  Her döngü ~250ms
  Toplam yenileme: 17 × 250ms = ~4.25 saniye ✓ (10s hedefin çok altında)

Ama 5000 etiket olursa:
  Bir tam tur = 5000 / 120 = 42 döngü × 250ms = ~10.5 saniye
  Bu zaten 10s hedefini geçiyor. Artırsan ne olur?

poll_cap = 300 ile:
  Bir tam tur = 5000 / 300 = 17 döngü × 250ms = ~4.25 saniye ✓
```

**Ek sorun: Auto-tune çıkmazı**
```
Sistem hızlıysa (read < 250ms), poll_cap her döngüde +3 artıyor.
AMA en fazla 120'e ulaşabiliyor.

Hızlı bir OPC DA sunucu (örn. KEPServer hızlı modda)
aslında 200-300 etiket okuyabilirken,
120 sınırıyla potansiyelinin altında çalışıyor.
```

---

### Büyük Tesis Etkisi (Hesaplanmış)

```
Etiket Sayısı  │  poll_cap=120  │  poll_cap=300  │  Fark
───────────────┼────────────────┼────────────────┼──────────
     1,000     │    2.25 sn     │    1.08 sn     │  2.1x hız
     2,000     │    4.25 sn     │    1.75 sn     │  2.4x hız
     5,000     │   10.50 sn     │    4.25 sn     │  2.5x hız
    10,000     │   21.00 sn     │    8.50 sn     │  2.5x hız
```

---

### Düzeltme — 3 Kademeli Yaklaşım

**Seçenek 1: Sabit değeri artır (En Kolay)**
```python
# ❌ ESKİ
MAX_POLLED_PER_CYCLE = 120

# ✅ YENİ — Konservatif artış
MAX_POLLED_PER_CYCLE = 300
```

**Seçenek 2: GUI'den ayarlanabilir yap (Orta)**
```python
# GatewayApp başlatma parametrelerine ekle:
class GatewayWorker(QThread):
    def __init__(self, prog_id, ip, port, etiketler, yetki="FULL",
                 max_poll_cap=300):  # ← parametre ekle
        ...
        self.max_poll_cap = max_poll_cap
        
# _ua_dongusu içinde:
MAX_POLLED_PER_CYCLE = self.max_poll_cap  # sabit yerine instance değişkeni
```

**Seçenek 3: Otomatik tespit (En İyi)**
```python
# Mevcut etiket sayısına göre akıllı başlangıç değeri:
n = len(etiket_listesi)
if   n <= 100:   MAX_POLLED_PER_CYCLE = 50
elif n <= 500:   MAX_POLLED_PER_CYCLE = 120   # mevcut
elif n <= 2000:  MAX_POLLED_PER_CYCLE = 200
elif n <= 5000:  MAX_POLLED_PER_CYCLE = 350
else:            MAX_POLLED_PER_CYCLE = 500

MIN_POLLED_PER_CYCLE = max(6, n // 50)  # dinamik min de
```

---

## ❺ `UYGULAMA_SIFRESI = "admin1234"` Hardcoded

### Kodda Nerede?

**[gateway_v5.0.py satır 38](file:///c:/Users/onnur/Desktop/OPC/Kaynak%20Kodlar/HWID_version/gateway_v5.0.py#L38)**:

```python
SUNUCU_URL       = "https://web-production-b5bbc.up.railway.app"
UYGULAMA_SIFRESI = "admin1234"    # ← BU SATIR
```

Bu değer her `_api_iste()` çağrısında **HTTP header olarak gönderiliyor:**

```python
# satır 673
headers={
    "Content-Type": "application/json",
    "X-App-Secret": UYGULAMA_SIFRESI,  # "admin1234" her istekte gider!
    "X-App-Version": VERSIYON,
},
```

Sunucu tarafında kontrol ([routes_client.py](file:///c:/Users/onnur/Desktop/opc-lisans-sunucu/routes_client.py)):
```python
# Sunucu bu header'ı alıyor ve SECRET_KEY env değişkeniyle karşılaştırıyor
```

---

### Bu Neden Problem?

**Katman 1: EXE içindeki sır**

EXE reverse-engineer edilebilir. `builder.py` Fernet şifreliyor ama bu mutlak koruma değil:

```
Saldırgan:
  1. strings.exe OPCGateway.exe | findstr "admin"
     → admin1234 açık görünmeyebilir (şifreli payload içinde)
  
  2. Fernet şifresini kırmak çok zordur AMA:
     - EXE RAM'de çalışırken memory dump alınabilir
     - Python marshal unpack araçları vardır
     - Belirlenen şifreyi bulduktan sonra:
```

**Katman 2: Şifreyi bulduktan sonra ne olur?**

Saldırgan `admin1234`'ü öğrenirse:
```python
import requests

# Sahte bir HWID ile sonsuz lisans aktivasyonu!
r = requests.post(
    "https://web-production-b5bbc.up.railway.app/api/aktive-et",
    headers={"X-App-Secret": "admin1234"},
    json={"lisans_kodu": "AYL-XXXX-XXXX-XXXX", "hwid": "FAKE_HWID_HERE"}
)
```

Sunucu bu isteği **gerçek bir EXE isteği gibi kabul eder.**

**Katman 3: `admin1234` zayıf şifre**

İnsan tarafından yazılmış tahmin edilebilir. Brute-force veya wordlist saldırılarında ilk denenenler arasında.

**Katman 4: Railway URL açıkta**

`SUNUCU_URL = "https://web-production-b5bbc.up.railway.app"` de EXE içinde. Saldırgan URL + şifreyi birlikte bilirse direkt API'ye saldırabilir.

---

### Gerçek Saldırı Senaryosu (Adım Adım)

```
1. Saldırgan EXE'yi indirir (web siteden download düğmesi var!)
2. Process Hacker ile çalışan EXE'nin heap dump'ını alır
3. Dump içinde "admin1234" stringini bulur (şifresiz Python nesneleri heap'te görünür)
4. Railway URL'i de bulur
5. Python script yazar:
   POST /api/aktive-et → {"lisans_kodu": "OBY-XXXX-XXXX-XXXX", "hwid": "KENDI_HWID"}
   X-App-Secret: admin1234
6. Sunucu "geçerli" döndürür
7. Ömür boyu lisans ücretsiz aktive edilmiş olur
```

---

### Düzeltme — 3 Katmanlı Çözüm

#### Katman 1: Şifreyi Güçlendir (Minimum)

```python
# ❌ ESKİ
UYGULAMA_SIFRESI = "admin1234"

# ✅ YENİ — en az 32 karakter, rastgele, anlamsız
UYGULAMA_SIFRESI = "xK9#mP2$vL7@nQ4!wR1^tY6&uJ3*oI8%"
```

Ama bu hâlâ sabit ve EXE içinde — temel sorun çözülmüyor.

#### Katman 2: HMAC-Tabanlı Dinamik İmza (Güçlü)

Şifreyi göndermek yerine, her istekte **imza** gönder:

```python
import hmac, hashlib, time

GIZLI_ANAHTAR = b"xK9#mP2$vL7@nQ4!wR1^tY6&uJ3*oI8%"  # 32 byte

def _api_imzasi_uret(endpoint: str, ts: int) -> str:
    """Her istekte farklı imza üretir — replay saldırısı imkansız"""
    mesaj = f"{endpoint}:{ts}:{HWID[:8]}".encode()
    return hmac.new(GIZLI_ANAHTAR, mesaj, hashlib.sha256).hexdigest()[:24]

# İstek gönderirken:
ts = int(time.time())
imza = _api_imzasi_uret(endpoint, ts)
headers = {
    "X-Timestamp": str(ts),
    "X-Signature": imza,
    # Artık X-App-Secret YOK
}

# Sunucu tarafında:
# 1. Timestamp kontrolü: abs(time.time() - ts) < 60 saniye → replay engeli
# 2. HMAC doğrulama
```

#### Katman 3: Nuitka ile Derleme (Ek Koruma)

`builder.py` şu an PyInstaller kullanıyor (bytecode tabanlı). Nuitka C'ye derler:

```bash
pip install nuitka
nuitka --onefile --windows-disable-console \
       --include-data-file=logo.ico=logo.ico \
       gateway_v5.0.py

# Sonuç: gerçek native binary
# UYGULAMA_SIFRESI string olarak görünmez
# Reverse engineering çok daha zor
```

---

## 📊 Özet Tablo

| Sorun | Koddaki Satır | Risk Seviyesi | Etkilenecek Yer | Düzeltme Zorluğu |
|---|---|---|---|---|
| `CERT_NONE` (3 yerde) | 666, 1316, 2290 | 🔴 YÜKSEK | Tüm API istekleri + Python indirme | ⭐ Çok Kolay (2 satır sil) |
| In-memory session | helpers.py:185 | 🟡 ORTA | Her yeni deploy'da login kayıpları | ⭐⭐ Orta (DB session) |
| Namespace `v4` | 1678 | 🟡 ORTA | Mevcut müşterilerde SCADA bağlantı kopar | ⭐ Kolay (1 satır) |
| `poll_cap = 120` | 1735 | 🟢 DÜŞÜK | Büyük tesisler yavaş yenileme | ⭐ Kolay (değer artır) |
| `"admin1234"` | 38 | 🔴 YÜKSEK | API yetkisiz erişim | ⭐⭐⭐ Zor (HMAC sistemi) |

---

## ✅ Öncelik Sırası (Satışa Çıkmadan Önce)

**1. HEMEN YAP (1 saat):**
- `"admin1234"` → Güçlü rastgele string (en az 32 karakter)
- `CERT_NONE` → 3 yerdeki 2 satırı sil
- `VERSIYON = "5.0"` yap
- Namespace `v4` → `v5` yap (saha testi henüz yeni, müşteri yok)

**2. KISA VADELİ (1-2 gün):**
- Session'ı SQLite'a taşı
- `poll_cap` dinamik hesaplamaya geç

**3. ORTA VADELİ (2-4 hafta):**
- `X-App-Secret` → HMAC imzalı dinamik token
- Nuitka derlemesine geç
- Railway'e Redis ekle
