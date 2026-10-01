# -*- coding: utf-8 -*-
"""
TÜBİTAK 2209-B Saha İstasyonu ve Simülatör
Modül: Ticari Lisans Uyumlu Qt Katmanı (Qt Compatibility Layer)

Öncelikli olarak LGPL v3 lisanslı PySide6 veya PySide2'yi yükler;
böylece ticari ve kapalı kaynaklı dağıtımlarda GPL copyleft zorunluluğu
veya ticari PyQt lisanslama maliyeti ortadan kalkar.
"""

import sys

QT_BINDING = None

# 1. Öncelik: PySide6 (LGPL v3 - Ticari / Closed Source Uyumlu)
try:
    import PySide6.QtCore as QtCore
    import PySide6.QtGui as QtGui
    import PySide6.QtWidgets as QtWidgets
    from PySide6.QtCore import Qt, QTimer, Signal as pyqtSignal, Slot as pyqtSlot, QThread, QObject
    from PySide6.QtWidgets import QMessageBox, QDialog
    QT_BINDING = "PySide6"
except ImportError:
    # 2. Öncelik: PySide2 (LGPL v3)
    try:
        import PySide2.QtCore as QtCore
        import PySide2.QtGui as QtGui
        import PySide2.QtWidgets as QtWidgets
        from PySide2.QtCore import Qt, QTimer, Signal as pyqtSignal, Slot as pyqtSlot, QThread, QObject
        from PySide2.QtWidgets import QMessageBox, QDialog
        QT_BINDING = "PySide2"
    except ImportError:
        # 3. Öncelik: PyQt5 (Mevcut sistemlerde geri uyumluluk)
        try:
            import PyQt5.QtCore as QtCore
            import PyQt5.QtGui as QtGui
            import PyQt5.QtWidgets as QtWidgets
            from PyQt5.QtCore import Qt, QTimer, pyqtSignal, pyqtSlot, QThread, QObject
            from PyQt5.QtWidgets import QMessageBox, QDialog
            QT_BINDING = "PyQt5"
        except ImportError:
            raise ImportError(
                "Sistemde ne PySide6 ne de PyQt5 bulundu! Lütfen pip install PySide6 komutu ile kurun."
            )
