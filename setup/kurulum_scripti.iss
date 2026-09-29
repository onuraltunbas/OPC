[Setup]
AppName=Nautilus OPC Suite Pro
AppVersion=5.0
AppPublisher=Nautilus Technology
AppCopyright=Copyright (C) 2026 Nautilus Technology
DefaultDirName={autopf}\Nautilus Technology\OPC Gateway
DefaultGroupName=Nautilus Technology
SetupIconFile=logo.ico
UninstallDisplayIcon={app}\OPC_Gateway_Pro.exe
Compression=lzma2/ultra64
SolidCompression=yes
LZMAUseSeparateProcess=yes
OutputDir=Output
OutputBaseFilename=Nautilus_Gateway_v5_Setup
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
; --- ANA UYGULAMA DOSYALARI ---
Source: "dist\OPC_Gateway_Pro.exe"; DestDir: "{app}"; Flags: ignoreversion; Components: gateway
Source: "dist\OPC_Viewer_Pro.exe"; DestDir: "{app}"; Flags: ignoreversion; Components: viewer
Source: "logo.ico"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\Nautilus OPC Gateway"; Filename: "{app}\OPC_Gateway_Pro.exe"; IconFilename: "{app}\logo.ico"; Components: gateway
Name: "{autodesktop}\Nautilus OPC Gateway"; Filename: "{app}\OPC_Gateway_Pro.exe"; Tasks: desktopicon; IconFilename: "{app}\logo.ico"; Components: gateway
Name: "{group}\Nautilus OPC Viewer"; Filename: "{app}\OPC_Viewer_Pro.exe"; IconFilename: "{app}\logo.ico"; Components: viewer
Name: "{autodesktop}\Nautilus OPC Viewer"; Filename: "{app}\OPC_Viewer_Pro.exe"; Tasks: desktopicon; IconFilename: "{app}\logo.ico"; Components: viewer
Name: "{group}\Kurulumu Kaldır"; Filename: "{uninstallexe}"

[Run]
; Kurulum Sonu Başlatma Seçenekleri
Filename: "{app}\OPC_Gateway_Pro.exe"; Description: "Nautilus OPC Gateway'i Başlat"; Components: gateway; Flags: nowait postinstall skipifsilent
Filename: "{app}\OPC_Viewer_Pro.exe"; Description: "Nautilus OPC Viewer'ı Başlat"; Components: viewer; Flags: nowait postinstall skipifsilent