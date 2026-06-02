import asyncio
import OpenOPC
from asyncua import Server, ua
import pythoncom
import copyreg
import pywintypes
import datetime

# --- PICKLE ÇÖZÜMÜ ---
def windows_saatini_cevir(dt):
    return datetime.datetime, (dt.year, dt.month, dt.day, dt.hour, dt.minute, dt.second, dt.microsecond)
copyreg.pickle(type(pywintypes.Time(1)), windows_saatini_cevir)

# --- GLOBAL OPC NESNESİ (Dinleyici erişebilsin diye) ---
opc_client = None

# --- UA'DAN GELEN EMİRLERİ DİNLEYEN SINIF ---
class KontrolMerkezi:
    async def datachange_notification(self, node, val, data):
        global opc_client
        # Değişkenin adını alıyoruz (UaExpert'te hangi etiketi değiştirdin?)
        node_adi = (await node.read_browse_name()).Name
        
        # Eğer Matrikon bağlıysa, UA'dan gelen değeri DA'ya yaz!
        if opc_client:
            try:
                # UA'daki ismi tekrar DA formatına çeviriyoruz (Örn: Kazan_Motoru -> Kazan.Motoru)
                da_etiket_adi = node_adi.replace('_', '.')
                
                # Matrikon'a yazma emri!
                opc_client.write((da_etiket_adi, val))
                print(f"📥 KONTROL: UA'dan gelen emir -> {da_etiket_adi} = {val} (Matrikon'a yazıldı)")
            except Exception as e:
                print(f"❌ Yazma hatası: {e}")

async def main():
    global opc_client
    ua_server = Server()
    await ua_server.init()
    ua_server.set_endpoint("opc.tcp://0.0.0.0:4840/")
    
    idx = await ua_server.register_namespace("http://mevlana/control")
    objects = ua_server.nodes.objects
    kontrol_klasoru = await objects.add_object(idx, "Saha_Kontrol_Paneli")
    
    # KONTROL ETMEK İSTEDİĞİMİZ DEĞİŞKEN (Örn: Bir lamba veya motor)
    # Başlangıç değeri False (Kapalı)
    node_lamba = await kontrol_klasoru.add_variable(idx, "Lamba_Durumu", False)
    await node_lamba.set_writable() # Dışarıdan (UaExpert'ten) değiştirilebilir yaptık!

    async with ua_server:
        print("Mevlana Kontrol Sistemi")
        
        # --- ABONELİK KURULUMU (Dinleyiciyi başlat) ---
        handler = KontrolMerkezi()
        sub = await ua_server.create_subscription(500, handler)
        await sub.subscribe_data_change(node_lamba) # Bu değişkeni izle!

        while True:
            if opc_client is None:
                try:
                    pythoncom.CoInitialize()
                    opc_client = OpenOPC.client()
                    opc_client.connect('Matrikon.OPC.Simulation.1')
                    print("✅ Matrikon Bağlantısı Tamam!")
                except:
                    opc_client = None
                    await asyncio.sleep(3)
                    continue

            # İstersen burada hala DA'dan veri okumaya devam edebilirsin
            await asyncio.sleep(1)

if __name__ == "__main__":
    import sys
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())