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

# 动态导入带空格的模块
module_name = "Zhu Xian World Health Bar Test(choice box)"
module_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Zhu Xian World Health Bar Test(choice box).py")
spec = importlib.util.spec_from_file_location(module_name, module_path)
health_bar_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(health_bar_module)

# 从模块中获取需要的函数
get_hp_percentage = health_bar_module.get_hp_percentage

class MonitorSignals(QObject):
    """定义监控信号类，用于在线程间传递信号"""
    update_signal = pyqtSignal(object)  # 更新血量信号，传递队员血量列表
    status_signal = pyqtSignal(str)   # 状态信号，传递监控状态信息

class HealthMonitor:
    """血条监控类
    
    负责管理血条监控功能，包括设置血条位置、颜色和实时监控。
    
    属性:
        team: 队伍对象，包含所有队员信息
        monitoring: 是否正在监控
        monitor_thread: 监控线程
        update_interval: 监控更新间隔（秒）
        signals: 监控信号对象
    """
    
    def __init__(self, team):
        """初始化血条监控
        
        参数:
            team: 队伍对象
        """
        self.team = team
        self.monitoring = False
        self.monitor_thread = None
        self.update_interval = 0.5  # 默认更新间隔0.5秒
        self.signals = MonitorSignals()
        
        # 快捷键设置（默认值）
        self.start_monitoring_hotkey = 'f9'
        self.stop_monitoring_hotkey = 'f10'
        self.hotkey_handlers = []  # 存储快捷键处理器的引用
        
        # 自动选择低血量队友相关设置
        self.auto_select_enabled = False
        self.health_threshold = 50.0  # 默认50%以下触发自动选择
        self.cooldown_time = 2.0  # 默认冷却时间2秒
        self.last_select_time = 0  # 上次自动选择的时间
        self.priority_roles = []  # 优先选择的职业列表
        
        # 新增：职业优先级
        self.priority_profession = None  # 默认无优先职业
        
        # 加载快捷键设置
        self.load_hotkey_config()
        self.load_auto_select_config()  # 加载自动选择配置
        
        # 注册全局快捷键
        self.register_hotkeys()
    
    def load_hotkey_config(self):
        """加载快捷键配置"""
        try:
            config_dir = os.path.dirname(os.path.abspath(__file__))
            config_file = os.path.join(config_dir, "hotkeys_config.json")
            
            if not os.path.exists(config_file):
                # 创建默认配置
                self.save_hotkey_config()
                return
                
            with open(config_file, 'r', encoding='utf-8') as f:
                config = json.load(f)
                
                if 'hotkeys' in config:
                    hotkeys = config['hotkeys']
                    self.start_monitoring_hotkey = hotkeys.get('start_monitoring', 'f9')
                    self.stop_monitoring_hotkey = hotkeys.get('stop_monitoring', 'f10')
                    print(f"已加载快捷键配置: 开始监控={self.start_monitoring_hotkey}, 停止监控={self.stop_monitoring_hotkey}")
        
        except Exception as e:
            print(f"加载快捷键配置失败: {str(e)}")
            # 使用默认值
    
    def save_hotkey_config(self):
        """保存快捷键配置"""
        temp_file = None
        
        try:
            config_dir = os.path.dirname(os.path.abspath(__file__))
            config_file = os.path.join(config_dir, "hotkeys_config.json")
            
            config = {
                'hotkeys': {
                    'start_monitoring': self.start_monitoring_hotkey,
                    'stop_monitoring': self.stop_monitoring_hotkey
                }
            }
            
            # 使用临时文件保存
            import uuid
            temp_file = config_file + f'.tmp.{uuid.uuid4().hex[:8]}'
            with open(temp_file, 'w', encoding='utf-8') as f:
                json.dump(config, f, ensure_ascii=False, indent=4)
            
            # 检查临时文件是否正确创建
            if not os.path.exists(temp_file):
                print(f"临时配置文件未能创建: {temp_file}")
                return False
                
            # 如果保存成功，替换原文件
            if os.path.exists(config_file):
                # 在Windows上，有时需要多次尝试删除文件
                max_attempts = 3
                for attempt in range(max_attempts):
                    try:
                        os.remove(config_file)
                        break
                    except Exception as e:
                        print(f"尝试 {attempt+1}/{max_attempts} 删除原配置文件失败: {str(e)}")
                        time.sleep(0.1)
                        if attempt == max_attempts - 1:  # 最后一次尝试
                            print(f"无法删除原配置文件，将尝试直接重命名")
            
            # 重命名临时文件为正式配置文件
            try:
                os.rename(temp_file, config_file)
            except Exception as e:
                print(f"重命名临时文件失败: {str(e)}")
                # 如果重命名失败，但临时文件存在，尝试复制内容
                if os.path.exists(temp_file):
                    try:
                        with open(temp_file, 'r', encoding='utf-8') as src:
                            content = src.read()
                        with open(config_file, 'w', encoding='utf-8') as dest:
                            dest.write(content)
                        print(f"通过复制内容方式保存配置")
                        # 尝试删除临时文件
                        try:
                            os.remove(temp_file)
                        except:
                            pass
                    except Exception as copy_err:
                        print(f"复制配置内容失败: {str(copy_err)}")
                        return False
                else:
                    return False
            
            print(f"已成功保存快捷键配置到: {config_file}")
            return True
            
        except Exception as e:
            print(f"保存快捷键配置失败: {str(e)}")
            # 如果临时文件存在，清理它
            if temp_file and os.path.exists(temp_file):
                try:
                    os.remove(temp_file)
                except:
                    pass
            return False
    
    def register_hotkeys(self):
        """注册全局快捷键"""
        try:
            # 清除之前的快捷键监听器
            self.unregister_hotkeys()
            
            # 等待一小段时间，确保旧的快捷键已经被完全注销
            time.sleep(0.2)
            
            # 存储快捷键的引用，以便于后续注销
            self.hotkey_handlers = []
            
            # 注册开始监控快捷键
            try:
                start_handler = keyboard.add_hotkey(
                    self.start_monitoring_hotkey, 
                    self.start_monitoring, 
                    suppress=False  # 不阻止按键传递给其他应用程序
                )
                self.hotkey_handlers.append(start_handler)
                print(f"已注册开始监控快捷键: {self.start_monitoring_hotkey}")
            except Exception as e:
                print(f"注册开始监控快捷键失败: {str(e)}")
                return False
            
            # 注册停止监控快捷键
            try:
                stop_handler = keyboard.add_hotkey(
                    self.stop_monitoring_hotkey, 
                    self.stop_monitoring, 
                    suppress=False  # 不阻止按键传递给其他应用程序
                )
                self.hotkey_handlers.append(stop_handler)
                print(f"已注册停止监控快捷键: {self.stop_monitoring_hotkey}")
            except Exception as e:
                print(f"注册停止监控快捷键失败: {str(e)}")
                # 如果第二个注册失败，注销第一个
                if len(self.hotkey_handlers) > 0:
                    try:
                        keyboard.unhook(self.hotkey_handlers[0])
                    except:
                        pass
                return False
            
            self.signals.status_signal.emit(f"已注册快捷键: 开始监控={self.start_monitoring_hotkey}, 停止监控={self.stop_monitoring_hotkey}")
            print(f"已成功注册所有快捷键: 开始监控={self.start_monitoring_hotkey}, 停止监控={self.stop_monitoring_hotkey}")
            return True
            
        except Exception as e:
            self.signals.status_signal.emit(f"注册快捷键失败: {str(e)}")
            print(f"注册快捷键失败: {str(e)}")
            return False
    
    def unregister_hotkeys(self):
        """注销全局快捷键"""
        try:
            # 注销之前存储的快捷键处理器
            if hasattr(self, 'hotkey_handlers') and self.hotkey_handlers:
                for handler in self.hotkey_handlers:
                    try:
                        keyboard.unhook(handler)
                    except:
                        pass
                self.hotkey_handlers = []
                print("已注销所有快捷键")
            
            # 尝试清除指定热键
            try:
                # 尝试直接使用remove_hotkey方法（如果存在）
                if hasattr(keyboard, 'remove_hotkey'):
                    keyboard.remove_hotkey(self.start_monitoring_hotkey)
                    keyboard.remove_hotkey(self.stop_monitoring_hotkey)
                # 或者通过_listener访问（如果存在）
                elif hasattr(keyboard, '_listener') and hasattr(keyboard._listener, 'remove_hotkey'):
                    keyboard._listener.remove_hotkey(self.start_monitoring_hotkey)
                    keyboard._listener.remove_hotkey(self.stop_monitoring_hotkey)
            except:
                # 忽略可能的错误
                pass
                
        except Exception as e:
            print(f"注销快捷键失败: {str(e)}")
            # 即使失败也不抛出异常，让程序可以继续运行
    
    def set_hotkeys(self, start_key, stop_key):
        """设置新的快捷键
        
        参数:
            start_key: 开始监控的快捷键
            stop_key: 停止监控的快捷键
            
        返回:
            bool: 是否设置成功
        """
        try:
            # 检查快捷键是否有效
            if not start_key or not stop_key:
                self.signals.status_signal.emit("快捷键不能为空")
                return False
            
            # 先注销当前的快捷键
            self.unregister_hotkeys()
            
            # 等待一小段时间，确保旧的快捷键已经被完全注销
            QApplication.processEvents()  # 处理等待的事件
            time.sleep(0.3)
            
            # 保存新的快捷键设置
            self.start_monitoring_hotkey = start_key
            self.stop_monitoring_hotkey = stop_key
            
            # 保存到配置文件
            success = self.save_hotkey_config()
            if not success:
                self.signals.status_signal.emit("保存快捷键配置失败")
                return False
            
            # 重新注册快捷键
            success = self.register_hotkeys()
            if not success:
                self.signals.status_signal.emit("注册新快捷键失败")
                return False
            
            self.signals.status_signal.emit(f"快捷键设置已更新: 开始监控={start_key}, 停止监控={stop_key}")
            return True
            
        except Exception as e:
            self.signals.status_signal.emit(f"设置快捷键失败: {str(e)}")
            return False
            
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
    
    def start_monitoring(self):
        """开始监控"""
        # 如果已经在监控中，只显示消息不做其他操作
        if self.monitoring:
            import inspect
            caller_frame = inspect.currentframe().f_back
            caller_name = caller_frame.f_code.co_name if caller_frame else ""
            if 'record_hook' in caller_name or caller_name == "":
                self.signals.status_signal.emit("监控已经在运行中")
            return False
        
        if not self.team.members:
            self.signals.status_signal.emit("没有队员可以监控")
            return False
        
        incomplete_members = []
        for member in self.team.members:
            if member.x1 == 100 and member.y1 == 100 and member.x2 == 300 and member.y2 == 120:
                incomplete_members.append(f"{member.name} (未设置血条位置)")
        
        if incomplete_members:
            message = "以下队员设置不完整，请先完成设置:\n" + "\n".join(incomplete_members)
            self.signals.status_signal.emit(message)
            return False
        
        self.monitoring = True
        self.monitor_thread = threading.Thread(target=self._monitor_loop)
        self.monitor_thread.daemon = True
        self.monitor_thread.start()
        
        self.signals.status_signal.emit("监控已启动")
        
        # 尝试立即获取并发送一次初始血量数据
        try:
            print("监控启动后，尝试立即发送初始血量数据...")
            initial_results = self.team.update_all_health()
            print(f"获取到的初始血量数据: {initial_results}")
            self.signals.update_signal.emit(initial_results)
        except Exception as e:
            print(f"发送初始血量数据时出错: {str(e)}")
            self.signals.status_signal.emit(f"发送初始血量失败: {str(e)}")
            
        try:
            main_window = next((obj for obj in QApplication.topLevelWidgets() if isinstance(obj, QMainWindow)), None)
            if main_window and hasattr(main_window, 'play_speech'):
                main_window.play_speech("监控已启动，开始实时跟踪队友状态")
        except Exception as e:
            print(f"播放开始监控语音提示失败: {str(e)}")
            
        return True
    
    def stop_monitoring(self):
        """停止监控"""
        # 如果没有在监控中，只显示消息不做其他操作
        if not self.monitoring:
            # 只在通过快捷键触发时显示消息（减少重复消息）
            import inspect
            caller_frame = inspect.currentframe().f_back
            caller_name = caller_frame.f_code.co_name if caller_frame else ""
            if 'record_hook' in caller_name or caller_name == "":  # 由快捷键触发
                self.signals.status_signal.emit("监控未在运行")
            return False
        
        self.monitoring = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=1.0)
            self.monitor_thread = None
        
        # 发送清除监控日志的信号和状态信号
        self.signals.update_signal.emit([])
        self.signals.status_signal.emit("监控已停止")
        
        # 播放语音提示（如果主窗口有TTS功能）
        try:
            # 尝试获取主窗口对象并播放语音
            main_window = next((obj for obj in QApplication.topLevelWidgets() if isinstance(obj, QMainWindow)), None)
            if main_window and hasattr(main_window, 'play_speech'):
                main_window.play_speech("监控已停止")
        except Exception as e:
            print(f"播放停止监控语音提示失败: {str(e)}")
            
        return True
    
    def release_resources(self):
        """释放资源，确保程序关闭时正确清理"""
        print("开始释放资源...")
        
        # 注销所有快捷键
        try:
            print("正在注销快捷键...")
            self.unregister_hotkeys()
            print("快捷键注销完成")
        except Exception as e:
            print(f"注销快捷键时出错: {str(e)}")
        
        # 停止监控
        try:
            if self.monitoring:
                print("正在停止监控...")
                # 直接设置标志而不调用stop_monitoring方法，避免发送不必要的信号
                self.monitoring = False
                if self.monitor_thread and self.monitor_thread.is_alive():
                    print("等待监控线程结束...")
                    self.monitor_thread.join(timeout=2.0)
                    if self.monitor_thread.is_alive():
                        print("监控线程未能在指定时间内结束")
                    else:
                        print("监控线程已结束")
                self.monitor_thread = None
                print("监控已停止")
        except Exception as e:
            print(f"停止监控时出错: {str(e)}")
            
        print("资源释放完成")
    
    def load_auto_select_config(self):
        """加载自动选择配置"""
        try:
            config_dir = os.path.dirname(os.path.abspath(__file__))
            config_file = os.path.join(config_dir, "auto_select_config.json")
            
            if not os.path.exists(config_file):
                # 创建默认配置
                self.save_auto_select_config()
                return
                
            with open(config_file, 'r', encoding='utf-8') as f:
                config = json.load(f)
                
                if 'auto_select' in config:
                    auto_select = config['auto_select']
                    self.auto_select_enabled = auto_select.get('enabled', False)
                    self.health_threshold = auto_select.get('health_threshold', 50.0)
                    self.cooldown_time = auto_select.get('cooldown_time', 2.0)
                    self.priority_roles = auto_select.get('priority_roles', [])
                    self.priority_profession = auto_select.get('priority_profession', None)
                    print(f"已加载自动选择配置: 启用={self.auto_select_enabled}, 血量阈值={self.health_threshold}, 冷却时间={self.cooldown_time}")
        
        except Exception as e:
            print(f"加载自动选择配置失败: {str(e)}")
            # 使用默认值
    
    def save_auto_select_config(self):
        """保存自动选择配置"""
        try:
            config_dir = os.path.dirname(os.path.abspath(__file__))
            config_file = os.path.join(config_dir, "auto_select_config.json")
            
            config = {
                'auto_select': {
                    'enabled': self.auto_select_enabled,
                    'health_threshold': self.health_threshold,
                    'cooldown_time': self.cooldown_time,
                    'priority_roles': self.priority_roles,
                    'priority_profession': self.priority_profession
                }
            }
            
            with open(config_file, 'w', encoding='utf-8') as f:
                json.dump(config, f, ensure_ascii=False, indent=4)
            
            print(f"已成功保存自动选择配置")
            return True
            
        except Exception as e:
            print(f"保存自动选择配置失败: {str(e)}")
            return False
    
    def set_auto_select_settings(self, enabled, threshold, cooldown, priority_roles):
        """设置自动选择参数
        
        参数:
            enabled (bool): 是否启用自动选择
            threshold (float): 血量阈值
            cooldown (float): 冷却时间
            priority_roles (list): 优先职业列表
        """
        self.auto_select_enabled = enabled
        self.health_threshold = threshold
        self.cooldown_time = cooldown
        self.priority_roles = priority_roles
        
        # 保存配置
        success = self.save_auto_select_config()
        if success:
            self.signals.status_signal.emit(f"自动选择设置已更新: 启用={enabled}, 血量阈值={threshold}%, 冷却时间={cooldown}秒")
        else:
            self.signals.status_signal.emit(f"自动选择设置已更新，但保存配置失败")
        
        return success
    
    def check_right_button(self):
        """检查鼠标右键状态
        
        返回:
            bool: 右键是否按下
        """
        return win32api.GetKeyState(win32con.VK_RBUTTON) < 0  # 负值表示按键被按下
    
    def get_priority_score(self, member):
        """计算队友的优先级分数
        
        参数:
            member (TeamMember): 队友对象
            
        返回:
            float: 优先级分数，值越小优先级越高
        """
        # 基础分数：血量百分比
        score = member.health_percentage
        
        # 如果该队员的职业是当前设置的单个优先职业，则给予分数加成（降低分数以提高优先级）
        if self.priority_profession and member.profession == self.priority_profession:
            score -= 10  # 优先职业的血量可以高10%也会被优先选择
        
        return score
    
    def auto_select_low_health(self):
        """自动选择低血量队友"""
        # 如果功能未启用或正在冷却中，直接返回
        if not self.auto_select_enabled:
            return
            
        current_time = time.time()
        if current_time - self.last_select_time < self.cooldown_time:
            return
            
        # 如果鼠标右键正在按下，不执行自动选择
        if self.check_right_button():
            return
            
        # 筛选血量低于阈值的存活队友（必须是存活状态且血量大于0）
        low_health_members = [member for member in self.team.members 
                             if member.is_alive and member.health_percentage > 0 and 
                             member.health_percentage < self.health_threshold]
                             
        if not low_health_members:
            return  # 没有低血量队友
            
        # 根据优先级规则排序
        low_health_members.sort(key=self.get_priority_score)
        
        # 选择优先级最高的队友
        target_member = low_health_members[0]
        
        # 记录当前鼠标位置
        original_x, original_y = pyautogui.position()
        
        try:
            # 计算血条中心点
            target_x = (target_member.x1 + target_member.x2) // 2
            target_y = (target_member.y1 + target_member.y2) // 2
            
            # 移动鼠标并点击
            pyautogui.moveTo(target_x, target_y, duration=0.1)
            pyautogui.click()
            
            # 更新最后选择时间
            self.last_select_time = current_time
            
            # 记录日志
            self.signals.status_signal.emit(f"自动选择了 {target_member.name} (血量: {target_member.health_percentage:.1f}%)")
            
            # 返回原始鼠标位置
            pyautogui.moveTo(original_x, original_y, duration=0.1)
            
        except Exception as e:
            print(f"自动选择队友时出错: {str(e)}")
            # 确保鼠标返回原位
            try:
                pyautogui.moveTo(original_x, original_y, duration=0.1)
            except:
                pass
    
    def _monitor_loop(self):
        """监控循环，在单独的线程中运行"""
        error_count = 0  # 错误计数器
        max_errors = 3   # 最大允许错误次数
        
        # 添加调试输出
        print("监控线程已启动")
        
        while self.monitoring:
            try:
                # 更新所有队员的血量
                results = self.team.update_all_health()
                
                # 调试输出
                print(f"监控线程获取到血量数据: {results}")
                
                # 发送更新信号 - 确保在UI线程中使用正确格式的数据
                # 确保数据是元组列表格式: [(名称, 血量百分比, 是否存活), ...]
                self.signals.update_signal.emit(results)
                
                # 检查是否有队员血量低于警戒值
                low_health_members = []
                for name, hp, is_alive in results:
                    if is_alive and hp < 30:  # 血量低于30%发出警告
                        low_health_members.append(f"{name}({hp:.1f}%)")
                
                if low_health_members:
                    warning_msg = f"警告: {', '.join(low_health_members)} 血量低于30%!"
                    self.signals.status_signal.emit(warning_msg)
                
                # 尝试执行自动选择
                self.auto_select_low_health()
                
                # 重置错误计数
                error_count = 0
                
                # 等待指定的间隔时间
                time.sleep(self.update_interval)
                
            except Exception as e:
                error_count += 1
                error_msg = f"监控出错 ({error_count}/{max_errors}): {str(e)}"
                print(error_msg)  # 同时输出到控制台便于调试
                self.signals.status_signal.emit(error_msg)
                
                # 如果连续错误次数超过阈值，停止监控
                if error_count >= max_errors:
                    self.signals.status_signal.emit("由于连续错误，监控已自动停止")
                    self.monitoring = False
                    break
                
                # 出错后等待稍长时间再重试
                time.sleep(1.0)
        
        # 线程结束时发送状态更新
        print("监控线程已结束")
        self.signals.status_signal.emit("监控线程已结束")

    def capture_health_bar(self, member):
        """截取指定队友的血条区域
        
        参数:
            member: TeamMember对象
            
        返回:
            numpy.ndarray: 血条区域的截图
        """
        try:
            # 获取血条区域坐标
            x1, y1 = member.x1, member.y1
            x2, y2 = member.x2, member.y2
            
            # 将坐标向内收缩1-2像素，避免包含边框
            x1 += 2
            y1 += 2
            x2 -= 2
            y2 -= 2
            
            # 确保区域大小合理
            if x2 <= x1 or y2 <= y1:
                print(f"警告: {member.name}的血条区域无效: ({x1}, {y1}, {x2}, {y2})")
                return None
            
            # 计算宽度和高度
            width = x2 - x1
            height = y2 - y1
            
            # 使用pyautogui截取屏幕指定区域
            screenshot = pyautogui.screenshot(region=(x1, y1, width, height))
            
            # 转换为OpenCV格式(BGR)
            frame = np.array(screenshot)
            frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
            
            return frame
        except Exception as e:
            print(f"截取{member.name}的血条区域时出错: {str(e)}")
            return None