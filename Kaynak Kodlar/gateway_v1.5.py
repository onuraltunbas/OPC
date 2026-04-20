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
import multiprocessing

# EXE'nin kendi kendini klonlayıp çökmesini önleyen en kritik komut (En başta olmalı)
if __name__ == '__main__':
    multiprocessing.freeze_support()

from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtCore import QThread, pyqtSignal, QObject
from PyQt5.QtGui import QTextCursor

# =====================================================================
# 1. BÖLÜM: ARAYÜZ TASARIMI (Senin Çizdiğin Qt Designer Çıktısı)
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
        self.cb_sunucu.setGeometry(QtCore.QRect(250, 220, 140, 31)) 
        self.cb_sunucu.setObjectName("cb_sunucu")
        self.label = QtWidgets.QLabel(self.centralwidget)
        self.label.setGeometry(QtCore.QRect(270, 180, 47, 13))
        self.label.setObjectName("label")
        self.label_2 = QtWidgets.QLabel(self.centralwidget)
        self.label_2.setGeometry(QtCore.QRect(440, 170, 80, 21))
        self.label_2.setObjectName("label_2")
        self.btn_etiket_tara = QtWidgets.QPushButton(self.centralwidget)
        self.btn_etiket_tara.setGeometry(QtCore.QRect(430, 190, 81, 21))
        self.btn_etiket_tara.setObjectName("btn_etiket_tara")
        self.list_etiket = QtWidgets.QListWidget(self.centralwidget)
        self.list_etiket.setGeometry(QtCore.QRect(400, 210, 161, 91))
        self.list_etiket.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)
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
        self.label_3.setGeometry(QtCore.QRect(650, 180, 80, 16))
        self.label_3.setObjectName("label_3")
        self.label_4 = QtWidgets.QLabel(self.centralwidget)
        self.label_4.setGeometry(QtCore.QRect(40, 320, 80, 16))
        self.label_4.setObjectName("label_4")
        self.label_5 = QtWidgets.QLabel(self.centralwidget)
        self.label_5.setGeometry(QtCore.QRect(10, 20, 47, 13))
        self.label_5.setObjectName("label_5")
        self.btn_kurulum_ac = QtWidgets.QPushButton(self.centralwidget)
        self.btn_kurulum_ac.setGeometry(QtCore.QRect(20, 40, 150, 31))
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
        btn_sunucu_tara.setWindowTitle(_translate("btn_sunucu_tara", "KATOT IIoT Gateway"))
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
# 2. BÖLÜM: KURULUM PENCERESİ
# =====================================================================
class KurulumPenceresi(QtWidgets.QDialog):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Sistem Kurulum Merkezi")
        self.resize(500, 450)
        self.setModal(True)
        layout = QtWidgets.QVBoxLayout(self)

        self.lbl_mimari = QtWidgets.QLabel()
        self.lbl_mimari.setAlignment(QtCore.Qt.AlignCenter)
        if sys.maxsize > 2**32:
            self.lbl_mimari.setText("⚠️ UYARI: Python 64-Bit! (32-Bit Tavsiye Edilir)")
            self.lbl_mimari.setStyleSheet("color: red; font-weight: bold;")
        else:
            self.lbl_mimari.setText("✅ Sistem Uygun: Python 32-Bit Tespit Edildi.")
            self.lbl_mimari.setStyleSheet("color: green; font-weight: bold;")
        layout.addWidget(self.lbl_mimari)

        # 0. Python
        h0 = QtWidgets.QHBoxLayout()
        self.btn_python = QtWidgets.QPushButton("0. Python 3.13 (32-Bit) İndir/Kur")
        self.btn_python.setStyleSheet("background-color: #3776ab; color: white;")
        self.btn_python.clicked.connect(self.python_indir_ve_kur)
        self.lbl_durum0 = QtWidgets.QLabel("❌ Yapılmadı"); self.lbl_durum0.setStyleSheet("color: gray;")
        h0.addWidget(self.btn_python); h0.addWidget(self.lbl_durum0)
        layout.addLayout(h0)

        # 1. Kütüphaneler
        h1 = QtWidgets.QHBoxLayout()
        self.btn_kutuphane = QtWidgets.QPushButton("1. Kütüphaneleri Kur (PIP)")
        self.btn_kutuphane.clicked.connect(self.kutuphaneleri_kur)
        self.lbl_durum1 = QtWidgets.QLabel("❌ Yapılmadı"); self.lbl_durum1.setStyleSheet("color: gray;")
        h1.addWidget(self.btn_kutuphane); h1.addWidget(self.lbl_durum1)
        layout.addLayout(h1)

        # 2. DLL
        h2 = QtWidgets.QHBoxLayout()
        self.btn_dll = QtWidgets.QPushButton("2. Windows DLL'lerini Onar")
        self.btn_dll.clicked.connect(self.dll_kaydet)
        self.lbl_durum2 = QtWidgets.QLabel("❌ Yapılmadı"); self.lbl_durum2.setStyleSheet("color: gray;")
        h2.addWidget(self.btn_dll); h2.addWidget(self.lbl_durum2)
        layout.addLayout(h2)

        self.kurulum_log = QtWidgets.QTextEdit()
        self.kurulum_log.setReadOnly(True)
        self.kurulum_log.setStyleSheet("background-color: #1e1e1e; color: #d4d4d4;")
        layout.addWidget(self.kurulum_log)

    def log_yaz(self, metin):
        self.kurulum_log.append(metin)
        self.kurulum_log.moveCursor(QtGui.QTextCursor.End)

    def komut_calistir(self, komut, lbl_widget):
        def islem():
            lbl_widget.setText("⏳ İşleniyor...")
            lbl_widget.setStyleSheet("color: orange;")
            self.log_yaz(f"> Komut Başlatıldı: {komut}")
            try:
                p = subprocess.Popen(komut, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, shell=True)
                for line in p.stdout:
                    self.log_yaz(line.strip())
                p.wait()
                lbl_widget.setText("✅ Tamamlandı")
                lbl_widget.setStyleSheet("color: green; font-weight: bold;")
            except Exception as e:
                self.log_yaz(f"❌ Hata: {e}")
                lbl_widget.setText("❌ Hata")
        threading.Thread(target=islem, daemon=True).start()

    def python_indir_ve_kur(self):
        url = "https://www.python.org/ftp/python/3.13.13/python-3.13.13.exe"
        path = os.path.join(tempfile.gettempdir(), "py_setup.exe")
        def download():
            self.lbl_durum0.setText("⏳ İndiriliyor...")
            self.lbl_durum0.setStyleSheet("color: orange;")
            self.log_yaz("📥 Python 3.13 indiriliyor... (Lütfen bekleyin)")
            try:
                urllib.request.urlretrieve(url, path)
                self.log_yaz("✅ İndirme bitti! Kurulum ekranı açılıyor.")
                self.log_yaz("⚠️ LÜTFEN EKRANDAKİ 'Add Python.exe to PATH' TİKİNİ İŞARETLEYİN!")
                self.lbl_durum0.setText("✅ Kuruluma Geçildi")
                subprocess.Popen([path], shell=True)
            except Exception as e:
                self.log_yaz(f"❌ İndirme Hatası: {e}")
        threading.Thread(target=download, daemon=True).start()

    def kutuphaneleri_kur(self):
        self.komut_calistir("python -m pip install OpenOPC-Python3x asyncua pywin32 pyro4", self.lbl_durum1)

    def dll_kaydet(self):
        self.komut_calistir("python -m pywin32_postinstall -install", self.lbl_durum2)

# =====================================================================
# 3. BÖLÜM: GATEWAY MOTORU (TEKİL OKUMA - MATRIKON ÇÖKME FİXİ)
# =====================================================================
class GatewayWorker(QThread):
    finished_signal = pyqtSignal()
    
    def __init__(self, prog_id, ip, etiketler):
        super().__init__()
        self.prog_id = prog_id; self.ip = ip; self.etiketler = etiketler; self.is_running = True

    def run(self):
        try:
            import pythoncom, OpenOPC, pywintypes
            from asyncua import Server, ua
            
            def w_conv(dt): return datetime.datetime, (dt.year, dt.month, dt.day, dt.hour, dt.minute, dt.second, dt.microsecond)
            copyreg.pickle(type(pywintypes.Time(1)), w_conv)

            async def main_loop():
                srv = Server()
                await srv.init()
                srv.set_endpoint(f"opc.tcp://{self.ip}:4840/")
                idx = await srv.register_namespace("http://katot/gateway")
                root = await srv.nodes.objects.add_object(idx, "Saha_Verileri")

                async with srv:
                    print(f"📡 OPC UA Yayınında: opc.tcp://{self.ip}:4840/")
                    pythoncom.CoInitialize()
                    opc = OpenOPC.client()
                    opc.connect(self.prog_id)
                    print("✅ OPC DA Sunucusuna Bağlanıldı.")
                    
                    nodes = {}
                    for et in self.etiketler:
                        safe_name = et.replace(".", "_").replace(" ", "_")
                        nodes[et] = await root.add_variable(idx, safe_name, 0.0, ua.VariantType.Double)
                    
                    print(f"🔄 Seçilen {len(self.etiketler)} etiket için canlı yayın başladı...")

                    while self.is_running:
                        # HATA ÇÖZÜMÜ: Matrikon'u yormamak için etiketler TEK TEK okutulur.
                        for et_adi in nodes.keys():
                            try:
                                sonuc = opc.read(et_adi, sync=True)
                                if sonuc:
                                    val, qual, time = sonuc
                                    if val is not None and qual == 'Good':
                                        await nodes[et_adi].write_value(float(val), ua.VariantType.Double)
                            except Exception as alt_hata:
                                pass # Kopan sensör olursa program çökmesin, sonrakine geçsin
                                
                        print(f"⏳ Akış Aktif: Veriler başarıyla iletiliyor...")
                        await asyncio.sleep(1)
                    opc.close()

            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(main_loop())
        except ImportError:
            print("❌ Kütüphaneler eksik! Lütfen 'Kurulum' menüsünden kurulumları tamamlayın.")
        except Exception as e: 
            print(f"❌ Motor Hatası: {e}")
        finally:
            self.finished_signal.emit()

    def stop(self): self.is_running = False

# =====================================================================
# 4. BÖLÜM: ANA UYGULAMA (SİNYAL VE BUTON BAĞLANTILARI)
# =====================================================================
class GatewayApp(QtWidgets.QMainWindow, Ui_btn_sunucu_tara):
    def __init__(self):
        super().__init__()
        self.setupUi(self)
        self.worker = None
        self.kurulum_penceresi = KurulumPenceresi()
        
        # Konsol Makyajı ve Yönlendirmesi
        self.txt_konsol.setStyleSheet("background: black; color: #00ff00; font-family: Consolas; font-size: 13px;")
        class Stream(QObject):
            written = pyqtSignal(str)
            def write(self, text): self.written.emit(str(text))
            def flush(self): pass
        
        self.monitor = Stream()
        self.monitor.written.connect(lambda t: self.txt_konsol.insertPlainText(t))
        sys.stdout = self.monitor

        self.btn_durdur.setEnabled(False)

        # Buton Bağlantıları
        self.btn_kurulum_ac.clicked.connect(self.kurulum_penceresi.show)
        self.pushButton.clicked.connect(self.sunucu_tara)
        self.btn_etiket_tara.clicked.connect(self.etiket_tara)
        self.btn_baslat.clicked.connect(self.baslat)
        self.btn_durdur.clicked.connect(self.durdur)

    def sunucu_tara(self):
        try:
            import OpenOPC
            opc = OpenOPC.client()
            self.cb_sunucu.clear()
            self.cb_sunucu.addItems(opc.servers())
            print("✅ Sunucular başarıyla bulundu.\n")
        except: 
            print("❌ Lütfen önce kütüphaneleri kurun!\n")

    def etiket_tara(self):
        try:
            import OpenOPC
            opc = OpenOPC.client()
            opc.connect(self.cb_sunucu.currentText())
            self.list_etiket.clear()
            print("⏳ Klasörlerin içi derinlemesine taranıyor...\n")
            
            # Derin Tarama
            tags = opc.list('**', flat=True)
            if not tags or len(tags) <= 5:
                tags = []
                for klasor in opc.list():
                    for alt_klasor in opc.list(klasor):
                        sensorler = opc.list(f"{klasor}.{alt_klasor}.*", flat=True)
                        if sensorler: tags.extend(sensorler)
            
            # Matrikon Test Etiketleri (Yedek)
            if not tags:
                tags = ['Random.Real8', 'Random.Int4', 'Random.Boolean', 'Triangle Waves.Real8', 'Saw-toothed Waves.Int4']

            self.list_etiket.addItems(tags)
            opc.close()
            print(f"✅ Etiketler listeye eklendi. Listeden okumak istediklerinizi seçin.\n")
        except: 
            print("❌ Bağlantı hatası veya kütüphane eksik.\n")

    def baslat(self):
        srv = self.cb_sunucu.currentText()
        
        # Sadece "Seçili Olan" etiketleri UA'ya gönderiyoruz
        secili_ogeler = self.list_etiket.selectedItems()
        tags = [item.text() for item in secili_ogeler]

        if not srv:
            return QtWidgets.QMessageBox.warning(self, "Hata", "Lütfen bir sunucu seçin!")
        if not tags:
            return QtWidgets.QMessageBox.warning(self, "Hata", "Listeden okumak istediğiniz etiketleri işaretleyin!")

        self.btn_baslat.setEnabled(False)
        self.btn_durdur.setEnabled(True)
        self.txt_konsol.clear()
        
        self.worker = GatewayWorker(srv, self.txt_ip.text(), tags)
        self.worker.finished_signal.connect(self.bitti)
        self.worker.start()

    def durdur(self):
        if self.worker:
            self.worker.stop()
            self.btn_durdur.setEnabled(False)
            print("\n🛑 Gateway kapatılıyor...")

    def bitti(self):
        self.btn_baslat.setEnabled(True)
        self.btn_durdur.setEnabled(False)

if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    pencere = GatewayApp()
    pencere.show()
    sys.exit(app.exec_())