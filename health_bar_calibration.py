import cv2
import time
import json
import numpy as np
import os
from PIL import Image, ImageDraw
import threading
import sys
import importlib.util

# 从PyQt5导入所需的类和库
from PyQt5.QtCore import Qt, QPropertyAnimation, QObject, pyqtSignal as Signal, QRect, QTimer
from PyQt5.QtGui import QColor, QIcon, QDesktopServices
from PyQt5.QtWidgets import (
    QApplication, QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
    QPushButton, QMessageBox, QProgressBar, QFrame, QInputDialog,
    QListWidget, QListWidgetItem, QAbstractItemView, QGraphicsDropShadowEffect
)

from qfluentwidgets import (InfoBar, InfoBarPosition, MessageBoxBase, SubtitleLabel, 
                           BodyLabel, PushButton, PrimaryPushButton, CaptionLabel, 
                           ToolButton, ComboBox, Action, setTheme, Theme, MessageBox, 
                           TransparentPushButton, LineEdit, StrongBodyLabel, FluentIcon as FIF)

from 选择框 import show_selection_box
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
        
        # 新增：初始化全局默认颜色属性
        self.default_hp_color_lower = None
        self.default_hp_color_upper = None
        
        # 加载校准数据
        self.load_all_calibration_sets()
    
    def load_all_calibration_sets(self):
        """加载所有校准数据集"""
        if not os.path.exists(self.calibration_file):
            print(f"校准文件 {self.calibration_file} 不存在")
            self.calibration_sets = {}
            return False
            
        try:
            print(f"尝试加载校准文件: {self.calibration_file}")
            with open(self.calibration_file, 'r', encoding='utf-8') as f:
                try:
                    data = json.load(f)
                    print("JSON解析成功")
                    
                    if 'calibration_sets' in data and isinstance(data['calibration_sets'], dict):
                        self.calibration_sets = data['calibration_sets']
                        print(f"校准集数量: {len(self.calibration_sets)}")
                        print(f"校准集名称: {list(self.calibration_sets.keys())}")
                    
                        # 加载最后使用的校准集
                        if 'last_used' in data and data['last_used'] in self.calibration_sets:
                            self.current_set_name = data['last_used']
                            self.health_bars = self.calibration_sets[self.current_set_name]['health_bars']
                            print(f"加载最后使用的校准集: {self.current_set_name}")
                        else:
                            print("无最后使用的校准集或其已不存在")
                    
                        return len(self.calibration_sets) > 0
                    else:
                        print("校准文件中找不到有效的校准集数据")
                except json.JSONDecodeError as json_err:
                    print(f"校准文件JSON解析失败: {json_err}")
                    # 尝试不同的编码方式
                    f.seek(0)
                    content = f.read()
                    try:
                        # 尝试用不同的方式手动解析
                        data = json.loads(content)
                        if 'calibration_sets' in data and isinstance(data['calibration_sets'], dict):
                            self.calibration_sets = data['calibration_sets']
                            print(f"使用替代方法成功加载校准集: {len(self.calibration_sets)}")
                            return len(self.calibration_sets) > 0
                    except Exception as alt_err:
                        print(f"替代解析方法也失败: {alt_err}")
        except Exception as e:
            print(f"加载血条校准数据失败: {str(e)}")
            import traceback
            traceback.print_exc()
        
        return False
    
    def load_calibration(self, set_name=None):
        """加载指定校准数据集
        
        参数:
            set_name (str): 校准集名称，如果为None则使用当前校准集
            
        返回:
            bool: 是否成功加载校准数据
        """
        print(f"\n--- 加载校准集 '{set_name}' ---")
        if not self.calibration_sets:
            print("错误: 没有可用的校准集")
            return False
            
        if set_name is None:
            if not self.current_set_name:
                # 如果未指定且当前无选择，则使用第一个校准集
                if self.calibration_sets:
                    self.current_set_name = list(self.calibration_sets.keys())[0]
                    print(f"未指定校准集，使用第一个: {self.current_set_name}")
                else:
                    print("错误: 没有可用的校准集")
                    return False
            else:
                print(f"使用当前校准集: {self.current_set_name}")
        else:
            print(f"设置当前校准集为: {set_name}")
            self.current_set_name = set_name
        
        if self.current_set_name in self.calibration_sets:
            self.health_bars = self.calibration_sets[self.current_set_name]['health_bars']
            print(f"校准集 '{self.current_set_name}' 加载成功，包含 {len(self.health_bars)} 个血条")
            
            # 打印血条位置信息
            for i, bar in enumerate(self.health_bars):
                print(f"血条 {i+1}: x1={bar.get('x1')}, y1={bar.get('y1')}, x2={bar.get('x2')}, y2={bar.get('y2')}")
            
            return len(self.health_bars) > 0
        else:
            print(f"错误: 校准集 '{self.current_set_name}' 不存在")
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
        try:
            # 创建新的校准集名称
            self.current_set_name = f"{num_health_bars}条血条_{time.strftime('%m%d%H%M')}"
            self.health_bars = []  # 清空现有校准数据
            
            self.signals.status_signal.emit("开始血条位置校准...")
            
            # 显示开始提示 - 使用无边框对话框
            try:
                guide_dialog = CalibrationGuideMessageBox(num_health_bars, True)
                guide_dialog.exec()
            except Exception as e:
                print(f"显示校准指导对话框时出错: {e}")
                self.signals.status_signal.emit(f"校准指导显示失败: {e}")
                import traceback
                traceback.print_exc()
            
            for i in range(num_health_bars):
                self.signals.status_signal.emit(f"请框选第 {i+1}/{num_health_bars} 个血条区域...")
                self.signals.progress_signal.emit(int(i * 100 / num_health_bars))
                
                # 如果不是第一个，显示下一个的提示 - 使用无边框对话框
                if i > 0:
                    try:
                        continue_dialog = CalibrationGuideMessageBox((i, num_health_bars), False)
                        continue_dialog.exec()
                    except Exception as e:
                        print(f"显示继续校准对话框时出错: {e}")
                        # 错误不会中断流程
                
                # 显示选择框并等待用户选择
                rect = self._select_health_bar_area()
                if rect is None:
                    self.signals.status_signal.emit("校准被用户取消")
                    return False
                
                # 检查rect是否有效
                if rect.width() <= 0 or rect.height() <= 0:
                    self.signals.status_signal.emit("选择区域无效，校准已取消")
                    return False
                
                # 添加有效的血条区域
                self.health_bars.append({
                    'x1': rect.x(),
                    'y1': rect.y(),
                    'x2': rect.x() + rect.width(),
                    'y2': rect.y() + rect.height(),
                    'recognition_done': False
                })
            
            # 完成消息 - 使用无边框对话框
            try:
                complete_dialog = CalibrationCompleteMessageBox(num_health_bars)
                complete_dialog.exec()
            except Exception as e:
                print(f"显示校准完成对话框时出错: {e}")
                # 这个错误不影响校准结果
            
            # 保存校准结果
            if self.health_bars:
                success = self.save_calibration()
                if success:
                    self.signals.status_signal.emit(f"血条校准完成并保存为 '{self.current_set_name}'")
                    self.signals.progress_signal.emit(100)
                    self.signals.complete_signal.emit(self.health_bars)
                else:
                    self.signals.status_signal.emit("血条校准完成但保存失败")
                
                return success
            else:
                self.signals.status_signal.emit("没有有效的血条区域，校准失败")
                return False
                
        except Exception as e:
            self.signals.status_signal.emit(f"校准过程中发生错误: {e}")
            print(f"校准过程中发生错误: {e}")
            import traceback
            traceback.print_exc()
            return False
    
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
        """选择血条区域"""
        selected_rect = [None]
        
        def on_selection_complete(rect):
            # 添加对rect为None或无效的检查
            if rect is None:
                print("选择被取消或返回了None")
                selected_rect[0] = None
                return
            
            # 检查矩形是否有效（宽度和高度大于0）
            if rect.width() <= 0 or rect.height() <= 0:
                print(f"选择的矩形无效: 宽度={rect.width()}, 高度={rect.height()}")
                selected_rect[0] = None
                return
            
            selected_rect[0] = rect
            print(f"选择完成: {rect}")
        
        try:
            # 使用show_selection_box函数，它自己会管理QApplication
            from 选择框 import show_selection_box
            result = show_selection_box(on_selection_complete)
            
            # 检查选择框结果：如果用户取消了选择（按了ESC）返回None
            if not result:
                print("用户取消了选择（按了ESC键）")
                return None
            
            # 检查是否成功选择了矩形
            if selected_rect[0] is not None:
                return selected_rect[0]
            
            # 如果没有有效的矩形，也返回None
            return None
        except Exception as e:
            print(f"选择区域时出错: {str(e)}")
            import traceback
            traceback.print_exc()
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
                
                # 应用颜色设置
                if self.default_hp_color_lower is not None and self.default_hp_color_upper is not None:
                    teammate.hp_color_lower = np.copy(self.default_hp_color_lower)
                    teammate.hp_color_upper = np.copy(self.default_hp_color_upper)
                else:
                    # 如果没有全局默认颜色，则使用硬编码的备用值
                    teammate.hp_color_lower = np.array([45, 80, 130]) 
                    teammate.hp_color_upper = np.array([60, 160, 210])
                
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
        # 使用基于 MessageBoxBase 的无边框对话框
        dialog = BarCountSelectionMessageBox(None)  # 不设置父窗口以避免可能的窗口层级问题
        
        if dialog.exec():
            return dialog.result
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

    def get_calibration_sets(self):
        """获取所有校准集名称（作为 get_calibration_set_names 的别名）
        
        返回:
            list: 校准集名称列表
        """
        return self.get_calibration_set_names()
        
    def get_calibration_info(self, set_name):
        """获取指定校准集的信息（作为 get_calibration_set_info 的别名）
        
        参数:
            set_name (str): 校准集名称
            
        返回:
            dict: 校准集信息，包含count和calibration_time
        """
        return self.get_calibration_set_info(set_name)


class CalibrationDialog(QDialog):
    """血条校准对话框
    
    提供用户界面，引导用户完成血条校准流程
    """
    
    def __init__(self, parent=None):
        """初始化校准对话框"""
        # 确保QApplication已存在
        ensure_application()
        super().__init__(parent)
        self.calibration = HealthBarCalibration()
        self.initUI()
        
        # 连接信号
        self.calibration.signals.status_signal.connect(self.update_status)
        self.calibration.signals.progress_signal.connect(self.update_progress)
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
        self.progress_label = QLabel("准备就绪")
        self.progress_label.setStyleSheet("color: blue;")
        right_layout.addWidget(self.progress_label)
        
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
                self.progress_label.setText(f"已加载校准集: {set_name}")
                
                self.result_label.setText(
                    f"校准集 '{set_name}' 已加载\n"
                    f"包含 {info['count']} 条血条位置\n"
                    f"可以点击'识别队友'按钮开始识别"
                )
            else:
                self.progress_label.setText(f"加载校准集失败: {set_name}")
    
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
                    self.progress_label.setText(f"已删除校准集: {set_name}")
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
                    self.progress_label.setText(f"删除校准集失败: {set_name}")
    
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
            self.progress_label.setText("请先选择校准集")
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
        self.progress_label.setText(message)
    
    def update_progress(self, value):
        """更新进度条"""
        self.progress_bar.setValue(value)
    
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
                # 显示错误提示
                InfoBar.error(
                    title='重置失败',
                    content=f'重置校准数据时出错: {str(e)}',
                    orient=Qt.Horizontal,
                    isClosable=True,
                    position=InfoBarPosition.TOP,
                    duration=3000,
                    parent=self
                )
            
            self.setEnabled(True)  # 恢复对话框
    
    def show_bar_count_selection_dialog(self):
        """显示血条数量选择对话框
        
        返回:
            int: 用户选择的血条数量，如果用户取消则返回0
        """
        dialog = BarCountSelectionMessageBox(None)  # 不设置父窗口以避免可能的窗口层级问题
        
        if dialog.exec():
            return dialog.result
        else:
            return 0

    def clear_teammate_recognition(self):
        """清除所有队友识别"""
        if not self.calibration.current_set_name:
            self.progress_label.setText("请先选择校准集")
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


def ensure_application():
    """确保QApplication实例已经存在"""
    # 明确使用PyQt5
    app = QApplication.instance()
    if app is None:
        # 仅创建实例但不启动事件循环
        app = QApplication(sys.argv)
    return app

def show_calibration_dialog(parent=None, auto_start=False):
    """显示校准对话框的便捷函数
    
    参数:
        parent: 父窗口
        auto_start: 是否自动开始新建校准
    """
    # 确保应用已初始化
    app = ensure_application()
    
    # 创建并显示对话框，避免父窗口问题
    dialog = CalibrationDialog(None)
    dialog.setWindowFlags(dialog.windowFlags() | Qt.Window)
    
    # 如果设置了自动开始，则直接触发新建校准
    # 需要使用exec_模式而不是show()，确保对话框显示完整并且用户可以交互
    # 只有用户确认后再返回
    if auto_start:
        # 先显示对话框
        dialog.show()
        # 等待对话框完全显示
        QApplication.processEvents()
        # 然后触发校准选项
        dialog.show_calibration_options()
    
    # 使用exec_()方法以模态方式显示对话框，确保用户完成操作后才返回
    dialog.exec_()
    
    # 返回对话框实例
    return dialog

def main():
    """主函数，用于独立运行校准工具"""
    # 明确使用PyQt5
    app = ensure_application() 
    
    # 设置Fluent UI主题
    from qfluentwidgets import setTheme, Theme
    setTheme(Theme.AUTO)
    
    # 显示校准对话框
    dialog = CalibrationDialog()
    dialog.exec()
    
    # 如果是独立运行则启动事件循环
    if QApplication.instance() is app:
        sys.exit(app.exec())

def quick_calibration(parent=None):
    """快速校准血条位置，不显示主界面
    
    直接弹出选择血条数量对话框，然后进行校准，最后保存到json文件
    
    参数:
        parent: 父窗口
    
    返回:
        bool: 是否成功完成校准
    """
    # 确保应用已初始化
    app = ensure_application()
    
    # 创建校准工具实例
    calibration = HealthBarCalibration()
    
    # 弹出选择血条数量的对话框
    num_bars = select_bar_count_dialog(parent)
    
    if num_bars <= 0:
        return False  # 用户取消了操作
    
    # 开始校准流程
    success = calibration.start_calibration(num_bars)
    
    return success

# 新增 BarCountSelectionMessageBox 类
class BarCountSelectionMessageBox(MessageBoxBase):
    """基于 MessageBoxBase 的血条数量选择对话框"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.titleLabel = SubtitleLabel('选择血条数量', self)
        self.contentLabel = BodyLabel("请选择要校准的血条数量：")
        self.contentLabel.setWordWrap(True)
        
        # 创建按钮布局
        self.buttonLayout = QHBoxLayout()
        self.btn_5 = PushButton("5条血条", self)
        self.btn_10 = PushButton("10条血条", self)
        self.btn_20 = PushButton("20条血条", self)
        self.btn_custom = PushButton("自定义...", self)
        
        self.buttonLayout.addWidget(self.btn_5)
        self.buttonLayout.addWidget(self.btn_10)
        self.buttonLayout.addWidget(self.btn_20)
        self.buttonLayout.addWidget(self.btn_custom)
        
        # 添加所有控件到视图布局
        self.viewLayout.addWidget(self.titleLabel)
        self.viewLayout.addWidget(self.contentLabel)
        self.viewLayout.addLayout(self.buttonLayout)
        
        # 修改默认按钮文本
        self.yesButton.setText('确定')
        self.cancelButton.setText('取消')
        
        # 隐藏确定按钮，我们将直接使用选择按钮
        self.hideYesButton()
        
        # 设置最小宽度
        self.widget.setMinimumWidth(400)
        
        # 存储结果
        self.result = 0
        
        # 连接按钮信号
        self.btn_5.clicked.connect(lambda: self._set_result(5))
        self.btn_10.clicked.connect(lambda: self._set_result(10))
        self.btn_20.clicked.connect(lambda: self._set_result(20))
        self.btn_custom.clicked.connect(self._show_custom_dialog)
    
    def _set_result(self, value):
        """设置结果并接受对话框"""
        self.result = value
        self.accept()
    
    def _show_custom_dialog(self):
        """显示自定义数量输入对话框"""
        from PyQt5.QtWidgets import QInputDialog
        custom_num, ok = QInputDialog.getInt(
            self, 
            "自定义血条数量", 
            "请输入要校准的血条数量：",
            5, 1, 50, 1
        )
        if ok:
            self.result = custom_num
            self.accept()

# 修改 select_bar_count_dialog 函数
def select_bar_count_dialog(parent=None):
    """显示血条数量选择对话框(独立版本)
    
    返回:
        int: 用户选择的血条数量，如果用户取消则返回0
    """
    # 确保应用已初始化
    app = ensure_application()
    
    # 创建并显示对话框
    dialog = BarCountSelectionMessageBox(parent)
    if dialog.exec():
        return dialog.result
    else:
        return 0

# 修改无边框校准指导对话框类
class CalibrationGuideMessageBox(MessageBoxBase):
    """校准指导无边框对话框"""
    
    def __init__(self, num_health_bars, is_first=True, parent=None):
        # 创建自己的窗口作为根组件，不依赖父窗口的尺寸
        tempWidget = None
        try:
            if parent is None:
                # 获取当前活动窗口
                parent = QApplication.activeWindow()
                if parent is None:
                    # 创建临时容器但不显示
                    from PyQt5.QtWidgets import QWidget
                    tempWidget = QWidget()
                    tempWidget.resize(800, 600)
                    parent = tempWidget
        except Exception as e:
            print(f"CalibrationGuideMessageBox创建父窗口时出错: {e}")
            # 在出错时保证有一个父级窗口
            from PyQt5.QtWidgets import QWidget
            tempWidget = QWidget()
            tempWidget.resize(800, 600)
            parent = tempWidget
            
        # 调用父类初始化
        super().__init__(parent)
        
        # 设置标题
        title = "校准指导" if is_first else "继续校准"
        self.titleLabel = SubtitleLabel(title, self)
        self.titleLabel.setStyleSheet("font-size: 16px; font-weight: bold; color: #333333;")
        
        # 添加图标
        self.iconLabel = QLabel(self)
        pixmap = FIF.SEARCH.icon().pixmap(32, 32)
        self.iconLabel.setPixmap(pixmap)
        self.iconLabel.setAlignment(Qt.AlignCenter)
        self.iconLabel.setStyleSheet("margin-right: 10px;")
        
        # 标题栏布局
        titleLayout = QHBoxLayout()
        titleLayout.addWidget(self.iconLabel)
        titleLayout.addWidget(self.titleLabel)
        titleLayout.addStretch(1)
        
        # 内容文本
        content_text = ""
        if is_first:
            # 初始校准提示
            # 确保 num_health_bars 是整数类型
            bar_count = num_health_bars
            if isinstance(num_health_bars, tuple) and len(num_health_bars) >= 2:
                bar_count = num_health_bars[1]  # 使用总数
            
            content_text = (f"即将开始校准 {bar_count} 个血条位置。\n\n"
                            "请依次框选每个队友的血条区域，\n"
                            "框选完成后按Enter键确认。\n\n"
                            "第一个血条开始...")
        else:
            # 继续校准提示
            if isinstance(num_health_bars, tuple) and len(num_health_bars) >= 2:
                current, total = num_health_bars
                content_text = (f"已完成 {current}/{total} 个血条。\n\n"
                                f"请继续框选第 {current+1} 个血条区域。")
            else:
                # 安全处理其他情况
                content_text = "请继续框选下一个血条区域。"
        
        # 内容标签
        self.contentLabel = BodyLabel(content_text)
        self.contentLabel.setWordWrap(True)
        self.contentLabel.setStyleSheet("line-height: 150%; margin: 10px 0; font-size: 14px; color: #505050;")
        
        # 提示信息
        self.tipLabel = CaptionLabel("提示：按ESC键可以取消当前选择")
        self.tipLabel.setStyleSheet("color: #0078d7; margin-top: 10px; font-size: 12px;")
        
        # 添加到视图布局
        self.viewLayout.addLayout(titleLayout)
        self.viewLayout.addWidget(self.contentLabel)
        self.viewLayout.addWidget(self.tipLabel)
        
        # 设置按钮文本和样式
        self.yesButton.setText('确定')
        self.yesButton.setIcon(FIF.ACCEPT.icon())
        self.cancelButton.hide()  # 隐藏取消按钮
        
        # 设置窗口样式和尺寸
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
        """自定义对话框阴影效果"""
        try:
            shadow = QGraphicsDropShadowEffect(self.widget)
            shadow.setBlurRadius(15)
            shadow.setColor(QColor(0, 0, 0, 80))
            shadow.setOffset(0, 0)
            self.widget.setGraphicsEffect(shadow)
        except Exception as e:
            print(f"设置阴影效果时出错: {e}")

# 修改无边框校准完成对话框类
class CalibrationCompleteMessageBox(MessageBoxBase):
    """校准完成无边框对话框"""
    
    def __init__(self, num_health_bars, parent=None):
        # 创建自己的窗口作为根组件，不依赖父窗口的尺寸
        tempWidget = None
        try:
            if parent is None:
                # 获取当前活动窗口
                parent = QApplication.activeWindow()
                if parent is None:
                    # 创建临时容器但不显示
                    from PyQt5.QtWidgets import QWidget
                    tempWidget = QWidget()
                    tempWidget.resize(800, 600)
                    parent = tempWidget
        except Exception as e:
            print(f"CalibrationCompleteMessageBox创建父窗口时出错: {e}")
            # 在出错时保证有一个父级窗口
            from PyQt5.QtWidgets import QWidget
            tempWidget = QWidget()
            tempWidget.resize(800, 600)
            parent = tempWidget
            
        # 调用父类初始化
        super().__init__(parent)
        
        # 设置标题
        self.titleLabel = SubtitleLabel("校准完成", self)
        self.titleLabel.setStyleSheet("font-size: 16px; font-weight: bold; color: #333333;")
        
        # 添加图标
        self.iconLabel = QLabel(self)
        pixmap = FIF.CHECKMARK.icon().pixmap(32, 32)
        self.iconLabel.setPixmap(pixmap)
        self.iconLabel.setAlignment(Qt.AlignCenter)
        self.iconLabel.setStyleSheet("margin-right: 10px;")
        
        # 标题栏布局
        titleLayout = QHBoxLayout()
        titleLayout.addWidget(self.iconLabel)
        titleLayout.addWidget(self.titleLabel)
        titleLayout.addStretch(1)
        
        # 内容文本 - 处理num_health_bars可能是元组的情况
        if isinstance(num_health_bars, tuple) and len(num_health_bars) >= 2:
            # 如果是元组(当前索引, 总数)
            current, total = num_health_bars
            content_text = f"已完成所有 {total} 个血条的校准！"
        else:
            # 如果是单个数字
            content_text = f"已完成所有 {num_health_bars} 个血条的校准！"
        
        # 内容标签
        self.contentLabel = BodyLabel(content_text)
        self.contentLabel.setWordWrap(True)
        self.contentLabel.setStyleSheet("line-height: 150%; margin: 10px 0; font-size: 14px; color: #505050;")
        
        # 添加到视图布局
        self.viewLayout.addLayout(titleLayout)
        self.viewLayout.addWidget(self.contentLabel)
        
        # 设置按钮文本和样式
        self.yesButton.setText('确定')
        self.yesButton.setIcon(FIF.ACCEPT.icon())
        self.cancelButton.hide()  # 隐藏取消按钮
        
        # 设置窗口样式和尺寸
        self.widget.setMinimumWidth(350)
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
        """自定义对话框阴影效果"""
        try:
            shadow = QGraphicsDropShadowEffect(self.widget)
            shadow.setBlurRadius(15)
            shadow.setColor(QColor(0, 0, 0, 80))
            shadow.setOffset(0, 0)
            self.widget.setGraphicsEffect(shadow)
        except Exception as e:
            print(f"设置阴影效果时出错: {e}")


if __name__ == "__main__":
    main() 