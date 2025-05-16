import os
import json
import numpy as np

class TeamMember:
    """队友类，代表一个队员"""
    
    def __init__(self, name, profession="未知"):
        """初始化队友
        
        参数:
            name: 队友名称
            profession: 队友职业
        """
        self.name = name
        self.profession = profession
        self.x1 = 0  # 血条左上角x坐标
        self.y1 = 0  # 血条左上角y坐标
        self.x2 = 0  # 血条右下角x坐标
        self.y2 = 0  # 血条右下角y坐标
        self.hp_color_lower = np.array([0, 0, 0], dtype=np.uint8)  # 血条颜色下限
        self.hp_color_upper = np.array([255, 255, 255], dtype=np.uint8)  # 血条颜色上限
        self.health_percentage = 100.0  # 当前血量百分比
        self.is_alive = True  # 存活状态
        
        # 加载配置
        self.load_config()
    
    def save_config(self):
        """保存队友配置到文件"""
        config = {
            'name': self.name,
            'profession': self.profession,
            'health_bar': {
                'x1': self.x1,
                'y1': self.y1,
                'x2': self.x2,
                'y2': self.y2
            },
            'hp_color': {
                'lower': self.hp_color_lower.tolist() if hasattr(self.hp_color_lower, 'tolist') else list(self.hp_color_lower),
                'upper': self.hp_color_upper.tolist() if hasattr(self.hp_color_upper, 'tolist') else list(self.hp_color_upper)
            }
        }
        
        config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), f"{self.name}_config.json")
        
        try:
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(config, f, ensure_ascii=False, indent=4)
            print(f"已保存配置到 {config_path}")
        except Exception as e:
            print(f"保存配置失败: {e}")
    
    def load_config(self):
        """从文件加载队友配置"""
        config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), f"{self.name}_config.json")
        
        if not os.path.exists(config_path):
            return
            
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
                
            if 'profession' in config:
                self.profession = config['profession']
                
            if 'health_bar' in config:
                health_bar = config['health_bar']
                self.x1 = health_bar.get('x1', 0)
                self.y1 = health_bar.get('y1', 0)
                self.x2 = health_bar.get('x2', 0)
                self.y2 = health_bar.get('y2', 0)
                
            if 'hp_color' in config:
                hp_color = config['hp_color']
                self.hp_color_lower = np.array(hp_color.get('lower', [0, 0, 0]), dtype=np.uint8)
                self.hp_color_upper = np.array(hp_color.get('upper', [255, 255, 255]), dtype=np.uint8)
                
            print(f"已加载 {self.name} 的配置")
        except Exception as e:
            print(f"加载配置失败: {e}")
    
    def __str__(self):
        """返回队友的字符串表示"""
        return f"{self.name} ({self.profession})"

class Team:
    """队伍类，管理多个队友"""
    
    def __init__(self):
        """初始化队伍"""
        self.members = []
        self.load_all_members()
    
    def add_member(self, name, profession="未知"):
        """添加队友
        
        参数:
            name: 队友名称
            profession: 队友职业
            
        返回:
            TeamMember: 新添加的队友
        """
        # 检查是否已存在同名队友
        for member in self.members:
            if member.name == name:
                # 更新职业
                member.profession = profession
                member.save_config()
                return member
        
        # 创建新队友
        new_member = TeamMember(name, profession)
        self.members.append(new_member)
        return new_member
    
    def remove_member(self, index):
        """移除队友
        
        参数:
            index: 队友索引
            
        返回:
            bool: 是否成功移除
        """
        if index < 0 or index >= len(self.members):
            return False
            
        member = self.members[index]
        
        # 删除配置文件
        config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), f"{member.name}_config.json")
        if os.path.exists(config_path):
            try:
                os.remove(config_path)
            except Exception as e:
                print(f"删除配置文件失败: {e}")
                return False
        
        # 从列表中移除
        self.members.pop(index)
        return True
    
    def get_member_by_name(self, name):
        """根据名称获取队友
        
        参数:
            name: 队友名称
            
        返回:
            TeamMember: 找到的队友，如果未找到则返回None
        """
        for member in self.members:
            if member.name == name:
                return member
        return None
    
    def load_all_members(self):
        """加载所有队友配置"""
        self.members = []
        
        # 获取当前目录
        current_dir = os.path.dirname(os.path.abspath(__file__))
        
        # 扫描队友配置文件
        for filename in os.listdir(current_dir):
            if filename.endswith('_config.json') and filename != 'hotkeys_config.json':
                try:
                    # 排除系统配置文件
                    if filename.startswith(('hotkeys', 'settings', 'config', 'system', 'default', 'auto')):
                        continue
                        
                    # 从文件名提取队友名称
                    member_name = filename[:-12]  # 移除'_config.json'
                    
                    # 读取配置获取职业信息
                    config_path = os.path.join(current_dir, filename)
                    with open(config_path, 'r', encoding='utf-8') as f:
                        config = json.load(f)
                        
                        # 检查是否是有效的队友配置
                        if 'profession' not in config:
                            continue
                        
                        # 获取职业信息
                        profession = config.get('profession', '未知')
                        
                        # 创建队友并加载配置
                        member = TeamMember(member_name, profession)
                        self.members.append(member)
                        
                except Exception as e:
                    print(f'加载配置文件 {filename} 时出错: {str(e)}')
                    continue
        
        print(f"已加载 {len(self.members)} 个队友配置")
    
    def clear_all_members(self):
        """清除所有队友"""
        current_dir = os.path.dirname(os.path.abspath(__file__))
        deleted_count = 0
        
        for member in self.members:
            config_path = os.path.join(current_dir, f"{member.name}_config.json")
            if os.path.exists(config_path):
                try:
                    os.remove(config_path)
                    deleted_count += 1
                except Exception as e:
                    print(f"删除 {member.name} 的配置文件失败: {e}")
        
        self.members = []
        return deleted_count
    
    def __len__(self):
        """返回队伍中的队友数量"""
        return len(self.members)
    
    def __getitem__(self, index):
        """通过索引获取队友"""
        return self.members[index]
    
    def __iter__(self):
        """返回迭代器"""
        return iter(self.members) 