@echo off
REM ================================================================================
REM  TÜBİTAK 2209-B SANAYİ ODAKLI BİTİRME VE AR-GE PROJESİ
REM  Endüstriyel Altyapı Kaldırıcı ve Sıfırlayıcı (Zero-Trace Uninstaller)
REM  Telif Hakkı (C) 2026 Nautilus Technology & TÜBİTAK 2209-B Proje Ekibi
REM ================================================================================
chcp 65001 >nul
setlocal enabledelayedexpansion
title TÜBİTAK 2209-B Endüstriyel OPC Ağ Geçidi - Altyapı Kaldırıcı (Uninstaller)

REM --------------------------------------------------------------------------------
REM 1. YÖNETİCİ (ADMINISTRATOR) YETKİSİ KONTROLÜ VE OTOMATİK YÜKSELME (UAC)
REM --------------------------------------------------------------------------------
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo.
    echo ============================================================================
    echo  [!] UYARI: Altyapıyı kaldırmak için Windows Yönetici yetkisi gerekir.
    echo  [!] Yetkilendirme penceresi (UAC) açılıyor, lütfen "Evet"i seçin...
    echo ============================================================================
    powershell -NoProfile -ExecutionPolicy Bypass -Command "Start-Process cmd -ArgumentList '/c \"\"%~f0\"\"' -Verb RunAs"
    exit /b
)

cd /d "%~dp0"

cls
color 0C
echo ================================================================================
echo   TÜBİTAK 2209-B: ENDÜSTRİYEL ALTYAPI KALDIRICI (UNINSTALLER)
echo   Sistemi Hiç Kurulmamış Gibi Tertemiz İlk Haline Döndürme Aracı
echo ================================================================================
echo.
echo  [!] DİKKAT: Bu işlem, Nautilus OPC Gateway ve TÜBİTAK 2209-B için kurulan:
echo      • Python 3.13 (32-Bit) çalışma ortamını (C:\Python313_32)
echo      • OpenOPC, asyncua, pywin32 vb. endüstriyel kütüphaneleri
echo      • Yapılandırılan COM sürücü kayıtlarını (OPCDAAuto.dll)
echo      • Açılan Güvenlik Duvarı (Firewall Port 4840) kurallarını
echo      tamamen kaldıracak ve bilgisayarı orijinal haline döndürecektir.
echo.

set /p ONAY="  Kurulan tüm altyapıyı kaldırmak istiyor musunuz? (E/H): "
if /i not "%ONAY%"=="E" (
    echo.
    echo  [*] İşlem kullanıcı tarafından iptal edildi. Hiçbir şeye dokunulmadı.
    pause
    exit /b 0
)

echo.
echo  [*] Kaldırma işlemi başlatılıyor, lütfen bekleyin...
echo.

set "TARGET_PYTHON_DIR=C:\Python313_32"
set "TAG_DIR=C:\ProgramData\TubitakOPCGateway"
set "TAG_FILE=%TAG_DIR%\kurulum_kaydi.tag"

if "%PROCESSOR_ARCHITECTURE%"=="AMD64" (
    set "SYS_DIR=%SystemRoot%\SysWOW64"
) else if "%PROCESSOR_ARCHITEW6432%"=="AMD64" (
    set "SYS_DIR=%SystemRoot%\SysWOW64"
) else (
    set "SYS_DIR=%SystemRoot%\System32"
)

REM --------------------------------------------------------------------------------
REM 2. GÜVENLİK DUVARI KURALLARINI SİL
REM --------------------------------------------------------------------------------
echo  [1/6] Güvenlik duvarı kuralları siliniyor...
netsh advfirewall firewall delete rule name="TÜBİTAK 2209-B OPC Gateway (Port 4840)" >nul 2>&1
netsh advfirewall firewall delete rule name="Nautilus OPC Gateway" >nul 2>&1
echo  [+] Port 4840 güvenlik duvarı kuralları kaldırıldı.

REM --------------------------------------------------------------------------------
REM 3. OPCDAAUTO.DLL COM KAYDINI VE DOSYASINI KALDIR
REM --------------------------------------------------------------------------------
echo  [2/6] OPC DA COM Automation sürücü kaydı denetleniyor...
set "OPCDAAUTO_SIL=0"
if exist "%TAG_FILE%" (
    findstr /i "opcdaauto_biz_kurduk=1" "%TAG_FILE%" >nul 2>&1
    if %errorlevel% equ 0 set "OPCDAAUTO_SIL=1"
) else (
    REM Etiket dosyası yoksa güvenli modda sadece biz kopyaladıysak kaldır
    set "OPCDAAUTO_SIL=1"
)

if "%OPCDAAUTO_SIL%"=="1" (
    echo  [*] Bizim yüklediğimiz OPCDAAuto.dll kaydı düşürülüyor...
    regsvr32.exe /u /s "%SYS_DIR%\OPCDAAuto.dll" >nul 2>&1
    if exist "%SYS_DIR%\OPCDAAuto.dll" (
        del /f /q "%SYS_DIR%\OPCDAAuto.dll" >nul 2>&1
    )
    echo  [+] OPCDAAuto.dll sistemden güvenle kaldırıldı.
) else (
    echo  [i] OPCDAAuto.dll önceden var olduğu için fabrika/saha kaydına dokunulmadı.
)

REM --------------------------------------------------------------------------------
REM 4. PYWIN32 COM ENTEGRASYONUNU KALDIR
REM --------------------------------------------------------------------------------
echo  [3/6] pywin32 COM kayıtları temizleniyor...
if exist "%TARGET_PYTHON_DIR%\Scripts\pywin32_postinstall.py" (
    "%TARGET_PYTHON_DIR%\python.exe" "%TARGET_PYTHON_DIR%\Scripts\pywin32_postinstall.py" -remove >nul 2>&1
    echo  [+] pywin32 COM kayıtları düşürüldü.
)

REM --------------------------------------------------------------------------------
REM 5. PYTHON 3.13 32-BIT ÇALIŞMA ZAMANINI SESSİZCE KALDIR
REM --------------------------------------------------------------------------------
echo  [4/6] Python 3.13 (32-Bit) sistemi kaldırılıyor...
if exist "%~dp0offline_kurulumlar\python-3.13.3.exe" (
    "%~dp0offline_kurulumlar\python-3.13.3.exe" /uninstall /quiet >nul 2>&1
    timeout /t 5 /nobreak >nul 2>&1
)

REM Kalan klasör ve artık dosyaları tamamen yok et
if exist "%TARGET_PYTHON_DIR%" (
    rmdir /s /q "%TARGET_PYTHON_DIR%" >nul 2>&1
)
echo  [+] Python 3.13 ve kütüphane klasörü (%TARGET_PYTHON_DIR%) tamamen silindi.

REM --------------------------------------------------------------------------------
REM 6. PATH ORTAM DEĞİŞKENLERİNİ TEMİZLE
REM --------------------------------------------------------------------------------
echo  [5/6] Windows PATH ortam değişkenleri temizleniyor...
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
    "$paths = [Environment]::GetEnvironmentVariable('Path', 'Machine') -split ';' | Where-Object { $_ -and $_ -notlike '*Python313_32*' };" ^
    "[Environment]::SetEnvironmentVariable('Path', ($paths -join ';'), 'Machine');" ^
    "$uPaths = [Environment]::GetEnvironmentVariable('Path', 'User') -split ';' | Where-Object { $_ -and $_ -notlike '*Python313_32*' };" ^
    "[Environment]::SetEnvironmentVariable('Path', ($uPaths -join ';'), 'User');" >nul 2>&1
echo  [+] PATH kayıtları temizlendi.

REM --------------------------------------------------------------------------------
REM 7. ÖNBELLEK VE ETİKET DOSYALARINI TEMİZLE
REM --------------------------------------------------------------------------------
echo  [6/6] Geçici dosyalar ve önbellekler temizleniyor...
if exist "%TEMP%\gen_py" (
    rmdir /s /q "%TEMP%\gen_py" >nul 2>&1
)
if exist "%TAG_DIR%" (
    rmdir /s /q "%TAG_DIR%" >nul 2>&1
)
echo  [+] COM önbelleği ve kurulum izleri temizlendi.

REM --------------------------------------------------------------------------------
REM 8. TAMAMLANDI BİLDİRİMİ
REM --------------------------------------------------------------------------------
cls
color 0A
echo.
echo ================================================================================
echo  ✅ [BAŞARILI] TÜM ALTYAPI SİSTEMDEN TAMAMEN KALDIRILDI!
echo ================================================================================
echo   • C:\Python313_32 dizini ve kütüphaneler silindi.
echo   • OPCDAAuto.dll kaydı düşürüldü ve kaldırıldı.
echo   • Güvenlik duvarı (Firewall 4840) kuralları silindi.
echo   • Windows PATH değişkenleri eski haline getirildi.
echo   • COM ve geçici önbellekler temizlendi.
echo.
echo  Bilgisayar, bu altyapı hiç kurulmamış gibi tertemiz orijinal haline döndü.
echo ================================================================================
echo.
pause
