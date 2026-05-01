import os
import sys
import base64
import subprocess
import marshal
from cryptography.fernet import Fernet


CUSTOM_ALPHABET = "АБВГДЕЖЗИЙКЛМНОПРСТУФХЦЧШЩЪЫЬЭЮЯ汉字龙书Ω∑∞∫≈≠≤≥★♦♣♠♥♩♪♫♬♔♕♖♗♘♙♚♛♜♝♞"
BASE64_ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/"

def custom_encode(data: bytes) -> str:
    b64 = base64.b64encode(data).decode('ascii').rstrip('=')
    return b64.translate(str.maketrans(BASE64_ALPHABET, CUSTOM_ALPHABET))

def build_simple_fortress():
    current_dir = os.path.dirname(os.path.abspath(__file__))
    target_py = os.path.join(current_dir, '..', 'Kaynak Kodlar', 'HWID_version', 'gateway_v5.0.py')
    output_name = "Nautilus_Gateway"
    
    if not os.path.exists(target_py):
        print(f"[-] Hata: {target_py} bulunamadı!")
        return

    print("[*] Kod okunuyor ve şifreleniyor...")
    with open(target_py, 'rb') as f:
        original_code = f.read()


    key = Fernet.generate_key()
    compiled_code = marshal.dumps(compile(original_code, 'gateway', 'exec'))
    encrypted_payload = custom_encode(Fernet(key).encrypt(compiled_code))

    
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
    logo_path = os.path.join(current_dir, "logo.ico")
    ver_path = os.path.join(current_dir, "ver.txt")
    manifest_path = os.path.join(current_dir, "app.manifest")

    hidden_imports = [
        "--hidden-import=OpenOPC", 
        "--hidden-import=pywin32", 
        "--hidden-import=cryptography",
        "--hidden-import=asyncio",
        "--hidden-import=PyQt5",
        "--hidden-import=PyQt5.QtCore",      # <--- EKLENDİ
        "--hidden-import=PyQt5.QtGui",       # <--- EKLENDİ
        "--hidden-import=PyQt5.QtWidgets",   # <--- EKLENDİ
        "--hidden-import=asyncua",
        "--hidden-import=pythoncom",
        "--hidden-import=pywintypes",
        "--hidden-import=urllib.request",
        "--hidden-import=urllib.error"
    ]
    
    pyinstaller_cmd = [
        "pyinstaller", "--onefile", "--noconsole",
        "--noupx", "--name=" + output_name,
        f"--icon={logo_path}",
        f"--version-file={ver_path}",
        f"--manifest={manifest_path}",
        f"--add-data={logo_path};.",
    ] + hidden_imports + [temp_loader_path]
    
    subprocess.run(pyinstaller_cmd, shell=True, cwd=current_dir)
    if os.path.exists(temp_loader_path): os.remove(temp_loader_path)
    print(f"\\n[+] BITTI! sifreleme/dist/{output_name}.exe hazir. Istedigin kisiye yollayabilirsin.")
if __name__ == "__main__":
    build_simple_fortress()