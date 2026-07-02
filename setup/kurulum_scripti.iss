[Setup]
; Temel Uygulama Bilgileri
AppName=Nautilus OPC Suite
AppVersion=5.0
AppPublisher=Nautilus Technology
AppCopyright=Copyright (C) 2026 Nautilus Technology
DefaultDirName={autopf}\Nautilus Technology\OPC Gateway
DefaultGroupName=Nautilus Technology
SetupIconFile=logo.ico
UninstallDisplayIcon={app}\OPC_Gateway_Pro.exe
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
Name: "gateway"; Description: "Nautilus OPC Gateway Modülü"; Types: full custom
Name: "viewer"; Description: "Nautilus OPC Viewer Modülü"; Types: full custom
Name: "libs"; Description: "Gerekli Endüstriyel Kütüphaneler"; Types: full compact custom; Flags: fixed

[Files]
; Ana uygulama dosyaları ({app} klasörüne gider)
Source: "dist\OPC_Gateway_Pro.exe"; DestDir: "{app}"; Flags: ignoreversion; Components: gateway
Source: "dist\OPC_Viewer_Pro.exe"; DestDir: "{app}"; Flags: ignoreversion; Components: viewer
Source: "logo.ico"; DestDir: "{app}"; Flags: ignoreversion; Components: gateway viewer

; Pip Kütüphaneleri (Geçici klasöre gider, kurulum bitince silinir)
Source: "offline_kurulumlar\wheels\*"; DestDir: "{tmp}\wheels"; Flags: ignoreversion recursesubdirs createallsubdirs deleteafterinstall; Components: libs

[Icons]
; Gateway - Başlat Menüsü ve Masaüstü Kısayolları
Name: "{group}\Nautilus OPC Gateway"; Filename: "{app}\OPC_Gateway_Pro.exe"; IconFilename: "{app}\logo.ico"; Components: gateway
Name: "{autodesktop}\Nautilus OPC Gateway"; Filename: "{app}\OPC_Gateway_Pro.exe"; Tasks: desktopicon; IconFilename: "{app}\logo.ico"; Components: gateway

; Viewer - Başlat Menüsü ve Masaüstü Kısayolları
Name: "{group}\Nautilus OPC Viewer"; Filename: "{app}\OPC_Viewer_Pro.exe"; IconFilename: "{app}\logo.ico"; Components: viewer
Name: "{autodesktop}\Nautilus OPC Viewer"; Filename: "{app}\OPC_Viewer_Pro.exe"; Tasks: desktopicon; IconFilename: "{app}\logo.ico"; Components: viewer

; Kaldırma kısayolu
Name: "{group}\Kurulumu Kaldır"; Filename: "{uninstallexe}"

[Run]
; 1. Çevrimdışı Pip Kütüphane Kurulumu
Filename: "C:\Python313_32\python.exe"; Parameters: "-m pip install --no-index --find-links=""{tmp}\wheels"" OpenOPC-Python3x asyncua pywin32 pyro4"; Componesnts: libs; StatusMsg: "Endüstriyel iletişim kütüphaneleri yükleniyor..."; Flags: waituntilterminated

; 2. PyWin32 Post Install (Windows OPC DLL Kaydı)
Filename: "C:\Python313_32\python.exe"; Parameters: "C:\Python313_32\Scripts\pywin32_postinstall.py -install"; Components: libs; StatusMsg: "Windows OPC bileşenleri kaydediliyor..."; Flags: waituntilterminated

; 3. Kurulum bitince Gateway'i başlatma seçeneği
Filename: "{app}\OPC_Gateway_Pro.exe"; Description: "Nautilus OPC Gateway'i Başlat"; Components: gateway; Flags: nowait postinstall skipifsilent

; 4. Kurulum bitince Viewer'ı başlatma seçeneği
Filename: "{app}\OPC_Viewer_Pro.exe"; Description: "Nautilus OPC Viewer'ı Başlat"; Components: viewer; Flags: nowait postinstall skipifsilent