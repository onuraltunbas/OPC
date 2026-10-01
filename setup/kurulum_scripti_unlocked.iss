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
PrivilegesRequired=admin

; Görseller ve Lisans
LicenseFile=lisans.txt
WizardImageFile=sol_gorsel.bmp
WizardSmallImageFile=qr_kod.bmp

[Tasks]
Name: "desktopicon"; Description: "Masaüstüne kısayol oluştur"; GroupDescription: "Masaüstü Simgeleri:"

; --- GÜVENLİK DUVARI (FIREWALL) PORT SEÇENEKLERİ ---
Name: "fw_base"; Description: "Temel Endüstriyel Portları Aç (OPC UA: 4840, Siemens S7: 102/1102, Modbus TCP: 502/5020/5021)"; GroupDescription: "Windows Güvenlik Duvarı İzinleri (Standart):"; Flags: checkedonce
Name: "fw_sim"; Description: "Nautilus PLC Simülatör Test Portu (TCP 4845)"; GroupDescription: "Windows Güvenlik Duvarı İzinleri (İsteğe Bağlı Donanım/Marka Portları):"; Flags: unchecked
Name: "fw_rockwell"; Description: "Rockwell / Allen-Bradley EtherNet/IP Portu (TCP 44818)"; GroupDescription: "Windows Güvenlik Duvarı İzinleri (İsteğe Bağlı Donanım/Marka Portları):"; Flags: unchecked
Name: "fw_melsec"; Description: "Mitsubishi Electric MELSEC / SLMP Portu (TCP 48898, 48899, 5002)"; GroupDescription: "Windows Güvenlik Duvarı İzinleri (İsteğe Bağlı Donanım/Marka Portları):"; Flags: unchecked
Name: "fw_omron"; Description: "Omron FINS Endüstriyel Portu (TCP 9600)"; GroupDescription: "Windows Güvenlik Duvarı İzinleri (İsteğe Bağlı Donanım/Marka Portları):"; Flags: unchecked
Name: "fw_mqtt"; Description: "Endüstriyel IoT MQTT Portları (TCP 1883, 8883)"; GroupDescription: "Windows Güvenlik Duvarı İzinleri (İsteğe Bağlı Donanım/Marka Portları):"; Flags: unchecked

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
; Güvenlik Duvarı Kuralları - Standart
Filename: "netsh"; Parameters: "advfirewall firewall add rule name=""Nautilus OPC UA Gateway (Port 4840)"" dir=in action=allow protocol=TCP localport=4840"; Flags: runhidden; Tasks: fw_base
Filename: "netsh"; Parameters: "advfirewall firewall add rule name=""Nautilus Siemens S7 PLC (Port 102/1102)"" dir=in action=allow protocol=TCP localport=102,1102"; Flags: runhidden; Tasks: fw_base
Filename: "netsh"; Parameters: "advfirewall firewall add rule name=""Nautilus Modbus TCP PLC (Port 502/5020/5021)"" dir=in action=allow protocol=TCP localport=502,5020,5021"; Flags: runhidden; Tasks: fw_base

; Güvenlik Duvarı Kuralları - İsteğe Bağlı
Filename: "netsh"; Parameters: "advfirewall firewall add rule name=""Nautilus Simulatör Test (Port 4845)"" dir=in action=allow protocol=TCP localport=4845"; Flags: runhidden; Tasks: fw_sim
Filename: "netsh"; Parameters: "advfirewall firewall add rule name=""Nautilus Rockwell EtherNet-IP (Port 44818)"" dir=in action=allow protocol=TCP localport=44818"; Flags: runhidden; Tasks: fw_rockwell
Filename: "netsh"; Parameters: "advfirewall firewall add rule name=""Nautilus Mitsubishi MELSEC (Port 48898/48899/5002)"" dir=in action=allow protocol=TCP localport=48898,48899,5002"; Flags: runhidden; Tasks: fw_melsec
Filename: "netsh"; Parameters: "advfirewall firewall add rule name=""Nautilus Omron FINS (Port 9600)"" dir=in action=allow protocol=TCP localport=9600"; Flags: runhidden; Tasks: fw_omron
Filename: "netsh"; Parameters: "advfirewall firewall add rule name=""Nautilus Industrial MQTT (Port 1883/8883)"" dir=in action=allow protocol=TCP localport=1883,8883"; Flags: runhidden; Tasks: fw_mqtt

; Kurulum Sonu Başlatma Seçenekleri
Filename: "{app}\Altyapi_Kurulumu.exe"; Description: "Endüstriyel Altyapıyı Şimdi Kur"; Flags: nowait postinstall skipifsilent unchecked
Filename: "{app}\OPC_Gateway_Unlocked.exe"; Description: "Nautilus OPC Gateway'i Başlat"; Components: gateway; Flags: nowait postinstall skipifsilent
Filename: "{app}\OPC_Viewer_Unlocked.exe"; Description: "Nautilus OPC Viewer'ı Başlat"; Components: viewer; Flags: nowait postinstall skipifsilent

[UninstallRun]
Filename: "netsh"; Parameters: "advfirewall firewall delete rule name=""Nautilus OPC UA Gateway (Port 4840)"""; Flags: runhidden
Filename: "netsh"; Parameters: "advfirewall firewall delete rule name=""Nautilus Siemens S7 PLC (Port 102/1102)"""; Flags: runhidden
Filename: "netsh"; Parameters: "advfirewall firewall delete rule name=""Nautilus Modbus TCP PLC (Port 502/5020/5021)"""; Flags: runhidden
Filename: "netsh"; Parameters: "advfirewall firewall delete rule name=""Nautilus Simulatör Test (Port 4845)"""; Flags: runhidden
Filename: "netsh"; Parameters: "advfirewall firewall delete rule name=""Nautilus Simulatör OPC UA (Port 4845)"""; Flags: runhidden
Filename: "netsh"; Parameters: "advfirewall firewall delete rule name=""Nautilus Rockwell EtherNet-IP (Port 44818)"""; Flags: runhidden
Filename: "netsh"; Parameters: "advfirewall firewall delete rule name=""Nautilus Mitsubishi MELSEC (Port 48898/48899/5002)"""; Flags: runhidden
Filename: "netsh"; Parameters: "advfirewall firewall delete rule name=""Nautilus Omron FINS (Port 9600)"""; Flags: runhidden
Filename: "netsh"; Parameters: "advfirewall firewall delete rule name=""Nautilus Industrial MQTT (Port 1883/8883)"""; Flags: runhidden