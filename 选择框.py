import sys
import numpy as np
import cv2
from typing import Callable, Optional
from PySide6.QtWidgets import QApplication, QWidget, QDialog, QLabel
from PySide6.QtCore import Qt, QPoint, QRect, QEventLoop
from PySide6.QtGui import QPainter, QColor, QPen, QScreen, QKeyEvent

class TransparentSelectionBox(QDialog):
    def __init__(self, on_selection_complete: Optional[Callable[[QRect], None]] = None):
        super().__init__()
        self.initUI()
        self.start_point = QPoint()
        self.end_point = QPoint()
        self.dragging = False
        self.on_selection_complete = on_selection_complete
        self.selected_rect = None
        self.is_capturing = False  # 添加截图状态标志
        # 设置为应用程序级别的模态对话框，防止干扰其他操作
        self.setWindowModality(Qt.ApplicationModal)

    def initUI(self):
        # 设置窗口属性
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint  # 无边框
            | Qt.WindowType.WindowStaysOnTopHint  # 置顶
            | Qt.WindowType.Tool  # 隐藏任务栏图标
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)  # 透明背景
        self.setWindowState(Qt.WindowState.WindowFullScreen)  # 全屏覆盖
        
        # 获取主屏幕尺寸
        screen = QApplication.primaryScreen()
        self.screen_rect = screen.geometry()
        self.setGeometry(self.screen_rect)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.start_point = event.position().toPoint()
            self.end_point = self.start_point
            self.dragging = True
            self.update()

    def mouseMoveEvent(self, event):
        if self.dragging:
            self.end_point = event.position().toPoint()
            self.update()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.dragging = False
            self.selected_rect = self.get_selected_rect()
            self.update()
            
            # 按Enter键确认才能完成选择
            # 这里只记录选择区域，但不关闭窗口

    def paintEvent(self, event):
        """绘制选择框
        
        使用半透明背景和边框绘制选择框。
        使用两个不同的矩形：一个用于显示，一个用于截图。
        """
        painter = QPainter(self)
        
        # 设置半透明背景
        painter.fillRect(self.rect(), QColor(0, 0, 0, 50))
        
        # 如果有选择区域，则绘制选择框和清除选择框内的半透明背景
        if self.selected_rect and self.selected_rect.isValid():
            # 保存绘图状态
            painter.save()
            
            # 设置选择区域为透明
            eraser = QPainter(self)
            eraser.setCompositionMode(QPainter.CompositionMode_Clear)
            eraser.fillRect(self.selected_rect, Qt.transparent)
            
            # 恢复绘图状态
            painter.restore()
            
            # 绘制边框 - 仅在界面显示时
            if not self.dragging:
                # 使用更细的边框，设置为2像素宽
                pen = QPen(QColor(0, 255, 0))  # 绿色边框
                pen.setWidth(2)
                painter.setPen(pen)
                # 绘制边框在选择区域外侧，不会影响截图内容
                painter.drawRect(self.selected_rect.adjusted(-2, -2, 2, 2))
        
        # 如果正在拖动，绘制当前选择框
        elif self.dragging:
            temp_rect = self.get_selected_rect()
            painter.setPen(QPen(QColor(255, 255, 255), 2, Qt.DashLine))  # 白色虚线边框
            painter.setBrush(QColor(255, 255, 255, 30))  # 半透明填充
            painter.drawRect(temp_rect)

    def get_selected_rect(self):
        # 确保矩形坐标正确(处理反向拖动)
        return QRect(
            min(self.start_point.x(), self.end_point.x()),
            min(self.start_point.y(), self.end_point.y()),
            abs(self.start_point.x() - self.end_point.x()),
            abs(self.start_point.y() - self.end_point.y())
        )
        
    def get_selected_image(self):
        """获取选择区域的截图, 返回numpy数组格式的图像
        
        Returns:
            numpy.ndarray: 选择区域的截图, 如果截图失败则返回None
        """
        try:
            # 获取选择区域
            rect = self.get_selected_rect()
            if rect.width() <= 0 or rect.height() <= 0:
                print("错误: 选择区域无效")
                return None
                
            # 截取选定区域的截图
            screen = QApplication.primaryScreen()
            screenshot = screen.grabWindow(0, rect.x(), rect.y(), rect.width(), rect.height())
            
            # 检查截图是否有效
            if screenshot.isNull():
                print("错误: 截图获取失败")
                return None
                
            # 将QPixmap转换为numpy数组
            image = screenshot.toImage()
            buffer = image.bits().tobytes()
            import numpy as np
            img_array = np.frombuffer(buffer, dtype=np.uint8).reshape(
                (image.height(), image.width(), 4))
            
            # 转换为BGR格式(OpenCV格式)
            import cv2
            img_array = cv2.cvtColor(img_array, cv2.COLOR_BGRA2BGR)
            
            return img_array
            
        except Exception as e:
            print(f"获取截图时出错: {str(e)}")
            return None
        
    def keyPressEvent(self, event: QKeyEvent):
        if event.key() == Qt.Key.Key_Return or event.key() == Qt.Key.Key_Enter:
            # 按Enter确认选择
            if self.selected_rect and self.selected_rect.width() > 5 and self.selected_rect.height() > 5:
                if self.on_selection_complete:
                    self.on_selection_complete(self.selected_rect)
                self.accept()  # 使用accept来正确关闭对话框
        elif event.key() == Qt.Key.Key_Escape:
            # 按ESC取消选择
            self.reject()  # 使用reject来取消对话框
            
    def set_instruction_text(self, text):
        """设置指导文本"""
        if hasattr(self, 'instruction_label'):
            self.instruction_label.setText(text)
        else:
            # 创建指导标签
            self.instruction_label = QLabel(text, self)
            self.instruction_label.setStyleSheet("color: white; background-color: rgba(0, 0, 0, 150);")
            self.instruction_label.setAlignment(Qt.AlignCenter)
            self.instruction_label.move(10, 10)
            self.instruction_label.adjustSize()
            self.instruction_label.show()

    def start_capture(self):
        """开始截图模式，暂时隐藏边框"""
        self.is_capturing = True
        self.update()
    
    def end_capture(self):
        """结束截图模式，恢复边框显示"""
        self.is_capturing = False
        self.update()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    
    # 示例: 定义回调函数
    def on_selection(rect: QRect):
        print(f"起始坐标: ({rect.x()}, {rect.y()})")
        print(f"结束坐标: ({rect.x() + rect.width()}, {rect.y() + rect.height()})")

    
    window = TransparentSelectionBox(on_selection)
    window.show() # 显示窗口    
    sys.exit(app.exec()) # 确保程序不会退出