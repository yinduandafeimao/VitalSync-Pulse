import os
import json
import logging
from configparser import ConfigParser

class ConfigManager:
    """
    集中管理应用程序配置的类
    使用ConfigParser处理配置文件，并提供统一的读写接口
    """
    
    # 配置文件类型和实例映射
    _instances = {}
    
    @classmethod
    def get_instance(cls, config_name='main'):
        """
        获取指定配置名称的单例实例
        
        参数:
            config_name (str): 配置名称，用于区分不同的配置文件
        
        返回:
            ConfigManager: 配置管理器实例
        """
        if config_name not in cls._instances:
            cls._instances[config_name] = cls(config_name)
        return cls._instances[config_name]
    
    def __init__(self, config_name='main'):
        """
        初始化配置管理器
        
        参数:
            config_name (str): 配置名称，用于区分不同的配置文件
        """
        self.config_name = config_name
        self.config_dir = os.path.dirname(os.path.abspath(__file__))
        
        # 设置配置文件路径
        self.config_file = os.path.join(self.config_dir, f"{config_name}_config.ini")
        self.json_config_file = os.path.join(self.config_dir, f"{config_name}_config.json")
        
        # 创建ConfigParser实例
        self.config_parser = ConfigParser()
        
        # 兼容性字典 (用于保存不适合ini格式的复杂数据)
        self.json_config = {}
        
        # 从文件加载配置
        self.load_config()
    
    def load_config(self):
        """从配置文件加载配置"""
        # 加载ini配置
        if os.path.exists(self.config_file):
            try:
                self.config_parser.read(self.config_file, encoding='utf-8')
                logging.info(f"从 {self.config_file} 加载配置成功")
            except Exception as e:
                logging.error(f"加载配置文件 {self.config_file} 时出错: {str(e)}")
        
        # 加载json配置 (用于不适合ini格式的复杂数据)
        if os.path.exists(self.json_config_file):
            try:
                with open(self.json_config_file, 'r', encoding='utf-8') as f:
                    self.json_config = json.load(f)
                logging.info(f"从 {self.json_config_file} 加载配置成功")
            except Exception as e:
                logging.error(f"加载配置文件 {self.json_config_file} 时出错: {str(e)}")
    
    def save_config(self):
        """保存配置到文件"""
        # 保存ini配置
        try:
            os.makedirs(os.path.dirname(self.config_file), exist_ok=True)
            with open(self.config_file, 'w', encoding='utf-8') as f:
                self.config_parser.write(f)
            logging.info(f"配置已保存到 {self.config_file}")
        except Exception as e:
            logging.error(f"保存配置到 {self.config_file} 时出错: {str(e)}")
        
        # 保存json配置
        if self.json_config:
            try:
                with open(self.json_config_file, 'w', encoding='utf-8') as f:
                    json.dump(self.json_config, f, ensure_ascii=False, indent=4)
                logging.info(f"配置已保存到 {self.json_config_file}")
            except Exception as e:
                logging.error(f"保存配置到 {self.json_config_file} 时出错: {str(e)}")
    
    def get(self, section, key, default=None, value_type=str):
        """
        获取配置值
        
        参数:
            section (str): 配置节
            key (str): 配置键
            default: 默认值
            value_type: 值的类型转换函数
        
        返回:
            获取的配置值，如果不存在则返回默认值
        """
        try:
            if section in self.config_parser and key in self.config_parser[section]:
                value = self.config_parser[section][key]
                if value_type == bool:
                    return value.lower() in ('true', 'yes', '1', 'on')
                return value_type(value)
            return default
        except Exception as e:
            logging.error(f"获取配置 [{section}]{key} 时出错: {str(e)}")
            return default
    
    def set(self, section, key, value):
        """
        设置配置值
        
        参数:
            section (str): 配置节
            key (str): 配置键
            value: 配置值
        """
        if section not in self.config_parser:
            self.config_parser[section] = {}
        
        self.config_parser[section][key] = str(value)
    
    def get_json(self, key, default=None):
        """
        从JSON配置获取值
        
        参数:
            key (str): 配置键 (支持点号分隔的路径，如 'voice_settings.rate')
            default: 默认值
        
        返回:
            获取的配置值，如果不存在则返回默认值
        """
        try:
            if not key:
                return self.json_config
            
            # 处理嵌套键 (如 'voice_settings.rate')
            parts = key.split('.')
            value = self.json_config
            
            for part in parts:
                if isinstance(value, dict) and part in value:
                    value = value[part]
                else:
                    return default
            
            return value
        except Exception as e:
            logging.error(f"获取JSON配置 {key} 时出错: {str(e)}")
            return default
    
    def set_json(self, key, value):
        """
        设置JSON配置值
        
        参数:
            key (str): 配置键 (支持点号分隔的路径，如 'voice_settings.rate')
            value: 配置值
        """
        try:
            if not key:  # 设置整个配置
                if isinstance(value, dict):
                    self.json_config = value
                return
            
            # 处理嵌套键
            parts = key.split('.')
            config = self.json_config
            
            # 遍历路径，创建必要的子字典
            for i, part in enumerate(parts[:-1]):
                if part not in config or not isinstance(config[part], dict):
                    config[part] = {}
                config = config[part]
            
            # 设置最终值
            config[parts[-1]] = value
            
        except Exception as e:
            logging.error(f"设置JSON配置 {key} 时出错: {str(e)}")
    
    def delete_json(self, key):
        """
        删除JSON配置键
        
        参数:
            key (str): 配置键 (支持点号分隔的路径，如 'voice_settings.rate')
        
        返回:
            bool: 删除是否成功
        """
        try:
            if not key:
                return False
            
            parts = key.split('.')
            config = self.json_config
            
            # 遍历到倒数第二层
            for i, part in enumerate(parts[:-1]):
                if part not in config or not isinstance(config[part], dict):
                    return False
                config = config[part]
            
            # 删除最终键
            if parts[-1] in config:
                del config[parts[-1]]
                return True
            return False
            
        except Exception as e:
            logging.error(f"删除JSON配置 {key} 时出错: {str(e)}")
            return False

# 便捷函数 - 获取默认配置管理器实例
def get_config():
    """获取默认配置管理器实例"""
    return ConfigManager.get_instance('main') 