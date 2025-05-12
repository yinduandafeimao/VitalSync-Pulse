import sys
from PyQt5.QtWidgets import QApplication, QDialog, QLabel
from PyQt5.QtCore import Qt, QPoint, QRect, QSize
from PyQt5.QtGui import QPainter, QColor, QPen, QScreen
from qfluentwidgets import InfoBar, InfoBarPosition, TeachingTip, ToolTipPosition

class FluentSelectionBox(QDialog):
    def __init__(self, parent=None, callback=None):
        super().__init__(parent)
        self.callback = callback
        self.start_point = QPoint()
        self.end_point = QPoint()
        self.dragging = False
        self.selected_rect = None
        self.is_capturing = False  # 标记是否正在截图
        
        # 设置窗口属性
        self.setWindowFlags(
            Qt.FramelessWindowHint  # 无边框
            | Qt.WindowStaysOnTopHint  # 置顶
            | Qt.Tool  # 隐藏任务栏图标
        )
        self.setAttribute(Qt.WA_TranslucentBackground)  # 透明背景
        self.setWindowModality(Qt.ApplicationModal)  # 应用模态
        
        # 获取屏幕尺寸并设置全屏
        self.screen_rect = QApplication.primaryScreen().geometry()
        self.setGeometry(self.screen_rect)
        
        # 添加指导标签
        self.instruction_label = QLabel(self)
        self.instruction_label.setStyleSheet(
            "background-color: rgba(0, 0, 0, 150); color: white; padding: 10px; border-radius: 5px;"
        )
        self.instruction_label.setAlignment(Qt.AlignCenter)
        self.instruction_label.move(20, 20)
        self.showInstructions("请拖动鼠标选择区域，按Enter确认，按ESC取消")

    def showInstructions(self, text):
        """显示操作指导提示"""
        self.instruction_label.setText(text)
        self.instruction_label.adjustSize()
        self.instruction_label.show()
    
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.start_point = event.pos()
            self.end_point = self.start_point
            self.dragging = True
            self.update()

    def mouseMoveEvent(self, event):
        if self.dragging:
            self.end_point = event.pos()
            self.update()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton and self.dragging:
            self.dragging = False
            self.selected_rect = self.getSelectedRect()
            
            # 显示选择的坐标信息
            if self.selected_rect.isValid() and self.selected_rect.width() > 5 and self.selected_rect.height() > 5:
                rect_info = f"位置: ({self.selected_rect.x()}, {self.selected_rect.y()}), " \
                           f"大小: {self.selected_rect.width()}x{self.selected_rect.height()}"
                self.showInstructions(f"已选择区域: {rect_info}\n按Enter确认，按ESC取消")
            
            self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        
        # 设置半透明背景
        painter.fillRect(self.rect(), QColor(0, 0, 0, 50))
        
        # 如果有选择区域，绘制选择框
        if self.selected_rect and self.selected_rect.isValid():
            # 清除选择区域的半透明背景
            painter.save()
            eraser = QPainter(self)
            eraser.setCompositionMode(QPainter.CompositionMode_Clear)
            eraser.fillRect(self.selected_rect, Qt.transparent)
            painter.restore()
            
            # 绘制边框，只在非截图模式下显示
            if not self.is_capturing:
                # 绿色边框
                pen = QPen(QColor(0, 168, 174))  # 使用和VitalSync相同的青绿色
                pen.setWidth(2)
                painter.setPen(pen)
                painter.drawRect(self.selected_rect.adjusted(-2, -2, 2, 2))
                
                # 在四角绘制控制点
                control_points = [
                    QRect(self.selected_rect.left()-4, self.selected_rect.top()-4, 8, 8),
                    QRect(self.selected_rect.right()-4, self.selected_rect.top()-4, 8, 8),
                    QRect(self.selected_rect.left()-4, self.selected_rect.bottom()-4, 8, 8),
                    QRect(self.selected_rect.right()-4, self.selected_rect.bottom()-4, 8, 8)
                ]
                
                painter.setBrush(QColor(0, 168, 174))
                for point in control_points:
                    painter.drawRect(point)
        
        # 如果正在拖动，绘制选择框
        elif self.dragging:
            temp_rect = self.getSelectedRect()
            if temp_rect.isValid():
                # 绘制虚线边框和半透明背景
                painter.setPen(QPen(QColor(255, 255, 255), 1, Qt.DashLine))
                painter.setBrush(QColor(255, 255, 255, 30))
                painter.drawRect(temp_rect)
                
                # 显示尺寸信息
                size_text = f"{temp_rect.width()} x {temp_rect.height()}"
                painter.setPen(Qt.white)
                painter.drawText(temp_rect.center(), size_text)

    def getSelectedRect(self):
        """获取选择的矩形区域(处理反向拖动)"""
        return QRect(
            min(self.start_point.x(), self.end_point.x()),
            min(self.start_point.y(), self.end_point.y()),
            abs(self.start_point.x() - self.end_point.x()),
            abs(self.start_point.y() - self.end_point.y())
        )
    
    def getSelectedImage(self):
        """获取选择区域的截图"""
        if not self.selected_rect or not self.selected_rect.isValid():
            return None
            
        try:
            # 标记开始截图
            self.is_capturing = True
            self.update()  # 刷新显示，隐藏边框
            
            # 等待重绘完成
            QApplication.processEvents()
            
            # 截取选定区域
            screen = QApplication.primaryScreen()
            screenshot = screen.grabWindow(
                0, 
                self.selected_rect.x(), 
                self.selected_rect.y(), 
                self.selected_rect.width(), 
                self.selected_rect.height()
            )
            
            # 转换为numpy数组
            image = screenshot.toImage()
            buffer = image.bits().tobytes()
            
            import numpy as np
            import cv2
            img_array = np.frombuffer(buffer, dtype=np.uint8).reshape(
                (image.height(), image.width(), 4))
            img_array = cv2.cvtColor(img_array, cv2.COLOR_BGRA2BGR)
            
            # 恢复显示边框
            self.is_capturing = False
            self.update()
            
            return img_array
        except Exception as e:
            print(f"截图失败: {str(e)}")
            self.is_capturing = False
            self.update()
            return None
    
    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Return or event.key() == Qt.Key_Enter:
            # 确认选择
            if self.selected_rect and self.selected_rect.width() > 5 and self.selected_rect.height() > 5:
                # 调用回调函数
                if self.callback:
                    self.callback(self.selected_rect)
                self.accept()
        elif event.key() == Qt.Key_Escape:
            # 取消选择
            self.reject()

def show_selection_box(callback=None):
    """创建并显示选择框
    
    参数:
        callback: 选择完成后的回调函数，接收一个QRect参数
        
    返回:
        如果用户按下Enter确认，返回True；如果按下ESC取消，返回False
    """
    # 确保已经有QApplication实例
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
        is_new_app = True
    else:
        is_new_app = False
        
    # 创建选择框
    selection_box = FluentSelectionBox(callback=callback)
    result = selection_box.exec_()
    
    # 如果是新创建的QApplication，退出它
    if is_new_app:
        app.quit()
        
    return result == QDialog.Accepted

# 为了兼容性，保留原来的名称
TransparentSelectionBox = FluentSelectionBox

if __name__ == "__main__":
    app = QApplication(sys.argv)
    
    # 示例: 定义回调函数
    def on_selection(rect: QRect):
        print(f"起始坐标: ({rect.x()}, {rect.y()})")
        print(f"结束坐标: ({rect.x() + rect.width()}, {rect.y() + rect.height()})")

    
    window = FluentSelectionBox(callback=on_selection)
    window.show() # 显示窗口    
    sys.exit(app.exec()) # 确保程序不会退出