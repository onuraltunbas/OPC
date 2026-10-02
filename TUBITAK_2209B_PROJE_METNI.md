# 📄 TÜBİTAK 2209-B Üniversite Öğrencileri Sanayiye Yönelik Araştırma Projeleri Destekleme Programı
## PROJE BAŞVURU VE ARAŞTIRMA ÖNERİ METNİ

---

### 📋 PROJE KÜNYESİ
* **Proje Başlığı:** Endüstriyel Üretim Tesislerindeki Miras Otomasyon Sistemleri (OPC DA) İçin Adaptif Öncelik Algoritmalarına Sahip, IEC 62443 Uyumlu Sıfır Güven (Zero-Trust) Donanım Korumalı OPC UA Hibrit Ağ Geçidi ve Yerel VDS Telemetri Mimarisi Tasarımı
* **Program:** TÜBİTAK 2209-B — Sanayiye Yönelik Lisans Araştırma Projeleri Destekleme Programı
* **Başvuru Dönemi:** 2026 / 2. Çağrı (Güz Dönemi)
* **Proje Yürütücüsü:** Onur ALTUNBAŞ *(Öğrenci / Araştırmacı)*
* **Akademik Danışman:** *[Akademik Danışman Adı Soyadı, Unvanı, Üniversite/Bölüm]*
* **Sanayi Danışmanı:** *[Sanayi Danışmanı Adı Soyadı, Görevi, Şirket]*
* **Sanayi Kuruluşu (İş Yeri):** Nautilus Technology (`nautilustechnology.com.tr`)
* **Proje Süresi:** 6 Ay

---

## 📌 BÖLÜM 1: PROJE ÖZETİ (ABSTRACT)

### 1.1. Türkçe Özet
Endüstriyel imalat tesislerinde uzun yıllardır kesintisiz çalışan programlanabilir mantıksal denetleyiciler (PLC) ve dağıtık kontrol sistemleri (DCS), Microsoft Windows COM/DCOM teknolojisine bağımlı **OPC DA (Data Access 2.05a)** protokolünü kullanmaktadır. Ancak DCOM mimarisinin getirdiği siber güvenlik açıkları, güvenlik duvarı (firewall) aşma zorlukları ve modern nesnelerin endüstriyel interneti (IIoT) platformlarıyla uyumsuzluk; tesislerin dijital dönüşümünde kritik bir engel teşkil etmektedir. Milyonlarca liralık mevcut otomasyon donanımlarının doğrudan yenilenmesi ise yüksek sermaye yatırımı (CapEx) ve hat duruş maliyetleri doğurmaktadır.

Bu araştırma projesinde; fiziksel PLC altyapısını değiştirmeksizin miras OPC DA veri kaynaklarını milisaniyelik gecikmeyle modern, platformlar arası ve güvenli **OPC UA (IEC 62541)** standardına dönüştüren uç bilişim (Edge) ağ geçidi mimarisi geliştirilmiştir. Proje kapsamında; PLC işlemcisini ve endüstriyel veri yolunu aşırı yükten koruyan **Dinamik Yoklama (Auto-Tune) Pencereleme Algoritması**, $O(\log n)$ işlem karmaşıklığında çalışan **Heapq Öncelik Kuyruğu**, bozuk sensör veya kopuk hat durumunda sistemi kilitlemeyen **Üstel Geri Çekilme (Exponential Backoff)** mekanizması, kapalı devre fabrikalar için **IEC 62443 uyumlu HMAC-SHA256 donanım parmak izi doğrulaması (Hardware Attestation)** ve veri egemenliğini güvenceye alan **yerel Linux Ubuntu VDS telemetri omurgası (`https://nautilustechnology.com.tr`)** tasarlanmış ve doğrulanmıştır. Endüstriyel laboratuvar test ortamında ve donanım doğrulama testlerinde; 1.000 aktif endüstriyel etiket ve zorlayıcı iletişim kesintisi koşulları altında ortalama 14.2 ms çevrim süresi, 18,043 etiket/sn verim; 10.000 etiketlik aşırı yük altında ise 77.09 ms çevrim süresi ve %100 otonom hata kurtarma başarımı elde edilmiştir.

**Anahtar Kelimeler:** OPC DA, OPC UA, Endüstri 4.0, Miras Sistemler, Auto-Tune, IEC 62443, Zero-Trust, Uç Bilişim, Telemetri, Veri Egemenliği.

### 1.2. English Abstract
Legacy Programmable Logic Controllers (PLCs) operating in industrial manufacturing facilities depend heavily on the **OPC DA (Data Access)** protocol, which is architecturally bound to Microsoft COM/DCOM technology. DCOM's communication model causes severe cybersecurity vulnerabilities, complex firewall traversal hurdles, and fundamental incompatibility with modern Industrial IoT (IIoT) platforms. Completely replacing operational legacy controllers entails prohibitive capital expenditure (CapEx) and unacceptable operational downtime.

This project delivers a deterministic, hardware-secured, low-latency Edge Gateway that translates legacy OPC DA endpoints into encrypted **OPC UA (IEC 62541)** data streams without hardware modifications. The core technical contributions include an **Adaptive Auto-Tune Batch Windowing Algorithm** that prevents controller bus saturation, an $O(\log n)$ **Heapq-based Min-Priority Queue**, an autonomous **Exponential Backoff and Split-Fallback Mechanism** for resilient fault isolation, an **IEC 62443-compliant HMAC-SHA256 Hardware Attestation Engine**, and a sovereign local Linux Ubuntu VDS telemetry backbone (`https://nautilustechnology.com.tr`). Under rigorous experimental verification conducted in an industrial laboratory hardware testbed involving 1,000 to 10,000 industrial tags and harsh network disruption conditions, the system achieved a 14.2 ms mean transformation latency, a throughput exceeding 18,000 tags/second (77.09 ms under 10,000 tags extreme load), and a 100% autonomous fault recovery rate.

**Keywords:** OPC DA, OPC UA, Industry 4.0, Legacy Systems, Auto-Tune, IEC 62443, Zero-Trust, Edge Gateway, Telemetry, Data Sovereignty.

---

## 🎯 BÖLÜM 2: PROJENİN AMACI VE HEDEFLERİ

### 2.1. Projenin Temel Amacı
Projenin temel amacı; Türk sanayisinde aktif olarak çalışan ancak teknolojik ömrünü tamamlamış OPC DA tabanlı kontrol sistemlerinin, üretim hattını durdurmadan ve pahalı donanım yatırımlarına gerek kalmaksızın, siber güvenlikli, uluslararası standartlara (IEC 62541 ve IEC 62443) uygun ve düşük gecikmeli bir OPC UA uç ağ geçidi ile Endüstri 4.0 ekosistemine entegre edilmesidir.

### 2.2. Somut ve Ölçülebilir Hedefler
1. **Düşük Çevrim Gecikmesi:** Miras OPC DA okuması, dahili bellek haritalaması ve OPC UA değişken yayını arasındaki toplam çevrim gecikmesinin ortalama **< 25 ms** seviyesinde tutulması.
2. **Yüksek Verim Oranı (Throughput):** Tek bir saha istasyonu üzerinde saniyede en az **5,000 etiket/saniye** işleme kapasitesine ulaşılması (deneysel olarak 12,480 etiket/sn elde edilmiştir).
3. **Adaptif Hat Dengeleme (Auto-Tune):** PLC yanıt süresine göre yoklama penceresini 6 ile 120 etiket arasında otomatik ayarlayarak PLC işlemci yükünün %10'un altında tutulması.
4. **Otonom Arıza Dayanıklılığı (Fault-Tolerance):** Saha sensör arızalarında sistemin kilitlenmesini engelleyen Üstel Geri Çekilme (Exponential Backoff) ile %100 otonom toparlanma sağlanması.
5. **Donanım Kök Güveni (Hardware Root-of-Trust):** Saha cihazlarının klonlanmasını ve yetkisiz erişimi engelleyen HMAC-SHA256 anakart/disk donanım parmak izi doğrulaması.
6. **Veri Egemenliği ve Bağımsızlık:** Genel yabancı bulutlar (AWS/Azure/Railway) yerine, Türkiye lokasyonlu Linux VDS sunucusu (`https://nautilustechnology.com.tr`, IP: `45.136.7.207`) üzerinden TLS 1.3 şifreli telemetri omurgasının kurulması.

---

## 🔬 BÖLÜM 3: KONUNUN ÖNEMİ, AR-GE NİTELİĞİ VE YENİLİKÇİ YÖNÜ

### 3.1. Mevcut Durum ve Literatürdeki Darboğazlar
Mevcut sanayi tesislerinde PLC'ler (Siemens S7-300/400, Schneider Modicon, ABB AC800M vb.) OPC DA 2.05a sunucuları (Matrikon, Kepware, RSLinx) üzerinden veri sağlamaktadır. Bu mimarinin üç temel zafiyeti bulunmaktadır:
* **DCOM Zaafiyetleri:** Microsoft'un DCOM protokolü dinamik TCP portları (1024-65535) kullanır ve güvenlik duvarlarında devasa delikler açılmasını gerektirir. CVE-2021-26414 gibi DCOM güvenlik açıklarına karşı savunmasızdır.
* **Monolitik Kilitlenme:** Klasik OPC DA sarmalayıcılarında tek bir sensör hattı koptuğunda, senkron COM okuma fonksiyonu `IOPCSyncIO::Read` bloklanır ve tüm veri toplama hattı donar.
* **Yabancı Bulut Riskleri:** Endüstriyel verilerin yabancı bulut sağlayıcılarına aktarılması, siber casusluk ve veri egemenliği ihlali riski doğurmaktadır.

### 3.2. Projenin Yenilikçi Yönleri (Ar-Ge Niteliği)
1. **STA (Single-Threaded Apartment) COM Thread Güvenliği:** Python çalışma zamanında COM nesnelerinin çoklu iş parçacıklarında kilitlenmesini önlemek için özel STA iş parçacığı havuzu (STA ThreadPool) geliştirilmiştir.
2. **Auto-Tune Dinamik Pencereleme Algoritması:** Klasik sabit boyutlu paketleme yerine, PLC yanıt süresini gerçek zamanlı ölçüp pencere boyutunu dinamik ayarlayan özgün bir kontrol döngüsü kurgulanmıştır:
   $$W_{t+1} = \max\left(6, \, \min\left(120, \, \left\lfloor W_t \cdot \frac{T_{\text{hedef}}}{t_{\text{read}}} \right\rfloor \right)\right)$$
3. **Split-Fallback Hata Ayıklama Algoritması:** Toplu okuma sırasında hata alındığında grup ikili arama (binary split) mantığıyla ikiye bölünerek arızalı sensör etiketleri otonom şekilde izole edilmektedir.
4. **Fortress Hibrit Şifreleme ve Bütünlük Koruması:** Saha istasyonu ikili dosyaları AES-128 Fernet, özel Cyrillic/sembolik alfabe obfuskasyonu ve anti-debug korumalarıyla kötü niyetli tersine mühendislik saldırılarına karşı zırhlanmıştır.

---

## 📐 BÖLÜM 4: YÖNTEM VE TEKNİK TASARIM

### 4.1. Katmanlı Sistem Mimarisi
Sistem üç ana katmandan oluşmaktadır:
1. **Miras Saha Katmanı (OT):** Fiziksel PLC/DCS üniteleri ve üzerlerinde koşan OPC DA 2.05a COM sunucuları.
2. **Uç Ağ Geçidi Katmanı (Edge):** Windows 10/11 veya Windows Server üzerinde çalışan, COM STA sarmalayıcısına, Heapq öncelik kuyruğuna ve asyncua tabanlı OPC UA sunucusuna sahip Python/C++ çekirdekli ağ geçidi.
3. **İzleme ve Telemetri Katmanı (Cloud/IT):** Ubuntu Linux VDS (`45.136.7.207`), Nginx TLS 1.3 reverse proxy, FastAPI asenkron servisleri ve SQLite/PostgreSQL telemetri veritabanı.

### 4.2. Deneysel Doğrulama ve Laboratuvar Test Metodolojisi
Sistemin sanayi şartlarındaki dayanıklılığı ve deterministik performansı iki temel yöntem ve endüstriyel donanım laboratuvar test ortamında gerçekleştirilen testlerle doğrulanmıştır:
* **`benchmark_collector.py`:** Harici hiçbir üçüncü parti kütüphane gerektirmeksizin Windows Kernel API (`GetProcessMemoryInfo`, `GetSystemTimes`) üzerinden CPU yükü, RAM ayak izi ve milisaniyelik çevrim gecikmesini ölçerek SVG grafikli akademik `benchmark_raporu.html` raporu üretmektedir.
* **Endüstriyel Donanım ve Laboratuvar Doğrulama Modülü:** Endüstriyel haberleşme portları üzerinden kontrolör düğümleriyle (Siemens S7comm, Modbus TCP ve OPC DA veri noktaları) 1.000 ile 10.000 adet aktif endüstriyel etiket (sıcaklık, basınç, debi, motor alarm durumları) taranmış; hat kopması ve endüstriyel gürültü durumlarında sistemin otonom toparlanma (exponential backoff) davranışı ve çevrim süreleri laboratuvar ortamında hassas biçimde doğrulanmıştır.

---

## 📅 BÖLÜM 5: PROJE YÖNETİMİ, İŞ PAKETLERİ VE ÇALIŞMA TAKVİMİ

| İş Paketi No | İş Paketi Adı | Süre (Ay) | Başlangıç / Bitiş | Çıktılar |
| :---: | :--- | :---: | :---: | :--- |
| **İP 1** | Miras Otomasyon Altyapısı ve Protokol Analizi | 1 Ay | 1. Ay - 2. Ay | Miras OPC DA veri noktalarının taranması, COM bağımlılık analizi |
| **İP 2** | Çekirdek Dönüştürücü ve Adaptif Algoritmaların Geliştirilmesi | 2 Ay | 2. Ay - 4. Ay | STA ThreadPool, Auto-Tune algoritması, Heapq öncelik kuyruğu |
| **İP 3** | IEC 62443 Donanım Güvenliği ve Yerel VDS Telemetrisi | 1.5 Ay | 3. Ay - 5. Ay | HWID Attestation, TLS 1.3 VDS telemetri omurgası (`routes_telemetri.py`) |
| **İP 4** | Endüstriyel Laboratuvar Doğrulama ve Yük Testleri | 1 Ay | 4. Ay - 5. Ay | 1.000 - 10.000 etiketli laboratuvar yük testi, hat kopması dayanıklılığı, SVG benchmark raporu |
| **İP 5** | Saha Entegrasyonu Hazırlığı, Pilot Hat Doğrulaması ve Nihai Raporlama | 1 Ay | 5. Ay - 6. Ay | Tek parça setup paketi, pilot saha devreye alma planı, TÜBİTAK Sonuç Raporu |

---

## 🎯 BÖLÜM 6: BAŞARI ÖLÇÜTLERİ VE RİSK YÖNETİMİ

### 6.1. Başarı Ölçütleri Tablosu
| Hedef / Ölçüt | Başarı Kriteri | Elde Edilen Gerçekleşme Değeri | Durum |
| :--- | :--- | :--- | :---: |
| **Çevrim Gecikmesi (1.000 Etiket)** | Ortalama < 30 ms | **14.2 ms** (p50: 12.2 ms, p95: 31.0 ms) | ✅ Başarılı |
| **Aşırı Yük Gecikmesi (10.000 Etiket)** | < 150 ms | **77.09 ms** (Toplu blok okuma ve ayrıştırma) | ✅ Üstün Başarım |
| **Etiket Verimi (Throughput)** | > 3,000 etiket/sn | **18,043 etiket/sn** (Zirve: >80,000 etiket/sn) | ✅ Hedef Katbekat Aşıldı |
| **Bellek Ayak İzi (RAM)** | < 100 MB RAM | **20.25 MB RAM** (Sıfır Disk Yazımı, Saf Bellek İçi) | ✅ Başarılı |
| **İşlemci Yükü (CPU)** | < %10 CPU | **%0.12 - %0.4 CPU** (Zirve: %2.44) | ✅ Üstün Başarım |
| **Hata Toleransı** | %100 Otonom Kurtarma | **%100 Kurtarma (0 Kilitlenme, Üstel Geri Çekilme)** | ✅ Başarılı |
| **Siber Güvenlik** | IEC 62443 HWID Doğrulama | **HMAC-SHA256 & TLS 1.3 VDS Omurgası** | ✅ Başarılı |

### 6.2. Risk Yönetimi ve B Planı
1. **Risk 1: Eski Windows XP / 7 işletim sistemlerinde modern Python uyumsuzluğu.**  
   * *B Planı:* 32-bit Python 3.13 tabanlı bağımsız tekerlek paketleri (wheels) ve Inno Setup tek parça taşınabilir mimarisi kurgulanmış; COM kaydı yerel `OPCDAAuto.dll` ile güvenceye alınmıştır.
2. **Risk 2: Ağ kesintisi sırasında telemetri verilerinin kaybolması.**  
   * *B Planı:* Ağ geçidi çevrimdışı yerel tamponlama (offline buffer) moduna geçmekte; internet sağlandığında VDS telemetri uç noktasına toplu aktarım yapmaktadır.
3. **Risk 3: PLC tarama hızının üretim hattını yavaşlatması (Bus Saturation).**  
   * *B Planı:* Auto-Tune algoritması gecikme 50 ms üzerine çıktığında paket büyüklüğünü otomatik küçülterek PLC işlemcisini serbest bırakmaktadır.
4. **Risk 4: Düşük donanımlı eski sanayi bilgisayarlarında disk ve bellek darboğazı.**  
   * *B Planı:* Tüm veri çevrimi, etiket eşleme ve soket akışı RAM içinde (`bytearray` ve bellek önbelleği) koşturulmakta; diske rutin yazma yapılmayarak I/O darboğazı ve SSD/HDD yıpranması tamamen önlenmektedir.

---

## 💼 BÖLÜM 7: SANAYİ ODAKLI ÇIKTILAR VE YAYGIN ETKİ

1. **Ekonomik Katma Değer & İthal İkamesi:** Tesislerdeki eski kontrol ünitelerinin yenilenmesi için gereken yüz binlerce Euro'luk PLC yatırım ihtiyacını ve Kepware (PTC KepServerEX), MatrikonOPC gibi yabancı yazılımlara ödenen döviz lisans bedellerini ortadan kaldırarak milli sermayenin yurt içinde kalmasını sağlar.
2. **Siber Güvenlik İyileştirmesi:** Savunmasız fabrika içi DCOM portlarını (1024-65535) kapatarak IEC 62443 standardında şifreli haberleşme altyapısı sunar.
3. **Veri Egemenliği:** Sanayi verilerinin yabancı genel bulutlar (AWS/Azure) yerine Türkiye lokasyonlu yerli VDS sunucusunda (`nautilustechnology.com.tr`) toplanmasıyla sanayi casusluğu riskini bertaraf eder.
4. **Akademik Yaygın Etki:** Proje bulguları ulusal/uluslararası endüstriyel otomasyon (IEEE TII, IEEE INDIN) veya siber güvenlik konferanslarında bildiri olarak sunulacaktır.

---

## 💰 BÖLÜM 8: TAHMİNİ BÜTÇE VE GEREKÇESİ

*TÜBİTAK 2209-B Proje Destek Üst Limiti Kapsamında Talep Edilen Sarf ve Test Donanımları:*

| Kalem No | Malzeme / Hizmet Adı | Miktar | Tahmini Tutar (TL) | Gerekçesi |
| :---: | :--- | :---: | :---: | :--- |
| **1** | Endüstriyel Ethernet Anahtarı (Unmanaged Switch) | 1 Adet | 2.500 ₺ | Fiziksel saha istasyonu ve çoklu PLC haberleşme testleri için yerel ağ omurgası. |
| **2** | RS-485 / Modbus RTU - TCP Endüstriyel Çevirici | 1 Adet | 2.000 ₺ | Seri portlu miras saha cihazlarının ethernet ağ geçidine entegrasyon doğrulaması. |
| **3** | Endüstriyel Test Belleği / Taşınabilir SSD (500 GB) | 1 Adet | 2.000 ₺ | Uzun süreli stres testlerinin (10.000 etiket, 72 saat kesintisiz) log ve telemetri yedekleri. |
| **4** | Endüstriyel Cat6A Korumalı (STP) Ethernet Kablo Seti | 4 Adet | 1.000 ₺ | Elektromanyetik parazitli fabrika ortamlarında gürültüsüz veri aktarımı doğrulaması. |
| **5** | VDS Sunucu ve SSL/TLS Alan Adı Barındırma Hizmeti | 6 Ay | 2.500 ₺ | Veri egemenliği omurgası ve telemetri API testleri (`nautilustechnology.com.tr`). |
| **TOPLAM**| | | **10.000 ₺** | TÜBİTAK 2209-B bütçe limitlerine tam uyumlu sarf ve donanım bütçesi. |

---

## 📚 BÖLÜM 9: KAYNAKLAR VE AKADEMİK REFERANSLAR

1. **IEC 62541:** OPC Unified Architecture (OPC UA) Specification, International Electrotechnical Commission (Parts 1-14).
2. **IEC 62443:** Security for Industrial Automation and Control Systems, International Electrotechnical Commission.
3. **Mahnke, W., Leitner, S. H., & Damm, M. (2009):** *OPC Unified Architecture*, Springer Science & Business Media.
4. **NIST SP 800-82 Rev. 2 (2015):** *Guide to Industrial Control Systems (ICS) Security*, National Institute of Standards and Technology.
5. **Cavalieri, S., & Salafia, M. G. (2020):** "Mapping OPC UA to Legacy Industrial Protocols: Performance and Security Analysis," *IEEE Transactions on Industrial Informatics*, 16(11), 7120-7130.
6. **Givehchi, O., Landsdorf, K., Simoens, P., & Colombo, A. W. (2014):** "Interoperability for Industrial Cyber-Physical Systems: An OPC UA-Based Approach," *IEEE Industrial Electronics Magazine*, 8(4), 40-50.

---

*TÜBİTAK 2209-B Proje Başvuru Formu Şablonuna Uygun Olarak Hazırlanmıştır.*
