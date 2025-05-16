import os
import json
import numpy as np
from config_manager import ConfigManager

# 动态导入带空格的模块
import importlib.util

# 动态导入team_members模块
module_name = "team_members(choice box)"
module_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "team_members(choice box).py")
spec = importlib.util.spec_from_file_location(module_name, module_path)
team_members_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(team_members_module)

# 从module中获取Team和TeamMember类
Team = team_members_module.Team
TeamMember = team_members_module.TeamMember

class TeamManager:
    """团队成员管理类，负责处理队友的增删改查和配置管理"""
    
    def __init__(self):
        """初始化团队管理器"""
        self.team = Team()  # 创建Team实例
        self.default_hp_color_lower = None  # 默认血条颜色下限
        self.default_hp_color_upper = None  # 默认血条颜色上限
        self.load_default_colors()  # 从配置加载默认颜色设置
    
    def add_member(self, name, profession):
        """添加新队友
        
        参数:
            name: 队友名称
            profession: 队友职业
            
        返回:
            TeamMember: 新创建的队友对象
        """
        new_member = self.team.add_member(name, profession)
        
        # 使用全局默认颜色设置(如果有的话)
        if self.default_hp_color_lower is not None and self.default_hp_color_upper is not None:
            new_member.hp_color_lower = np.copy(self.default_hp_color_lower)
            new_member.hp_color_upper = np.copy(self.default_hp_color_upper)
            new_member.save_config()  # 保存颜色设置到队员配置文件
        
        return new_member
    
    def remove_member(self, index):
        """移除队友
        
        参数:
            index: 队友索引
            
        返回:
            bool: 是否成功移除
        """
        if 0 <= index < len(self.team.members):
            selected_member = self.team.members[index]
            try:
                # 删除配置文件
                config_file = f"{selected_member.name}_config.json"
                config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), config_file)
                if os.path.exists(config_path):
                    os.remove(config_path)
                
                # 从队伍中移除队员
                self.team.members.pop(index)
                return True
            except Exception as e:
                print(f"移除队友失败: {e}")
                return False
        return False
    
    def clear_all_members(self):
        """清除所有队友
        
        返回:
            int: 成功删除的队友数量
        """
        deleted_count = 0
        for member in list(self.team.members):  # 使用列表副本进行遍历
            config_file = f"{member.name}_config.json"
            config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), config_file)
            if os.path.exists(config_path):
                try:
                    os.remove(config_path)
                    deleted_count += 1
                except Exception as e:
                    print(f"删除配置文件 {config_path} 失败: {e}")
        
        # 清空队友列表
        self.team.members = []
        return deleted_count
    
    def load_teammates(self):
        """加载所有队友配置
        
        返回:
            int: 成功加载的队友数量
        """
        # 先清空当前队伍
        self.team.members = []
        
        # 获取当前目录
        current_dir = os.path.dirname(os.path.abspath(__file__))
        loaded_count = 0
        
        # 扫描队友配置文件
        for filename in os.listdir(current_dir):
            if filename.endswith('_config.json') and filename != 'hotkeys_config.json':
                try:
                    # 排除系统配置文件
                    if filename.startswith(('hotkeys', 'settings', 'config', 'system', 'default_color', 'auto_select')):
                        continue
                        
                    # 从文件名提取队友名称
                    member_name = filename[:-12]  # 移除'_config.json'
                    
                    # 读取配置获取职业信息
                    config_path = os.path.join(current_dir, filename)
                    with open(config_path, 'r', encoding='utf-8') as f:
                        config = json.load(f)
                        
                        # 检查是否是有效的队友配置
                        if 'profession' not in config or 'health_bar' not in config:
                            continue
                        
                        # 获取职业信息
                        profession = config.get('profession', '未知')
                        
                        # 加载队友
                        member = self.team.add_member(member_name, profession)
                        
                        # 设置血条坐标
                        health_bar = config.get('health_bar', {})
                        member.x1 = health_bar.get('x1', 0)
                        member.y1 = health_bar.get('y1', 0)
                        member.x2 = health_bar.get('x2', 0)
                        member.y2 = health_bar.get('y2', 0)
                        
                        # 设置血条颜色
                        colors = config.get('colors', {})
                        if 'lower' in colors and 'upper' in colors:
                            member.hp_color_lower = np.array(colors['lower'], dtype=np.uint8)
                            member.hp_color_upper = np.array(colors['upper'], dtype=np.uint8)
                        
                        loaded_count += 1
                        
                except Exception as e:
                    print(f'加载配置文件 {filename} 时出错: {str(e)}')
                    continue
        
        return loaded_count
    
    def export_config(self, file_path):
        """导出团队配置到文件
        
        参数:
            file_path: 导出文件路径
            
        返回:
            bool: 是否成功导出
        """
        try:
            import time
            
            # 构建导出数据
            export_data = {
                'export_time': time.strftime('%Y-%m-%d %H:%M:%S'),
                'app_version': 'VitalSync 1.0.0',
                'teammates': []
            }
            
            # 添加所有队友信息
            for member in self.team.members:
                teammate_data = {
                    'name': member.name,
                    'profession': member.profession,
                    'health_bar': {
                        'x1': member.x1,
                        'y1': member.y1,
                        'x2': member.x2,
                        'y2': member.y2
                    },
                    'colors': {
                        'lower': member.hp_color_lower.tolist() if hasattr(member.hp_color_lower, 'tolist') else list(member.hp_color_lower),
                        'upper': member.hp_color_upper.tolist() if hasattr(member.hp_color_upper, 'tolist') else list(member.hp_color_upper)
                    }
                }
                export_data['teammates'].append(teammate_data)
            
            # 写入文件
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(export_data, f, ensure_ascii=False, indent=4)
            
            return True
        except Exception as e:
            print(f"导出配置失败: {e}")
            return False
    
    def set_member_health_bar_position(self, member, x1, y1, x2, y2):
        """设置队员血条位置
        
        参数:
            member: 队友对象
            x1: 左上角x坐标
            y1: 左上角y坐标
            x2: 右下角x坐标
            y2: 右下角y坐标
        """
        member.x1 = x1
        member.y1 = y1
        member.x2 = x2
        member.y2 = y2
        member.save_config()  # 保存新的坐标设置
        
    def set_member_health_bar_color(self, member, color_rgb):
        """设置队员血条颜色
        
        参数:
            member: 队友对象
            color_rgb: RGB颜色元组
        """
        # 将RGB转换为BGR
        bgr_values = (color_rgb[2], color_rgb[1], color_rgb[0])  # B, G, R
        
        # 创建颜色上下限（允许一定范围的变化）- 使用BGR值
        color_lower = np.array([max(0, c - 30) for c in bgr_values], dtype=np.uint8)
        color_upper = np.array([min(255, c + 30) for c in bgr_values], dtype=np.uint8)
        
        # 更新队友的血条颜色设置
        member.hp_color_lower = color_lower
        member.hp_color_upper = color_upper
        
        # 保存到配置文件
        member.save_config()
    
    def set_all_members_color(self, color_rgb):
        """设置所有队员血条颜色
        
        参数:
            color_rgb: RGB颜色元组
            
        返回:
            int: 成功设置的队员数量
        """
        if not self.team.members:
            return 0
            
        # 将RGB转换为BGR
        bgr_values = (color_rgb[2], color_rgb[1], color_rgb[0])  # B, G, R
        
        # 保存为全局默认值，供新队员使用
        color_lower = np.array([max(0, c - 30) for c in bgr_values], dtype=np.uint8)
        color_upper = np.array([min(255, c + 30) for c in bgr_values], dtype=np.uint8)
        self.default_hp_color_lower = color_lower
        self.default_hp_color_upper = color_upper
        self.save_default_colors()  # 保存默认颜色到配置文件
        
        success_count = 0
        for member in self.team.members:
            try:
                # 创建颜色上下限（允许一定范围的变化） - 使用BGR值
                member.hp_color_lower = np.copy(color_lower)  # 使用拷贝防止引用共享
                member.hp_color_upper = np.copy(color_upper)  # 使用拷贝防止引用共享
                member.save_config()
                success_count += 1
            except Exception as e:
                print(f"为队友 {member.name} 更新颜色配置时出错: {e}")
        
        return success_count
    
    def save_default_colors(self):
        """保存默认血条颜色设置到配置文件"""
        if self.default_hp_color_lower is None or self.default_hp_color_upper is None:
            return False

        try:
            config_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "default_color_config.json")
            config = {
                'default_hp_color': {
                    'lower': self.default_hp_color_lower.tolist() if hasattr(self.default_hp_color_lower, 'tolist') else list(self.default_hp_color_lower),
                    'upper': self.default_hp_color_upper.tolist() if hasattr(self.default_hp_color_upper, 'tolist') else list(self.default_hp_color_upper)
                }
            }
            with open(config_file, 'w', encoding='utf-8') as f:
                json.dump(config, f, ensure_ascii=False, indent=4)
            print(f"默认血条颜色设置已保存到 {config_file}")
            return True
        except Exception as e:
            print(f"保存默认血条颜色设置失败: {e}")
            return False

    def load_default_colors(self):
        """从配置文件加载默认血条颜色设置"""
        try:
            config_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "default_color_config.json")
            if not os.path.exists(config_file):
                return False  # 如果配置文件不存在，使用 None 作为默认值
                
            with open(config_file, 'r', encoding='utf-8') as f:
                config = json.load(f)
                
            if 'default_hp_color' in config:
                self.default_hp_color_lower = np.array(config['default_hp_color']['lower'], dtype=np.uint8)
                self.default_hp_color_upper = np.array(config['default_hp_color']['upper'], dtype=np.uint8)
                print(f"已加载默认血条颜色设置")
                return True
            return False
        except Exception as e:
            print(f"加载默认血条颜色设置失败: {e}")
            return False 