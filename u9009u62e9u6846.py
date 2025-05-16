import os
import sys
import time
from PyQt5.QtCore import Qt, QRect, QPoint, QSize, pyqtSignal
from PyQt5.QtWidgets import QApplication, QWidget, QLabel, QRubberBand, QDesktopWidget
from PyQt5.QtGui import QCursor, QColor, QPainter, QPen, QBrush, QFont

class TransparentSelectionBox(QWidget):
    """u900fu660eu9009u62e9u6846uff0cu7528u4e8eu9009u62e9u5c4fu5e55u4e0au7684u533au57df"""
    
    selection_completed = pyqtSignal(QRect)  # u9009u62e9u5b8cu6210u4fe1u53f7uff0cu53d1u9001u9009u62e9u533au57df
    selection_canceled = pyqtSignal()       # u9009u62e9u53d6u6d88u4fe1u53f7
    
    def __init__(self, parent=None, callback=None):
        """u521du59cbu5316u9009u62e9u6846
        
        u53c2u6570:
            parent: u7236u7a97u53e3
            callback: u9009u62e9u5b8cu6210u56deu8c03u51fdu6570
        """
        super().__init__(parent)
        # u4fddu5b58u56deu8c03u51fdu6570
        self.callback = callback
        
        # u521du59cbu5316u7a97u53e3u8bbeu7f6e
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_DeleteOnClose)
        
        # u9009u62e9u6846u53d8u91cf
        self.rubberBand = QRubberBand(QRubberBand.Rectangle, self)
        self.origin = QPoint()
        self.current_rect = QRect()
        
        # u6307u5357u6807u7b7e
        self.guide_label = QLabel(self)
        self.guide_label.setStyleSheet(
            "background-color: rgba(0, 0, 0, 120); color: white; padding: 10px; border-radius: 5px;"
        )
        self.guide_label.setFont(QFont("Arial", 10, QFont.Bold))
        self.guide_label.setText(
            "u9009u62e9u8840u6761u533au57df:\n" 
            "1. u6309u4f4fu5de6u952eu5e76u62d6u52a8u9009u62e9u533au57df\n" 
            "2. u91cau653eu9f20u6807u5b8cu6210u9009u62e9\n" 
            "3. u6309ESCu53d6u6d88u9009u62e9"
        )
        self.guide_label.setFixedSize(250, 80)
        
        # u6307u793au5668u6807u7b7euff0cu663eu793au5f53u524du533au57dfu4fe1u606f
        self.indicator_label = QLabel(self)
        self.indicator_label.setStyleSheet(
            "background-color: rgba(0, 0, 0, 150); color: white; padding: 5px; border-radius: 3px;"
        )
        self.indicator_label.setFont(QFont("Arial", 9))
        self.indicator_label.setFixedSize(150, 20)
        self.indicator_label.hide()  # u521du59cbu65f6u9690u85cf
        
        # u8fdeu63a5u4fe1u53f7
        self.selection_completed.connect(self.on_selection_completed)
        self.selection_canceled.connect(self.on_selection_canceled)
        
        # u4f7fu7528u5f53u524du5c4fu5e55u5c3au5bf8
        self.showFullScreen()
    
    def keyPressEvent(self, event):
        """u6309u952eu4e8bu4ef6u5904u7406"""
        # u5982u679cu6309u4e0bESCu952euff0cu53d6u6d88u9009u62e9
        if event.key() == Qt.Key_Escape:
            self.selection_canceled.emit()
            self.close()
    
    def mousePressEvent(self, event):
        """u9f20u6807u6309u4e0bu4e8bu4ef6u5904u7406"""
        if event.button() == Qt.LeftButton:
            self.origin = event.pos()
            self.rubberBand.setGeometry(QRect(self.origin, QSize()))
            self.rubberBand.show()
    
    def mouseMoveEvent(self, event):
        """u9f20u6807u79fbu52a8u4e8bu4ef6u5904u7406"""
        if not self.origin.isNull():
            # u66f4u65b0u6a61u76aeu7b4bu5f62u72b6
            self.current_rect = QRect(self.origin, event.pos()).normalized()
            self.rubberBand.setGeometry(self.current_rect)
            
            # u66f4u65b0u6307u793au5668u6587u672c
            rect_text = f"Position: ({self.current_rect.x()}, {self.current_rect.y()}) Size: {self.current_rect.width()} x {self.current_rect.height()}"
            self.indicator_label.setText(rect_text)
            
            # u663eu793au6307u793au5668u5e76u79fbu52a8u5230u9f20u6807u4f4du7f6eu9644u8fd1
            indicator_pos = event.pos() + QPoint(10, 10)
            self.indicator_label.move(indicator_pos)
            self.indicator_label.show()
            
            # u79fbu52a8u6307u5357u6807u7b7eu5230u5c4fu5e55u53f3u4e0au89d2
            screen_geometry = QDesktopWidget().screenGeometry()
            self.guide_label.move(screen_geometry.width() - self.guide_label.width() - 20, 20)
    
    def mouseReleaseEvent(self, event):
        """u9f20u6807u91cau653eu4e8bu4ef6u5904u7406"""
        if event.button() == Qt.LeftButton and not self.origin.isNull():
            # u83b7u53d6u6700u7ec8u9009u62e9u533au57df
            self.rubberBand.hide()
            self.indicator_label.hide()
            
            # u4ec5u5f53u533au57dfu8db3u591fu5927u65f6u624du53d1u9001u5b8cu6210u4fe1u53f7
            if self.current_rect.width() > 5 and self.current_rect.height() > 5:
                self.selection_completed.emit(self.current_rect)
            else:
                # u533au57dfu592au5c0fuff0cu91cdu7f6eu9009u62e9
                self.origin = QPoint()
    
    def paintEvent(self, event):
        """u7ed8u5236u534au900fu660eu906eu7f69u5c42"""
        painter = QPainter(self)
        painter.setOpacity(0.2)  # u8bbeu7f6eu534au900fu660eu5ea6
        painter.setBrush(QBrush(QColor(0, 0, 0)))
        painter.setPen(Qt.NoPen)
        painter.drawRect(0, 0, self.width(), self.height())
    
    def on_selection_completed(self, rect):
        """u5904u7406u9009u62e9u5b8cu6210u4fe1u53f7"""
        if self.callback:
            # u6267u884cu56deu8c03uff0cu4f20u5165u9009u62e9u533au57df
            self.callback(rect)
        self.close()  # u5173u95edu9009u62e9u6846
    
    def on_selection_canceled(self):
        """u5904u7406u9009u62e9u53d6u6d88u4fe1u53f7"""
        if self.callback:
            # u6267u884cu56deu8c03uff0cu4f20u5165Noneu8868u793au53d6u6d88
            self.callback(None)
        self.close()  # u5173u95edu9009u62e9u6846

def show_selection_box(callback=None):
    """u663eu793au9009u62e9u6846u7a97u53e3
    
    u53c2u6570:
        callback: u9009u62e9u5b8cu6210u540eu7684u56deu8c03u51fdu6570uff0cu63a5u6536u4e00u4e2aQRectu53c2u6570u6216Noneuff08u5982u679cu53d6u6d88uff09
        
    u8fd4u56de:
        bool: u662fu5426u6210u529fu663eu793au9009u62e9u6846
    """
    try:
        # u786eu4fddu5b58u5728QApplicationu5b9eu4f8b
        app = QApplication.instance()
        if app is None:
            app = QApplication(sys.argv)
        
        # u521bu5efau5e76u663eu793au9009u62e9u6846
        selection_box = TransparentSelectionBox(None, callback)
        selection_box.show()
        
        return True
    except Exception as e:
        print(f"u663eu793au9009u62e9u6846u65f6u51fau9519: {str(e)}")
        return False

# u6d4bu8bd5u4ee3u7801
if __name__ == "__main__":
    app = QApplication(sys.argv)
    
    def test_callback(rect):
        if rect:
            print(f"Selected area: ({rect.x()}, {rect.y()}, {rect.width()} x {rect.height()})")
        else:
            print("Selection canceled")
    
    show_selection_box(test_callback)
    sys.exit(app.exec_()) 