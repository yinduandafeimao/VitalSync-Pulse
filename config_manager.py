import os
import json

class ConfigManager:
    """配置管理类，负责处理应用程序的配置读写"""
    CONFIG_FILE = 'config.json'
    
    @classmethod
    def save_settings(cls, settings_dict):
        """保存设置到配置文件
        
        参数:
            settings_dict: 包含设置的字典
            
        返回:
            bool: 保存是否成功
        """
        try:
            existing_config = {}
            if os.path.exists(cls.CONFIG_FILE):
                with open(cls.CONFIG_FILE, 'r', encoding='utf-8') as f:
                    existing_config = json.load(f)
            
            # 更新设置
            for key, value in settings_dict.items():
                existing_config[key] = value
            
            with open(cls.CONFIG_FILE, 'w', encoding='utf-8') as f:
                json.dump(existing_config, f, indent=4, ensure_ascii=False)
            return True
        except Exception as e:
            print(f"保存设置失败: {e}")
            return False
    
    @classmethod
    def load_settings(cls):
        """从配置文件加载设置
        
        返回:
            dict: 设置字典，失败时返回空字典
        """
        try:
            if os.path.exists(cls.CONFIG_FILE):
                with open(cls.CONFIG_FILE, 'r', encoding='utf-8') as f:
                    return json.load(f)
            return {}
        except Exception as e:
            print(f"加载设置失败: {e}")
            return {}
    
    @classmethod
    def save_specific_config(cls, config_name, config_data):
        """保存特定配置到指定文件
        
        参数:
            config_name: 配置文件名（不含扩展名）
            config_data: 配置数据字典
            
        返回:
            bool: 保存是否成功
        """
        try:
            config_file = f"{config_name}_config.json"
            with open(config_file, 'w', encoding='utf-8') as f:
                json.dump(config_data, f, indent=4, ensure_ascii=False)
            return True
        except Exception as e:
            print(f"保存配置 {config_name} 失败: {e}")
            return False
    
    @classmethod
    def load_specific_config(cls, config_name):
        """加载特定配置文件
        
        参数:
            config_name: 配置文件名（不含扩展名）
            
        返回:
            dict: 配置数据字典，失败时返回空字典
        """
        try:
            config_file = f"{config_name}_config.json"
            if os.path.exists(config_file):
                with open(config_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            return {}
        except Exception as e:
            print(f"加载配置 {config_name} 失败: {e}")
            return {}
    
    @classmethod
    def delete_specific_config(cls, config_name):
        """删除特定配置文件
        
        参数:
            config_name: 配置文件名（不含扩展名）
            
        返回:
            bool: 删除是否成功
        """
        try:
            config_file = f"{config_name}_config.json"
            if os.path.exists(config_file):
                os.remove(config_file)
                return True
            return False
        except Exception as e:
            print(f"删除配置 {config_name} 失败: {e}")
            return False 