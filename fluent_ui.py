import sys
import os
import cv2
import numpy as np
import json
import threading
import pyautogui
import time
import asyncio
import edge_tts
import tempfile
import queue # 新增导入
import logging
from config_manager import ConfigManager, get_config
from config_defaults import DEFAULT_CONFIG
# 移除 playsound 导入
# from playsound import playsound
# 添加 pygame 导入
import pygame
from PyQt5.QtCore import Qt, QTimer, QByteArray, QBuffer, QIODevice, QPoint, QSize, QRect, QThread, pyqtSignal, QObject, QEvent, QUrl, QPropertyAnimation
from PyQt5.QtGui import QPixmap, QImage, QIcon, QColor, QFont, QKeySequence, QDesktopServices
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                            QLabel, QFileDialog, QFrame, QGridLayout, QSplitter, QTabWidget, QGroupBox,
                            QInputDialog, QDialog, QListWidget, QListWidgetItem, QAbstractItemView,
                            QGraphicsDropShadowEffect)

# 导入Fluent组件库
from qfluentwidgets import (FluentWindow, NavigationItemPosition, PushButton, 
                           ToolButton, PrimaryPushButton, ComboBox, RadioButton, CheckBox,
                           Slider, SwitchButton, ToggleButton, SubtitleLabel, BodyLabel,
                           Action, setTheme, Theme, MessageBox, MessageBoxBase, InfoBar, TabBar,
                           TransparentPushButton, LineEdit, StrongBodyLabel, CaptionLabel,
                           SpinBox, DoubleSpinBox, ScrollArea, CardWidget, HeaderCardWidget,
                           InfoBarPosition, NavigationInterface, setThemeColor, FluentIcon as FIF)

# 导入血条校准模块
from health_bar_calibration import HealthBarCalibration

# 导入血条监控模块
from health_monitor import HealthMonitor, MonitorSignals

# 动态导入带空格的模块
import importlib.util

# 动态导入带空格的模块
module_name = "team_members(choice box)"
module_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "team_members(choice box).py")
spec = importlib.util.spec_from_file_location(module_name, module_path)
team_members_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(team_members_module)

# 从module中获取Team和TeamMember类
Team = team_members_module.Team
TeamMember = team_members_module.TeamMember

# 设置应用全局样式
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

# 定义配置文件名
# CONFIG_FILE = 'config.json'  # 已迁移到配置管理系统

# 自定义对话框类 - 完全参照示例代码
class ColorPickerMessageBox(MessageBoxBase):
    """ Custom message box for color picking """

    def __init__(self, member_name, parent=None):
        super().__init__(parent)
        self.titleLabel = SubtitleLabel(f'设置 {member_name} 的血条颜色', self)
        
        # 添加指南标签
        self.guideLabel = BodyLabel(
            '1. 将鼠标移动到游戏中该队友的血条上\n'
            '2. 选择血条最具代表性的颜色位置\n'
            '3. 按下空格键获取颜色\n'
            '4. 按ESC键取消操作'
        )
        self.guideLabel.setWordWrap(True)
        
        # 状态标签
        self.statusLabel = CaptionLabel("状态：等待获取颜色...")
        self.statusLabel.setTextColor("#1e88e5", QColor(30, 136, 229))
        
        # 预览区域
        previewLayout = QHBoxLayout()
        previewLabel = BodyLabel('颜色预览：')
        self.colorPreview = QFrame()
        self.colorPreview.setFixedSize(50, 20)
        self.colorPreview.setFrameShape(QFrame.Box)
        previewLayout.addWidget(previewLabel)
        previewLayout.addWidget(self.colorPreview)
        previewWidget = QWidget()
        previewWidget.setLayout(previewLayout)

        # 添加到视图布局
        self.viewLayout.addWidget(self.titleLabel)
        self.viewLayout.addWidget(self.guideLabel)
        self.viewLayout.addWidget(self.statusLabel)
        self.viewLayout.addWidget(previewWidget)

        # 修改按钮文本
        self.yesButton.setText('确定')
        self.cancelButton.setText('取消')

        # 设置最小宽度
        self.widget.setMinimumWidth(350)
        
        # 颜色获取状态和计时器
        self.color_captured = False
        self.key_check_timer = QTimer(self)
        self.key_check_timer.timeout.connect(self.check_keys_and_position)
        self.key_check_timer.start(100)
        
        # 存储成员名称
        self.member_name = member_name
        
    def check_keys_and_position(self):
        """检查键盘输入和鼠标位置"""
        import keyboard
        if keyboard.is_pressed('space'):
            # 防止重复处理
            if self.color_captured:
                return
            
            self.color_captured = True
            self.key_check_timer.stop()
            
            # 获取当前鼠标位置的屏幕像素颜色
            try:
                import pyautogui
                x, y = pyautogui.position()
                pixel_color = pyautogui.screenshot().getpixel((x, y))
                
                # 显示获取的颜色
                color_hex = "#{:02x}{:02x}{:02x}".format(pixel_color[0], pixel_color[1], pixel_color[2])
                self.colorPreview.setStyleSheet(f"background-color: {color_hex};")
                
                # --- 将RGB转换为BGR ---
                rgb_tuple = pixel_color[:3]
                bgr_values = (rgb_tuple[2], rgb_tuple[1], rgb_tuple[0]) # B, G, R
                
                # 创建颜色上下限（允许一定范围的变化）- 使用BGR值
                import numpy as np
                self.color_lower = np.array([max(0, c - 30) for c in bgr_values], dtype=np.uint8)
                self.color_upper = np.array([min(255, c + 30) for c in bgr_values], dtype=np.uint8)
                
                self.statusLabel.setText(f"状态：成功获取颜色！RGB: {rgb_tuple}")
                self.statusLabel.setTextColor("#2ecc71", QColor(46, 204, 113))
                
                # 延迟关闭对话框
                QTimer.singleShot(1500, lambda: self.accept())
                
            except Exception as e:
                self.statusLabel.setText(f"状态：获取颜色失败 - {str(e)}")
                self.statusLabel.setTextColor("#e74c3c", QColor(231, 76, 60))
                self.color_captured = False  # 重置状态，允许重试
                self.key_check_timer.start()  # 重新启动定时器
        
        elif keyboard.is_pressed('esc'):
            if not self.color_captured:  # 只有在未捕获颜色时才处理ESC键
                self.key_check_timer.stop()
                self.reject()

class HotkeySettingsMessageBox(MessageBoxBase):
    """ Custom message box for hotkey settings """

    def __init__(self, health_monitor, parent=None):
        super().__init__(parent)
        self.titleLabel = SubtitleLabel('监控快捷键设置', self)
        self.health_monitor = health_monitor
        self.parent_window = parent
        
        # 当前快捷键展示
        self.infoLabel = BodyLabel(f"当前快捷键设置:\n开始监控: {health_monitor.start_monitoring_hotkey}\n停止监控: {health_monitor.stop_monitoring_hotkey}")
        self.infoLabel.setWordWrap(True)
        
        # 设置表单
        form_widget = QWidget()
        form_layout = QGridLayout(form_widget)
        form_layout.setSpacing(10)
        
        # 开始监控输入
        self.start_label = BodyLabel("开始监控键:")
        self.start_input = LineEdit()
        self.start_input.setText(health_monitor.start_monitoring_hotkey)
        self.start_input.setPlaceholderText("按下快捷键组合")
        
        # 停止监控输入
        self.stop_label = BodyLabel("停止监控键:")
        self.stop_input = LineEdit()
        self.stop_input.setText(health_monitor.stop_monitoring_hotkey)
        self.stop_input.setPlaceholderText("按下快捷键组合")
        
        # 错误提示标签
        self.error_label = CaptionLabel("")
        self.error_label.setTextColor("#cf1010", QColor(255, 28, 32))
        self.error_label.hide()
        
        # 增加记录按钮以记录实际按键
        self.start_record = PushButton("记录")
        self.start_record.clicked.connect(lambda: self.record_hotkey('start'))
        
        self.stop_record = PushButton("记录")
        self.stop_record.clicked.connect(lambda: self.record_hotkey('stop'))
        
        # 添加到布局
        form_layout.addWidget(self.start_label, 0, 0)
        form_layout.addWidget(self.start_input, 0, 1)
        form_layout.addWidget(self.start_record, 0, 2)
        
        form_layout.addWidget(self.stop_label, 1, 0)
        form_layout.addWidget(self.stop_input, 1, 1)
        form_layout.addWidget(self.stop_record, 1, 2)
        
        # 将所有控件添加到视图布局
        self.viewLayout.addWidget(self.titleLabel)
        self.viewLayout.addWidget(self.infoLabel)
        self.viewLayout.addWidget(form_widget)
        self.viewLayout.addWidget(self.error_label)
        
        # 设置按钮文本
        self.yesButton.setText('保存')
        self.cancelButton.setText('取消')
        
        # 设置最小宽度
        self.widget.setMinimumWidth(400)
    
    def record_hotkey(self, which):
        """弹出对话框录入快捷键"""
        from PyQt5.QtGui import QKeySequence
        
        # 创建录入对话框
        dialog = MessageBoxBase(self)
        dialog.titleLabel = SubtitleLabel('录入快捷键', dialog)
        
        # 说明标签
        guide_label = BodyLabel('请按下新的快捷键组合（如 Ctrl+Alt+S）')
        key_label = BodyLabel('等待按键...')
        
        # 添加到视图布局
        dialog.viewLayout.addWidget(dialog.titleLabel)
        dialog.viewLayout.addWidget(guide_label)
        dialog.viewLayout.addWidget(key_label)
        
        # 设置按钮文本，初始时禁用确定按钮
        dialog.yesButton.setText('确定')
        dialog.yesButton.setEnabled(False)
        dialog.cancelButton.setText('取消')
        
        # 存储按键
        key_seq = {'text': ''}
        
        # 重写keyPressEvent处理按键
        def keyPressEvent(event):
            # 保存原始方法
            original_keyPressEvent = dialog.keyPressEvent
            
            key_text = ''
            modifiers = event.modifiers()
            if modifiers & Qt.ControlModifier:
                key_text += 'ctrl+'
            if modifiers & Qt.AltModifier:
                key_text += 'alt+'
            if modifiers & Qt.ShiftModifier:
                key_text += 'shift+'
            key = event.key()
            if key in (Qt.Key_Control, Qt.Key_Alt, Qt.Key_Shift):
                # 恢复原始方法并调用它
                dialog.keyPressEvent = original_keyPressEvent
                return original_keyPressEvent(event)
            key_name = QKeySequence(key).toString().lower()
            key_text += key_name
            key_seq['text'] = key_text
            key_label.setText(f'已录入: {key_text}')
            dialog.yesButton.setEnabled(True)
            
            # 恢复原始方法
            dialog.keyPressEvent = original_keyPressEvent
        
        # 保存原始方法
        original_method = dialog.keyPressEvent
        # 替换方法
        dialog.keyPressEvent = keyPressEvent
        
        # 显示对话框
        if dialog.exec():
            if key_seq['text']:
                if which == 'start':
                    self.start_input.setText(key_seq['text'])
                else:
                    self.stop_input.setText(key_seq['text'])
    
    def validate(self):
        """验证输入是否有效"""
        start_key = self.start_input.text()
        stop_key = self.stop_input.text()
        
        # 检查输入是否有效
        if not start_key or not stop_key:
            self.error_label.setText("快捷键不能为空")
            self.error_label.show()
            return False
            
        if start_key == stop_key:
            self.error_label.setText("开始和停止快捷键不能相同")
            self.error_label.show()
            return False
        
        # 尝试设置新的快捷键
        success = self.health_monitor.set_hotkeys(start_key, stop_key)
        
        if not success:
            self.error_label.setText("设置快捷键失败，请重试")
            self.error_label.show()
            return False
            
        return True

class TeammateSelectionMessageBox(MessageBoxBase):
    """ Custom message box for teammate selection """

    def __init__(self, title, team_members, parent=None):
        super().__init__(parent)
        self.titleLabel = SubtitleLabel(title, self)
        
        # 添加说明
        self.infoLabel = BodyLabel("请从列表中选择一个队友")
        
        # 创建队友列表
        self.listWidget = QListWidget(self)
        for i, member in enumerate(team_members):
            self.listWidget.addItem(f"{member.name} ({member.profession})")
        
        # 警告标签
        self.warningLabel = CaptionLabel("未选择任何队友")
        self.warningLabel.setTextColor("#cf1010", QColor(255, 28, 32))
        self.warningLabel.hide()  # 默认隐藏
        
        # 添加到视图布局
        self.viewLayout.addWidget(self.titleLabel)
        self.viewLayout.addWidget(self.infoLabel)
        self.viewLayout.addWidget(self.listWidget)
        self.viewLayout.addWidget(self.warningLabel)
        
        # 设置按钮文本
        self.yesButton.setText('选择')
        self.cancelButton.setText('取消')
        
        # 设置最小宽度
        self.widget.setMinimumWidth(350)
        
        # 存储队友列表
        self.team_members = team_members
        self.selected_index = -1
        
        # 连接列表点击事件
        self.listWidget.itemClicked.connect(self.on_item_clicked)
    
    def on_item_clicked(self, item):
        """列表项被点击时更新选择索引"""
        self.selected_index = self.listWidget.row(item)
        self.warningLabel.hide()  # 隐藏警告
    
    def get_selected_member(self):
        """获取选中的队友"""
        if self.selected_index >= 0 and self.selected_index < len(self.team_members):
            return self.team_members[self.selected_index]
        return None
        
    def validate(self):
        """验证是否选择了队友"""
        if self.selected_index >= 0:
            return True
        else:
            self.warningLabel.show()  # 显示警告
            return False

class UnifiedColorPickerMessageBox(MessageBoxBase):
    """ Custom message box for unified color picking """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.titleLabel = SubtitleLabel('统一设置所有队友的血条颜色', self)
        
        # 添加操作指南
        self.guideLabel = BodyLabel(
            '1. 将鼠标移动到游戏中任意一个队友的血条上\n'
            '2. 选择血条最具代表性的颜色位置\n'
            '3. 按下空格键获取颜色，此颜色将应用于所有队友\n'
            '4. 按ESC键取消操作'
        )
        self.guideLabel.setWordWrap(True)
        
        # 状态标签
        self.statusLabel = CaptionLabel("状态：等待获取颜色...")
        self.statusLabel.setTextColor("#1e88e5", QColor(30, 136, 229))
        
        # 预览区域
        previewLayout = QHBoxLayout()
        previewLabel = BodyLabel('颜色预览：')
        self.colorPreview = QFrame()
        self.colorPreview.setFixedSize(50, 20)
        self.colorPreview.setFrameShape(QFrame.Box)
        previewLayout.addWidget(previewLabel)
        previewLayout.addWidget(self.colorPreview)
        previewWidget = QWidget()
        previewWidget.setLayout(previewLayout)
        
        # 添加到视图布局
        self.viewLayout.addWidget(self.titleLabel)
        self.viewLayout.addWidget(self.guideLabel)
        self.viewLayout.addWidget(self.statusLabel)
        self.viewLayout.addWidget(previewWidget)
        
        # 设置按钮文本
        self.yesButton.setText('确定')
        self.cancelButton.setText('取消')
        
        # 设置最小宽度
        self.widget.setMinimumWidth(350)
        
        # 颜色获取状态和计时器
        self.color_captured = False
        self.key_check_timer = QTimer(self)
        self.key_check_timer.timeout.connect(self.check_keys_and_position)
        self.key_check_timer.start(100)
        
        # 存储获取的颜色值
        self.pixel_color_rgb = None

    def check_keys_and_position(self):
        """检查键盘输入和鼠标位置"""
        import keyboard
        if keyboard.is_pressed('space'):
            if self.color_captured:
                return
            
            self.color_captured = True
            self.key_check_timer.stop()
            
            try:
                import pyautogui
                x, y = pyautogui.position()
                self.pixel_color_rgb = pyautogui.screenshot().getpixel((x, y))[:3]  # 确保是RGB
                
                color_hex = "#{:02x}{:02x}{:02x}".format(
                    self.pixel_color_rgb[0], 
                    self.pixel_color_rgb[1], 
                    self.pixel_color_rgb[2]
                )
                self.colorPreview.setStyleSheet(f"background-color: {color_hex};")
                
                self.statusLabel.setText(f"状态：成功获取颜色！RGB: {self.pixel_color_rgb}")
                self.statusLabel.setTextColor("#2ecc71", QColor(46, 204, 113))
                
                # 延迟关闭对话框
                QTimer.singleShot(2000, lambda: self.accept())
                
            except Exception as e:
                self.statusLabel.setText(f"状态：获取颜色失败 - {str(e)}")
                self.statusLabel.setTextColor("#e74c3c", QColor(231, 76, 60))
                self.color_captured = False
                self.key_check_timer.start()
        
        elif keyboard.is_pressed('esc'):
            if not self.color_captured:
                self.key_check_timer.stop()
                self.reject()

class MainWindow(FluentWindow):
    def __init__(self):
        """初始化主窗口"""
        super().__init__()
        
        # 初始化 pygame mixer
        try:
            pygame.mixer.init()
            pygame.mixer.set_num_channels(16) # 设置足够多的声道
        except pygame.error as e:
            print(f"Pygame mixer 初始化失败: {e}")
            # 可以选择禁用语音功能或显示错误提示
            InfoBar.error(
                title='音频初始化失败',
                content='无法初始化音频播放组件 (pygame.mixer)，语音播报功能将不可用。',
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=5000,
                parent=self
            )
        
        self._icon_capture_show_selection_timer = None
        self._icon_capture_do_grab_timer = None
        self._icon_capture_rect = None # Store the rect between timer calls
        
        # --- 添加缺失的语音参数初始化 ---
        # 初始化语音参数属性 - 使用滑块的默认值
        # 语速: slider 0-10 -> rate -50% to +50% -> + (value*10 - 50) %
        default_rate_value = 5
        self.voice_rate_param = f'+{default_rate_value * 10 - 50}%'
        # 音量: slider 0-100 -> volume -50% to +50% -> + (value - 50) %
        default_volume_value = 80
        self.voice_volume_param = f'+{default_volume_value - 50}%'
        # --- 初始化结束 ---
        
        # 设置窗口标题和大小
        self.setWindowTitle('VitalSync')
        self.resize(1200, 500) # 将高度从 800 调整为 700
        
        # 设置应用强调色 - 使用截图中的青绿色
        setThemeColor(QColor(0, 168, 174))
        
        # 启用亚克力效果
        self.navigationInterface.setAcrylicEnabled(True)
        
        # 初始化队友管理相关属性
        self.team = Team()  # 创建Team实例
        self.selection_box = None # 屏幕选择框
        
        # 初始化全局默认血条颜色
        self.default_hp_color_lower = None  # 默认血条颜色下限
        self.default_hp_color_upper = None  # 默认血条颜色上限
        self.load_default_colors()  # 从配置加载默认颜色设置
        
        # 初始化健康监控相关属性
        self.health_monitor = HealthMonitor(self.team)  # 创建健康监控实例
        # 连接监控信号
        self.health_monitor.signals.update_signal.connect(self.update_health_display)
        self.health_monitor.signals.status_signal.connect(self.update_monitor_status)
        
        # 创建界面
        self.teamRecognitionInterface = QWidget()
        self.teamRecognitionInterface.setObjectName("teamRecognitionInterface")
        
        self.healthMonitorInterface = QWidget()
        self.healthMonitorInterface.setObjectName("healthMonitorInterface")
        
        self.assistInterface = QWidget()
        self.assistInterface.setObjectName("assistInterface")
        
        self.settingsInterface = QWidget()
        self.settingsInterface.setObjectName("settingsInterface")
        
        # 新增：语音设置界面实例
        self.voiceSettingsInterface = QWidget()
        self.voiceSettingsInterface.setObjectName("voiceSettingsInterface")
        
        # 初始化界面
        self.initTeamRecognitionInterface()
        self.initHealthMonitorInterface()
        self.initAssistInterface()
        self.initSettingsInterface()
        self.initVoiceSettingsInterface() # 新增：调用语音设置界面初始化
        
        # 初始化导航
        self.initNavigation()
        
        # --- 加载设置 ---
        self.load_settings() # 在UI初始化后加载设置
        
        # 显示提示信息
        InfoBar.success(
            title='初始化完成',
            content='系统已准备就绪',
            orient=Qt.Horizontal,
            isClosable=True,
            position=InfoBarPosition.TOP,
            duration=2000,
            parent=self
        )
        
        # 在__init__方法末尾添加：
        self.load_teammates()
        
        # 初始化语音队列和工作线程
        self.speech_queue = queue.Queue()
        self.active_speech = {} # 用于跟踪正在播放的语音及其资源
        self.speech_worker_thread = threading.Thread(target=self._speech_worker_loop, daemon=True)
        self.speech_worker_thread.start()
        
        # 设置一个定时器来处理 Pygame 事件和清理
        self.pygame_event_timer = QTimer(self)
        self.pygame_event_timer.timeout.connect(self._process_pygame_events)
        self.pygame_event_timer.start(100) # 每 100ms 检查一次
    
    def initNavigation(self):
        """初始化导航栏"""
        # 添加子界面
        self.addSubInterface(self.teamRecognitionInterface, FIF.PEOPLE, '队员识别')
        self.addSubInterface(self.healthMonitorInterface, FIF.HEART, '血条监控')
        self.addSubInterface(self.assistInterface, FIF.IOT, '辅助功能')
        self.addSubInterface(self.voiceSettingsInterface, FIF.MICROPHONE, '语音设置') # 使用 FIF.MICROPHONE 图标
        
        # 添加底部界面
        self.addSubInterface(
            self.settingsInterface, 
            FIF.SETTING, 
            '系统设置',
            NavigationItemPosition.BOTTOM
        )

    def initTeamRecognitionInterface(self):
        """初始化队员识别界面"""
        layout = QVBoxLayout(self.teamRecognitionInterface)
        layout.setSpacing(24)  # 增加垂直间距
        layout.setContentsMargins(24, 24, 24, 24)  # 增加外边距
        
        # 创建顶部水平布局，包含职业图标管理和队友管理
        topLayout = QHBoxLayout()
        topLayout.setSpacing(24)  # 增加水平间距
        
        # ========== 左侧：职业图标管理 ==========
        iconCard = HeaderCardWidget(self.teamRecognitionInterface)
        iconCard.setTitle("职业图标管理")
        iconCard.setFixedHeight(200)  # 适当减少卡片高度
        iconLayout = QVBoxLayout()
        iconLayout.setSpacing(15)  # 增加垂直间距
        iconLayout.setContentsMargins(0, 10, 0, 10)  # 增加内边距
        
        # 按钮区域 - 也使用网格布局
        btnLayout = QGridLayout()
        btnLayout.setSpacing(15)  # 增加按钮间距
        
        addIconBtn = PrimaryPushButton('添加图标')
        addIconBtn.setIcon(FIF.ADD)
        addIconBtn.setFixedWidth(140)  # 显著增加按钮宽度
        addIconBtn.setMinimumHeight(36)  # 设置最小高度
        
        captureIconBtn = PushButton('截取图标')
        captureIconBtn.setIcon(FIF.CAMERA) # 使用 CAMERA 图标替代 SCREENSHOT
        captureIconBtn.setFixedWidth(140)  # 显著增加按钮宽度
        captureIconBtn.setMinimumHeight(36)  # 设置最小高度
        
        manageIconsBtn = PushButton('管理图标')
        manageIconsBtn.setIcon(FIF.SETTING)
        manageIconsBtn.setFixedWidth(140)  # 显著增加按钮宽度
        manageIconsBtn.setMinimumHeight(36)  # 设置最小高度
        
        # 连接按钮事件
        addIconBtn.clicked.connect(self.addProfessionIcon)
        captureIconBtn.clicked.connect(self.captureScreenIcon)
        manageIconsBtn.clicked.connect(self.loadProfessionIcons)
        
        # 将按钮添加到网格布局
        btnLayout.addWidget(addIconBtn, 0, 0)
        btnLayout.addWidget(captureIconBtn, 0, 1)
        btnLayout.addWidget(manageIconsBtn, 0, 2)
        
        # 显示图标数量信息
        profession_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "profession_icons")
        
        # 检查文件夹是否存在
        if not os.path.exists(profession_path):
            os.makedirs(profession_path)
            icon_count = 0
        else:
            icon_count = len([f for f in os.listdir(profession_path) if f.endswith(('.png', '.jpg', '.jpeg'))])
            
        infoLabel = BodyLabel(f'已加载 {icon_count} 个职业图标')
        infoLabel.setStyleSheet("color: #666; font-size: 13px;")  # 设置样式，使其显示更清晰
        infoLabel.setAlignment(Qt.AlignCenter)  # 居中对齐
        
        # 添加到卡片布局
        iconLayout.addLayout(btnLayout)
        iconLayout.addWidget(infoLabel)
        iconLayout.addStretch(1)  # 添加弹性空间，将内容推向顶部，使标签居中
        iconCardWidget = QWidget()
        iconCardWidget.setLayout(iconLayout)
        iconCard.viewLayout.addWidget(iconCardWidget)
        self.iconCardWidget = iconCardWidget
        
        # ========== 右侧：队友管理 ==========
        teammateCard = HeaderCardWidget(self.teamRecognitionInterface)
        teammateCard.setTitle("队友管理")
        teammateCard.setFixedHeight(200)  # 适当减少卡片高度
        teammateLayout = QVBoxLayout()
        teammateLayout.setSpacing(30)  # 增加垂直间距
        teammateLayout.setContentsMargins(0, 0, 0, 10)  # 顶部margin设为0，整体上移
        
        # 队友管理按钮区域 - 使用网格布局确保均匀分布
        teammateBtnLayout = QGridLayout()  # 改回网格布局
        teammateBtnLayout.setSpacing(18)  # 进一步增加基础间距 (原为15)
        teammateBtnLayout.setVerticalSpacing(48)  # 大幅增大垂直间距 (原为20)
        teammateBtnLayout.setContentsMargins(10, 0, 10, 0)  # 保持或调整水平内边距
        
        addTeammateBtn = PrimaryPushButton('添加队友')
        addTeammateBtn.setIcon(FIF.ADD)
        addTeammateBtn.setFixedWidth(115)  # 进一步减少按钮宽度 (原为125)
        addTeammateBtn.setMinimumHeight(36)  # 保持按钮高度
        
        removeTeammateBtn = PushButton('移除队友')
        removeTeammateBtn.setIcon(FIF.REMOVE)
        removeTeammateBtn.setFixedWidth(115)  # 进一步减少按钮宽度 (原为125)
        removeTeammateBtn.setMinimumHeight(36)  # 保持按钮高度
        
        loadTeammateBtn = PushButton('加载队友')
        loadTeammateBtn.setIcon(FIF.DOWNLOAD)
        loadTeammateBtn.setFixedWidth(115)  # 进一步减少按钮宽度 (原为125)
        loadTeammateBtn.setMinimumHeight(36)  # 保持按钮高度
        
        clearAllTeammatesBtn = PushButton('清除全部')
        clearAllTeammatesBtn.setIcon(FIF.DELETE)
        clearAllTeammatesBtn.setFixedWidth(115)  # 进一步减少按钮宽度 (原为125)
        clearAllTeammatesBtn.setMinimumHeight(36)  # 保持按钮高度
        
        # 连接按钮事件
        addTeammateBtn.clicked.connect(self.addTeammate)
        removeTeammateBtn.clicked.connect(self.removeTeammate)
        loadTeammateBtn.clicked.connect(self.loadTeammate)
        clearAllTeammatesBtn.clicked.connect(self.clearAllTeammates)
        
        # 使用网格布局均匀排列按钮，2行2列，修正行号并增加间距
        teammateBtnLayout.addWidget(addTeammateBtn, 0, 0)      # 第1行第1列
        teammateBtnLayout.addWidget(removeTeammateBtn, 0, 1)   # 第1行第2列
        teammateBtnLayout.addWidget(loadTeammateBtn, 1, 0)     # 第2行第1列
        teammateBtnLayout.addWidget(clearAllTeammatesBtn, 1, 1) # 第2行第2列
        
        # 队友信息显示
        teammateInfoLabel = BodyLabel('')
        teammateInfoLabel.setObjectName("teammateInfoLabel")  # 设置对象名以便更新时查找
        teammateInfoLabel.setWordWrap(True)  # 允许文字换行
        teammateInfoLabel.setStyleSheet("color: #666; font-size: 13px;")  # 设置样式，使其显示更清晰
        teammateInfoLabel.setAlignment(Qt.AlignCenter)  # 居中对齐
        
        # 添加到卡片布局
        teammateLayout.addLayout(teammateBtnLayout)
        teammateLayout.addWidget(teammateInfoLabel)
        teammateLayout.addStretch(1)  # 添加弹性空间，将内容推向顶部，使标签居中
        teammateCardWidget = QWidget()
        teammateCardWidget.setLayout(teammateLayout)
        teammateCard.viewLayout.addWidget(teammateCardWidget)
        
        # 将两个卡片添加到顶部布局
        topLayout.addWidget(iconCard, 1) # 设置伸展因子为1
        topLayout.addWidget(teammateCard, 1) # 设置伸展因子为1
        
        # ========== 识别队友区域 ==========
        recognitionCard = HeaderCardWidget(self.teamRecognitionInterface)
        recognitionCard.setTitle("识别队友")
        recognitionLayout = QVBoxLayout()
        recognitionLayout.setSpacing(18)  # 增加垂直间距
        recognitionLayout.setContentsMargins(0, 8, 0, 8)  # 增加内边距
        
        # 控制面板区域
        controlsPanel = QFrame()
        controlsPanel.setObjectName("cardFrame")
        controlsPanelLayout = QHBoxLayout(controlsPanel)
        controlsPanelLayout.setSpacing(16)
        controlsPanelLayout.setContentsMargins(16, 12, 16, 12)  # 增加内边距使内容更加突出
        
        # 选择识别位置按钮
        selectPositionBtn = PrimaryPushButton("选择识别位置")
        selectPositionBtn.setIcon(FIF.EDIT)
        selectPositionBtn.setMinimumWidth(160)  # 增加按钮宽度
        
        # 识别状态显示
        statusLabel = BodyLabel("状态: 未开始识别")
        statusLabel.setStyleSheet("color: #888; font-size: 14px;")  # 调整样式
        
        controlsPanelLayout.addWidget(selectPositionBtn)
        controlsPanelLayout.addWidget(statusLabel)
        controlsPanelLayout.addStretch(1)
        
        # 预览区域
        previewArea = QFrame()
        previewArea.setObjectName("cardFrame")
        # 修改：使用浅色背景和深色文字
        previewArea.setStyleSheet("#cardFrame{background-color: #f8f9fa; color: #333333; border-radius: 10px; border: 1px solid #e0e0e0;}") 
        previewLayout = QVBoxLayout(previewArea)
        previewLayout.setContentsMargins(10, 10, 10, 10)  # 添加内边距
        
        previewTitle = QLabel("队友信息预览")
        previewTitle.setAlignment(Qt.AlignCenter)
        # 修改：标题文字颜色改为深色
        previewTitle.setStyleSheet("color: #333333; font-size: 16px; font-weight: bold; margin-bottom: 10px;")
        
        # 创建滚动区域
        scrollArea = ScrollArea()
        scrollArea.setWidgetResizable(True)
        scrollArea.setStyleSheet("background: transparent; border: none;")
        
        scrollContent = QWidget()
        scrollLayout = QVBoxLayout(scrollContent)
        scrollLayout.setContentsMargins(0, 0, 0, 0)
        scrollLayout.setSpacing(8)
        
        # 创建队友信息标签
        self.teammateInfoPreview = QLabel("加载队友信息中...")
        self.teammateInfoPreview.setWordWrap(True)
        # 修改：默认文字颜色改为深色
        self.teammateInfoPreview.setStyleSheet("color: #333333; font-size: 14px;") 
        scrollLayout.addWidget(self.teammateInfoPreview)
        
        scrollArea.setWidget(scrollContent)
        
        previewLayout.addWidget(previewTitle)
        previewLayout.addWidget(scrollArea)
        
        # 添加更新按钮
        updateInfoBtn = PushButton("刷新队友信息")
        updateInfoBtn.setIcon(FIF.SYNC)
        updateInfoBtn.clicked.connect(self.update_teammate_preview)
        previewLayout.addWidget(updateInfoBtn)
        
        # 底部控制按钮
        buttonLayout = QHBoxLayout()
        buttonLayout.setSpacing(16)
        
        startBtn = PrimaryPushButton("开始识别")
        startBtn.setIcon(FIF.PLAY)
        startBtn.setMinimumWidth(130)  # 增加按钮宽度
        
        stopBtn = PushButton("停止")
        stopBtn.setIcon(FIF.CANCEL)
        stopBtn.setMinimumWidth(130)  # 增加按钮宽度
        
        saveBtn = PushButton("导出配置")
        saveBtn.setIcon(FIF.SAVE)
        saveBtn.setMinimumWidth(130)  # 增加按钮宽度
        
        # 连接按钮事件
        selectPositionBtn.clicked.connect(self.select_recognition_position)
        startBtn.clicked.connect(self.start_recognition_from_calibration)
        stopBtn.clicked.connect(self.stop_recognition)
        saveBtn.clicked.connect(self.export_recognition_config)
        
        # 然后继续添加按钮到布局
        buttonLayout.addStretch(1)
        buttonLayout.addWidget(startBtn)
        buttonLayout.addWidget(stopBtn)
        buttonLayout.addWidget(saveBtn)
        buttonLayout.addStretch(1)
        
        # 添加到识别布局
        recognitionLayout.addWidget(controlsPanel)
        recognitionLayout.addWidget(previewArea)
        recognitionLayout.addLayout(buttonLayout)
        
        recognitionCardWidget = QWidget()
        recognitionCardWidget.setLayout(recognitionLayout)
        recognitionCard.viewLayout.addWidget(recognitionCardWidget)
        
        # 添加到主布局
        layout.addLayout(topLayout)
        layout.addWidget(recognitionCard, 1)  # 1表示伸展因子，让这个区域占据更多空间
        
    def loadProfessionIcons(self):
        """加载职业图标并显示管理对话框"""
        # 使用自定义无边框对话框
        manage_dialog = ProfessionIconsManageDialog(self)
        manage_dialog.exec()
    
    def deleteProfessionIcon(self, icon_file, frame, dialog=None):
        """删除职业图标"""
        profession_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "profession_icons")
        icon_path = os.path.join(profession_path, icon_file)
        
        # 确认删除
        confirm_dialog = ConfirmMessageBox(
            "确认删除",
            f"确定要删除职业图标 {os.path.splitext(icon_file)[0]} 吗？",
            self if not dialog else dialog # Keep ConfirmMessageBox parented to dialog for modality
        )
        
        if confirm_dialog.exec():
            try:
                # 删除文件
                os.remove(icon_path)
                # 从UI中移除
                frame.setParent(None)
                frame.deleteLater()
                # 更新图标计数
                self.updateIconCount()
                # 提示成功
                InfoBar.success(
                    title='删除成功',
                    content=f'已删除职业图标 {os.path.splitext(icon_file)[0]}',
                    orient=Qt.Horizontal,
                    isClosable=True,
                    position=InfoBarPosition.TOP,
                    duration=2000,
                    parent=self  # Ensure InfoBar is parented to MainWindow
                )
            except Exception as e:
                # 删除失败提示
                InfoBar.error(
                    title='删除失败',
                    content=str(e),
                    orient=Qt.Horizontal,
                    isClosable=True,
                    position=InfoBarPosition.TOP,
                    duration=3000,
                    parent=self  # Ensure InfoBar is parented to MainWindow
                )

    def initHealthMonitorInterface(self):
        """初始化血条监控界面"""
        layout = QVBoxLayout(self.healthMonitorInterface)
        layout.setSpacing(16)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # 标题和状态信息
        titleLayout = QHBoxLayout()
        titleLabel = StrongBodyLabel("血条实时监控")
        titleLabel.setStyleSheet("font-size: 18px; font-weight: bold;")
        
        self.monitor_status_label = BodyLabel("准备就绪")
        self.monitor_status_label.setStyleSheet("color: #3498db;")
        titleLayout.addWidget(titleLabel)
        titleLayout.addStretch(1)
        titleLayout.addWidget(self.monitor_status_label)
        
        # 控制按钮区域
        controlLayout = QHBoxLayout()
        
        startMonitorBtn = PrimaryPushButton("开始监控")
        startMonitorBtn.setIcon(FIF.PLAY)
        startMonitorBtn.setMinimumWidth(120)
        
        stopMonitorBtn = PushButton("停止监控")
        stopMonitorBtn.setIcon(FIF.CLOSE)
        stopMonitorBtn.setMinimumWidth(120)
        
        # 新增：设置血条颜色按钮
        setColorBtn = PushButton("设置血条颜色")
        setColorBtn.setIcon(FIF.PALETTE) # 使用 PALETTE 图标替代 COLOR
        setColorBtn.setMinimumWidth(120)
        
        # 新增：统一设置血条颜色按钮
        setAllColorsBtn = PushButton("统一设置颜色")
        setAllColorsBtn.setIcon(FIF.BRUSH) # 使用 BRUSH 图标
        setAllColorsBtn.setMinimumWidth(120)
        
        # 连接按钮事件
        startMonitorBtn.clicked.connect(self.health_monitor.start_monitoring)
        stopMonitorBtn.clicked.connect(self.health_monitor.stop_monitoring)
        setColorBtn.clicked.connect(self.setTeammateHealthBarColor)  # 连接到单个设置方法
        setAllColorsBtn.clicked.connect(self.handleSetAllTeammatesColor) # 连接到统一设置方法
        
        controlLayout.addWidget(startMonitorBtn)
        controlLayout.addWidget(stopMonitorBtn)
        controlLayout.addWidget(setColorBtn)  # 添加单个设置按钮
        controlLayout.addWidget(setAllColorsBtn) # 添加统一设置按钮
        controlLayout.addStretch(1)
        
        # 血条展示区域
        self.health_bars_frame = QFrame()
        self.health_bars_frame.setObjectName("cardFrame")
        self.health_bars_frame.setStyleSheet("QFrame#cardFrame { background-color: rgba(240, 240, 240, 0.7); border-radius: 8px; padding: 10px; }")
        healthBarsLayout = QVBoxLayout(self.health_bars_frame)
        healthBarsLayout.setSpacing(12)
        healthBarsLayout.setContentsMargins(15, 15, 15, 15)
        
        # 初始化血条UI
        self.init_health_bars_ui()
        
        # 添加到监控布局
        layout.addLayout(titleLayout)
        layout.addLayout(controlLayout)
        layout.addWidget(self.health_bars_frame, 1)  # 将监控卡片设置为可伸展，占用更多空间
        
        # 设置卡片
        settingsCard = HeaderCardWidget(self.healthMonitorInterface)
        settingsCard.setTitle("血条监控设置")
        
        settingsLayout = QVBoxLayout()
        settingsLayout.setSpacing(12)
        
        # 基本设置组
        paramsGroup = QGroupBox("监控参数", self.healthMonitorInterface)
        paramsGroupLayout = QVBoxLayout()
        
        # 阈值设置
        thresholdLayout = QHBoxLayout()
        thresholdLabel = BodyLabel(f"血条阈值: {int(self.health_monitor.health_threshold)}%")
        thresholdSlider = Slider(Qt.Horizontal)
        thresholdSlider.setRange(0, 100)
        thresholdSlider.setValue(int(self.health_monitor.health_threshold))
        thresholdLayout.addWidget(thresholdLabel)
        thresholdLayout.addWidget(thresholdSlider)
        thresholdSlider.valueChanged.connect(lambda v: self.update_health_threshold(v, thresholdLabel))
        
        # 采样率设置
        samplingLayout = QHBoxLayout()
        samplingLabel = BodyLabel("采样率 (fps):")
        samplingSpinBox = SpinBox()
        samplingSpinBox.setRange(1, 60)
        samplingSpinBox.setValue(10)
        samplingLayout.addWidget(samplingLabel)
        samplingLayout.addWidget(samplingSpinBox)
        
        # 添加所有参数设置
        paramsGroupLayout.addLayout(thresholdLayout)
        paramsGroupLayout.addLayout(samplingLayout)
        
        # 自动点击低血量队友功能开关
        autoClickLayout = QHBoxLayout()
        autoClickLabel = BodyLabel("自动点击低血量队友:")
        self.autoClickSwitch = SwitchButton()
        # 从 HealthMonitor 加载初始状态
        if hasattr(self, 'health_monitor') and hasattr(self.health_monitor, 'auto_select_enabled'):
            self.autoClickSwitch.setChecked(self.health_monitor.auto_select_enabled)
        else:
            self.autoClickSwitch.setChecked(False) # 默认关闭
        
        # 新增：职业优先级下拉框
        priorityLabel = BodyLabel("优先职业:")
        self.priorityComboBox = ComboBox()
        self.priorityComboBox.setFixedWidth(120)
        # 加载所有职业选项
        self.load_profession_options()
        # 设置当前选中值
        if hasattr(self, 'health_monitor') and hasattr(self.health_monitor, 'priority_profession'):
            priority_index = self.priorityComboBox.findText(self.health_monitor.priority_profession)
            if priority_index >= 0:
                self.priorityComboBox.setCurrentIndex(priority_index)
        
        # 连接信号
        self.autoClickSwitch.checkedChanged.connect(self.toggle_auto_click_low_health)
        self.priorityComboBox.currentTextChanged.connect(self.update_priority_profession)
        
        autoClickLayout.addWidget(autoClickLabel)
        autoClickLayout.addWidget(self.autoClickSwitch)
        autoClickLayout.addSpacing(20)  # 增加间距
        autoClickLayout.addWidget(priorityLabel)
        autoClickLayout.addWidget(self.priorityComboBox)
        autoClickLayout.addStretch(1)
        paramsGroupLayout.addLayout(autoClickLayout) # 添加到参数组布局
        
        paramsGroup.setLayout(paramsGroupLayout)
        
        # 添加到主设置布局
        settingsLayout.addWidget(paramsGroup)
        settingsCardWidget = QWidget()
        settingsCardWidget.setLayout(settingsLayout)
        settingsCard.viewLayout.addWidget(settingsCardWidget)
        
        # 添加卡片到主布局，但设置较小的高度比例
        layout.addWidget(settingsCard)
        
        # 更新采样率设置
        samplingSpinBox.valueChanged.connect(self.update_sampling_rate)
    
    def init_health_bars_ui(self):
        """初始化血条UI显示"""
        if not self.health_bars_frame:
            return

        # 清除现有布局中的所有组件
        current_layout = self.health_bars_frame.layout()
        if current_layout is not None:
            while current_layout.count():
                item = current_layout.takeAt(0)
                widget = item.widget()
                if widget:
                    widget.deleteLater()
        else:
            # 如果布局不存在，则创建一个新的
            new_layout = QVBoxLayout(self.health_bars_frame)
            new_layout.setSpacing(12)
            new_layout.setContentsMargins(15, 15, 15, 15)
            self.health_bars_frame.setLayout(new_layout) # 设置新布局
        
        # --- 新增：按血条 y1, x1 坐标对队员进行排序 ---
        sorted_members = sorted(self.team.members, key=lambda m: (m.y1, m.x1))
        
        # 添加队友信息卡片
        for i, member in enumerate(sorted_members): # 使用排序后的列表
            self.add_health_bar_card(i, member.name, member.profession)
            
        # 如果没有队友，显示提示信息
        if not self.team.members and self.health_bars_frame.layout() is not None: # 检查原始列表判断是否有队友
            noMemberLabel = StrongBodyLabel("没有队友信息。请在队员识别页面添加队友。")
            noMemberLabel.setAlignment(Qt.AlignCenter)
            self.health_bars_frame.layout().addWidget(noMemberLabel)
        
        # 添加：强制更新框架，确保UI刷新
        self.health_bars_frame.update()
    
    def add_health_bar_card(self, index, name, profession):
        """添加血条卡片
        
        参数:
            index: 队友索引
            name: 队友名称
            profession: 队友职业
        """
        # 创建水平布局，每一行一个队员
        memberCard = QFrame()
        memberCard.setObjectName(f"member_card_{index}")
        memberCard.setFixedHeight(60)  # 设置固定高度
        memberCard.setStyleSheet("background-color: transparent;")
        memberLayout = QHBoxLayout(memberCard)
        memberLayout.setContentsMargins(5, 0, 5, 0)
        memberLayout.setSpacing(10)
        
        # 队员编号和名称 - 使用实际名称
        nameLabel = StrongBodyLabel(name)
        nameLabel.setObjectName(f"name_label_{index}")
        nameLabel.setStyleSheet("font-size: 14px; font-weight: bold;")
        nameLabel.setFixedWidth(80)
        
        # 修改：直接显示识别到的职业名称
        roleLabel = BodyLabel(str(profession)) # 确保是字符串
        roleLabel.setStyleSheet("color: #666; font-size: 12px;")
        roleLabel.setFixedWidth(60)
        roleLabel.setToolTip(str(profession)) # 添加悬浮提示显示完整职业名
        
        # 血条容器
        healthBarContainer = QFrame()
        healthBarContainer.setFixedHeight(25)
        healthBarContainer.setStyleSheet("background-color: #333; border-radius: 5px;")
        # --- 添加：设置最大宽度 --- 
        MAX_WIDTH = 300  # 与 update_health_display 中保持一致
        healthBarContainer.setMaximumWidth(MAX_WIDTH) 
        # --- 结束添加 ---
        healthBarContainerLayout = QHBoxLayout(healthBarContainer)
        healthBarContainerLayout.setContentsMargins(2, 2, 2, 2)
        healthBarContainerLayout.setSpacing(0)
        
        # 血条
        healthBar = QFrame()
        healthBar.setObjectName(f"health_bar_{index}")
        healthBar.setFixedHeight(21)
        
        # 根据索引设置不同颜色
        color = "#2ecc71"  # 绿色 (默认，表示90%)
        if index == 1:
            color = "#2ecc71"  # 绿色 (70%)
        elif index == 2:
            color = "#f39c12"  # 黄色 (50%)
        elif index == 3:
            color = "#e74c3c"  # 红色 (30%)
        elif index == 4:
            color = "#e74c3c"  # 红色 (10%)
        
        # 设置默认百分比
        default_percentage = 90
        if index == 1:
            default_percentage = 70
        elif index == 2:
            default_percentage = 50
        elif index == 3:
            default_percentage = 30
        elif index == 4:
            default_percentage = 10
        
        # 设置血条缩放因子和最大宽度
        SCALE_FACTOR = 3
        MAX_WIDTH = 300  # 血条最大宽度
        
        # 计算血条宽度
        bar_width = min(int(default_percentage * SCALE_FACTOR), MAX_WIDTH)
        print(f"队员{index+1} 初始血条宽度: {bar_width}px (血量: {default_percentage}%)")
        
        healthBar.setStyleSheet(f"background-color: {color}; border-radius: 3px;")
        healthBar.setFixedWidth(bar_width)  # 使用计算的宽度
        
        healthBarContainerLayout.addWidget(healthBar)
        healthBarContainerLayout.addStretch(1)
        
        # 血量百分比
        valueLabel = StrongBodyLabel(f"{default_percentage}%")
        valueLabel.setObjectName(f"value_label_{index}")
        valueLabel.setStyleSheet(f"color: {color}; font-weight: bold; font-size: 15px;")
        valueLabel.setAlignment(Qt.AlignCenter)
        valueLabel.setFixedWidth(60)
        
        # 添加调试标签 - 开发期间使用，显示实际内部存储的血量
        debugLabel = QLabel(f"dbg:ok")
        debugLabel.setObjectName(f"debug_label_{index}")
        debugLabel.setStyleSheet("color: #999; font-size: 8px;")
        debugLabel.setFixedWidth(50)
        
        # 添加到卡片布局
        memberLayout.addWidget(nameLabel)
        memberLayout.addWidget(roleLabel)
        memberLayout.addWidget(healthBarContainer)
        memberLayout.addWidget(valueLabel)
        memberLayout.addWidget(debugLabel)  # 添加调试标签
        
        # 添加到主布局
        self.health_bars_frame.layout().addWidget(memberCard)
        
        # 添加分隔线（除了最后一个）
        if index < len(self.team.members) - 1:
            separator = QFrame()
            separator.setFrameShape(QFrame.HLine)
            separator.setFrameShadow(QFrame.Sunken)
            separator.setStyleSheet("background-color: #e0e0e0;")
            separator.setFixedHeight(1)
            self.health_bars_frame.layout().addWidget(separator)
    
    def update_sampling_rate(self, value):
        """更新监控采样率
        
        参数:
            value: 采样率值（fps）
        """
        if hasattr(self, 'health_monitor'):
            # 转换为更新间隔（秒）
            interval = 1.0 / value if value > 0 else 0.1
            self.health_monitor.update_interval = interval
            self.update_monitor_status(f"采样率已更新: {value} fps (更新间隔: {interval:.2f}秒)")
    
    def show_hotkey_settings(self):
        """显示快捷键设置对话框"""
        dialog = HotkeySettingsMessageBox(self.health_monitor, self)
        dialog.exec()
    
    def show_error_message(self, message):
        """显示错误消息
        
        参数:
            message: 错误消息
        """
        InfoBar.error(
            title='错误',
            content=message,
            orient=Qt.Horizontal,
            isClosable=True,
            position=InfoBarPosition.TOP,
            duration=3000,
            parent=self
        )
    
    def set_auto_select(self, enabled):
        """设置自动选择功能
        
        参数:
            enabled: 是否启用
        """
        if hasattr(self, 'health_monitor'):
            self.health_monitor.auto_select_enabled = enabled
            self.health_monitor.save_auto_select_config()
            status = "启用" if enabled else "禁用"
            self.update_monitor_status(f"自动选择功能已{status}")

    def initAssistInterface(self):
        """初始化辅助功能界面"""
        layout = QVBoxLayout(self.assistInterface)
        layout.setSpacing(16)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # 左右布局，左侧为主要功能，右侧为次要功能
        mainLayout = QHBoxLayout()
        mainLayout.setSpacing(16)
        
        # 左侧布局 - 现在只包含快捷键设置
        leftLayout = QVBoxLayout()
        leftLayout.setSpacing(16)
        
        # 快捷键卡片
        hotkeyCard = HeaderCardWidget(self.assistInterface)
        hotkeyCard.setTitle("快捷键设置")
        
        hotkeyLayout = QVBoxLayout()
        hotkeyLayout.setSpacing(12)
        
        # 提示信息
        hotkey_info = BodyLabel("设置全局快捷键用于快速操作。点击\"记录\"按钮后，按下想要设置的键。")
        hotkey_info.setWordWrap(True)
        
        # 快捷键表格
        hotkeyGridLayout = QGridLayout()
        hotkeyGridLayout.setSpacing(12)
        
        # 开始监控
        startMonitorLabel = BodyLabel('开始监控:')
        startMonitorEdit = LineEdit()
        startMonitorEdit.setReadOnly(True)
        startMonitorEdit.setText(self.health_monitor.start_monitoring_hotkey)
        startMonitorRecordBtn = PushButton('记录')
        
        # 停止监控
        stopMonitorLabel = BodyLabel('停止监控:')
        stopMonitorEdit = LineEdit()
        stopMonitorEdit.setReadOnly(True)
        stopMonitorEdit.setText(self.health_monitor.stop_monitoring_hotkey)
        stopMonitorRecordBtn = PushButton('记录')
        
        # 绑定"记录"按钮事件，使用事件过滤器方式
        startMonitorRecordBtn.clicked.connect(lambda: self.install_hotkey_event_filter(startMonitorEdit, stopMonitorEdit, 'start'))
        stopMonitorRecordBtn.clicked.connect(lambda: self.install_hotkey_event_filter(stopMonitorEdit, startMonitorEdit, 'stop'))
        
        # 添加到网格
        hotkeyGridLayout.addWidget(startMonitorLabel, 0, 0)
        hotkeyGridLayout.addWidget(startMonitorEdit, 0, 1)
        hotkeyGridLayout.addWidget(startMonitorRecordBtn, 0, 2)
        
        hotkeyGridLayout.addWidget(stopMonitorLabel, 1, 0)
        hotkeyGridLayout.addWidget(stopMonitorEdit, 1, 1)
        hotkeyGridLayout.addWidget(stopMonitorRecordBtn, 1, 2)
        
        # 添加所有组件到快捷键卡片
        hotkeyLayout.addWidget(hotkey_info)
        hotkeyLayout.addLayout(hotkeyGridLayout)
        # 增加状态信息标签
        self.hotkeyStatusLabel = BodyLabel('')
        hotkeyLayout.addWidget(self.hotkeyStatusLabel)
        hotkeyCardWidget = QWidget()
        hotkeyCardWidget.setLayout(hotkeyLayout)
        hotkeyCard.viewLayout.addWidget(hotkeyCardWidget)
        
        # 添加快捷键卡片到左侧布局
        leftLayout.addWidget(hotkeyCard)
        leftLayout.addStretch(1)
        
        # 右侧布局 - 保持不变
        rightLayout = QVBoxLayout()
        rightLayout.setSpacing(16)
        
        # 数据导出卡片
        exportCard = HeaderCardWidget(self.assistInterface)
        exportCard.setTitle("数据导出")
        
        exportLayout = QVBoxLayout()
        exportLayout.setSpacing(12)
        
        # 导出按钮
        exportBtnsLayout = QHBoxLayout()
        
        exportCsvBtn = PushButton("导出CSV")
        exportCsvBtn.setIcon(FIF.DOWNLOAD)
        
        exportJsonBtn = PushButton("导出JSON")
        exportJsonBtn.setIcon(FIF.DOWNLOAD)
        
        exportBtnsLayout.addWidget(exportCsvBtn)
        exportBtnsLayout.addWidget(exportJsonBtn)
        exportBtnsLayout.addStretch(1)
        
        # 自动导出开关
        autoExportLayout = QHBoxLayout()
        autoExportLabel = BodyLabel("自动导出:")
        autoExportSwitch = SwitchButton()
        
        autoExportLayout.addWidget(autoExportLabel)
        autoExportLayout.addWidget(autoExportSwitch)
        autoExportLayout.addStretch(1)
        
        # 导出路径
        exportPathLayout = QHBoxLayout()
        exportPathLabel = BodyLabel("导出路径:")
        exportPathEdit = LineEdit()
        exportPathEdit.setText(os.path.join(os.path.expanduser("~"), "Documents"))
        exportPathBtn = PushButton("浏览")
        exportPathBtn.setIcon(FIF.FOLDER)
        
        exportPathLayout.addWidget(exportPathLabel)
        exportPathLayout.addWidget(exportPathEdit)
        exportPathLayout.addWidget(exportPathBtn)
        
        # 添加所有组件到导出卡片
        exportLayout.addLayout(exportBtnsLayout)
        exportLayout.addLayout(autoExportLayout)
        exportLayout.addLayout(exportPathLayout)
        exportCardWidget = QWidget()
        exportCardWidget.setLayout(exportLayout)
        exportCard.viewLayout.addWidget(exportCardWidget)
        
        # 添加导出卡片到右侧布局
        rightLayout.addWidget(exportCard)
        rightLayout.addStretch(1)
        
        # 添加左右布局到主布局
        mainLayout.addLayout(leftLayout, 2)
        mainLayout.addLayout(rightLayout, 1)
        
        # 添加主布局到辅助功能界面
        layout.addLayout(mainLayout)

    def initSettingsInterface(self):
        """初始化设置界面"""
        layout = QVBoxLayout(self.settingsInterface)
        layout.setSpacing(16)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # 基本设置卡片
        basicCard = HeaderCardWidget(self.settingsInterface)
        basicCard.setTitle("基本设置")
        
        basicLayout = QVBoxLayout()
        basicLayout.setSpacing(16)
        
        # 主题设置
        themeLayout = QHBoxLayout()
        themeLabel = BodyLabel("主题:")
        themeCombo = ComboBox()
        themeCombo.addItems(["跟随系统", "亮色模式", "暗色模式"])
        themeLayout.addWidget(themeLabel)
        themeLayout.addWidget(themeCombo)
        themeLayout.addStretch(1)
        
        # 语言设置
        languageLayout = QHBoxLayout()
        languageLabel = BodyLabel("语言:")
        languageCombo = ComboBox()
        languageCombo.addItems(["简体中文", "English"])
        languageLayout.addWidget(languageLabel)
        languageLayout.addWidget(languageCombo)
        languageLayout.addStretch(1)
        
        # 自动启动
        autoStartLayout = QHBoxLayout()
        autoStartLabel = BodyLabel("开机自动启动:")
        autoStartSwitch = SwitchButton()
        autoStartLayout.addWidget(autoStartLabel)
        autoStartLayout.addWidget(autoStartSwitch)
        autoStartLayout.addStretch(1)
        
        # 添加所有组件到基本设置卡片
        basicLayout.addLayout(themeLayout)
        basicLayout.addLayout(languageLayout)
        basicLayout.addLayout(autoStartLayout)
        basicCardWidget = QWidget()
        basicCardWidget.setLayout(basicLayout)
        basicCard.viewLayout.addWidget(basicCardWidget)
        
        # 高级设置卡片
        advancedCard = HeaderCardWidget(self.settingsInterface)
        advancedCard.setTitle("高级设置")
        
        advancedLayout = QVBoxLayout()
        advancedLayout.setSpacing(16)
        
        # 缓存设置
        cacheLayout = QHBoxLayout()
        cacheLabel = BodyLabel("缓存大小:")
        cacheSizeLabel = BodyLabel("23.5 MB")
        clearCacheBtn = PushButton("清除缓存")
        clearCacheBtn.setIcon(FIF.DELETE)
        
        cacheLayout.addWidget(cacheLabel)
        cacheLayout.addWidget(cacheSizeLabel)
        cacheLayout.addStretch(1)
        cacheLayout.addWidget(clearCacheBtn)
        
        # AI模型设置
        modelLayout = QHBoxLayout()
        modelLabel = BodyLabel("AI模型:")
        modelCombo = ComboBox()
        modelCombo.addItems(['标准模型', '轻量级模型', '高精度模型', '自娱自乐模型', '作者没钱加模型'])
        modelLayout.addWidget(modelLabel)
        modelLayout.addWidget(modelCombo)
        modelLayout.addStretch(1)
        
        # GPU加速
        gpuLayout = QHBoxLayout()
        gpuLabel = BodyLabel("GPU加速:")
        gpuSwitch = SwitchButton()
        gpuSwitch.setChecked(True)
        gpuLayout.addWidget(gpuLabel)
        gpuLayout.addWidget(gpuSwitch)
        gpuLayout.addStretch(1)
        
        # 添加所有组件到高级设置卡片
        advancedLayout.addLayout(cacheLayout)
        advancedLayout.addLayout(modelLayout)
        advancedLayout.addLayout(gpuLayout)
        advancedCardWidget = QWidget()
        advancedCardWidget.setLayout(advancedLayout)
        advancedCard.viewLayout.addWidget(advancedCardWidget)
        
        # 关于卡片
        aboutCard = HeaderCardWidget(self.settingsInterface)
        aboutCard.setTitle("关于")
        
        aboutLayout = QVBoxLayout()
        aboutLayout.setSpacing(16)
        
        # 版本信息
        versionLayout = QHBoxLayout()
        versionLabel = BodyLabel("版本:")
        versionValueLabel = BodyLabel("VitalSync 2.0.0")
        versionLayout.addWidget(versionLabel)
        versionLayout.addWidget(versionValueLabel)
        versionLayout.addStretch(1)
        
        # 关于信息
        aboutInfoLabel = BodyLabel("VitalSync 是一款专为游戏设计的队员血条识别与监控软件，支持多种游戏和场景。")
        aboutInfoLabel.setWordWrap(True)
        
        # 控制按钮
        controlLayout = QHBoxLayout()
        updateBtn = PushButton("检查更新")
        updateBtn.setIcon(FIF.UPDATE)
        
        githubBtn = PushButton("GitHub项目")
        githubBtn.setIcon(FIF.LINK)
        # 连接点击事件
        githubBtn.clicked.connect(self.openGitHubProject)
        
        controlLayout.addWidget(updateBtn)
        controlLayout.addWidget(githubBtn)
        controlLayout.addStretch(1)
        
        # 添加所有组件到关于卡片
        aboutLayout.addLayout(versionLayout)
        aboutLayout.addWidget(aboutInfoLabel)
        aboutLayout.addLayout(controlLayout)
        aboutCardWidget = QWidget()
        aboutCardWidget.setLayout(aboutLayout)
        aboutCard.viewLayout.addWidget(aboutCardWidget)
        
        # 添加所有卡片到设置界面
        layout.addWidget(basicCard)
        layout.addWidget(advancedCard)
        layout.addWidget(aboutCard)
        layout.addStretch(1)

    def openGitHubProject(self):
        """打开GitHub项目页面"""
        url = QUrl("https://github.com/yinduandafeimao/VitalSync-Pulse")
        QDesktopServices.openUrl(url)
        
        # 显示提示信息
        InfoBar.success(
            title='已打开链接',
            content='已在浏览器中打开GitHub项目页面',
            orient=Qt.Horizontal,
            isClosable=True,
            position=InfoBarPosition.TOP,
            duration=2000,
            parent=self
        )

    def addProfessionIcon(self):
        """添加新的职业图标"""
        # 检查profession_icons文件夹是否存在
        profession_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "profession_icons")
        if not os.path.exists(profession_path):
            os.makedirs(profession_path)  # 创建文件夹如果不存在
            
        # 打开文件选择对话框
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "选择职业图标",
            "",
            "图片文件 (*.png *.jpg *.jpeg)"
        )
        
        if not file_path:
            return
        
        # 获取文件名
        file_name_without_ext = os.path.splitext(os.path.basename(file_path))[0]
        
        # 使用自定义无边框对话框获取职业名称
        input_dialog = TextInputMessageBox(
            title='输入职业名称',
            label_text='请输入该职业图标的名称:',
            default_text=file_name_without_ext,
            placeholder_text='例如：奶妈、坦克、输出',
            parent=self
        )
        
        if not input_dialog.exec():
            return
        
        icon_name = input_dialog.get_text()
        if not icon_name:
            InfoBar.warning(
                title='输入无效',
                content='职业名称不能为空。',
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=2000,
                parent=self
            )
            return
        
        # 构造目标路径
        target_path = os.path.join(profession_path, icon_name + os.path.splitext(file_path)[1])
        
        # 检查是否已存在同名文件
        if os.path.exists(target_path):
            confirm_dialog = ConfirmMessageBox(
                "文件已存在",
                f"职业 '{icon_name}' 已存在，是否覆盖?",
                self
            )
            
            if not confirm_dialog.exec():
                return
        
        try:
            # 复制文件
            import shutil
            shutil.copy2(file_path, target_path)
            
            # 显示成功消息
            InfoBar.success(
                title='添加成功',
                content=f'职业图标 {icon_name} 已添加',
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=2000,
                parent=self
            )
            
            # 更新图标数量显示
            self.updateIconCount()
        except Exception as e:
            # 显示错误消息
            InfoBar.error(
                title='添加失败',
                content=str(e),
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=3000,
                parent=self
            )
    
    def updateIconCount(self):
        """更新职业图标数量显示"""
        # 重新计算图标数量
        profession_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "profession_icons")
        icon_count = len([f for f in os.listdir(profession_path) if f.endswith(('.png', '.jpg', '.jpeg'))])
        
        # 查找信息标签并更新
        for i in range(self.iconCardWidget.layout().count()):
            item = self.iconCardWidget.layout().itemAt(i)
            if item.widget() and isinstance(item.widget(), BodyLabel) and "当前已加载" in item.widget().text():
                item.widget().setText(f'当前已加载 {icon_count} 个职业图标')
                break

    def init_recognition(self):
        """初始化识别模块"""
        try:
            if self.recognition is None:
                from teammate_recognition import TeammateRecognition
                self.recognition = TeammateRecognition()
                InfoBar.success(
                    title='OCR模型加载成功',
                    content='队友识别功能已准备就绪',
                    orient=Qt.Horizontal,
                    isClosable=True,
                    position=InfoBarPosition.TOP,
                    duration=2000,
                    parent=self
                )
            return True
        except Exception as e:
            InfoBar.error(
                title='OCR初始化失败',
                content=f'错误: {str(e)}',
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=3000,
                parent=self
            )
            return False

    def addTeammate(self):
        """添加队友"""
        print("\n添加新队友:")
        
        # 使用自定义的MessageBoxBase子类
        dialog = AddTeammateMessageBox(self)
        
        if dialog.exec():
            name, profession = dialog.get_teammate_info()
            
            # 使用Team类添加队友
            new_member = self.team.add_member(name, profession)
            
            # 使用全局默认颜色设置(如果有的话)
            if self.default_hp_color_lower is not None and self.default_hp_color_upper is not None:
                import numpy as np
                new_member.hp_color_lower = np.copy(self.default_hp_color_lower)
                new_member.hp_color_upper = np.copy(self.default_hp_color_upper)
                new_member.save_config()  # 保存颜色设置到队员配置文件
            
            # 更新健康监控
            self.health_monitor.team = self.team
            self.init_health_bars_ui()
            
            # 提示设置血条位置 - 使用自定义确认对话框
            confirm_dialog = ConfirmMessageBox(
                "设置血条位置",
                f"是否立即为 {name} 设置血条位置？",
                self
            )
            
            if confirm_dialog.exec():
                # 使用选择框设置血条位置
                self.set_health_bar_position(new_member)
            
            InfoBar.success(
                title='添加成功',
                content=f'队友 {name} ({profession}) 已添加',
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                parent=self
            )

class HotkeySettingsMessageBox(MessageBoxBase):
    """ Custom message box for hotkey settings """

    def __init__(self, health_monitor, parent=None):
        super().__init__(parent)
        self.titleLabel = SubtitleLabel('监控快捷键设置', self)
        self.health_monitor = health_monitor
        self.parent_window = parent
        
        # 当前快捷键展示
        self.infoLabel = BodyLabel(f"当前快捷键设置:\n开始监控: {health_monitor.start_monitoring_hotkey}\n停止监控: {health_monitor.stop_monitoring_hotkey}")
        self.infoLabel.setWordWrap(True)
        
        # 设置表单
        form_widget = QWidget()
        form_layout = QGridLayout(form_widget)
        form_layout.setSpacing(10)
        
        # 开始监控输入
        self.start_label = BodyLabel("开始监控键:")
        self.start_input = LineEdit()
        self.start_input.setText(health_monitor.start_monitoring_hotkey)
        self.start_input.setPlaceholderText("按下快捷键组合")
        
        # 停止监控输入
        self.stop_label = BodyLabel("停止监控键:")
        self.stop_input = LineEdit()
        self.stop_input.setText(health_monitor.stop_monitoring_hotkey)
        self.stop_input.setPlaceholderText("按下快捷键组合")
        
        # 错误提示标签
        self.error_label = CaptionLabel("")
        self.error_label.setTextColor("#cf1010", QColor(255, 28, 32))
        self.error_label.hide()
        
        # 增加记录按钮以记录实际按键
        self.start_record = PushButton("记录")
        self.start_record.clicked.connect(lambda: self.record_hotkey('start'))
        
        self.stop_record = PushButton("记录")
        self.stop_record.clicked.connect(lambda: self.record_hotkey('stop'))
        
        # 添加到布局
        form_layout.addWidget(self.start_label, 0, 0)
        form_layout.addWidget(self.start_input, 0, 1)
        form_layout.addWidget(self.start_record, 0, 2)
        
        form_layout.addWidget(self.stop_label, 1, 0)
        form_layout.addWidget(self.stop_input, 1, 1)
        form_layout.addWidget(self.stop_record, 1, 2)
        
        # 将所有控件添加到视图布局
        self.viewLayout.addWidget(self.titleLabel)
        self.viewLayout.addWidget(self.infoLabel)
        self.viewLayout.addWidget(form_widget)
        self.viewLayout.addWidget(self.error_label)
        
        # 设置按钮文本
        self.yesButton.setText('保存')
        self.cancelButton.setText('取消')
        
        # 设置最小宽度
        self.widget.setMinimumWidth(400)
    
    def record_hotkey(self, which):
        """弹出对话框录入快捷键"""
        from PyQt5.QtGui import QKeySequence
        
        # 创建录入对话框
        dialog = MessageBoxBase(self)
        dialog.titleLabel = SubtitleLabel('录入快捷键', dialog)
        
        # 说明标签
        guide_label = BodyLabel('请按下新的快捷键组合（如 Ctrl+Alt+S）')
        key_label = BodyLabel('等待按键...')
        
        # 添加到视图布局
        dialog.viewLayout.addWidget(dialog.titleLabel)
        dialog.viewLayout.addWidget(guide_label)
        dialog.viewLayout.addWidget(key_label)
        
        # 设置按钮文本，初始时禁用确定按钮
        dialog.yesButton.setText('确定')
        dialog.yesButton.setEnabled(False)
        dialog.cancelButton.setText('取消')
        
        # 存储按键
        key_seq = {'text': ''}
        
        # 重写keyPressEvent处理按键
        def keyPressEvent(event):
            # 保存原始方法
            original_keyPressEvent = dialog.keyPressEvent
            
            key_text = ''
            modifiers = event.modifiers()
            if modifiers & Qt.ControlModifier:
                key_text += 'ctrl+'
            if modifiers & Qt.AltModifier:
                key_text += 'alt+'
            if modifiers & Qt.ShiftModifier:
                key_text += 'shift+'
            key = event.key()
            if key in (Qt.Key_Control, Qt.Key_Alt, Qt.Key_Shift):
                # 恢复原始方法并调用它
                dialog.keyPressEvent = original_keyPressEvent
                return original_keyPressEvent(event)
            key_name = QKeySequence(key).toString().lower()
            key_text += key_name
            key_seq['text'] = key_text
            key_label.setText(f'已录入: {key_text}')
            dialog.yesButton.setEnabled(True)
            
            # 恢复原始方法
            dialog.keyPressEvent = original_keyPressEvent
        
        # 保存原始方法
        original_method = dialog.keyPressEvent
        # 替换方法
        dialog.keyPressEvent = keyPressEvent
        
        # 显示对话框
        if dialog.exec():
            if key_seq['text']:
                if which == 'start':
                    self.start_input.setText(key_seq['text'])
                else:
                    self.stop_input.setText(key_seq['text'])
    
    def validate(self):
        """验证输入是否有效"""
        start_key = self.start_input.text()
        stop_key = self.stop_input.text()
        
        # 检查输入是否有效
        if not start_key or not stop_key:
            self.error_label.setText("快捷键不能为空")
            self.error_label.show()
            return False
            
        if start_key == stop_key:
            self.error_label.setText("开始和停止快捷键不能相同")
            self.error_label.show()
            return False
        
        # 尝试设置新的快捷键
        success = self.health_monitor.set_hotkeys(start_key, stop_key)
        
        if not success:
            self.error_label.setText("设置快捷键失败，请重试")
            self.error_label.show()
            return False
            
        return True

class TeammateSelectionMessageBox(MessageBoxBase):
    """ Custom message box for teammate selection """

    def __init__(self, title, team_members, parent=None):
        super().__init__(parent)
        self.titleLabel = SubtitleLabel(title, self)
        
        # 添加说明
        self.infoLabel = BodyLabel("请从列表中选择一个队友")
        
        # 创建队友列表
        self.listWidget = QListWidget(self)
        for i, member in enumerate(team_members):
            self.listWidget.addItem(f"{member.name} ({member.profession})")
        
        # 警告标签
        self.warningLabel = CaptionLabel("未选择任何队友")
        self.warningLabel.setTextColor("#cf1010", QColor(255, 28, 32))
        self.warningLabel.hide()  # 默认隐藏
        
        # 添加到视图布局
        self.viewLayout.addWidget(self.titleLabel)
        self.viewLayout.addWidget(self.infoLabel)
        self.viewLayout.addWidget(self.listWidget)
        self.viewLayout.addWidget(self.warningLabel)
        
        # 设置按钮文本
        self.yesButton.setText('选择')
        self.cancelButton.setText('取消')
        
        # 设置最小宽度
        self.widget.setMinimumWidth(350)
        
        # 存储队友列表
        self.team_members = team_members
        self.selected_index = -1
        
        # 连接列表点击事件
        self.listWidget.itemClicked.connect(self.on_item_clicked)
    
    def on_item_clicked(self, item):
        """列表项被点击时更新选择索引"""
        self.selected_index = self.listWidget.row(item)
        self.warningLabel.hide()  # 隐藏警告
    
    def get_selected_member(self):
        """获取选中的队友"""
        if self.selected_index >= 0 and self.selected_index < len(self.team_members):
            return self.team_members[self.selected_index]
        return None
        
    def validate(self):
        """验证是否选择了队友"""
        if self.selected_index >= 0:
            return True
        else:
            self.warningLabel.show()  # 显示警告
            return False

class UnifiedColorPickerMessageBox(MessageBoxBase):
    """ Custom message box for unified color picking """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.titleLabel = SubtitleLabel('统一设置所有队友的血条颜色', self)
        
        # 添加操作指南
        self.guideLabel = BodyLabel(
            '1. 将鼠标移动到游戏中任意一个队友的血条上\n'
            '2. 选择血条最具代表性的颜色位置\n'
            '3. 按下空格键获取颜色，此颜色将应用于所有队友\n'
            '4. 按ESC键取消操作'
        )
        self.guideLabel.setWordWrap(True)
        
        # 状态标签
        self.statusLabel = CaptionLabel("状态：等待获取颜色...")
        self.statusLabel.setTextColor("#1e88e5", QColor(30, 136, 229))
        
        # 预览区域
        previewLayout = QHBoxLayout()
        previewLabel = BodyLabel('颜色预览：')
        self.colorPreview = QFrame()
        self.colorPreview.setFixedSize(50, 20)
        self.colorPreview.setFrameShape(QFrame.Box)
        previewLayout.addWidget(previewLabel)
        previewLayout.addWidget(self.colorPreview)
        previewWidget = QWidget()
        previewWidget.setLayout(previewLayout)
        
        # 添加到视图布局
        self.viewLayout.addWidget(self.titleLabel)
        self.viewLayout.addWidget(self.guideLabel)
        self.viewLayout.addWidget(self.statusLabel)
        self.viewLayout.addWidget(previewWidget)
        
        # 设置按钮文本
        self.yesButton.setText('确定')
        self.cancelButton.setText('取消')
        
        # 设置最小宽度
        self.widget.setMinimumWidth(350)
        
        # 颜色获取状态和计时器
        self.color_captured = False
        self.key_check_timer = QTimer(self)
        self.key_check_timer.timeout.connect(self.check_keys_and_position)
        self.key_check_timer.start(100)
        
        # 存储获取的颜色值
        self.pixel_color_rgb = None

    def check_keys_and_position(self):
        """检查键盘输入和鼠标位置"""
        import keyboard
        if keyboard.is_pressed('space'):
            if self.color_captured:
                return
            
            self.color_captured = True
            self.key_check_timer.stop()
            
            try:
                import pyautogui
                x, y = pyautogui.position()
                self.pixel_color_rgb = pyautogui.screenshot().getpixel((x, y))[:3]  # 确保是RGB
                
                color_hex = "#{:02x}{:02x}{:02x}".format(
                    self.pixel_color_rgb[0], 
                    self.pixel_color_rgb[1], 
                    self.pixel_color_rgb[2]
                )
                self.colorPreview.setStyleSheet(f"background-color: {color_hex};")
                
                self.statusLabel.setText(f"状态：成功获取颜色！RGB: {self.pixel_color_rgb}")
                self.statusLabel.setTextColor("#2ecc71", QColor(46, 204, 113))
                
                # 延迟关闭对话框
                QTimer.singleShot(2000, lambda: self.accept())
                
            except Exception as e:
                self.statusLabel.setText(f"状态：获取颜色失败 - {str(e)}")
                self.statusLabel.setTextColor("#e74c3c", QColor(231, 76, 60))
                self.color_captured = False
                self.key_check_timer.start()
        
        elif keyboard.is_pressed('esc'):
            if not self.color_captured:
                self.key_check_timer.stop()
                self.reject()

class MainWindow(FluentWindow):
    def __init__(self):
        """初始化主窗口"""
        super().__init__()
        
        # 初始化 pygame mixer
        try:
            pygame.mixer.init()
            pygame.mixer.set_num_channels(16) # 设置足够多的声道
        except pygame.error as e:
            print(f"Pygame mixer 初始化失败: {e}")
            # 可以选择禁用语音功能或显示错误提示
            InfoBar.error(
                title='音频初始化失败',
                content='无法初始化音频播放组件 (pygame.mixer)，语音播报功能将不可用。',
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=5000,
                parent=self
            )
        
        self._icon_capture_show_selection_timer = None
        self._icon_capture_do_grab_timer = None
        self._icon_capture_rect = None # Store the rect between timer calls
        
        # --- 添加缺失的语音参数初始化 ---
        # 初始化语音参数属性 - 使用滑块的默认值
        # 语速: slider 0-10 -> rate -50% to +50% -> + (value*10 - 50) %
        default_rate_value = 5
        self.voice_rate_param = f'+{default_rate_value * 10 - 50}%'
        # 音量: slider 0-100 -> volume -50% to +50% -> + (value - 50) %
        default_volume_value = 80
        self.voice_volume_param = f'+{default_volume_value - 50}%'
        # --- 初始化结束 ---
        
        # 设置窗口标题和大小
        self.setWindowTitle('VitalSync')
        self.resize(1200, 500) # 将高度从 800 调整为 700
        
        # 设置应用强调色 - 使用截图中的青绿色
        setThemeColor(QColor(0, 168, 174))
        
        # 启用亚克力效果
        self.navigationInterface.setAcrylicEnabled(True)
        
        # 初始化队友管理相关属性
        self.team = Team()  # 创建Team实例
        self.selection_box = None # 屏幕选择框
        
        # 初始化全局默认血条颜色
        self.default_hp_color_lower = None  # 默认血条颜色下限
        self.default_hp_color_upper = None  # 默认血条颜色上限
        self.load_default_colors()  # 从配置加载默认颜色设置
        
        # 初始化健康监控相关属性
        self.health_monitor = HealthMonitor(self.team)  # 创建健康监控实例
        # 连接监控信号
        self.health_monitor.signals.update_signal.connect(self.update_health_display)
        self.health_monitor.signals.status_signal.connect(self.update_monitor_status)
        
        # 创建界面
        self.teamRecognitionInterface = QWidget()
        self.teamRecognitionInterface.setObjectName("teamRecognitionInterface")
        
        self.healthMonitorInterface = QWidget()
        self.healthMonitorInterface.setObjectName("healthMonitorInterface")
        
        self.assistInterface = QWidget()
        self.assistInterface.setObjectName("assistInterface")
        
        self.settingsInterface = QWidget()
        self.settingsInterface.setObjectName("settingsInterface")
        
        # 新增：语音设置界面实例
        self.voiceSettingsInterface = QWidget()
        self.voiceSettingsInterface.setObjectName("voiceSettingsInterface")
        
        # 初始化界面
        self.initTeamRecognitionInterface()
        self.initHealthMonitorInterface()
        self.initAssistInterface()
        self.initSettingsInterface()
        self.initVoiceSettingsInterface() # 新增：调用语音设置界面初始化
        
        # 初始化导航
        self.initNavigation()
        
        # --- 加载设置 ---
        self.load_settings() # 在UI初始化后加载设置
        
        # 显示提示信息
        InfoBar.success(
            title='初始化完成',
            content='系统已准备就绪',
            orient=Qt.Horizontal,
            isClosable=True,
            position=InfoBarPosition.TOP,
            duration=2000,
            parent=self
        )
        
        # 在__init__方法末尾添加：
        self.load_teammates()
        
        # 初始化语音队列和工作线程
        self.speech_queue = queue.Queue()
        self.active_speech = {} # 用于跟踪正在播放的语音及其资源
        self.speech_worker_thread = threading.Thread(target=self._speech_worker_loop, daemon=True)
        self.speech_worker_thread.start()
        
        # 设置一个定时器来处理 Pygame 事件和清理
        self.pygame_event_timer = QTimer(self)
        self.pygame_event_timer.timeout.connect(self._process_pygame_events)
        self.pygame_event_timer.start(100) # 每 100ms 检查一次
    
    def initNavigation(self):
        """初始化导航栏"""
        # 添加子界面
        self.addSubInterface(self.teamRecognitionInterface, FIF.PEOPLE, '队员识别')
        self.addSubInterface(self.healthMonitorInterface, FIF.HEART, '血条监控')
        self.addSubInterface(self.assistInterface, FIF.IOT, '辅助功能')
        self.addSubInterface(self.voiceSettingsInterface, FIF.MICROPHONE, '语音设置') # 使用 FIF.MICROPHONE 图标
        
        # 添加底部界面
        self.addSubInterface(
            self.settingsInterface, 
            FIF.SETTING, 
            '系统设置',
            NavigationItemPosition.BOTTOM
        )

    def initTeamRecognitionInterface(self):
        """初始化队员识别界面"""
        layout = QVBoxLayout(self.teamRecognitionInterface)
        layout.setSpacing(24)  # 增加垂直间距
        layout.setContentsMargins(24, 24, 24, 24)  # 增加外边距
        
        # 创建顶部水平布局，包含职业图标管理和队友管理
        topLayout = QHBoxLayout()
        topLayout.setSpacing(24)  # 增加水平间距
        
        # ========== 左侧：职业图标管理 ==========
        iconCard = HeaderCardWidget(self.teamRecognitionInterface)
        iconCard.setTitle("职业图标管理")
        iconCard.setFixedHeight(200)  # 适当减少卡片高度
        iconLayout = QVBoxLayout()
        iconLayout.setSpacing(15)  # 增加垂直间距
        iconLayout.setContentsMargins(0, 10, 0, 10)  # 增加内边距
        
        # 按钮区域 - 也使用网格布局
        btnLayout = QGridLayout()
        btnLayout.setSpacing(15)  # 增加按钮间距
        
        addIconBtn = PrimaryPushButton('添加图标')
        addIconBtn.setIcon(FIF.ADD)
        addIconBtn.setFixedWidth(140)  # 显著增加按钮宽度
        addIconBtn.setMinimumHeight(36)  # 设置最小高度
        
        captureIconBtn = PushButton('截取图标')
        captureIconBtn.setIcon(FIF.CAMERA) # 使用 CAMERA 图标替代 SCREENSHOT
        captureIconBtn.setFixedWidth(140)  # 显著增加按钮宽度
        captureIconBtn.setMinimumHeight(36)  # 设置最小高度
        
        manageIconsBtn = PushButton('管理图标')
        manageIconsBtn.setIcon(FIF.SETTING)
        manageIconsBtn.setFixedWidth(140)  # 显著增加按钮宽度
        manageIconsBtn.setMinimumHeight(36)  # 设置最小高度
        
        # 连接按钮事件
        addIconBtn.clicked.connect(self.addProfessionIcon)
        captureIconBtn.clicked.connect(self.captureScreenIcon)
        manageIconsBtn.clicked.connect(self.loadProfessionIcons)
        
        # 将按钮添加到网格布局
        btnLayout.addWidget(addIconBtn, 0, 0)
        btnLayout.addWidget(captureIconBtn, 0, 1)
        btnLayout.addWidget(manageIconsBtn, 0, 2)
        
        # 显示图标数量信息
        profession_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "profession_icons")
        
        # 检查文件夹是否存在
        if not os.path.exists(profession_path):
            os.makedirs(profession_path)
            icon_count = 0
        else:
            icon_count = len([f for f in os.listdir(profession_path) if f.endswith(('.png', '.jpg', '.jpeg'))])
            
        infoLabel = BodyLabel(f'已加载 {icon_count} 个职业图标')
        infoLabel.setStyleSheet("color: #666; font-size: 13px;")  # 设置样式，使其显示更清晰
        infoLabel.setAlignment(Qt.AlignCenter)  # 居中对齐
        
        # 添加到卡片布局
        iconLayout.addLayout(btnLayout)
        iconLayout.addWidget(infoLabel)
        iconLayout.addStretch(1)  # 添加弹性空间，将内容推向顶部，使标签居中
        iconCardWidget = QWidget()
        iconCardWidget.setLayout(iconLayout)
        iconCard.viewLayout.addWidget(iconCardWidget)
        self.iconCardWidget = iconCardWidget
        
        # ========== 右侧：队友管理 ==========
        teammateCard = HeaderCardWidget(self.teamRecognitionInterface)
        teammateCard.setTitle("队友管理")
        teammateCard.setFixedHeight(200)  # 适当减少卡片高度
        teammateLayout = QVBoxLayout()
        teammateLayout.setSpacing(30)  # 增加垂直间距
        teammateLayout.setContentsMargins(0, 0, 0, 10)  # 顶部margin设为0，整体上移
        
        # 队友管理按钮区域 - 使用网格布局确保均匀分布
        teammateBtnLayout = QGridLayout()  # 改回网格布局
        teammateBtnLayout.setSpacing(18)  # 进一步增加基础间距 (原为15)
        teammateBtnLayout.setVerticalSpacing(48)  # 大幅增大垂直间距 (原为20)
        teammateBtnLayout.setContentsMargins(10, 0, 10, 0)  # 保持或调整水平内边距
        
        addTeammateBtn = PrimaryPushButton('添加队友')
        addTeammateBtn.setIcon(FIF.ADD)
        addTeammateBtn.setFixedWidth(115)  # 进一步减少按钮宽度 (原为125)
        addTeammateBtn.setMinimumHeight(36)  # 保持按钮高度
        
        removeTeammateBtn = PushButton('移除队友')
        removeTeammateBtn.setIcon(FIF.REMOVE)
        removeTeammateBtn.setFixedWidth(115)  # 进一步减少按钮宽度 (原为125)
        removeTeammateBtn.setMinimumHeight(36)  # 保持按钮高度
        
        loadTeammateBtn = PushButton('加载队友')
        loadTeammateBtn.setIcon(FIF.DOWNLOAD)
        loadTeammateBtn.setFixedWidth(115)  # 进一步减少按钮宽度 (原为125)
        loadTeammateBtn.setMinimumHeight(36)  # 保持按钮高度
        
        clearAllTeammatesBtn = PushButton('清除全部')
        clearAllTeammatesBtn.setIcon(FIF.DELETE)
        clearAllTeammatesBtn.setFixedWidth(115)  # 进一步减少按钮宽度 (原为125)
        clearAllTeammatesBtn.setMinimumHeight(36)  # 保持按钮高度
        
        # 连接按钮事件
        addTeammateBtn.clicked.connect(self.addTeammate)
        removeTeammateBtn.clicked.connect(self.removeTeammate)
        loadTeammateBtn.clicked.connect(self.loadTeammate)
        clearAllTeammatesBtn.clicked.connect(self.clearAllTeammates)
        
        # 使用网格布局均匀排列按钮，2行2列，修正行号并增加间距
        teammateBtnLayout.addWidget(addTeammateBtn, 0, 0)      # 第1行第1列
        teammateBtnLayout.addWidget(removeTeammateBtn, 0, 1)   # 第1行第2列
        teammateBtnLayout.addWidget(loadTeammateBtn, 1, 0)     # 第2行第1列
        teammateBtnLayout.addWidget(clearAllTeammatesBtn, 1, 1) # 第2行第2列
        
        # 队友信息显示
        teammateInfoLabel = BodyLabel('')
        teammateInfoLabel.setObjectName("teammateInfoLabel")  # 设置对象名以便更新时查找
        teammateInfoLabel.setWordWrap(True)  # 允许文字换行
        teammateInfoLabel.setStyleSheet("color: #666; font-size: 13px;")  # 设置样式，使其显示更清晰
        teammateInfoLabel.setAlignment(Qt.AlignCenter)  # 居中对齐
        
        # 添加到卡片布局
        teammateLayout.addLayout(teammateBtnLayout)
        teammateLayout.addWidget(teammateInfoLabel)
        teammateLayout.addStretch(1)  # 添加弹性空间，将内容推向顶部，使标签居中
        teammateCardWidget = QWidget()
        teammateCardWidget.setLayout(teammateLayout)
        teammateCard.viewLayout.addWidget(teammateCardWidget)
        
        # 将两个卡片添加到顶部布局
        topLayout.addWidget(iconCard, 1) # 设置伸展因子为1
        topLayout.addWidget(teammateCard, 1) # 设置伸展因子为1
        
        # ========== 识别队友区域 ==========
        recognitionCard = HeaderCardWidget(self.teamRecognitionInterface)
        recognitionCard.setTitle("识别队友")
        recognitionLayout = QVBoxLayout()
        recognitionLayout.setSpacing(18)  # 增加垂直间距
        recognitionLayout.setContentsMargins(0, 8, 0, 8)  # 增加内边距
        
        # 控制面板区域
        controlsPanel = QFrame()
        controlsPanel.setObjectName("cardFrame")
        controlsPanelLayout = QHBoxLayout(controlsPanel)
        controlsPanelLayout.setSpacing(16)
        controlsPanelLayout.setContentsMargins(16, 12, 16, 12)  # 增加内边距使内容更加突出
        
        # 选择识别位置按钮
        selectPositionBtn = PrimaryPushButton("选择识别位置")
        selectPositionBtn.setIcon(FIF.EDIT)
        selectPositionBtn.setMinimumWidth(160)  # 增加按钮宽度
        
        # 识别状态显示
        statusLabel = BodyLabel("状态: 未开始识别")
        statusLabel.setStyleSheet("color: #888; font-size: 14px;")  # 调整样式
        
        controlsPanelLayout.addWidget(selectPositionBtn)
        controlsPanelLayout.addWidget(statusLabel)
        controlsPanelLayout.addStretch(1)
        
        # 预览区域
        previewArea = QFrame()
        previewArea.setObjectName("cardFrame")
        # 修改：使用浅色背景和深色文字
        previewArea.setStyleSheet("#cardFrame{background-color: #f8f9fa; color: #333333; border-radius: 10px; border: 1px solid #e0e0e0;}") 
        previewLayout = QVBoxLayout(previewArea)
        previewLayout.setContentsMargins(10, 10, 10, 10)  # 添加内边距
        
        previewTitle = QLabel("队友信息预览")
        previewTitle.setAlignment(Qt.AlignCenter)
        # 修改：标题文字颜色改为深色
        previewTitle.setStyleSheet("color: #333333; font-size: 16px; font-weight: bold; margin-bottom: 10px;")
        
        # 创建滚动区域
        scrollArea = ScrollArea()
        scrollArea.setWidgetResizable(True)
        scrollArea.setStyleSheet("background: transparent; border: none;")
        
        scrollContent = QWidget()
        scrollLayout = QVBoxLayout(scrollContent)
        scrollLayout.setContentsMargins(0, 0, 0, 0)
        scrollLayout.setSpacing(8)
        
        # 创建队友信息标签
        self.teammateInfoPreview = QLabel("加载队友信息中...")
        self.teammateInfoPreview.setWordWrap(True)
        # 修改：默认文字颜色改为深色
        self.teammateInfoPreview.setStyleSheet("color: #333333; font-size: 14px;") 
        scrollLayout.addWidget(self.teammateInfoPreview)
        
        scrollArea.setWidget(scrollContent)
        
        previewLayout.addWidget(previewTitle)
        previewLayout.addWidget(scrollArea)
        
        # 添加更新按钮
        updateInfoBtn = PushButton("刷新队友信息")
        updateInfoBtn.setIcon(FIF.SYNC)
        updateInfoBtn.clicked.connect(self.update_teammate_preview)
        previewLayout.addWidget(updateInfoBtn)
        
        # 底部控制按钮
        buttonLayout = QHBoxLayout()
        buttonLayout.setSpacing(16)
        
        startBtn = PrimaryPushButton("开始识别")
        startBtn.setIcon(FIF.PLAY)
        startBtn.setMinimumWidth(130)  # 增加按钮宽度
        
        stopBtn = PushButton("停止")
        stopBtn.setIcon(FIF.CANCEL)
        stopBtn.setMinimumWidth(130)  # 增加按钮宽度
        
        saveBtn = PushButton("导出配置")
        saveBtn.setIcon(FIF.SAVE)
        saveBtn.setMinimumWidth(130)  # 增加按钮宽度
        
        # 连接按钮事件
        selectPositionBtn.clicked.connect(self.select_recognition_position)
        startBtn.clicked.connect(self.start_recognition_from_calibration)
        stopBtn.clicked.connect(self.stop_recognition)
        saveBtn.clicked.connect(self.export_recognition_config)
        
        # 然后继续添加按钮到布局
        buttonLayout.addStretch(1)
        buttonLayout.addWidget(startBtn)
        buttonLayout.addWidget(stopBtn)
        buttonLayout.addWidget(saveBtn)
        buttonLayout.addStretch(1)
        
        # 添加到识别布局
        recognitionLayout.addWidget(controlsPanel)
        recognitionLayout.addWidget(previewArea)
        recognitionLayout.addLayout(buttonLayout)
        
        recognitionCardWidget = QWidget()
        recognitionCardWidget.setLayout(recognitionLayout)
        recognitionCard.viewLayout.addWidget(recognitionCardWidget)
        
        # 添加到主布局
        layout.addLayout(topLayout)
        layout.addWidget(recognitionCard, 1)  # 1表示伸展因子，让这个区域占据更多空间
        
    def loadProfessionIcons(self):
        """加载职业图标并显示管理对话框"""
        # 使用自定义无边框对话框
        manage_dialog = ProfessionIconsManageDialog(self)
        manage_dialog.exec()
    
    def deleteProfessionIcon(self, icon_file, frame, dialog=None):
        """删除职业图标"""
        profession_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "profession_icons")
        icon_path = os.path.join(profession_path, icon_file)
        
        # 确认删除
        confirm_dialog = ConfirmMessageBox(
            "确认删除",
            f"确定要删除职业图标 {os.path.splitext(icon_file)[0]} 吗？",
            self if not dialog else dialog # Keep ConfirmMessageBox parented to dialog for modality
        )
        
        if confirm_dialog.exec():
            try:
                # 删除文件
                os.remove(icon_path)
                # 从UI中移除
                frame.setParent(None)
                frame.deleteLater()
                # 更新图标计数
                self.updateIconCount()
                # 提示成功
                InfoBar.success(
                    title='删除成功',
                    content=f'已删除职业图标 {os.path.splitext(icon_file)[0]}',
                    orient=Qt.Horizontal,
                    isClosable=True,
                    position=InfoBarPosition.TOP,
                    duration=2000,
                    parent=self  # Ensure InfoBar is parented to MainWindow
                )
            except Exception as e:
                # 删除失败提示
                InfoBar.error(
                    title='删除失败',
                    content=str(e),
                    orient=Qt.Horizontal,
                    isClosable=True,
                    position=InfoBarPosition.TOP,
                    duration=3000,
                    parent=self  # Ensure InfoBar is parented to MainWindow
                )

    def initHealthMonitorInterface(self):
        """初始化血条监控界面"""
        layout = QVBoxLayout(self.healthMonitorInterface)
        layout.setSpacing(16)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # 标题和状态信息
        titleLayout = QHBoxLayout()
        titleLabel = StrongBodyLabel("血条实时监控")
        titleLabel.setStyleSheet("font-size: 18px; font-weight: bold;")
        
        self.monitor_status_label = BodyLabel("准备就绪")
        self.monitor_status_label.setStyleSheet("color: #3498db;")
        titleLayout.addWidget(titleLabel)
        titleLayout.addStretch(1)
        titleLayout.addWidget(self.monitor_status_label)
        
        # 控制按钮区域
        controlLayout = QHBoxLayout()
        
        startMonitorBtn = PrimaryPushButton("开始监控")
        startMonitorBtn.setIcon(FIF.PLAY)
        startMonitorBtn.setMinimumWidth(120)
        
        stopMonitorBtn = PushButton("停止监控")
        stopMonitorBtn.setIcon(FIF.CLOSE)
        stopMonitorBtn.setMinimumWidth(120)
        
        # 新增：设置血条颜色按钮
        setColorBtn = PushButton("设置血条颜色")
        setColorBtn.setIcon(FIF.PALETTE) # 使用 PALETTE 图标替代 COLOR
        setColorBtn.setMinimumWidth(120)
        
        # 新增：统一设置血条颜色按钮
        setAllColorsBtn = PushButton("统一设置颜色")
        setAllColorsBtn.setIcon(FIF.BRUSH) # 使用 BRUSH 图标
        setAllColorsBtn.setMinimumWidth(120)
        
        # 连接按钮事件
        startMonitorBtn.clicked.connect(self.health_monitor.start_monitoring)
        stopMonitorBtn.clicked.connect(self.health_monitor.stop_monitoring)
        setColorBtn.clicked.connect(self.setTeammateHealthBarColor)  # 连接到单个设置方法
        setAllColorsBtn.clicked.connect(self.handleSetAllTeammatesColor) # 连接到统一设置方法
        
        controlLayout.addWidget(startMonitorBtn)
        controlLayout.addWidget(stopMonitorBtn)
        controlLayout.addWidget(setColorBtn)  # 添加单个设置按钮
        controlLayout.addWidget(setAllColorsBtn) # 添加统一设置按钮
        controlLayout.addStretch(1)
        
        # 血条展示区域
        self.health_bars_frame = QFrame()
        self.health_bars_frame.setObjectName("cardFrame")
        self.health_bars_frame.setStyleSheet("QFrame#cardFrame { background-color: rgba(240, 240, 240, 0.7); border-radius: 8px; padding: 10px; }")
        healthBarsLayout = QVBoxLayout(self.health_bars_frame)
        healthBarsLayout.setSpacing(12)
        healthBarsLayout.setContentsMargins(15, 15, 15, 15)
        
        # 初始化血条UI
        self.init_health_bars_ui()
        
        # 添加到监控布局
        layout.addLayout(titleLayout)
        layout.addLayout(controlLayout)
        layout.addWidget(self.health_bars_frame, 1)  # 将监控卡片设置为可伸展，占用更多空间
        
        # 设置卡片
        settingsCard = HeaderCardWidget(self.healthMonitorInterface)
        settingsCard.setTitle("血条监控设置")
        
        settingsLayout = QVBoxLayout()
        settingsLayout.setSpacing(12)
        
        # 基本设置组
        paramsGroup = QGroupBox("监控参数", self.healthMonitorInterface)
        paramsGroupLayout = QVBoxLayout()
        
        # 阈值设置
        thresholdLayout = QHBoxLayout()
        thresholdLabel = BodyLabel(f"血条阈值: {int(self.health_monitor.health_threshold)}%")
        thresholdSlider = Slider(Qt.Horizontal)
        thresholdSlider.setRange(0, 100)
        thresholdSlider.setValue(int(self.health_monitor.health_threshold))
        thresholdLayout.addWidget(thresholdLabel)
        thresholdLayout.addWidget(thresholdSlider)
        thresholdSlider.valueChanged.connect(lambda v: self.update_health_threshold(v, thresholdLabel))
        
        # 采样率设置
        samplingLayout = QHBoxLayout()
        samplingLabel = BodyLabel("采样率 (fps):")
        samplingSpinBox = SpinBox()
        samplingSpinBox.setRange(1, 60)
        samplingSpinBox.setValue(10)
        samplingLayout.addWidget(samplingLabel)
        samplingLayout.addWidget(samplingSpinBox)
        
        # 添加所有参数设置
        paramsGroupLayout.addLayout(thresholdLayout)
        paramsGroupLayout.addLayout(samplingLayout)
        
        # 自动点击低血量队友功能开关
        autoClickLayout = QHBoxLayout()
        autoClickLabel = BodyLabel("自动点击低血量队友:")
        self.autoClickSwitch = SwitchButton()
        # 从 HealthMonitor 加载初始状态
        if hasattr(self, 'health_monitor') and hasattr(self.health_monitor, 'auto_select_enabled'):
            self.autoClickSwitch.setChecked(self.health_monitor.auto_select_enabled)
        else:
            self.autoClickSwitch.setChecked(False) # 默认关闭
        
        # 新增：职业优先级下拉框
        priorityLabel = BodyLabel("优先职业:")
        self.priorityComboBox = ComboBox()
        self.priorityComboBox.setFixedWidth(120)
        # 加载所有职业选项
        self.load_profession_options()
        # 设置当前选中值
        if hasattr(self, 'health_monitor') and hasattr(self.health_monitor, 'priority_profession'):
            priority_index = self.priorityComboBox.findText(self.health_monitor.priority_profession)
            if priority_index >= 0:
                self.priorityComboBox.setCurrentIndex(priority_index)
        
        # 连接信号
        self.autoClickSwitch.checkedChanged.connect(self.toggle_auto_click_low_health)
        self.priorityComboBox.currentTextChanged.connect(self.update_priority_profession)
        
        autoClickLayout.addWidget(autoClickLabel)
        autoClickLayout.addWidget(self.autoClickSwitch)
        autoClickLayout.addSpacing(20)  # 增加间距
        autoClickLayout.addWidget(priorityLabel)
        autoClickLayout.addWidget(self.priorityComboBox)
        autoClickLayout.addStretch(1)
        paramsGroupLayout.addLayout(autoClickLayout) # 添加到参数组布局
        
        paramsGroup.setLayout(paramsGroupLayout)
        
        # 添加到主设置布局
        settingsLayout.addWidget(paramsGroup)
        settingsCardWidget = QWidget()
        settingsCardWidget.setLayout(settingsLayout)
        settingsCard.viewLayout.addWidget(settingsCardWidget)
        
        # 添加卡片到主布局，但设置较小的高度比例
        layout.addWidget(settingsCard)
        
        # 更新采样率设置
        samplingSpinBox.valueChanged.connect(self.update_sampling_rate)
    
    def init_health_bars_ui(self):
        """初始化血条UI显示"""
        if not self.health_bars_frame:
            return

        # 清除现有布局中的所有组件
        current_layout = self.health_bars_frame.layout()
        if current_layout is not None:
            while current_layout.count():
                item = current_layout.takeAt(0)
                widget = item.widget()
                if widget:
                    widget.deleteLater()
        else:
            # 如果布局不存在，则创建一个新的
            new_layout = QVBoxLayout(self.health_bars_frame)
            new_layout.setSpacing(12)
            new_layout.setContentsMargins(15, 15, 15, 15)
            self.health_bars_frame.setLayout(new_layout) # 设置新布局
        
        # --- 新增：按血条 y1, x1 坐标对队员进行排序 ---
        sorted_members = sorted(self.team.members, key=lambda m: (m.y1, m.x1))
        
        # 添加队友信息卡片
        for i, member in enumerate(sorted_members): # 使用排序后的列表
            self.add_health_bar_card(i, member.name, member.profession)
            
        # 如果没有队友，显示提示信息
        if not self.team.members and self.health_bars_frame.layout() is not None: # 检查原始列表判断是否有队友
            noMemberLabel = StrongBodyLabel("没有队友信息。请在队员识别页面添加队友。")
            noMemberLabel.setAlignment(Qt.AlignCenter)
            self.health_bars_frame.layout().addWidget(noMemberLabel)
        
        # 添加：强制更新框架，确保UI刷新
        self.health_bars_frame.update()
    
    def add_health_bar_card(self, index, name, profession):
        """添加血条卡片
        
        参数:
            index: 队友索引
            name: 队友名称
            profession: 队友职业
        """
        # 创建水平布局，每一行一个队员
        memberCard = QFrame()
        memberCard.setObjectName(f"member_card_{index}")
        memberCard.setFixedHeight(60)  # 设置固定高度
        memberCard.setStyleSheet("background-color: transparent;")
        memberLayout = QHBoxLayout(memberCard)
        memberLayout.setContentsMargins(5, 0, 5, 0)
        memberLayout.setSpacing(10)
        
        # 队员编号和名称 - 使用实际名称
        nameLabel = StrongBodyLabel(name)
        nameLabel.setObjectName(f"name_label_{index}")
        nameLabel.setStyleSheet("font-size: 14px; font-weight: bold;")
        nameLabel.setFixedWidth(80)
        
        # 修改：直接显示识别到的职业名称
        roleLabel = BodyLabel(str(profession)) # 确保是字符串
        roleLabel.setStyleSheet("color: #666; font-size: 12px;")
        roleLabel.setFixedWidth(60)
        roleLabel.setToolTip(str(profession)) # 添加悬浮提示显示完整职业名
        
        # 血条容器
        healthBarContainer = QFrame()
        healthBarContainer.setFixedHeight(25)
        healthBarContainer.setStyleSheet("background-color: #333; border-radius: 5px;")
        # --- 添加：设置最大宽度 --- 
        MAX_WIDTH = 300  # 与 update_health_display 中保持一致
        healthBarContainer.setMaximumWidth(MAX_WIDTH) 
        # --- 结束添加 ---
        healthBarContainerLayout = QHBoxLayout(healthBarContainer)
        healthBarContainerLayout.setContentsMargins(2, 2, 2, 2)
        healthBarContainerLayout.setSpacing(0)
        
        # 血条
        healthBar = QFrame()
        healthBar.setObjectName(f"health_bar_{index}")
        healthBar.setFixedHeight(21)
        
        # 根据索引设置不同颜色
        color = "#2ecc71"  # 绿色 (默认，表示90%)
        if index == 1:
            color = "#2ecc71"  # 绿色 (70%)
        elif index == 2:
            color = "#f39c12"  # 黄色 (50%)
        elif index == 3:
            color = "#e74c3c"  # 红色 (30%)
        elif index == 4:
            color = "#e74c3c"  # 红色 (10%)
        
        # 设置默认百分比
        default_percentage = 90
        if index == 1:
            default_percentage = 70
        elif index == 2:
            default_percentage = 50
        elif index == 3:
            default_percentage = 30
        elif index == 4:
            default_percentage = 10
        
        # 设置血条缩放因子和最大宽度
        SCALE_FACTOR = 3
        MAX_WIDTH = 300  # 血条最大宽度
        
        # 计算血条宽度
        bar_width = min(int(default_percentage * SCALE_FACTOR), MAX_WIDTH)
        print(f"队员{index+1} 初始血条宽度: {bar_width}px (血量: {default_percentage}%)")
        
        healthBar.setStyleSheet(f"background-color: {color}; border-radius: 3px;")
        healthBar.setFixedWidth(bar_width)  # 使用计算的宽度
        
        healthBarContainerLayout.addWidget(healthBar)
        healthBarContainerLayout.addStretch(1)
        
        # 血量百分比
        valueLabel = StrongBodyLabel(f"{default_percentage}%")
        valueLabel.setObjectName(f"value_label_{index}")
        valueLabel.setStyleSheet(f"color: {color}; font-weight: bold; font-size: 15px;")
        valueLabel.setAlignment(Qt.AlignCenter)
        valueLabel.setFixedWidth(60)
        
        # 添加调试标签 - 开发期间使用，显示实际内部存储的血量
        debugLabel = QLabel(f"dbg:ok")
        debugLabel.setObjectName(f"debug_label_{index}")
        debugLabel.setStyleSheet("color: #999; font-size: 8px;")
        debugLabel.setFixedWidth(50)
        
        # 添加到卡片布局
        memberLayout.addWidget(nameLabel)
        memberLayout.addWidget(roleLabel)
        memberLayout.addWidget(healthBarContainer)
        memberLayout.addWidget(valueLabel)
        memberLayout.addWidget(debugLabel)  # 添加调试标签
        
        # 添加到主布局
        self.health_bars_frame.layout().addWidget(memberCard)
        
        # 添加分隔线（除了最后一个）
        if index < len(self.team.members) - 1:
            separator = QFrame()
            separator.setFrameShape(QFrame.HLine)
            separator.setFrameShadow(QFrame.Sunken)
            separator.setStyleSheet("background-color: #e0e0e0;")
            separator.setFixedHeight(1)
            self.health_bars_frame.layout().addWidget(separator)
    
    def update_sampling_rate(self, value):
        """更新监控采样率
        
        参数:
            value: 采样率值（fps）
        """
        if hasattr(self, 'health_monitor'):
            # 转换为更新间隔（秒）
            interval = 1.0 / value if value > 0 else 0.1
            self.health_monitor.update_interval = interval
            self.update_monitor_status(f"采样率已更新: {value} fps (更新间隔: {interval:.2f}秒)")
    
    def show_hotkey_settings(self):
        """显示快捷键设置对话框"""
        dialog = HotkeySettingsMessageBox(self.health_monitor, self)
        dialog.exec()
    
    def show_error_message(self, message):
        """显示错误消息
        
        参数:
            message: 错误消息
        """
        InfoBar.error(
            title='错误',
            content=message,
            orient=Qt.Horizontal,
            isClosable=True,
            position=InfoBarPosition.TOP,
            duration=3000,
            parent=self
        )
    
    def set_auto_select(self, enabled):
        """设置自动选择功能
        
        参数:
            enabled: 是否启用
        """
        if hasattr(self, 'health_monitor'):
            self.health_monitor.auto_select_enabled = enabled
            self.health_monitor.save_auto_select_config()
            status = "启用" if enabled else "禁用"
            self.update_monitor_status(f"自动选择功能已{status}")

    def initAssistInterface(self):
        """初始化辅助功能界面"""
        layout = QVBoxLayout(self.assistInterface)
        layout.setSpacing(16)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # 左右布局，左侧为主要功能，右侧为次要功能
        mainLayout = QHBoxLayout()
        mainLayout.setSpacing(16)
        
        # 左侧布局 - 现在只包含快捷键设置
        leftLayout = QVBoxLayout()
        leftLayout.setSpacing(16)
        
        # 快捷键卡片
        hotkeyCard = HeaderCardWidget(self.assistInterface)
        hotkeyCard.setTitle("快捷键设置")
        
        hotkeyLayout = QVBoxLayout()
        hotkeyLayout.setSpacing(12)
        
        # 提示信息
        hotkey_info = BodyLabel("设置全局快捷键用于快速操作。点击\"记录\"按钮后，按下想要设置的键。")
        hotkey_info.setWordWrap(True)
        
        # 快捷键表格
        hotkeyGridLayout = QGridLayout()
        hotkeyGridLayout.setSpacing(12)
        
        # 开始监控
        startMonitorLabel = BodyLabel('开始监控:')
        startMonitorEdit = LineEdit()
        startMonitorEdit.setReadOnly(True)
        startMonitorEdit.setText(self.health_monitor.start_monitoring_hotkey)
        startMonitorRecordBtn = PushButton('记录')
        
        # 停止监控
        stopMonitorLabel = BodyLabel('停止监控:')
        stopMonitorEdit = LineEdit()
        stopMonitorEdit.setReadOnly(True)
        stopMonitorEdit.setText(self.health_monitor.stop_monitoring_hotkey)
        stopMonitorRecordBtn = PushButton('记录')
        
        # 绑定"记录"按钮事件，使用事件过滤器方式
        startMonitorRecordBtn.clicked.connect(lambda: self.install_hotkey_event_filter(startMonitorEdit, stopMonitorEdit, 'start'))
        stopMonitorRecordBtn.clicked.connect(lambda: self.install_hotkey_event_filter(stopMonitorEdit, startMonitorEdit, 'stop'))
        
        # 添加到网格
        hotkeyGridLayout.addWidget(startMonitorLabel, 0, 0)
        hotkeyGridLayout.addWidget(startMonitorEdit, 0, 1)
        hotkeyGridLayout.addWidget(startMonitorRecordBtn, 0, 2)
        
        hotkeyGridLayout.addWidget(stopMonitorLabel, 1, 0)
        hotkeyGridLayout.addWidget(stopMonitorEdit, 1, 1)
        hotkeyGridLayout.addWidget(stopMonitorRecordBtn, 1, 2)
        
        # 添加所有组件到快捷键卡片
        hotkeyLayout.addWidget(hotkey_info)
        hotkeyLayout.addLayout(hotkeyGridLayout)
        # 增加状态信息标签
        self.hotkeyStatusLabel = BodyLabel('')
        hotkeyLayout.addWidget(self.hotkeyStatusLabel)
        hotkeyCardWidget = QWidget()
        hotkeyCardWidget.setLayout(hotkeyLayout)
        hotkeyCard.viewLayout.addWidget(hotkeyCardWidget)
        
        # 添加快捷键卡片到左侧布局
        leftLayout.addWidget(hotkeyCard)
        leftLayout.addStretch(1)
        
        # 右侧布局 - 保持不变
        rightLayout = QVBoxLayout()
        rightLayout.setSpacing(16)
        
        # 数据导出卡片
        exportCard = HeaderCardWidget(self.assistInterface)
        exportCard.setTitle("数据导出")
        
        exportLayout = QVBoxLayout()
        exportLayout.setSpacing(12)
        
        # 导出按钮
        exportBtnsLayout = QHBoxLayout()
        
        exportCsvBtn = PushButton("导出CSV")
        exportCsvBtn.setIcon(FIF.DOWNLOAD)
        
        exportJsonBtn = PushButton("导出JSON")
        exportJsonBtn.setIcon(FIF.DOWNLOAD)
        
        exportBtnsLayout.addWidget(exportCsvBtn)
        exportBtnsLayout.addWidget(exportJsonBtn)
        exportBtnsLayout.addStretch(1)
        
        # 自动导出开关
        autoExportLayout = QHBoxLayout()
        autoExportLabel = BodyLabel("自动导出:")
        autoExportSwitch = SwitchButton()
        
        autoExportLayout.addWidget(autoExportLabel)
        autoExportLayout.addWidget(autoExportSwitch)
        autoExportLayout.addStretch(1)
        
        # 导出路径
        exportPathLayout = QHBoxLayout()
        exportPathLabel = BodyLabel("导出路径:")
        exportPathEdit = LineEdit()
        exportPathEdit.setText(os.path.join(os.path.expanduser("~"), "Documents"))
        exportPathBtn = PushButton("浏览")
        exportPathBtn.setIcon(FIF.FOLDER)
        
        exportPathLayout.addWidget(exportPathLabel)
        exportPathLayout.addWidget(exportPathEdit)
        exportPathLayout.addWidget(exportPathBtn)
        
        # 添加所有组件到导出卡片
        exportLayout.addLayout(exportBtnsLayout)
        exportLayout.addLayout(autoExportLayout)
        exportLayout.addLayout(exportPathLayout)
        exportCardWidget = QWidget()
        exportCardWidget.setLayout(exportLayout)
        exportCard.viewLayout.addWidget(exportCardWidget)
        
        # 添加导出卡片到右侧布局
        rightLayout.addWidget(exportCard)
        rightLayout.addStretch(1)
        
        # 添加左右布局到主布局
        mainLayout.addLayout(leftLayout, 2)
        mainLayout.addLayout(rightLayout, 1)
        
        # 添加主布局到辅助功能界面
        layout.addLayout(mainLayout)

    def initSettingsInterface(self):
        """初始化设置界面"""
        layout = QVBoxLayout(self.settingsInterface)
        layout.setSpacing(16)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # 基本设置卡片
        basicCard = HeaderCardWidget(self.settingsInterface)
        basicCard.setTitle("基本设置")
        
        basicLayout = QVBoxLayout()
        basicLayout.setSpacing(16)
        
        # 主题设置
        themeLayout = QHBoxLayout()
        themeLabel = BodyLabel("主题:")
        themeCombo = ComboBox()
        themeCombo.addItems(["跟随系统", "亮色模式", "暗色模式"])
        themeLayout.addWidget(themeLabel)
        themeLayout.addWidget(themeCombo)
        themeLayout.addStretch(1)
        
        # 语言设置
        languageLayout = QHBoxLayout()
        languageLabel = BodyLabel("语言:")
        languageCombo = ComboBox()
        languageCombo.addItems(["简体中文", "English"])
        languageLayout.addWidget(languageLabel)
        languageLayout.addWidget(languageCombo)
        languageLayout.addStretch(1)
        
        # 自动启动
        autoStartLayout = QHBoxLayout()
        autoStartLabel = BodyLabel("开机自动启动:")
        autoStartSwitch = SwitchButton()
        autoStartLayout.addWidget(autoStartLabel)
        autoStartLayout.addWidget(autoStartSwitch)
        autoStartLayout.addStretch(1)
        
        # 添加所有组件到基本设置卡片
        basicLayout.addLayout(themeLayout)
        basicLayout.addLayout(languageLayout)
        basicLayout.addLayout(autoStartLayout)
        basicCardWidget = QWidget()
        basicCardWidget.setLayout(basicLayout)
        basicCard.viewLayout.addWidget(basicCardWidget)
        
        # 高级设置卡片
        advancedCard = HeaderCardWidget(self.settingsInterface)
        advancedCard.setTitle("高级设置")
        
        advancedLayout = QVBoxLayout()
        advancedLayout.setSpacing(16)
        
        # 缓存设置
        cacheLayout = QHBoxLayout()
        cacheLabel = BodyLabel("缓存大小:")
        cacheSizeLabel = BodyLabel("23.5 MB")
        clearCacheBtn = PushButton("清除缓存")
        clearCacheBtn.setIcon(FIF.DELETE)
        
        cacheLayout.addWidget(cacheLabel)
        cacheLayout.addWidget(cacheSizeLabel)
        cacheLayout.addStretch(1)
        cacheLayout.addWidget(clearCacheBtn)
        
        # AI模型设置
        modelLayout = QHBoxLayout()
        modelLabel = BodyLabel("AI模型:")
        modelCombo = ComboBox()
        modelCombo.addItems(['标准模型', '轻量级模型', '高精度模型', '自娱自乐模型', '作者没钱加模型'])
        modelLayout.addWidget(modelLabel)
        modelLayout.addWidget(modelCombo)
        modelLayout.addStretch(1)
        
        # GPU加速
        gpuLayout = QHBoxLayout()
        gpuLabel = BodyLabel("GPU加速:")
        gpuSwitch = SwitchButton()
        gpuSwitch.setChecked(True)
        gpuLayout.addWidget(gpuLabel)
        gpuLayout.addWidget(gpuSwitch)
        gpuLayout.addStretch(1)
        
        # 添加所有组件到高级设置卡片
        advancedLayout.addLayout(cacheLayout)
        advancedLayout.addLayout(modelLayout)
        advancedLayout.addLayout(gpuLayout)
        advancedCardWidget = QWidget()
        advancedCardWidget.setLayout(advancedLayout)
        advancedCard.viewLayout.addWidget(advancedCardWidget)
        
        # 关于卡片
        aboutCard = HeaderCardWidget(self.settingsInterface)
        aboutCard.setTitle("关于")
        
        aboutLayout = QVBoxLayout()
        aboutLayout.setSpacing(16)
        
        # 版本信息
        versionLayout = QHBoxLayout()
        versionLabel = BodyLabel("版本:")
        versionValueLabel = BodyLabel("VitalSync 2.0.0")
        versionLayout.addWidget(versionLabel)
        versionLayout.addWidget(versionValueLabel)
        versionLayout.addStretch(1)
        
        # 关于信息
        aboutInfoLabel = BodyLabel("VitalSync 是一款专为游戏设计的队员血条识别与监控软件，支持多种游戏和场景。")
        aboutInfoLabel.setWordWrap(True)
        
        # 控制按钮
        controlLayout = QHBoxLayout()
        updateBtn = PushButton("检查更新")
        updateBtn.setIcon(FIF.UPDATE)
        
        githubBtn = PushButton("GitHub项目")
        githubBtn.setIcon(FIF.LINK)
        # 连接点击事件
        githubBtn.clicked.connect(self.openGitHubProject)
        
        controlLayout.addWidget(updateBtn)
        controlLayout.addWidget(githubBtn)
        controlLayout.addStretch(1)
        
        # 添加所有组件到关于卡片
        aboutLayout.addLayout(versionLayout)
        aboutLayout.addWidget(aboutInfoLabel)
        aboutLayout.addLayout(controlLayout)
        aboutCardWidget = QWidget()
        aboutCardWidget.setLayout(aboutLayout)
        aboutCard.viewLayout.addWidget(aboutCardWidget)
        
        # 添加所有卡片到设置界面
        layout.addWidget(basicCard)
        layout.addWidget(advancedCard)
        layout.addWidget(aboutCard)
        layout.addStretch(1)

    def openGitHubProject(self):
        """打开GitHub项目页面"""
        url = QUrl("https://github.com/yinduandafeimao/VitalSync-Pulse")
        QDesktopServices.openUrl(url)
        
        # 显示提示信息
        InfoBar.success(
            title='已打开链接',
            content='已在浏览器中打开GitHub项目页面',
            orient=Qt.Horizontal,
            isClosable=True,
            position=InfoBarPosition.TOP,
            duration=2000,
            parent=self
        )

    def addProfessionIcon(self):
        """添加新的职业图标"""
        # 检查profession_icons文件夹是否存在
        profession_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "profession_icons")
        if not os.path.exists(profession_path):
            os.makedirs(profession_path)  # 创建文件夹如果不存在
            
        # 打开文件选择对话框
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "选择职业图标",
            "",
            "图片文件 (*.png *.jpg *.jpeg)"
        )
        
        if not file_path:
            return
        
        # 获取文件名
        file_name_without_ext = os.path.splitext(os.path.basename(file_path))[0]
        
        # 使用自定义无边框对话框获取职业名称
        input_dialog = TextInputMessageBox(
            title='输入职业名称',
            label_text='请输入该职业图标的名称:',
            default_text=file_name_without_ext,
            placeholder_text='例如：奶妈、坦克、输出',
            parent=self
        )
        
        if not input_dialog.exec():
            return
        
        icon_name = input_dialog.get_text()
        if not icon_name:
            InfoBar.warning(
                title='输入无效',
                content='职业名称不能为空。',
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=2000,
                parent=self
            )
            return
        
        # 构造目标路径
        target_path = os.path.join(profession_path, icon_name + os.path.splitext(file_path)[1])
        
        # 检查是否已存在同名文件
        if os.path.exists(target_path):
            confirm_dialog = ConfirmMessageBox(
                "文件已存在",
                f"职业 '{icon_name}' 已存在，是否覆盖?",
                self
            )
            
            if not confirm_dialog.exec():
                return
        
        try:
            # 复制文件
            import shutil
            shutil.copy2(file_path, target_path)
            
            # 显示成功消息
            InfoBar.success(
                title='添加成功',
                content=f'职业图标 {icon_name} 已添加',
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=2000,
                parent=self
            )
            
            # 更新图标数量显示
            self.updateIconCount()
        except Exception as e:
            # 显示错误消息
            InfoBar.error(
                title='添加失败',
                content=str(e),
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=3000,
                parent=self
            )
    
    def updateIconCount(self):
        """更新职业图标数量显示"""
        # 重新计算图标数量
        profession_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "profession_icons")
        icon_count = len([f for f in os.listdir(profession_path) if f.endswith(('.png', '.jpg', '.jpeg'))])
        
        # 查找信息标签并更新
        for i in range(self.iconCardWidget.layout().count()):
            item = self.iconCardWidget.layout().itemAt(i)
            if item.widget() and isinstance(item.widget(), BodyLabel) and "当前已加载" in item.widget().text():
                item.widget().setText(f'当前已加载 {icon_count} 个职业图标')
                break

    def init_recognition(self):
        """初始化识别模块"""
        try:
            if self.recognition is None:
                from teammate_recognition import TeammateRecognition
                self.recognition = TeammateRecognition()
                InfoBar.success(
                    title='OCR模型加载成功',
                    content='队友识别功能已准备就绪',
                    orient=Qt.Horizontal,
                    isClosable=True,
                    position=InfoBarPosition.TOP,
                    duration=2000,
                    parent=self
                )
            return True
        except Exception as e:
            InfoBar.error(
                title='OCR初始化失败',
                content=f'错误: {str(e)}',
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=3000,
                parent=self
            )
            return False

    def addTeammate(self):
        """添加队友"""
        print("\n添加新队友:")
        
        # 使用自定义的MessageBoxBase子类
        dialog = AddTeammateMessageBox(self)
        
        if dialog.exec():
            name, profession = dialog.get_teammate_info()
            
            # 使用Team类添加队友
            new_member = self.team.add_member(name, profession)
            
            # 使用全局默认颜色设置(如果有的话)
            if self.default_hp_color_lower is not None and self.default_hp_color_upper is not None:
                import numpy as np
                new_member.hp_color_lower = np.copy(self.default_hp_color_lower)
                new_member.hp_color_upper = np.copy(self.default_hp_color_upper)
                new_member.save_config()  # 保存颜色设置到队员配置文件
            
            # 更新健康监控
            self.health_monitor.team = self.team
            self.init_health_bars_ui()
            
            # 提示设置血条位置 - 使用自定义确认对话框
            confirm_dialog = ConfirmMessageBox(
                "设置血条位置",
                f"是否立即为 {name} 设置血条位置？",
                self
            )
            
            if confirm_dialog.exec():
                # 使用选择框设置血条位置
                self.set_health_bar_position(new_member)
            
            InfoBar.success(
                title='添加成功',
                content=f'队友 {name} ({profession}) 已添加',
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=2000,
                parent=self
            )

    def set_health_bar_position(self, member):
        """设置队员血条位置"""
        from 选择框 import show_selection_box
        
import sys
import os
import cv2
import numpy as np
import json
import threading
import pyautogui
import time
import asyncio
import edge_tts
import tempfile
import queue # 新增导入
# 移除 playsound 导入
# from playsound import playsound
# 添加 pygame 导入
import pygame
from PyQt5.QtCore import Qt, QTimer, QByteArray, QBuffer, QIODevice, QPoint, QSize, QRect, QThread, pyqtSignal, QObject, QEvent, QUrl, QPropertyAnimation
from PyQt5.QtGui import QPixmap, QImage, QIcon, QColor, QFont, QKeySequence, QDesktopServices
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                            QLabel, QFileDialog, QFrame, QGridLayout, QSplitter, QTabWidget, QGroupBox,
                            QInputDialog, QDialog, QListWidget, QListWidgetItem, QAbstractItemView,
                            QGraphicsDropShadowEffect)

# 导入Fluent组件库
from qfluentwidgets import (FluentWindow, NavigationItemPosition, PushButton, 
                           ToolButton, PrimaryPushButton, ComboBox, RadioButton, CheckBox,
                           Slider, SwitchButton, ToggleButton, SubtitleLabel, BodyLabel,
                           Action, setTheme, Theme, MessageBox, MessageBoxBase, InfoBar, TabBar,
                           TransparentPushButton, LineEdit, StrongBodyLabel, CaptionLabel,
                           SpinBox, DoubleSpinBox, ScrollArea, CardWidget, HeaderCardWidget,
                           InfoBarPosition, NavigationInterface, setThemeColor, FluentIcon as FIF)

# 导入血条校准模块
from health_bar_calibration import HealthBarCalibration

# 导入血条监控模块
from health_monitor import HealthMonitor, MonitorSignals

# 动态导入带空格的模块
import importlib.util

# 动态导入带空格的模块
module_name = "team_members(choice box)"
module_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "team_members(choice box).py")
spec = importlib.util.spec_from_file_location(module_name, module_path)
team_members_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(team_members_module)

# 从module中获取Team和TeamMember类
Team = team_members_module.Team
TeamMember = team_members_module.TeamMember

# 设置应用全局样式
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

# 定义配置文件名
# CONFIG_FILE = 'config.json'  # 已迁移到配置管理系统

# 自定义对话框类 - 完全参照示例代码
class ColorPickerMessageBox(MessageBoxBase):
    """ Custom message box for color picking """

    def __init__(self, member_name, parent=None):
        super().__init__(parent)
        self.titleLabel = SubtitleLabel(f'设置 {member_name} 的血条颜色', self)
        
        # 添加指南标签
        self.guideLabel = BodyLabel(
            '1. 将鼠标移动到游戏中该队友的血条上\n'
            '2. 选择血条最具代表性的颜色位置\n'
            '3. 按下空格键获取颜色\n'
            '4. 按ESC键取消操作'
        )
        self.guideLabel.setWordWrap(True)
        
        # 状态标签
        self.statusLabel = CaptionLabel("状态：等待获取颜色...")
        self.statusLabel.setTextColor("#1e88e5", QColor(30, 136, 229))
        
        # 预览区域
        previewLayout = QHBoxLayout()
        previewLabel = BodyLabel('颜色预览：')
        self.colorPreview = QFrame()
        self.colorPreview.setFixedSize(50, 20)
        self.colorPreview.setFrameShape(QFrame.Box)
        previewLayout.addWidget(previewLabel)
        previewLayout.addWidget(self.colorPreview)
        previewWidget = QWidget()
        previewWidget.setLayout(previewLayout)

        # 添加到视图布局
        self.viewLayout.addWidget(self.titleLabel)
        self.viewLayout.addWidget(self.guideLabel)
        self.viewLayout.addWidget(self.statusLabel)
        self.viewLayout.addWidget(previewWidget)

        # 修改按钮文本
        self.yesButton.setText('确定')
        self.cancelButton.setText('取消')

        # 设置最小宽度
        self.widget.setMinimumWidth(350)
        
        # 颜色获取状态和计时器
        self.color_captured = False
        self.key_check_timer = QTimer(self)
        self.key_check_timer.timeout.connect(self.check_keys_and_position)
        self.key_check_timer.start(100)
        
        # 存储成员名称
        self.member_name = member_name
        
    def check_keys_and_position(self):
        """检查键盘输入和鼠标位置"""
        import keyboard
        if keyboard.is_pressed('space'):
            # 防止重复处理
            if self.color_captured:
                return
            
            self.color_captured = True
            self.key_check_timer.stop()
            
            # 获取当前鼠标位置的屏幕像素颜色
            try:
                import pyautogui
                x, y = pyautogui.position()
                pixel_color = pyautogui.screenshot().getpixel((x, y))
                
                # 显示获取的颜色
                color_hex = "#{:02x}{:02x}{:02x}".format(pixel_color[0], pixel_color[1], pixel_color[2])
                self.colorPreview.setStyleSheet(f"background-color: {color_hex};")
                
                # --- 将RGB转换为BGR ---
                rgb_tuple = pixel_color[:3]
                bgr_values = (rgb_tuple[2], rgb_tuple[1], rgb_tuple[0]) # B, G, R
                
                # 创建颜色上下限（允许一定范围的变化）- 使用BGR值
                import numpy as np
                self.color_lower = np.array([max(0, c - 30) for c in bgr_values], dtype=np.uint8)
                self.color_upper = np.array([min(255, c + 30) for c in bgr_values], dtype=np.uint8)
                
                self.statusLabel.setText(f"状态：成功获取颜色！RGB: {rgb_tuple}")
                self.statusLabel.setTextColor("#2ecc71", QColor(46, 204, 113))
                
                # 延迟关闭对话框
                QTimer.singleShot(1500, lambda: self.accept())
                
            except Exception as e:
                self.statusLabel.setText(f"状态：获取颜色失败 - {str(e)}")
                self.statusLabel.setTextColor("#e74c3c", QColor(231, 76, 60))
                self.color_captured = False  # 重置状态，允许重试
                self.key_check_timer.start()  # 重新启动定时器
        
        elif keyboard.is_pressed('esc'):
            if not self.color_captured:  # 只有在未捕获颜色时才处理ESC键
                self.key_check_timer.stop()
                self.reject()

class HotkeySettingsMessageBox(MessageBoxBase):
    """ Custom message box for hotkey settings """

    def __init__(self, health_monitor, parent=None):
        super().__init__(parent)
        self.titleLabel = SubtitleLabel('监控快捷键设置', self)
        self.health_monitor = health_monitor
        self.parent_window = parent
        
        # 当前快捷键展示
        self.infoLabel = BodyLabel(f"当前快捷键设置:\n开始监控: {health_monitor.start_monitoring_hotkey}\n停止监控: {health_monitor.stop_monitoring_hotkey}")
        self.infoLabel.setWordWrap(True)
        
        # 设置表单
        form_widget = QWidget()
        form_layout = QGridLayout(form_widget)
        form_layout.setSpacing(10)
        
        # 开始监控输入
        self.start_label = BodyLabel("开始监控键:")
        self.start_input = LineEdit()
        self.start_input.setText(health_monitor.start_monitoring_hotkey)
        self.start_input.setPlaceholderText("按下快捷键组合")
        
        # 停止监控输入
        self.stop_label = BodyLabel("停止监控键:")
        self.stop_input = LineEdit()
        self.stop_input.setText(health_monitor.stop_monitoring_hotkey)
        self.stop_input.setPlaceholderText("按下快捷键组合")
        
        # 错误提示标签
        self.error_label = CaptionLabel("")
        self.error_label.setTextColor("#cf1010", QColor(255, 28, 32))
        self.error_label.hide()
        
        # 增加记录按钮以记录实际按键
        self.start_record = PushButton("记录")
        self.start_record.clicked.connect(lambda: self.record_hotkey('start'))
        
        self.stop_record = PushButton("记录")
        self.stop_record.clicked.connect(lambda: self.record_hotkey('stop'))
        
        # 添加到布局
        form_layout.addWidget(self.start_label, 0, 0)
        form_layout.addWidget(self.start_input, 0, 1)
        form_layout.addWidget(self.start_record, 0, 2)
        
        form_layout.addWidget(self.stop_label, 1, 0)
        form_layout.addWidget(self.stop_input, 1, 1)
        form_layout.addWidget(self.stop_record, 1, 2)
        
        # 将所有控件添加到视图布局
        self.viewLayout.addWidget(self.titleLabel)
        self.viewLayout.addWidget(self.infoLabel)
        self.viewLayout.addWidget(form_widget)
        self.viewLayout.addWidget(self.error_label)
        
        # 设置按钮文本
        self.yesButton.setText('保存')
        self.cancelButton.setText('取消')
        
        # 设置最小宽度
        self.widget.setMinimumWidth(400)
    
    def record_hotkey(self, which):
        """弹出对话框录入快捷键"""
        from PyQt5.QtGui import QKeySequence
        
        # 创建录入对话框
        dialog = MessageBoxBase(self)
        dialog.titleLabel = SubtitleLabel('录入快捷键', dialog)
        
        # 说明标签
        guide_label = BodyLabel('请按下新的快捷键组合（如 Ctrl+Alt+S）')
        key_label = BodyLabel('等待按键...')
        
        # 添加到视图布局
        dialog.viewLayout.addWidget(dialog.titleLabel)
        dialog.viewLayout.addWidget(guide_label)
        dialog.viewLayout.addWidget(key_label)
        
        # 设置按钮文本，初始时禁用确定按钮
        dialog.yesButton.setText('确定')
        dialog.yesButton.setEnabled(False)
        dialog.cancelButton.setText('取消')
        
        # 存储按键
        key_seq = {'text': ''}
        
        # 重写keyPressEvent处理按键
        def keyPressEvent(event):
            # 保存原始方法
            original_keyPressEvent = dialog.keyPressEvent
            
            key_text = ''
            modifiers = event.modifiers()
            if modifiers & Qt.ControlModifier:
                key_text += 'ctrl+'
            if modifiers & Qt.AltModifier:
                key_text += 'alt+'
            if modifiers & Qt.ShiftModifier:
                key_text += 'shift+'
            key = event.key()
            if key in (Qt.Key_Control, Qt.Key_Alt, Qt.Key_Shift):
                # 恢复原始方法并调用它
                dialog.keyPressEvent = original_keyPressEvent
                return original_keyPressEvent(event)
            key_name = QKeySequence(key).toString().lower()
            key_text += key_name
            key_seq['text'] = key_text
            key_label.setText(f'已录入: {key_text}')
            dialog.yesButton.setEnabled(True)
            
            # 恢复原始方法
            dialog.keyPressEvent = original_keyPressEvent
        
        # 保存原始方法
        original_method = dialog.keyPressEvent
        # 替换方法
        dialog.keyPressEvent = keyPressEvent
        
        # 显示对话框
        if dialog.exec():
            if key_seq['text']:
                if which == 'start':
                    self.start_input.setText(key_seq['text'])
                else:
                    self.stop_input.setText(key_seq['text'])
    
    def validate(self):
        """验证输入是否有效"""
        start_key = self.start_input.text()
        stop_key = self.stop_input.text()
        
        # 检查输入是否有效
        if not start_key or not stop_key:
            self.error_label.setText("快捷键不能为空")
            self.error_label.show()
            return False
            
        if start_key == stop_key:
            self.error_label.setText("开始和停止快捷键不能相同")
            self.error_label.show()
            return False
        
        # 尝试设置新的快捷键
        success = self.health_monitor.set_hotkeys(start_key, stop_key)
        
        if not success:
            self.error_label.setText("设置快捷键失败，请重试")
            self.error_label.show()
            return False
            
        return True

class TeammateSelectionMessageBox(MessageBoxBase):
    """ Custom message box for teammate selection """

    def __init__(self, title, team_members, parent=None):
        super().__init__(parent)
        self.titleLabel = SubtitleLabel(title, self)
        
        # 添加说明
        self.infoLabel = BodyLabel("请从列表中选择一个队友")
        
        # 创建队友列表
        self.listWidget = QListWidget(self)
        for i, member in enumerate(team_members):
            self.listWidget.addItem(f"{member.name} ({member.profession})")
        
        # 警告标签
        self.warningLabel = CaptionLabel("未选择任何队友")
        self.warningLabel.setTextColor("#cf1010", QColor(255, 28, 32))
        self.warningLabel.hide()  # 默认隐藏
        
        # 添加到视图布局
        self.viewLayout.addWidget(self.titleLabel)
        self.viewLayout.addWidget(self.infoLabel)
        self.viewLayout.addWidget(self.listWidget)
        self.viewLayout.addWidget(self.warningLabel)
        
        # 设置按钮文本
        self.yesButton.setText('选择')
        self.cancelButton.setText('取消')
        
        # 设置最小宽度
        self.widget.setMinimumWidth(350)
        
        # 存储队友列表
        self.team_members = team_members
        self.selected_index = -1
        
        # 连接列表点击事件
        self.listWidget.itemClicked.connect(self.on_item_clicked)
    
    def on_item_clicked(self, item):
        """列表项被点击时更新选择索引"""
        self.selected_index = self.listWidget.row(item)
        self.warningLabel.hide()  # 隐藏警告
    
    def get_selected_member(self):
        """获取选中的队友"""
        if self.selected_index >= 0 and self.selected_index < len(self.team_members):
            return self.team_members[self.selected_index]
        return None
        
    def validate(self):
        """验证是否选择了队友"""
        if self.selected_index >= 0:
            return True
        else:
            self.warningLabel.show()  # 显示警告
            return False

class UnifiedColorPickerMessageBox(MessageBoxBase):
    """ Custom message box for unified color picking """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.titleLabel = SubtitleLabel('统一设置所有队友的血条颜色', self)
        
        # 添加操作指南
        self.guideLabel = BodyLabel(
            '1. 将鼠标移动到游戏中任意一个队友的血条上\n'
            '2. 选择血条最具代表性的颜色位置\n'
            '3. 按下空格键获取颜色，此颜色将应用于所有队友\n'
            '4. 按ESC键取消操作'
        )
        self.guideLabel.setWordWrap(True)
        
        # 状态标签
        self.statusLabel = CaptionLabel("状态：等待获取颜色...")
        self.statusLabel.setTextColor("#1e88e5", QColor(30, 136, 229))
        
        # 预览区域
        previewLayout = QHBoxLayout()
        previewLabel = BodyLabel('颜色预览：')
        self.colorPreview = QFrame()
        self.colorPreview.setFixedSize(50, 20)
        self.colorPreview.setFrameShape(QFrame.Box)
        previewLayout.addWidget(previewLabel)
        previewLayout.addWidget(self.colorPreview)
        previewWidget = QWidget()
        previewWidget.setLayout(previewLayout)
        
        # 添加到视图布局
        self.viewLayout.addWidget(self.titleLabel)
        self.viewLayout.addWidget(self.guideLabel)
        self.viewLayout.addWidget(self.statusLabel)
        self.viewLayout.addWidget(previewWidget)
        
        # 设置按钮文本
        self.yesButton.setText('确定')
        self.cancelButton.setText('取消')
        
        # 设置最小宽度
        self.widget.setMinimumWidth(350)
        
        # 颜色获取状态和计时器
        self.color_captured = False
        self.key_check_timer = QTimer(self)
        self.key_check_timer.timeout.connect(self.check_keys_and_position)
        self.key_check_timer.start(100)
        
        # 存储获取的颜色值
        self.pixel_color_rgb = None

    def check_keys_and_position(self):
        """检查键盘输入和鼠标位置"""
        import keyboard
        if keyboard.is_pressed('space'):
            if self.color_captured:
                return
            
            self.color_captured = True
            self.key_check_timer.stop()
            
            try:
                import pyautogui
                x, y = pyautogui.position()
                self.pixel_color_rgb = pyautogui.screenshot().getpixel((x, y))[:3]  # 确保是RGB
                
                color_hex = "#{:02x}{:02x}{:02x}".format(
                    self.pixel_color_rgb[0], 
                    self.pixel_color_rgb[1], 
                    self.pixel_color_rgb[2]
                )
                self.colorPreview.setStyleSheet(f"background-color: {color_hex};")
                
                self.statusLabel.setText(f"状态：成功获取颜色！RGB: {self.pixel_color_rgb}")
                self.statusLabel.setTextColor("#2ecc71", QColor(46, 204, 113))
                
                # 延迟关闭对话框
                QTimer.singleShot(2000, lambda: self.accept())
                
            except Exception as e:
                self.statusLabel.setText(f"状态：获取颜色失败 - {str(e)}")
                self.statusLabel.setTextColor("#e74c3c", QColor(231, 76, 60))
                self.color_captured = False
                self.key_check_timer.start()
        
        elif keyboard.is_pressed('esc'):
            if not self.color_captured:
                self.key_check_timer.stop()
                self.reject()

class MainWindow(FluentWindow):
    def __init__(self):
        """初始化主窗口"""
        super().__init__()
        
        # 初始化 pygame mixer
        try:
            pygame.mixer.init()
            pygame.mixer.set_num_channels(16) # 设置足够多的声道
        except pygame.error as e:
            print(f"Pygame mixer 初始化失败: {e}")
            # 可以选择禁用语音功能或显示错误提示
            InfoBar.error(
                title='音频初始化失败',
                content='无法初始化音频播放组件 (pygame.mixer)，语音播报功能将不可用。',
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=5000,
                parent=self
            )
        
        self._icon_capture_show_selection_timer = None
        self._icon_capture_do_grab_timer = None
        self._icon_capture_rect = None # Store the rect between timer calls
        
        # --- 添加缺失的语音参数初始化 ---
        # 初始化语音参数属性 - 使用滑块的默认值
        # 语速: slider 0-10 -> rate -50% to +50% -> + (value*10 - 50) %
        default_rate_value = 5
        self.voice_rate_param = f'+{default_rate_value * 10 - 50}%'
        # 音量: slider 0-100 -> volume -50% to +50% -> + (value - 50) %
        default_volume_value = 80
        self.voice_volume_param = f'+{default_volume_value - 50}%'
        # --- 初始化结束 ---
        
        # 设置窗口标题和大小
        self.setWindowTitle('VitalSync')
        self.resize(1200, 500) # 将高度从 800 调整为 700
        
        # 设置应用强调色 - 使用截图中的青绿色
        setThemeColor(QColor(0, 168, 174))
        
        # 启用亚克力效果
        self.navigationInterface.setAcrylicEnabled(True)
        
        # 初始化队友管理相关属性
        self.team = Team()  # 创建Team实例
        self.selection_box = None # 屏幕选择框
        
        # 初始化全局默认血条颜色
        self.default_hp_color_lower = None  # 默认血条颜色下限
        self.default_hp_color_upper = None  # 默认血条颜色上限
        self.load_default_colors()  # 从配置加载默认颜色设置
        
        # 初始化健康监控相关属性
        self.health_monitor = HealthMonitor(self.team)  # 创建健康监控实例
        # 连接监控信号
        self.health_monitor.signals.update_signal.connect(self.update_health_display)
        self.health_monitor.signals.status_signal.connect(self.update_monitor_status)
        
        # 创建界面
        self.teamRecognitionInterface = QWidget()
        self.teamRecognitionInterface.setObjectName("teamRecognitionInterface")
        
        self.healthMonitorInterface = QWidget()
        self.healthMonitorInterface.setObjectName("healthMonitorInterface")
        
        self.assistInterface = QWidget()
        self.assistInterface.setObjectName("assistInterface")
        
        self.settingsInterface = QWidget()
        self.settingsInterface.setObjectName("settingsInterface")
        
        # 新增：语音设置界面实例
        self.voiceSettingsInterface = QWidget()
        self.voiceSettingsInterface.setObjectName("voiceSettingsInterface")
        
        # 初始化界面
        self.initTeamRecognitionInterface()
        self.initHealthMonitorInterface()
        self.initAssistInterface()
        self.initSettingsInterface()
        self.initVoiceSettingsInterface() # 新增：调用语音设置界面初始化
        
        # 初始化导航
        self.initNavigation()
        
        # --- 加载设置 ---
        self.load_settings() # 在UI初始化后加载设置
        
        # 显示提示信息
        InfoBar.success(
            title='初始化完成',
            content='系统已准备就绪',
            orient=Qt.Horizontal,
            isClosable=True,
            position=InfoBarPosition.TOP,
            duration=2000,
            parent=self
        )
        
        # 在__init__方法末尾添加：
        self.load_teammates()
        
        # 初始化语音队列和工作线程
        self.speech_queue = queue.Queue()
        self.active_speech = {} # 用于跟踪正在播放的语音及其资源
        self.speech_worker_thread = threading.Thread(target=self._speech_worker_loop, daemon=True)
        self.speech_worker_thread.start()
        
        # 设置一个定时器来处理 Pygame 事件和清理
        self.pygame_event_timer = QTimer(self)
        self.pygame_event_timer.timeout.connect(self._process_pygame_events)
        self.pygame_event_timer.start(100) # 每 100ms 检查一次
    
    def initNavigation(self):
        """初始化导航栏"""
        # 添加子界面
        self.addSubInterface(self.teamRecognitionInterface, FIF.PEOPLE, '队员识别')
        self.addSubInterface(self.healthMonitorInterface, FIF.HEART, '血条监控')
        self.addSubInterface(self.assistInterface, FIF.IOT, '辅助功能')
        self.addSubInterface(self.voiceSettingsInterface, FIF.MICROPHONE, '语音设置') # 使用 FIF.MICROPHONE 图标
        
        # 添加底部界面
        self.addSubInterface(
            self.settingsInterface, 
            FIF.SETTING, 
            '系统设置',
            NavigationItemPosition.BOTTOM
        )

    def initTeamRecognitionInterface(self):
        """初始化队员识别界面"""
        layout = QVBoxLayout(self.teamRecognitionInterface)
        layout.setSpacing(24)  # 增加垂直间距
        layout.setContentsMargins(24, 24, 24, 24)  # 增加外边距
        
        # 创建顶部水平布局，包含职业图标管理和队友管理
        topLayout = QHBoxLayout()
        topLayout.setSpacing(24)  # 增加水平间距
        
        # ========== 左侧：职业图标管理 ==========
        iconCard = HeaderCardWidget(self.teamRecognitionInterface)
        iconCard.setTitle("职业图标管理")
        iconCard.setFixedHeight(200)  # 适当减少卡片高度
        iconLayout = QVBoxLayout()
        iconLayout.setSpacing(15)  # 增加垂直间距
        iconLayout.setContentsMargins(0, 10, 0, 10)  # 增加内边距
        
        # 按钮区域 - 也使用网格布局
        btnLayout = QGridLayout()
        btnLayout.setSpacing(15)  # 增加按钮间距
        
        addIconBtn = PrimaryPushButton('添加图标')
        addIconBtn.setIcon(FIF.ADD)
        addIconBtn.setFixedWidth(140)  # 显著增加按钮宽度
        addIconBtn.setMinimumHeight(36)  # 设置最小高度
        
        captureIconBtn = PushButton('截取图标')
        captureIconBtn.setIcon(FIF.CAMERA) # 使用 CAMERA 图标替代 SCREENSHOT
        captureIconBtn.setFixedWidth(140)  # 显著增加按钮宽度
        captureIconBtn.setMinimumHeight(36)  # 设置最小高度
        
        manageIconsBtn = PushButton('管理图标')
        manageIconsBtn.setIcon(FIF.SETTING)
        manageIconsBtn.setFixedWidth(140)  # 显著增加按钮宽度
        manageIconsBtn.setMinimumHeight(36)  # 设置最小高度
        
        # 连接按钮事件
        addIconBtn.clicked.connect(self.addProfessionIcon)
        captureIconBtn.clicked.connect(self.captureScreenIcon)
        manageIconsBtn.clicked.connect(self.loadProfessionIcons)
        
        # 将按钮添加到网格布局
        btnLayout.addWidget(addIconBtn, 0, 0)
        btnLayout.addWidget(captureIconBtn, 0, 1)
        btnLayout.addWidget(manageIconsBtn, 0, 2)
        
        # 显示图标数量信息
        profession_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "profession_icons")
        
        # 检查文件夹是否存在
        if not os.path.exists(profession_path):
            os.makedirs(profession_path)
            icon_count = 0
        else:
            icon_count = len([f for f in os.listdir(profession_path) if f.endswith(('.png', '.jpg', '.jpeg'))])
            
        infoLabel = BodyLabel(f'已加载 {icon_count} 个职业图标')
        infoLabel.setStyleSheet("color: #666; font-size: 13px;")  # 设置样式，使其显示更清晰
        infoLabel.setAlignment(Qt.AlignCenter)  # 居中对齐
        
        # 添加到卡片布局
        iconLayout.addLayout(btnLayout)
        iconLayout.addWidget(infoLabel)
        iconLayout.addStretch(1)  # 添加弹性空间，将内容推向顶部，使标签居中
        iconCardWidget = QWidget()
        iconCardWidget.setLayout(iconLayout)
        iconCard.viewLayout.addWidget(iconCardWidget)
        self.iconCardWidget = iconCardWidget
        
        # ========== 右侧：队友管理 ==========
        teammateCard = HeaderCardWidget(self.teamRecognitionInterface)
        teammateCard.setTitle("队友管理")
        teammateCard.setFixedHeight(200)  # 适当减少卡片高度
        teammateLayout = QVBoxLayout()
        teammateLayout.setSpacing(30)  # 增加垂直间距
        teammateLayout.setContentsMargins(0, 0, 0, 10)  # 顶部margin设为0，整体上移
        
        # 队友管理按钮区域 - 使用网格布局确保均匀分布
        teammateBtnLayout = QGridLayout()  # 改回网格布局
        teammateBtnLayout.setSpacing(18)  # 进一步增加基础间距 (原为15)
        teammateBtnLayout.setVerticalSpacing(48)  # 大幅增大垂直间距 (原为20)
        teammateBtnLayout.setContentsMargins(10, 0, 10, 0)  # 保持或调整水平内边距
        
        addTeammateBtn = PrimaryPushButton('添加队友')
        addTeammateBtn.setIcon(FIF.ADD)
        addTeammateBtn.setFixedWidth(115)  # 进一步减少按钮宽度 (原为125)
        addTeammateBtn.setMinimumHeight(36)  # 保持按钮高度
        
        removeTeammateBtn = PushButton('移除队友')
        removeTeammateBtn.setIcon(FIF.REMOVE)
        removeTeammateBtn.setFixedWidth(115)  # 进一步减少按钮宽度 (原为125)
        removeTeammateBtn.setMinimumHeight(36)  # 保持按钮高度
        
        loadTeammateBtn = PushButton('加载队友')
        loadTeammateBtn.setIcon(FIF.DOWNLOAD)
        loadTeammateBtn.setFixedWidth(115)  # 进一步减少按钮宽度 (原为125)
        loadTeammateBtn.setMinimumHeight(36)  # 保持按钮高度
        
        clearAllTeammatesBtn = PushButton('清除全部')
        clearAllTeammatesBtn.setIcon(FIF.DELETE)
        clearAllTeammatesBtn.setFixedWidth(115)  # 进一步减少按钮宽度 (原为125)
        clearAllTeammatesBtn.setMinimumHeight(36)  # 保持按钮高度
        
        # 连接按钮事件
        addTeammateBtn.clicked.connect(self.addTeammate)
        removeTeammateBtn.clicked.connect(self.removeTeammate)
        loadTeammateBtn.clicked.connect(self.loadTeammate)
        clearAllTeammatesBtn.clicked.connect(self.clearAllTeammates)
        
        # 使用网格布局均匀排列按钮，2行2列，修正行号并增加间距
        teammateBtnLayout.addWidget(addTeammateBtn, 0, 0)      # 第1行第1列
        teammateBtnLayout.addWidget(removeTeammateBtn, 0, 1)   # 第1行第2列
        teammateBtnLayout.addWidget(loadTeammateBtn, 1, 0)     # 第2行第1列
        teammateBtnLayout.addWidget(clearAllTeammatesBtn, 1, 1) # 第2行第2列
        
        # 队友信息显示
        teammateInfoLabel = BodyLabel('')
        teammateInfoLabel.setObjectName("teammateInfoLabel")  # 设置对象名以便更新时查找
        teammateInfoLabel.setWordWrap(True)  # 允许文字换行
        teammateInfoLabel.setStyleSheet("color: #666; font-size: 13px;")  # 设置样式，使其显示更清晰
        teammateInfoLabel.setAlignment(Qt.AlignCenter)  # 居中对齐
        
        # 添加到卡片布局
        teammateLayout.addLayout(teammateBtnLayout)
        teammateLayout.addWidget(teammateInfoLabel)
        teammateLayout.addStretch(1)  # 添加弹性空间，将内容推向顶部，使标签居中
        teammateCardWidget = QWidget()
        teammateCardWidget.setLayout(teammateLayout)
        teammateCard.viewLayout.addWidget(teammateCardWidget)
        
        # 将两个卡片添加到顶部布局
        topLayout.addWidget(iconCard, 1) # 设置伸展因子为1
        topLayout.addWidget(teammateCard, 1) # 设置伸展因子为1
        
        # ========== 识别队友区域 ==========
        recognitionCard = HeaderCardWidget(self.teamRecognitionInterface)
        recognitionCard.setTitle("识别队友")
        recognitionLayout = QVBoxLayout()
        recognitionLayout.setSpacing(18)  # 增加垂直间距
        recognitionLayout.setContentsMargins(0, 8, 0, 8)  # 增加内边距
        
        # 控制面板区域
        controlsPanel = QFrame()
        controlsPanel.setObjectName("cardFrame")
        controlsPanelLayout = QHBoxLayout(controlsPanel)
        controlsPanelLayout.setSpacing(16)
        controlsPanelLayout.setContentsMargins(16, 12, 16, 12)  # 增加内边距使内容更加突出
        
        # 选择识别位置按钮
        selectPositionBtn = PrimaryPushButton("选择识别位置")
        selectPositionBtn.setIcon(FIF.EDIT)
        selectPositionBtn.setMinimumWidth(160)  # 增加按钮宽度
        
        # 识别状态显示
        statusLabel = BodyLabel("状态: 未开始识别")
        statusLabel.setStyleSheet("color: #888; font-size: 14px;")  # 调整样式
        
        controlsPanelLayout.addWidget(selectPositionBtn)
        controlsPanelLayout.addWidget(statusLabel)
        controlsPanelLayout.addStretch(1)
        
        # 预览区域
        previewArea = QFrame()
        previewArea.setObjectName("cardFrame")
        # 修改：使用浅色背景和深色文字
        previewArea.setStyleSheet("#cardFrame{background-color: #f8f9fa; color: #333333; border-radius: 10px; border: 1px solid #e0e0e0;}") 
        previewLayout = QVBoxLayout(previewArea)
        previewLayout.setContentsMargins(10, 10, 10, 10)  # 添加内边距
        
        previewTitle = QLabel("队友信息预览")
        previewTitle.setAlignment(Qt.AlignCenter)
        # 修改：标题文字颜色改为深色
        previewTitle.setStyleSheet("color: #333333; font-size: 16px; font-weight: bold; margin-bottom: 10px;")
        
        # 创建滚动区域
        scrollArea = ScrollArea()
        scrollArea.setWidgetResizable(True)
        scrollArea.setStyleSheet("background: transparent; border: none;")
        
        scrollContent = QWidget()
        scrollLayout = QVBoxLayout(scrollContent)
        scrollLayout.setContentsMargins(0, 0, 0, 0)
        scrollLayout.setSpacing(8)
        
        # 创建队友信息标签
        self.teammateInfoPreview = QLabel("加载队友信息中...")
        self.teammateInfoPreview.setWordWrap(True)
        # 修改：默认文字颜色改为深色
        self.teammateInfoPreview.setStyleSheet("color: #333333; font-size: 14px;") 
        scrollLayout.addWidget(self.teammateInfoPreview)
        
        scrollArea.setWidget(scrollContent)
        
        previewLayout.addWidget(previewTitle)
        previewLayout.addWidget(scrollArea)
        
        # 添加更新按钮
        updateInfoBtn = PushButton("刷新队友信息")
        updateInfoBtn.setIcon(FIF.SYNC)
        updateInfoBtn.clicked.connect(self.update_teammate_preview)
        previewLayout.addWidget(updateInfoBtn)
        
        # 底部控制按钮
        buttonLayout = QHBoxLayout()
        buttonLayout.setSpacing(16)
        
        startBtn = PrimaryPushButton("开始识别")
        startBtn.setIcon(FIF.PLAY)
        startBtn.setMinimumWidth(130)  # 增加按钮宽度
        
        stopBtn = PushButton("停止")
        stopBtn.setIcon(FIF.CANCEL)
        stopBtn.setMinimumWidth(130)  # 增加按钮宽度
        
        saveBtn = PushButton("导出配置")
        saveBtn.setIcon(FIF.SAVE)
        saveBtn.setMinimumWidth(130)  # 增加按钮宽度
        
        # 连接按钮事件
        selectPositionBtn.clicked.connect(self.select_recognition_position)
        startBtn.clicked.connect(self.start_recognition_from_calibration)
        stopBtn.clicked.connect(self.stop_recognition)
        saveBtn.clicked.connect(self.export_recognition_config)
        
        # 然后继续添加按钮到布局
        buttonLayout.addStretch(1)
        buttonLayout.addWidget(startBtn)
        buttonLayout.addWidget(stopBtn)
        buttonLayout.addWidget(saveBtn)
        buttonLayout.addStretch(1)
        
        # 添加到识别布局
        recognitionLayout.addWidget(controlsPanel)
        recognitionLayout.addWidget(previewArea)
        recognitionLayout.addLayout(buttonLayout)
        
        recognitionCardWidget = QWidget()
        recognitionCardWidget.setLayout(recognitionLayout)
        recognitionCard.viewLayout.addWidget(recognitionCardWidget)
        
        # 添加到主布局
        layout.addLayout(topLayout)
        layout.addWidget(recognitionCard, 1)  # 1表示伸展因子，让这个区域占据更多空间
        
    def loadProfessionIcons(self):
        """加载职业图标并显示管理对话框"""
        # 使用自定义无边框对话框
        manage_dialog = ProfessionIconsManageDialog(self)
        manage_dialog.exec()
    
    def deleteProfessionIcon(self, icon_file, frame, dialog=None):
        """删除职业图标"""
        profession_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "profession_icons")
        icon_path = os.path.join(profession_path, icon_file)
        
        # 确认删除
        confirm_dialog = ConfirmMessageBox(
            "确认删除",
            f"确定要删除职业图标 {os.path.splitext(icon_file)[0]} 吗？",
            self if not dialog else dialog # Keep ConfirmMessageBox parented to dialog for modality
        )
        
        if confirm_dialog.exec():
            try:
                # 删除文件
                os.remove(icon_path)
                # 从UI中移除
                frame.setParent(None)
                frame.deleteLater()
                # 更新图标计数
                self.updateIconCount()
                # 提示成功
                InfoBar.success(
                    title='删除成功',
                    content=f'已删除职业图标 {os.path.splitext(icon_file)[0]}',
                    orient=Qt.Horizontal,
                    isClosable=True,
                    position=InfoBarPosition.TOP,
                    duration=2000,
                    parent=self  # Ensure InfoBar is parented to MainWindow
                )
            except Exception as e:
                # 删除失败提示
                InfoBar.error(
                    title='删除失败',
                    content=str(e),
                    orient=Qt.Horizontal,
                    isClosable=True,
                    position=InfoBarPosition.TOP,
                    duration=3000,
                    parent=self  # Ensure InfoBar is parented to MainWindow
                )

    def initHealthMonitorInterface(self):
        """初始化血条监控界面"""
        layout = QVBoxLayout(self.healthMonitorInterface)
        layout.setSpacing(16)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # 标题和状态信息
        titleLayout = QHBoxLayout()
        titleLabel = StrongBodyLabel("血条实时监控")
        titleLabel.setStyleSheet("font-size: 18px; font-weight: bold;")
        
        self.monitor_status_label = BodyLabel("准备就绪")
        self.monitor_status_label.setStyleSheet("color: #3498db;")
        titleLayout.addWidget(titleLabel)
        titleLayout.addStretch(1)
        titleLayout.addWidget(self.monitor_status_label)
        
        # 控制按钮区域
        controlLayout = QHBoxLayout()
        
        startMonitorBtn = PrimaryPushButton("开始监控")
        startMonitorBtn.setIcon(FIF.PLAY)
        startMonitorBtn.setMinimumWidth(120)
        
        stopMonitorBtn = PushButton("停止监控")
        stopMonitorBtn.setIcon(FIF.CLOSE)
        stopMonitorBtn.setMinimumWidth(120)
        
        # 新增：设置血条颜色按钮
        setColorBtn = PushButton("设置血条颜色")
        setColorBtn.setIcon(FIF.PALETTE) # 使用 PALETTE 图标替代 COLOR
        setColorBtn.setMinimumWidth(120)
        
        # 新增：统一设置血条颜色按钮
        setAllColorsBtn = PushButton("统一设置颜色")
        setAllColorsBtn.setIcon(FIF.BRUSH) # 使用 BRUSH 图标
        setAllColorsBtn.setMinimumWidth(120)
        
        # 连接按钮事件
        startMonitorBtn.clicked.connect(self.health_monitor.start_monitoring)
        stopMonitorBtn.clicked.connect(self.health_monitor.stop_monitoring)
        setColorBtn.clicked.connect(self.setTeammateHealthBarColor)  # 连接到单个设置方法
        setAllColorsBtn.clicked.connect(self.handleSetAllTeammatesColor) # 连接到统一设置方法
        
        controlLayout.addWidget(startMonitorBtn)
        controlLayout.addWidget(stopMonitorBtn)
        controlLayout.addWidget(setColorBtn)  # 添加单个设置按钮
        controlLayout.addWidget(setAllColorsBtn) # 添加统一设置按钮
        controlLayout.addStretch(1)
        
        # 血条展示区域
        self.health_bars_frame = QFrame()
        self.health_bars_frame.setObjectName("cardFrame")
        self.health_bars_frame.setStyleSheet("QFrame#cardFrame { background-color: rgba(240, 240, 240, 0.7); border-radius: 8px; padding: 10px; }")
        healthBarsLayout = QVBoxLayout(self.health_bars_frame)
        healthBarsLayout.setSpacing(12)
        healthBarsLayout.setContentsMargins(15, 15, 15, 15)
        
        # 初始化血条UI
        self.init_health_bars_ui()
        
        # 添加到监控布局
        layout.addLayout(titleLayout)
        layout.addLayout(controlLayout)
        layout.addWidget(self.health_bars_frame, 1)  # 将监控卡片设置为可伸展，占用更多空间
        
        # 设置卡片
        settingsCard = HeaderCardWidget(self.healthMonitorInterface)
        settingsCard.setTitle("血条监控设置")
        
        settingsLayout = QVBoxLayout()
        settingsLayout.setSpacing(12)
        
        # 基本设置组
        paramsGroup = QGroupBox("监控参数", self.healthMonitorInterface)
        paramsGroupLayout = QVBoxLayout()
        
        # 阈值设置
        thresholdLayout = QHBoxLayout()
        thresholdLabel = BodyLabel(f"血条阈值: {int(self.health_monitor.health_threshold)}%")
        thresholdSlider = Slider(Qt.Horizontal)
        thresholdSlider.setRange(0, 100)
        thresholdSlider.setValue(int(self.health_monitor.health_threshold))
        thresholdLayout.addWidget(thresholdLabel)
        thresholdLayout.addWidget(thresholdSlider)
        thresholdSlider.valueChanged.connect(lambda v: self.update_health_threshold(v, thresholdLabel))
        
        # 采样率设置
        samplingLayout = QHBoxLayout()
        samplingLabel = BodyLabel("采样率 (fps):")
        samplingSpinBox = SpinBox()
        samplingSpinBox.setRange(1, 60)
        samplingSpinBox.setValue(10)
        samplingLayout.addWidget(samplingLabel)
        samplingLayout.addWidget(samplingSpinBox)
        
        # 添加所有参数设置
        paramsGroupLayout.addLayout(thresholdLayout)
        paramsGroupLayout.addLayout(samplingLayout)
        
        # 自动点击低血量队友功能开关
        autoClickLayout = QHBoxLayout()
        autoClickLabel = BodyLabel("自动点击低血量队友:")
        self.autoClickSwitch = SwitchButton()
        # 从 HealthMonitor 加载初始状态
        if hasattr(self, 'health_monitor') and hasattr(self.health_monitor, 'auto_select_enabled'):
            self.autoClickSwitch.setChecked(self.health_monitor.auto_select_enabled)
        else:
            self.autoClickSwitch.setChecked(False) # 默认关闭
        
        # 新增：职业优先级下拉框
        priorityLabel = BodyLabel("优先职业:")
        self.priorityComboBox = ComboBox()
        self.priorityComboBox.setFixedWidth(120)
        # 加载所有职业选项
        self.load_profession_options()
        # 设置当前选中值
        if hasattr(self, 'health_monitor') and hasattr(self.health_monitor, 'priority_profession'):
            priority_index = self.priorityComboBox.findText(self.health_monitor.priority_profession)
            if priority_index >= 0:
                self.priorityComboBox.setCurrentIndex(priority_index)
        
        # 连接信号
        self.autoClickSwitch.checkedChanged.connect(self.toggle_auto_click_low_health)
        self.priorityComboBox.currentTextChanged.connect(self.update_priority_profession)
        
        autoClickLayout.addWidget(autoClickLabel)
        autoClickLayout.addWidget(self.autoClickSwitch)
        autoClickLayout.addSpacing(20)  # 增加间距
        autoClickLayout.addWidget(priorityLabel)
        autoClickLayout.addWidget(self.priorityComboBox)
        autoClickLayout.addStretch(1)
        paramsGroupLayout.addLayout(autoClickLayout) # 添加到参数组布局
        
        paramsGroup.setLayout(paramsGroupLayout)
        
        # 添加到主设置布局
        settingsLayout.addWidget(paramsGroup)
        settingsCardWidget = QWidget()
        settingsCardWidget.setLayout(settingsLayout)
        settingsCard.viewLayout.addWidget(settingsCardWidget)
        
        # 添加卡片到主布局，但设置较小的高度比例
        layout.addWidget(settingsCard)
        
        # 更新采样率设置
        samplingSpinBox.valueChanged.connect(self.update_sampling_rate)
    
    def init_health_bars_ui(self):
        """初始化血条UI显示"""
        if not self.health_bars_frame:
            return

        # 清除现有布局中的所有组件
        current_layout = self.health_bars_frame.layout()
        if current_layout is not None:
            while current_layout.count():
                item = current_layout.takeAt(0)
                widget = item.widget()
                if widget:
                    widget.deleteLater()
        else:
            # 如果布局不存在，则创建一个新的
            new_layout = QVBoxLayout(self.health_bars_frame)
            new_layout.setSpacing(12)
            new_layout.setContentsMargins(15, 15, 15, 15)
            self.health_bars_frame.setLayout(new_layout) # 设置新布局
        
        # --- 新增：按血条 y1, x1 坐标对队员进行排序 ---
        sorted_members = sorted(self.team.members, key=lambda m: (m.y1, m.x1))
        
        # 添加队友信息卡片
        for i, member in enumerate(sorted_members): # 使用排序后的列表
            self.add_health_bar_card(i, member.name, member.profession)
            
        # 如果没有队友，显示提示信息
        if not self.team.members and self.health_bars_frame.layout() is not None: # 检查原始列表判断是否有队友
            noMemberLabel = StrongBodyLabel("没有队友信息。请在队员识别页面添加队友。")
            noMemberLabel.setAlignment(Qt.AlignCenter)
            self.health_bars_frame.layout().addWidget(noMemberLabel)
        
        # 添加：强制更新框架，确保UI刷新
        self.health_bars_frame.update()
    
    def add_health_bar_card(self, index, name, profession):
        """添加血条卡片
        
        参数:
            index: 队友索引
            name: 队友名称
            profession: 队友职业
        """
        # 创建水平布局，每一行一个队员
        memberCard = QFrame()
        memberCard.setObjectName(f"member_card_{index}")
        memberCard.setFixedHeight(60)  # 设置固定高度
        memberCard.setStyleSheet("background-color: transparent;")
        memberLayout = QHBoxLayout(memberCard)
        memberLayout.setContentsMargins(5, 0, 5, 0)
        memberLayout.setSpacing(10)
        
        # 队员编号和名称 - 使用实际名称
        nameLabel = StrongBodyLabel(name)
        nameLabel.setObjectName(f"name_label_{index}")
        nameLabel.setStyleSheet("font-size: 14px; font-weight: bold;")
        nameLabel.setFixedWidth(80)
        
        # 修改：直接显示识别到的职业名称
        roleLabel = BodyLabel(str(profession)) # 确保是字符串
        roleLabel.setStyleSheet("color: #666; font-size: 12px;")
        roleLabel.setFixedWidth(60)
        roleLabel.setToolTip(str(profession)) # 添加悬浮提示显示完整职业名
        
        # 血条容器
        healthBarContainer = QFrame()
        healthBarContainer.setFixedHeight(25)
        healthBarContainer.setStyleSheet("background-color: #333; border-radius: 5px;")
        # --- 添加：设置最大宽度 --- 
        MAX_WIDTH = 300  # 与 update_health_display 中保持一致
        healthBarContainer.setMaximumWidth(MAX_WIDTH) 
        # --- 结束添加 ---
        healthBarContainerLayout = QHBoxLayout(healthBarContainer)
        healthBarContainerLayout.setContentsMargins(2, 2, 2, 2)
        healthBarContainerLayout.setSpacing(0)
        
        # 血条
        healthBar = QFrame()
        healthBar.setObjectName(f"health_bar_{index}")
        healthBar.setFixedHeight(21)
        
        # 根据索引设置不同颜色
        color = "#2ecc71"  # 绿色 (默认，表示90%)
        if index == 1:
            color = "#2ecc71"  # 绿色 (70%)
        elif index == 2:
            color = "#f39c12"  # 黄色 (50%)
        elif index == 3:
            color = "#e74c3c"  # 红色 (30%)
        elif index == 4:
            color = "#e74c3c"  # 红色 (10%)
        
        # 设置默认百分比
        default_percentage = 90
        if index == 1:
            default_percentage = 70
        elif index == 2:
            default_percentage = 50
        elif index == 3:
            default_percentage = 30
        elif index == 4:
            default_percentage = 10
        
        # 设置血条缩放因子和最大宽度
        SCALE_FACTOR = 3
        MAX_WIDTH = 300  # 血条最大宽度
        
        # 计算血条宽度
        bar_width = min(int(default_percentage * SCALE_FACTOR), MAX_WIDTH)
        print(f"队员{index+1} 初始血条宽度: {bar_width}px (血量: {default_percentage}%)")
        
        healthBar.setStyleSheet(f"background-color: {color}; border-radius: 3px;")
        healthBar.setFixedWidth(bar_width)  # 使用计算的宽度
        
        healthBarContainerLayout.addWidget(healthBar)
        healthBarContainerLayout.addStretch(1)
        
        # 血量百分比
        valueLabel = StrongBodyLabel(f"{default_percentage}%")
        valueLabel.setObjectName(f"value_label_{index}")
        valueLabel.setStyleSheet(f"color: {color}; font-weight: bold; font-size: 15px;")
        valueLabel.setAlignment(Qt.AlignCenter)
        valueLabel.setFixedWidth(60)
        
        # 添加调试标签 - 开发期间使用，显示实际内部存储的血量
        debugLabel = QLabel(f"dbg:ok")
        debugLabel.setObjectName(f"debug_label_{index}")
        debugLabel.setStyleSheet("color: #999; font-size: 8px;")
        debugLabel.setFixedWidth(50)
        
        # 添加到卡片布局
        memberLayout.addWidget(nameLabel)
        memberLayout.addWidget(roleLabel)
        memberLayout.addWidget(healthBarContainer)
        memberLayout.addWidget(valueLabel)
        memberLayout.addWidget(debugLabel)  # 添加调试标签
        
        # 添加到主布局
        self.health_bars_frame.layout().addWidget(memberCard)
        
        # 添加分隔线（除了最后一个）
        if index < len(self.team.members) - 1:
            separator = QFrame()
            separator.setFrameShape(QFrame.HLine)
            separator.setFrameShadow(QFrame.Sunken)
            separator.setStyleSheet("background-color: #e0e0e0;")
            separator.setFixedHeight(1)
            self.health_bars_frame.layout().addWidget(separator)
    
    def update_sampling_rate(self, value):
        """更新监控采样率
        
        参数:
            value: 采样率值（fps）
        """
        if hasattr(self, 'health_monitor'):
            # 转换为更新间隔（秒）
            interval = 1.0 / value if value > 0 else 0.1
            self.health_monitor.update_interval = interval
            self.update_monitor_status(f"采样率已更新: {value} fps (更新间隔: {interval:.2f}秒)")
    
    def show_hotkey_settings(self):
        """显示快捷键设置对话框"""
        dialog = HotkeySettingsMessageBox(self.health_monitor, self)
        dialog.exec()
    
    def show_error_message(self, message):
        """显示错误消息
        
        参数:
            message: 错误消息
        """
        InfoBar.error(
            title='错误',
            content=message,
            orient=Qt.Horizontal,
            isClosable=True,
            position=InfoBarPosition.TOP,
            duration=3000,
            parent=self
        )
    
    def set_auto_select(self, enabled):
        """设置自动选择功能
        
        参数:
            enabled: 是否启用
        """
        if hasattr(self, 'health_monitor'):
            self.health_monitor.auto_select_enabled = enabled
            self.health_monitor.save_auto_select_config()
            status = "启用" if enabled else "禁用"
            self.update_monitor_status(f"自动选择功能已{status}")

    def initAssistInterface(self):
        """初始化辅助功能界面"""
        layout = QVBoxLayout(self.assistInterface)
        layout.setSpacing(16)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # 左右布局，左侧为主要功能，右侧为次要功能
        mainLayout = QHBoxLayout()
        mainLayout.setSpacing(16)
        
        # 左侧布局 - 现在只包含快捷键设置
        leftLayout = QVBoxLayout()
        leftLayout.setSpacing(16)
        
        # 快捷键卡片
        hotkeyCard = HeaderCardWidget(self.assistInterface)
        hotkeyCard.setTitle("快捷键设置")
        
        hotkeyLayout = QVBoxLayout()
        hotkeyLayout.setSpacing(12)
        
        # 提示信息
        hotkey_info = BodyLabel("设置全局快捷键用于快速操作。点击\"记录\"按钮后，按下想要设置的键。")
        hotkey_info.setWordWrap(True)
        
        # 快捷键表格
        hotkeyGridLayout = QGridLayout()
        hotkeyGridLayout.setSpacing(12)
        
        # 开始监控
        startMonitorLabel = BodyLabel('开始监控:')
        startMonitorEdit = LineEdit()
        startMonitorEdit.setReadOnly(True)
        startMonitorEdit.setText(self.health_monitor.start_monitoring_hotkey)
        startMonitorRecordBtn = PushButton('记录')
        
        # 停止监控
        stopMonitorLabel = BodyLabel('停止监控:')
        stopMonitorEdit = LineEdit()
        stopMonitorEdit.setReadOnly(True)
        stopMonitorEdit.setText(self.health_monitor.stop_monitoring_hotkey)
        stopMonitorRecordBtn = PushButton('记录')
        
        # 绑定"记录"按钮事件，使用事件过滤器方式
        startMonitorRecordBtn.clicked.connect(lambda: self.install_hotkey_event_filter(startMonitorEdit, stopMonitorEdit, 'start'))
        stopMonitorRecordBtn.clicked.connect(lambda: self.install_hotkey_event_filter(stopMonitorEdit, startMonitorEdit, 'stop'))
        
        # 添加到网格
        hotkeyGridLayout.addWidget(startMonitorLabel, 0, 0)
        hotkeyGridLayout.addWidget(startMonitorEdit, 0, 1)
        hotkeyGridLayout.addWidget(startMonitorRecordBtn, 0, 2)
        
        hotkeyGridLayout.addWidget(stopMonitorLabel, 1, 0)
        hotkeyGridLayout.addWidget(stopMonitorEdit, 1, 1)
        hotkeyGridLayout.addWidget(stopMonitorRecordBtn, 1, 2)
        
        # 添加所有组件到快捷键卡片
        hotkeyLayout.addWidget(hotkey_info)
        hotkeyLayout.addLayout(hotkeyGridLayout)
        # 增加状态信息标签
        self.hotkeyStatusLabel = BodyLabel('')
        hotkeyLayout.addWidget(self.hotkeyStatusLabel)
        hotkeyCardWidget = QWidget()
        hotkeyCardWidget.setLayout(hotkeyLayout)
        hotkeyCard.viewLayout.addWidget(hotkeyCardWidget)
        
        # 添加快捷键卡片到左侧布局
        leftLayout.addWidget(hotkeyCard)
        leftLayout.addStretch(1)
        
        # 右侧布局 - 保持不变
        rightLayout = QVBoxLayout()
        rightLayout.setSpacing(16)
        
        # 数据导出卡片
        exportCard = HeaderCardWidget(self.assistInterface)
        exportCard.setTitle("数据导出")
        
        exportLayout = QVBoxLayout()
        exportLayout.setSpacing(12)
        
        # 导出按钮
        exportBtnsLayout = QHBoxLayout()
        
        exportCsvBtn = PushButton("导出CSV")
        exportCsvBtn.setIcon(FIF.DOWNLOAD)
        
        exportJsonBtn = PushButton("导出JSON")
        exportJsonBtn.setIcon(FIF.DOWNLOAD)
        
        exportBtnsLayout.addWidget(exportCsvBtn)
        exportBtnsLayout.addWidget(exportJsonBtn)
        exportBtnsLayout.addStretch(1)
        
        # 自动导出开关
        autoExportLayout = QHBoxLayout()
        autoExportLabel = BodyLabel("自动导出:")
        autoExportSwitch = SwitchButton()
        
        autoExportLayout.addWidget(autoExportLabel)
        autoExportLayout.addWidget(autoExportSwitch)
        autoExportLayout.addStretch(1)
        
        # 导出路径
        exportPathLayout = QHBoxLayout()
        exportPathLabel = BodyLabel("导出路径:")
        exportPathEdit = LineEdit()
        exportPathEdit.setText(os.path.join(os.path.expanduser("~"), "Documents"))
        exportPathBtn = PushButton("浏览")
        exportPathBtn.setIcon(FIF.FOLDER)
        
        exportPathLayout.addWidget(exportPathLabel)
        exportPathLayout.addWidget(exportPathEdit)
        exportPathLayout.addWidget(exportPathBtn)
        
        # 添加所有组件到导出卡片
        exportLayout.addLayout(exportBtnsLayout)
        exportLayout.addLayout(autoExportLayout)
        exportLayout.addLayout(exportPathLayout)
        exportCardWidget = QWidget()
        exportCardWidget.setLayout(exportLayout)
        exportCard.viewLayout.addWidget(exportCardWidget)
        
        # 添加导出卡片到右侧布局
        rightLayout.addWidget(exportCard)
        rightLayout.addStretch(1)
        
        # 添加左右布局到主布局
        mainLayout.addLayout(leftLayout, 2)
        mainLayout.addLayout(rightLayout, 1)
        
        # 添加主布局到辅助功能界面
        layout.addLayout(mainLayout)

    def initSettingsInterface(self):
        """初始化设置界面"""
        layout = QVBoxLayout(self.settingsInterface)
        layout.setSpacing(16)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # 基本设置卡片
        basicCard = HeaderCardWidget(self.settingsInterface)
        basicCard.setTitle("基本设置")
        
        basicLayout = QVBoxLayout()
        basicLayout.setSpacing(16)
        
        # 主题设置
        themeLayout = QHBoxLayout()
        themeLabel = BodyLabel("主题:")
        themeCombo = ComboBox()
        themeCombo.addItems(["跟随系统", "亮色模式", "暗色模式"])
        themeLayout.addWidget(themeLabel)
        themeLayout.addWidget(themeCombo)
        themeLayout.addStretch(1)
        
        # 语言设置
        languageLayout = QHBoxLayout()
        languageLabel = BodyLabel("语言:")
        languageCombo = ComboBox()
        languageCombo.addItems(["简体中文", "English"])
        languageLayout.addWidget(languageLabel)
        languageLayout.addWidget(languageCombo)
        languageLayout.addStretch(1)
        
        # 自动启动
        autoStartLayout = QHBoxLayout()
        autoStartLabel = BodyLabel("开机自动启动:")
        autoStartSwitch = SwitchButton()
        autoStartLayout.addWidget(autoStartLabel)
        autoStartLayout.addWidget(autoStartSwitch)
        autoStartLayout.addStretch(1)
        
        # 添加所有组件到基本设置卡片
        basicLayout.addLayout(themeLayout)
        basicLayout.addLayout(languageLayout)
        basicLayout.addLayout(autoStartLayout)
        basicCardWidget = QWidget()
        basicCardWidget.setLayout(basicLayout)
        basicCard.viewLayout.addWidget(basicCardWidget)
        
        # 高级设置卡片
        advancedCard = HeaderCardWidget(self.settingsInterface)
        advancedCard.setTitle("高级设置")
        
        advancedLayout = QVBoxLayout()
        advancedLayout.setSpacing(16)
        
        # 缓存设置
        cacheLayout = QHBoxLayout()
        cacheLabel = BodyLabel("缓存大小:")
        cacheSizeLabel = BodyLabel("23.5 MB")
        clearCacheBtn = PushButton("清除缓存")
        clearCacheBtn.setIcon(FIF.DELETE)
        
        cacheLayout.addWidget(cacheLabel)
        cacheLayout.addWidget(cacheSizeLabel)
        cacheLayout.addStretch(1)
        cacheLayout.addWidget(clearCacheBtn)
        
        # AI模型设置
        modelLayout = QHBoxLayout()
        modelLabel = BodyLabel("AI模型:")
        modelCombo = ComboBox()
        modelCombo.addItems(['标准模型', '轻量级模型', '高精度模型', '自娱自乐模型', '作者没钱加模型'])
        modelLayout.addWidget(modelLabel)
        modelLayout.addWidget(modelCombo)
        modelLayout.addStretch(1)
        
        # GPU加速
        gpuLayout = QHBoxLayout()
        gpuLabel = BodyLabel("GPU加速:")
        gpuSwitch = SwitchButton()
        gpuSwitch.setChecked(True)
        gpuLayout.addWidget(gpuLabel)
        gpuLayout.addWidget(gpuSwitch)
        gpuLayout.addStretch(1)
        
        # 添加所有组件到高级设置卡片
        advancedLayout.addLayout(cacheLayout)
        advancedLayout.addLayout(modelLayout)
        advancedLayout.addLayout(gpuLayout)
        advancedCardWidget = QWidget()
        advancedCardWidget.setLayout(advancedLayout)
        advancedCard.viewLayout.addWidget(advancedCardWidget)
        
        # 关于卡片
        aboutCard = HeaderCardWidget(self.settingsInterface)
        aboutCard.setTitle("关于")
        
        aboutLayout = QVBoxLayout()
        aboutLayout.setSpacing(16)
        
        # 版本信息
        versionLayout = QHBoxLayout()
        versionLabel = BodyLabel("版本:")
        versionValueLabel = BodyLabel("VitalSync 2.0.0")
        versionLayout.addWidget(versionLabel)
        versionLayout.addWidget(versionValueLabel)
        versionLayout.addStretch(1)
        
        # 关于信息
        aboutInfoLabel = BodyLabel("VitalSync 是一款专为游戏设计的队员血条识别与监控软件，支持多种游戏和场景。")
        aboutInfoLabel.setWordWrap(True)
        
        # 控制按钮
        controlLayout = QHBoxLayout()
        updateBtn = PushButton("检查更新")
        updateBtn.setIcon(FIF.UPDATE)
        
        githubBtn = PushButton("GitHub项目")
        githubBtn.setIcon(FIF.LINK)
        # 连接点击事件
        githubBtn.clicked.connect(self.openGitHubProject)
        
        controlLayout.addWidget(updateBtn)
        controlLayout.addWidget(githubBtn)
        controlLayout.addStretch(1)
        
        # 添加所有组件到关于卡片
        aboutLayout.addLayout(versionLayout)
        aboutLayout.addWidget(aboutInfoLabel)
        aboutLayout.addLayout(controlLayout)
        aboutCardWidget = QWidget()
        aboutCardWidget.setLayout(aboutLayout)
        aboutCard.viewLayout.addWidget(aboutCardWidget)
        
        # 添加所有卡片到设置界面
        layout.addWidget(basicCard)
        layout.addWidget(advancedCard)
        layout.addWidget(aboutCard)
        layout.addStretch(1)

    def openGitHubProject(self):
        """打开GitHub项目页面"""
        url = QUrl("https://github.com/yinduandafeimao/VitalSync-Pulse")
        QDesktopServices.openUrl(url)
        
        # 显示提示信息
        InfoBar.success(
            title='已打开链接',
            content='已在浏览器中打开GitHub项目页面',
            orient=Qt.Horizontal,
            isClosable=True,
            position=InfoBarPosition.TOP,
            duration=2000,
            parent=self
        )

    def addProfessionIcon(self):
        """添加新的职业图标"""
        # 检查profession_icons文件夹是否存在
        profession_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "profession_icons")
        if not os.path.exists(profession_path):
            os.makedirs(profession_path)  # 创建文件夹如果不存在
            
        # 打开文件选择对话框
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "选择职业图标",
            "",
            "图片文件 (*.png *.jpg *.jpeg)"
        )
        
        if not file_path:
            return
        
        # 获取文件名
        file_name_without_ext = os.path.splitext(os.path.basename(file_path))[0]
        
        # 使用自定义无边框对话框获取职业名称
        input_dialog = TextInputMessageBox(
            title='输入职业名称',
            label_text='请输入该职业图标的名称:',
            default_text=file_name_without_ext,
            placeholder_text='例如：奶妈、坦克、输出',
            parent=self
        )
        
        if not input_dialog.exec():
            return
        
        icon_name = input_dialog.get_text()
        if not icon_name:
            InfoBar.warning(
                title='输入无效',
                content='职业名称不能为空。',
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=2000,
                parent=self
            )
            return
        
        # 构造目标路径
        target_path = os.path.join(profession_path, icon_name + os.path.splitext(file_path)[1])
        
        # 检查是否已存在同名文件
        if os.path.exists(target_path):
            confirm_dialog = ConfirmMessageBox(
                "文件已存在",
                f"职业 '{icon_name}' 已存在，是否覆盖?",
                self
            )
            
            if not confirm_dialog.exec():
                return
        
        try:
            # 复制文件
            import shutil
            shutil.copy2(file_path, target_path)
            
            # 显示成功消息
            InfoBar.success(
                title='添加成功',
                content=f'职业图标 {icon_name} 已添加',
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=2000,
                parent=self
            )
            
            # 更新图标数量显示
            self.updateIconCount()
        except Exception as e:
            # 显示错误消息
            InfoBar.error(
                title='添加失败',
                content=str(e),
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=3000,
                parent=self
            )
    
    def updateIconCount(self):
        """更新职业图标数量显示"""
        # 重新计算图标数量
        profession_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "profession_icons")
        icon_count = len([f for f in os.listdir(profession_path) if f.endswith(('.png', '.jpg', '.jpeg'))])
        
        # 查找信息标签并更新
        for i in range(self.iconCardWidget.layout().count()):
            item = self.iconCardWidget.layout().itemAt(i)
            if item.widget() and isinstance(item.widget(), BodyLabel) and "当前已加载" in item.widget().text():
                item.widget().setText(f'当前已加载 {icon_count} 个职业图标')
                break

    def init_recognition(self):
        """初始化识别模块"""
        try:
            if self.recognition is None:
                from teammate_recognition import TeammateRecognition
                self.recognition = TeammateRecognition()
                InfoBar.success(
                    title='OCR模型加载成功',
                    content='队友识别功能已准备就绪',
                    orient=Qt.Horizontal,
                    isClosable=True,
                    position=InfoBarPosition.TOP,
                    duration=2000,
                    parent=self
                )
            return True
        except Exception as e:
            InfoBar.error(
                title='OCR初始化失败',
                content=f'错误: {str(e)}',
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=3000,
                parent=self
            )
            return False

    def addTeammate(self):
        """添加队友"""
        print("\n添加新队友:")
        
        # 使用自定义的MessageBoxBase子类
        dialog = AddTeammateMessageBox(self)
        
        if dialog.exec():
            name, profession = dialog.get_teammate_info()
            
            # 使用Team类添加队友
            new_member = self.team.add_member(name, profession)
            
            # 使用全局默认颜色设置(如果有的话)
            if self.default_hp_color_lower is not None and self.default_hp_color_upper is not None:
                import numpy as np
                new_member.hp_color_lower = np.copy(self.default_hp_color_lower)
                new_member.hp_color_upper = np.copy(self.default_hp_color_upper)
                new_member.save_config()  # 保存颜色设置到队员配置文件
            
            # 更新健康监控
            self.health_monitor.team = self.team
            self.init_health_bars_ui()
            
            # 提示设置血条位置 - 使用自定义确认对话框
            confirm_dialog = ConfirmMessageBox(
                "设置血条位置",
                f"是否立即为 {name} 设置血条位置？",
                self
            )
            
            if confirm_dialog.exec():
                # 使用选择框设置血条位置
                self.set_health_bar_position(new_member)
            
            InfoBar.success(
                title='添加成功',
                content=f'队友 {name} ({profession}) 已添加',
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                parent=self
            )

class HotkeySettingsMessageBox(MessageBoxBase):
    """ Custom message box for hotkey settings """

    def __init__(self, health_monitor, parent=None):
        super().__init__(parent)
        self.titleLabel = SubtitleLabel('监控快捷键设置', self)
        self.health_monitor = health_monitor
        self.parent_window = parent
        
        # 当前快捷键展示
        self.infoLabel = BodyLabel(f"当前快捷键设置:\n开始监控: {health_monitor.start_monitoring_hotkey}\n停止监控: {health_monitor.stop_monitoring_hotkey}")
        self.infoLabel.setWordWrap(True)
        
        # 设置表单
        form_widget = QWidget()
        form_layout = QGridLayout(form_widget)
        form_layout.setSpacing(10)
        
        # 开始监控输入
        self.start_label = BodyLabel("开始监控键:")
        self.start_input = LineEdit()
        self.start_input.setText(health_monitor.start_monitoring_hotkey)
        self.start_input.setPlaceholderText("按下快捷键组合")
        
        # 停止监控输入
        self.stop_label = BodyLabel("停止监控键:")
        self.stop_input = LineEdit()
        self.stop_input.setText(health_monitor.stop_monitoring_hotkey)
        self.stop_input.setPlaceholderText("按下快捷键组合")
        
        # 错误提示标签
        self.error_label = CaptionLabel("")
        self.error_label.setTextColor("#cf1010", QColor(255, 28, 32))
        self.error_label.hide()
        
        # 增加记录按钮以记录实际按键
        self.start_record = PushButton("记录")
        self.start_record.clicked.connect(lambda: self.record_hotkey('start'))
        
        self.stop_record = PushButton("记录")
        self.stop_record.clicked.connect(lambda: self.record_hotkey('stop'))
        
        # 添加到布局
        form_layout.addWidget(self.start_label, 0, 0)
        form_layout.addWidget(self.start_input, 0, 1)
        form_layout.addWidget(self.start_record, 0, 2)
        
        form_layout.addWidget(self.stop_label, 1, 0)
        form_layout.addWidget(self.stop_input, 1, 1)
        form_layout.addWidget(self.stop_record, 1, 2)
        
        # 将所有控件添加到视图布局
        self.viewLayout.addWidget(self.titleLabel)
        self.viewLayout.addWidget(self.infoLabel)
        self.viewLayout.addWidget(form_widget)
        self.viewLayout.addWidget(self.error_label)
        
        # 设置按钮文本
        self.yesButton.setText('保存')
        self.cancelButton.setText('取消')
        
        # 设置最小宽度
        self.widget.setMinimumWidth(400)
    
    def record_hotkey(self, which):
        """弹出对话框录入快捷键"""
        from PyQt5.QtGui import QKeySequence
        
        # 创建录入对话框
        dialog = MessageBoxBase(self)
        dialog.titleLabel = SubtitleLabel('录入快捷键', dialog)
        
        # 说明标签
        guide_label = BodyLabel('请按下新的快捷键组合（如 Ctrl+Alt+S）')
        key_label = BodyLabel('等待按键...')
        
        # 添加到视图布局
        dialog.viewLayout.addWidget(dialog.titleLabel)
        dialog.viewLayout.addWidget(guide_label)
        dialog.viewLayout.addWidget(key_label)
        
        # 设置按钮文本，初始时禁用确定按钮
        dialog.yesButton.setText('确定')
        dialog.yesButton.setEnabled(False)
        dialog.cancelButton.setText('取消')
        
        # 存储按键
        key_seq = {'text': ''}
        
        # 重写keyPressEvent处理按键
        def keyPressEvent(event):
            # 保存原始方法
            original_keyPressEvent = dialog.keyPressEvent
            
            key_text = ''
            modifiers = event.modifiers()
            if modifiers & Qt.ControlModifier:
                key_text += 'ctrl+'
            if modifiers & Qt.AltModifier:
                key_text += 'alt+'
            if modifiers & Qt.ShiftModifier:
                key_text += 'shift+'
            key = event.key()
            if key in (Qt.Key_Control, Qt.Key_Alt, Qt.Key_Shift):
                # 恢复原始方法并调用它
                dialog.keyPressEvent = original_keyPressEvent
                return original_keyPressEvent(event)
            key_name = QKeySequence(key).toString().lower()
            key_text += key_name
            key_seq['text'] = key_text
            key_label.setText(f'已录入: {key_text}')
            dialog.yesButton.setEnabled(True)
            
            # 恢复原始方法
            dialog.keyPressEvent = original_keyPressEvent
        
        # 保存原始方法
        original_method = dialog.keyPressEvent
        # 替换方法
        dialog.keyPressEvent = keyPressEvent
        
        # 显示对话框
        if dialog.exec():
            if key_seq['text']:
                if which == 'start':
                    self.start_input.setText(key_seq['text'])
                else:
                    self.stop_input.setText(key_seq['text'])
    
    def validate(self):
        """验证输入是否有效"""
        start_key = self.start_input.text()
        stop_key = self.stop_input.text()
        
        # 检查输入是否有效
        if not start_key or not stop_key:
            self.error_label.setText("快捷键不能为空")
            self.error_label.show()
            return False
            
        if start_key == stop_key:
            self.error_label.setText("开始和停止快捷键不能相同")
            self.error_label.show()
            return False
        
        # 尝试设置新的快捷键
        success = self.health_monitor.set_hotkeys(start_key, stop_key)
        
        if not success:
            self.error_label.setText("设置快捷键失败，请重试")
            self.error_label.show()
            return False
            
        return True

class TeammateSelectionMessageBox(MessageBoxBase):
    """ Custom message box for teammate selection """

    def __init__(self, title, team_members, parent=None):
        super().__init__(parent)
        self.titleLabel = SubtitleLabel(title, self)
        
        # 添加说明
        self.infoLabel = BodyLabel("请从列表中选择一个队友")
        
        # 创建队友列表
        self.listWidget = QListWidget(self)
        for i, member in enumerate(team_members):
            self.listWidget.addItem(f"{member.name} ({member.profession})")
        
        # 警告标签
        self.warningLabel = CaptionLabel("未选择任何队友")
        self.warningLabel.setTextColor("#cf1010", QColor(255, 28, 32))
        self.warningLabel.hide()  # 默认隐藏
        
        # 添加到视图布局
        self.viewLayout.addWidget(self.titleLabel)
        self.viewLayout.addWidget(self.infoLabel)
        self.viewLayout.addWidget(self.listWidget)
        self.viewLayout.addWidget(self.warningLabel)
        
        # 设置按钮文本
        self.yesButton.setText('选择')
        self.cancelButton.setText('取消')
        
        # 设置最小宽度
        self.widget.setMinimumWidth(350)
        
        # 存储队友列表
        self.team_members = team_members
        self.selected_index = -1
        
        # 连接列表点击事件
        self.listWidget.itemClicked.connect(self.on_item_clicked)
    
    def on_item_clicked(self, item):
        """列表项被点击时更新选择索引"""
        self.selected_index = self.listWidget.row(item)
        self.warningLabel.hide()  # 隐藏警告
    
    def get_selected_member(self):
        """获取选中的队友"""
        if self.selected_index >= 0 and self.selected_index < len(self.team_members):
            return self.team_members[self.selected_index]
        return None
        
    def validate(self):
        """验证是否选择了队友"""
        if self.selected_index >= 0:
            return True
        else:
            self.warningLabel.show()  # 显示警告
            return False

class UnifiedColorPickerMessageBox(MessageBoxBase):
    """ Custom message box for unified color picking """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.titleLabel = SubtitleLabel('统一设置所有队友的血条颜色', self)
        
        # 添加操作指南
        self.guideLabel = BodyLabel(
            '1. 将鼠标移动到游戏中任意一个队友的血条上\n'
            '2. 选择血条最具代表性的颜色位置\n'
            '3. 按下空格键获取颜色，此颜色将应用于所有队友\n'
            '4. 按ESC键取消操作'
        )
        self.guideLabel.setWordWrap(True)
        
        # 状态标签
        self.statusLabel = CaptionLabel("状态：等待获取颜色...")
        self.statusLabel.setTextColor("#1e88e5", QColor(30, 136, 229))
        
        # 预览区域
        previewLayout = QHBoxLayout()
        previewLabel = BodyLabel('颜色预览：')
        self.colorPreview = QFrame()
        self.colorPreview.setFixedSize(50, 20)
        self.colorPreview.setFrameShape(QFrame.Box)
        previewLayout.addWidget(previewLabel)
        previewLayout.addWidget(self.colorPreview)
        previewWidget = QWidget()
        previewWidget.setLayout(previewLayout)
        
        # 添加到视图布局
        self.viewLayout.addWidget(self.titleLabel)
        self.viewLayout.addWidget(self.guideLabel)
        self.viewLayout.addWidget(self.statusLabel)
        self.viewLayout.addWidget(previewWidget)
        
        # 设置按钮文本
        self.yesButton.setText('确定')
        self.cancelButton.setText('取消')
        
        # 设置最小宽度
        self.widget.setMinimumWidth(350)
        
        # 颜色获取状态和计时器
        self.color_captured = False
        self.key_check_timer = QTimer(self)
        self.key_check_timer.timeout.connect(self.check_keys_and_position)
        self.key_check_timer.start(100)
        
        # 存储获取的颜色值
        self.pixel_color_rgb = None

    def check_keys_and_position(self):
        """检查键盘输入和鼠标位置"""
        import keyboard
        if keyboard.is_pressed('space'):
            if self.color_captured:
                return
            
            self.color_captured = True
            self.key_check_timer.stop()
            
            try:
                import pyautogui
                x, y = pyautogui.position()
                self.pixel_color_rgb = pyautogui.screenshot().getpixel((x, y))[:3]  # 确保是RGB
                
                color_hex = "#{:02x}{:02x}{:02x}".format(
                    self.pixel_color_rgb[0], 
                    self.pixel_color_rgb[1], 
                    self.pixel_color_rgb[2]
                )
                self.colorPreview.setStyleSheet(f"background-color: {color_hex};")
                
                self.statusLabel.setText(f"状态：成功获取颜色！RGB: {self.pixel_color_rgb}")
                self.statusLabel.setTextColor("#2ecc71", QColor(46, 204, 113))
                
                # 延迟关闭对话框
                QTimer.singleShot(2000, lambda: self.accept())
                
            except Exception as e:
                self.statusLabel.setText(f"状态：获取颜色失败 - {str(e)}")
                self.statusLabel.setTextColor("#e74c3c", QColor(231, 76, 60))
                self.color_captured = False
                self.key_check_timer.start()
        
        elif keyboard.is_pressed('esc'):
            if not self.color_captured:
                self.key_check_timer.stop()
                self.reject()

class MainWindow(FluentWindow):
    def __init__(self):
        """初始化主窗口"""
        super().__init__()
        
        # 初始化 pygame mixer
        try:
            pygame.mixer.init()
            pygame.mixer.set_num_channels(16) # 设置足够多的声道
        except pygame.error as e:
            print(f"Pygame mixer 初始化失败: {e}")
            # 可以选择禁用语音功能或显示错误提示
            InfoBar.error(
                title='音频初始化失败',
                content='无法初始化音频播放组件 (pygame.mixer)，语音播报功能将不可用。',
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=5000,
                parent=self
            )
        
        self._icon_capture_show_selection_timer = None
        self._icon_capture_do_grab_timer = None
        self._icon_capture_rect = None # Store the rect between timer calls
        
        # --- 添加缺失的语音参数初始化 ---
        # 初始化语音参数属性 - 使用滑块的默认值
        # 语速: slider 0-10 -> rate -50% to +50% -> + (value*10 - 50) %
        default_rate_value = 5
        self.voice_rate_param = f'+{default_rate_value * 10 - 50}%'
        # 音量: slider 0-100 -> volume -50% to +50% -> + (value - 50) %
        default_volume_value = 80
        self.voice_volume_param = f'+{default_volume_value - 50}%'
        # --- 初始化结束 ---
        
        # 设置窗口标题和大小
        self.setWindowTitle('VitalSync')
        self.resize(1200, 500) # 将高度从 800 调整为 700
        
        # 设置应用强调色 - 使用截图中的青绿色
        setThemeColor(QColor(0, 168, 174))
        
        # 启用亚克力效果
        self.navigationInterface.setAcrylicEnabled(True)
        
        # 初始化队友管理相关属性
        self.team = Team()  # 创建Team实例
        self.selection_box = None # 屏幕选择框
        
        # 初始化全局默认血条颜色
        self.default_hp_color_lower = None  # 默认血条颜色下限
        self.default_hp_color_upper = None  # 默认血条颜色上限
        self.load_default_colors()  # 从配置加载默认颜色设置
        
        # 初始化健康监控相关属性
        self.health_monitor = HealthMonitor(self.team)  # 创建健康监控实例
        # 连接监控信号
        self.health_monitor.signals.update_signal.connect(self.update_health_display)
        self.health_monitor.signals.status_signal.connect(self.update_monitor_status)
        
        # 创建界面
        self.teamRecognitionInterface = QWidget()
        self.teamRecognitionInterface.setObjectName("teamRecognitionInterface")
        
        self.healthMonitorInterface = QWidget()
        self.healthMonitorInterface.setObjectName("healthMonitorInterface")
        
        self.assistInterface = QWidget()
        self.assistInterface.setObjectName("assistInterface")
        
        self.settingsInterface = QWidget()
        self.settingsInterface.setObjectName("settingsInterface")
        
        # 新增：语音设置界面实例
        self.voiceSettingsInterface = QWidget()
        self.voiceSettingsInterface.setObjectName("voiceSettingsInterface")
        
        # 初始化界面
        self.initTeamRecognitionInterface()
        self.initHealthMonitorInterface()
        self.initAssistInterface()
        self.initSettingsInterface()
        self.initVoiceSettingsInterface() # 新增：调用语音设置界面初始化
        
        # 初始化导航
        self.initNavigation()
        
        # --- 加载设置 ---
        self.load_settings() # 在UI初始化后加载设置
        
        # 显示提示信息
        InfoBar.success(
            title='初始化完成',
            content='系统已准备就绪',
            orient=Qt.Horizontal,
            isClosable=True,
            position=InfoBarPosition.TOP,
            duration=2000,
            parent=self
        )
        
        # 在__init__方法末尾添加：
        self.load_teammates()
        
        # 初始化语音队列和工作线程
        self.speech_queue = queue.Queue()
        self.active_speech = {} # 用于跟踪正在播放的语音及其资源
        self.speech_worker_thread = threading.Thread(target=self._speech_worker_loop, daemon=True)
        self.speech_worker_thread.start()
        
        # 设置一个定时器来处理 Pygame 事件和清理
        self.pygame_event_timer = QTimer(self)
        self.pygame_event_timer.timeout.connect(self._process_pygame_events)
        self.pygame_event_timer.start(100) # 每 100ms 检查一次
    
    def initNavigation(self):
        """初始化导航栏"""
        # 添加子界面
        self.addSubInterface(self.teamRecognitionInterface, FIF.PEOPLE, '队员识别')
        self.addSubInterface(self.healthMonitorInterface, FIF.HEART, '血条监控')
        self.addSubInterface(self.assistInterface, FIF.IOT, '辅助功能')
        self.addSubInterface(self.voiceSettingsInterface, FIF.MICROPHONE, '语音设置') # 使用 FIF.MICROPHONE 图标
        
        # 添加底部界面
        self.addSubInterface(
            self.settingsInterface, 
            FIF.SETTING, 
            '系统设置',
            NavigationItemPosition.BOTTOM
        )

    def initTeamRecognitionInterface(self):
        """初始化队员识别界面"""
        layout = QVBoxLayout(self.teamRecognitionInterface)
        layout.setSpacing(24)  # 增加垂直间距
        layout.setContentsMargins(24, 24, 24, 24)  # 增加外边距
        
        # 创建顶部水平布局，包含职业图标管理和队友管理
        topLayout = QHBoxLayout()
        topLayout.setSpacing(24)  # 增加水平间距
        
        # ========== 左侧：职业图标管理 ==========
        iconCard = HeaderCardWidget(self.teamRecognitionInterface)
        iconCard.setTitle("职业图标管理")
        iconCard.setFixedHeight(200)  # 适当减少卡片高度
        iconLayout = QVBoxLayout()
        iconLayout.setSpacing(15)  # 增加垂直间距
        iconLayout.setContentsMargins(0, 10, 0, 10)  # 增加内边距
        
        # 按钮区域 - 也使用网格布局
        btnLayout = QGridLayout()
        btnLayout.setSpacing(15)  # 增加按钮间距
        
        addIconBtn = PrimaryPushButton('添加图标')
        addIconBtn.setIcon(FIF.ADD)
        addIconBtn.setFixedWidth(140)  # 显著增加按钮宽度
        addIconBtn.setMinimumHeight(36)  # 设置最小高度
        
        captureIconBtn = PushButton('截取图标')
        captureIconBtn.setIcon(FIF.CAMERA) # 使用 CAMERA 图标替代 SCREENSHOT
        captureIconBtn.setFixedWidth(140)  # 显著增加按钮宽度
        captureIconBtn.setMinimumHeight(36)  # 设置最小高度
        
        manageIconsBtn = PushButton('管理图标')
        manageIconsBtn.setIcon(FIF.SETTING)
        manageIconsBtn.setFixedWidth(140)  # 显著增加按钮宽度
        manageIconsBtn.setMinimumHeight(36)  # 设置最小高度
        
        # 连接按钮事件
        addIconBtn.clicked.connect(self.addProfessionIcon)
        captureIconBtn.clicked.connect(self.captureScreenIcon)
        manageIconsBtn.clicked.connect(self.loadProfessionIcons)
        
        # 将按钮添加到网格布局
        btnLayout.addWidget(addIconBtn, 0, 0)
        btnLayout.addWidget(captureIconBtn, 0, 1)
        btnLayout.addWidget(manageIconsBtn, 0, 2)
        
        # 显示图标数量信息
        profession_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "profession_icons")
        
        # 检查文件夹是否存在
        if not os.path.exists(profession_path):
            os.makedirs(profession_path)
            icon_count = 0
        else:
            icon_count = len([f for f in os.listdir(profession_path) if f.endswith(('.png', '.jpg', '.jpeg'))])
            
        infoLabel = BodyLabel(f'已加载 {icon_count} 个职业图标')
        infoLabel.setStyleSheet("color: #666; font-size: 13px;")  # 设置样式，使其显示更清晰
        infoLabel.setAlignment(Qt.AlignCenter)  # 居中对齐
        
        # 添加到卡片布局
        iconLayout.addLayout(btnLayout)
        iconLayout.addWidget(infoLabel)
        iconLayout.addStretch(1)  # 添加弹性空间，将内容推向顶部，使标签居中
        iconCardWidget = QWidget()
        iconCardWidget.setLayout(iconLayout)
        iconCard.viewLayout.addWidget(iconCardWidget)
        self.iconCardWidget = iconCardWidget
        
        # ========== 右侧：队友管理 ==========
        teammateCard = HeaderCardWidget(self.teamRecognitionInterface)
        teammateCard.setTitle("队友管理")
        teammateCard.setFixedHeight(200)  # 适当减少卡片高度
        teammateLayout = QVBoxLayout()
        teammateLayout.setSpacing(30)  # 增加垂直间距
        teammateLayout.setContentsMargins(0, 0, 0, 10)  # 顶部margin设为0，整体上移
        
        # 队友管理按钮区域 - 使用网格布局确保均匀分布
        teammateBtnLayout = QGridLayout()  # 改回网格布局
        teammateBtnLayout.setSpacing(18)  # 进一步增加基础间距 (原为15)
        teammateBtnLayout.setVerticalSpacing(48)  # 大幅增大垂直间距 (原为20)
        teammateBtnLayout.setContentsMargins(10, 0, 10, 0)  # 保持或调整水平内边距
        
        addTeammateBtn = PrimaryPushButton('添加队友')
        addTeammateBtn.setIcon(FIF.ADD)
        addTeammateBtn.setFixedWidth(115)  # 进一步减少按钮宽度 (原为125)
        addTeammateBtn.setMinimumHeight(36)  # 保持按钮高度
        
        removeTeammateBtn = PushButton('移除队友')
        removeTeammateBtn.setIcon(FIF.REMOVE)
        removeTeammateBtn.setFixedWidth(115)  # 进一步减少按钮宽度 (原为125)
        removeTeammateBtn.setMinimumHeight(36)  # 保持按钮高度
        
        loadTeammateBtn = PushButton('加载队友')
        loadTeammateBtn.setIcon(FIF.DOWNLOAD)
        loadTeammateBtn.setFixedWidth(115)  # 进一步减少按钮宽度 (原为125)
        loadTeammateBtn.setMinimumHeight(36)  # 保持按钮高度
        
        clearAllTeammatesBtn = PushButton('清除全部')
        clearAllTeammatesBtn.setIcon(FIF.DELETE)
        clearAllTeammatesBtn.setFixedWidth(115)  # 进一步减少按钮宽度 (原为125)
        clearAllTeammatesBtn.setMinimumHeight(36)  # 保持按钮高度
        
        # 连接按钮事件
        addTeammateBtn.clicked.connect(self.addTeammate)
        removeTeammateBtn.clicked.connect(self.removeTeammate)
        loadTeammateBtn.clicked.connect(self.loadTeammate)
        clearAllTeammatesBtn.clicked.connect(self.clearAllTeammates)
        
        # 使用网格布局均匀排列按钮，2行2列，修正行号并增加间距
        teammateBtnLayout.addWidget(addTeammateBtn, 0, 0)      # 第1行第1列
        teammateBtnLayout.addWidget(removeTeammateBtn, 0, 1)   # 第1行第2列
        teammateBtnLayout.addWidget(loadTeammateBtn, 1, 0)     # 第2行第1列
        teammateBtnLayout.addWidget(clearAllTeammatesBtn, 1, 1) # 第2行第2列
        
        # 队友信息显示
        teammateInfoLabel = BodyLabel('')
        teammateInfoLabel.setObjectName("teammateInfoLabel")  # 设置对象名以便更新时查找
        teammateInfoLabel.setWordWrap(True)  # 允许文字换行
        teammateInfoLabel.setStyleSheet("color: #666; font-size: 13px;")  # 设置样式，使其显示更清晰
        teammateInfoLabel.setAlignment(Qt.AlignCenter)  # 居中对齐
        
        # 添加到卡片布局
        teammateLayout.addLayout(teammateBtnLayout)
        teammateLayout.addWidget(teammateInfoLabel)
        teammateLayout.addStretch(1)  # 添加弹性空间，将内容推向顶部，使标签居中
        teammateCardWidget = QWidget()
        teammateCardWidget.setLayout(teammateLayout)
        teammateCard.viewLayout.addWidget(teammateCardWidget)
        
        # 将两个卡片添加到顶部布局
        topLayout.addWidget(iconCard, 1) # 设置伸展因子为1
        topLayout.addWidget(teammateCard, 1) # 设置伸展因子为1
        
        # ========== 识别队友区域 ==========
        recognitionCard = HeaderCardWidget(self.teamRecognitionInterface)
        recognitionCard.setTitle("识别队友")
        recognitionLayout = QVBoxLayout()
        recognitionLayout.setSpacing(18)  # 增加垂直间距
        recognitionLayout.setContentsMargins(0, 8, 0, 8)  # 增加内边距
        
        # 控制面板区域
        controlsPanel = QFrame()
        controlsPanel.setObjectName("cardFrame")
        controlsPanelLayout = QHBoxLayout(controlsPanel)
        controlsPanelLayout.setSpacing(16)
        controlsPanelLayout.setContentsMargins(16, 12, 16, 12)  # 增加内边距使内容更加突出
        
        # 选择识别位置按钮
        selectPositionBtn = PrimaryPushButton("选择识别位置")
        selectPositionBtn.setIcon(FIF.EDIT)
        selectPositionBtn.setMinimumWidth(160)  # 增加按钮宽度
        
        # 识别状态显示
        statusLabel = BodyLabel("状态: 未开始识别")
        statusLabel.setStyleSheet("color: #888; font-size: 14px;")  # 调整样式
        
        controlsPanelLayout.addWidget(selectPositionBtn)
        controlsPanelLayout.addWidget(statusLabel)
        controlsPanelLayout.addStretch(1)
        
        # 预览区域
        previewArea = QFrame()
        previewArea.setObjectName("cardFrame")
        # 修改：使用浅色背景和深色文字
        previewArea.setStyleSheet("#cardFrame{background-color: #f8f9fa; color: #333333; border-radius: 10px; border: 1px solid #e0e0e0;}") 
        previewLayout = QVBoxLayout(previewArea)
        previewLayout.setContentsMargins(10, 10, 10, 10)  # 添加内边距
        
        previewTitle = QLabel("队友信息预览")
        previewTitle.setAlignment(Qt.AlignCenter)
        # 修改：标题文字颜色改为深色
        previewTitle.setStyleSheet("color: #333333; font-size: 16px; font-weight: bold; margin-bottom: 10px;")
        
        # 创建滚动区域
        scrollArea = ScrollArea()
        scrollArea.setWidgetResizable(True)
        scrollArea.setStyleSheet("background: transparent; border: none;")
        
        scrollContent = QWidget()
        scrollLayout = QVBoxLayout(scrollContent)
        scrollLayout.setContentsMargins(0, 0, 0, 0)
        scrollLayout.setSpacing(8)
        
        # 创建队友信息标签
        self.teammateInfoPreview = QLabel("加载队友信息中...")
        self.teammateInfoPreview.setWordWrap(True)
        # 修改：默认文字颜色改为深色
        self.teammateInfoPreview.setStyleSheet("color: #333333; font-size: 14px;") 
        scrollLayout.addWidget(self.teammateInfoPreview)
        
        scrollArea.setWidget(scrollContent)
        
        previewLayout.addWidget(previewTitle)
        previewLayout.addWidget(scrollArea)
        
        # 添加更新按钮
        updateInfoBtn = PushButton("刷新队友信息")
        updateInfoBtn.setIcon(FIF.SYNC)
        updateInfoBtn.clicked.connect(self.update_teammate_preview)
        previewLayout.addWidget(updateInfoBtn)
        
        # 底部控制按钮
        buttonLayout = QHBoxLayout()
        buttonLayout.setSpacing(16)
        
        startBtn = PrimaryPushButton("开始识别")
        startBtn.setIcon(FIF.PLAY)
        startBtn.setMinimumWidth(130)  # 增加按钮宽度
        
        stopBtn = PushButton("停止")
        stopBtn.setIcon(FIF.CANCEL)
        stopBtn.setMinimumWidth(130)  # 增加按钮宽度
        
        saveBtn = PushButton("导出配置")
        saveBtn.setIcon(FIF.SAVE)
        saveBtn.setMinimumWidth(130)  # 增加按钮宽度
        
        # 连接按钮事件
        selectPositionBtn.clicked.connect(self.select_recognition_position)
        startBtn.clicked.connect(self.start_recognition_from_calibration)
        stopBtn.clicked.connect(self.stop_recognition)
        saveBtn.clicked.connect(self.export_recognition_config)
        
        # 然后继续添加按钮到布局
        buttonLayout.addStretch(1)
        buttonLayout.addWidget(startBtn)
        buttonLayout.addWidget(stopBtn)
        buttonLayout.addWidget(saveBtn)
        buttonLayout.addStretch(1)
        
        # 添加到识别布局
        recognitionLayout.addWidget(controlsPanel)
        recognitionLayout.addWidget(previewArea)
        recognitionLayout.addLayout(buttonLayout)
        
        recognitionCardWidget = QWidget()
        recognitionCardWidget.setLayout(recognitionLayout)
        recognitionCard.viewLayout.addWidget(recognitionCardWidget)
        
        # 添加到主布局
        layout.addLayout(topLayout)
        layout.addWidget(recognitionCard, 1)  # 1表示伸展因子，让这个区域占据更多空间
        
    def loadProfessionIcons(self):
        """加载职业图标并显示管理对话框"""
        # 使用自定义无边框对话框
        manage_dialog = ProfessionIconsManageDialog(self)
        manage_dialog.exec()
    
    def deleteProfessionIcon(self, icon_file, frame, dialog=None):
        """删除职业图标"""
        profession_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "profession_icons")
        icon_path = os.path.join(profession_path, icon_file)
        
        # 确认删除
        confirm_dialog = ConfirmMessageBox(
            "确认删除",
            f"确定要删除职业图标 {os.path.splitext(icon_file)[0]} 吗？",
            self if not dialog else dialog # Keep ConfirmMessageBox parented to dialog for modality
        )
        
        if confirm_dialog.exec():
            try:
                # 删除文件
                os.remove(icon_path)
                # 从UI中移除
                frame.setParent(None)
                frame.deleteLater()
                # 更新图标计数
                self.updateIconCount()
                # 提示成功
                InfoBar.success(
                    title='删除成功',
                    content=f'已删除职业图标 {os.path.splitext(icon_file)[0]}',
                    orient=Qt.Horizontal,
                    isClosable=True,
                    position=InfoBarPosition.TOP,
                    duration=2000,
                    parent=self  # Ensure InfoBar is parented to MainWindow
                )
            except Exception as e:
                # 删除失败提示
                InfoBar.error(
                    title='删除失败',
                    content=str(e),
                    orient=Qt.Horizontal,
                    isClosable=True,
                    position=InfoBarPosition.TOP,
                    duration=3000,
                    parent=self  # Ensure InfoBar is parented to MainWindow
                )

    def initHealthMonitorInterface(self):
        """初始化血条监控界面"""
        layout = QVBoxLayout(self.healthMonitorInterface)
        layout.setSpacing(16)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # 标题和状态信息
        titleLayout = QHBoxLayout()
        titleLabel = StrongBodyLabel("血条实时监控")
        titleLabel.setStyleSheet("font-size: 18px; font-weight: bold;")
        
        self.monitor_status_label = BodyLabel("准备就绪")
        self.monitor_status_label.setStyleSheet("color: #3498db;")
        titleLayout.addWidget(titleLabel)
        titleLayout.addStretch(1)
        titleLayout.addWidget(self.monitor_status_label)
        
        # 控制按钮区域
        controlLayout = QHBoxLayout()
        
        startMonitorBtn = PrimaryPushButton("开始监控")
        startMonitorBtn.setIcon(FIF.PLAY)
        startMonitorBtn.setMinimumWidth(120)
        
        stopMonitorBtn = PushButton("停止监控")
        stopMonitorBtn.setIcon(FIF.CLOSE)
        stopMonitorBtn.setMinimumWidth(120)
        
        # 新增：设置血条颜色按钮
        setColorBtn = PushButton("设置血条颜色")
        setColorBtn.setIcon(FIF.PALETTE) # 使用 PALETTE 图标替代 COLOR
        setColorBtn.setMinimumWidth(120)
        
        # 新增：统一设置血条颜色按钮
        setAllColorsBtn = PushButton("统一设置颜色")
        setAllColorsBtn.setIcon(FIF.BRUSH) # 使用 BRUSH 图标
        setAllColorsBtn.setMinimumWidth(120)
        
        # 连接按钮事件
        startMonitorBtn.clicked.connect(self.health_monitor.start_monitoring)
        stopMonitorBtn.clicked.connect(self.health_monitor.stop_monitoring)
        setColorBtn.clicked.connect(self.setTeammateHealthBarColor)  # 连接到单个设置方法
        setAllColorsBtn.clicked.connect(self.handleSetAllTeammatesColor) # 连接到统一设置方法
        
        controlLayout.addWidget(startMonitorBtn)
        controlLayout.addWidget(stopMonitorBtn)
        controlLayout.addWidget(setColorBtn)  # 添加单个设置按钮
        controlLayout.addWidget(setAllColorsBtn) # 添加统一设置按钮
        controlLayout.addStretch(1)
        
        # 血条展示区域
        self.health_bars_frame = QFrame()
        self.health_bars_frame.setObjectName("cardFrame")
        self.health_bars_frame.setStyleSheet("QFrame#cardFrame { background-color: rgba(240, 240, 240, 0.7); border-radius: 8px; padding: 10px; }")
        healthBarsLayout = QVBoxLayout(self.health_bars_frame)
        healthBarsLayout.setSpacing(12)
        healthBarsLayout.setContentsMargins(15, 15, 15, 15)
        
        # 初始化血条UI
        self.init_health_bars_ui()
        
        # 添加到监控布局
        layout.addLayout(titleLayout)
        layout.addLayout(controlLayout)
        layout.addWidget(self.health_bars_frame, 1)  # 将监控卡片设置为可伸展，占用更多空间
        
        # 设置卡片
        settingsCard = HeaderCardWidget(self.healthMonitorInterface)
        settingsCard.setTitle("血条监控设置")
        
        settingsLayout = QVBoxLayout()
        settingsLayout.setSpacing(12)
        
        # 基本设置组
        paramsGroup = QGroupBox("监控参数", self.healthMonitorInterface)
        paramsGroupLayout = QVBoxLayout()
        
        # 阈值设置
        thresholdLayout = QHBoxLayout()
        thresholdLabel = BodyLabel(f"血条阈值: {int(self.health_monitor.health_threshold)}%")
        thresholdSlider = Slider(Qt.Horizontal)
        thresholdSlider.setRange(0, 100)
        thresholdSlider.setValue(int(self.health_monitor.health_threshold))
        thresholdLayout.addWidget(thresholdLabel)
        thresholdLayout.addWidget(thresholdSlider)
        thresholdSlider.valueChanged.connect(lambda v: self.update_health_threshold(v, thresholdLabel))
        
        # 采样率设置
        samplingLayout = QHBoxLayout()
        samplingLabel = BodyLabel("采样率 (fps):")
        samplingSpinBox = SpinBox()
        samplingSpinBox.setRange(1, 60)
        samplingSpinBox.setValue(10)
        samplingLayout.addWidget(samplingLabel)
        samplingLayout.addWidget(samplingSpinBox)
        
        # 添加所有参数设置
        paramsGroupLayout.addLayout(thresholdLayout)
        paramsGroupLayout.addLayout(samplingLayout)
        
        # 自动点击低血量队友功能开关
        autoClickLayout = QHBoxLayout()
        autoClickLabel = BodyLabel("自动点击低血量队友:")
        self.autoClickSwitch = SwitchButton()
        # 从 HealthMonitor 加载初始状态
        if hasattr(self, 'health_monitor') and hasattr(self.health_monitor, 'auto_select_enabled'):
            self.autoClickSwitch.setChecked(self.health_monitor.auto_select_enabled)
        else:
            self.autoClickSwitch.setChecked(False) # 默认关闭
        
        # 新增：职业优先级下拉框
        priorityLabel = BodyLabel("优先职业:")
        self.priorityComboBox = ComboBox()
        self.priorityComboBox.setFixedWidth(120)
        # 加载所有职业选项
        self.load_profession_options()
        # 设置当前选中值
        if hasattr(self, 'health_monitor') and hasattr(self.health_monitor, 'priority_profession'):
            priority_index = self.priorityComboBox.findText(self.health_monitor.priority_profession)
            if priority_index >= 0:
                self.priorityComboBox.setCurrentIndex(priority_index)
        
        # 连接信号
        self.autoClickSwitch.checkedChanged.connect(self.toggle_auto_click_low_health)
        self.priorityComboBox.currentTextChanged.connect(self.update_priority_profession)
        
        autoClickLayout.addWidget(autoClickLabel)
        autoClickLayout.addWidget(self.autoClickSwitch)
        autoClickLayout.addSpacing(20)  # 增加间距
        autoClickLayout.addWidget(priorityLabel)
        autoClickLayout.addWidget(self.priorityComboBox)
        autoClickLayout.addStretch(1)
        paramsGroupLayout.addLayout(autoClickLayout) # 添加到参数组布局
        
        paramsGroup.setLayout(paramsGroupLayout)
        
        # 添加到主设置布局
        settingsLayout.addWidget(paramsGroup)
        settingsCardWidget = QWidget()
        settingsCardWidget.setLayout(settingsLayout)
        settingsCard.viewLayout.addWidget(settingsCardWidget)
        
        # 添加卡片到主布局，但设置较小的高度比例
        layout.addWidget(settingsCard)
        
        # 更新采样率设置
        samplingSpinBox.valueChanged.connect(self.update_sampling_rate)
    
    def init_health_bars_ui(self):
        """初始化血条UI显示"""
        if not self.health_bars_frame:
            return

        # 清除现有布局中的所有组件
        current_layout = self.health_bars_frame.layout()
        if current_layout is not None:
            while current_layout.count():
                item = current_layout.takeAt(0)
                widget = item.widget()
                if widget:
                    widget.deleteLater()
        else:
            # 如果布局不存在，则创建一个新的
            new_layout = QVBoxLayout(self.health_bars_frame)
            new_layout.setSpacing(12)
            new_layout.setContentsMargins(15, 15, 15, 15)
            self.health_bars_frame.setLayout(new_layout) # 设置新布局
        
        # --- 新增：按血条 y1, x1 坐标对队员进行排序 ---
        sorted_members = sorted(self.team.members, key=lambda m: (m.y1, m.x1))
        
        # 添加队友信息卡片
        for i, member in enumerate(sorted_members): # 使用排序后的列表
            self.add_health_bar_card(i, member.name, member.profession)
            
        # 如果没有队友，显示提示信息
        if not self.team.members and self.health_bars_frame.layout() is not None: # 检查原始列表判断是否有队友
            noMemberLabel = StrongBodyLabel("没有队友信息。请在队员识别页面添加队友。")
            noMemberLabel.setAlignment(Qt.AlignCenter)
            self.health_bars_frame.layout().addWidget(noMemberLabel)
        
        # 添加：强制更新框架，确保UI刷新
        self.health_bars_frame.update()
    
    def add_health_bar_card(self, index, name, profession):
        """添加血条卡片
        
        参数:
            index: 队友索引
            name: 队友名称
            profession: 队友职业
        """
        # 创建水平布局，每一行一个队员
        memberCard = QFrame()
        memberCard.setObjectName(f"member_card_{index}")
        memberCard.setFixedHeight(60)  # 设置固定高度
        memberCard.setStyleSheet("background-color: transparent;")
        memberLayout = QHBoxLayout(memberCard)
        memberLayout.setContentsMargins(5, 0, 5, 0)
        memberLayout.setSpacing(10)
        
        # 队员编号和名称 - 使用实际名称
        nameLabel = StrongBodyLabel(name)
        nameLabel.setObjectName(f"name_label_{index}")
        nameLabel.setStyleSheet("font-size: 14px; font-weight: bold;")
        nameLabel.setFixedWidth(80)
        
        # 修改：直接显示识别到的职业名称
        roleLabel = BodyLabel(str(profession)) # 确保是字符串
        roleLabel.setStyleSheet("color: #666; font-size: 12px;")
        roleLabel.setFixedWidth(60)
        roleLabel.setToolTip(str(profession)) # 添加悬浮提示显示完整职业名
        
        # 血条容器
        healthBarContainer = QFrame()
        healthBarContainer.setFixedHeight(25)
        healthBarContainer.setStyleSheet("background-color: #333; border-radius: 5px;")
        # --- 添加：设置最大宽度 --- 
        MAX_WIDTH = 300  # 与 update_health_display 中保持一致
        healthBarContainer.setMaximumWidth(MAX_WIDTH) 
        # --- 结束添加 ---
        healthBarContainerLayout = QHBoxLayout(healthBarContainer)
        healthBarContainerLayout.setContentsMargins(2, 2, 2, 2)
        healthBarContainerLayout.setSpacing(0)
        
        # 血条
        healthBar = QFrame()
        healthBar.setObjectName(f"health_bar_{index}")
        healthBar.setFixedHeight(21)
        
        # 根据索引设置不同颜色
        color = "#2ecc71"  # 绿色 (默认，表示90%)
        if index == 1:
            color = "#2ecc71"  # 绿色 (70%)
        elif index == 2:
            color = "#f39c12"  # 黄色 (50%)
        elif index == 3:
            color = "#e74c3c"  # 红色 (30%)
        elif index == 4:
            color = "#e74c3c"  # 红色 (10%)
        
        # 设置默认百分比
        default_percentage = 90
        if index == 1:
            default_percentage = 70
        elif index == 2:
            default_percentage = 50
        elif index == 3:
            default_percentage = 30
        elif index == 4:
            default_percentage = 10
        
        # 设置血条缩放因子和最大宽度
        SCALE_FACTOR = 3
        MAX_WIDTH = 300  # 血条最大宽度
        
        # 计算血条宽度
        bar_width = min(int(default_percentage * SCALE_FACTOR), MAX_WIDTH)
        print(f"队员{index+1} 初始血条宽度: {bar_width}px (血量: {default_percentage}%)")
        
        healthBar.setStyleSheet(f"background-color: {color}; border-radius: 3px;")
        healthBar.setFixedWidth(bar_width)  # 使用计算的宽度
        
        healthBarContainerLayout.addWidget(healthBar)
        healthBarContainerLayout.addStretch(1)
        
        # 血量百分比
        valueLabel = StrongBodyLabel(f"{default_percentage}%")
        valueLabel.setObjectName(f"value_label_{index}")
        valueLabel.setStyleSheet(f"color: {color}; font-weight: bold; font-size: 15px;")
        valueLabel.setAlignment(Qt.AlignCenter)
        valueLabel.setFixedWidth(60)
        
        # 添加调试标签 - 开发期间使用，显示实际内部存储的血量
        debugLabel = QLabel(f"dbg:ok")
        debugLabel.setObjectName(f"debug_label_{index}")
        debugLabel.setStyleSheet("color: #999; font-size: 8px;")
        debugLabel.setFixedWidth(50)
        
        # 添加到卡片布局
        memberLayout.addWidget(nameLabel)
        memberLayout.addWidget(roleLabel)
        memberLayout.addWidget(healthBarContainer)
        memberLayout.addWidget(valueLabel)
        memberLayout.addWidget(debugLabel)  # 添加调试标签
        
        # 添加到主布局
        self.health_bars_frame.layout().addWidget(memberCard)
        
        # 添加分隔线（除了最后一个）
        if index < len(self.team.members) - 1:
            separator = QFrame()
            separator.setFrameShape(QFrame.HLine)
            separator.setFrameShadow(QFrame.Sunken)
            separator.setStyleSheet("background-color: #e0e0e0;")
            separator.setFixedHeight(1)
            self.health_bars_frame.layout().addWidget(separator)
    
    def update_sampling_rate(self, value):
        """更新监控采样率
        
        参数:
            value: 采样率值（fps）
        """
        if hasattr(self, 'health_monitor'):
            # 转换为更新间隔（秒）
            interval = 1.0 / value if value > 0 else 0.1
            self.health_monitor.update_interval = interval
            self.update_monitor_status(f"采样率已更新: {value} fps (更新间隔: {interval:.2f}秒)")
    
    def show_hotkey_settings(self):
        """显示快捷键设置对话框"""
        dialog = HotkeySettingsMessageBox(self.health_monitor, self)
        dialog.exec()
    
    def show_error_message(self, message):
        """显示错误消息
        
        参数:
            message: 错误消息
        """
        InfoBar.error(
            title='错误',
            content=message,
            orient=Qt.Horizontal,
            isClosable=True,
            position=InfoBarPosition.TOP,
            duration=3000,
            parent=self
        )
    
    def set_auto_select(self, enabled):
        """设置自动选择功能
        
        参数:
            enabled: 是否启用
        """
        if hasattr(self, 'health_monitor'):
            self.health_monitor.auto_select_enabled = enabled
            self.health_monitor.save_auto_select_config()
            status = "启用" if enabled else "禁用"
            self.update_monitor_status(f"自动选择功能已{status}")

    def initAssistInterface(self):
        """初始化辅助功能界面"""
        layout = QVBoxLayout(self.assistInterface)
        layout.setSpacing(16)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # 左右布局，左侧为主要功能，右侧为次要功能
        mainLayout = QHBoxLayout()
        mainLayout.setSpacing(16)
        
        # 左侧布局 - 现在只包含快捷键设置
        leftLayout = QVBoxLayout()
        leftLayout.setSpacing(16)
        
        # 快捷键卡片
        hotkeyCard = HeaderCardWidget(self.assistInterface)
        hotkeyCard.setTitle("快捷键设置")
        
        hotkeyLayout = QVBoxLayout()
        hotkeyLayout.setSpacing(12)
        
        # 提示信息
        hotkey_info = BodyLabel("设置全局快捷键用于快速操作。点击\"记录\"按钮后，按下想要设置的键。")
        hotkey_info.setWordWrap(True)
        
        # 快捷键表格
        hotkeyGridLayout = QGridLayout()
        hotkeyGridLayout.setSpacing(12)
        
        # 开始监控
        startMonitorLabel = BodyLabel('开始监控:')
        startMonitorEdit = LineEdit()
        startMonitorEdit.setReadOnly(True)
        startMonitorEdit.setText(self.health_monitor.start_monitoring_hotkey)
        startMonitorRecordBtn = PushButton('记录')
        
        # 停止监控
        stopMonitorLabel = BodyLabel('停止监控:')
        stopMonitorEdit = LineEdit()
        stopMonitorEdit.setReadOnly(True)
        stopMonitorEdit.setText(self.health_monitor.stop_monitoring_hotkey)
        stopMonitorRecordBtn = PushButton('记录')
        
        # 绑定"记录"按钮事件，使用事件过滤器方式
        startMonitorRecordBtn.clicked.connect(lambda: self.install_hotkey_event_filter(startMonitorEdit, stopMonitorEdit, 'start'))
        stopMonitorRecordBtn.clicked.connect(lambda: self.install_hotkey_event_filter(stopMonitorEdit, startMonitorEdit, 'stop'))
        
        # 添加到网格
        hotkeyGridLayout.addWidget(startMonitorLabel, 0, 0)
        hotkeyGridLayout.addWidget(startMonitorEdit, 0, 1)
        hotkeyGridLayout.addWidget(startMonitorRecordBtn, 0, 2)
        
        hotkeyGridLayout.addWidget(stopMonitorLabel, 1, 0)
        hotkeyGridLayout.addWidget(stopMonitorEdit, 1, 1)
        hotkeyGridLayout.addWidget(stopMonitorRecordBtn, 1, 2)
        
        # 添加所有组件到快捷键卡片
        hotkeyLayout.addWidget(hotkey_info)
        hotkeyLayout.addLayout(hotkeyGridLayout)
        # 增加状态信息标签
        self.hotkeyStatusLabel = BodyLabel('')
        hotkeyLayout.addWidget(self.hotkeyStatusLabel)
        hotkeyCardWidget = QWidget()
        hotkeyCardWidget.setLayout(hotkeyLayout)
        hotkeyCard.viewLayout.addWidget(hotkeyCardWidget)
        
        # 添加快捷键卡片到左侧布局
        leftLayout.addWidget(hotkeyCard)
        leftLayout.addStretch(1)
        
        # 右侧布局 - 保持不变
        rightLayout = QVBoxLayout()
        rightLayout.setSpacing(16)
        
        # 数据导出卡片
        exportCard = HeaderCardWidget(self.assistInterface)
        exportCard.setTitle("数据导出")
        
        exportLayout = QVBoxLayout()
        exportLayout.setSpacing(12)
        
        # 导出按钮
        exportBtnsLayout = QHBoxLayout()
        
        exportCsvBtn = PushButton("导出CSV")
        exportCsvBtn.setIcon(FIF.DOWNLOAD)
        
        exportJsonBtn = PushButton("导出JSON")
        exportJsonBtn.setIcon(FIF.DOWNLOAD)
        
        exportBtnsLayout.addWidget(exportCsvBtn)
        exportBtnsLayout.addWidget(exportJsonBtn)
        exportBtnsLayout.addStretch(1)
        
        # 自动导出开关
        autoExportLayout = QHBoxLayout()
        autoExportLabel = BodyLabel("自动导出:")
        autoExportSwitch = SwitchButton()
        
        autoExportLayout.addWidget(autoExportLabel)
        autoExportLayout.addWidget(autoExportSwitch)
        autoExportLayout.addStretch(1)
        
        # 导出路径
        exportPathLayout = QHBoxLayout()
        exportPathLabel = BodyLabel("导出路径:")
        exportPathEdit = LineEdit()
        exportPathEdit.setText(os.path.join(os.path.expanduser("~"), "Documents"))
        exportPathBtn = PushButton("浏览")
        exportPathBtn.setIcon(FIF.FOLDER)
        
        exportPathLayout.addWidget(exportPathLabel)
        exportPathLayout.addWidget(exportPathEdit)
        exportPathLayout.addWidget(exportPathBtn)
        
        # 添加所有组件到导出卡片
        exportLayout.addLayout(exportBtnsLayout)
        exportLayout.addLayout(autoExportLayout)
        exportLayout.addLayout(exportPathLayout)
        exportCardWidget = QWidget()
        exportCardWidget.setLayout(exportLayout)
        exportCard.viewLayout.addWidget(exportCardWidget)
        
        # 添加导出卡片到右侧布局
        rightLayout.addWidget(exportCard)
        rightLayout.addStretch(1)
        
        # 添加左右布局到主布局
        mainLayout.addLayout(leftLayout, 2)
        mainLayout.addLayout(rightLayout, 1)
        
        # 添加主布局到辅助功能界面
        layout.addLayout(mainLayout)

    def initSettingsInterface(self):
        """初始化设置界面"""
        layout = QVBoxLayout(self.settingsInterface)
        layout.setSpacing(16)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # 基本设置卡片
        basicCard = HeaderCardWidget(self.settingsInterface)
        basicCard.setTitle("基本设置")
        
        basicLayout = QVBoxLayout()
        basicLayout.setSpacing(16)
        
        # 主题设置
        themeLayout = QHBoxLayout()
        themeLabel = BodyLabel("主题:")
        themeCombo = ComboBox()
        themeCombo.addItems(["跟随系统", "亮色模式", "暗色模式"])
        themeLayout.addWidget(themeLabel)
        themeLayout.addWidget(themeCombo)
        themeLayout.addStretch(1)
        
        # 语言设置
        languageLayout = QHBoxLayout()
        languageLabel = BodyLabel("语言:")
        languageCombo = ComboBox()
        languageCombo.addItems(["简体中文", "English"])
        languageLayout.addWidget(languageLabel)
        languageLayout.addWidget(languageCombo)
        languageLayout.addStretch(1)
        
        # 自动启动
        autoStartLayout = QHBoxLayout()
        autoStartLabel = BodyLabel("开机自动启动:")
        autoStartSwitch = SwitchButton()
        autoStartLayout.addWidget(autoStartLabel)
        autoStartLayout.addWidget(autoStartSwitch)
        autoStartLayout.addStretch(1)
        
        # 添加所有组件到基本设置卡片
        basicLayout.addLayout(themeLayout)
        basicLayout.addLayout(languageLayout)
        basicLayout.addLayout(autoStartLayout)
        basicCardWidget = QWidget()
        basicCardWidget.setLayout(basicLayout)
        basicCard.viewLayout.addWidget(basicCardWidget)
        
        # 高级设置卡片
        advancedCard = HeaderCardWidget(self.settingsInterface)
        advancedCard.setTitle("高级设置")
        
        advancedLayout = QVBoxLayout()
        advancedLayout.setSpacing(16)
        
        # 缓存设置
        cacheLayout = QHBoxLayout()
        cacheLabel = BodyLabel("缓存大小:")
        cacheSizeLabel = BodyLabel("23.5 MB")
        clearCacheBtn = PushButton("清除缓存")
        clearCacheBtn.setIcon(FIF.DELETE)
        
        cacheLayout.addWidget(cacheLabel)
        cacheLayout.addWidget(cacheSizeLabel)
        cacheLayout.addStretch(1)
        cacheLayout.addWidget(clearCacheBtn)
        
        # AI模型设置
        modelLayout = QHBoxLayout()
        modelLabel = BodyLabel("AI模型:")
        modelCombo = ComboBox()
        modelCombo.addItems(['标准模型', '轻量级模型', '高精度模型', '自娱自乐模型', '作者没钱加模型'])
        modelLayout.addWidget(modelLabel)
        modelLayout.addWidget(modelCombo)
        modelLayout.addStretch(1)
        
        # GPU加速
        gpuLayout = QHBoxLayout()
        gpuLabel = BodyLabel("GPU加速:")
        gpuSwitch = SwitchButton()
        gpuSwitch.setChecked(True)
        gpuLayout.addWidget(gpuLabel)
        gpuLayout.addWidget(gpuSwitch)
        gpuLayout.addStretch(1)
        
        # 添加所有组件到高级设置卡片
        advancedLayout.addLayout(cacheLayout)
        advancedLayout.addLayout(modelLayout)
        advancedLayout.addLayout(gpuLayout)
        advancedCardWidget = QWidget()
        advancedCardWidget.setLayout(advancedLayout)
        advancedCard.viewLayout.addWidget(advancedCardWidget)
        
        # 关于卡片
        aboutCard = HeaderCardWidget(self.settingsInterface)
        aboutCard.setTitle("关于")
        
        aboutLayout = QVBoxLayout()
        aboutLayout.setSpacing(16)
        
        # 版本信息
        versionLayout = QHBoxLayout()
        versionLabel = BodyLabel("版本:")
        versionValueLabel = BodyLabel("VitalSync 2.0.0")
        versionLayout.addWidget(versionLabel)
        versionLayout.addWidget(versionValueLabel)
        versionLayout.addStretch(1)
        
        # 关于信息
        aboutInfoLabel = BodyLabel("VitalSync 是一款专为游戏设计的队员血条识别与监控软件，支持多种游戏和场景。")
        aboutInfoLabel.setWordWrap(True)
        
        # 控制按钮
        controlLayout = QHBoxLayout()
        updateBtn = PushButton("检查更新")
        updateBtn.setIcon(FIF.UPDATE)
        
        githubBtn = PushButton("GitHub项目")
        githubBtn.setIcon(FIF.LINK)
        # 连接点击事件
        githubBtn.clicked.connect(self.openGitHubProject)
        
        controlLayout.addWidget(updateBtn)
        controlLayout.addWidget(githubBtn)
        controlLayout.addStretch(1)
        
        # 添加所有组件到关于卡片
        aboutLayout.addLayout(versionLayout)
        aboutLayout.addWidget(aboutInfoLabel)
        aboutLayout.addLayout(controlLayout)
        aboutCardWidget = QWidget()
        aboutCardWidget.setLayout(aboutLayout)
        aboutCard.viewLayout.addWidget(aboutCardWidget)
        
        # 添加所有卡片到设置界面
        layout.addWidget(basicCard)
        layout.addWidget(advancedCard)
        layout.addWidget(aboutCard)
        layout.addStretch(1)

    def openGitHubProject(self):
        """打开GitHub项目页面"""
        url = QUrl("https://github.com/yinduandafeimao/VitalSync-Pulse")
        QDesktopServices.openUrl(url)
        
        # 显示提示信息
        InfoBar.success(
            title='已打开链接',
            content='已在浏览器中打开GitHub项目页面',
            orient=Qt.Horizontal,
            isClosable=True,
            position=InfoBarPosition.TOP,
            duration=2000,
            parent=self
        )

    def addProfessionIcon(self):
        """添加新的职业图标"""
        # 检查profession_icons文件夹是否存在
        profession_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "profession_icons")
        if not os.path.exists(profession_path):
            os.makedirs(profession_path)  # 创建文件夹如果不存在
            
        # 打开文件选择对话框
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "选择职业图标",
            "",
            "图片文件 (*.png *.jpg *.jpeg)"
        )
        
        if not file_path:
            return
        
        # 获取文件名
        file_name_without_ext = os.path.splitext(os.path.basename(file_path))[0]
        
        # 使用自定义无边框对话框获取职业名称
        input_dialog = TextInputMessageBox(
            title='输入职业名称',
            label_text='请输入该职业图标的名称:',
            default_text=file_name_without_ext,
            placeholder_text='例如：奶妈、坦克、输出',
            parent=self
        )
        
        if not input_dialog.exec():
            return
        
        icon_name = input_dialog.get_text()
        if not icon_name:
            InfoBar.warning(
                title='输入无效',
                content='职业名称不能为空。',
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=2000,
                parent=self
            )
            return
        
        # 构造目标路径
        target_path = os.path.join(profession_path, icon_name + os.path.splitext(file_path)[1])
        
        # 检查是否已存在同名文件
        if os.path.exists(target_path):
            confirm_dialog = ConfirmMessageBox(
                "文件已存在",
                f"职业 '{icon_name}' 已存在，是否覆盖?",
                self
            )
            
            if not confirm_dialog.exec():
                return
        
        try:
            # 复制文件
            import shutil
            shutil.copy2(file_path, target_path)
            
            # 显示成功消息
            InfoBar.success(
                title='添加成功',
                content=f'职业图标 {icon_name} 已添加',
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=2000,
                parent=self
            )
            
            # 更新图标数量显示
            self.updateIconCount()
        except Exception as e:
            # 显示错误消息
            InfoBar.error(
                title='添加失败',
                content=str(e),
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=3000,
                parent=self
            )
    
    def updateIconCount(self):
        """更新职业图标数量显示"""
        # 重新计算图标数量
        profession_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "profession_icons")
        icon_count = len([f for f in os.listdir(profession_path) if f.endswith(('.png', '.jpg', '.jpeg'))])
        
        # 查找信息标签并更新
        for i in range(self.iconCardWidget.layout().count()):
            item = self.iconCardWidget.layout().itemAt(i)
            if item.widget() and isinstance(item.widget(), BodyLabel) and "当前已加载" in item.widget().text():
                item.widget().setText(f'当前已加载 {icon_count} 个职业图标')
                break

    def init_recognition(self):
        """初始化识别模块"""
        try:
            if self.recognition is None:
                from teammate_recognition import TeammateRecognition
                self.recognition = TeammateRecognition()
                InfoBar.success(
                    title='OCR模型加载成功',
                    content='队友识别功能已准备就绪',
                    orient=Qt.Horizontal,
                    isClosable=True,
                    position=InfoBarPosition.TOP,
                    duration=2000,
                    parent=self
                )
            return True
        except Exception as e:
            InfoBar.error(
                title='OCR初始化失败',
                content=f'错误: {str(e)}',
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=3000,
                parent=self
            )
            return False

    def addTeammate(self):
        """添加队友"""
        print("\n添加新队友:")
        
        # 使用自定义的MessageBoxBase子类
        dialog = AddTeammateMessageBox(self)
        
        if dialog.exec():
            name, profession = dialog.get_teammate_info()
            
            # 使用Team类添加队友
            new_member = self.team.add_member(name, profession)
            
            # 使用全局默认颜色设置(如果有的话)
            if self.default_hp_color_lower is not None and self.default_hp_color_upper is not None:
                import numpy as np
                new_member.hp_color_lower = np.copy(self.default_hp_color_lower)
                new_member.hp_color_upper = np.copy(self.default_hp_color_upper)
                new_member.save_config()  # 保存颜色设置到队员配置文件
            
            # 更新健康监控
            self.health_monitor.team = self.team
            self.init_health_bars_ui()
            
            # 提示设置血条位置 - 使用自定义确认对话框
            confirm_dialog = ConfirmMessageBox(
                "设置血条位置",
                f"是否立即为 {name} 设置血条位置？",
                self
            )
            
            if confirm_dialog.exec():
                # 使用选择框设置血条位置
                self.set_health_bar_position(new_member)
            
            InfoBar.success(
                title='添加成功',
                content=f'队友 {name} ({profession}) 已添加',
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=2000,
                parent=self
            )
            
            # 更新队友信息显示
            self.update_teammate_info()

    def set_health_bar_position(self, member):
        """设置队员血条位置"""
        from 选择框 import show_selection_box
        
        # 定义选择完成回调
        def on_selection(rect):
            member.x1 = rect.x()
            member.y1 = rect.y()
            member.x2 = rect.x() + rect.width()
            member.y2 = rect.y() + rect.height()
            print(f"{member.name}血条起始坐标设置为: ({member.x1}, {member.y1})")
            print(f"{member.name}血条结束坐标设置为: ({member.x2}, {member.y2})")
            member.save_config()  # 保存新的坐标设置
        
        # 显示选择框
        result = show_selection_box(on_selection)
        return result

import sys
import os
import cv2
import numpy as np
import json
import threading
import pyautogui
import time
import asyncio
import edge_tts
import tempfile
import queue # 新增导入
import logging
from config_manager import ConfigManager, get_config
from config_defaults import DEFAULT_CONFIG
# 移除 playsound 导入
# from playsound import playsound
# 添加 pygame 导入
import pygame
from PyQt5.QtCore import Qt, QTimer, QByteArray, QBuffer, QIODevice, QPoint, QSize, QRect, QThread, pyqtSignal, QObject, QEvent, QUrl, QPropertyAnimation
from PyQt5.QtGui import QPixmap, QImage, QIcon, QColor, QFont, QKeySequence, QDesktopServices
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                            QLabel, QFileDialog, QFrame, QGridLayout, QSplitter, QTabWidget, QGroupBox,
                            QInputDialog, QDialog, QListWidget, QListWidgetItem, QAbstractItemView,
                            QGraphicsDropShadowEffect)

# 导入Fluent组件库
from qfluentwidgets import (FluentWindow, NavigationItemPosition, PushButton, 
                           ToolButton, PrimaryPushButton, ComboBox, RadioButton, CheckBox,
                           Slider, SwitchButton, ToggleButton, SubtitleLabel, BodyLabel,
                           Action, setTheme, Theme, MessageBox, MessageBoxBase, InfoBar, TabBar,
                           TransparentPushButton, LineEdit, StrongBodyLabel, CaptionLabel,
                           SpinBox, DoubleSpinBox, ScrollArea, CardWidget, HeaderCardWidget,
                           InfoBarPosition, NavigationInterface, setThemeColor, FluentIcon as FIF)

# 导入血条校准模块
from health_bar_calibration import HealthBarCalibration

# 导入血条监控模块
from health_monitor import HealthMonitor, MonitorSignals

# 动态导入带空格的模块
import importlib.util

# 动态导入带空格的模块
module_name = "team_members(choice box)"
module_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "team_members(choice box).py")
spec = importlib.util.spec_from_file_location(module_name, module_path)
team_members_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(team_members_module)

# 从module中获取Team和TeamMember类
Team = team_members_module.Team
TeamMember = team_members_module.TeamMember

# 设置应用全局样式
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

# 定义配置文件名
# CONFIG_FILE = 'config.json'  # 已迁移到配置管理系统

# 自定义对话框类 - 完全参照示例代码
class ColorPickerMessageBox(MessageBoxBase):
    """ Custom message box for color picking """

    def __init__(self, member_name, parent=None):
        super().__init__(parent)
        self.titleLabel = SubtitleLabel(f'设置 {member_name} 的血条颜色', self)
        
        # 添加指南标签
        self.guideLabel = BodyLabel(
            '1. 将鼠标移动到游戏中该队友的血条上\n'
            '2. 选择血条最具代表性的颜色位置\n'
            '3. 按下空格键获取颜色\n'
            '4. 按ESC键取消操作'
        )
        self.guideLabel.setWordWrap(True)
        
        # 状态标签
        self.statusLabel = CaptionLabel("状态：等待获取颜色...")
        self.statusLabel.setTextColor("#1e88e5", QColor(30, 136, 229))
        
        # 预览区域
        previewLayout = QHBoxLayout()
        previewLabel = BodyLabel('颜色预览：')
        self.colorPreview = QFrame()
        self.colorPreview.setFixedSize(50, 20)
        self.colorPreview.setFrameShape(QFrame.Box)
        previewLayout.addWidget(previewLabel)
        previewLayout.addWidget(self.colorPreview)
        previewWidget = QWidget()
        previewWidget.setLayout(previewLayout)

        # 添加到视图布局
        self.viewLayout.addWidget(self.titleLabel)
        self.viewLayout.addWidget(self.guideLabel)
        self.viewLayout.addWidget(self.statusLabel)
        self.viewLayout.addWidget(previewWidget)

        # 修改按钮文本
        self.yesButton.setText('确定')
        self.cancelButton.setText('取消')

        # 设置最小宽度
        self.widget.setMinimumWidth(350)
        
        # 颜色获取状态和计时器
        self.color_captured = False
        self.key_check_timer = QTimer(self)
        self.key_check_timer.timeout.connect(self.check_keys_and_position)
        self.key_check_timer.start(100)
        
        # 存储成员名称
        self.member_name = member_name
        
    def check_keys_and_position(self):
        """检查键盘输入和鼠标位置"""
        import keyboard
        if keyboard.is_pressed('space'):
            # 防止重复处理
            if self.color_captured:
                return
            
            self.color_captured = True
            self.key_check_timer.stop()
            
            # 获取当前鼠标位置的屏幕像素颜色
            try:
                import pyautogui
                x, y = pyautogui.position()
                pixel_color = pyautogui.screenshot().getpixel((x, y))
                
                # 显示获取的颜色
                color_hex = "#{:02x}{:02x}{:02x}".format(pixel_color[0], pixel_color[1], pixel_color[2])
                self.colorPreview.setStyleSheet(f"background-color: {color_hex};")
                
                # --- 将RGB转换为BGR ---
                rgb_tuple = pixel_color[:3]
                bgr_values = (rgb_tuple[2], rgb_tuple[1], rgb_tuple[0]) # B, G, R
                
                # 创建颜色上下限（允许一定范围的变化）- 使用BGR值
                import numpy as np
                self.color_lower = np.array([max(0, c - 30) for c in bgr_values], dtype=np.uint8)
                self.color_upper = np.array([min(255, c + 30) for c in bgr_values], dtype=np.uint8)
                
                self.statusLabel.setText(f"状态：成功获取颜色！RGB: {rgb_tuple}")
                self.statusLabel.setTextColor("#2ecc71", QColor(46, 204, 113))
                
                # 延迟关闭对话框
                QTimer.singleShot(1500, lambda: self.accept())
                
            except Exception as e:
                self.statusLabel.setText(f"状态：获取颜色失败 - {str(e)}")
                self.statusLabel.setTextColor("#e74c3c", QColor(231, 76, 60))
                self.color_captured = False  # 重置状态，允许重试
                self.key_check_timer.start()  # 重新启动定时器
        
        elif keyboard.is_pressed('esc'):
            if not self.color_captured:  # 只有在未捕获颜色时才处理ESC键
                self.key_check_timer.stop()
                self.reject()

class HotkeySettingsMessageBox(MessageBoxBase):
    """ Custom message box for hotkey settings """

    def __init__(self, health_monitor, parent=None):
        super().__init__(parent)
        self.titleLabel = SubtitleLabel('监控快捷键设置', self)
        self.health_monitor = health_monitor
        self.parent_window = parent
        
        # 当前快捷键展示
        self.infoLabel = BodyLabel(f"当前快捷键设置:\n开始监控: {health_monitor.start_monitoring_hotkey}\n停止监控: {health_monitor.stop_monitoring_hotkey}")
        self.infoLabel.setWordWrap(True)
        
        # 设置表单
        form_widget = QWidget()
        form_layout = QGridLayout(form_widget)
        form_layout.setSpacing(10)
        
        # 开始监控输入
        self.start_label = BodyLabel("开始监控键:")
        self.start_input = LineEdit()
        self.start_input.setText(health_monitor.start_monitoring_hotkey)
        self.start_input.setPlaceholderText("按下快捷键组合")
        
        # 停止监控输入
        self.stop_label = BodyLabel("停止监控键:")
        self.stop_input = LineEdit()
        self.stop_input.setText(health_monitor.stop_monitoring_hotkey)
        self.stop_input.setPlaceholderText("按下快捷键组合")
        
        # 错误提示标签
        self.error_label = CaptionLabel("")
        self.error_label.setTextColor("#cf1010", QColor(255, 28, 32))
        self.error_label.hide()
        
        # 增加记录按钮以记录实际按键
        self.start_record = PushButton("记录")
        self.start_record.clicked.connect(lambda: self.record_hotkey('start'))
        
        self.stop_record = PushButton("记录")
        self.stop_record.clicked.connect(lambda: self.record_hotkey('stop'))
        
        # 添加到布局
        form_layout.addWidget(self.start_label, 0, 0)
        form_layout.addWidget(self.start_input, 0, 1)
        form_layout.addWidget(self.start_record, 0, 2)
        
        form_layout.addWidget(self.stop_label, 1, 0)
        form_layout.addWidget(self.stop_input, 1, 1)
        form_layout.addWidget(self.stop_record, 1, 2)
        
        # 将所有控件添加到视图布局
        self.viewLayout.addWidget(self.titleLabel)
        self.viewLayout.addWidget(self.infoLabel)
        self.viewLayout.addWidget(form_widget)
        self.viewLayout.addWidget(self.error_label)
        
        # 设置按钮文本
        self.yesButton.setText('保存')
        self.cancelButton.setText('取消')
        
        # 设置最小宽度
        self.widget.setMinimumWidth(400)
    
    def record_hotkey(self, which):
        """弹出对话框录入快捷键"""
        from PyQt5.QtGui import QKeySequence
        
        # 创建录入对话框
        dialog = MessageBoxBase(self)
        dialog.titleLabel = SubtitleLabel('录入快捷键', dialog)
        
        # 说明标签
        guide_label = BodyLabel('请按下新的快捷键组合（如 Ctrl+Alt+S）')
        key_label = BodyLabel('等待按键...')
        
        # 添加到视图布局
        dialog.viewLayout.addWidget(dialog.titleLabel)
        dialog.viewLayout.addWidget(guide_label)
        dialog.viewLayout.addWidget(key_label)
        
        # 设置按钮文本，初始时禁用确定按钮
        dialog.yesButton.setText('确定')
        dialog.yesButton.setEnabled(False)
        dialog.cancelButton.setText('取消')
        
        # 存储按键
        key_seq = {'text': ''}
        
        # 重写keyPressEvent处理按键
        def keyPressEvent(event):
            # 保存原始方法
            original_keyPressEvent = dialog.keyPressEvent
            
            key_text = ''
            modifiers = event.modifiers()
            if modifiers & Qt.ControlModifier:
                key_text += 'ctrl+'
            if modifiers & Qt.AltModifier:
                key_text += 'alt+'
            if modifiers & Qt.ShiftModifier:
                key_text += 'shift+'
            key = event.key()
            if key in (Qt.Key_Control, Qt.Key_Alt, Qt.Key_Shift):
                # 恢复原始方法并调用它
                dialog.keyPressEvent = original_keyPressEvent
                return original_keyPressEvent(event)
            key_name = QKeySequence(key).toString().lower()
            key_text += key_name
            key_seq['text'] = key_text
            key_label.setText(f'已录入: {key_text}')
            dialog.yesButton.setEnabled(True)
            
            # 恢复原始方法
            dialog.keyPressEvent = original_keyPressEvent
        
        # 保存原始方法
        original_method = dialog.keyPressEvent
        # 替换方法
        dialog.keyPressEvent = keyPressEvent
        
        # 显示对话框
        if dialog.exec():
            if key_seq['text']:
                if which == 'start':
                    self.start_input.setText(key_seq['text'])
                else:
                    self.stop_input.setText(key_seq['text'])
    
    def validate(self):
        """验证输入是否有效"""
        start_key = self.start_input.text()
        stop_key = self.stop_input.text()
        
        # 检查输入是否有效
        if not start_key or not stop_key:
            self.error_label.setText("快捷键不能为空")
            self.error_label.show()
            return False
            
        if start_key == stop_key:
            self.error_label.setText("开始和停止快捷键不能相同")
            self.error_label.show()
            return False
        
        # 尝试设置新的快捷键
        success = self.health_monitor.set_hotkeys(start_key, stop_key)
        
        if not success:
            self.error_label.setText("设置快捷键失败，请重试")
            self.error_label.show()
            return False
            
        return True

class TeammateSelectionMessageBox(MessageBoxBase):
    """ Custom message box for teammate selection """

    def __init__(self, title, team_members, parent=None):
        super().__init__(parent)
        self.titleLabel = SubtitleLabel(title, self)
        
        # 添加说明
        self.infoLabel = BodyLabel("请从列表中选择一个队友")
        
        # 创建队友列表
        self.listWidget = QListWidget(self)
        for i, member in enumerate(team_members):
            self.listWidget.addItem(f"{member.name} ({member.profession})")
        
        # 警告标签
        self.warningLabel = CaptionLabel("未选择任何队友")
        self.warningLabel.setTextColor("#cf1010", QColor(255, 28, 32))
        self.warningLabel.hide()  # 默认隐藏
        
        # 添加到视图布局
        self.viewLayout.addWidget(self.titleLabel)
        self.viewLayout.addWidget(self.infoLabel)
        self.viewLayout.addWidget(self.listWidget)
        self.viewLayout.addWidget(self.warningLabel)
        
        # 设置按钮文本
        self.yesButton.setText('选择')
        self.cancelButton.setText('取消')
        
        # 设置最小宽度
        self.widget.setMinimumWidth(350)
        
        # 存储队友列表
        self.team_members = team_members
        self.selected_index = -1
        
        # 连接列表点击事件
        self.listWidget.itemClicked.connect(self.on_item_clicked)
    
    def on_item_clicked(self, item):
        """列表项被点击时更新选择索引"""
        self.selected_index = self.listWidget.row(item)
        self.warningLabel.hide()  # 隐藏警告
    
    def get_selected_member(self):
        """获取选中的队友"""
        if self.selected_index >= 0 and self.selected_index < len(self.team_members):
            return self.team_members[self.selected_index]
        return None
        
    def validate(self):
        """验证是否选择了队友"""
        if self.selected_index >= 0:
            return True
        else:
            self.warningLabel.show()  # 显示警告
            return False

class UnifiedColorPickerMessageBox(MessageBoxBase):
    """ Custom message box for unified color picking """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.titleLabel = SubtitleLabel('统一设置所有队友的血条颜色', self)
        
        # 添加操作指南
        self.guideLabel = BodyLabel(
            '1. 将鼠标移动到游戏中任意一个队友的血条上\n'
            '2. 选择血条最具代表性的颜色位置\n'
            '3. 按下空格键获取颜色，此颜色将应用于所有队友\n'
            '4. 按ESC键取消操作'
        )
        self.guideLabel.setWordWrap(True)
        
        # 状态标签
        self.statusLabel = CaptionLabel("状态：等待获取颜色...")
        self.statusLabel.setTextColor("#1e88e5", QColor(30, 136, 229))
        
        # 预览区域
        previewLayout = QHBoxLayout()
        previewLabel = BodyLabel('颜色预览：')
        self.colorPreview = QFrame()
        self.colorPreview.setFixedSize(50, 20)
        self.colorPreview.setFrameShape(QFrame.Box)
        previewLayout.addWidget(previewLabel)
        previewLayout.addWidget(self.colorPreview)
        previewWidget = QWidget()
        previewWidget.setLayout(previewLayout)
        
        # 添加到视图布局
        self.viewLayout.addWidget(self.titleLabel)
        self.viewLayout.addWidget(self.guideLabel)
        self.viewLayout.addWidget(self.statusLabel)
        self.viewLayout.addWidget(previewWidget)
        
        # 设置按钮文本
        self.yesButton.setText('确定')
        self.cancelButton.setText('取消')
        
        # 设置最小宽度
        self.widget.setMinimumWidth(350)
        
        # 颜色获取状态和计时器
        self.color_captured = False
        self.key_check_timer = QTimer(self)
        self.key_check_timer.timeout.connect(self.check_keys_and_position)
        self.key_check_timer.start(100)
        
        # 存储获取的颜色值
        self.pixel_color_rgb = None

    def check_keys_and_position(self):
        """检查键盘输入和鼠标位置"""
        import keyboard
        if keyboard.is_pressed('space'):
            if self.color_captured:
                return
            
            self.color_captured = True
            self.key_check_timer.stop()
            
            try:
                import pyautogui
                x, y = pyautogui.position()
                self.pixel_color_rgb = pyautogui.screenshot().getpixel((x, y))[:3]  # 确保是RGB
                
                color_hex = "#{:02x}{:02x}{:02x}".format(
                    self.pixel_color_rgb[0], 
                    self.pixel_color_rgb[1], 
                    self.pixel_color_rgb[2]
                )
                self.colorPreview.setStyleSheet(f"background-color: {color_hex};")
                
                self.statusLabel.setText(f"状态：成功获取颜色！RGB: {self.pixel_color_rgb}")
                self.statusLabel.setTextColor("#2ecc71", QColor(46, 204, 113))
                
                # 延迟关闭对话框
                QTimer.singleShot(2000, lambda: self.accept())
                
            except Exception as e:
                self.statusLabel.setText(f"状态：获取颜色失败 - {str(e)}")
                self.statusLabel.setTextColor("#e74c3c", QColor(231, 76, 60))
                self.color_captured = False
                self.key_check_timer.start()
        
        elif keyboard.is_pressed('esc'):
            if not self.color_captured:
                self.key_check_timer.stop()
                self.reject()

class MainWindow(FluentWindow):
    def __init__(self):
        """初始化主窗口"""
        super().__init__()
        
        # 初始化 pygame mixer
        try:
            pygame.mixer.init()
            pygame.mixer.set_num_channels(16) # 设置足够多的声道
        except pygame.error as e:
            print(f"Pygame mixer 初始化失败: {e}")
            # 可以选择禁用语音功能或显示错误提示
            InfoBar.error(
                title='音频初始化失败',
                content='无法初始化音频播放组件 (pygame.mixer)，语音播报功能将不可用。',
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=5000,
                parent=self
            )
        
        self._icon_capture_show_selection_timer = None
        self._icon_capture_do_grab_timer = None
        self._icon_capture_rect = None # Store the rect between timer calls
        
        # --- 添加缺失的语音参数初始化 ---
        # 初始化语音参数属性 - 使用滑块的默认值
        # 语速: slider 0-10 -> rate -50% to +50% -> + (value*10 - 50) %
        default_rate_value = 5
        self.voice_rate_param = f'+{default_rate_value * 10 - 50}%'
        # 音量: slider 0-100 -> volume -50% to +50% -> + (value - 50) %
        default_volume_value = 80
        self.voice_volume_param = f'+{default_volume_value - 50}%'
        # --- 初始化结束 ---
        
        # 设置窗口标题和大小
        self.setWindowTitle('VitalSync')
        self.resize(1200, 500) # 将高度从 800 调整为 700
        
        # 设置应用强调色 - 使用截图中的青绿色
        setThemeColor(QColor(0, 168, 174))
        
        # 启用亚克力效果
        self.navigationInterface.setAcrylicEnabled(True)
        
        # 初始化队友管理相关属性
        self.team = Team()  # 创建Team实例
        self.selection_box = None # 屏幕选择框
        
        # 初始化全局默认血条颜色
        self.default_hp_color_lower = None  # 默认血条颜色下限
        self.default_hp_color_upper = None  # 默认血条颜色上限
        self.load_default_colors()  # 从配置加载默认颜色设置
        
        # 初始化健康监控相关属性
        self.health_monitor = HealthMonitor(self.team)  # 创建健康监控实例
        # 连接监控信号
        self.health_monitor.signals.update_signal.connect(self.update_health_display)
        self.health_monitor.signals.status_signal.connect(self.update_monitor_status)
        
        # 创建界面
        self.teamRecognitionInterface = QWidget()
        self.teamRecognitionInterface.setObjectName("teamRecognitionInterface")
        
        self.healthMonitorInterface = QWidget()
        self.healthMonitorInterface.setObjectName("healthMonitorInterface")
        
        self.assistInterface = QWidget()
        self.assistInterface.setObjectName("assistInterface")
        
        self.settingsInterface = QWidget()
        self.settingsInterface.setObjectName("settingsInterface")
        
        # 新增：语音设置界面实例
        self.voiceSettingsInterface = QWidget()
        self.voiceSettingsInterface.setObjectName("voiceSettingsInterface")
        
        # 初始化界面
        self.initTeamRecognitionInterface()
        self.initHealthMonitorInterface()
        self.initAssistInterface()
        self.initSettingsInterface()
        self.initVoiceSettingsInterface() # 新增：调用语音设置界面初始化
        
        # 初始化导航
        self.initNavigation()
        
        # --- 加载设置 ---
        self.load_settings() # 在UI初始化后加载设置
        
        # 显示提示信息
        InfoBar.success(
            title='初始化完成',
            content='系统已准备就绪',
            orient=Qt.Horizontal,
            isClosable=True,
            position=InfoBarPosition.TOP,
            duration=2000,
            parent=self
        )
        
        # 在__init__方法末尾添加：
        self.load_teammates()
        
        # 初始化语音队列和工作线程
        self.speech_queue = queue.Queue()
        self.active_speech = {} # 用于跟踪正在播放的语音及其资源
        self.speech_worker_thread = threading.Thread(target=self._speech_worker_loop, daemon=True)
        self.speech_worker_thread.start()
        
        # 设置一个定时器来处理 Pygame 事件和清理
        self.pygame_event_timer = QTimer(self)
        self.pygame_event_timer.timeout.connect(self._process_pygame_events)
        self.pygame_event_timer.start(100) # 每 100ms 检查一次
    
    def initNavigation(self):
        """初始化导航栏"""
        # 添加子界面
        self.addSubInterface(self.teamRecognitionInterface, FIF.PEOPLE, '队员识别')
        self.addSubInterface(self.healthMonitorInterface, FIF.HEART, '血条监控')
        self.addSubInterface(self.assistInterface, FIF.IOT, '辅助功能')
        self.addSubInterface(self.voiceSettingsInterface, FIF.MICROPHONE, '语音设置') # 使用 FIF.MICROPHONE 图标
        
        # 添加底部界面
        self.addSubInterface(
            self.settingsInterface, 
            FIF.SETTING, 
            '系统设置',
            NavigationItemPosition.BOTTOM
        )

    def initTeamRecognitionInterface(self):
        """初始化队员识别界面"""
        layout = QVBoxLayout(self.teamRecognitionInterface)
        layout.setSpacing(24)  # 增加垂直间距
        layout.setContentsMargins(24, 24, 24, 24)  # 增加外边距
        
        # 创建顶部水平布局，包含职业图标管理和队友管理
        topLayout = QHBoxLayout()
        topLayout.setSpacing(24)  # 增加水平间距
        
        # ========== 左侧：职业图标管理 ==========
        iconCard = HeaderCardWidget(self.teamRecognitionInterface)
        iconCard.setTitle("职业图标管理")
        iconCard.setFixedHeight(200)  # 适当减少卡片高度
        iconLayout = QVBoxLayout()
        iconLayout.setSpacing(15)  # 增加垂直间距
        iconLayout.setContentsMargins(0, 10, 0, 10)  # 增加内边距
        
        # 按钮区域 - 也使用网格布局
        btnLayout = QGridLayout()
        btnLayout.setSpacing(15)  # 增加按钮间距
        
        addIconBtn = PrimaryPushButton('添加图标')
        addIconBtn.setIcon(FIF.ADD)
        addIconBtn.setFixedWidth(140)  # 显著增加按钮宽度
        addIconBtn.setMinimumHeight(36)  # 设置最小高度
        
        captureIconBtn = PushButton('截取图标')
        captureIconBtn.setIcon(FIF.CAMERA) # 使用 CAMERA 图标替代 SCREENSHOT
        captureIconBtn.setFixedWidth(140)  # 显著增加按钮宽度
        captureIconBtn.setMinimumHeight(36)  # 设置最小高度
        
        manageIconsBtn = PushButton('管理图标')
        manageIconsBtn.setIcon(FIF.SETTING)
        manageIconsBtn.setFixedWidth(140)  # 显著增加按钮宽度
        manageIconsBtn.setMinimumHeight(36)  # 设置最小高度
        
        # 连接按钮事件
        addIconBtn.clicked.connect(self.addProfessionIcon)
        captureIconBtn.clicked.connect(self.captureScreenIcon)
        manageIconsBtn.clicked.connect(self.loadProfessionIcons)
        
        # 将按钮添加到网格布局
        btnLayout.addWidget(addIconBtn, 0, 0)
        btnLayout.addWidget(captureIconBtn, 0, 1)
        btnLayout.addWidget(manageIconsBtn, 0, 2)
        
        # 显示图标数量信息
        profession_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "profession_icons")
        
        # 检查文件夹是否存在
        if not os.path.exists(profession_path):
            os.makedirs(profession_path)
            icon_count = 0
        else:
            icon_count = len([f for f in os.listdir(profession_path) if f.endswith(('.png', '.jpg', '.jpeg'))])
            
        infoLabel = BodyLabel(f'已加载 {icon_count} 个职业图标')
        infoLabel.setStyleSheet("color: #666; font-size: 13px;")  # 设置样式，使其显示更清晰
        infoLabel.setAlignment(Qt.AlignCenter)  # 居中对齐
        
        # 添加到卡片布局
        iconLayout.addLayout(btnLayout)
        iconLayout.addWidget(infoLabel)
        iconLayout.addStretch(1)  # 添加弹性空间，将内容推向顶部，使标签居中
        iconCardWidget = QWidget()
        iconCardWidget.setLayout(iconLayout)
        iconCard.viewLayout.addWidget(iconCardWidget)
        self.iconCardWidget = iconCardWidget
        
        # ========== 右侧：队友管理 ==========
        teammateCard = HeaderCardWidget(self.teamRecognitionInterface)
        teammateCard.setTitle("队友管理")
        teammateCard.setFixedHeight(200)  # 适当减少卡片高度
        teammateLayout = QVBoxLayout()
        teammateLayout.setSpacing(30)  # 增加垂直间距
        teammateLayout.setContentsMargins(0, 0, 0, 10)  # 顶部margin设为0，整体上移
        
        # 队友管理按钮区域 - 使用网格布局确保均匀分布
        teammateBtnLayout = QGridLayout()  # 改回网格布局
        teammateBtnLayout.setSpacing(18)  # 进一步增加基础间距 (原为15)
        teammateBtnLayout.setVerticalSpacing(48)  # 大幅增大垂直间距 (原为20)
        teammateBtnLayout.setContentsMargins(10, 0, 10, 0)  # 保持或调整水平内边距
        
        addTeammateBtn = PrimaryPushButton('添加队友')
        addTeammateBtn.setIcon(FIF.ADD)
        addTeammateBtn.setFixedWidth(115)  # 进一步减少按钮宽度 (原为125)
        addTeammateBtn.setMinimumHeight(36)  # 保持按钮高度
        
        removeTeammateBtn = PushButton('移除队友')
        removeTeammateBtn.setIcon(FIF.REMOVE)
        removeTeammateBtn.setFixedWidth(115)  # 进一步减少按钮宽度 (原为125)
        removeTeammateBtn.setMinimumHeight(36)  # 保持按钮高度
        
        loadTeammateBtn = PushButton('加载队友')
        loadTeammateBtn.setIcon(FIF.DOWNLOAD)
        loadTeammateBtn.setFixedWidth(115)  # 进一步减少按钮宽度 (原为125)
        loadTeammateBtn.setMinimumHeight(36)  # 保持按钮高度
        
        clearAllTeammatesBtn = PushButton('清除全部')
        clearAllTeammatesBtn.setIcon(FIF.DELETE)
        clearAllTeammatesBtn.setFixedWidth(115)  # 进一步减少按钮宽度 (原为125)
        clearAllTeammatesBtn.setMinimumHeight(36)  # 保持按钮高度
        
        # 连接按钮事件
        addTeammateBtn.clicked.connect(self.addTeammate)
        removeTeammateBtn.clicked.connect(self.removeTeammate)
        loadTeammateBtn.clicked.connect(self.loadTeammate)
        clearAllTeammatesBtn.clicked.connect(self.clearAllTeammates)
        
        # 使用网格布局均匀排列按钮，2行2列，修正行号并增加间距
        teammateBtnLayout.addWidget(addTeammateBtn, 0, 0)      # 第1行第1列
        teammateBtnLayout.addWidget(removeTeammateBtn, 0, 1)   # 第1行第2列
        teammateBtnLayout.addWidget(loadTeammateBtn, 1, 0)     # 第2行第1列
        teammateBtnLayout.addWidget(clearAllTeammatesBtn, 1, 1) # 第2行第2列
        
        # 队友信息显示
        teammateInfoLabel = BodyLabel('')
        teammateInfoLabel.setObjectName("teammateInfoLabel")  # 设置对象名以便更新时查找
        teammateInfoLabel.setWordWrap(True)  # 允许文字换行
        teammateInfoLabel.setStyleSheet("color: #666; font-size: 13px;")  # 设置样式，使其显示更清晰
        teammateInfoLabel.setAlignment(Qt.AlignCenter)  # 居中对齐
        
        # 添加到卡片布局
        teammateLayout.addLayout(teammateBtnLayout)
        teammateLayout.addWidget(teammateInfoLabel)
        teammateLayout.addStretch(1)  # 添加弹性空间，将内容推向顶部，使标签居中
        teammateCardWidget = QWidget()
        teammateCardWidget.setLayout(teammateLayout)
        teammateCard.viewLayout.addWidget(teammateCardWidget)
        
        # 将两个卡片添加到顶部布局
        topLayout.addWidget(iconCard, 1) # 设置伸展因子为1
        topLayout.addWidget(teammateCard, 1) # 设置伸展因子为1
        
        # ========== 识别队友区域 ==========
        recognitionCard = HeaderCardWidget(self.teamRecognitionInterface)
        recognitionCard.setTitle("识别队友")
        recognitionLayout = QVBoxLayout()
        recognitionLayout.setSpacing(18)  # 增加垂直间距
        recognitionLayout.setContentsMargins(0, 8, 0, 8)  # 增加内边距
        
        # 控制面板区域
        controlsPanel = QFrame()
        controlsPanel.setObjectName("cardFrame")
        controlsPanelLayout = QHBoxLayout(controlsPanel)
        controlsPanelLayout.setSpacing(16)
        controlsPanelLayout.setContentsMargins(16, 12, 16, 12)  # 增加内边距使内容更加突出
        
        # 选择识别位置按钮
        selectPositionBtn = PrimaryPushButton("选择识别位置")
        selectPositionBtn.setIcon(FIF.EDIT)
        selectPositionBtn.setMinimumWidth(160)  # 增加按钮宽度
        
        # 识别状态显示
        statusLabel = BodyLabel("状态: 未开始识别")
        statusLabel.setStyleSheet("color: #888; font-size: 14px;")  # 调整样式
        
        controlsPanelLayout.addWidget(selectPositionBtn)
        controlsPanelLayout.addWidget(statusLabel)
        controlsPanelLayout.addStretch(1)
        
        # 预览区域
        previewArea = QFrame()
        previewArea.setObjectName("cardFrame")
        # 修改：使用浅色背景和深色文字
        previewArea.setStyleSheet("#cardFrame{background-color: #f8f9fa; color: #333333; border-radius: 10px; border: 1px solid #e0e0e0;}") 
        previewLayout = QVBoxLayout(previewArea)
        previewLayout.setContentsMargins(10, 10, 10, 10)  # 添加内边距
        
        previewTitle = QLabel("队友信息预览")
        previewTitle.setAlignment(Qt.AlignCenter)
        # 修改：标题文字颜色改为深色
        previewTitle.setStyleSheet("color: #333333; font-size: 16px; font-weight: bold; margin-bottom: 10px;")
        
        # 创建滚动区域
        scrollArea = ScrollArea()
        scrollArea.setWidgetResizable(True)
        scrollArea.setStyleSheet("background: transparent; border: none;")
        
        scrollContent = QWidget()
        scrollLayout = QVBoxLayout(scrollContent)
        scrollLayout.setContentsMargins(0, 0, 0, 0)
        scrollLayout.setSpacing(8)
        
        # 创建队友信息标签
        self.teammateInfoPreview = QLabel("加载队友信息中...")
        self.teammateInfoPreview.setWordWrap(True)
        # 修改：默认文字颜色改为深色
        self.teammateInfoPreview.setStyleSheet("color: #333333; font-size: 14px;") 
        scrollLayout.addWidget(self.teammateInfoPreview)
        
        scrollArea.setWidget(scrollContent)
        
        previewLayout.addWidget(previewTitle)
        previewLayout.addWidget(scrollArea)
        
        # 添加更新按钮
        updateInfoBtn = PushButton("刷新队友信息")
        updateInfoBtn.setIcon(FIF.SYNC)
        updateInfoBtn.clicked.connect(self.update_teammate_preview)
        previewLayout.addWidget(updateInfoBtn)
        
        # 底部控制按钮
        buttonLayout = QHBoxLayout()
        buttonLayout.setSpacing(16)
        
        startBtn = PrimaryPushButton("开始识别")
        startBtn.setIcon(FIF.PLAY)
        startBtn.setMinimumWidth(130)  # 增加按钮宽度
        
        stopBtn = PushButton("停止")
        stopBtn.setIcon(FIF.CANCEL)
        stopBtn.setMinimumWidth(130)  # 增加按钮宽度
        
        saveBtn = PushButton("导出配置")
        saveBtn.setIcon(FIF.SAVE)
        saveBtn.setMinimumWidth(130)  # 增加按钮宽度
        
        # 连接按钮事件
        selectPositionBtn.clicked.connect(self.select_recognition_position)
        startBtn.clicked.connect(self.start_recognition_from_calibration)
        stopBtn.clicked.connect(self.stop_recognition)
        saveBtn.clicked.connect(self.export_recognition_config)
        
        # 然后继续添加按钮到布局
        buttonLayout.addStretch(1)
        buttonLayout.addWidget(startBtn)
        buttonLayout.addWidget(stopBtn)
        buttonLayout.addWidget(saveBtn)
        buttonLayout.addStretch(1)
        
        # 添加到识别布局
        recognitionLayout.addWidget(controlsPanel)
        recognitionLayout.addWidget(previewArea)
        recognitionLayout.addLayout(buttonLayout)
        
        recognitionCardWidget = QWidget()
        recognitionCardWidget.setLayout(recognitionLayout)
        recognitionCard.viewLayout.addWidget(recognitionCardWidget)
        
        # 添加到主布局
        layout.addLayout(topLayout)
        layout.addWidget(recognitionCard, 1)  # 1表示伸展因子，让这个区域占据更多空间
        
    def loadProfessionIcons(self):
        """加载职业图标并显示管理对话框"""
        # 使用自定义无边框对话框
        manage_dialog = ProfessionIconsManageDialog(self)
        manage_dialog.exec()
    
    def deleteProfessionIcon(self, icon_file, frame, dialog=None):
        """删除职业图标"""
        profession_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "profession_icons")
        icon_path = os.path.join(profession_path, icon_file)
        
        # 确认删除
        confirm_dialog = ConfirmMessageBox(
            "确认删除",
            f"确定要删除职业图标 {os.path.splitext(icon_file)[0]} 吗？",
            self if not dialog else dialog # Keep ConfirmMessageBox parented to dialog for modality
        )
        
        if confirm_dialog.exec():
            try:
                # 删除文件
                os.remove(icon_path)
                # 从UI中移除
                frame.setParent(None)
                frame.deleteLater()
                # 更新图标计数
                self.updateIconCount()
                # 提示成功
                InfoBar.success(
                    title='删除成功',
                    content=f'已删除职业图标 {os.path.splitext(icon_file)[0]}',
                    orient=Qt.Horizontal,
                    isClosable=True,
                    position=InfoBarPosition.TOP,
                    duration=2000,
                    parent=self  # Ensure InfoBar is parented to MainWindow
                )
            except Exception as e:
                # 删除失败提示
                InfoBar.error(
                    title='删除失败',
                    content=str(e),
                    orient=Qt.Horizontal,
                    isClosable=True,
                    position=InfoBarPosition.TOP,
                    duration=3000,
                    parent=self  # Ensure InfoBar is parented to MainWindow
                )

    def initHealthMonitorInterface(self):
        """初始化血条监控界面"""
        layout = QVBoxLayout(self.healthMonitorInterface)
        layout.setSpacing(16)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # 标题和状态信息
        titleLayout = QHBoxLayout()
        titleLabel = StrongBodyLabel("血条实时监控")
        titleLabel.setStyleSheet("font-size: 18px; font-weight: bold;")
        
        self.monitor_status_label = BodyLabel("准备就绪")
        self.monitor_status_label.setStyleSheet("color: #3498db;")
        titleLayout.addWidget(titleLabel)
        titleLayout.addStretch(1)
        titleLayout.addWidget(self.monitor_status_label)
        
        # 控制按钮区域
        controlLayout = QHBoxLayout()
        
        startMonitorBtn = PrimaryPushButton("开始监控")
        startMonitorBtn.setIcon(FIF.PLAY)
        startMonitorBtn.setMinimumWidth(120)
        
        stopMonitorBtn = PushButton("停止监控")
        stopMonitorBtn.setIcon(FIF.CLOSE)
        stopMonitorBtn.setMinimumWidth(120)
        
        # 新增：设置血条颜色按钮
        setColorBtn = PushButton("设置血条颜色")
        setColorBtn.setIcon(FIF.PALETTE) # 使用 PALETTE 图标替代 COLOR
        setColorBtn.setMinimumWidth(120)
        
        # 新增：统一设置血条颜色按钮
        setAllColorsBtn = PushButton("统一设置颜色")
        setAllColorsBtn.setIcon(FIF.BRUSH) # 使用 BRUSH 图标
        setAllColorsBtn.setMinimumWidth(120)
        
        # 连接按钮事件
        startMonitorBtn.clicked.connect(self.health_monitor.start_monitoring)
        stopMonitorBtn.clicked.connect(self.health_monitor.stop_monitoring)
        setColorBtn.clicked.connect(self.setTeammateHealthBarColor)  # 连接到单个设置方法
        setAllColorsBtn.clicked.connect(self.handleSetAllTeammatesColor) # 连接到统一设置方法
        
        controlLayout.addWidget(startMonitorBtn)
        controlLayout.addWidget(stopMonitorBtn)
        controlLayout.addWidget(setColorBtn)  # 添加单个设置按钮
        controlLayout.addWidget(setAllColorsBtn) # 添加统一设置按钮
        controlLayout.addStretch(1)
        
        # 血条展示区域
        self.health_bars_frame = QFrame()
        self.health_bars_frame.setObjectName("cardFrame")
        self.health_bars_frame.setStyleSheet("QFrame#cardFrame { background-color: rgba(240, 240, 240, 0.7); border-radius: 8px; padding: 10px; }")
        healthBarsLayout = QVBoxLayout(self.health_bars_frame)
        healthBarsLayout.setSpacing(12)
        healthBarsLayout.setContentsMargins(15, 15, 15, 15)
        
        # 初始化血条UI
        self.init_health_bars_ui()
        
        # 添加到监控布局
        layout.addLayout(titleLayout)
        layout.addLayout(controlLayout)
        layout.addWidget(self.health_bars_frame, 1)  # 将监控卡片设置为可伸展，占用更多空间
        
        # 设置卡片
        settingsCard = HeaderCardWidget(self.healthMonitorInterface)
        settingsCard.setTitle("血条监控设置")
        
        settingsLayout = QVBoxLayout()
        settingsLayout.setSpacing(12)
        
        # 基本设置组
        paramsGroup = QGroupBox("监控参数", self.healthMonitorInterface)
        paramsGroupLayout = QVBoxLayout()
        
        # 阈值设置
        thresholdLayout = QHBoxLayout()
        thresholdLabel = BodyLabel(f"血条阈值: {int(self.health_monitor.health_threshold)}%")
        thresholdSlider = Slider(Qt.Horizontal)
        thresholdSlider.setRange(0, 100)
        thresholdSlider.setValue(int(self.health_monitor.health_threshold))
        thresholdLayout.addWidget(thresholdLabel)
        thresholdLayout.addWidget(thresholdSlider)
        thresholdSlider.valueChanged.connect(lambda v: self.update_health_threshold(v, thresholdLabel))
        
        # 采样率设置
        samplingLayout = QHBoxLayout()
        samplingLabel = BodyLabel("采样率 (fps):")
        samplingSpinBox = SpinBox()
        samplingSpinBox.setRange(1, 60)
        samplingSpinBox.setValue(10)
        samplingLayout.addWidget(samplingLabel)
        samplingLayout.addWidget(samplingSpinBox)
        
        # 添加所有参数设置
        paramsGroupLayout.addLayout(thresholdLayout)
        paramsGroupLayout.addLayout(samplingLayout)
        
        # 自动点击低血量队友功能开关
        autoClickLayout = QHBoxLayout()
        autoClickLabel = BodyLabel("自动点击低血量队友:")
        self.autoClickSwitch = SwitchButton()
        # 从 HealthMonitor 加载初始状态
        if hasattr(self, 'health_monitor') and hasattr(self.health_monitor, 'auto_select_enabled'):
            self.autoClickSwitch.setChecked(self.health_monitor.auto_select_enabled)
        else:
            self.autoClickSwitch.setChecked(False) # 默认关闭
        
        # 新增：职业优先级下拉框
        priorityLabel = BodyLabel("优先职业:")
        self.priorityComboBox = ComboBox()
        self.priorityComboBox.setFixedWidth(120)
        # 加载所有职业选项
        self.load_profession_options()
        # 设置当前选中值
        if hasattr(self, 'health_monitor') and hasattr(self.health_monitor, 'priority_profession'):
            priority_index = self.priorityComboBox.findText(self.health_monitor.priority_profession)
            if priority_index >= 0:
                self.priorityComboBox.setCurrentIndex(priority_index)
        
        # 连接信号
        self.autoClickSwitch.checkedChanged.connect(self.toggle_auto_click_low_health)
        self.priorityComboBox.currentTextChanged.connect(self.update_priority_profession)
        
        autoClickLayout.addWidget(autoClickLabel)
        autoClickLayout.addWidget(self.autoClickSwitch)
        autoClickLayout.addSpacing(20)  # 增加间距
        autoClickLayout.addWidget(priorityLabel)
        autoClickLayout.addWidget(self.priorityComboBox)
        autoClickLayout.addStretch(1)
        paramsGroupLayout.addLayout(autoClickLayout) # 添加到参数组布局
        
        paramsGroup.setLayout(paramsGroupLayout)
        
        # 添加到主设置布局
        settingsLayout.addWidget(paramsGroup)
        settingsCardWidget = QWidget()
        settingsCardWidget.setLayout(settingsLayout)
        settingsCard.viewLayout.addWidget(settingsCardWidget)
        
        # 添加卡片到主布局，但设置较小的高度比例
        layout.addWidget(settingsCard)
        
        # 更新采样率设置
        samplingSpinBox.valueChanged.connect(self.update_sampling_rate)
    
    def init_health_bars_ui(self):
        """初始化血条UI显示"""
        if not self.health_bars_frame:
            return

        # 清除现有布局中的所有组件
        current_layout = self.health_bars_frame.layout()
        if current_layout is not None:
            while current_layout.count():
                item = current_layout.takeAt(0)
                widget = item.widget()
                if widget:
                    widget.deleteLater()
        else:
            # 如果布局不存在，则创建一个新的
            new_layout = QVBoxLayout(self.health_bars_frame)
            new_layout.setSpacing(12)
            new_layout.setContentsMargins(15, 15, 15, 15)
            self.health_bars_frame.setLayout(new_layout) # 设置新布局
        
        # --- 新增：按血条 y1, x1 坐标对队员进行排序 ---
        sorted_members = sorted(self.team.members, key=lambda m: (m.y1, m.x1))
        
        # 添加队友信息卡片
        for i, member in enumerate(sorted_members): # 使用排序后的列表
            self.add_health_bar_card(i, member.name, member.profession)
            
        # 如果没有队友，显示提示信息
        if not self.team.members and self.health_bars_frame.layout() is not None: # 检查原始列表判断是否有队友
            noMemberLabel = StrongBodyLabel("没有队友信息。请在队员识别页面添加队友。")
            noMemberLabel.setAlignment(Qt.AlignCenter)
            self.health_bars_frame.layout().addWidget(noMemberLabel)
        
        # 添加：强制更新框架，确保UI刷新
        self.health_bars_frame.update()
    
    def add_health_bar_card(self, index, name, profession):
        """添加血条卡片
        
        参数:
            index: 队友索引
            name: 队友名称
            profession: 队友职业
        """
        # 创建水平布局，每一行一个队员
        memberCard = QFrame()
        memberCard.setObjectName(f"member_card_{index}")
        memberCard.setFixedHeight(60)  # 设置固定高度
        memberCard.setStyleSheet("background-color: transparent;")
        memberLayout = QHBoxLayout(memberCard)
        memberLayout.setContentsMargins(5, 0, 5, 0)
        memberLayout.setSpacing(10)
        
        # 队员编号和名称 - 使用实际名称
        nameLabel = StrongBodyLabel(name)
        nameLabel.setObjectName(f"name_label_{index}")
        nameLabel.setStyleSheet("font-size: 14px; font-weight: bold;")
        nameLabel.setFixedWidth(80)
        
        # 修改：直接显示识别到的职业名称
        roleLabel = BodyLabel(str(profession)) # 确保是字符串
        roleLabel.setStyleSheet("color: #666; font-size: 12px;")
        roleLabel.setFixedWidth(60)
        roleLabel.setToolTip(str(profession)) # 添加悬浮提示显示完整职业名
        
        # 血条容器
        healthBarContainer = QFrame()
        healthBarContainer.setFixedHeight(25)
        healthBarContainer.setStyleSheet("background-color: #333; border-radius: 5px;")
        # --- 添加：设置最大宽度 --- 
        MAX_WIDTH = 300  # 与 update_health_display 中保持一致
        healthBarContainer.setMaximumWidth(MAX_WIDTH) 
        # --- 结束添加 ---
        healthBarContainerLayout = QHBoxLayout(healthBarContainer)
        healthBarContainerLayout.setContentsMargins(2, 2, 2, 2)
        healthBarContainerLayout.setSpacing(0)
        
        # 血条
        healthBar = QFrame()
        healthBar.setObjectName(f"health_bar_{index}")
        healthBar.setFixedHeight(21)
        
        # 根据索引设置不同颜色
        color = "#2ecc71"  # 绿色 (默认，表示90%)
        if index == 1:
            color = "#2ecc71"  # 绿色 (70%)
        elif index == 2:
            color = "#f39c12"  # 黄色 (50%)
        elif index == 3:
            color = "#e74c3c"  # 红色 (30%)
        elif index == 4:
            color = "#e74c3c"  # 红色 (10%)
        
        # 设置默认百分比
        default_percentage = 90
        if index == 1:
            default_percentage = 70
        elif index == 2:
            default_percentage = 50
        elif index == 3:
            default_percentage = 30
        elif index == 4:
            default_percentage = 10
        
        # 设置血条缩放因子和最大宽度
        SCALE_FACTOR = 3
        MAX_WIDTH = 300  # 血条最大宽度
        
        # 计算血条宽度
        bar_width = min(int(default_percentage * SCALE_FACTOR), MAX_WIDTH)
        print(f"队员{index+1} 初始血条宽度: {bar_width}px (血量: {default_percentage}%)")
        
        healthBar.setStyleSheet(f"background-color: {color}; border-radius: 3px;")
        healthBar.setFixedWidth(bar_width)  # 使用计算的宽度
        
        healthBarContainerLayout.addWidget(healthBar)
        healthBarContainerLayout.addStretch(1)
        
        # 血量百分比
        valueLabel = StrongBodyLabel(f"{default_percentage}%")
        valueLabel.setObjectName(f"value_label_{index}")
        valueLabel.setStyleSheet(f"color: {color}; font-weight: bold; font-size: 15px;")
        valueLabel.setAlignment(Qt.AlignCenter)
        valueLabel.setFixedWidth(60)
        
        # 添加调试标签 - 开发期间使用，显示实际内部存储的血量
        debugLabel = QLabel(f"dbg:ok")
        debugLabel.setObjectName(f"debug_label_{index}")
        debugLabel.setStyleSheet("color: #999; font-size: 8px;")
        debugLabel.setFixedWidth(50)
        
        # 添加到卡片布局
        memberLayout.addWidget(nameLabel)
        memberLayout.addWidget(roleLabel)
        memberLayout.addWidget(healthBarContainer)
        memberLayout.addWidget(valueLabel)
        memberLayout.addWidget(debugLabel)  # 添加调试标签
        
        # 添加到主布局
        self.health_bars_frame.layout().addWidget(memberCard)
        
        # 添加分隔线（除了最后一个）
        if index < len(self.team.members) - 1:
            separator = QFrame()
            separator.setFrameShape(QFrame.HLine)
            separator.setFrameShadow(QFrame.Sunken)
            separator.setStyleSheet("background-color: #e0e0e0;")
            separator.setFixedHeight(1)
            self.health_bars_frame.layout().addWidget(separator)
    
    def update_sampling_rate(self, value):
        """更新监控采样率
        
        参数:
            value: 采样率值（fps）
        """
        if hasattr(self, 'health_monitor'):
            # 转换为更新间隔（秒）
            interval = 1.0 / value if value > 0 else 0.1
            self.health_monitor.update_interval = interval
            self.update_monitor_status(f"采样率已更新: {value} fps (更新间隔: {interval:.2f}秒)")
    
    def show_hotkey_settings(self):
        """显示快捷键设置对话框"""
        dialog = HotkeySettingsMessageBox(self.health_monitor, self)
        dialog.exec()
    
    def show_error_message(self, message):
        """显示错误消息
        
        参数:
            message: 错误消息
        """
        InfoBar.error(
            title='错误',
            content=message,
            orient=Qt.Horizontal,
            isClosable=True,
            position=InfoBarPosition.TOP,
            duration=3000,
            parent=self
        )
    
    def set_auto_select(self, enabled):
        """设置自动选择功能
        
        参数:
            enabled: 是否启用
        """
        if hasattr(self, 'health_monitor'):
            self.health_monitor.auto_select_enabled = enabled
            self.health_monitor.save_auto_select_config()
            status = "启用" if enabled else "禁用"
            self.update_monitor_status(f"自动选择功能已{status}")

    def initAssistInterface(self):
        """初始化辅助功能界面"""
        layout = QVBoxLayout(self.assistInterface)
        layout.setSpacing(16)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # 左右布局，左侧为主要功能，右侧为次要功能
        mainLayout = QHBoxLayout()
        mainLayout.setSpacing(16)
        
        # 左侧布局 - 现在只包含快捷键设置
        leftLayout = QVBoxLayout()
        leftLayout.setSpacing(16)
        
        # 快捷键卡片
        hotkeyCard = HeaderCardWidget(self.assistInterface)
        hotkeyCard.setTitle("快捷键设置")
        
        hotkeyLayout = QVBoxLayout()
        hotkeyLayout.setSpacing(12)
        
        # 提示信息
        hotkey_info = BodyLabel("设置全局快捷键用于快速操作。点击\"记录\"按钮后，按下想要设置的键。")
        hotkey_info.setWordWrap(True)
        
        # 快捷键表格
        hotkeyGridLayout = QGridLayout()
        hotkeyGridLayout.setSpacing(12)
        
        # 开始监控
        startMonitorLabel = BodyLabel('开始监控:')
        startMonitorEdit = LineEdit()
        startMonitorEdit.setReadOnly(True)
        startMonitorEdit.setText(self.health_monitor.start_monitoring_hotkey)
        startMonitorRecordBtn = PushButton('记录')
        
        # 停止监控
        stopMonitorLabel = BodyLabel('停止监控:')
        stopMonitorEdit = LineEdit()
        stopMonitorEdit.setReadOnly(True)
        stopMonitorEdit.setText(self.health_monitor.stop_monitoring_hotkey)
        stopMonitorRecordBtn = PushButton('记录')
        
        # 绑定"记录"按钮事件，使用事件过滤器方式
        startMonitorRecordBtn.clicked.connect(lambda: self.install_hotkey_event_filter(startMonitorEdit, stopMonitorEdit, 'start'))
        stopMonitorRecordBtn.clicked.connect(lambda: self.install_hotkey_event_filter(stopMonitorEdit, startMonitorEdit, 'stop'))
        
        # 添加到网格
        hotkeyGridLayout.addWidget(startMonitorLabel, 0, 0)
        hotkeyGridLayout.addWidget(startMonitorEdit, 0, 1)
        hotkeyGridLayout.addWidget(startMonitorRecordBtn, 0, 2)
        
        hotkeyGridLayout.addWidget(stopMonitorLabel, 1, 0)
        hotkeyGridLayout.addWidget(stopMonitorEdit, 1, 1)
        hotkeyGridLayout.addWidget(stopMonitorRecordBtn, 1, 2)
        
        # 添加所有组件到快捷键卡片
        hotkeyLayout.addWidget(hotkey_info)
        hotkeyLayout.addLayout(hotkeyGridLayout)
        # 增加状态信息标签
        self.hotkeyStatusLabel = BodyLabel('')
        hotkeyLayout.addWidget(self.hotkeyStatusLabel)
        hotkeyCardWidget = QWidget()
        hotkeyCardWidget.setLayout(hotkeyLayout)
        hotkeyCard.viewLayout.addWidget(hotkeyCardWidget)
        
        # 添加快捷键卡片到左侧布局
        leftLayout.addWidget(hotkeyCard)
        leftLayout.addStretch(1)
        
        # 右侧布局 - 保持不变
        rightLayout = QVBoxLayout()
        rightLayout.setSpacing(16)
        
        # 数据导出卡片
        exportCard = HeaderCardWidget(self.assistInterface)
        exportCard.setTitle("数据导出")
        
        exportLayout = QVBoxLayout()
        exportLayout.setSpacing(12)
        
        # 导出按钮
        exportBtnsLayout = QHBoxLayout()
        
        exportCsvBtn = PushButton("导出CSV")
        exportCsvBtn.setIcon(FIF.DOWNLOAD)
        
        exportJsonBtn = PushButton("导出JSON")
        exportJsonBtn.setIcon(FIF.DOWNLOAD)
        
        exportBtnsLayout.addWidget(exportCsvBtn)
        exportBtnsLayout.addWidget(exportJsonBtn)
        exportBtnsLayout.addStretch(1)
        
        # 自动导出开关
        autoExportLayout = QHBoxLayout()
        autoExportLabel = BodyLabel("自动导出:")
        autoExportSwitch = SwitchButton()
        
        autoExportLayout.addWidget(autoExportLabel)
        autoExportLayout.addWidget(autoExportSwitch)
        autoExportLayout.addStretch(1)
        
        # 导出路径
        exportPathLayout = QHBoxLayout()
        exportPathLabel = BodyLabel("导出路径:")
        exportPathEdit = LineEdit()
        exportPathEdit.setText(os.path.join(os.path.expanduser("~"), "Documents"))
        exportPathBtn = PushButton("浏览")
        exportPathBtn.setIcon(FIF.FOLDER)
        
        exportPathLayout.addWidget(exportPathLabel)
        exportPathLayout.addWidget(exportPathEdit)
        exportPathLayout.addWidget(exportPathBtn)
        
        # 添加所有组件到导出卡片
        exportLayout.addLayout(exportBtnsLayout)
        exportLayout.addLayout(autoExportLayout)
        exportLayout.addLayout(exportPathLayout)
        exportCardWidget = QWidget()
        exportCardWidget.setLayout(exportLayout)
        exportCard.viewLayout.addWidget(exportCardWidget)
        
        # 添加导出卡片到右侧布局
        rightLayout.addWidget(exportCard)
        rightLayout.addStretch(1)
        
        # 添加左右布局到主布局
        mainLayout.addLayout(leftLayout, 2)
        mainLayout.addLayout(rightLayout, 1)
        
        # 添加主布局到辅助功能界面
        layout.addLayout(mainLayout)

    def initSettingsInterface(self):
        """初始化设置界面"""
        layout = QVBoxLayout(self.settingsInterface)
        layout.setSpacing(16)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # 基本设置卡片
        basicCard = HeaderCardWidget(self.settingsInterface)
        basicCard.setTitle("基本设置")
        
        basicLayout = QVBoxLayout()
        basicLayout.setSpacing(16)
        
        # 主题设置
        themeLayout = QHBoxLayout()
        themeLabel = BodyLabel("主题:")
        themeCombo = ComboBox()
        themeCombo.addItems(["跟随系统", "亮色模式", "暗色模式"])
        themeLayout.addWidget(themeLabel)
        themeLayout.addWidget(themeCombo)
        themeLayout.addStretch(1)
        
        # 语言设置
        languageLayout = QHBoxLayout()
        languageLabel = BodyLabel("语言:")
        languageCombo = ComboBox()
        languageCombo.addItems(["简体中文", "English"])
        languageLayout.addWidget(languageLabel)
        languageLayout.addWidget(languageCombo)
        languageLayout.addStretch(1)
        
        # 自动启动
        autoStartLayout = QHBoxLayout()
        autoStartLabel = BodyLabel("开机自动启动:")
        autoStartSwitch = SwitchButton()
        autoStartLayout.addWidget(autoStartLabel)
        autoStartLayout.addWidget(autoStartSwitch)
        autoStartLayout.addStretch(1)
        
        # 添加所有组件到基本设置卡片
        basicLayout.addLayout(themeLayout)
        basicLayout.addLayout(languageLayout)
        basicLayout.addLayout(autoStartLayout)
        basicCardWidget = QWidget()
        basicCardWidget.setLayout(basicLayout)
        basicCard.viewLayout.addWidget(basicCardWidget)
        
        # 高级设置卡片
        advancedCard = HeaderCardWidget(self.settingsInterface)
        advancedCard.setTitle("高级设置")
        
        advancedLayout = QVBoxLayout()
        advancedLayout.setSpacing(16)
        
        # 缓存设置
        cacheLayout = QHBoxLayout()
        cacheLabel = BodyLabel("缓存大小:")
        cacheSizeLabel = BodyLabel("23.5 MB")
        clearCacheBtn = PushButton("清除缓存")
        clearCacheBtn.setIcon(FIF.DELETE)
        
        cacheLayout.addWidget(cacheLabel)
        cacheLayout.addWidget(cacheSizeLabel)
        cacheLayout.addStretch(1)
        cacheLayout.addWidget(clearCacheBtn)
        
        # AI模型设置
        modelLayout = QHBoxLayout()
        modelLabel = BodyLabel("AI模型:")
        modelCombo = ComboBox()
        modelCombo.addItems(['标准模型', '轻量级模型', '高精度模型', '自娱自乐模型', '作者没钱加模型'])
        modelLayout.addWidget(modelLabel)
        modelLayout.addWidget(modelCombo)
        modelLayout.addStretch(1)
        
        # GPU加速
        gpuLayout = QHBoxLayout()
        gpuLabel = BodyLabel("GPU加速:")
        gpuSwitch = SwitchButton()
        gpuSwitch.setChecked(True)
        gpuLayout.addWidget(gpuLabel)
        gpuLayout.addWidget(gpuSwitch)
        gpuLayout.addStretch(1)
        
        # 添加所有组件到高级设置卡片
        advancedLayout.addLayout(cacheLayout)
        advancedLayout.addLayout(modelLayout)
        advancedLayout.addLayout(gpuLayout)
        advancedCardWidget = QWidget()
        advancedCardWidget.setLayout(advancedLayout)
        advancedCard.viewLayout.addWidget(advancedCardWidget)
        
        # 关于卡片
        aboutCard = HeaderCardWidget(self.settingsInterface)
        aboutCard.setTitle("关于")
        
        aboutLayout = QVBoxLayout()
        aboutLayout.setSpacing(16)
        
        # 版本信息
        versionLayout = QHBoxLayout()
        versionLabel = BodyLabel("版本:")
        versionValueLabel = BodyLabel("VitalSync 2.0.0")
        versionLayout.addWidget(versionLabel)
        versionLayout.addWidget(versionValueLabel)
        versionLayout.addStretch(1)
        
        # 关于信息
        aboutInfoLabel = BodyLabel("VitalSync 是一款专为游戏设计的队员血条识别与监控软件，支持多种游戏和场景。")
        aboutInfoLabel.setWordWrap(True)
        
        # 控制按钮
        controlLayout = QHBoxLayout()
        updateBtn = PushButton("检查更新")
        updateBtn.setIcon(FIF.UPDATE)
        
        githubBtn = PushButton("GitHub项目")
        githubBtn.setIcon(FIF.LINK)
        # 连接点击事件
        githubBtn.clicked.connect(self.openGitHubProject)
        
        controlLayout.addWidget(updateBtn)
        controlLayout.addWidget(githubBtn)
        controlLayout.addStretch(1)
        
        # 添加所有组件到关于卡片
        aboutLayout.addLayout(versionLayout)
        aboutLayout.addWidget(aboutInfoLabel)
        aboutLayout.addLayout(controlLayout)
        aboutCardWidget = QWidget()
        aboutCardWidget.setLayout(aboutLayout)
        aboutCard.viewLayout.addWidget(aboutCardWidget)
        
        # 添加所有卡片到设置界面
        layout.addWidget(basicCard)
        layout.addWidget(advancedCard)
        layout.addWidget(aboutCard)
        layout.addStretch(1)

    def openGitHubProject(self):
        """打开GitHub项目页面"""
        url = QUrl("https://github.com/yinduandafeimao/VitalSync-Pulse")
        QDesktopServices.openUrl(url)
        
        # 显示提示信息
        InfoBar.success(
            title='已打开链接',
            content='已在浏览器中打开GitHub项目页面',
            orient=Qt.Horizontal,
            isClosable=True,
            position=InfoBarPosition.TOP,
            duration=2000,
            parent=self
        )

    def addProfessionIcon(self):
        """添加新的职业图标"""
        # 检查profession_icons文件夹是否存在
        profession_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "profession_icons")
        if not os.path.exists(profession_path):
            os.makedirs(profession_path)  # 创建文件夹如果不存在
            
        # 打开文件选择对话框
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "选择职业图标",
            "",
            "图片文件 (*.png *.jpg *.jpeg)"
        )
        
        if not file_path:
            return
        
        # 获取文件名
        file_name_without_ext = os.path.splitext(os.path.basename(file_path))[0]
        
        # 使用自定义无边框对话框获取职业名称
        input_dialog = TextInputMessageBox(
            title='输入职业名称',
            label_text='请输入该职业图标的名称:',
            default_text=file_name_without_ext,
            placeholder_text='例如：奶妈、坦克、输出',
            parent=self
        )
        
        if not input_dialog.exec():
            return
        
        icon_name = input_dialog.get_text()
        if not icon_name:
            InfoBar.warning(
                title='输入无效',
                content='职业名称不能为空。',
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=2000,
                parent=self
            )
            return
        
        # 构造目标路径
        target_path = os.path.join(profession_path, icon_name + os.path.splitext(file_path)[1])
        
        # 检查是否已存在同名文件
        if os.path.exists(target_path):
            confirm_dialog = ConfirmMessageBox(
                "文件已存在",
                f"职业 '{icon_name}' 已存在，是否覆盖?",
                self
            )
            
            if not confirm_dialog.exec():
                return
        
        try:
            # 复制文件
            import shutil
            shutil.copy2(file_path, target_path)
            
            # 显示成功消息
            InfoBar.success(
                title='添加成功',
                content=f'职业图标 {icon_name} 已添加',
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=2000,
                parent=self
            )
            
            # 更新图标数量显示
            self.updateIconCount()
        except Exception as e:
            # 显示错误消息
            InfoBar.error(
                title='添加失败',
                content=str(e),
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=3000,
                parent=self
            )
    
    def updateIconCount(self):
        """更新职业图标数量显示"""
        # 重新计算图标数量
        profession_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "profession_icons")
        icon_count = len([f for f in os.listdir(profession_path) if f.endswith(('.png', '.jpg', '.jpeg'))])
        
        # 查找信息标签并更新
        for i in range(self.iconCardWidget.layout().count()):
            item = self.iconCardWidget.layout().itemAt(i)
            if item.widget() and isinstance(item.widget(), BodyLabel) and "当前已加载" in item.widget().text():
                item.widget().setText(f'当前已加载 {icon_count} 个职业图标')
                break

    def init_recognition(self):
        """初始化识别模块"""
        try:
            if self.recognition is None:
                from teammate_recognition import TeammateRecognition
                self.recognition = TeammateRecognition()
                InfoBar.success(
                    title='OCR模型加载成功',
                    content='队友识别功能已准备就绪',
                    orient=Qt.Horizontal,
                    isClosable=True,
                    position=InfoBarPosition.TOP,
                    duration=2000,
                    parent=self
                )
            return True
        except Exception as e:
            InfoBar.error(
                title='OCR初始化失败',
                content=f'错误: {str(e)}',
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=3000,
                parent=self
            )
            return False

    def addTeammate(self):
        """添加队友"""
        print("\n添加新队友:")
        
        # 使用自定义的MessageBoxBase子类
        dialog = AddTeammateMessageBox(self)
        
        if dialog.exec():
            name, profession = dialog.get_teammate_info()
            
            # 使用Team类添加队友
            new_member = self.team.add_member(name, profession)
            
            # 使用全局默认颜色设置(如果有的话)
            if self.default_hp_color_lower is not None and self.default_hp_color_upper is not None:
                import numpy as np
                new_member.hp_color_lower = np.copy(self.default_hp_color_lower)
                new_member.hp_color_upper = np.copy(self.default_hp_color_upper)
                new_member.save_config()  # 保存颜色设置到队员配置文件
            
            # 更新健康监控
            self.health_monitor.team = self.team
            self.init_health_bars_ui()
            
            # 提示设置血条位置 - 使用自定义确认对话框
            confirm_dialog = ConfirmMessageBox(
                "设置血条位置",
                f"是否立即为 {name} 设置血条位置？",
                self
            )
            
            if confirm_dialog.exec():
                # 使用选择框设置血条位置
                self.set_health_bar_position(new_member)
            
            InfoBar.success(
                title='添加成功',
                content=f'队友 {name} ({profession}) 已添加',
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                parent=self
            )

class HotkeySettingsMessageBox(MessageBoxBase):
    """ Custom message box for hotkey settings """

    def __init__(self, health_monitor, parent=None):
        super().__init__(parent)
        self.titleLabel = SubtitleLabel('监控快捷键设置', self)
        self.health_monitor = health_monitor
        self.parent_window = parent
        
        # 当前快捷键展示
        self.infoLabel = BodyLabel(f"当前快捷键设置:\n开始监控: {health_monitor.start_monitoring_hotkey}\n停止监控: {health_monitor.stop_monitoring_hotkey}")
        self.infoLabel.setWordWrap(True)
        
        # 设置表单
        form_widget = QWidget()
        form_layout = QGridLayout(form_widget)
        form_layout.setSpacing(10)
        
        # 开始监控输入
        self.start_label = BodyLabel("开始监控键:")
        self.start_input = LineEdit()
        self.start_input.setText(health_monitor.start_monitoring_hotkey)
        self.start_input.setPlaceholderText("按下快捷键组合")
        
        # 停止监控输入
        self.stop_label = BodyLabel("停止监控键:")
        self.stop_input = LineEdit()
        self.stop_input.setText(health_monitor.stop_monitoring_hotkey)
        self.stop_input.setPlaceholderText("按下快捷键组合")
        
        # 错误提示标签
        self.error_label = CaptionLabel("")
        self.error_label.setTextColor("#cf1010", QColor(255, 28, 32))
        self.error_label.hide()
        
        # 增加记录按钮以记录实际按键
        self.start_record = PushButton("记录")
        self.start_record.clicked.connect(lambda: self.record_hotkey('start'))
        
        self.stop_record = PushButton("记录")
        self.stop_record.clicked.connect(lambda: self.record_hotkey('stop'))
        
        # 添加到布局
        form_layout.addWidget(self.start_label, 0, 0)
        form_layout.addWidget(self.start_input, 0, 1)
        form_layout.addWidget(self.start_record, 0, 2)
        
        form_layout.addWidget(self.stop_label, 1, 0)
        form_layout.addWidget(self.stop_input, 1, 1)
        form_layout.addWidget(self.stop_record, 1, 2)
        
        # 将所有控件添加到视图布局
        self.viewLayout.addWidget(self.titleLabel)
        self.viewLayout.addWidget(self.infoLabel)
        self.viewLayout.addWidget(form_widget)
        self.viewLayout.addWidget(self.error_label)
        
        # 设置按钮文本
        self.yesButton.setText('保存')
        self.cancelButton.setText('取消')
        
        # 设置最小宽度
        self.widget.setMinimumWidth(400)
    
    def record_hotkey(self, which):
        """弹出对话框录入快捷键"""
        from PyQt5.QtGui import QKeySequence
        
        # 创建录入对话框
        dialog = MessageBoxBase(self)
        dialog.titleLabel = SubtitleLabel('录入快捷键', dialog)
        
        # 说明标签
        guide_label = BodyLabel('请按下新的快捷键组合（如 Ctrl+Alt+S）')
        key_label = BodyLabel('等待按键...')
        
        # 添加到视图布局
        dialog.viewLayout.addWidget(dialog.titleLabel)
        dialog.viewLayout.addWidget(guide_label)
        dialog.viewLayout.addWidget(key_label)
        
        # 设置按钮文本，初始时禁用确定按钮
        dialog.yesButton.setText('确定')
        dialog.yesButton.setEnabled(False)
        dialog.cancelButton.setText('取消')
        
        # 存储按键
        key_seq = {'text': ''}
        
        # 重写keyPressEvent处理按键
        def keyPressEvent(event):
            # 保存原始方法
            original_keyPressEvent = dialog.keyPressEvent
            
            key_text = ''
            modifiers = event.modifiers()
            if modifiers & Qt.ControlModifier:
                key_text += 'ctrl+'
            if modifiers & Qt.AltModifier:
                key_text += 'alt+'
            if modifiers & Qt.ShiftModifier:
                key_text += 'shift+'
            key = event.key()
            if key in (Qt.Key_Control, Qt.Key_Alt, Qt.Key_Shift):
                # 恢复原始方法并调用它
                dialog.keyPressEvent = original_keyPressEvent
                return original_keyPressEvent(event)
            key_name = QKeySequence(key).toString().lower()
            key_text += key_name
            key_seq['text'] = key_text
            key_label.setText(f'已录入: {key_text}')
            dialog.yesButton.setEnabled(True)
            
            # 恢复原始方法
            dialog.keyPressEvent = original_keyPressEvent
        
        # 保存原始方法
        original_method = dialog.keyPressEvent
        # 替换方法
        dialog.keyPressEvent = keyPressEvent
        
        # 显示对话框
        if dialog.exec():
            if key_seq['text']:
                if which == 'start':
                    self.start_input.setText(key_seq['text'])
                else:
                    self.stop_input.setText(key_seq['text'])
    
    def validate(self):
        """验证输入是否有效"""
        start_key = self.start_input.text()
        stop_key = self.stop_input.text()
        
        # 检查输入是否有效
        if not start_key or not stop_key:
            self.error_label.setText("快捷键不能为空")
            self.error_label.show()
            return False
            
        if start_key == stop_key:
            self.error_label.setText("开始和停止快捷键不能相同")
            self.error_label.show()
            return False
        
        # 尝试设置新的快捷键
        success = self.health_monitor.set_hotkeys(start_key, stop_key)
        
        if not success:
            self.error_label.setText("设置快捷键失败，请重试")
            self.error_label.show()
            return False
            
        return True

class TeammateSelectionMessageBox(MessageBoxBase):
    """ Custom message box for teammate selection """

    def __init__(self, title, team_members, parent=None):
        super().__init__(parent)
        self.titleLabel = SubtitleLabel(title, self)
        
        # 添加说明
        self.infoLabel = BodyLabel("请从列表中选择一个队友")
        
        # 创建队友列表
        self.listWidget = QListWidget(self)
        for i, member in enumerate(team_members):
            self.listWidget.addItem(f"{member.name} ({member.profession})")
        
        # 警告标签
        self.warningLabel = CaptionLabel("未选择任何队友")
        self.warningLabel.setTextColor("#cf1010", QColor(255, 28, 32))
        self.warningLabel.hide()  # 默认隐藏
        
        # 添加到视图布局
        self.viewLayout.addWidget(self.titleLabel)
        self.viewLayout.addWidget(self.infoLabel)
        self.viewLayout.addWidget(self.listWidget)
        self.viewLayout.addWidget(self.warningLabel)
        
        # 设置按钮文本
        self.yesButton.setText('选择')
        self.cancelButton.setText('取消')
        
        # 设置最小宽度
        self.widget.setMinimumWidth(350)
        
        # 存储队友列表
        self.team_members = team_members
        self.selected_index = -1
        
        # 连接列表点击事件
        self.listWidget.itemClicked.connect(self.on_item_clicked)
    
    def on_item_clicked(self, item):
        """列表项被点击时更新选择索引"""
        self.selected_index = self.listWidget.row(item)
        self.warningLabel.hide()  # 隐藏警告
    
    def get_selected_member(self):
        """获取选中的队友"""
        if self.selected_index >= 0 and self.selected_index < len(self.team_members):
            return self.team_members[self.selected_index]
        return None
        
    def validate(self):
        """验证是否选择了队友"""
        if self.selected_index >= 0:
            return True
        else:
            self.warningLabel.show()  # 显示警告
            return False

class UnifiedColorPickerMessageBox(MessageBoxBase):
    """ Custom message box for unified color picking """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.titleLabel = SubtitleLabel('统一设置所有队友的血条颜色', self)
        
        # 添加操作指南
        self.guideLabel = BodyLabel(
            '1. 将鼠标移动到游戏中任意一个队友的血条上\n'
            '2. 选择血条最具代表性的颜色位置\n'
            '3. 按下空格键获取颜色，此颜色将应用于所有队友\n'
            '4. 按ESC键取消操作'
        )
        self.guideLabel.setWordWrap(True)
        
        # 状态标签
        self.statusLabel = CaptionLabel("状态：等待获取颜色...")
        self.statusLabel.setTextColor("#1e88e5", QColor(30, 136, 229))
        
        # 预览区域
        previewLayout = QHBoxLayout()
        previewLabel = BodyLabel('颜色预览：')
        self.colorPreview = QFrame()
        self.colorPreview.setFixedSize(50, 20)
        self.colorPreview.setFrameShape(QFrame.Box)
        previewLayout.addWidget(previewLabel)
        previewLayout.addWidget(self.colorPreview)
        previewWidget = QWidget()
        previewWidget.setLayout(previewLayout)
        
        # 添加到视图布局
        self.viewLayout.addWidget(self.titleLabel)
        self.viewLayout.addWidget(self.guideLabel)
        self.viewLayout.addWidget(self.statusLabel)
        self.viewLayout.addWidget(previewWidget)
        
        # 设置按钮文本
        self.yesButton.setText('确定')
        self.cancelButton.setText('取消')
        
        # 设置最小宽度
        self.widget.setMinimumWidth(350)
        
        # 颜色获取状态和计时器
        self.color_captured = False
        self.key_check_timer = QTimer(self)
        self.key_check_timer.timeout.connect(self.check_keys_and_position)
        self.key_check_timer.start(100)
        
        # 存储获取的颜色值
        self.pixel_color_rgb = None

    def check_keys_and_position(self):
        """检查键盘输入和鼠标位置"""
        import keyboard
        if keyboard.is_pressed('space'):
            if self.color_captured:
                return
            
            self.color_captured = True
            self.key_check_timer.stop()
            
            try:
                import pyautogui
                x, y = pyautogui.position()
                self.pixel_color_rgb = pyautogui.screenshot().getpixel((x, y))[:3]  # 确保是RGB
                
                color_hex = "#{:02x}{:02x}{:02x}".format(
                    self.pixel_color_rgb[0], 
                    self.pixel_color_rgb[1], 
                    self.pixel_color_rgb[2]
                )
                self.colorPreview.setStyleSheet(f"background-color: {color_hex};")
                
                self.statusLabel.setText(f"状态：成功获取颜色！RGB: {self.pixel_color_rgb}")
                self.statusLabel.setTextColor("#2ecc71", QColor(46, 204, 113))
                
                # 延迟关闭对话框
                QTimer.singleShot(2000, lambda: self.accept())
                
            except Exception as e:
                self.statusLabel.setText(f"状态：获取颜色失败 - {str(e)}")
                self.statusLabel.setTextColor("#e74c3c", QColor(231, 76, 60))
                self.color_captured = False
                self.key_check_timer.start()
        
        elif keyboard.is_pressed('esc'):
            if not self.color_captured:
                self.key_check_timer.stop()
                self.reject()

class MainWindow(FluentWindow):
    def __init__(self):
        """初始化主窗口"""
        super().__init__()
        
        # 初始化 pygame mixer
        try:
            pygame.mixer.init()
            pygame.mixer.set_num_channels(16) # 设置足够多的声道
        except pygame.error as e:
            print(f"Pygame mixer 初始化失败: {e}")
            # 可以选择禁用语音功能或显示错误提示
            InfoBar.error(
                title='音频初始化失败',
                content='无法初始化音频播放组件 (pygame.mixer)，语音播报功能将不可用。',
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=5000,
                parent=self
            )
        
        self._icon_capture_show_selection_timer = None
        self._icon_capture_do_grab_timer = None
        self._icon_capture_rect = None # Store the rect between timer calls
        
        # --- 添加缺失的语音参数初始化 ---
        # 初始化语音参数属性 - 使用滑块的默认值
        # 语速: slider 0-10 -> rate -50% to +50% -> + (value*10 - 50) %
        default_rate_value = 5
        self.voice_rate_param = f'+{default_rate_value * 10 - 50}%'
        # 音量: slider 0-100 -> volume -50% to +50% -> + (value - 50) %
        default_volume_value = 80
        self.voice_volume_param = f'+{default_volume_value - 50}%'
        # --- 初始化结束 ---
        
        # 设置窗口标题和大小
        self.setWindowTitle('VitalSync')
        self.resize(1200, 500) # 将高度从 800 调整为 700
        
        # 设置应用强调色 - 使用截图中的青绿色
        setThemeColor(QColor(0, 168, 174))
        
        # 启用亚克力效果
        self.navigationInterface.setAcrylicEnabled(True)
        
        # 初始化队友管理相关属性
        self.team = Team()  # 创建Team实例
        self.selection_box = None # 屏幕选择框
        
        # 初始化全局默认血条颜色
        self.default_hp_color_lower = None  # 默认血条颜色下限
        self.default_hp_color_upper = None  # 默认血条颜色上限
        self.load_default_colors()  # 从配置加载默认颜色设置
        
        # 初始化健康监控相关属性
        self.health_monitor = HealthMonitor(self.team)  # 创建健康监控实例
        # 连接监控信号
        self.health_monitor.signals.update_signal.connect(self.update_health_display)
        self.health_monitor.signals.status_signal.connect(self.update_monitor_status)
        
        # 创建界面
        self.teamRecognitionInterface = QWidget()
        self.teamRecognitionInterface.setObjectName("teamRecognitionInterface")
        
        self.healthMonitorInterface = QWidget()
        self.healthMonitorInterface.setObjectName("healthMonitorInterface")
        
        self.assistInterface = QWidget()
        self.assistInterface.setObjectName("assistInterface")
        
        self.settingsInterface = QWidget()
        self.settingsInterface.setObjectName("settingsInterface")
        
        # 新增：语音设置界面实例
        self.voiceSettingsInterface = QWidget()
        self.voiceSettingsInterface.setObjectName("voiceSettingsInterface")
        
        # 初始化界面
        self.initTeamRecognitionInterface()
        self.initHealthMonitorInterface()
        self.initAssistInterface()
        self.initSettingsInterface()
        self.initVoiceSettingsInterface() # 新增：调用语音设置界面初始化
        
        # 初始化导航
        self.initNavigation()
        
        # --- 加载设置 ---
        self.load_settings() # 在UI初始化后加载设置
        
        # 显示提示信息
        InfoBar.success(
            title='初始化完成',
            content='系统已准备就绪',
            orient=Qt.Horizontal,
            isClosable=True,
            position=InfoBarPosition.TOP,
            duration=2000,
            parent=self
        )
        
        # 在__init__方法末尾添加：
        self.load_teammates()
        
        # 初始化语音队列和工作线程
        self.speech_queue = queue.Queue()
        self.active_speech = {} # 用于跟踪正在播放的语音及其资源
        self.speech_worker_thread = threading.Thread(target=self._speech_worker_loop, daemon=True)
        self.speech_worker_thread.start()
        
        # 设置一个定时器来处理 Pygame 事件和清理
        self.pygame_event_timer = QTimer(self)
        self.pygame_event_timer.timeout.connect(self._process_pygame_events)
        self.pygame_event_timer.start(100) # 每 100ms 检查一次
    
    def initNavigation(self):
        """初始化导航栏"""
        # 添加子界面
        self.addSubInterface(self.teamRecognitionInterface, FIF.PEOPLE, '队员识别')
        self.addSubInterface(self.healthMonitorInterface, FIF.HEART, '血条监控')
        self.addSubInterface(self.assistInterface, FIF.IOT, '辅助功能')
        self.addSubInterface(self.voiceSettingsInterface, FIF.MICROPHONE, '语音设置') # 使用 FIF.MICROPHONE 图标
        
        # 添加底部界面
        self.addSubInterface(
            self.settingsInterface, 
            FIF.SETTING, 
            '系统设置',
            NavigationItemPosition.BOTTOM
        )

    def initTeamRecognitionInterface(self):
        """初始化队员识别界面"""
        layout = QVBoxLayout(self.teamRecognitionInterface)
        layout.setSpacing(24)  # 增加垂直间距
        layout.setContentsMargins(24, 24, 24, 24)  # 增加外边距
        
        # 创建顶部水平布局，包含职业图标管理和队友管理
        topLayout = QHBoxLayout()
        topLayout.setSpacing(24)  # 增加水平间距
        
        # ========== 左侧：职业图标管理 ==========
        iconCard = HeaderCardWidget(self.teamRecognitionInterface)
        iconCard.setTitle("职业图标管理")
        iconCard.setFixedHeight(200)  # 适当减少卡片高度
        iconLayout = QVBoxLayout()
        iconLayout.setSpacing(15)  # 增加垂直间距
        iconLayout.setContentsMargins(0, 10, 0, 10)  # 增加内边距
        
        # 按钮区域 - 也使用网格布局
        btnLayout = QGridLayout()
        btnLayout.setSpacing(15)  # 增加按钮间距
        
        addIconBtn = PrimaryPushButton('添加图标')
        addIconBtn.setIcon(FIF.ADD)
        addIconBtn.setFixedWidth(140)  # 显著增加按钮宽度
        addIconBtn.setMinimumHeight(36)  # 设置最小高度
        
        captureIconBtn = PushButton('截取图标')
        captureIconBtn.setIcon(FIF.CAMERA) # 使用 CAMERA 图标替代 SCREENSHOT
        captureIconBtn.setFixedWidth(140)  # 显著增加按钮宽度
        captureIconBtn.setMinimumHeight(36)  # 设置最小高度
        
        manageIconsBtn = PushButton('管理图标')
        manageIconsBtn.setIcon(FIF.SETTING)
        manageIconsBtn.setFixedWidth(140)  # 显著增加按钮宽度
        manageIconsBtn.setMinimumHeight(36)  # 设置最小高度
        
        # 连接按钮事件
        addIconBtn.clicked.connect(self.addProfessionIcon)
        captureIconBtn.clicked.connect(self.captureScreenIcon)
        manageIconsBtn.clicked.connect(self.loadProfessionIcons)
        
        # 将按钮添加到网格布局
        btnLayout.addWidget(addIconBtn, 0, 0)
        btnLayout.addWidget(captureIconBtn, 0, 1)
        btnLayout.addWidget(manageIconsBtn, 0, 2)
        
        # 显示图标数量信息
        profession_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "profession_icons")
        
        # 检查文件夹是否存在
        if not os.path.exists(profession_path):
            os.makedirs(profession_path)
            icon_count = 0
        else:
            icon_count = len([f for f in os.listdir(profession_path) if f.endswith(('.png', '.jpg', '.jpeg'))])
            
        infoLabel = BodyLabel(f'已加载 {icon_count} 个职业图标')
        infoLabel.setStyleSheet("color: #666; font-size: 13px;")  # 设置样式，使其显示更清晰
        infoLabel.setAlignment(Qt.AlignCenter)  # 居中对齐
        
        # 添加到卡片布局
        iconLayout.addLayout(btnLayout)
        iconLayout.addWidget(infoLabel)
        iconLayout.addStretch(1)  # 添加弹性空间，将内容推向顶部，使标签居中
        iconCardWidget = QWidget()
        iconCardWidget.setLayout(iconLayout)
        iconCard.viewLayout.addWidget(iconCardWidget)
        self.iconCardWidget = iconCardWidget
        
        # ========== 右侧：队友管理 ==========
        teammateCard = HeaderCardWidget(self.teamRecognitionInterface)
        teammateCard.setTitle("队友管理")
        teammateCard.setFixedHeight(200)  # 适当减少卡片高度
        teammateLayout = QVBoxLayout()
        teammateLayout.setSpacing(30)  # 增加垂直间距
        teammateLayout.setContentsMargins(0, 0, 0, 10)  # 顶部margin设为0，整体上移
        
        # 队友管理按钮区域 - 使用网格布局确保均匀分布
        teammateBtnLayout = QGridLayout()  # 改回网格布局
        teammateBtnLayout.setSpacing(18)  # 进一步增加基础间距 (原为15)
        teammateBtnLayout.setVerticalSpacing(48)  # 大幅增大垂直间距 (原为20)
        teammateBtnLayout.setContentsMargins(10, 0, 10, 0)  # 保持或调整水平内边距
        
        addTeammateBtn = PrimaryPushButton('添加队友')
        addTeammateBtn.setIcon(FIF.ADD)
        addTeammateBtn.setFixedWidth(115)  # 进一步减少按钮宽度 (原为125)
        addTeammateBtn.setMinimumHeight(36)  # 保持按钮高度
        
        removeTeammateBtn = PushButton('移除队友')
        removeTeammateBtn.setIcon(FIF.REMOVE)
        removeTeammateBtn.setFixedWidth(115)  # 进一步减少按钮宽度 (原为125)
        removeTeammateBtn.setMinimumHeight(36)  # 保持按钮高度
        
        loadTeammateBtn = PushButton('加载队友')
        loadTeammateBtn.setIcon(FIF.DOWNLOAD)
        loadTeammateBtn.setFixedWidth(115)  # 进一步减少按钮宽度 (原为125)
        loadTeammateBtn.setMinimumHeight(36)  # 保持按钮高度
        
        clearAllTeammatesBtn = PushButton('清除全部')
        clearAllTeammatesBtn.setIcon(FIF.DELETE)
        clearAllTeammatesBtn.setFixedWidth(115)  # 进一步减少按钮宽度 (原为125)
        clearAllTeammatesBtn.setMinimumHeight(36)  # 保持按钮高度
        
        # 连接按钮事件
        addTeammateBtn.clicked.connect(self.addTeammate)
        removeTeammateBtn.clicked.connect(self.removeTeammate)
        loadTeammateBtn.clicked.connect(self.loadTeammate)
        clearAllTeammatesBtn.clicked.connect(self.clearAllTeammates)
        
        # 使用网格布局均匀排列按钮，2行2列，修正行号并增加间距
        teammateBtnLayout.addWidget(addTeammateBtn, 0, 0)      # 第1行第1列
        teammateBtnLayout.addWidget(removeTeammateBtn, 0, 1)   # 第1行第2列
        teammateBtnLayout.addWidget(loadTeammateBtn, 1, 0)     # 第2行第1列
        teammateBtnLayout.addWidget(clearAllTeammatesBtn, 1, 1) # 第2行第2列
        
        # 队友信息显示
        teammateInfoLabel = BodyLabel('')
        teammateInfoLabel.setObjectName("teammateInfoLabel")  # 设置对象名以便更新时查找
        teammateInfoLabel.setWordWrap(True)  # 允许文字换行
        teammateInfoLabel.setStyleSheet("color: #666; font-size: 13px;")  # 设置样式，使其显示更清晰
        teammateInfoLabel.setAlignment(Qt.AlignCenter)  # 居中对齐
        
        # 添加到卡片布局
        teammateLayout.addLayout(teammateBtnLayout)
        teammateLayout.addWidget(teammateInfoLabel)
        teammateLayout.addStretch(1)  # 添加弹性空间，将内容推向顶部，使标签居中
        teammateCardWidget = QWidget()
        teammateCardWidget.setLayout(teammateLayout)
        teammateCard.viewLayout.addWidget(teammateCardWidget)
        
        # 将两个卡片添加到顶部布局
        topLayout.addWidget(iconCard, 1) # 设置伸展因子为1
        topLayout.addWidget(teammateCard, 1) # 设置伸展因子为1
        
        # ========== 识别队友区域 ==========
        recognitionCard = HeaderCardWidget(self.teamRecognitionInterface)
        recognitionCard.setTitle("识别队友")
        recognitionLayout = QVBoxLayout()
        recognitionLayout.setSpacing(18)  # 增加垂直间距
        recognitionLayout.setContentsMargins(0, 8, 0, 8)  # 增加内边距
        
        # 控制面板区域
        controlsPanel = QFrame()
        controlsPanel.setObjectName("cardFrame")
        controlsPanelLayout = QHBoxLayout(controlsPanel)
        controlsPanelLayout.setSpacing(16)
        controlsPanelLayout.setContentsMargins(16, 12, 16, 12)  # 增加内边距使内容更加突出
        
        # 选择识别位置按钮
        selectPositionBtn = PrimaryPushButton("选择识别位置")
        selectPositionBtn.setIcon(FIF.EDIT)
        selectPositionBtn.setMinimumWidth(160)  # 增加按钮宽度
        
        # 识别状态显示
        statusLabel = BodyLabel("状态: 未开始识别")
        statusLabel.setStyleSheet("color: #888; font-size: 14px;")  # 调整样式
        
        controlsPanelLayout.addWidget(selectPositionBtn)
        controlsPanelLayout.addWidget(statusLabel)
        controlsPanelLayout.addStretch(1)
        
        # 预览区域
        previewArea = QFrame()
        previewArea.setObjectName("cardFrame")
        # 修改：使用浅色背景和深色文字
        previewArea.setStyleSheet("#cardFrame{background-color: #f8f9fa; color: #333333; border-radius: 10px; border: 1px solid #e0e0e0;}") 
        previewLayout = QVBoxLayout(previewArea)
        previewLayout.setContentsMargins(10, 10, 10, 10)  # 添加内边距
        
        previewTitle = QLabel("队友信息预览")
        previewTitle.setAlignment(Qt.AlignCenter)
        # 修改：标题文字颜色改为深色
        previewTitle.setStyleSheet("color: #333333; font-size: 16px; font-weight: bold; margin-bottom: 10px;")
        
        # 创建滚动区域
        scrollArea = ScrollArea()
        scrollArea.setWidgetResizable(True)
        scrollArea.setStyleSheet("background: transparent; border: none;")
        
        scrollContent = QWidget()
        scrollLayout = QVBoxLayout(scrollContent)
        scrollLayout.setContentsMargins(0, 0, 0, 0)
        scrollLayout.setSpacing(8)
        
        # 创建队友信息标签
        self.teammateInfoPreview = QLabel("加载队友信息中...")
        self.teammateInfoPreview.setWordWrap(True)
        # 修改：默认文字颜色改为深色
        self.teammateInfoPreview.setStyleSheet("color: #333333; font-size: 14px;") 
        scrollLayout.addWidget(self.teammateInfoPreview)
        
        scrollArea.setWidget(scrollContent)
        
        previewLayout.addWidget(previewTitle)
        previewLayout.addWidget(scrollArea)
        
        # 添加更新按钮
        updateInfoBtn = PushButton("刷新队友信息")
        updateInfoBtn.setIcon(FIF.SYNC)
        updateInfoBtn.clicked.connect(self.update_teammate_preview)
        previewLayout.addWidget(updateInfoBtn)
        
        # 底部控制按钮
        buttonLayout = QHBoxLayout()
        buttonLayout.setSpacing(16)
        
        startBtn = PrimaryPushButton("开始识别")
        startBtn.setIcon(FIF.PLAY)
        startBtn.setMinimumWidth(130)  # 增加按钮宽度
        
        stopBtn = PushButton("停止")
        stopBtn.setIcon(FIF.CANCEL)
        stopBtn.setMinimumWidth(130)  # 增加按钮宽度
        
        saveBtn = PushButton("导出配置")
        saveBtn.setIcon(FIF.SAVE)
        saveBtn.setMinimumWidth(130)  # 增加按钮宽度
        
        # 连接按钮事件
        selectPositionBtn.clicked.connect(self.select_recognition_position)
        startBtn.clicked.connect(self.start_recognition_from_calibration)
        stopBtn.clicked.connect(self.stop_recognition)
        saveBtn.clicked.connect(self.export_recognition_config)
        
        # 然后继续添加按钮到布局
        buttonLayout.addStretch(1)
        buttonLayout.addWidget(startBtn)
        buttonLayout.addWidget(stopBtn)
        buttonLayout.addWidget(saveBtn)
        buttonLayout.addStretch(1)
        
        # 添加到识别布局
        recognitionLayout.addWidget(controlsPanel)
        recognitionLayout.addWidget(previewArea)
        recognitionLayout.addLayout(buttonLayout)
        
        recognitionCardWidget = QWidget()
        recognitionCardWidget.setLayout(recognitionLayout)
        recognitionCard.viewLayout.addWidget(recognitionCardWidget)
        
        # 添加到主布局
        layout.addLayout(topLayout)
        layout.addWidget(recognitionCard, 1)  # 1表示伸展因子，让这个区域占据更多空间
        
    def loadProfessionIcons(self):
        """加载职业图标并显示管理对话框"""
        # 使用自定义无边框对话框
        manage_dialog = ProfessionIconsManageDialog(self)
        manage_dialog.exec()
    
    def deleteProfessionIcon(self, icon_file, frame, dialog=None):
        """删除职业图标"""
        profession_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "profession_icons")
        icon_path = os.path.join(profession_path, icon_file)
        
        # 确认删除
        confirm_dialog = ConfirmMessageBox(
            "确认删除",
            f"确定要删除职业图标 {os.path.splitext(icon_file)[0]} 吗？",
            self if not dialog else dialog # Keep ConfirmMessageBox parented to dialog for modality
        )
        
        if confirm_dialog.exec():
            try:
                # 删除文件
                os.remove(icon_path)
                # 从UI中移除
                frame.setParent(None)
                frame.deleteLater()
                # 更新图标计数
                self.updateIconCount()
                # 提示成功
                InfoBar.success(
                    title='删除成功',
                    content=f'已删除职业图标 {os.path.splitext(icon_file)[0]}',
                    orient=Qt.Horizontal,
                    isClosable=True,
                    position=InfoBarPosition.TOP,
                    duration=2000,
                    parent=self  # Ensure InfoBar is parented to MainWindow
                )
            except Exception as e:
                # 删除失败提示
                InfoBar.error(
                    title='删除失败',
                    content=str(e),
                    orient=Qt.Horizontal,
                    isClosable=True,
                    position=InfoBarPosition.TOP,
                    duration=3000,
                    parent=self  # Ensure InfoBar is parented to MainWindow
                )

    def initHealthMonitorInterface(self):
        """初始化血条监控界面"""
        layout = QVBoxLayout(self.healthMonitorInterface)
        layout.setSpacing(16)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # 标题和状态信息
        titleLayout = QHBoxLayout()
        titleLabel = StrongBodyLabel("血条实时监控")
        titleLabel.setStyleSheet("font-size: 18px; font-weight: bold;")
        
        self.monitor_status_label = BodyLabel("准备就绪")
        self.monitor_status_label.setStyleSheet("color: #3498db;")
        titleLayout.addWidget(titleLabel)
        titleLayout.addStretch(1)
        titleLayout.addWidget(self.monitor_status_label)
        
        # 控制按钮区域
        controlLayout = QHBoxLayout()
        
        startMonitorBtn = PrimaryPushButton("开始监控")
        startMonitorBtn.setIcon(FIF.PLAY)
        startMonitorBtn.setMinimumWidth(120)
        
        stopMonitorBtn = PushButton("停止监控")
        stopMonitorBtn.setIcon(FIF.CLOSE)
        stopMonitorBtn.setMinimumWidth(120)
        
        # 新增：设置血条颜色按钮
        setColorBtn = PushButton("设置血条颜色")
        setColorBtn.setIcon(FIF.PALETTE) # 使用 PALETTE 图标替代 COLOR
        setColorBtn.setMinimumWidth(120)
        
        # 新增：统一设置血条颜色按钮
        setAllColorsBtn = PushButton("统一设置颜色")
        setAllColorsBtn.setIcon(FIF.BRUSH) # 使用 BRUSH 图标
        setAllColorsBtn.setMinimumWidth(120)
        
        # 连接按钮事件
        startMonitorBtn.clicked.connect(self.health_monitor.start_monitoring)
        stopMonitorBtn.clicked.connect(self.health_monitor.stop_monitoring)
        setColorBtn.clicked.connect(self.setTeammateHealthBarColor)  # 连接到单个设置方法
        setAllColorsBtn.clicked.connect(self.handleSetAllTeammatesColor) # 连接到统一设置方法
        
        controlLayout.addWidget(startMonitorBtn)
        controlLayout.addWidget(stopMonitorBtn)
        controlLayout.addWidget(setColorBtn)  # 添加单个设置按钮
        controlLayout.addWidget(setAllColorsBtn) # 添加统一设置按钮
        controlLayout.addStretch(1)
        
        # 血条展示区域
        self.health_bars_frame = QFrame()
        self.health_bars_frame.setObjectName("cardFrame")
        self.health_bars_frame.setStyleSheet("QFrame#cardFrame { background-color: rgba(240, 240, 240, 0.7); border-radius: 8px; padding: 10px; }")
        healthBarsLayout = QVBoxLayout(self.health_bars_frame)
        healthBarsLayout.setSpacing(12)
        healthBarsLayout.setContentsMargins(15, 15, 15, 15)
        
        # 初始化血条UI
        self.init_health_bars_ui()
        
        # 添加到监控布局
        layout.addLayout(titleLayout)
        layout.addLayout(controlLayout)
        layout.addWidget(self.health_bars_frame, 1)  # 将监控卡片设置为可伸展，占用更多空间
        
        # 设置卡片
        settingsCard = HeaderCardWidget(self.healthMonitorInterface)
        settingsCard.setTitle("血条监控设置")
        
        settingsLayout = QVBoxLayout()
        settingsLayout.setSpacing(12)
        
        # 基本设置组
        paramsGroup = QGroupBox("监控参数", self.healthMonitorInterface)
        paramsGroupLayout = QVBoxLayout()
        
        # 阈值设置
        thresholdLayout = QHBoxLayout()
        thresholdLabel = BodyLabel(f"血条阈值: {int(self.health_monitor.health_threshold)}%")
        thresholdSlider = Slider(Qt.Horizontal)
        thresholdSlider.setRange(0, 100)
        thresholdSlider.setValue(int(self.health_monitor.health_threshold))
        thresholdLayout.addWidget(thresholdLabel)
        thresholdLayout.addWidget(thresholdSlider)
        thresholdSlider.valueChanged.connect(lambda v: self.update_health_threshold(v, thresholdLabel))
        
        # 采样率设置
        samplingLayout = QHBoxLayout()
        samplingLabel = BodyLabel("采样率 (fps):")
        samplingSpinBox = SpinBox()
        samplingSpinBox.setRange(1, 60)
        samplingSpinBox.setValue(10)
        samplingLayout.addWidget(samplingLabel)
        samplingLayout.addWidget(samplingSpinBox)
        
        # 添加所有参数设置
        paramsGroupLayout.addLayout(thresholdLayout)
        paramsGroupLayout.addLayout(samplingLayout)
        
        # 自动点击低血量队友功能开关
        autoClickLayout = QHBoxLayout()
        autoClickLabel = BodyLabel("自动点击低血量队友:")
        self.autoClickSwitch = SwitchButton()
        # 从 HealthMonitor 加载初始状态
        if hasattr(self, 'health_monitor') and hasattr(self.health_monitor, 'auto_select_enabled'):
            self.autoClickSwitch.setChecked(self.health_monitor.auto_select_enabled)
        else:
            self.autoClickSwitch.setChecked(False) # 默认关闭
        
        # 新增：职业优先级下拉框
        priorityLabel = BodyLabel("优先职业:")
        self.priorityComboBox = ComboBox()
        self.priorityComboBox.setFixedWidth(120)
        # 加载所有职业选项
        self.load_profession_options()
        # 设置当前选中值
        if hasattr(self, 'health_monitor') and hasattr(self.health_monitor, 'priority_profession'):
            priority_index = self.priorityComboBox.findText(self.health_monitor.priority_profession)
            if priority_index >= 0:
                self.priorityComboBox.setCurrentIndex(priority_index)
        
        # 连接信号
        self.autoClickSwitch.checkedChanged.connect(self.toggle_auto_click_low_health)
        self.priorityComboBox.currentTextChanged.connect(self.update_priority_profession)
        
        autoClickLayout.addWidget(autoClickLabel)
        autoClickLayout.addWidget(self.autoClickSwitch)
        autoClickLayout.addSpacing(20)  # 增加间距
        autoClickLayout.addWidget(priorityLabel)
        autoClickLayout.addWidget(self.priorityComboBox)
        autoClickLayout.addStretch(1)
        paramsGroupLayout.addLayout(autoClickLayout) # 添加到参数组布局
        
        paramsGroup.setLayout(paramsGroupLayout)
        
        # 添加到主设置布局
        settingsLayout.addWidget(paramsGroup)
        settingsCardWidget = QWidget()
        settingsCardWidget.setLayout(settingsLayout)
        settingsCard.viewLayout.addWidget(settingsCardWidget)
        
        # 添加卡片到主布局，但设置较小的高度比例
        layout.addWidget(settingsCard)
        
        # 更新采样率设置
        samplingSpinBox.valueChanged.connect(self.update_sampling_rate)
    
    def init_health_bars_ui(self):
        """初始化血条UI显示"""
        if not self.health_bars_frame:
            return

        # 清除现有布局中的所有组件
        current_layout = self.health_bars_frame.layout()
        if current_layout is not None:
            while current_layout.count():
                item = current_layout.takeAt(0)
                widget = item.widget()
                if widget:
                    widget.deleteLater()
        else:
            # 如果布局不存在，则创建一个新的
            new_layout = QVBoxLayout(self.health_bars_frame)
            new_layout.setSpacing(12)
            new_layout.setContentsMargins(15, 15, 15, 15)
            self.health_bars_frame.setLayout(new_layout) # 设置新布局
        
        # --- 新增：按血条 y1, x1 坐标对队员进行排序 ---
        sorted_members = sorted(self.team.members, key=lambda m: (m.y1, m.x1))
        
        # 添加队友信息卡片
        for i, member in enumerate(sorted_members): # 使用排序后的列表
            self.add_health_bar_card(i, member.name, member.profession)
            
        # 如果没有队友，显示提示信息
        if not self.team.members and self.health_bars_frame.layout() is not None: # 检查原始列表判断是否有队友
            noMemberLabel = StrongBodyLabel("没有队友信息。请在队员识别页面添加队友。")
            noMemberLabel.setAlignment(Qt.AlignCenter)
            self.health_bars_frame.layout().addWidget(noMemberLabel)
        
        # 添加：强制更新框架，确保UI刷新
        self.health_bars_frame.update()
    
    def add_health_bar_card(self, index, name, profession):
        """添加血条卡片
        
        参数:
            index: 队友索引
            name: 队友名称
            profession: 队友职业
        """
        # 创建水平布局，每一行一个队员
        memberCard = QFrame()
        memberCard.setObjectName(f"member_card_{index}")
        memberCard.setFixedHeight(60)  # 设置固定高度
        memberCard.setStyleSheet("background-color: transparent;")
        memberLayout = QHBoxLayout(memberCard)
        memberLayout.setContentsMargins(5, 0, 5, 0)
        memberLayout.setSpacing(10)
        
        # 队员编号和名称 - 使用实际名称
        nameLabel = StrongBodyLabel(name)
        nameLabel.setObjectName(f"name_label_{index}")
        nameLabel.setStyleSheet("font-size: 14px; font-weight: bold;")
        nameLabel.setFixedWidth(80)
        
        # 修改：直接显示识别到的职业名称
        roleLabel = BodyLabel(str(profession)) # 确保是字符串
        roleLabel.setStyleSheet("color: #666; font-size: 12px;")
        roleLabel.setFixedWidth(60)
        roleLabel.setToolTip(str(profession)) # 添加悬浮提示显示完整职业名
        
        # 血条容器
        healthBarContainer = QFrame()
        healthBarContainer.setFixedHeight(25)
        healthBarContainer.setStyleSheet("background-color: #333; border-radius: 5px;")
        # --- 添加：设置最大宽度 --- 
        MAX_WIDTH = 300  # 与 update_health_display 中保持一致
        healthBarContainer.setMaximumWidth(MAX_WIDTH) 
        # --- 结束添加 ---
        healthBarContainerLayout = QHBoxLayout(healthBarContainer)
        healthBarContainerLayout.setContentsMargins(2, 2, 2, 2)
        healthBarContainerLayout.setSpacing(0)
        
        # 血条
        healthBar = QFrame()
        healthBar.setObjectName(f"health_bar_{index}")
        healthBar.setFixedHeight(21)
        
        # 根据索引设置不同颜色
        color = "#2ecc71"  # 绿色 (默认，表示90%)
        if index == 1:
            color = "#2ecc71"  # 绿色 (70%)
        elif index == 2:
            color = "#f39c12"  # 黄色 (50%)
        elif index == 3:
            color = "#e74c3c"  # 红色 (30%)
        elif index == 4:
            color = "#e74c3c"  # 红色 (10%)
        
        # 设置默认百分比
        default_percentage = 90
        if index == 1:
            default_percentage = 70
        elif index == 2:
            default_percentage = 50
        elif index == 3:
            default_percentage = 30
        elif index == 4:
            default_percentage = 10
        
        # 设置血条缩放因子和最大宽度
        SCALE_FACTOR = 3
        MAX_WIDTH = 300  # 血条最大宽度
        
        # 计算血条宽度
        bar_width = min(int(default_percentage * SCALE_FACTOR), MAX_WIDTH)
        print(f"队员{index+1} 初始血条宽度: {bar_width}px (血量: {default_percentage}%)")
        
        healthBar.setStyleSheet(f"background-color: {color}; border-radius: 3px;")
        healthBar.setFixedWidth(bar_width)  # 使用计算的宽度
        
        healthBarContainerLayout.addWidget(healthBar)
        healthBarContainerLayout.addStretch(1)
        
        # 血量百分比
        valueLabel = StrongBodyLabel(f"{default_percentage}%")
        valueLabel.setObjectName(f"value_label_{index}")
        valueLabel.setStyleSheet(f"color: {color}; font-weight: bold; font-size: 15px;")
        valueLabel.setAlignment(Qt.AlignCenter)
        valueLabel.setFixedWidth(60)
        
        # 添加调试标签 - 开发期间使用，显示实际内部存储的血量
        debugLabel = QLabel(f"dbg:ok")
        debugLabel.setObjectName(f"debug_label_{index}")
        debugLabel.setStyleSheet("color: #999; font-size: 8px;")
        debugLabel.setFixedWidth(50)
        
        # 添加到卡片布局
        memberLayout.addWidget(nameLabel)
        memberLayout.addWidget(roleLabel)
        memberLayout.addWidget(healthBarContainer)
        memberLayout.addWidget(valueLabel)
        memberLayout.addWidget(debugLabel)  # 添加调试标签
        
        # 添加到主布局
        self.health_bars_frame.layout().addWidget(memberCard)
        
        # 添加分隔线（除了最后一个）
        if index < len(self.team.members) - 1:
            separator = QFrame()
            separator.setFrameShape(QFrame.HLine)
            separator.setFrameShadow(QFrame.Sunken)
            separator.setStyleSheet("background-color: #e0e0e0;")
            separator.setFixedHeight(1)
            self.health_bars_frame.layout().addWidget(separator)
    
    def update_sampling_rate(self, value):
        """更新监控采样率
        
        参数:
            value: 采样率值（fps）
        """
        if hasattr(self, 'health_monitor'):
            # 转换为更新间隔（秒）
            interval = 1.0 / value if value > 0 else 0.1
            self.health_monitor.update_interval = interval
            self.update_monitor_status(f"采样率已更新: {value} fps (更新间隔: {interval:.2f}秒)")
    
    def show_hotkey_settings(self):
        """显示快捷键设置对话框"""
        dialog = HotkeySettingsMessageBox(self.health_monitor, self)
        dialog.exec()
    
    def show_error_message(self, message):
        """显示错误消息
        
        参数:
            message: 错误消息
        """
        InfoBar.error(
            title='错误',
            content=message,
            orient=Qt.Horizontal,
            isClosable=True,
            position=InfoBarPosition.TOP,
            duration=3000,
            parent=self
        )
    
    def set_auto_select(self, enabled):
        """设置自动选择功能
        
        参数:
            enabled: 是否启用
        """
        if hasattr(self, 'health_monitor'):
            self.health_monitor.auto_select_enabled = enabled
            self.health_monitor.save_auto_select_config()
            status = "启用" if enabled else "禁用"
            self.update_monitor_status(f"自动选择功能已{status}")

    def initAssistInterface(self):
        """初始化辅助功能界面"""
        layout = QVBoxLayout(self.assistInterface)
        layout.setSpacing(16)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # 左右布局，左侧为主要功能，右侧为次要功能
        mainLayout = QHBoxLayout()
        mainLayout.setSpacing(16)
        
        # 左侧布局 - 现在只包含快捷键设置
        leftLayout = QVBoxLayout()
        leftLayout.setSpacing(16)
        
        # 快捷键卡片
        hotkeyCard = HeaderCardWidget(self.assistInterface)
        hotkeyCard.setTitle("快捷键设置")
        
        hotkeyLayout = QVBoxLayout()
        hotkeyLayout.setSpacing(12)
        
        # 提示信息
        hotkey_info = BodyLabel("设置全局快捷键用于快速操作。点击\"记录\"按钮后，按下想要设置的键。")
        hotkey_info.setWordWrap(True)
        
        # 快捷键表格
        hotkeyGridLayout = QGridLayout()
        hotkeyGridLayout.setSpacing(12)
        
        # 开始监控
        startMonitorLabel = BodyLabel('开始监控:')
        startMonitorEdit = LineEdit()
        startMonitorEdit.setReadOnly(True)
        startMonitorEdit.setText(self.health_monitor.start_monitoring_hotkey)
        startMonitorRecordBtn = PushButton('记录')
        
        # 停止监控
        stopMonitorLabel = BodyLabel('停止监控:')
        stopMonitorEdit = LineEdit()
        stopMonitorEdit.setReadOnly(True)
        stopMonitorEdit.setText(self.health_monitor.stop_monitoring_hotkey)
        stopMonitorRecordBtn = PushButton('记录')
        
        # 绑定"记录"按钮事件，使用事件过滤器方式
        startMonitorRecordBtn.clicked.connect(lambda: self.install_hotkey_event_filter(startMonitorEdit, stopMonitorEdit, 'start'))
        stopMonitorRecordBtn.clicked.connect(lambda: self.install_hotkey_event_filter(stopMonitorEdit, startMonitorEdit, 'stop'))
        
        # 添加到网格
        hotkeyGridLayout.addWidget(startMonitorLabel, 0, 0)
        hotkeyGridLayout.addWidget(startMonitorEdit, 0, 1)
        hotkeyGridLayout.addWidget(startMonitorRecordBtn, 0, 2)
        
        hotkeyGridLayout.addWidget(stopMonitorLabel, 1, 0)
        hotkeyGridLayout.addWidget(stopMonitorEdit, 1, 1)
        hotkeyGridLayout.addWidget(stopMonitorRecordBtn, 1, 2)
        
        # 添加所有组件到快捷键卡片
        hotkeyLayout.addWidget(hotkey_info)
        hotkeyLayout.addLayout(hotkeyGridLayout)
        # 增加状态信息标签
        self.hotkeyStatusLabel = BodyLabel('')
        hotkeyLayout.addWidget(self.hotkeyStatusLabel)
        hotkeyCardWidget = QWidget()
        hotkeyCardWidget.setLayout(hotkeyLayout)
        hotkeyCard.viewLayout.addWidget(hotkeyCardWidget)
        
        # 添加快捷键卡片到左侧布局
        leftLayout.addWidget(hotkeyCard)
        leftLayout.addStretch(1)
        
        # 右侧布局 - 保持不变
        rightLayout = QVBoxLayout()
        rightLayout.setSpacing(16)
        
        # 数据导出卡片
        exportCard = HeaderCardWidget(self.assistInterface)
        exportCard.setTitle("数据导出")
        
        exportLayout = QVBoxLayout()
        exportLayout.setSpacing(12)
        
        # 导出按钮
        exportBtnsLayout = QHBoxLayout()
        
        exportCsvBtn = PushButton("导出CSV")
        exportCsvBtn.setIcon(FIF.DOWNLOAD)
        
        exportJsonBtn = PushButton("导出JSON")
        exportJsonBtn.setIcon(FIF.DOWNLOAD)
        
        exportBtnsLayout.addWidget(exportCsvBtn)
        exportBtnsLayout.addWidget(exportJsonBtn)
        exportBtnsLayout.addStretch(1)
        
        # 自动导出开关
        autoExportLayout = QHBoxLayout()
        autoExportLabel = BodyLabel("自动导出:")
        autoExportSwitch = SwitchButton()
        
        autoExportLayout.addWidget(autoExportLabel)
        autoExportLayout.addWidget(autoExportSwitch)
        autoExportLayout.addStretch(1)
        
        # 导出路径
        exportPathLayout = QHBoxLayout()
        exportPathLabel = BodyLabel("导出路径:")
        exportPathEdit = LineEdit()
        exportPathEdit.setText(os.path.join(os.path.expanduser("~"), "Documents"))
        exportPathBtn = PushButton("浏览")
        exportPathBtn.setIcon(FIF.FOLDER)
        
        exportPathLayout.addWidget(exportPathLabel)
        exportPathLayout.addWidget(exportPathEdit)
        exportPathLayout.addWidget(exportPathBtn)
        
        # 添加所有组件到导出卡片
        exportLayout.addLayout(exportBtnsLayout)
        exportLayout.addLayout(autoExportLayout)
        exportLayout.addLayout(exportPathLayout)
        exportCardWidget = QWidget()
        exportCardWidget.setLayout(exportLayout)
        exportCard.viewLayout.addWidget(exportCardWidget)
        
        # 添加导出卡片到右侧布局
        rightLayout.addWidget(exportCard)
        rightLayout.addStretch(1)
        
        # 添加左右布局到主布局
        mainLayout.addLayout(leftLayout, 2)
        mainLayout.addLayout(rightLayout, 1)
        
        # 添加主布局到辅助功能界面
        layout.addLayout(mainLayout)

    def initSettingsInterface(self):
        """初始化设置界面"""
        layout = QVBoxLayout(self.settingsInterface)
        layout.setSpacing(16)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # 基本设置卡片
        basicCard = HeaderCardWidget(self.settingsInterface)
        basicCard.setTitle("基本设置")
        
        basicLayout = QVBoxLayout()
        basicLayout.setSpacing(16)
        
        # 主题设置
        themeLayout = QHBoxLayout()
        themeLabel = BodyLabel("主题:")
        themeCombo = ComboBox()
        themeCombo.addItems(["跟随系统", "亮色模式", "暗色模式"])
        themeLayout.addWidget(themeLabel)
        themeLayout.addWidget(themeCombo)
        themeLayout.addStretch(1)
        
        # 语言设置
        languageLayout = QHBoxLayout()
        languageLabel = BodyLabel("语言:")
        languageCombo = ComboBox()
        languageCombo.addItems(["简体中文", "English"])
        languageLayout.addWidget(languageLabel)
        languageLayout.addWidget(languageCombo)
        languageLayout.addStretch(1)
        
        # 自动启动
        autoStartLayout = QHBoxLayout()
        autoStartLabel = BodyLabel("开机自动启动:")
        autoStartSwitch = SwitchButton()
        autoStartLayout.addWidget(autoStartLabel)
        autoStartLayout.addWidget(autoStartSwitch)
        autoStartLayout.addStretch(1)
        
        # 添加所有组件到基本设置卡片
        basicLayout.addLayout(themeLayout)
        basicLayout.addLayout(languageLayout)
        basicLayout.addLayout(autoStartLayout)
        basicCardWidget = QWidget()
        basicCardWidget.setLayout(basicLayout)
        basicCard.viewLayout.addWidget(basicCardWidget)
        
        # 高级设置卡片
        advancedCard = HeaderCardWidget(self.settingsInterface)
        advancedCard.setTitle("高级设置")
        
        advancedLayout = QVBoxLayout()
        advancedLayout.setSpacing(16)
        
        # 缓存设置
        cacheLayout = QHBoxLayout()
        cacheLabel = BodyLabel("缓存大小:")
        cacheSizeLabel = BodyLabel("23.5 MB")
        clearCacheBtn = PushButton("清除缓存")
        clearCacheBtn.setIcon(FIF.DELETE)
        
        cacheLayout.addWidget(cacheLabel)
        cacheLayout.addWidget(cacheSizeLabel)
        cacheLayout.addStretch(1)
        cacheLayout.addWidget(clearCacheBtn)
        
        # AI模型设置
        modelLayout = QHBoxLayout()
        modelLabel = BodyLabel("AI模型:")
        modelCombo = ComboBox()
        modelCombo.addItems(['标准模型', '轻量级模型', '高精度模型', '自娱自乐模型', '作者没钱加模型'])
        modelLayout.addWidget(modelLabel)
        modelLayout.addWidget(modelCombo)
        modelLayout.addStretch(1)
        
        # GPU加速
        gpuLayout = QHBoxLayout()
        gpuLabel = BodyLabel("GPU加速:")
        gpuSwitch = SwitchButton()
        gpuSwitch.setChecked(True)
        gpuLayout.addWidget(gpuLabel)
        gpuLayout.addWidget(gpuSwitch)
        gpuLayout.addStretch(1)
        
        # 添加所有组件到高级设置卡片
        advancedLayout.addLayout(cacheLayout)
        advancedLayout.addLayout(modelLayout)
        advancedLayout.addLayout(gpuLayout)
        advancedCardWidget = QWidget()
        advancedCardWidget.setLayout(advancedLayout)
        advancedCard.viewLayout.addWidget(advancedCardWidget)
        
        # 关于卡片
        aboutCard = HeaderCardWidget(self.settingsInterface)
        aboutCard.setTitle("关于")
        
        aboutLayout = QVBoxLayout()
        aboutLayout.setSpacing(16)
        
        # 版本信息
        versionLayout = QHBoxLayout()
        versionLabel = BodyLabel("版本:")
        versionValueLabel = BodyLabel("VitalSync 2.0.0")
        versionLayout.addWidget(versionLabel)
        versionLayout.addWidget(versionValueLabel)
        versionLayout.addStretch(1)
        
        # 关于信息
        aboutInfoLabel = BodyLabel("VitalSync 是一款专为游戏设计的队员血条识别与监控软件，支持多种游戏和场景。")
        aboutInfoLabel.setWordWrap(True)
        
        # 控制按钮
        controlLayout = QHBoxLayout()
        updateBtn = PushButton("检查更新")
        updateBtn.setIcon(FIF.UPDATE)
        
        githubBtn = PushButton("GitHub项目")
        githubBtn.setIcon(FIF.LINK)
        # 连接点击事件
        githubBtn.clicked.connect(self.openGitHubProject)
        
        controlLayout.addWidget(updateBtn)
        controlLayout.addWidget(githubBtn)
        controlLayout.addStretch(1)
        
        # 添加所有组件到关于卡片
        aboutLayout.addLayout(versionLayout)
        aboutLayout.addWidget(aboutInfoLabel)
        aboutLayout.addLayout(controlLayout)
        aboutCardWidget = QWidget()
        aboutCardWidget.setLayout(aboutLayout)
        aboutCard.viewLayout.addWidget(aboutCardWidget)
        
        # 添加所有卡片到设置界面
        layout.addWidget(basicCard)
        layout.addWidget(advancedCard)
        layout.addWidget(aboutCard)
        layout.addStretch(1)

    def openGitHubProject(self):
        """打开GitHub项目页面"""
        url = QUrl("https://github.com/yinduandafeimao/VitalSync-Pulse")
        QDesktopServices.openUrl(url)
        
        # 显示提示信息
        InfoBar.success(
            title='已打开链接',
            content='已在浏览器中打开GitHub项目页面',
            orient=Qt.Horizontal,
            isClosable=True,
            position=InfoBarPosition.TOP,
            duration=2000,
            parent=self
        )

    def addProfessionIcon(self):
        """添加新的职业图标"""
        # 检查profession_icons文件夹是否存在
        profession_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "profession_icons")
        if not os.path.exists(profession_path):
            os.makedirs(profession_path)  # 创建文件夹如果不存在
            
        # 打开文件选择对话框
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "选择职业图标",
            "",
            "图片文件 (*.png *.jpg *.jpeg)"
        )
        
        if not file_path:
            return
        
        # 获取文件名
        file_name_without_ext = os.path.splitext(os.path.basename(file_path))[0]
        
        # 使用自定义无边框对话框获取职业名称
        input_dialog = TextInputMessageBox(
            title='输入职业名称',
            label_text='请输入该职业图标的名称:',
            default_text=file_name_without_ext,
            placeholder_text='例如：奶妈、坦克、输出',
            parent=self
        )
        
        if not input_dialog.exec():
            return
        
        icon_name = input_dialog.get_text()
        if not icon_name:
            InfoBar.warning(
                title='输入无效',
                content='职业名称不能为空。',
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=2000,
                parent=self
            )
            return
        
        # 构造目标路径
        target_path = os.path.join(profession_path, icon_name + os.path.splitext(file_path)[1])
        
        # 检查是否已存在同名文件
        if os.path.exists(target_path):
            confirm_dialog = ConfirmMessageBox(
                "文件已存在",
                f"职业 '{icon_name}' 已存在，是否覆盖?",
                self
            )
            
            if not confirm_dialog.exec():
                return
        
        try:
            # 复制文件
            import shutil
            shutil.copy2(file_path, target_path)
            
            # 显示成功消息
            InfoBar.success(
                title='添加成功',
                content=f'职业图标 {icon_name} 已添加',
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=2000,
                parent=self
            )
            
            # 更新图标数量显示
            self.updateIconCount()
        except Exception as e:
            # 显示错误消息
            InfoBar.error(
                title='添加失败',
                content=str(e),
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=3000,
                parent=self
            )
    
    def updateIconCount(self):
        """更新职业图标数量显示"""
        # 重新计算图标数量
        profession_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "profession_icons")
        icon_count = len([f for f in os.listdir(profession_path) if f.endswith(('.png', '.jpg', '.jpeg'))])
        
        # 查找信息标签并更新
        for i in range(self.iconCardWidget.layout().count()):
            item = self.iconCardWidget.layout().itemAt(i)
            if item.widget() and isinstance(item.widget(), BodyLabel) and "当前已加载" in item.widget().text():
                item.widget().setText(f'当前已加载 {icon_count} 个职业图标')
                break

    def init_recognition(self):
        """初始化识别模块"""
        try:
            if self.recognition is None:
                from teammate_recognition import TeammateRecognition
                self.recognition = TeammateRecognition()
                InfoBar.success(
                    title='OCR模型加载成功',
                    content='队友识别功能已准备就绪',
                    orient=Qt.Horizontal,
                    isClosable=True,
                    position=InfoBarPosition.TOP,
                    duration=2000,
                    parent=self
                )
            return True
        except Exception as e:
            InfoBar.error(
                title='OCR初始化失败',
                content=f'错误: {str(e)}',
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=3000,
                parent=self
            )
            return False

    def addTeammate(self):
        """添加队友"""
        print("\n添加新队友:")
        
        # 使用自定义的MessageBoxBase子类
        dialog = AddTeammateMessageBox(self)
        
        if dialog.exec():
            name, profession = dialog.get_teammate_info()
            
            # 使用Team类添加队友
            new_member = self.team.add_member(name, profession)
            
            # 使用全局默认颜色设置(如果有的话)
            if self.default_hp_color_lower is not None and self.default_hp_color_upper is not None:
                import numpy as np
                new_member.hp_color_lower = np.copy(self.default_hp_color_lower)
                new_member.hp_color_upper = np.copy(self.default_hp_color_upper)
                new_member.save_config()  # 保存颜色设置到队员配置文件
            
            # 更新健康监控
            self.health_monitor.team = self.team
            self.init_health_bars_ui()
            
            # 提示设置血条位置 - 使用自定义确认对话框
            confirm_dialog = ConfirmMessageBox(
                "设置血条位置",
                f"是否立即为 {name} 设置血条位置？",
                self
            )
            
            if confirm_dialog.exec():
                # 使用选择框设置血条位置
                self.set_health_bar_position(new_member)
            
            InfoBar.success(
                title='添加成功',
                content=f'队友 {name} ({profession}) 已添加',
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=2000,
                parent=self
            )

    def set_health_bar_position(self, member):
        """设置队员血条位置"""
        from 选择框 import show_selection_box
        
import sys
import os
import cv2
import numpy as np
import json
import threading
import pyautogui
import time
import asyncio
import edge_tts
import tempfile
import queue # 新增导入
# 移除 playsound 导入
# from playsound import playsound
# 添加 pygame 导入
import pygame
from PyQt5.QtCore import Qt, QTimer, QByteArray, QBuffer, QIODevice, QPoint, QSize, QRect, QThread, pyqtSignal, QObject, QEvent, QUrl, QPropertyAnimation
from PyQt5.QtGui import QPixmap, QImage, QIcon, QColor, QFont, QKeySequence, QDesktopServices
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                            QLabel, QFileDialog, QFrame, QGridLayout, QSplitter, QTabWidget, QGroupBox,
                            QInputDialog, QDialog, QListWidget, QListWidgetItem, QAbstractItemView,
                            QGraphicsDropShadowEffect)

# 导入Fluent组件库
from qfluentwidgets import (FluentWindow, NavigationItemPosition, PushButton, 
                           ToolButton, PrimaryPushButton, ComboBox, RadioButton, CheckBox,
                           Slider, SwitchButton, ToggleButton, SubtitleLabel, BodyLabel,
                           Action, setTheme, Theme, MessageBox, MessageBoxBase, InfoBar, TabBar,
                           TransparentPushButton, LineEdit, StrongBodyLabel, CaptionLabel,
                           SpinBox, DoubleSpinBox, ScrollArea, CardWidget, HeaderCardWidget,
                           InfoBarPosition, NavigationInterface, setThemeColor, FluentIcon as FIF)

# 导入血条校准模块
from health_bar_calibration import HealthBarCalibration

# 导入血条监控模块
from health_monitor import HealthMonitor, MonitorSignals

# 动态导入带空格的模块
import importlib.util

# 动态导入带空格的模块
module_name = "team_members(choice box)"
module_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "team_members(choice box).py")
spec = importlib.util.spec_from_file_location(module_name, module_path)
team_members_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(team_members_module)

# 从module中获取Team和TeamMember类
Team = team_members_module.Team
TeamMember = team_members_module.TeamMember

# 设置应用全局样式
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

# 定义配置文件名
# CONFIG_FILE = 'config.json'  # 已迁移到配置管理系统

# 自定义对话框类 - 完全参照示例代码
class ColorPickerMessageBox(MessageBoxBase):
    """ Custom message box for color picking """

    def __init__(self, member_name, parent=None):
        super().__init__(parent)
        self.titleLabel = SubtitleLabel(f'设置 {member_name} 的血条颜色', self)
        
        # 添加指南标签
        self.guideLabel = BodyLabel(
            '1. 将鼠标移动到游戏中该队友的血条上\n'
            '2. 选择血条最具代表性的颜色位置\n'
            '3. 按下空格键获取颜色\n'
            '4. 按ESC键取消操作'
        )
        self.guideLabel.setWordWrap(True)
        
        # 状态标签
        self.statusLabel = CaptionLabel("状态：等待获取颜色...")
        self.statusLabel.setTextColor("#1e88e5", QColor(30, 136, 229))
        
        # 预览区域
        previewLayout = QHBoxLayout()
        previewLabel = BodyLabel('颜色预览：')
        self.colorPreview = QFrame()
        self.colorPreview.setFixedSize(50, 20)
        self.colorPreview.setFrameShape(QFrame.Box)
        previewLayout.addWidget(previewLabel)
        previewLayout.addWidget(self.colorPreview)
        previewWidget = QWidget()
        previewWidget.setLayout(previewLayout)

        # 添加到视图布局
        self.viewLayout.addWidget(self.titleLabel)
        self.viewLayout.addWidget(self.guideLabel)
        self.viewLayout.addWidget(self.statusLabel)
        self.viewLayout.addWidget(previewWidget)

        # 修改按钮文本
        self.yesButton.setText('确定')
        self.cancelButton.setText('取消')

        # 设置最小宽度
        self.widget.setMinimumWidth(350)
        
        # 颜色获取状态和计时器
        self.color_captured = False
        self.key_check_timer = QTimer(self)
        self.key_check_timer.timeout.connect(self.check_keys_and_position)
        self.key_check_timer.start(100)
        
        # 存储成员名称
        self.member_name = member_name
        
    def check_keys_and_position(self):
        """检查键盘输入和鼠标位置"""
        import keyboard
        if keyboard.is_pressed('space'):
            # 防止重复处理
            if self.color_captured:
                return
            
            self.color_captured = True
            self.key_check_timer.stop()
            
            # 获取当前鼠标位置的屏幕像素颜色
            try:
                import pyautogui
                x, y = pyautogui.position()
                pixel_color = pyautogui.screenshot().getpixel((x, y))
                
                # 显示获取的颜色
                color_hex = "#{:02x}{:02x}{:02x}".format(pixel_color[0], pixel_color[1], pixel_color[2])
                self.colorPreview.setStyleSheet(f"background-color: {color_hex};")
                
                # --- 将RGB转换为BGR ---
                rgb_tuple = pixel_color[:3]
                bgr_values = (rgb_tuple[2], rgb_tuple[1], rgb_tuple[0]) # B, G, R
                
                # 创建颜色上下限（允许一定范围的变化）- 使用BGR值
                import numpy as np
                self.color_lower = np.array([max(0, c - 30) for c in bgr_values], dtype=np.uint8)
                self.color_upper = np.array([min(255, c + 30) for c in bgr_values], dtype=np.uint8)
                
                self.statusLabel.setText(f"状态：成功获取颜色！RGB: {rgb_tuple}")
                self.statusLabel.setTextColor("#2ecc71", QColor(46, 204, 113))
                
                # 延迟关闭对话框
                QTimer.singleShot(1500, lambda: self.accept())
                
            except Exception as e:
                self.statusLabel.setText(f"状态：获取颜色失败 - {str(e)}")
                self.statusLabel.setTextColor("#e74c3c", QColor(231, 76, 60))
                self.color_captured = False  # 重置状态，允许重试
                self.key_check_timer.start()  # 重新启动定时器
        
        elif keyboard.is_pressed('esc'):
            if not self.color_captured:  # 只有在未捕获颜色时才处理ESC键
                self.key_check_timer.stop()
                self.reject()

class HotkeySettingsMessageBox(MessageBoxBase):
    """ Custom message box for hotkey settings """

    def __init__(self, health_monitor, parent=None):
        super().__init__(parent)
        self.titleLabel = SubtitleLabel('监控快捷键设置', self)
        self.health_monitor = health_monitor
        self.parent_window = parent
        
        # 当前快捷键展示
        self.infoLabel = BodyLabel(f"当前快捷键设置:\n开始监控: {health_monitor.start_monitoring_hotkey}\n停止监控: {health_monitor.stop_monitoring_hotkey}")
        self.infoLabel.setWordWrap(True)
        
        # 设置表单
        form_widget = QWidget()
        form_layout = QGridLayout(form_widget)
        form_layout.setSpacing(10)
        
        # 开始监控输入
        self.start_label = BodyLabel("开始监控键:")
        self.start_input = LineEdit()
        self.start_input.setText(health_monitor.start_monitoring_hotkey)
        self.start_input.setPlaceholderText("按下快捷键组合")
        
        # 停止监控输入
        self.stop_label = BodyLabel("停止监控键:")
        self.stop_input = LineEdit()
        self.stop_input.setText(health_monitor.stop_monitoring_hotkey)
        self.stop_input.setPlaceholderText("按下快捷键组合")
        
        # 错误提示标签
        self.error_label = CaptionLabel("")
        self.error_label.setTextColor("#cf1010", QColor(255, 28, 32))
        self.error_label.hide()
        
        # 增加记录按钮以记录实际按键
        self.start_record = PushButton("记录")
        self.start_record.clicked.connect(lambda: self.record_hotkey('start'))
        
        self.stop_record = PushButton("记录")
        self.stop_record.clicked.connect(lambda: self.record_hotkey('stop'))
        
        # 添加到布局
        form_layout.addWidget(self.start_label, 0, 0)
        form_layout.addWidget(self.start_input, 0, 1)
        form_layout.addWidget(self.start_record, 0, 2)
        
        form_layout.addWidget(self.stop_label, 1, 0)
        form_layout.addWidget(self.stop_input, 1, 1)
        form_layout.addWidget(self.stop_record, 1, 2)
        
        # 将所有控件添加到视图布局
        self.viewLayout.addWidget(self.titleLabel)
        self.viewLayout.addWidget(self.infoLabel)
        self.viewLayout.addWidget(form_widget)
        self.viewLayout.addWidget(self.error_label)
        
        # 设置按钮文本
        self.yesButton.setText('保存')
        self.cancelButton.setText('取消')
        
        # 设置最小宽度
        self.widget.setMinimumWidth(400)
    
    def record_hotkey(self, which):
        """弹出对话框录入快捷键"""
        from PyQt5.QtGui import QKeySequence
        
        # 创建录入对话框
        dialog = MessageBoxBase(self)
        dialog.titleLabel = SubtitleLabel('录入快捷键', dialog)
        
        # 说明标签
        guide_label = BodyLabel('请按下新的快捷键组合（如 Ctrl+Alt+S）')
        key_label = BodyLabel('等待按键...')
        
        # 添加到视图布局
        dialog.viewLayout.addWidget(dialog.titleLabel)
        dialog.viewLayout.addWidget(guide_label)
        dialog.viewLayout.addWidget(key_label)
        
        # 设置按钮文本，初始时禁用确定按钮
        dialog.yesButton.setText('确定')
        dialog.yesButton.setEnabled(False)
        dialog.cancelButton.setText('取消')
        
        # 存储按键
        key_seq = {'text': ''}
        
        # 重写keyPressEvent处理按键
        def keyPressEvent(event):
            # 保存原始方法
            original_keyPressEvent = dialog.keyPressEvent
            
            key_text = ''
            modifiers = event.modifiers()
            if modifiers & Qt.ControlModifier:
                key_text += 'ctrl+'
            if modifiers & Qt.AltModifier:
                key_text += 'alt+'
            if modifiers & Qt.ShiftModifier:
                key_text += 'shift+'
            key = event.key()
            if key in (Qt.Key_Control, Qt.Key_Alt, Qt.Key_Shift):
                # 恢复原始方法并调用它
                dialog.keyPressEvent = original_keyPressEvent
                return original_keyPressEvent(event)
            key_name = QKeySequence(key).toString().lower()
            key_text += key_name
            key_seq['text'] = key_text
            key_label.setText(f'已录入: {key_text}')
            dialog.yesButton.setEnabled(True)
            
            # 恢复原始方法
            dialog.keyPressEvent = original_keyPressEvent
        
        # 保存原始方法
        original_method = dialog.keyPressEvent
        # 替换方法
        dialog.keyPressEvent = keyPressEvent
        
        # 显示对话框
        if dialog.exec():
            if key_seq['text']:
                if which == 'start':
                    self.start_input.setText(key_seq['text'])
                else:
                    self.stop_input.setText(key_seq['text'])
    
    def validate(self):
        """验证输入是否有效"""
        start_key = self.start_input.text()
        stop_key = self.stop_input.text()
        
        # 检查输入是否有效
        if not start_key or not stop_key:
            self.error_label.setText("快捷键不能为空")
            self.error_label.show()
            return False
            
        if start_key == stop_key:
            self.error_label.setText("开始和停止快捷键不能相同")
            self.error_label.show()
            return False
        
        # 尝试设置新的快捷键
        success = self.health_monitor.set_hotkeys(start_key, stop_key)
        
        if not success:
            self.error_label.setText("设置快捷键失败，请重试")
            self.error_label.show()
            return False
            
        return True

class TeammateSelectionMessageBox(MessageBoxBase):
    """ Custom message box for teammate selection """

    def __init__(self, title, team_members, parent=None):
        super().__init__(parent)
        self.titleLabel = SubtitleLabel(title, self)
        
        # 添加说明
        self.infoLabel = BodyLabel("请从列表中选择一个队友")
        
        # 创建队友列表
        self.listWidget = QListWidget(self)
        for i, member in enumerate(team_members):
            self.listWidget.addItem(f"{member.name} ({member.profession})")
        
        # 警告标签
        self.warningLabel = CaptionLabel("未选择任何队友")
        self.warningLabel.setTextColor("#cf1010", QColor(255, 28, 32))
        self.warningLabel.hide()  # 默认隐藏
        
        # 添加到视图布局
        self.viewLayout.addWidget(self.titleLabel)
        self.viewLayout.addWidget(self.infoLabel)
        self.viewLayout.addWidget(self.listWidget)
        self.viewLayout.addWidget(self.warningLabel)
        
        # 设置按钮文本
        self.yesButton.setText('选择')
        self.cancelButton.setText('取消')
        
        # 设置最小宽度
        self.widget.setMinimumWidth(350)
        
        # 存储队友列表
        self.team_members = team_members
        self.selected_index = -1
        
        # 连接列表点击事件
        self.listWidget.itemClicked.connect(self.on_item_clicked)
    
    def on_item_clicked(self, item):
        """列表项被点击时更新选择索引"""
        self.selected_index = self.listWidget.row(item)
        self.warningLabel.hide()  # 隐藏警告
    
    def get_selected_member(self):
        """获取选中的队友"""
        if self.selected_index >= 0 and self.selected_index < len(self.team_members):
            return self.team_members[self.selected_index]
        return None
        
    def validate(self):
        """验证是否选择了队友"""
        if self.selected_index >= 0:
            return True
        else:
            self.warningLabel.show()  # 显示警告
            return False

class UnifiedColorPickerMessageBox(MessageBoxBase):
    """ Custom message box for unified color picking """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.titleLabel = SubtitleLabel('统一设置所有队友的血条颜色', self)
        
        # 添加操作指南
        self.guideLabel = BodyLabel(
            '1. 将鼠标移动到游戏中任意一个队友的血条上\n'
            '2. 选择血条最具代表性的颜色位置\n'
            '3. 按下空格键获取颜色，此颜色将应用于所有队友\n'
            '4. 按ESC键取消操作'
        )
        self.guideLabel.setWordWrap(True)
        
        # 状态标签
        self.statusLabel = CaptionLabel("状态：等待获取颜色...")
        self.statusLabel.setTextColor("#1e88e5", QColor(30, 136, 229))
        
        # 预览区域
        previewLayout = QHBoxLayout()
        previewLabel = BodyLabel('颜色预览：')
        self.colorPreview = QFrame()
        self.colorPreview.setFixedSize(50, 20)
        self.colorPreview.setFrameShape(QFrame.Box)
        previewLayout.addWidget(previewLabel)
        previewLayout.addWidget(self.colorPreview)
        previewWidget = QWidget()
        previewWidget.setLayout(previewLayout)
        
        # 添加到视图布局
        self.viewLayout.addWidget(self.titleLabel)
        self.viewLayout.addWidget(self.guideLabel)
        self.viewLayout.addWidget(self.statusLabel)
        self.viewLayout.addWidget(previewWidget)
        
        # 设置按钮文本
        self.yesButton.setText('确定')
        self.cancelButton.setText('取消')
        
        # 设置最小宽度
        self.widget.setMinimumWidth(350)
        
        # 颜色获取状态和计时器
        self.color_captured = False
        self.key_check_timer = QTimer(self)
        self.key_check_timer.timeout.connect(self.check_keys_and_position)
        self.key_check_timer.start(100)
        
        # 存储获取的颜色值
        self.pixel_color_rgb = None

    def check_keys_and_position(self):
        """检查键盘输入和鼠标位置"""
        import keyboard
        if keyboard.is_pressed('space'):
            if self.color_captured:
                return
            
            self.color_captured = True
            self.key_check_timer.stop()
            
            try:
                import pyautogui
                x, y = pyautogui.position()
                self.pixel_color_rgb = pyautogui.screenshot().getpixel((x, y))[:3]  # 确保是RGB
                
                color_hex = "#{:02x}{:02x}{:02x}".format(
                    self.pixel_color_rgb[0], 
                    self.pixel_color_rgb[1], 
                    self.pixel_color_rgb[2]
                )
                self.colorPreview.setStyleSheet(f"background-color: {color_hex};")
                
                self.statusLabel.setText(f"状态：成功获取颜色！RGB: {self.pixel_color_rgb}")
                self.statusLabel.setTextColor("#2ecc71", QColor(46, 204, 113))
                
                # 延迟关闭对话框
                QTimer.singleShot(2000, lambda: self.accept())
                
            except Exception as e:
                self.statusLabel.setText(f"状态：获取颜色失败 - {str(e)}")
                self.statusLabel.setTextColor("#e74c3c", QColor(231, 76, 60))
                self.color_captured = False
                self.key_check_timer.start()
        
        elif keyboard.is_pressed('esc'):
            if not self.color_captured:
                self.key_check_timer.stop()
                self.reject()

class MainWindow(FluentWindow):
    def __init__(self):
        """初始化主窗口"""
        super().__init__()
        
        # 初始化 pygame mixer
        try:
            pygame.mixer.init()
            pygame.mixer.set_num_channels(16) # 设置足够多的声道
        except pygame.error as e:
            print(f"Pygame mixer 初始化失败: {e}")
            # 可以选择禁用语音功能或显示错误提示
            InfoBar.error(
                title='音频初始化失败',
                content='无法初始化音频播放组件 (pygame.mixer)，语音播报功能将不可用。',
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=5000,
                parent=self
            )
        
        self._icon_capture_show_selection_timer = None
        self._icon_capture_do_grab_timer = None
        self._icon_capture_rect = None # Store the rect between timer calls
        
        # --- 添加缺失的语音参数初始化 ---
        # 初始化语音参数属性 - 使用滑块的默认值
        # 语速: slider 0-10 -> rate -50% to +50% -> + (value*10 - 50) %
        default_rate_value = 5
        self.voice_rate_param = f'+{default_rate_value * 10 - 50}%'
        # 音量: slider 0-100 -> volume -50% to +50% -> + (value - 50) %
        default_volume_value = 80
        self.voice_volume_param = f'+{default_volume_value - 50}%'
        # --- 初始化结束 ---
        
        # 设置窗口标题和大小
        self.setWindowTitle('VitalSync')
        self.resize(1200, 500) # 将高度从 800 调整为 700
        
        # 设置应用强调色 - 使用截图中的青绿色
        setThemeColor(QColor(0, 168, 174))
        
        # 启用亚克力效果
        self.navigationInterface.setAcrylicEnabled(True)
        
        # 初始化队友管理相关属性
        self.team = Team()  # 创建Team实例
        self.selection_box = None # 屏幕选择框
        
        # 初始化全局默认血条颜色
        self.default_hp_color_lower = None  # 默认血条颜色下限
        self.default_hp_color_upper = None  # 默认血条颜色上限
        self.load_default_colors()  # 从配置加载默认颜色设置
        
        # 初始化健康监控相关属性
        self.health_monitor = HealthMonitor(self.team)  # 创建健康监控实例
        # 连接监控信号
        self.health_monitor.signals.update_signal.connect(self.update_health_display)
        self.health_monitor.signals.status_signal.connect(self.update_monitor_status)
        
        # 创建界面
        self.teamRecognitionInterface = QWidget()
        self.teamRecognitionInterface.setObjectName("teamRecognitionInterface")
        
        self.healthMonitorInterface = QWidget()
        self.healthMonitorInterface.setObjectName("healthMonitorInterface")
        
        self.assistInterface = QWidget()
        self.assistInterface.setObjectName("assistInterface")
        
        self.settingsInterface = QWidget()
        self.settingsInterface.setObjectName("settingsInterface")
        
        # 新增：语音设置界面实例
        self.voiceSettingsInterface = QWidget()
        self.voiceSettingsInterface.setObjectName("voiceSettingsInterface")
        
        # 初始化界面
        self.initTeamRecognitionInterface()
        self.initHealthMonitorInterface()
        self.initAssistInterface()
        self.initSettingsInterface()
        self.initVoiceSettingsInterface() # 新增：调用语音设置界面初始化
        
        # 初始化导航
        self.initNavigation()
        
        # --- 加载设置 ---
        self.load_settings() # 在UI初始化后加载设置
        
        # 显示提示信息
        InfoBar.success(
            title='初始化完成',
            content='系统已准备就绪',
            orient=Qt.Horizontal,
            isClosable=True,
            position=InfoBarPosition.TOP,
            duration=2000,
            parent=self
        )
        
        # 在__init__方法末尾添加：
        self.load_teammates()
        
        # 初始化语音队列和工作线程
        self.speech_queue = queue.Queue()
        self.active_speech = {} # 用于跟踪正在播放的语音及其资源
        self.speech_worker_thread = threading.Thread(target=self._speech_worker_loop, daemon=True)
        self.speech_worker_thread.start()
        
        # 设置一个定时器来处理 Pygame 事件和清理
        self.pygame_event_timer = QTimer(self)
        self.pygame_event_timer.timeout.connect(self._process_pygame_events)
        self.pygame_event_timer.start(100) # 每 100ms 检查一次
    
    def initNavigation(self):
        """初始化导航栏"""
        # 添加子界面
        self.addSubInterface(self.teamRecognitionInterface, FIF.PEOPLE, '队员识别')
        self.addSubInterface(self.healthMonitorInterface, FIF.HEART, '血条监控')
        self.addSubInterface(self.assistInterface, FIF.IOT, '辅助功能')
        self.addSubInterface(self.voiceSettingsInterface, FIF.MICROPHONE, '语音设置') # 使用 FIF.MICROPHONE 图标
        
        # 添加底部界面
        self.addSubInterface(
            self.settingsInterface, 
            FIF.SETTING, 
            '系统设置',
            NavigationItemPosition.BOTTOM
        )

    def initTeamRecognitionInterface(self):
        """初始化队员识别界面"""
        layout = QVBoxLayout(self.teamRecognitionInterface)
        layout.setSpacing(24)  # 增加垂直间距
        layout.setContentsMargins(24, 24, 24, 24)  # 增加外边距
        
        # 创建顶部水平布局，包含职业图标管理和队友管理
        topLayout = QHBoxLayout()
        topLayout.setSpacing(24)  # 增加水平间距
        
        # ========== 左侧：职业图标管理 ==========
        iconCard = HeaderCardWidget(self.teamRecognitionInterface)
        iconCard.setTitle("职业图标管理")
        iconCard.setFixedHeight(200)  # 适当减少卡片高度
        iconLayout = QVBoxLayout()
        iconLayout.setSpacing(15)  # 增加垂直间距
        iconLayout.setContentsMargins(0, 10, 0, 10)  # 增加内边距
        
        # 按钮区域 - 也使用网格布局
        btnLayout = QGridLayout()
        btnLayout.setSpacing(15)  # 增加按钮间距
        
        addIconBtn = PrimaryPushButton('添加图标')
        addIconBtn.setIcon(FIF.ADD)
        addIconBtn.setFixedWidth(140)  # 显著增加按钮宽度
        addIconBtn.setMinimumHeight(36)  # 设置最小高度
        
        captureIconBtn = PushButton('截取图标')
        captureIconBtn.setIcon(FIF.CAMERA) # 使用 CAMERA 图标替代 SCREENSHOT
        captureIconBtn.setFixedWidth(140)  # 显著增加按钮宽度
        captureIconBtn.setMinimumHeight(36)  # 设置最小高度
        
        manageIconsBtn = PushButton('管理图标')
        manageIconsBtn.setIcon(FIF.SETTING)
        manageIconsBtn.setFixedWidth(140)  # 显著增加按钮宽度
        manageIconsBtn.setMinimumHeight(36)  # 设置最小高度
        
        # 连接按钮事件
        addIconBtn.clicked.connect(self.addProfessionIcon)
        captureIconBtn.clicked.connect(self.captureScreenIcon)
        manageIconsBtn.clicked.connect(self.loadProfessionIcons)
        
        # 将按钮添加到网格布局
        btnLayout.addWidget(addIconBtn, 0, 0)
        btnLayout.addWidget(captureIconBtn, 0, 1)
        btnLayout.addWidget(manageIconsBtn, 0, 2)
        
        # 显示图标数量信息
        profession_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "profession_icons")
        
        # 检查文件夹是否存在
        if not os.path.exists(profession_path):
            os.makedirs(profession_path)
            icon_count = 0
        else:
            icon_count = len([f for f in os.listdir(profession_path) if f.endswith(('.png', '.jpg', '.jpeg'))])
            
        infoLabel = BodyLabel(f'已加载 {icon_count} 个职业图标')
        infoLabel.setStyleSheet("color: #666; font-size: 13px;")  # 设置样式，使其显示更清晰
        infoLabel.setAlignment(Qt.AlignCenter)  # 居中对齐
        
        # 添加到卡片布局
        iconLayout.addLayout(btnLayout)
        iconLayout.addWidget(infoLabel)
        iconLayout.addStretch(1)  # 添加弹性空间，将内容推向顶部，使标签居中
        iconCardWidget = QWidget()
        iconCardWidget.setLayout(iconLayout)
        iconCard.viewLayout.addWidget(iconCardWidget)
        self.iconCardWidget = iconCardWidget
        
        # ========== 右侧：队友管理 ==========
        teammateCard = HeaderCardWidget(self.teamRecognitionInterface)
        teammateCard.setTitle("队友管理")
        teammateCard.setFixedHeight(200)  # 适当减少卡片高度
        teammateLayout = QVBoxLayout()
        teammateLayout.setSpacing(30)  # 增加垂直间距
        teammateLayout.setContentsMargins(0, 0, 0, 10)  # 顶部margin设为0，整体上移
        
        # 队友管理按钮区域 - 使用网格布局确保均匀分布
        teammateBtnLayout = QGridLayout()  # 改回网格布局
        teammateBtnLayout.setSpacing(18)  # 进一步增加基础间距 (原为15)
        teammateBtnLayout.setVerticalSpacing(48)  # 大幅增大垂直间距 (原为20)
        teammateBtnLayout.setContentsMargins(10, 0, 10, 0)  # 保持或调整水平内边距
        
        addTeammateBtn = PrimaryPushButton('添加队友')
        addTeammateBtn.setIcon(FIF.ADD)
        addTeammateBtn.setFixedWidth(115)  # 进一步减少按钮宽度 (原为125)
        addTeammateBtn.setMinimumHeight(36)  # 保持按钮高度
        
        removeTeammateBtn = PushButton('移除队友')
        removeTeammateBtn.setIcon(FIF.REMOVE)
        removeTeammateBtn.setFixedWidth(115)  # 进一步减少按钮宽度 (原为125)
        removeTeammateBtn.setMinimumHeight(36)  # 保持按钮高度
        
        loadTeammateBtn = PushButton('加载队友')
        loadTeammateBtn.setIcon(FIF.DOWNLOAD)
        loadTeammateBtn.setFixedWidth(115)  # 进一步减少按钮宽度 (原为125)
        loadTeammateBtn.setMinimumHeight(36)  # 保持按钮高度
        
        clearAllTeammatesBtn = PushButton('清除全部')
        clearAllTeammatesBtn.setIcon(FIF.DELETE)
        clearAllTeammatesBtn.setFixedWidth(115)  # 进一步减少按钮宽度 (原为125)
        clearAllTeammatesBtn.setMinimumHeight(36)  # 保持按钮高度
        
        # 连接按钮事件
        addTeammateBtn.clicked.connect(self.addTeammate)
        removeTeammateBtn.clicked.connect(self.removeTeammate)
        loadTeammateBtn.clicked.connect(self.loadTeammate)
        clearAllTeammatesBtn.clicked.connect(self.clearAllTeammates)
        
        # 使用网格布局均匀排列按钮，2行2列，修正行号并增加间距
        teammateBtnLayout.addWidget(addTeammateBtn, 0, 0)      # 第1行第1列
        teammateBtnLayout.addWidget(removeTeammateBtn, 0, 1)   # 第1行第2列
        teammateBtnLayout.addWidget(loadTeammateBtn, 1, 0)     # 第2行第1列
        teammateBtnLayout.addWidget(clearAllTeammatesBtn, 1, 1) # 第2行第2列
        
        # 队友信息显示
        teammateInfoLabel = BodyLabel('')
        teammateInfoLabel.setObjectName("teammateInfoLabel")  # 设置对象名以便更新时查找
        teammateInfoLabel.setWordWrap(True)  # 允许文字换行
        teammateInfoLabel.setStyleSheet("color: #666; font-size: 13px;")  # 设置样式，使其显示更清晰
        teammateInfoLabel.setAlignment(Qt.AlignCenter)  # 居中对齐
        
        # 添加到卡片布局
        teammateLayout.addLayout(teammateBtnLayout)
        teammateLayout.addWidget(teammateInfoLabel)
        teammateLayout.addStretch(1)  # 添加弹性空间，将内容推向顶部，使标签居中
        teammateCardWidget = QWidget()
        teammateCardWidget.setLayout(teammateLayout)
        teammateCard.viewLayout.addWidget(teammateCardWidget)
        
        # 将两个卡片添加到顶部布局
        topLayout.addWidget(iconCard, 1) # 设置伸展因子为1
        topLayout.addWidget(teammateCard, 1) # 设置伸展因子为1
        
        # ========== 识别队友区域 ==========
        recognitionCard = HeaderCardWidget(self.teamRecognitionInterface)
        recognitionCard.setTitle("识别队友")
        recognitionLayout = QVBoxLayout()
        recognitionLayout.setSpacing(18)  # 增加垂直间距
        recognitionLayout.setContentsMargins(0, 8, 0, 8)  # 增加内边距
        
        # 控制面板区域
        controlsPanel = QFrame()
        controlsPanel.setObjectName("cardFrame")
        controlsPanelLayout = QHBoxLayout(controlsPanel)
        controlsPanelLayout.setSpacing(16)
        controlsPanelLayout.setContentsMargins(16, 12, 16, 12)  # 增加内边距使内容更加突出
        
        # 选择识别位置按钮
        selectPositionBtn = PrimaryPushButton("选择识别位置")
        selectPositionBtn.setIcon(FIF.EDIT)
        selectPositionBtn.setMinimumWidth(160)  # 增加按钮宽度
        
        # 识别状态显示
        statusLabel = BodyLabel("状态: 未开始识别")
        statusLabel.setStyleSheet("color: #888; font-size: 14px;")  # 调整样式
        
        controlsPanelLayout.addWidget(selectPositionBtn)
        controlsPanelLayout.addWidget(statusLabel)
        controlsPanelLayout.addStretch(1)
        
        # 预览区域
        previewArea = QFrame()
        previewArea.setObjectName("cardFrame")
        # 修改：使用浅色背景和深色文字
        previewArea.setStyleSheet("#cardFrame{background-color: #f8f9fa; color: #333333; border-radius: 10px; border: 1px solid #e0e0e0;}") 
        previewLayout = QVBoxLayout(previewArea)
        previewLayout.setContentsMargins(10, 10, 10, 10)  # 添加内边距
        
        previewTitle = QLabel("队友信息预览")
        previewTitle.setAlignment(Qt.AlignCenter)
        # 修改：标题文字颜色改为深色
        previewTitle.setStyleSheet("color: #333333; font-size: 16px; font-weight: bold; margin-bottom: 10px;")
        
        # 创建滚动区域
        scrollArea = ScrollArea()
        scrollArea.setWidgetResizable(True)
        scrollArea.setStyleSheet("background: transparent; border: none;")
        
        scrollContent = QWidget()
        scrollLayout = QVBoxLayout(scrollContent)
        scrollLayout.setContentsMargins(0, 0, 0, 0)
        scrollLayout.setSpacing(8)
        
        # 创建队友信息标签
        self.teammateInfoPreview = QLabel("加载队友信息中...")
        self.teammateInfoPreview.setWordWrap(True)
        # 修改：默认文字颜色改为深色
        self.teammateInfoPreview.setStyleSheet("color: #333333; font-size: 14px;") 
        scrollLayout.addWidget(self.teammateInfoPreview)
        
        scrollArea.setWidget(scrollContent)
        
        previewLayout.addWidget(previewTitle)
        previewLayout.addWidget(scrollArea)
        
        # 添加更新按钮
        updateInfoBtn = PushButton("刷新队友信息")
        updateInfoBtn.setIcon(FIF.SYNC)
        updateInfoBtn.clicked.connect(self.update_teammate_preview)
        previewLayout.addWidget(updateInfoBtn)
        
        # 底部控制按钮
        buttonLayout = QHBoxLayout()
        buttonLayout.setSpacing(16)
        
        startBtn = PrimaryPushButton("开始识别")
        startBtn.setIcon(FIF.PLAY)
        startBtn.setMinimumWidth(130)  # 增加按钮宽度
        
        stopBtn = PushButton("停止")
        stopBtn.setIcon(FIF.CANCEL)
        stopBtn.setMinimumWidth(130)  # 增加按钮宽度
        
        saveBtn = PushButton("导出配置")
        saveBtn.setIcon(FIF.SAVE)
        saveBtn.setMinimumWidth(130)  # 增加按钮宽度
        
        # 连接按钮事件
        selectPositionBtn.clicked.connect(self.select_recognition_position)
        startBtn.clicked.connect(self.start_recognition_from_calibration)
        stopBtn.clicked.connect(self.stop_recognition)
        saveBtn.clicked.connect(self.export_recognition_config)
        
        # 然后继续添加按钮到布局
        buttonLayout.addStretch(1)
        buttonLayout.addWidget(startBtn)
        buttonLayout.addWidget(stopBtn)
        buttonLayout.addWidget(saveBtn)
        buttonLayout.addStretch(1)
        
        # 添加到识别布局
        recognitionLayout.addWidget(controlsPanel)
        recognitionLayout.addWidget(previewArea)
        recognitionLayout.addLayout(buttonLayout)
        
        recognitionCardWidget = QWidget()
        recognitionCardWidget.setLayout(recognitionLayout)
        recognitionCard.viewLayout.addWidget(recognitionCardWidget)
        
        # 添加到主布局
        layout.addLayout(topLayout)
        layout.addWidget(recognitionCard, 1)  # 1表示伸展因子，让这个区域占据更多空间
        
    def loadProfessionIcons(self):
        """加载职业图标并显示管理对话框"""
        # 使用自定义无边框对话框
        manage_dialog = ProfessionIconsManageDialog(self)
        manage_dialog.exec()
    
    def deleteProfessionIcon(self, icon_file, frame, dialog=None):
        """删除职业图标"""
        profession_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "profession_icons")
        icon_path = os.path.join(profession_path, icon_file)
        
        # 确认删除
        confirm_dialog = ConfirmMessageBox(
            "确认删除",
            f"确定要删除职业图标 {os.path.splitext(icon_file)[0]} 吗？",
            self if not dialog else dialog # Keep ConfirmMessageBox parented to dialog for modality
        )
        
        if confirm_dialog.exec():
            try:
                # 删除文件
                os.remove(icon_path)
                # 从UI中移除
                frame.setParent(None)
                frame.deleteLater()
                # 更新图标计数
                self.updateIconCount()
                # 提示成功
                InfoBar.success(
                    title='删除成功',
                    content=f'已删除职业图标 {os.path.splitext(icon_file)[0]}',
                    orient=Qt.Horizontal,
                    isClosable=True,
                    position=InfoBarPosition.TOP,
                    duration=2000,
                    parent=self  # Ensure InfoBar is parented to MainWindow
                )
            except Exception as e:
                # 删除失败提示
                InfoBar.error(
                    title='删除失败',
                    content=str(e),
                    orient=Qt.Horizontal,
                    isClosable=True,
                    position=InfoBarPosition.TOP,
                    duration=3000,
                    parent=self  # Ensure InfoBar is parented to MainWindow
                )

    def initHealthMonitorInterface(self):
        """初始化血条监控界面"""
        layout = QVBoxLayout(self.healthMonitorInterface)
        layout.setSpacing(16)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # 标题和状态信息
        titleLayout = QHBoxLayout()
        titleLabel = StrongBodyLabel("血条实时监控")
        titleLabel.setStyleSheet("font-size: 18px; font-weight: bold;")
        
        self.monitor_status_label = BodyLabel("准备就绪")
        self.monitor_status_label.setStyleSheet("color: #3498db;")
        titleLayout.addWidget(titleLabel)
        titleLayout.addStretch(1)
        titleLayout.addWidget(self.monitor_status_label)
        
        # 控制按钮区域
        controlLayout = QHBoxLayout()
        
        startMonitorBtn = PrimaryPushButton("开始监控")
        startMonitorBtn.setIcon(FIF.PLAY)
        startMonitorBtn.setMinimumWidth(120)
        
        stopMonitorBtn = PushButton("停止监控")
        stopMonitorBtn.setIcon(FIF.CLOSE)
        stopMonitorBtn.setMinimumWidth(120)
        
        # 新增：设置血条颜色按钮
        setColorBtn = PushButton("设置血条颜色")
        setColorBtn.setIcon(FIF.PALETTE) # 使用 PALETTE 图标替代 COLOR
        setColorBtn.setMinimumWidth(120)
        
        # 新增：统一设置血条颜色按钮
        setAllColorsBtn = PushButton("统一设置颜色")
        setAllColorsBtn.setIcon(FIF.BRUSH) # 使用 BRUSH 图标
        setAllColorsBtn.setMinimumWidth(120)
        
        # 连接按钮事件
        startMonitorBtn.clicked.connect(self.health_monitor.start_monitoring)
        stopMonitorBtn.clicked.connect(self.health_monitor.stop_monitoring)
        setColorBtn.clicked.connect(self.setTeammateHealthBarColor)  # 连接到单个设置方法
        setAllColorsBtn.clicked.connect(self.handleSetAllTeammatesColor) # 连接到统一设置方法
        
        controlLayout.addWidget(startMonitorBtn)
        controlLayout.addWidget(stopMonitorBtn)
        controlLayout.addWidget(setColorBtn)  # 添加单个设置按钮
        controlLayout.addWidget(setAllColorsBtn) # 添加统一设置按钮
        controlLayout.addStretch(1)
        
        # 血条展示区域
        self.health_bars_frame = QFrame()
        self.health_bars_frame.setObjectName("cardFrame")
        self.health_bars_frame.setStyleSheet("QFrame#cardFrame { background-color: rgba(240, 240, 240, 0.7); border-radius: 8px; padding: 10px; }")
        healthBarsLayout = QVBoxLayout(self.health_bars_frame)
        healthBarsLayout.setSpacing(12)
        healthBarsLayout.setContentsMargins(15, 15, 15, 15)
        
        # 初始化血条UI
        self.init_health_bars_ui()
        
        # 添加到监控布局
        layout.addLayout(titleLayout)
        layout.addLayout(controlLayout)
        layout.addWidget(self.health_bars_frame, 1)  # 将监控卡片设置为可伸展，占用更多空间
        
        # 设置卡片
        settingsCard = HeaderCardWidget(self.healthMonitorInterface)
        settingsCard.setTitle("血条监控设置")
        
        settingsLayout = QVBoxLayout()
        settingsLayout.setSpacing(12)
        
        # 基本设置组
        paramsGroup = QGroupBox("监控参数", self.healthMonitorInterface)
        paramsGroupLayout = QVBoxLayout()
        
        # 阈值设置
        thresholdLayout = QHBoxLayout()
        thresholdLabel = BodyLabel(f"血条阈值: {int(self.health_monitor.health_threshold)}%")
        thresholdSlider = Slider(Qt.Horizontal)
        thresholdSlider.setRange(0, 100)
        thresholdSlider.setValue(int(self.health_monitor.health_threshold))
        thresholdLayout.addWidget(thresholdLabel)
        thresholdLayout.addWidget(thresholdSlider)
        thresholdSlider.valueChanged.connect(lambda v: self.update_health_threshold(v, thresholdLabel))
        
        # 采样率设置
        samplingLayout = QHBoxLayout()
        samplingLabel = BodyLabel("采样率 (fps):")
        samplingSpinBox = SpinBox()
        samplingSpinBox.setRange(1, 60)
        samplingSpinBox.setValue(10)
        samplingLayout.addWidget(samplingLabel)
        samplingLayout.addWidget(samplingSpinBox)
        
        # 添加所有参数设置
        paramsGroupLayout.addLayout(thresholdLayout)
        paramsGroupLayout.addLayout(samplingLayout)
        
        # 自动点击低血量队友功能开关
        autoClickLayout = QHBoxLayout()
        autoClickLabel = BodyLabel("自动点击低血量队友:")
        self.autoClickSwitch = SwitchButton()
        # 从 HealthMonitor 加载初始状态
        if hasattr(self, 'health_monitor') and hasattr(self.health_monitor, 'auto_select_enabled'):
            self.autoClickSwitch.setChecked(self.health_monitor.auto_select_enabled)
        else:
            self.autoClickSwitch.setChecked(False) # 默认关闭
        
        # 新增：职业优先级下拉框
        priorityLabel = BodyLabel("优先职业:")
        self.priorityComboBox = ComboBox()
        self.priorityComboBox.setFixedWidth(120)
        # 加载所有职业选项
        self.load_profession_options()
        # 设置当前选中值
        if hasattr(self, 'health_monitor') and hasattr(self.health_monitor, 'priority_profession'):
            priority_index = self.priorityComboBox.findText(self.health_monitor.priority_profession)
            if priority_index >= 0:
                self.priorityComboBox.setCurrentIndex(priority_index)
        
        # 连接信号
        self.autoClickSwitch.checkedChanged.connect(self.toggle_auto_click_low_health)
        self.priorityComboBox.currentTextChanged.connect(self.update_priority_profession)
        
        autoClickLayout.addWidget(autoClickLabel)
        autoClickLayout.addWidget(self.autoClickSwitch)
        autoClickLayout.addSpacing(20)  # 增加间距
        autoClickLayout.addWidget(priorityLabel)
        autoClickLayout.addWidget(self.priorityComboBox)
        autoClickLayout.addStretch(1)
        paramsGroupLayout.addLayout(autoClickLayout) # 添加到参数组布局
        
        paramsGroup.setLayout(paramsGroupLayout)
        
        # 添加到主设置布局
        settingsLayout.addWidget(paramsGroup)
        settingsCardWidget = QWidget()
        settingsCardWidget.setLayout(settingsLayout)
        settingsCard.viewLayout.addWidget(settingsCardWidget)
        
        # 添加卡片到主布局，但设置较小的高度比例
        layout.addWidget(settingsCard)
        
        # 更新采样率设置
        samplingSpinBox.valueChanged.connect(self.update_sampling_rate)
    
    def init_health_bars_ui(self):
        """初始化血条UI显示"""
        if not self.health_bars_frame:
            return

        # 清除现有布局中的所有组件
        current_layout = self.health_bars_frame.layout()
        if current_layout is not None:
            while current_layout.count():
                item = current_layout.takeAt(0)
                widget = item.widget()
                if widget:
                    widget.deleteLater()
        else:
            # 如果布局不存在，则创建一个新的
            new_layout = QVBoxLayout(self.health_bars_frame)
            new_layout.setSpacing(12)
            new_layout.setContentsMargins(15, 15, 15, 15)
            self.health_bars_frame.setLayout(new_layout) # 设置新布局
        
        # --- 新增：按血条 y1, x1 坐标对队员进行排序 ---
        sorted_members = sorted(self.team.members, key=lambda m: (m.y1, m.x1))
        
        # 添加队友信息卡片
        for i, member in enumerate(sorted_members): # 使用排序后的列表
            self.add_health_bar_card(i, member.name, member.profession)
            
        # 如果没有队友，显示提示信息
        if not self.team.members and self.health_bars_frame.layout() is not None: # 检查原始列表判断是否有队友
            noMemberLabel = StrongBodyLabel("没有队友信息。请在队员识别页面添加队友。")
            noMemberLabel.setAlignment(Qt.AlignCenter)
            self.health_bars_frame.layout().addWidget(noMemberLabel)
        
        # 添加：强制更新框架，确保UI刷新
        self.health_bars_frame.update()
    
    def add_health_bar_card(self, index, name, profession):
        """添加血条卡片
        
        参数:
            index: 队友索引
            name: 队友名称
            profession: 队友职业
        """
        # 创建水平布局，每一行一个队员
        memberCard = QFrame()
        memberCard.setObjectName(f"member_card_{index}")
        memberCard.setFixedHeight(60)  # 设置固定高度
        memberCard.setStyleSheet("background-color: transparent;")
        memberLayout = QHBoxLayout(memberCard)
        memberLayout.setContentsMargins(5, 0, 5, 0)
        memberLayout.setSpacing(10)
        
        # 队员编号和名称 - 使用实际名称
        nameLabel = StrongBodyLabel(name)
        nameLabel.setObjectName(f"name_label_{index}")
        nameLabel.setStyleSheet("font-size: 14px; font-weight: bold;")
        nameLabel.setFixedWidth(80)
        
        # 修改：直接显示识别到的职业名称
        roleLabel = BodyLabel(str(profession)) # 确保是字符串
        roleLabel.setStyleSheet("color: #666; font-size: 12px;")
        roleLabel.setFixedWidth(60)
        roleLabel.setToolTip(str(profession)) # 添加悬浮提示显示完整职业名
        
        # 血条容器
        healthBarContainer = QFrame()
        healthBarContainer.setFixedHeight(25)
        healthBarContainer.setStyleSheet("background-color: #333; border-radius: 5px;")
        # --- 添加：设置最大宽度 --- 
        MAX_WIDTH = 300  # 与 update_health_display 中保持一致
        healthBarContainer.setMaximumWidth(MAX_WIDTH) 
        # --- 结束添加 ---
        healthBarContainerLayout = QHBoxLayout(healthBarContainer)
        healthBarContainerLayout.setContentsMargins(2, 2, 2, 2)
        healthBarContainerLayout.setSpacing(0)
        
        # 血条
        healthBar = QFrame()
        healthBar.setObjectName(f"health_bar_{index}")
        healthBar.setFixedHeight(21)
        
        # 根据索引设置不同颜色
        color = "#2ecc71"  # 绿色 (默认，表示90%)
        if index == 1:
            color = "#2ecc71"  # 绿色 (70%)
        elif index == 2:
            color = "#f39c12"  # 黄色 (50%)
        elif index == 3:
            color = "#e74c3c"  # 红色 (30%)
        elif index == 4:
            color = "#e74c3c"  # 红色 (10%)
        
        # 设置默认百分比
        default_percentage = 90
        if index == 1:
            default_percentage = 70
        elif index == 2:
            default_percentage = 50
        elif index == 3:
            default_percentage = 30
        elif index == 4:
            default_percentage = 10
        
        # 设置血条缩放因子和最大宽度
        SCALE_FACTOR = 3
        MAX_WIDTH = 300  # 血条最大宽度
        
        # 计算血条宽度
        bar_width = min(int(default_percentage * SCALE_FACTOR), MAX_WIDTH)
        print(f"队员{index+1} 初始血条宽度: {bar_width}px (血量: {default_percentage}%)")
        
        healthBar.setStyleSheet(f"background-color: {color}; border-radius: 3px;")
        healthBar.setFixedWidth(bar_width)  # 使用计算的宽度
        
        healthBarContainerLayout.addWidget(healthBar)
        healthBarContainerLayout.addStretch(1)
        
        # 血量百分比
        valueLabel = StrongBodyLabel(f"{default_percentage}%")
        valueLabel.setObjectName(f"value_label_{index}")
        valueLabel.setStyleSheet(f"color: {color}; font-weight: bold; font-size: 15px;")
        valueLabel.setAlignment(Qt.AlignCenter)
        valueLabel.setFixedWidth(60)
        
        # 添加调试标签 - 开发期间使用，显示实际内部存储的血量
        debugLabel = QLabel(f"dbg:ok")
        debugLabel.setObjectName(f"debug_label_{index}")
        debugLabel.setStyleSheet("color: #999; font-size: 8px;")
        debugLabel.setFixedWidth(50)
        
        # 添加到卡片布局
        memberLayout.addWidget(nameLabel)
        memberLayout.addWidget(roleLabel)
        memberLayout.addWidget(healthBarContainer)
        memberLayout.addWidget(valueLabel)
        memberLayout.addWidget(debugLabel)  # 添加调试标签
        
        # 添加到主布局
        self.health_bars_frame.layout().addWidget(memberCard)
        
        # 添加分隔线（除了最后一个）
        if index < len(self.team.members) - 1:
            separator = QFrame()
            separator.setFrameShape(QFrame.HLine)
            separator.setFrameShadow(QFrame.Sunken)
            separator.setStyleSheet("background-color: #e0e0e0;")
            separator.setFixedHeight(1)
            self.health_bars_frame.layout().addWidget(separator)
    
    def update_sampling_rate(self, value):
        """更新监控采样率
        
        参数:
            value: 采样率值（fps）
        """
        if hasattr(self, 'health_monitor'):
            # 转换为更新间隔（秒）
            interval = 1.0 / value if value > 0 else 0.1
            self.health_monitor.update_interval = interval
            self.update_monitor_status(f"采样率已更新: {value} fps (更新间隔: {interval:.2f}秒)")
    
    def show_hotkey_settings(self):
        """显示快捷键设置对话框"""
        dialog = HotkeySettingsMessageBox(self.health_monitor, self)
        dialog.exec()
    
    def show_error_message(self, message):
        """显示错误消息
        
        参数:
            message: 错误消息
        """
        InfoBar.error(
            title='错误',
            content=message,
            orient=Qt.Horizontal,
            isClosable=True,
            position=InfoBarPosition.TOP,
            duration=3000,
            parent=self
        )
    
    def set_auto_select(self, enabled):
        """设置自动选择功能
        
        参数:
            enabled: 是否启用
        """
        if hasattr(self, 'health_monitor'):
            self.health_monitor.auto_select_enabled = enabled
            self.health_monitor.save_auto_select_config()
            status = "启用" if enabled else "禁用"
            self.update_monitor_status(f"自动选择功能已{status}")

    def initAssistInterface(self):
        """初始化辅助功能界面"""
        layout = QVBoxLayout(self.assistInterface)
        layout.setSpacing(16)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # 左右布局，左侧为主要功能，右侧为次要功能
        mainLayout = QHBoxLayout()
        mainLayout.setSpacing(16)
        
        # 左侧布局 - 现在只包含快捷键设置
        leftLayout = QVBoxLayout()
        leftLayout.setSpacing(16)
        
        # 快捷键卡片
        hotkeyCard = HeaderCardWidget(self.assistInterface)
        hotkeyCard.setTitle("快捷键设置")
        
        hotkeyLayout = QVBoxLayout()
        hotkeyLayout.setSpacing(12)
        
        # 提示信息
        hotkey_info = BodyLabel("设置全局快捷键用于快速操作。点击\"记录\"按钮后，按下想要设置的键。")
        hotkey_info.setWordWrap(True)
        
        # 快捷键表格
        hotkeyGridLayout = QGridLayout()
        hotkeyGridLayout.setSpacing(12)
        
        # 开始监控
        startMonitorLabel = BodyLabel('开始监控:')
        startMonitorEdit = LineEdit()
        startMonitorEdit.setReadOnly(True)
        startMonitorEdit.setText(self.health_monitor.start_monitoring_hotkey)
        startMonitorRecordBtn = PushButton('记录')
        
        # 停止监控
        stopMonitorLabel = BodyLabel('停止监控:')
        stopMonitorEdit = LineEdit()
        stopMonitorEdit.setReadOnly(True)
        stopMonitorEdit.setText(self.health_monitor.stop_monitoring_hotkey)
        stopMonitorRecordBtn = PushButton('记录')
        
        # 绑定"记录"按钮事件，使用事件过滤器方式
        startMonitorRecordBtn.clicked.connect(lambda: self.install_hotkey_event_filter(startMonitorEdit, stopMonitorEdit, 'start'))
        stopMonitorRecordBtn.clicked.connect(lambda: self.install_hotkey_event_filter(stopMonitorEdit, startMonitorEdit, 'stop'))
        
        # 添加到网格
        hotkeyGridLayout.addWidget(startMonitorLabel, 0, 0)
        hotkeyGridLayout.addWidget(startMonitorEdit, 0, 1)
        hotkeyGridLayout.addWidget(startMonitorRecordBtn, 0, 2)
        
        hotkeyGridLayout.addWidget(stopMonitorLabel, 1, 0)
        hotkeyGridLayout.addWidget(stopMonitorEdit, 1, 1)
        hotkeyGridLayout.addWidget(stopMonitorRecordBtn, 1, 2)
        
        # 添加所有组件到快捷键卡片
        hotkeyLayout.addWidget(hotkey_info)
        hotkeyLayout.addLayout(hotkeyGridLayout)
        # 增加状态信息标签
        self.hotkeyStatusLabel = BodyLabel('')
        hotkeyLayout.addWidget(self.hotkeyStatusLabel)
        hotkeyCardWidget = QWidget()
        hotkeyCardWidget.setLayout(hotkeyLayout)
        hotkeyCard.viewLayout.addWidget(hotkeyCardWidget)
        
        # 添加快捷键卡片到左侧布局
        leftLayout.addWidget(hotkeyCard)
        leftLayout.addStretch(1)
        
        # 右侧布局 - 保持不变
        rightLayout = QVBoxLayout()
        rightLayout.setSpacing(16)
        
        # 数据导出卡片
        exportCard = HeaderCardWidget(self.assistInterface)
        exportCard.setTitle("数据导出")
        
        exportLayout = QVBoxLayout()
        exportLayout.setSpacing(12)
        
        # 导出按钮
        exportBtnsLayout = QHBoxLayout()
        
        exportCsvBtn = PushButton("导出CSV")
        exportCsvBtn.setIcon(FIF.DOWNLOAD)
        
        exportJsonBtn = PushButton("导出JSON")
        exportJsonBtn.setIcon(FIF.DOWNLOAD)
        
        exportBtnsLayout.addWidget(exportCsvBtn)
        exportBtnsLayout.addWidget(exportJsonBtn)
        exportBtnsLayout.addStretch(1)
        
        # 自动导出开关
        autoExportLayout = QHBoxLayout()
        autoExportLabel = BodyLabel("自动导出:")
        autoExportSwitch = SwitchButton()
        
        autoExportLayout.addWidget(autoExportLabel)
        autoExportLayout.addWidget(autoExportSwitch)
        autoExportLayout.addStretch(1)
        
        # 导出路径
        exportPathLayout = QHBoxLayout()
        exportPathLabel = BodyLabel("导出路径:")
        exportPathEdit = LineEdit()
        exportPathEdit.setText(os.path.join(os.path.expanduser("~"), "Documents"))
        exportPathBtn = PushButton("浏览")
        exportPathBtn.setIcon(FIF.FOLDER)
        
        exportPathLayout.addWidget(exportPathLabel)
        exportPathLayout.addWidget(exportPathEdit)
        exportPathLayout.addWidget(exportPathBtn)
        
        # 添加所有组件到导出卡片
        exportLayout.addLayout(exportBtnsLayout)
        exportLayout.addLayout(autoExportLayout)
        exportLayout.addLayout(exportPathLayout)
        exportCardWidget = QWidget()
        exportCardWidget.setLayout(exportLayout)
        exportCard.viewLayout.addWidget(exportCardWidget)
        
        # 添加导出卡片到右侧布局
        rightLayout.addWidget(exportCard)
        rightLayout.addStretch(1)
        
        # 添加左右布局到主布局
        mainLayout.addLayout(leftLayout, 2)
        mainLayout.addLayout(rightLayout, 1)
        
        # 添加主布局到辅助功能界面
        layout.addLayout(mainLayout)

    def initSettingsInterface(self):
        """初始化设置界面"""
        layout = QVBoxLayout(self.settingsInterface)
        layout.setSpacing(16)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # 基本设置卡片
        basicCard = HeaderCardWidget(self.settingsInterface)
        basicCard.setTitle("基本设置")
        
        basicLayout = QVBoxLayout()
        basicLayout.setSpacing(16)
        
        # 主题设置
        themeLayout = QHBoxLayout()
        themeLabel = BodyLabel("主题:")
        themeCombo = ComboBox()
        themeCombo.addItems(["跟随系统", "亮色模式", "暗色模式"])
        themeLayout.addWidget(themeLabel)
        themeLayout.addWidget(themeCombo)
        themeLayout.addStretch(1)
        
        # 语言设置
        languageLayout = QHBoxLayout()
        languageLabel = BodyLabel("语言:")
        languageCombo = ComboBox()
        languageCombo.addItems(["简体中文", "English"])
        languageLayout.addWidget(languageLabel)
        languageLayout.addWidget(languageCombo)
        languageLayout.addStretch(1)
        
        # 自动启动
        autoStartLayout = QHBoxLayout()
        autoStartLabel = BodyLabel("开机自动启动:")
        autoStartSwitch = SwitchButton()
        autoStartLayout.addWidget(autoStartLabel)
        autoStartLayout.addWidget(autoStartSwitch)
        autoStartLayout.addStretch(1)
        
        # 添加所有组件到基本设置卡片
        basicLayout.addLayout(themeLayout)
        basicLayout.addLayout(languageLayout)
        basicLayout.addLayout(autoStartLayout)
        basicCardWidget = QWidget()
        basicCardWidget.setLayout(basicLayout)
        basicCard.viewLayout.addWidget(basicCardWidget)
        
        # 高级设置卡片
        advancedCard = HeaderCardWidget(self.settingsInterface)
        advancedCard.setTitle("高级设置")
        
        advancedLayout = QVBoxLayout()
        advancedLayout.setSpacing(16)
        
        # 缓存设置
        cacheLayout = QHBoxLayout()
        cacheLabel = BodyLabel("缓存大小:")
        cacheSizeLabel = BodyLabel("23.5 MB")
        clearCacheBtn = PushButton("清除缓存")
        clearCacheBtn.setIcon(FIF.DELETE)
        
        cacheLayout.addWidget(cacheLabel)
        cacheLayout.addWidget(cacheSizeLabel)
        cacheLayout.addStretch(1)
        cacheLayout.addWidget(clearCacheBtn)
        
        # AI模型设置
        modelLayout = QHBoxLayout()
        modelLabel = BodyLabel("AI模型:")
        modelCombo = ComboBox()
        modelCombo.addItems(['标准模型', '轻量级模型', '高精度模型', '自娱自乐模型', '作者没钱加模型'])
        modelLayout.addWidget(modelLabel)
        modelLayout.addWidget(modelCombo)
        modelLayout.addStretch(1)
        
        # GPU加速
        gpuLayout = QHBoxLayout()
        gpuLabel = BodyLabel("GPU加速:")
        gpuSwitch = SwitchButton()
        gpuSwitch.setChecked(True)
        gpuLayout.addWidget(gpuLabel)
        gpuLayout.addWidget(gpuSwitch)
        gpuLayout.addStretch(1)
        
        # 添加所有组件到高级设置卡片
        advancedLayout.addLayout(cacheLayout)
        advancedLayout.addLayout(modelLayout)
        advancedLayout.addLayout(gpuLayout)
        advancedCardWidget = QWidget()
        advancedCardWidget.setLayout(advancedLayout)
        advancedCard.viewLayout.addWidget(advancedCardWidget)
        
        # 关于卡片
        aboutCard = HeaderCardWidget(self.settingsInterface)
        aboutCard.setTitle("关于")
        
        aboutLayout = QVBoxLayout()
        aboutLayout.setSpacing(16)
        
        # 版本信息
        versionLayout = QHBoxLayout()
        versionLabel = BodyLabel("版本:")
        versionValueLabel = BodyLabel("VitalSync 2.0.0")
        versionLayout.addWidget(versionLabel)
        versionLayout.addWidget(versionValueLabel)
        versionLayout.addStretch(1)
        
        # 关于信息
        aboutInfoLabel = BodyLabel("VitalSync 是一款专为游戏设计的队员血条识别与监控软件，支持多种游戏和场景。")
        aboutInfoLabel.setWordWrap(True)
        
        # 控制按钮
        controlLayout = QHBoxLayout()
        updateBtn = PushButton("检查更新")
        updateBtn.setIcon(FIF.UPDATE)
        
        githubBtn = PushButton("GitHub项目")
        githubBtn.setIcon(FIF.LINK)
        # 连接点击事件
        githubBtn.clicked.connect(self.openGitHubProject)
        
        controlLayout.addWidget(updateBtn)
        controlLayout.addWidget(githubBtn)
        controlLayout.addStretch(1)
        
        # 添加所有组件到关于卡片
        aboutLayout.addLayout(versionLayout)
        aboutLayout.addWidget(aboutInfoLabel)
        aboutLayout.addLayout(controlLayout)
        aboutCardWidget = QWidget()
        aboutCardWidget.setLayout(aboutLayout)
        aboutCard.viewLayout.addWidget(aboutCardWidget)
        
        # 添加所有卡片到设置界面
        layout.addWidget(basicCard)
        layout.addWidget(advancedCard)
        layout.addWidget(aboutCard)
        layout.addStretch(1)

    def openGitHubProject(self):
        """打开GitHub项目页面"""
        url = QUrl("https://github.com/yinduandafeimao/VitalSync-Pulse")
        QDesktopServices.openUrl(url)
        
        # 显示提示信息
        InfoBar.success(
            title='已打开链接',
            content='已在浏览器中打开GitHub项目页面',
            orient=Qt.Horizontal,
            isClosable=True,
            position=InfoBarPosition.TOP,
            duration=2000,
            parent=self
        )

    def addProfessionIcon(self):
        """添加新的职业图标"""
        # 检查profession_icons文件夹是否存在
        profession_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "profession_icons")
        if not os.path.exists(profession_path):
            os.makedirs(profession_path)  # 创建文件夹如果不存在
            
        # 打开文件选择对话框
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "选择职业图标",
            "",
            "图片文件 (*.png *.jpg *.jpeg)"
        )
        
        if not file_path:
            return
        
        # 获取文件名
        file_name_without_ext = os.path.splitext(os.path.basename(file_path))[0]
        
        # 使用自定义无边框对话框获取职业名称
        input_dialog = TextInputMessageBox(
            title='输入职业名称',
            label_text='请输入该职业图标的名称:',
            default_text=file_name_without_ext,
            placeholder_text='例如：奶妈、坦克、输出',
            parent=self
        )
        
        if not input_dialog.exec():
            return
        
        icon_name = input_dialog.get_text()
        if not icon_name:
            InfoBar.warning(
                title='输入无效',
                content='职业名称不能为空。',
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=2000,
                parent=self
            )
            return
        
        # 构造目标路径
        target_path = os.path.join(profession_path, icon_name + os.path.splitext(file_path)[1])
        
        # 检查是否已存在同名文件
        if os.path.exists(target_path):
            confirm_dialog = ConfirmMessageBox(
                "文件已存在",
                f"职业 '{icon_name}' 已存在，是否覆盖?",
                self
            )
            
            if not confirm_dialog.exec():
                return
        
        try:
            # 复制文件
            import shutil
            shutil.copy2(file_path, target_path)
            
            # 显示成功消息
            InfoBar.success(
                title='添加成功',
                content=f'职业图标 {icon_name} 已添加',
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=2000,
                parent=self
            )
            
            # 更新图标数量显示
            self.updateIconCount()
        except Exception as e:
            # 显示错误消息
            InfoBar.error(
                title='添加失败',
                content=str(e),
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=3000,
                parent=self
            )
    
    def updateIconCount(self):
        """更新职业图标数量显示"""
        # 重新计算图标数量
        profession_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "profession_icons")
        icon_count = len([f for f in os.listdir(profession_path) if f.endswith(('.png', '.jpg', '.jpeg'))])
        
        # 查找信息标签并更新
        for i in range(self.iconCardWidget.layout().count()):
            item = self.iconCardWidget.layout().itemAt(i)
            if item.widget() and isinstance(item.widget(), BodyLabel) and "当前已加载" in item.widget().text():
                item.widget().setText(f'当前已加载 {icon_count} 个职业图标')
                break

    def init_recognition(self):
        """初始化识别模块"""
        try:
            if self.recognition is None:
                from teammate_recognition import TeammateRecognition
                self.recognition = TeammateRecognition()
                InfoBar.success(
                    title='OCR模型加载成功',
                    content='队友识别功能已准备就绪',
                    orient=Qt.Horizontal,
                    isClosable=True,
                    position=InfoBarPosition.TOP,
                    duration=2000,
                    parent=self
                )
            return True
        except Exception as e:
            InfoBar.error(
                title='OCR初始化失败',
                content=f'错误: {str(e)}',
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=3000,
                parent=self
            )
            return False

    def addTeammate(self):
        """添加队友"""
        print("\n添加新队友:")
        
        # 使用自定义的MessageBoxBase子类
        dialog = AddTeammateMessageBox(self)
        
        if dialog.exec():
            name, profession = dialog.get_teammate_info()
            
            # 使用Team类添加队友
            new_member = self.team.add_member(name, profession)
            
            # 使用全局默认颜色设置(如果有的话)
            if self.default_hp_color_lower is not None and self.default_hp_color_upper is not None:
                import numpy as np
                new_member.hp_color_lower = np.copy(self.default_hp_color_lower)
                new_member.hp_color_upper = np.copy(self.default_hp_color_upper)
                new_member.save_config()  # 保存颜色设置到队员配置文件
            
            # 更新健康监控
            self.health_monitor.team = self.team
            self.init_health_bars_ui()
            
            # 提示设置血条位置 - 使用自定义确认对话框
            confirm_dialog = ConfirmMessageBox(
                "设置血条位置",
                f"是否立即为 {name} 设置血条位置？",
                self
            )
            
            if confirm_dialog.exec():
                # 使用选择框设置血条位置
                self.set_health_bar_position(new_member)
            
            InfoBar.success(
                title='添加成功',
                content=f'队友 {name} ({profession}) 已添加',
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                parent=self
            )

class HotkeySettingsMessageBox(MessageBoxBase):
    """ Custom message box for hotkey settings """

    def __init__(self, health_monitor, parent=None):
        super().__init__(parent)
        self.titleLabel = SubtitleLabel('监控快捷键设置', self)
        self.health_monitor = health_monitor
        self.parent_window = parent
        
        # 当前快捷键展示
        self.infoLabel = BodyLabel(f"当前快捷键设置:\n开始监控: {health_monitor.start_monitoring_hotkey}\n停止监控: {health_monitor.stop_monitoring_hotkey}")
        self.infoLabel.setWordWrap(True)
        
        # 设置表单
        form_widget = QWidget()
        form_layout = QGridLayout(form_widget)
        form_layout.setSpacing(10)
        
        # 开始监控输入
        self.start_label = BodyLabel("开始监控键:")
        self.start_input = LineEdit()
        self.start_input.setText(health_monitor.start_monitoring_hotkey)
        self.start_input.setPlaceholderText("按下快捷键组合")
        
        # 停止监控输入
        self.stop_label = BodyLabel("停止监控键:")
        self.stop_input = LineEdit()
        self.stop_input.setText(health_monitor.stop_monitoring_hotkey)
        self.stop_input.setPlaceholderText("按下快捷键组合")
        
        # 错误提示标签
        self.error_label = CaptionLabel("")
        self.error_label.setTextColor("#cf1010", QColor(255, 28, 32))
        self.error_label.hide()
        
        # 增加记录按钮以记录实际按键
        self.start_record = PushButton("记录")
        self.start_record.clicked.connect(lambda: self.record_hotkey('start'))
        
        self.stop_record = PushButton("记录")
        self.stop_record.clicked.connect(lambda: self.record_hotkey('stop'))
        
        # 添加到布局
        form_layout.addWidget(self.start_label, 0, 0)
        form_layout.addWidget(self.start_input, 0, 1)
        form_layout.addWidget(self.start_record, 0, 2)
        
        form_layout.addWidget(self.stop_label, 1, 0)
        form_layout.addWidget(self.stop_input, 1, 1)
        form_layout.addWidget(self.stop_record, 1, 2)
        
        # 将所有控件添加到视图布局
        self.viewLayout.addWidget(self.titleLabel)
        self.viewLayout.addWidget(self.infoLabel)
        self.viewLayout.addWidget(form_widget)
        self.viewLayout.addWidget(self.error_label)
        
        # 设置按钮文本
        self.yesButton.setText('保存')
        self.cancelButton.setText('取消')
        
        # 设置最小宽度
        self.widget.setMinimumWidth(400)
    
    def record_hotkey(self, which):
        """弹出对话框录入快捷键"""
        from PyQt5.QtGui import QKeySequence
        
        # 创建录入对话框
        dialog = MessageBoxBase(self)
        dialog.titleLabel = SubtitleLabel('录入快捷键', dialog)
        
        # 说明标签
        guide_label = BodyLabel('请按下新的快捷键组合（如 Ctrl+Alt+S）')
        key_label = BodyLabel('等待按键...')
        
        # 添加到视图布局
        dialog.viewLayout.addWidget(dialog.titleLabel)
        dialog.viewLayout.addWidget(guide_label)
        dialog.viewLayout.addWidget(key_label)
        
        # 设置按钮文本，初始时禁用确定按钮
        dialog.yesButton.setText('确定')
        dialog.yesButton.setEnabled(False)
        dialog.cancelButton.setText('取消')
        
        # 存储按键
        key_seq = {'text': ''}
        
        # 重写keyPressEvent处理按键
        def keyPressEvent(event):
            # 保存原始方法
            original_keyPressEvent = dialog.keyPressEvent
            
            key_text = ''
            modifiers = event.modifiers()
            if modifiers & Qt.ControlModifier:
                key_text += 'ctrl+'
            if modifiers & Qt.AltModifier:
                key_text += 'alt+'
            if modifiers & Qt.ShiftModifier:
                key_text += 'shift+'
            key = event.key()
            if key in (Qt.Key_Control, Qt.Key_Alt, Qt.Key_Shift):
                # 恢复原始方法并调用它
                dialog.keyPressEvent = original_keyPressEvent
                return original_keyPressEvent(event)
            key_name = QKeySequence(key).toString().lower()
            key_text += key_name
            key_seq['text'] = key_text
            key_label.setText(f'已录入: {key_text}')
            dialog.yesButton.setEnabled(True)
            
            # 恢复原始方法
            dialog.keyPressEvent = original_keyPressEvent
        
        # 保存原始方法
        original_method = dialog.keyPressEvent
        # 替换方法
        dialog.keyPressEvent = keyPressEvent
        
        # 显示对话框
        if dialog.exec():
            if key_seq['text']:
                if which == 'start':
                    self.start_input.setText(key_seq['text'])
                else:
                    self.stop_input.setText(key_seq['text'])
    
    def validate(self):
        """验证输入是否有效"""
        start_key = self.start_input.text()
        stop_key = self.stop_input.text()
        
        # 检查输入是否有效
        if not start_key or not stop_key:
            self.error_label.setText("快捷键不能为空")
            self.error_label.show()
            return False
            
        if start_key == stop_key:
            self.error_label.setText("开始和停止快捷键不能相同")
            self.error_label.show()
            return False
        
        # 尝试设置新的快捷键
        success = self.health_monitor.set_hotkeys(start_key, stop_key)
        
        if not success:
            self.error_label.setText("设置快捷键失败，请重试")
            self.error_label.show()
            return False
            
        return True

class TeammateSelectionMessageBox(MessageBoxBase):
    """ Custom message box for teammate selection """

    def __init__(self, title, team_members, parent=None):
        super().__init__(parent)
        self.titleLabel = SubtitleLabel(title, self)
        
        # 添加说明
        self.infoLabel = BodyLabel("请从列表中选择一个队友")
        
        # 创建队友列表
        self.listWidget = QListWidget(self)
        for i, member in enumerate(team_members):
            self.listWidget.addItem(f"{member.name} ({member.profession})")
        
        # 警告标签
        self.warningLabel = CaptionLabel("未选择任何队友")
        self.warningLabel.setTextColor("#cf1010", QColor(255, 28, 32))
        self.warningLabel.hide()  # 默认隐藏
        
        # 添加到视图布局
        self.viewLayout.addWidget(self.titleLabel)
        self.viewLayout.addWidget(self.infoLabel)
        self.viewLayout.addWidget(self.listWidget)
        self.viewLayout.addWidget(self.warningLabel)
        
        # 设置按钮文本
        self.yesButton.setText('选择')
        self.cancelButton.setText('取消')
        
        # 设置最小宽度
        self.widget.setMinimumWidth(350)
        
        # 存储队友列表
        self.team_members = team_members
        self.selected_index = -1
        
        # 连接列表点击事件
        self.listWidget.itemClicked.connect(self.on_item_clicked)
    
    def on_item_clicked(self, item):
        """列表项被点击时更新选择索引"""
        self.selected_index = self.listWidget.row(item)
        self.warningLabel.hide()  # 隐藏警告
    
    def get_selected_member(self):
        """获取选中的队友"""
        if self.selected_index >= 0 and self.selected_index < len(self.team_members):
            return self.team_members[self.selected_index]
        return None
        
    def validate(self):
        """验证是否选择了队友"""
        if self.selected_index >= 0:
            return True
        else:
            self.warningLabel.show()  # 显示警告
            return False

class UnifiedColorPickerMessageBox(MessageBoxBase):
    """ Custom message box for unified color picking """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.titleLabel = SubtitleLabel('统一设置所有队友的血条颜色', self)
        
        # 添加操作指南
        self.guideLabel = BodyLabel(
            '1. 将鼠标移动到游戏中任意一个队友的血条上\n'
            '2. 选择血条最具代表性的颜色位置\n'
            '3. 按下空格键获取颜色，此颜色将应用于所有队友\n'
            '4. 按ESC键取消操作'
        )
        self.guideLabel.setWordWrap(True)
        
        # 状态标签
        self.statusLabel = CaptionLabel("状态：等待获取颜色...")
        self.statusLabel.setTextColor("#1e88e5", QColor(30, 136, 229))
        
        # 预览区域
        previewLayout = QHBoxLayout()
        previewLabel = BodyLabel('颜色预览：')
        self.colorPreview = QFrame()
        self.colorPreview.setFixedSize(50, 20)
        self.colorPreview.setFrameShape(QFrame.Box)
        previewLayout.addWidget(previewLabel)
        previewLayout.addWidget(self.colorPreview)
        previewWidget = QWidget()
        previewWidget.setLayout(previewLayout)
        
        # 添加到视图布局
        self.viewLayout.addWidget(self.titleLabel)
        self.viewLayout.addWidget(self.guideLabel)
        self.viewLayout.addWidget(self.statusLabel)
        self.viewLayout.addWidget(previewWidget)
        
        # 设置按钮文本
        self.yesButton.setText('确定')
        self.cancelButton.setText('取消')
        
        # 设置最小宽度
        self.widget.setMinimumWidth(350)
        
        # 颜色获取状态和计时器
        self.color_captured = False
        self.key_check_timer = QTimer(self)
        self.key_check_timer.timeout.connect(self.check_keys_and_position)
        self.key_check_timer.start(100)
        
        # 存储获取的颜色值
        self.pixel_color_rgb = None

    def check_keys_and_position(self):
        """检查键盘输入和鼠标位置"""
        import keyboard
        if keyboard.is_pressed('space'):
            if self.color_captured:
                return
            
            self.color_captured = True
            self.key_check_timer.stop()
            
            try:
                import pyautogui
                x, y = pyautogui.position()
                self.pixel_color_rgb = pyautogui.screenshot().getpixel((x, y))[:3]  # 确保是RGB
                
                color_hex = "#{:02x}{:02x}{:02x}".format(
                    self.pixel_color_rgb[0], 
                    self.pixel_color_rgb[1], 
                    self.pixel_color_rgb[2]
                )
                self.colorPreview.setStyleSheet(f"background-color: {color_hex};")
                
                self.statusLabel.setText(f"状态：成功获取颜色！RGB: {self.pixel_color_rgb}")
                self.statusLabel.setTextColor("#2ecc71", QColor(46, 204, 113))
                
                # 延迟关闭对话框
                QTimer.singleShot(2000, lambda: self.accept())
                
            except Exception as e:
                self.statusLabel.setText(f"状态：获取颜色失败 - {str(e)}")
                self.statusLabel.setTextColor("#e74c3c", QColor(231, 76, 60))
                self.color_captured = False
                self.key_check_timer.start()
        
        elif keyboard.is_pressed('esc'):
            if not self.color_captured:
                self.key_check_timer.stop()
                self.reject()

class MainWindow(FluentWindow):
    def __init__(self):
        """初始化主窗口"""
        super().__init__()
        
        # 初始化 pygame mixer
        try:
            pygame.mixer.init()
            pygame.mixer.set_num_channels(16) # 设置足够多的声道
        except pygame.error as e:
            print(f"Pygame mixer 初始化失败: {e}")
            # 可以选择禁用语音功能或显示错误提示
            InfoBar.error(
                title='音频初始化失败',
                content='无法初始化音频播放组件 (pygame.mixer)，语音播报功能将不可用。',
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=5000,
                parent=self
            )
        
        self._icon_capture_show_selection_timer = None
        self._icon_capture_do_grab_timer = None
        self._icon_capture_rect = None # Store the rect between timer calls
        
        # --- 添加缺失的语音参数初始化 ---
        # 初始化语音参数属性 - 使用滑块的默认值
        # 语速: slider 0-10 -> rate -50% to +50% -> + (value*10 - 50) %
        default_rate_value = 5
        self.voice_rate_param = f'+{default_rate_value * 10 - 50}%'
        # 音量: slider 0-100 -> volume -50% to +50% -> + (value - 50) %
        default_volume_value = 80
        self.voice_volume_param = f'+{default_volume_value - 50}%'
        # --- 初始化结束 ---
        
        # 设置窗口标题和大小
        self.setWindowTitle('VitalSync')
        self.resize(1200, 500) # 将高度从 800 调整为 700
        
        # 设置应用强调色 - 使用截图中的青绿色
        setThemeColor(QColor(0, 168, 174))
        
        # 启用亚克力效果
        self.navigationInterface.setAcrylicEnabled(True)
        
        # 初始化队友管理相关属性
        self.team = Team()  # 创建Team实例
        self.selection_box = None # 屏幕选择框
        
        # 初始化全局默认血条颜色
        self.default_hp_color_lower = None  # 默认血条颜色下限
        self.default_hp_color_upper = None  # 默认血条颜色上限
        self.load_default_colors()  # 从配置加载默认颜色设置
        
        # 初始化健康监控相关属性
        self.health_monitor = HealthMonitor(self.team)  # 创建健康监控实例
        # 连接监控信号
        self.health_monitor.signals.update_signal.connect(self.update_health_display)
        self.health_monitor.signals.status_signal.connect(self.update_monitor_status)
        
        # 创建界面
        self.teamRecognitionInterface = QWidget()
        self.teamRecognitionInterface.setObjectName("teamRecognitionInterface")
        
        self.healthMonitorInterface = QWidget()
        self.healthMonitorInterface.setObjectName("healthMonitorInterface")
        
        self.assistInterface = QWidget()
        self.assistInterface.setObjectName("assistInterface")
        
        self.settingsInterface = QWidget()
        self.settingsInterface.setObjectName("settingsInterface")
        
        # 新增：语音设置界面实例
        self.voiceSettingsInterface = QWidget()
        self.voiceSettingsInterface.setObjectName("voiceSettingsInterface")
        
        # 初始化界面
        self.initTeamRecognitionInterface()
        self.initHealthMonitorInterface()
        self.initAssistInterface()
        self.initSettingsInterface()
        self.initVoiceSettingsInterface() # 新增：调用语音设置界面初始化
        
        # 初始化导航
        self.initNavigation()
        
        # --- 加载设置 ---
        self.load_settings() # 在UI初始化后加载设置
        
        # 显示提示信息
        InfoBar.success(
            title='初始化完成',
            content='系统已准备就绪',
            orient=Qt.Horizontal,
            isClosable=True,
            position=InfoBarPosition.TOP,
            duration=2000,
            parent=self
        )
        
        # 在__init__方法末尾添加：
        self.load_teammates()
        
        # 初始化语音队列和工作线程
        self.speech_queue = queue.Queue()
        self.active_speech = {} # 用于跟踪正在播放的语音及其资源
        self.speech_worker_thread = threading.Thread(target=self._speech_worker_loop, daemon=True)
        self.speech_worker_thread.start()
        
        # 设置一个定时器来处理 Pygame 事件和清理
        self.pygame_event_timer = QTimer(self)
        self.pygame_event_timer.timeout.connect(self._process_pygame_events)
        self.pygame_event_timer.start(100) # 每 100ms 检查一次
    
    def initNavigation(self):
        """初始化导航栏"""
        # 添加子界面
        self.addSubInterface(self.teamRecognitionInterface, FIF.PEOPLE, '队员识别')
        self.addSubInterface(self.healthMonitorInterface, FIF.HEART, '血条监控')
        self.addSubInterface(self.assistInterface, FIF.IOT, '辅助功能')
        self.addSubInterface(self.voiceSettingsInterface, FIF.MICROPHONE, '语音设置') # 使用 FIF.MICROPHONE 图标
        
        # 添加底部界面
        self.addSubInterface(
            self.settingsInterface, 
            FIF.SETTING, 
            '系统设置',
            NavigationItemPosition.BOTTOM
        )

    def initTeamRecognitionInterface(self):
        """初始化队员识别界面"""
        layout = QVBoxLayout(self.teamRecognitionInterface)
        layout.setSpacing(24)  # 增加垂直间距
        layout.setContentsMargins(24, 24, 24, 24)  # 增加外边距
        
        # 创建顶部水平布局，包含职业图标管理和队友管理
        topLayout = QHBoxLayout()
        topLayout.setSpacing(24)  # 增加水平间距
        
        # ========== 左侧：职业图标管理 ==========
        iconCard = HeaderCardWidget(self.teamRecognitionInterface)
        iconCard.setTitle("职业图标管理")
        iconCard.setFixedHeight(200)  # 适当减少卡片高度
        iconLayout = QVBoxLayout()
        iconLayout.setSpacing(15)  # 增加垂直间距
        iconLayout.setContentsMargins(0, 10, 0, 10)  # 增加内边距
        
        # 按钮区域 - 也使用网格布局
        btnLayout = QGridLayout()
        btnLayout.setSpacing(15)  # 增加按钮间距
        
        addIconBtn = PrimaryPushButton('添加图标')
        addIconBtn.setIcon(FIF.ADD)
        addIconBtn.setFixedWidth(140)  # 显著增加按钮宽度
        addIconBtn.setMinimumHeight(36)  # 设置最小高度
        
        captureIconBtn = PushButton('截取图标')
        captureIconBtn.setIcon(FIF.CAMERA) # 使用 CAMERA 图标替代 SCREENSHOT
        captureIconBtn.setFixedWidth(140)  # 显著增加按钮宽度
        captureIconBtn.setMinimumHeight(36)  # 设置最小高度
        
        manageIconsBtn = PushButton('管理图标')
        manageIconsBtn.setIcon(FIF.SETTING)
        manageIconsBtn.setFixedWidth(140)  # 显著增加按钮宽度
        manageIconsBtn.setMinimumHeight(36)  # 设置最小高度
        
        # 连接按钮事件
        addIconBtn.clicked.connect(self.addProfessionIcon)
        captureIconBtn.clicked.connect(self.captureScreenIcon)
        manageIconsBtn.clicked.connect(self.loadProfessionIcons)
        
        # 将按钮添加到网格布局
        btnLayout.addWidget(addIconBtn, 0, 0)
        btnLayout.addWidget(captureIconBtn, 0, 1)
        btnLayout.addWidget(manageIconsBtn, 0, 2)
        
        # 显示图标数量信息
        profession_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "profession_icons")
        
        # 检查文件夹是否存在
        if not os.path.exists(profession_path):
            os.makedirs(profession_path)
            icon_count = 0
        else:
            icon_count = len([f for f in os.listdir(profession_path) if f.endswith(('.png', '.jpg', '.jpeg'))])
            
        infoLabel = BodyLabel(f'已加载 {icon_count} 个职业图标')
        infoLabel.setStyleSheet("color: #666; font-size: 13px;")  # 设置样式，使其显示更清晰
        infoLabel.setAlignment(Qt.AlignCenter)  # 居中对齐
        
        # 添加到卡片布局
        iconLayout.addLayout(btnLayout)
        iconLayout.addWidget(infoLabel)
        iconLayout.addStretch(1)  # 添加弹性空间，将内容推向顶部，使标签居中
        iconCardWidget = QWidget()
        iconCardWidget.setLayout(iconLayout)
        iconCard.viewLayout.addWidget(iconCardWidget)
        self.iconCardWidget = iconCardWidget
        
        # ========== 右侧：队友管理 ==========
        teammateCard = HeaderCardWidget(self.teamRecognitionInterface)
        teammateCard.setTitle("队友管理")
        teammateCard.setFixedHeight(200)  # 适当减少卡片高度
        teammateLayout = QVBoxLayout()
        teammateLayout.setSpacing(30)  # 增加垂直间距
        teammateLayout.setContentsMargins(0, 0, 0, 10)  # 顶部margin设为0，整体上移
        
        # 队友管理按钮区域 - 使用网格布局确保均匀分布
        teammateBtnLayout = QGridLayout()  # 改回网格布局
        teammateBtnLayout.setSpacing(18)  # 进一步增加基础间距 (原为15)
        teammateBtnLayout.setVerticalSpacing(48)  # 大幅增大垂直间距 (原为20)
        teammateBtnLayout.setContentsMargins(10, 0, 10, 0)  # 保持或调整水平内边距
        
        addTeammateBtn = PrimaryPushButton('添加队友')
        addTeammateBtn.setIcon(FIF.ADD)
        addTeammateBtn.setFixedWidth(115)  # 进一步减少按钮宽度 (原为125)
        addTeammateBtn.setMinimumHeight(36)  # 保持按钮高度
        
        removeTeammateBtn = PushButton('移除队友')
        removeTeammateBtn.setIcon(FIF.REMOVE)
        removeTeammateBtn.setFixedWidth(115)  # 进一步减少按钮宽度 (原为125)
        removeTeammateBtn.setMinimumHeight(36)  # 保持按钮高度
        
        loadTeammateBtn = PushButton('加载队友')
        loadTeammateBtn.setIcon(FIF.DOWNLOAD)
        loadTeammateBtn.setFixedWidth(115)  # 进一步减少按钮宽度 (原为125)
        loadTeammateBtn.setMinimumHeight(36)  # 保持按钮高度
        
        clearAllTeammatesBtn = PushButton('清除全部')
        clearAllTeammatesBtn.setIcon(FIF.DELETE)
        clearAllTeammatesBtn.setFixedWidth(115)  # 进一步减少按钮宽度 (原为125)
        clearAllTeammatesBtn.setMinimumHeight(36)  # 保持按钮高度
        
        # 连接按钮事件
        addTeammateBtn.clicked.connect(self.addTeammate)
        removeTeammateBtn.clicked.connect(self.removeTeammate)
        loadTeammateBtn.clicked.connect(self.loadTeammate)
        clearAllTeammatesBtn.clicked.connect(self.clearAllTeammates)
        
        # 使用网格布局均匀排列按钮，2行2列，修正行号并增加间距
        teammateBtnLayout.addWidget(addTeammateBtn, 0, 0)      # 第1行第1列
        teammateBtnLayout.addWidget(removeTeammateBtn, 0, 1)   # 第1行第2列
        teammateBtnLayout.addWidget(loadTeammateBtn, 1, 0)     # 第2行第1列
        teammateBtnLayout.addWidget(clearAllTeammatesBtn, 1, 1) # 第2行第2列
        
        # 队友信息显示
        teammateInfoLabel = BodyLabel('')
        teammateInfoLabel.setObjectName("teammateInfoLabel")  # 设置对象名以便更新时查找
        teammateInfoLabel.setWordWrap(True)  # 允许文字换行
        teammateInfoLabel.setStyleSheet("color: #666; font-size: 13px;")  # 设置样式，使其显示更清晰
        teammateInfoLabel.setAlignment(Qt.AlignCenter)  # 居中对齐
        
        # 添加到卡片布局
        teammateLayout.addLayout(teammateBtnLayout)
        teammateLayout.addWidget(teammateInfoLabel)
        teammateLayout.addStretch(1)  # 添加弹性空间，将内容推向顶部，使标签居中
        teammateCardWidget = QWidget()
        teammateCardWidget.setLayout(teammateLayout)
        teammateCard.viewLayout.addWidget(teammateCardWidget)
        
        # 将两个卡片添加到顶部布局
        topLayout.addWidget(iconCard, 1) # 设置伸展因子为1
        topLayout.addWidget(teammateCard, 1) # 设置伸展因子为1
        
        # ========== 识别队友区域 ==========
        recognitionCard = HeaderCardWidget(self.teamRecognitionInterface)
        recognitionCard.setTitle("识别队友")
        recognitionLayout = QVBoxLayout()
        recognitionLayout.setSpacing(18)  # 增加垂直间距
        recognitionLayout.setContentsMargins(0, 8, 0, 8)  # 增加内边距
        
        # 控制面板区域
        controlsPanel = QFrame()
        controlsPanel.setObjectName("cardFrame")
        controlsPanelLayout = QHBoxLayout(controlsPanel)
        controlsPanelLayout.setSpacing(16)
        controlsPanelLayout.setContentsMargins(16, 12, 16, 12)  # 增加内边距使内容更加突出
        
        # 选择识别位置按钮
        selectPositionBtn = PrimaryPushButton("选择识别位置")
        selectPositionBtn.setIcon(FIF.EDIT)
        selectPositionBtn.setMinimumWidth(160)  # 增加按钮宽度
        
        # 识别状态显示
        statusLabel = BodyLabel("状态: 未开始识别")
        statusLabel.setStyleSheet("color: #888; font-size: 14px;")  # 调整样式
        
        controlsPanelLayout.addWidget(selectPositionBtn)
        controlsPanelLayout.addWidget(statusLabel)
        controlsPanelLayout.addStretch(1)
        
        # 预览区域
        previewArea = QFrame()
        previewArea.setObjectName("cardFrame")
        # 修改：使用浅色背景和深色文字
        previewArea.setStyleSheet("#cardFrame{background-color: #f8f9fa; color: #333333; border-radius: 10px; border: 1px solid #e0e0e0;}") 
        previewLayout = QVBoxLayout(previewArea)
        previewLayout.setContentsMargins(10, 10, 10, 10)  # 添加内边距
        
        previewTitle = QLabel("队友信息预览")
        previewTitle.setAlignment(Qt.AlignCenter)
        # 修改：标题文字颜色改为深色
        previewTitle.setStyleSheet("color: #333333; font-size: 16px; font-weight: bold; margin-bottom: 10px;")
        
        # 创建滚动区域
        scrollArea = ScrollArea()
        scrollArea.setWidgetResizable(True)
        scrollArea.setStyleSheet("background: transparent; border: none;")
        
        scrollContent = QWidget()
        scrollLayout = QVBoxLayout(scrollContent)
        scrollLayout.setContentsMargins(0, 0, 0, 0)
        scrollLayout.setSpacing(8)
        
        # 创建队友信息标签
        self.teammateInfoPreview = QLabel("加载队友信息中...")
        self.teammateInfoPreview.setWordWrap(True)
        # 修改：默认文字颜色改为深色
        self.teammateInfoPreview.setStyleSheet("color: #333333; font-size: 14px;") 
        scrollLayout.addWidget(self.teammateInfoPreview)
        
        scrollArea.setWidget(scrollContent)
        
        previewLayout.addWidget(previewTitle)
        previewLayout.addWidget(scrollArea)
        
        # 添加更新按钮
        updateInfoBtn = PushButton("刷新队友信息")
        updateInfoBtn.setIcon(FIF.SYNC)
        updateInfoBtn.clicked.connect(self.update_teammate_preview)
        previewLayout.addWidget(updateInfoBtn)
        
        # 底部控制按钮
        buttonLayout = QHBoxLayout()
        buttonLayout.setSpacing(16)
        
        startBtn = PrimaryPushButton("开始识别")
        startBtn.setIcon(FIF.PLAY)
        startBtn.setMinimumWidth(130)  # 增加按钮宽度
        
        stopBtn = PushButton("停止")
        stopBtn.setIcon(FIF.CANCEL)
        stopBtn.setMinimumWidth(130)  # 增加按钮宽度
        
        saveBtn = PushButton("导出配置")
        saveBtn.setIcon(FIF.SAVE)
        saveBtn.setMinimumWidth(130)  # 增加按钮宽度
        
        # 连接按钮事件
        selectPositionBtn.clicked.connect(self.select_recognition_position)
        startBtn.clicked.connect(self.start_recognition_from_calibration)
        stopBtn.clicked.connect(self.stop_recognition)
        saveBtn.clicked.connect(self.export_recognition_config)
        
        # 然后继续添加按钮到布局
        buttonLayout.addStretch(1)
        buttonLayout.addWidget(startBtn)
        buttonLayout.addWidget(stopBtn)
        buttonLayout.addWidget(saveBtn)
        buttonLayout.addStretch(1)
        
        # 添加到识别布局
        recognitionLayout.addWidget(controlsPanel)
        recognitionLayout.addWidget(previewArea)
        recognitionLayout.addLayout(buttonLayout)
        
        recognitionCardWidget = QWidget()
        recognitionCardWidget.setLayout(recognitionLayout)
        recognitionCard.viewLayout.addWidget(recognitionCardWidget)
        
        # 添加到主布局
        layout.addLayout(topLayout)
        layout.addWidget(recognitionCard, 1)  # 1表示伸展因子，让这个区域占据更多空间
        
    def loadProfessionIcons(self):
        """加载职业图标并显示管理对话框"""
        # 使用自定义无边框对话框
        manage_dialog = ProfessionIconsManageDialog(self)
        manage_dialog.exec()
    
    def deleteProfessionIcon(self, icon_file, frame, dialog=None):
        """删除职业图标"""
        profession_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "profession_icons")
        icon_path = os.path.join(profession_path, icon_file)
        
        # 确认删除
        confirm_dialog = ConfirmMessageBox(
            "确认删除",
            f"确定要删除职业图标 {os.path.splitext(icon_file)[0]} 吗？",
            self if not dialog else dialog # Keep ConfirmMessageBox parented to dialog for modality
        )
        
        if confirm_dialog.exec():
            try:
                # 删除文件
                os.remove(icon_path)
                # 从UI中移除
                frame.setParent(None)
                frame.deleteLater()
                # 更新图标计数
                self.updateIconCount()
                # 提示成功
                InfoBar.success(
                    title='删除成功',
                    content=f'已删除职业图标 {os.path.splitext(icon_file)[0]}',
                    orient=Qt.Horizontal,
                    isClosable=True,
                    position=InfoBarPosition.TOP,
                    duration=2000,
                    parent=self  # Ensure InfoBar is parented to MainWindow
                )
            except Exception as e:
                # 删除失败提示
                InfoBar.error(
                    title='删除失败',
                    content=str(e),
                    orient=Qt.Horizontal,
                    isClosable=True,
                    position=InfoBarPosition.TOP,
                    duration=3000,
                    parent=self  # Ensure InfoBar is parented to MainWindow
                )

    def initHealthMonitorInterface(self):
        """初始化血条监控界面"""
        layout = QVBoxLayout(self.healthMonitorInterface)
        layout.setSpacing(16)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # 标题和状态信息
        titleLayout = QHBoxLayout()
        titleLabel = StrongBodyLabel("血条实时监控")
        titleLabel.setStyleSheet("font-size: 18px; font-weight: bold;")
        
        self.monitor_status_label = BodyLabel("准备就绪")
        self.monitor_status_label.setStyleSheet("color: #3498db;")
        titleLayout.addWidget(titleLabel)
        titleLayout.addStretch(1)
        titleLayout.addWidget(self.monitor_status_label)
        
        # 控制按钮区域
        controlLayout = QHBoxLayout()
        
        startMonitorBtn = PrimaryPushButton("开始监控")
        startMonitorBtn.setIcon(FIF.PLAY)
        startMonitorBtn.setMinimumWidth(120)
        
        stopMonitorBtn = PushButton("停止监控")
        stopMonitorBtn.setIcon(FIF.CLOSE)
        stopMonitorBtn.setMinimumWidth(120)
        
        # 新增：设置血条颜色按钮
        setColorBtn = PushButton("设置血条颜色")
        setColorBtn.setIcon(FIF.PALETTE) # 使用 PALETTE 图标替代 COLOR
        setColorBtn.setMinimumWidth(120)
        
        # 新增：统一设置血条颜色按钮
        setAllColorsBtn = PushButton("统一设置颜色")
        setAllColorsBtn.setIcon(FIF.BRUSH) # 使用 BRUSH 图标
        setAllColorsBtn.setMinimumWidth(120)
        
        # 连接按钮事件
        startMonitorBtn.clicked.connect(self.health_monitor.start_monitoring)
        stopMonitorBtn.clicked.connect(self.health_monitor.stop_monitoring)
        setColorBtn.clicked.connect(self.setTeammateHealthBarColor)  # 连接到单个设置方法
        setAllColorsBtn.clicked.connect(self.handleSetAllTeammatesColor) # 连接到统一设置方法
        
        controlLayout.addWidget(startMonitorBtn)
        controlLayout.addWidget(stopMonitorBtn)
        controlLayout.addWidget(setColorBtn)  # 添加单个设置按钮
        controlLayout.addWidget(setAllColorsBtn) # 添加统一设置按钮
        controlLayout.addStretch(1)
        
        # 血条展示区域
        self.health_bars_frame = QFrame()
        self.health_bars_frame.setObjectName("cardFrame")
        self.health_bars_frame.setStyleSheet("QFrame#cardFrame { background-color: rgba(240, 240, 240, 0.7); border-radius: 8px; padding: 10px; }")
        healthBarsLayout = QVBoxLayout(self.health_bars_frame)
        healthBarsLayout.setSpacing(12)
        healthBarsLayout.setContentsMargins(15, 15, 15, 15)
        
        # 初始化血条UI
        self.init_health_bars_ui()
        
        # 添加到监控布局
        layout.addLayout(titleLayout)
        layout.addLayout(controlLayout)
        layout.addWidget(self.health_bars_frame, 1)  # 将监控卡片设置为可伸展，占用更多空间
        
        # 设置卡片
        settingsCard = HeaderCardWidget(self.healthMonitorInterface)
        settingsCard.setTitle("血条监控设置")
        
        settingsLayout = QVBoxLayout()
        settingsLayout.setSpacing(12)
        
        # 基本设置组
        paramsGroup = QGroupBox("监控参数", self.healthMonitorInterface)
        paramsGroupLayout = QVBoxLayout()
        
        # 阈值设置
        thresholdLayout = QHBoxLayout()
        thresholdLabel = BodyLabel(f"血条阈值: {int(self.health_monitor.health_threshold)}%")
        thresholdSlider = Slider(Qt.Horizontal)
        thresholdSlider.setRange(0, 100)
        thresholdSlider.setValue(int(self.health_monitor.health_threshold))
        thresholdLayout.addWidget(thresholdLabel)
        thresholdLayout.addWidget(thresholdSlider)
        thresholdSlider.valueChanged.connect(lambda v: self.update_health_threshold(v, thresholdLabel))
        
        # 采样率设置
        samplingLayout = QHBoxLayout()
        samplingLabel = BodyLabel("采样率 (fps):")
        samplingSpinBox = SpinBox()
        samplingSpinBox.setRange(1, 60)
        samplingSpinBox.setValue(10)
        samplingLayout.addWidget(samplingLabel)
        samplingLayout.addWidget(samplingSpinBox)
        
        # 添加所有参数设置
        paramsGroupLayout.addLayout(thresholdLayout)
        paramsGroupLayout.addLayout(samplingLayout)
        
        # 自动点击低血量队友功能开关
        autoClickLayout = QHBoxLayout()
        autoClickLabel = BodyLabel("自动点击低血量队友:")
        self.autoClickSwitch = SwitchButton()
        # 从 HealthMonitor 加载初始状态
        if hasattr(self, 'health_monitor') and hasattr(self.health_monitor, 'auto_select_enabled'):
            self.autoClickSwitch.setChecked(self.health_monitor.auto_select_enabled)
        else:
            self.autoClickSwitch.setChecked(False) # 默认关闭
        
        # 新增：职业优先级下拉框
        priorityLabel = BodyLabel("优先职业:")
        self.priorityComboBox = ComboBox()
        self.priorityComboBox.setFixedWidth(120)
        # 加载所有职业选项
        self.load_profession_options()
        # 设置当前选中值
        if hasattr(self, 'health_monitor') and hasattr(self.health_monitor, 'priority_profession'):
            priority_index = self.priorityComboBox.findText(self.health_monitor.priority_profession)
            if priority_index >= 0:
                self.priorityComboBox.setCurrentIndex(priority_index)
        
        # 连接信号
        self.autoClickSwitch.checkedChanged.connect(self.toggle_auto_click_low_health)
        self.priorityComboBox.currentTextChanged.connect(self.update_priority_profession)
        
        autoClickLayout.addWidget(autoClickLabel)
        autoClickLayout.addWidget(self.autoClickSwitch)
        autoClickLayout.addSpacing(20)  # 增加间距
        autoClickLayout.addWidget(priorityLabel)
        autoClickLayout.addWidget(self.priorityComboBox)
        autoClickLayout.addStretch(1)
        paramsGroupLayout.addLayout(autoClickLayout) # 添加到参数组布局
        
        paramsGroup.setLayout(paramsGroupLayout)
        
        # 添加到主设置布局
        settingsLayout.addWidget(paramsGroup)
        settingsCardWidget = QWidget()
        settingsCardWidget.setLayout(settingsLayout)
        settingsCard.viewLayout.addWidget(settingsCardWidget)
        
        # 添加卡片到主布局，但设置较小的高度比例
        layout.addWidget(settingsCard)
        
        # 更新采样率设置
        samplingSpinBox.valueChanged.connect(self.update_sampling_rate)
    
    def init_health_bars_ui(self):
        """初始化血条UI显示"""
        if not self.health_bars_frame:
            return

        # 清除现有布局中的所有组件
        current_layout = self.health_bars_frame.layout()
        if current_layout is not None:
            while current_layout.count():
                item = current_layout.takeAt(0)
                widget = item.widget()
                if widget:
                    widget.deleteLater()
        else:
            # 如果布局不存在，则创建一个新的
            new_layout = QVBoxLayout(self.health_bars_frame)
            new_layout.setSpacing(12)
            new_layout.setContentsMargins(15, 15, 15, 15)
            self.health_bars_frame.setLayout(new_layout) # 设置新布局
        
        # --- 新增：按血条 y1, x1 坐标对队员进行排序 ---
        sorted_members = sorted(self.team.members, key=lambda m: (m.y1, m.x1))
        
        # 添加队友信息卡片
        for i, member in enumerate(sorted_members): # 使用排序后的列表
            self.add_health_bar_card(i, member.name, member.profession)
            
        # 如果没有队友，显示提示信息
        if not self.team.members and self.health_bars_frame.layout() is not None: # 检查原始列表判断是否有队友
            noMemberLabel = StrongBodyLabel("没有队友信息。请在队员识别页面添加队友。")
            noMemberLabel.setAlignment(Qt.AlignCenter)
            self.health_bars_frame.layout().addWidget(noMemberLabel)
        
        # 添加：强制更新框架，确保UI刷新
        self.health_bars_frame.update()
    
    def add_health_bar_card(self, index, name, profession):
        """添加血条卡片
        
        参数:
            index: 队友索引
            name: 队友名称
            profession: 队友职业
        """
        # 创建水平布局，每一行一个队员
        memberCard = QFrame()
        memberCard.setObjectName(f"member_card_{index}")
        memberCard.setFixedHeight(60)  # 设置固定高度
        memberCard.setStyleSheet("background-color: transparent;")
        memberLayout = QHBoxLayout(memberCard)
        memberLayout.setContentsMargins(5, 0, 5, 0)
        memberLayout.setSpacing(10)
        
        # 队员编号和名称 - 使用实际名称
        nameLabel = StrongBodyLabel(name)
        nameLabel.setObjectName(f"name_label_{index}")
        nameLabel.setStyleSheet("font-size: 14px; font-weight: bold;")
        nameLabel.setFixedWidth(80)
        
        # 修改：直接显示识别到的职业名称
        roleLabel = BodyLabel(str(profession)) # 确保是字符串
        roleLabel.setStyleSheet("color: #666; font-size: 12px;")
        roleLabel.setFixedWidth(60)
        roleLabel.setToolTip(str(profession)) # 添加悬浮提示显示完整职业名
        
        # 血条容器
        healthBarContainer = QFrame()
        healthBarContainer.setFixedHeight(25)
        healthBarContainer.setStyleSheet("background-color: #333; border-radius: 5px;")
        # --- 添加：设置最大宽度 --- 
        MAX_WIDTH = 300  # 与 update_health_display 中保持一致
        healthBarContainer.setMaximumWidth(MAX_WIDTH) 
        # --- 结束添加 ---
        healthBarContainerLayout = QHBoxLayout(healthBarContainer)
        healthBarContainerLayout.setContentsMargins(2, 2, 2, 2)
        healthBarContainerLayout.setSpacing(0)
        
        # 血条
        healthBar = QFrame()
        healthBar.setObjectName(f"health_bar_{index}")
        healthBar.setFixedHeight(21)
        
        # 根据索引设置不同颜色
        color = "#2ecc71"  # 绿色 (默认，表示90%)
        if index == 1:
            color = "#2ecc71"  # 绿色 (70%)
        elif index == 2:
            color = "#f39c12"  # 黄色 (50%)
        elif index == 3:
            color = "#e74c3c"  # 红色 (30%)
        elif index == 4:
            color = "#e74c3c"  # 红色 (10%)
        
        # 设置默认百分比
        default_percentage = 90
        if index == 1:
            default_percentage = 70
        elif index == 2:
            default_percentage = 50
        elif index == 3:
            default_percentage = 30
        elif index == 4:
            default_percentage = 10
        
        # 设置血条缩放因子和最大宽度
        SCALE_FACTOR = 3
        MAX_WIDTH = 300  # 血条最大宽度
        
        # 计算血条宽度
        bar_width = min(int(default_percentage * SCALE_FACTOR), MAX_WIDTH)
        print(f"队员{index+1} 初始血条宽度: {bar_width}px (血量: {default_percentage}%)")
        
        healthBar.setStyleSheet(f"background-color: {color}; border-radius: 3px;")
        healthBar.setFixedWidth(bar_width)  # 使用计算的宽度
        
        healthBarContainerLayout.addWidget(healthBar)
        healthBarContainerLayout.addStretch(1)
        
        # 血量百分比
        valueLabel = StrongBodyLabel(f"{default_percentage}%")
        valueLabel.setObjectName(f"value_label_{index}")
        valueLabel.setStyleSheet(f"color: {color}; font-weight: bold; font-size: 15px;")
        valueLabel.setAlignment(Qt.AlignCenter)
        valueLabel.setFixedWidth(60)
        
        # 添加调试标签 - 开发期间使用，显示实际内部存储的血量
        debugLabel = QLabel(f"dbg:ok")
        debugLabel.setObjectName(f"debug_label_{index}")
        debugLabel.setStyleSheet("color: #999; font-size: 8px;")
        debugLabel.setFixedWidth(50)
        
        # 添加到卡片布局
        memberLayout.addWidget(nameLabel)
        memberLayout.addWidget(roleLabel)
        memberLayout.addWidget(healthBarContainer)
        memberLayout.addWidget(valueLabel)
        memberLayout.addWidget(debugLabel)  # 添加调试标签
        
        # 添加到主布局
        self.health_bars_frame.layout().addWidget(memberCard)
        
        # 添加分隔线（除了最后一个）
        if index < len(self.team.members) - 1:
            separator = QFrame()
            separator.setFrameShape(QFrame.HLine)
            separator.setFrameShadow(QFrame.Sunken)
            separator.setStyleSheet("background-color: #e0e0e0;")
            separator.setFixedHeight(1)
            self.health_bars_frame.layout().addWidget(separator)
    
    def update_sampling_rate(self, value):
        """更新监控采样率
        
        参数:
            value: 采样率值（fps）
        """
        if hasattr(self, 'health_monitor'):
            # 转换为更新间隔（秒）
            interval = 1.0 / value if value > 0 else 0.1
            self.health_monitor.update_interval = interval
            self.update_monitor_status(f"采样率已更新: {value} fps (更新间隔: {interval:.2f}秒)")
    
    def show_hotkey_settings(self):
        """显示快捷键设置对话框"""
        dialog = HotkeySettingsMessageBox(self.health_monitor, self)
        dialog.exec()
    
    def show_error_message(self, message):
        """显示错误消息
        
        参数:
            message: 错误消息
        """
        InfoBar.error(
            title='错误',
            content=message,
            orient=Qt.Horizontal,
            isClosable=True,
            position=InfoBarPosition.TOP,
            duration=3000,
            parent=self
        )
    
    def set_auto_select(self, enabled):
        """设置自动选择功能
        
        参数:
            enabled: 是否启用
        """
        if hasattr(self, 'health_monitor'):
            self.health_monitor.auto_select_enabled = enabled
            self.health_monitor.save_auto_select_config()
            status = "启用" if enabled else "禁用"
            self.update_monitor_status(f"自动选择功能已{status}")

    def initAssistInterface(self):
        """初始化辅助功能界面"""
        layout = QVBoxLayout(self.assistInterface)
        layout.setSpacing(16)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # 左右布局，左侧为主要功能，右侧为次要功能
        mainLayout = QHBoxLayout()
        mainLayout.setSpacing(16)
        
        # 左侧布局 - 现在只包含快捷键设置
        leftLayout = QVBoxLayout()
        leftLayout.setSpacing(16)
        
        # 快捷键卡片
        hotkeyCard = HeaderCardWidget(self.assistInterface)
        hotkeyCard.setTitle("快捷键设置")
        
        hotkeyLayout = QVBoxLayout()
        hotkeyLayout.setSpacing(12)
        
        # 提示信息
        hotkey_info = BodyLabel("设置全局快捷键用于快速操作。点击\"记录\"按钮后，按下想要设置的键。")
        hotkey_info.setWordWrap(True)
        
        # 快捷键表格
        hotkeyGridLayout = QGridLayout()
        hotkeyGridLayout.setSpacing(12)
        
        # 开始监控
        startMonitorLabel = BodyLabel('开始监控:')
        startMonitorEdit = LineEdit()
        startMonitorEdit.setReadOnly(True)
        startMonitorEdit.setText(self.health_monitor.start_monitoring_hotkey)
        startMonitorRecordBtn = PushButton('记录')
        
        # 停止监控
        stopMonitorLabel = BodyLabel('停止监控:')
        stopMonitorEdit = LineEdit()
        stopMonitorEdit.setReadOnly(True)
        stopMonitorEdit.setText(self.health_monitor.stop_monitoring_hotkey)
        stopMonitorRecordBtn = PushButton('记录')
        
        # 绑定"记录"按钮事件，使用事件过滤器方式
        startMonitorRecordBtn.clicked.connect(lambda: self.install_hotkey_event_filter(startMonitorEdit, stopMonitorEdit, 'start'))
        stopMonitorRecordBtn.clicked.connect(lambda: self.install_hotkey_event_filter(stopMonitorEdit, startMonitorEdit, 'stop'))
        
        # 添加到网格
        hotkeyGridLayout.addWidget(startMonitorLabel, 0, 0)
        hotkeyGridLayout.addWidget(startMonitorEdit, 0, 1)
        hotkeyGridLayout.addWidget(startMonitorRecordBtn, 0, 2)
        
        hotkeyGridLayout.addWidget(stopMonitorLabel, 1, 0)
        hotkeyGridLayout.addWidget(stopMonitorEdit, 1, 1)
        hotkeyGridLayout.addWidget(stopMonitorRecordBtn, 1, 2)
        
        # 添加所有组件到快捷键卡片
        hotkeyLayout.addWidget(hotkey_info)
        hotkeyLayout.addLayout(hotkeyGridLayout)
        # 增加状态信息标签
        self.hotkeyStatusLabel = BodyLabel('')
        hotkeyLayout.addWidget(self.hotkeyStatusLabel)
        hotkeyCardWidget = QWidget()
        hotkeyCardWidget.setLayout(hotkeyLayout)
        hotkeyCard.viewLayout.addWidget(hotkeyCardWidget)
        
        # 添加快捷键卡片到左侧布局
        leftLayout.addWidget(hotkeyCard)
        leftLayout.addStretch(1)
        
        # 右侧布局 - 保持不变
        rightLayout = QVBoxLayout()
        rightLayout.setSpacing(16)
        
        # 数据导出卡片
        exportCard = HeaderCardWidget(self.assistInterface)
        exportCard.setTitle("数据导出")
        
        exportLayout = QVBoxLayout()
        exportLayout.setSpacing(12)
        
        # 导出按钮
        exportBtnsLayout = QHBoxLayout()
        
        exportCsvBtn = PushButton("导出CSV")
        exportCsvBtn.setIcon(FIF.DOWNLOAD)
        
        exportJsonBtn = PushButton("导出JSON")
        exportJsonBtn.setIcon(FIF.DOWNLOAD)
        
        exportBtnsLayout.addWidget(exportCsvBtn)
        exportBtnsLayout.addWidget(exportJsonBtn)
        exportBtnsLayout.addStretch(1)
        
        # 自动导出开关
        autoExportLayout = QHBoxLayout()
        autoExportLabel = BodyLabel("自动导出:")
        autoExportSwitch = SwitchButton()
        
        autoExportLayout.addWidget(autoExportLabel)
        autoExportLayout.addWidget(autoExportSwitch)
        autoExportLayout.addStretch(1)
        
        # 导出路径
        exportPathLayout = QHBoxLayout()
        exportPathLabel = BodyLabel("导出路径:")
        exportPathEdit = LineEdit()
        exportPathEdit.setText(os.path.join(os.path.expanduser("~"), "Documents"))
        exportPathBtn = PushButton("浏览")
        exportPathBtn.setIcon(FIF.FOLDER)
        
        exportPathLayout.addWidget(exportPathLabel)
        exportPathLayout.addWidget(exportPathEdit)
        exportPathLayout.addWidget(exportPathBtn)
        
        # 添加所有组件到导出卡片
        exportLayout.addLayout(exportBtnsLayout)
        exportLayout.addLayout(autoExportLayout)
        exportLayout.addLayout(exportPathLayout)
        exportCardWidget = QWidget()
        exportCardWidget.setLayout(exportLayout)
        exportCard.viewLayout.addWidget(exportCardWidget)
        
        # 添加导出卡片到右侧布局
        rightLayout.addWidget(exportCard)
        rightLayout.addStretch(1)
        
        # 添加左右布局到主布局
        mainLayout.addLayout(leftLayout, 2)
        mainLayout.addLayout(rightLayout, 1)
        
        # 添加主布局到辅助功能界面
        layout.addLayout(mainLayout)

    def initSettingsInterface(self):
        """初始化设置界面"""
        layout = QVBoxLayout(self.settingsInterface)
        layout.setSpacing(16)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # 基本设置卡片
        basicCard = HeaderCardWidget(self.settingsInterface)
        basicCard.setTitle("基本设置")
        
        basicLayout = QVBoxLayout()
        basicLayout.setSpacing(16)
        
        # 主题设置
        themeLayout = QHBoxLayout()
        themeLabel = BodyLabel("主题:")
        themeCombo = ComboBox()
        themeCombo.addItems(["跟随系统", "亮色模式", "暗色模式"])
        themeLayout.addWidget(themeLabel)
        themeLayout.addWidget(themeCombo)
        themeLayout.addStretch(1)
        
        # 语言设置
        languageLayout = QHBoxLayout()
        languageLabel = BodyLabel("语言:")
        languageCombo = ComboBox()
        languageCombo.addItems(["简体中文", "English"])
        languageLayout.addWidget(languageLabel)
        languageLayout.addWidget(languageCombo)
        languageLayout.addStretch(1)
        
        # 自动启动
        autoStartLayout = QHBoxLayout()
        autoStartLabel = BodyLabel("开机自动启动:")
        autoStartSwitch = SwitchButton()
        autoStartLayout.addWidget(autoStartLabel)
        autoStartLayout.addWidget(autoStartSwitch)
        autoStartLayout.addStretch(1)
        
        # 添加所有组件到基本设置卡片
        basicLayout.addLayout(themeLayout)
        basicLayout.addLayout(languageLayout)
        basicLayout.addLayout(autoStartLayout)
        basicCardWidget = QWidget()
        basicCardWidget.setLayout(basicLayout)
        basicCard.viewLayout.addWidget(basicCardWidget)
        
        # 高级设置卡片
        advancedCard = HeaderCardWidget(self.settingsInterface)
        advancedCard.setTitle("高级设置")
        
        advancedLayout = QVBoxLayout()
        advancedLayout.setSpacing(16)
        
        # 缓存设置
        cacheLayout = QHBoxLayout()
        cacheLabel = BodyLabel("缓存大小:")
        cacheSizeLabel = BodyLabel("23.5 MB")
        clearCacheBtn = PushButton("清除缓存")
        clearCacheBtn.setIcon(FIF.DELETE)
        
        cacheLayout.addWidget(cacheLabel)
        cacheLayout.addWidget(cacheSizeLabel)
        cacheLayout.addStretch(1)
        cacheLayout.addWidget(clearCacheBtn)
        
        # AI模型设置
        modelLayout = QHBoxLayout()
        modelLabel = BodyLabel("AI模型:")
        modelCombo = ComboBox()
        modelCombo.addItems(['标准模型', '轻量级模型', '高精度模型', '自娱自乐模型', '作者没钱加模型'])
        modelLayout.addWidget(modelLabel)
        modelLayout.addWidget(modelCombo)
        modelLayout.addStretch(1)
        
        # GPU加速
        gpuLayout = QHBoxLayout()
        gpuLabel = BodyLabel("GPU加速:")
        gpuSwitch = SwitchButton()
        gpuSwitch.setChecked(True)
        gpuLayout.addWidget(gpuLabel)
        gpuLayout.addWidget(gpuSwitch)
        gpuLayout.addStretch(1)
        
        # 添加所有组件到高级设置卡片
        advancedLayout.addLayout(cacheLayout)
        advancedLayout.addLayout(modelLayout)
        advancedLayout.addLayout(gpuLayout)
        advancedCardWidget = QWidget()
        advancedCardWidget.setLayout(advancedLayout)
        advancedCard.viewLayout.addWidget(advancedCardWidget)
        
        # 关于卡片
        aboutCard = HeaderCardWidget(self.settingsInterface)
        aboutCard.setTitle("关于")
        
        aboutLayout = QVBoxLayout()
        aboutLayout.setSpacing(16)
        
        # 版本信息
        versionLayout = QHBoxLayout()
        versionLabel = BodyLabel("版本:")
        versionValueLabel = BodyLabel("VitalSync 2.0.0")
        versionLayout.addWidget(versionLabel)
        versionLayout.addWidget(versionValueLabel)
        versionLayout.addStretch(1)
        
        # 关于信息
        aboutInfoLabel = BodyLabel("VitalSync 是一款专为游戏设计的队员血条识别与监控软件，支持多种游戏和场景。")
        aboutInfoLabel.setWordWrap(True)
        
        # 控制按钮
        controlLayout = QHBoxLayout()
        updateBtn = PushButton("检查更新")
        updateBtn.setIcon(FIF.UPDATE)
        
        githubBtn = PushButton("GitHub项目")
        githubBtn.setIcon(FIF.LINK)
        # 连接点击事件
        githubBtn.clicked.connect(self.openGitHubProject)
        
        controlLayout.addWidget(updateBtn)
        controlLayout.addWidget(githubBtn)
        controlLayout.addStretch(1)
        
        # 添加所有组件到关于卡片
        aboutLayout.addLayout(versionLayout)
        aboutLayout.addWidget(aboutInfoLabel)
        aboutLayout.addLayout(controlLayout)
        aboutCardWidget = QWidget()
        aboutCardWidget.setLayout(aboutLayout)
        aboutCard.viewLayout.addWidget(aboutCardWidget)
        
        # 添加所有卡片到设置界面
        layout.addWidget(basicCard)
        layout.addWidget(advancedCard)
        layout.addWidget(aboutCard)
        layout.addStretch(1)

    def openGitHubProject(self):
        """打开GitHub项目页面"""
        url = QUrl("https://github.com/yinduandafeimao/VitalSync-Pulse")
        QDesktopServices.openUrl(url)
        
        # 显示提示信息
        InfoBar.success(
            title='已打开链接',
            content='已在浏览器中打开GitHub项目页面',
            orient=Qt.Horizontal,
            isClosable=True,
            position=InfoBarPosition.TOP,
            duration=2000,
            parent=self
        )

    def addProfessionIcon(self):
        """添加新的职业图标"""
        # 检查profession_icons文件夹是否存在
        profession_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "profession_icons")
        if not os.path.exists(profession_path):
            os.makedirs(profession_path)  # 创建文件夹如果不存在
            
        # 打开文件选择对话框
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "选择职业图标",
            "",
            "图片文件 (*.png *.jpg *.jpeg)"
        )
        
        if not file_path:
            return
        
        # 获取文件名
        file_name_without_ext = os.path.splitext(os.path.basename(file_path))[0]
        
        # 使用自定义无边框对话框获取职业名称
        input_dialog = TextInputMessageBox(
            title='输入职业名称',
            label_text='请输入该职业图标的名称:',
            default_text=file_name_without_ext,
            placeholder_text='例如：奶妈、坦克、输出',
            parent=self
        )
        
        if not input_dialog.exec():
            return
        
        icon_name = input_dialog.get_text()
        if not icon_name:
            InfoBar.warning(
                title='输入无效',
                content='职业名称不能为空。',
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=2000,
                parent=self
            )
            return
        
        # 构造目标路径
        target_path = os.path.join(profession_path, icon_name + os.path.splitext(file_path)[1])
        
        # 检查是否已存在同名文件
        if os.path.exists(target_path):
            confirm_dialog = ConfirmMessageBox(
                "文件已存在",
                f"职业 '{icon_name}' 已存在，是否覆盖?",
                self
            )
            
            if not confirm_dialog.exec():
                return
        
        try:
            # 复制文件
            import shutil
            shutil.copy2(file_path, target_path)
            
            # 显示成功消息
            InfoBar.success(
                title='添加成功',
                content=f'职业图标 {icon_name} 已添加',
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=2000,
                parent=self
            )
            
            # 更新图标数量显示
            self.updateIconCount()
        except Exception as e:
            # 显示错误消息
            InfoBar.error(
                title='添加失败',
                content=str(e),
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=3000,
                parent=self
            )
    
    def updateIconCount(self):
        """更新职业图标数量显示"""
        # 重新计算图标数量
        profession_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "profession_icons")
        icon_count = len([f for f in os.listdir(profession_path) if f.endswith(('.png', '.jpg', '.jpeg'))])
        
        # 查找信息标签并更新
        for i in range(self.iconCardWidget.layout().count()):
            item = self.iconCardWidget.layout().itemAt(i)
            if item.widget() and isinstance(item.widget(), BodyLabel) and "当前已加载" in item.widget().text():
                item.widget().setText(f'当前已加载 {icon_count} 个职业图标')
                break

    def init_recognition(self):
        """初始化识别模块"""
        try:
            if self.recognition is None:
                from teammate_recognition import TeammateRecognition
                self.recognition = TeammateRecognition()
                InfoBar.success(
                    title='OCR模型加载成功',
                    content='队友识别功能已准备就绪',
                    orient=Qt.Horizontal,
                    isClosable=True,
                    position=InfoBarPosition.TOP,
                    duration=2000,
                    parent=self
                )
            return True
        except Exception as e:
            InfoBar.error(
                title='OCR初始化失败',
                content=f'错误: {str(e)}',
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=3000,
                parent=self
            )
            return False

    def addTeammate(self):
        """添加队友"""
        print("\n添加新队友:")
        
        # 使用自定义的MessageBoxBase子类
        dialog = AddTeammateMessageBox(self)
        
        if dialog.exec():
            name, profession = dialog.get_teammate_info()
            
            # 使用Team类添加队友
            new_member = self.team.add_member(name, profession)
            
            # 使用全局默认颜色设置(如果有的话)
            if self.default_hp_color_lower is not None and self.default_hp_color_upper is not None:
                import numpy as np
                new_member.hp_color_lower = np.copy(self.default_hp_color_lower)
                new_member.hp_color_upper = np.copy(self.default_hp_color_upper)
                new_member.save_config()  # 保存颜色设置到队员配置文件
            
            # 更新健康监控
            self.health_monitor.team = self.team
            self.init_health_bars_ui()
            
            # 提示设置血条位置 - 使用自定义确认对话框
            confirm_dialog = ConfirmMessageBox(
                "设置血条位置",
                f"是否立即为 {name} 设置血条位置？",
                self
            )
            
            if confirm_dialog.exec():
                # 使用选择框设置血条位置
                self.set_health_bar_position(new_member)
            
            InfoBar.success(
                title='添加成功',
                content=f'队友 {name} ({profession}) 已添加',
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=2000,
                parent=self
            )
            
            # 更新队友信息显示
            self.update_teammate_info()

    def set_health_bar_position(self, member):
        """设置队员血条位置"""
        from 选择框 import show_selection_box
        
        # 定义选择完成回调
        def on_selection(rect):
            member.x1 = rect.x()
            member.y1 = rect.y()
            member.x2 = rect.x() + rect.width()
            member.y2 = rect.y() + rect.height()
            print(f"{member.name}血条起始坐标设置为: ({member.x1}, {member.y1})")
            print(f"{member.name}血条结束坐标设置为: ({member.x2}, {member.y2})")
            member.save_config()  # 保存新的坐标设置
        
        # 显示选择框
        result = show_selection_box(on_selection)
        return result

    def set_health_bar_color(self, member):
        """设置队员血条颜色"""
        # 使用ColorPickerMessageBox代替普通QDialog
        color_picker_dialog = ColorPickerMessageBox(member.name, self)
        
        # 显示消息框
        if color_picker_dialog.exec():
            # 更新队友的血条颜色设置
            if hasattr(color_picker_dialog, 'color_lower') and hasattr(color_picker_dialog, 'color_upper'):
                member.hp_color_lower = color_picker_dialog.color_lower
                member.hp_color_upper = color_picker_dialog.color_upper
                    
                # 保存到配置文件
                member.save_config()
                
                # 显示成功提示
                InfoBar.success(
                    title='设置成功',
                    content=f'已设置 {member.name} 的血条颜色',
                    orient=Qt.Horizontal,
                    isClosable=True,
                    position=InfoBarPosition.TOP,
                    duration=2000,
                    parent=self
                )

    def load_teammates(self):
        """加载所有队友配置"""
        self.team_members = []
        
        # 获取当前目录
        current_dir = os.path.dirname(os.path.abspath(__file__))
        
        # 扫描队友配置文件
        for filename in os.listdir(current_dir):
            if filename.endswith('_config.json') and filename != 'hotkeys_config.json':
                try:
                    # 排除系统配置文件
                    if filename.startswith(('hotkeys', 'settings', 'config', 'system')):
                        continue
                        
                    # 从文件名提取队友名称
                    member_name = filename[:-12]  # 移除'_config.json'
                    
                    # 读取配置获取职业信息
                    config_path = os.path.join(current_dir, filename)
                    with open(config_path, 'r', encoding='utf-8') as f:
                        config = json.load(f)
                        
                        # 检查是否是有效的队友配置
                        if 'profession' not in config or 'health_bar' not in config:
                            continue
                        
                        # 获取职业信息
                        profession = config.get('profession', '未知')
                        
                        # 添加到队友列表
                        self.team_members.append({
                            'name': member_name,
                            'profession': profession,
                            'config': config
                        })
                        
                except Exception as e:
                    print(f'加载配置文件 {filename} 时出错: {str(e)}')
                    continue
        
        # 更新队友信息显示
        self.update_teammate_info()

    def update_teammate_info(self):
        """更新队友信息显示"""
        # 已移除队友信息标签，无需更新
        return

    def removeTeammate(self):
        """移除队友"""
        if not self.team.members:
            self.show_safe_infobar(
                '无队友',
                '当前无可移除的队友',
                'warning',
                2000
            )
            return
        
        # 使用自定义的消息框进行队友选择
        selection_dialog = TeammateSelectionMessageBox(
            '选择要移除的队友', 
            self.team.members, 
            self
        )
        
        if selection_dialog.exec():
            selected_member = selection_dialog.get_selected_member()
            if selected_member:
                try:
                    # 删除配置文件
                    config_file = f"{selected_member.name}_config.json"
                    config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), config_file)
                    if os.path.exists(config_path):
                        os.remove(config_path)
                    
                    # 从队伍中移除队员
                    selected_idx = self.team.members.index(selected_member)
                    self.team.members.pop(selected_idx)
                    
                    # 更新队友信息显示
                    self.update_teammate_info()
                    
                    # 更新健康监控
                    self.health_monitor.team = self.team
                    self.init_health_bars_ui()
                    
                    self.show_safe_infobar(
                        '移除成功',
                        f'队友 {selected_member.name} 已移除',
                        'success',
                        2000
                    )
                except Exception as e:
                    self.show_safe_infobar(
                        '移除失败',
                        f'错误: {str(e)}',
                        'error',
                        3000
                    )

    def loadTeammate(self):
        print('loadTeammate called')
        try:
            self.team = Team()
            self.health_monitor.team = self.team
            self.update_teammate_info()
            self.init_health_bars_ui()
            self.health_bars_frame.update()
            QApplication.processEvents()
            InfoBar.success(
                title='加载成功',
                content=f'已加载 {len(self.team.members)} 个队友',
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=2000,
                parent=self
            )
        except Exception as e:
            InfoBar.error(
                title='加载失败',
                content=f'错误: {str(e)}',
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=3000,
                parent=self
            )

    def clearAllTeammates(self):
        """清除所有队友"""
        # 创建确认对话框
        confirm_dialog = ConfirmMessageBox(
            "确认清除",
            "确定要清除所有队友吗？该操作不可恢复。",
            self
        )
        
        if confirm_dialog.exec():
            try:
                # 删除所有队友配置文件
                deleted_count = 0
                for member in self.team.members:
                    config_file = f"{member.name}_config.json"
                    config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), config_file)
                    if os.path.exists(config_path):
                        os.remove(config_path)
                        deleted_count += 1
                
                # 清空队友列表
                self.team.members = []
                
                # 更新队友信息显示
                self.update_teammate_info()
                
                # 更新健康监控
                self.health_monitor.team = self.team
                self.init_health_bars_ui()
                
                InfoBar.success(
                    title='清除成功',
                    content=f'已清除 {deleted_count} 个队友',
                    orient=Qt.Horizontal,
                    isClosable=True,
                    position=InfoBarPosition.TOP,
                    duration=2000,
                    parent=self
                )
            except Exception as e:
                InfoBar.error(
                    title='清除失败',
                    content=f'错误: {str(e)}',
                    orient=Qt.Horizontal,
                    isClosable=True,
                    position=InfoBarPosition.TOP,
                    duration=3000,
                    parent=self
                )
        print('clearAllTeammates called')

    def update_teammate_preview(self):
        """更新队友信息预览显示"""
        if not hasattr(self, 'teammateInfoPreview'):
            return
        
        if not self.team.members:
            self.teammateInfoPreview.setText("当前没有队友信息，请先添加或加载队友。")
            return
        
        # --- 新增：按血条 y1, x1 坐标对队员进行排序 ---
        sorted_members_for_preview = sorted(self.team.members, key=lambda m: (m.y1, m.x1))

        # 修改：body 样式，使用深色文字
        html = "<html><body style='color: #333333;'>" 
        
        for idx, member in enumerate(sorted_members_for_preview): # 使用排序后的列表
            # 修改：卡片样式适应浅色背景
            card_bg = "#ffffff"  # 白色背景
            border = "1px solid #e0e0e0" # 浅灰色边框
            
            # 检查是否有职业图标
            icon_html = ""
            # (这部分保持不变)
            profession_icon_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "profession_icons", f"{member.profession}.png")
            if os.path.exists(profession_icon_path):
                # 使用 file:/// 协议来确保本地文件路径在 HTML 中被正确解析
                icon_uri = QUrl.fromLocalFile(profession_icon_path).toString()
                icon_html = f"<img src='{icon_uri}' width='24' height='24' style='vertical-align: middle; margin-right: 8px;'/>"
            
            # 血条位置信息
            position = f"({member.x1}, {member.y1}) - ({member.x2}, {member.y2})"
            
            # 血条颜色信息
            color_lower = ", ".join([str(val) for val in member.hp_color_lower])
            color_upper = ", ".join([str(val) for val in member.hp_color_upper])
            
            # 添加队友信息卡片
            html += f"""
            <div style='background: {card_bg}; border: {border}; border-radius: 8px; padding: 10px; margin-bottom: 12px;'>
                <div style='font-weight: bold; font-size: 16px; margin-bottom: 8px;'>
                    {icon_html}{member.name} <span style='color: #3498db;'>({member.profession})</span>
                </div>
                <div style='margin-bottom: 6px;'>
                    <span style='color: #666666;'>血条位置:</span> {position} 
                </div>
                <div style='margin-bottom: 6px;'>
                    <span style='color: #666666;'>颜色下限:</span> [{color_lower}]
                </div>
                <div>
                    <span style='color: #666666;'>颜色上限:</span> [{color_upper}]
                </div>
            </div>
            """ # 修改：标签颜色从 #bbb 改为 #666666
        
        html += "</body></html>"
        self.teammateInfoPreview.setText(html)
        
    def export_recognition_config(self):
        """导出当前识别配置到文件"""
        if not self.team.members:
            InfoBar.warning(
                title='无可导出数据',
                content='当前没有队友信息可供导出',
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=2000,
                parent=self
            )
            return
            
        # 弹出文件保存对话框
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "导出识别配置",
            os.path.join(os.path.expanduser("~"), "Documents", "队友识别配置.json"),
            "JSON文件 (*.json)"
        )
        
        if not file_path:
            return
            
        try:
            # 构建导出数据
            export_data = {
                'export_time': time.strftime('%Y-%m-%d %H:%M:%S'),
                'app_version': 'VitalSync 1.0.0',
                'teammates': []
            }
            
            # 添加所有队友信息
            for member in self.team.members:
                teammate_data = {
                    'name': member.name,
                    'profession': member.profession,
                    'health_bar': {
                        'x1': member.x1,
                        'y1': member.y1,
                        'x2': member.x2,
                        'y2': member.y2
                    },
                    'colors': {
                        'lower': member.hp_color_lower.tolist() if hasattr(member.hp_color_lower, 'tolist') else list(member.hp_color_lower),
                        'upper': member.hp_color_upper.tolist() if hasattr(member.hp_color_upper, 'tolist') else list(member.hp_color_upper)
                    }
                }
                export_data['teammates'].append(teammate_data)
            
            # 写入文件
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(export_data, f, ensure_ascii=False, indent=4)
                
            # 显示成功消息
            InfoBar.success(
                title='导出成功',
                content=f'已导出 {len(self.team.members)} 个队友的识别配置',
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=2000,
                parent=self
            )
        except Exception as e:
            # 显示错误消息
            InfoBar.error(
                title='导出失败',
                content=f'错误: {str(e)}',
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=3000,
                parent=self
            )

    def open_calibration_tool(self):
        """打开一键识别队友工具"""
        # 确保RecognitionUI类可用
        from teammate_recognition import RecognitionUI
        recognition_ui = RecognitionUI()
        recognition_ui.exec_()
        
        # 识别完成后刷新队友预览
        self.load_teammates()
        self.update_teammate_preview()

    def select_recognition_position(self):
        """选择识别位置并保存到校准文件"""
        # 显示选择指南
        guide_dialog = SelectionGuideDialog(
            "选择识别区域",
            "接下来您将选择屏幕上的识别区域，以便程序能够识别队友信息。\n\n请准备好游戏界面，显示所有队友的血条。点击\"开始选择\"后，拖动鼠标框选整个队友显示区域。",
            self
        )
        
        if not guide_dialog.exec():
            return False
        
        try:
            # 导入修改后的模块
            from health_bar_calibration import quick_calibration
            
            # 使用快速校准功能，直接弹出血条数量选择对话框
            success = quick_calibration(self)
            
            if success:
                # 校准完成后刷新队友信息
                self.load_teammates()
                self.update_teammate_preview()
                
                # 更新状态提示
                InfoBar.success(
                    title='位置校准完成',
                    content='队友血条位置已保存到校准文件中',
                    orient=Qt.Horizontal,
                    isClosable=True,
                    position=InfoBarPosition.TOP,
                    duration=2000,
                    parent=self
                )
            else:
                InfoBar.warning(
                    title='校准未完成',
                    content='血条位置校准未完成或被取消',
                    orient=Qt.Horizontal,
                    isClosable=True,
                    position=InfoBarPosition.TOP,
                    duration=2000,
                    parent=self
                )
            return success
        except Exception as e:
            InfoBar.error(
                title='校准错误',
                content=f'校准过程中出错: {str(e)}',
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=3000,
                parent=self
            )
            return False

    def start_recognition_from_calibration(self):
        """从校准文件加载血条位置信息开始识别"""
        try:
            # 先检查校准文件是否正常
            if not self.check_calibration_file():
                self.show_safe_infobar(
                    '校准文件错误',
                    '校准文件不存在或内容无效，请先创建校准文件',
                    'error',
                    3000
                )
                return
                
            # 导入校准工具
            from health_bar_calibration import HealthBarCalibration
            calibration = HealthBarCalibration()
            print("\n=== 开始血条识别流程 ===")
            print(f"校准对象创建完成，可用校准集: {calibration.get_calibration_set_names()}")
            
            # 如果没有可用的校准集，提示用户
            if not calibration.get_calibration_set_names():
                self.show_safe_infobar(
                    '无可用校准数据集',
                    '请先通过"选择识别位置"创建校准数据',
                    'warning',
                    3000
                )
                return
                
            # 创建自定义选择对话框
            try:
                calibration_dialog = CalibrationSelectionMessageBox(calibration, self)
            except Exception as dialog_err:
                print(f"创建对话框时出错: {dialog_err}")
                import traceback
                traceback.print_exc()
                self.show_safe_infobar(
                    '对话框错误',
                    f'创建校准选择对话框时出错: {str(dialog_err)}',
                    'error',
                    3000
                )
                return
                
            # 显示对话框
            try:
                result = calibration_dialog.exec()
                if not result:
                    return
            except Exception as exec_err:
                print(f"显示对话框时出错: {exec_err}")
                import traceback
                traceback.print_exc()
                self.show_safe_infobar(
                    '对话框错误',
                    f'显示校准选择对话框时出错: {str(exec_err)}',
                    'error',
                    3000
                )
                return
            
            # 获取选择的校准数据集
            if not calibration_dialog.selected_calibration:
                return
                
            # 将全局默认血条颜色传递给校准工具（如果有的话）
            if hasattr(self, 'default_hp_color_lower') and hasattr(self, 'default_hp_color_upper') and \
               self.default_hp_color_lower is not None and self.default_hp_color_upper is not None:
                calibration.default_hp_color_lower = self.default_hp_color_lower
                calibration.default_hp_color_upper = self.default_hp_color_upper
            
            # 显示识别进度提示
            self.show_safe_infobar(
                '开始识别',
                f'正在使用校准集 "{calibration_dialog.selected_calibration}" 识别队友...',
                'info',
                1500
            )
            
            # 检查teammateInfoPreview是否存在
            if hasattr(self, 'teammateInfoPreview'):
                # 更新预览区显示识别状态
                self.teammateInfoPreview.setText(f"<html><body style='color: #333333;'>"
                                               f"<div style='font-weight: bold; font-size: 16px;'>正在识别队友...</div>"
                                               f"<div>使用校准集: {calibration_dialog.selected_calibration}</div>"
                                               f"<div>请稍候...</div>"
                                               f"</body></html>")
                QApplication.processEvents()  # 立即更新UI
            
            # 进行队友识别
            self.recognition_in_progress = True
            self.recognition_thread = RecognitionThread(calibration, calibration_dialog.selected_calibration)
            self.recognition_thread.progress_signal.connect(self.update_recognition_progress)
            self.recognition_thread.result_signal.connect(self.update_recognition_results)
            self.recognition_thread.finished.connect(self.recognition_finished)
            self.recognition_thread.start()
        
        except Exception as e:
            # 处理识别过程中的异常
            print(f"识别过程中出错: {e}")
            import traceback
            traceback.print_exc()
            self.show_safe_infobar(
                '识别错误',
                f'识别过程中出错: {str(e)}',
                'error',
                3000
            )
    
    def update_recognition_progress(self, progress_info):
        """更新识别进度显示
        
        参数:
            progress_info: 字典，包含进度信息
        """
        if not hasattr(self, 'teammateInfoPreview'):
            return
            
        current = progress_info.get('current', 0)
        total = progress_info.get('total', 1)
        message = progress_info.get('message', '正在识别...')
        
        # 计算进度百分比
        percentage = int(current * 100 / total)
        
        # 进度条HTML
        progress_html = f"""
        <div style='width:100%; background-color:#444; height:20px; border-radius:10px; margin:10px 0;'>
            <div style='width:{percentage}%; background-color:#3498db; height:20px; border-radius:10px;'></div>
        </div>
        <div style='text-align:center; margin-top:5px;'>{percentage}% ({current}/{total})</div>
        """
        
        # 更新预览显示
        self.teammateInfoPreview.setText(f"<html><body style='color: white;'>"
                                       f"<div style='font-weight: bold; font-size: 16px;'>识别进行中</div>"
                                       f"<div style='margin:8px 0;'>{message}</div>"
                                       f"{progress_html}"
                                       f"</body></html>")
        QApplication.processEvents()  # 立即更新UI
    
    def update_recognition_results(self, teammates_data):
        """更新识别结果显示，并更新到队友数据和血条监控界面
        
        参数:
            teammates_data: 识别到的队友列表，每个元素是一个包含 'name' 和 'profession' 的字典
        """
        if not hasattr(self, 'teammateInfoPreview'):
            return
            
        html = "<html><body style='color: #333333;'>" # 适应浅色背景的文字颜色
        html += "<div style='font-weight: bold; font-size: 16px; margin-bottom: 10px;'>识别结果</div>"
        
        updated_members_count = 0

        if not teammates_data:
            html += "<div>未识别到任何队友</div>"
        else:
            for recognized_data in teammates_data:
                name = recognized_data.get('name')
                new_profession = recognized_data.get('profession', '未知') # 获取识别到的职业
                health_bar_info = recognized_data.get('health_bar', {})

                # 更新到 self.team.members
                member_updated = False
                for member_obj in self.team.members:
                    if member_obj.name == name:
                        if member_obj.profession != new_profession:
                            member_obj.profession = new_profession
                            
                            # 如果没有设置过颜色，同时应用默认颜色
                            if ((member_obj.hp_color_lower is None or len(member_obj.hp_color_lower) == 0) or \
                                (member_obj.hp_color_upper is None or len(member_obj.hp_color_upper) == 0)) and \
                               self.default_hp_color_lower is not None and self.default_hp_color_upper is not None:
                                import numpy as np
                                member_obj.hp_color_lower = np.copy(self.default_hp_color_lower)
                                member_obj.hp_color_upper = np.copy(self.default_hp_color_upper)
                            
                            member_obj.save_config() # 保存更新后的配置
                            updated_members_count += 1
                        member_updated = True
                        break
                
                # 如果是识别到的新队友且不在当前队伍中，可以选择是否添加
                # 为简化，当前逻辑仅更新已有同名队友的职业
                # if not member_updated:
                #     # 可以在这里添加逻辑：如果识别到一个全新的队友，是否自动添加到self.team
                #     # new_member = self.team.add_member(name, new_profession)
                #     # ... 设置其血条坐标、颜色等 ...
                #     # new_member.save_config()
                #     pass # 暂不处理新增，仅更新已有

                # --- HTML 预览部分（保持不变，使用识别到的职业） ---
                card_bg = "#ffffff"  # 白色背景
                border = "1px solid #e0e0e0" # 浅灰色边框
                
                position = f"({health_bar_info.get('x1', 0)}, {health_bar_info.get('y1', 0)}) - "
                position += f"({health_bar_info.get('x2', 0)}, {health_bar_info.get('y2', 0)})"
                
                # 尝试获取职业图标路径 (与 update_teammate_preview 逻辑一致)
                icon_html = ""
                profession_icon_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "profession_icons", f"{new_profession}.png")
                if os.path.exists(profession_icon_path):
                    icon_uri = QUrl.fromLocalFile(profession_icon_path).toString()
                    icon_html = f"<img src='{icon_uri}' width='24' height='24' style='vertical-align: middle; margin-right: 8px;'/>"

                html += f"""
                <div style='background: {card_bg}; border: {border}; border-radius: 8px; padding: 10px; margin-bottom: 12px;'>
                    <div style='font-weight: bold; font-size: 16px; margin-bottom: 8px;'>
                        {icon_html}{name} <span style='color: #3498db;'>({new_profession})</span>
                    </div>
                    <div style='margin-bottom: 6px;'>
                        <span style='color: #666666;'>血条位置:</span> {position}
                    </div>
                </div>
                """
        
        html += "</body></html>"
        self.teammateInfoPreview.setText(html)
        QApplication.processEvents()  # 立即更新UI

        if updated_members_count > 0:
            InfoBar.success(
                title='职业信息已更新',
                content=f'已成功更新 {updated_members_count} 名队友的职业信息。',
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=2500,
                parent=self
            )
            # 触发依赖职业信息的UI更新
            self.update_teammate_preview() # 刷新"队员识别"页面的完整预览（如果有其他信息源）
            self.init_health_bars_ui()   # 刷新"血条监控"页面的血条（角色等信息）
    
    def recognition_finished(self):
        """识别完成后的回调函数"""
        self.recognition_in_progress = False
        
        # 安全显示识别完成消息
        self.show_safe_infobar(
            '识别完成',
            '队友识别已完成。请检查识别结果。',
            'success',
            2000
        )
    
    def stop_recognition(self):
        """停止正在进行的识别"""
        if hasattr(self, 'recognition_thread') and self.recognition_thread and self.recognition_thread.isRunning():
            self.recognition_thread.requestInterruption()
            self.recognition_thread.wait(1000)  # 等待最多1秒
            
            # 安全显示停止消息
            self.show_safe_infobar(
                '已停止',
                '识别过程已停止',
                'warning',
                2000
            )
            
            self.recognition_in_progress = False
        else:
            # 安全显示消息
            self.show_safe_infobar(
                '提示',
                '没有正在进行的识别任务',
                'info',
                2000
            )

    def update_health_display(self, health_data):
        """更新血量显示
        
        参数:
            health_data: 包含队友血量信息的列表 [(名称, 血量百分比, 是否存活),...]
        """
        if not hasattr(self, 'health_bars_frame'):
            return  # 如果界面还未初始化，直接返回
            
        print(f"UI线程收到血量更新: {health_data}") # 确认UI线程收到数据
            
        # --- 修改：将 health_data 转为字典以便按名称查找 ---
        health_data_map = {item[0]: (item[1], item[2]) for item in health_data} # name: (health_percentage, is_alive)

        # --- 修改：获取在UI中按坐标排序的队员列表 ---
        # 确保 self.team.members 存在且不为空，否则 sorted 可能报错或产生意外结果
        if not self.team or not self.team.members:
            # 如果没有队员，但收到了 health_data (不太可能，但作为防御)，或者需要清空
            # 沿用之前的逻辑：如果 health_data 为空，则清空/重置UI
            if not health_data:
                 # 清理所有现有的血条 (如果 self.team.members 为空，这个循环不会执行)
                # 这里的逻辑需要确保即使 self.team.members 为空，如果UI上之前有残留，也能清理
                # 这通常由 init_health_bars_ui 在队员列表变空时处理
                # 为简单起见，如果 self.team.members 为空，我们假设UI也应为空或由 init_health_bars_ui 处理
                pass # init_health_bars_ui 应该已经处理了无队员的情况
            self.health_bars_frame.update()
            QApplication.processEvents()
            return

        sorted_ui_members = sorted(self.team.members, key=lambda m: (m.y1, m.x1))

        if not health_data:
            # 当监控停止或数据为空时，清空或重置UI (针对已排序的UI元素)
            for ui_idx, member_obj_in_ui in enumerate(sorted_ui_members):
                member_frame = self.health_bars_frame.findChild(QFrame, f"member_card_{ui_idx}")
                if not member_frame:
                    # print(f"错误: 清理时找不到队员 (UI索引 {ui_idx}) 的界面元素")
                    continue

                health_bar = member_frame.findChild(QFrame, f"health_bar_{ui_idx}")
                value_label = member_frame.findChild(StrongBodyLabel, f"value_label_{ui_idx}")
                debug_label = member_frame.findChild(QLabel, f"debug_label_{ui_idx}")
                name_label = member_frame.findChild(StrongBodyLabel, f"name_label_{ui_idx}")

                if health_bar:
                    health_bar.setFixedWidth(0)
                    health_bar.setStyleSheet("background-color: #555; border-radius: 3px;")
                if value_label:
                    value_label.setText("0.0%")
                    value_label.setStyleSheet("color: #777; font-weight: bold; font-size: 15px;")
                if debug_label:
                    debug_label.setText("dbg: --")
                if name_label: # 重置名称标签状态
                    name_label.setStyleSheet("font-size: 14px; font-weight: bold;") # 恢复默认样式
            self.health_bars_frame.update()
            QApplication.processEvents()
            return

        # --- 修改：遍历按坐标排序的UI队员列表 ---
        for ui_idx, member_in_ui_order in enumerate(sorted_ui_members):
            current_member_name = member_in_ui_order.name
            
            member_frame = self.health_bars_frame.findChild(QFrame, f"member_card_{ui_idx}")
            if not member_frame:
                print(f"错误: 更新时找不到队员 '{current_member_name}' (UI索引 {ui_idx}) 的界面元素 member_card")
                continue
                
            health_bar = member_frame.findChild(QFrame, f"health_bar_{ui_idx}")
            value_label = member_frame.findChild(StrongBodyLabel, f"value_label_{ui_idx}")
            name_label = member_frame.findChild(StrongBodyLabel, f"name_label_{ui_idx}")
            debug_label = member_frame.findChild(QLabel, f"debug_label_{ui_idx}")

            if not health_bar or not value_label or not name_label:
                print(f"错误: 队员 '{current_member_name}' (UI索引 {ui_idx}) 的血条、数值或名称标签元素缺失")
                # 即使部分组件缺失，也尝试更新其他存在的组件
                # continue # 移除 continue，尝试更新能找到的组件

            # 检查当前队员是否在传入的 health_data 中
            if current_member_name not in health_data_map:
                print(f"UI 更新: 队员 '{current_member_name}' (UI 索引 {ui_idx}) 在当前 health_data 中未找到。设置为N/A状态。")
                if health_bar:
                    health_bar.setFixedWidth(0)
                    health_bar.setStyleSheet("background-color: #555; border-radius: 3px;")
                if value_label:
                    value_label.setText("N/A")
                    value_label.setStyleSheet("color: #777; font-weight: bold; font-size: 15px;")
                if name_label:
                    name_label.setText(current_member_name) # 确保名字正确显示
                    name_label.setStyleSheet("color: #777777; font-size: 14px; font-weight: bold;") # 暗色表示N/A
                if debug_label:
                    debug_label.setText("dbg: N/A")
                continue # 处理下一个UI队员

            # 如果找到了数据，则解包
            health_percentage, is_alive = health_data_map[current_member_name]
            
            if debug_label:
                # member_in_ui_order 是 TeamMember 对象，它应该有 health_percentage 属性
                if hasattr(member_in_ui_order, 'health_percentage'):
                    debug_label.setText(f"内存:{member_in_ui_order.health_percentage:.1f}%")
                else:
                    debug_label.setText("内存:N/A")

            current_hp_from_signal = health_percentage
            
            # 根据存活状态和血量设置颜色
            final_color = "#2ecc71" # 默认健康绿色
            if not is_alive:
                final_color = "#777777"  # 灰色表示离线/死亡
                current_hp_from_signal = 0.0 # 死亡时血量视为0
            elif current_hp_from_signal <= 30:
                final_color = "#e74c3c"  # 红色表示危险
            elif current_hp_from_signal <= 60:
                final_color = "#f39c12"  # 黄色表示警告
            
            SCALE_FACTOR = 3
            MAX_WIDTH = 300 
            
            new_width = min(int(current_hp_from_signal * SCALE_FACTOR), MAX_WIDTH)
            if new_width < 0: new_width = 0
            
            if health_bar:
                current_stylesheet = health_bar.styleSheet()
                new_stylesheet = f"background-color: {final_color}; border-radius: 3px;"
                current_bar_width = health_bar.width()

                if abs(current_bar_width - new_width) > 1e-9 or current_stylesheet != new_stylesheet: # 比较浮点数宽度
                    # print(f"UI更新: 队员 '{current_member_name}' (UI {ui_idx}), 血量: {current_hp_from_signal:.1f}%, 旧宽:{current_bar_width} -> 新宽:{new_width}")
                    health_bar.setStyleSheet(new_stylesheet)
                    health_bar.setFixedWidth(new_width)
                    
                    parent_widget = health_bar.parentWidget() 
                    if parent_widget and parent_widget.layout():
                        parent_widget.layout().invalidate() 
                        parent_widget.updateGeometry() 
                    if member_frame: member_frame.update()
            
            if value_label:
                value_label.setText(f"{current_hp_from_signal:.1f}%")
                value_label.setStyleSheet(f"color: {final_color}; font-weight: bold; font-size: 15px;")
            
            if name_label:
                name_label_text = current_member_name # 使用来自 UI 顺序的队员名
                if name_label.text() != name_label_text:
                    name_label.setText(name_label_text)
                
                if not is_alive:
                    name_label.setStyleSheet("color: #777777; font-size: 14px; font-weight: bold;")
                else:
                    # 根据血量设置名字颜色（可选，如果需要更明显的区分）
                    # if current_hp_from_signal <= 30:
                    #     name_label.setStyleSheet(f"color: {final_color}; font-size: 14px; font-weight: bold;")
                    # else:
                    name_label.setStyleSheet("font-size: 14px; font-weight: bold;") # 默认样式
            
            if health_bar: health_bar.update()
            if value_label: value_label.update()
            if name_label: name_label.update()
            if debug_label: debug_label.update()

        self.health_bars_frame.update()
        QApplication.processEvents()
        
        # check_health_warnings 使用原始的 health_data，这部分不需要修改
        # 因为它关心的是实际的血量数据，而不是UI顺序
        low_hp_count = 0
        total_alive = 0
        # 重新从 health_data_map 的值计算，以确保与UI更新的数据源一致
        for _, (hp, alive_status) in health_data_map.items():
            if alive_status:
                total_alive += 1
                if hp <= 30: # 使用30%作为低血量标准
                    low_hp_count += 1
        
        self.check_health_warnings(health_data, low_hp_count, total_alive)

    def check_health_warnings(self, health_data, low_hp_count, total_alive):
        """检查并播放血量警告语音
        
        参数:
            health_data: 血量数据列表，每项为(名称, 血量百分比, 是否存活)
            low_hp_count: 低血量队友数量
            total_alive: 存活队友总数
        """
        # 如果语音警告设置不存在，直接返回
        if not hasattr(self, 'low_health_warning_enabled') or not self.low_health_warning_enabled:
            return
            
        # 获取当前时间
        current_time = time.time()
        
        # 初始化语音警告上次播放时间（如果不存在）
        if not hasattr(self, 'last_voice_warning_time'):
            self.last_voice_warning_time = {}
        
        # 获取语音设置
        voice = self.get_selected_voice(self.voiceTypeCombo)
        
        # 团队危险警告（多人低血量）
        if hasattr(self, 'team_danger_warning_enabled') and self.team_danger_warning_enabled:
            # 检查是否达到低血量队友数量阈值
            low_health_count_threshold = getattr(self, 'team_warning_threshold', 2)
            
            if low_hp_count >= low_health_count_threshold:
                # 检查冷却时间
                team_warning_key = "team_danger"
                last_time = self.last_voice_warning_time.get(team_warning_key, 0)
                warning_cooldown = getattr(self, 'warning_cooldown', 5.0)
                
                if current_time - last_time >= warning_cooldown:
                    # 格式化警告文本
                    warning_template = getattr(self, 'team_warning_text', "警告，团队状态危险，{count}名队友血量过低")
                    warning_text = warning_template.format(count=low_hp_count, total=total_alive)
                    
                    # 播放警告
                    self.play_speech_threaded(warning_text, voice)
                    
                    # 更新最后播放时间
                    self.last_voice_warning_time[team_warning_key] = current_time
                    return  # 如果播放了团队警告，不再播放个人警告
        
        # 个人低血量警告
        if hasattr(self, 'low_health_warning_enabled') and self.low_health_warning_enabled:
            # 获取警告阈值
            warning_threshold = getattr(self, 'warning_threshold', 30.0)
            
            # 遍历所有队友
            for name, health, is_alive in health_data:
                if is_alive and health <= warning_threshold:
                    # 检查冷却时间
                    teammate_warning_key = f"low_health_{name}"
                    last_time = self.last_voice_warning_time.get(teammate_warning_key, 0)
                    warning_cooldown = getattr(self, 'warning_cooldown', 5.0)
                    
                    if current_time - last_time >= warning_cooldown:
                        # 获取职业
                        profession = "未知"
                        for member in self.team.members:
                            if member.name == name:
                                profession = member.profession
                                break
                        
                        # 格式化警告文本
                        warning_template = getattr(self, 'warning_text', "{name}血量过低，仅剩{health}%")
                        warning_text = warning_template.format(name=name, health=round(health), profession=profession)
                        
                        # 播放警告
                        self.play_speech_threaded(warning_text, voice)
                        
                        # 更新最后播放时间
                        self.last_voice_warning_time[teammate_warning_key] = current_time
                        break  # 一次只警告一个队友

    def update_monitor_status(self, status_message):
        """更新监控状态信息
        
        参数:
            status_message: 状态消息文本
        """
        if not hasattr(self, 'monitor_status_label'):
            return  # 如果界面还未初始化，直接返回
            
        # 更新状态标签
        self.monitor_status_label.setText(status_message)
        
        # 根据关键词设置不同的状态颜色
        if "错误" in status_message or "失败" in status_message:
            self.monitor_status_label.setStyleSheet("color: #e74c3c;")  # 红色
        elif "警告" in status_message:
            self.monitor_status_label.setStyleSheet("color: #f39c12;")  # 黄色
        elif "成功" in status_message or "启动" in status_message or "启用" in status_message or "禁用" in status_message: # 添加启用禁用的判断
            self.monitor_status_label.setStyleSheet("color: #2ecc71;")  # 绿色
        else:
            self.monitor_status_label.setStyleSheet("color: #3498db;")  # 蓝色

    def toggle_auto_click_low_health(self, checked):
        if hasattr(self, 'health_monitor'):
            self.health_monitor.auto_select_enabled = checked
            if hasattr(self.health_monitor, 'save_auto_select_config'):
                self.health_monitor.save_auto_select_config() # 保存这个状态
            status_message = f"自动点击低血量队友功能已{'启用' if checked else '禁用'}"
            self.update_monitor_status(status_message) # 更新状态栏信息
            print(status_message)

    def closeEvent(self, event):
        """重写关闭事件，确保清理资源"""
        try:
            # 停止监控
            if hasattr(self, 'health_monitor'):
                self.health_monitor.stop_monitoring()
                
            # 停止语音队列工作线程
            if hasattr(self, 'speech_worker_thread') and self.speech_worker_thread.is_alive():
                # 向队列添加哨兵值，通知线程退出
                if hasattr(self, 'speech_queue'):
                    self.speech_queue.put(None)
                # 等待线程完成当前任务，最多等待1秒
                self.speech_worker_thread.join(1.0)
                
            # 保存设置
            self.save_settings()
            
            # 调用PyQt基类方法
            super().closeEvent(event)
            
            # 确保pygame已退出
            pygame.quit()
            
            # 安全显示退出消息
            self.show_safe_infobar('程序已关闭', '感谢使用VitalSync', 'info', 1000)
            
        except Exception as e:
            print(f"关闭时出错: {e}")
            # 调用基类方法确保应用关闭
            super().closeEvent(event)

    def update_health_threshold(self, value, label=None):
        """更新自动点击低血量队友的血条阈值"""
        if hasattr(self, 'health_monitor'):
            self.health_monitor.health_threshold = value
            if label:
                label.setText(f'血条阈值: {value}%')
            self.update_monitor_status(f'自动点击阈值已更新为 {value}%')
            # 保存到配置
            if hasattr(self.health_monitor, 'save_auto_select_config'):
                self.health_monitor.save_auto_select_config()

    def install_hotkey_event_filter(self, edit, other_edit, which):
        edit.setReadOnly(False)
        edit.setText('请按下新快捷键...')
        edit.setFocus()
        self.hotkeyStatusLabel.setText('请按下新快捷键')
        self.hotkeyStatusLabel.setStyleSheet("color: #3498db; font-weight: bold;")
        self._hotkey_filter = HotkeyEventFilter(self, edit, other_edit, which, self.hotkeyStatusLabel, self.health_monitor)
        edit.installEventFilter(self._hotkey_filter)

    def play_speech_threaded(self, text, voice='zh-CN-XiaoxiaoNeural'):
        """将语音任务放入队列，由工作线程处理"""
        # 从实例属性获取当前的速率和音量参数
        rate = self.voice_rate_param
        volume = self.voice_volume_param
        
        # 创建任务元组
        task = (text, voice, rate, volume)
        print(f"加入语音任务到队列: {text[:30]}... (voice={voice}, rate={rate}, volume={volume})")
        self.speech_queue.put(task)

    def _execute_speech(self, text, voice='zh-CN-XiaoxiaoNeural', rate='+0%', volume='+0%'):
        """使用 edge-tts 合成语音并使用 pygame.mixer.Sound 播放 (由工作线程调用)
        
        语音合成 -> 加载 Sound -> 查找空闲 Channel -> 播放 -> 注册结束事件 -> 返回
        实际的资源清理由 _process_pygame_events 通过定时器处理
        """
        print(f"[{threading.current_thread().name}] _execute_speech: voice={voice}, rate={rate}, volume={volume}, text='{text[:30]}...' ")
        output_path = None
        temp_file = None
        sound = None
        channel = None
        
        try:
            # 1. 创建唯一的临时文件
            temp_file = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
            output_path = temp_file.name
            temp_file.close()
            print(f"[{threading.current_thread().name}] 创建唯一临时文件: {output_path}")

            # 2. 异步生成语音文件
            async def _generate_speech_async():
                try:
                    print(f"[{threading.current_thread().name}] 尝试生成语音到 {output_path}...")
                    communicate = edge_tts.Communicate(text, voice=voice, rate=rate, volume=volume)
                    await communicate.save(output_path)
                    if os.path.exists(output_path):
                        print(f"[{threading.current_thread().name}] 语音文件 {output_path} 生成成功.")
                        return output_path
                    else:
                        print(f"[{threading.current_thread().name}] 错误: communicate.save 调用后文件 {output_path} 不存在!")
                        return None
                except edge_tts.NoAudioReceived:
                     print(f"[{threading.current_thread().name}] edge-tts 错误: 没有收到音频数据。 voice='{voice}'无效?")
                     return None
                except Exception as e:
                    print(f'[{threading.current_thread().name}] edge-tts 语音合成时发生异常: {e}')
                    return None

            # --- 同步执行异步生成 ---
            generated_path = None
            try:
                print(f"[{threading.current_thread().name}] 准备运行 asyncio 生成语音...")
                generated_path = asyncio.run(_generate_speech_async())
                print(f"[{threading.current_thread().name}] asyncio 运行完成, generated_path = {generated_path}")
            except RuntimeError as e:
                if "cannot run event loop while another loop is running" in str(e):
                    print(f"[{threading.current_thread().name}] 检测到现有事件循环...")
                    try:
                        loop = asyncio.get_event_loop()
                        generated_path = loop.run_until_complete(_generate_speech_async())
                        print(f"[{threading.current_thread().name}] run_until_complete 完成, generated_path = {generated_path}")
                    except Exception as inner_e:
                        print(f"[{threading.current_thread().name}] 现有事件循环运行失败: {inner_e}")
                else:
                    print(f"[{threading.current_thread().name}] asyncio RuntimeError: {e}")
            except Exception as e:
                 print(f"[{threading.current_thread().name}] 语音生成未知错误: {e}")

            # 3. 加载和播放 (如果生成成功)
            if generated_path and os.path.exists(generated_path):
                print(f"[{threading.current_thread().name}] 准备加载和播放 {generated_path}")
                try:
                    if not pygame.mixer.get_init():
                        print(f"[{threading.current_thread().name}] Pygame mixer 未初始化，尝试重新初始化...")
                        pygame.mixer.init()
                        pygame.mixer.set_num_channels(16) # 确保声道已设置

                    # 加载为 Sound 对象
                    sound = pygame.mixer.Sound(generated_path)
                    print(f"[{threading.current_thread().name}] 文件 {generated_path} 已加载为 Sound 对象.")
                    
                    # 查找一个空闲的 Channel
                    channel = pygame.mixer.find_channel(True) # force=True 会强制获取一个声道
                    if channel:
                        print(f"[{threading.current_thread().name}] 获取到空闲声道: {channel}")
                        
                        # 存储信息以便后续清理 - 使用 channel 对象本身作为键
                        self.active_speech[channel] = {'filename': generated_path, 'sound': sound}
                        
                        # 播放声音
                        channel.play(sound)
                        print(f"[{threading.current_thread().name}] 在声道 {channel} 上开始播放...")
                        
                        # ！！！关键：不再等待播放结束，直接返回，让工作线程处理下一个任务
                        output_path = None # 清空 output_path 防止 finally 块尝试删除
                        return # <--- Worker thread is now free!
                        
                    else:
                        print(f"[{threading.current_thread().name}] 错误: 无法找到空闲的 Pygame 声道!")

                except pygame.error as e:
                    print(f"[{threading.current_thread().name}] Pygame 加载/播放 Sound 失败: {e}")
                except Exception as e:
                    print(f"[{threading.current_thread().name}] 加载/播放过程中发生未知错误: {e}")
            
            # 如果生成失败或播放未成功启动，则 generated_path 仍然指向临时文件
            output_path = generated_path # 确保 finally 块能清理生成失败的文件
            
        finally:
            # 4. 最终清理 (只清理那些未成功启动播放的临时文件)
            # 成功启动播放的文件由 _process_pygame_events 清理
            if output_path and os.path.exists(output_path):
                print(f"[{threading.current_thread().name}] _execute_speech 清理：删除未播放或生成失败的文件 {output_path}...")
                try:
                    os.remove(output_path)
                    print(f"[{threading.current_thread().name}] 文件 {output_path} 已删除.")
                except Exception as e:
                    print(f"[{threading.current_thread().name}] _execute_speech 清理时删除文件 {output_path} 失败: {e}")
            elif output_path:
                 print(f"[{threading.current_thread().name}] _execute_speech 清理：文件 {output_path} 已不存在，无需删除.")

    def _process_pygame_events(self):
        """由 QTimer 调用，处理 Pygame 事件队列和检查播放结束状态。"""
        if not pygame.get_init() or not pygame.mixer.get_init():
            return # Pygame 未初始化，不做处理

        # 移除 pygame.event.get() 循环和基于 USEREVENT 的检查

        finished_channels = []
        # 迭代活动声道的副本，因为我们可能在循环中修改字典
        for channel, speech_info in list(self.active_speech.items()):
            if not channel.get_busy():
                print(f"主线程定时器: 检测到声道 {channel} 播放结束。")
                filename = speech_info.get('filename')
                
                print(f"主线程定时器: 清理声道 {channel} 的资源，文件: {filename}")
                
                # 尝试删除文件
                if filename and os.path.exists(filename):
                    try:
                        os.remove(filename)
                        print(f"主线程定时器: 临时文件 {filename} 已删除.")
                    except PermissionError:
                        print(f"主线程定时器: 删除失败 - 无法删除临时文件 {filename}，权限不足或仍被占用。")
                    except Exception as e:
                        print(f"主线程定时器: 删除临时文件 {filename} 时发生其他错误: {e}")
                elif filename:
                    print(f"主线程定时器: 清理时文件 {filename} 已不存在，无需删除。")

                finished_channels.append(channel) # 标记此声道为完成

        # 从 active_speech 字典中移除已完成的声道
        for channel in finished_channels:
            if channel in self.active_speech:
                del self.active_speech[channel]
                print(f"主线程定时器: 已从 active_speech 移除声道 {channel} 的记录。")

        # 可以保留 pygame.event.pump() 来确保 Pygame 内部事件处理正常进行
        pygame.event.pump()

    def _speech_worker_loop(self):
        """语音播报工作线程的主循环"""
        print("语音工作线程已启动。")
        while True:
            try:
                task = self.speech_queue.get() # 阻塞直到获取任务
                if task is None: # 收到停止信号
                    print("语音工作线程收到停止信号，准备退出。")
                    self.speech_queue.task_done()
                    break
                
                text, voice, rate, volume = task
                print(f"语音工作线程处理任务: {text[:30]}...")
                self._execute_speech(text, voice, rate, volume) # 调用实际执行方法
                self.speech_queue.task_done()
            except Exception as e:
                print(f"语音工作线程发生错误: {e}")
                # 发生错误时，如果任务不是 None，也需要标记完成以防队列阻塞
                if task is not None:
                    try:
                        self.speech_queue.task_done()
                    except ValueError: # 如果任务已完成，会抛出 ValueError
                        pass 
        print("语音工作线程已退出。")

    def get_selected_voice(self, combo):
        """根据下拉框选择返回 edge-tts 语音名"""
        # 更新映射的键以匹配下拉框中的新名称，并移除英文语音
        mapping = {
            # 标准普通话
            '晓晓 (普通话女)': 'zh-CN-XiaoxiaoNeural',
            '云希 (普通话男)': 'zh-CN-YunxiNeural',
            '晓伊 (普通话女)': 'zh-CN-XiaoyiNeural',
            '云健 (普通话男)': 'zh-CN-YunjianNeural',
            # 台湾普通话
            '晓臻 (台湾女)':   'zh-TW-HsiaoChenNeural',
            '雲哲 (台湾男)':   'zh-TW-YunJheNeural',
            # 香港粤语
            '晓佳 (香港女)':   'zh-HK-HiuGaaiNeural',
            '雲龍 (香港男)':   'zh-HK-WanLungNeural',
            # 英文语音条目已删除
        }
        text = combo.currentText()
        # 如果找不到映射（理论上不应发生，因为选项来自 addItems），返回默认的晓晓
        return mapping.get(text, 'zh-CN-XiaoxiaoNeural')

    def update_voice_rate(self, value):
        """更新语音速率参数并保存设置"""
        rate_percent = value * 10 - 50
        self.voice_rate_param = f"{rate_percent:+}%"
        # print(f"语音速率更新为: {self.voice_rate_param}") # 调试信息
        self.save_settings() # 保存更改

    def update_voice_volume(self, value):
        """更新语音音量参数并保存设置"""
        volume_percent = value - 50
        self.voice_volume_param = f"{volume_percent:+}%"
        # print(f"语音音量更新为: {self.voice_volume_param}") # 调试信息
        self.save_settings() # 保存更改
    def load_settings(self):
        """加载应用程序设置"""
        # 使用配置管理器获取配置
        config_manager = get_config()
        
        try:
            # 确保默认配置存在
            if not config_manager.get_json(''):
                from config_defaults import DEFAULT_CONFIG
                config_manager.set_json('', DEFAULT_CONFIG)
                config_manager.save_config()
                print("已创建默认配置文件")
            
            # 设置默认滑块值（如果配置无法加载）
            self.voiceSpeedSlider.setValue(5)
            self.volumeSlider.setValue(80)
                
            # 加载语音设置
            voice_settings = config_manager.get_json('voice_settings', {})
            if voice_settings:
                rate_value = voice_settings.get('rate', 5) # 默认值 5
                volume_value = voice_settings.get('volume', 80) # 默认值 80
                
                self.voiceSpeedSlider.setValue(rate_value)
                self.volumeSlider.setValue(volume_value)
                
                # 加载选中的语音类型
                selected_voice_name = voice_settings.get('selected_voice')
                if selected_voice_name:
                    index = self.voiceTypeCombo.findText(selected_voice_name)
                    if index >= 0:
                        self.voiceTypeCombo.setCurrentIndex(index)
            
            # 加载语音警告设置
            alert_settings = config_manager.get_json('low_health_alert_settings', {})
            if alert_settings:
                # 低血量警告设置
                self.low_health_warning_enabled = alert_settings.get('enabled', False)
                self.low_health_warning_checkbox.setChecked(self.low_health_warning_enabled)
                
                self.warning_threshold = float(alert_settings.get('threshold', 30.0))
                self.warning_threshold_spinbox.setValue(int(self.warning_threshold))
                
                self.warning_cooldown = float(alert_settings.get('cooldown', 5.0))
                self.warning_cooldown_spinbox.setValue(int(self.warning_cooldown))
                
                self.warning_text = alert_settings.get('warning_text', "{name}血量过低，仅剩{health}%")
                self.warning_text_edit.setText(self.warning_text)
                
                # 团队危险警告设置
                self.team_danger_warning_enabled = alert_settings.get('team_danger_enabled', False)
                self.team_danger_warning_checkbox.setChecked(self.team_danger_warning_enabled)
                
                self.team_warning_threshold = alert_settings.get('team_danger_threshold', 2)
                self.team_warning_threshold_spinbox.setValue(self.team_warning_threshold)
                
                self.team_warning_text = alert_settings.get('team_danger_text', "警告，团队状态危险，{count}名队友血量过低")
                self.team_warning_text_edit.setText(self.team_warning_text)
                
                print("已加载语音警告设置")

            print("设置已从配置管理器加载。")
        except Exception as e:
            print(f"加载配置时发生错误: {e}")
            InfoBar.error(
                title='加载设置失败',
                content=f'无法加载配置: {e}',
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP_RIGHT,
                duration=3000,
                parent=self
            )

    def save_settings(self):
        """保存应用程序设置"""
        # 使用配置管理器保存设置
        config_manager = get_config()
        
        try:
            # 获取当前语音设置值
            rate_value = self.voiceSpeedSlider.value()
            volume_value = self.volumeSlider.value()
            selected_voice_name = self.voiceTypeCombo.currentText()

            # 更新配置字典
            voice_settings = {
                'rate': rate_value,
                'volume': volume_value,
                'selected_voice': selected_voice_name # 保存选中的语音名称
            }
            config_manager.set_json('voice_settings', voice_settings)

            # 保存语音警告设置
            if hasattr(self, 'low_health_warning_enabled'):
                alert_settings = {
                    'enabled': self.low_health_warning_enabled,
                    'threshold': self.warning_threshold,
                    'cooldown': self.warning_cooldown,
                    'warning_text': self.warning_text,
                    'team_danger_enabled': self.team_danger_warning_enabled,
                    'team_danger_threshold': self.team_warning_threshold,
                    'team_danger_text': self.team_warning_text
                }
                config_manager.set_json('low_health_alert_settings', alert_settings)

            # 保存配置
            config_manager.save_config()
            
        except Exception as e:
            print(f"保存配置文件时发生错误: {e}")
            # 显示一个错误 InfoBar
            InfoBar.error(
                title='保存设置失败',
                content=f'无法写入配置: {e}',
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP_RIGHT,
                duration=3000,
                parent=self
            )

    def toggle_low_health_warning(self, checked):
        """切换低血量语音警告的启用状态"""
        self.low_health_warning_enabled = checked
        status_message = f"低血量语音警告已{'启用' if checked else '禁用'}"
        self.update_monitor_status(status_message)
        self.save_warning_settings()

    def toggle_team_danger_warning(self, checked):
        """切换团队危险语音警告的启用状态"""
        self.team_danger_warning_enabled = checked
        status_message = f"团队危险语音警告已{'启用' if checked else '禁用'}"
        self.update_monitor_status(status_message)
        self.save_warning_settings()

    def update_warning_threshold(self, value):
        """更新低血量警告阈值"""
        self.warning_threshold = float(value)
        self.save_warning_settings()

    def update_warning_cooldown(self, value):
        """更新警告冷却时间"""
        self.warning_cooldown = float(value)
        self.save_warning_settings()

    def update_warning_text(self, text):
        """更新低血量警告文本模板"""
        self.warning_text = text
        self.save_warning_settings()

    def update_team_warning_threshold(self, value):
        """更新团队警告阈值"""
        self.team_warning_threshold = value
        self.save_warning_settings()

    def update_team_warning_text(self, text):
        """更新团队警告文本模板"""
        self.team_warning_text = text
        self.save_warning_settings()

    def save_warning_settings(self):
        """保存语音警告设置到配置文件"""
        # 使用配置管理器保存警告设置
        config_manager = get_config()
        
        try:
            # 更新语音警告设置
            alert_settings = {
                'enabled': self.low_health_warning_enabled,
                'threshold': self.warning_threshold,
                'cooldown': self.warning_cooldown,
                'warning_text': self.warning_text,
                'team_danger_enabled': self.team_danger_warning_enabled,
                'team_danger_threshold': self.team_warning_threshold,
                'team_danger_text': self.team_warning_text
            }
            config_manager.set_json('low_health_alert_settings', alert_settings)
            
            # 保存配置
            config_manager.save_config()
            print("语音警告设置已保存")
            
        except Exception as e:
            print(f"保存语音警告设置失败: {e}")
            # 显示一个错误 InfoBar
            InfoBar.error(
                title='保存警告设置失败',
                content=f'无法保存语音警告设置: {e}',
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP_RIGHT,
                duration=3000,
                parent=self
            )

    def initVoiceSettingsInterface(self):
        """初始化语音设置界面"""
        layout = QVBoxLayout(self.voiceSettingsInterface)
        layout.setSpacing(16)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # 语音播报卡片
        voiceCard = HeaderCardWidget(self.voiceSettingsInterface) # 父级改为 voiceSettingsInterface
        voiceCard.setTitle("语音播报设置")
        
        voiceLayout = QVBoxLayout()
        voiceLayout.setSpacing(12)
        
        # 启用语音播报开关
        enableVoiceLayout = QHBoxLayout()
        enableVoiceLabel = BodyLabel("启用语音播报:")
        enableVoiceSwitch = SwitchButton()
        enableVoiceSwitch.setChecked(True)
        enableVoiceLayout.addWidget(enableVoiceLabel)
        enableVoiceLayout.addWidget(enableVoiceSwitch)
        enableVoiceLayout.addStretch(1)
        
        # 语音类型选择
        voiceTypeLayout = QHBoxLayout()
        voiceTypeLabel = BodyLabel("语音类型:")
        self.voiceTypeCombo = ComboBox() # 保持为实例属性
        self.voiceTypeCombo.addItems([
            "晓晓 (普通话女)", "云希 (普通话男)",
            "晓伊 (普通话女)", "云健 (普通话男)",
            "晓臻 (台湾女)",   "雲哲 (台湾男)",
            "晓佳 (香港女)",   "雲龍 (香港男)",
        ])
        voiceTypeLayout.addWidget(voiceTypeLabel)
        voiceTypeLayout.addWidget(self.voiceTypeCombo)
        voiceTypeLayout.addStretch(1)
        
        # 语音设置组
        voiceSettingsGroup = QGroupBox("语音参数", self.voiceSettingsInterface) # 父级改为 voiceSettingsInterface
        voiceSettingsLayout = QVBoxLayout()
        
        # 语速调节
        voiceSpeedLayout = QHBoxLayout()
        voiceSpeedLabel = BodyLabel("语速:")
        # 将滑块设为实例属性
        self.voiceSpeedSlider = Slider(Qt.Horizontal)
        self.voiceSpeedSlider.setRange(0, 10)
        # self.voiceSpeedSlider.setValue(5) # 默认值，会被 load_settings 覆盖
        voiceSpeedLayout.addWidget(voiceSpeedLabel)
        voiceSpeedLayout.addWidget(self.voiceSpeedSlider)
        # 连接信号
        self.voiceSpeedSlider.valueChanged.connect(self.update_voice_rate)
        
        # 音量调节
        volumeLayout = QHBoxLayout()
        volumeLabel = BodyLabel("音量:")
        # 将滑块设为实例属性
        self.volumeSlider = Slider(Qt.Horizontal)
        self.volumeSlider.setRange(0, 100)
        # self.volumeSlider.setValue(80) # 默认值，会被 load_settings 覆盖
        volumeLayout.addWidget(volumeLabel)
        volumeLayout.addWidget(self.volumeSlider)
        # 连接信号
        self.volumeSlider.valueChanged.connect(self.update_voice_volume)
        
        # 添加设置到组
        voiceSettingsLayout.addLayout(voiceSpeedLayout)
        voiceSettingsLayout.addLayout(volumeLayout)
        voiceSettingsGroup.setLayout(voiceSettingsLayout)
        
        # 测试语音按钮
        testVoiceBtn = PrimaryPushButton("测试语音")
        testVoiceBtn.setIcon(FIF.VOLUME)
        # 修改 lambda，不再传递 rate 和 volume
        testVoiceBtn.clicked.connect(lambda: self.play_speech_threaded(
            '语音播报测试成功',
            voice=self.get_selected_voice(self.voiceTypeCombo) # 从实例属性获取 combo
        ))
        
        # ----- 语音警告设置组 -----
        warningGroup = QGroupBox("语音警告设置", self.voiceSettingsInterface) # 父级改为 voiceSettingsInterface
        warningLayout = QVBoxLayout()
        
        # 启用低血量语音警告
        self.low_health_warning_checkbox = CheckBox("启用低血量语音警告")
        self.low_health_warning_checkbox.setChecked(False)  # 默认不启用
        
        # 设置实例属性，这样check_health_warnings可以使用它
        self.low_health_warning_enabled = False
        self.low_health_warning_checkbox.toggled.connect(self.toggle_low_health_warning)
        warningLayout.addWidget(self.low_health_warning_checkbox)
        
        # 血量警告阈值
        thresholdLayout = QHBoxLayout()
        thresholdLabel = BodyLabel("血量警告阈值:")
        self.warning_threshold_spinbox = SpinBox()
        self.warning_threshold_spinbox.setRange(1, 99)
        self.warning_threshold_spinbox.setValue(30)  # 默认30%
        self.warning_threshold_spinbox.setSuffix("%")
        self.warning_threshold = 30.0  # 默认值，设置为实例属性
        self.warning_threshold_spinbox.valueChanged.connect(self.update_warning_threshold)
        thresholdLayout.addWidget(thresholdLabel)
        thresholdLayout.addWidget(self.warning_threshold_spinbox)
        warningLayout.addLayout(thresholdLayout)
        
        # 警告冷却时间
        cooldownLayout = QHBoxLayout()
        cooldownLabel = BodyLabel("警告冷却时间:")
        self.warning_cooldown_spinbox = SpinBox()
        self.warning_cooldown_spinbox.setRange(1, 30)
        self.warning_cooldown_spinbox.setValue(5)  # 默认5秒
        self.warning_cooldown_spinbox.setSuffix("秒")
        self.warning_cooldown = 5.0  # 默认值，设置为实例属性
        self.warning_cooldown_spinbox.valueChanged.connect(self.update_warning_cooldown)
        cooldownLayout.addWidget(cooldownLabel)
        cooldownLayout.addWidget(self.warning_cooldown_spinbox)
        warningLayout.addLayout(cooldownLayout)
        
        # 自定义警告文本
        warningTextLabel = BodyLabel("自定义警告文本:")
        self.warning_text_edit = LineEdit()
        self.warning_text_edit.setText("{name}血量过低，仅剩{health}%")
        self.warning_text_edit.setPlaceholderText("输入自定义警告内容，{name}表示队友名称，{health}表示血量百分比")
        self.warning_text = "{name}血量过低，仅剩{health}%"  # 默认值，设置为实例属性
        self.warning_text_edit.textChanged.connect(self.update_warning_text)
        warningLayout.addWidget(warningTextLabel)
        warningLayout.addWidget(self.warning_text_edit)
        
        # 变量说明
        variablesLabel = BodyLabel("可用变量: {name}=队友名称, {health}=血量百分比, {profession}=职业")
        variablesLabel.setStyleSheet("color: #7F8C8D; font-size: 12px;")
        warningLayout.addWidget(variablesLabel)
        
        # 启用团队危险警告
        self.team_danger_warning_checkbox = CheckBox("启用团队危险语音警告（多人低血量时）")
        self.team_danger_warning_checkbox.setChecked(False)  # 默认不启用
        self.team_danger_warning_enabled = False  # 默认值，设置为实例属性
        self.team_danger_warning_checkbox.toggled.connect(self.toggle_team_danger_warning)
        warningLayout.addWidget(self.team_danger_warning_checkbox)
        
        # 低血量队友数量阈值
        teamThresholdLayout = QHBoxLayout()
        teamThresholdLabel = BodyLabel("低血量队友数量阈值:")
        self.team_warning_threshold_spinbox = SpinBox()
        self.team_warning_threshold_spinbox.setRange(2, 10)
        self.team_warning_threshold_spinbox.setValue(2)  # 默认2人
        self.team_warning_threshold = 2  # 默认值，设置为实例属性
        self.team_warning_threshold_spinbox.valueChanged.connect(self.update_team_warning_threshold)
        teamThresholdLayout.addWidget(teamThresholdLabel)
        teamThresholdLayout.addWidget(self.team_warning_threshold_spinbox)
        warningLayout.addLayout(teamThresholdLayout)
        
        # 自定义团队警告文本
        teamWarningTextLabel = BodyLabel("自定义团队警告文本:")
        self.team_warning_text_edit = LineEdit()
        self.team_warning_text_edit.setText("警告，团队状态危险，{count}名队友血量过低")
        self.team_warning_text_edit.setPlaceholderText("输入自定义团队警告内容，{count}表示低血量队友数量")
        self.team_warning_text = "警告，团队状态危险，{count}名队友血量过低"  # 默认值，设置为实例属性
        self.team_warning_text_edit.textChanged.connect(self.update_team_warning_text)
        warningLayout.addWidget(teamWarningTextLabel)
        warningLayout.addWidget(self.team_warning_text_edit)
        
        # 团队变量说明
        teamVariablesLabel = BodyLabel("可用变量: {count}=低血量队友数量, {total}=总队友数量")
        teamVariablesLabel.setStyleSheet("color: #7F8C8D; font-size: 12px;")
        warningLayout.addWidget(teamVariablesLabel)
        
        warningGroup.setLayout(warningLayout)
        
        # 添加所有组件到语音卡片
        voiceLayout.addLayout(enableVoiceLayout)
        voiceLayout.addLayout(voiceTypeLayout)
        voiceLayout.addWidget(voiceSettingsGroup)
        voiceLayout.addWidget(testVoiceBtn)
        voiceLayout.addWidget(warningGroup)
        voiceCardWidget = QWidget()
        voiceCardWidget.setLayout(voiceLayout)
        voiceCard.viewLayout.addWidget(voiceCardWidget)
        
        layout.addWidget(voiceCard)
        layout.addStretch(1)

    def captureScreenIcon(self):
        """截取屏幕区域作为职业图标并保存"""
        from 选择框 import show_selection_box
        import uuid

        # 定义选择完成回调
        def on_selection(rect):
            if not self.isVisible(): # 检查父窗口是否还可见
                return

            if not rect or rect.width() <= 0 or rect.height() <= 0:
                self.show_safe_infobar(
                    '截取取消',
                    '未选择有效区域或操作被取消',
                    'warning',
                    2000
                )
                return
            
            self._icon_capture_rect = rect # Store for the next timer

            # --- 修改：延迟截图以确保选择框消失 ---
            def capture_and_save():
                if not self.isVisible(): # 再次检查
                    return
                
                # 使用存储的rect
                current_rect = self._icon_capture_rect 
                if not current_rect: # Should not happen if logic is correct
                    return

                # 创建屏幕截图
                screenshot = QApplication.primaryScreen().grabWindow(0, current_rect.x(), current_rect.y(), current_rect.width(), current_rect.height())
                
                if screenshot.isNull():
                    self.show_safe_infobar(
                        '截图失败',
                        '无法获取屏幕截图',
                        'error',
                        3000
                    )
                    return
                
                # --- 移除之前的裁剪代码 ---\n                # (不再需要裁剪，因为我们期望截图中没有边框)\n                
                # 询问用户输入职业名称
                temp_name = f"icon_{uuid.uuid4().hex[:8]}"
                
                # 使用自定义无边框对话框获取职业名称
                input_dialog = TextInputMessageBox(
                    title='输入职业名称',
                    label_text='请输入该职业图标的名称:',
                    default_text=temp_name,
                    placeholder_text='例如：奶妈、坦克、输出',
                    parent=self
                )
                
                if not input_dialog.exec():
                    return
                    
                icon_name = input_dialog.get_text()
                if not icon_name:
                    return
                    
                # 检查profession_icons文件夹是否存在
                profession_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "profession_icons")
                if not os.path.exists(profession_path):
                    os.makedirs(profession_path)
                    
                # 构造目标路径
                target_path = os.path.join(profession_path, f"{icon_name}.png")
                
                # 检查是否已存在同名文件
                if os.path.exists(target_path):
                    confirm_dialog = ConfirmMessageBox(
                        "文件已存在",
                        f"职业 '{icon_name}' 已存在，是否覆盖?",
                        self
                    )
                    
                    if not confirm_dialog.exec():
                        return
                        
                # 保存截图
                try:
                    screenshot.save(target_path, "PNG")
                    
                    # 显示成功消息
                    self.show_safe_infobar(
                        '截取成功',
                        f'职业图标 {icon_name} 已添加',
                        'success',
                        2000
                    )
                    
                    # 更新图标数量显示
                    self.updateIconCount()
                except Exception as e:
                    self.show_safe_infobar(
                        '保存失败',
                        str(e),
                        'error',
                        3000
                    )
            
            if self._icon_capture_do_grab_timer:
                self._icon_capture_do_grab_timer.stop()
            self._icon_capture_do_grab_timer = QTimer(self)
            self._icon_capture_do_grab_timer.setSingleShot(True)
            self._icon_capture_do_grab_timer.timeout.connect(capture_and_save)
            self._icon_capture_do_grab_timer.start(150) # 延迟 150 毫秒执行截图和保存
            # --- 修改结束 ---

        # 显示选择框的 InfoBar
        self.show_safe_infobar(
            '截取图标',
            '请在屏幕上选择要截取的图标区域',
            'info',
            2000
        )
        
        # 稍微延迟显示选择框，让InfoBar先显示
        if self._icon_capture_show_selection_timer:
            self._icon_capture_show_selection_timer.stop()
        self._icon_capture_show_selection_timer = QTimer(self)
        self._icon_capture_show_selection_timer.setSingleShot(True)
        self._icon_capture_show_selection_timer.timeout.connect(lambda: show_selection_box(on_selection) if self.isVisible() else None)
        self._icon_capture_show_selection_timer.start(500)

    def setTeammateHealthBarColor(self):
        """设置队友血条颜色"""
        # 检查是否有队友
        if not self.team.members:
            self.show_safe_infobar(
                '无队友',
                '当前无可设置的队友',
                'warning',
                2000
            )
            return
        
        # 使用自定义的消息框进行队友选择
        selection_dialog = TeammateSelectionMessageBox(
            '选择要设置血条颜色的队友', 
            self.team.members, 
            self
        )
        
        if selection_dialog.exec():
            selected_member = selection_dialog.get_selected_member()
            if selected_member:
                # 显示取色消息框
                self.show_color_picker_guide(selected_member)
    
    def show_color_picker_guide(self, member):
        """显示血条颜色选择指南 - 使用自定义MessageBox"""
        # 创建自定义消息框
        color_picker_dialog = ColorPickerMessageBox(member.name, self)
        
        # 显示消息框
        if color_picker_dialog.exec():
                    # 更新队友的血条颜色设置
            if hasattr(color_picker_dialog, 'color_lower') and hasattr(color_picker_dialog, 'color_upper'):
                member.hp_color_lower = color_picker_dialog.color_lower
                member.hp_color_upper = color_picker_dialog.color_upper
                    
                    # 保存到配置文件
                member.save_config()

    def handleSetAllTeammatesColor(self):
        """处理统一设置所有队友血条颜色的请求"""
        if not self.team.members:
            self.show_safe_infobar(
                '无队友',
                '当前没有队友可供设置颜色。',
                'warning',
                2000
            )
            return
        
        # 使用自定义消息框
        color_dialog = UnifiedColorPickerMessageBox(self)
        
        if color_dialog.exec() and color_dialog.pixel_color_rgb:
            self._apply_picked_color_to_all_teammates(color_dialog.pixel_color_rgb)

    def _apply_picked_color_to_all_teammates(self, pixel_color_rgb):
        """将选取的颜色应用到所有队友的配置中"""
        import numpy as np
        success_count = 0
        if not self.team.members:
            return

        # --- 将RGB转换为BGR ---
        bgr_values = (pixel_color_rgb[2], pixel_color_rgb[1], pixel_color_rgb[0]) # B, G, R

        # 保存为全局默认值，供新队员使用
        color_lower = np.array([max(0, c - 30) for c in bgr_values], dtype=np.uint8)
        color_upper = np.array([min(255, c + 30) for c in bgr_values], dtype=np.uint8)
        self.default_hp_color_lower = color_lower
        self.default_hp_color_upper = color_upper
        self.save_default_colors()  # 保存默认颜色到配置文件

        for member in self.team.members:
            try:
                # 创建颜色上下限（允许一定范围的变化） - 使用BGR值
                member.hp_color_lower = np.copy(color_lower)  # 使用拷贝防止引用共享
                member.hp_color_upper = np.copy(color_upper)  # 使用拷贝防止引用共享
                member.save_config()
                success_count += 1
            except Exception as e:
                print(f"为队友 {member.name} 更新颜色配置时出错: {e}")
                # 可以在这里用 InfoBar 提示单个队友更新失败，但可能会过多
        
        if success_count > 0:
            self.show_safe_infobar(
                '统一设置成功',
                f'已为 {success_count} 名队友统一更新了血条颜色。',
                'success',
                3000
            )
        else:
            self.show_safe_infobar(
                '统一设置失败',
                '未能为任何队友更新血条颜色。',
                'error',
                3000
            )
            
    def removeTeammate(self):
        """移除队友"""
        if not self.team.members:
            self.show_safe_infobar(
                '无队友',
                '当前无可移除的队友',
                'warning',
                2000
            )
            return
        
        # 使用自定义的消息框进行队友选择
        selection_dialog = TeammateSelectionMessageBox(
            '选择要移除的队友', 
            self.team.members, 
            self
        )
        
        if selection_dialog.exec():
            selected_member = selection_dialog.get_selected_member()
            if selected_member:
                try:
                    # 删除配置文件
                    config_file = f"{selected_member.name}_config.json"
                    config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), config_file)
                    if os.path.exists(config_path):
                        os.remove(config_path)
                    
                    # 从队伍中移除队员
                    selected_idx = self.team.members.index(selected_member)
                    self.team.members.pop(selected_idx)
                    
                    # 更新队友信息显示
                    self.update_teammate_info()
                    
                    # 更新健康监控
                    self.health_monitor.team = self.team
                    self.init_health_bars_ui()
                    
                    self.show_safe_infobar(
                        '移除成功',
                        f'队友 {selected_member.name} 已移除',
                        'success',
                        2000
                    )
                except Exception as e:
                    self.show_safe_infobar(
                        '移除失败',
                        f'错误: {str(e)}',
                        'error',
                        3000
                    )

    def load_teammates(self):
        """加载所有队友配置"""
        self.team_members = []
        
        # 获取当前目录
        current_dir = os.path.dirname(os.path.abspath(__file__))
        
        # 扫描队友配置文件
        for filename in os.listdir(current_dir):
            if filename.endswith('_config.json') and filename != 'hotkeys_config.json':
                try:
                    # 排除系统配置文件
                    if filename.startswith(('hotkeys', 'settings', 'config', 'system')):
                        continue
                        
                    # 从文件名提取队友名称
                    member_name = filename[:-12]  # 移除'_config.json'
                    
                    # 读取配置获取职业信息
                    config_path = os.path.join(current_dir, filename)
                    with open(config_path, 'r', encoding='utf-8') as f:
                        config = json.load(f)
                        
                        # 检查是否是有效的队友配置
                        if 'profession' not in config or 'health_bar' not in config:
                            continue
                        
                        # 获取职业信息
                        profession = config.get('profession', '未知')
                        
                        # 添加到队友列表
                        self.team_members.append({
                            'name': member_name,
                            'profession': profession,
                            'config': config
                        })
                        
                except Exception as e:
                    print(f'加载配置文件 {filename} 时出错: {str(e)}')
                    continue
        
        # 更新队友信息显示
        self.update_teammate_info()

    def update_teammate_info(self):
        """更新队友信息显示"""
        # 已移除队友信息标签，无需更新
        return

    def load_profession_options(self):
        """加载职业图标文件夹中的所有职业作为下拉框选项"""
        # 确保下拉框存在
        if not hasattr(self, 'priorityComboBox'):
            return
            
        # 清空当前项
        self.priorityComboBox.clear()
        
        # 添加"无优先"选项
        self.priorityComboBox.addItem("无优先")
        
        # 获取profession_icons文件夹路径
        profession_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "profession_icons")
        
        # 检查文件夹是否存在
        if not os.path.exists(profession_path):
            return
            
        # 获取所有图标文件名并排序
        profession_icons = []
        for filename in os.listdir(profession_path):
            if filename.endswith(('.png', '.jpg', '.jpeg')):
                # 去掉文件扩展名，得到职业名称
                profession_name = os.path.splitext(filename)[0]
                profession_icons.append(profession_name)
                
        # 排序
        profession_icons.sort()
        
        # 添加到下拉框
        for profession in profession_icons:
            self.priorityComboBox.addItem(profession)
    
    def update_priority_profession(self, profession):
        """更新优先职业设置"""
        if hasattr(self, 'health_monitor'):
            # 将"无优先"选项转换为None
            priority = None if profession == "无优先" else profession
            
            # 更新健康监控对象的优先职业
            self.health_monitor.priority_profession = priority
            
            # 保存设置
            self.save_priority_profession_setting()
            
            # 更新状态显示
            status = f"已设置优先职业: {profession}" if priority else "已取消职业优先选择"
            self.update_monitor_status(status)
    
    def save_priority_profession_setting(self):
        """保存优先职业设置到配置文件"""
        try:
            # 获取自动选择配置文件路径
            config_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "auto_select_config.json")
            
            # 读取现有配置
            if os.path.exists(config_file):
                with open(config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
            else:
                config = {}
            
            # 更新配置
            config['priority_profession'] = self.health_monitor.priority_profession
            
            # 保存配置
            with open(config_file, 'w', encoding='utf-8') as f:
                json.dump(config, f, ensure_ascii=False, indent=4)
                
        except Exception as e:
            print(f"保存优先职业设置失败: {e}")
            # 显示错误提示
            InfoBar.error(
                title='保存失败',
                content=f'无法保存优先职业设置: {str(e)}',
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=3000,
                parent=self
            )

    def save_default_colors(self):
        """保存默认血条颜色设置到配置文件"""
        if self.default_hp_color_lower is None or self.default_hp_color_upper is None:
            return

        try:
            config_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "default_color_config.json")
            config = {
                'default_hp_color': {
                    'lower': self.default_hp_color_lower.tolist(),
                    'upper': self.default_hp_color_upper.tolist()
                }
            }
            with open(config_file, 'w', encoding='utf-8') as f:
                json.dump(config, f, ensure_ascii=False, indent=4)
            print(f"默认血条颜色设置已保存到 {config_file}")
        except Exception as e:
            print(f"保存默认血条颜色设置失败: {e}")

    def load_default_colors(self):
        """从配置文件加载默认血条颜色设置"""
        try:
            config_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "default_color_config.json")
            if not os.path.exists(config_file):
                return  # 如果配置文件不存在，使用 None 作为默认值
                
            with open(config_file, 'r', encoding='utf-8') as f:
                config = json.load(f)
                
            if 'default_hp_color' in config:
                import numpy as np
                self.default_hp_color_lower = np.array(config['default_hp_color']['lower'], dtype=np.uint8)
                self.default_hp_color_upper = np.array(config['default_hp_color']['upper'], dtype=np.uint8)
                print(f"已加载默认血条颜色设置")
        except Exception as e:
            print(f"加载默认血条颜色设置失败: {e}")

    def show_safe_infobar(self, title, content, type_='info', duration=2000, parent=None, position=InfoBarPosition.TOP):
        """安全显示 InfoBar，防止 TopInfoBarManager 对象被删除后的错误
        
        参数:
            title: 标题
            content: 内容
            type_: 类型，'info', 'success', 'warning', 'error' 之一
            duration: 显示时长(毫秒)
            parent: 父窗口
            position: 显示位置
        """
        try:
            # 检查父对象是否有效
            if parent is None:
                parent = self
                
            # 确保父对象仍然有效（未被销毁）
            if not parent or not hasattr(parent, 'isVisible') or not parent.isVisible():
                print(f"警告: 无法显示InfoBar - 父对象无效或不可见")
                return
                
            # 使用QTimer延迟执行，避免直接调用可能导致的问题
            def show_infobar():
                try:
                    if not parent or not hasattr(parent, 'isVisible') or not parent.isVisible():
                        return
                        
                    if type_ == 'info':
                        InfoBar.info(title, content, orient=Qt.Horizontal, isClosable=True, position=position, duration=duration, parent=parent)
                    elif type_ == 'success':
                        InfoBar.success(title, content, orient=Qt.Horizontal, isClosable=True, position=position, duration=duration, parent=parent)
                    elif type_ == 'warning':
                        InfoBar.warning(title, content, orient=Qt.Horizontal, isClosable=True, position=position, duration=duration, parent=parent)
                    elif type_ == 'error':
                        InfoBar.error(title, content, orient=Qt.Horizontal, isClosable=True, position=position, duration=duration, parent=parent)
                except RuntimeError as e:
                    if "has been deleted" in str(e):
                        print(f"InfoBar 显示错误: 对象已被删除")
                    else:
                        print(f"InfoBar 运行时错误: {e}")
                except Exception as e:
                    print(f"InfoBar 未知错误: {e}")
            
            # 使用单次触发的定时器延迟显示
            QTimer.singleShot(10, show_infobar)
            
        except RuntimeError as e:
            if "has been deleted" in str(e):
                print(f"InfoBar 显示错误: 对象已被删除")
            else:
                print(f"InfoBar 运行时错误: {e}")
        except Exception as e:
            print(f"InfoBar 未知错误: {e}")

    def check_calibration_file(self):
        """检查校准文件是否有效，必要时尝试修复"""
        import os
        import json
        
        calibration_file = "health_bars_calibration.json"
        
        # 检查文件是否存在
        if not os.path.exists(calibration_file):
            print(f"校准文件 {calibration_file} 不存在")
            return False
        
        # 尝试加载文件检查是否有效
        try:
            with open(calibration_file, 'r', encoding='utf-8') as f:
                try:
                    data = json.load(f)
                    # 检查基本结构
                    if not isinstance(data, dict):
                        print(f"校准文件不是有效的JSON对象: {type(data)}")
                        return False
                    
                    # 检查是否包含校准集
                    if 'calibration_sets' not in data or not isinstance(data['calibration_sets'], dict):
                        print(f"校准文件中没有有效的calibration_sets数据")
                        return False
                        
                    # 检查是否有至少一个校准集
                    if len(data['calibration_sets']) == 0:
                        print(f"校准文件中没有任何校准集")
                        return False
                    
                    # 文件有效
                    return True
                    
                except json.JSONDecodeError as e:
                    print(f"校准文件JSON解析失败: {e}")
                    
                    # 尝试修复文件
                    try:
                        # 读取原始内容
                        f.seek(0)
                        content = f.read()
                        
                        # 尝试简单替换常见的无效JSON字符
                        content = content.replace('\n', ' ').replace('\r', '')
                        data = json.loads(content)
                        
                        # 如果成功解析，则写回文件
                        with open(calibration_file, 'w', encoding='utf-8') as out_f:
                            json.dump(data, out_f, indent=4, ensure_ascii=False)
                        
                        print("校准文件已尝试修复")
                        return True
                    except Exception as fix_err:
                        print(f"尝试修复校准文件失败: {fix_err}")
                        return False
                        
        except Exception as e:
            print(f"读取校准文件时出错: {e}")
            return False

class RecognitionThread(QThread):
    """队友识别线程类"""
    progress_signal = pyqtSignal(dict)  # 进度信号
    result_signal = pyqtSignal(list)    # 结果信号
    
    def __init__(self, calibration, set_name):
        """初始化识别线程
        
        参数:
            calibration: HealthBarCalibration实例
            set_name: 校准集名称
        """
        super().__init__()
        self.calibration = calibration
        self.set_name = set_name
    
    def run(self):
        """线程主函数，执行识别任务"""
        try:
            # 加载校准数据
            print(f"开始加载校准集: {self.set_name}")
            self.calibration.load_calibration(self.set_name)
            health_bars = self.calibration.health_bars
            
            # 打印血条信息，检查是否正确加载
            print(f"加载到 {len(health_bars)} 个血条位置:")
            for i, bar in enumerate(health_bars):
                print(f"血条 {i+1}: x1={bar.get('x1')}, y1={bar.get('y1')}, x2={bar.get('x2')}, y2={bar.get('y2')}")
            
            results = []
            
            # 循环识别每个血条区域
            for i, health_bar in enumerate(health_bars):
                # 检查是否被中断
                if self.isInterruptionRequested():
                    break
                    
                # 发送进度信号
                self.progress_signal.emit({
                    'current': i + 1,
                    'total': len(health_bars),
                    'message': f'正在识别第 {i+1}/{len(health_bars)} 个血条区域'
                })
                
                # 延时一点时间，防止识别过快造成UI更新不及时
                self.msleep(100)
                
                # 执行识别...
                # 这里会实际调用calibration对象进行识别
                # 为了简化示例，我们这里创建一个模拟结果
                result = {
                    'name': f"队友{i+1}",
                    'profession': '未知',
                    'health_bar': health_bar
                }
                results.append(result)
            
            # 如果没有被中断，发送完整结果
            if not self.isInterruptionRequested():
                # 实际执行识别
                print("开始执行队友识别...")
                teammates = self.calibration.recognize_teammates()
                print(f"识别完成，返回 {len(teammates) if teammates else 0} 个队友信息")
                # 发送结果信号
                self.result_signal.emit(teammates if teammates else results)
        
        except Exception as e:
            # 发送错误信息
            print(f"识别线程出错: {e}")
            import traceback
            traceback.print_exc()
            self.progress_signal.emit({
                'current': 0,
                'total': 1,
                'message': f'识别出错: {str(e)}'
            })
            # 发送空结果
            self.result_signal.emit([])

class CalibrationSelectionMessageBox(MessageBoxBase):
    """校准集选择对话框"""
    
    def __init__(self, calibration, parent=None):
        """初始化校准集选择对话框"""
        super().__init__(parent)
        self.calibration = calibration
        self.selected_calibration = None
        
        # 设置标题标签
        self.titleLabel = SubtitleLabel('选择校准数据集', self)
        
        # 1. 创建列表控件
        try:
            self.list_widget = QListWidget(self)
            self.list_widget.setObjectName("calibration_list_widget")
            self.list_widget.setSelectionMode(QAbstractItemView.SingleSelection)
            self.list_widget.setFixedHeight(200)
            
            # 设置列表基本样式
            self.list_widget.setStyleSheet("""
                QListWidget {
                    border: 1px solid #e0e0e0;
                    border-radius: 5px;
                    background-color: white;
                    outline: none;
                }
                QListWidget::item {
                    padding: 6px;
                    border-bottom: 1px solid #f0f0f0;
                }
                QListWidget::item:selected {
                    background-color: #ecf6ff;
                    color: #1976d2;
                }
            """)
        except Exception as e:
            print(f"创建列表控件时出错: {e}")
            self.list_widget = QListWidget(self)
        
        # 3. 创建详细信息标签和警告标签
        try:
            self.detail_label = BodyLabel("选择一个校准集以查看详细信息")
            self.detail_label.setWordWrap(True)
            
            self.warning_label = CaptionLabel("请选择一个校准数据集")
            self.warning_label.setTextColor("#cf1010", QColor(255, 28, 32))
            self.warning_label.hide()  # 默认隐藏
        except Exception as label_err:
            print(f"创建标签时出错: {label_err}")
            # 确保这些属性始终存在
            if not hasattr(self, 'detail_label'):
                self.detail_label = BodyLabel("选择一个校准集以查看详细信息", self)
            if not hasattr(self, 'warning_label'):
                self.warning_label = CaptionLabel("请选择一个校准数据集", self)
        
        # 创建删除按钮
        try:
            self.delete_button = PushButton("删除选中的校准集")
            self.delete_button.setIcon(FIF.DELETE.icon())
            self.delete_button.setEnabled(False)  # 初始禁用，直到选中项目
            self.delete_button.clicked.connect(self.delete_selected_calibration)
        except Exception as btn_err:
            print(f"创建删除按钮时出错: {btn_err}")
            self.delete_button = PushButton("删除选中的校准集", self)
            self.delete_button.setEnabled(False)
        
        # 4. 添加组件到视图布局
        try:
            self.viewLayout.addWidget(self.titleLabel)
            self.viewLayout.addWidget(self.list_widget)
            self.viewLayout.addWidget(self.detail_label)
            self.viewLayout.addWidget(self.delete_button)
            self.viewLayout.addWidget(self.warning_label)
            
            # 修改按钮文本
            self.yesButton.setText('开始识别')
            self.yesButton.setIcon(FIF.PLAY.icon())
            self.yesButton.setFixedWidth(120)
            self.cancelButton.setText('取消')
            self.cancelButton.setIcon(FIF.CANCEL.icon())
            self.cancelButton.setFixedWidth(100)
            
            # 设置最小宽度
            self.widget.setMinimumWidth(450)
        except Exception as layout_err:
            print(f"设置布局时出错: {layout_err}")
        
        # 5. 连接事件和加载数据
        try:
            self.list_widget.itemClicked.connect(self.on_selection_changed)
            self.loadCalibrationSets()
        except Exception as connect_err:
            print(f"连接事件或加载数据时出错: {connect_err}")
            
        # 为了向后兼容，添加兼容性属性
        self.selection_detail_label = self.detail_label
        self.warningLabel = self.warning_label

    def loadCalibrationSets(self):
        """加载所有可用的校准数据集"""
        try:
            # 确保 calibration 存在
            if not self.calibration:
                from health_bar_calibration import HealthBarCalibration
                self.calibration = HealthBarCalibration()
            
            # 获取校准集列表
            cal_sets = self.calibration.get_calibration_set_names()
            
            # 清空列表
            self.list_widget.clear()
            
            # 添加校准集到列表
            for cal_set in cal_sets:
                item = QListWidgetItem(cal_set)
                # 存储校准集名称
                item.setData(Qt.UserRole, cal_set)
                self.list_widget.addItem(item)
            
            # 如果有校准集，默认选择第一个
            if cal_sets:
                self.list_widget.setCurrentRow(0)
                self.on_selection_changed(self.list_widget.item(0))
        except Exception as e:
            print(f"加载校准集列表时出错: {e}")
            import traceback
            traceback.print_exc()
    
    def on_selection_changed(self, item):
        """当选择改变时更新详细信息"""
        try:
            if item:
                cal_set_name = item.data(Qt.UserRole)
                self.selected_calibration = cal_set_name
                
                # 获取校准集详细信息
                cal_info = self.calibration.get_calibration_info(cal_set_name)
                
                # 使用直接属性访问
                if not hasattr(self, 'detail_label'):
                    print("错误: detail_label 属性不存在")
                    return
                
                if cal_info:
                    health_bars_count = len(cal_info.get('health_bars', []))
                    creation_time = cal_info.get('creation_time', '未知')
                    
                    # 更新详细信息显示
                    info_text = f"校准集: {cal_set_name}\n包含 {health_bars_count} 个血条\n创建时间: {creation_time}"
                    
                    self.detail_label.setText(info_text)
                    if hasattr(self, 'warning_label') and self.warning_label:
                        self.warning_label.hide()
                else:
                    self.detail_label.setText(f"校准集 {cal_set_name} 无法获取详细信息")
                    
                # 启用删除按钮
                if hasattr(self, 'delete_button') and self.delete_button:
                    self.delete_button.setEnabled(True)
            else:
                if hasattr(self, 'detail_label') and self.detail_label:
                    self.detail_label.setText("请选择一个校准集")
                
                self.selected_calibration = None
                
                # 禁用删除按钮
                if hasattr(self, 'delete_button') and self.delete_button:
                    self.delete_button.setEnabled(False)
        except Exception as e:
            print(f"处理选择变更时出错: {e}")
            import traceback
            traceback.print_exc()
    
    def exec(self):
        """显示对话框并等待用户操作"""
        try:
            # 执行父类的exec方法显示对话框
            result = super().exec()
            
            # 如果用户点击了确定按钮
            if result:
                # 获取当前选中的校准集
                if hasattr(self, 'list_widget') and self.list_widget and self.list_widget.currentItem():
                    # 从用户数据中获取校准集名称
                    self.selected_calibration = self.list_widget.currentItem().data(Qt.UserRole)
                else:
                    self.selected_calibration = None
            else:
                self.selected_calibration = None
                
            return result
        except Exception as e:
            print(f"CalibrationSelectionMessageBox.exec 方法出错: {e}")
            import traceback
            traceback.print_exc()
            self.selected_calibration = None
            return False
    
    def delete_selected_calibration(self):
        """删除选中的校准集"""
        if not self.selected_calibration:
            return
            
        # 保存当前选中的校准集名称
        current_cal_name = self.selected_calibration
            
        # 创建确认对话框
        confirm_dialog = ConfirmMessageBox(
            "确认删除",
            f"确定要删除校准集 '{current_cal_name}' 吗？此操作不可撤销。",
            self
        )
        
        if confirm_dialog.exec():
            try:
                # 检查校准工具实例
                if not self.calibration:
                    return
                
                # 调用校准工具的删除方法
                success = self.calibration.delete_calibration_set(current_cal_name)
                
                if success:
                    # 更新列表
                    self.loadCalibrationSets()
                    self.selected_calibration = None
                    
                    # 设置文本
                    if hasattr(self, 'detail_label'):
                        self.detail_label.setText("选择一个校准集以查看详细信息")
                    
                    # 禁用删除按钮
                    if hasattr(self, 'delete_button'):
                        self.delete_button.setEnabled(False)
                    
                    # 显示成功消息
                    InfoBar.success(
                        title='删除成功',
                        content=f'已删除校准集 {current_cal_name}',
                        orient=Qt.Horizontal,
                        isClosable=True,
                        position=InfoBarPosition.TOP,
                        duration=2000,
                        parent=self
                    )
                else:
                    # 显示错误消息
                    InfoBar.error(
                        title='删除失败',
                        content=f'无法删除校准集 {current_cal_name}',
                        orient=Qt.Horizontal,
                        isClosable=True,
                        position=InfoBarPosition.TOP,
                        duration=2000,
                        parent=self
                    )
            except Exception as e:
                # 显示错误消息
                InfoBar.error(
                    title='删除失败',
                    content=f'删除过程中出错: {str(e)}',
                    orient=Qt.Horizontal,
                    isClosable=True,
                    position=InfoBarPosition.TOP,
                    duration=3000,
                    parent=self
                )
                
    def validate(self):
        """验证是否选择了校准集"""
        if self.selected_calibration:
            return True
        
        # 显示警告
        if hasattr(self, 'warning_label'):
            self.warning_label.setText("请选择一个校准数据集")
            self.warning_label.show()
            
        return False

class HotkeyEventFilter(QObject):
    def __init__(self, parent, edit, other_edit, which, status_label, health_monitor):
        super().__init__(parent)
        self.edit = edit
        self.other_edit = other_edit
        self.which = which
        self.status_label = status_label
        self.health_monitor = health_monitor

    def eventFilter(self, obj, event):
        if obj == self.edit and event.type() == QEvent.KeyPress:
            key_text = ''
            modifiers = event.modifiers()
            if modifiers & Qt.ControlModifier:
                key_text += 'ctrl+'
            if modifiers & Qt.AltModifier:
                key_text += 'alt+'
            if modifiers & Qt.ShiftModifier:
                key_text += 'shift+'
            key = event.key()
            if key in (Qt.Key_Control, Qt.Key_Alt, Qt.Key_Shift):
                return True
            from PyQt5.QtGui import QKeySequence
            key_name = QKeySequence(key).toString().lower()
            key_text += key_name
            self.edit.setText(key_text)
            self.edit.setReadOnly(True)
            # 保存并注册
            if self.which == 'start':
                success = self.health_monitor.set_hotkeys(key_text, self.other_edit.text())
            else:
                success = self.health_monitor.set_hotkeys(self.other_edit.text(), key_text)
            if success:
                self.status_label.setText('快捷键设置成功')
            else:
                self.status_label.setText('快捷键设置失败，请重试')
            self.edit.removeEventFilter(self)
            return True
        return False

# 在MainWindow类前添加AddTeammateMessageBox类
class AddTeammateMessageBox(MessageBoxBase):
    """ Custom message box for adding teammate """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.titleLabel = SubtitleLabel('添加队友', self)
        
        # 名称输入
        self.nameLabel = BodyLabel("队友名称:")
        self.nameEdit = LineEdit(self)
        self.nameEdit.setPlaceholderText("请输入队友名称")
        
        # 职业输入
        self.professionLabel = BodyLabel("队友职业:")
        self.professionEdit = LineEdit(self)
        self.professionEdit.setPlaceholderText("请输入队友职业 (可选)")
        
        # 警告标签
        self.warningLabel = CaptionLabel("请输入队友名称")
        self.warningLabel.setTextColor("#cf1010", QColor(255, 28, 32))
        self.warningLabel.hide()  # 默认隐藏
        
        # 添加到视图布局
        self.viewLayout.addWidget(self.titleLabel)
        
        nameLayout = QHBoxLayout()
        nameLayout.addWidget(self.nameLabel)
        nameLayout.addWidget(self.nameEdit)
        self.viewLayout.addLayout(nameLayout)
        
        professionLayout = QHBoxLayout()
        professionLayout.addWidget(self.professionLabel)
        professionLayout.addWidget(self.professionEdit)
        self.viewLayout.addLayout(professionLayout)
        
        self.viewLayout.addWidget(self.warningLabel)
        
        # 修改按钮文本
        self.yesButton.setText('添加')
        self.cancelButton.setText('取消')
        
        # 设置最小宽度
        self.widget.setMinimumWidth(350)
        
        # 添加回车键确认功能
        self.nameEdit.returnPressed.connect(self.on_return_pressed)
        self.professionEdit.returnPressed.connect(self.on_return_pressed)
    
    def on_return_pressed(self):
        """回车键按下时触发确认，但需要先验证"""
        if self.validate():
            self.accept()
    
    def validate(self):
        """验证输入是否有效"""
        isValid = bool(self.nameEdit.text().strip())
        self.warningLabel.setVisible(not isValid)
        self.nameEdit.setError(not isValid)
        return isValid
    
    def get_teammate_info(self):
        """获取队友信息"""
        name = self.nameEdit.text().strip()
        profession = self.professionEdit.text().strip() or "未知"  # 默认职业值
        return name, profession

# 添加确认对话框类
class ConfirmMessageBox(MessageBoxBase):
    """Custom confirmation message box"""

    def __init__(self, title, content, parent=None):
        super().__init__(parent)
        self.titleLabel = SubtitleLabel(title, self)
        self.titleLabel.setStyleSheet("font-size: 16px; font-weight: bold; color: #333333;")
        
        # 添加图标
        self.iconLabel = QLabel(self)
        # 正确使用FluentIcon获取图标
        pixmap = FIF.HELP.icon().pixmap(32, 32)
        self.iconLabel.setPixmap(pixmap)
        self.iconLabel.setAlignment(Qt.AlignCenter)
        
        # 标题栏布局
        titleLayout = QHBoxLayout()
        titleLayout.addWidget(self.iconLabel)
        titleLayout.addWidget(self.titleLabel)
        titleLayout.addStretch(1)
        
        # 内容标签
        self.contentLabel = BodyLabel(content)
        self.contentLabel.setWordWrap(True)
        self.contentLabel.setStyleSheet("line-height: 150%; margin: 10px 0; font-size: 14px; color: #505050;")
        
        # 添加到视图布局
        self.viewLayout.addLayout(titleLayout)
        self.viewLayout.addWidget(self.contentLabel)
        
        # 设置按钮文本和样式
        self.yesButton.setText('确定')
        self.yesButton.setIcon(FIF.ACCEPT.icon())  # 使用icon()方法获取QIcon
        self.cancelButton.setText('取消')
        self.cancelButton.setIcon(FIF.CANCEL.icon())  # 使用icon()方法获取QIcon
        
        # 设置外观和尺寸
        self.widget.setMinimumWidth(380)
        self.widget.setStyleSheet("""
            QWidget {
                background-color: rgba(253, 253, 253, 0.98);
                border-radius: 8px;
            }
        """)
        
        # 设置动画和阴影效果
        self.animation = QPropertyAnimation(self, b"windowOpacity")
        self.animation.setDuration(200)
        self.animation.setStartValue(0)
        self.animation.setEndValue(1)
        self.animation.start()
        
        # 自定义阴影效果
        self.customShadowEffect()
        
    def customShadowEffect(self):
        """自定义对话框阴影效果（不覆盖父类方法）"""
        try:
            shadow = QGraphicsDropShadowEffect(self.widget)
            shadow.setBlurRadius(15)
            shadow.setColor(QColor(0, 0, 0, 80))
            shadow.setOffset(0, 0)
            self.widget.setGraphicsEffect(shadow)
        except Exception as e:
            print(f"设置阴影效果时出错: {e}")

# 添加职业图标对话框类
class ProfessionIconMessageBox(MessageBoxBase):
    """职业图标输入对话框"""

    def __init__(self, default_name='', parent=None):
        super().__init__(parent)
        self.titleLabel = SubtitleLabel('输入职业名称', self)
        self.nameEdit = LineEdit(self)
        
        self.nameEdit.setPlaceholderText('请输入该职业图标的名称')
        self.nameEdit.setText(default_name)
        self.nameEdit.setClearButtonEnabled(True)
        
        self.warningLabel = CaptionLabel("请输入有效的职业名称")
        self.warningLabel.setTextColor("#cf1010", QColor(255, 28, 32))
        
        # 添加到视图布局
        self.viewLayout.addWidget(self.titleLabel)
        self.viewLayout.addWidget(self.nameEdit)
        self.viewLayout.addWidget(self.warningLabel)
        self.warningLabel.hide()
        
        # 修改按钮文本
        self.yesButton.setText('确定')
        self.cancelButton.setText('取消')
        
        # 设置最小宽度
        self.widget.setMinimumWidth(350)
        
        # 添加回车键确认功能
        self.nameEdit.returnPressed.connect(self.on_return_pressed)
    
    def on_return_pressed(self):
        """回车键按下时触发确认，但需要先验证"""
        if self.validate():
            self.accept()
    
    def validate(self):
        """验证输入是否有效"""
        isValid = bool(self.nameEdit.text().strip())
        self.warningLabel.setVisible(not isValid)
        self.nameEdit.setError(not isValid)
        return isValid
    
    def get_profession_name(self):
        """获取输入的职业名称"""
        return self.nameEdit.text().strip()

# 管理图标对话框类
class ProfessionIconsManageDialog(MessageBoxBase):
    """职业图标管理对话框"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent
        self.titleLabel = SubtitleLabel('管理当前已加载的职业图标', self)
        
        # 设置更大的尺寸
        self.widget.setMinimumWidth(600)
        self.widget.setMinimumHeight(400)
        
        # 创建滚动区域
        self.scrollArea = ScrollArea()
        self.scrollArea.setWidgetResizable(True)
        
        self.scrollWidget = QWidget()
        self.scrollLayout = QGridLayout(self.scrollWidget)
        self.scrollLayout.setSpacing(12)
        
        self.scrollArea.setWidget(self.scrollWidget)
        self.scrollArea.setMinimumSize(580, 300)
        
        # 添加到视图布局
        self.viewLayout.addWidget(self.titleLabel)
        self.viewLayout.addWidget(self.scrollArea)
        
        # 加载图标
        self.load_icons()
        
        # 修改按钮文本
        self.yesButton.setText('关闭')
        self.cancelButton.hide()  # 隐藏取消按钮
    
    def load_icons(self):
        """加载所有职业图标到网格中"""
        profession_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "profession_icons")
        
        # 检查文件夹是否存在
        if not os.path.exists(profession_path):
            os.makedirs(profession_path)
            return
        
        # 获取所有图标文件
        icons = [f for f in os.listdir(profession_path) if f.endswith(('.png', '.jpg', '.jpeg'))]
        
        # 如果没有图标，显示提示信息
        if not icons:
            emptyLabel = BodyLabel("当前没有职业图标。点击\"添加图标\"按钮添加新图标。")
            emptyLabel.setAlignment(Qt.AlignCenter)
            self.scrollLayout.addWidget(emptyLabel, 0, 0)
            return
        
        # 添加图标到网格
        for i, icon_file in enumerate(icons):
            frame = QFrame()
            frame.setObjectName("cardFrame")
            frame.setFixedSize(120, 140)
            frameLayout = QVBoxLayout(frame)
            
            # 图标
            icon_path = os.path.join(profession_path, icon_file)
            pixmap = QPixmap(icon_path).scaled(80, 80, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            iconLabel = QLabel()
            iconLabel.setPixmap(pixmap)
            iconLabel.setAlignment(Qt.AlignCenter)
            
            # 图标名称
            nameLabel = QLabel(os.path.splitext(icon_file)[0])
            nameLabel.setAlignment(Qt.AlignCenter)
            
            # 删除按钮
            deleteBtn = TransparentPushButton("删除")
            deleteBtn.setIcon(FIF.DELETE.icon())  # 使用icon()方法获取QIcon
            deleteBtn.setObjectName(icon_file)  # 存储文件名用于删除
            deleteBtn.clicked.connect(lambda checked, file=icon_file, frm=frame: self.parent.deleteProfessionIcon(file, frm, self))
            
            frameLayout.addWidget(iconLabel)
            frameLayout.addWidget(nameLabel)
            frameLayout.addWidget(deleteBtn)
            
            self.scrollLayout.addWidget(frame, i//4, i%4)  # 每行4个图标

# 识别区域选择消息框类
class SelectionGuideDialog(MessageBoxBase):
    """选择识别区域指导对话框"""

    def __init__(self, title, content, parent=None):
        super().__init__(parent)
        # 不要设置额外的窗口标志，因为MessageBoxBase可能已经设置了
        # 设置标题和内容
        self.titleLabel = SubtitleLabel(title, self)
        self.titleLabel.setStyleSheet("font-size: 16px; font-weight: bold; color: #333333;")
        
        # 添加图标
        self.iconLabel = QLabel(self)
        # 直接使用FIF.SEARCH作为图标，而不是尝试创建QIcon
        pixmap = FIF.SEARCH.icon().pixmap(36, 36)
        self.iconLabel.setPixmap(pixmap)
        self.iconLabel.setAlignment(Qt.AlignCenter)
        self.iconLabel.setStyleSheet("margin-right: 10px;")
        
        # 标题与图标水平布局
        titleLayout = QHBoxLayout()
        titleLayout.addWidget(self.iconLabel)
        titleLayout.addWidget(self.titleLabel)
        titleLayout.addStretch(1)
        titleLayout.setContentsMargins(0, 5, 0, 10)  # 增加上下间距
        
        # 内容标签增强
        self.contentLabel = BodyLabel(content)
        self.contentLabel.setWordWrap(True)
        self.contentLabel.setStyleSheet("line-height: 160%; margin: 12px 0; font-size: 14px; color: #505050;")
        
        # 创建分隔线
        self.separator = QFrame()
        self.separator.setFrameShape(QFrame.HLine)
        self.separator.setFrameShadow(QFrame.Sunken)
        self.separator.setStyleSheet("background-color: #e0e0e0; max-height: 1px; margin: 15px 0;")
        
        # 提示信息
        self.tipLabel = CaptionLabel("提示：选择区域后可按ESC键取消选择")
        self.tipLabel.setStyleSheet("color: #0078d7; margin-top: 10px; font-size: 12px;")
        
        # 图示区域 - 显示简单的选择框示意图
        self.demoLabel = QLabel(self)
        self.demoLabel.setFixedHeight(80)
        self.demoLabel.setStyleSheet("""
            background-color: #f5f5f5; 
            border: 1px dashed #999; 
            border-radius: 4px;
        """)
        self.demoLabel.setAlignment(Qt.AlignCenter)
        self.demoLabel.setText("↖ 拖动鼠标框选区域示例 ↘")
        
        # 添加到视图布局
        self.viewLayout.addLayout(titleLayout)
        self.viewLayout.addWidget(self.contentLabel)
        self.viewLayout.addWidget(self.demoLabel)
        self.viewLayout.addWidget(self.separator)
        self.viewLayout.addWidget(self.tipLabel)
        
        # 修改按钮文本和样式
        self.yesButton.setText('开始选择')
        self.yesButton.setIcon(FIF.PLAY.icon())  # 使用icon()方法获取QIcon
        self.yesButton.setFixedWidth(120)  # 固定按钮宽度
        self.cancelButton.setText('取消')
        self.cancelButton.setIcon(FIF.CANCEL.icon())  # 使用icon()方法获取QIcon
        self.cancelButton.setFixedWidth(100)  # 固定按钮宽度
        
        # 设置窗口样式和尺寸
        self.widget.setMinimumWidth(480)
        self.widget.setStyleSheet("""
            QWidget {
                background-color: rgba(253, 253, 253, 0.98);
                border-radius: 8px;
            }
        """)
        
        # 设置动画效果
        self.animation = QPropertyAnimation(self, b"windowOpacity")
        self.animation.setDuration(200)
        self.animation.setStartValue(0)
        self.animation.setEndValue(1)
        self.animation.start()
        
        # 自定义阴影效果（不覆盖父类方法）
        self.customShadowEffect()
    
    def customShadowEffect(self):
        """自定义对话框阴影效果（不覆盖父类方法）"""
        try:
            shadow = QGraphicsDropShadowEffect(self.widget)
            shadow.setBlurRadius(15)
            shadow.setColor(QColor(0, 0, 0, 80))
            shadow.setOffset(0, 0)
            self.widget.setGraphicsEffect(shadow)
        except Exception as e:
            print(f"设置阴影效果时出错: {e}")

# 新增：通用文本输入对话框
class TextInputMessageBox(MessageBoxBase):
    """通用文本输入对话框，用于替代 QInputDialog.getText"""

    def __init__(self, title, label_text, default_text="", placeholder_text="", parent=None):
        super().__init__(parent)
        
        # 设置标题栏
        self.dialogTitleLabel = SubtitleLabel(title, self)
        self.dialogTitleLabel.setStyleSheet("font-size: 16px; font-weight: bold; color: #333333;")
        
        # 添加图标
        self.iconLabel = QLabel(self)
        # 正确使用FluentIcon获取图标
        pixmap = FIF.EDIT.icon().pixmap(32, 32)
        self.iconLabel.setPixmap(pixmap)
        self.iconLabel.setAlignment(Qt.AlignCenter)
        
        # 标题栏布局
        titleLayout = QHBoxLayout()
        titleLayout.addWidget(self.iconLabel)
        titleLayout.addWidget(self.dialogTitleLabel)
        titleLayout.addStretch(1)
        
        # 添加到视图布局
        self.viewLayout.addLayout(titleLayout)

        # 如果提供了标签文本，则添加为BodyLabel
        if label_text:
            self.inputInstructionLabel = BodyLabel(label_text, self)
            self.inputInstructionLabel.setStyleSheet("margin-top: 10px; color: #505050;")
            self.viewLayout.addWidget(self.inputInstructionLabel)

        # 输入框
        self.lineEdit = LineEdit(self)
        self.lineEdit.setText(default_text)
        self.lineEdit.setStyleSheet("""
            LineEdit {
                padding: 8px;
                border: 1px solid #e0e0e0;
                border-radius: 4px;
                background-color: #fafafa;
                margin-top: 5px;
                margin-bottom: 5px;
            }
            LineEdit:focus {
                border: 1px solid #0078d7;
            }
        """)
        
        if placeholder_text:
            self.lineEdit.setPlaceholderText(placeholder_text)
        elif label_text and not default_text:
             self.lineEdit.setPlaceholderText(label_text)
        
        self.lineEdit.setClearButtonEnabled(True)
        self.viewLayout.addWidget(self.lineEdit)
        
        # 警告标签
        self.warningLabel = CaptionLabel("输入不能为空")
        self.warningLabel.setTextColor("#cf1010", QColor(255, 28, 32))
        self.warningLabel.setStyleSheet("margin-top: 5px;")
        self.viewLayout.addWidget(self.warningLabel)
        self.warningLabel.hide()

        # 设置按钮文本和图标
        self.yesButton.setText('确定')
        self.yesButton.setIcon(FIF.ACCEPT.icon())  # 使用icon()方法获取QIcon
        self.cancelButton.setText('取消')
        self.cancelButton.setIcon(FIF.CANCEL.icon())  # 使用icon()方法获取QIcon

        # 设置对话框样式和尺寸
        self.widget.setMinimumWidth(400)
        self.widget.setStyleSheet("""
            QWidget {
                background-color: rgba(253, 253, 253, 0.98);
                border-radius: 8px;
            }
        """)
        
        # 连接回车按键事件
        self.lineEdit.returnPressed.connect(self.on_return_pressed)
        
        # 设置动画和阴影效果
        self.animation = QPropertyAnimation(self, b"windowOpacity")
        self.animation.setDuration(200)
        self.animation.setStartValue(0)
        self.animation.setEndValue(1)
        self.animation.start()
        
        # 自定义阴影效果
        self.customShadowEffect()

    def on_return_pressed(self):
        if self.validate():
            self.accept()

    def validate(self):
        is_valid = bool(self.lineEdit.text().strip())
        self.warningLabel.setHidden(is_valid)
        self.lineEdit.setError(not is_valid)
        return is_valid

    def get_text(self):
        return self.lineEdit.text().strip()
        
    def customShadowEffect(self):
        """自定义对话框阴影效果（不覆盖父类方法）"""
        try:
            shadow = QGraphicsDropShadowEffect(self.widget)
            shadow.setBlurRadius(15)
            shadow.setColor(QColor(0, 0, 0, 80))
            shadow.setOffset(0, 0)
            self.widget.setGraphicsEffect(shadow)
        except Exception as e:
            print(f"设置阴影效果时出错: {e}")

def main():
    """主函数，用于启动应用程序"""
    # 设置高DPI支持 - 在创建应用程序之前进行设置
    # 注意：必须在QApplication实例化之前设置这些属性
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
    
    app = QApplication(sys.argv)
    
    # 添加全局异常处理，专门处理InfoBar相关的错误
    def handle_exception(exc_type, exc_value, exc_traceback):
        if issubclass(exc_type, RuntimeError) and "TopInfoBarManager" in str(exc_value):
            print("捕获到 TopInfoBarManager 错误，已忽略：", exc_value)
        else:
            # 对于其他异常，调用默认异常处理
            sys.__excepthook__(exc_type, exc_value, exc_traceback)
    
    # 设置全局异常处理器
    sys.excepthook = handle_exception
    
    # 设置全局样式
    app.setStyleSheet(GLOBAL_STYLE)
    
    # 设置字体
    font = QFont("Microsoft YaHei UI", 9)
    app.setFont(font)
    
    # 设置主题
    setTheme(Theme.AUTO)
    
    # 创建主窗口
    window = MainWindow()
    window.show()
    
    exit_code = app.exec_()

    # 确保 pygame 在退出时正确清理 (虽然 closeEvent 里有，这里再加一层保险)
    pygame.quit()

    sys.exit(exit_code)

if __name__ == "__main__":
    main() 