"""
高级技能系统UI示例

展示如何创建高级技能系统的用户界面。
"""

from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QColor
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                             QLabel, QTabWidget, QGridLayout, QListWidget, QListWidgetItem,
                             QAbstractItemView)
from qfluentwidgets import (PushButton, PrimaryPushButton, ComboBox, LineEdit, SpinBox, 
                           DoubleSpinBox, CheckBox, SwitchButton, ScrollArea, CardWidget, 
                           HeaderCardWidget, StrongBodyLabel, BodyLabel, ColorDialog,
                           MessageBox, InfoBar, InfoBarPosition)

import time
from advanced_skill_system import AdvancedSkill, TriggerCondition, advanced_skill_manager

class AdvancedSkillUI(QWidget):
    """高级技能界面类"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent
        self.initUI()
    
    def initUI(self):
        """初始化UI"""
        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # 标题和状态区域
        titleLayout = QHBoxLayout()
        titleLabel = StrongBodyLabel("高级技能系统")
        titleLabel.setStyleSheet("font-size: 18px; font-weight: bold;")
        
        self.statusLabel = BodyLabel("准备就绪")
        
        titleLayout.addWidget(titleLabel)
        titleLayout.addStretch(1)
        titleLayout.addWidget(self.statusLabel)
        
        # 连接信号
        advanced_skill_manager.signals.status_signal.connect(self.updateStatus)
        advanced_skill_manager.signals.skill_used_signal.connect(lambda: self.refreshSkillList())
        
        # 控制按钮区域
        controlLayout = QHBoxLayout()
        
        startButton = PrimaryPushButton("开始")
        startButton.clicked.connect(advanced_skill_manager.start_cycle)
        
        stopButton = PushButton("停止")
        stopButton.clicked.connect(advanced_skill_manager.stop_cycle)
        
        hotkeysButton = PushButton("设置快捷键")
        hotkeysButton.clicked.connect(self.showHotkeySettings)
        
        controlLayout.addWidget(startButton)
        controlLayout.addWidget(stopButton)
        controlLayout.addWidget(hotkeysButton)
        controlLayout.addStretch(1)
        
        # 选项卡区域
        tabWidget = QTabWidget()
        
        # 技能列表选项卡
        skillsTab = QWidget()
        skillsLayout = QVBoxLayout(skillsTab)
        
        # 技能卡片
        skillCard = HeaderCardWidget(self)
        skillCard.setTitle("技能列表")
        
        skillsListLayout = QVBoxLayout()
        
        # 创建技能列表控件
        self.skillsListWidget = QListWidget()
        self.skillsListWidget.setSelectionMode(QAbstractItemView.SingleSelection)
        self.skillsListWidget.setStyleSheet("""
            QListWidget {
                background: rgba(255, 255, 255, 0.7);
                border-radius: 8px;
                padding: 5px;
            }
            QListWidget::item {
                height: 40px;
                border-radius: 4px;
                padding: 5px;
                margin: 2px 0;
            }
            QListWidget::item:selected {
                background: rgba(0, 168, 174, 0.2);
            }
            QListWidget::item:hover {
                background: rgba(0, 0, 0, 0.05);
            }
        """)
        
        # 初始化技能列表
        self.refreshSkillList()
        
        skillsListLayout.addWidget(self.skillsListWidget)
        
        # 技能操作按钮
        skillButtonsLayout = QHBoxLayout()
        
        addSkillButton = PrimaryPushButton("添加技能")
        addSkillButton.clicked.connect(self.addSkill)
        
        editSkillButton = PushButton("编辑技能")
        editSkillButton.clicked.connect(self.editSkill)
        
        removeSkillButton = PushButton("删除技能")
        removeSkillButton.clicked.connect(self.removeSkill)
        
        skillButtonsLayout.addWidget(addSkillButton)
        skillButtonsLayout.addWidget(editSkillButton)
        skillButtonsLayout.addWidget(removeSkillButton)
        skillButtonsLayout.addStretch(1)
        
        skillsListLayout.addLayout(skillButtonsLayout)
        
        # 添加到卡片
        skillCardWidget = QWidget()
        skillCardWidget.setLayout(skillsListLayout)
        skillCard.viewLayout.addWidget(skillCardWidget)
        
        skillsLayout.addWidget(skillCard)
        
        # 条件选项卡
        conditionsTab = QWidget()
        conditionsLayout = QVBoxLayout(conditionsTab)
        
        # 条件卡片
        conditionCard = HeaderCardWidget(self)
        conditionCard.setTitle("触发条件")
        
        conditionsListLayout = QVBoxLayout()
        
        # 简化示例
        conditionLabel = BodyLabel("条件列表会显示在这里")
        conditionsListLayout.addWidget(conditionLabel)
        
        # 条件操作按钮
        conditionButtonsLayout = QHBoxLayout()
        
        addColorCondButton = PushButton("添加颜色条件")
        addColorCondButton.clicked.connect(lambda: self.addCondition("color"))
        
        addTextCondButton = PushButton("添加文本条件")
        addTextCondButton.clicked.connect(lambda: self.addCondition("text"))
        
        addTimeCondButton = PushButton("添加时间条件")
        addTimeCondButton.clicked.connect(lambda: self.addCondition("time"))
        
        addComboCondButton = PushButton("添加组合条件")
        addComboCondButton.clicked.connect(lambda: self.addCondition("combo"))
        
        conditionButtonsLayout.addWidget(addColorCondButton)
        conditionButtonsLayout.addWidget(addTextCondButton)
        conditionButtonsLayout.addWidget(addTimeCondButton)
        conditionButtonsLayout.addWidget(addComboCondButton)
        conditionButtonsLayout.addStretch(1)
        
        conditionsListLayout.addLayout(conditionButtonsLayout)
        
        # 添加到卡片
        conditionCardWidget = QWidget()
        conditionCardWidget.setLayout(conditionsListLayout)
        conditionCard.viewLayout.addWidget(conditionCardWidget)
        
        conditionsLayout.addWidget(conditionCard)
        
        # 添加选项卡
        tabWidget.addTab(skillsTab, "技能")
        tabWidget.addTab(conditionsTab, "条件")
        
        # 添加到主布局
        layout.addLayout(titleLayout)
        layout.addLayout(controlLayout)
        layout.addWidget(tabWidget)
    
    def refreshSkillList(self):
        """刷新技能列表"""
        self.skillsListWidget.clear()
        
        for skill in advanced_skill_manager.skills:
            # 创建项目
            item = QListWidgetItem(str(skill))
            
            # 设置状态颜色
            if not skill.enabled:
                item.setForeground(QColor(150, 150, 150))  # 灰色表示禁用
            elif time.time() - skill.last_used_time < skill.cooldown:
                item.setForeground(QColor(231, 76, 60))  # 红色表示冷却中
            else:
                item.setForeground(QColor(46, 204, 113))  # 绿色表示可用
            
            self.skillsListWidget.addItem(item)
    
    def updateStatus(self, status):
        """更新状态标签"""
        self.statusLabel.setText(status)
    
    def showHotkeySettings(self):
        """显示快捷键设置对话框"""
        # 简化示例
        InfoBar.success(
            title='快捷键设置',
            content="此功能尚未实现",
            orient=Qt.Horizontal,
            isClosable=True,
            position=InfoBarPosition.TOP,
            duration=2000,
            parent=self
        )
    
    def addSkill(self):
        """添加技能"""
        # 简化示例
        InfoBar.success(
            title='添加技能',
            content="此功能尚未实现",
            orient=Qt.Horizontal,
            isClosable=True,
            position=InfoBarPosition.TOP,
            duration=2000,
            parent=self
        )
        # 添加后刷新列表
        self.refreshSkillList()
    
    def editSkill(self):
        """编辑技能"""
        # 获取当前选中项
        current_item = self.skillsListWidget.currentItem()
        if not current_item:
            InfoBar.warning(
                title='未选择技能',
                content='请先选择要编辑的技能',
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=2000,
                parent=self
            )
            return
            
        # 解析技能名称
        skill_text = current_item.text()
        skill_name = skill_text.split(' - ')[0]
        
        # 获取技能对象
        skill = advanced_skill_manager.get_skill(skill_name)
        if not skill:
            InfoBar.error(
                title='错误',
                content='未找到技能对象',
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=2000,
                parent=self
            )
            return
        
        # 实际项目中这里应该弹出编辑对话框
        InfoBar.success(
            title='编辑技能',
            content=f"将要编辑技能: {skill_name}",
            orient=Qt.Horizontal,
            isClosable=True,
            position=InfoBarPosition.TOP,
            duration=2000,
            parent=self
        )
        
        # 编辑后刷新列表
        self.refreshSkillList()
    
    def removeSkill(self):
        """删除技能"""
        # 获取当前选中项
        current_item = self.skillsListWidget.currentItem()
        if not current_item:
            InfoBar.warning(
                title='未选择技能',
                content='请先选择要删除的技能',
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=2000,
                parent=self
            )
            return
            
        # 解析技能名称
        skill_text = current_item.text()
        skill_name = skill_text.split(' - ')[0]
        
        # 确认删除
        msgBox = MessageBox(
            '确认删除',
            f'确定要删除技能 {skill_name} 吗？',
            self.parent if self.parent else self
        )
        msgBox.yesButton.setText('确定')
        msgBox.cancelButton.setText('取消')
        
        if msgBox.exec():
            # 删除技能
            if advanced_skill_manager.remove_skill(skill_name):
                # 刷新列表
                self.refreshSkillList()
                
                # 成功提示
                InfoBar.success(
                    title='删除成功',
                    content=f'技能 {skill_name} 已删除',
                    orient=Qt.Horizontal,
                    isClosable=True,
                    position=InfoBarPosition.TOP,
                    duration=2000,
                    parent=self
                )
            else:
                InfoBar.error(
                    title='删除失败',
                    content=f'未找到技能 {skill_name}',
                    orient=Qt.Horizontal,
                    isClosable=True,
                    position=InfoBarPosition.TOP,
                    duration=2000,
                    parent=self
                )
    
    def addCondition(self, condition_type):
        """添加条件
        
        参数:
            condition_type (str): 条件类型
        """
        # 简化示例
        InfoBar.success(
            title='添加条件',
            content=f"将要添加{condition_type}条件",
            orient=Qt.Horizontal,
            isClosable=True,
            position=InfoBarPosition.TOP,
            duration=2000,
            parent=self
        )

# 如果作为独立应用运行
if __name__ == "__main__":
    import sys
    
    app = QApplication(sys.argv)
    window = QMainWindow()
    window.setWindowTitle("高级技能系统演示")
    window.resize(800, 600)
    
    advanced_skill_ui = AdvancedSkillUI(window)
    window.setCentralWidget(advanced_skill_ui)
    
    window.show()
    sys.exit(app.exec_())