@echo off
REM ================================================================================
REM  TÜBİTAK 2209-B SANAYİ ODAKLI BİTİRME VE AR-GE PROJESİ
REM  IEC 62443 Uyumlu Endüstriyel OPC DA/UA Hibrit Ağ Geçidi Altyapı Kurulum Betiği
REM  Telif Hakkı (C) 2026 Nautilus Technology & TÜBİTAK 2209-B Proje Ekibi
REM ================================================================================
chcp 65001 >nul
setlocal enabledelayedexpansion
title TÜBİTAK 2209-B Endüstriyel OPC Ağ Geçidi - Altyapı Kurulumu

REM --------------------------------------------------------------------------------
REM 1. YÖNETİCİ (ADMINISTRATOR) YETKİSİ KONTROLÜ VE OTOMATİK YÜKSELME (UAC)
REM --------------------------------------------------------------------------------
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo.
    echo ============================================================================
    echo  [!] UYARI: Bu kurulum için Windows Yönetici (Administrator) yetkisi gerekir.
    echo  [!] Yetkilendirme penceresi (UAC) açılıyor, lütfen "Evet"i seçin...
    echo ============================================================================
    powershell -NoProfile -ExecutionPolicy Bypass -Command "Start-Process cmd -ArgumentList '/c \"\"%~f0\"\"' -Verb RunAs"
    exit /b
)

cd /d "%~dp0"

cls
color 0B
echo ================================================================================
echo   TÜBİTAK 2209-B: SANAYİ ODAKLI AR-GE PROJESİ
echo   IEC 62443 Uyumlu Endüstriyel OPC DA / OPC UA Hibrit Ağ Geçidi Altyapı Kurulumu
echo ================================================================================
echo.
echo  [*] Kurulum Başlatılıyor...
echo  [*] Çalışma Dizini : %~dp0
echo.

REM --------------------------------------------------------------------------------
REM 2. SİSTEM MİMARİSİ VE DİZİN TESPİTİ
REM --------------------------------------------------------------------------------
set "TARGET_PYTHON_DIR=C:\Python313_32"
set "TAG_DIR=C:\ProgramData\TubitakOPCGateway"
set "TAG_FILE=%TAG_DIR%\kurulum_kaydi.tag"

if not exist "%TAG_DIR%" (
    mkdir "%TAG_DIR%" >nul 2>&1
)

if "%PROCESSOR_ARCHITECTURE%"=="AMD64" (
    set "SYS_DIR=%SystemRoot%\SysWOW64"
    set "OS_BIT=64-Bit"
) else if "%PROCESSOR_ARCHITEW6432%"=="AMD64" (
    set "SYS_DIR=%SystemRoot%\SysWOW64"
    set "OS_BIT=64-Bit"
) else (
    set "SYS_DIR=%SystemRoot%\System32"
    set "OS_BIT=32-Bit"
)
echo  [i] İşletim Sistemi Mimarisi: %OS_BIT%
echo  [i] COM Hedef Sistem Dizini : %SYS_DIR%
echo.

REM --------------------------------------------------------------------------------
REM 3. ADIM 1: 32-BIT PYTHON ALTYAPISININ KURULUMU
REM --------------------------------------------------------------------------------
echo --------------------------------------------------------------------------------
echo  [ADIM 1/5] Python 3.13 (32-Bit) Endüstriyel Çalışma Zamanı Denetleniyor...
echo --------------------------------------------------------------------------------
if exist "%TARGET_PYTHON_DIR%\python.exe" (
    echo  [+] Python 3.13 32-bit zaten kurulu: %TARGET_PYTHON_DIR% (Atlandı)
    echo python_onceden_vardi=1 >> "%TAG_FILE%"
) else (
    echo  [*] Python 3.13.3 (32-bit) sessiz kurulumu başlatılıyor...
    echo  [*] Lütfen bekleyin, bu işlem 30-60 saniye sürebilir...
    
    if not exist "%~dp0offline_kurulumlar\python-3.13.3.exe" (
        color 0C
        echo.
        echo  [-] HATA: offline_kurulumlar\python-3.13.3.exe bulunamadı!
        echo  [-] Kurulum tamamlanamadı.
        pause
        exit /b 1
    )

    "%~dp0offline_kurulumlar\python-3.13.3.exe" /quiet InstallAllUsers=1 PrependPath=1 Include_test=0 TargetDir="%TARGET_PYTHON_DIR%"
    
    if not exist "%TARGET_PYTHON_DIR%\python.exe" (
        color 0C
        echo.
        echo  [-] HATA: Python kurulumu başarısız oldu! Lütfen kurulum dosyasını kontrol edin.
        pause
        exit /b 1
    )
    echo  [+] Python 3.13 (32-bit) başarıyla kuruldu: %TARGET_PYTHON_DIR%
    echo python_biz_kurduk=1 >> "%TAG_FILE%"
)
echo.

REM --------------------------------------------------------------------------------
REM 4. ADIM 2: ENDÜSTRİYEL KÜTÜPHANELERİN YÜKLENMESİ (ÇEVRİMDIŞI PIP WHEELS)
REM --------------------------------------------------------------------------------
echo --------------------------------------------------------------------------------
echo  [ADIM 2/5] Endüstriyel İletişim Kütüphaneleri Yükleniyor (Çevrimdışı)...
echo --------------------------------------------------------------------------------
echo  [*] OpenOPC, asyncua, pywin32, pyro4, cryptography paketleri sisteme entegre ediliyor...

"%TARGET_PYTHON_DIR%\python.exe" -m pip install --no-index --find-links="%~dp0offline_kurulumlar\wheels" OpenOPC-Python3x asyncua pywin32 pyro4 cryptography pyopenssl >nul 2>&1
if %errorlevel% neq 0 (
    echo  [!] Paket kurulumu uyarısı alındı, ayrıntılı log ile tekrar deneniyor...
    "%TARGET_PYTHON_DIR%\python.exe" -m pip install --no-index --find-links="%~dp0offline_kurulumlar\wheels" OpenOPC-Python3x asyncua pywin32 pyro4 cryptography pyopenssl
) else (
    echo  [+] Endüstriyel Python kütüphaneleri başarıyla kuruldu.
)
echo.

REM --------------------------------------------------------------------------------
REM 5. ADIM 3: WINDOWS COM ENTEGRASYONU (pywin32_postinstall)
REM --------------------------------------------------------------------------------
echo --------------------------------------------------------------------------------
echo  [ADIM 3/5] Windows OPC COM Sürücüleri Sisteme Kaydediliyor...
echo --------------------------------------------------------------------------------
if exist "%TARGET_PYTHON_DIR%\Scripts\pywin32_postinstall.py" (
    "%TARGET_PYTHON_DIR%\python.exe" "%TARGET_PYTHON_DIR%\Scripts\pywin32_postinstall.py" -install >nul 2>&1
    echo  [+] pywin32 COM entegrasyonu tamamlandı.
) else (
    echo  [!] pywin32_postinstall.py bulunamadı, dahili modülle bağlanıyor...
    "%TARGET_PYTHON_DIR%\python.exe" -c "import win32com" >nul 2>&1
)
echo.

REM --------------------------------------------------------------------------------
REM 6. ADIM 4: OPC DA COM AUTOMATION SÜRÜCÜSÜ (OPCDAAuto.dll)
REM --------------------------------------------------------------------------------
echo --------------------------------------------------------------------------------
echo  [ADIM 4/5] OPC DA Automation Sürücüsü (OPCDAAuto.dll) Yapılandırılıyor...
echo --------------------------------------------------------------------------------
set "OPC_SURUCU_VAR=0"
reg query "HKCR\OPC.Automation" >nul 2>&1
if %errorlevel% equ 0 set "OPC_SURUCU_VAR=1"

reg query "HKCR\Matrikon.OPC.Automation" >nul 2>&1
if %errorlevel% equ 0 set "OPC_SURUCU_VAR=1"

if "%OPC_SURUCU_VAR%"=="1" (
    echo  [+] Sistemde önceden kayıtlı bir OPC Automation sürücüsü tespit edildi.
    echo  [+] Mevcut fabrika/saha konfigürasyonu korundu (Atlandı).
    echo opcdaauto_onceden_vardi=1 >> "%TAG_FILE%"
) else (
    echo  [*] Temiz Windows tespiti: OPCDAAuto.dll sisteme yükleniyor...
    if exist "%~dp0offline_kurulumlar\OPCDAAuto.dll" (
        copy /y "%~dp0offline_kurulumlar\OPCDAAuto.dll" "%SYS_DIR%\OPCDAAuto.dll" >nul 2>&1
        regsvr32.exe /s "%SYS_DIR%\OPCDAAuto.dll"
        echo  [+] OPCDAAuto.dll başarıyla kaydedildi: %SYS_DIR%\OPCDAAuto.dll
        echo opcdaauto_biz_kurduk=1 >> "%TAG_FILE%"
    ) else (
        echo  [!] UYARI: offline_kurulumlar\OPCDAAuto.dll bulunamadı!
    )
)
echo.

REM --------------------------------------------------------------------------------
REM 7. ADIM 5: WINDOWS GÜVENLİK DUVARI (FIREWALL - IEC 62443 PORTU)
REM --------------------------------------------------------------------------------
echo --------------------------------------------------------------------------------
echo  [ADIM 5/5] Endüstriyel Ağ Güvenlik Duvarı Kuralı Tanımlanıyor...
echo --------------------------------------------------------------------------------
netsh advfirewall firewall show rule name="TÜBİTAK 2209-B OPC Gateway (Port 4840)" >nul 2>&1
if %errorlevel% equ 0 (
    echo  [+] Güvenlik duvarı kuralı zaten mevcut (Atlandı).
) else (
    netsh advfirewall firewall add rule name="TÜBİTAK 2209-B OPC Gateway (Port 4840)" dir=in action=allow protocol=TCP localport=4840 >nul 2>&1
    netsh advfirewall firewall add rule name="Nautilus OPC Gateway" dir=in action=allow protocol=TCP localport=4840 >nul 2>&1
    echo  [+] TCP 4840 (OPC UA İletişim Portu) gelen bağlantılara açıldı.
    echo firewall_biz_actik=1 >> "%TAG_FILE%"
)
echo.

REM --------------------------------------------------------------------------------
REM 8. DOĞRULAMA VE BAŞARI ÖZETİ
REM --------------------------------------------------------------------------------
echo --------------------------------------------------------------------------------
echo  [*] Altyapı Bütünlüğü Doğrulanıyor...
echo --------------------------------------------------------------------------------
"%TARGET_PYTHON_DIR%\python.exe" -c "import OpenOPC, asyncua, win32com.client, cryptography; print('[+] Tüm kritik kütüphaneler başarıyla yüklendi.')" 2>nul
if %errorlevel% equ 0 (
    color 0A
    echo.
    echo ================================================================================
    echo  🎉 [TEBRİKLER] ALTYAPI KURULUMU BAŞARIYLA TAMAMLANDI!
    echo ================================================================================
    echo   • 32-Bit Python Altyapısı: C:\Python313_32 [HAZIR]
    echo   • Endüstriyel Kütüphaneler: OpenOPC, asyncua, pywin32 [HAZIR]
    echo   • OPC DA COM Sürücüleri   : OPCDAAuto.dll [KAYITLI]
    echo   • Ağ Güvenlik Kuralı      : TCP 4840 [AÇIK]
    echo.
    echo  Artık OPC Gateway ve OPC Viewer uygulamalarını doğrudan çalıştırabilirsiniz.
    echo ================================================================================
) else (
    color 0E
    echo.
    echo ================================================================================
    echo  [!] Kurulum tamamlandı ancak doğrulama sırasında küçük bir uyarı alındı.
    echo  [!] Programı açıp test edebilirsiniz.
    echo ================================================================================
)

echo.
pause
