import sys
import os
import cv2
import numpy as np
import time
import threading
import importlib.util
import pyautogui
import keyboard
import win32api  # 导入win32api用于检测鼠标状态
import win32con  # 导入win32con用于鼠标键值常量
from PyQt5.QtWidgets import QApplication, QDialog, QVBoxLayout, QLabel, QComboBox, QPushButton, QLineEdit, QMainWindow
from PyQt5.QtCore import QTimer, pyqtSignal, QObject, QRect, QEventLoop
from 选择框 import TransparentSelectionBox
import json
import pygetwindow as gw

# 动态导入带空格的模块
module_name = "Zhu Xian World Health Bar Test(choice box)"
module_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Zhu Xian World Health Bar Test(choice box).py")
spec = importlib.util.spec_from_file_location(module_name, module_path)
health_bar_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(health_bar_module)

# 从模块中获取需要的函数
get_hp_percentage = health_bar_module.get_hp_percentage

class HealthMonitorSignals(QObject):
    """健康监控信号类"""
    update_signal = pyqtSignal(list)  # 更新血量数据
    status_signal = pyqtSignal(str)   # 状态消息

class HealthMonitor:
    """健康监控类，负责监控游戏中队友血条状态"""
    
    def __init__(self, team=None):
        """初始化健康监控器
        
        参数:
            team: 团队对象，包含所有需要监控的队友
        """
        self.team = team
        self.is_running = False
        self.update_interval = 0.1  # 默认每100ms更新一次
        self.monitor_thread = None
        self.health_threshold = 30.0  # 默认低血量阈值（百分比）
        self.auto_select_enabled = False  # 是否启用自动点击低血量队友
        self.priority_profession = None  # 优先职业
        self.signals = HealthMonitorSignals()
        
        # 加载自动点击配置
        self.load_auto_select_config()
    
    def load_auto_select_config(self):
        """加载自动点击配置"""
        try:
            # 获取配置文件路径
            config_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "auto_select_config.json")
            
            if os.path.exists(config_file):
                with open(config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    self.auto_select_enabled = config.get('enabled', False)
                    self.health_threshold = config.get('threshold', 30.0)
                    self.priority_profession = config.get('priority_profession', None)
        except Exception as e:
            print(f"加载自动点击配置失败: {e}")
    
    def save_auto_select_config(self):
        """保存自动点击配置"""
        try:
            # 获取配置文件路径
            config_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "auto_select_config.json")
            
            # 构造配置
            config = {
                'enabled': self.auto_select_enabled,
                'threshold': self.health_threshold,
                'priority_profession': self.priority_profession
            }
            
            # 保存配置
            with open(config_file, 'w', encoding='utf-8') as f:
                json.dump(config, f, ensure_ascii=False, indent=4)
        except Exception as e:
            print(f"保存自动点击配置失败: {e}")
    
    def start(self):
        """启动健康监控"""
        if self.is_running:
            return
        
        self.is_running = True
        self.monitor_thread = threading.Thread(target=self._monitoring_loop, daemon=True)
        self.monitor_thread.start()
        self.signals.status_signal.emit("健康监控已启动")
    
    def stop(self):
        """停止健康监控"""
        self.is_running = False
        if self.monitor_thread and self.monitor_thread.is_alive():
            self.monitor_thread.join(timeout=2.0)  # 等待线程结束，最多2秒
        self.signals.status_signal.emit("健康监控已停止")
    
    def release_resources(self):
        """释放资源，在应用程序关闭前调用"""
        self.stop()
    
    def _monitoring_loop(self):
        """监控循环，在独立线程中运行"""
        last_update_time = 0
        consecutive_errors = 0
        max_allowed_errors = 5  # 允许连续出错的最大次数
        
        while self.is_running:
            try:
                # 检查时间间隔
                current_time = time.time()
                if current_time - last_update_time < self.update_interval:
                    time.sleep(0.01)  # 短暂休眠以避免CPU占用过高
                    continue
                
                last_update_time = current_time
                
                # 检查是否有队友
                if not self.team or not self.team.members or len(self.team.members) == 0:
                    time.sleep(0.5)  # 如果没有队友，就等久一点
                    continue
                
                # 抓取屏幕截图
                screenshot = pyautogui.screenshot()
                screenshot_np = np.array(screenshot)
                screenshot_rgb = cv2.cvtColor(screenshot_np, cv2.COLOR_RGB2BGR)
                
                # 检测每个队友的血量
                health_data = []
                lowest_health_member = None
                lowest_health_value = 100.0
                
                for member in self.team.members:
                    try:
                        # 确保有血条位置
                        if not hasattr(member, 'x1') or not hasattr(member, 'y1') or \
                           not hasattr(member, 'x2') or not hasattr(member, 'y2') or \
                           member.x1 is None or member.y1 is None or \
                           member.x2 is None or member.y2 is None:
                            continue
                        
                        # 获取血条区域
                        x1, y1, x2, y2 = int(member.x1), int(member.y1), int(member.x2), int(member.y2)
                        health_bar_region = screenshot_rgb[y1:y2, x1:x2]
                        
                        if health_bar_region.size == 0:
                            continue  # 跳过无效区域
                        
                        # 确定血条颜色范围
                        has_custom_color = hasattr(member, 'hp_color_lower') and hasattr(member, 'hp_color_upper') and \
                                         member.hp_color_lower is not None and member.hp_color_upper is not None
                        
                        if has_custom_color:
                            # 使用自定义颜色范围
                            lower_bound = member.hp_color_lower
                            upper_bound = member.hp_color_upper
                        else:
                            # 使用默认颜色范围（绿色）
                            lower_bound = np.array([50, 100, 50])
                            upper_bound = np.array([90, 255, 90])
                        
                        # 创建掩码，识别血条颜色
                        mask = cv2.inRange(health_bar_region, lower_bound, upper_bound)
                        
                        # 计算血量百分比
                        health_pixels = cv2.countNonZero(mask)
                        total_pixels = health_bar_region.shape[0] * health_bar_region.shape[1]
                        health_percentage = (health_pixels / total_pixels) * 100 if total_pixels > 0 else 0
                        
                        # 存储血量数据
                        member_data = {
                            'name': member.name,
                            'health': health_percentage,
                            'profession': getattr(member, 'profession', '未知'),
                            'x1': x1,
                            'y1': y1,
                            'x2': x2,
                            'y2': y2
                        }
                        health_data.append(member_data)
                        
                        # 检查是否是血量最低的队友
                        if health_percentage < lowest_health_value:
                            # 如果设置了优先职业且当前队友职业匹配
                            if self.priority_profession is None or \
                               (hasattr(member, 'profession') and \
                                member.profession == self.priority_profession):
                                lowest_health_value = health_percentage
                                lowest_health_member = member
                    except Exception as e:
                        # 忽略单个队友处理错误，继续处理其他队友
                        print(f"处理队友 {member.name} 时发生错误: {e}")
                
                # 发送血量数据更新信号
                if health_data:
                    self.signals.update_signal.emit(health_data)
                    consecutive_errors = 0  # 重置错误计数
                    
                    # 检查是否需要自动点击低血量队友
                    if self.auto_select_enabled and lowest_health_member and lowest_health_value < self.health_threshold:
                        self._auto_click_low_health_member(lowest_health_member)
            
            except Exception as e:
                consecutive_errors += 1
                error_msg = f"监控循环发生错误: {e}"
                print(error_msg)
                self.signals.status_signal.emit(error_msg)
                
                # 如果连续多次出错，暂停监控
                if consecutive_errors >= max_allowed_errors:
                    error_msg = f"连续 {max_allowed_errors} 次出错，监控已暂停"
                    print(error_msg)
                    self.signals.status_signal.emit(error_msg)
                    self.is_running = False
                    break
                    
                time.sleep(1)  # 出错后等待一秒再继续
    
    def _auto_click_low_health_member(self, member):
        """自动点击低血量队友
        
        参数:
            member: 血量低的队友对象
        """
        try:
            # 确保有血条位置
            if not hasattr(member, 'x1') or not hasattr(member, 'y1') or \
               not hasattr(member, 'x2') or not hasattr(member, 'y2') or \
               member.x1 is None or member.y1 is None or \
               member.x2 is None or member.y2 is None:
                return
            
            # 计算血条中心位置
            click_x = int((member.x1 + member.x2) / 2)
            click_y = int((member.y1 + member.y2) / 2)
            
            # 检查是否在屏幕内
            screen_width, screen_height = pyautogui.size()
            if 0 <= click_x < screen_width and 0 <= click_y < screen_height:
                # 执行点击操作
                current_x, current_y = pyautogui.position()  # 保存当前鼠标位置
                pyautogui.click(click_x, click_y)
                pyautogui.moveTo(current_x, current_y)  # 恢复鼠标位置
                
                # 记录点击信息
                status_msg = f"已自动点击血量低于 {self.health_threshold}% 的队友: {member.name}"
                print(status_msg)
                self.signals.status_signal.emit(status_msg)
                
                # 点击后暂停一段时间，避免连续点击
                time.sleep(2.0)
        except Exception as e:
            print(f"自动点击队友时发生错误: {e}")

    def select_member_dialog(self):
        """创建队员选择对话框
        
        返回:
            选择的队员对象或None
        """
        if not self.team.members:
            self.signals.status_signal.emit("没有队员可以选择")
            return None
            
        dialog = QDialog()
        dialog.setWindowTitle('选择队员')
        layout = QVBoxLayout(dialog)
        
        # 添加说明标签
        label = QLabel('请选择要设置的队员:')
        layout.addWidget(label)
        
        # 添加下拉选择框
        combo = QComboBox()
        for i, member in enumerate(self.team.members):
            combo.addItem(f"{member.name} ({member.profession})")
        layout.addWidget(combo)
        
        # 添加确认和取消按钮
        button_layout = QVBoxLayout()
        confirm_btn = QPushButton('确认')
        cancel_btn = QPushButton('取消')
        button_layout.addWidget(confirm_btn)
        button_layout.addWidget(cancel_btn)
        layout.addLayout(button_layout)
        
        # 设置对话框结果
        selected_index = -1
        
        def on_confirm():
            nonlocal selected_index
            selected_index = combo.currentIndex()
            dialog.accept()
            
        def on_cancel():
            dialog.reject()
            
        confirm_btn.clicked.connect(on_confirm)
        cancel_btn.clicked.connect(on_cancel)
        
        # 显示对话框
        result = dialog.exec()
        
        if result == QDialog.Accepted and selected_index >= 0:
            selected_member = self.team.members[selected_index]
            self.signals.status_signal.emit(f"已选择队员: {selected_member.name}")
            return selected_member
        else:
            self.signals.status_signal.emit("已取消选择队员")
            return None
    
    def set_health_bar_position(self):
        """设置队员血条位置"""
        # 选择队员
        member = self.select_member_dialog()
        if member is None:
            return False
        
        # 使用选择框设置血条位置
        try:
            # 发送状态信号
            self.signals.status_signal.emit(f"正在设置 {member.name} 的血条位置...")
            
            # 创建选择框
            def on_selection(rect: QRect):
                member.x1 = rect.x()
                member.y1 = rect.y()
                member.x2 = rect.x() + rect.width()
                member.y2 = rect.y() + rect.height()
                print(f"{member.name}血条起始坐标设置为: ({member.x1}, {member.y1})")
                print(f"{member.name}血条结束坐标设置为: ({member.x2}, {member.y2})")
                member.save_config()  # 保存新的坐标设置
                self.signals.status_signal.emit(f"{member.name} 的血条位置已设置")
            
            window = TransparentSelectionBox(on_selection)
            result = window.exec()
            if result == QDialog.Accepted:
                self.signals.status_signal.emit(f"已完成 {member.name} 的血条位置设置")
                return True
            else:
                self.signals.status_signal.emit(f"已取消 {member.name} 的血条位置设置")
                return False
        except Exception as e:
            self.signals.status_signal.emit(f"设置血条位置时出错: {str(e)}")
            return False
    
    def set_health_bar_color(self):
        """设置队员血条颜色"""
        # 选择队员
        member = self.select_member_dialog()
        if member is None:
            return False
        
        # 设置血条颜色
        try:
            self.signals.status_signal.emit(f"正在设置 {member.name} 的血条颜色...")
            
            # 创建提示对话框
            info_dialog = QDialog()
            info_dialog.setWindowTitle(f"设置 {member.name} 的血条颜色")
            info_dialog.setMinimumSize(400, 200)
            info_layout = QVBoxLayout(info_dialog)
            
            # 添加操作指南
            guide_label = QLabel("操作指南：")
            guide_label.setStyleSheet("font-weight: bold; font-size: 14px;")
            info_layout.addWidget(guide_label)
            
            steps_label = QLabel(
                "1. 将鼠标移动到游戏中队员的血条上\n"
                "2. 确保选择的是血条颜色最具代表性的位置\n"
                "3. 按下空格键获取颜色\n"
                "4. 按ESC键取消操作"
            )
            steps_label.setWordWrap(True)
            info_layout.addWidget(steps_label)
            
            # 添加状态标签
            status_label = QLabel("状态：等待获取颜色...")
            status_label.setStyleSheet("color: blue;")
            info_layout.addWidget(status_label)
            
            # 创建一个定时器，用于检查键盘输入
            from PySide6.QtCore import QTimer
            key_check_timer = QTimer(info_dialog)
            
            # 颜色获取状态
            color_captured = [False]  # 使用列表包装布尔值，使其可以在嵌套函数中修改
            
            # 定时器回调函数
            def check_keys():
                if keyboard.is_pressed('space'):
                    # 防止重复处理
                    if color_captured[0]:
                        return
                    
                    color_captured[0] = True
                    key_check_timer.stop()
                    
                    x, y = pyautogui.position()
                    status_label.setText(f"状态：正在获取坐标({x}, {y})的颜色...")
                    status_label.setStyleSheet("color: orange;")
                    QApplication.processEvents()  # 更新UI
                    
                    # 截取鼠标位置的屏幕
                    screenshot = pyautogui.screenshot(region=(x, y, 1, 1))
                    frame = np.array(screenshot)
                    # 转换为OpenCV格式
                    frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
                    # 转换到HSV色彩空间
                    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
                    # 获取HSV值
                    h, s, v = hsv[0, 0]
                    # 设置HSV范围（大幅降低范围值，使检测更精确）
                    member.hp_color_lower = np.array([max(0, h-3), max(0, s-25), max(0, v-25)])
                    member.hp_color_upper = np.array([min(180, h+3), min(255, s+25), min(255, v+25)])
                    
                    # 更新状态和日志
                    print(f"{member.name}的HSV颜色值: ({h}, {s}, {v})")
                    print(f"设置{member.name}的HSV范围为: {member.hp_color_lower} - {member.hp_color_upper}")
                    status_label.setText(f"状态：成功获取颜色！HSV值: ({h}, {s}, {v})")
                    status_label.setStyleSheet("color: green; font-weight: bold;")
                    QApplication.processEvents()  # 更新UI
                    
                    # 保存配置
                    member.save_config()  # 保存新的颜色设置
                    self.signals.status_signal.emit(f"{member.name} 的血条颜色已设置")
                    
                    # 设置一个定时器，等待1.5秒后关闭对话框
                    close_timer = QTimer(info_dialog)
                    close_timer.setSingleShot(True)
                    close_timer.timeout.connect(info_dialog.accept)
                    close_timer.start(1500)  # 1.5秒
                
                elif keyboard.is_pressed('esc'):
                    if not color_captured[0]:  # 只有在未捕获颜色时才处理ESC键
                        key_check_timer.stop()
                        self.signals.status_signal.emit(f"已取消设置 {member.name} 的血条颜色")
                        info_dialog.reject()
            
            # 启动定时器，每100毫秒检查一次键盘
            key_check_timer.timeout.connect(check_keys)
            key_check_timer.start(100)
            
            # 显示对话框（模态）
            result = info_dialog.exec()
            
            return result == QDialog.Accepted
        except Exception as e:
            self.signals.status_signal.emit(f"设置血条颜色时出错: {str(e)}")
            return False
    
    def add_team_member(self):
        """添加队员对话框"""
        dialog = QDialog()
        dialog.setWindowTitle('添加队员')
        layout = QVBoxLayout(dialog)
        
        # 添加说明标签
        name_label = QLabel('队员名称:')
        layout.addWidget(name_label)
        
        # 添加名称输入框
        name_input = QLineEdit()
        layout.addWidget(name_input)
        
        # 添加职业标签
        profession_label = QLabel('队员职业:')
        layout.addWidget(profession_label)
        
        # 添加职业输入框
        profession_input = QLineEdit()
        layout.addWidget(profession_input)
        
        # 添加确认和取消按钮
        button_layout = QVBoxLayout()
        confirm_btn = QPushButton('确认')
        cancel_btn = QPushButton('取消')
        button_layout.addWidget(confirm_btn)
        button_layout.addWidget(cancel_btn)
        layout.addLayout(button_layout)
        
        # 设置对话框结果
        name = ""
        profession = ""
        
        def on_confirm():
            nonlocal name, profession
            name = name_input.text().strip()
            profession = profession_input.text().strip()
            if name and profession:
                dialog.accept()
            else:
                error_label = QLabel('名称和职业不能为空!')
                error_label.setStyleSheet('color: red')
                layout.addWidget(error_label)
            
        def on_cancel():
            dialog.reject()
            
        confirm_btn.clicked.connect(on_confirm)
        cancel_btn.clicked.connect(on_cancel)
        
        # 显示对话框
        result = dialog.exec()
        
        if result == QDialog.Accepted and name and profession:
            # 添加队员
            new_member = self.team.add_member(name, profession)
            self.signals.status_signal.emit(f"已添加队员: {name} ({profession})")
            return True
        return False
    
    def remove_team_member(self):
        """移除队员"""
        # 选择队员
        member = self.select_member_dialog()
        if member is None:
            return False
        
        # 从队伍中移除队员
        if member in self.team.members:
            self.team.members.remove(member)
            print(f"已移除队员: {member.name}")
            
            # 删除队员配置文件
            try:
                config_file = f"{member.name}_config.json"
                config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), config_file)
                if os.path.exists(config_path):
                    os.remove(config_path)
                    print(f"已删除队员配置文件: {config_file}")
                    self.signals.status_signal.emit(f"已移除队员 {member.name} 并删除配置文件")
                else:
                    self.signals.status_signal.emit(f"已移除队员 {member.name}，未找到配置文件")
            except Exception as e:
                print(f"删除配置文件时出错: {str(e)}")
                self.signals.status_signal.emit(f"已移除队员 {member.name}，但删除配置文件失败")
            
            return True
        return False