# 🏭 Nautilus OPC Gateway Pro — Kapsamlı Proje Analizi

---

## 🔷 BÖLÜM 1: TEKNİK ANALİZ (Mühendis / Geliştirici Seviyesi)

### Proje Genel Yapısı

Bu proje iki ana bileşenden oluşmaktadır:

| Bileşen | Konum | Teknoloji |
|---|---|---|
| **Gateway İstemcisi (EXE)** | `OPC/Kaynak Kodlar/HWID_version/gateway_v5.0.py` | Python 3.x (32-bit), PyQt5, asyncua, OpenOPC |
| **Lisans Sunucusu (Backend)** | `opc-lisans-sunucu/` | Python, FastAPI, SQLAlchemy, SQLite/PostgreSQL |

---

### 1.1 Gateway İstemcisi — Teknik Detay

**Temel İşlev:**
OPC DA (Data Access, eski COM/DCOM tabanlı endüstriyel protokol) → OPC UA (Unified Architecture, modern TCP tabanlı endüstriyel protokol) dönüştürücüsü. Windows ortamında çalışır.

**Mimari Akış:**
```
OPC DA Sunucu (SCADA/PLC)
        │
        │ COM/DCOM (OpenOPC Python kütüphanesi)
        ▼
 GatewayWorker (QThread)
   • _toplu_oku() → asyncio async bulk read
   • Adaptif poll scheduler (heapq tabanlı)
   • Auto-tune: poll_cap 6-120 arası otomatik ayarlanır
   • Hataya dayanıklı: split-fallback, poisoned connection tespiti
        │
        │ asyncua (OPC UA TCP)
        ▼
 OPC UA Server: opc.tcp://[IP]:[PORT]/
   • Namespace: http://opcgateway/v4
   • Node ağacı: Objects → Saha_Verileri → [Tag_Adı]
   • Yetki seviyesine göre write enable/disable
```

**Kritik Teknik Özellikler:**

**Performans Optimizasyonları:**
- `ThreadPoolExecutor(max_workers=1)` — COM thread safety için aynı thread'den okuma
- Adaptif poll scheduling: başarısız tag için exponential backoff (2^n × 200ms, max 10s)
- Bulk read → split fallback → per-tag fallback hiyerarşisi
- GUI güncelleme throttle: 2 Hz (500ms batching)
- CSV log: 1 Hz write (buffer flush)
- Otomatik poll_cap ayarlama: read_elapsed_ms değerine göre ±3-8 değişim

**OPC DA Okuma Normalizasyon:**
- `_normalize_read()`: hem `(value, quality, timestamp)` hem `(tag, value, quality, timestamp)` formatını destekler
- `_coerce_numeric()`: bool, int, float, str → float dönüşümü (virgüllü sayılar dahil)
- "Poisoned connection" tespiti: bulk read'de %50+ missing value → client yeniden oluştur

---

### 1.2 Lisans Sistemi — İki Katmanlı Mimari

#### Katman A: Online Lisans (HWID + Sunucu)

```
EXE Başlatıldı
      │
      ├── internet_var_mi()? ─── NO ──→ Offline Akış
      │
     YES
      │
      ▼
LisansYoneticisi.dogrula()
      │
      ├── Dosya yok? → AktivasyonPenceresi (lisans kodu girişi)
      ├── HWID uyuşmuyor? → lisans sil + hata
      ├── Süre dolmuş? → _sunucu_checkin()
      │       ├── internet yok → gecerli (offline grace)
      │       └── sunucu iptal → hata
      └── gecerli → GatewayApp başlat
                         │
                   LisansKontrolcusu (QThread)
                   her 10 saniyede /api/kontrol POST
                   iptal → lisans sil + AktivasyonPenceresi
```

**HWID Üretim Algoritması:**
```python
raw = f"{cpu_id}::{smbios_uuid}::{UYGULAMA_SIFRESI}"
hwid = SHA256(raw)[:32].upper()
# Fallback: MachineGuid kullanılır
```

**API Güvenliği:**
- Her istekte `X-App-Secret` header kontrolü (`UYGULAMA_SIFRESI`)
- SSL doğrulama devre dışı (self-signed cert uyumu için)
- 7 günde bir zorunlu server checkin (offline grace period)

#### Katman B: Offline Lisans (Air-Gapped)

**HWID Üretimi (Anti-Spoofing):**
```python
raw = f"{BaseBoardSerialNumber}|{MachineGuid}|{DiskVolumeSerial}"
hwid_hash = HMAC-SHA256(OFFLINE_SECRET_KEY, raw)
```

**Challenge-Response Protokolü:**
```
Müşteri:  REQ-{base32(hwid[:8] + timestamp_slot)}
Satıcı:   imza = HMAC-SHA256(secret, challenge|süre|yetki)[:16]
          ACT-{süre}D-{yetki}-{imza}
```

**Güvenlik Katmanları:**
1. HMAC-SHA256 imza doğrulama
2. Challenge içindeki HWID prefix kontrolü
3. Burn-in listesi (tek kullanımlık imza takibi)
4. Registry çift kayıt (dosya/registry tutarlılık kontrolü)
5. XOR şifreli dosya (OFFLINE_SECRET_KEY türevli)
6. Saat geri alma tespiti (son_giris_ts – 30sn tolerans)
7. `IsDebuggerPresent()` kontrolü (her 3 saniyede periyodik)

**Yetki Seviyeleri:**
- `FULL`: Tam erişim, OPC UA tag'lere yazma açık
- `READ`: Salt okunur, tag'ler writable değil
- `DEMO`: Ticari kullanım yasak, başlıkta uyarı

---

### 1.3 Backend Sunucu — API Mimarisi

**Framework:** FastAPI + SQLAlchemy + SQLite (prod: PostgreSQL)  
**Deploy:** Railway.app (Procfile: `uvicorn lisans_sunucu:app`)

**Veritabanı Şeması:**

| Tablo | Açıklama |
|---|---|
| `lisanslar` | Lisans kayıtları, HWID bağlama, süre |
| `kullanicilar` | Müşteri hesapları, oturum yönetimi |
| `lisans_talepler` | Online/offline lisans talepleri |
| `mesajlar` | Admin↔müşteri chat sistemi |
| `ip_banlar` | IP bazlı erişim engeli |
| `uyelik_turleri` | Lisans paket tanımları (prefix, süre) |
| `panel_kullanicilari` | Alt yönetici hesapları, granüler yetki |
| `panel_loglar` | Panel işlem geçmişi |
| `loglar` | EXE API erişim logları |
| `ayarlar` | Admin kimlik bilgileri, EXE hash takibi |

**API Route Grupları:**

| Router | Prefix | Açıklama |
|---|---|---|
| `routes_client` | `/api/` | EXE'nin kullandığı endpointler |
| `routes_kullanici` | `/api/` | Müşteri web panel API |
| `routes_panel` | `/panel/` | Admin panel API |
| `routes_html` | `/` | HTML sayfa sunumu |

**İstihbarat Sistemi (Telegram):**
Her kritik işlemde Telegram Bot API'ye bildirim:
- IP adresi + ip-api.com'dan coğrafi konum
- İşlemi yapan kişi, tarih/saat
- Sunucu crash'leri, yeni deploy, yeni kullanıcı kaydı vb.

**Panel Yetki Matrisi (Granüler):**
```
Ana Admin → tam yetki
Alt Yönetici → seçili yetkiler:
  lisans_olustur | lisans_sil | hwid_sifirla | sure_uzat
  talep_onayla | kullanici_ekle | mesaj_yaz | ip_ban
  uyelik_tur | offline_paket_yonetimi | offline_lisans_uret
```

---

### 1.4 EXE Derleme ve Kod Koruma Sistemi

**`sifreleme/builder.py` — Fortress Builder:**
1. Kaynak kod → Python bytecode (`marshal.dumps(compile(...))`)
2. Fernet şifrelemesi (AES-128-CBC)
3. Özel alfabe ile base64 encoding (Kiril + Çin + sembol karakterler)
4. Loader wrapper → PyInstaller `--onefile --noconsole`
5. Anti-debug: `IsDebuggerPresent` + timing attack tespiti

**Kurulum Scripti (`kurulum_scripti.iss` — Inno Setup):**
- Uygulama adı: **Nautilus OPC Gateway**
- Publisher: **Nautilus Technology**
- Offline kurulum: Python 3.13 + pip wheels dahil
- 3 aşamalı kurulum: Python → kütüphaneler → DLL kaydı

---

## 🔷 BÖLÜM 2: PAZARLAMA / SATIŞ TANITIMI

### Nautilus OPC Gateway Pro — Endüstriyel Veri Köprüsü

**Ürün Pozisyonu:**  
Fabrikalar ve endüstriyel tesislerdeki eski OPC DA sistemleri ile modern OPC UA altyapısı arasındaki uçurumu kapatmak için tasarlanmış, ticari lisanslı bir yazılım ürünüdür.

---

**🎯 Hangi Problemi Çözüyor?**

Dünyada milyonlarca endüstriyel kontrol sistemi (PLC, SCADA, DCS) yıllardır kullanılan **OPC DA** protokolünü kullanmaktadır. Ancak bu protokol:
- Yalnızca Windows COM/DCOM üzerinde çalışır
- Uzaktan erişim ve modern entegrasyona kapalıdır
- Endüstri 4.0 ve IoT platformlarıyla uyumsuzdur

**Nautilus OPC Gateway Pro**, bu eski sistemi herhangi bir değişiklik gerektirmeden **modern OPC UA** protokolüne çevirerek üretim verilerini dijital dönüşüm altyapılarına açar.

---

**🚀 Temel Özellikler ve Faydalar**

| Özellik | Fayda |
|---|---|
| OPC DA → OPC UA Köprü | Mevcut altyapıyı değiştirmeden modernleşme |
| Çevrimiçi + Çevrimdışı Lisans | İnternet kesintilerinde kesintisiz çalışma |
| HWID Tabanlı Güvenlik | Lisansın başka bilgisayara kopyalanması engellenir |
| PyQt5 Karanlık Tema Arayüz | Endüstriyel ortamlara uygun profesyonel görünüm |
| Sistem Tepsisi Entegrasyonu | Arka planda sessiz çalışma |
| Adaptif Veri Okuma | Ağ koşullarına göre otomatik performans optimizasyonu |
| Web Tabanlı Müşteri Paneli | Lisans talebi, mesajlaşma, program indirme |
| Admin Yönetim Paneli | Tek merkezden tüm müşterileri yönetme |
| Telegram Bildirimleri | Gerçek zamanlı işlem takibi |
| Granüler Yetki Sistemi | Ekip üyelerine özel yetki tanımlama |

---

**💼 Hedef Müşteri Kitlesi**

- Otomasyona geçiş sürecindeki **üretim tesisleri**
- Endüstri 4.0 dönüşümü yapan **sistem entegratörleri**
- Eski SCADA sistemlerini modernize eden **mühendislik firmaları**
- OPC tabanlı altyapısı olan **enerji, petrokimya, gıda, otomotiv** sektörleri

---

**📦 Lisans Modelleri**

| Paket | Süre | Özellikler |
|---|---|---|
| Deneme (DEN-) | 24 saat | Tam özellik, ücretsiz |
| Aylık (AYL-) | 30 gün | Tam erişim |
| Yıllık (YIL-) | 365 gün | Tam erişim, daha ekonomik |
| Ömür Boyu (OBY-) | Süresiz | En avantajlı seçenek |
| Offline | Esnek (1-365 gün) | İnternetsiz ortamlar için |

---

**🛡️ Neden Rakiplerden Farklı?**

✅ **Çevrimdışı Lisans** — Fabrika ağlarında internet erişimi yoksa bile çalışır  
✅ **Kurumsal Panel** — Alt yönetici, müşteri mesajlaşma, log takibi  
✅ **Gerçek Zamanlı İstihbarat** — Her işlem anında Telegram'a bildirim  
✅ **Sıfır Altyapı Değişikliği** — Mevcut OPC DA sunuculara dokunmaya gerek yok  
✅ **Yerli Destek** — Türkçe arayüz ve Türkçe destek  

---

## 🔷 BÖLÜM 3: BAŞLANGIÇ SEVİYESİ AÇIKLAMA

### "OPC Gateway Pro Nedir?" — Hiç Bilmeyenler İçin

Diyelim ki bir fabrikada eski model bir makine var. Bu makinenin sürekli ürettiği veriler var: sıcaklık kaç derece, motor kaç RPM'de dönüyor, üretim sayacı ne gösteriyor gibi bilgiler.

Bu bilgileri okumak için eski bir "dil" (OPC DA) kullanılıyor. Sorun şu: Bu eski dili yeni bilgisayarlar, telefonlar veya internet sistemleri anlamıyor. Sanki fabrikadaki makine eski Osmanlıca yazılarla not yazıyor ama modern sistemler bunu okuyamıyor.

---

**Bu Program Ne Yapıyor?**

Bu program bir **"tercüman"** görevi görüyor:

```
Eski Makine           Bu Program          Modern Sistem
(OPC DA dili)    →   (Gateway)       →   (OPC UA dili)
   [MAKINE]     ──────────────────►    [Fabrika Yönetim
                  "Anlayıp çeviriyor"    Sistemi / Bulut]
```

Yani eski ve yeni sistemler arasında otomatik çeviri yapıyor. Fabrika sahibi ne eski makineyi değiştirmek zorunda kalıyor, ne de yeni sistemi eski dile uyarlamak için para harcamak zorunda.

---

**Peki Bu Program Nasıl Satılıyor?**

Program bir ürün olduğu için, onu kullanmak isteyen kişilerin **lisans satın alması** gerekiyor. Bu tıpkı Microsoft Office'in ya da Adobe'nin abonelik sistemi gibi çalışıyor.

Sisteme dahil olan ikinci büyük parça da bu lisansları yöneten **web sitesi (sunucu)**:

1. **Siz (satıcı)** web sitesinden bir lisans kodu üretiyorsunuz (örn: `AYL-A3F2-9B1C-4E7D`)
2. Bu kodu müşteriye gönderiyorsunuz
3. Müşteri programı açıyor, bu kodu giriyor
4. Program internetten doğrulama yapıyor → kapılar açılıyor ✅

---

**Peki Ya İnternet Yoksa?**

Bazı fabrikalar internet bağlantısına sahip değildir (güvenlik nedeniyle kapalı ağ kullanırlar). Bunun için özel bir sistem var:

1. Müşteri program açar, bir "istek kodu" üretir (tıpkı bir banka işlem kodu gibi)
2. Bu kodu size (satıcıya) iletir (e-posta veya telefon ile)
3. Siz yönetim panelinden bir "aktivasyon kodu" üretirsiniz
4. Müşteri bu kodu programa girer → program internete ihtiyaç duymadan açılır ✅

---

**Güvenlik Nasıl Sağlanıyor?**

Program her bilgisayarın "parmak izini" alıyor (buna HWID deniyor). Bu parmak izi işlemciden, anakarttan ve sabit diskten çıkarılıyor. Bu sayede:

- Bir kişi lisansı alıp başkasına veremez
- Program sadece lisans satın alınan bilgisayarda çalışır
- Siz istediğiniz zaman bir lisansı iptal edebilirsiniz

Ek güvenlik: Eğer biri programı manipüle etmeye çalışırsa (debugger kullanırsa), program bunu anlayıp kendini kapatıyor.

---

**Yönetim Paneli Ne İş Yapar?**

Bir web sitesinde (admin panelinizde) şunları yapabilirsiniz:

- 🟢 Yeni lisans oluşturma ve gönderme
- 🔴 Ödeme yapmayan müşterinin lisansını iptal etme
- 📅 Lisans süresini uzatma
- 💬 Müşterilerle mesajlaşma
- 📊 Kim, ne zaman, nereden giriş yaptı takibi
- 🚫 İstenmeyen IP adreslerini engelleme
- 👥 Yardımcı çalışanlarınıza sınırlı yetki verme

Ve tüm bu işlemler anında Telegram'ınıza bildirim olarak geliyor!

---

## 📊 ÖZET TABLO

| Kategori | Detay |
|---|---|
| **Ürün Adı** | Nautilus OPC Gateway Pro |
| **Şirket** | Nautilus Technology |
| **Versiyon** | 5.0 |
| **Platform** | Windows (32-bit Python gerektiriyor) |
| **Lisans Sunucu** | Railway.app (bulut, sürekli çevrimiçi) |
| **Arayüz** | PyQt5 Karanlık Tema, Türkçe |
| **Protokoller** | OPC DA (giriş) → OPC UA TCP (çıkış) |
| **Güvenlik** | HWID, HMAC-SHA256, Debugger Engeli, Burn-in |
| **Lisans Türleri** | Deneme / Aylık / Yıllık / Ömür Boyu / Offline |
| **Backend** | FastAPI + SQLite/PostgreSQL |
| **Bildirim** | Telegram Bot entegrasyonu |
| **Derleme** | PyInstaller + Fernet şifreli kod koruma |
