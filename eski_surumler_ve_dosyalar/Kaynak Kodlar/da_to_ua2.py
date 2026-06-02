import asyncio
import OpenOPC
from asyncua import Server, ua
import copyreg
import pywintypes
import datetime
import pythoncom

# --- PICKLE ÇÖZÜMÜ ---
def windows_saatini_cevir(dt):
    return datetime.datetime, (dt.year, dt.month, dt.day, dt.hour, dt.minute, dt.second, dt.microsecond)
copyreg.pickle(type(pywintypes.Time(1)), windows_saatini_cevir)

async def main():
    ua_server = Server()
    await ua_server.init()
    ua_server.set_endpoint("opc.tcp://0.0.0.0:4840/")
    ua_server.set_server_name("Mevlana_Smart_Type")

    uri = "http://mevlana/smart"
    idx = await ua_server.register_namespace(uri)
    objects = ua_server.nodes.objects
    ana_depo = await objects.add_object(idx, "Otomatik_Saha_Verileri")
    
    etiket_haritasi = {} # { 'DA_Etiket_Adı': { 'node': UA_Node, 'type': UA_Type } }

    async with ua_server:
        print("🚀 Mevlana Smart Type Gateway YAYINDA!")
        opc = None

        while True:
            if opc is None:
                try:
                    pythoncom.CoInitialize()
                    opc = OpenOPC.client()
                    opc.connect('Matrikon.OPC.Simulation.1')
                    
                    print("🔎 Sunucu taranıyor ve tipler belirleniyor...")
                    bulunanlar = opc.list('*', recursive=True)
                    
                    # İlk keşif anında tipleri belirleyelim
                    for etiket in bulunanlar:
                        if etiket not in etiket_haritasi:
                            try:
                                # Etiketi bir kez oku ki tipini anlayalım
                                ham = opc.read(etiket)
                                ilk_deger = ham[0] # Value kısmı
                                
                                ua_isim = etiket.replace('.', '_').replace(' ', '_')
                                
                                # Tip belirleme mantığı
                                if isinstance(ilk_deger, bool):
                                    v_type = ua.VariantType.Boolean
                                    başlangıç = False
                                elif isinstance(ilk_deger, (int, float)):
                                    v_type = ua.VariantType.Double
                                    başlangıç = 0.0
                                else:
                                    v_type = ua.VariantType.String
                                    başlangıç = ""

                                # Değişkeni doğru tiple oluştur
                                node = await ana_depo.add_variable(idx, ua_isim, başlangıç, v_type)
                                await node.set_writable()
                                
                                # Haritaya hem node'u hem tipini kaydet
                                etiket_haritasi[etiket] = {'node': node, 'type': v_type}
                            except:
                                continue # Okunamazsa pas geç
                    
                    print(f"✅ {len(etiket_haritasi)} etiket doğru tiplerle oluşturuldu!")
                    
                except Exception as e:
                    print(f"❌ Bağlantı Hatası: {e}")
                    opc = None
                    await asyncio.sleep(5)
                    continue

            # --- VERİ AKIŞI ---
            try:
                # Sadece haritadaki etiketleri oku
                okumalar = opc.read(list(etiket_haritasi.keys()))
                
                for etiket_adi, deger, kalite, zaman in okumalar:
                    if deger is not None:
                        bilgi = etiket_haritasi[etiket_adi]
                        ua_node = bilgi['node']
                        hedef_tip = bilgi['type']
                        
                        try:
                            # Veriyi hedeflenen tipe zorla çevirerek yaz
                            if hedef_tip == ua.VariantType.Double:
                                # Eğer içinden '()' gibi saçma bir şey gelirse 0 yap
                                val = float(deger) if str(deger).replace('.','',1).isdigit() else 0.0
                                await ua_node.write_value(val, hedef_tip)
                            elif hedef_tip == ua.VariantType.Boolean:
                                await ua_node.write_value(bool(deger), hedef_tip)
                            else:
                                await ua_node.write_value(str(deger), hedef_tip)
                        except:
                            continue # Yazma hatası olursa o anlık pas geç
                
            except Exception as e:
                print(f"⚠️ Akış hatası: {e}")
                await asyncio.sleep(2)
            
            await asyncio.sleep(1)

if __name__ == "__main__":
    import sys
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())