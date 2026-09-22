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
    OutputBaseFilename=Nautilus_Gateway_v5_Unlocked_Setup
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
    ; --- 1. ZORUNLU KURULUM ALTYAPISI (Geçici klasöre çıkarılır, kurulum bitince otomatik silinir) ---
    Source: "offline_kurulumlar\python-3.13.3.exe"; DestDir: "{tmp}"; Flags: ignoreversion deleteafterinstall
    Source: "offline_kurulumlar\wheels\*"; DestDir: "{tmp}\wheels"; Flags: ignoreversion recursesubdirs createallsubdirs deleteafterinstall

    ; --- 2. ANA UYGULAMA DOSYALARI ---
    Source: "dist\OPC_Gateway_Unlocked.exe"; DestDir: "{app}"; Flags: ignoreversion; Components: gateway
    Source: "dist\OPC_Viewer_Unlocked.exe"; DestDir: "{app}"; Flags: ignoreversion; Components: viewer
    Source: "logo.ico"; DestDir: "{app}"; Flags: ignoreversion

    [Icons]
    Name: "{group}\Nautilus OPC Gateway"; Filename: "{app}\OPC_Gateway_Unlocked.exe"; IconFilename: "{app}\logo.ico"; Components: gateway
    Name: "{autodesktop}\Nautilus OPC Gateway"; Filename: "{app}\OPC_Gateway_Unlocked.exe"; Tasks: desktopicon; IconFilename: "{app}\logo.ico"; Components: gateway
    Name: "{group}\Nautilus OPC Viewer"; Filename: "{app}\OPC_Viewer_Unlocked.exe"; IconFilename: "{app}\logo.ico"; Components: viewer
    Name: "{autodesktop}\Nautilus OPC Viewer"; Filename: "{app}\OPC_Viewer_Unlocked.exe"; Tasks: desktopicon; IconFilename: "{app}\logo.ico"; Components: viewer
    Name: "{group}\Kurulumu Kaldır"; Filename: "{uninstallexe}"

    [Run]
    ; --- ADIM A: Python 3.13 (32-bit) Sessiz ve Çevrimdışı Kurulumu ---
    ; Eğer bilgisayarda C:\Python313_32\python.exe yoksa kurar, varsa atlar.
    Filename: "{tmp}\python-3.13.3.exe"; Parameters: "/quiet InstallAllUsers=1 PrependPath=1 Include_test=0 TargetDir=""C:\Python313_32"""; StatusMsg: "32-Bit Python Altyapısı Kuruluyor (Lütfen bekleyin)..."; Flags: waituntilterminated; Check: PythonGerekliMi

    ; --- ADIM B: Endüstriyel Kütüphanelerin Yüklenmesi (Çevrimdışı PIP) ---
    Filename: "C:\Python313_32\python.exe"; Parameters: "-m pip install --no-index --find-links=""{tmp}\wheels"" OpenOPC-Python3x asyncua pywin32 pyro4"; StatusMsg: "Endüstriyel iletişim kütüphaneleri sisteme entegre ediliyor..."; Flags: waituntilterminated

    ; --- ADIM C: Windows OPC COM DLL Kaydı ---
    Filename: "C:\Python313_32\python.exe"; Parameters: "C:\Python313_32\Scripts\pywin32_postinstall.py -install"; StatusMsg: "Windows OPC COM sürücüleri kaydediliyor..."; Flags: waituntilterminated

    ; --- ADIM D: Kurulum Sonu Başlatma Seçenekleri ---
    Filename: "{app}\OPC_Gateway_Unlocked.exe"; Description: "Nautilus OPC Gateway'i Başlat"; Components: gateway; Flags: nowait postinstall skipifsilent
    Filename: "{app}\OPC_Viewer_Unlocked.exe"; Description: "Nautilus OPC Viewer'ı Başlat"; Components: viewer; Flags: nowait postinstall skipifsilent

    [Code]
    // Bilgisayarda Python 32-bit zaten var mı kontrolü
    function PythonGerekliMi(): Boolean;
    begin
      Result := not FileExists('C:\Python313_32\python.exe');
    end;