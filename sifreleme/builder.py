import os
import sys
import base64
import subprocess
import marshal
import shutil
from cryptography.fernet import Fernet

try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass


CUSTOM_ALPHABET = "АБВГДЕЖЗИЙКЛМНОПРСТУФХЦЧШЩЪЫЬЭЮЯ汉字龙书Ω∑∞∫≈≠≤≥★♦♣♠♥♩♪♫♬♔♕♖♗♘♙♚♛♜♝♞"
BASE64_ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/"

def custom_encode(data: bytes) -> str:
    b64 = base64.b64encode(data).decode('ascii').rstrip('=')
    return b64.translate(str.maketrans(BASE64_ALPHABET, CUSTOM_ALPHABET))

# ---------------------------------------------------------------
# Derlenecek hedef uygulamalar listesi
# Format: { "EXE_Adı": { "yol": "...", "console": bool } }
# ---------------------------------------------------------------
hedef_uygulamalar = {
    # 1. Normal Lisanslı Sürümler
    "OPC_Gateway_Pro": {
        "yol": os.path.join('..', 'Kaynak Kodlar', 'HWID_version', 'gateway_v5.0.py'),
        "console": False
    },
    "OPC_Viewer_Pro": {
        "yol": os.path.join('..', 'Kaynak Kodlar', 'HWID_version', 'NautilusViewer.py'),
        "console": False
    },

    # 2. Unlocked / Lisanssız Sürümler
    "OPC_Gateway_Unlocked": {
        "yol": os.path.join('..', 'Kaynak Kodlar', 'HWID_version', 'gateway_v5.0_unlocked.py'),
        "console": False
    },
    "OPC_Viewer_Unlocked": {
        "yol": os.path.join('..', 'Kaynak Kodlar', 'HWID_version', 'NautilusViewer_unlocked.py'),
        "console": False
    },

    # 3. Altyapı Yönetim Araçları (Şifreli Konsol Araçları)
    "Altyapi_Kurulumu": {
        "yol": os.path.join('..', 'Gereksinimler', 'altyapi_kurulumu.py'),
        "console": True
    },
    "Altyapi_Kaldir": {
        "yol": os.path.join('..', 'Gereksinimler', 'altyapi_kaldir.py'),
        "console": True
    },
}

def build_simple_fortress():
    current_dir = os.path.dirname(os.path.abspath(__file__))

    for output_name, config in hedef_uygulamalar.items():
        target_py = os.path.normpath(os.path.join(current_dir, config["yol"]))
        is_console = config.get("console", False)

        print(f"\n{'='*65}")
        print(f"[*] Hedef : {os.path.basename(target_py)}  ->  {output_name}.exe (Console={is_console})")
        print(f"{'='*65}")

        if not os.path.exists(target_py):
            print(f"[-] Hata: {target_py} bulunamadı! Bu hedef atlanıyor...")
            continue

        print("[*] Kod okunuyor ve şifreleniyor...")
        with open(target_py, 'rb') as f:
            original_code = f.read()

        # --- ŞİFRELEME BLOĞU (Fernet AES-128-CBC + Custom Symbol Encoding) ---
        key = Fernet.generate_key()
        compiled_code = marshal.dumps(compile(original_code, os.path.basename(target_py), 'exec'))
        encrypted_payload = custom_encode(Fernet(key).encrypt(compiled_code))
        # ---------------------------------------------------------------------

        loader_code = f"""
import ctypes, sys, time, base64, marshal
from cryptography.fernet import Fernet

def check_security():
    # Sadece temel Anti-Debug (Hacker Savar)
    if ctypes.windll.kernel32.IsDebuggerPresent(): sys.exit(1)
    t = time.perf_counter()
    time.sleep(0.01)
    if (time.perf_counter() - t) > 0.1: sys.exit(1)

def run():
    check_security()
    
    _K = {key}
    _M = "{encrypted_payload}"
    _A = "{CUSTOM_ALPHABET}"
    _S = "{BASE64_ALPHABET}"
    
    # Özel alfabeden geri dön
    b64 = _M.translate(str.maketrans(_A, _S))
    b64 += "=" * ((-len(b64)) % 4)
    raw = base64.b64decode(b64)
    
    # Şifreyi çöz ve RAM'de çalıştır
    dec = Fernet(_K).decrypt(raw)
    exec(marshal.loads(dec), globals())

if __name__ == "__main__":
    run()
"""

        temp_loader_path = os.path.join(current_dir, "temp_loader.py")
        with open(temp_loader_path, "w", encoding="utf-8") as f:
            f.write(loader_code)

        print("[*] EXE derleniyor...")
        logo_path     = os.path.join(current_dir, "logo.ico")
        ver_path      = os.path.join(current_dir, "ver.txt")
        manifest_path = os.path.join(current_dir, "app.manifest")

        hidden_imports = [
            # --- OpenOPC / Win32 ---
            "--hidden-import=OpenOPC",
            "--hidden-import=pywin32",
            "--hidden-import=pythoncom",
            "--hidden-import=pywintypes",
            # --- PyQt5 (eksiksiz) ---
            "--hidden-import=PyQt5",
            "--hidden-import=PyQt5.QtCore",
            "--hidden-import=PyQt5.QtGui",
            "--hidden-import=PyQt5.QtWidgets",
            "--hidden-import=PyQt5.QtNetwork",
            "--hidden-import=PyQt5.QtOpenGL",
            "--hidden-import=PyQt5.sip",
            # --- OPC-UA ---
            "--hidden-import=asyncua",
            "--hidden-import=asyncua.client",
            "--hidden-import=asyncua.server",
            "--hidden-import=asyncua.common",
            # --- Kriptografi (eksiksiz) ---
            "--hidden-import=cryptography",
            "--hidden-import=cryptography.fernet",
            "--hidden-import=cryptography.hazmat",
            "--hidden-import=cryptography.hazmat.primitives",
            "--hidden-import=cryptography.hazmat.primitives.ciphers",
            "--hidden-import=cryptography.hazmat.backends",
            "--hidden-import=cryptography.hazmat.backends.openssl",
            # --- Donanım Sürücüleri ---
            "--hidden-import=drivers",
            "--hidden-import=drivers.scanner",
            "--hidden-import=drivers.s7_driver",
            "--hidden-import=drivers.modbus_driver",
            "--hidden-import=drivers.qt_compat",
            # --- Standart kütüphane ---
            "--hidden-import=asyncio",
            "--hidden-import=urllib.request",
            "--hidden-import=urllib.error",
        ]

        console_flag = "--console" if is_console else "--noconsole"
        hwid_dir = os.path.normpath(os.path.join(current_dir, '..', 'Kaynak Kodlar', 'HWID_version'))
        drivers_dir = os.path.join(hwid_dir, 'drivers')

        pyinstaller_cmd = [
            "pyinstaller", "--onefile", console_flag,
            "--noupx", "--name=" + output_name,
            f"--icon={logo_path}",
            f"--version-file={ver_path}",
            f"--manifest={manifest_path}",
            f"--paths={hwid_dir}",
            f"--add-data={logo_path};.",
            f"--add-data={drivers_dir};drivers",
        ] + hidden_imports + [temp_loader_path]

        subprocess.run(pyinstaller_cmd, shell=True, cwd=current_dir)

        # Her derleme sonrasında temp_loader temizlenir
        if os.path.exists(temp_loader_path):
            os.remove(temp_loader_path)
            print(f"[*] temp_loader.py silindi.")

        # setup/dist klasörüne otomatik kopyala
        setup_dist = os.path.join(current_dir, '..', 'setup', 'dist')
        os.makedirs(setup_dist, exist_ok=True)
        src_exe = os.path.join(current_dir, 'dist', f"{output_name}.exe")
        dst_exe = os.path.join(setup_dist, f"{output_name}.exe")
        if os.path.exists(src_exe):
            shutil.copy2(src_exe, dst_exe)
            print(f"[+] {output_name}.exe -> setup/dist/ klasörüne kopyalandı.")

        # Eğer Altyapı aracı ise Gereksinimler klasörüne de kopyala
        if output_name in ("Altyapi_Kurulumu", "Altyapi_Kaldir"):
            gereksinimler_dir = os.path.join(current_dir, '..', 'Gereksinimler')
            os.makedirs(gereksinimler_dir, exist_ok=True)
            dst_ger = os.path.join(gereksinimler_dir, f"{output_name}.exe")
            if os.path.exists(src_exe):
                shutil.copy2(src_exe, dst_ger)
                print(f"[+] {output_name}.exe -> Gereksinimler/ klasörüne kopyalandı.")

        print(f"[+] BİTTİ! sifreleme/dist/{output_name}.exe hazır.")

    print("\n" + "="*65)
    print("[TAMAMLANDI] TÜM ŞİFRELİ EXE'LER BAŞARIYLA DERLENDİ!")
    print("="*65)

if __name__ == "__main__":
    build_simple_fortress()