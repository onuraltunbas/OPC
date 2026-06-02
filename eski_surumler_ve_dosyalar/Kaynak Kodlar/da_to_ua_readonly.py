# OPC-DA TO OPC-UA GATEWAY



#----------KURULUM----------
# 1) https://www.python.org/ftp/python/3.13.13/python-3.13.13.exe linki ile gerekli olan python sürümünü indirebilirsiniz.
# Eğer python kurulu ise 32-bit olmalıdır.
# 2) Bu komut satırını CMD'yi yönetici olarak açıp çalıştırınız.
# pip install OpenOPC-Python3x asyncua pywin32 pyro4
# 3) Eğer DLL hatası alırsanız aşağıdaki komutu CMD'yi yönetici olarak çalıştırıp bu komut satırını çalıştırınız.
# python -m pywin32_postinstall -install 
# 4) Microsoft Visual C++ hatası alırsanız aşağıdaki linkten indirip kurunuz.
# https://download.microsoft.com/download/1/6/5/165255e7-1014-4d0a-b094-b6a430a6bffc/vcredist_x86.exe
# 5) Bilgisayardaki DA suncularının PogID sini öğrenmek için aşağıdaki komutu CMD'yi yönetici olarak çalıştırıp bu komut satırını çalıştırınız.
# python -c "import OpenOPC; opc=OpenOPC.client(); print('\n'.join(opc.servers()))"
# Bağlanılan herhangi bir OPC sunucusunun içindeki tüm klasörleri ve altındaki etiketleri (sensörleri) görmek için CMD'yi yönetici olarak çalıştırıp aşağıdaki komut satırını çalıştırınız.
# python -c "import OpenOPC; opc=OpenOPC.client(); opc.connect('BURAYA ProgID GİRİNİZ'); print('\n'.join(opc.list('**')))"

#----------KULLANIM----------
# Önce bu kodu çalıştırınız. Daha sonra diğer adımlara geçiniz.
# UA Expert gibi programlarda verileri görüntülemek için OPC DA nın olduğu bilgisayarın ip adresi görüntüleme programına aşağıdaki şekilde girilmelidir.
# opc.tcp://X.X.X.X:4840/
# IP adresinizi öğrenmek için CMD üzerinden ipconfig komutu çalıştırılarak IP adresi öğrenilebilir.


import asyncio
import OpenOPC
from asyncua import Server, ua
import pythoncom
import copyreg
import pywintypes
import datetime

# Matrikon Explorer'da gördüğün tam Item ID'leri buraya yaz
IZLENECEK_ETIKETLER = [
    'sicaklik',  # Örnek olarak eklenen, senin oluşturduğun özel etiketin (Alias) adı.
    'Random.Real8'      # Yedek olarak Matrikon'un kendi hazır verisi (Sistemin kod hatası olmadan çalışıp çalışmadığını test etmek içindir).
]

# --- PICKLE ÇÖZÜMÜ --- (Windows'un saat ayarlarıyla alakalı bir paket değişikliği çözümü)
def windows_saatini_cevir(dt):
    return datetime.datetime, (dt.year, dt.month, dt.day, dt.hour, dt.minute, dt.second, dt.microsecond)
copyreg.pickle(type(pywintypes.Time(1)), windows_saatini_cevir)

async def main():
    ua_server = Server()
    await ua_server.init()
    ua_server.set_endpoint("opc.tcp://0.0.0.0:4840/")
    ua_server.set_server_name("UA_Gateway")

    uri = "http://da_to_ua/monitoring" 
    idx = await ua_server.register_namespace(uri) 
    objects = ua_server.nodes.objects 
    ana_depo = await objects.add_object(idx, "Saha_Izleme_Verileri") 
    
    etiket_haritasi = {} 

    async with ua_server:
        print("🚀Başlatıldı!") 
        
        pythoncom.CoInitialize()
        opc = OpenOPC.client() 
        opc.connect('BURAYA ProgID GİRİNİZ') #DA ProgID giriniz.
        
        print("🔗 Matrikon bağlantısı kuruldu. Etiketler ekleniyor...") 

        for etiket in IZLENECEK_ETIKETLER: 
            try: 
                ham = opc.read(etiket) 
                ua_isim = etiket.replace('.', '_').replace(' ', '_') 
                
                
                node = await ana_depo.add_variable(idx, ua_isim, 0.0, ua.VariantType.Double) 
                etiket_haritasi[etiket] = node 
                print(f"✅ Eklendi: {etiket}") 
            except Exception as e:
                print(f"❌ Hata: {etiket} bulunamadı! ({e})") 

        while True: 
            try:
                okumalar = opc.read(list(etiket_haritasi.keys())) 
                
                for etiket_adi, deger, kalite, zaman in okumalar: 
                    if deger is not None: 
                        node = etiket_haritasi[etiket_adi]
                        await node.write_value(float(deger), ua.VariantType.Double)
                
                print(f"🔄 Veri Akışı Aktif: {len(okumalar)} Etiket Güncellendi.")
            except Exception as e:
                print(f"⚠️ Akış hatası: {e}")
                await asyncio.sleep(2)
            
            await asyncio.sleep(1) 

if __name__ == "__main__":
    import sys
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())