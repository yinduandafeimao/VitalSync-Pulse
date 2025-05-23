import os
import cv2
import numpy as np
import time
import threading
import pyautogui
import keyboard
from datetime import datetime
from PyQt5.QtCore import Qt, QTimer, QRect, pyqtSignal, QObject, QEvent
from PyQt5.QtGui import QColor, QKeySequence
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QFrame, QGridLayout,
                            QLabel, QListWidget, QListWidgetItem, QAbstractItemView,
                            QComboBox, QSpacerItem, QSizePolicy, QTextEdit, QDialog)

from qfluentwidgets import (PushButton, PrimaryPushButton, ComboBox, RadioButton, CheckBox,
                           Slider, SwitchButton, ToggleButton, SubtitleLabel, BodyLabel,
                           Action, MessageBox, MessageBoxBase, InfoBar, TransparentPushButton,
                           LineEdit, StrongBodyLabel, CaptionLabel, SpinBox, DoubleSpinBox,
                           ScrollArea, CardWidget, HeaderCardWidget, InfoBarPosition, FluentIcon as FIF,
                           TitleLabel)

from 选择框 import show_selection_box
from skill_cycle import Skill, new_skill_manager
from skill_data_models import SkillGroup, Action, config_manager, Skill as DataSkill, ConditionReference
import traceback

class SkillCycleInterface(QWidget):
    """技能循环界面类"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent
        self.skill_manager = new_skill_manager  # 使用新的技能循环管理器
        self.initUI()
        self._recent_messages = {}  # 用于存储最近显示的消息
        self._is_closing = False  # 标记组件是否正在关闭
        
        # 添加定时器初始化
        self.refresh_timer = QTimer()
        self.refresh_timer.timeout.connect(self.refresh_skill_list)
        self.refresh_timer.start(500)  # 设置500毫秒刷新一次，可根据性能调整

    def __del__(self):
        """组件销毁时进行清理"""
        self._is_closing = True
        # 停止定时器
        if hasattr(self, 'refresh_timer') and self.refresh_timer.isActive():
            self.refresh_timer.stop()
        # 断开信号连接，避免悬挂引用
        try:
            self.skill_manager.signals.status_signal.disconnect(self.update_skill_status)
            self.skill_manager.signals.skill_used_signal.disconnect()
        except:
            pass

    def closeEvent(self, event):
        """窗口关闭事件"""
        self._is_closing = True
        # 停止定时器
        if hasattr(self, 'refresh_timer') and self.refresh_timer.isActive():
            self.refresh_timer.stop()
        # 确保父类方法被调用
        super().closeEvent(event)

    def initUI(self):
        """初始化技能循环界面"""
        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # 标题和状态信息
        titleLayout = QHBoxLayout()
        titleLabel = StrongBodyLabel("技能循环管理")
        titleLabel.setStyleSheet("font-size: 18px; font-weight: bold;")
        
        self.skill_status_label = BodyLabel("准备就绪")
        self.skill_status_label.setStyleSheet("color: #3498db;")
        # 连接信号
        self.skill_manager.signals.status_signal.connect(self.update_skill_status)
        
        titleLayout.addWidget(titleLabel)
        titleLayout.addStretch(1)
        titleLayout.addWidget(self.skill_status_label)
        
        # 顶部控制按钮区域
        controlLayout = QHBoxLayout()
        
        startCycleBtn = PrimaryPushButton("开始循环")
        startCycleBtn.setIcon(FIF.PLAY)
        startCycleBtn.setMinimumWidth(120)
        
        stopCycleBtn = PushButton("停止循环")
        stopCycleBtn.setIcon(FIF.CLOSE)
        stopCycleBtn.setMinimumWidth(120)
        
        setHotkeyBtn = PushButton("快捷键设置")
        setHotkeyBtn.setIcon(FIF.SETTING)
        setHotkeyBtn.setMinimumWidth(120)
        
        # 添加条件管理按钮
        conditionsBtn = PushButton("条件管理")
        conditionsBtn.setIcon(FIF.CHECKBOX)
        conditionsBtn.setMinimumWidth(120)
        
        # 连接按钮事件
        startCycleBtn.clicked.connect(self.skill_manager.start_cycle)
        stopCycleBtn.clicked.connect(self.skill_manager.stop_cycle)
        setHotkeyBtn.clicked.connect(self.show_skill_hotkey_settings)
        conditionsBtn.clicked.connect(self.manage_conditions)
        
        controlLayout.addWidget(startCycleBtn)
        controlLayout.addWidget(stopCycleBtn)
        controlLayout.addWidget(setHotkeyBtn)
        controlLayout.addWidget(conditionsBtn)
        controlLayout.addStretch(1)
        
        # 技能组选择区域
        groupLayout = QHBoxLayout()
        groupLabel = BodyLabel("技能组:")
        self.groupComboBox = ComboBox()
        self.refresh_skill_groups()
        
        groupLayout.addWidget(groupLabel)
        groupLayout.addWidget(self.groupComboBox)
        
        manageGroupBtn = PushButton("管理组")
        manageGroupBtn.setIcon(FIF.FOLDER)
        groupLayout.addWidget(manageGroupBtn)
        manageGroupBtn.clicked.connect(self.manage_skill_groups)
        
        # 技能列表区域
        skillListCard = HeaderCardWidget(self)
        skillListCard.setTitle("技能列表")
        
        skillListLayout = QVBoxLayout()
        
        # 添加技能组选择到技能列表卡片
        skillListLayout.addLayout(groupLayout)
        
        # 创建技能列表控件
        self.skillListWidget = QListWidget()
        self.skillListWidget.setSelectionMode(QAbstractItemView.SingleSelection)
        self.skillListWidget.setStyleSheet("""
            QListWidget {
                border: 1px solid #e0e0e0;
                border-radius: 5px;
                background-color: white;
                outline: none;
                padding: 2px;
            }
            QListWidget::item {
                padding: 6px;
                border-bottom: 1px solid #f0f0f0;
                margin: 2px 0;
                border-radius: 4px;
            }
            QListWidget::item:hover {
                background-color: rgba(25, 118, 210, 0.1);
            }
            QListWidget::item:selected {
                background-color: rgba(25, 118, 210, 0.2);
                color: #1976d2;
            }
            QListWidget::item:selected:active {
                background-color: rgba(25, 118, 210, 0.3);
                color: #1976d2;
            }
        """)
        
        # 刷新技能列表
        self.refresh_skill_list()
        
        # 连接技能组选择的变化信号
        self.groupComboBox.currentIndexChanged.connect(self.on_group_changed)
        
        skillListLayout.addWidget(self.skillListWidget)
        
        # 技能管理按钮区域
        skillBtnLayout = QHBoxLayout()
        
        addSkillBtn = PrimaryPushButton("添加技能")
        addSkillBtn.setIcon(FIF.ADD)
        
        editSkillBtn = PushButton("编辑技能")
        editSkillBtn.setIcon(FIF.EDIT)
        
        removeSkillBtn = PushButton("删除技能")
        removeSkillBtn.setIcon(FIF.DELETE)
        
        setIconBtn = PushButton("设置图标")
        setIconBtn.setIcon(FIF.CAMERA)
        
        # 连接按钮事件
        addSkillBtn.clicked.connect(self.add_new_skill)
        editSkillBtn.clicked.connect(self.edit_selected_skill)
        removeSkillBtn.clicked.connect(self.remove_selected_skill)
        setIconBtn.clicked.connect(self.set_selected_skill_icon)
        
        skillBtnLayout.addWidget(addSkillBtn)
        skillBtnLayout.addWidget(editSkillBtn)
        skillBtnLayout.addWidget(removeSkillBtn)
        skillBtnLayout.addWidget(setIconBtn)
        skillBtnLayout.addStretch(1)
        
        skillListLayout.addLayout(skillBtnLayout)
        
        skillListCardWidget = QWidget()
        skillListCardWidget.setLayout(skillListLayout)
        skillListCard.viewLayout.addWidget(skillListCardWidget)
        
        # 技能参数设置区域
        settingsCard = HeaderCardWidget(self)
        settingsCard.setTitle("全局参数设置")
        
        settingsLayout = QVBoxLayout()
        
        # 更新间隔设置
        intervalLayout = QHBoxLayout()
        intervalLabel = BodyLabel(f"循环更新间隔(秒):")
        self.intervalSpinBox = DoubleSpinBox()
        self.intervalSpinBox.setRange(0.01, 10.0)
        self.intervalSpinBox.setSingleStep(0.01)
        self.intervalSpinBox.setValue(self.skill_manager.update_interval)
        intervalLayout.addWidget(intervalLabel)
        intervalLayout.addWidget(self.intervalSpinBox)
        intervalLayout.addStretch(1)
        
        # 导入导出按钮
        importExportLayout = QHBoxLayout()
        
        importBtn = PushButton("导入配置")
        # 修复图标问题，使用正确的图标
        try:
            importBtn.setIcon(FIF.DOWNLOAD)  # 改用下载图标替代导入
        except:
            pass  # 如果图标不存在，不设置图标
        
        exportBtn = PushButton("导出配置")
        try:
            exportBtn.setIcon(FIF.SHARE)
        except:
            pass  # 如果图标不存在，不设置图标
        
        importExportLayout.addWidget(importBtn)
        importExportLayout.addWidget(exportBtn)
        importExportLayout.addStretch(1)
        
        # 连接按钮事件
        importBtn.clicked.connect(self.import_config)
        exportBtn.clicked.connect(self.export_config)
        
        # 连接更新间隔的变化信号
        self.intervalSpinBox.valueChanged.connect(self.update_cycle_interval)
        
        # 添加所有设置到布局
        settingsLayout.addLayout(intervalLayout)
        settingsLayout.addLayout(importExportLayout)
        settingsLayout.addStretch(1)
        
        settingsCardWidget = QWidget()
        settingsCardWidget.setLayout(settingsLayout)
        settingsCard.viewLayout.addWidget(settingsCardWidget)
        
        # 将所有组件添加到主布局
        layout.addLayout(titleLayout)
        layout.addLayout(controlLayout)
        layout.addWidget(skillListCard, 1)  # 技能列表占据主要空间
        layout.addWidget(settingsCard)
        
        # 连接技能使用信号，在技能使用后立即刷新
        self.skill_manager.signals.skill_used_signal.connect(lambda name: self._schedule_refresh())
    
    def update_skill_status(self, status):
        """更新技能状态标签
        
        参数:
            status (str): 状态文本
        """
        if self._is_closing:
            return
            
        self.skill_status_label.setText(status)
        
    def refresh_skill_groups(self):
        """刷新技能组下拉列表"""
        # 记录当前选中的组ID
        current_selected_id = None
        if self.groupComboBox.count() > 0:
            current_selected_id = self.groupComboBox.currentData()
        
        # 清空下拉框并添加选项
        self.groupComboBox.clear()
        
        # 添加默认技能组
        self.groupComboBox.addItem("全部技能", "all")
        
        # 确保配置是最新的
        config_manager._load_system_config()
        
        # 获取所有技能组
        all_groups = config_manager.get_all_skill_groups()
        print(f"刷新技能组列表: 找到 {len(all_groups)} 个技能组")
        
        # 添加所有已定义的技能组
        for group in all_groups:
            if group.id and group.id != "default":  # 跳过默认组，它已经在前面添加了
                self.groupComboBox.addItem(group.name, group.id)
        
        # 恢复之前选中的组（如果存在）
        if current_selected_id:
            for i in range(self.groupComboBox.count()):
                if self.groupComboBox.itemData(i) == current_selected_id:
                    self.groupComboBox.setCurrentIndex(i)
                    break
        
        print(f"技能组刷新完成，当前选中: {self.groupComboBox.currentText()} (ID: {self.groupComboBox.currentData()})")
    
    def on_group_changed(self, index):
        """技能组选择变化时的处理
        
        参数:
            index (int): 选中的索引
        """
        # 获取当前选择的组ID
        current_group_id = self.groupComboBox.currentData()
        print(f"技能组变更: 组ID: {current_group_id}")
        
        # 如果是特定组，检查组信息
        if current_group_id and current_group_id != "all":
            # 获取技能组
            group = config_manager.get_skill_group(current_group_id)
            if not group:
                print(f"警告: 未找到ID为 {current_group_id} 的技能组")
        
        # 确保技能管理器配置已更新
        if self.skill_manager:
            self.skill_manager.load_config()
                
        # 刷新技能列表
        self.refresh_skill_list()
        
        # 强制更新UI
        self.skillListWidget.update()
    
    def manage_skill_groups(self):
        """管理技能组"""
        try:
            dialog = SkillGroupManagementDialog(
                parent=self.parent if self.parent else self,
                skill_manager=self.skill_manager
            )
            
            # 显示对话框
            if dialog.exec_():
                # 刷新技能组和列表
                self.refresh_skill_groups()
                self.refresh_skill_list()
                
        except Exception as e:
            print(f"打开技能组管理对话框时出错: {str(e)}")
            traceback.print_exc()
            # 使用show_message方法，它默认使用BOTTOM位置
            self.show_message("error", "错误", f"打开技能组管理对话框失败: {str(e)}", 2000)
        
    def import_config(self):
        """导入配置"""
        # TODO: 实现配置导入功能
        self.show_message("info", "功能开发中", "配置导入功能正在开发中...", 2000)
        
    def export_config(self):
        """导出配置"""
        # TODO: 实现配置导出功能
        self.show_message("info", "功能开发中", "配置导出功能正在开发中...", 2000)

    def refresh_skill_list(self):
        """刷新技能列表"""
        # 如果组件正在关闭，不执行刷新
        if hasattr(self, '_is_closing') and self._is_closing:
            return
            
        try:
            # 暂时禁用选中信号，避免频繁刷新
            self.skillListWidget.blockSignals(True)
            
            # 保存当前选中项的ID（如果有）
            current_skill_id = None
            current_item = self.skillListWidget.currentItem()
            if current_item and current_item.data(Qt.UserRole) is not None:
                current_skill_id = current_item.data(Qt.UserRole)
            
            # 获取当前选中的技能组
            current_group = None
            if self.groupComboBox.currentData() is not None:
                current_group = self.groupComboBox.currentData()
            
            # 获取技能列表
            skills_to_display = []
            try:
                # 先确保技能管理器配置是最新的
                if self.skill_manager:
                    self.skill_manager.load_config()
                
                # 根据技能组过滤技能
                if current_group is None or current_group == "all":
                    # 显示所有技能
                    skills_to_display = sorted(
                        self.skill_manager.skills,
                        key=lambda x: (x.priority if hasattr(x, 'priority') else 0)
                    )
                else:
                    # 显示指定组的技能
                    skills_to_display = sorted(
                        self.skill_manager.get_skills_by_group(current_group),
                        key=lambda x: (x.priority if hasattr(x, 'priority') else 0)
                    )
                print(f"当前显示技能数: {len(skills_to_display)}, 组: {current_group}")
            except Exception as e:
                print(f"获取技能列表时出错: {str(e)}")
                traceback.print_exc()
            
            # 清空列表并重新填充
            self.skillListWidget.clear()
                
            # 添加技能到列表
            for skill in skills_to_display:
                try:
                    # 检查技能是否有效
                    if not hasattr(skill, 'name') or not skill.name:
                        continue
                    
                    # 创建新的列表项
                    skill_name = getattr(skill, 'name', '未知技能')
                    item = QListWidgetItem(skill_name)
                    item.setData(Qt.UserRole, skill_name)
                    self.skillListWidget.addItem(item)
                    
                    # 更新项的状态（优先级、冷却时间等）
                    self._update_skill_item(item, skill)
                except Exception as e:
                    print(f"添加技能 {getattr(skill, 'name', '未知')} 到列表时出错: {str(e)}")
                    traceback.print_exc()
                    continue
            
            # 如果有之前选中的项，尝试重新选中
            if current_skill_id:
                for i in range(self.skillListWidget.count()):
                    item = self.skillListWidget.item(i)
                    if item and item.data(Qt.UserRole) == current_skill_id:
                        self.skillListWidget.setCurrentItem(item)
                        break
            
            # 恢复信号
            self.skillListWidget.blockSignals(False)
            
            # 强制更新UI
            self.skillListWidget.update()
            
        except Exception as e:
            print(f"刷新技能列表时出错: {str(e)}")
            traceback.print_exc()
    
    def _schedule_refresh(self):
        """安全地设置定时刷新，避免对象生命周期问题"""
        # 如果组件正在关闭，不再设置定时器
        if hasattr(self, '_is_closing') and self._is_closing:
            return
            
        try:
            # 使用弱引用方式设置定时刷新，避免对象被销毁后仍然执行
            QTimer.singleShot(100, lambda: self.refresh_skill_list() if hasattr(self, 'skillListWidget') and not self._is_closing else None)
        except RuntimeError:
            # 捕获可能的运行时错误，例如对象已被删除
            print("定时刷新出错，组件可能已被销毁")
            pass
    
    def add_new_skill(self):
        """添加新技能"""
        try:
            # 创建技能编辑对话框
            dialog = SkillEditDialog(parent=self, skill_manager=self.skill_manager)
            
            # 显示对话框并等待用户操作
            if dialog.exec_():
                # 获取用户设置的技能信息
                skill_info = dialog.get_skill_info()
                if skill_info:
                    # 解包元组到单独的变量
                    name, key, priority, cooldown, threshold, press_delay, release_delay, enabled, group_id = skill_info
                    
                    # 创建新技能对象
                    skill = Skill(name, key, priority)
                    skill.cooldown = cooldown
                    skill.threshold = threshold
                    skill.press_delay = press_delay
                    skill.release_delay = release_delay
                    skill.enabled = enabled
                    
                    # 添加到技能管理器
                    self.skill_manager.add_skill(skill)
                    
                    # 刷新技能列表
                    self.refresh_skill_list()
                    
                    # 显示通知
                    self.show_message("success", "成功", f"技能 {name} 已添加")
        except Exception as e:
            print(f"添加技能时出错: {str(e)}")
            traceback.print_exc()
    
    def edit_selected_skill(self):
        """编辑选中的技能"""
        try:
            # 获取选中的项
            current_item = self.skillListWidget.currentItem()
            if not current_item:
                return
                
            # 获取技能名称和对象
            skill_name = current_item.data(Qt.UserRole)
            if not skill_name:
                return
                
            skill = self.skill_manager.get_skill(skill_name)
            if not skill:
                return
            
            # 创建技能编辑对话框，传入选中的技能
            dialog = SkillEditDialog(parent=self, skill=skill, skill_manager=self.skill_manager)
            
            # 显示对话框并等待用户操作
            if dialog.exec_():
                # 获取用户设置的技能信息
                skill_info = dialog.get_skill_info()
                if skill_info:
                    # 解包元组到单独的变量
                    name, key, priority, cooldown, threshold, press_delay, release_delay, enabled, group_id = skill_info
                    
                    # 更新技能属性
                    old_name = skill.name
                    new_name = name
                    
                    # 修改对象属性
                    skill.name = new_name
                    skill.key = key
                    skill.priority = priority
                    skill.cooldown = cooldown
                    skill.threshold = threshold
                    skill.press_delay = press_delay
                    skill.release_delay = release_delay
                    skill.enabled = enabled
                    
                    # 保存到技能管理器（新版管理器会自动处理）
                    # 如果名称变更，需要特殊处理
                    if old_name != new_name:
                        print(f"技能名称已变更: {old_name} -> {new_name}，需要特殊处理")
                        # 删除旧名称的技能
                        self.skill_manager.remove_skill(old_name)
                        # 添加新名称的技能
                        self.skill_manager.add_skill(skill)
                    
                    # 确保技能管理器重新加载配置
                    print("重新加载技能管理器配置...")
                    self.skill_manager.load_config()
                    
                    # 强制刷新技能组（可能有变更）
                    print("刷新技能组...")
                    self.refresh_skill_groups()
                    
                    # 刷新技能列表
                    print("刷新技能列表...")
                    self.refresh_skill_list()
                    
                    # 显示通知
                    self.show_message("success", "成功", f"技能 {new_name} 已更新")
        except Exception as e:
            print(f"编辑技能时出错: {str(e)}")
            traceback.print_exc()
    
    def remove_selected_skill(self):
        """删除选中的技能"""
        # 获取当前选中项
        current_item = self.skillListWidget.currentItem()
        if not current_item:
            self.show_message('warning', '未选择技能', '请先选择要删除的技能')
            return
            
        # 解析技能名称
        skill_text = current_item.text()
        skill_name = skill_text.split(' - ')[0]
        
        # 确认删除对话框
        confirm_dialog = ConfirmMessageBox(
            "确认删除",
            f"确定要删除技能 {skill_name} 吗？",
            self.parent if self.parent else self
        )
        
        if confirm_dialog.exec():
            # 删除技能
            if self.skill_manager.remove_skill(skill_name):
                # 刷新列表
                self.refresh_skill_list()
                
                # 成功提示
                self.show_message('success', '删除成功', f'技能 {skill_name} 已删除')
            else:
                self.show_message('error', '删除失败', f'未找到技能 {skill_name}')
    
    def set_selected_skill_icon(self):
        """设置选中技能的图标位置"""
        # 获取当前选中项
        current_item = self.skillListWidget.currentItem()
        if not current_item:
            self.show_message('warning', '未选择技能', '请先选择要设置图标的技能')
            return
            
        # 解析技能名称
        skill_text = current_item.text()
        skill_name = skill_text.split(' - ')[0]
        
        # 设置图标位置
        result = self.skill_manager.set_skill_icon_position(skill_name)
        
        if result:
            self.show_message('success', '设置成功', f'已设置 {skill_name} 的图标位置')
        else:
            self.show_message('error', '设置失败', f'设置 {skill_name} 的图标位置失败')
    
    def update_cycle_interval(self, value):
        """更新技能循环更新间隔"""
        self.skill_manager.update_interval = value
        self.skill_manager.save_config()
        self.update_skill_status(f"已设置循环更新间隔为 {value} 秒")
    
    def show_skill_hotkey_settings(self):
        """显示技能循环快捷键设置对话框"""
        dialog = SkillHotkeySettingsMessageBox(self.skill_manager, self.parent if self.parent else self)
        dialog.exec()

    def show_message(self, message_type, title, content, duration=1000):
        """统一消息提示方法，避免重复显示"""
        # 如果组件正在关闭，不再显示消息
        if hasattr(self, '_is_closing') and self._is_closing:
            return
            
        # 检查是否已有相同消息正在显示
        current_time = time.time()
        message_key = f"{message_type}:{title}:{content}"
        
        # 如果相同消息在短时间内显示过，则忽略
        if message_key in self._recent_messages:
            last_time = self._recent_messages[message_key]
            if current_time - last_time < 1.5:  # 1.5秒内不重复显示
                return
        
        # 记录此消息
        self._recent_messages[message_key] = current_time
        
        # 确保InfoBar设置正确的父对象，并使用较短的时间，主窗口可能持有引用
        parent = self
        # 根据类型显示不同消息
        try:
            if message_type == 'success':
                InfoBar.success(
                    title=title,
                    content=content,
                    orient=Qt.Horizontal,
                    isClosable=True,
                    position=InfoBarPosition.BOTTOM,  # 改为底部，避免TopInfoBarManager的问题
                    duration=duration,
                    parent=parent
                )
            elif message_type == 'warning':
                InfoBar.warning(
                    title=title,
                    content=content,
                    orient=Qt.Horizontal,
                    isClosable=True,
                    position=InfoBarPosition.BOTTOM,  # 改为底部，避免TopInfoBarManager的问题
                    duration=duration,
                    parent=parent
                )
            elif message_type == 'error':
                InfoBar.error(
                    title=title,
                    content=content,
                    orient=Qt.Horizontal,
                    isClosable=True,
                    position=InfoBarPosition.BOTTOM,  # 改为底部，避免TopInfoBarManager的问题
                    duration=duration,
                    parent=parent
                )
        except RuntimeError as e:
            # 捕获可能的运行时错误，例如对象已被删除
            print(f"InfoBar显示错误：{e}")
            pass

    def _update_skill_item(self, item, skill):
        """更新技能列表项的显示
        
        参数:
            item (QListWidgetItem): 列表项
            skill (Skill): 技能对象
        """
        try:
            # 安全地获取技能属性
            skill_name = getattr(skill, 'name', '未知技能')
            skill_key = getattr(skill, 'key', '')
            skill_priority = getattr(skill, 'priority', 0)
            skill_enabled = getattr(skill, 'enabled', False)
            
            # 检查技能冷却状态
            cd_status = ""
            if hasattr(skill, 'cooldown') and hasattr(skill, 'last_used_time'):
                cooldown = getattr(skill, 'cooldown', 0)
                last_used_time = getattr(skill, 'last_used_time', 0)
                
                if cooldown > 0:
                    remaining = max(0, cooldown - (time.time() - last_used_time))
                    if remaining > 0:
                        cd_status = f"(冷却中: {remaining:.1f}s)"
            
            # 设置文本与图标
            status_text = "启用" if skill_enabled else "禁用"
            item.setText(f"{skill_name} - 按键:{skill_key} 优先级:{skill_priority} {cd_status} [{status_text}]")
            
            # 设置颜色
            if not skill_enabled:
                item.setForeground(QColor("#999999"))  # 禁用状态显示灰色
            elif cd_status:
                item.setForeground(QColor("#e74c3c"))  # 冷却中显示红色
            else:
                item.setForeground(QColor("#2ecc71"))  # 可用状态显示绿色
                
        except Exception as e:
            # 如果更新失败，至少确保项目有基本文本
            print(f"更新技能项时出错: {str(e)}")
            try:
                item.setText(getattr(skill, 'name', '未知技能') + " [错误]")
                item.setForeground(QColor("#e74c3c"))  # 错误状态显示红色
            except:
                item.setText("技能数据错误")
                item.setForeground(QColor("#e74c3c"))

    def manage_conditions(self):
        """打开条件管理对话框"""
        try:
            # 导入条件UI模块
            from condition_ui import ConditionManagementDialog
            
            dialog = ConditionManagementDialog(parent=self)
            
            # 显示对话框
            if dialog.exec_():
                # 刷新条件列表
                self.refresh_skill_list()
                
        except Exception as e:
            print(f"打开条件管理对话框时出错: {str(e)}")
            traceback.print_exc()
            
            # 显示错误信息
            self.show_message("error", "错误", f"打开条件管理对话框失败: {str(e)}", 2000)


class SkillEditDialog(MessageBoxBase):
    """技能编辑对话框"""
    
    def __init__(self, parent=None, skill=None, skill_manager=None):
        super().__init__(parent)
        self.skill = skill
        self.skill_manager = skill_manager
        
        # 设置对话框不可拖动
        self.setDraggable(False)
        
        # 设置遮罩颜色为完全透明
        self.setMaskColor(QColor(0, 0, 0, 0))
        
        # 设置更合适的阴影效果，减少灰色边框问题
        self.setShadowEffect(60, (0, 6), QColor(0, 0, 0, 80))
        
        # 是否为编辑模式
        self.edit_mode = skill is not None
        
        # 当前选择的条件列表
        self.selected_conditions = []
        
        # 保存原始技能ID和组ID，用于跟踪技能组变化
        self.original_skill_id = None
        self.original_group_id = None
        if self.edit_mode and self.skill:
            # 构建当前技能ID
            current_skill_id = self.skill.name.lower().replace(" ", "_")
            
            # 获取原始的数据库技能对象
            original_data_skill = config_manager.skills_db.get_skill(current_skill_id)
            if original_data_skill:
                self.original_skill_id = original_data_skill.id
                self.original_group_id = original_data_skill.group_id
                print(f"编辑技能: {self.skill.name} (ID: {self.original_skill_id}, 组ID: {self.original_group_id})")
                
                # 加载技能的条件
                if hasattr(original_data_skill, "conditions"):
                    self.selected_conditions = original_data_skill.conditions.copy()
            else:
                print(f"警告: 未找到技能 {self.skill.name} 对应的数据模型")
        
        # 设置标题和大小 (替换 setTitle 方法)
        self._window_title = "编辑技能" if self.edit_mode else "添加技能"
        
        # 设置对话框样式
        self.widget.setObjectName("skillEditDialogWidget")
        self.widget.setStyleSheet("""
            #skillEditDialogWidget {
                background-color: #ffffff;
                border-radius: 8px;
            }
        """)
        
        # 设置对话框的初始大小
        self.widget.setMinimumWidth(480)
        self.widget.setMinimumHeight(580)
        
        self.initUI()
        
        # 如果是编辑模式，填充当前技能数据
        if self.edit_mode:
            self.nameLineEdit.setText(skill.name)
            self.keyLineEdit.setText(skill.key)
            self.prioritySpinBox.setValue(skill.priority)
            self.cooldownSpinBox.setValue(skill.cooldown)
            self.thresholdSpinBox.setValue(skill.threshold)
            self.pressDelaySpinBox.setValue(skill.press_delay)
            self.releaseDelaySpinBox.setValue(skill.release_delay)
            self.enabledCheck.setChecked(skill.enabled)
            
            # 选中技能所属的组
            self._select_skill_group(skill.name)
            
            # 刷新条件列表
            self.refresh_conditions_list()
    
    def initUI(self):
        """初始化对话框UI"""
        # 设置整体布局结构
        self.viewLayout.setSpacing(16)  # 增加元素间距
        self.viewLayout.setContentsMargins(24, 24, 24, 24)  # 设置统一的边距
        
        # 添加标题标签 - 确保标题最先被添加到布局中
        self.titleLabel = TitleLabel(self._window_title)
        self.viewLayout.addWidget(self.titleLabel)
        
        # 添加间隔
        spacer = QSpacerItem(20, 10, QSizePolicy.Minimum, QSizePolicy.Fixed)
        self.viewLayout.addSpacerItem(spacer)
        
        # 错误信息标签
        self.error_label = BodyLabel("")
        self.error_label.setStyleSheet("color: #e74c3c;")
        self.error_label.setVisible(False)
        self.viewLayout.addWidget(self.error_label)
        
        # 使用网格布局排列表单
        self.formWidget = QWidget()
        self.formLayout = QGridLayout(self.formWidget)
        self.formLayout.setContentsMargins(0, 0, 0, 0)
        self.formLayout.setVerticalSpacing(16)  # 增加垂直间距
        self.formLayout.setHorizontalSpacing(16)  # 增加水平间距
        
        # 字段标签样式
        label_style = "font-weight: bold;"
        
        # 技能名称
        nameLabel = BodyLabel("技能名称:")
        nameLabel.setStyleSheet(label_style)
        self.nameLineEdit = LineEdit()
        self.nameLineEdit.setPlaceholderText("输入技能名称")
        self.nameLineEdit.setClearButtonEnabled(True)
        self.nameLineEdit.setMinimumWidth(250)
        
        # 触发按键
        keyLabel = BodyLabel("触发按键:")
        keyLabel.setStyleSheet(label_style)
        self.keyLineEdit = LineEdit()
        self.keyLineEdit.setPlaceholderText("单个键位，如 1, 2, a, b 等")
        self.keyLineEdit.setClearButtonEnabled(True)
        
        # 优先级
        priorityLabel = BodyLabel("优先级:")
        priorityLabel.setStyleSheet(label_style)
        self.prioritySpinBox = SpinBox()
        self.prioritySpinBox.setRange(0, 100)
        self.prioritySpinBox.setValue(0)
        self.prioritySpinBox.setToolTip("数值越小优先级越高")
        
        # 冷却时间
        cooldownLabel = BodyLabel("冷却时间(秒):")
        cooldownLabel.setStyleSheet(label_style)
        self.cooldownSpinBox = DoubleSpinBox()
        self.cooldownSpinBox.setRange(0.0, 3600.0)
        self.cooldownSpinBox.setSingleStep(0.5)
        self.cooldownSpinBox.setValue(0.0)
        
        # 匹配阈值
        thresholdLabel = BodyLabel("匹配阈值:")
        thresholdLabel.setStyleSheet(label_style)
        self.thresholdSpinBox = DoubleSpinBox()
        self.thresholdSpinBox.setRange(0.1, 1.0)
        self.thresholdSpinBox.setSingleStep(0.05)
        self.thresholdSpinBox.setValue(0.7)
        self.thresholdSpinBox.setToolTip("图像匹配的相似度阈值，越大越精确")
        
        # 延迟时间
        pressDelayLabel = BodyLabel("按下延迟(秒):")
        pressDelayLabel.setStyleSheet(label_style)
        self.pressDelaySpinBox = DoubleSpinBox()
        self.pressDelaySpinBox.setRange(0.0, 10.0)
        self.pressDelaySpinBox.setSingleStep(0.01)
        self.pressDelaySpinBox.setValue(0.0)
        
        releaseDelayLabel = BodyLabel("释放延迟(秒):")
        releaseDelayLabel.setStyleSheet(label_style)
        self.releaseDelaySpinBox = DoubleSpinBox()
        self.releaseDelaySpinBox.setRange(0.0, 10.0)
        self.releaseDelaySpinBox.setSingleStep(0.01)
        self.releaseDelaySpinBox.setValue(0.05)
        
        # 技能状态
        enabledLabel = BodyLabel("启用状态:")
        enabledLabel.setStyleSheet(label_style)
        self.enabledCheck = CheckBox("启用")
        self.enabledCheck.setChecked(True)
        
        # 技能组选择
        groupLabel = BodyLabel("所属技能组:")
        groupLabel.setStyleSheet(label_style)
        self.groupComboBox = ComboBox()
        self._refresh_skill_groups()
        
        # 设置表单布局的列宽比例，使标签列和控件列保持固定比例
        self.formLayout.setColumnStretch(0, 1)   # 标签列
        self.formLayout.setColumnStretch(1, 3)   # 控件列
        
        # 添加表单字段到布局，并确保标签右对齐
        row = 0
        self.formLayout.addWidget(nameLabel, row, 0, Qt.AlignRight | Qt.AlignVCenter)
        self.formLayout.addWidget(self.nameLineEdit, row, 1)
        
        row += 1
        self.formLayout.addWidget(keyLabel, row, 0, Qt.AlignRight | Qt.AlignVCenter)
        self.formLayout.addWidget(self.keyLineEdit, row, 1)
        
        row += 1
        self.formLayout.addWidget(priorityLabel, row, 0, Qt.AlignRight | Qt.AlignVCenter)
        self.formLayout.addWidget(self.prioritySpinBox, row, 1)
        
        row += 1
        self.formLayout.addWidget(cooldownLabel, row, 0, Qt.AlignRight | Qt.AlignVCenter)
        self.formLayout.addWidget(self.cooldownSpinBox, row, 1)
        
        row += 1
        self.formLayout.addWidget(thresholdLabel, row, 0, Qt.AlignRight | Qt.AlignVCenter)
        self.formLayout.addWidget(self.thresholdSpinBox, row, 1)
        
        row += 1
        self.formLayout.addWidget(pressDelayLabel, row, 0, Qt.AlignRight | Qt.AlignVCenter)
        self.formLayout.addWidget(self.pressDelaySpinBox, row, 1)
        
        row += 1
        self.formLayout.addWidget(releaseDelayLabel, row, 0, Qt.AlignRight | Qt.AlignVCenter)
        self.formLayout.addWidget(self.releaseDelaySpinBox, row, 1)
        
        row += 1
        self.formLayout.addWidget(enabledLabel, row, 0, Qt.AlignRight | Qt.AlignVCenter)
        self.formLayout.addWidget(self.enabledCheck, row, 1)
        
        row += 1
        self.formLayout.addWidget(groupLabel, row, 0, Qt.AlignRight | Qt.AlignVCenter)
        self.formLayout.addWidget(self.groupComboBox, row, 1)
        
        # 添加条件选择区域
        row += 1
        conditionsLabel = SubtitleLabel("触发条件")
        self.formLayout.addWidget(conditionsLabel, row, 0, 1, 2, Qt.AlignLeft)
        
        row += 1
        conditionsWidget = QWidget()
        conditionsLayout = QVBoxLayout(conditionsWidget)
        conditionsLayout.setContentsMargins(0, 0, 0, 0)
        
        # 条件列表
        self.conditionsListWidget = QListWidget()
        self.conditionsListWidget.setMaximumHeight(120)
        self.conditionsListWidget.setStyleSheet("""
            QListWidget {
                border: 1px solid #e0e0e0;
                border-radius: 5px;
                background-color: white;
                outline: none;
                padding: 2px;
            }
            QListWidget::item {
                padding: 6px;
                border-bottom: 1px solid #f0f0f0;
                margin: 2px 0;
                border-radius: 4px;
            }
        """)
        conditionsLayout.addWidget(self.conditionsListWidget)
        
        # 条件管理按钮
        conditionButtonLayout = QHBoxLayout()
        
        self.addConditionBtn = PushButton("添加条件")
        self.addConditionBtn.setIcon(FIF.ADD)
        self.addConditionBtn.clicked.connect(self.add_condition)
        
        self.removeConditionBtn = PushButton("移除条件")
        self.removeConditionBtn.setIcon(FIF.REMOVE)
        self.removeConditionBtn.clicked.connect(self.remove_condition)
        
        self.manageConditionsBtn = PushButton("管理所有条件")
        self.manageConditionsBtn.setIcon(FIF.CHECKBOX)
        self.manageConditionsBtn.clicked.connect(self.manage_conditions)
        
        conditionButtonLayout.addWidget(self.addConditionBtn)
        conditionButtonLayout.addWidget(self.removeConditionBtn)
        conditionButtonLayout.addStretch(1)
        conditionButtonLayout.addWidget(self.manageConditionsBtn)
        
        conditionsLayout.addLayout(conditionButtonLayout)
        
        # 条件描述信息
        self.conditionInfoLabel = CaptionLabel("提示: 添加条件可以使技能在特定情况下才会触发")
        self.conditionInfoLabel.setStyleSheet("color: #3498db;")
        conditionsLayout.addWidget(self.conditionInfoLabel)
        
        self.formLayout.addWidget(conditionsWidget, row, 0, 1, 2)
        
        # 添加提示信息
        tipLabel = CaptionLabel("提示: 请设置恰当的冷却时间和优先级，以确保技能循环正常工作")
        tipLabel.setStyleSheet("color: #3498db;")
        row += 1
        self.formLayout.addWidget(tipLabel, row, 0, 1, 2, Qt.AlignLeft)
        
        # 添加表单到视图
        self.viewLayout.addWidget(self.formWidget)
        
        # 添加弹性空间，确保底部按钮位置正确
        self.viewLayout.addStretch(1)
        
        # 创建按钮
        self.yesButton.setText("保存")
        self.cancelButton.setText("取消")
        
        # 连接信号
        self.yesButton.clicked.connect(self.validate)
    
    def _refresh_skill_groups(self):
        """刷新技能组下拉列表"""
        self.groupComboBox.clear()
        self.groupComboBox.addItem("默认技能组", "default")
        
        # 添加系统中的所有技能组
        for group_info in config_manager.system_config.skill_groups:
            group_id = group_info.get("id", "")
            group_name = group_info.get("name", group_id)
            if group_id and group_id != "default":
                self.groupComboBox.addItem(group_name, group_id)
    
    def _select_skill_group(self, skill_name):
        """选中技能所属的组
        
        参数:
            skill_name (str): 技能名称
        """
        try:
            # 获取数据库中的技能
            skill_id = skill_name.lower().replace(" ", "_")
            data_skill = config_manager.skills_db.get_skill(skill_id)
            
            if data_skill:
                # 在下拉框中查找和选中组
                for i in range(self.groupComboBox.count()):
                    if self.groupComboBox.itemData(i) == data_skill.group_id:
                        self.groupComboBox.setCurrentIndex(i)
                        break
        except Exception as e:
            print(f"选择技能组出错: {str(e)}")
    
    def get_skill_info(self):
        """获取界面中的技能信息
        
        返回:
            tuple: (name, key, priority, cooldown, threshold, press_delay, release_delay, enabled, group_id)
        """
        name = self.nameLineEdit.text().strip()
        key = self.keyLineEdit.text().strip()
        priority = self.prioritySpinBox.value()
        cooldown = self.cooldownSpinBox.value()
        threshold = self.thresholdSpinBox.value()
        press_delay = self.pressDelaySpinBox.value()
        release_delay = self.releaseDelaySpinBox.value()
        enabled = self.enabledCheck.isChecked()
        group_id = self.groupComboBox.currentData()
        
        return (name, key, priority, cooldown, threshold, press_delay, release_delay, enabled, group_id)

    def validate(self):
        """验证表单数据并保存"""
        try:
            # 获取表单数据
            name, key, priority, cooldown, threshold, press_delay, release_delay, enabled, group_id = self.get_skill_info()
            
            # 基本验证
            if not name:
                self.error_label.setText("技能名称不能为空")
                self.error_label.setVisible(True)
                return
                
            if not key:
                self.error_label.setText("触发按键不能为空")
                self.error_label.setVisible(True)
                return
            
            # 如果是新建技能，检查名称是否已存在
            if not self.edit_mode:
                # 检查本地列表
                skill_id = name.lower().replace(" ", "_")
                if config_manager.skills_db.get_skill(skill_id) is not None:
                    self.error_label.setText(f"技能名称 {name} 已存在")
                    self.error_label.setVisible(True)
                    return
                
            # 如果是编辑现有技能，检查名称是否与其他技能冲突
            if self.skill and name != self.skill.name:
                # 构建新的ID
                new_skill_id = name.lower().replace(" ", "_")
                
                # 检查是否存在同名技能
                existing_skill = config_manager.skills_db.get_skill(new_skill_id)
                if existing_skill is not None:
                    self.error_label.setText(f"技能名称 {name} 已存在")
                    self.error_label.setVisible(True)
                    return
            
            # 保存数据
            if self.edit_mode and self.skill:
                # 更新现有技能
                self.skill.name = name
                self.skill.key = key
                self.skill.priority = priority
                self.skill.cooldown = cooldown
                self.skill.threshold = threshold
                self.skill.press_delay = press_delay
                self.skill.release_delay = release_delay
                self.skill.enabled = enabled
                
                # 更新对应的数据模型技能
                skill_id = name.lower().replace(" ", "_")
                data_skill = config_manager.skills_db.get_skill(self.original_skill_id)
                
                # 确保data_skill存在
                if data_skill is None:
                    # 如果找不到原始ID的技能，可能是因为技能名称已改变，尝试通过新ID查找
                    data_skill = config_manager.skills_db.get_skill(skill_id)
                    
                # 如果仍然找不到，创建一个新的
                if data_skill is None:
                    data_skill = DataSkill(
                        id=skill_id,
                        name=name,
                        key=key,
                        priority=priority,
                        group_id=group_id
                    )
                
                # 更新属性
                data_skill.name = name  # 确保名称也被更新
                data_skill.id = skill_id  # 更新ID以匹配可能改变的名称
                data_skill.key = key
                data_skill.priority = priority
                data_skill.enabled = enabled
                data_skill.group_id = group_id
                
                # 更新参数
                data_skill.parameters["cooldown"] = cooldown
                data_skill.parameters["press_delay"] = press_delay
                data_skill.parameters["release_delay"] = release_delay
                
                # 更新条件列表
                data_skill.conditions = self.selected_conditions
                
                # 更新技能组信息，传入原始组ID
                self._update_skill_group_membership(data_skill, self.original_group_id)
                
                # 如果名称改变了，需要从数据库中移除旧名称的技能
                if self.original_skill_id != skill_id:
                    config_manager.skills_db.remove_skill(self.original_skill_id)
                
                # 保存到数据库
                config_manager.skills_db.add_skill(data_skill)
                config_manager.save_skills_db()
                
                # 确保系统配置被重新加载
                config_manager._load_system_config()
            else:
                # 创建新技能
                new_skill = Skill(name, key, priority)
                new_skill.cooldown = cooldown
                new_skill.threshold = threshold
                new_skill.press_delay = press_delay
                new_skill.release_delay = release_delay
                new_skill.enabled = enabled
                
                # 创建数据模型技能
                skill_id = name.lower().replace(" ", "_")
                data_skill = DataSkill(
                    id=skill_id,
                    name=name,
                    key=key,
                    priority=priority,
                    group_id=group_id,
                    enabled=enabled
                )
                
                # 设置参数
                data_skill.parameters["cooldown"] = cooldown
                data_skill.parameters["press_delay"] = press_delay
                data_skill.parameters["release_delay"] = release_delay
                
                # 添加默认动作
                data_skill.actions.append(Action(type="keypress", key=key))
                
                # 更新技能组信息
                self._update_skill_group_membership(data_skill)
                
                # 保存到数据库
                config_manager.skills_db.add_skill(data_skill)
                config_manager.save_skills_db()
                
                # 添加到管理器（运行时）
                self.skill_manager.add_skill(new_skill)
                
                # 确保系统配置被重新加载
                config_manager._load_system_config()
            
            # 强制刷新父窗口中的技能组和列表
            if self.parent and isinstance(self.parent, SkillCycleInterface):
                print("强制刷新父窗口中的技能组和列表")
                # 刷新技能组和列表
                self.parent.refresh_skill_groups()
                self.parent.refresh_skill_list()
            
            # 关闭对话框
            self.accept()
            
        except Exception as e:
            self.error_label.setText(f"保存失败: {str(e)}")
            self.error_label.setVisible(True)
            print(f"保存技能信息时出错: {str(e)}")
    
    def _update_skill_group_membership(self, data_skill, previous_group_id=None):
        """更新技能组成员关系
        
        参数:
            data_skill (DataSkill): 数据模型技能
            previous_group_id (str, optional): 技能之前所属的组ID
        """
        try:
            # 验证数据技能有效性
            if not data_skill or not hasattr(data_skill, "id") or not data_skill.id:
                print("无效的数据技能对象")
                return
                
            # 获取技能当前的组ID
            current_group_id = getattr(data_skill, "group_id", None)
            skill_id = data_skill.id
            print(f"技能组变更 - 技能: {data_skill.name} 从 {previous_group_id} 到 {current_group_id}")
            
            # 防止空或None的组ID，确保默认值
            if not current_group_id:
                current_group_id = "default"
                data_skill.group_id = "default"
            
            # 确保默认组存在
            default_group = config_manager.get_skill_group("default")
            if not default_group:
                # 创建默认组
                default_group = SkillGroup(id="default", name="默认组")
                config_manager.add_skill_group(default_group)
                    
            # 如果前一个组与当前组一样，不需要更新
            if previous_group_id == current_group_id:
                print(f"技能 {data_skill.name} 组未变更，保持在 {current_group_id}")
                return
            
            # 处理从前一个组移出
            if previous_group_id:
                previous_group = config_manager.get_skill_group(previous_group_id)
                if previous_group and skill_id in previous_group.skill_ids:
                    # 从前一个组中移除技能ID
                    previous_group.skill_ids.remove(skill_id)
                    config_manager.update_skill_group(previous_group)
                    print(f"已从组 {previous_group_id} 中移除技能 {data_skill.name}")
            
            # 获取当前组
            current_group = config_manager.get_skill_group(current_group_id)
            if not current_group:
                # 如果组不存在，创建新组
                current_group = SkillGroup(id=current_group_id, name=current_group_id)
                config_manager.add_skill_group(current_group)
                print(f"已创建新组 {current_group_id}")
            
            # 将技能添加到新组（避免重复）
            if skill_id not in current_group.skill_ids:
                current_group.skill_ids.append(skill_id)
                config_manager.update_skill_group(current_group)
                print(f"已将技能 {data_skill.name} 添加到组 {current_group_id}")
                
                # 保存并重新加载配置，确保运行时系统反映这些变化
                config_manager.save_system_config()
            
            # 如果有技能管理器，重新加载配置
            if self.skill_manager:
                self.skill_manager.load_config()
            
            # 重新加载系统配置，确保所有变更都被应用
            config_manager._load_system_config()
            
            print(f"技能组成员关系更新完成 - 技能: {data_skill.name} 现在属于组: {current_group_id}")
                
        except Exception as e:
            print(f"更新技能组成员关系时出错: {str(e)}")
            import traceback
            traceback.print_exc()

    def refresh_conditions_list(self):
        """刷新条件列表"""
        try:
            # 清空列表
            self.conditionsListWidget.clear()
            
            # 添加已选择的条件
            for condition_ref in self.selected_conditions:
                # 获取条件ID
                condition_id = condition_ref.id
                
                # 尝试获取条件名称
                condition = config_manager.get_condition(condition_id)
                if condition:
                    item = QListWidgetItem()
                    item.setText(condition.name)
                    item.setData(Qt.UserRole, condition_id)
                    self.conditionsListWidget.addItem(item)
                else:
                    # 如果条件不存在，仍然显示ID
                    item = QListWidgetItem()
                    item.setText(f"{condition_id} (未找到)")
                    item.setData(Qt.UserRole, condition_id)
                    item.setForeground(QColor("#999999"))
                    self.conditionsListWidget.addItem(item)
                    
        except Exception as e:
            print(f"刷新条件列表时出错: {str(e)}")
            traceback.print_exc()
    
    def add_condition(self):
        """添加条件到技能"""
        try:
            # 获取已选择的条件ID列表
            selected_condition_ids = [cr.id for cr in self.selected_conditions]
            
            # 导入条件选择对话框
            from condition_ui import ConditionSelectionDialog
            
            # 创建条件选择对话框，传入已选择的条件ID作为排除列表
            dialog = ConditionSelectionDialog(
                parent=self,
                multi_select=True,  # 允许多选
                exclude_ids=selected_condition_ids
            )
            
            # 显示对话框
            if dialog.exec_() == QDialog.Accepted:
                # 获取选中的条件ID列表
                selected_ids = dialog.get_selected_conditions()
                
                if selected_ids:
                    # 添加所有选中的条件
                    for condition_id in selected_ids:
                        # 添加条件引用
                        condition_ref = ConditionReference(id=condition_id)
                        self.selected_conditions.append(condition_ref)
                    
                    # 刷新条件列表
                    self.refresh_conditions_list()
                    
                    # 显示成功消息
                    if len(selected_ids) == 1:
                        InfoBar.success(
                            title="添加成功",
                            content="已添加1个条件",
                            orient=Qt.Horizontal,
                            isClosable=True,
                            position=InfoBarPosition.TOP,
                            duration=2000,
                            parent=self
                        )
                    else:
                        InfoBar.success(
                            title="添加成功",
                            content=f"已添加{len(selected_ids)}个条件",
                            orient=Qt.Horizontal,
                            isClosable=True,
                            position=InfoBarPosition.TOP,
                            duration=2000,
                            parent=self
                        )
                
        except Exception as e:
            print(f"添加条件时出错: {str(e)}")
            traceback.print_exc()
    
    def remove_condition(self):
        """从技能中移除条件"""
        try:
            # 获取选中的条件项
            selected_items = self.conditionsListWidget.selectedItems()
            if not selected_items:
                return
                
            # 遍历选中的项并移除对应的条件
            for item in selected_items:
                condition_id = item.data(Qt.UserRole)
                
                # 从列表中移除对应的条件引用
                self.selected_conditions = [cr for cr in self.selected_conditions if cr.id != condition_id]
            
            # 刷新列表
            self.refresh_conditions_list()
            
        except Exception as e:
            print(f"移除条件时出错: {str(e)}")
            traceback.print_exc()
    
    def manage_conditions(self):
        """打开条件管理对话框"""
        try:
            # 导入条件UI模块
            from condition_ui import ConditionManagementDialog
            
            dialog = ConditionManagementDialog(parent=self)
            
            # 显示对话框
            if dialog.exec_():
                # 刷新条件列表
                self.refresh_skill_list()
                
        except Exception as e:
            print(f"打开条件管理对话框时出错: {str(e)}")
            traceback.print_exc()
            
            # 显示错误信息
            self.show_message("error", "错误", f"打开条件管理对话框失败: {str(e)}", 2000)


class SkillHotkeySettingsMessageBox(MessageBoxBase):
    """技能循环快捷键设置对话框"""
    
    def __init__(self, skill_manager, parent=None):
        super().__init__(parent)
        self.skill_manager = skill_manager
        
        # 设置对话框不可拖动
        self.setDraggable(False)
        
        # 设置遮罩颜色为完全透明
        self.setMaskColor(QColor(0, 0, 0, 0))
        
        # 设置更合适的阴影效果，减少灰色边框问题
        self.setShadowEffect(60, (0, 6), QColor(0, 0, 0, 80))
        
        # 设置标题和大小 (替换 setTitle 方法)
        self._window_title = "技能循环快捷键设置"
        
        # 初始化记录的快捷键
        self.recorded_hotkeys = {}
        
        # 获取当前快捷键设置
        from skill_cycle import NewSkillCycleManager
        if isinstance(self.skill_manager, NewSkillCycleManager):
            # 新版技能管理器
            self.recorded_hotkeys["start_cycle"] = self.skill_manager.hotkeys.get("start_cycle", "")
            self.recorded_hotkeys["stop_cycle"] = self.skill_manager.hotkeys.get("stop_cycle", "")
        else:
            # 旧版技能管理器
            self.recorded_hotkeys["start_cycle"] = getattr(self.skill_manager, "start_hotkey", "")
            self.recorded_hotkeys["stop_cycle"] = getattr(self.skill_manager, "stop_hotkey", "")
        
        # 设置对话框样式
        self.widget.setObjectName("hotkeySettingsDialogWidget")
        self.widget.setStyleSheet("""
            #hotkeySettingsDialogWidget {
                background-color: #ffffff;
                border-radius: 8px;
            }
        """)
        
        # 设置对话框的初始大小
        self.widget.setMinimumWidth(480)
        self.widget.setMinimumHeight(300)
        
        self.initUI()
    
    def initUI(self):
        """初始化UI"""
        # 设置整体布局结构
        self.viewLayout.setSpacing(20)  # 增加元素间距
        self.viewLayout.setContentsMargins(30, 30, 30, 30)  # 增加边距，减少拥挤感
        
        # 添加标题标签 - 确保在最上方
        self.titleLabel = TitleLabel(self._window_title)
        self.titleLabel.setStyleSheet("font-size: 18px;")
        self.viewLayout.addWidget(self.titleLabel)
        
        # 添加间隔
        spacer = QSpacerItem(20, 15, QSizePolicy.Minimum, QSizePolicy.Fixed)
        self.viewLayout.addSpacerItem(spacer)
        
        # 错误信息标签
        self.error_label = BodyLabel("")
        self.error_label.setStyleSheet("color: #e74c3c;")
        self.error_label.setVisible(False)
        self.viewLayout.addWidget(self.error_label)
        
        # 创建表单布局
        self.formWidget = QWidget()
        self.formLayout = QGridLayout(self.formWidget)
        self.formLayout.setContentsMargins(0, 0, 0, 0)
        self.formLayout.setVerticalSpacing(20)  # 增加垂直间距
        self.formLayout.setHorizontalSpacing(15)
        
        # 设置表单布局的列宽比例
        self.formLayout.setColumnStretch(0, 1)   # 标签列
        self.formLayout.setColumnStretch(1, 2)   # 控件列
        
        # 字段标签样式
        label_style = "font-weight: bold; font-size: 14px;"
        
        # 开始循环快捷键
        startHotkeyLabel = BodyLabel("开始技能循环:")
        startHotkeyLabel.setStyleSheet(label_style)
        self.startHotkeyButton = PushButton()
        
        # 获取和显示当前的开始循环快捷键
        start_hotkey = self.recorded_hotkeys.get("start_cycle", "未设置")
        self.startHotkeyButton.setText(start_hotkey)
        
        self.startHotkeyButton.setMinimumWidth(220)  # 增加按钮宽度
        self.startHotkeyButton.setMinimumHeight(36)  # 增加按钮高度
        self.startHotkeyButton.clicked.connect(lambda: self.record_hotkey("start_cycle"))
        
        # 停止循环快捷键
        stopHotkeyLabel = BodyLabel("停止技能循环:")
        stopHotkeyLabel.setStyleSheet(label_style)
        self.stopHotkeyButton = PushButton()
        
        # 获取和显示当前的停止循环快捷键
        stop_hotkey = self.recorded_hotkeys.get("stop_cycle", "未设置")
        self.stopHotkeyButton.setText(stop_hotkey)
        
        self.stopHotkeyButton.setMinimumWidth(220)  # 增加按钮宽度
        self.stopHotkeyButton.setMinimumHeight(36)  # 增加按钮高度
        self.stopHotkeyButton.clicked.connect(lambda: self.record_hotkey("stop_cycle"))
        
        # 添加提示信息
        tipLabel = CaptionLabel("提示: 点击按钮后按下快捷键即可记录，建议避免使用游戏内已用的按键")
        tipLabel.setStyleSheet("color: #3498db; font-size: 12px;")
        
        # 添加到表单布局
        row = 0
        self.formLayout.addWidget(startHotkeyLabel, row, 0, Qt.AlignRight)
        self.formLayout.addWidget(self.startHotkeyButton, row, 1)
        
        row += 1
        self.formLayout.addWidget(stopHotkeyLabel, row, 0, Qt.AlignRight)
        self.formLayout.addWidget(self.stopHotkeyButton, row, 1)
        
        row += 1
        self.formLayout.addWidget(tipLabel, row, 0, 1, 2)  # 提示信息占据两列
        
        # 添加到视图布局
        self.viewLayout.addWidget(self.formWidget)
        
        # 添加伸缩空间，使按钮始终在底部
        self.viewLayout.addStretch(1)
        
        # 设置按钮
        self.yesButton.setText("确定")
        self.yesButton.setMinimumWidth(100)
        self.yesButton.setMinimumHeight(36)
        
        self.cancelButton.setText("取消")
        self.cancelButton.setMinimumWidth(100)
        self.cancelButton.setMinimumHeight(36)
        
        # 连接信号
        self.yesButton.clicked.connect(self.validate)
        
        # 设置窗口标志
        self.setAttribute(Qt.WA_DeleteOnClose, True)
    
    def validate(self):
        """验证表单数据并保存"""
        try:
            # 获取表单数据
            start_cycle_hotkey = self.startHotkeyButton.text()
            stop_cycle_hotkey = self.stopHotkeyButton.text()
            
            # 基本验证
            if not start_cycle_hotkey:
                self.error_label.setText("开始循环快捷键不能为空")
                self.error_label.setVisible(True)
                return
                
            if not stop_cycle_hotkey:
                self.error_label.setText("停止循环快捷键不能为空")
                self.error_label.setVisible(True)
                return
            
            # 根据技能管理器类型选择正确的设置方式
            from skill_cycle import NewSkillCycleManager
            
            # 保存数据
            if isinstance(self.skill_manager, NewSkillCycleManager):
                # 新版技能管理器使用字典格式
                print(f"使用新版格式保存快捷键: {start_cycle_hotkey}, {stop_cycle_hotkey}")
                self.skill_manager.hotkeys["start_cycle"] = start_cycle_hotkey
                self.skill_manager.hotkeys["stop_cycle"] = stop_cycle_hotkey
            else:
                # 旧版技能管理器使用属性格式
                print(f"使用旧版格式保存快捷键: {start_cycle_hotkey}, {stop_cycle_hotkey}")
                self.skill_manager.start_hotkey = start_cycle_hotkey
                self.skill_manager.stop_hotkey = stop_cycle_hotkey
            
            # 保存配置
            success = self.skill_manager.set_hotkeys(start_cycle_hotkey, stop_cycle_hotkey)
            if not success:
                self.error_label.setText("保存快捷键配置失败，请检查快捷键格式是否正确")
                self.error_label.setVisible(True)
                return
            
            # 强制刷新父窗口中的技能组和列表
            if self.parent and isinstance(self.parent, SkillCycleInterface):
                # 刷新技能组和列表
                self.parent.refresh_skill_groups()
                self.parent.refresh_skill_list()
            
            # 关闭对话框
            self.accept()
            
        except Exception as e:
            self.error_label.setText(f"保存失败: {str(e)}")
            self.error_label.setVisible(True)
            print(f"保存快捷键设置时出错: {str(e)}")

    def record_hotkey(self, hotkey_type):
        """记录用户按下的快捷键
        
        参数:
            hotkey_type (str): 快捷键类型，"start_cycle"或"stop_cycle"
        """
        try:
            # 确定要更新的按钮
            button = self.startHotkeyButton if hotkey_type == "start_cycle" else self.stopHotkeyButton
            
            # 更改按钮文本提示用户按下快捷键
            original_text = button.text()
            button.setText("请按下快捷键...")
            
            # 禁用其他按钮，防止干扰
            self.yesButton.setEnabled(False)
            self.cancelButton.setEnabled(False)
            other_button = self.stopHotkeyButton if hotkey_type == "start_cycle" else self.startHotkeyButton
            other_button.setEnabled(False)
            
            # 创建一个事件过滤器对象来捕获键盘事件
            class KeyPressFilter(QObject):
                def __init__(self, parent, hotkey_type, button, original_text, callback):
                    super().__init__(parent)
                    self.parent = parent
                    self.hotkey_type = hotkey_type
                    self.button = button
                    self.original_text = original_text
                    self.callback = callback
                
                def eventFilter(self, obj, event):
                    if event.type() == QEvent.KeyPress:
                        # 获取按键序列
                        modifiers = event.modifiers()
                        key = event.key()
                        
                        # 忽略单独的修饰键
                        if key in (Qt.Key_Control, Qt.Key_Alt, Qt.Key_Shift, Qt.Key_Meta):
                            return True
                        
                        # 创建快捷键文本
                        hotkey_text = ""
                        if modifiers & Qt.ControlModifier:
                            hotkey_text += "ctrl+"
                        if modifiers & Qt.AltModifier:
                            hotkey_text += "alt+"
                        if modifiers & Qt.ShiftModifier:
                            hotkey_text += "shift+"
                        if modifiers & Qt.MetaModifier:
                            hotkey_text += "meta+"
                        
                        # 添加主键
                        key_text = QKeySequence(key).toString().lower()
                        if key_text:
                            hotkey_text += key_text
                        
                        # 更新按钮文本和记录
                        if hotkey_text:
                            self.button.setText(hotkey_text)
                            self.callback(self.hotkey_type, hotkey_text)
                        else:
                            self.button.setText(self.original_text)
                        
                        # 完成后回调
                        self.finalize()
                        return True
                    return False
                
                def finalize(self):
                    print("移除事件过滤器并恢复按钮状态")
                    # 从父对象移除此事件过滤器
                    if self.parent is not None:
                        self.parent.removeEventFilter(self)
                        
                        # 恢复所有按钮状态
                        self.parent.yesButton.setEnabled(True)
                        self.parent.cancelButton.setEnabled(True)
                        if self.hotkey_type == "start_cycle":
                            self.parent.stopHotkeyButton.setEnabled(True)
                        else:
                            self.parent.startHotkeyButton.setEnabled(True)
            
            # 回调函数，用于记录快捷键
            def on_hotkey_recorded(hotkey_type, hotkey_text):
                self.recorded_hotkeys[hotkey_type] = hotkey_text
                print(f"已记录快捷键: {hotkey_type} = {hotkey_text}")
            
            # 创建并安装事件过滤器
            self.key_filter = KeyPressFilter(self, hotkey_type, button, original_text, on_hotkey_recorded)
            self.installEventFilter(self.key_filter)
            print(f"已安装事件过滤器，等待按键输入({hotkey_type})...")
            
        except Exception as e:
            print(f"记录快捷键时出错: {str(e)}")
            # 恢复按钮状态
            button.setText(original_text)
            self.yesButton.setEnabled(True)
            self.cancelButton.setEnabled(True)
            if hotkey_type == "start_cycle":
                self.stopHotkeyButton.setEnabled(True)
            else:
                self.startHotkeyButton.setEnabled(True)


class ConfirmMessageBox(MessageBoxBase):
    """确认对话框"""
    
    def __init__(self, title, content, parent=None):
        super().__init__(parent)
        self._window_title = title
        self._content = content
        
        # 设置对话框不可拖动
        self.setDraggable(False)
        
        # 设置遮罩颜色为完全透明
        self.setMaskColor(QColor(0, 0, 0, 0))
        
        # 设置更合适的阴影效果，减少灰色边框问题
        self.setShadowEffect(60, (0, 6), QColor(0, 0, 0, 80))
        
        # 设置对话框样式
        self.widget.setObjectName("confirmDialogWidget")
        self.widget.setStyleSheet("""
            #confirmDialogWidget {
                background-color: #ffffff;
                border-radius: 8px;
            }
        """)
        
        # 设置对话框的初始大小
        self.widget.setMinimumWidth(420)
        self.widget.setMinimumHeight(220)
        
        self.initUI()
    
    def initUI(self):
        """初始化UI"""
        # 设置整体布局结构
        self.viewLayout.setSpacing(20)  # 增加元素间距
        self.viewLayout.setContentsMargins(30, 30, 30, 30)  # 设置更宽松的边距
        
        # 添加标题标签
        self.titleLabel = TitleLabel(self._window_title)
        self.titleLabel.setStyleSheet("font-size: 18px;")
        self.viewLayout.addWidget(self.titleLabel)
        
        # 添加间隔
        spacer = QSpacerItem(20, 15, QSizePolicy.Minimum, QSizePolicy.Fixed)
        self.viewLayout.addSpacerItem(spacer)
        
        # 设置内容标签
        self.contentLabel = SubtitleLabel(self._content)
        self.contentLabel.setWordWrap(True)
        self.contentLabel.setAlignment(Qt.AlignLeft | Qt.AlignTop)  # 左对齐顶部对齐
        self.contentLabel.setMinimumHeight(60)  # 设置最小高度，避免文本太少时对话框太窄
        self.viewLayout.addWidget(self.contentLabel)
        
        # 设置弹性空间，使按钮始终在底部
        self.viewLayout.addStretch(1)
        
        # 设置按钮
        self.yesButton.setText("确定")
        self.yesButton.setMinimumWidth(100)
        self.yesButton.setMinimumHeight(36)
        
        self.cancelButton.setText("取消")
        self.cancelButton.setMinimumWidth(100)
        self.cancelButton.setMinimumHeight(36)
        
        # 设置对话框整体样式
        self.widget.setObjectName("confirmDialogWidget")
        self.widget.setStyleSheet("""
            #confirmDialogWidget {
                background-color: #ffffff;
                border-radius: 8px;
            }
        """)
        
        # 设置窗口标志
        self.setAttribute(Qt.WA_DeleteOnClose, True) 

class SkillGroupManagementDialog(MessageBoxBase):
    """技能组管理对话框"""
    
    def __init__(self, parent=None, skill_manager=None):
        super().__init__(parent)
        self.skill_manager = skill_manager
        
        # 设置对话框属性
        self.setDraggable(False)
        self.setMaskColor(QColor(0, 0, 0, 0))
        self.setShadowEffect(60, (0, 6), QColor(0, 0, 0, 80))
        
        # 设置标题
        self._window_title = "技能组管理"
        
        # 设置对话框样式
        self.widget.setObjectName("skillGroupManagementDialogWidget")
        self.widget.setStyleSheet("""
            #skillGroupManagementDialogWidget {
                background-color: #ffffff;
                border-radius: 8px;
            }
        """)
        
        # 设置对话框的初始大小
        self.widget.setMinimumWidth(680)
        self.widget.setMinimumHeight(520)
        
        # 初始化UI
        self.initUI()
        
        # 刷新技能组列表
        self.refresh_group_list()
        
    def initUI(self):
        """初始化对话框UI"""
        # 设置整体布局结构
        self.viewLayout.setSpacing(16)
        self.viewLayout.setContentsMargins(24, 24, 24, 24)
        
        # 添加标题标签
        self.titleLabel = TitleLabel(self._window_title)
        self.viewLayout.addWidget(self.titleLabel)
        
        # 添加间隔
        spacer = QSpacerItem(20, 10, QSizePolicy.Minimum, QSizePolicy.Fixed)
        self.viewLayout.addSpacerItem(spacer)
        
        # 创建主内容区域
        mainContent = QWidget()
        mainLayout = QHBoxLayout(mainContent)
        mainLayout.setContentsMargins(0, 0, 0, 0)
        mainLayout.setSpacing(16)
        
        # 左侧技能组列表
        leftPanel = QWidget()
        leftLayout = QVBoxLayout(leftPanel)
        leftLayout.setContentsMargins(0, 0, 0, 0)
        leftLayout.setSpacing(8)
        
        groupListLabel = SubtitleLabel("技能组列表")
        leftLayout.addWidget(groupListLabel)
        
        self.groupListWidget = QListWidget()
        self.groupListWidget.setSelectionMode(QAbstractItemView.SingleSelection)
        self.groupListWidget.setMaximumWidth(220)
        self.groupListWidget.setStyleSheet("""
            QListWidget {
                border: 1px solid #e0e0e0;
                border-radius: 5px;
                background-color: white;
                outline: none;
                padding: 2px;
            }
            QListWidget::item {
                padding: 8px;
                border-bottom: 1px solid #f0f0f0;
                margin: 2px 0;
                border-radius: 4px;
            }
            QListWidget::item:hover {
                background-color: rgba(25, 118, 210, 0.1);
            }
            QListWidget::item:selected {
                background-color: rgba(25, 118, 210, 0.2);
                color: #1976d2;
            }
            QListWidget::item:selected:active {
                background-color: rgba(25, 118, 210, 0.3);
                color: #1976d2;
            }
        """)
        leftLayout.addWidget(self.groupListWidget, 1)
        
        # 左侧按钮区域
        groupButtonLayout = QHBoxLayout()
        
        self.addGroupBtn = PrimaryPushButton("添加")
        self.addGroupBtn.setIcon(FIF.ADD)
        self.addGroupBtn.clicked.connect(self.add_skill_group)
        
        self.editGroupBtn = PushButton("编辑")
        self.editGroupBtn.setIcon(FIF.EDIT)
        self.editGroupBtn.clicked.connect(self.edit_skill_group)
        
        self.deleteGroupBtn = PushButton("删除")
        self.deleteGroupBtn.setIcon(FIF.DELETE)
        self.deleteGroupBtn.clicked.connect(self.delete_skill_group)
        
        groupButtonLayout.addWidget(self.addGroupBtn)
        groupButtonLayout.addWidget(self.editGroupBtn)
        groupButtonLayout.addWidget(self.deleteGroupBtn)
        leftLayout.addLayout(groupButtonLayout)
        
        # 右侧技能组详情
        rightPanel = QWidget()
        rightLayout = QVBoxLayout(rightPanel)
        rightLayout.setContentsMargins(0, 0, 0, 0)
        rightLayout.setSpacing(12)
        
        # 组详情区域
        detailsLabel = SubtitleLabel("技能组详情")
        rightLayout.addWidget(detailsLabel)
        
        detailsWidget = QWidget()
        detailsWidget.setStyleSheet("background-color: #f8f8f8; border-radius: 6px; padding: 10px;")
        detailsLayout = QVBoxLayout(detailsWidget)
        
        # 名称区域
        self.groupNameLabel = StrongBodyLabel("未选择技能组")
        self.groupNameLabel.setStyleSheet("font-size: 16px; color: #2c3e50;")
        detailsLayout.addWidget(self.groupNameLabel)
        
        # 描述区域
        self.groupDescLabel = BodyLabel("请在左侧列表中选择一个技能组以查看详情。")
        self.groupDescLabel.setWordWrap(True)
        detailsLayout.addWidget(self.groupDescLabel)
        
        # 启用状态
        self.groupEnabledLabel = BodyLabel("状态: --")
        detailsLayout.addWidget(self.groupEnabledLabel)
        
        # 创建/更新时间
        self.groupTimeInfoLabel = CaptionLabel("创建时间: --")
        detailsLayout.addWidget(self.groupTimeInfoLabel)
        
        rightLayout.addWidget(detailsWidget)
        
        # 技能列表区域
        skillsLabel = SubtitleLabel("组内技能")
        rightLayout.addWidget(skillsLabel)
        
        self.skillsListWidget = QListWidget()
        self.skillsListWidget.setSelectionMode(QAbstractItemView.NoSelection)
        self.skillsListWidget.setStyleSheet("""
            QListWidget {
                border: 1px solid #e0e0e0;
                border-radius: 5px;
                background-color: white;
                outline: none;
                padding: 2px;
            }
            QListWidget::item {
                padding: 6px;
                border-bottom: 1px solid #f0f0f0;
                margin: 2px 0;
                border-radius: 4px;
            }
        """)
        rightLayout.addWidget(self.skillsListWidget, 1)
        
        # 将左右面板添加到主布局
        mainLayout.addWidget(leftPanel)
        mainLayout.addWidget(rightPanel, 1)
        
        # 将主内容区域添加到对话框
        self.viewLayout.addWidget(mainContent, 1)
        
        # 创建按钮
        self.yesButton.setText("关闭")
        self.cancelButton.setVisible(False)
        
        # 连接信号
        self.groupListWidget.currentItemChanged.connect(self.on_group_selected)
    
    def refresh_group_list(self):
        """刷新技能组列表"""
        try:
            # 清空列表
            self.groupListWidget.clear()
            
            # 获取所有技能组
            groups = config_manager.get_all_skill_groups()
            
            # 默认组始终显示在第一位
            default_group_item = None
            
            # 添加到列表中
            for group in groups:
                item = QListWidgetItem()
                item.setText(group.name)
                item.setData(Qt.UserRole, group.id)
                
                # 禁用的组显示为灰色
                if not group.enabled:
                    item.setForeground(QColor("#999999"))
                    
                # 保存默认组项目引用
                if group.id == "default":
                    default_group_item = item
                    
                if group.id != "default":  # 先添加非默认组
                    self.groupListWidget.addItem(item)
            
            # 默认组添加到最前面
            if default_group_item:
                self.groupListWidget.insertItem(0, default_group_item)
                
            # 如果有项目，选中第一个
            if self.groupListWidget.count() > 0:
                self.groupListWidget.setCurrentRow(0)
        
        except Exception as e:
            print(f"刷新技能组列表时出错: {str(e)}")
            traceback.print_exc()
    
    def on_group_selected(self, current, previous):
        """选中技能组时的处理
        
        参数:
            current (QListWidgetItem): 当前选中的项
            previous (QListWidgetItem): 之前选中的项
        """
        if not current:
            self.clear_group_details()
            return
            
        # 获取选中的组ID
        group_id = current.data(Qt.UserRole)
        if not group_id:
            self.clear_group_details()
            return
            
        # 获取组详情
        group = config_manager.get_skill_group(group_id)
        if not group:
            self.clear_group_details()
            return
            
        # 更新组详情显示
        self.groupNameLabel.setText(group.name)
        self.groupDescLabel.setText(group.description if group.description else "无描述")
        self.groupEnabledLabel.setText(f"状态: {'启用' if group.enabled else '禁用'}")
        
        # 显示时间信息
        time_info = f"创建时间: {group.created_at}"
        if hasattr(group, 'updated_at') and group.updated_at:
            time_info += f" | 最后更新: {group.updated_at}"
        self.groupTimeInfoLabel.setText(time_info)
        
        # 显示该组中的技能
        self.refresh_group_skills(group)
    
    def refresh_group_skills(self, group):
        """刷新技能组中的技能列表
        
        参数:
            group (SkillGroup): 技能组对象
        """
        # 清空技能列表
        self.skillsListWidget.clear()
        
        # 获取组中的所有技能
        for skill_id in group.skill_ids:
            # 获取技能详情
            skill = config_manager.skills_db.get_skill(skill_id)
            if skill:
                item = QListWidgetItem()
                item.setText(f"{skill.name} - {skill.key}")
                
                # 禁用的技能显示灰色
                if not skill.enabled:
                    item.setForeground(QColor("#999999"))
                
                self.skillsListWidget.addItem(item)
        
        # 如果组中没有技能，显示提示信息
        if self.skillsListWidget.count() == 0:
            item = QListWidgetItem("该技能组中没有技能")
            item.setForeground(QColor("#999999"))
            self.skillsListWidget.addItem(item)
    
    def clear_group_details(self):
        """清空技能组详情显示"""
        self.groupNameLabel.setText("未选择技能组")
        self.groupDescLabel.setText("请在左侧列表中选择一个技能组以查看详情。")
        self.groupEnabledLabel.setText("状态: --")
        self.groupTimeInfoLabel.setText("创建时间: --")
        self.skillsListWidget.clear()
    
    def add_skill_group(self):
        """添加新技能组"""
        dialog = SkillGroupEditDialog(parent=self)
        if dialog.exec_():
            # 刷新列表
            self.refresh_group_list()
    
    def edit_skill_group(self):
        """编辑选中的技能组"""
        # 获取当前选中的技能组
        current_item = self.groupListWidget.currentItem()
        if not current_item:
            InfoBar.warning(
                title="未选择技能组",
                content="请先选择要编辑的技能组",
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.BOTTOM,  # 改为底部，避免TopInfoBarManager的问题
                duration=2000,
                parent=self
            )
            return
            
        # 获取组ID
        group_id = current_item.data(Qt.UserRole)
        if not group_id:
            return
            
        # 禁止编辑默认组
        if group_id == "default":
            InfoBar.warning(
                title="无法编辑",
                content="默认技能组不能被编辑",
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.BOTTOM,  # 改为底部，避免TopInfoBarManager的问题
                duration=2000,
                parent=self
            )
            return
            
        # 获取技能组
        group = config_manager.get_skill_group(group_id)
        if not group:
            return
            
        # 打开编辑对话框
        dialog = SkillGroupEditDialog(parent=self, group=group)
        if dialog.exec_():
            # 刷新列表和详情
            self.refresh_group_list()
    
    def delete_skill_group(self):
        """删除选中的技能组"""
        # 获取当前选中的技能组
        current_item = self.groupListWidget.currentItem()
        if not current_item:
            InfoBar.warning(
                title="未选择技能组",
                content="请先选择要删除的技能组",
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.BOTTOM,  # 改为底部，避免TopInfoBarManager的问题
                duration=2000,
                parent=self
            )
            return
            
        # 获取组ID
        group_id = current_item.data(Qt.UserRole)
        if not group_id:
            return
            
        # 默认组不能删除
        if group_id == "default":
            InfoBar.warning(
                title="无法删除",
                content="默认技能组不能被删除",
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.BOTTOM,  # 改为底部，避免TopInfoBarManager的问题
                duration=2000,
                parent=self
            )
            return
            
        # 确认删除
        group = config_manager.get_skill_group(group_id)
        if not group:
            return
            
        # 显示确认对话框
        confirm_dialog = ConfirmMessageBox(
            "确认删除",
            f"确定要删除技能组 {group.name} 吗？\n\n该组内的所有技能将被移动到默认组。",
            self
        )
        
        if confirm_dialog.exec():
            # 执行删除
            success = config_manager.remove_skill_group(group_id)
            
            if success:
                InfoBar.success(
                    title="删除成功",
                    content=f"技能组 {group.name} 已被删除",
                    orient=Qt.Horizontal,
                    isClosable=True,
                    position=InfoBarPosition.BOTTOM,  # 改为底部，避免TopInfoBarManager的问题
                    duration=2000,
                    parent=self
                )
                
                # 刷新列表
                self.refresh_group_list()
            else:
                InfoBar.error(
                    title="删除失败",
                    content="技能组删除失败，请检查日志",
                    orient=Qt.Horizontal,
                    isClosable=True,
                    position=InfoBarPosition.BOTTOM,  # 改为底部，避免TopInfoBarManager的问题
                    duration=2000,
                    parent=self
                ) 

class SkillGroupEditDialog(MessageBoxBase):
    """技能组编辑对话框"""
    
    def __init__(self, parent=None, group=None):
        super().__init__(parent)
        self.group = group
        
        # 是否为编辑模式
        self.edit_mode = group is not None
        
        # 设置对话框属性
        self.setDraggable(False)
        self.setMaskColor(QColor(0, 0, 0, 0))
        self.setShadowEffect(60, (0, 6), QColor(0, 0, 0, 80))
        
        # 设置标题
        self._window_title = "编辑技能组" if self.edit_mode else "添加技能组"
        
        # 设置对话框样式
        self.widget.setObjectName("skillGroupEditDialogWidget")
        self.widget.setStyleSheet("""
            #skillGroupEditDialogWidget {
                background-color: #ffffff;
                border-radius: 8px;
            }
        """)
        
        # 设置对话框的初始大小
        self.widget.setMinimumWidth(480)
        self.widget.setMinimumHeight(440)
        
        self.initUI()
        
        # 如果是编辑模式，填充现有数据
        if self.edit_mode and self.group:
            self.nameLineEdit.setText(self.group.name)
            self.descTextEdit.setPlainText(self.group.description)
            self.enabledCheck.setChecked(self.group.enabled)
            
            # 选中该组包含的技能
            self.select_group_skills()
    
    def initUI(self):
        """初始化对话框UI"""
        # 设置整体布局结构
        self.viewLayout.setSpacing(16)
        self.viewLayout.setContentsMargins(24, 24, 24, 24)
        
        # 添加标题标签
        self.titleLabel = TitleLabel(self._window_title)
        self.viewLayout.addWidget(self.titleLabel)
        
        # 添加间隔
        spacer = QSpacerItem(20, 10, QSizePolicy.Minimum, QSizePolicy.Fixed)
        self.viewLayout.addSpacerItem(spacer)
        
        # 错误信息标签
        self.error_label = BodyLabel("")
        self.error_label.setStyleSheet("color: #e74c3c;")
        self.error_label.setVisible(False)
        self.viewLayout.addWidget(self.error_label)
        
        # 创建表单布局
        formWidget = QWidget()
        formLayout = QGridLayout(formWidget)
        formLayout.setContentsMargins(0, 0, 0, 0)
        formLayout.setVerticalSpacing(16)
        formLayout.setHorizontalSpacing(16)
        
        # 字段标签样式
        label_style = "font-weight: bold;"
        
        # 设置列宽比例
        formLayout.setColumnStretch(0, 1)   # 标签列
        formLayout.setColumnStretch(1, 3)   # 控件列
        
        # 名称字段
        nameLabel = BodyLabel("组名称:")
        nameLabel.setStyleSheet(label_style)
        self.nameLineEdit = LineEdit()
        self.nameLineEdit.setPlaceholderText("输入技能组名称")
        self.nameLineEdit.setClearButtonEnabled(True)
        
        row = 0
        formLayout.addWidget(nameLabel, row, 0, Qt.AlignRight | Qt.AlignVCenter)
        formLayout.addWidget(self.nameLineEdit, row, 1)
        
        # 描述字段
        descLabel = BodyLabel("描述:")
        descLabel.setStyleSheet(label_style)
        self.descTextEdit = QTextEdit()
        self.descTextEdit.setPlaceholderText("输入技能组描述")
        self.descTextEdit.setMaximumHeight(100)
        
        row += 1
        formLayout.addWidget(descLabel, row, 0, Qt.AlignRight | Qt.AlignTop)
        formLayout.addWidget(self.descTextEdit, row, 1)
        
        # 启用状态
        enabledLabel = BodyLabel("启用状态:")
        enabledLabel.setStyleSheet(label_style)
        self.enabledCheck = CheckBox("启用")
        self.enabledCheck.setChecked(True)
        
        row += 1
        formLayout.addWidget(enabledLabel, row, 0, Qt.AlignRight | Qt.AlignVCenter)
        formLayout.addWidget(self.enabledCheck, row, 1)
        
        # 添加表单到视图
        self.viewLayout.addWidget(formWidget)
        
        # 技能列表
        skillsLabel = SubtitleLabel("包含的技能")
        self.viewLayout.addWidget(skillsLabel)
        
        # 创建技能选择列表
        self.skillsListWidget = QListWidget()
        self.skillsListWidget.setSelectionMode(QAbstractItemView.NoSelection)
        self.skillsListWidget.setStyleSheet("""
            QListWidget {
                border: 1px solid #e0e0e0;
                border-radius: 5px;
                background-color: white;
                outline: none;
                padding: 2px;
            }
            QListWidget::item {
                padding: 4px;
                border-bottom: 1px solid #f0f0f0;
            }
        """)
        self.skillsListWidget.setMaximumHeight(200)
        
        # 添加所有可用技能到列表
        self.load_skills()
        
        self.viewLayout.addWidget(self.skillsListWidget)
        
        # 添加弹性空间
        self.viewLayout.addStretch(1)
        
        # 设置按钮
        self.yesButton.setText("保存")
        self.cancelButton.setText("取消")
        
        # 连接信号
        self.yesButton.clicked.connect(self.validate)
    
    def load_skills(self):
        """加载所有可用技能到列表中"""
        try:
            # 清空列表
            self.skillsListWidget.clear()
            
            # 获取所有技能
            skills = config_manager.skills_db.skills
            
            # 按名称排序
            skills = sorted(skills, key=lambda x: x.name.lower())
            
            # 添加技能到列表，使用复选框
            for skill in skills:
                item = QListWidgetItem()
                self.skillsListWidget.addItem(item)
                
                # 创建复选框
                checkbox = CheckBox(f"{skill.name} - {skill.key}")
                if not skill.enabled:
                    checkbox.setStyleSheet("color: #999999;")
                
                # 设置数据
                checkbox.skill_id = skill.id
                
                # 设置项目小部件
                self.skillsListWidget.setItemWidget(item, checkbox)
        except Exception as e:
            print(f"加载技能列表时出错: {str(e)}")
            traceback.print_exc()
    
    def select_group_skills(self):
        """选中该组包含的技能"""
        if not self.group or not hasattr(self.group, 'skill_ids'):
            return
            
        # 遍历所有技能项
        for i in range(self.skillsListWidget.count()):
            item = self.skillsListWidget.item(i)
            checkbox = self.skillsListWidget.itemWidget(item)
            
            if hasattr(checkbox, 'skill_id') and checkbox.skill_id in self.group.skill_ids:
                checkbox.setChecked(True)
    
    def validate(self):
        """验证并保存技能组"""
        try:
            # 获取表单数据
            name = self.nameLineEdit.text().strip()
            description = self.descTextEdit.toPlainText().strip()
            enabled = self.enabledCheck.isChecked()
            
            # 验证名称
            if not name:
                self.error_label.setText("技能组名称不能为空")
                self.error_label.setVisible(True)
                return
            
            # 生成ID (编辑模式保持原ID)
            if self.edit_mode and self.group:
                group_id = self.group.id
            else:
                group_id = name.lower().replace(" ", "_")
                
                # 检查ID是否已存在
                existing_group = config_manager.get_skill_group(group_id)
                if existing_group and not self.edit_mode:
                    self.error_label.setText(f"技能组 {name} 已存在")
                    self.error_label.setVisible(True)
                    return
            
            # 收集选中的技能ID
            skill_ids = []
            for i in range(self.skillsListWidget.count()):
                item = self.skillsListWidget.item(i)
                checkbox = self.skillsListWidget.itemWidget(item)
                
                if checkbox.isChecked() and hasattr(checkbox, 'skill_id'):
                    skill_ids.append(checkbox.skill_id)
            
            # 创建或更新技能组
            if self.edit_mode and self.group:
                # 更新现有组
                self.group.name = name
                self.group.description = description
                self.group.enabled = enabled
                self.group.skill_ids = skill_ids
                self.group.updated_at = datetime.now().isoformat()
                
                # 保存到配置
                success = config_manager.update_skill_group(self.group)
            else:
                # 创建新组
                new_group = SkillGroup(
                    id=group_id,
                    name=name,
                    enabled=enabled,
                    description=description,
                    created_at=datetime.now().isoformat(),
                    updated_at=datetime.now().isoformat(),
                    skill_ids=skill_ids
                )
                
                # 保存到配置
                success = config_manager.add_skill_group(new_group)
            
            # 更新所有选中技能的组ID
            for skill_id in skill_ids:
                skill = config_manager.skills_db.get_skill(skill_id)
                if skill and skill.group_id != group_id:
                    skill.group_id = group_id
                    config_manager.skills_db.add_skill(skill)
            
            # 保存技能数据库
            config_manager.save_skills_db()
            
            # 处理结果
            if success:
                # 关闭对话框
                self.accept()
            else:
                self.error_label.setText("保存技能组失败")
                self.error_label.setVisible(True)
                
        except Exception as e:
            self.error_label.setText(f"保存失败: {str(e)}")
            self.error_label.setVisible(True)
            print(f"保存技能组时出错: {str(e)}")
            traceback.print_exc()