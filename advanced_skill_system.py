import sys
import os
import cv2
import numpy as np
import time
import threading
import pyautogui
import keyboard
import json
import queue
from datetime import datetime
from PyQt5.QtCore import QObject, pyqtSignal, QRect, QTimer
import pytesseract  # OCR文字识别库
from skill_cycle import Skill, SkillCycleManager, SkillSignals

# 配置pytesseract
try:
    pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'  # Windows
except:
    pass  # 如果不需要设置路径或在其他OS上运行则忽略

class TriggerCondition(QObject):
    """触发条件类
    
    表示技能触发的条件，如颜色匹配、文本匹配或时间条件。
    
    属性:
        condition_type (str): 条件类型，如 'color', 'text', 'time', 'combo'
        name (str): 条件名称
        parameters (dict): 条件参数
        enabled (bool): 是否启用此条件
        parent_skill (Skill): 关联的技能
    """
    
    # 条件匹配信号
    condition_matched = pyqtSignal(str)  # 参数为条件名称
    
    def __init__(self, name, condition_type, parameters=None, parent_skill=None):
        """初始化触发条件
        
        参数:
            name (str): 条件名称
            condition_type (str): 条件类型，支持 'color', 'text', 'time', 'combo'
            parameters (dict, optional): 条件参数
            parent_skill (Skill, optional): 关联的技能
        """
        super().__init__()
        self.name = name
        self.condition_type = condition_type
        self.parameters = parameters or {}
        self.enabled = True
        self.parent_skill = parent_skill
        self.last_check_time = 0.0
        self.last_match_time = 0.0
        self.check_interval = 0.1  # 默认检查间隔（秒）
        
        # 子条件（用于组合条件）
        self.sub_conditions = []
        
        # 条件配置文件路径
        self.config_dir = os.path.dirname(os.path.abspath(__file__))
        self.config_file = os.path.join(self.config_dir, f"condition_{name}_config.json")
        
        # 尝试加载配置
        self.load_config()
    
    def load_config(self):
        """从配置文件加载设置"""
        try:
            if not os.path.exists(self.config_file):
                print(f"未找到{self.name}条件的配置文件，将使用默认设置")
                return
                
            with open(self.config_file, 'r', encoding='utf-8') as f:
                config = json.load(f)
                
                # 加载基本配置
                self.condition_type = config.get('condition_type', self.condition_type)
                self.parameters = config.get('parameters', self.parameters)
                self.enabled = config.get('enabled', self.enabled)
                self.check_interval = config.get('check_interval', self.check_interval)
                
                # 加载子条件
                if 'sub_conditions' in config:
                    for sub_config in config['sub_conditions']:
                        sub_cond = TriggerCondition(
                            sub_config.get('name', 'Unknown'),
                            sub_config.get('condition_type', 'color'),
                            sub_config.get('parameters', {})
                        )
                        self.sub_conditions.append(sub_cond)
                    
        except Exception as e:
            print(f"加载{self.name}条件配置文件时出错: {str(e)}")
    
    def save_config(self):
        """保存设置到配置文件"""
        config = {
            'name': self.name,
            'condition_type': self.condition_type,
            'parameters': self.parameters,
            'enabled': self.enabled,
            'check_interval': self.check_interval,
            'sub_conditions': []
        }
        
        # 保存子条件配置
        for sub_cond in self.sub_conditions:
            sub_config = {
                'name': sub_cond.name,
                'condition_type': sub_cond.condition_type,
                'parameters': sub_cond.parameters,
                'enabled': sub_cond.enabled
            }
            config['sub_conditions'].append(sub_config)
        
        try:
            # 确保配置文件目录存在
            os.makedirs(os.path.dirname(self.config_file), exist_ok=True)
            
            # 使用临时文件来保存配置
            temp_file = self.config_file + '.tmp'
            with open(temp_file, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=4)
            
            # 如果写入成功，则替换原配置文件
            if os.path.exists(self.config_file):
                os.remove(self.config_file)
            os.rename(temp_file, self.config_file)
            
            print(f"{self.name}条件的设置已成功保存")
            return True
            
        except Exception as e:
            print(f"保存{self.name}条件配置文件时出错: {str(e)}")
            return False
    
    def add_sub_condition(self, sub_condition):
        """添加子条件（用于组合条件）
        
        参数:
            sub_condition (TriggerCondition): 子条件
        """
        self.sub_conditions.append(sub_condition)
        self.save_config()
    
    def remove_sub_condition(self, name):
        """移除子条件
        
        参数:
            name (str): 子条件名称
        
        返回:
            bool: 是否成功移除
        """
        for i, cond in enumerate(self.sub_conditions):
            if cond.name == name:
                del self.sub_conditions[i]
                self.save_config()
                return True
        return False
    
    def check_condition(self):
        """检查条件是否满足
        
        返回:
            bool: 是否满足条件
        """
        # 如果条件未启用，总是返回False
        if not self.enabled:
            return False
        
        # 检查间隔控制，避免频繁检查
        current_time = time.time()
        if current_time - self.last_check_time < self.check_interval:
            return False
        
        self.last_check_time = current_time
        
        # 基于条件类型进行检查
        result = False
        
        if self.condition_type == 'color':
            result = self._check_color_condition()
        elif self.condition_type == 'text':
            result = self._check_text_condition()
        elif self.condition_type == 'time':
            result = self._check_time_condition()
        elif self.condition_type == 'combo':
            result = self._check_combo_condition()
        
        # 如果条件满足，更新最后匹配时间并发送信号
        if result:
            self.last_match_time = current_time
            self.condition_matched.emit(self.name)
        
        return result
    
    def _check_color_condition(self):
        """检查颜色条件"""
        try:
            # 获取参数
            x = self.parameters.get('x', 0)
            y = self.parameters.get('y', 0)
            target_color = self.parameters.get('color', [0, 0, 0])  # RGB格式
            tolerance = self.parameters.get('tolerance', 10)
            region = self.parameters.get('region', None)  # 区域检查
            
            # 截取屏幕
            if region:
                x1, y1, x2, y2 = region
                screenshot = pyautogui.screenshot(region=(x1, y1, x2-x1, y2-y1))
                frame = np.array(screenshot)
                # 相对于区域的点位置
                x = x - x1
                y = y - y1
            else:
                screenshot = pyautogui.screenshot()
                frame = np.array(screenshot)
            
            # 确保点在图像范围内
            h, w = frame.shape[:2]
            if x < 0 or x >= w or y < 0 or y >= h:
                return False
            
            # 获取目标点的颜色 (RGB格式)
            pixel_color = frame[y, x]
            
            # 检查颜色是否匹配（考虑容差）
            r_diff = abs(int(pixel_color[0]) - int(target_color[0]))
            g_diff = abs(int(pixel_color[1]) - int(target_color[1]))
            b_diff = abs(int(pixel_color[2]) - int(target_color[2]))
            
            return r_diff <= tolerance and g_diff <= tolerance and b_diff <= tolerance
            
        except Exception as e:
            print(f"检查颜色条件时出错: {str(e)}")
            return False
    
    def _check_text_condition(self):
        """检查文本条件"""
        try:
            # 获取参数
            region = self.parameters.get('region', [0, 0, 100, 50])  # 默认区域
            target_text = self.parameters.get('text', '')
            is_regex = self.parameters.get('is_regex', False)
            
            # 截取屏幕区域
            x1, y1, x2, y2 = region
            screenshot = pyautogui.screenshot(region=(x1, y1, x2-x1, y2-y1))
            
            # 将PIL图像转换为OpenCV格式
            frame = np.array(screenshot)
            frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
            
            # 使用OCR识别文本
            text = pytesseract.image_to_string(frame, lang='eng+chi_sim')
            
            # 检查文本匹配
            if is_regex:
                import re
                return bool(re.search(target_text, text))
            else:
                return target_text.lower() in text.lower()
                
        except Exception as e:
            print(f"检查文本条件时出错: {str(e)}")
            return False
    
    def _check_time_condition(self):
        """检查时间条件"""
        try:
            # 获取参数
            interval = self.parameters.get('interval', 5.0)  # 默认5秒间隔
            offset = self.parameters.get('offset', 0.0)  # 时间偏移
            
            # 检查是否达到时间间隔
            current_time = time.time()
            elapsed = current_time - self.last_match_time - offset
            
            return elapsed >= interval
            
        except Exception as e:
            print(f"检查时间条件时出错: {str(e)}")
            return False
    
    def _check_combo_condition(self):
        """检查组合条件"""
        try:
            # 获取参数
            combo_type = self.parameters.get('combo_type', 'AND')  # AND或OR组合
            
            # 检查子条件
            if not self.sub_conditions:
                return False
                
            if combo_type == 'AND':
                # 所有子条件都必须满足
                return all(cond.check_condition() for cond in self.sub_conditions if cond.enabled)
            elif combo_type == 'OR':
                # 任一子条件满足即可
                return any(cond.check_condition() for cond in self.sub_conditions if cond.enabled)
            else:
                return False
                
        except Exception as e:
            print(f"检查组合条件时出错: {str(e)}")
            return False


class KeyboardSimulator:
    """键盘模拟器
    
    处理各种键盘按键模拟，支持按键组合和精确时间控制。
    """
    
    def __init__(self):
        """初始化键盘模拟器"""
        self.active_keys = set()  # 当前按下的键
    
    def press_key(self, key, delay=0.0):
        """按下按键
        
        参数:
            key (str): 按键名称
            delay (float, optional): 延迟（秒）
        """
        try:
            if delay > 0:
                time.sleep(delay)
                
            # 使用pyautogui按下按键
            pyautogui.keyDown(key)
            self.active_keys.add(key)
            
            return True
            
        except Exception as e:
            print(f"按下按键{key}时出错: {str(e)}")
            return False
    
    def release_key(self, key, delay=0.0):
        """释放按键
        
        参数:
            key (str): 按键名称
            delay (float, optional): 延迟（秒）
        """
        try:
            if delay > 0:
                time.sleep(delay)
                
            # 使用pyautogui释放按键
            pyautogui.keyUp(key)
            self.active_keys.discard(key)
            
            return True
            
        except Exception as e:
            print(f"释放按键{key}时出错: {str(e)}")
            return False
    
    def press_and_release(self, key, press_delay=0.0, hold_time=0.05):
        """按下并释放按键
        
        参数:
            key (str): 按键名称
            press_delay (float, optional): 按下前延迟（秒）
            hold_time (float, optional): 按住时长（秒）
        """
        try:
            # 按下按键
            self.press_key(key, press_delay)
            
            # 等待指定时间
            time.sleep(hold_time)
            
            # 释放按键
            self.release_key(key)
            
            return True
            
        except Exception as e:
            print(f"按下并释放按键{key}时出错: {str(e)}")
            # 确保按键被释放
            try:
                pyautogui.keyUp(key)
                self.active_keys.discard(key)
            except:
                pass
            return False
    
    def press_hotkey(self, keys, sequential=False, interval=0.05):
        """按下热键组合
        
        参数:
            keys (list): 按键列表
            sequential (bool, optional): 是否按顺序按下
            interval (float, optional): 按键间隔（秒）
        """
        try:
            if sequential:
                # 按顺序按下每个键
                for key in keys:
                    self.press_and_release(key, 0, interval)
                return True
            else:
                # 同时按下多个键
                # 按下所有键
                for key in keys:
                    self.press_key(key, 0)
                
                # 等待指定时间
                time.sleep(interval)
                
                # 释放所有键（逆序）
                for key in reversed(keys):
                    self.release_key(key, 0)
                
                return True
                
        except Exception as e:
            print(f"按下热键组合时出错: {str(e)}")
            # 确保所有按键被释放
            for key in keys:
                try:
                    pyautogui.keyUp(key)
                    self.active_keys.discard(key)
                except:
                    pass
            return False
    
    def type_text(self, text, interval=0.05):
        """输入文本
        
        参数:
            text (str): 要输入的文本
            interval (float, optional): 字符间隔（秒）
        """
        try:
            pyautogui.typewrite(text, interval=interval)
            return True
            
        except Exception as e:
            print(f"输入文本时出错: {str(e)}")
            return False
    
    def release_all_keys(self):
        """释放所有按下的按键"""
        try:
            # 复制集合，因为在迭代过程中会修改它
            keys_to_release = set(self.active_keys)
            
            for key in keys_to_release:
                self.release_key(key)
                
            return True
            
        except Exception as e:
            print(f"释放所有按键时出错: {str(e)}")
            return False


class AdvancedSkill(Skill):
    """高级技能类
    
    继承基本技能类，添加触发条件和高级控制功能。
    
    新增属性:
        conditions (list): 触发条件列表
        keyboard_simulator (KeyboardSimulator): 键盘模拟器
        auto_trigger (bool): 是否自动触发（满足条件时）
    """
    
    def __init__(self, name, key, priority=0):
        """初始化高级技能
        
        参数:
            name (str): 技能名称
            key (str): 触发技能的按键
            priority (int): 技能优先级（默认0）
        """
        super().__init__(name, key, priority)
        self.conditions = []  # 触发条件列表
        self.keyboard_simulator = KeyboardSimulator()  # 键盘模拟器
        self.auto_trigger = True  # 默认启用自动触发
        self.key_sequence = [key]  # 按键序列（默认只有一个键）
        self.sequential_press = False  # 是否按顺序按下按键
        
        # 扩展配置加载
        self.load_advanced_config()
    
    def load_advanced_config(self):
        """加载高级配置"""
        try:
            if not os.path.exists(self.config_file):
                return
                
            with open(self.config_file, 'r', encoding='utf-8') as f:
                config = json.load(f)
                
                # 加载高级配置
                self.auto_trigger = config.get('auto_trigger', self.auto_trigger)
                self.key_sequence = config.get('key_sequence', self.key_sequence)
                self.sequential_press = config.get('sequential_press', self.sequential_press)
                
                # 加载条件
                if 'conditions' in config:
                    for cond_config in config['conditions']:
                        condition = TriggerCondition(
                            cond_config.get('name', 'Unknown'),
                            cond_config.get('condition_type', 'color'),
                            cond_config.get('parameters', {}),
                            self
                        )
                        self.conditions.append(condition)
                    
        except Exception as e:
            print(f"加载{self.name}高级技能配置时出错: {str(e)}")
    
    def save_config(self):
        """保存配置，扩展基类方法"""
        # 添加高级配置
        config = {
            'name': self.name,
            'key': self.key,
            'priority': self.priority,
            'cooldown': self.cooldown,
            'threshold': self.threshold,
            'press_delay': self.press_delay,
            'release_delay': self.release_delay,
            'enabled': self.enabled,
            'position': {
                'x1': self.x1,
                'y1': self.y1,
                'x2': self.x2,
                'y2': self.y2
            },
            'img_path': self.img_path,
            # 高级配置
            'auto_trigger': self.auto_trigger,
            'key_sequence': self.key_sequence,
            'sequential_press': self.sequential_press,
            'conditions': []
        }
        
        # 保存条件列表
        for condition in self.conditions:
            cond_config = {
                'name': condition.name,
                'condition_type': condition.condition_type,
                'parameters': condition.parameters,
                'enabled': condition.enabled
            }
            config['conditions'].append(cond_config)
        
        try:
            # 确保配置文件目录存在
            os.makedirs(os.path.dirname(self.config_file), exist_ok=True)
            
            # 使用临时文件来保存配置
            temp_file = self.config_file + '.tmp'
            with open(temp_file, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=4)
            
            # 如果写入成功，则替换原配置文件
            if os.path.exists(self.config_file):
                os.remove(self.config_file)
            os.rename(temp_file, self.config_file)
            
            print(f"{self.name}技能的设置已成功保存")
            return True
            
        except Exception as e:
            print(f"保存{self.name}技能配置文件时出错: {str(e)}")
            return False
    
    def add_condition(self, condition):
        """添加触发条件
        
        参数:
            condition (TriggerCondition): 触发条件
        """
        condition.parent_skill = self
        self.conditions.append(condition)
        self.save_config()
    
    def remove_condition(self, name):
        """移除触发条件
        
        参数:
            name (str): 条件名称
            
        返回:
            bool: 是否成功移除
        """
        for i, cond in enumerate(self.conditions):
            if cond.name == name:
                del self.conditions[i]
                self.save_config()
                return True
        return False
    
    def can_trigger(self):
        """检查是否可以触发技能
        
        返回:
            bool: 是否可触发
        """
        # 检查基本可用性
        if not self.is_available():
            return False
            
        # 如果没有条件，则与基础is_available相同
        if not self.conditions:
            return True
            
        # 检查所有条件
        return all(cond.check_condition() for cond in self.conditions if cond.enabled)
    
    def use_skill(self):
        """使用技能，重写基类方法"""
        if not self.enabled:
            return False
            
        try:
            # 使用按键序列
            if len(self.key_sequence) > 1:
                success = self.keyboard_simulator.press_hotkey(
                    self.key_sequence,
                    self.sequential_press,
                    self.press_delay
                )
            else:
                # 单个按键，使用基本的按下/释放
                # 按下按键
                self.keyboard_simulator.press_key(self.key)
                # 等待按下延迟
                time.sleep(self.press_delay)
                # 释放按键
                self.keyboard_simulator.release_key(self.key)
                # 等待释放延迟
                time.sleep(self.release_delay)
                success = True
            
            # 更新最后使用时间
            if success:
                self.last_used_time = time.time()
            
            return success
            
        except Exception as e:
            print(f"使用{self.name}技能时出错: {str(e)}")
            # 确保所有按键被释放
            self.keyboard_simulator.release_all_keys()
            return False


class AdvancedSkillManager(SkillCycleManager):
    """高级技能管理器
    
    扩展基本技能循环管理器，添加基于条件的触发和高级功能。
    
    新增属性:
        condition_check_interval (float): 条件检查间隔（秒）
        condition_thread (Thread): 条件检查线程
    """
    
    def __init__(self):
        """初始化高级技能管理器"""
        super().__init__()
        self.condition_check_interval = 0.05  # 默认条件检查间隔
        self.condition_thread = None
        self.condition_running = False
        
        # 其他加载操作已在父类完成
    
    def load_config(self):
        """加载配置，扩展父类方法"""
        super().load_config()
        
        try:
            config_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "advanced_skill_manager_config.json")
            
            if not os.path.exists(config_file):
                print("未找到高级技能管理器配置文件，将使用默认设置")
                return
                
            with open(config_file, 'r', encoding='utf-8') as f:
                config = json.load(f)
                
                # 加载高级设置
                self.condition_check_interval = config.get('condition_check_interval', self.condition_check_interval)
                
        except Exception as e:
            print(f"加载高级技能管理器配置文件时出错: {str(e)}")
    
    def save_config(self):
        """保存配置，扩展父类方法"""
        # 先调用父类方法
        super().save_config()
        
        # 保存高级设置
        config_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "advanced_skill_manager_config.json")
        
        config = {
            'condition_check_interval': self.condition_check_interval
        }
        
        try:
            # 确保配置文件目录存在
            os.makedirs(os.path.dirname(config_file), exist_ok=True)
            
            # 使用临时文件来保存配置
            temp_file = config_file + '.tmp'
            with open(temp_file, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=4)
            
            # 如果写入成功，则替换原配置文件
            if os.path.exists(config_file):
                os.remove(config_file)
            os.rename(temp_file, config_file)
            
            print("高级技能管理器设置已成功保存")
            return True
            
        except Exception as e:
            print(f"保存高级技能管理器配置文件时出错: {str(e)}")
            return False
    
    def add_skill(self, skill):
        """添加技能，支持AdvancedSkill"""
        super().add_skill(skill)
    
    def start_condition_check(self):
        """开始条件检查线程"""
        if self.condition_running:
            return
            
        self.condition_running = True
        
        # 创建并启动条件检查线程
        self.condition_thread = threading.Thread(target=self._condition_check_loop, daemon=True)
        self.condition_thread.start()
        
        self.signals.status_signal.emit("条件检查已启动")
    
    def stop_condition_check(self):
        """停止条件检查线程"""
        if not self.condition_running:
            return
            
        self.condition_running = False
        
        if self.condition_thread and self.condition_thread.is_alive():
            # 等待线程结束
            self.condition_thread.join(1.0)
            
        self.condition_thread = None
        self.signals.status_signal.emit("条件检查已停止")
    
    def _condition_check_loop(self):
        """条件检查线程主循环"""
        while self.condition_running:
            # 检查每个启用的技能的条件
            for skill in self.skills:
                if not skill.enabled or not isinstance(skill, AdvancedSkill):
                    continue
                    
                # 检查条件并可能触发技能
                if skill.auto_trigger and skill.can_trigger():
                    if skill.use_skill():
                        self.signals.status_signal.emit(f"条件触发技能: {skill.name}")
                        self.signals.skill_used_signal.emit(skill.name)
            
            # 等待一段时间后再检查
            time.sleep(self.condition_check_interval)
    
    def start_cycle(self):
        """开始技能循环，同时启动条件检查"""
        super().start_cycle()
        self.start_condition_check()
    
    def stop_cycle(self):
        """停止技能循环，同时停止条件检查"""
        super().stop_cycle()
        self.stop_condition_check()

# 创建单例实例
advanced_skill_manager = AdvancedSkillManager() 