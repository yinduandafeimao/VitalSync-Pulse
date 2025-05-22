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
from skill_data_models import config_manager, Skill as DataSkill, Action
import uuid

class SkillSignals(QObject):
    """技能信号类，用于在线程间传递信号"""
    status_signal = pyqtSignal(str)   # 状态信号，传递监控状态信息
    skill_used_signal = pyqtSignal(str)  # 技能使用信号，传递已使用的技能名称

class Skill:
    """技能类
    
    表示一个游戏中的技能，包含技能位置、图标和CD时间等属性。
    
    属性:
        name (str): 技能名称
        key (str): 触发技能的按键
        priority (int): 技能优先级（越小越优先）
        cooldown (float): 冷却时间（秒）
        x1, y1, x2, y2 (int): 技能图标位置坐标
        img_path (str): 技能图标图像路径
        template (numpy.ndarray): 技能模板图像
        threshold (float): 图像匹配阈值
        last_used_time (float): 上次使用时间戳
        press_delay (float): 按下延迟（秒）
        release_delay (float): 弹起延迟（秒）
        enabled (bool): 是否启用此技能
    """
    
    def __init__(self, name, key, priority=0):
        """初始化技能
        
        参数:
            name (str): 技能名称
            key (str): 触发技能的按键
            priority (int): 技能优先级（默认0）
        """
        self.name = name
        self.key = key
        self.priority = priority
        self.cooldown = 0.0  # 默认无冷却时间
        self.x1 = 0
        self.y1 = 0
        self.x2 = 0
        self.y2 = 0
        self.img_path = ""
        self.template = None
        self.threshold = 0.7  # 默认匹配阈值
        self.last_used_time = 0.0
        self.press_delay = 0.0
        self.release_delay = 0.05  # 默认50ms弹起延迟
        self.enabled = True
        
        # 配置文件路径
        self.config_dir = os.path.dirname(os.path.abspath(__file__))
        self.config_file = os.path.join(self.config_dir, f"skill_{name}_config.json")
        
        # 尝试加载配置
        self.load_config()
    
    def load_config(self):
        """从配置文件加载设置"""
        try:
            if not os.path.exists(self.config_file):
                print(f"未找到{self.name}技能的配置文件，将使用默认设置")
                return
                
            with open(self.config_file, 'r', encoding='utf-8') as f:
                config = json.load(f)
                
                # 加载基本配置
                self.key = config.get('key', self.key)
                self.priority = config.get('priority', self.priority)
                self.cooldown = config.get('cooldown', self.cooldown)
                self.threshold = config.get('threshold', self.threshold)
                self.press_delay = config.get('press_delay', self.press_delay)
                self.release_delay = config.get('release_delay', self.release_delay)
                self.enabled = config.get('enabled', self.enabled)
                
                # 加载图标位置
                if 'position' in config:
                    self.x1 = config['position'].get('x1', self.x1)
                    self.y1 = config['position'].get('y1', self.y1)
                    self.x2 = config['position'].get('x2', self.x2)
                    self.y2 = config['position'].get('y2', self.y2)
                
                # 加载图像路径
                self.img_path = config.get('img_path', self.img_path)
                if self.img_path and os.path.exists(self.img_path):
                    self.template = cv2.imread(self.img_path)
                    
        except Exception as e:
            print(f"加载{self.name}技能配置文件时出错: {str(e)}")
    
    def save_config(self):
        """保存设置到配置文件"""
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
            'img_path': self.img_path
        }
        
        try:
            # 确保配置文件目录存在
            os.makedirs(os.path.dirname(self.config_file), exist_ok=True)
            
            # 使用临时文件来保存配置，防止写入过程中出错
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
    
    def set_icon_position(self, x1, y1, x2, y2):
        """设置技能图标位置
        
        参数:
            x1, y1 (int): 左上角坐标
            x2, y2 (int): 右下角坐标
        """
        self.x1 = x1
        self.y1 = y1
        self.x2 = x2
        self.y2 = y2
        self.save_config()
    
    def capture_icon_template(self):
        """截取技能图标作为模板"""
        try:
            # 截取技能图标区域
            screenshot = pyautogui.screenshot(region=(self.x1, self.y1, self.x2-self.x1, self.y2-self.y1))
            frame = np.array(screenshot)
            # 转换为OpenCV BGR格式
            frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
            
            # 保存模板图像
            os.makedirs('skill_icons', exist_ok=True)
            current_time = datetime.now().strftime("%Y%m%d%H%M%S")
            img_path = f"skill_icons/{self.name}_{current_time}.png"
            cv2.imwrite(img_path, frame)
            
            self.img_path = img_path
            self.template = frame
            self.save_config()
            
            return True
            
        except Exception as e:
            print(f"截取{self.name}技能图标时出错: {str(e)}")
            return False
    
    def is_available(self):
        """检查技能是否可用（不在CD中）"""
        if not self.enabled:
            return False
            
        # 检查冷却时间
        if time.time() - self.last_used_time < self.cooldown:
            return False
        
        # 如果没有模板图像，则假设技能可用
        if self.template is None:
            return True
        
        try:
            # 截取技能图标区域
            screenshot = pyautogui.screenshot(region=(self.x1, self.y1, self.x2-self.x1, self.y2-self.y1))
            frame = np.array(screenshot)
            # 转换为OpenCV BGR格式
            frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
            
            # 使用模板匹配
            result = cv2.matchTemplate(frame, self.template, cv2.TM_CCOEFF_NORMED)
            _, max_val, _, _ = cv2.minMaxLoc(result)
            
            # 返回是否匹配
            return max_val >= self.threshold
            
        except Exception as e:
            print(f"检查{self.name}技能是否可用时出错: {str(e)}")
            return False
    
    def use_skill(self):
        """使用技能"""
        if not self.enabled:
            return False
            
        try:
            # 按下按键
            pyautogui.keyDown(self.key)
            # 等待按下延迟
            time.sleep(self.press_delay)
            # 释放按键
            pyautogui.keyUp(self.key)
            # 等待释放延迟
            time.sleep(self.release_delay)
            
            # 更新最后使用时间
            self.last_used_time = time.time()
            
            return True
            
        except Exception as e:
            print(f"使用{self.name}技能时出错: {str(e)}")
            return False
    
    def __str__(self):
        """获取技能信息字符串"""
        status = "启用" if self.enabled else "禁用"
        cd_status = ""
        if self.cooldown > 0:
            remaining = max(0, self.cooldown - (time.time() - self.last_used_time))
            if remaining > 0:
                cd_status = f"(冷却中: {remaining:.1f}s)"
                
        return f"{self.name} - 按键:{self.key} 优先级:{self.priority} 冷却时间:{self.cooldown}s {cd_status} [{status}]"


class SkillCycleManager:
    """技能循环管理器
    
    负责管理多个技能，并按照优先级和冷却时间自动循环使用技能。
    
    属性:
        skills (list): 技能列表
        running (bool): 是否正在运行
        cycle_thread (Thread): 循环线程
        update_interval (float): 更新间隔（秒）
        signals (SkillSignals): 信号对象
    """
    
    def __init__(self):
        """初始化技能循环管理器"""
        self.skills = []
        self.running = False
        self.cycle_thread = None
        self.update_interval = 0.1  # 默认更新间隔0.1秒
        self.signals = SkillSignals()
        
        # 快捷键设置
        self.start_hotkey = 'ctrl+f11'
        self.stop_hotkey = 'ctrl+f12'
        self.hotkey_handlers = []
        
        # 加载配置
        self.load_config()
        
        # 注册快捷键
        self.register_hotkeys()
    
    def load_config(self):
        """加载配置"""
        try:
            config_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "skill_cycle_config.json")
            
            if not os.path.exists(config_file):
                print("未找到技能循环配置文件，将使用默认设置")
                return
                
            with open(config_file, 'r', encoding='utf-8') as f:
                config = json.load(f)
                
                # 基本设置
                self.update_interval = config.get('update_interval', self.update_interval)
                self.start_hotkey = config.get('start_hotkey', self.start_hotkey)
                self.stop_hotkey = config.get('stop_hotkey', self.stop_hotkey)
                
                # 加载技能列表
                if 'skills' in config:
                    self.skills = []
                    for skill_config in config['skills']:
                        skill = Skill(
                            skill_config.get('name', 'Unknown'),
                            skill_config.get('key', 'q'),
                            skill_config.get('priority', 0)
                        )
                        self.skills.append(skill)
                        
        except Exception as e:
            print(f"加载技能循环配置文件时出错: {str(e)}")
    
    def save_config(self):
        """保存配置"""
        config_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "skill_cycle_config.json")
        
        config = {
            'update_interval': self.update_interval,
            'start_hotkey': self.start_hotkey,
            'stop_hotkey': self.stop_hotkey,
            'skills': []
        }
        
        # 保存技能列表
        for skill in self.skills:
            skill_config = {
                'name': skill.name,
                'key': skill.key,
                'priority': skill.priority
            }
            config['skills'].append(skill_config)
        
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
            
            print("技能循环设置已成功保存")
            return True
            
        except Exception as e:
            print(f"保存技能循环配置文件时出错: {str(e)}")
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
            
            # 注册开始循环快捷键
            try:
                start_handler = keyboard.add_hotkey(
                    self.start_hotkey, 
                    self.start_cycle, 
                    suppress=False
                )
                self.hotkey_handlers.append(start_handler)
                print(f"已注册开始技能循环快捷键: {self.start_hotkey}")
            except Exception as e:
                print(f"注册开始技能循环快捷键失败: {str(e)}")
                return False
            
            # 注册停止循环快捷键
            try:
                stop_handler = keyboard.add_hotkey(
                    self.stop_hotkey, 
                    self.stop_cycle, 
                    suppress=False
                )
                self.hotkey_handlers.append(stop_handler)
                print(f"已注册停止技能循环快捷键: {self.stop_hotkey}")
            except Exception as e:
                print(f"注册停止技能循环快捷键失败: {str(e)}")
                # 如果第二个注册失败，注销第一个
                if len(self.hotkey_handlers) > 0:
                    try:
                        keyboard.unhook(self.hotkey_handlers[0])
                    except:
                        pass
                return False
            
            self.signals.status_signal.emit(f"已注册技能循环快捷键: 开始={self.start_hotkey}, 停止={self.stop_hotkey}")
            return True
            
        except Exception as e:
            self.signals.status_signal.emit(f"注册技能循环快捷键失败: {str(e)}")
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
                print("已注销所有技能循环快捷键")
                
        except Exception as e:
            print(f"注销技能循环快捷键失败: {str(e)}")
    
    def set_hotkeys(self, start_key, stop_key):
        """设置新的快捷键
        
        参数:
            start_key (str): 开始循环的快捷键
            stop_key (str): 停止循环的快捷键
            
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
            
            # 等待一小段时间
            time.sleep(0.3)
            
            # 保存新的快捷键设置
            self.start_hotkey = start_key
            self.stop_hotkey = stop_key
            
            # 保存到配置文件
            success = self.save_config()
            if not success:
                self.signals.status_signal.emit("保存技能循环快捷键配置失败")
                return False
            
            # 重新注册快捷键
            success = self.register_hotkeys()
            if not success:
                self.signals.status_signal.emit("注册新技能循环快捷键失败")
                return False
            
            self.signals.status_signal.emit(f"技能循环快捷键设置已更新: 开始={start_key}, 停止={stop_key}")
            return True
            
        except Exception as e:
            self.signals.status_signal.emit(f"设置技能循环快捷键失败: {str(e)}")
            return False
    
    def add_skill(self, skill):
        """添加技能
        
        参数:
            skill (Skill): 技能对象
        """
        self.skills.append(skill)
        self.skills.sort(key=lambda s: s.priority)  # 按优先级排序
        self.save_config()
    
    def remove_skill(self, name):
        """移除技能
        
        参数:
            name (str): 技能名称
            
        返回:
            bool: 是否成功移除
        """
        for i, skill in enumerate(self.skills):
            if skill.name == name:
                del self.skills[i]
                self.save_config()
                return True
        return False
    
    def get_skill(self, name):
        """获取技能
        
        参数:
            name (str): 技能名称
            
        返回:
            Skill: 技能对象，未找到则返回None
        """
        for skill in self.skills:
            if skill.name == name:
                return skill
        return None
    
    def start_cycle(self):
        """开始技能循环"""
        if self.running:
            return
            
        # 检查是否有可用技能
        if not self.skills:
            self.signals.status_signal.emit("没有可用技能，请先添加技能")
            return
            
        self.running = True
        
        # 创建并启动循环线程
        self.cycle_thread = threading.Thread(target=self._cycle_loop, daemon=True)
        self.cycle_thread.start()
        
        self.signals.status_signal.emit("技能循环已启动")
    
    def stop_cycle(self):
        """停止技能循环"""
        if not self.running:
            return
            
        self.running = False
        
        if self.cycle_thread and self.cycle_thread.is_alive():
            # 等待线程结束
            self.cycle_thread.join(1.0)
            
        self.cycle_thread = None
        self.signals.status_signal.emit("技能循环已停止")
    
    def _cycle_loop(self):
        """技能循环线程"""
        while self.running:
            # 获取可用的最高优先级技能
            available_skills = [s for s in self.skills if s.is_available() and s.enabled]
            
            if available_skills:
                # 按优先级排序（优先级值小的优先）
                available_skills.sort(key=lambda s: s.priority)
                
                # 使用优先级最高的技能
                skill = available_skills[0]
                if skill.use_skill():
                    self.signals.status_signal.emit(f"使用技能: {skill.name}")
                    self.signals.skill_used_signal.emit(skill.name)
            
            # 等待一段时间后再检查
            time.sleep(self.update_interval)
    
    def set_skill_icon_position(self, name):
        """设置技能图标位置
        
        参数:
            name (str): 技能名称
            
        返回:
            bool: 是否成功设置
        """
        skill = self.get_skill(name)
        if not skill:
            return False
        
        from 选择框 import show_selection_box
        
        def on_selection(rect):
            skill.x1 = rect.x()
            skill.y1 = rect.y()
            skill.x2 = rect.x() + rect.width()
            skill.y2 = rect.y() + rect.height()
            print(f"{skill.name}技能图标位置: ({skill.x1}, {skill.y1}) - ({skill.x2}, {skill.y2})")
            skill.save_config()
            
            # 捕获技能图标模板
            skill.capture_icon_template()
        
        # 显示选择框并等待用户操作
        result = show_selection_box(on_selection)
        
        return result

# 创建单例实例
skill_manager = SkillCycleManager() 

class NewSkillCycleManager(SkillCycleManager):
    """使用新数据模型的技能循环管理器
    
    该类继承自SkillCycleManager，但使用新的数据结构存储和管理技能。
    新的技能管理器使用集中式的配置管理器来处理所有配置。
    """
    
    def __init__(self):
        """初始化新的技能循环管理器"""
        # 先设置config_manager属性，再调用父类构造函数
        self.config_manager = config_manager
        
        # 初始化基本属性而不是调用父类的__init__
        self.skills = []
        self.running = False
        self.cycle_thread = None
        self.update_interval = 0.1
        self.signals = SkillSignals()
        
        # 快捷键设置
        self.hotkeys = {
            "start_cycle": "ctrl+f11",
            "stop_cycle": "ctrl+f12"
        }
        
        # 加载配置
        self.load_config()
        
        # 注册快捷键
        self.register_hotkeys()
    
    def load_config(self):
        """加载技能配置
        
        从集中式配置管理器加载技能和基本设置
        """
        # 清空当前技能列表
        self.skills.clear()
        
        try:
            # 加载通用配置，安全处理属性访问
            general_config = self.config_manager.system_config.general
            
            # 更新间隔
            if hasattr(general_config, "update_interval"):
                self.update_interval = general_config.update_interval
            elif isinstance(general_config, dict) and "update_interval" in general_config:
                self.update_interval = general_config["update_interval"]
            
            # 热键设置
            if hasattr(general_config, "hotkeys"):
                hotkeys = general_config.hotkeys
            elif isinstance(general_config, dict) and "hotkeys" in general_config:
                hotkeys = general_config["hotkeys"]
            else:
                hotkeys = {}
            
            # 设置热键
            self.hotkeys["start_cycle"] = hotkeys.get("start_cycle", "ctrl+f11") if hotkeys else "ctrl+f11"
            self.hotkeys["stop_cycle"] = hotkeys.get("stop_cycle", "ctrl+f12") if hotkeys else "ctrl+f12"
            
            # 安全获取技能列表
            skills_list = []
            if hasattr(self.config_manager, "skills_db"):
                skills_db = self.config_manager.skills_db
                if hasattr(skills_db, "skills") and skills_db.skills is not None:
                    skills_list = skills_db.skills
                    
                    # 确保skills_list是一个列表
                    if not isinstance(skills_list, list):
                        print(f"技能列表格式错误: {type(skills_list)}")
                        skills_list = []
            
            # 加载技能数据库中的所有技能
            for data_skill in skills_list:
                try:
                    # 确保是Skill对象
                    if isinstance(data_skill, dict):
                        # 转换字典为Skill对象
                        from skill_data_models import Skill as DataSkill
                        data_skill = DataSkill.from_dict(data_skill)
                    
                    # 检查技能是否启用
                    if not getattr(data_skill, "enabled", True):
                        continue
                        
                    # 检查必要属性
                    if not hasattr(data_skill, "name") or not data_skill.name:
                        print(f"跳过无效技能: 缺少名称")
                        continue
                        
                    if not hasattr(data_skill, "key") or not data_skill.key:
                        print(f"跳过无效技能 {data_skill.name}: 缺少按键")
                        continue
                    
                    # 将数据模型转换为运行时模型
                    skill = self._convert_data_skill_to_runtime(data_skill)
                    if skill:
                        self.skills.append(skill)
                except Exception as e:
                    skill_name = getattr(data_skill, "name", "未知") if hasattr(data_skill, "name") else "未知"
                    print(f"转换技能 {skill_name} 时出错: {str(e)}")
                    import traceback
                    traceback.print_exc()
            
            print(f"已加载 {len(self.skills)} 个技能")
            
        except Exception as e:
            print(f"加载配置出错: {str(e)}")
            import traceback
            traceback.print_exc()
            # 使用默认配置
    
    def save_config(self):
        """保存技能配置
        
        将当前的技能状态保存到集中式配置
        """
        try:
            # 更新技能数据库中的技能
            for skill in self.skills:
                # 查找或创建数据库技能
                data_skill = self.config_manager.skills_db.get_skill(skill.name.lower().replace(" ", "_"))
                if data_skill is None:
                    # 创建新的数据技能
                    data_skill = DataSkill(
                        id=skill.name.lower().replace(" ", "_"),
                        name=skill.name,
                        key=skill.key,
                        priority=skill.priority
                    )
                
                # 更新数据技能的状态
                self._update_data_skill_from_runtime(data_skill, skill)
                
                # 保存到数据库
                self.config_manager.skills_db.add_skill(data_skill)
            
            # 更新通用配置
            general_config = self.config_manager.system_config.general
            
            # 安全地更新通用配置
            if hasattr(general_config, "update_interval"):
                general_config.update_interval = self.update_interval
            elif isinstance(general_config, dict):
                general_config["update_interval"] = self.update_interval
            
            # 安全地更新热键配置
            if hasattr(general_config, "hotkeys"):
                hotkeys = general_config.hotkeys
            elif isinstance(general_config, dict) and "hotkeys" in general_config:
                hotkeys = general_config["hotkeys"]
            else:
                # 如果hotkeys不存在，创建一个新的
                if isinstance(general_config, dict):
                    general_config["hotkeys"] = {}
                    hotkeys = general_config["hotkeys"]
                else:
                    # 如果general_config不是字典也没有hotkeys属性，我们创建一个
                    setattr(general_config, "hotkeys", {})
                    hotkeys = general_config.hotkeys
            
            # 设置热键
            if isinstance(hotkeys, dict):
                hotkeys["start_cycle"] = self.hotkeys["start_cycle"]
                hotkeys["stop_cycle"] = self.hotkeys["stop_cycle"]
            else:
                # 如果hotkeys不是字典，我们尝试设置属性
                setattr(hotkeys, "start_cycle", self.hotkeys["start_cycle"])
                setattr(hotkeys, "stop_cycle", self.hotkeys["stop_cycle"])
            
            # 保存所有配置
            self.config_manager.save_system_config()
            self.config_manager.save_skills_db()
            
            print("技能配置已保存")
            return True
            
        except Exception as e:
            print(f"保存配置出错: {str(e)}")
            return False
    
    def _convert_data_skill_to_runtime(self, data_skill):
        """将数据模型技能转换为运行时技能对象
        
        参数:
            data_skill (DataSkill): 数据模型技能对象
            
        返回:
            Skill: 运行时技能对象，转换失败则返回None
        """
        try:
            # 检查必要属性是否存在
            if not hasattr(data_skill, "name") or not data_skill.name:
                print("无效的技能数据: 缺少名称")
                return None
                
            if not hasattr(data_skill, "key") or not data_skill.key:
                print(f"无效的技能数据 {data_skill.name}: 缺少按键")
                return None
            
            # 安全获取优先级
            priority = getattr(data_skill, "priority", 0)
            if not isinstance(priority, int):
                try:
                    priority = int(priority)
                except:
                    priority = 0
                
            # 创建技能实例
            skill = Skill(data_skill.name, data_skill.key, priority)
            
            # 设置基本属性
            parameters = getattr(data_skill, "parameters", {})
            if not parameters:
                parameters = {}
                
            skill.cooldown = parameters.get("cooldown", 0.0)
            skill.press_delay = parameters.get("press_delay", 0.0)
            skill.release_delay = parameters.get("release_delay", 0.05)
            skill.enabled = getattr(data_skill, "enabled", True)
            
            # 设置图标信息
            if hasattr(data_skill, "icon"):
                icon = data_skill.icon
                pos = getattr(icon, "position", {})
                if not pos:
                    pos = {"x1": 0, "y1": 0, "x2": 0, "y2": 0}
                    
                skill.x1 = pos.get("x1", 0)
                skill.y1 = pos.get("y1", 0)
                skill.x2 = pos.get("x2", 0)
                skill.y2 = pos.get("y2", 0)
                skill.img_path = getattr(icon, "img_path", "")
                skill.threshold = getattr(icon, "threshold", 0.7)
                
                # 加载图像模板
                if skill.img_path and os.path.exists(skill.img_path):
                    try:
                        skill.template = cv2.imread(skill.img_path)
                    except Exception as e:
                        print(f"加载技能{skill.name}图标时出错: {str(e)}")
                
            return skill
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            print(f"转换技能数据模型时出错: {str(e)}")
            return None
    
    def _update_data_skill_from_runtime(self, data_skill, runtime_skill):
        """用运行时技能更新数据模型技能
        
        参数:
            data_skill (DataSkill): 要更新的数据模型技能
            runtime_skill (Skill): 运行时技能对象
        """
        # 更新基本属性
        data_skill.key = runtime_skill.key
        data_skill.priority = runtime_skill.priority
        data_skill.enabled = runtime_skill.enabled
        
        # 更新参数
        data_skill.parameters["cooldown"] = runtime_skill.cooldown
        data_skill.parameters["press_delay"] = runtime_skill.press_delay
        data_skill.parameters["release_delay"] = runtime_skill.release_delay
        
        # 更新图标信息
        data_skill.icon.position["x1"] = runtime_skill.x1
        data_skill.icon.position["y1"] = runtime_skill.y1
        data_skill.icon.position["x2"] = runtime_skill.x2
        data_skill.icon.position["y2"] = runtime_skill.y2
        data_skill.icon.img_path = runtime_skill.img_path
        data_skill.icon.threshold = runtime_skill.threshold
        
        # 确保有默认动作
        if not data_skill.actions:
            data_skill.actions.append(Action(type="keypress", key=runtime_skill.key))
    
    def add_skill(self, skill):
        """添加技能
        
        参数:
            skill (Skill): 要添加的技能对象
        """
        # 添加到运行时列表
        super().add_skill(skill)
        
        # 创建并保存数据模型技能
        data_skill = DataSkill(
            id=skill.name.lower().replace(" ", "_"),
            name=skill.name,
            key=skill.key,
            priority=skill.priority
        )
        
        # 更新数据模型的属性
        self._update_data_skill_from_runtime(data_skill, skill)
        
        # 添加到数据库并保存
        self.config_manager.skills_db.add_skill(data_skill)
        self.config_manager.save_skills_db()
    
    def remove_skill(self, name):
        """移除技能
        
        参数:
            name (str): 技能名称
        
        返回:
            bool: 是否成功移除
        """
        # 从运行时列表中移除
        result = super().remove_skill(name)
        
        if result:
            # 从数据库中移除
            skill_id = name.lower().replace(" ", "_")
            self.config_manager.skills_db.remove_skill(skill_id)
            self.config_manager.save_skills_db()
        
        return result
    
    def get_skill_group_ids(self):
        """获取所有技能组ID
        
        返回:
            list: 技能组ID列表
        """
        groups = []
        for group_info in self.config_manager.system_config.skill_groups:
            groups.append(group_info.get("id", ""))
        return groups
    
    def get_skills_by_group(self, group_id):
        """获取指定组的所有技能
        
        参数:
            group_id (str): 技能组ID
            
        返回:
            list: 技能对象列表
        """
        # 获取技能组配置
        group = self.config_manager.get_skill_group(group_id)
        if group is None:
            return []
            
        # 返回该组中的所有技能
        result = []
        for skill_id in group.skill_ids:
            data_skill = self.config_manager.skills_db.get_skill(skill_id)
            if data_skill and data_skill.enabled:
                skill = self._convert_data_skill_to_runtime(data_skill)
                result.append(skill)
        
        return result
    
    def check_version_compatibility(self):
        """检查版本兼容性
        
        检查当前数据格式版本，并在需要时执行迁移
        
        返回:
            bool: 是否兼容
        """
        try:
            # 如果还没有数据库文件，尝试迁移旧数据
            if not os.path.exists(self.config_manager.skills_db_file):
                print("未找到技能数据库，尝试迁移旧版数据...")
                
                # 执行迁移
                migrated = self.config_manager.migrate_legacy_data()
                
                # 创建默认技能组
                try:
                    # 检查默认组是否存在
                    default_group = self.config_manager.get_skill_group("default")
                    if default_group is None:
                        # 创建默认技能组
                        from skill_data_models import SkillGroup
                        default_group = SkillGroup(
                            id="default",
                            name="默认技能组",
                            enabled=True,
                            description="默认技能组"
                        )
                        
                        # 查找所有技能ID并添加到默认组
                        for skill in self.config_manager.skills_db.skills:
                            skill_id = getattr(skill, "id", "")
                            if skill_id and skill_id not in default_group.skill_ids:
                                default_group.skill_ids.append(skill_id)
                        
                        # 保存默认组
                        self.config_manager.save_skill_group(default_group)
                        print("已创建默认技能组")
                except Exception as e:
                    print(f"创建默认技能组时出错: {str(e)}")
                
                if migrated:
                    print("数据迁移完成。")
                    # 再次加载配置，确保使用新数据
                    self.load_config()
                    return True
                else:
                    print("没有找到可迁移的旧数据，创建新的配置。")
                    # 创建基本配置结构
                    self.config_manager.save_system_config()
                    self.config_manager.save_skills_db()
                    return True
            
            return True
        except Exception as e:
            print(f"版本兼容性检查出错: {str(e)}")
            import traceback
            traceback.print_exc()
            return False
            
    def register_hotkeys(self):
        """注册全局快捷键，重写父类方法以适配新的热键存储格式"""
        try:
            # 清除之前的快捷键监听器
            self.unregister_hotkeys()
            
            # 等待一小段时间，确保旧的快捷键已经被完全注销
            time.sleep(0.2)
            
            # 存储快捷键的引用，以便于后续注销
            self.hotkey_handlers = []
            
            # 注册开始循环快捷键
            try:
                start_handler = keyboard.add_hotkey(
                    self.hotkeys["start_cycle"], 
                    self.start_cycle, 
                    suppress=False
                )
                self.hotkey_handlers.append(start_handler)
                print(f"已注册开始技能循环快捷键: {self.hotkeys['start_cycle']}")
            except Exception as e:
                print(f"注册开始技能循环快捷键失败: {str(e)}")
                return False
            
            # 注册停止循环快捷键
            try:
                stop_handler = keyboard.add_hotkey(
                    self.hotkeys["stop_cycle"], 
                    self.stop_cycle, 
                    suppress=False
                )
                self.hotkey_handlers.append(stop_handler)
                print(f"已注册停止技能循环快捷键: {self.hotkeys['stop_cycle']}")
            except Exception as e:
                print(f"注册停止技能循环快捷键失败: {str(e)}")
                # 如果第二个注册失败，注销第一个
                if len(self.hotkey_handlers) > 0:
                    try:
                        keyboard.unhook(self.hotkey_handlers[0])
                    except:
                        pass
                return False
            
            self.signals.status_signal.emit(f"已注册技能循环快捷键: 开始={self.hotkeys['start_cycle']}, 停止={self.hotkeys['stop_cycle']}")
            return True
            
        except Exception as e:
            self.signals.status_signal.emit(f"注册技能循环快捷键失败: {str(e)}")
            return False
    
    def set_hotkeys(self, start_key, stop_key):
        """设置新的快捷键，重写父类方法以适配新的热键存储格式
        
        参数:
            start_key (str): 开始循环的快捷键
            stop_key (str): 停止循环的快捷键
            
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
            
            # 等待一小段时间
            time.sleep(0.3)
            
            # 保存新的快捷键设置
            self.hotkeys["start_cycle"] = start_key
            self.hotkeys["stop_cycle"] = stop_key
            
            # 保存到配置文件
            success = self.save_config()
            if not success:
                self.signals.status_signal.emit("保存技能循环快捷键配置失败")
                return False
            
            # 重新注册快捷键
            success = self.register_hotkeys()
            if not success:
                self.signals.status_signal.emit("注册新技能循环快捷键失败")
                return False
            
            self.signals.status_signal.emit(f"技能循环快捷键设置已更新: 开始={start_key}, 停止={stop_key}")
            return True
            
        except Exception as e:
            self.signals.status_signal.emit(f"设置技能循环快捷键失败: {str(e)}")
            return False

# 创建新的管理器实例
new_skill_manager = NewSkillCycleManager()

# 迁移旧版数据
new_skill_manager.check_version_compatibility() 