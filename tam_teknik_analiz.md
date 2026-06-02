# 🔬 Nautilus OPC Gateway Pro — TAM TEKNİK REFERANS BELGESI

> Versiyon: 5.0 | Şirket: **Nautilus Technology** | Analiz: Canlı kod çalıştırma ile doğrulanmış

---

## PROJE TAKIM BİLGİLERİ

| Rol | Kişi | İletişim |
|---|---|---|
| **CEO / Kurucu Ortak** | Kadir Han Çobanoğlu | +90 544 888 96 94 / kcobanoglu@hotmail.com |
| **CTO / Kurucu Ortak** | Remzican Onur Altunbaş | +90 553 016 68 47 / onnuraltunbass@gmail.com |

---

## 1. PROJE MİMARİSİ — TAM GENEL BAKIŞ

```
┌─────────────────────────────────────────────────────────────┐
│                    NAUTILUS GATEWAY SİSTEMİ                  │
└─────────────────────────────────────────────────────────────┘

  [PLC / SCADA / DCS]
       │ OPC DA (COM/DCOM, 32-bit Windows)
       ▼
  ┌─────────────────────────┐
  │  OPCGateway.exe         │  ← Python 32-bit, PyQt5, asyncua
  │  (Nautilus_Gateway.exe) │
  │  ─────────────────────  │
  │  • LisansYoneticisi     │──→ HTTPS POST ──→ [Railway.app Sunucu]
  │  • OfflineLisansYon.    │                         │
  │  • GatewayWorker        │                   [FastAPI Backend]
  │  • GatewayApp (GUI)     │                   [SQLite/PostgreSQL]
  │  • KurulumPenceresi     │                   [Telegram Bot]
  └─────────────────────────┘
       │ OPC UA TCP (asyncua)
       ▼
  [Modern SCADA / ERP / IoT / MES / Bulut]
```

---

## 2. DOSYA ENVANTERİ — EKSİKSİZ

### OPC/ (Ana Proje)

| Dosya | Boyut | Açıklama |
|---|---|---|
| `Kaynak Kodlar/HWID_version/gateway_v5.0.py` | 99,817 byte / 2432 satır | **Ana kaynak kod** |
| `Kaynak Kodlar/HWID_version/KURULUM_KILAVUZU.md` | 3,510 byte | Kurulum ve deploy kılavuzu |
| `sifreleme/builder.py` | 3,651 byte | EXE derleme + şifreleme scripti |
| `sifreleme/ver.txt` | 884 byte | Windows EXE versiyon meta |
| `sifreleme/app.manifest` | 982 byte | Windows UAC manifest |
| `setup/kurulum_scripti.iss` | 3,079 byte | Inno Setup installer scripti |
| `setup/lisans.txt` | 8,541 byte | EULA son kullanıcı lisans sözleşmesi |
| `UI/arayuz1.py` + `arayuz1.ui` | ~10KB | Alt arayüz bileşenleri |
| `UI/arayuz2.py` + `arayuz2.ui` | ~10KB | Alt arayüz bileşenleri |
| `OPC_Gateway_Pro.spec` | 861 byte | PyInstaller spec dosyası |
| `dosyalar/OPC_Gateway_Pro.exe` | **83.3 MB** | Dağıtım EXE (sunucuda) |
| `setup/dist/OPC_Gateway_Pro.exe` | **41.9 MB** | Kurulum paketi EXE |
| `cikti.uap` | 97,039 byte | Çıktı/arşiv dosyası |

### opc-lisans-sunucu/ (Web Backend)

| Dosya | Boyut | Açıklama |
|---|---|---|
| `lisans_sunucu.py` | 4,765 byte | FastAPI uygulama giriş noktası |
| `database.py` | 11,778 byte | Tüm DB modelleri + migration |
| `helpers.py` | 7,960 byte | Yardımcı fonksiyonlar + Telegram |
| `auth.py` | 2,487 byte | Panel kimlik doğrulama |
| `routes_client.py` | 3,090 byte | EXE API (2 endpoint) |
| `routes_kullanici.py` | 12,397 byte | Kullanıcı API (14 endpoint) |
| `routes_panel.py` | 34,124 byte | Admin panel API (36 endpoint) |
| `routes_html.py` | 1,800 byte | HTML sayfa routing |
| `html_panel.py` | 91,416 byte | Admin panel HTML (tek dosya) |
| `html_site_template.dat` | 91,788 byte | Müşteri web sitesi HTML |
| `html_site_css.dat` | 20,120 byte | Müşteri web sitesi CSS |
| `html_site.py` | 523 byte | .dat dosyalarını yükler |
| `static/logo.png` | 84,004 byte | Site logosu |
| `static/adres_data.js` | 11,577 byte | Türkiye il/ilçe verisi |
| `requirements.txt` | 130 byte | Python bağımlılıkları |
| `Procfile` | 58 byte | Railway deploy komutu |
| `test_api.ps1` | 1,742 byte | PowerShell API test scripti |
| `test_api.py` | 849 byte | Python API test scripti |

---

## 3. PERFORMANS ANALİZİ — GERÇEK SAYILAR (Kod Çalıştırılarak Hesaplandı)

### 3.1 Etiket Kapasitesi ve Poll Hızı

```
 ETİKET SAYISI  →  poll_cap  →  tam_tur_döngü  →  ort. yenileme
 ─────────────────────────────────────────────────────────────────
     10 etiket  →      6     →       2 döngü   →  ~0.50 saniye
     50 etiket  →     10     →       5 döngü   →  ~1.25 saniye
    100 etiket  →     20     →       5 döngü   →  ~1.25 saniye
    500 etiket  →    100     →       5 döngü   →  ~1.25 saniye  ✦ TATLİ NOKTA
  1,000 etiket  →    120     →       9 döngü   →  ~2.25 saniye
  2,000 etiket  →    120     →      17 döngü   →  ~4.25 saniye
  5,000 etiket  →    120     →      42 döngü   →  ~10.5 saniye
 10,000 etiket  →    120     →      84 döngü   →  ~21.0 saniye
```

> **Formül:** `poll_cap = min(120, max(6, n ÷ 5))`  
> Yenileme süresi = `⌈n ÷ poll_cap⌉ × 250ms`

### 3.2 Hedeflenen Yenileme Süresine Göre Maksimum Etiket

```
  Hedef Yenileme  →  Teorik Maks Etiket
  ────────────────────────────────────
   1 saniye  →     480 etiket
   2 saniye  →     960 etiket
   5 saniye  →   2,400 etiket   ← Pratik üst sınır (çoğu uygulama)
  10 saniye  →   4,800 etiket
  30 saniye  →  14,400 etiket
  60 saniye  →  28,800 etiket   ← Teorik max
```

> ⚠️ **Önemli Not:** Bu hesaplamalar teorik limitlerdir. Gerçek limit OPC DA sunucusunun cevap hızına bağlıdır. Yavaş bir OPC DA sunucu, auto-tune mekanizmasının `poll_cap`'i otomatik olarak düşürmesine neden olur.

### 3.3 Auto-Tune Mekanizması (Donanım Bağımsız)

```
  Okunan süre (ms)  →  poll_cap değişimi
  ─────────────────────────────────────
   > 900ms          →   -8  (ağır yük, düşür)
   > 700ms          →   -4  (orta yük, biraz düşür)
   < 250ms          →   +3  (hafif yük, artır)
   < 450ms          →   +1  (makul yük, yavaş artır)
  
  Aralık: 6 (min) ↔ 120 (max)
```

Bu mekanizma sayesinde program, eski ve zayıf donanımlarda da kendini otomatik ayarlar.

---

## 4. EXPONENTIAL BACKOFF ALGORİTMASI

Bir etiketten veri gelmeye başlayınca:

```
  fail_streak  →  Poll Aralığı
  ─────────────────────────────
  0            →   200ms  (normal)
  1            →   400ms
  2            →   800ms
  3            →  1600ms
  4            →  3200ms
  5            →  6400ms
  6+           → 10000ms  (10 saniye - tavan)

  Başarı olunca: anında 200ms'e sıfırla
```

---

## 5. GROUP TIMEOUT FONKSİYONU

`_group_timeout(n) = max(0.25, min(2.5, 0.10 + 0.035 × n))`

```
  Grup Büyüklüğü  →  Timeout
  ──────────────────────────
    1 etiket      →  0.250s
    5 etiket      →  0.275s
   10 etiket      →  0.450s
   20 etiket      →  0.800s
   30 etiket      →  1.150s
   50 etiket      →  1.850s
   70 etiket      →  2.500s  (tavan)
  100 etiket      →  2.500s  (tavan)
```

---

## 6. OKUMA STRATEJİSİ — 3 KATMANLI FALLBACK

```
  1. BULK READ (en hızlı)
     └── Tüm etiketleri tek seferde oku
     └── Başarı → normalize → UA'ya yaz
     └── Başarısız veya %50+ missing → Bağlantıyı yeniden kur → Bir kez daha dene

  2. SPLIT FALLBACK (orta)
     └── Grubu ikiye böl, her yarıyı ayrı oku
     └── Timeout olan yarıyı tekrar ikiye böl
     └── Böylece kötü etiketler izole edilir

  3. PER-TAG READ (en yavaş, son çare)
     └── Tek tek etiket oku
     └── Başarısız → properties() ile dene
     └── Yine başarısız → (None, None, None) → backoff başlat
```

---

## 7. BELLEK KULLANIMI

```
  Etiket Sayısı  →  Ek RAM (tag_state + heap + cache)
  ──────────────────────────────────────────────────
       100       →  ~0.1 MB
       500       →  ~0.3 MB
     1,000       →  ~0.6 MB
     5,000       →  ~2.9 MB
    10,000       →  ~5.7 MB
```

> Python'ın kendisi ~30-50 MB, PyQt5 GUI ~20-40 MB, asyncua server ~10-20 MB.  
> 10,000 etiket için toplam: ~80-120 MB RAM.

---

## 8. GÜVENLİK KATMANLARI — 14 ADET

Canlı analizden elde edilen tam liste:

| # | Katman | Tür | Detay |
|---|---|---|---|
| 1 | HWID: CPU + SMBIOS UUID + MachineGuid | Online | SHA256(cpu::uuid::secret)[:32] |
| 2 | Anti-Spoofing HWID: MB Serial + Disk + GUID | Offline | HMAC-SHA256(key, raw) |
| 3 | HMAC-SHA256 aktivasyon imzası | Offline | hex[:16].upper() = 16 karakter |
| 4 | Challenge zaman damgası | Offline | ts // 600 → 10 dakikalık pencere |
| 5 | Burn-in listesi | Offline | İmza hash'i kalıcı dosyaya kaydedilir |
| 6 | Registry çift kayıt tutarlılık | Offline | File ≠ Registry → erişim engeli |
| 7 | XOR şifreli lisans dosyası | Offline | SHA256(key+"xor_v1") ile XOR |
| 8 | Saat geri alma tespiti | Offline | now < son_giris - 30s → soft-lock |
| 9 | IsDebuggerPresent (her 3sn) | Ortak | Windows kernel32 API |
| 10 | Timing attack tespiti | Ortak | sleep(0.01) > 0.1s → çıkış |
| 11 | Fernet-AES + marshal + Kiril alfabe | Ortak | builder.py ile EXE şifrelemesi |
| 12 | X-App-Secret header | Online | Her EXE→Sunucu isteğinde zorunlu |
| 13 | IP Ban sistemi | Sunucu | Ayrı tablo, soft/hard ban |
| 14 | 7 günlük offline grace + checkin | Online | Periyodik sunucu doğrulama |

---

## 9. OFFLİNE AKTİVASYON SİSTEMİ — DETAY

### Challenge Kodu Formatı
```
REQ-{base32(hwid[:8] + pack('>Q', ts_slot))}[:20]
Örnek: REQ-MFRGGZDFMYYTEAAAAAAA
```

### Aktivasyon Kodu Formatı
```
ACT-{SURE}D-{YETKİ}-{HMAC_İMZA}
Örnek: ACT-30D-FULL-3828803FF4CFB3F4

Bileşenler:
  ACT     → sabit önek
  30D     → 30 gün süre (1-365 arası)
  FULL    → yetki seviyesi (FULL / READ / DEMO)
  16 hex  → HMAC-SHA256(key, "challenge|sure|yetki")[:16].upper()
```

### Güvenli Key Yapısı (Parçalanmış)
```python
_SK_P1 = bytes([0x4f,0x50,0x43,0x5f,0x47,0x57,0x5f,0x4f])  # "OPC_GW_O"
_SK_P2 = bytes([0x46,0x46,0x4c,0x49,0x4e,0x45,0x5f,0x4b])  # "FFLINE_K"
_SK_P3 = SHA256(b"opcgw_offline_2026_salt_v1")[:16]
OFFLINE_SECRET_KEY = _SK_P1 + _SK_P2 + _SK_P3  # 32 byte toplam
```

> Aynı key hem EXE içine hem sunucu `database.py`'e gömülüdür. İmza doğrulama serverless yapılabilir.

---

## 10. VERİTABANI ŞEMASI — TAM

```
lisanslar              ← Ana lisans tablosu
  ├── id (UUID)
  ├── lisans_kodu      ← AYL-XXXX-XXXX-XXXX (unique)
  ├── hwid             ← Bilgisayar parmak izi (32 karakter)
  ├── musteri_adi
  ├── musteri_email
  ├── tur              ← aylik / yillik / omur_boyu / deneme / Offline
  ├── aktif (bool)
  ├── olusturma_tar
  ├── bitis_tarihi     ← NULL = ömür boyu
  ├── notlar
  ├── son_checkin
  ├── aktivasyon_tar
  ├── iptal_nedeni
  ├── iptal_tarihi
  ├── uretilen_tip     ← "online" / "offline"
  ├── istek_kodu_db    ← Offline: REQ-... kodu
  └── sure_gun_db      ← Offline: kaç gün

kullanicilar           ← Müşteri web paneli hesapları
  ├── id (UUID)
  ├── ad_soyad
  ├── email (unique)
  ├── sifre_hash       ← SHA256
  ├── email_dogrulandi
  ├── kayit_tar
  ├── son_giris
  ├── son_ip
  ├── firma_ismi
  └── detayli_adres    ← İl/İlçe/Mahalle/No

lisans_talepler        ← Müşterinin lisans başvurusu
  ├── id, kullanici_id
  ├── ad_soyad, email
  ├── tur              ← İstenen paket
  ├── durum            ← "beklemede" / "onaylandi" / "reddedildi"
  ├── talep_tipi       ← "online" / "offline"
  ├── istek_kodu       ← Offline: REQ-...
  └── aktivasyon_kodu  ← Offline: ACT-...

mesajlar               ← Admin↔Müşteri chat
  ├── id, kullanici_id
  ├── gonderen         ← "admin" / "kullanici"
  ├── icerik
  ├── tarih
  └── okundu (bool)

ip_banlar              ← IP kara liste
  ├── id, ip (unique)
  ├── sebep
  ├── tarih
  └── aktif (bool)

uyelik_turleri         ← Lisans paket tanımları
  ├── id
  ├── kod              ← "aylik", "yillik" vb.
  ├── ad, aciklama
  ├── aktif, sira
  ├── sure_gun         ← 0 = ömür boyu
  ├── prefix           ← "AYL", "YIL", "OBY", "DEN"
  └── is_offline (bool)

panel_kullanicilari    ← Alt yöneticiler
  ├── id, kullanici_adi, isim_soyad, email
  ├── sifre_hash
  ├── is_admin
  ├── yetki_lisans_olustur
  ├── yetki_lisans_sil
  ├── yetki_hwid_sifirla
  ├── yetki_sure_uzat
  ├── yetki_talep_onayla
  ├── yetki_kullanici_ekle
  ├── yetki_mesaj_yaz
  ├── yetki_ip_ban
  ├── yetki_uyelik_tur
  ├── yetki_offline_paket_yonetimi
  ├── yetki_offline_lisans_uret
  ├── telegram_chat_id
  ├── telegram_bildirim_alabilir
  ├── son_giris
  └── son_cikis

loglar                 ← EXE API erişim geçmişi
  ├── id, tarih, islem
  ├── lisans_kodu, hwid
  ├── ip, mesaj

panel_loglar           ← Panel işlem geçmişi
  ├── id, tarih
  ├── kullanici_adi
  ├── islem, detay

ayarlar                ← Sistem ayarları (tek satır)
  ├── id
  ├── admin_kullanici  ← Değiştirilebilir ana admin
  ├── admin_sifre_hash
  ├── son_exe_hash     ← Deploy kontrolü
  └── son_surum_tarihi
```

---

## 11. API ENDANTERİ — 60 ENDPOINT

### EXE API (2 endpoint)
```
POST /api/aktive-et   → Lisans kodunu HWID ile eşleştir, aktivasyonu kaydet
POST /api/kontrol     → Periyodik doğrulama, son_checkin güncelle
```

### Kullanıcı API (14 endpoint)
```
POST /api/kayit                → Hesap oluştur (firma_ismi, adres dahil)
POST /api/giris                → Giriş → httponly session cookie
POST /api/cikis                → Session sil
GET  /api/profil               → Lisans durumu, indirme linki, EXE hash
POST /api/talep-olustur        → Online veya offline lisans talebi
GET  /api/benim-taleplerim     → Kullanıcının talep geçmişi
POST /api/mesaj-gonder         → Admin'e mesaj yaz
GET  /api/mesajlarim           → Chat geçmişi (okundu işareti)
POST /api/lisansimi-iptal-et   → Kullanıcı kendi lisansını iptal edebilir
GET  /api/lisans-gecmisim      → Tüm lisans geçmişi (online + offline)
GET  /api/uyelik-turleri-public→ Aktif paketler (genel erişim)
GET  /api/program-indir        → EXE indirme (giriş zorunlu)
GET  /api/public-info          → EXE hash + son güncelleme tarihi
POST /api/sifre-degistir       → Şifre güncelle
```

### Panel API (36 endpoint)
```
CRUD Lisans:     lisans-olustur, iptal, lisans-sil, hwid-sifirla, sure-uzat
CRUD Talep:      talep-guncelle, talep-sil, talep-toplu-sil
CRUD Mesaj:      admin-mesaj-gonder, mesaj-sil, mesaj-konusma-sil, mesaj-toplu-sil
CRUD Kullanıcı:  kullanicilar, kullanici-sil, kullanici-duzenle
CRUD Yetkili:    yetkili-ekle, yetkili-sil, yetkililer, yetkili-guncelle
Offline:         offline-lisans-uret
İzleme:          loglar, panel-loglari, ip-banlar, mesajlar-ozet, kullanici-mesajlar
IP:              ip-ban-ekle, ip-ban-kaldir
Paket:           uyelik-tur-ekle, uyelik-tur-guncelle, uyelik-tur-sil, uyelik-turleri
Sistem:          giris, cikis, admin-guncelle, iptal-istatistikleri
```

---

## 12. WEB SİTESİ SAYFALARI (10 sayfa)

| URL | İçerik |
|---|---|
| `/` | Anasayfa (hero, özellikler, CTA) |
| `/kayit` | Kayıt formu (ad, firma, e-posta, il/ilçe, adres) |
| `/giris` | Giriş formu + "Beni Hatırla" seçeneği |
| `/dashboard` | Kullanıcı paneli (lisans durumu, indirme, mesaj, geçmiş) |
| `/planlar` | Paket listesi (dinamik, DB'den çekiliyor) |
| `/offline-aktivasyon` | REQ-kodu ile offline lisans talebi |
| `/hakkimizda` | Şirket profili + ekip kartları |
| `/iletisim` | WhatsApp + telefon + e-posta (iki kurucu) |
| `/gereksinimler` | Donanım gereksinimleri (min/önerilen) |
| `/panel` | Tam admin yönetim paneli |

**Özel web sitesi özellikleri:**
- Karanlık/Aydınlık tema toggle
- Çerez onay banner'ı + tercih modali (GDPR uyumlu)
- Google Site Verification meta etiketi
- Türkiye il/ilçe seçicisi (adres verisi: `adres_data.js` - 11.5KB)
- VirusTotal raporu linki (EXE güven göstergesi)
- "YENİ SÜRÜM YAYINDA" banner'ı (24 saat içinde deploy varsa)

---

## 13. EXE DERLEME ve KORUMA SİSTEMİ (builder.py)

```
Adım 1: gateway_v5.0.py oku
Adım 2: compile() ile bytecode'a çevir
Adım 3: marshal.dumps() ile seri hale getir
Adım 4: Fernet.generate_key() → AES-128-CBC anahtarı üret
Adım 5: Fernet(key).encrypt(bytecode) → şifreli payload
Adım 6: base64.b64encode() → standart base64
Adım 7: BASE64_ALPHABET → CUSTOM_ALPHABET çeviri
         (Kiril + Çin + sembol karakterler - 64 karakter özel alfabe)
Adım 8: Loader wrapper Python dosyası yaz:
         • IsDebuggerPresent kontrolü
         • Timing attack tespiti (sleep > 0.1s)
         • Alfabe ters çevir → base64 → Fernet decrypt → marshal.loads → exec()
Adım 9: PyInstaller --onefile --noconsole → tek EXE

Korunan alanlar:
  • Şifreli key (Fernet random, her derlemede farklı)
  • OFFLINE_SECRET_KEY (kaynak kodda parçalı, EXE'de şifreli)
  • SUNUCU_URL ve UYGULAMA_SIFRESI (şifreli payload içinde)
```

---

## 14. SİSTEM GEREKSİNİMLERİ (Web Sitesinden)

| | Minimum | Önerilen |
|---|---|---|
| **OS** | Windows 10 / Server 2016 | Windows 11 / Server 2022 |
| **CPU** | Çift çekirdek 2.0 GHz (i3/Ryzen 3) | 4 çekirdek 3.0 GHz (i5/Ryzen 5) |
| **RAM** | 2 GB | 8 GB+ |
| **Depolama** | 150 MB (yazılım) | 1 GB SSD (CSV loglama) |
| **GPU** | Paylaşımlı grafik yeterli | Gereksiz |
| **Ağ** | Sabit IP / LAN | Gigabit Ethernet (1 Gbps) |
| **Etiket** | Max ~1,000 etiket | 10,000+ etiket |

---

## 15. TELEGRAM İSTİHBARAT SİSTEMİ

Her kritik işlemde şu bilgiler gönderilir:
- 🚨 **İşlem türü** (lisans üretildi, talep onaylandı, giriş yapıldı, crash vb.)
- 👤 **İşlemi yapan** (admin adı veya müşteri adı)
- 📄 **Detay** (lisans kodu, müşteri, süre vb.)
- 🌐 **IP + Coğrafi Konum** (ip-api.com ile otomatik çözümlenir)
- 🕒 **Tarih/Saat** (UTC+3, Türkiye saatiyle)

**Tetikleyen olaylar:**
- Sunucu başlatma (`startup`) ve kapanma (`shutdown`)
- Her crash (global exception handler)
- Yeni EXE deploy (hash değişimi tespiti)
- Admin panel girişi
- Yeni kullanıcı kaydı
- Online/offline lisans talebi
- Talep onaylama/reddetme
- Lisans iptali
- HWID sıfırlama
- IP ban ekleme/kaldırma
- Alt yetkili ekleme/güncelleme/silme
- Müşteriye mesaj gönderme

**Çoklu Telegram alıcı desteği:**
- Ana `TELEGRAM_CHAT_ID` (ortam değişkeni)
- Her alt yöneticinin kendi `telegram_chat_id`'si (kişisel bildirim)

---

## 16. BİLİNEN KISITLAMALAR VE RİSKLER

| Konu | Detay |
|---|---|
| **32-bit Python zorunluluğu** | OPC DA (OpenOPC) yalnızca 32-bit COM/DCOM ile çalışır. Kaynak `sys.maxsize > 2**32` kontrolü yapıyor ve uyarıyor. |
| **Windows Only** | COM/DCOM ve winreg kütüphaneleri Windows'a özeldir. Linux/Mac'te çalışmaz. |
| **SSL doğrulama kapalı** | `ctx.verify_mode = ssl.CERT_NONE` — Railway'de self-signed cert uyumu için. Prod'da CA sertifikasıyla düzeltilmeli. |
| **Session in-memory** | `_sessions = {}` — Sunucu yeniden başlarsa tüm oturumlar kapanır. Kalıcı session için Redis gibi harici store gerekir. |
| **SQLite single-file** | Yüksek eş zamanlı isteklerde (>100 aktif kullanıcı) PostgreSQL'e geçiş şart (zaten `DATABASE_URL` env ile destekleniyor). |
| **Panel Auth (Bearer)** | `kullanici:sifre` formatında Bearer token — HTTP üzerinde plaintext risk. HTTPS zorunlu (Railway varsayılan HTTPS). |
| **poll_cap tavan = 120** | Kaynak kodda `MAX_POLLED_PER_CYCLE = 120` hardcoded. Çok büyük tesisler için bu değerin artırılması gerekebilir. |
| **OPC UA namespace** | `http://opcgateway/v4` — v5.0 kodda hâlâ v4 namespace. İleride uyumsuzluk yaratabilir. |

---

## 17. DEPLOY AKIŞI

```
Geliştirici          GitHub               Railway.app          Müşteri
    │                   │                      │                   │
    │──push gateway──→  │                      │                   │
    │  + lisans sunucu  │                      │                   │
    │                   │──webhook deploy──→   │                   │
    │                   │                      │── startup_event ──│
    │                   │                      │   Telegram: deploy│
    │                   │                      │   EXE hash kontrol│
    │                   │                      │                   │
    │──builder.py──→ Nautilus_Gateway.exe       │                   │
    │   (şifrele)       │                      │                   │
    │                   │                      │                   │
    │──upload EXE──→ dosyalar/ klasörü ─────→  │                   │
    │                   │                      │                   │
    │──panel/lisans-olustur → lisans kodu ──→   │   ──→ Müşteriye  │
    │                   │                      │       e-posta/SMS │
    │                   │                      │                   │
    │                   │                      │   ←─ EXE aç ──────│
    │                   │                      │   ←─ /api/aktive-et
    │                   │                      │   Telegram: aktivasyon
```

---

## 18. ÖZET İSTATİSTİKLER (Anlık Sayılar)

| Metrik | Değer |
|---|---|
| Ana kaynak kodu (satır) | **2,432 satır** |
| Ana kaynak kodu (byte) | **99,817 byte** |
| Toplam API endpoint | **60 endpoint** |
| Veritabanı tablosu | **10 tablo** |
| Güvenlik katmanı | **14 katman** |
| Web sitesi sayfası | **10 sayfa** |
| Yetki türü (panel) | **11 granüler yetki** |
| Lisans türü | **5 (Deneme/Aylık/Yıllık/ÖmürBoyu/Offline)** |
| Derleme EXE boyutu | **41.9 MB (kurulum) / 83.3 MB (dağıtım)** |
| Maks teorik etiket (5s yenileme) | **~2,400 etiket** |
| Maks teorik etiket (60s yenileme) | **~28,800 etiket** |
| Pratik önerilen etiket sayısı | **<500 etiket (1.25s yenileme)** |
