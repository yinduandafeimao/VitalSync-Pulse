import os
import sys
import json
import cv2
import numpy as np
import time
import importlib.util
from PySide6.QtWidgets import (
    QApplication, QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
    QPushButton, QMessageBox, QProgressBar, QFrame, QInputDialog,
    QListWidget, QListWidgetItem, QAbstractItemView
)
from PySide6.QtCore import Qt, Signal, QObject, QRect
from 选择框 import TransparentSelectionBox
from teammate_recognition import TeammateRecognition

# 动态导入带空格的模块
module_name = "team_members(choice box)"
module_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "team_members(choice box).py")
spec = importlib.util.spec_from_file_location(module_name, module_path)
team_members_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(team_members_module)

# 从模块中获取需要的类
TeamMember = team_members_module.TeamMember

class CalibrationSignals(QObject):
    """校准信号类，用于在校准过程中发送状态信号"""
    status_signal = Signal(str)  # 状态信号
    progress_signal = Signal(int)  # 进度信号
    complete_signal = Signal(list)  # 完成信号，传递校准的血条区域

class HealthBarCalibration:
    """血条位置校准类
    
    负责管理血条位置的校准、存储和读取。
    首次运行时会自动进入校准模式，让用户框选血条区域。
    """
    
    def __init__(self):
        """初始化校准工具"""
        self.calibration_file = "health_bars_calibration.json"
        self.calibration_sets = {}  # 存储多组校准数据
        self.current_set_name = ""  # 当前使用的校准组名称
        self.health_bars = []  # 当前选择的血条区域列表
        self.recognition = TeammateRecognition()  # 队友识别工具
        self.signals = CalibrationSignals()
        self.is_first_run = not os.path.exists(self.calibration_file)
        
        # 加载校准数据
        self.load_all_calibration_sets()
    
    def load_all_calibration_sets(self):
        """加载所有校准数据集"""
        if not os.path.exists(self.calibration_file):
            self.calibration_sets = {}
            return False
            
        try:
            with open(self.calibration_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if 'calibration_sets' in data and isinstance(data['calibration_sets'], dict):
                    self.calibration_sets = data['calibration_sets']
                    
                    # 加载最后使用的校准集
                    if 'last_used' in data and data['last_used'] in self.calibration_sets:
                        self.current_set_name = data['last_used']
                        self.health_bars = self.calibration_sets[self.current_set_name]['health_bars']
                    
                    return len(self.calibration_sets) > 0
        except Exception as e:
            print(f"加载血条校准数据失败: {str(e)}")
        
        return False
    
    def load_calibration(self, set_name=None):
        """加载指定校准数据集
        
        参数:
            set_name (str): 校准集名称，如果为None则使用当前校准集
            
        返回:
            bool: 是否成功加载校准数据
        """
        if not self.calibration_sets:
            return False
            
        if set_name is None:
            if not self.current_set_name:
                # 如果未指定且当前无选择，则使用第一个校准集
                if self.calibration_sets:
                    self.current_set_name = list(self.calibration_sets.keys())[0]
                else:
                    return False
        else:
            self.current_set_name = set_name
        
        if self.current_set_name in self.calibration_sets:
            self.health_bars = self.calibration_sets[self.current_set_name]['health_bars']
            return len(self.health_bars) > 0
        
        return False
    
    def save_calibration(self):
        """保存当前校准数据集
        
        将当前的血条位置信息保存到校准文件中
        
        返回:
            bool: 是否成功保存校准数据
        """
        if not self.current_set_name:
            return False
            
        try:
            # 更新或创建当前校准集
            self.calibration_sets[self.current_set_name] = {
                'count': len(self.health_bars),
                'calibration_time': time.strftime('%Y-%m-%d %H:%M:%S'),
                'health_bars': self.health_bars
            }
            
            data = {
                'calibration_sets': self.calibration_sets,
                'last_used': self.current_set_name
            }
            
            with open(self.calibration_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=4)
            
            return True
        except Exception as e:
            print(f"保存血条校准数据失败: {str(e)}")
            return False
    
    def start_calibration(self, num_health_bars=5):
        """开始血条校准
        
        参数:
            num_health_bars (int): 需要校准的血条数量，默认为5
            
        返回:
            bool: 是否成功完成校准
        """
        # 创建新的校准集名称
        self.current_set_name = f"{num_health_bars}条血条_{time.strftime('%m%d%H%M')}"
        self.health_bars = []  # 清空现有校准数据
        
        self.signals.status_signal.emit("开始血条位置校准...")
        
        # 显示开始提示
        QMessageBox.information(None, "校准指导", 
                               f"即将开始校准 {num_health_bars} 个血条位置。\n\n"
                               "请依次框选每个队友的血条区域，\n"
                               "框选完成后按Enter键确认。\n\n"
                               "第一个血条开始...")
        
        for i in range(num_health_bars):
            self.signals.status_signal.emit(f"请框选第 {i+1}/{num_health_bars} 个血条区域...")
            self.signals.progress_signal.emit(int(i * 100 / num_health_bars))
            
            # 如果不是第一个，显示下一个的提示
            if i > 0:
                QMessageBox.information(None, "继续校准", 
                                      f"已完成 {i}/{num_health_bars} 个血条。\n\n"
                                      f"请继续框选第 {i+1} 个血条区域。")
            
            rect = self._select_health_bar_area()
            if rect is None:
                self.signals.status_signal.emit("校准被用户取消")
                return False
                
            self.health_bars.append({
                'x1': rect.x(),
                'y1': rect.y(),
                'x2': rect.x() + rect.width(),
                'y2': rect.y() + rect.height(),
                'recognition_done': False
            })
        
        # 完成消息
        QMessageBox.information(None, "校准完成", 
                               f"已完成所有 {num_health_bars} 个血条的校准！")
        
        success = self.save_calibration()
        if success:
            self.signals.status_signal.emit(f"血条校准完成并保存为 '{self.current_set_name}'")
            self.signals.progress_signal.emit(100)
            self.signals.complete_signal.emit(self.health_bars)
        else:
            self.signals.status_signal.emit("血条校准完成但保存失败")
        
        return success
    
    def get_calibration_set_names(self):
        """获取所有校准集名称
        
        返回:
            list: 校准集名称列表
        """
        return list(self.calibration_sets.keys())
    
    def get_calibration_set_info(self, set_name):
        """获取指定校准集的信息
        
        参数:
            set_name (str): 校准集名称
            
        返回:
            dict: 校准集信息，包含count和calibration_time
        """
        if set_name in self.calibration_sets:
            return self.calibration_sets[set_name]
        return None
    
    def delete_calibration_set(self, set_name):
        """删除指定的校准集
        
        参数:
            set_name (str): 要删除的校准集名称
            
        返回:
            bool: 是否成功删除
        """
        if set_name in self.calibration_sets:
            try:
                # 删除校准集
                del self.calibration_sets[set_name]
                
                # 如果删除的是当前使用的校准集，则重置当前选择
                if self.current_set_name == set_name:
                    if self.calibration_sets:
                        # 如果还有其他校准集，选择第一个
                        self.current_set_name = list(self.calibration_sets.keys())[0]
                        self.health_bars = self.calibration_sets[self.current_set_name]['health_bars']
                    else:
                        # 如果没有校准集了，则清空当前选择
                        self.current_set_name = ""
                        self.health_bars = []
                
                # 保存更新后的校准集数据
                data = {
                    'calibration_sets': self.calibration_sets,
                    'last_used': self.current_set_name
                }
                
                with open(self.calibration_file, 'w', encoding='utf-8') as f:
                    json.dump(data, f, ensure_ascii=False, indent=4)
                
                return True
            except Exception as e:
                print(f"删除校准集失败: {str(e)}")
                return False
        else:
            return False
    
    def _select_health_bar_area(self):
        """选择血条区域
        
        显示一个透明选择框，让用户框选血条区域
        
        返回:
            QRect: 用户选择的区域，如果用户取消则返回None
        """
        selected_rect = [None]  # 使用列表存储结果，便于在回调中修改
        
        def on_selection_complete(rect):
            selected_rect[0] = rect
            print(f"选择完成: {rect}")
        
        try:
            # 使用单独的QApplication实例创建选择框
            selection_box = TransparentSelectionBox(on_selection_complete)
            selection_box.set_instruction_text("请框选血条区域，完成后按Enter键确认")
            
            # 显示为模态对话框
            result = selection_box.exec()
            
            print(f"对话框结果: {result}, 选择区域: {selected_rect[0]}")
            
            if result == QDialog.Accepted and selected_rect[0] is not None:
                return selected_rect[0]
            else:
                return None
        except Exception as e:
            print(f"选择区域时出错: {str(e)}")
            return None
    
    def recognize_teammates(self):
        """识别血条区域对应的队友
        
        对每个已校准的血条区域进行队友识别，并保存识别结果
        
        返回:
            list: 识别到的队友信息列表
        """
        if not self.health_bars:
            self.signals.status_signal.emit("请先选择校准集")
            return []
        
        teammates = []
        profession_icons = self.recognition.load_profession_icons()
        
        for i, health_bar in enumerate(self.health_bars):
            self.signals.status_signal.emit(f"正在识别第 {i+1}/{len(self.health_bars)} 个血条的队友...")
            self.signals.progress_signal.emit(int(i * 100 / len(self.health_bars)))
            
            try:
                # 截取血条区域的图像
                x1, y1, x2, y2 = health_bar['x1'], health_bar['y1'], health_bar['x2'], health_bar['y2']
                screenshot = self._capture_screen_area(x1, y1, x2, y2)
                
                if screenshot is None:
                    continue
                
                # 识别队友职业
                profession = self.recognition.match_profession_icon(screenshot, profession_icons)
                
                # 识别队友名称
                name = self.recognition.extract_name(screenshot)
                if name == '未识别':
                    name = f"队友{i+1}"
                
                # 更新血条信息
                health_bar['recognition_done'] = True
                health_bar['name'] = name
                health_bar['profession'] = profession or '未知'
                
                # 创建队友对象
                teammate = TeamMember(name, profession or '未知')
                teammate.x1 = x1
                teammate.y1 = y1
                teammate.x2 = x2
                teammate.y2 = y2
                
                # 设置默认的血条颜色范围
                teammate.hp_color_lower = np.array([43, 71, 121])
                teammate.hp_color_upper = np.array([63, 171, 221])
                
                # 保存队友配置
                teammate.save_config()
                
                teammates.append({
                    'name': name,
                    'profession': profession or '未知',
                    'health_bar': {'x1': x1, 'y1': y1, 'x2': x2, 'y2': y2}
                })
                
                self.signals.status_signal.emit(f"识别到队友: {name} ({profession or '未知'})")
                
            except Exception as e:
                self.signals.status_signal.emit(f"识别第 {i+1} 个血条的队友时出错: {str(e)}")
        
        # 更新当前校准集中的识别状态
        if self.current_set_name:
            self.calibration_sets[self.current_set_name]['health_bars'] = self.health_bars
            self.save_calibration()
        
        self.signals.status_signal.emit(f"队友识别完成，共识别 {len(teammates)}/{len(self.health_bars)} 个队友")
        self.signals.progress_signal.emit(100)
        
        return teammates
    
    def _capture_screen_area(self, x1, y1, x2, y2):
        """截取屏幕区域
        
        参数:
            x1, y1, x2, y2: 截取区域的坐标
            
        返回:
            np.ndarray: 截取的图像，失败则返回None
        """
        try:
            import pyautogui
            screenshot = pyautogui.screenshot(region=(x1, y1, x2-x1, y2-y1))
            return cv2.cvtColor(np.array(screenshot), cv2.COLOR_RGB2BGR)
        except Exception as e:
            self.signals.status_signal.emit(f"截取屏幕区域失败: {str(e)}")
            return None
    
    def reset_calibration(self):
        """重置所有校准数据
        
        清除所有已保存的校准数据，并重新开始校准流程
        
        返回:
            bool: 是否成功重置和重新校准
        """
        self.calibration_sets = {}
        self.current_set_name = ""
        self.health_bars = []
        
        # 删除校准文件
        if os.path.exists(self.calibration_file):
            try:
                os.remove(self.calibration_file)
            except Exception as e:
                self.signals.status_signal.emit(f"删除校准文件失败: {str(e)}")
                return False
        
        # 重新开始校准
        num_bars = self.show_bar_count_selection_dialog()
        if num_bars > 0:
            return self.start_calibration(num_bars)
        return False
    
    def show_bar_count_selection_dialog(self):
        """显示血条数量选择对话框
        
        返回:
            int: 用户选择的血条数量，如果用户取消则返回0
        """
        dialog = QDialog(self)
        dialog.setWindowTitle("选择血条数量")
        layout = QVBoxLayout(dialog)
        
        # 添加说明文本
        label = QLabel("请选择要校准的血条数量：", dialog)
        layout.addWidget(label)
        
        # 添加按钮组
        button_layout = QHBoxLayout()
        
        btn_5 = QPushButton("5条血条", dialog)
        btn_10 = QPushButton("10条血条", dialog)
        btn_20 = QPushButton("20条血条", dialog)
        btn_custom = QPushButton("自定义...", dialog)
        
        button_layout.addWidget(btn_5)
        button_layout.addWidget(btn_10)
        button_layout.addWidget(btn_20)
        button_layout.addWidget(btn_custom)
        
        layout.addLayout(button_layout)
        
        # 用于存储选择结果
        result = [5]  # 默认为5条
        
        # 连接按钮信号
        def on_btn_5_clicked():
            result[0] = 5
            dialog.accept()
            
        def on_btn_10_clicked():
            result[0] = 10
            dialog.accept()
            
        def on_btn_20_clicked():
            result[0] = 20
            dialog.accept()
            
        def on_btn_custom_clicked():
            # 显示自定义数量输入对话框
            custom_num, ok = QInputDialog.getInt(
                dialog, 
                "自定义血条数量", 
                "请输入要校准的血条数量：",
                5, 1, 50, 1
            )
            if ok:
                result[0] = custom_num
                dialog.accept()
        
        btn_5.clicked.connect(on_btn_5_clicked)
        btn_10.clicked.connect(on_btn_10_clicked)
        btn_20.clicked.connect(on_btn_20_clicked)
        btn_custom.clicked.connect(on_btn_custom_clicked)
        
        # 添加取消按钮
        cancel_layout = QHBoxLayout()
        cancel_btn = QPushButton("取消", dialog)
        cancel_btn.clicked.connect(dialog.reject)
        cancel_layout.addStretch()
        cancel_layout.addWidget(cancel_btn)
        layout.addLayout(cancel_layout)
        
        # 设置对话框样式
        dialog.setStyleSheet("""
            QDialog {
                background-color: #f5f5f5;
            }
            QLabel {
                font-size: 14px;
                margin-bottom: 10px;
            }
            QPushButton {
                min-width: 100px;
                min-height: 30px;
                padding: 5px;
                font-size: 13px;
            }
        """)
        
        # 显示对话框并等待用户选择
        if dialog.exec() == QDialog.Accepted:
            return result[0]
        else:
            return 0

    def reset_all_calibration(self):
        """重置所有校准数据
        
        清除所有校准集并重新开始校准流程
        
        返回:
            bool: 是否成功重置
        """
        self.calibration_sets = {}
        self.current_set_name = ""
        self.health_bars = []
        
        # 删除校准文件
        if os.path.exists(self.calibration_file):
            try:
                os.remove(self.calibration_file)
            except Exception as e:
                self.signals.status_signal.emit(f"删除校准文件失败: {str(e)}")
                return False
        
        self.signals.status_signal.emit("已重置所有校准数据")
        return True

    def clear_teammate_recognition(self):
        """清除所有队友的识别结果
        
        保留血条位置数据，但清除识别状态
        
        返回:
            bool: 是否成功清除
        """
        if not self.current_set_name or not self.health_bars:
            return False
        
        try:
            # 清除识别标记
            for health_bar in self.health_bars:
                health_bar['recognition_done'] = False
                # 如果还有其他识别相关字段，也一并清除
                if 'teammate_info' in health_bar:
                    del health_bar['teammate_info']
            
            # 更新校准集
            self.calibration_sets[self.current_set_name]['health_bars'] = self.health_bars
            
            # 保存更新
            data = {
                'calibration_sets': self.calibration_sets,
                'last_used': self.current_set_name
            }
            
            with open(self.calibration_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=4)
            
            self.signals.status_signal.emit("已清除所有队友识别结果")
            return True
        except Exception as e:
            self.signals.status_signal.emit(f"清除队友识别结果失败: {str(e)}")
            return False


class CalibrationDialog(QDialog):
    """血条校准对话框
    
    提供用户界面，引导用户完成血条校准流程
    """
    
    def __init__(self, parent=None):
        """初始化校准对话框"""
        super().__init__(parent)
        self.calibration = HealthBarCalibration()
        self.initUI()
        
        # 连接信号
        self.calibration.signals.status_signal.connect(self.update_status)
        self.calibration.signals.progress_signal.connect(self.progress_bar.setValue)
        self.calibration.signals.complete_signal.connect(self.on_calibration_complete)
        
        # 加载校准集列表
        self.load_calibration_sets()
        
        # 检查是否首次运行
        if self.calibration.is_first_run:
            self.show_first_run_dialog()
    
    def initUI(self):
        """初始化用户界面"""
        self.setWindowTitle("血条位置校准")
        self.setMinimumWidth(600)
        
        main_layout = QHBoxLayout(self)
        
        # 左侧面板 - 校准集列表
        left_panel = QFrame()
        left_panel.setFrameStyle(QFrame.StyledPanel)
        left_panel.setMaximumWidth(200)
        left_layout = QVBoxLayout(left_panel)
        
        # 校准集列表
        list_label = QLabel("已保存的校准集:")
        left_layout.addWidget(list_label)
        
        self.calibration_list = QListWidget()
        self.calibration_list.setSelectionMode(QAbstractItemView.SingleSelection)
        self.calibration_list.itemClicked.connect(self.on_calibration_set_selected)
        left_layout.addWidget(self.calibration_list)
        
        # 校准集管理按钮
        list_buttons = QHBoxLayout()
        
        self.delete_btn = QPushButton("删除")
        self.delete_btn.clicked.connect(self.delete_calibration_set)
        self.delete_btn.setEnabled(False)
        
        self.load_btn = QPushButton("加载")
        self.load_btn.clicked.connect(self.load_selected_calibration)
        self.load_btn.setEnabled(False)
        
        list_buttons.addWidget(self.load_btn)
        list_buttons.addWidget(self.delete_btn)
        
        left_layout.addLayout(list_buttons)
        
        # 右侧面板 - 校准操作
        right_panel = QFrame()
        right_panel.setFrameStyle(QFrame.StyledPanel)
        right_layout = QVBoxLayout(right_panel)
        
        # 标题
        title_label = QLabel("血条位置校准工具")
        title_label.setStyleSheet("font-size: 16pt; font-weight: bold;")
        title_label.setAlignment(Qt.AlignCenter)
        right_layout.addWidget(title_label)
        
        # 当前校准集
        self.current_set_label = QLabel("当前未选择校准集")
        self.current_set_label.setStyleSheet("font-weight: bold; color: blue;")
        right_layout.addWidget(self.current_set_label)
        
        # 说明文本
        description = QLabel(
            "此工具用于校准队友血条位置，以便自动监控血量。\n"
            "您可以创建多组校准数据，适应不同的游戏场景。"
        )
        description.setWordWrap(True)
        right_layout.addWidget(description)
        
        # 进度条
        self.progress_bar = QProgressBar()
        right_layout.addWidget(self.progress_bar)
        
        # 状态标签
        self.status_label = QLabel("准备就绪")
        self.status_label.setStyleSheet("color: blue;")
        right_layout.addWidget(self.status_label)
        
        # 按钮区域
        buttons_layout = QHBoxLayout()
        
        # 开始校准按钮
        self.calibrate_btn = QPushButton("新建校准")
        self.calibrate_btn.clicked.connect(self.show_calibration_options)
        buttons_layout.addWidget(self.calibrate_btn)
        
        # 识别队友按钮
        self.recognize_btn = QPushButton("识别队友")
        self.recognize_btn.clicked.connect(self.recognize_teammates)
        self.recognize_btn.setEnabled(False)
        buttons_layout.addWidget(self.recognize_btn)
        
        # 重置按钮
        reset_btn = QPushButton("全部重置")
        reset_btn.clicked.connect(self.reset_calibration)
        buttons_layout.addWidget(reset_btn)
        
        # 清除队友识别按钮
        self.clear_recognition_btn = QPushButton("清除队友识别")
        self.clear_recognition_btn.setToolTip("清除所有已识别的队友信息，保留校准位置")
        self.clear_recognition_btn.clicked.connect(self.clear_teammate_recognition)
        buttons_layout.addWidget(self.clear_recognition_btn)
        
        right_layout.addLayout(buttons_layout)
        
        # 结果显示区
        result_frame = QFrame()
        result_frame.setFrameStyle(QFrame.StyledPanel)
        result_layout = QVBoxLayout(result_frame)
        
        result_title = QLabel("校准结果")
        result_title.setStyleSheet("font-weight: bold;")
        result_layout.addWidget(result_title)
        
        self.result_label = QLabel("请开始校准或选择已保存的校准集...")
        self.result_label.setWordWrap(True)
        self.result_label.setMinimumHeight(100)
        result_layout.addWidget(self.result_label)
        
        right_layout.addWidget(result_frame)
        
        # 添加左右面板到主布局
        main_layout.addWidget(left_panel)
        main_layout.addWidget(right_panel, 1)  # 右侧面板占更多空间
        
        # 设置窗口大小
        self.resize(800, 500)
    
    def load_calibration_sets(self):
        """加载校准集列表"""
        self.calibration_list.clear()
        
        set_names = self.calibration.get_calibration_set_names()
        for name in set_names:
            info = self.calibration.get_calibration_set_info(name)
            item_text = f"{name} ({info['count']}条)"
            item = QListWidgetItem(item_text)
            item.setData(Qt.UserRole, name)  # 存储实际的校准集名称
            self.calibration_list.addItem(item)
        
        # 如果有校准集，默认选中第一个
        if self.calibration_list.count() > 0:
            self.calibration_list.setCurrentRow(0)
            self.on_calibration_set_selected(self.calibration_list.item(0))
    
    def on_calibration_set_selected(self, item):
        """校准集被选中时的处理"""
        if item:
            set_name = item.data(Qt.UserRole)
            info = self.calibration.get_calibration_set_info(set_name)
            
            if info:
                self.result_label.setText(
                    f"校准集: {set_name}\n"
                    f"血条数量: {info['count']}\n"
                    f"校准时间: {info['calibration_time']}\n"
                    f"点击'加载'按钮使用此校准集"
                )
                
                self.delete_btn.setEnabled(True)
                self.load_btn.setEnabled(True)
    
    def load_selected_calibration(self):
        """加载选中的校准集"""
        if self.calibration_list.currentItem():
            set_name = self.calibration_list.currentItem().data(Qt.UserRole)
            success = self.calibration.load_calibration(set_name)
            
            if success:
                info = self.calibration.get_calibration_set_info(set_name)
                self.current_set_label.setText(f"当前校准集: {set_name} ({info['count']}条)")
                self.recognize_btn.setEnabled(True)
                self.status_label.setText(f"已加载校准集: {set_name}")
                
                self.result_label.setText(
                    f"校准集 '{set_name}' 已加载\n"
                    f"包含 {info['count']} 条血条位置\n"
                    f"可以点击'识别队友'按钮开始识别"
                )
            else:
                self.status_label.setText(f"加载校准集失败: {set_name}")
    
    def delete_calibration_set(self):
        """删除选中的校准集"""
        if self.calibration_list.currentItem():
            set_name = self.calibration_list.currentItem().data(Qt.UserRole)
            
            reply = QMessageBox.question(
                self,
                "确认删除",
                f"确定要删除校准集 '{set_name}' 吗？此操作不可恢复。",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            
            if reply == QMessageBox.Yes:
                success = self.calibration.delete_calibration_set(set_name)
                if success:
                    self.status_label.setText(f"已删除校准集: {set_name}")
                    self.load_calibration_sets()  # 重新加载列表
                    
                    # 更新当前校准集显示
                    if self.calibration.current_set_name:
                        info = self.calibration.get_calibration_set_info(self.calibration.current_set_name)
                        self.current_set_label.setText(f"当前校准集: {self.calibration.current_set_name} ({info['count']}条)")
                        self.recognize_btn.setEnabled(True)
                    else:
                        self.current_set_label.setText("当前未选择校准集")
                        self.recognize_btn.setEnabled(False)
                else:
                    self.status_label.setText(f"删除校准集失败: {set_name}")
    
    def show_first_run_dialog(self):
        """显示首次运行对话框"""
        QMessageBox.information(
            self,
            "首次运行",
            "欢迎使用血条校准工具！\n"
            "您需要创建一个新的校准集。\n"
            "接下来请选择要校准的血条数量。"
        )
        self.show_calibration_options()
    
    def recognize_teammates(self):
        """识别队友"""
        if not self.calibration.current_set_name:
            self.status_label.setText("请先选择校准集")
            return
            
        self.setEnabled(False)  # 禁用对话框，防止用户操作
        QApplication.processEvents()  # 更新UI
        
        try:
            teammates = self.calibration.recognize_teammates()
            
            if teammates:
                result_text = f"队友识别完成！(校准集: {self.calibration.current_set_name})\n\n已识别的队友:\n"
                for tm in teammates:
                    result_text += f"- {tm['name']} ({tm['profession']})\n"
                self.result_label.setText(result_text)
            else:
                self.result_label.setText("没有识别到任何队友，请检查校准是否正确")
        except Exception as e:
            self.result_label.setText(f"识别队友时出错: {str(e)}")
        
        self.setEnabled(True)  # 恢复对话框
    
    def show_calibration_options(self):
        """显示校准选项"""
        num_bars = self.show_bar_count_selection_dialog()
        if num_bars > 0:
            self.start_calibration(num_bars)
    
    def start_calibration(self, num_health_bars=5):
        """开始校准流程
        
        参数:
            num_health_bars: 要校准的血条数量
        """
        self.setEnabled(False)  # 禁用对话框，防止用户操作
        QApplication.processEvents()  # 更新UI
        
        try:
            success = self.calibration.start_calibration(num_health_bars)
            if success:
                self.result_label.setText("校准完成！\n\n" + 
                                         f"已校准 {len(self.calibration.health_bars)} 个血条位置\n\n" + 
                                         '接下来可以点击"识别队友"进行自动识别')
            else:
                self.result_label.setText("校准未完成或被取消")
        except Exception as e:
            self.result_label.setText(f"校准过程中出错: {str(e)}")
        
        self.setEnabled(True)  # 恢复对话框
        self.update_button_states()
    
    def on_calibration_complete(self, health_bars):
        """校准完成后的回调"""
        self.update_button_states()
    
    def update_button_states(self):
        """更新按钮状态"""
        has_calibration = self.calibration.load_calibration()
        self.recognize_btn.setEnabled(has_calibration)
    
    def update_status(self, message):
        """更新状态信息"""
        self.status_label.setText(message)
        QApplication.processEvents()  # 更新UI
    
    def reset_calibration(self):
        """重置所有校准数据"""
        reply = QMessageBox.question(
            self,
            "确认重置",
            "确定要重置所有校准数据吗？这将删除所有保存的校准集。",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            self.setEnabled(False)  # 禁用对话框，防止用户操作
            QApplication.processEvents()  # 更新UI
            
            try:
                success = self.calibration.reset_all_calibration()
                if success:
                    self.result_label.setText("所有校准数据已重置")
                    self.load_calibration_sets()  # 重新加载列表
                    self.current_set_label.setText("当前未选择校准集")
                    self.recognize_btn.setEnabled(False)
                else:
                    self.result_label.setText("重置校准数据失败")
            except Exception as e:
                self.result_label.setText(f"重置校准时出错: {str(e)}")
            
            self.setEnabled(True)  # 恢复对话框

    def show_bar_count_selection_dialog(self):
        """显示血条数量选择对话框
        
        返回:
            int: 用户选择的血条数量，如果用户取消则返回0
        """
        dialog = QDialog(self)
        dialog.setWindowTitle("选择血条数量")
        layout = QVBoxLayout(dialog)
        
        # 添加说明文本
        label = QLabel("请选择要校准的血条数量：", dialog)
        layout.addWidget(label)
        
        # 添加按钮组
        button_layout = QHBoxLayout()
        
        btn_5 = QPushButton("5条血条", dialog)
        btn_10 = QPushButton("10条血条", dialog)
        btn_20 = QPushButton("20条血条", dialog)
        btn_custom = QPushButton("自定义...", dialog)
        
        button_layout.addWidget(btn_5)
        button_layout.addWidget(btn_10)
        button_layout.addWidget(btn_20)
        button_layout.addWidget(btn_custom)
        
        layout.addLayout(button_layout)
        
        # 用于存储选择结果
        result = [5]  # 默认为5条
        
        # 连接按钮信号
        def on_btn_5_clicked():
            result[0] = 5
            dialog.accept()
            
        def on_btn_10_clicked():
            result[0] = 10
            dialog.accept()
            
        def on_btn_20_clicked():
            result[0] = 20
            dialog.accept()
            
        def on_btn_custom_clicked():
            # 显示自定义数量输入对话框
            custom_num, ok = QInputDialog.getInt(
                dialog, 
                "自定义血条数量", 
                "请输入要校准的血条数量：",
                5, 1, 50, 1
            )
            if ok:
                result[0] = custom_num
                dialog.accept()
        
        btn_5.clicked.connect(on_btn_5_clicked)
        btn_10.clicked.connect(on_btn_10_clicked)
        btn_20.clicked.connect(on_btn_20_clicked)
        btn_custom.clicked.connect(on_btn_custom_clicked)
        
        # 添加取消按钮
        cancel_layout = QHBoxLayout()
        cancel_btn = QPushButton("取消", dialog)
        cancel_btn.clicked.connect(dialog.reject)
        cancel_layout.addStretch()
        cancel_layout.addWidget(cancel_btn)
        layout.addLayout(cancel_layout)
        
        # 设置对话框样式
        dialog.setStyleSheet("""
            QDialog {
                background-color: #f5f5f5;
            }
            QLabel {
                font-size: 14px;
                margin-bottom: 10px;
            }
            QPushButton {
                min-width: 100px;
                min-height: 30px;
                padding: 5px;
                font-size: 13px;
            }
        """)
        
        # 显示对话框并等待用户选择
        if dialog.exec() == QDialog.Accepted:
            return result[0]
        else:
            return 0

    def clear_teammate_recognition(self):
        """清除所有队友识别"""
        if not self.calibration.current_set_name:
            self.status_label.setText("请先选择校准集")
            return
        
        reply = QMessageBox.question(
            self,
            "确认清除",
            "确定要清除所有已识别的队友信息吗？\n这不会删除校准的血条位置数据。",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            self.setEnabled(False)  # 禁用对话框，防止用户操作
            QApplication.processEvents()  # 更新UI
            
            try:
                success = self.calibration.clear_teammate_recognition()
                if success:
                    self.result_label.setText(f"已清除校准集 '{self.calibration.current_set_name}' 的队友识别结果\n\n"
                                             f"可以点击'识别队友'按钮重新识别")
                else:
                    self.result_label.setText("清除队友识别结果失败")
            except Exception as e:
                self.result_label.setText(f"清除队友识别结果时出错: {str(e)}")
            
            self.setEnabled(True)  # 恢复对话框


def main():
    """主函数"""
    app = QApplication(sys.argv)
    dialog = CalibrationDialog()
    dialog.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main() 