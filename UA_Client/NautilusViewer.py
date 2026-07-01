# -*- coding: utf-8 -*-
"""
OPC UA Viewer (Client)
Nautilus Technology - Kurumsal Tema Uyumlu
"""

import sys
import asyncio
import datetime
from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtCore import QThread, pyqtSignal, QObject, Qt
from asyncua import Client

# Ana programla birebir aynı tema, QTableWidget eklemeleriyle zenginleştirildi.
GLOBAL_STYLESHEET = """
QWidget {
    background-color: #0f1117;
    color: #e0e0e0;
    font-family: "Segoe UI", system-ui, sans-serif;
}
QGroupBox {
    background-color: #1a1d2e;
    border: 1px solid #2a2d3e;
    border-radius: 6px;
    margin-top: 14px;
    font-weight: bold;
    color: #5b8cff;
}
QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 0 5px;
    left: 10px;
}
QPushButton {
    background-color: #222540;
    color: #e0e0e0;
    border: 1px solid #2a2d3e;
    border-radius: 6px;
    padding: 8px 14px;
    font-weight: bold;
}
QPushButton:hover {
    background-color: #2a2d3e;
    border-color: #5b8cff;
}
QPushButton:pressed {
    background-color: #1a1d2e;
}
QPushButton:disabled {
    background-color: #1e2033;
    color: #666666;
    border-color: #1e2033;
}
QLineEdit, QTextEdit {
    background-color: #0a0c14;
    border: 1px solid #2a2d3e;
    border-radius: 6px;
    color: #e0e0e0;
    padding: 6px;
}
QLineEdit:focus, QTextEdit:focus {
    border-color: #5b8cff;
}
QTableWidget {
    background-color: #0a0c14;
    color: #4ade80;
    font-family: Consolas, 'Courier New';
    font-size: 13px;
    border: 1px solid #2a2d3e;
    border-radius: 6px;
    gridline-color: #1a1d2e;
}
QHeaderView::section {
    background-color: #1a1d2e;
    color: #5b8cff;
    font-weight: bold;
    border: 1px solid #2a2d3e;
    padding: 4px;
}
QTableCornerButton::section {
    background-color: #1a1d2e;
    border: 1px solid #2a2d3e;
}
"""

# =====================================================================
# BÖLÜM 1: ASYNCUA ABONELİK YAKALAYICI
# =====================================================================
class SubscriptionHandler:
    """Sunucudan gelen anlık veri değişimlerini yakalar ve GUI'ye sinyal gönderir."""
    def __init__(self, veri_sinyali):
        self.veri_sinyali = veri_sinyali

    def datachange_notification(self, node, val, data):
        node_id = str(node.nodeid.Identifier)
        # Gelen zaman damgasını formatla
        ts = data.monitored_item.Value.ServerTimestamp
        ts_str = ts.strftime("%H:%M:%S.%f")[:-3] if ts else datetime.datetime.now().strftime("%H:%M:%S")
        self.veri_sinyali.emit(node_id, str(val), ts_str)

# =====================================================================
# BÖLÜM 2: OPC UA CLIENT MOTORU (ARKA PLAN)
# =====================================================================
class UaClientWorker(QThread):
    log_sinyali    = pyqtSignal(str)
    baglan_sinyali = pyqtSignal(bool)
    veri_sinyali   = pyqtSignal(str, str, str) # NodeID, Value, Timestamp

    def __init__(self, endpoint_url):
        super().__init__()
        self.endpoint_url = endpoint_url
        self._calisiyor = True
        self.client = None

    def _log(self, metin):
        self.log_sinyali.emit(str(metin))

    def run(self):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(self._istemci_dongusu())
        except Exception as e:
            self._log(f"İstemci Hatası: {e}")
            self.baglan_sinyali.emit(False)
        finally:
            loop.close()

    async def _istemci_dongusu(self):
        from asyncua import Client, ua
        self.client = Client(url=self.endpoint_url)
        try:
            self._log(f"Bağlanılıyor: {self.endpoint_url}")
            await self.client.connect()
            self.baglan_sinyali.emit(True)
            self._log("Bağlantı başarılı. Sadece 'Saha_Verileri' taranıyor...")

            degiskenler = []
            
            # 1. Sadece "Objects" ana dizinine git
            objects_node = self.client.nodes.objects
            cocuklar = await objects_node.get_children()
            
            # 2. İçerisinde sadece Gateway'in ürettiği "Saha_Verileri" klasörünü bul
            hedef_klasor = None
            for child in cocuklar:
                bname = await child.read_browse_name()
                if bname.Name == "Saha_Verileri":
                    hedef_klasor = child
                    break
                    
            # 3. Klasör bulunduysa, içindeki değişkenleri listeye al
            if hedef_klasor:
                klasor_icindekiler = await hedef_klasor.get_children()
                for item in klasor_icindekiler:
                    node_class = await item.read_node_class()
                    if node_class == ua.NodeClass.Variable:
                        degiskenler.append(item)
            
            if not degiskenler:
                self._log("Uyarı: Sunucuda 'Saha_Verileri' bulunamadı!")
                self._log("Lütfen Gateway programında yayının başlatıldığından emin olun.")
            else:
                self._log(f"{len(degiskenler)} adet özel etiket bulundu. Akış başlıyor...")
                # Sadece senin seçtiğin etiketlere abone ol
                handler = SubscriptionHandler(self.veri_sinyali)
                sub = await self.client.create_subscription(100, handler)
                await sub.subscribe_data_change(degiskenler)

            while self._calisiyor:
                await asyncio.sleep(1)

        except asyncio.CancelledError: 
            pass
        except Exception as e:
            self._log(f"Bağlantı koptu veya hata: {e}")
            self.baglan_sinyali.emit(False)
        finally:
            if self.client:
                try: 
                    await self.client.disconnect()
                except: 
                    pass
            self._log("Bağlantı kesildi.")

    def durdur(self):
        self._calisiyor = False
        self.client = None  # Client referansını hemen bırak

# =====================================================================
# BÖLÜM 3: ARAYÜZ TASARIMI
# =====================================================================
class LogKoprusu(QObject):
    log_sinyali = pyqtSignal(str)

    def __init__(self, hedef_widget):
        super().__init__()
        self.log_sinyali.connect(self._yaz)
        self.hedef = hedef_widget

    def _yaz(self, metin):
        self.hedef.append(metin)
        self.hedef.moveCursor(QtGui.QTextCursor.End)

    def yaz(self, metin):
        self.log_sinyali.emit(str(metin))

class ClientApp(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.worker = None
        self.etiket_satirlari = {} # NodeID -> Tablo Satır Indexi

        self.setWindowTitle("Nautilus Technology - OPC UA Viewer")
        self.resize(780, 600)
        self.setMinimumSize(780, 600)

        self.centralwidget = QtWidgets.QWidget(self)
        self.setCentralWidget(self.centralwidget)

        # 1. Bağlantı Paneli
        grp_baglanti = QtWidgets.QGroupBox("Sunucu Bağlantısı", self.centralwidget)
        grp_baglanti.setGeometry(20, 20, 740, 80)
        lay_baglanti = QtWidgets.QHBoxLayout(grp_baglanti)
        
        self.txt_url = QtWidgets.QLineEdit("opc.tcp://127.0.0.1:4840/")
        self.btn_baglan = QtWidgets.QPushButton("Bağlan")
        self.btn_baglan.setStyleSheet("background-color: #2e7d32; color: white; border: none;")
        self.btn_kes = QtWidgets.QPushButton("Bağlantıyı Kes")
        self.btn_kes.setStyleSheet("background-color: #c62828; color: white; border: none;")
        self.btn_kes.setEnabled(False)

        lay_baglanti.addWidget(QtWidgets.QLabel("Endpoint URL:"), 0)
        lay_baglanti.addWidget(self.txt_url, 1)
        lay_baglanti.addWidget(self.btn_baglan, 0)
        lay_baglanti.addWidget(self.btn_kes, 0)

        # 2. Canlı Veri Tablosu
        grp_veri = QtWidgets.QGroupBox("Canlı Saha Verileri", self.centralwidget)
        grp_veri.setGeometry(20, 110, 740, 300)
        lay_veri = QtWidgets.QVBoxLayout(grp_veri)
        
        self.tablo = QtWidgets.QTableWidget(0, 3)
        self.tablo.setHorizontalHeaderLabels(["Etiket (NodeID)", "Değer", "Son Güncelleme"])
        header = self.tablo.horizontalHeader()
        header.setSectionResizeMode(0, QtWidgets.QHeaderView.Stretch)
        header.setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeToContents)
        header.setSectionResizeMode(2, QtWidgets.QHeaderView.ResizeToContents)
        self.tablo.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.tablo.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        lay_veri.addWidget(self.tablo)

        # 3. Log Konsolu
        grp_log = QtWidgets.QGroupBox("Sistem Logları", self.centralwidget)
        grp_log.setGeometry(20, 420, 740, 160)
        lay_log = QtWidgets.QVBoxLayout(grp_log)
        self.txt_konsol = QtWidgets.QTextEdit()
        self.txt_konsol.setReadOnly(True)
        lay_log.addWidget(self.txt_konsol)

        self._log_koprusu = LogKoprusu(self.txt_konsol)

        # Sinyal Bağlantıları
        self.btn_baglan.clicked.connect(self._baglan)
        self.btn_kes.clicked.connect(self._kes)

        self._log("OPC UA Görüntüleyici hazır. Sunucu URL'sini girip bağlanın.")

    def _log(self, metin):
        self._log_koprusu.yaz(metin)

    def _baglan(self):
        url = self.txt_url.text().strip()
        if not url:
            return

        # Eski worker varsa önce düzgünce temizle
        if self.worker is not None:
            self._worker_baglantilari_kes(self.worker)
            if self.worker.isRunning():
                self.worker.durdur()
                self.worker.wait(3000)  # En fazla 3 sn bekle
            self.worker = None

        self.btn_baglan.setEnabled(False)
        self.btn_kes.setEnabled(False)
        self.txt_url.setEnabled(False)
        self.tablo.setRowCount(0)
        self.etiket_satirlari.clear()

        self.worker = UaClientWorker(url)
        self.worker.log_sinyali.connect(self._log)
        self.worker.baglan_sinyali.connect(self._baglanti_durumu)
        self.worker.veri_sinyali.connect(self._veri_guncelle)
        # Thread bittiğinde UI'yi sıfırla
        self.worker.finished.connect(self._worker_bitti)
        self.worker.start()

    def _worker_baglantilari_kes(self, worker):
        """Eski worker sinyallerini güvenli şekilde ayır."""
        try:
            worker.log_sinyali.disconnect(self._log)
        except Exception:
            pass
        try:
            worker.baglan_sinyali.disconnect(self._baglanti_durumu)
        except Exception:
            pass
        try:
            worker.veri_sinyali.disconnect(self._veri_guncelle)
        except Exception:
            pass
        try:
            worker.finished.disconnect(self._worker_bitti)
        except Exception:
            pass

    @QtCore.pyqtSlot()
    def _worker_bitti(self):
        """Thread tamamen kapanınca Bağlan butonunu tekrar aktifleştir."""
        self.btn_baglan.setEnabled(True)
        self.btn_kes.setEnabled(False)
        self.txt_url.setEnabled(True)
        self._log("Bağlantı tamamen sonlandırıldı. Tekrar bağlanabilirsiniz.")

    def _kes(self):
        if self.worker and self.worker.isRunning():
            self.worker.durdur()
            self.btn_kes.setEnabled(False)
            self.btn_baglan.setEnabled(False)  # Worker bitmeden tekrar bağlanmayı engelle
            self._log("Durdurma sinyali gönderildi, bağlantı kapatılıyor...")

    @QtCore.pyqtSlot(bool)
    def _baglanti_durumu(self, basarili):
        if basarili:
            self.btn_baglan.setEnabled(False)
            self.btn_kes.setEnabled(True)
        else:
            # Hata durumunda worker'ın finished sinyali zaten UI'yi sıfırlayacak
            self.btn_kes.setEnabled(False)

    @QtCore.pyqtSlot(str, str, str)
    def _veri_guncelle(self, node_id, deger, zaman):
        if node_id not in self.etiket_satirlari:
            # Yeni bir etiket geldiyse tabloya satır ekle
            row_idx = self.tablo.rowCount()
            self.tablo.insertRow(row_idx)
            
            item_node = QtWidgets.QTableWidgetItem(node_id)
            item_val = QtWidgets.QTableWidgetItem(deger)
            item_time = QtWidgets.QTableWidgetItem(zaman)
            
            # Değer hücrelerini ortala
            item_val.setTextAlignment(Qt.AlignCenter)
            item_time.setTextAlignment(Qt.AlignCenter)

            self.tablo.setItem(row_idx, 0, item_node)
            self.tablo.setItem(row_idx, 1, item_val)
            self.tablo.setItem(row_idx, 2, item_time)
            
            self.etiket_satirlari[node_id] = row_idx
        else:
            # Etiket zaten varsa sadece Değer ve Zaman hücrelerini güncelle
            row_idx = self.etiket_satirlari[node_id]
            self.tablo.item(row_idx, 1).setText(deger)
            self.tablo.item(row_idx, 2).setText(zaman)

    def closeEvent(self, event):
        if self.worker and self.worker.isRunning():
            self._worker_baglantilari_kes(self.worker)
            self.worker.durdur()
            self.worker.wait(3000)
        event.accept()

if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setStyleSheet(GLOBAL_STYLESHEET)
    
    pencere = ClientApp()
    pencere.show()
    sys.exit(app.exec_())