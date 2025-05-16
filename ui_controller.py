import os
import json
from PyQt5.QtCore import Qt, pyqtSignal, QObject, QTimer, QUrl
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, 
                            QGridLayout, QDialog, QListWidget, QListWidgetItem, QGroupBox)
from PyQt5.QtGui import QColor, QIcon
from qfluentwidgets import (PushButton, PrimaryPushButton, InfoBarPosition, InfoBar, 
                           MessageBox, StrongBodyLabel, BodyLabel, ScrollArea,
                           HeaderCardWidget, TransparentPushButton, LineEdit,
                           ComboBox, SpinBox, SwitchButton, Slider, CheckBox,
                           FluentIcon as FIF)

from health_visualization import HealthVisualization

class UIController(QObject):
    """UI控制器类，负责构建和管理用户界面"""
    
    # 定义信号
    add_teammate_signal = pyqtSignal(str, str)  # 添加队友的信号(名称, 职业)
    remove_teammate_signal = pyqtSignal(int)  # 移除队友的信号(索引)
    load_teammates_signal = pyqtSignal()  # 加载队友的信号
    clear_teammates_signal = pyqtSignal()  # 清除所有队友的信号
    
    def __init__(self, parent=None):
        """初始化UI控制器"""
        super().__init__(parent)
        
        # 初始化可视化组件
        self.health_visualization = HealthVisualization()
        
        # 记录当前UI元素的引用
        self.health_bars_frame = None
        self.monitor_status_label = None
        self.teammateInfoPreview = None
        
        # 语音设置元素引用
        self.voiceTypeCombo = None
        self.voiceSpeedSlider = None
        self.volumeSlider = None
        
        # 警告设置
        self.low_health_warning_enabled = False
        self.team_danger_warning_enabled = False
        self.warning_threshold = 30.0
        self.warning_cooldown = 5.0
        self.warning_text = "{name}血量过低，仅剩{health}%"
        self.team_warning_threshold = 2
        self.team_warning_text = "警告，团队状态危险，{count}名队友血量过低"
        
        # 最后一次发出语音警告的时间
        self.last_voice_warning_time = {}
        
    def setup_team_recognition_interface(self, interface):
        """设置队员识别界面
        
        参数:
            interface: 要设置的界面实例
        """
        # 实现队员识别界面的构建
        layout = QVBoxLayout(interface)
        layout.setSpacing(24)
        layout.setContentsMargins(24, 24, 24, 24)
        
        # 创建顶部水平布局
        topLayout = QHBoxLayout()
        topLayout.setSpacing(24)
        
        # 职业图标管理卡片
        iconCard = HeaderCardWidget(interface)
        iconCard.setTitle("职业图标管理")
        iconLayout = QVBoxLayout()
        iconLayout.setSpacing(15)
        iconLayout.setContentsMargins(0, 10, 0, 10)
        
        # 按钮布局
        btnLayout = QHBoxLayout()
        btnLayout.setSpacing(15)
        
        addIconBtn = PrimaryPushButton('添加图标')
        addIconBtn.setIcon(FIF.ADD)
        addIconBtn.setFixedWidth(140)
        addIconBtn.setMinimumHeight(36)
        
        captureIconBtn = PushButton('截取图标')
        captureIconBtn.setIcon(FIF.CAMERA)
        captureIconBtn.setFixedWidth(140)
        captureIconBtn.setMinimumHeight(36)
        
        manageIconsBtn = PushButton('管理图标')
        manageIconsBtn.setIcon(FIF.SETTING)
        manageIconsBtn.setFixedWidth(140)
        manageIconsBtn.setMinimumHeight(36)
        
        # 连接按钮事件 (连接到父窗口的方法)
        if self.parent():
            addIconBtn.clicked.connect(self.parent().addProfessionIcon)
            captureIconBtn.clicked.connect(self.parent().captureScreenIcon)
            manageIconsBtn.clicked.connect(self.parent().loadProfessionIcons)
        
        btnLayout.addWidget(addIconBtn)
        btnLayout.addWidget(captureIconBtn)
        btnLayout.addWidget(manageIconsBtn)
        btnLayout.addStretch(1)
        
        # 显示图标数量信息
        profession_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "profession_icons")
        
        # 检查文件夹是否存在
        if not os.path.exists(profession_path):
            os.makedirs(profession_path)
            self.icon_count = 0
        else:
            self.icon_count = len([f for f in os.listdir(profession_path) if f.endswith(('.png', '.jpg', '.jpeg'))])
            
        infoLabel = BodyLabel(f'已加载 {self.icon_count} 个职业图标')
        infoLabel.setStyleSheet("color: #666; font-size: 13px;")
        infoLabel.setAlignment(Qt.AlignCenter)
        
        # 添加到卡片布局
        iconLayout.addLayout(btnLayout)
        iconLayout.addWidget(infoLabel)
        iconLayout.addStretch(1)
        iconCardWidget = QWidget()
        iconCardWidget.setLayout(iconLayout)
        iconCard.viewLayout.addWidget(iconCardWidget)
        self.iconInfoLabel = infoLabel  # 保存引用以便稍后更新
        
        # 队友管理卡片
        teammateCard = HeaderCardWidget(interface)
        teammateCard.setTitle("队友管理")
        teammateLayout = QVBoxLayout()
        teammateLayout.setSpacing(30)
        teammateLayout.setContentsMargins(0, 0, 0, 10)
        
        # 队友管理按钮 - 使用网格布局
        teammateBtnLayout = QHBoxLayout()
        teammateBtnLayout.setSpacing(15)
        
        addTeammateBtn = PrimaryPushButton('添加队友')
        addTeammateBtn.setIcon(FIF.ADD)
        addTeammateBtn.setFixedWidth(115)
        addTeammateBtn.setMinimumHeight(36)
        
        removeTeammateBtn = PushButton('移除队友')
        removeTeammateBtn.setIcon(FIF.REMOVE)
        removeTeammateBtn.setFixedWidth(115)
        removeTeammateBtn.setMinimumHeight(36)
        
        loadTeammateBtn = PushButton('加载队友')
        loadTeammateBtn.setIcon(FIF.DOWNLOAD)
        loadTeammateBtn.setFixedWidth(115)
        loadTeammateBtn.setMinimumHeight(36)
        
        clearAllTeammatesBtn = PushButton('清除全部')
        clearAllTeammatesBtn.setIcon(FIF.DELETE)
        clearAllTeammatesBtn.setFixedWidth(115)
        clearAllTeammatesBtn.setMinimumHeight(36)
        
        # 连接按钮事件
        if self.parent():
            addTeammateBtn.clicked.connect(self.parent().addTeammate)
            removeTeammateBtn.clicked.connect(self.parent().removeTeammate)
            loadTeammateBtn.clicked.connect(self.parent().loadTeammate)
            clearAllTeammatesBtn.clicked.connect(self.parent().clearAllTeammates)
        
        # 添加到布局
        teammateBtnLayout.addWidget(addTeammateBtn)
        teammateBtnLayout.addWidget(removeTeammateBtn)
        teammateBtnLayout.addWidget(loadTeammateBtn)
        teammateBtnLayout.addWidget(clearAllTeammatesBtn)
        teammateBtnLayout.addStretch(1)
        
        # 队友信息显示
        teammateInfoLabel = BodyLabel('')
        teammateInfoLabel.setObjectName("teammateInfoLabel")
        teammateInfoLabel.setWordWrap(True)
        teammateInfoLabel.setStyleSheet("color: #666; font-size: 13px;")
        teammateInfoLabel.setAlignment(Qt.AlignCenter)
        
        # 添加到卡片布局
        teammateLayout.addLayout(teammateBtnLayout)
        teammateLayout.addWidget(teammateInfoLabel)
        teammateLayout.addStretch(1)
        teammateCardWidget = QWidget()
        teammateCardWidget.setLayout(teammateLayout)
        teammateCard.viewLayout.addWidget(teammateCardWidget)
        
        # 将两个卡片添加到顶部布局
        topLayout.addWidget(iconCard, 1)
        topLayout.addWidget(teammateCard, 1)
        
        # 识别队友卡片
        recognitionCard = HeaderCardWidget(interface)
        recognitionCard.setTitle("识别队友")
        recognitionLayout = QVBoxLayout()
        recognitionLayout.setSpacing(18)
        recognitionLayout.setContentsMargins(0, 8, 0, 8)
        
        # 控制面板区域
        controlsPanel = QFrame()
        controlsPanel.setObjectName("cardFrame")
        controlsPanelLayout = QHBoxLayout(controlsPanel)
        controlsPanelLayout.setSpacing(16)
        controlsPanelLayout.setContentsMargins(16, 12, 16, 12)
        
        # 选择识别位置按钮
        selectPositionBtn = PrimaryPushButton("选择识别位置")
        selectPositionBtn.setIcon(FIF.EDIT)
        selectPositionBtn.setMinimumWidth(160)
        
        # 识别状态显示
        statusLabel = BodyLabel("状态: 未开始识别")
        statusLabel.setStyleSheet("color: #888; font-size: 14px;")
        
        controlsPanelLayout.addWidget(selectPositionBtn)
        controlsPanelLayout.addWidget(statusLabel)
        controlsPanelLayout.addStretch(1)
        
        # 预览区域
        previewArea = QFrame()
        previewArea.setObjectName("cardFrame")
        previewArea.setStyleSheet("#cardFrame{background-color: #f8f9fa; color: #333333; border-radius: 10px; border: 1px solid #e0e0e0;}")
        previewLayout = QVBoxLayout(previewArea)
        previewLayout.setContentsMargins(10, 10, 10, 10)
        
        previewTitle = QLabel("队友信息预览")
        previewTitle.setAlignment(Qt.AlignCenter)
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
        self.teammateInfoPreview.setStyleSheet("color: #333333; font-size: 14px;")
        scrollLayout.addWidget(self.teammateInfoPreview)
        
        scrollArea.setWidget(scrollContent)
        
        previewLayout.addWidget(previewTitle)
        previewLayout.addWidget(scrollArea)
        
        # 添加更新按钮
        updateInfoBtn = PushButton("刷新队友信息")
        updateInfoBtn.setIcon(FIF.SYNC)
        if self.parent():
            updateInfoBtn.clicked.connect(self.parent().update_teammate_preview)
        previewLayout.addWidget(updateInfoBtn)
        
        # 底部控制按钮
        buttonLayout = QHBoxLayout()
        buttonLayout.setSpacing(16)
        
        startBtn = PrimaryPushButton("开始识别")
        startBtn.setIcon(FIF.PLAY)
        startBtn.setMinimumWidth(130)
        
        stopBtn = PushButton("停止")
        stopBtn.setIcon(FIF.CANCEL)
        stopBtn.setMinimumWidth(130)
        
        saveBtn = PushButton("导出配置")
        saveBtn.setIcon(FIF.SAVE)
        saveBtn.setMinimumWidth(130)
        
        # 连接按钮事件
        if self.parent():
            selectPositionBtn.clicked.connect(self.parent().select_recognition_position)
            startBtn.clicked.connect(self.parent().start_recognition_from_calibration)
            stopBtn.clicked.connect(self.parent().stop_recognition)
            saveBtn.clicked.connect(self.parent().export_recognition_config)
        
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
        layout.addWidget(recognitionCard, 1)
        
        # 保存引用以便后续更新
        self.selectPositionBtn = selectPositionBtn
        self.statusLabel = statusLabel
    
    def setup_health_monitor_interface(self, interface, health_monitor=None):
        """设置血条监控界面
        
        参数:
            interface: 要设置的界面实例
            health_monitor: 健康监控实例
        """
        layout = QVBoxLayout(interface)
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
        
        setColorBtn = PushButton("设置血条颜色")
        setColorBtn.setIcon(FIF.PALETTE)
        setColorBtn.setMinimumWidth(120)
        
        setAllColorsBtn = PushButton("统一设置颜色")
        setAllColorsBtn.setIcon(FIF.BRUSH)
        setAllColorsBtn.setMinimumWidth(120)
        
        # 连接按钮事件
        if health_monitor:
            startMonitorBtn.clicked.connect(health_monitor.start_monitoring)
            stopMonitorBtn.clicked.connect(health_monitor.stop_monitoring)
            
        if self.parent():
            setColorBtn.clicked.connect(self.parent().setTeammateHealthBarColor)
            setAllColorsBtn.clicked.connect(self.parent().handleSetAllTeammatesColor)
        
        controlLayout.addWidget(startMonitorBtn)
        controlLayout.addWidget(stopMonitorBtn)
        controlLayout.addWidget(setColorBtn)
        controlLayout.addWidget(setAllColorsBtn)
        controlLayout.addStretch(1)
        
        # 血条展示区域
        self.health_bars_frame = QFrame()
        self.health_bars_frame.setObjectName("cardFrame")
        self.health_bars_frame.setStyleSheet("QFrame#cardFrame { background-color: rgba(240, 240, 240, 0.7); border-radius: 8px; padding: 10px; }")
        healthBarsLayout = QVBoxLayout(self.health_bars_frame)
        healthBarsLayout.setSpacing(12)
        healthBarsLayout.setContentsMargins(15, 15, 15, 15)
        
        # 设置健康可视化的展示框架
        self.health_visualization.set_health_bars_frame(self.health_bars_frame)
        
        # 添加到监控布局
        layout.addLayout(titleLayout)
        layout.addLayout(controlLayout)
        layout.addWidget(self.health_bars_frame, 1)
        
        # 设置卡片
        settingsCard = HeaderCardWidget(interface)
        settingsCard.setTitle("血条监控设置")
        
        settingsLayout = QVBoxLayout()
        settingsLayout.setSpacing(12)
        
        # 基本设置组
        paramsGroup = QGroupBox("监控参数", interface)
        paramsGroupLayout = QVBoxLayout()
        
        # 阈值设置
        thresholdLayout = QHBoxLayout()
        threshold_value = 30
        if health_monitor:
            threshold_value = int(health_monitor.health_threshold)
        self.thresholdLabel = BodyLabel(f"血条阈值: {threshold_value}%")
        self.thresholdSlider = Slider(Qt.Horizontal)
        self.thresholdSlider.setRange(0, 100)
        self.thresholdSlider.setValue(threshold_value)
        thresholdLayout.addWidget(self.thresholdLabel)
        thresholdLayout.addWidget(self.thresholdSlider)
        
        # 采样率设置
        samplingLayout = QHBoxLayout()
        samplingLabel = BodyLabel("采样率 (fps):")
        self.samplingSpinBox = SpinBox()
        self.samplingSpinBox.setRange(1, 60)
        self.samplingSpinBox.setValue(10)
        samplingLayout.addWidget(samplingLabel)
        samplingLayout.addWidget(self.samplingSpinBox)
        
        # 添加所有参数设置
        paramsGroupLayout.addLayout(thresholdLayout)
        paramsGroupLayout.addLayout(samplingLayout)
        
        # 自动点击低血量队友功能开关
        autoClickLayout = QHBoxLayout()
        autoClickLabel = BodyLabel("自动点击低血量队友:")
        self.autoClickSwitch = SwitchButton()
        auto_select_enabled = False
        if health_monitor and hasattr(health_monitor, 'auto_select_enabled'):
            auto_select_enabled = health_monitor.auto_select_enabled
        self.autoClickSwitch.setChecked(auto_select_enabled)
        
        # 新增：职业优先级下拉框
        priorityLabel = BodyLabel("优先职业:")
        self.priorityComboBox = ComboBox()
        self.priorityComboBox.setFixedWidth(120)
        
        # 连接信号
        if self.parent():
            self.thresholdSlider.valueChanged.connect(
                lambda v: self.parent().update_health_threshold(v, self.thresholdLabel))
            self.samplingSpinBox.valueChanged.connect(self.parent().update_sampling_rate)
            self.autoClickSwitch.checkedChanged.connect(self.parent().toggle_auto_click_low_health)
            self.priorityComboBox.currentTextChanged.connect(self.parent().update_priority_profession)
        
        autoClickLayout.addWidget(autoClickLabel)
        autoClickLayout.addWidget(self.autoClickSwitch)
        autoClickLayout.addSpacing(20)
        autoClickLayout.addWidget(priorityLabel)
        autoClickLayout.addWidget(self.priorityComboBox)
        autoClickLayout.addStretch(1)
        paramsGroupLayout.addLayout(autoClickLayout)
        
        paramsGroup.setLayout(paramsGroupLayout)
        
        # 添加到主设置布局
        settingsLayout.addWidget(paramsGroup)
        settingsCardWidget = QWidget()
        settingsCardWidget.setLayout(settingsLayout)
        settingsCard.viewLayout.addWidget(settingsCardWidget)
        
        # 添加卡片到主布局
        layout.addWidget(settingsCard)
        
        # 为此接口连接信号和槽
        # ... 信号连接代码 ...
    
    def setup_assist_interface(self, interface):
        """设置辅助功能界面
        
        参数:
            interface: 要设置的界面实例
        """
        # 实现辅助功能界面的构建
        layout = QVBoxLayout(interface)
        # ... 构建代码 ...
    
    def setup_settings_interface(self, interface):
        """设置系统设置界面
        
        参数:
            interface: 要设置的界面实例
        """
        # 实现系统设置界面的构建
        layout = QVBoxLayout(interface)
        # ... 构建代码 ...
    
    def setup_voice_settings_interface(self, interface):
        """设置语音设置界面
        
        参数:
            interface: 要设置的界面实例
        """
        # 实现语音设置界面的构建
        layout = QVBoxLayout(interface)
        # ... 构建代码 ...
        
        # 保存关键控件的引用
        self.voiceTypeCombo = ComboBox()
        self.voiceSpeedSlider = Slider(Qt.Horizontal)
        self.volumeSlider = Slider(Qt.Horizontal)
        
        # 语音警告设置控件
        self.low_health_warning_checkbox = CheckBox("启用低血量语音警告")
        self.warning_threshold_spinbox = SpinBox()
        self.warning_cooldown_spinbox = SpinBox()
        self.warning_text_edit = LineEdit()
        self.team_danger_warning_checkbox = CheckBox("启用团队危险语音警告")
        self.team_warning_threshold_spinbox = SpinBox()
        self.team_warning_text_edit = LineEdit()
    
    def update_icon_count(self):
        """更新职业图标数量显示"""
        profession_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "profession_icons")
        if os.path.exists(profession_path):
            self.icon_count = len([f for f in os.listdir(profession_path) if f.endswith(('.png', '.jpg', '.jpeg'))])
        else:
            self.icon_count = 0
            
        if hasattr(self, 'iconInfoLabel'):
            self.iconInfoLabel.setText(f'已加载 {self.icon_count} 个职业图标')
    
    def update_teammate_preview(self, team):
        """更新队友信息预览显示
        
        参数:
            team: 队伍实例
        """
        if not hasattr(self, 'teammateInfoPreview') or not self.teammateInfoPreview:
            return
        
        if not team.members:
            self.teammateInfoPreview.setText("当前没有队友信息，请先添加或加载队友。")
            return
        
        # ... 实现预览内容构建 ...
    
    def init_health_bars_ui(self, team):
        """初始化血条UI显示
        
        参数:
            team: 队伍实例
        """
        return self.health_visualization.init_health_bars_ui(team.members)
    
    def check_health_warnings(self, health_data, main_window):
        """检查并播放血量警告语音
        
        参数:
            health_data: 血量数据列表
            main_window: 主窗口实例，用于播放语音
        """
        # 如果语音警告设置不存在，直接返回
        if not self.low_health_warning_enabled and not self.team_danger_warning_enabled:
            return
            
        # 获取当前时间
        import time
        current_time = time.time()
        
        # 计算低血量队友数
        health_data_map = {item[0]: (item[1], item[2]) for item in health_data}
        low_hp_count = 0
        total_alive = 0
        
        for _, (hp, alive_status) in health_data_map.items():
            if alive_status:
                total_alive += 1
                if hp <= self.warning_threshold:
                    low_hp_count += 1
        
        # 获取语音设置
        voice = main_window.get_selected_voice(self.voiceTypeCombo)
        
        # 团队危险警告
        if self.team_danger_warning_enabled and low_hp_count >= self.team_warning_threshold:
            team_warning_key = "team_danger"
            last_time = self.last_voice_warning_time.get(team_warning_key, 0)
            
            if current_time - last_time >= self.warning_cooldown:
                warning_text = self.team_warning_text.format(count=low_hp_count, total=total_alive)
                main_window.play_speech_threaded(warning_text, voice)
                self.last_voice_warning_time[team_warning_key] = current_time
                return
        
        # 个人低血量警告
        if self.low_health_warning_enabled:
            for name, health, is_alive in health_data:
                if is_alive and health <= self.warning_threshold:
                    teammate_warning_key = f"low_health_{name}"
                    last_time = self.last_voice_warning_time.get(teammate_warning_key, 0)
                    
                    if current_time - last_time >= self.warning_cooldown:
                        # 获取职业信息
                        profession = "未知"
                        for member in main_window.team.members:
                            if member.name == name:
                                profession = member.profession
                                break
                        
                        warning_text = self.warning_text.format(name=name, health=round(health), profession=profession)
                        main_window.play_speech_threaded(warning_text, voice)
                        self.last_voice_warning_time[teammate_warning_key] = current_time
                        break
    
    def update_monitor_status(self, status_message):
        """更新监控状态信息
        
        参数:
            status_message: 状态消息文本
        """
        if not hasattr(self, 'monitor_status_label') or not self.monitor_status_label:
            return
            
        # 更新状态标签
        self.monitor_status_label.setText(status_message)
        
        # 根据关键词设置不同的状态颜色
        if "错误" in status_message or "失败" in status_message:
            self.monitor_status_label.setStyleSheet("color: #e74c3c;")  # 红色
        elif "警告" in status_message:
            self.monitor_status_label.setStyleSheet("color: #f39c12;")  # 黄色
        elif "成功" in status_message or "启动" in status_message or "启用" in status_message or "禁用" in status_message:
            self.monitor_status_label.setStyleSheet("color: #2ecc71;")  # 绿色
        else:
            self.monitor_status_label.setStyleSheet("color: #3498db;")  # 蓝色
    
    def show_info_message(self, title, content, parent=None, duration=2000):
        """显示信息消息
        
        参数:
            title: 标题
            content: 内容
            parent: 父窗口
            duration: 显示时长
        """
        InfoBar.success(
            title=title,
            content=content,
            orient=Qt.Horizontal,
            isClosable=True,
            position=InfoBarPosition.TOP,
            duration=duration,
            parent=parent
        )
    
    def show_warning_message(self, title, content, parent=None, duration=2000):
        """显示警告消息
        
        参数:
            title: 标题
            content: 内容
            parent: 父窗口
            duration: 显示时长
        """
        InfoBar.warning(
            title=title,
            content=content,
            orient=Qt.Horizontal,
            isClosable=True,
            position=InfoBarPosition.TOP,
            duration=duration,
            parent=parent
        )
    
    def show_error_message(self, title, content, parent=None, duration=3000):
        """显示错误消息
        
        参数:
            title: 标题
            content: 内容
            parent: 父窗口
            duration: 显示时长
        """
        InfoBar.error(
            title=title,
            content=content,
            orient=Qt.Horizontal,
            isClosable=True,
            position=InfoBarPosition.TOP,
            duration=duration,
            parent=parent
        )
    
    def load_profession_options(self):
        """加载职业图标文件夹中的所有职业作为下拉框选项"""
        # ... 实现代码 ...
    
    def update_voice_settings(self, rate_value, volume_value):
        """更新语音设置控件
        
        参数:
            rate_value: 语速值
            volume_value: 音量值
        """
        if hasattr(self, 'voiceSpeedSlider') and self.voiceSpeedSlider:
            self.voiceSpeedSlider.setValue(rate_value)
            
        if hasattr(self, 'volumeSlider') and self.volumeSlider:
            self.volumeSlider.setValue(volume_value)
    
    def get_voice_settings(self):
        """获取当前语音设置
        
        返回:
            dict: 语音设置字典
        """
        if not hasattr(self, 'voiceSpeedSlider') or not hasattr(self, 'volumeSlider'):
            return {}
            
        settings = {
            'rate': self.voiceSpeedSlider.value() if self.voiceSpeedSlider else 5,
            'volume': self.volumeSlider.value() if self.volumeSlider else 80
        }
        
        if hasattr(self, 'voiceTypeCombo') and self.voiceTypeCombo:
            settings['selected_voice'] = self.voiceTypeCombo.currentText()
            
        return settings
    
    def get_alert_settings(self):
        """获取语音警告设置
        
        返回:
            dict: 警告设置字典
        """
        settings = {
            'enabled': self.low_health_warning_enabled,
            'threshold': self.warning_threshold,
            'cooldown': self.warning_cooldown,
            'warning_text': self.warning_text,
            'team_danger_enabled': self.team_danger_warning_enabled,
            'team_danger_threshold': self.team_warning_threshold,
            'team_danger_text': self.team_warning_text
        }
        return settings
    
    def load_alert_settings(self, settings):
        """加载语音警告设置
        
        参数:
            settings: 设置字典
        """
        self.low_health_warning_enabled = settings.get('enabled', False)
        if hasattr(self, 'low_health_warning_checkbox'):
            self.low_health_warning_checkbox.setChecked(self.low_health_warning_enabled)
            
        self.warning_threshold = float(settings.get('threshold', 30.0))
        if hasattr(self, 'warning_threshold_spinbox'):
            self.warning_threshold_spinbox.setValue(int(self.warning_threshold))
            
        self.warning_cooldown = float(settings.get('cooldown', 5.0))
        if hasattr(self, 'warning_cooldown_spinbox'):
            self.warning_cooldown_spinbox.setValue(int(self.warning_cooldown))
            
        self.warning_text = settings.get('warning_text', "{name}血量过低，仅剩{health}%")
        if hasattr(self, 'warning_text_edit'):
            self.warning_text_edit.setText(self.warning_text)
            
        self.team_danger_warning_enabled = settings.get('team_danger_enabled', False)
        if hasattr(self, 'team_danger_warning_checkbox'):
            self.team_danger_warning_checkbox.setChecked(self.team_danger_warning_enabled)
            
        self.team_warning_threshold = settings.get('team_danger_threshold', 2)
        if hasattr(self, 'team_warning_threshold_spinbox'):
            self.team_warning_threshold_spinbox.setValue(self.team_warning_threshold)
            
        self.team_warning_text = settings.get('team_danger_text', "警告，团队状态危险，{count}名队友血量过低")
        if hasattr(self, 'team_warning_text_edit'):
            self.team_warning_text_edit.setText(self.team_warning_text) 