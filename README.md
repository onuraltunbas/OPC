# 🏭 TÜBİTAK 2209-B: Endüstriyel OPC DA / OPC UA Hibrit Ağ Geçidi (Edge Gateway)

> **TÜBİTAK 2209-B — Sanayiye Yönelik Lisans Araştırma Projeleri Desteği Programı**  
> **Proje Başlığı:** Endüstriyel Üretim Tesislerindeki Miras Otomasyon Sistemleri (OPC DA) İçin Adaptif Öncelik Algoritmalarına Sahip, IEC 62443 Uyumlu Sıfır Güven (Zero-Trust) Donanım Korumalı OPC UA Hibrit Ağ Geçidi ve Yerel VDS Telemetri Mimarisi Tasarımı  
> **Telif Hakkı (C) 2026 Nautilus Technology & TÜBİTAK 2209-B Proje Ekibi**

---

## 📌 1. Proje Özeti ve AR-GE Vizyonu

Endüstriyel tesislerde uzun yıllardır kullanılan klasik **OPC DA (Data Access)** standardı, Microsoft Windows COM/DCOM altyapısına doğrudan bağımlıdır. Bu bağımlılık, siber güvenlik açıkları (DCOM zaafiyetleri), güvenlik duvarı geçiş sorunları ve modern Endüstri 4.0 / SCADA / MES bulut sistemleriyle entegrasyon imkansızlığı doğurmaktadır.

Bu araştırma projesinde;
1. **Miras Sistem Entegrasyonu:** Sahadaki eski PLC ve DCS sistemlerinin (Siemens, ABB, Schneider, Kepware, Matrikon vb.) OPC DA verilerini okuyarak modern, güvenli ve platformlar arası **OPC UA (IEC 62541)** protokolüne gerçek zamanlı dönüştüren hibrit bir ağ geçidi (Edge Gateway) tasarlanmıştır.
2. **Adaptif Yoklama ve Kuyruk Algoritması (Auto-Tune):** PLC işlemcisini ve endüstriyel veri yolunu boğmayan, anlık gecikme süresine (`read_elapsed_ms`) göre okuma penceresini (6 ila 120 arası) otomatik ayarlayan `heapq` tabanlı dinamik öncelik kuyruğu geliştirilmiştir.
3. **Otonom Hata Kurtarma (Exponential Backoff):** Hatalı veya kopan tag'lerde sistemi kilitlemeyen, kademeli gecikme (exponential backoff) ve parçalı geri çekilme (split-fallback) algoritması modellenmiştir.
4. **IEC 62443 Uyumlu Uç Güvenliği (Zero-Trust):** Kapalı devre (air-gapped) fabrikalar için donanım parmak izi (HMAC-SHA256) tabanlı challenge-response doğrulama protokolü geliştirilmiştir.
5. **Veri Egemenliği ve Yerel VDS:** Veri gizliliğini korumak amacıyla yabancı genel bulutlar yerine, yerel Linux Ubuntu VDS ve TLS 1.3 şifrelemesiyle çalışan telemetri omurgası entegre edilmiştir.

---

## 🏛️ 2. Sistem Mimarisi

```
  [ PLC / DCS / SCADA ]
          │ (OPC DA 2.0 COM/DCOM)
          ▼
┌───────────────────────────────────────────────────────────┐
│     TÜBİTAK 2209-B HİBRİT AĞ GEÇİDİ (WINDOWS EDGE)       │
│                                                           │
│  • STA ThreadPoolExecutor (COM Thread Güvenliği)          │
│  • Adaptif Poll Scheduler (Heapq Dinamik Kuyruk)          │
│  • Auto-Tune: Okuma süresine göre dinamik poll_cap        │
│  • Split-Fallback & Poisoned Connection Tespiti           │
│  • IEC 62443 Donanım İmzası (HMAC-SHA256)                 │
│  • Milisaniyelik Benchmark Motoru (benchmark_collector)   │
└───────────────────────────────────────────────────────────┘
          │ (OPC UA TCP / Binary Protokolü)
          ▼
┌───────────────────────────────────────────────────────────┐
│     OPC UA SUNUCU VE İSTEMCİ AĞI                          │
│                                                           │
│  • OPC UA Server (opc.tcp://0.0.0.0:4840/)                │
│  • Bağımsız İstemci: Nautilus OPC UA Viewer Pro           │
│  • Güvenli TLS 1.3 Telemetri: https://nautilustechnology.com.tr
└───────────────────────────────────────────────────────────┘
```

---

## 🗂️ 3. Dizin Yapısı

```
OPC/
├── Gereksinimler/                       # Endüstriyel Kurulum ve Sıfırlama Paketi
│   ├── Altyapi_Kurulumu.exe             # Şifreli Altyapı Kurulum Aracı (UAC Yönetici)
│   ├── Altyapi_Kaldir.exe               # Şifreli Sıfır-İz Kaldırma Aracı (Uninstaller)
│   ├── Altyapi_Kurulumu.bat             # Açık kaynak toplu kurulum scripti
│   ├── Altyapi_Kaldir.bat               # Açık kaynak toplu kaldırma scripti
│   └── offline_kurulumlar/              # Çevrimdışı Bağımlılık Arşivi
│       ├── python-3.13.3.exe            # 32-bit Python çalışma zamanı
│       ├── OPCDAAuto.dll                # OPC Foundation Automation COM Sürücüsü
│       └── wheels/                      # 16 adet çevrimdışı Python kütüphanesi
│
├── Kaynak Kodlar/HWID_version/          # Uygulama Kaynak Kodları
│   ├── gateway_v5.0.py                  # Lisanslı Ağ Geçidi (Pro)
│   ├── gateway_v5.0_unlocked.py         # Lisanssız / Tam Yetkili Ağ Geçidi
│   ├── NautilusViewer.py                # Lisanslı OPC UA Viewer
│   └── NautilusViewer_unlocked.py       # Lisanssız / Sıfır Gecikmeli Viewer
│
├── setup/                               # Inno Setup Dağıtım Paketleri
│   ├── kurulum_scripti.iss              # Tek Parça Lisanslı Kurulum Scripti
│   ├── kurulum_scripti_unlocked.iss     # Tek Parça Unlocked Kurulum Scripti
│   ├── dist/                            # PyInstaller derleme çıktıları
│   └── Output/                          # Üretilen son kullanıcı kurulum paketleri
│
├── sifreleme/                           # IEC 62443 Uç Cihaz Bütünlük ve Şifreleme Motoru
│   ├── builder.py                       # Fernet AES-128 + Özel Alfabe + Anti-Debug
│   ├── app.manifest                     # Windows UAC Yönetici Hakları Manifesti
│   ├── ver.txt                          # Windows PE Versiyon Bilgisi
│   └── logo.ico                         # Kurumsal Güvenlik İkonu
│
├── benchmark_collector.py               # Milisaniyelik Ölçüm ve Matplotlib Grafik Motoru
└── opc_simulasyon_test_harness.py       # %5 Hata ve Gecikme Enjeksiyonlu Sanayi Test Düzeneği
```

---

## ⚡ 4. Kurulum ve Çalıştırma

### A. Tek Parça Setup İle Kurulum (Önerilen)
1. `setup/Output/nautilus_setup.exe` dosyasını çalıştırın.
2. Kurulum sihirbazında istediğiniz bileşenleri (Gateway ve/veya Viewer) seçin.
3. Kurulum tamamlandığında son ekrandaki **"Endüstriyel Altyapıyı Şimdi Kur"** seçeneğini işaretleyerek kurulumu tek tıkla tamamlayın.

### B. Manuel Altyapı Kurulumu
Temiz ve internetsiz bir bilgisayarda ağ geçidini çalıştırmadan önce:
```cmd
cd Gereksinimler
Altyapi_Kurulumu.exe
```
Bu işlem; Python 3.13 (32-bit), 16 endüstriyel kütüphane, `OPCDAAuto.dll` COM kaydı ve Windows Firewall 4840 port kuralını otomatik olarak sisteme işler.

### C. Altyapıyı Tamamen Kaldırma (Sıfır İz)
```cmd
cd Gereksinimler
Altyapi_Kaldir.exe
```
Sistemdeki tüm Python dosyaları, kayıt defteri girdileri, güvenlik duvarı kuralları ve COM kayıtları silinir; bilgisayar altyapı hiç kurulmamış gibi orijinal haline döner.

---

## 🧪 5. Bilimsel Doğrulama ve Benchmark Testleri

* **Hata Enjeksiyonu ve Otonom Kurtarma Testi:**
  ```cmd
  python opc_simulasyon_test_harness.py
  ```
* **Milisaniyelik Performans ve Sistem Yük Analizi:**
  ```cmd
  python benchmark_collector.py
  ```
  Oluşan `benchmark_results.csv` ve `performans_grafigi.png` dosyaları TÜBİTAK Sonuç Raporu için yüksek çözünürlüklü veri sağlar.

---

## 📜 6. Lisans ve Akademik Beyan
Bu proje, **TÜBİTAK 2209-B Üniversite Öğrencileri Sanayiye Yönelik Araştırma Projeleri Desteği Programı** kapsamında geliştirilmiştir. Tüm fikri mülkiyet ve telif hakları proje yürütücüsüne aittir.
