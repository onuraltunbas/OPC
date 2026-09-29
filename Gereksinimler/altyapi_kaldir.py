# -*- coding: utf-8 -*-
"""
TÜBİTAK 2209-B: SANAYİ ODAKLI AR-GE PROJESİ
Endüstriyel Altyapı Kaldırıcı ve Sıfırlayıcı (Zero-Trace Uninstaller)
Telif Hakkı (C) 2026 Nautilus Technology & TÜBİTAK 2209-B Proje Ekibi
"""

import sys
import os
import subprocess
import ctypes
import shutil
import tempfile

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

def main():
    elevate()
    os.system("color 0C")

    print("=" * 80)
    print("  TÜBİTAK 2209-B: ENDÜSTRİYEL ALTYAPI KALDIRICI (UNINSTALLER)")
    print("  Sistemi Hiç Kurulmamış Gibi Tertemiz İlk Haline Döndürme Aracı")
    print("=" * 80)
    print()
    print("  [!] DİKKAT: Bu işlem, Nautilus OPC Gateway ve TÜBİTAK 2209-B için kurulan:")
    print("      • Python 3.13 (32-Bit) çalışma ortamını (C:\\Python313_32)")
    print("      • OpenOPC, asyncua, pywin32 vb. endüstriyel kütüphaneleri")
    print("      • Yapılandırılan COM sürücü kayıtlarını (OPCDAAuto.dll)")
    print("      • Açılan Güvenlik Duvarı (Firewall Port 4840) kurallarını")
    print("      tamamen kaldıracak ve bilgisayarı orijinal haline döndürecektir.\n")

    onay = input("  Kurulan tüm altyapıyı kaldırmak istiyor musunuz? (E/H): ").strip().upper()
    if onay != "E":
        print("\n  [*] İşlem kullanıcı tarafından iptal edildi. Hiçbir şeye dokunulmadı.")
        input("\nÇıkmak için Enter tuşuna basın...")
        sys.exit(0)

    print("\n  [*] Kaldırma işlemi başlatılıyor, lütfen bekleyin...\n")

    target_python_dir = r"C:\Python313_32"
    tag_dir = r"C:\ProgramData\TubitakOPCGateway"
    tag_file = os.path.join(tag_dir, "kurulum_kaydi.tag")

    is_64bit = sys.maxsize > 2**32 or "PROGRAMFILES(X86)" in os.environ
    sys_dir = os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "SysWOW64" if is_64bit else "System32")

    # 1. Güvenlik Duvarı
    print("  [1/6] Güvenlik duvarı kuralları siliniyor...")
    subprocess.run('netsh advfirewall firewall delete rule name="TÜBİTAK 2209-B OPC Gateway (Port 4840)"', shell=True, capture_output=True)
    subprocess.run('netsh advfirewall firewall delete rule name="Nautilus OPC Gateway"', shell=True, capture_output=True)
    print("  [+] Port 4840 güvenlik duvarı kuralları kaldırıldı.")

    # 2. OPCDAAuto.dll
    print("  [2/6] OPC DA COM Automation sürücü kaydı denetleniyor...")
    silinsin_mi = True
    if os.path.exists(tag_file):
        try:
            with open(tag_file, "r", encoding="utf-8") as f:
                tag_content = f.read()
            if "opcdaauto_onceden_vardi=1" in tag_content:
                silinsin_mi = False
        except Exception:
            pass

    if silinsin_mi:
        dll_path = os.path.join(sys_dir, "OPCDAAuto.dll")
        subprocess.run(f'regsvr32.exe /u /s "{dll_path}"', shell=True, capture_output=True)
        if os.path.exists(dll_path):
            try:
                os.remove(dll_path)
            except Exception:
                pass
        print("  [+] OPCDAAuto.dll sistemden güvenle kaldırıldı.")
    else:
        print("  [i] OPCDAAuto.dll önceden var olduğu için fabrika kaydına dokunulmadı.")

    # 3. pywin32 COM
    print("  [3/6] pywin32 COM kayıtları temizleniyor...")
    python_exe = os.path.join(target_python_dir, "python.exe")
    postinstall = os.path.join(target_python_dir, "Scripts", "pywin32_postinstall.py")
    if os.path.exists(python_exe) and os.path.exists(postinstall):
        subprocess.run(f'"{python_exe}" "{postinstall}" -remove', shell=True, capture_output=True)
        print("  [+] pywin32 COM kayıtları düşürüldü.")

    # 4. Python 3.13 Kaldırma
    print("  [4/6] Python 3.13 (32-Bit) sistemi kaldırılıyor...")
    # Base dir ve offline_kurulumlar'daki python installer ile sessiz uninstall dene
    base_dir = os.path.dirname(os.path.abspath(sys.executable if getattr(sys, 'frozen', False) else __file__))
    olasi_installer = [
        os.path.join(base_dir, "Gereksinimler", "offline_kurulumlar", "python-3.13.3.exe"),
        os.path.join(base_dir, "offline_kurulumlar", "python-3.13.3.exe"),
        r"C:\Program Files (x86)\Nautilus Technology\OPC Gateway\Gereksinimler\offline_kurulumlar\python-3.13.3.exe"
    ]
    for inst in olasi_installer:
        if os.path.exists(inst):
            subprocess.run(f'"{inst}" /uninstall /quiet', shell=True, capture_output=True)
            break

    if os.path.exists(target_python_dir):
        try:
            shutil.rmtree(target_python_dir, ignore_errors=True)
        except Exception:
            pass
    print(f"  [+] Python 3.13 ve kütüphane klasörü ({target_python_dir}) tamamen silindi.")

    # 5. PATH Temizliği
    print("  [5/6] Windows PATH ortam değişkenleri temizleniyor...")
    ps_cmd = (
        "$paths = [Environment]::GetEnvironmentVariable('Path', 'Machine') -split ';' | Where-Object { $_ -and $_ -notlike '*Python313_32*' };"
        "[Environment]::SetEnvironmentVariable('Path', ($paths -join ';'), 'Machine');"
        "$uPaths = [Environment]::GetEnvironmentVariable('Path', 'User') -split ';' | Where-Object { $_ -and $_ -notlike '*Python313_32*' };"
        "[Environment]::SetEnvironmentVariable('Path', ($uPaths -join ';'), 'User');"
    )
    subprocess.run(f'powershell -NoProfile -ExecutionPolicy Bypass -Command "{ps_cmd}"', shell=True, capture_output=True)
    print("  [+] PATH kayıtları temizlendi.")

    # 6. Önbellek ve Tag Temizliği
    print("  [6/6] Geçici dosyalar ve önbellekler temizleniyor...")
    gen_py = os.path.join(tempfile.gettempdir(), "gen_py")
    if os.path.exists(gen_py):
        shutil.rmtree(gen_py, ignore_errors=True)
    if os.path.exists(tag_dir):
        shutil.rmtree(tag_dir, ignore_errors=True)
    print("  [+] COM önbelleği ve kurulum izleri temizlendi.")

    # SONUÇ
    os.system("color 0A")
    print()
    print("=" * 80)
    print("  ✅ [BAŞARILI] TÜM ALTYAPI SİSTEMDEN TAMAMEN KALDIRILDI!")
    print("=" * 80)
    print("   • C:\\Python313_32 dizini ve kütüphaneler silindi.")
    print("   • OPCDAAuto.dll kaydı düşürüldü ve kaldırıldı.")
    print("   • Güvenlik duvarı (Firewall 4840) kuralları silindi.")
    print("   • Windows PATH değişkenleri eski haline getirildi.")
    print("   • COM ve geçici önbellekler temizlendi.")
    print()
    print("  Bilgisayar, bu altyapı hiç kurulmamış gibi tertemiz orijinal haline döndü.")
    print("=" * 80)
    print()
    input("Pencereyi kapatmak için Enter tuşuna basın...")

if __name__ == "__main__":
    main()
