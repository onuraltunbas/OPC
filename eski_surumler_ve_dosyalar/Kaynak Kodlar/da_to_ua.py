import asyncio
import OpenOPC
from asyncua import Server
import copyreg
import pywintypes
import datetime

# Pickle Hatası Çözümü
def windows_saatini_cevir(dt):
    return datetime.datetime, (dt.year, dt.month, dt.day, dt.hour, dt.minute, dt.second, dt.microsecond)
copyreg.pickle(type(pywintypes.Time(1)), windows_saatini_cevir)

async def main():
    # ==========================================
    # 1. OPC UA SUNUCUSUNU (VİTRİNİ) HAZIRLA
    # ==========================================
    ua_server = Server()
    await ua_server.init()
    ua_server.set_endpoint("opc.tcp://0.0.0.0:4840/")
    ua_server.set_server_name("Mevlana_Gateway")

    uri = "http://mevlana/gateway"
    idx = await ua_server.register_namespace(uri)
    objects = ua_server.nodes.objects
    
    # Vitrindeki Klasör ve Değişkenler (Farklı Veri Tipleri)
    fabrika_klasoru = await objects.add_object(idx, "Veriler")
    
    node_sicaklik = await fabrika_klasoru.add_variable(idx, "Kazan_Sicakligi_Real8", 0.0)
    node_basinc = await fabrika_klasoru.add_variable(idx, "Valf_Basinci_Int4", 0)
    node_motor = await fabrika_klasoru.add_variable(idx, "Motor_Durumu_Bool", False)

    await node_sicaklik.set_writable()
    await node_basinc.set_writable()
    await node_motor.set_writable()

    # ==========================================
    # 2. BAĞLANTIYI VE AKIŞI YÖNETEN ANA DÖNGÜ
    # ==========================================
    async with ua_server:
        print("🚀 Mevlana Ağ Geçidi YAYINDA!")
        print("👉 UaExpert ile şu adrese bağlan: opc.tcp://127.0.0.1:4840")
        print("-" * 50)

        # OPC DA İstemcisini oluşturuyoruz
        opc = OpenOPC.client()
        baglantı_var = False

        while True:
            # EĞER BAĞLANTI YOKSA, BAĞLANMAYA ÇALIŞ (Ölümsüzlük Döngüsü)
            if not baglantı_var:
                try:
                    opc.connect('Matrikon.OPC.Simulation.1')
                    print("✅ Matrikon DA Sunucusuna Bağlanıldı! Veri akışı başlıyor...")
                    baglantı_var = True
                except Exception:
                    print("⏳ Matrikon DA aranıyor... (Lütfen Matrikon'u açın)")
                    await asyncio.sleep(3)
                    continue # Bağlanana kadar bekle ve başa dön

           # BAĞLANTI VARSA VERİLERİ OKU VE ÇEVİR
            try:
                # 1. DÜZELTME: Matrikon'da kesin bulunan standart etiketler
                veriler = opc.read(['Random.Real8', 'Random.Int4', 'Random.Boolean'])
                
                deger_sicaklik = veriler[0][1]
                deger_basinc = veriler[1][1]
                deger_motor = veriler[2][1]

                # 2. DÜZELTME: Eğer Matrikon'dan 'None' gelirse sistemi çökertme, pas geç
                if deger_sicaklik is not None:
                    await node_sicaklik.write_value(float(deger_sicaklik)) # Kesinlikle ondalıklı sayı yap
                
                if deger_basinc is not None:
                    await node_basinc.write_value(int(deger_basinc)) # Kesinlikle tam sayı yap
                
                if deger_motor is not None:
                    await node_motor.write_value(bool(deger_motor)) # Kesinlikle True/False yap
                
                print(f"🔄 Aktarılan -> Sıcaklık: {deger_sicaklik} | Basınç: {deger_basinc} | Motor: {deger_motor}")
                
            except Exception as e:
                # 3. DÜZELTME: Sadece koptu demesin, asıl hatayı da ekrana yazdırsın ki görelim
                print(f"⚠️ Hata: {e}")
                await asyncio.sleep(2) # Hata verirse 2 saniye bekle
                # baglantı_var = False (Eğer hala sürekli başa sararsa bu satırı aktif ederiz)
            
            await asyncio.sleep(1)

if __name__ == "__main__":
    import sys
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())