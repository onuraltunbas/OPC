# OPC Gateway v4.0 — Kurulum ve Deploy Kılavuzu

## ADIM 1: Sunucuyu Railway'e Deploy Edin

### 1.1 — Dosyaları hazırlayın
Sunucu için 3 dosyaya ihtiyacınız var:
  - lisans_sunucu.py
  - requirements.txt
  - Procfile  (içeriği: web: uvicorn lisans_sunucu:app --host 0.0.0.0 --port $PORT)

### 1.2 — GitHub'a yükleyin
Bir GitHub repo açın ve bu 3 dosyayı yükleyin.

### 1.3 — Railway'de deploy edin
1. https://railway.app adresine gidin → GitHub ile üye olun
2. "New Project" → "Deploy from GitHub Repo" → reponuzu seçin
3. Deploy tamamlanınca size bir URL verilir:
   Örn: https://opc-gateway-lisans.up.railway.app

### 1.4 — Ortam değişkenlerini girin (çok önemli!)
Railway panelinde "Variables" sekmesine gidin ve ekleyin:
  SECRET_KEY  = istediğiniz_gizli_anahtar_buraya   (en az 32 karakter)
  PANEL_SIFRE = yonetim_paneli_sifreniz

---

## ADIM 2: gateway_v4_hwid.py'yi Yapılandırın

Dosyanın en üstündeki şu satırları düzenleyin:

```python
SUNUCU_URL       = "https://opc-gateway-lisans.up.railway.app"  # Railway URL'niz
UYGULAMA_SIFRESI = "istediğiniz_gizli_anahtar_buraya"           # SECRET_KEY ile AYNI olmalı
```

---

## ADIM 3: İlk Lisansı Oluşturun

### Yöntem A — Tarayıcı Paneli (Kolay)
1. https://opc-gateway-lisans.up.railway.app/panel adresine gidin
2. Panel şifrenizi girin
3. "Yeni Lisans Oluştur" bölümünden istediğiniz türü seçin
4. "Lisans Oluştur" butonuna basın
5. Oluşturulan kodu (ör: AYL-A3F2-9B1C-4E7D) müşteriye gönderin

### Yöntem B — API ile (Programatik)
```bash
curl -X POST https://opc-gateway-lisans.up.railway.app/panel/lisans-olustur \
  -H "Authorization: Bearer PANEL_SIFRENIZ" \
  -H "Content-Type: application/json" \
  -d '{"musteri_adi":"Ahmet Yilmaz","tur":"aylik","musteri_email":"ahmet@firma.com"}'
```

---

## ADIM 4: Müşteri Akışı

1. Müşteri EXE'yi açar → "Lisans kontrolü..." ekranı görür
2. Lisansı yoksa "Aktivasyon Ekranı" açılır
3. HWID otomatik gösterilir (müşteri bunu size göndermek zorunda değil)
4. Müşteri lisans kodunu yapıştırır → "Aktive Et"
5. Sunucu doğrular → %100ms içinde program açılır
6. Sonraki açılışlarda (7 gün içinde) tamamen offline çalışır

---

## Lisans Türleri

| Tür       | Süre          | Kod Prefix |
|-----------|---------------|------------|
| Aylık     | 30 gün        | AYL-       |
| Yıllık    | 365 gün       | YIL-       |
| Ömür Boyu | Süresiz       | OBY-       |
| Deneme    | Sizin belirlediğiniz (saat) | DEN- |

Deneme süresi için "deneme_saat" değerini istediğiniz gibi ayarlayın:
  2 saat → deneme_saat: 2
  48 saat → deneme_saat: 48
  1 hafta → deneme_saat: 168

---

## Müşteri Bilgisayarı Değiştiğinde

Panel'e gidin → Lisans kodunu girin → "HWID Sıfırla" butonuna basın.
Müşteri yeni bilgisayarında EXE'yi açtığında yeni HWID otomatik kaydedilir.

---

## PyInstaller ile EXE Yapma

```bash
pip install pyinstaller
pyinstaller --onefile --windowed --name OPCGateway gateway_v4_hwid.py
```

EXE dist/ klasöründe oluşur. Bu tek dosyayı müşteriye verin.

---

## Güvenlik Notları

- SUNUCU_URL ve UYGULAMA_SIFRESI EXE içinde gömülüdür.
  Nuitka ile derleme bu değerlerin okunmasını çok zorlaştırır.
- SECRET_KEY'i Railway "Variables" dışında kimseyle paylaşmayın.
- Panel URL'si (/panel) herkese açıktır ama şifre korumalıdır.
  Ekstra güvenlik için Railway'de "Private Network" moduna alabilirsiniz.
