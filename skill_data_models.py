"""
技能循环模块数据模型

这个模块定义了技能循环系统中使用的数据模型类，用于处理技能、条件和配置等数据。
"""

import os
import json
import time
from datetime import datetime
from typing import Dict, List, Optional, Union, Any
from dataclasses import dataclass, field, asdict

class JsonSerializable:
    """可序列化为JSON的基类"""
    
    def to_dict(self) -> Dict[str, Any]:
        """将对象转换为字典"""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'JsonSerializable':
        """从字典创建对象"""
        try:
            # 处理基本数据类型
            if not isinstance(data, dict):
                return data
                
            # 获取类的字段信息
            import inspect
            from dataclasses import is_dataclass, fields
            
            # 如果不是dataclass，返回原始数据
            if not is_dataclass(cls):
                return cls(**data)
                
            # 预处理数据
            processed_data = {}
            class_fields = {f.name: f for f in fields(cls)}
            
            for key, value in data.items():
                if key not in class_fields:
                    # 未知字段直接添加
                    processed_data[key] = value
                    continue
                    
                field_info = class_fields[key]
                field_type = field_info.type
                
                # 递归处理列表
                if isinstance(value, list) and hasattr(field_type, "__origin__") and field_type.__origin__ is list:
                    # 获取列表元素类型
                    element_type = field_type.__args__[0]
                    
                    # 判断元素类型是否是JsonSerializable的子类
                    if isinstance(element_type, type) and issubclass(element_type, JsonSerializable):
                        processed_data[key] = [element_type.from_dict(item) for item in value]
                    else:
                        processed_data[key] = value
                        
                # 递归处理嵌套对象
                elif isinstance(value, dict):
                    # 如果字段类型是JsonSerializable的子类
                    if isinstance(field_type, type) and issubclass(field_type, JsonSerializable):
                        processed_data[key] = field_type.from_dict(value)
                    else:
                        processed_data[key] = value
                else:
                    processed_data[key] = value
            
            return cls(**processed_data)
        except Exception as e:
            print(f"从字典创建对象时出错: {str(e)}, 数据类型: {cls.__name__}, 数据: {data}")
            # 返回一个空的默认实例
            import inspect
            if inspect.isclass(cls) and hasattr(cls, "__call__"):
                try:
                    return cls()
                except:
                    return None
            return None
    
    def save_to_file(self, filepath: str) -> bool:
        """保存对象到JSON文件"""
        try:
            os.makedirs(os.path.dirname(filepath), exist_ok=True)
            
            # 使用临时文件保存
            temp_file = filepath + '.tmp'
            with open(temp_file, 'w', encoding='utf-8') as f:
                json.dump(self.to_dict(), f, indent=4, ensure_ascii=False)
            
            # 如果保存成功，替换原文件
            if os.path.exists(filepath):
                os.remove(filepath)
            os.rename(temp_file, filepath)
            
            return True
        except Exception as e:
            print(f"保存文件出错: {str(e)}")
            return False
    
    @classmethod
    def load_from_file(cls, filepath: str) -> Optional['JsonSerializable']:
        """从JSON文件加载对象"""
        try:
            if not os.path.exists(filepath):
                print(f"文件不存在: {filepath}")
                return None
                
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
                
            return cls.from_dict(data)
        except Exception as e:
            print(f"加载文件出错: {str(e)}")
            return None


@dataclass
class IconInfo(JsonSerializable):
    """技能图标信息"""
    position: Dict[str, int] = field(default_factory=lambda: {"x1": 0, "y1": 0, "x2": 0, "y2": 0})
    img_path: str = ""
    threshold: float = 0.7


@dataclass
class ConditionReference(JsonSerializable):
    """条件引用"""
    id: str
    reference: str = ""


@dataclass
class Action(JsonSerializable):
    """技能动作"""
    type: str
    key: str = ""
    hold_time: float = 0.05
    sequence: List[str] = field(default_factory=list)


@dataclass
class Skill(JsonSerializable):
    """技能数据模型"""
    id: str
    name: str
    key: str
    priority: int = 0
    group_id: str = "default"
    enabled: bool = True
    parameters: Dict[str, Any] = field(default_factory=lambda: {
        "cooldown": 0.0,
        "press_delay": 0.0,
        "release_delay": 0.05
    })
    icon: IconInfo = field(default_factory=IconInfo)
    conditions: List[ConditionReference] = field(default_factory=list)
    actions: List[Action] = field(default_factory=list)
    last_used_time: float = 0.0
    
    def is_available(self) -> bool:
        """检查技能是否可用（不在CD中）"""
        if not self.enabled:
            return False
            
        cooldown = self.parameters.get("cooldown", 0.0)
        return time.time() - self.last_used_time >= cooldown


@dataclass
class ConditionParameter(JsonSerializable):
    """条件参数"""
    combo_type: str = "AND"
    x: int = 0
    y: int = 0
    color: List[int] = field(default_factory=lambda: [0, 0, 0])
    tolerance: int = 20
    interval: float = 0.0
    initial_delay: float = 0.0
    region: Dict[str, int] = field(default_factory=lambda: {"x1": 0, "y1": 0, "x2": 0, "y2": 0})
    text: str = ""
    font_size: int = 12
    

@dataclass
class Condition(JsonSerializable):
    """条件数据模型"""
    id: str
    name: str
    type: str
    enabled: bool = True
    check_interval: float = 0.1
    parameters: Dict[str, Any] = field(default_factory=dict)
    sub_conditions: List[ConditionReference] = field(default_factory=list)
    description: str = ""
    last_check_time: float = 0.0
    last_match_time: float = 0.0


@dataclass
class ActivationCondition(JsonSerializable):
    """激活条件"""
    id: str
    type: str = "static"
    value: bool = True
    reference: str = ""


@dataclass
class SkillGroup(JsonSerializable):
    """技能组数据模型"""
    id: str
    name: str
    enabled: bool = True
    description: str = ""
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())
    skill_ids: List[str] = field(default_factory=list)
    activation_condition: ActivationCondition = field(default_factory=lambda: ActivationCondition(id="always"))


@dataclass
class GeneralConfig(JsonSerializable):
    """通用配置"""
    update_interval: float = 0.1
    hotkeys: Dict[str, str] = field(default_factory=lambda: {"start_cycle": "ctrl+f11", "stop_cycle": "ctrl+f12"})
    ui_settings: Dict[str, str] = field(default_factory=lambda: {"theme": "light", "icon_size": "medium"})


@dataclass
class SystemConfig(JsonSerializable):
    """系统配置数据模型"""
    version: str = "1.0.0"
    general: GeneralConfig = field(default_factory=GeneralConfig)
    skill_groups: List[Dict[str, Any]] = field(default_factory=list)
    conditions: Dict[str, List[Dict[str, Any]]] = field(default_factory=lambda: {"global_conditions": []})


@dataclass
class SkillDatabase(JsonSerializable):
    """技能数据库"""
    version: str = "1.0.0"
    last_updated: str = field(default_factory=lambda: datetime.now().isoformat())
    skills: List[Skill] = field(default_factory=list)
    
    def get_skill(self, skill_id: str) -> Optional[Skill]:
        """获取技能"""
        for skill in self.skills:
            if skill.id == skill_id:
                return skill
        return None
    
    def add_skill(self, skill: Skill) -> None:
        """添加技能"""
        # 删除同ID的旧技能
        self.remove_skill(skill.id)
        self.skills.append(skill)
        self.last_updated = datetime.now().isoformat()
    
    def remove_skill(self, skill_id: str) -> bool:
        """移除技能"""
        for i, skill in enumerate(self.skills):
            if skill.id == skill_id:
                del self.skills[i]
                self.last_updated = datetime.now().isoformat()
                return True
        return False


@dataclass
class ConditionDatabase(JsonSerializable):
    """条件数据库"""
    version: str = "1.0.0"
    last_updated: str = field(default_factory=lambda: datetime.now().isoformat())
    conditions: List[Condition] = field(default_factory=list)
    
    def get_condition(self, condition_id: str) -> Optional[Condition]:
        """获取条件"""
        for condition in self.conditions:
            if condition.id == condition_id:
                return condition
        return None
    
    def add_condition(self, condition: Condition) -> None:
        """添加条件"""
        # 删除同ID的旧条件
        self.remove_condition(condition.id)
        self.conditions.append(condition)
        self.last_updated = datetime.now().isoformat()
    
    def remove_condition(self, condition_id: str) -> bool:
        """移除条件"""
        for i, condition in enumerate(self.conditions):
            if condition.id == condition_id:
                del self.conditions[i]
                self.last_updated = datetime.now().isoformat()
                return True
        return False


class ConfigManager:
    """配置管理器，负责加载和保存配置文件"""
    
    def __init__(self, config_dir: str = "configs"):
        """初始化配置管理器
        
        参数:
            config_dir: 配置文件目录
        """
        self.config_dir = config_dir
        self.system_config_file = os.path.join(config_dir, "skill_system_config.json")
        self.skills_db_file = os.path.join(config_dir, "skills", "skills_db.json")
        self.conditions_db_file = os.path.join(config_dir, "conditions", "conditions_db.json")
        
        # 确保目录存在
        os.makedirs(os.path.join(config_dir, "skills"), exist_ok=True)
        os.makedirs(os.path.join(config_dir, "conditions"), exist_ok=True)
        os.makedirs(os.path.join(config_dir, "skill_groups"), exist_ok=True)
        os.makedirs(os.path.join(config_dir, "presets"), exist_ok=True)
        
        # 加载配置
        self.system_config = self._load_system_config()
        self.skills_db = self._load_skills_db()
        self.conditions_db = self._load_conditions_db()
        
    def _load_system_config(self) -> SystemConfig:
        """加载系统配置"""
        config = SystemConfig.load_from_file(self.system_config_file)
        if config is None:
            config = SystemConfig()
            config.save_to_file(self.system_config_file)
        return config
    
    def _load_skills_db(self) -> SkillDatabase:
        """加载技能数据库"""
        db = SkillDatabase.load_from_file(self.skills_db_file)
        if db is None:
            db = SkillDatabase()
            db.save_to_file(self.skills_db_file)
        return db
    
    def _load_conditions_db(self) -> ConditionDatabase:
        """加载条件数据库"""
        db = ConditionDatabase.load_from_file(self.conditions_db_file)
        if db is None:
            db = ConditionDatabase()
            db.save_to_file(self.conditions_db_file)
        return db
    
    def save_system_config(self) -> bool:
        """保存系统配置"""
        return self.system_config.save_to_file(self.system_config_file)
    
    def save_skills_db(self) -> bool:
        """保存技能数据库"""
        return self.skills_db.save_to_file(self.skills_db_file)
    
    def save_conditions_db(self) -> bool:
        """保存条件数据库"""
        return self.conditions_db.save_to_file(self.conditions_db_file)
    
    def get_skill_group(self, group_id: str) -> Optional[SkillGroup]:
        """获取技能组配置
        
        参数:
            group_id (str): 技能组ID
            
        返回:
            Optional[SkillGroup]: 技能组对象，未找到则返回None
        """
        try:
            # 检查无效ID
            if group_id is None or group_id == "" or group_id == "all":
                print(f"无效的技能组ID: {group_id}")
                return None
                
            group_file = os.path.join(self.config_dir, "skill_groups", f"{group_id}.json")
            
            # 检查文件是否存在
            if not os.path.exists(group_file):
                print(f"技能组文件不存在: {group_file}")
                
                # 如果是默认组，自动创建
                if group_id == "default":
                    default_group = SkillGroup(
                        id="default",
                        name="默认技能组",
                        enabled=True,
                        description="默认技能组"
                    )
                    self.save_skill_group(default_group)
                    return default_group
                return None
                
            return SkillGroup.load_from_file(group_file)
        except Exception as e:
            print(f"加载技能组配置出错: {str(e)}")
            return None
    
    def save_skill_group(self, group: SkillGroup) -> bool:
        """保存技能组配置"""
        try:
            group_file = os.path.join(self.config_dir, "skill_groups", f"{group.id}.json")
            return group.save_to_file(group_file)
        except Exception as e:
            print(f"保存技能组配置出错: {str(e)}")
            return False
    
    def get_condition(self, condition_id: str) -> Optional[Condition]:
        """获取单个条件配置"""
        try:
            condition_file = os.path.join(self.config_dir, "conditions", f"{condition_id}.json")
            return Condition.load_from_file(condition_file)
        except Exception as e:
            print(f"加载条件配置出错: {str(e)}")
            return None
    
    def save_condition(self, condition: Condition) -> bool:
        """保存单个条件配置"""
        try:
            condition_file = os.path.join(self.config_dir, "conditions", f"{condition.id}.json")
            success = condition.save_to_file(condition_file)
            
            # 更新条件数据库
            if success:
                self.conditions_db.add_condition(condition)
                self.save_conditions_db()
                
            return success
        except Exception as e:
            print(f"保存条件配置出错: {str(e)}")
            return False
    
    def get_preset(self, preset_id: str) -> Dict[str, Any]:
        """获取预设配置"""
        try:
            preset_file = os.path.join(self.config_dir, "presets", f"{preset_id}.json")
            if not os.path.exists(preset_file):
                return {}
                
            with open(preset_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"加载预设配置出错: {str(e)}")
            return {}
    
    def save_preset(self, preset_id: str, data: Dict[str, Any]) -> bool:
        """保存预设配置"""
        try:
            preset_file = os.path.join(self.config_dir, "presets", f"{preset_id}.json")
            
            # 确保目录存在
            os.makedirs(os.path.dirname(preset_file), exist_ok=True)
            
            # 使用临时文件保存
            temp_file = preset_file + '.tmp'
            with open(temp_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=4, ensure_ascii=False)
            
            # 如果保存成功，替换原文件
            if os.path.exists(preset_file):
                os.remove(preset_file)
            os.rename(temp_file, preset_file)
            
            return True
        except Exception as e:
            print(f"保存预设配置出错: {str(e)}")
            return False
    
    def migrate_legacy_data(self) -> bool:
        """迁移旧版数据格式到新系统
        
        将旧版技能循环系统中的独立技能配置文件和主配置文件转换为新的数据库格式。
        
        返回:
            bool: 迁移是否成功
        """
        try:
            # 检查并迁移主配置
            legacy_config_file = os.path.join(os.path.dirname(self.config_dir), "skill_cycle_config.json")
            if os.path.exists(legacy_config_file):
                print(f"发现旧版主配置文件: {legacy_config_file}")
                
                with open(legacy_config_file, 'r', encoding='utf-8') as f:
                    legacy_config = json.load(f)
                
                # 更新全局配置
                self.system_config.general.update_interval = legacy_config.get("update_interval", 0.1)
                self.system_config.general.hotkeys["start_cycle"] = legacy_config.get("start_hotkey", "ctrl+f11")
                self.system_config.general.hotkeys["stop_cycle"] = legacy_config.get("stop_hotkey", "ctrl+f12")
                
                # 处理旧版技能列表
                for skill_info in legacy_config.get("skills", []):
                    skill_name = skill_info.get("name", "")
                    if not skill_name:
                        continue
                    
                    # 查找对应的技能配置文件
                    legacy_skill_file = os.path.join(os.path.dirname(self.config_dir), f"skill_{skill_name}_config.json")
                    
                    # 创建默认技能对象
                    skill_id = skill_name.lower().replace(" ", "_")
                    skill = Skill(
                        id=skill_id,
                        name=skill_name,
                        key=skill_info.get("key", ""),
                        priority=skill_info.get("priority", 0)
                    )
                    
                    # 如果存在单独的技能配置文件，加载详细设置
                    if os.path.exists(legacy_skill_file):
                        try:
                            with open(legacy_skill_file, 'r', encoding='utf-8') as f:
                                legacy_skill_config = json.load(f)
                                
                            # 更新参数
                            skill.parameters["cooldown"] = legacy_skill_config.get("cooldown", 0.0)
                            skill.parameters["press_delay"] = legacy_skill_config.get("press_delay", 0.0)
                            skill.parameters["release_delay"] = legacy_skill_config.get("release_delay", 0.05)
                            skill.enabled = legacy_skill_config.get("enabled", True)
                            
                            # 更新图标信息
                            if "position" in legacy_skill_config:
                                pos = legacy_skill_config["position"]
                                skill.icon.position["x1"] = pos.get("x1", 0)
                                skill.icon.position["y1"] = pos.get("y1", 0)
                                skill.icon.position["x2"] = pos.get("x2", 0)
                                skill.icon.position["y2"] = pos.get("y2", 0)
                            
                            skill.icon.img_path = legacy_skill_config.get("img_path", "")
                            skill.icon.threshold = legacy_skill_config.get("threshold", 0.7)
                            
                            # 添加默认动作
                            skill.actions = [Action(type="keypress", key=skill.key, hold_time=0.05)]
                            
                            print(f"已迁移技能: {skill_name}")
                        except Exception as e:
                            print(f"迁移技能{skill_name}配置时出错: {str(e)}")
                    
                    # 添加到数据库
                    self.skills_db.add_skill(skill)
                
                # 保存更新后的配置
                self.save_system_config()
                self.save_skills_db()
                
                print("旧版配置迁移完成")
                return True
            else:
                print("未找到旧版配置文件，无需迁移")
                return False
                
        except Exception as e:
            print(f"迁移旧版数据出错: {str(e)}")
            return False


# 创建全局配置管理器实例
config_manager = ConfigManager() 