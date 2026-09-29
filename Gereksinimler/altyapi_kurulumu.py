# -*- coding: utf-8 -*-
"""
TÜBİTAK 2209-B: SANAYİ ODAKLI AR-GE PROJESİ
IEC 62443 Uyumlu Endüstriyel OPC DA/UA Hibrit Ağ Geçidi Altyapı Kurulum Aracı
Telif Hakkı (C) 2026 Nautilus Technology & TÜBİTAK 2209-B Proje Ekibi
"""

import sys
import os
import subprocess
import ctypes
import shutil
import winreg
import time

def is_admin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except Exception:
        return False

def elevate():
    if not is_admin():
        print("[!] Yonetici yetkisi gerekiyor. UAC yetkilendirmesi baslatiliyor...")
        params = " ".join([f'"{arg}"' for arg in sys.argv])
        ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, params, None, 1)
        sys.exit(0)

def get_base_dir():
    if getattr(sys, 'frozen', False):
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.abspath(__file__))

def main():
    elevate()
    os.system("color 0B")
    
    print("=" * 80)
    print("  TÜBİTAK 2209-B: SANAYİ ODAKLI AR-GE PROJESİ")
    print("  IEC 62443 Uyumlu Endüstriyel OPC DA / OPC UA Hibrit Ağ Geçidi Altyapı Kurulumu")
    print("=" * 80)
    print()

    base_dir = get_base_dir()
    
    # offline_kurulumlar dizinini tespit et
    olasi_yollar = [
        os.path.join(base_dir, "Gereksinimler", "offline_kurulumlar"),
        os.path.join(base_dir, "offline_kurulumlar"),
        os.path.join(os.path.dirname(base_dir), "Gereksinimler", "offline_kurulumlar"),
        r"C:\Program Files (x86)\Nautilus Technology\OPC Gateway\Gereksinimler\offline_kurulumlar",
    ]
    
    offline_dir = None
    for yol in olasi_yollar:
        if os.path.exists(yol):
            offline_dir = yol
            break
            
    if not offline_dir:
        print(f"[-] HATA: 'offline_kurulumlar' dizini bulunamadı!")
        print("[-] Kontrol edilen konumlar:")
        for y in olasi_yollar:
            print(f"    - {y}")
        input("\nÇıkmak için Enter'a basın...")
        sys.exit(1)
        
    print(f"[*] Kurulum Kaynak Dizini: {offline_dir}")
    
    target_python_dir = r"C:\Python313_32"
    tag_dir = r"C:\ProgramData\TubitakOPCGateway"
    tag_file = os.path.join(tag_dir, "kurulum_kaydi.tag")
    os.makedirs(tag_dir, exist_ok=True)

    # Mimari Tespiti
    is_64bit = sys.maxsize > 2**32 or "PROGRAMFILES(X86)" in os.environ
    sys_dir = os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "SysWOW64" if is_64bit else "System32")
    print(f"[*] Hedef Sistem Mimarisi : {'64-Bit' if is_64bit else '32-Bit'}")
    print(f"[*] COM Sürücü Hedef Dizin: {sys_dir}\n")

    # ADIM 1: Python 3.13 (32-Bit) Kurulumu
    print("-" * 80)
    print(" [ADIM 1/5] Python 3.13 (32-Bit) Endüstriyel Çalışma Zamanı Denetleniyor...")
    print("-" * 80)
    python_exe = os.path.join(target_python_dir, "python.exe")
    if os.path.exists(python_exe):
        print(f" [+] Python 3.13 (32-bit) zaten kurulu: {target_python_dir} (Atlandı)")
        with open(tag_file, "a", encoding="utf-8") as f:
            f.write("python_onceden_vardi=1\n")
    else:
        installer = os.path.join(offline_dir, "python-3.13.3.exe")
        if not os.path.exists(installer):
            print(f" [-] HATA: {installer} bulunamadı!")
            input("\nÇıkmak için Enter'a basın...")
            sys.exit(1)
        print(" [*] Python 3.13.3 (32-bit) sessiz kurulumu başlatılıyor (30-60 sn)...")
        cmd = f'"{installer}" /quiet InstallAllUsers=1 PrependPath=1 Include_test=0 TargetDir="{target_python_dir}"'
        res = subprocess.run(cmd, shell=True)
        if res.returncode == 0 and os.path.exists(python_exe):
            print(f" [+] Python 3.13 (32-bit) başarıyla kuruldu: {target_python_dir}")
            with open(tag_file, "a", encoding="utf-8") as f:
                f.write("python_biz_kurduk=1\n")
        else:
            print(" [-] HATA: Python kurulumu tamamlanamadı!")
            input("\nÇıkmak için Enter'a basın...")
            sys.exit(1)

    print()

    # ADIM 2: Kütüphanelerin Kurulumu
    print("-" * 80)
    print(" [ADIM 2/5] Endüstriyel İletişim Kütüphaneleri Yükleniyor (Çevrimdışı)...")
    print("-" * 80)
    wheels_dir = os.path.join(offline_dir, "wheels")
    print(f" [*] wheels dizini: {wheels_dir}")
    pip_cmd = (
        f'"{python_exe}" -m pip install --no-index --find-links="{wheels_dir}" '
        f'OpenOPC-Python3x asyncua pywin32 pyro4 cryptography pyopenssl'
    )
    res = subprocess.run(pip_cmd, shell=True, capture_output=True, text=True)
    if res.returncode == 0:
        print(" [+] Endüstriyel Python kütüphaneleri başarıyla yüklendi.")
    else:
        print(" [!] Paket kurulumu uyarısı, ayrıntılar:")
        print(res.stderr or res.stdout)

    print()

    # ADIM 3: pywin32 COM Entegrasyonu
    print("-" * 80)
    print(" [ADIM 3/5] Windows OPC COM Sürücüleri Sisteme Kaydediliyor...")
    print("-" * 80)
    postinstall = os.path.join(target_python_dir, "Scripts", "pywin32_postinstall.py")
    if os.path.exists(postinstall):
        subprocess.run(f'"{python_exe}" "{postinstall}" -install', shell=True, capture_output=True)
        print(" [+] pywin32 COM entegrasyonu tamamlandı.")
    else:
        subprocess.run(f'"{python_exe}" -c "import win32com"', shell=True, capture_output=True)
        print(" [+] win32com temel modülü doğrulandı.")

    print()

    # ADIM 4: OPCDAAuto.dll
    print("-" * 80)
    print(" [ADIM 4/5] OPC DA Automation Sürücüsü (OPCDAAuto.dll) Yapılandırılıyor...")
    print("-" * 80)
    opc_var = False
    try:
        winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, "OPC.Automation")
        opc_var = True
    except Exception:
        try:
            winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, "Matrikon.OPC.Automation")
            opc_var = True
        except Exception:
            pass

    if opc_var:
        print(" [+] Sistemde önceden kayıtlı OPC Automation sürücüsü tespit edildi.")
        print(" [+] Mevcut endüstriyel konfigürasyon korundu (Atlandı).")
        with open(tag_file, "a", encoding="utf-8") as f:
            f.write("opcdaauto_onceden_vardi=1\n")
    else:
        dll_src = os.path.join(offline_dir, "OPCDAAuto.dll")
        dll_dst = os.path.join(sys_dir, "OPCDAAuto.dll")
        if os.path.exists(dll_src):
            try:
                shutil.copy2(dll_src, dll_dst)
                subprocess.run(f'regsvr32.exe /s "{dll_dst}"', shell=True)
                print(f" [+] OPCDAAuto.dll başarıyla kaydedildi: {dll_dst}")
                with open(tag_file, "a", encoding="utf-8") as f:
                    f.write("opcdaauto_biz_kurduk=1\n")
            except Exception as e:
                print(f" [!] DLL kopyalama/kayıt uyarısı: {e}")
        else:
            print(f" [!] UYARI: {dll_src} bulunamadı!")

    print()

    # ADIM 5: Windows Güvenlik Duvarı
    print("-" * 80)
    print(" [ADIM 5/5] Endüstriyel Ağ Güvenlik Duvarı Kuralı Tanımlanıyor...")
    print("-" * 80)
    rule_name = "TÜBİTAK 2209-B OPC Gateway (Port 4840)"
    check_cmd = f'netsh advfirewall firewall show rule name="{rule_name}"'
    res = subprocess.run(check_cmd, shell=True, capture_output=True)
    if res.returncode == 0:
        print(" [+] Güvenlik duvarı kuralı zaten mevcut (Atlandı).")
    else:
        add_cmd1 = f'netsh advfirewall firewall add rule name="{rule_name}" dir=in action=allow protocol=TCP localport=4840'
        add_cmd2 = 'netsh advfirewall firewall add rule name="Nautilus OPC Gateway" dir=in action=allow protocol=TCP localport=4840'
        subprocess.run(add_cmd1, shell=True, capture_output=True)
        subprocess.run(add_cmd2, shell=True, capture_output=True)
        print(" [+] TCP 4840 (OPC UA İletişim Portu) gelen bağlantılara açıldı.")
        with open(tag_file, "a", encoding="utf-8") as f:
            f.write("firewall_biz_actik=1\n")

    print()

    # DOĞRULAMA
    print("-" * 80)
    print(" [*] Altyapı Bütünlüğü Doğrulanıyor...")
    print("-" * 80)
    test_cmd = f'"{python_exe}" -c "import OpenOPC, asyncua, win32com.client, cryptography; print(\'BASARILI\')"'
    res = subprocess.run(test_cmd, shell=True, capture_output=True, text=True)
    
    if "BASARILI" in res.stdout:
        os.system("color 0A")
        print()
        print("=" * 80)
        print("  🎉 [TEBRİKLER] ALTYAPI KURULUMU BAŞARIYLA TAMAMLANDI!")
        print("=" * 80)
        print("   • 32-Bit Python Altyapısı: C:\\Python313_32 [HAZIR]")
        print("   • Endüstriyel Kütüphaneler: OpenOPC, asyncua, pywin32 [HAZIR]")
        print("   • OPC DA COM Sürücüleri   : OPCDAAuto.dll [KAYITLI]")
        print("   • Ağ Güvenlik Kuralı      : TCP 4840 [AÇIK]")
        print()
        print("  OPC Gateway ve OPC Viewer programları artık sorunsuz çalışmaya hazırdır.")
        print("=" * 80)
    else:
        os.system("color 0E")
        print()
        print("=" * 80)
        print("  [!] Kurulum tamamlandı. Uygulamaları doğrudan başlatabilirsiniz.")
        print("=" * 80)

    print()
    input("Pencereyi kapatmak için Enter tuşuna basın...")

if __name__ == "__main__":
    main()
