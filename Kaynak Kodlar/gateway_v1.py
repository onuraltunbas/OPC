# -*- coding: utf-8 -*-
import sys
import os
import subprocess
import threading
import asyncio
import copyreg
import datetime
import urllib.request
import tempfile
from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtCore import QThread, pyqtSignal, QObject
from PyQt5.QtGui import QTextCursor

# =====================================================================
# 1. BÖLÜM: ARAYÜZ TASARIMI (Qt Designer Çıktısı)
# =====================================================================
class Ui_btn_sunucu_tara(object):
    def setupUi(self, btn_sunucu_tara):
        btn_sunucu_tara.setObjectName("btn_sunucu_tara")
        btn_sunucu_tara.resize(800, 600)
        self.centralwidget = QtWidgets.QWidget(btn_sunucu_tara)
        self.centralwidget.setObjectName("centralwidget")
        self.pushButton = QtWidgets.QPushButton(self.centralwidget)
        self.pushButton.setGeometry(QtCore.QRect(250, 200, 91, 21))
        self.pushButton.setObjectName("pushButton")
        self.cb_sunucu = QtWidgets.QComboBox(self.centralwidget)
        self.cb_sunucu.setGeometry(QtCore.QRect(250, 220, 81, 31))
        self.cb_sunucu.setObjectName("cb_sunucu")
        self.label = QtWidgets.QLabel(self.centralwidget)
        self.label.setGeometry(QtCore.QRect(270, 180, 47, 13))
        self.label.setObjectName("label")
        self.label_2 = QtWidgets.QLabel(self.centralwidget)
        self.label_2.setGeometry(QtCore.QRect(440, 170, 61, 21))
        self.label_2.setObjectName("label_2")
        self.btn_etiket_tara = QtWidgets.QPushButton(self.centralwidget)
        self.btn_etiket_tara.setGeometry(QtCore.QRect(430, 190, 81, 21))
        self.btn_etiket_tara.setObjectName("btn_etiket_tara")
        self.list_etiket = QtWidgets.QListWidget(self.centralwidget)
        self.list_etiket.setGeometry(QtCore.QRect(400, 210, 161, 91))
        self.list_etiket.setObjectName("list_etiket")
        self.txt_ip = QtWidgets.QLineEdit(self.centralwidget)
        self.txt_ip.setGeometry(QtCore.QRect(630, 200, 113, 20))
        self.txt_ip.setObjectName("txt_ip")
        self.btn_baslat = QtWidgets.QPushButton(self.centralwidget)
        self.btn_baslat.setGeometry(QtCore.QRect(640, 230, 75, 23))
        self.btn_baslat.setObjectName("btn_baslat")
        self.btn_durdur = QtWidgets.QPushButton(self.centralwidget)
        self.btn_durdur.setGeometry(QtCore.QRect(640, 260, 75, 23))
        self.btn_durdur.setObjectName("btn_durdur")
        self.txt_konsol = QtWidgets.QTextEdit(self.centralwidget)
        self.txt_konsol.setGeometry(QtCore.QRect(30, 340, 740, 201))
        self.txt_konsol.setObjectName("txt_konsol")
        self.label_3 = QtWidgets.QLabel(self.centralwidget)
        self.label_3.setGeometry(QtCore.QRect(650, 180, 71, 16))
        self.label_3.setObjectName("label_3")
        self.label_4 = QtWidgets.QLabel(self.centralwidget)
        self.label_4.setGeometry(QtCore.QRect(40, 320, 51, 16))
        self.label_4.setObjectName("label_4")
        self.label_5 = QtWidgets.QLabel(self.centralwidget)
        self.label_5.setGeometry(QtCore.QRect(10, 20, 47, 13))
        self.label_5.setObjectName("label_5")
        self.btn_kurulum_ac = QtWidgets.QPushButton(self.centralwidget)
        self.btn_kurulum_ac.setGeometry(QtCore.QRect(20, 40, 131, 31))
        self.btn_kurulum_ac.setObjectName("btn_kurulum_ac")
        btn_sunucu_tara.setCentralWidget(self.centralwidget)
        self.menubar = QtWidgets.QMenuBar(btn_sunucu_tara)
        self.menubar.setGeometry(QtCore.QRect(0, 0, 800, 21))
        self.menubar.setObjectName("menubar")
        self.menuOPC_DA_OPC_UA_GATEWAY = QtWidgets.QMenu(self.menubar)
        self.menuOPC_DA_OPC_UA_GATEWAY.setObjectName("menuOPC_DA_OPC_UA_GATEWAY")
        btn_sunucu_tara.setMenuBar(self.menubar)
        self.statusbar = QtWidgets.QStatusBar(btn_sunucu_tara)
        self.statusbar.setObjectName("statusbar")
        btn_sunucu_tara.setStatusBar(self.statusbar)
        self.menubar.addAction(self.menuOPC_DA_OPC_UA_GATEWAY.menuAction())

        self.retranslateUi(btn_sunucu_tara)
        QtCore.QMetaObject.connectSlotsByName(btn_sunucu_tara)

    def retranslateUi(self, btn_sunucu_tara):
        _translate = QtCore.QCoreApplication.translate
        btn_sunucu_tara.setWindowTitle(_translate("btn_sunucu_tara", "KATOT - OPC Gateway"))
        self.pushButton.setText(_translate("btn_sunucu_tara", "Sunucuları Tara"))
        self.label.setText(_translate("btn_sunucu_tara", "ProgID"))
        self.label_2.setText(_translate("btn_sunucu_tara", "Etiket Seçimi"))
        self.btn_etiket_tara.setText(_translate("btn_sunucu_tara", "Etiketleri Tara"))
        self.txt_ip.setText(_translate("btn_sunucu_tara", "0.0.0.0"))
        self.btn_baslat.setText(_translate("btn_sunucu_tara", "Başlat"))
        self.btn_durdur.setText(_translate("btn_sunucu_tara", "Durdur"))
        self.label_3.setText(_translate("btn_sunucu_tara", "Başlatma Ve IP"))
        self.label_4.setText(_translate("btn_sunucu_tara", "Canlı Veri"))
        self.label_5.setText(_translate("btn_sunucu_tara", "Kurulum"))
        self.btn_kurulum_ac.setText(_translate("btn_sunucu_tara", "⚙️ Sistem Kurulumları"))
        self.menuOPC_DA_OPC_UA_GATEWAY.setTitle(_translate("btn_sunucu_tara", "OPC DA - OPC UA GATEWAY"))

# =====================================================================
# 2. BÖLÜM: DİNAMİK KURULUM YÖNETİCİSİ (Açılır Pencere)
# =====================================================================
class KurulumPenceresi(QtWidgets.QDialog):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Sistem Kurulum ve Onarım Merkezi")
        self.resize(550, 450)
        layout = QtWidgets.QVBoxLayout(self)

        # Python Mimari Kontrolü
        self.lbl_mimari = QtWidgets.QLabel()
        self.lbl_mimari.setAlignment(QtCore.Qt.AlignCenter)
        if sys.maxsize > 2**32:
            self.lbl_mimari.setText("⚠️ UYARI: Python 64-Bit Çalışıyor! (32-Bit Tavsiye Edilir)")
            self.lbl_mimari.setStyleSheet("color: red; font-weight: bold; font-size: 13px;")
        else:
            self.lbl_mimari.setText("✅ Sistem Harika: Python 32-Bit Tespit Edildi.")
            self.lbl_mimari.setStyleSheet("color: green; font-weight: bold; font-size: 13px;")
        layout.addWidget(self.lbl_mimari)

        # 0. Python İndirme Satırı
        h0 = QtWidgets.QHBoxLayout()
        self.btn_python = QtWidgets.QPushButton("0. Python 3.13 (32-Bit) İndir ve Kur")
        self.btn_python.setStyleSheet("background-color: #3776ab; color: white; font-weight: bold;")
        self.btn_python.clicked.connect(self.python_indir_ve_kur)
        self.lbl_durum0 = QtWidgets.QLabel("❌ İndirilmedi")
        self.lbl_durum0.setStyleSheet("color: gray;")
        h0.addWidget(self.btn_python)
        h0.addWidget(self.lbl_durum0)
        layout.addLayout(h0)

        # 1. Kütüphane Kurulum Satırı
        h1 = QtWidgets.QHBoxLayout()
        self.btn_kutuphane = QtWidgets.QPushButton("1. Gerekli Tüm Kütüphaneleri Kur")
        self.btn_kutuphane.clicked.connect(self.kutuphaneleri_kur)
        self.lbl_durum1 = QtWidgets.QLabel("❌ Kurulmadı")
        self.lbl_durum1.setStyleSheet("color: gray;")
        h1.addWidget(self.btn_kutuphane)
        h1.addWidget(self.lbl_durum1)
        layout.addLayout(h1)

        # 2. DLL Kayıt Satırı
        h2 = QtWidgets.QHBoxLayout()
        self.btn_dll = QtWidgets.QPushButton("2. Windows COM/DLL Sistemini Onar")
        self.btn_dll.clicked.connect(self.dll_kaydet)
        self.lbl_durum2 = QtWidgets.QLabel("❌ Yapılmadı")
        self.lbl_durum2.setStyleSheet("color: gray;")
        h2.addWidget(self.btn_dll)
        h2.addWidget(self.lbl_durum2)
        layout.addLayout(h2)

        # Log Ekranı
        self.kurulum_log = QtWidgets.QTextEdit()
        self.kurulum_log.setReadOnly(True)
        self.kurulum_log.setStyleSheet("background-color: #1e1e1e; color: #d4d4d4;")
        layout.addWidget(self.kurulum_log)

    def log_ekle(self, metin):
        self.kurulum_log.append(metin)
        self.kurulum_log.moveCursor(QtGui.QTextCursor.End)

    def python_indir_ve_kur(self):
        def islem():
            self.lbl_durum0.setText("⏳ İndiriliyor...")
            self.lbl_durum0.setStyleSheet("color: orange;")
            self.log_ekle("📥 Python 3.13 (32-Bit) sunucudan indiriliyor... (Yaklaşık 25MB, lütfen bekleyin)")
            
            url = "https://www.python.org/ftp/python/3.13.13/python-3.13.13.exe"
            hedef_dosya = os.path.join(tempfile.gettempdir(), "python_3.13.13_32bit_kurulum.exe")
            
            try:
                urllib.request.urlretrieve(url, hedef_dosya)
                self.log_ekle("✅ İndirme tamamlandı! Kurulum sihirbazı açılıyor...")
                self.log_ekle("⚠️ DİKKAT: Açılan kurulum ekranının en altındaki 'Add Python.exe to PATH' kutucuğunu MUTLAKA İŞARETLEYİN!")
                self.lbl_durum0.setText("✅ Tamamlandı")
                self.lbl_durum0.setStyleSheet("color: green; font-weight: bold;")
                
                # İndirilen dosyayı çalıştır
                subprocess.Popen([hedef_dosya], shell=True)
            except Exception as e:
                self.log_ekle(f"❌ İndirme Hatası: {e}")
                self.lbl_durum0.setText("❌ Hata")
                self.lbl_durum0.setStyleSheet("color: red;")
                
        threading.Thread(target=islem, daemon=True).start()

    def komut_calistir(self, komut, etiket_widget, basari_mesaji):
        def islem():
            self.log_ekle(f"⏳ Başlatılıyor: {' '.join(komut)}")
            try:
                process = subprocess.Popen(komut, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, creationflags=subprocess.CREATE_NO_WINDOW)
                for line in process.stdout:
                    self.log_ekle(line.strip())
                process.wait()
                if process.returncode == 0:
                    etiket_widget.setText(basari_mesaji)
                    etiket_widget.setStyleSheet("color: green; font-weight: bold;")
                    self.log_ekle("✅ İşlem Başarılı.")
                else:
                    self.log_ekle("❌ İşlem sırasında hata oluştu.")
            except Exception as e:
                self.log_ekle(f"KRİTİK HATA: {e}")
        threading.Thread(target=islem, daemon=True).start()

    def kutuphaneleri_kur(self):
        self.lbl_durum1.setText("⏳ Kuruluyor...")
        self.lbl_durum1.setStyleSheet("color: orange;")
        komut = [sys.executable, "-m", "pip", "install", "OpenOPC-Python3x", "asyncua", "pywin32", "pyro4"]
        self.komut_calistir(komut, self.lbl_durum1, "✅ Kuruldu")

    def dll_kaydet(self):
        self.lbl_durum2.setText("⏳ Onarılıyor...")
        self.lbl_durum2.setStyleSheet("color: orange;")
        komut = [sys.executable, "-m", "pywin32_postinstall", "-install"]
        self.komut_calistir(komut, self.lbl_durum2, "✅ Onarıldı")

# =====================================================================
# 3. BÖLÜM: YARDIMCI SINIFLAR VE GATEWAY MOTORU
# =====================================================================
class EmittingStream(QObject):
    textWritten = pyqtSignal(str)
    def write(self, text): self.textWritten.emit(str(text))
    def flush(self): pass

class GatewayWorker(QThread):
    finished_signal = pyqtSignal()
    
    def __init__(self, prog_id, ip, etiketler):
        super().__init__()
        self.prog_id = prog_id; self.ip = ip; self.etiketler = etiketler; self.is_running = True

    def run(self):
        try:
            import pythoncom, OpenOPC, pywintypes
            from asyncua import Server, ua
            
            def w_zaman_cevir(dt):
                return datetime.datetime, (dt.year, dt.month, dt.day, dt.hour, dt.minute, dt.second, dt.microsecond)
            copyreg.pickle(type(pywintypes.Time(1)), w_zaman_cevir)

            async def asenkron_gateway():
                ua_server = Server()
                await ua_server.init()
                ua_server.set_endpoint(f"opc.tcp://{self.ip}:4840/")
                ua_server.set_server_name("KATOT_Gateway")
                idx = await ua_server.register_namespace("http://katot_endustri/monitoring")
                ana_depo = await ua_server.nodes.objects.add_object(idx, "Saha_Verileri")

                async with ua_server:
                    print(f"🚀 GATEWAY AKTİF: opc.tcp://{self.ip}:4840/")
                    pythoncom.CoInitialize()
                    opc = OpenOPC.client()
                    opc.connect(self.prog_id)
                    print("✅ OPC DA Bağlandı.\n")

                    harita = {}
                    for et in self.etiketler:
                        isim = et.replace('.', '_').replace(' ', '_')
                        harita[et] = await ana_depo.add_variable(idx, isim, 0.0, ua.VariantType.Double)
                    
                    while self.is_running:
                        okumalar = opc.read(list(harita.keys()))
                        for adi, deg, kal, zam in okumalar:
                            if deg is not None and kal == 'Good':
                                await harita[adi].write_value(float(deg), ua.VariantType.Double)
                        print(f"⏳ Veri Akışı Aktif: {len(okumalar)} Etiket Güncelleniyor.")
                        await asyncio.sleep(1)
                    opc.close()

            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(asenkron_gateway())
        except ImportError:
            print("❌ HATA: Gerekli kütüphaneler eksik! Lütfen 'Kurulum' menüsünden kurulumları yapın.")
        except Exception as e: 
            print(f"HATA: {e}")
        finally: 
            self.finished_signal.emit()

    def stop(self): self.is_running = False

# =====================================================================
# 4. BÖLÜM: ANA UYGULAMA (Arayüz Bağlantıları)
# =====================================================================
class GatewayApp(QtWidgets.QMainWindow, Ui_btn_sunucu_tara):
    def __init__(self):
        super().__init__()
        self.setupUi(self)
        self.gateway_worker = None
        self.kurulum_penceresi = KurulumPenceresi() 

        self.txt_konsol.setStyleSheet("background-color: black; color: #00FF00; font-family: Consolas; font-size: 13px;")
        sys.stdout = EmittingStream(textWritten=self.log_yazdir)
        
        self.list_etiket.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)
        self.btn_durdur.setEnabled(False)

        self.btn_kurulum_ac.clicked.connect(self.kurulum_penceresini_goster)
        self.pushButton.clicked.connect(self.tara_sunucu)
        self.btn_etiket_tara.clicked.connect(self.tara_etiket)
        self.btn_baslat.clicked.connect(self.baslat)
        self.btn_durdur.clicked.connect(self.durdur)

    def kurulum_penceresini_goster(self):
        self.kurulum_penceresi.show() 

    def log_yazdir(self, text):
        crs = self.txt_konsol.textCursor()
        crs.movePosition(QTextCursor.End)
        crs.insertText(text)
        self.txt_konsol.setTextCursor(crs)
        self.txt_konsol.ensureCursorVisible()

    def tara_sunucu(self):
        try:
            import OpenOPC
            opc = OpenOPC.client()
            self.cb_sunucu.clear()
            self.cb_sunucu.addItems(opc.servers())
        except ImportError: 
            print("❌ Lütfen önce '⚙️ Sistem Kurulumları' menüsünden kütüphaneleri yükleyin!")
        except Exception as e: 
            print(f"HATA: {e}")

    def tara_etiket(self):
        try:
            import OpenOPC
            opc = OpenOPC.client()
            opc.connect(self.cb_sunucu.currentText())
            self.list_etiket.clear()
            self.list_etiket.addItems(opc.list('**'))
            opc.close()
        except ImportError:
            print("❌ Lütfen kütüphaneleri yükleyin.")
        except Exception as e: 
            print(f"BAĞLANTI HATASI: {e}")

    def baslat(self):
        srv = self.cb_sunucu.currentText()
        tags = [i.text() for i in self.list_etiket.selectedItems()]
        if not srv or not tags: 
            return print("⚠️ Hata: Sunucu veya Etiket listesinden seçim yapmadınız!")
        
        self.btn_baslat.setEnabled(False)
        self.btn_durdur.setEnabled(True)
        self.txt_konsol.clear()
        
        self.gateway_worker = GatewayWorker(srv, self.txt_ip.text(), tags)
        self.gateway_worker.finished_signal.connect(self.bitti)
        self.gateway_worker.start()

    def durdur(self):
        if self.gateway_worker: 
            self.gateway_worker.stop()
            self.btn_durdur.setEnabled(False)
            print("\n🛑 Kapatma isteği gönderildi, bekleniyor...")

    def bitti(self):
        self.btn_baslat.setEnabled(True)
        self.btn_durdur.setEnabled(False)

if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    pencere = GatewayApp()
    pencere.show()
    sys.exit(app.exec_())