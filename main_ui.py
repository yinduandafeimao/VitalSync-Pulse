import sys
import os
import importlib.util
import json
import cv2
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTabWidget, QPushButton, QLabel, QFrame, QScrollArea,
    QFileDialog, QDialog, QGridLayout, QSlider, QSpinBox, QLineEdit,
    QCheckBox, QDoubleSpinBox, QListWidget, QListWidgetItem, QMessageBox, QColorDialog, QInputDialog  # 添加所需控件
)
from PySide6.QtCore import Qt, QTimer, QByteArray, QBuffer, QIODevice, QPoint, QSize
from PySide6.QtGui import QPixmap, QImage, QIcon, QMouseEvent
import numpy as np
try:
    import qtawesome as qta  # 尝试导入qtawesome用于图标
except ImportError:
    # 如果没有安装qtawesome，提供一个空的替代接口
    class QtaReplacement:
        def icon(self, *args, **kwargs):
            return QIcon()
    
    qta = QtaReplacement()

# 动态导入带空格的模块
module_name = "team_members(choice box)"
module_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "team_members(choice box).py")
spec = importlib.util.spec_from_file_location(module_name, module_path)
team_members_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(team_members_module)

# 从模块中获取需要的类
TeamMember = team_members_module.TeamMember
Team = team_members_module.Team
from teammate_recognition import TeammateRecognition, RecognitionUI # 添加 RecognitionUI 导入
from health_monitor import HealthMonitor
from health_bar_calibration import CalibrationDialog

class MainWindow(QMainWindow):
    def __init__(self):
        """初始化主窗口"""
        super().__init__()
        
        # 设置窗口标题和大小
        self.setWindowTitle('VitalSync Pulse')
        self.setGeometry(100, 100, 960, 700)
        
        # 设置无边框窗口和透明背景
        self.setWindowFlag(Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        
        # 设置背景样式
        # 使用渐变背景替代图片背景，更现代的设计
        self.setStyleSheet("""
            QMainWindow {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, 
                    stop:0 #E0F7FA, stop:0.5 #B3E5FC, stop:1 #81D4FA);
                border-radius: 20px;
                border: 1px solid rgba(255, 255, 255, 150);
            }
        """)
        
        # 定义通用样式
        self.frame_style = """
            QFrame {
                background: rgba(255, 255, 255, 0.8);
                border-radius: 15px;
                padding: 10px;
                border: 1px solid rgba(52, 152, 219, 0.3);
            }
        """
        
        self.title_style = """
            QLabel {
                font-weight: bold; 
                font-size: 14px; 
                color: #2C3E50;
                margin-bottom: 5px;
            }
        """
        
        # 窗口拖动功能
        self._drag_pos = None
        
        # 创建中央部件和主布局
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(10, 10, 10, 10)
        
        # 创建自定义标题栏
        self.create_title_bar(main_layout)
        
        # 创建标签页控件
        self.tab_widget = QTabWidget()
        self.tab_widget.setStyleSheet("""
            QTabWidget::pane {
                background: rgba(255, 255, 255, 0.9);
                border-radius: 15px;
                border: none;
            }
            QTabBar::tab {
                background: qlineargradient(x1:0, y1:0, x1:1, y1:0, 
                    stop:0 #2C3E50, stop:1 #3498DB);
                color: white;
                padding: 8px 12px;
                margin-right: 4px;
                border-top-left-radius: 8px;
                border-top-right-radius: 8px;
            }
            QTabBar::tab:selected {
                background: qlineargradient(x1:0, y1:0, x1:1, y1:0, 
                    stop:0 #1A5276, stop:1 #2980B9);
                font-weight: bold;
            }
            QTabBar::tab:hover:!selected {
                background: qlineargradient(x1:0, y1:0, x1:1, y1:0, 
                    stop:0 #34495E, stop:1 #5DADE2);
            }
        """)
        main_layout.addWidget(self.tab_widget)
        
        # 创建队伍对象
        self.team = Team()
        
        # 初始化组件
        self.recognition = TeammateRecognition()
        self.health_monitor = HealthMonitor(self.team)
        
        # 创建结果显示标签
        self.result_label = None
        self.monitor_result_label = None
        
        # 确保 health_monitor 已完全初始化并加载了配置
        QApplication.processEvents()
        
        # 创建不同功能的标签页
        self.create_tabs()
        
        # 添加结果显示区域
        if self.result_label is None:
            self.result_label = QLabel('准备就绪')
            self.result_label.setWordWrap(True)  # 允许文本自动换行
            self.result_label.setMinimumHeight(100)
            self.result_label.setStyleSheet("""
                QLabel {
                    background: rgba(255, 255, 255, 0.8);
                    border-radius: 10px;
                    padding: 10px;
                    color: #2C3E50;
                }
            """)
            main_layout.addWidget(self.result_label)
        
        # 尝试加载已存在的队友配置
        self.load_teammate_configs()
        
        # 在__init__方法中调用职业图标加载
        self.profession_icons = {}  # 用于存储职业图标
        self.load_profession_icons()
        
        # 设置整体样式
        self.setStyleSheet("""
            QMainWindow {
                background: transparent;
            }
            QWidget {
                font-family: "微软雅黑", Arial, sans-serif;
                font-size: 13px;
            }
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x1:1, y1:0, 
                    stop:0 #2C3E50, stop:1 #3498DB);
                color: white;
                padding: 8px 12px;
                border-radius: 8px;
                border: none;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x1:1, y1:0, 
                    stop:0 #34495E, stop:1 #5DADE2);
            }
            QPushButton:pressed {
                background: qlineargradient(x1:0, y1:0, x1:1, y1:0, 
                    stop:0 #1A5276, stop:1 #2980B9);
            }
            QFrame {
                background: rgba(255, 255, 255, 0.8);
                border-radius: 15px;
                padding: 5px;
            }
            QLabel {
                color: #2C3E50;
            }
            QSpinBox, QDoubleSpinBox, QLineEdit {
                border-radius: 5px;
                padding: 5px;
                border: 1px solid #BDC3C7;
            }
            QCheckBox {
                color: #2C3E50;
            }
            QSlider::groove:horizontal {
                height: 8px;
                background: #D6EAF8;
                border-radius: 4px;
            }
            QSlider::handle:horizontal {
                background: #3498DB;
                border: 1px solid #2C3E50;
                width: 18px;
                margin: -5px 0;
                border-radius: 9px;
            }
        """)
    
    def create_title_bar(self, main_layout):
        """创建自定义标题栏"""
        title_bar = QWidget()
        title_bar.setFixedHeight(50)
        title_bar.setStyleSheet("""
            QWidget {
                background: qlineargradient(x1:0, y1:0, x1:1, y1:0, 
                    stop:0 #2C3E50, stop:1 #3498DB);
                border-radius: 15px;
            }
        """)
        
        title_layout = QHBoxLayout(title_bar)
        title_layout.setContentsMargins(10, 0, 10, 0)
        
        # 添加标题和图标
        title_label = QLabel("VitalSync Pulse")
        title_label.setStyleSheet("""
            QLabel {
                color: white;
                font-size: 18px;
                font-weight: bold;
            }
        """)
        
        # 添加窗口控制按钮
        btn_min = QPushButton("", self)
        btn_min.setIcon(qta.icon('fa5s.window-minimize', color='white'))
        btn_max = QPushButton("", self)
        btn_max.setIcon(qta.icon('fa5s.window-maximize', color='white'))
        btn_close = QPushButton("", self)
        btn_close.setIcon(qta.icon('fa5s.times', color='white'))
        
        # 设置按钮样式
        control_btn_style = """
            QPushButton {
                background: transparent;
                border: none;
                width: 30px;
                height: 30px;
                border-radius: 15px;
            }
            QPushButton:hover {
                background: rgba(255, 255, 255, 0.1);
            }
        """
        
        btn_close_style = """
            QPushButton {
                background: transparent;
                border: none;
                width: 30px;
                height: 30px;
                border-radius: 15px;
            }
            QPushButton:hover {
                background: rgba(255, 0, 0, 0.5);
            }
        """
        
        btn_min.setStyleSheet(control_btn_style)
        btn_max.setStyleSheet(control_btn_style)
        btn_close.setStyleSheet(btn_close_style)
        
        # 连接按钮信号
        btn_min.clicked.connect(self.showMinimized)
        btn_max.clicked.connect(self.toggle_maximize)
        btn_close.clicked.connect(self.close)
        
        # 设置工具提示
        btn_min.setToolTip("最小化")
        btn_max.setToolTip("最大化")
        btn_close.setToolTip("关闭")
        
        # 添加各元素到标题栏布局
        title_layout.addWidget(title_label)
        title_layout.addStretch()  # 弹性空间
        title_layout.addWidget(btn_min)
        title_layout.addWidget(btn_max)
        title_layout.addWidget(btn_close)
        
        # 将标题栏添加到主布局
        main_layout.addWidget(title_bar)
    
    def toggle_maximize(self):
        if self.isMaximized():
            self.showNormal()
        else:
            self.showMaximized()
    
    # 窗口拖动事件处理
    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()
    
    def mouseMoveEvent(self, event: QMouseEvent):
        if event.buttons() == Qt.LeftButton and self._drag_pos:
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()
    
    def mouseReleaseEvent(self, event: QMouseEvent):
        self._drag_pos = None
        event.accept()
    
    def create_tabs(self):
        """创建不同功能的标签页"""
        # 创建队员识别配置标签页
        recognition_tab = self.create_recognition_tab()
        self.tab_widget.addTab(recognition_tab, '队员识别配置')
        
        # 创建血条监控标签页
        monitoring_tab = self.create_monitoring_tab()
        self.tab_widget.addTab(monitoring_tab, '血条监控')
        
        # 创建设置与控制标签页
        settings_tab = self.create_settings_tab()
        self.tab_widget.addTab(settings_tab, '设置与控制')
    
    def create_recognition_tab(self):
        """创建队员识别配置标签页"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setSpacing(10)
        
        # 添加职业图标管理区域
        icon_group = QFrame()
        icon_group.setFrameStyle(QFrame.StyledPanel)
        icon_group.setStyleSheet(self.frame_style)
        icon_layout = QVBoxLayout(icon_group)
        
        icon_title = QLabel('职业图标管理')
        icon_title.setStyleSheet(self.title_style)
        icon_layout.addWidget(icon_title)
        
        icon_buttons = QHBoxLayout()
        add_icon_btn = QPushButton('添加职业图标')
        add_icon_btn.setIcon(qta.icon('fa5s.plus-circle', color='white'))
        view_icons_btn = QPushButton('查看已有图标')
        view_icons_btn.setIcon(qta.icon('fa5s.eye', color='white'))
        icon_buttons.addWidget(add_icon_btn)
        icon_buttons.addWidget(view_icons_btn)
        icon_layout.addLayout(icon_buttons)
        
        # 连接按钮信号
        add_icon_btn.clicked.connect(self.add_profession_icon)
        view_icons_btn.clicked.connect(self.view_profession_icons)
        
        layout.addWidget(icon_group)
        
        # 添加队员识别区域
        recognition_group = QFrame()
        recognition_group.setFrameStyle(QFrame.StyledPanel)
        recognition_group.setStyleSheet(self.frame_style)
        recognition_layout = QVBoxLayout(recognition_group)
        
        recognition_title = QLabel('队员识别')
        recognition_title.setStyleSheet(self.title_style)
        recognition_layout.addWidget(recognition_title)
        
        # 添加图像质量设置区域
        quality_layout = QHBoxLayout()
        quality_label = QLabel('图像质量设置:')
        quality_layout.addWidget(quality_label)
        
        # 对比度设置
        contrast_label = QLabel('对比度:')
        self.contrast_slider = QSlider(Qt.Horizontal)
        self.contrast_slider.setMinimum(10)
        self.contrast_slider.setMaximum(20)
        self.contrast_slider.setValue(12)  # 默认值1.2
        self.contrast_slider.setToolTip('调整图像对比度，提高识别精度')
        quality_layout.addWidget(contrast_label)
        quality_layout.addWidget(self.contrast_slider)
        
        # 亮度设置
        brightness_label = QLabel('亮度:')
        self.brightness_slider = QSlider(Qt.Horizontal)
        self.brightness_slider.setMinimum(0)
        self.brightness_slider.setMaximum(30)
        self.brightness_slider.setValue(10)  # 默认值10
        self.brightness_slider.setToolTip('调整图像亮度，提高识别精度')
        quality_layout.addWidget(brightness_label)
        quality_layout.addWidget(self.brightness_slider)
        
        # 采样次数设置
        samples_label = QLabel('采样次数:')
        self.samples_spinner = QSpinBox()
        self.samples_spinner.setMinimum(1)
        self.samples_spinner.setMaximum(5)
        self.samples_spinner.setValue(3)  # 默认3次采样
        self.samples_spinner.setToolTip('增加采样次数可提高识别准确率，但会降低速度')
        quality_layout.addWidget(samples_label)
        quality_layout.addWidget(self.samples_spinner)
        
        recognition_layout.addLayout(quality_layout)
        
        recognition_buttons = QHBoxLayout()
        select_area_btn = QPushButton('选择识别区域')
        select_area_btn.setIcon(qta.icon('fa5s.crop', color='white'))
        start_recognition_btn = QPushButton('开始识别')
        start_recognition_btn.setIcon(qta.icon('fa5s.play', color='white'))
        load_config_btn = QPushButton('加载队友配置')
        load_config_btn.setIcon(qta.icon('fa5s.file-import', color='white'))
        auto_recognize_btn = QPushButton('一键识别队友')
        auto_recognize_btn.setIcon(qta.icon('fa5s.sliders-h', color='white'))
        auto_recognize_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x1:1, y1:0, 
                    stop:0 #8E44AD, stop:1 #9B59B6);
                font-weight: bold;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x1:1, y1:0, 
                    stop:0 #9B59B6, stop:1 #A569BD);
            }
        """)
        recognition_buttons.addWidget(select_area_btn)
        recognition_buttons.addWidget(start_recognition_btn)
        recognition_buttons.addWidget(load_config_btn)
        recognition_buttons.addWidget(auto_recognize_btn)
        recognition_layout.addLayout(recognition_buttons)
        
        # 连接按钮信号
        select_area_btn.clicked.connect(self.select_recognition_area)
        start_recognition_btn.clicked.connect(self.start_recognition)
        load_config_btn.clicked.connect(self.load_teammate_configs)
        auto_recognize_btn.clicked.connect(self.open_calibration_tool)
        
        layout.addWidget(recognition_group)
        
        # 添加识别结果显示区域
        results_group = QFrame()
        results_group.setFrameStyle(QFrame.StyledPanel)
        results_group.setStyleSheet(self.frame_style)
        results_layout = QVBoxLayout(results_group)
        
        results_title = QLabel('识别结果')
        results_title.setStyleSheet(self.title_style)
        results_layout.addWidget(results_title)
        
        # 创建滚动区域来显示识别结果
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setStyleSheet("""
            QScrollArea {
                border: none;
                background: transparent;
            }
            QScrollBar:vertical {
                border: none;
                background: #D6EAF8;
                width: 10px;
                border-radius: 5px;
            }
            QScrollBar::handle:vertical {
                background: #3498DB;
                min-height: 20px;
                border-radius: 5px;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
        """)
        scroll_widget = QWidget()
        scroll_layout = QVBoxLayout(scroll_widget)
        
        # 添加结果显示标签
        self.result_label = QLabel('等待操作...')
        self.result_label.setWordWrap(True)
        self.result_label.setStyleSheet("""
            QLabel {
                color: #2C3E50;
                background: transparent;
            }
        """)
        scroll_layout.addWidget(self.result_label)
        
        scroll_area.setWidget(scroll_widget)
        results_layout.addWidget(scroll_area)
        
        layout.addWidget(results_group)
        
        return tab
    
    def create_monitoring_tab(self):
        """创建血条监控标签页"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setSpacing(10)
        
        # 添加队员管理区域
        member_group = QFrame()
        member_group.setFrameStyle(QFrame.StyledPanel)
        member_group.setStyleSheet(self.frame_style)
        member_layout = QVBoxLayout(member_group)
        
        member_title = QLabel('队员管理')
        member_title.setStyleSheet(self.title_style)
        member_layout.addWidget(member_title)
        
        member_buttons = QHBoxLayout()
        add_member_btn = QPushButton('添加队员')
        add_member_btn.setIcon(qta.icon('fa5s.user-plus', color='white'))
        remove_member_btn = QPushButton('移除队员')
        remove_member_btn.setIcon(qta.icon('fa5s.user-minus', color='white'))
        
        # 添加"一键移除全部队友"按钮
        remove_all_btn = QPushButton('一键移除全部队友')
        remove_all_btn.setIcon(qta.icon('fa5s.users-slash', color='white'))
        remove_all_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x1:1, y1:0, 
                    stop:0 #E74C3C, stop:1 #C0392B);
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x1:1, y1:0, 
                    stop:0 #C0392B, stop:1 #CD6155);
            }
        """)
        remove_all_btn.setToolTip("一次性移除所有队友")
        remove_all_btn.clicked.connect(self.remove_all_teammates)
        
        # 添加"批量设置血条颜色"按钮
        set_all_colors_btn = QPushButton('批量设置血条颜色')
        set_all_colors_btn.setIcon(qta.icon('fa5s.palette', color='white'))
        set_all_colors_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x1:1, y1:0, 
                    stop:0 #3498DB, stop:1 #2980B9);
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x1:1, y1:0, 
                    stop:0 #2980B9, stop:1 #2E86C1);
            }
        """)
        set_all_colors_btn.setToolTip("一次性为所有队友设置相同的血条颜色范围")
        set_all_colors_btn.clicked.connect(self.set_all_health_bar_colors)
        
        member_buttons.addWidget(add_member_btn)
        member_buttons.addWidget(remove_member_btn)
        member_buttons.addWidget(remove_all_btn)
        member_buttons.addWidget(set_all_colors_btn)  # 添加新按钮
        member_layout.addLayout(member_buttons)
        
        # 连接队员管理按钮信号
        add_member_btn.clicked.connect(self.add_team_member)
        remove_member_btn.clicked.connect(self.remove_team_member)
        
        layout.addWidget(member_group)
        
        # 添加血条设置区域
        health_group = QFrame()
        health_group.setFrameStyle(QFrame.StyledPanel)
        health_group.setStyleSheet(self.frame_style)
        health_layout = QVBoxLayout(health_group)
        
        health_title = QLabel('血条设置')
        health_title.setStyleSheet(self.title_style)
        health_layout.addWidget(health_title)
        
        health_buttons = QHBoxLayout()
        set_position_btn = QPushButton('设置血条位置')
        set_position_btn.setIcon(qta.icon('fa5s.arrows-alt', color='white'))
        set_color_btn = QPushButton('设置血条颜色')
        set_color_btn.setIcon(qta.icon('fa5s.fill-drip', color='white'))
        health_buttons.addWidget(set_position_btn)
        health_buttons.addWidget(set_color_btn)
        health_layout.addLayout(health_buttons)
        
        # 连接血条设置按钮信号
        set_position_btn.clicked.connect(self.set_health_bar_position)
        set_color_btn.clicked.connect(self.set_health_bar_color)
        
        layout.addWidget(health_group)
        
        # 添加监控结果显示区域
        monitor_results_group = QFrame()
        monitor_results_group.setFrameStyle(QFrame.StyledPanel)
        monitor_results_group.setStyleSheet(self.frame_style)
        monitor_results_layout = QVBoxLayout(monitor_results_group)
        
        monitor_results_title = QLabel('监控结果')
        monitor_results_title.setStyleSheet(self.title_style)
        monitor_results_layout.addWidget(monitor_results_title)
        
        # 创建滚动区域来显示监控结果
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setStyleSheet("""
            QScrollArea {
                border: none;
                background: transparent;
            }
            QScrollBar:vertical {
                border: none;
                background: #D6EAF8;
                width: 10px;
                border-radius: 5px;
            }
            QScrollBar::handle:vertical {
                background: #3498DB;
                min-height: 20px;
                border-radius: 5px;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
        """)
        scroll_widget = QWidget()
        scroll_layout = QVBoxLayout(scroll_widget)
        
        # 添加监控结果显示标签
        self.monitor_result_label = QLabel('等待开始监控...')
        self.monitor_result_label.setWordWrap(True)
        self.monitor_result_label.setStyleSheet("""
            QLabel {
                color: #2C3E50;
                background: transparent;
            }
        """)
        scroll_layout.addWidget(self.monitor_result_label)
        
        scroll_area.setWidget(scroll_widget)
        monitor_results_layout.addWidget(scroll_area)
        
        # 连接监控信号
        self.health_monitor.signals.update_signal.connect(self.update_monitor_results)
        self.health_monitor.signals.status_signal.connect(self.update_monitor_status)
        
        layout.addWidget(monitor_results_group)
        
        return tab
    
    def create_settings_tab(self):
        """创建设置与控制标签页"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setSpacing(10)
        
        # 添加快捷键设置区域
        hotkey_group = QFrame()
        hotkey_group.setFrameStyle(QFrame.StyledPanel)
        hotkey_group.setStyleSheet(self.frame_style)
        hotkey_layout = QVBoxLayout(hotkey_group)
        
        hotkey_title = QLabel('快捷键设置')
        hotkey_title.setStyleSheet(self.title_style)
        hotkey_layout.addWidget(hotkey_title)
        
        # 添加说明文本
        hotkey_info = QLabel('设置全局快捷键用于开始和停止监控。按下"记录"按钮后，再按下想要设置的快捷键。')
        hotkey_info.setWordWrap(True)
        hotkey_info.setStyleSheet('color: #7F8C8D;')
        hotkey_layout.addWidget(hotkey_info)
        
        # 开始监控快捷键设置
        start_hotkey_layout = QHBoxLayout()
        start_hotkey_label = QLabel('开始监控:')
        self.start_hotkey_edit = QLineEdit()
        self.start_hotkey_edit.setReadOnly(True)
        self.start_hotkey_edit.setText(self.health_monitor.start_monitoring_hotkey)
        start_hotkey_record_btn = QPushButton('记录')
        start_hotkey_record_btn.setIcon(qta.icon('fa5s.keyboard', color='white'))
        start_hotkey_layout.addWidget(start_hotkey_label)
        start_hotkey_layout.addWidget(self.start_hotkey_edit)
        start_hotkey_layout.addWidget(start_hotkey_record_btn)
        hotkey_layout.addLayout(start_hotkey_layout)
        
        # 停止监控快捷键设置
        stop_hotkey_layout = QHBoxLayout()
        stop_hotkey_label = QLabel('停止监控:')
        self.stop_hotkey_edit = QLineEdit()
        self.stop_hotkey_edit.setReadOnly(True)
        self.stop_hotkey_edit.setText(self.health_monitor.stop_monitoring_hotkey)
        stop_hotkey_record_btn = QPushButton('记录')
        stop_hotkey_record_btn.setIcon(qta.icon('fa5s.keyboard', color='white'))
        stop_hotkey_layout.addWidget(stop_hotkey_label)
        stop_hotkey_layout.addWidget(self.stop_hotkey_edit)
        stop_hotkey_layout.addWidget(stop_hotkey_record_btn)
        hotkey_layout.addLayout(stop_hotkey_layout)
        
        # 保存快捷键设置按钮
        save_hotkeys_btn = QPushButton('保存快捷键设置')
        save_hotkeys_btn.setIcon(qta.icon('fa5s.save', color='white'))
        hotkey_layout.addWidget(save_hotkeys_btn)
        
        # 连接快捷键设置按钮信号
        start_hotkey_record_btn.clicked.connect(lambda: self.record_hotkey(self.start_hotkey_edit))
        stop_hotkey_record_btn.clicked.connect(lambda: self.record_hotkey(self.stop_hotkey_edit))
        save_hotkeys_btn.clicked.connect(self.save_hotkey_settings)
        
        layout.addWidget(hotkey_group)
        
        # 添加自动选择设置区域
        auto_select_group = QFrame()
        auto_select_group.setFrameStyle(QFrame.StyledPanel)
        auto_select_group.setStyleSheet(self.frame_style)
        auto_select_layout = QVBoxLayout(auto_select_group)
        
        auto_select_title = QLabel('自动选择设置')
        auto_select_title.setStyleSheet(self.title_style)
        auto_select_layout.addWidget(auto_select_title)
        
        # 启用/禁用复选框
        enable_layout = QHBoxLayout()
        self.auto_select_checkbox = QCheckBox('启用自动选择低血量队友')
        self.auto_select_checkbox.setChecked(self.health_monitor.auto_select_enabled)
        self.auto_select_checkbox.setStyleSheet("""
            QCheckBox {
                color: #2C3E50;
                font-weight: bold;
            }
            QCheckBox::indicator {
                width: 18px;
                height: 18px;
            }
            QCheckBox::indicator:unchecked {
                border: 2px solid #3498DB;
                border-radius: 3px;
                background-color: #FFFFFF;
            }
            QCheckBox::indicator:checked {
                border: 2px solid #3498DB;
                border-radius: 3px;
                background-color: #3498DB;
                image: url("resources/images/check.png");
            }
        """)
        enable_layout.addWidget(self.auto_select_checkbox)
        auto_select_layout.addLayout(enable_layout)
        
        # 血量阈值设置
        threshold_layout = QHBoxLayout()
        threshold_label = QLabel('血量阈值:')
        self.threshold_spinbox = QDoubleSpinBox()
        self.threshold_spinbox.setMinimum(1.0)
        self.threshold_spinbox.setMaximum(99.0)
        self.threshold_spinbox.setValue(self.health_monitor.health_threshold)
        self.threshold_spinbox.setSuffix('%')
        self.threshold_spinbox.setToolTip('当队友血量低于此值时触发自动选择')
        threshold_layout.addWidget(threshold_label)
        threshold_layout.addWidget(self.threshold_spinbox)
        auto_select_layout.addLayout(threshold_layout)
        
        # 冷却时间设置
        cooldown_layout = QHBoxLayout()
        cooldown_label = QLabel('冷却时间:')
        self.cooldown_spinbox = QDoubleSpinBox()
        self.cooldown_spinbox.setMinimum(0.5)
        self.cooldown_spinbox.setMaximum(10.0)
        self.cooldown_spinbox.setValue(self.health_monitor.cooldown_time)
        self.cooldown_spinbox.setSuffix('秒')
        self.cooldown_spinbox.setToolTip('两次自动选择之间的最小间隔')
        cooldown_layout.addWidget(cooldown_label)
        cooldown_layout.addWidget(self.cooldown_spinbox)
        auto_select_layout.addLayout(cooldown_layout)
        
        # 优先职业设置
        priority_label = QLabel('优先选择职业:')
        auto_select_layout.addWidget(priority_label)
        
        self.priority_list = QListWidget()
        self.priority_list.setMaximumHeight(100)
        self.priority_list.setStyleSheet("""
            QListWidget {
                border: 1px solid #BDC3C7;
                border-radius: 5px;
                padding: 5px;
            }
            QListWidget::item {
                padding: 5px;
                border-radius: 3px;
            }
            QListWidget::item:selected {
                background-color: #D6EAF8;
                color: #2C3E50;
            }
            QListWidget::item:hover {
                background-color: #EBF5FB;
            }
        """)
        
        # 获取所有职业类型
        professions = set()
        for member in self.team.members:
            if member.profession and member.profession != '未知':
                professions.add(member.profession)
        
        # 添加职业到列表中
        for profession in sorted(professions):
            item = QListWidgetItem(profession)
            item.setCheckState(Qt.Checked if profession in self.health_monitor.priority_roles else Qt.Unchecked)
            self.priority_list.addItem(item)
        
        auto_select_layout.addWidget(self.priority_list)
        
        # 添加保存按钮
        save_auto_select_btn = QPushButton('保存自动选择设置')
        save_auto_select_btn.setIcon(qta.icon('fa5s.save', color='white'))
        auto_select_layout.addWidget(save_auto_select_btn)
        
        # 连接信号
        save_auto_select_btn.clicked.connect(self.save_auto_select_settings)
        
        layout.addWidget(auto_select_group)
        
        # 添加监控控制区域
        control_group = QFrame()
        control_group.setFrameStyle(QFrame.StyledPanel)
        control_group.setStyleSheet(self.frame_style)
        control_layout = QVBoxLayout(control_group)
        
        control_title = QLabel('监控控制')
        control_title.setStyleSheet(self.title_style)
        control_layout.addWidget(control_title)
        
        # 添加控制面板显示区域
        control_info = QLabel('控制面板用于开始或停止血条监控功能。您也可以使用设置的快捷键进行快速操作。')
        control_info.setWordWrap(True)
        control_info.setStyleSheet('color: #7F8C8D;')
        control_layout.addWidget(control_info)
        
        control_buttons = QHBoxLayout()
        start_monitor_btn = QPushButton('开始监控')
        start_monitor_btn.setIcon(qta.icon('fa5s.play-circle', color='white'))
        start_monitor_btn.setMinimumHeight(50)  # 增加按钮高度
        start_monitor_btn.setIconSize(QSize(24, 24))  # 增加图标大小
        start_monitor_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x1:1, y1:0, 
                    stop:0 #2ECC71, stop:1 #27AE60);
                font-weight: bold;
                font-size: 14px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x1:1, y1:0, 
                    stop:0 #27AE60, stop:1 #2ECC71);
            }
        """)
        
        stop_monitor_btn = QPushButton('停止监控')
        stop_monitor_btn.setIcon(qta.icon('fa5s.stop-circle', color='white'))
        stop_monitor_btn.setMinimumHeight(50)  # 增加按钮高度
        stop_monitor_btn.setIconSize(QSize(24, 24))  # 增加图标大小
        stop_monitor_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x1:1, y1:0, 
                    stop:0 #E74C3C, stop:1 #C0392B);
                font-weight: bold;
                font-size: 14px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x1:1, y1:0, 
                    stop:0 #C0392B, stop:1 #E74C3C);
            }
        """)
        
        control_buttons.addWidget(start_monitor_btn)
        control_buttons.addWidget(stop_monitor_btn)
        control_layout.addLayout(control_buttons)
        
        # 添加状态指示区域
        status_layout = QHBoxLayout()
        status_label = QLabel('当前状态:')
        self.monitor_status_label = QLabel('未启动')
        self.monitor_status_label.setStyleSheet('font-weight: bold; color: #95A5A6;')
        status_layout.addWidget(status_label)
        status_layout.addWidget(self.monitor_status_label)
        status_layout.addStretch()
        control_layout.addLayout(status_layout)
        
        # 连接监控控制按钮信号
        start_monitor_btn.clicked.connect(self.start_monitoring_from_settings)
        stop_monitor_btn.clicked.connect(self.stop_monitoring_from_settings)
        
        layout.addWidget(control_group)
        
        return tab

    def add_profession_icon(self):
        """添加职业图标"""
        # 创建对话框
        dialog = QDialog(self)
        dialog.setWindowTitle('添加职业图标')
        dialog.setMinimumSize(300, 100)
        
        # 创建布局
        layout = QVBoxLayout(dialog)
        
        # 添加按钮
        btn_layout = QHBoxLayout()
        select_file_btn = QPushButton('从文件选择')
        capture_screen_btn = QPushButton('从屏幕截取')
        btn_layout.addWidget(select_file_btn)
        btn_layout.addWidget(capture_screen_btn)
        layout.addLayout(btn_layout)
        
        # 从文件选择图标
        def select_from_file():
            file_dialog = QFileDialog(self)
            file_dialog.setNameFilter("图片文件 (*.png *.jpg *.jpeg)")
            file_dialog.setWindowTitle('选择职业图标')
            
            if file_dialog.exec() == QDialog.Accepted:
                selected_files = file_dialog.selectedFiles()
                if selected_files:
                    file_path = selected_files[0]
                    save_icon(file_path)
            dialog.close()
        
        # 从屏幕截取图标
        def capture_from_screen():
            dialog.hide()  # 暂时隐藏对话框
            
            # 创建选择框
            selection_box = self.recognition.create_selection_box()
            if selection_box.exec_() == QDialog.Accepted:
                # 获取选择区域的图像
                screenshot = selection_box.get_selected_image()
                if screenshot is not None:
                    # 生成一个唯一的临时文件名
                    import tempfile
                    import uuid
                    temp_dir = tempfile.gettempdir()
                    unique_filename = f"icon_{uuid.uuid4().hex}.png"
                    temp_path = os.path.join(temp_dir, unique_filename)
                    
                    # 确保cv2已导入
                    import cv2
                    cv2.imwrite(temp_path, screenshot)
                    
                    # 在保存后弹出对话框让用户输入职业名称
                    profession_name, ok = QInputDialog.getText(
                        self, 
                        "输入职业名称", 
                        "请输入该图标对应的职业名称:",
                        QLineEdit.Normal
                    )
                    
                    if ok and profession_name:
                        # 使用用户输入的职业名称作为文件名
                        target_filename = f"{profession_name}.png"
                        # 保存时指定新的文件名
                        save_icon(temp_path, target_filename)
                    else:
                        # 如果用户取消，则直接使用临时文件名
                        save_icon(temp_path)
                    
                    # 删除临时文件
                    try:
                        os.remove(temp_path)
                        print(f"临时文件已删除: {temp_path}")
                    except Exception as e:
                        print(f"删除临时文件时出错: {str(e)}")
            
            dialog.close()
        
        # 保存图标
        def save_icon(file_path, custom_filename=None):
            try:
                # 获取文件名
                if custom_filename:
                    file_name = custom_filename
                else:
                    file_name = os.path.basename(file_path)
                
                # 确保目标目录存在
                os.makedirs(self.recognition.profession_icons_dir, exist_ok=True)
                
                # 复制文件到职业图标目录
                target_path = os.path.join(self.recognition.profession_icons_dir, file_name)
                
                # 检查目标文件是否已存在
                if os.path.exists(target_path):
                    # 如果已存在，在文件名中添加数字后缀
                    base_name, ext = os.path.splitext(file_name)
                    counter = 1
                    while os.path.exists(target_path):
                        new_name = f"{base_name}_{counter}{ext}"
                        target_path = os.path.join(self.recognition.profession_icons_dir, new_name)
                        counter += 1
                    file_name = os.path.basename(target_path)
                
                import shutil
                shutil.copy2(file_path, target_path)
                print(f'成功添加职业图标：{file_name}')
                
                # 显示成功消息
                QMessageBox.information(self, "添加成功", f"职业图标 {file_name} 已成功添加")
                
            except Exception as e:
                print(f'添加职业图标失败：{str(e)}')
                QMessageBox.critical(self, "添加失败", f"添加职业图标失败：{str(e)}")
        
        # 连接按钮信号
        select_file_btn.clicked.connect(select_from_file)
        capture_screen_btn.clicked.connect(capture_from_screen)
        
        # 显示对话框
        dialog.exec()
    
    def load_teammate_configs(self):
        """加载所有队友配置文件，禁止重复加载已存在的队友"""
        try:
            print("=== DEBUG: 开始加载队友配置 ===")
            # 获取当前目录
            current_dir = os.path.dirname(os.path.abspath(__file__))
            # 获取所有以 _config.json 结尾的文件，但排除 hotkeys_config.json
            all_config_files = [f for f in os.listdir(current_dir) if f.endswith('_config.json')]
            print(f"DEBUG: 所有配置文件: {all_config_files}")
            
            config_files = [f for f in os.listdir(current_dir) 
                           if f.endswith('_config.json') and f != 'hotkeys_config.json']
            print(f"DEBUG: 排除 hotkeys_config.json 后的配置文件: {config_files}")
            
            if not config_files:
                self.result_label.setText('未找到任何队友配置文件')
                return
            
            # 获取当前队伍中的队员名称列表
            existing_members = [member.name for member in self.team.members]
            
            loaded_configs = []
            skipped_configs = []
            
            for config_file in config_files:
                try:
                    # 获取队友名称（从文件名中提取）
                    teammate_name = config_file.replace('_config.json', '')
                    
                    # 检查文件名是否包含特殊关键字，可能不是队友配置
                    if teammate_name.lower() in ['hotkeys', 'settings', 'config', 'system']:
                        print(f'跳过非队友配置文件: {config_file}')
                        continue
                    
                    # 检查队员是否已存在于队伍中
                    if teammate_name in existing_members:
                        print(f'队员 {teammate_name} 已存在于队伍中，跳过加载')
                        skipped_configs.append(teammate_name)
                        continue
                    
                    # 读取配置文件
                    file_path = os.path.join(current_dir, config_file)
                    with open(file_path, 'r', encoding='utf-8') as f:
                        config = json.load(f)
                    
                    # 确认这是一个队友配置文件（检查必要的字段）
                    if 'profession' not in config or 'health_bar' not in config:
                        print(f'文件 {config_file} 不是有效的队友配置文件，跳过加载')
                        continue
                    
                    profession = config.get('profession', '未知')
                    health_bar = config.get('health_bar', {})
                    
                    # 创建或更新队友对象
                    teammate = TeamMember(teammate_name, profession)
                    
                    # 更新血条坐标
                    if 'coordinates' in health_bar:
                        coords = health_bar['coordinates']
                        teammate.health_bar_coords = {
                            'x1': coords.get('x1', 0),
                            'y1': coords.get('y1', 0),
                            'x2': coords.get('x2', 0),
                            'y2': coords.get('y2', 0)
                        }
                    
                    # 更新血条颜色
                    if 'color' in health_bar:
                        color = health_bar['color']
                        teammate.health_bar_color = {
                            'lower': color.get('lower', [43, 71, 121]),
                            'upper': color.get('upper', [63, 171, 221])
                        }
                    
                    # 将队友添加到队伍中
                    self.team.add_member(teammate_name, profession)
                    loaded_configs.append(f'{teammate_name}（{profession}）')
                    
                except Exception as e:
                    print(f'加载配置文件 {config_file} 时出错: {str(e)}')
                    continue
            
            # 显示加载结果
            result_text = ''
            if loaded_configs:
                result_text += '成功加载以下队友配置：\n' + '\n'.join(loaded_configs)
            else:
                result_text += '未能成功加载任何新配置文件\n'
            
            if skipped_configs:
                result_text += '\n\n以下队友已存在，已跳过加载：\n' + '\n'.join(skipped_configs)
            
            self.result_label.setText(result_text)
            
        except Exception as e:
            self.result_label.setText(f'加载配置文件时出错：{str(e)}')
    
    def select_recognition_area(self):
        """选择识别区域，添加待识别队友"""
        # 创建RecognitionUI实例并显示
        recognition_ui = RecognitionUI()
        recognition_ui.exec_()
        
    def start_recognition(self):
        """开始识别待识别队友"""
        # 创建RecognitionUI实例
        recognition_ui = RecognitionUI()
        
        # 传递图像质量设置参数
        # 对比度值需要除以10转换为浮点数
        contrast = self.contrast_slider.value() / 10.0
        brightness = self.brightness_slider.value()
        num_samples = self.samples_spinner.value()
        
        # 更新识别模块的参数
        recognition_ui.recognition.contrast = contrast
        recognition_ui.recognition.brightness = brightness
        recognition_ui.recognition.num_samples = num_samples
        
        # 显示设置信息
        self.result_label.setText(f"识别参数设置:\n对比度: {contrast}\n亮度: {brightness}\n采样次数: {num_samples}\n\n开始识别...")
        
        # 调用批量识别方法
        recognition_ui.batch_recognize_teammates()
        recognition_ui.exec_()
        
    def view_profession_icons(self):
        """查看已有职业图标"""
        dialog = QDialog(self)
        dialog.setWindowTitle('职业图标预览')
        dialog.setMinimumSize(400, 300)
        
        layout = QVBoxLayout(dialog)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        content = QWidget()
        grid = QGridLayout(content)
        
        # 加载并显示所有图标
        icons_dir = self.recognition.profession_icons_dir
        if os.path.exists(icons_dir):
            files = [f for f in os.listdir(icons_dir) if f.lower().endswith(('.png', '.jpg', '.jpeg'))]
            row = 0
            col = 0
            for file in files:
                try:
                    file_path = os.path.join(icons_dir, file)
                    pixmap = QPixmap(file_path)
                    if not pixmap.isNull():
                        # 缩放图标到合适大小
                        pixmap = pixmap.scaled(100, 100, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                        icon_label = QLabel()
                        icon_label.setPixmap(pixmap)
                        name_label = QLabel(os.path.splitext(file)[0])
                        name_label.setAlignment(Qt.AlignCenter)
                        
                        container = QWidget()
                        container_layout = QVBoxLayout(container)
                        container_layout.addWidget(icon_label, alignment=Qt.AlignCenter)
                        container_layout.addWidget(name_label)
                        
                        grid.addWidget(container, row, col)
                        
                        col += 1
                        if col >= 3:  # 每行显示3个图标
                            col = 0
                            row += 1
                except Exception as e:
                    print(f'加载图标失败：{file} - {str(e)}')
        
        scroll.setWidget(content)
        layout.addWidget(scroll)
        
        dialog.exec()

    def add_team_member(self):
        """添加队员"""
        self.health_monitor.add_team_member()
    
    def remove_team_member(self):
        """移除队员"""
        if self.health_monitor.remove_team_member():
            self.update_monitor_results([])
    
    def set_health_bar_position(self):
        """设置血条位置"""
        self.health_monitor.set_health_bar_position()
    
    def set_health_bar_color(self):
        """设置血条颜色"""
        self.health_monitor.set_health_bar_color()
    
    def start_monitoring(self):
        """开始监控"""
        self.health_monitor.start_monitoring()
    
    def stop_monitoring(self):
        """停止监控"""
        if self.health_monitor.stop_monitoring():
            # 清除UI监控日志
            self.monitor_result_label.setText("监控已停止，日志已清除")
    
    def update_monitor_results(self, health_data):
        """更新监控结果显示"""
        if not health_data:
            self.monitor_result_label.setText("未检测到队友或未启动监控")
            return
        
        result_text = "<html><body style='font-family: 微软雅黑, Arial, sans-serif;'>"
        
        # 添加状态摘要
        low_hp_count = sum(1 for _, health, is_alive in health_data if health <= 30 and is_alive)
        total_alive = sum(1 for _, _, is_alive in health_data if is_alive)
        
        if low_hp_count > 0:
            result_text += f"<div style='background: rgba(231, 76, 60, 0.2); padding: 10px; border-radius: 10px; margin-bottom: 15px; border-left: 4px solid #E74C3C;'>"
            result_text += f"<span style='color: #E74C3C; font-weight: bold;'>警告：</span> {low_hp_count} 名队友血量低于30%！</div>"
        
        result_text += f"<div style='margin-bottom: 15px; background: rgba(52, 152, 219, 0.1); padding: 10px; border-radius: 10px; text-align: center;'>"
        result_text += f"<span style='font-size: 14px;'>存活队友：<b>{total_alive}/{len(health_data)}</b></span></div>"
        
        # 创建队友状态卡片
        for name, health, is_alive in health_data:
            # 查找队友对象获取职业信息
            profession = "未知"
            for member in self.team.members:
                if member.name == name:
                    profession = member.profession
                    break
            
            # 设置血量颜色和背景
            if not is_alive:
                card_bg = "rgba(189, 195, 199, 0.2)"  # 灰色背景 - 阵亡
                health_color = "#95A5A6"
                status_color = "#95A5A6"
                status_text = "阵亡"
                border_color = "#95A5A6"
            elif health <= 30:
                card_bg = "rgba(231, 76, 60, 0.1)"  # 红色透明背景 - 危险
                health_color = "#E74C3C"
                status_color = "#E74C3C"
                status_text = "危险"
                border_color = "#E74C3C"
            elif health <= 70:
                card_bg = "rgba(243, 156, 18, 0.1)"  # 橙色透明背景 - 警告
                health_color = "#F39C12"
                status_color = "#F39C12"
                status_text = "警告"
                border_color = "#F39C12"
            else:
                card_bg = "rgba(46, 204, 113, 0.1)"  # 绿色透明背景 - 安全
                health_color = "#2ECC71"
                status_color = "#2ECC71"
                status_text = "安全"
                border_color = "#2ECC71"
            
            # 添加职业图标
            icon_html = ""
            if profession in self.profession_icons:
                # 将图标转换为base64编码以在HTML中显示
                pixmap = self.profession_icons[profession]
                if not pixmap.isNull():
                    ba = QByteArray()
                    buffer = QBuffer(ba)
                    buffer.open(QIODevice.WriteOnly)
                    pixmap.scaled(24, 24).save(buffer, 'PNG')
                    icon_data = ba.toBase64().data().decode()
                    icon_html = f'<img src="data:image/png;base64,{icon_data}" width="24" height="24" style="vertical-align:middle;margin-right:8px;"/>'
            
            # 创建血量条
            health_bar_width = 100  # 血量条总宽度
            current_health_width = int(health * health_bar_width / 100)  # 当前血量宽度
            
            # 构建队友状态卡片
            result_text += f"""
            <div style='background: {card_bg}; padding: 12px; border-radius: 10px; margin-bottom: 12px; border-left: 4px solid {border_color}; box-shadow: 0 2px 5px rgba(0,0,0,0.05);'>
                <div style='display: flex; justify-content: space-between; margin-bottom: 8px;'>
                    <div>
                        {icon_html}<span style='font-weight: bold; font-size: 14px;'>{name}</span> 
                        <span style='color: #7F8C8D; font-size: 12px;'>({profession})</span>
                    </div>
                    <div style='color: {status_color}; font-weight: bold; background: rgba(255,255,255,0.5); padding: 2px 8px; border-radius: 10px; font-size: 12px;'>{status_text}</div>
                </div>
                <div style='background: rgba(189, 195, 199, 0.3); height: 10px; border-radius: 5px; margin: 8px 0; overflow: hidden;'>
                    <div style='background: {health_color}; width: {current_health_width}%; height: 10px; border-radius: 5px; transition: width 0.3s ease-in-out;'></div>
                </div>
                <div style='text-align: right; color: {health_color}; font-weight: bold;'>{health:.1f}%</div>
            </div>
            """
        
        result_text += "</body></html>"
        self.monitor_result_label.setText(result_text)
    
    def update_monitor_status(self, status):
        """更新监控状态信息"""
        if hasattr(self, 'monitor_status_label'):
            # 更新设置页面的状态标签
            self.monitor_status_label.setText(status)
            
            # 根据状态设置不同颜色
            if "启动" in status or "开始" in status:
                self.monitor_status_label.setStyleSheet('font-weight: bold; color: #2ECC71;')
            elif "停止" in status or "错误" in status:
                self.monitor_status_label.setStyleSheet('font-weight: bold; color: #E74C3C;')
            else:
                self.monitor_status_label.setStyleSheet('font-weight: bold; color: #3498DB;')
        
        if self.monitor_result_label:
            current_text = self.monitor_result_label.text()
            if "状态:" in current_text:
                # 替换状态行
                lines = current_text.split('\n')
                for i, line in enumerate(lines):
                    if "状态:" in line:
                        lines[i] = f"状态: {status}"
                        break
                else:
                    lines.append(f"状态: {status}")
                self.monitor_result_label.setText('\n'.join(lines))
            else:
                # 添加状态信息
                self.monitor_result_label.setText(f"{current_text}\n\n状态: {status}")

    def record_hotkey(self, edit):
        """记录快捷键"""
        dialog = QDialog(self)
        dialog.setWindowTitle('记录快捷键')
        dialog.setFixedSize(300, 150)
        
        layout = QVBoxLayout(dialog)
        
        prompt_label = QLabel('请按下您想要设置的快捷键...')
        prompt_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(prompt_label)
        
        key_label = QLabel('按下的按键: ')
        key_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(key_label)
        
        # 快捷键记录标志
        dialog.key_recorded = False
        dialog.key_name = ""
        
        # 创建一个Qt计时器，用于延迟接受对话框
        accept_timer = QTimer(dialog)
        accept_timer.setSingleShot(True)
        accept_timer.timeout.connect(dialog.accept)
        
        # 快捷键记录事件过滤器
        def keyPressEvent(event):
            # 获取按键名称
            key = event.key()
            if key == Qt.Key_Escape:
                dialog.reject()
                return
                
            # 将Qt键码转换为keyboard库兼容的字符串
            key_text = ""
            if key == Qt.Key_F1: key_text = "f1"
            elif key == Qt.Key_F2: key_text = "f2"
            elif key == Qt.Key_F3: key_text = "f3"
            elif key == Qt.Key_F4: key_text = "f4"
            elif key == Qt.Key_F5: key_text = "f5"
            elif key == Qt.Key_F6: key_text = "f6"
            elif key == Qt.Key_F7: key_text = "f7"
            elif key == Qt.Key_F8: key_text = "f8"
            elif key == Qt.Key_F9: key_text = "f9"
            elif key == Qt.Key_F10: key_text = "f10"
            elif key == Qt.Key_F11: key_text = "f11"
            elif key == Qt.Key_F12: key_text = "f12"
            elif key == Qt.Key_Tab: key_text = "tab"
            elif key == Qt.Key_CapsLock: key_text = "caps lock"
            elif key == Qt.Key_Shift: key_text = "shift"
            elif key == Qt.Key_Control: key_text = "ctrl"
            elif key == Qt.Key_Alt: key_text = "alt"
            elif key == Qt.Key_Backspace: key_text = "backspace"
            elif key == Qt.Key_Return or key == Qt.Key_Enter: key_text = "enter"
            elif key == Qt.Key_Insert: key_text = "insert"
            elif key == Qt.Key_Delete: key_text = "delete"
            elif key == Qt.Key_Home: key_text = "home"
            elif key == Qt.Key_End: key_text = "end"
            elif key == Qt.Key_PageUp: key_text = "page up"
            elif key == Qt.Key_PageDown: key_text = "page down"
            elif key == Qt.Key_Space: key_text = "space"
            else:
                # 字母、数字和其他常规键
                key_text = event.text().lower()
                
            if key_text:
                dialog.key_name = key_text
                key_label.setText(f'按下的按键: {key_text}')
                dialog.key_recorded = True
                
                # 使用Qt计时器延迟500毫秒后自动接受对话框
                accept_timer.start(500)
        
        # 设置键盘事件处理函数
        dialog.keyPressEvent = keyPressEvent
        
        # 显示对话框并等待结果
        result = dialog.exec()
        
        if result == QDialog.Accepted and dialog.key_recorded:
            edit.setText(dialog.key_name)
            return dialog.key_name
        
        return None

    def save_hotkey_settings(self):
        """保存快捷键设置"""
        start_key = self.start_hotkey_edit.text()
        stop_key = self.stop_hotkey_edit.text()
        
        if not start_key or not stop_key:
            self.monitor_result_label.setText("错误: 快捷键不能为空")
            return
            
        if start_key == stop_key:
            self.monitor_result_label.setText("错误: 开始和停止的快捷键不能相同")
            return
            
        # 保存快捷键设置
        success = self.health_monitor.set_hotkeys(start_key, stop_key)
        
        if success:
            self.monitor_result_label.setText(f"快捷键设置已保存:\n开始监控: {start_key}\n停止监控: {stop_key}")
        else:
            self.monitor_result_label.setText("保存快捷键设置失败，请再试一次")
            
    def save_auto_select_settings(self):
        """保存自动选择设置"""
        # 获取界面设置
        enabled = self.auto_select_checkbox.isChecked()
        threshold = self.threshold_spinbox.value()
        cooldown = self.cooldown_spinbox.value()
        
        # 获取优先职业
        priority_roles = []
        for i in range(self.priority_list.count()):
            item = self.priority_list.item(i)
            if item.checkState() == Qt.Checked:
                priority_roles.append(item.text())
        
        # 更新设置
        success = self.health_monitor.set_auto_select_settings(
            enabled, threshold, cooldown, priority_roles
        )
        
        if success:
            self.monitor_result_label.setText(f"自动选择设置已保存:\n启用: {'是' if enabled else '否'}\n血量阈值: {threshold}%\n冷却时间: {cooldown}秒\n优先职业: {', '.join(priority_roles) if priority_roles else '无'}")
        else:
            self.monitor_result_label.setText("保存自动选择设置失败，请再试一次")

    def closeEvent(self, event):
        """窗口关闭事件处理"""
        print("正在关闭应用程序...")
        try:
            # 确保释放资源
            if hasattr(self, 'health_monitor'):
                print("正在释放健康监控资源...")
                self.health_monitor.release_resources()
                print("健康监控资源已释放")
        except Exception as e:
            print(f"关闭窗口时出错: {str(e)}")
        event.accept()
    
    def __del__(self):
        """析构函数，确保释放资源"""
        try:
            if hasattr(self, 'health_monitor'):
                self.health_monitor.release_resources()
        except Exception as e:
            print(f"释放资源时出错: {str(e)}")
            pass

    def open_calibration_tool(self):
        """打开血条校准工具"""
        dialog = CalibrationDialog(self)
        dialog.exec()
        # 校准完成后刷新队友列表
        self.team = Team()  # 重新加载队友
        self.health_monitor = HealthMonitor(self.team)
        # 重新连接信号
        self.health_monitor.signals.update_signal.connect(self.update_monitor_results)
        self.health_monitor.signals.status_signal.connect(self.update_monitor_status)

    def remove_all_teammates(self):
        """一键移除所有队友"""
        # 如果没有队友，直接返回
        if not self.team.members or len(self.team.members) == 0:
            QMessageBox.information(self, "提示", "当前没有队友可移除")
            return
        
        # 确认对话框
        reply = QMessageBox.question(
            self,
            "确认移除全部队友",
            f"确定要一次性移除所有 {len(self.team.members)} 名队友吗？\n此操作不可撤销。",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No  # 默认为"否"，防止误操作
        )
        
        if reply == QMessageBox.Yes:
            try:
                # 停止当前监控，防止访问已删除的队友数据
                if hasattr(self, 'health_monitor') and self.health_monitor:
                    self.health_monitor.stop_monitoring()
                
                # 获取所有队友名称，用于删除配置文件
                teammate_names = [member.name for member in self.team.members]
                
                # 清空队友列表
                self.team.members.clear()
                
                # 删除所有队友配置文件
                config_dir = os.path.dirname(os.path.abspath(__file__))
                for name in teammate_names:
                    config_file = os.path.join(config_dir, f"{name}_config.json")
                    if os.path.exists(config_file):
                        try:
                            os.remove(config_file)
                            print(f"已删除队友配置文件: {config_file}")
                        except Exception as e:
                            print(f"删除队友配置文件时出错: {str(e)}")
                
                # 更新UI
                self.update_monitor_results([])
                
                # 更新UI状态
                self.update_ui_states()
                
                # 清除任何可能的选中状态
                if hasattr(self, 'priority_list'):
                    self.priority_list.clearSelection()
                
                # 显示成功消息
                if hasattr(self, 'monitor_result_label') and self.monitor_result_label:
                    self.monitor_result_label.setText(f"已成功移除所有 {len(teammate_names)} 名队友并删除相关配置文件")
                
                # 如果有状态栏，也显示消息
                if hasattr(self, 'statusBar'):
                    self.statusBar().showMessage("已成功移除所有队友", 3000)
                
            except Exception as e:
                QMessageBox.critical(self, "错误", f"移除队友时出错：{str(e)}")

    def update_ui_states(self):
        """更新UI组件状态
        
        根据当前队友数量和状态更新相关按钮的启用/禁用状态
        """
        has_teammates = len(self.team.members) > 0 if hasattr(self, 'team') and self.team and hasattr(self.team, 'members') else False
        
        # 更新血条监控相关按钮
        if hasattr(self, 'start_monitor_btn'):
            self.start_monitor_btn.setEnabled(has_teammates)
        
        if hasattr(self, 'stop_monitor_btn'):
            self.stop_monitor_btn.setEnabled(has_teammates)
        
        # 更新队员管理相关按钮
        if hasattr(self, 'remove_member_btn'):
            self.remove_member_btn.setEnabled(has_teammates)
        
        # 优先级列表的更新
        if hasattr(self, 'priority_list'):
            self.priority_list.setEnabled(has_teammates)
        
        # 其他可能需要根据队友状态更新的UI元素
        if hasattr(self, 'auto_select_checkbox'):
            self.auto_select_checkbox.setEnabled(has_teammates)

    def load_profession_icons(self):
        """加载所有职业图标"""
        self.profession_icons = {}
        icons_dir = 'profession_icons'
        
        # 确保图标目录存在
        if not os.path.exists(icons_dir):
            os.makedirs(icons_dir)
            print(f"创建职业图标目录: {icons_dir}")
            return
        
        # 加载所有图标
        for filename in os.listdir(icons_dir):
            if filename.lower().endswith(('.png', '.jpg', '.jpeg')):
                try:
                    icon_path = os.path.join(icons_dir, filename)
                    profession_name = os.path.splitext(filename)[0]
                    
                    # 使用QPixmap加载图标
                    pixmap = QPixmap(icon_path)
                    if not pixmap.isNull():
                        self.profession_icons[profession_name] = pixmap
                        print(f"成功加载图标: {profession_name}")
                    else:
                        print(f"无法加载图标: {icon_path}")
                except Exception as e:
                    print(f"加载图标时出错 {filename}: {str(e)}")
        
        print(f"共加载 {len(self.profession_icons)} 个职业图标")

    def set_all_health_bar_colors(self):
        """批量设置所有队友的血条颜色范围"""
        # 检查是否有队友
        if not self.team.members or len(self.team.members) == 0:
            QMessageBox.information(self, "提示", "当前没有队友可设置")
            return
        
        # 创建颜色选择对话框
        try:
            # 显示颜色设置对话框
            dialog = QDialog(self)
            dialog.setWindowTitle("批量设置血条颜色")
            dialog.setMinimumWidth(400)
            
            layout = QVBoxLayout(dialog)
            
            # 添加说明文本
            info_label = QLabel("此功能将为所有队友设置相同的血条颜色检测范围。\n"
                               "通过调整HSV颜色空间的参数来设置检测范围。")
            info_label.setWordWrap(True)
            layout.addWidget(info_label)
            
            # 添加当前队友数量信息
            count_label = QLabel(f"当前共有 {len(self.team.members)} 名队友")
            layout.addWidget(count_label)
            
            # 如果有队友，则获取第一个队友的颜色范围作为默认值
            default_lower = [43, 71, 121]  # 默认HSV下限
            default_upper = [63, 171, 221]  # 默认HSV上限
            
            if len(self.team.members) > 0:
                first_member = self.team.members[0]
                if hasattr(first_member, 'hp_color_lower') and hasattr(first_member, 'hp_color_upper'):
                    default_lower = first_member.hp_color_lower.tolist()
                    default_upper = first_member.hp_color_upper.tolist()
            
            # 创建HSV范围设置框架
            hsv_frame = QFrame()
            hsv_layout = QGridLayout(hsv_frame)
            
            # 添加HSV滑块
            h_min_slider = QSlider(Qt.Horizontal)
            h_min_slider.setRange(0, 179)
            h_min_slider.setValue(default_lower[0])
            
            h_max_slider = QSlider(Qt.Horizontal)
            h_max_slider.setRange(0, 179)
            h_max_slider.setValue(default_upper[0])
            
            s_min_slider = QSlider(Qt.Horizontal)
            s_min_slider.setRange(0, 255)
            s_min_slider.setValue(default_lower[1])
            
            s_max_slider = QSlider(Qt.Horizontal)
            s_max_slider.setRange(0, 255)
            s_max_slider.setValue(default_upper[1])
            
            v_min_slider = QSlider(Qt.Horizontal)
            v_min_slider.setRange(0, 255)
            v_min_slider.setValue(default_lower[2])
            
            v_max_slider = QSlider(Qt.Horizontal)
            v_max_slider.setRange(0, 255)
            v_max_slider.setValue(default_upper[2])
            
            # 添加数值显示
            h_min_spin = QSpinBox()
            h_min_spin.setRange(0, 179)
            h_min_spin.setValue(default_lower[0])
            
            h_max_spin = QSpinBox()
            h_max_spin.setRange(0, 179)
            h_max_spin.setValue(default_upper[0])
            
            s_min_spin = QSpinBox()
            s_min_spin.setRange(0, 255)
            s_min_spin.setValue(default_lower[1])
            
            s_max_spin = QSpinBox()
            s_max_spin.setRange(0, 255)
            s_max_spin.setValue(default_upper[1])
            
            v_min_spin = QSpinBox()
            v_min_spin.setRange(0, 255)
            v_min_spin.setValue(default_lower[2])
            
            v_max_spin = QSpinBox()
            v_max_spin.setRange(0, 255)
            v_max_spin.setValue(default_upper[2])
            
            # 连接滑块和数值框
            h_min_slider.valueChanged.connect(h_min_spin.setValue)
            h_min_spin.valueChanged.connect(h_min_slider.setValue)
            
            h_max_slider.valueChanged.connect(h_max_spin.setValue)
            h_max_spin.valueChanged.connect(h_max_slider.setValue)
            
            s_min_slider.valueChanged.connect(s_min_spin.setValue)
            s_min_spin.valueChanged.connect(s_min_slider.setValue)
            
            s_max_slider.valueChanged.connect(s_max_spin.setValue)
            s_max_spin.valueChanged.connect(s_max_slider.setValue)
            
            v_min_slider.valueChanged.connect(v_min_spin.setValue)
            v_min_spin.valueChanged.connect(v_min_slider.setValue)
            
            v_max_slider.valueChanged.connect(v_max_spin.setValue)
            v_max_spin.valueChanged.connect(v_max_slider.setValue)
            
            # 布局
            hsv_layout.addWidget(QLabel("色调 (H)"), 0, 0)
            hsv_layout.addWidget(QLabel("最小值:"), 0, 1)
            hsv_layout.addWidget(h_min_slider, 0, 2)
            hsv_layout.addWidget(h_min_spin, 0, 3)
            hsv_layout.addWidget(QLabel("最大值:"), 0, 4)
            hsv_layout.addWidget(h_max_slider, 0, 5)
            hsv_layout.addWidget(h_max_spin, 0, 6)
            
            hsv_layout.addWidget(QLabel("饱和度 (S)"), 1, 0)
            hsv_layout.addWidget(QLabel("最小值:"), 1, 1)
            hsv_layout.addWidget(s_min_slider, 1, 2)
            hsv_layout.addWidget(s_min_spin, 1, 3)
            hsv_layout.addWidget(QLabel("最大值:"), 1, 4)
            hsv_layout.addWidget(s_max_slider, 1, 5)
            hsv_layout.addWidget(s_max_spin, 1, 6)
            
            hsv_layout.addWidget(QLabel("亮度 (V)"), 2, 0)
            hsv_layout.addWidget(QLabel("最小值:"), 2, 1)
            hsv_layout.addWidget(v_min_slider, 2, 2)
            hsv_layout.addWidget(v_min_spin, 2, 3)
            hsv_layout.addWidget(QLabel("最大值:"), 2, 4)
            hsv_layout.addWidget(v_max_slider, 2, 5)
            hsv_layout.addWidget(v_max_spin, 2, 6)
            
            layout.addWidget(hsv_frame)
            
            # 添加预览区域
            preview_label = QLabel("颜色预览:")
            layout.addWidget(preview_label)
            
            preview_frame = QFrame()
            preview_frame.setMinimumHeight(50)
            preview_frame.setStyleSheet("background-color: #4cc3dd;")  # 默认颜色
            layout.addWidget(preview_frame)
            
            # 更新预览区域颜色的函数
            def update_preview():
                # 这里使用近似颜色，因为HSV到RGB的转换比较复杂
                h = (h_min_spin.value() + h_max_spin.value()) / 2 / 179.0
                s = (s_min_spin.value() + s_max_spin.value()) / 2 / 255.0
                v = (v_min_spin.value() + v_max_spin.value()) / 2 / 255.0
                
                # 简单转换到RGB
                import colorsys
                r, g, b = colorsys.hsv_to_rgb(h, s, v)
                r, g, b = int(r * 255), int(g * 255), int(b * 255)
                
                # 更新预览颜色
                preview_frame.setStyleSheet(f"background-color: rgb({r},{g},{b});")
            
            # 连接更新函数
            h_min_slider.valueChanged.connect(update_preview)
            h_max_slider.valueChanged.connect(update_preview)
            s_min_slider.valueChanged.connect(update_preview)
            s_max_slider.valueChanged.connect(update_preview)
            v_min_slider.valueChanged.connect(update_preview)
            v_max_slider.valueChanged.connect(update_preview)
            
            # 初始更新预览
            update_preview()
            
            # 添加按钮
            button_box = QHBoxLayout()
            apply_btn = QPushButton("应用到所有队友")
            apply_btn.setStyleSheet("background-color: #4CAF50; color: white;")
            cancel_btn = QPushButton("取消")
            
            button_box.addWidget(cancel_btn)
            button_box.addWidget(apply_btn)
            layout.addLayout(button_box)
            
            # 连接按钮信号
            cancel_btn.clicked.connect(dialog.reject)
            
            # 应用颜色设置
            def apply_colors():
                try:
                    # 获取设置的HSV范围
                    lower_hsv = np.array([h_min_spin.value(), s_min_spin.value(), v_min_spin.value()])
                    upper_hsv = np.array([h_max_spin.value(), s_max_spin.value(), v_max_spin.value()])
                    
                    # 应用到所有队友
                    for member in self.team.members:
                        member.hp_color_lower = lower_hsv
                        member.hp_color_upper = upper_hsv
                        # 保存到配置文件
                        member.save_config()
                    
                    QMessageBox.information(dialog, "成功", f"已成功为所有 {len(self.team.members)} 名队友设置血条颜色范围")
                    dialog.accept()
                except Exception as e:
                    QMessageBox.critical(dialog, "错误", f"设置颜色时出错: {str(e)}")
            
            apply_btn.clicked.connect(apply_colors)
            
            # 显示对话框
            dialog.exec()
            
        except Exception as e:
            QMessageBox.critical(self, "错误", f"打开颜色设置对话框时出错: {str(e)}")

    def start_monitoring_from_settings(self):
        """从设置页面开始监控"""
        # 启动监控
        if self.health_monitor.start_monitoring():
            # 更新监控状态
            self.monitor_status_label.setText("正在监控")
            self.monitor_status_label.setStyleSheet('font-weight: bold; color: #2ECC71;')
            # 切换到监控标签页查看结果
            self.tab_widget.setCurrentIndex(1)  # 切换到血条监控标签页
    
    def stop_monitoring_from_settings(self):
        """从设置页面停止监控"""
        # 停止监控
        if self.health_monitor.stop_monitoring():
            # 更新监控状态
            self.monitor_status_label.setText("已停止")
            self.monitor_status_label.setStyleSheet('font-weight: bold; color: #E74C3C;')
    
def load_style_sheet(app):
    """加载现代风格样式表"""
    try:
        print("加载现代淡蓝色风格样式表...")
        style_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "resources", "style.qss")
        if os.path.exists(style_path):
            with open(style_path, "r", encoding="utf-8") as f:
                style = f.read()
                app.setStyleSheet(style)
                print("成功加载现代淡蓝色风格样式表")
        else:
            print(f"样式表文件不存在: {style_path}")
    except Exception as e:
        print(f"加载样式表时出错: {e}")

def main():
    # 在创建QApplication之前设置DPI感知
    os.environ["QT_ENABLE_HIGHDPI_SCALING"] = "1"
    os.environ["QT_SCALE_FACTOR_ROUNDING_POLICY"] = "PassThrough"
    
    app = None
    window = None
    
    try:
        app = QApplication(sys.argv)
        # 加载现代风格样式表
        load_style_sheet(app)
        
        # 确保资源目录存在
        resources_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "resources")
        images_dir = os.path.join(resources_dir, "images")
        os.makedirs(images_dir, exist_ok=True)
        
        window = MainWindow()
        window.show()
        sys.exit(app.exec())
    except Exception as e:
        import traceback
        print(f"错误: {e}")
        print(traceback.format_exc())
        
        # 程序异常时尝试释放资源
        try:
            if window and hasattr(window, 'health_monitor'):
                print("程序异常退出，尝试释放资源...")
                window.health_monitor.release_resources()
        except:
            pass
            
        sys.exit(1)

if __name__ == '__main__':
    main()