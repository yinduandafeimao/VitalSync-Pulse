import sys
import os
import pygame
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QApplication
from PyQt5.QtGui import QFont
from qfluentwidgets import setTheme, Theme, FluentIcon as FIF

# 添加错误处理
try:
    from mainwindow import MainWindow
except ImportError as e:
    print(f"导入错误: {str(e)}")
    print("请检查导入依赖是否正确安装")
    sys.exit(1)
except Exception as e:
    print(f"未知错误: {str(e)}")
    sys.exit(1)

# 设置全局样式
GLOBAL_STYLE = """
QWidget {
    font-family: "Microsoft YaHei", sans-serif;
}

QFrame#cardFrame {
    border: 1px solid rgba(0, 0, 0, 0.1);
    border-radius: 10px;
    background-color: rgba(255, 255, 255, 0.95);
}

QLabel {
    font-size: 13px;
    color: #333333;
}

QPushButton {
    padding: 8px 16px;
    border-radius: 6px;
    font-weight: 500;
}

QLineEdit {
    padding: 8px;
    border-radius: 5px;
    border: 1px solid #e0e0e0;
    background-color: #fafafa;
}

QComboBox {
    padding: 8px;
    border-radius: 5px;
    border: 1px solid #e0e0e0;
    background-color: #fafafa;
}
"""

def main():
    # 设置高DPI支持
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
    
    app = QApplication(sys.argv)
    
    # 设置全局样式
    app.setStyleSheet(GLOBAL_STYLE)
    
    # 设置字体
    font = QFont("Microsoft YaHei UI", 9)
    app.setFont(font)
    
    # 设置主题
    setTheme(Theme.AUTO)
    
    try:
        # 创建主窗口
        window = MainWindow()
        window.show()
        
        exit_code = app.exec_()
    except Exception as e:
        print(f"程序运行出错: {str(e)}")
        exit_code = 1
    finally:
        # 确保pygame在退出时正确清理
        pygame.quit()

    sys.exit(exit_code)

if __name__ == "__main__":
    main() 