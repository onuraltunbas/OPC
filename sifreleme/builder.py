import os
import sys
import base64
import subprocess
import marshal
from cryptography.fernet import Fernet

# 1. AYARLAR VE ÖZEL ALFABE
CUSTOM_ALPHABET = "АБВГДЕЖЗИЙКЛМНОПРСТУФХЦЧШЩЪЫЬЭЮЯ汉字龙书Ω∑∞∫≈≠≤≥★♦♣♠♥♩♪♫♬♔♕♖♗♘♙"
BASE64_ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/"

def custom_encode(data: bytes) -> str:
    b64 = base64.b64encode(data).decode('ascii').rstrip('=')
    return b64.translate(str.maketrans(BASE64_ALPHABET, CUSTOM_ALPHABET))

def build_simple_fortress():
    target_py = "gateway_v5.0.py"
    output_name = "OPC_Gateway_Pro"
    
    if not os.path.exists(target_py):
        print(f"[-] Hata: {target_py} bulunamadı!")
        return

    print("[*] Kod okunuyor ve şifreleniyor...")
    with open(target_py, 'rb') as f:
        original_code = f.read()

    # 2. ŞİFRELEME (AES-128 Fernet)
    # Her derlemede tamamen rastgele, tek kullanımlık bir anahtar üretilir
    key = Fernet.generate_key()
    compiled_code = marshal.dumps(compile(original_code, 'gateway', 'exec'))
    encrypted_payload = custom_encode(Fernet(key).encrypt(compiled_code))

    # 3. KENDİ KENDİNİ ÇÖZEN LOADER (Sadece Anti-Debug ve Çözücü var, lisans yok)
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

    with open("temp_loader.py", "w", encoding="utf-8") as f:
        f.write(loader_code)

    # 4. PYINSTALLER İLE EXE YAPMA
    print("[*] EXE derleniyor...")
    pyinstaller_cmd = [
        "pyinstaller", "--onefile", "--noconsole",
        "--noupx", "--name=" + output_name,
        "--icon=logo.ico",
        "--hidden-import=OpenOPC", "--hidden-import=pywin32", "--hidden-import=cryptography",
        "temp_loader.py"
    ]
    
    subprocess.run(pyinstaller_cmd, shell=True)
    
    # Temizlik
    if os.path.exists("temp_loader.py"): os.remove("temp_loader.py")
    print(f"\\n✅ BİTTİ! dist/{output_name}.exe hazır. İstediğin kişiye yollayabilirsin.")

if __name__ == "__main__":
    build_simple_fortress()