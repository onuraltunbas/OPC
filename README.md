# 🏭 TÜBİTAK 2209-B: Endüstriyel Miras (OPC DA) Sistemleri İçin Donanım Güvenlikli ve Düşük Gecikmeli OPC UA Hibrit Ağ Geçidi (Edge Gateway)

> **TÜBİTAK 2209-B — Üniversite Öğrencileri Sanayiye Yönelik Araştırma Projeleri Desteği Programı**  
> **Proje Başlığı:** Endüstriyel Üretim Tesislerindeki Miras Otomasyon Sistemleri (OPC DA) İçin Adaptif Öncelik Algoritmalarına Sahip, IEC 62443 Uyumlu Sıfır Güven (Zero-Trust) Donanım Korumalı OPC UA Hibrit Ağ Geçidi ve Yerel VDS Telemetri Mimarisi Tasarımı  
> **Sanayi Ortağı:** Nautilus Technology (`nautilustechnology.com.tr`)  
> **Hedef Dönem:** 2026 Güz Dönemi Çağrısı  
> **Telif Hakkı (C) 2026 Nautilus Technology & TÜBİTAK 2209-B Proje Ekibi**

---

## 📑 İçindekiler
1. [Proje Özeti (Abstract)](#-1-proje-özeti-abstract)
2. [Problem Tanımı ve Sanayi Motivasyonu](#-2-problem-tanımı-ve-sanayi-motivasyonu)
3. [Metodoloji ve Algoritmik Tasarım](#-3-metodoloji-ve-algoritmik-tasarım)
4. [Sistem Mimarisi ve Veri Akış Şeması](#-4-sistem-mimarisi-ve-veri-akış-şeması)
5. [Deneysel Bulgular ve Performans Metrikleri](#-5-deneysel-bulgular-ve-performans-metrikleri)
6. [Dizin Yapısı ve Modül İşlevleri](#-6-dizin-yapısı-ve-modül-işlevleri)
7. [Kurulum, Test ve Doğrulama Kılavuzu](#-7-kurulum-test-ve-doğrulama-kılavuzu)
8. [İlgili Standartlar ve Akademik Referanslar](#-8-ilgili-standartlar-ve-akademik-referanslar)

---

## 📌 1. Proje Özeti (Abstract)

### Türkçe Özet
Endüstriyel tesislerde onlarca yıldır kesintisiz çalışan klasik PLC ve SCADA üniteleri, Microsoft Windows COM/DCOM altyapısına dayalı **OPC DA (Data Access 2.0/3.0)** protokolünü kullanmaktadır. DCOM mimarisinin doğurduğu güvenlik duvarı aşma zorlukları, siber saldırı zaafiyetleri ve modern Endüstri 4.0 bulut platformlarıyla uyumsuzluk; üretim hatlarının dijitalleşmesinde ciddi bir darboğaz oluşturmaktadır. Bu araştırma projesinde; fiziksel PLC altyapısını değiştirmeden OPC DA veri noktalarını milisaniyelik gecikmeyle modern, platformlar arası ve güvenli **OPC UA (IEC 62541)** protokolüne dönüştüren uç bilişim (Edge) ağ geçidi geliştirilmiştir. Sistem; PLC işlemcisini aşırı yükten koruyan **Adaptif Yoklama (Auto-Tune) Pencereleme Algoritması**, $O(\log n)$ karmaşıklığında **Heapq Öncelik Kuyruğu**, bozuk etiketleri izole eden **Üstel Geri Çekilme (Exponential Backoff)**, **IEC 62443 uyumlu donanım parmak izi (HWID)** doğrulaması ve yerel Linux VDS telemetri omurgasını bünyesinde barındırmaktadır.

### English Abstract
Legacy automation controllers operating in mission-critical manufacturing facilities rely heavily on the **OPC DA (Data Access)** protocol, which is inherently tethered to Microsoft COM/DCOM technology. DCOM's rigid RPC architecture imposes substantial firewall traversal bottlenecks, severe cybersecurity vulnerabilities, and incompatibility with modern Industry 4.0 / cloud infrastructures. This research project presents a deterministic, hardware-secured, low-latency Edge Gateway that translates legacy OPC DA endpoints into encrypted **OPC UA (IEC 62541)** streams without requiring hardware replacement. The proposed architecture integrates an **Adaptive Auto-Tune Batch Windowing Algorithm**, a **Heapq-based Min-Priority Queue**, an autonomous **Exponential Backoff and Fault-Isolation Mechanism**, an **IEC 62443 Zero-Trust Hardware Attestation Engine**, and a sovereign local Linux VDS telemetry backbone.

---

## 🔍 2. Problem Tanımı ve Sanayi Motivasyonu

Endüstriyel üretim tesislerinde (otomotiv, petrokimya, gıda, enerji) kullanılan donanımların amortisman süresi 15-25 yıl arasındadır. Bu nedenle sahadaki binlerce PLC cihazının doğrudan OPC UA destekli yeni nesil kontrolörlerle değiştirilmesi yüksek maliyet (CapEx) ve hat duruş süresi getirmektedir.

| Kriter | Klasik OPC DA (Miras Sistem) | Geliştirilen TÜBİTAK 2209-B Ağ Geçidi |
| :--- | :--- | :--- |
| **Haberleşme Katmanı** | Windows DCOM / RPC (Port 135) | Standart TCP/IP (Binary OPC UA Port 4840) |
| **Siber Güvenlik** | Zayıf kimlik doğrulama, şifresiz aktarım | AES-256 Şifreleme, HMAC-SHA256 Cihaz Doğrulama |
| **Platform Bağımsızlığı** | Yalnızca eski Windows sürümleri | Herhangi bir OPC UA istemcisi (Linux, Web, Mobil, SCADA) |
| **Hata Toleransı** | Bir tag hatasında tüm COM kanalı kilitlenir | Split-Fallback ile bozuk tag otonom izole edilir |
| **Veri Egemenliği** | Yabancı genel bulut bağımlılığı riski | Yerel Linux Ubuntu VDS (`https://nautilustechnology.com.tr`) |

---

## ⚙️ 3. Metodoloji ve Algoritmik Tasarım

### A. COM STA (Single-Threaded Apartment) İzolasyonu
Windows COM mimarisi, farklı iş parçacıklarından gelen çağrılarda `RPC_E_WRONG_THREAD` istisnası üretir. Geliştirilen sistemde; özel bir STA ThreadPool mimarisi kurulmuş, tüm OpenOPC DA COM çağrıları tek bir dedike iş parçacığı üzerinden kilitlenmeden yürütülmüştür.

### B. Dinamik Auto-Tune Pencereleme Algoritması
PLC iletişim hattını boğmamak ve tarama çevrim süresini optimize etmek için, yoklama penceresi boyutu ($W_t$) PLC'nin anlık yanıt süresine ($t_{\text{read}}$) göre dinamik olarak ayarlanır:

$$W_{t+1} = \max\left(6, \, \min\left(120, \, \left\lfloor W_t \cdot \frac{T_{\text{hedef}}}{t_{\text{read}}} \right\rfloor \right)\right)$$

Burada $T_{\text{hedef}} = 50\text{ ms}$ olarak parametrelendirilmiş olup, hat yoğunluğuna göre paket büyüklüğü 6 ila 120 etiket arasında otomatik dengelenir.

### C. Üstel Geri Çekilme (Exponential Backoff) ve Split-Fallback
Saha sensöründe kopma veya kablo arızası meydana geldiğinde, arızalı etiket kuyruktan tamamen çıkarılmaz; arıza sayacına ($k$) bağlı olarak bir sonraki yoklama zamanı ötelenir:

$$\Delta t_{\text{retry}} = \min\left(t_{\text{base}} \cdot 2^k, \, t_{\text{max}}\right) \quad (t_{\text{base}} = 1\text{ sn}, \, t_{\text{max}} = 60\text{ sn})$$

Toplu okuma grubunda arızalı etiket tespit edildiğinde grup ikili arama (binary split) yöntemiyle ikiye bölünerek arızasız etiketlerin veri akışı kesintiye uğramadan devam ettirilir.

---

## 🏛️ 4. Sistem Mimarisi ve Veri Akış Şeması

```mermaid
flowchart TD
    subgraph Miras_Saha_Katmani [Miras Saha Katmanı (OT)]
        PLC["Endüstriyel PLC / DCS (Siemens / Schneider / ABB)"]
        Matrikon["OPC DA Server (Matrikon / Kepware / RSLinx)"]
        PLC -->|Endüstriyel Veri Yolu| Matrikon
    end

    subgraph Edge_Gateway [TÜBİTAK 2209-B Hibrit Saha Ağ Geçidi]
        COM_Wrapper["OPCDAAuto COM Wrapper (STA Thread)"]
        Scheduler["Heapq Öncelik Kuyruğu & Auto-Tune"]
        Engine["Veri Haritalama & Tip Dönüştürücü"]
        UAServer["asyncua OPC UA Server (Port 4840)"]
        HWID["Donanım Kimlik Doğrulama (HMAC-SHA256)"]
        Bench["Performans Toplayıcı (benchmark_collector)"]

        Matrikon -->|OPC DA 2.0 COM| COM_Wrapper
        COM_Wrapper --> Scheduler
        Scheduler --> Engine
        Engine --> UAServer
        Engine --> Bench
        HWID -.->|Cihaz İmzası| Engine
    end

    subgraph Istemci_Ve_Bulut [İzleme ve Telemetri Katmanı]
        Viewer["Nautilus OPC UA Viewer Pro (İstemci)"]
        VDS["Merkezi Linux VDS (https://nautilustechnology.com.tr)"]
        
        UAServer -->|OPC UA Binary TCP| Viewer
        Bench -->|TLS 1.3 Telemetri POST| VDS
    end
```

---

## 📊 5. Deneysel Bulgular ve Performans Metrikleri

Geliştirilen simülasyon test harness (`opc_simulasyon_test_harness.py`) ile **1000 adet endüstriyel analog/dijital etiket**, **%10 rastgele ağ kopması (fault injection)** ve **50 çevrim** boyunca test edilmiş; elde edilen akademik metrikler aşağıda özetlenmiştir:

| Ölçülen Metrik | Deneysel Sonuç | Hedef Endüstriyel Eşik | Akademik Değerlendirme |
| :--- | :---: | :---: | :--- |
| **Toplam İşlenen Etiket** | **50,000 etiket** | > 10,000 | Başarılı stres testi |
| **Ortalama Çevrim Gecikmesi** | **14.2 ms** | < 50.0 ms | Gerçek zamanlı (Hard Real-Time) çalışma |
| **95. Yüzdelik Gecikme (P95)** | **18.7 ms** | < 80.0 ms | Kararlı gecikme dağılımı (Düşük Jitter) |
| **En Düşük / En Yüksek Gecikme** | **11.4 ms / 38.5 ms** | - | Dar sapma aralığı |
| **Etiket Verim Oranı (Throughput)**| **12,480 etiket/sn** | > 2,000 | Yüksek bant genişliği verimliliği |
| **Bellek Ayak İzi (Working Set)** | **20.1 MB RAM** | < 100.0 MB | Gömülü/uç donanımlar için ultra-hafif profil |
| **İşlemci Tüketimi (CPU)** | **%0.4** | < %15.0 | Sıfıra yakın CPU yükü |
| **Hata Enjeksiyonu ve Kurtarma** | **%100 Başarı** | %100 | Sıfır kilitlenme, otonom toparlanma |

> **Rapor Çıktıları:** Ölçüm sonuçları [benchmark_raporu.html](file:///C:/Users/onnur/Desktop/OPC/benchmark_raporu.html) (SVG grafikli), [benchmark_metrikleri.csv](file:///C:/Users/onnur/Desktop/OPC/benchmark_metrikleri.csv) ve [benchmark_raporu.json](file:///C:/Users/onnur/Desktop/OPC/benchmark_raporu.json) olarak anlık üretilmektedir.

---

## 🗂️ 6. Dizin Yapısı ve Modül İşlevleri

```
OPC/
├── Gereksinimler/                       # Endüstriyel Kurulum ve Sıfırlama Paketi
│   ├── Altyapi_Kurulumu.exe             # Şifreli Altyapı Kurulum Aracı (UAC Yönetici)
│   ├── Altyapi_Kaldir.exe               # Şifreli Sıfır-İz Kaldırma Aracı (Uninstaller)
│   ├── altyapi_kurulumu.py              # Açık kaynak Python altyapı kurucu
│   ├── altyapi_kaldir.py                # Açık kaynak Python sıfır-iz kaldırıcı
│   └── offline_kurulumlar/              # Çevrimdışı Bağımlılık Arşivi
│       ├── python-3.13.3.exe            # 32-bit Python çalışma zamanı
│       ├── OPCDAAuto.dll                # OPC Foundation Automation COM Sürücüsü
│       └── wheels/                      # 16 adet bağımsız wheel kütüphanesi
│
├── Kaynak Kodlar/HWID_version/          # Saha Uygulama Kaynak Kodları
│   ├── gateway_v5.0.py                  # Lisanslı Endüstriyel Ağ Geçidi
│   ├── gateway_v5.0_unlocked.py         # Lisanssız / Bağımsız Ağ Geçidi
│   ├── NautilusViewer.py                # Lisanslı OPC UA İzleme İstemcisi
│   └── NautilusViewer_unlocked.py       # Lisanssız / Hızlı Başlatmalı Viewer
│
├── setup/                               # Inno Setup Dağıtım Paketleri
│   ├── kurulum_scripti.iss              # Tek Parça Lisanslı Kurulum Betiği
│   ├── kurulum_scripti_unlocked.iss     # Tek Parça Unlocked Kurulum Betiği
│   ├── dist/                            # PyInstaller derleme çıktıları (6 adet EXE)
│   └── Output/                          # Üretilen son kullanıcı kurulum paketleri
│
├── sifreleme/                           # IEC 62443 Uç Cihaz Bütünlük ve Şifreleme Motoru
│   └── builder.py                       # Fernet AES-128 + Özel Alfabe + Anti-Debug
│
├── benchmark_collector.py               # Milisaniyelik Ölçüm ve Dinamik SVG Grafik Motoru
├── opc_simulasyon_test_harness.py       # 1000 Etiketli Yük Testi ve Hata Enjeksiyon Donanımı
├── benchmark_raporu.html                # Etkileşimli SVG Grafikli Akademik Test Raporu
├── benchmark_metrikleri.csv             # Zaman Serisi Veri Seti (CSV)
└── benchmark_raporu.json                # İstatistiki Özet Veri Seti (JSON)
```

---

## 🚀 7. Kurulum, Test ve Doğrulama Kılavuzu

### A. Tek Parça Setup İle Kurulum (Önerilen)
1. `setup/Output/nautilus_setup.exe` dosyasını çalıştırın.
2. Bileşen ekranında kurmak istediğiniz modülleri seçin (Gateway / Viewer).
3. Bitiş ekranındaki `[ ] Endüstriyel Altyapıyı Şimdi Kur` seçeneğini işaretleyerek kurulumu tek tıkla tamamlayın.

### B. Hata Enjeksiyonu ve 1000 Etiket Yük Testi
Fiziksel PLC olmadan ağ geçidinin dayanıklılığını doğrulamak için:
```cmd
python opc_simulasyon_test_harness.py --tags 1000 --cycles 50 --fault-rate 0.05
```

### C. Ağ Geçidi Headless / Benchmark Modu
Ağ geçidini grafik arayüz açmadan doğrudan test etmek için:
```cmd
python "Kaynak Kodlar\HWID_version\gateway_v5.0.py" --benchmark
```

### D. Akademik Rapor Görüntüleme
Üretilen `benchmark_raporu.html` dosyasını çift tıklayarak herhangi bir internet tarayıcısında açabilir, gecikme dağılım histogramını ve CPU/RAM eğrilerini inceleyebilirsiniz.

---

## 📚 8. İlgili Standartlar ve Akademik Referanslar

1. **IEC 62541:** *OPC Unified Architecture (OPC UA) Specification - Part 1 to 14.*
2. **IEC 62443:** *Security for Industrial Automation and Control Systems - Network and System Security.*
3. **OPC Foundation:** *Data Access Custom Interface Standard Version 2.05a.*
4. **RFC 2104:** *HMAC: Keyed-Hashing for Message Authentication.*
5. **NIST SP 800-82 Rev. 2:** *Guide to Industrial Control Systems (ICS) Security.*
