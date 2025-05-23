"""
条件编辑器UI模块

这个模块包含了条件系统相关的UI组件，用于创建、编辑和管理条件。
"""

import os
import cv2
import numpy as np
import time
from datetime import datetime
from typing import List, Dict, Optional, Any

from PyQt5.QtCore import Qt, QRect, pyqtSignal, QObject, QTimer
from PyQt5.QtGui import QColor, QPixmap, QImage
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
                            QLabel, QListWidget, QListWidgetItem, QAbstractItemView,
                            QComboBox, QSpacerItem, QSizePolicy, QTextEdit, 
                            QScrollArea, QFrame, QApplication, QDialog, QFormLayout)

from qfluentwidgets import (PushButton, PrimaryPushButton, ComboBox, RadioButton, CheckBox,
                           Slider, SwitchButton, ToggleButton, SubtitleLabel, BodyLabel,
                           Action, MessageBox, MessageBoxBase, InfoBar, TransparentPushButton,
                           LineEdit, StrongBodyLabel, CaptionLabel, SpinBox, DoubleSpinBox,
                           ScrollArea, CardWidget, HeaderCardWidget, InfoBarPosition, FluentIcon as FIF,
                           TitleLabel, SimpleCardWidget)

from 选择框 import show_selection_box
from skill_data_models import Condition, ConditionParameter, ConditionReference, config_manager
import traceback

class ConditionManagementDialog(MessageBoxBase):
    """条件管理对话框
    
    用于管理系统中的条件，包括添加、编辑、删除和测试条件。
    """
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # 设置对话框属性
        self.setDraggable(False)
        self.setMaskColor(QColor(0, 0, 0, 0))
        self.setShadowEffect(60, (0, 6), QColor(0, 0, 0, 80))
        
        # 设置标题
        self._window_title = "条件管理"
        
        # 设置对话框样式
        self.widget.setObjectName("conditionManagementDialogWidget")
        self.widget.setStyleSheet("""
            #conditionManagementDialogWidget {
                background-color: #ffffff;
                border-radius: 8px;
            }
        """)
        
        # 设置对话框的初始大小
        self.widget.setMinimumWidth(720)
        self.widget.setMinimumHeight(540)
        
        # 初始化UI
        self.initUI()
        
        # 刷新条件列表
        self.refresh_condition_list()
        
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
        
        # 左侧条件列表
        leftPanel = QWidget()
        leftLayout = QVBoxLayout(leftPanel)
        leftLayout.setContentsMargins(0, 0, 0, 0)
        leftLayout.setSpacing(8)
        
        conditionListLabel = SubtitleLabel("条件列表")
        leftLayout.addWidget(conditionListLabel)
        
        self.conditionListWidget = QListWidget()
        self.conditionListWidget.setSelectionMode(QAbstractItemView.SingleSelection)
        self.conditionListWidget.setMaximumWidth(240)
        self.conditionListWidget.setStyleSheet("""
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
        leftLayout.addWidget(self.conditionListWidget, 1)
        
        # 左侧按钮区域
        conditionButtonLayout = QHBoxLayout()
        
        self.addConditionBtn = PrimaryPushButton("添加")
        self.addConditionBtn.setIcon(FIF.ADD)
        self.addConditionBtn.clicked.connect(self.add_condition)
        
        self.editConditionBtn = PushButton("编辑")
        self.editConditionBtn.setIcon(FIF.EDIT)
        self.editConditionBtn.clicked.connect(self.edit_condition)
        
        self.deleteConditionBtn = PushButton("删除")
        self.deleteConditionBtn.setIcon(FIF.DELETE)
        self.deleteConditionBtn.clicked.connect(self.delete_condition)
        
        conditionButtonLayout.addWidget(self.addConditionBtn)
        conditionButtonLayout.addWidget(self.editConditionBtn)
        conditionButtonLayout.addWidget(self.deleteConditionBtn)
        leftLayout.addLayout(conditionButtonLayout)
        
        # 右侧条件详情
        rightPanel = QWidget()
        rightLayout = QVBoxLayout(rightPanel)
        rightLayout.setContentsMargins(0, 0, 0, 0)
        rightLayout.setSpacing(12)
        
        # 条件详情区域
        detailsLabel = SubtitleLabel("条件详情")
        rightLayout.addWidget(detailsLabel)
        
        detailsWidget = QWidget()
        detailsWidget.setStyleSheet("background-color: #f8f8f8; border-radius: 6px; padding: 10px;")
        detailsLayout = QVBoxLayout(detailsWidget)
        
        # 名称区域
        self.conditionNameLabel = StrongBodyLabel("未选择条件")
        self.conditionNameLabel.setStyleSheet("font-size: 16px; color: #2c3e50;")
        detailsLayout.addWidget(self.conditionNameLabel)
        
        # 类型区域
        self.conditionTypeLabel = BodyLabel("类型: --")
        detailsLayout.addWidget(self.conditionTypeLabel)
        
        # 启用状态
        self.conditionEnabledLabel = BodyLabel("状态: --")
        detailsLayout.addWidget(self.conditionEnabledLabel)
        
        # 描述区域
        self.conditionDescLabel = BodyLabel("描述: --")
        self.conditionDescLabel.setWordWrap(True)
        detailsLayout.addWidget(self.conditionDescLabel)
        
        # 参数区域
        self.conditionParamsLabel = BodyLabel("参数: --")
        self.conditionParamsLabel.setWordWrap(True)
        detailsLayout.addWidget(self.conditionParamsLabel)
        
        rightLayout.addWidget(detailsWidget)
        
        # 添加条件测试区域
        testLabel = SubtitleLabel("条件测试")
        rightLayout.addWidget(testLabel)
        
        testWidget = QWidget()
        testWidget.setStyleSheet("background-color: #f8f8f8; border-radius: 6px; padding: 10px;")
        testLayout = QVBoxLayout(testWidget)
        
        # 测试状态显示
        self.testStatusLabel = StrongBodyLabel("选择条件进行测试")
        self.testStatusLabel.setStyleSheet("font-size: 14px; color: #2c3e50;")
        testLayout.addWidget(self.testStatusLabel)
        
        # 测试按钮
        testButtonLayout = QHBoxLayout()
        
        self.testConditionBtn = PrimaryPushButton("测试条件")
        self.testConditionBtn.setIcon(FIF.PLAY)
        self.testConditionBtn.clicked.connect(self.test_condition)
        
        testButtonLayout.addWidget(self.testConditionBtn)
        testButtonLayout.addStretch(1)
        
        testLayout.addLayout(testButtonLayout)
        rightLayout.addWidget(testWidget)
        
        # 将右侧面板设置为可伸缩
        rightLayout.addStretch(1)
        
        # 将左右面板添加到主布局
        mainLayout.addWidget(leftPanel)
        mainLayout.addWidget(rightPanel, 1)
        
        # 将主内容区域添加到对话框
        self.viewLayout.addWidget(mainContent, 1)
        
        # 创建按钮
        self.yesButton.setText("关闭")
        self.cancelButton.setVisible(False)
        
        # 连接信号
        self.conditionListWidget.currentItemChanged.connect(self.on_condition_selected)
    
    def refresh_condition_list(self):
        """刷新条件列表"""
        try:
            # 清空列表
            self.conditionListWidget.clear()
            
            # 获取所有条件
            conditions = config_manager.conditions_db.conditions
            
            # 添加到列表中
            for condition in conditions:
                item = QListWidgetItem()
                item.setText(condition.name)
                item.setData(Qt.UserRole, condition.id)
                
                # 设置启用/禁用状态的视觉提示
                if not condition.enabled:
                    item.setForeground(QColor("#999999"))
                
                self.conditionListWidget.addItem(item)
                
        except Exception as e:
            print(f"刷新条件列表时出错: {str(e)}")
            traceback.print_exc()
    
    def on_condition_selected(self, current, previous):
        """当选择条件改变时更新详情显示
        
        参数:
            current (QListWidgetItem): 当前选中的项
            previous (QListWidgetItem): 之前选中的项
        """
        if not current:
            self.clear_condition_details()
            return
            
        # 获取条件ID
        condition_id = current.data(Qt.UserRole)
        if not condition_id:
            self.clear_condition_details()
            return
            
        # 获取条件对象
        condition = config_manager.get_condition(condition_id)
        if not condition:
            self.clear_condition_details()
            return
            
        # 更新详情显示
        self.conditionNameLabel.setText(condition.name)
        self.conditionTypeLabel.setText(f"类型: {condition.type}")
        self.conditionEnabledLabel.setText(f"状态: {'启用' if condition.enabled else '禁用'}")
        
        if condition.description:
            self.conditionDescLabel.setText(f"描述: {condition.description}")
        else:
            self.conditionDescLabel.setText("描述: 无")
        
        # 显示参数信息
        params_text = "参数:\n"
        for key, value in condition.parameters.items():
            params_text += f"- {key}: {value}\n"
        self.conditionParamsLabel.setText(params_text)
    
    def clear_condition_details(self):
        """清空条件详情显示"""
        self.conditionNameLabel.setText("未选择条件")
        self.conditionTypeLabel.setText("类型: --")
        self.conditionEnabledLabel.setText("状态: --")
        self.conditionDescLabel.setText("描述: --")
        self.conditionParamsLabel.setText("参数: --")
        self.testStatusLabel.setText("选择条件进行测试")
    
    def add_condition(self):
        """添加新条件"""
        try:
            # 创建条件编辑对话框
            dialog = ConditionEditDialog(parent=self)
            
            # 显示对话框
            result = dialog.exec_()
            
            # 如果用户点击了确认按钮，获取条件数据并保存
            if result == QDialog.Accepted:
                # validate方法已经保存了条件数据到config_manager.conditions_db中
                # 所以这里只需要刷新条件列表
                self.refresh_condition_list()
                
                # 显示成功消息
                InfoBar.success(
                    title="添加成功",
                    content="条件已成功添加",
                    orient=Qt.Horizontal,
                    isClosable=True,
                    position=InfoBarPosition.TOP,
                    duration=2000,
                    parent=self
                )
                
        except Exception as e:
            print(f"添加条件时出错: {str(e)}")
            traceback.print_exc()
            
            # 显示错误信息
            InfoBar.error(
                title="添加失败",
                content=f"添加条件时出错: {str(e)}",
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=3000,
                parent=self
            )
    
    def edit_condition(self):
        """编辑选中条件"""
        try:
            # 获取选中的条件项
            selected_items = self.conditionListWidget.selectedItems()
            if not selected_items:
                InfoBar.warning(
                    title="未选择条件",
                    content="请先选择一个条件进行编辑",
                    orient=Qt.Horizontal,
                    isClosable=True,
                    position=InfoBarPosition.TOP,
                    duration=2000,
                    parent=self
                )
                return
                
            # 获取条件ID
            condition_id = selected_items[0].data(Qt.UserRole)
            
            # 从配置管理器获取条件
            condition_data = config_manager.get_condition(condition_id)
            if not condition_data:
                InfoBar.error(
                    title="条件不存在",
                    content=f"找不到ID为 {condition_id} 的条件",
                    orient=Qt.Horizontal,
                    isClosable=True,
                    position=InfoBarPosition.TOP,
                    duration=2000,
                    parent=self
                )
                return
                
            # 创建条件编辑对话框，传入现有条件数据
            dialog = ConditionEditDialog(parent=self, condition=condition_data)
            
            # 显示对话框
            result = dialog.exec_()
            
            # 如果用户点击了确认按钮，获取条件数据并保存
            if result == QDialog.Accepted:
                # validate方法已经保存了条件数据到config_manager.conditions_db中
                # 所以这里只需要刷新条件列表
                self.refresh_condition_list()
                
                # 重新选择编辑的条件
                for i in range(self.conditionListWidget.count()):
                    item = self.conditionListWidget.item(i)
                    if item.data(Qt.UserRole) == condition_id:
                        self.conditionListWidget.setCurrentItem(item)
                        break
                
                # 显示成功消息
                InfoBar.success(
                    title="编辑成功",
                    content="条件已成功更新",
                    orient=Qt.Horizontal,
                    isClosable=True,
                    position=InfoBarPosition.TOP,
                    duration=2000,
                    parent=self
                )
                
        except Exception as e:
            print(f"编辑条件时出错: {str(e)}")
            traceback.print_exc()
            
            # 显示错误信息
            InfoBar.error(
                title="编辑失败",
                content=f"编辑条件时出错: {str(e)}",
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=3000,
                parent=self
            )
    
    def delete_condition(self):
        """删除选中条件"""
        try:
            # 获取选中的条件项
            selected_items = self.conditionListWidget.selectedItems()
            if not selected_items:
                InfoBar.warning(
                    title="未选择条件",
                    content="请先选择一个条件进行删除",
                    orient=Qt.Horizontal,
                    isClosable=True,
                    position=InfoBarPosition.TOP,
                    duration=2000,
                    parent=self
                )
                return
                
            # 获取条件ID和名称
            condition_id = selected_items[0].data(Qt.UserRole)
            condition_name = selected_items[0].text()
            
            # 从配置管理器获取条件
            condition_data = config_manager.get_condition(condition_id)
            if not condition_data:
                InfoBar.error(
                    title="条件不存在",
                    content=f"找不到ID为 {condition_id} 的条件",
                    orient=Qt.Horizontal,
                    isClosable=True,
                    position=InfoBarPosition.TOP,
                    duration=2000,
                    parent=self
                )
                return
                
            # 创建确认对话框
            from skill_cycle_ui import ConfirmMessageBox
            confirm_dialog = ConfirmMessageBox(
                title="确认删除",
                content=f"确定要删除条件 \"{condition_name}\" 吗？\n\n删除后无法恢复，且可能影响依赖此条件的技能。",
                parent=self
            )
            
            # 显示确认对话框
            if confirm_dialog.exec_() == QDialog.Accepted:
                # 从条件数据库中删除条件
                if config_manager.conditions_db.remove_condition(condition_id):
                    # 保存条件数据库
                    config_manager.save_conditions_db()
                    
                    # 刷新条件列表
                    self.refresh_condition_list()
                    
                    # 清除条件详情
                    self.clear_condition_details()
                    
                    # 显示成功消息
                    InfoBar.success(
                        title="删除成功",
                        content=f"条件 \"{condition_name}\" 已成功删除",
                        orient=Qt.Horizontal,
                        isClosable=True,
                        position=InfoBarPosition.TOP,
                        duration=2000,
                        parent=self
                    )
                else:
                    # 删除失败
                    InfoBar.error(
                        title="删除失败",
                        content=f"无法删除条件 \"{condition_name}\"",
                        orient=Qt.Horizontal,
                        isClosable=True,
                        position=InfoBarPosition.TOP,
                        duration=2000,
                        parent=self
                    )
                
        except Exception as e:
            print(f"删除条件时出错: {str(e)}")
            traceback.print_exc()
            
            # 显示错误信息
            InfoBar.error(
                title="删除失败",
                content=f"删除条件时出错: {str(e)}",
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=3000,
                parent=self
            )
    
    def test_condition(self):
        """测试选中条件"""
        try:
            # 获取选中的条件项
            selected_items = self.conditionListWidget.selectedItems()
            if not selected_items:
                InfoBar.warning(
                    title="未选择条件",
                    content="请先选择一个条件进行测试",
                    orient=Qt.Horizontal,
                    isClosable=True,
                    position=InfoBarPosition.TOP,
                    duration=2000,
                    parent=self
                )
                return
                
            # 获取条件ID
            condition_id = selected_items[0].data(Qt.UserRole)
            
            # 从配置管理器获取条件
            condition_data = config_manager.get_condition(condition_id)
            if not condition_data:
                InfoBar.error(
                    title="条件不存在",
                    content=f"找不到ID为 {condition_id} 的条件",
                    orient=Qt.Horizontal,
                    isClosable=True,
                    position=InfoBarPosition.TOP,
                    duration=2000,
                    parent=self
                )
                return
                
            # 更新测试状态显示
            self.testStatusLabel.setText("正在测试条件...")
            QApplication.processEvents()
            
            # 根据条件类型执行不同的测试
            if condition_data.type == "color":
                result = self._test_color_condition(condition_data)
            elif condition_data.type == "time":
                result = self._test_time_condition(condition_data)
            elif condition_data.type == "combo":
                result = self._test_combo_condition(condition_data)
            else:
                InfoBar.error(
                    title="不支持的条件类型",
                    content=f"不支持测试 {condition_data.type} 类型的条件",
                    orient=Qt.Horizontal,
                    isClosable=True,
                    position=InfoBarPosition.TOP,
                    duration=2000,
                    parent=self
                )
                self.testStatusLabel.setText("测试失败: 不支持的条件类型")
                return
                
            # 显示测试结果
            if result:
                self.testStatusLabel.setText("测试结果: 条件满足 ✓")
                self.testStatusLabel.setStyleSheet("color: #2ecc71; font-weight: bold;")
                
                InfoBar.success(
                    title="条件测试",
                    content="条件满足 ✓",
                    orient=Qt.Horizontal,
                    isClosable=True,
                    position=InfoBarPosition.TOP,
                    duration=2000,
                    parent=self
                )
            else:
                self.testStatusLabel.setText("测试结果: 条件不满足 ✗")
                self.testStatusLabel.setStyleSheet("color: #e74c3c; font-weight: bold;")
                
                InfoBar.warning(
                    title="条件测试",
                    content="条件不满足 ✗",
                    orient=Qt.Horizontal,
                    isClosable=True,
                    position=InfoBarPosition.TOP,
                    duration=2000,
                    parent=self
                )
                
        except Exception as e:
            print(f"测试条件时出错: {str(e)}")
            traceback.print_exc()
            
            # 显示错误信息
            self.testStatusLabel.setText(f"测试失败: {str(e)}")
            self.testStatusLabel.setStyleSheet("color: #e74c3c;")
            
            InfoBar.error(
                title="测试失败",
                content=f"测试条件时出错: {str(e)}",
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=3000,
                parent=self
            )
            
    def _test_color_condition(self, condition_data):
        """测试颜色条件
        
        参数:
            condition_data: 条件数据对象
            
        返回:
            bool: 测试结果，True表示满足，False表示不满足
        """
        try:
            # 获取条件参数
            params = condition_data.parameters
            
            # 获取要检测的颜色和容差
            target_color = params.get("color", [0, 0, 0])
            tolerance = params.get("tolerance", 20)
            
            # 获取检测区域
            region = params.get("region", {"x1": 0, "y1": 0, "x2": 0, "y2": 0})
            
            # 检查区域是否有效
            if region["x1"] == region["x2"] or region["y1"] == region["y2"]:
                InfoBar.warning(
                    title="无效区域",
                    content="检测区域无效，请重新设置区域",
                    orient=Qt.Horizontal,
                    isClosable=True,
                    position=InfoBarPosition.TOP,
                    duration=2000,
                    parent=self
                )
                return False
                
            # 捕获屏幕区域
            import cv2
            import numpy as np
            import pyautogui
            
            # 截取指定区域的屏幕
            screenshot = pyautogui.screenshot(region=(
                region["x1"],
                region["y1"],
                region["x2"] - region["x1"],
                region["y2"] - region["y1"]
            ))
            
            # 转换为numpy数组
            img = np.array(screenshot)
            img = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
            
            # 计算平均颜色
            avg_color = cv2.mean(img)[:3]
            
            # 检查颜色是否在容差范围内
            color_diff = np.sqrt(np.sum(np.square(np.array(avg_color) - np.array(target_color))))
            
            # 显示测试详情
            detail_text = (
                f"目标颜色: RGB({target_color[2]}, {target_color[1]}, {target_color[0]})\n"
                f"实际颜色: RGB({int(avg_color[2])}, {int(avg_color[1])}, {int(avg_color[0])})\n"
                f"容差: {tolerance}, 差异: {int(color_diff)}"
            )
            print(detail_text)
            
            # 返回是否满足条件
            return color_diff <= tolerance
            
        except Exception as e:
            print(f"测试颜色条件时出错: {str(e)}")
            traceback.print_exc()
            return False
            
    def _test_time_condition(self, condition_data):
        """测试时间条件
        
        参数:
            condition_data: 条件数据对象
            
        返回:
            bool: 测试结果，True表示满足，False表示不满足
        """
        # 时间条件无法直接测试，总是返回True
        InfoBar.info(
            title="时间条件",
            content="时间条件是基于时间间隔触发的，无法立即测试。假设条件满足。",
            orient=Qt.Horizontal,
            isClosable=True,
            position=InfoBarPosition.TOP,
            duration=3000,
            parent=self
        )
        return True
        
    def _test_combo_condition(self, condition_data):
        """测试组合条件
        
        参数:
            condition_data: 条件数据对象
            
        返回:
            bool: 测试结果，True表示满足，False表示不满足
        """
        try:
            # 获取条件参数
            params = condition_data.parameters
            combo_type = params.get("combo_type", "AND")
            
            # 获取子条件列表
            sub_conditions = condition_data.sub_conditions
            
            # 如果没有子条件，返回False
            if not sub_conditions:
                InfoBar.warning(
                    title="无子条件",
                    content="组合条件没有子条件，无法测试",
                    orient=Qt.Horizontal,
                    isClosable=True,
                    position=InfoBarPosition.TOP,
                    duration=2000,
                    parent=self
                )
                return False
                
            # 测试每个子条件
            results = []
            for sub_ref in sub_conditions:
                # 获取子条件数据
                sub_condition = config_manager.get_condition(sub_ref.id)
                if not sub_condition:
                    print(f"找不到子条件: {sub_ref.id}")
                    continue
                    
                # 根据子条件类型测试
                if sub_condition.type == "color":
                    result = self._test_color_condition(sub_condition)
                elif sub_condition.type == "time":
                    result = self._test_time_condition(sub_condition)
                elif sub_condition.type == "combo":
                    # 避免递归层级过深
                    InfoBar.warning(
                        title="嵌套组合条件",
                        content="不支持测试嵌套的组合条件",
                        orient=Qt.Horizontal,
                        isClosable=True,
                        position=InfoBarPosition.TOP,
                        duration=2000,
                        parent=self
                    )
                    result = False
                else:
                    result = False
                    
                results.append(result)
                
            # 根据组合类型计算最终结果
            if combo_type == "AND":
                return all(results)
            else:  # "OR"
                return any(results)
                
        except Exception as e:
            print(f"测试组合条件时出错: {str(e)}")
            traceback.print_exc()
            return False

class ConditionEditDialog(MessageBoxBase):
    """条件编辑对话框"""
    
    def __init__(self, parent=None, condition=None):
        super().__init__(parent)
        self.condition = condition
        
        # 是否为编辑模式
        self.edit_mode = condition is not None
        
        # 区域数据
        self.region_data = None
        
        # 颜色数据
        self.color_data = None
        
        # 参考图像
        self.reference_image = None
        
        # 设置UI
        self._setup_ui()
        
        # 如果是编辑模式，加载现有条件数据
        if self.edit_mode:
            self._load_condition_data()
    
    def _load_condition_data(self):
        """加载条件数据到UI"""
        if not self.condition:
            return
            
        # 设置名称
        self.nameLineEdit.setText(self.condition.name)
        
        # 设置条件类型
        condition_type = getattr(self.condition, "type", "color_match")
        index = 0  # 默认为颜色匹配
        if condition_type == "pixel_match":
            index = 1
        self.typeComboBox.setCurrentIndex(index)
        
        # 加载参数
        params = getattr(self.condition, "params", {})
        if params:
            # 加载区域数据
            if "region" in params:
                self.region_data = params["region"]
                x1 = self.region_data.get("x1", 0)
                y1 = self.region_data.get("y1", 0)
                x2 = self.region_data.get("x2", 0)
                y2 = self.region_data.get("y2", 0)
                width = x2 - x1
                height = y2 - y1
                self.regionInfoLabel.setText(f"x:{x1}, y:{y1}, 宽:{width}, 高:{height}")
            
            # 根据条件类型加载特定参数
            if condition_type == "color_match":
                # 加载目标颜色
                if "target_color" in params:
                    self.color_data = params["target_color"]
                    r, g, b = self.color_data
                    self.colorPreviewLabel.setStyleSheet(f"background-color: rgb({r}, {g}, {b});")
                    self.colorInfoLabel.setText(f"RGB: ({r}, {g}, {b})")
                
                # 加载容差
                if "tolerance" in params:
                    tolerance = params["tolerance"]
                    self.toleranceSpinBox.setValue(tolerance)
                    self.toleranceSlider.setValue(tolerance)
            
            elif condition_type == "pixel_match":
                # 加载参考图像
                if "reference_image" in params:
                    self.reference_image = params["reference_image"]
                    if self.reference_image is not None:
                        h, w = self.reference_image.shape[:2]
                        self.referenceImageLabel.setText(f"已捕获参考图像 ({w}x{h})")
                
                # 加载阈值
                if "threshold" in params:
                    threshold = params["threshold"]
                    self.thresholdSpinBox.setValue(threshold)
                    self.thresholdSlider.setValue(int(threshold * 100))
    
    def _setup_ui(self):
        """设置UI"""
        # 设置对话框不可拖动
        self.setDraggable(False)
        
        # 设置遮罩颜色为完全透明
        self.setMaskColor(QColor(0, 0, 0, 0))
        
        # 设置更合适的阴影效果
        self.setShadowEffect(60, (0, 6), QColor(0, 0, 0, 80))
        
        # 设置标题
        self._window_title = "编辑条件" if self.edit_mode else "添加条件"
        
        # 设置对话框样式
        self.widget.setObjectName("conditionEditDialogWidget")
        self.widget.setStyleSheet("""
            #conditionEditDialogWidget {
                background-color: #ffffff;
                border-radius: 8px;
            }
        """)
        
        # 设置对话框的初始大小
        self.widget.setMinimumWidth(500)
        self.widget.setMinimumHeight(600)
        
        # 错误信息标签
        self.error_label = None
        
        # 初始化UI
        self.initUI()
        
        # 如果是编辑模式，填充当前条件数据
        if self.edit_mode and self.condition:
            self.fill_condition_data()
    
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
        
        # 使用滚动区域容纳表单
        scrollArea = ScrollArea()
        scrollArea.setWidgetResizable(True)
        scrollArea.setFrameShape(QFrame.NoFrame)
        
        # 创建表单容器
        self.formWidget = QWidget()
        self.formLayout = QGridLayout(self.formWidget)
        self.formLayout.setContentsMargins(0, 0, 0, 0)
        self.formLayout.setVerticalSpacing(16)
        self.formLayout.setHorizontalSpacing(16)
        
        # 设置表单布局的列宽比例
        self.formLayout.setColumnStretch(0, 1)   # 标签列
        self.formLayout.setColumnStretch(1, 3)   # 控件列
        
        # 字段标签样式
        label_style = "font-weight: bold;"
        
        # 创建表单字段
        row = 0
        
        # 条件名称
        nameLabel = BodyLabel("条件名称:")
        nameLabel.setStyleSheet(label_style)
        self.nameLineEdit = LineEdit()
        self.nameLineEdit.setPlaceholderText("输入条件名称")
        self.nameLineEdit.setClearButtonEnabled(True)
        self.formLayout.addWidget(nameLabel, row, 0, Qt.AlignRight | Qt.AlignVCenter)
        self.formLayout.addWidget(self.nameLineEdit, row, 1)
        
        row += 1
        
        # 条件类型
        typeLabel = BodyLabel("条件类型:")
        typeLabel.setStyleSheet(label_style)
        self.typeComboBox = ComboBox()
        self.typeComboBox.addItems(["颜色检测(color)", "时间条件(time)", "组合条件(combo)"])
        self.typeComboBox.currentIndexChanged.connect(self.on_condition_type_changed)
        self.formLayout.addWidget(typeLabel, row, 0, Qt.AlignRight | Qt.AlignVCenter)
        self.formLayout.addWidget(self.typeComboBox, row, 1)
        
        row += 1
        
        # 条件描述
        descLabel = BodyLabel("条件描述:")
        descLabel.setStyleSheet(label_style)
        self.descTextEdit = QTextEdit()
        self.descTextEdit.setPlaceholderText("输入条件描述（可选）")
        self.descTextEdit.setMaximumHeight(80)
        self.formLayout.addWidget(descLabel, row, 0, Qt.AlignRight | Qt.AlignVCenter)
        self.formLayout.addWidget(self.descTextEdit, row, 1)
        
        row += 1
        
        # 检查间隔
        intervalLabel = BodyLabel("检查间隔(秒):")
        intervalLabel.setStyleSheet(label_style)
        self.intervalSpinBox = DoubleSpinBox()
        self.intervalSpinBox.setRange(0.01, 10.0)
        self.intervalSpinBox.setSingleStep(0.1)
        self.intervalSpinBox.setValue(0.1)
        self.formLayout.addWidget(intervalLabel, row, 0, Qt.AlignRight | Qt.AlignVCenter)
        self.formLayout.addWidget(self.intervalSpinBox, row, 1)
        
        row += 1
        
        # 条件启用状态
        enabledLabel = BodyLabel("启用状态:")
        enabledLabel.setStyleSheet(label_style)
        self.enabledCheck = CheckBox("启用")
        self.enabledCheck.setChecked(True)
        self.formLayout.addWidget(enabledLabel, row, 0, Qt.AlignRight | Qt.AlignVCenter)
        self.formLayout.addWidget(self.enabledCheck, row, 1)
        
        row += 1
        
        # 创建参数区域标题
        paramsLabel = SubtitleLabel("条件参数")
        self.formLayout.addWidget(paramsLabel, row, 0, 1, 2, Qt.AlignLeft)
        
        row += 1
        
        # 创建参数容器，用于动态显示/隐藏不同类型的参数设置
        self.paramsContainer = QWidget()
        self.paramsLayout = QVBoxLayout(self.paramsContainer)
        self.paramsLayout.setContentsMargins(0, 0, 0, 0)
        self.formLayout.addWidget(self.paramsContainer, row, 0, 1, 2)
        
        # 初始化不同类型的参数设置组件
        self.setup_color_params()
        self.setup_time_params()
        self.setup_combo_params()
        
        # 根据默认选择的类型显示相应的参数设置
        self.on_condition_type_changed(0)  # 默认显示颜色条件参数
        
        # 将表单添加到滚动区域
        scrollArea.setWidget(self.formWidget)
        
        # 将滚动区域添加到主布局
        self.viewLayout.addWidget(scrollArea, 1)
        
        # 创建按钮
        self.yesButton.setText("保存")
        self.cancelButton.setText("取消")
        
        # 连接信号
        self.yesButton.clicked.connect(self.validate)
    
    def setup_color_params(self):
        """设置颜色条件参数UI"""
        self.colorParamsWidget = QWidget()
        layout = QGridLayout(self.colorParamsWidget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setVerticalSpacing(16)
        layout.setHorizontalSpacing(16)
        
        # 字段标签样式
        label_style = "font-weight: bold;"
        
        row = 0
        
        # 坐标设置
        xLabel = BodyLabel("X坐标:")
        xLabel.setStyleSheet(label_style)
        self.xSpinBox = SpinBox()
        self.xSpinBox.setRange(0, 9999)
        layout.addWidget(xLabel, row, 0, Qt.AlignRight | Qt.AlignVCenter)
        layout.addWidget(self.xSpinBox, row, 1)
        
        yLabel = BodyLabel("Y坐标:")
        yLabel.setStyleSheet(label_style)
        self.ySpinBox = SpinBox()
        self.ySpinBox.setRange(0, 9999)
        layout.addWidget(yLabel, row, 2, Qt.AlignRight | Qt.AlignVCenter)
        layout.addWidget(self.ySpinBox, row, 3)
        
        row += 1
        
        # 颜色预览
        colorPreviewLabel = BodyLabel("颜色预览:")
        colorPreviewLabel.setStyleSheet(label_style)
        
        previewWidget = QWidget()
        previewLayout = QHBoxLayout(previewWidget)
        previewLayout.setContentsMargins(0, 0, 0, 0)
        
        self.colorPreviewLabel = QLabel()
        self.colorPreviewLabel.setFixedSize(30, 30)
        self.colorPreviewLabel.setStyleSheet("background-color: rgb(0, 0, 0); border: 1px solid #cccccc;")
        
        self.colorInfoLabel = BodyLabel("RGB: (0, 0, 0)")
        
        # 添加选择颜色的按钮
        self.selectColorButton = PushButton("选择颜色")
        self.selectColorButton.setIcon(FIF.PALETTE)
        self.selectColorButton.clicked.connect(self.select_color)
        
        # RGB输入框的值变化信号将在下方连接
        
        previewLayout.addWidget(self.colorPreviewLabel)
        previewLayout.addWidget(self.colorInfoLabel)
        previewLayout.addWidget(self.selectColorButton)
        previewLayout.addStretch(1)
        
        layout.addWidget(colorPreviewLabel, row, 0, Qt.AlignRight | Qt.AlignVCenter)
        layout.addWidget(previewWidget, row, 1, 1, 3)
        
        row += 1
        
        # 颜色值
        colorLabel = BodyLabel("颜色值(RGB):")
        colorLabel.setStyleSheet(label_style)
        
        colorWidget = QWidget()
        colorLayout = QHBoxLayout(colorWidget)
        colorLayout.setContentsMargins(0, 0, 0, 0)
        
        self.rSpinBox = SpinBox()
        self.rSpinBox.setRange(0, 255)
        self.rSpinBox.setPrefix("R: ")
        
        self.gSpinBox = SpinBox()
        self.gSpinBox.setRange(0, 255)
        self.gSpinBox.setPrefix("G: ")
        
        self.bSpinBox = SpinBox()
        self.bSpinBox.setRange(0, 255)
        self.bSpinBox.setPrefix("B: ")
        
        colorLayout.addWidget(self.rSpinBox)
        colorLayout.addWidget(self.gSpinBox)
        colorLayout.addWidget(self.bSpinBox)
        
        # 连接RGB输入框的值变化信号
        self.rSpinBox.valueChanged.connect(self.update_color_preview)
        self.gSpinBox.valueChanged.connect(self.update_color_preview)
        self.bSpinBox.valueChanged.connect(self.update_color_preview)
        
        layout.addWidget(colorLabel, row, 0, Qt.AlignRight | Qt.AlignVCenter)
        layout.addWidget(colorWidget, row, 1, 1, 3)
        
        row += 1
        
        # 颜色容差
        toleranceLabel = BodyLabel("颜色容差:")
        toleranceLabel.setStyleSheet(label_style)
        self.toleranceSpinBox = SpinBox()
        self.toleranceSpinBox.setRange(0, 100)
        self.toleranceSpinBox.setValue(20)
        self.toleranceSpinBox.setToolTip("颜色匹配的容差范围，越大越宽松")
        layout.addWidget(toleranceLabel, row, 0, Qt.AlignRight | Qt.AlignVCenter)
        layout.addWidget(self.toleranceSpinBox, row, 1)
        
        row += 1
        
        # 区域设置按钮
        regionLabel = BodyLabel("检测区域:")
        regionLabel.setStyleSheet(label_style)
        
        self.regionButton = PushButton("选择区域")
        self.regionButton.setIcon(FIF.EDIT)
        self.regionButton.clicked.connect(self.select_region)
        
        layout.addWidget(regionLabel, row, 0, Qt.AlignRight | Qt.AlignVCenter)
        layout.addWidget(self.regionButton, row, 1)
        
        # 区域显示
        self.regionInfoLabel = BodyLabel("未设置区域")
        layout.addWidget(self.regionInfoLabel, row, 2, 1, 2)
        
        # 添加到参数布局
        self.paramsLayout.addWidget(self.colorParamsWidget)
        self.colorParamsWidget.setVisible(False)
    
    def setup_time_params(self):
        """设置时间条件参数UI"""
        self.timeParamsWidget = QWidget()
        layout = QGridLayout(self.timeParamsWidget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setVerticalSpacing(16)
        layout.setHorizontalSpacing(16)
        
        # 字段标签样式
        label_style = "font-weight: bold;"
        
        row = 0
        
        # 时间间隔
        intervalLabel = BodyLabel("触发间隔(秒):")
        intervalLabel.setStyleSheet(label_style)
        self.timeIntervalSpinBox = DoubleSpinBox()
        self.timeIntervalSpinBox.setRange(0.1, 3600.0)
        self.timeIntervalSpinBox.setSingleStep(1.0)
        self.timeIntervalSpinBox.setValue(60.0)
        layout.addWidget(intervalLabel, row, 0, Qt.AlignRight | Qt.AlignVCenter)
        layout.addWidget(self.timeIntervalSpinBox, row, 1)
        
        row += 1
        
        # 初始延迟
        delayLabel = BodyLabel("初始延迟(秒):")
        delayLabel.setStyleSheet(label_style)
        self.initialDelaySpinBox = DoubleSpinBox()
        self.initialDelaySpinBox.setRange(0.0, 60.0)
        self.initialDelaySpinBox.setSingleStep(1.0)
        self.initialDelaySpinBox.setValue(0.0)
        layout.addWidget(delayLabel, row, 0, Qt.AlignRight | Qt.AlignVCenter)
        layout.addWidget(self.initialDelaySpinBox, row, 1)
        
        # 添加到参数布局
        self.paramsLayout.addWidget(self.timeParamsWidget)
        self.timeParamsWidget.setVisible(False)
    
    def setup_combo_params(self):
        """设置组合条件参数UI"""
        self.comboParamsWidget = QWidget()
        layout = QVBoxLayout(self.comboParamsWidget)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # 组合类型
        comboTypeLayout = QHBoxLayout()
        
        comboTypeLabel = BodyLabel("组合类型:")
        comboTypeLabel.setStyleSheet("font-weight: bold;")
        
        self.andRadio = RadioButton("AND (所有条件满足)")
        self.orRadio = RadioButton("OR (任一条件满足)")
        self.andRadio.setChecked(True)
        
        comboTypeLayout.addWidget(comboTypeLabel)
        comboTypeLayout.addWidget(self.andRadio)
        comboTypeLayout.addWidget(self.orRadio)
        comboTypeLayout.addStretch(1)
        
        layout.addLayout(comboTypeLayout)
        
        # 子条件列表标题
        subConditionsLabel = BodyLabel("子条件列表:")
        subConditionsLabel.setStyleSheet("font-weight: bold;")
        layout.addWidget(subConditionsLabel)
        
        # 子条件列表
        self.subConditionsList = QListWidget()
        self.subConditionsList.setStyleSheet("""
            QListWidget {
                border: 1px solid #e0e0e0;
                border-radius: 5px;
                background-color: white;
                outline: none;
                padding: 2px;
                min-height: 100px;
            }
            QListWidget::item {
                padding: 6px;
                border-bottom: 1px solid #f0f0f0;
                margin: 2px 0;
                border-radius: 4px;
            }
        """)
        layout.addWidget(self.subConditionsList)
        
        # 子条件管理按钮
        buttonLayout = QHBoxLayout()
        
        self.addSubConditionBtn = PushButton("添加子条件")
        self.addSubConditionBtn.setIcon(FIF.ADD)
        self.addSubConditionBtn.clicked.connect(self.add_sub_condition)
        
        self.removeSubConditionBtn = PushButton("移除子条件")
        self.removeSubConditionBtn.setIcon(FIF.DELETE)
        self.removeSubConditionBtn.clicked.connect(self.remove_sub_condition)
        
        buttonLayout.addWidget(self.addSubConditionBtn)
        buttonLayout.addWidget(self.removeSubConditionBtn)
        buttonLayout.addStretch(1)
        
        layout.addLayout(buttonLayout)
        
        # 添加到参数布局
        self.paramsLayout.addWidget(self.comboParamsWidget)
        self.comboParamsWidget.setVisible(False)
    
    def on_condition_type_changed(self, index):
        """条件类型更改时切换参数UI
        
        参数:
            index (int): 组合框的当前索引
        """
        # 隐藏所有参数组件
        self.colorParamsWidget.setVisible(False)
        self.timeParamsWidget.setVisible(False)
        self.comboParamsWidget.setVisible(False)
        
        # 根据选择显示对应的参数组件
        if index == 0:  # 颜色条件
            self.colorParamsWidget.setVisible(True)
        elif index == 1:  # 时间条件
            self.timeParamsWidget.setVisible(True)
        elif index == 2:  # 组合条件
            self.comboParamsWidget.setVisible(True)
    
    def select_region(self):
        """选择屏幕区域"""
        try:
            # 使用选择框模块的show_selection_box函数
            from 选择框 import show_selection_box
            
            def on_region_selected(rect):
                """区域选择完成后的回调函数"""
                try:
                    # 获取选定区域的截图
                    selection_box = QApplication.topLevelWidgets()[-1]
                    if not hasattr(selection_box, 'getSelectedImage'):
                        raise RuntimeError("无法获取选择框实例")
                        
                    img = selection_box.getSelectedImage()
                    if img is None:
                        raise RuntimeError("无法获取选定区域的图像")
                    
                    # 确保图像有效
                    if img.size == 0 or img.shape[0] == 0 or img.shape[1] == 0:
                        raise ValueError("获取的图像数据无效")
                    
                    # 存储区域数据
                    self.region_data = {
                        "x1": rect.x(),
                        "y1": rect.y(),
                        "x2": rect.x() + rect.width(),
                        "y2": rect.y() + rect.height()
                    }
                    
                    # 更新UI显示
                    self.regionInfoLabel.setText(
                        f"x:{rect.x()}, y:{rect.y()}, "
                        f"宽:{rect.width()}, 高:{rect.height()}"
                    )
                    
                    # 显示成功消息
                    InfoBar.success(
                        title="区域已选择",
                        content=f"已设置检测区域: x:{rect.x()}, y:{rect.y()}, 宽:{rect.width()}, 高:{rect.height()}",
                        orient=Qt.Horizontal,
                        isClosable=True,
                        position=InfoBarPosition.TOP,
                        duration=2000,
                        parent=self
                    )
                except ImportError as e:
                    print(f"区域选择失败: 缺少必要的库 - {str(e)}")
                    InfoBar.error(
                        title="区域选择失败",
                        content="缺少必要的图像处理库，请确保已安装numpy和opencv-python",
                        orient=Qt.Horizontal,
                        isClosable=True,
                        position=InfoBarPosition.TOP,
                        duration=3000,
                        parent=self
                    )
                except Exception as e:
                    print(f"区域选择处理失败: {type(e).__name__} - {str(e)}")
                    traceback.print_exc()
                    
                    # 确定合适的错误消息
                    error_message = "区域选择处理失败，请重试"
                    if "numpy" in str(e).lower() or "cv2" in str(e).lower():
                        error_message = "图像处理失败，请确保系统已安装所需依赖"
                    elif "empty" in str(e).lower() or "size" in str(e).lower():
                        error_message = "选择的区域太小，无法获取有效区域"
                    
                    InfoBar.error(
                        title="区域选择失败",
                        content=error_message,
                        orient=Qt.Horizontal,
                        isClosable=True,
                        position=InfoBarPosition.TOP,
                        duration=3000,
                        parent=self
                    )
            
            # 显示选择框
            InfoBar.info(
                title="区域选择",
                content="请用鼠标框选要检测的屏幕区域，按Enter确认，Esc取消",
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=3000,
                parent=self
            )
            
            # 隐藏当前对话框，避免干扰选择
            self.hide()
            
            # 等待消息显示完成
            QApplication.processEvents()
            time.sleep(0.5)
            
            # 显示选择框并获取结果
            result = show_selection_box(on_region_selected)
            
            # 重新显示对话框
            self.show()
            
            if not result:
                InfoBar.warning(
                    title="选择取消",
                    content="区域选择已取消",
                    orient=Qt.Horizontal,
                    isClosable=True,
                    position=InfoBarPosition.TOP,
                    duration=2000,
                    parent=self
                )
                
        except Exception as e:
            print(f"区域选择时出错: {type(e).__name__} - {str(e)}")
            traceback.print_exc()
            
            # 重新显示对话框
            self.show()
            
            # 显示错误信息
            error_message = "区域选择失败，请重试"
            if "CROP" in str(e):
                error_message = "区域选择工具初始化失败，请检查系统设置"
            elif "QScreen" in str(e):
                error_message = "屏幕捕获失败，请检查系统权限"
            
            InfoBar.error(
                title="区域选择失败",
                content=error_message,
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=3000,
                parent=self
            )
    
    def select_color(self):
        """选择颜色"""
        try:
            # 使用选择框模块的show_selection_box函数
            from 选择框 import show_selection_box
            
            def on_color_selected(rect):
                """颜色选择完成后的回调函数"""
                try:
                    # 获取选定区域的截图
                    selection_box = QApplication.topLevelWidgets()[-1]
                    if not hasattr(selection_box, 'getSelectedImage'):
                        raise RuntimeError("无法获取选择框实例")
                        
                    img = selection_box.getSelectedImage()
                    if img is None:
                        raise RuntimeError("无法获取选定区域的图像")
                    
                    # 计算平均颜色
                    import numpy as np
                    import cv2
                    
                    # 确保图像有效
                    if img.size == 0:
                        raise ValueError("获取的图像数据为空")
                        
                    avg_color = np.mean(img, axis=(0, 1)).astype(int)
                    b, g, r = avg_color
                    
                    # 更新UI显示
                    self.colorPreviewLabel.setStyleSheet(f"background-color: rgb({r}, {g}, {b}); border: 1px solid #cccccc;")
                    self.colorInfoLabel.setText(f"RGB: ({r}, {g}, {b})")
                    
                    # 存储颜色数据 (OpenCV中为BGR顺序，我们存储为BGR)
                    self.color_data = [int(b), int(g), int(r)]
                    
                    # 更新RGB输入框
                    self.rSpinBox.setValue(int(r))
                    self.gSpinBox.setValue(int(g))
                    self.bSpinBox.setValue(int(b))
                    
                    # 显示成功消息
                    InfoBar.success(
                        title="颜色已选择",
                        content=f"已设置目标颜色: RGB({r}, {g}, {b})",
                        orient=Qt.Horizontal,
                        isClosable=True,
                        position=InfoBarPosition.TOP,
                        duration=2000,
                        parent=self
                    )
                except ImportError as e:
                    print(f"颜色选择失败: 缺少必要的库 - {str(e)}")
                    InfoBar.error(
                        title="颜色选择失败",
                        content="缺少必要的图像处理库，请确保已安装numpy和opencv-python",
                        orient=Qt.Horizontal,
                        isClosable=True,
                        position=InfoBarPosition.TOP,
                        duration=3000,
                        parent=self
                    )
                except Exception as e:
                    print(f"颜色选择处理失败: {type(e).__name__} - {str(e)}")
                    traceback.print_exc()
                    
                    # 确定合适的错误消息
                    error_message = "颜色选择处理失败，请重试"
                    if "numpy" in str(e).lower() or "cv2" in str(e).lower():
                        error_message = "图像处理失败，请确保系统已安装所需依赖"
                    elif "empty" in str(e).lower() or "size" in str(e).lower():
                        error_message = "选择的区域太小，无法获取有效颜色"
                    
                    InfoBar.error(
                        title="颜色选择失败",
                        content=error_message,
                        orient=Qt.Horizontal,
                        isClosable=True,
                        position=InfoBarPosition.TOP,
                        duration=3000,
                        parent=self
                    )
            
            # 显示选择框
            InfoBar.info(
                title="颜色选择",
                content="请用鼠标框选屏幕上的颜色区域，按Enter确认，Esc取消",
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=3000,
                parent=self
            )
            
            # 隐藏当前对话框，避免干扰选择
            self.hide()
            
            # 等待消息显示完成
            QApplication.processEvents()
            time.sleep(0.5)
            
            # 显示选择框并获取结果
            result = show_selection_box(on_color_selected)
            
            # 重新显示对话框
            self.show()
            
            if not result:
                InfoBar.warning(
                    title="选择取消",
                    content="颜色选择已取消",
                    orient=Qt.Horizontal,
                    isClosable=True,
                    position=InfoBarPosition.TOP,
                    duration=2000,
                    parent=self
                )
                
        except Exception as e:
            print(f"颜色选择时出错: {type(e).__name__} - {str(e)}")
            traceback.print_exc()
            
            # 重新显示对话框
            self.show()
            
            # 显示错误信息
            error_message = "颜色选择失败，请重试"
            if "CROP" in str(e):
                error_message = "颜色选择工具初始化失败，请检查系统设置"
            elif "QScreen" in str(e):
                error_message = "屏幕捕获失败，请检查系统权限"
            
            InfoBar.error(
                title="颜色选择失败",
                content=error_message,
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=3000,
                parent=self
            )
    
    def add_sub_condition(self):
        """添加子条件到组合条件"""
        try:
            # 获取已添加的子条件ID列表（用于排除）
            exclude_ids = []
            for i in range(self.subConditionsList.count()):
                item = self.subConditionsList.item(i)
                exclude_ids.append(item.data(Qt.UserRole))
                
            # 创建条件选择对话框
            dialog = ConditionSelectionDialog(
                parent=self,
                multi_select=False,  # 一次只能添加一个子条件
                exclude_ids=exclude_ids
            )
            
            # 显示对话框
            if dialog.exec_() == QDialog.Accepted:
                # 获取选中的条件ID
                selected_ids = dialog.get_selected_conditions()
                
                if selected_ids:
                    for condition_id in selected_ids:
                        # 获取条件对象
                        condition = config_manager.get_condition(condition_id)
                        
                        if condition:
                            # 创建列表项
                            item = QListWidgetItem()
                            item.setText(condition.name)
                            item.setData(Qt.UserRole, condition.id)
                            
                            # 检查是否是组合条件
                            if condition.type == "combo":
                                # 不能嵌套自己
                                if self.edit_mode and self.condition and self.condition.id == condition.id:
                                    InfoBar.warning(
                                        title="无效选择",
                                        content="不能将条件添加为自己的子条件",
                                        orient=Qt.Horizontal,
                                        isClosable=True,
                                        position=InfoBarPosition.TOP,
                                        duration=2000,
                                        parent=self
                                    )
                                    continue
                                    
                                # 设置工具提示
                                item.setToolTip("组合条件")
                                
                            # 添加到列表
                            self.subConditionsList.addItem(item)
                            
                            # 显示成功消息
                            InfoBar.success(
                                title="添加成功",
                                content=f"已添加子条件: {condition.name}",
                                orient=Qt.Horizontal,
                                isClosable=True,
                                position=InfoBarPosition.TOP,
                                duration=2000,
                                parent=self
                            )
                
        except Exception as e:
            print(f"添加子条件时出错: {str(e)}")
            traceback.print_exc()
            
            # 显示错误信息
            InfoBar.error(
                title="添加失败",
                content=f"添加子条件时出错: {str(e)}",
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=3000,
                parent=self
            )
    
    def remove_sub_condition(self):
        """移除选中的子条件"""
        try:
            # 获取选中的子条件
            selected_items = self.subConditionsList.selectedItems()
            
            if not selected_items:
                InfoBar.warning(
                    title="未选择子条件",
                    content="请先选择要移除的子条件",
                    orient=Qt.Horizontal,
                    isClosable=True,
                    position=InfoBarPosition.TOP,
                    duration=2000,
                    parent=self
                )
                return
                
            # 移除选中的子条件
            for item in selected_items:
                # 获取子条件名称
                condition_name = item.text()
                
                # 从列表中移除
                row = self.subConditionsList.row(item)
                self.subConditionsList.takeItem(row)
                
                # 显示成功消息
                InfoBar.success(
                    title="移除成功",
                    content=f"已移除子条件: {condition_name}",
                    orient=Qt.Horizontal,
                    isClosable=True,
                    position=InfoBarPosition.TOP,
                    duration=2000,
                    parent=self
                )
                
        except Exception as e:
            print(f"移除子条件时出错: {str(e)}")
            traceback.print_exc()
            
            # 显示错误信息
            InfoBar.error(
                title="移除失败",
                content=f"移除子条件时出错: {str(e)}",
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=3000,
                parent=self
            )

    def fill_condition_data(self):
        """填充当前条件数据到表单中"""
        try:
            if not self.condition:
                return
                
            # 填充基本信息
            self.nameLineEdit.setText(self.condition.name)
            
            # 设置条件类型
            type_index = 0  # 默认为颜色条件
            if self.condition.type == "time":
                type_index = 1
            elif self.condition.type == "combo":
                type_index = 2
                
            self.typeComboBox.setCurrentIndex(type_index)
            
            # 填充描述
            if hasattr(self.condition, "description") and self.condition.description:
                self.descTextEdit.setText(self.condition.description)
                
            # 填充检查间隔
            if hasattr(self.condition, "check_interval"):
                self.intervalSpinBox.setValue(self.condition.check_interval)
                
            # 填充启用状态
            self.enabledCheck.setChecked(getattr(self.condition, "enabled", True))
            
            # 填充特定类型的参数
            params = self.condition.parameters
            
            if self.condition.type == "color":
                # 填充颜色条件参数
                if "color" in params:
                    color = params["color"]
                    # 更新颜色预览
                    self.colorPreviewLabel.setStyleSheet(f"background-color: rgb({color[2]}, {color[1]}, {color[0]});")
                    # 设置RGB值
                    self.rSpinBox.setValue(color[2])  # OpenCV中BGR顺序
                    self.gSpinBox.setValue(color[1])
                    self.bSpinBox.setValue(color[0])
                    
                if "tolerance" in params:
                    self.toleranceSpinBox.setValue(params["tolerance"])
                    
                if "region" in params:
                    region = params["region"]
                    # 更新区域信息标签
                    self.regionInfoLabel.setText(
                        f"x:{region['x1']}, y:{region['y1']}, "
                        f"宽:{region['x2'] - region['x1']}, 高:{region['y2'] - region['y1']}"
                    )
                    # 存储区域数据
                    self.region_data = region
                    
            elif self.condition.type == "time":
                # 填充时间条件参数
                if "interval" in params:
                    self.timeIntervalSpinBox.setValue(params["interval"])
                    
                if "initial_delay" in params:
                    self.initialDelaySpinBox.setValue(params["initial_delay"])
                    
            elif self.condition.type == "combo":
                # 填充组合条件参数
                if "combo_type" in params:
                    if params["combo_type"] == "AND":
                        self.andRadio.setChecked(True)
                    else:
                        self.orRadio.setChecked(True)
                        
                # 填充子条件列表
                self.subConditionsList.clear()
                for sub_ref in self.condition.sub_conditions:
                    # 获取子条件数据
                    sub_condition = config_manager.get_condition(sub_ref.id)
                    if sub_condition:
                        item = QListWidgetItem()
                        item.setText(sub_condition.name)
                        item.setData(Qt.UserRole, sub_condition.id)
                        self.subConditionsList.addItem(item)
                    else:
                        # 如果子条件不存在，显示ID
                        item = QListWidgetItem()
                        item.setText(f"{sub_ref.id} (未找到)")
                        item.setData(Qt.UserRole, sub_ref.id)
                        item.setForeground(QColor("#999999"))
                        self.subConditionsList.addItem(item)
                
        except Exception as e:
            print(f"填充条件数据时出错: {str(e)}")
            traceback.print_exc()
            
            # 显示错误信息
            self.error_label.setText(f"载入条件数据出错: {str(e)}")
            self.error_label.setVisible(True)
            
    def validate(self):
        """验证表单数据并保存"""
        try:
            # 获取表单数据
            name = self.nameLineEdit.text().strip()
            index = self.typeComboBox.currentIndex()
            
            # 根据索引获取条件类型
            condition_type = "color"  # 默认颜色条件
            if index == 1:
                condition_type = "time"
            elif index == 2:
                condition_type = "combo"
            
            # 基本验证
            if not name:
                self.error_label.setText("条件名称不能为空")
                self.error_label.setVisible(True)
                return False
                
            # 如果是新建条件，检查名称是否已存在
            if not self.edit_mode:
                # 检查本地列表
                condition_id = name.lower().replace(" ", "_")
                if config_manager.conditions_db.get_condition(condition_id) is not None:
                    self.error_label.setText(f"条件名称 '{name}' 已存在")
                    self.error_label.setVisible(True)
                    return False
            
            # 根据条件类型执行特定验证
            params = {}
            if condition_type == "color":
                # 验证区域选择
                if not self.region_data:
                    self.error_label.setText("请选择检测区域")
                    self.error_label.setVisible(True)
                    return False
                    
                # 验证颜色选择
                if not hasattr(self, 'color_data') or not self.color_data:
                    self.error_label.setText("请选择目标颜色")
                    self.error_label.setVisible(True)
                    return False
                    
                # 获取容差值
                try:
                    tolerance = int(self.toleranceSpinBox.value())
                except ValueError:
                    self.error_label.setText("容差值必须是整数")
                    self.error_label.setVisible(True)
                    return False
                    
                # 构建参数
                params = {
                    "region": self.region_data,
                    "color": self.color_data,
                    "tolerance": tolerance
                }
            elif condition_type == "time":
                # 获取时间间隔和初始延迟
                try:
                    interval = float(self.timeIntervalSpinBox.value())
                    initial_delay = float(self.initialDelaySpinBox.value())
                except ValueError:
                    self.error_label.setText("时间值必须是数字")
                    self.error_label.setVisible(True)
                    return False
                    
                # 构建参数
                params = {
                    "interval": interval,
                    "initial_delay": initial_delay
                }
            elif condition_type == "combo":
                # 获取组合类型
                combo_type = "AND" if self.andRadio.isChecked() else "OR"
                
                # 获取子条件
                sub_conditions = []
                for i in range(self.subConditionsList.count()):
                    item = self.subConditionsList.item(i)
                    condition_id = item.data(Qt.UserRole)
                    sub_conditions.append({"id": condition_id})
                
                # 验证至少有一个子条件
                if not sub_conditions:
                    self.error_label.setText("请至少添加一个子条件")
                    self.error_label.setVisible(True)
                    return False
                
                # 构建参数
                params = {
                    "combo_type": combo_type
                }
            
            # 构建条件对象
            condition_data = {
                "name": name,
                "type": condition_type,
                "params": params,
                "enabled": True
            }
            
            # 如果是编辑模式，保留原始ID
            if self.edit_mode and self.condition:
                condition_data["id"] = self.condition.id
            else:
                condition_data["id"] = name.lower().replace(" ", "_")
            
            # 创建或更新条件
            try:
                if self.edit_mode:
                    # 更新现有条件
                    config_manager.conditions_db.update_condition(condition_data)
                else:
                    # 添加新条件
                    config_manager.conditions_db.add_condition(condition_data)
                
                # 保存配置
                config_manager.save_system_config()
                
                # 关闭对话框
                self.accept()
                return True
                
            except Exception as e:
                print(f"保存条件时出错: {type(e).__name__}: {str(e)}")
                traceback.print_exc()
                
                # 显示错误信息
                error_message = f"保存条件失败: {str(e)}"
                if "CROP" in str(e):
                    error_message = "保存条件失败: 图像处理错误，请重新选择区域"
                elif "JSON" in str(e) or "serialize" in str(e).lower():
                    error_message = "保存条件失败: 数据格式错误"
                
                self.error_label.setText(error_message)
                self.error_label.setVisible(True)
                return False
                
        except Exception as e:
            print(f"验证条件时出错: {type(e).__name__}: {str(e)}")
            traceback.print_exc()
            
            # 显示错误信息
            error_message = f"验证条件失败: {str(e)}"
            if "CROP" in str(e):
                error_message = "验证条件失败: 图像处理错误，请重新选择区域"
            elif "numpy" in str(e).lower() or "cv2" in str(e).lower():
                error_message = "验证条件失败: 图像处理库错误，请确保系统已安装所需依赖"
            
            self.error_label.setText(error_message)
            self.error_label.setVisible(True)
            return False

    def capture_reference_image(self):
        """捕获参考图像"""
        try:
            # 使用选择框模块的show_selection_box函数
            from 选择框 import show_selection_box
            
            def on_region_selected(rect):
                """区域选择完成后的回调函数"""
                try:
                    # 获取选定区域的截图
                    selection_box = QApplication.topLevelWidgets()[-1]
                    if not hasattr(selection_box, 'getSelectedImage'):
                        raise RuntimeError("无法获取选择框实例")
                        
                    img = selection_box.getSelectedImage()
                    if img is None:
                        raise RuntimeError("无法获取选定区域的图像")
                    
                    # 确保图像有效
                    if img.size == 0 or img.shape[0] == 0 or img.shape[1] == 0:
                        raise ValueError("获取的图像数据无效")
                    
                    # 存储参考图像
                    self.reference_image = img
                    
                    # 更新UI显示
                    h, w = img.shape[:2]
                    self.referenceImageLabel.setText(f"已捕获参考图像 ({w}x{h})")
                    
                    # 显示成功消息
                    InfoBar.success(
                        title="参考图像已捕获",
                        content=f"已设置参考图像: {w}x{h}像素",
                        orient=Qt.Horizontal,
                        isClosable=True,
                        position=InfoBarPosition.TOP,
                        duration=2000,
                        parent=self
                    )
                except ImportError as e:
                    print(f"参考图像捕获失败: 缺少必要的库 - {str(e)}")
                    InfoBar.error(
                        title="参考图像捕获失败",
                        content="缺少必要的图像处理库，请确保已安装numpy和opencv-python",
                        orient=Qt.Horizontal,
                        isClosable=True,
                        position=InfoBarPosition.TOP,
                        duration=3000,
                        parent=self
                    )
                except Exception as e:
                    print(f"参考图像处理失败: {type(e).__name__} - {str(e)}")
                    traceback.print_exc()
                    
                    # 确定合适的错误消息
                    error_message = "参考图像处理失败，请重试"
                    if "numpy" in str(e).lower() or "cv2" in str(e).lower():
                        error_message = "图像处理失败，请确保系统已安装所需依赖"
                    elif "empty" in str(e).lower() or "size" in str(e).lower():
                        error_message = "选择的区域太小，无法获取有效图像"
                    
                    InfoBar.error(
                        title="参考图像捕获失败",
                        content=error_message,
                        orient=Qt.Horizontal,
                        isClosable=True,
                        position=InfoBarPosition.TOP,
                        duration=3000,
                        parent=self
                    )
            
            # 显示选择框
            InfoBar.info(
                title="参考图像捕获",
                content="请用鼠标框选要作为参考的屏幕区域，按Enter确认，Esc取消",
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=3000,
                parent=self
            )
            
            # 隐藏当前对话框，避免干扰选择
            self.hide()
            
            # 等待消息显示完成
            QApplication.processEvents()
            time.sleep(0.5)
            
            # 显示选择框并获取结果
            result = show_selection_box(on_region_selected)
            
            # 重新显示对话框
            self.show()
            
            if not result:
                InfoBar.warning(
                    title="捕获取消",
                    content="参考图像捕获已取消",
                    orient=Qt.Horizontal,
                    isClosable=True,
                    position=InfoBarPosition.TOP,
                    duration=2000,
                    parent=self
                )
                
        except Exception as e:
            print(f"参考图像捕获时出错: {type(e).__name__} - {str(e)}")
            traceback.print_exc()
            
            # 重新显示对话框
            self.show()
            
            # 显示错误信息
            error_message = "参考图像捕获失败，请重试"
            if "CROP" in str(e):
                error_message = "图像捕获工具初始化失败，请检查系统设置"
            elif "QScreen" in str(e):
                error_message = "屏幕捕获失败，请检查系统权限"
            
            InfoBar.error(
                title="参考图像捕获失败",
                content=error_message,
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=3000,
                parent=self
            )

    def update_color_preview(self):
        """更新颜色预览"""
        try:
            # 获取RGB值
            r = self.rSpinBox.value()
            g = self.gSpinBox.value()
            b = self.bSpinBox.value()
            
            # 更新颜色预览
            self.colorPreviewLabel.setStyleSheet(f"background-color: rgb({r}, {g}, {b}); border: 1px solid #cccccc;")
            self.colorInfoLabel.setText(f"RGB: ({r}, {g}, {b})")
            
            # 更新颜色数据 (OpenCV中为BGR顺序)
            self.color_data = [int(b), int(g), int(r)]
        except Exception as e:
            print(f"更新颜色预览时出错: {str(e)}")
            traceback.print_exc()

class ConditionSelectionDialog(MessageBoxBase):
    """条件选择对话框
    
    用于从可用条件列表中选择一个或多个条件。
    """
    
    # 选择完成信号
    conditionsSelected = pyqtSignal(list)
    
    def __init__(self, parent=None, multi_select=True, exclude_ids=None):
        """初始化条件选择对话框
        
        参数:
            parent: 父窗口
            multi_select: 是否允许多选
            exclude_ids: 要排除的条件ID列表，这些条件不会显示在选择列表中
        """
        super().__init__(parent)
        
        # 设置对话框不可拖动
        self.setDraggable(False)
        
        # 设置遮罩颜色为完全透明
        self.setMaskColor(QColor(0, 0, 0, 0))
        
        # 设置更合适的阴影效果
        self.setShadowEffect(60, (0, 6), QColor(0, 0, 0, 80))
        
        # 设置标题
        self._window_title = "选择条件"
        
        # 是否允许多选
        self.multi_select = multi_select
        
        # 要排除的条件ID列表
        self.exclude_ids = exclude_ids or []
        
        # 设置对话框样式
        self.widget.setObjectName("conditionSelectionDialogWidget")
        self.widget.setStyleSheet("""
            #conditionSelectionDialogWidget {
                background-color: #ffffff;
                border-radius: 8px;
            }
        """)
        
        # 设置对话框的初始大小
        self.widget.setMinimumWidth(400)
        self.widget.setMinimumHeight(500)
        
        # 初始化UI
        self.initUI()
        
        # 加载条件列表
        self.load_conditions()
        
    def initUI(self):
        """初始化UI"""
        # 设置整体布局结构
        self.viewLayout.setSpacing(16)
        self.viewLayout.setContentsMargins(24, 24, 24, 24)
        
        # 添加标题标签
        self.titleLabel = TitleLabel(self._window_title)
        self.viewLayout.addWidget(self.titleLabel)
        
        # 添加间隔
        spacer = QSpacerItem(20, 10, QSizePolicy.Minimum, QSizePolicy.Fixed)
        self.viewLayout.addSpacerItem(spacer)
        
        # 搜索框
        searchLayout = QHBoxLayout()
        
        searchLabel = BodyLabel("搜索:")
        self.searchInput = LineEdit()
        self.searchInput.setPlaceholderText("输入关键词搜索条件")
        self.searchInput.setClearButtonEnabled(True)
        self.searchInput.textChanged.connect(self.filter_conditions)
        
        searchLayout.addWidget(searchLabel)
        searchLayout.addWidget(self.searchInput, 1)
        
        self.viewLayout.addLayout(searchLayout)
        
        # 条件列表
        self.conditionsList = QListWidget()
        
        # 设置选择模式
        if self.multi_select:
            self.conditionsList.setSelectionMode(QAbstractItemView.MultiSelection)
        else:
            self.conditionsList.setSelectionMode(QAbstractItemView.SingleSelection)
            
        self.conditionsList.setStyleSheet("""
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
        
        # 双击条件直接确认
        self.conditionsList.itemDoubleClicked.connect(self.on_condition_double_clicked)
        
        self.viewLayout.addWidget(self.conditionsList, 1)  # 1是拉伸因子，列表会占据大部分空间
        
        # 添加提示标签
        hint_text = "双击条件可快速选择" if not self.multi_select else "可以选择多个条件"
        hintLabel = CaptionLabel(hint_text)
        hintLabel.setAlignment(Qt.AlignCenter)
        self.viewLayout.addWidget(hintLabel)
        
        # 创建按钮
        if self.multi_select:
            self.yesButton.setText("确认选择")
        else:
            self.yesButton.setText("选择")
            
        self.cancelButton.setText("取消")
        
        # 连接信号
        self.yesButton.clicked.connect(self.on_confirm)
        
    def load_conditions(self):
        """加载条件列表"""
        try:
            # 清空列表
            self.conditionsList.clear()
            
            # 获取所有条件
            conditions = config_manager.conditions_db.conditions
            
            # 添加条件项，排除指定的ID
            for condition in conditions:
                # 跳过被排除的条件
                if condition.id in self.exclude_ids:
                    continue
                    
                # 创建列表项
                item = QListWidgetItem()
                
                # 设置条件名称
                display_text = condition.name
                if condition.description:
                    # 如果有描述，显示一部分
                    short_desc = condition.description[:20] + "..." if len(condition.description) > 20 else condition.description
                    display_text += f" - {short_desc}"
                    
                # 设置项目文本
                item.setText(display_text)
                
                # 存储条件数据
                item.setData(Qt.UserRole, condition.id)
                
                # 设置工具提示，显示更多信息
                tooltip = f"ID: {condition.id}\n类型: {condition.type}\n"
                if condition.description:
                    tooltip += f"描述: {condition.description}\n"
                    
                if condition.type == "color":
                    # 为颜色条件添加额外信息
                    color = condition.parameters.get("color", [0, 0, 0])
                    tooltip += f"颜色: RGB({color[2]}, {color[1]}, {color[0]})"
                    
                item.setToolTip(tooltip)
                
                # 添加到列表
                self.conditionsList.addItem(item)
                
        except Exception as e:
            print(f"加载条件列表时出错: {str(e)}")
            traceback.print_exc()
            
    def filter_conditions(self, text):
        """根据关键词过滤条件列表
        
        参数:
            text: 搜索关键词
        """
        # 如果搜索框为空，显示所有条件
        if not text:
            for i in range(self.conditionsList.count()):
                self.conditionsList.item(i).setHidden(False)
            return
            
        # 否则，根据关键词过滤
        search_terms = text.lower().split()
        
        for i in range(self.conditionsList.count()):
            item = self.conditionsList.item(i)
            item_text = item.text().lower()
            
            # 如果所有搜索词都匹配，则显示该项
            should_show = all(term in item_text for term in search_terms)
            item.setHidden(not should_show)
            
    def on_condition_double_clicked(self, item):
        """条件项被双击时的处理
        
        如果是单选模式，直接选择该条件并关闭对话框
        
        参数:
            item: 被双击的列表项
        """
        if not self.multi_select:
            # 单选模式，选择该条件并接受对话框
            self.conditionsList.clearSelection()
            item.setSelected(True)
            self.accept()
            
    def on_confirm(self):
        """确认按钮点击处理"""
        # 获取所有选中的条件
        selected_items = self.conditionsList.selectedItems()
        
        # 如果没有选中任何条件，显示警告
        if not selected_items:
            InfoBar.warning(
                title="未选择条件",
                content="请至少选择一个条件",
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=2000,
                parent=self
            )
            return
            
        # 收集选中的条件ID
        selected_conditions = []
        for item in selected_items:
            condition_id = item.data(Qt.UserRole)
            selected_conditions.append(condition_id)
            
        # 发送信号
        self.conditionsSelected.emit(selected_conditions)
        
        # 接受对话框
        self.accept()
        
    def get_selected_conditions(self):
        """获取选中的条件ID列表
        
        返回:
            list: 选中的条件ID列表
        """
        selected_items = self.conditionsList.selectedItems()
        return [item.data(Qt.UserRole) for item in selected_items]

    def select_color(self):
        """选择颜色"""
        try:
            # 使用选择框模块的show_selection_box函数
            from 选择框 import show_selection_box
            
            def on_color_selected(rect):
                """颜色选择完成后的回调函数"""
                try:
                    # 获取选定区域的截图
                    selection_box = QApplication.topLevelWidgets()[-1]
                    if not hasattr(selection_box, 'getSelectedImage'):
                        raise RuntimeError("无法获取选择框实例")
                        
                    img = selection_box.getSelectedImage()
                    if img is None:
                        raise RuntimeError("无法获取选定区域的图像")
                    
                    # 计算平均颜色
                    import numpy as np
                    import cv2
                    
                    # 确保图像有效
                    if img.size == 0:
                        raise ValueError("获取的图像数据为空")
                        
                    avg_color = np.mean(img, axis=(0, 1)).astype(int)
                    b, g, r = avg_color
                    
                    # 更新UI显示
                    self.colorPreviewLabel.setStyleSheet(f"background-color: rgb({r}, {g}, {b}); border: 1px solid #cccccc;")
                    self.colorInfoLabel.setText(f"RGB: ({r}, {g}, {b})")
                    
                    # 存储颜色数据 (OpenCV中为BGR顺序，我们存储为BGR)
                    self.color_data = [int(b), int(g), int(r)]
                    
                    # 更新RGB输入框
                    self.rSpinBox.setValue(int(r))
                    self.gSpinBox.setValue(int(g))
                    self.bSpinBox.setValue(int(b))
                    
                    # 显示成功消息
                    InfoBar.success(
                        title="颜色已选择",
                        content=f"已设置目标颜色: RGB({r}, {g}, {b})",
                        orient=Qt.Horizontal,
                        isClosable=True,
                        position=InfoBarPosition.TOP,
                        duration=2000,
                        parent=self
                    )
                except ImportError as e:
                    print(f"颜色选择失败: 缺少必要的库 - {str(e)}")
                    InfoBar.error(
                        title="颜色选择失败",
                        content="缺少必要的图像处理库，请确保已安装numpy和opencv-python",
                        orient=Qt.Horizontal,
                        isClosable=True,
                        position=InfoBarPosition.TOP,
                        duration=3000,
                        parent=self
                    )
                except Exception as e:
                    print(f"颜色选择处理失败: {type(e).__name__} - {str(e)}")
                    traceback.print_exc()
                    
                    # 确定合适的错误消息
                    error_message = "颜色选择处理失败，请重试"
                    if "numpy" in str(e).lower() or "cv2" in str(e).lower():
                        error_message = "图像处理失败，请确保系统已安装所需依赖"
                    elif "empty" in str(e).lower() or "size" in str(e).lower():
                        error_message = "选择的区域太小，无法获取有效颜色"
                    
                    InfoBar.error(
                        title="颜色选择失败",
                        content=error_message,
                        orient=Qt.Horizontal,
                        isClosable=True,
                        position=InfoBarPosition.TOP,
                        duration=3000,
                        parent=self
                    )
            
            # 显示选择框
            InfoBar.info(
                title="颜色选择",
                content="请用鼠标框选屏幕上的颜色区域，按Enter确认，Esc取消",
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=3000,
                parent=self
            )
            
            # 隐藏当前对话框，避免干扰选择
            self.hide()
            
            # 等待消息显示完成
            QApplication.processEvents()
            time.sleep(0.5)
            
            # 显示选择框并获取结果
            result = show_selection_box(on_color_selected)
            
            # 重新显示对话框
            self.show()
            
            if not result:
                InfoBar.warning(
                    title="选择取消",
                    content="颜色选择已取消",
                    orient=Qt.Horizontal,
                    isClosable=True,
                    position=InfoBarPosition.TOP,
                    duration=2000,
                    parent=self
                )
                
        except Exception as e:
            print(f"颜色选择时出错: {type(e).__name__} - {str(e)}")
            traceback.print_exc()
            
            # 重新显示对话框
            self.show()
            
            # 显示错误信息
            error_message = "颜色选择失败，请重试"
            if "CROP" in str(e):
                error_message = "颜色选择工具初始化失败，请检查系统设置"
            elif "QScreen" in str(e):
                error_message = "屏幕捕获失败，请检查系统权限"
            
            InfoBar.error(
                title="颜色选择失败",
                content=error_message,
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=3000,
                parent=self
            ) 