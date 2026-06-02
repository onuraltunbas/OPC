[Setup]
; Temel Uygulama Bilgileri
AppName=Nautilus OPC Gateway
AppVersion=5.0
AppPublisher=Nautilus Technology
AppCopyright=Copyright (C) 2026 Nautilus Technology
DefaultDirName={autopf}\Nautilus Technology\OPC Gateway
DefaultGroupName=Nautilus Technology
SetupIconFile=logo.ico
UninstallDisplayIcon={app}\Nautilus_Gateway.exe
Compression=lzma2/ultra64
SolidCompression=yes
OutputDir=Output
OutputBaseFilename=Nautilus_Gateway_v5_Setup
RestartIfNeededByRun=yes

; Görsel ve Lisans Ayarları
LicenseFile=lisans.txt
WizardImageFile=sol_gorsel.bmp
WizardSmallImageFile=qr_kod.bmp

[Tasks]
; Masaüstü kısayolu seçeneği
Name: "desktopicon"; Description: "Masaüstüne kısayol oluştur"; GroupDescription: "Ek Görevler:"

[Components]
; Kullanıcının seçeceği modüller
Name: "main"; Description: "Nautilus OPC Gateway"; Types: full compact custom; Flags: fixed
Name: "python"; Description: "Python 3.13 (32-Bit)"; Types: full
Name: "libs"; Description: "Gerekli Bileşenler"; Types: full

[Files]
; Ana dosyalar (Hedef klasöre gider)
Source: "dist\OPC_Gateway_Pro.exe"; DestDir: "{app}"; Flags: ignoreversion; Components: main
Source: "logo.ico"; DestDir: "{app}"; Flags: ignoreversion; Components: main

; Python Installer (Geçici klasöre gider, kurulum bitince silinir)
Source: "offline_kurulumlar\python-3.14.5.exe"; DestDir: "{tmp}"; Flags: deleteafterinstall; Components: python

; Pip Kütüphaneleri (Geçici klasöre gider, kurulum bitince silinir)
Source: "offline_kurulumlar\wheels\*"; DestDir: "{tmp}\wheels"; Flags: ignoreversion recursesubdirs createallsubdirs deleteafterinstall; Components: libs

[Icons]
; Başlat menüsü ve Masaüstü Kısayolları
Name: "{group}\Nautilus OPC Gateway"; Filename: "{app}\Nautilus_Gateway.exe"; IconFilename: "{app}\logo.ico"
Name: "{group}\Kurulumu Kaldır"; Filename: "{uninstallexe}"
Name: "{autodesktop}\Nautilus OPC Gateway"; Filename: "{app}\Nautilus_Gateway.exe"; Tasks: desktopicon; IconFilename: "{app}\logo.ico"

[Run]
; 1. Python Sessiz Kurulumu
Filename: "{tmp}\python-3.13.3.exe"; Parameters: "/quiet InstallAllUsers=1 PrependPath=1 Include_test=0 TargetDir=""C:\Python313_32"""; Components: python; StatusMsg: "Python 3.13 altyapısı kuruluyor, lütfen bekleyin..."; Flags: waituntilterminated

; 2. Çevrimdışı Pip Kütüphane Kurulumu
Filename: "C:\Python313_32\python.exe"; Parameters: "-m pip install --no-index --find-links=""{tmp}\wheels"" OpenOPC-Python3x asyncua pywin32 pyro4"; Components: libs; StatusMsg: "Endüstriyel iletişim kütüphaneleri yükleniyor..."; Flags: waituntilterminated

; 3. PyWin32 Post Install (Windows OPC DLL Kaydı)
Filename: "C:\Python313_32\python.exe"; Parameters: "C:\Python313_32\Scripts\pywin32_postinstall.py -install"; Components: libs; StatusMsg: "Windows OPC bileşenleri kaydediliyor..."; Flags: waituntilterminated

; 4. Kurulum bitince programı başlatma seçeneği
Filename: "{app}\Nautilus_Gateway.exe"; Description: "Nautilus OPC Gateway'i Başlat"; Flags: nowait postinstall skipifsilent