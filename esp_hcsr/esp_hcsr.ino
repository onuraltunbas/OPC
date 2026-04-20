#include <WiFi.h>
#include <ModbusIP_ESP8266.h>

// --- KULLANICI AYARLARI ---
const char* ssid = "onur";         // Bağlandığın WiFi adı
const char* password = "123456789";   // WiFi şifren

const int trigPin = 26; 
const int echoPin = 25; 

ModbusIP mb; // Modbus nesnesi

void setup() {
  Serial.begin(115200);

  // Mesafe Sensörü Pin Ayarları
  pinMode(trigPin, OUTPUT);
  pinMode(echoPin, INPUT);

  // WiFi Bağlantısı
  WiFi.begin(ssid, password);
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  
  Serial.println("\n✅ WiFi Baglandi!");
  Serial.print("🛑 ESP32 IP ADRESI: ");
  Serial.println(WiFi.localIP());

  // Modbus Sunucu Ayarları
  mb.server(502);    // Kapıyı (Port 502) açıkça belirtiyoruz
  mb.addHreg(1, 0);  // Adres 40001 (Mesafe verisi için)
  mb.addCoil(1, 0);  // Adres 00001 (Sistem sağlık durumu için)
}

void loop() {
  // Modbus iletişimini hayatta tut (Kilitlenmeyi önler)
  mb.task(); 

  // --- Mesafe Ölçüm Döngüsü ---
  digitalWrite(trigPin, LOW);
  delayMicroseconds(2);
  digitalWrite(trigPin, HIGH);
  delayMicroseconds(10);
  digitalWrite(trigPin, LOW);

  // Kilitlenmeyi önleyen 30ms'lik kritik zaman aşımı
  long duration = pulseIn(echoPin, HIGH, 30000); 
  
  int distance = 0;
  bool isHealthy = false;

  if (duration == 0) {
    // Sensörden yankı gelmedi (Kablo kopuk veya mesafe dışı)
    distance = 0;
    isHealthy = false;
    Serial.println("⚠️ Sensör Hatası: Yankı Alınamadı!");
  } else {
    // Mesafe hesaplama (Ses hızı formülü)
    // $$ \text{mesafe} = \frac{\text{süre} \times 0.034}{2} $$
    distance = duration * 0.034 / 2;
    isHealthy = true;
    
    Serial.print("📏 Mesafe: ");
    Serial.print(distance);
    Serial.println(" cm");
  }

  // --- Verileri Modbus Register'larına Yaz ---
  // Matrikon ve QModMaster bu adresleri okuyacak
  mb.Hreg(1, distance);  // 40001 nolu adrese mesafe yazılır
  mb.Coil(1, isHealthy); // 00001 nolu adrese True/False yazılır

  delay(200); // İşlemciyi yormamak için kısa bir bekleme
}