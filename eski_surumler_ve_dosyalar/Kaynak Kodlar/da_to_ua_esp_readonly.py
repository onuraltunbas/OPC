import asyncio
import OpenOPC
from asyncua import Server, ua
import pythoncom
import copyreg
import pywintypes
import datetime

# --- MANUEL AYARLAR ---
# Matrikon'da yarattığın gerçek sensör etiketleri (Harf duyarlılığına dikkat!)
IZLENECEK_ETIKETLER = [
    'mesafe',
    'saglik'
]

# --- PICKLE ÇÖZÜMÜ ---
def windows_saatini_cevir(dt):
    return datetime.datetime, (dt.year, dt.month, dt.day, dt.hour, dt.minute, dt.second, dt.microsecond)
copyreg.pickle(type(pywintypes.Time(1)), windows_saatini_cevir)

async def main():
    ua_server = Server()
    await ua_server.init()
    # Tüm ağlardan dinlemeye aç (Monster laptop için)
    ua_server.set_endpoint("opc.tcp://0.0.0.0:4840/")
    ua_server.set_server_name("Mevlana_ESP32_Gateway")

    uri = "http://mevlana/sahadan"
    idx = await ua_server.register_namespace(uri)
    objects = ua_server.nodes.objects
    ana_depo = await objects.add_object(idx, "Gercek_Saha_Verileri")
    
    etiket_haritasi = {} 

    async with ua_server:
        print("🚀 Mevlana ESP32 Modu Başlatıldı!")
        
        pythoncom.CoInitialize()
        opc = OpenOPC.client()
        # Matrikon Modbus sunucusuna bağlan (Simülasyon değil!)
        opc.connect('Matrikon.OPC.Modbus.1') 
        
        print("🔗 Matrikon Modbus bağlantısı kuruldu. Sensörler aranıyor...")

        # Etiketleri UA Sunucusunda oluştur
        for etiket in IZLENECEK_ETIKETLER:
            try:
                ham = opc.read(etiket)
                ilk_val = ham[0]
                ua_isim = etiket.replace('.', '_').replace(' ', '_')
                
                # Tip belirleme (Mesafe sayı, Sağlık boolean)
                if isinstance(ilk_val, bool):
                    v_type, init_val = ua.VariantType.Boolean, False
                else:
                    v_type, init_val = ua.VariantType.Double, 0.0

                node = await ana_depo.add_variable(idx, ua_isim, init_val, v_type)
                etiket_haritasi[etiket] = {'node': node, 'type': v_type}
                print(f"✅ Eklendi: {etiket} (Tip: {v_type})")
            except Exception as e:
                print(f"❌ Hata: {etiket} bulunamadı! ({e})")

        # Sürekli Okuma Döngüsü
        while True:
            try:
                okumalar = opc.read(list(etiket_haritasi.keys()))
                
                for etiket_adi, deger, kalite, zaman in okumalar:
                    if deger is not None:
                        bilgi = etiket_haritasi[etiket_adi]
                        # Tipine göre UA'ya yaz
                        if bilgi['type'] == ua.VariantType.Double:
                            val = float(deger) if str(deger).replace('.','',1).isdigit() else 0.0
                            await bilgi['node'].write_value(val, bilgi['type'])
                        else:
                            await bilgi['node'].write_value(bool(deger), bilgi['type'])
                
                print(f"🔄 CANLI VERİ: Mesafe ve Sağlık durumu UaExpert'e iletiliyor...")
            except Exception as e:
                print(f"⚠️ Akış hatası, Matrikon kontrol ediliyor: {e}")
                await asyncio.sleep(2)
            
            await asyncio.sleep(0.5) # Gerçek sensör için tepkime süresini hızlandırdık (Yarım saniye)

if __name__ == "__main__":
    import sys
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())