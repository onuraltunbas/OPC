[Setup]
AppName=Nautilus OPC Suite Pro UNLOCKED
AppVersion=5.0
AppPublisher=Nautilus Technology
AppCopyright=Copyright (C) 2026 Nautilus Technology
DefaultDirName={autopf}\Nautilus Technology\OPC Gateway
DefaultGroupName=Nautilus Technology
SetupIconFile=logo.ico
UninstallDisplayIcon={app}\OPC_Gateway_Unlocked.exe
Compression=lzma2/ultra64
SolidCompression=yes
LZMAUseSeparateProcess=yes
OutputDir=Output
OutputBaseFilename=nautilus_setup_unlocked
RestartIfNeededByRun=yes

; Görseller ve Lisans
LicenseFile=lisans.txt
WizardImageFile=sol_gorsel.bmp
WizardSmallImageFile=qr_kod.bmp

[Tasks]
Name: "desktopicon"; Description: "Masaüstüne kısayol oluştur"; GroupDescription: "Ek Görevler:"

[Components]
; Kullanıcının isteğe bağlı seçeceği programlar
Name: "gateway"; Description: "Nautilus OPC Gateway Pro (Köprü Sunucu)"; Types: full custom; Flags: checkablealone
Name: "viewer"; Description: "Nautilus OPC Viewer Pro (İzleme İstemcisi)"; Types: full custom; Flags: checkablealone

[Files]
; --- ANA UYGULAMA DOSYALARI (ŞİFRELİ) ---
Source: "dist\OPC_Gateway_Unlocked.exe"; DestDir: "{app}"; Flags: ignoreversion; Components: gateway
Source: "dist\OPC_Viewer_Unlocked.exe"; DestDir: "{app}"; Flags: ignoreversion; Components: viewer
Source: "dist\Altyapi_Kurulumu.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "dist\Altyapi_Kaldir.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "logo.ico"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\Gereksinimler\offline_kurulumlar\*"; DestDir: "{app}\Gereksinimler\offline_kurulumlar"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
; Yalnızca Gateway ve Viewer masaüstü ve başlat menüsü kısayolları
Name: "{group}\Nautilus OPC Gateway"; Filename: "{app}\OPC_Gateway_Unlocked.exe"; IconFilename: "{app}\logo.ico"; Components: gateway
Name: "{autodesktop}\Nautilus OPC Gateway"; Filename: "{app}\OPC_Gateway_Unlocked.exe"; Tasks: desktopicon; IconFilename: "{app}\logo.ico"; Components: gateway
Name: "{group}\Nautilus OPC Viewer"; Filename: "{app}\OPC_Viewer_Unlocked.exe"; IconFilename: "{app}\logo.ico"; Components: viewer
Name: "{autodesktop}\Nautilus OPC Viewer"; Filename: "{app}\OPC_Viewer_Unlocked.exe"; Tasks: desktopicon; IconFilename: "{app}\logo.ico"; Components: viewer
Name: "{group}\Kurulumu Kaldır"; Filename: "{uninstallexe}"

[Run]
; Kurulum Sonu Başlatma Seçenekleri
Filename: "{app}\Altyapi_Kurulumu.exe"; Description: "Endüstriyel Altyapıyı Şimdi Kur"; Flags: nowait postinstall skipifsilent unchecked
Filename: "{app}\OPC_Gateway_Unlocked.exe"; Description: "Nautilus OPC Gateway'i Başlat"; Components: gateway; Flags: nowait postinstall skipifsilent
Filename: "{app}\OPC_Viewer_Unlocked.exe"; Description: "Nautilus OPC Viewer'ı Başlat"; Components: viewer; Flags: nowait postinstall skipifsilent