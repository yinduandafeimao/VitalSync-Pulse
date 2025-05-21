import logging
import os
from config_manager import ConfigManager, get_config
from config_defaults import DEFAULT_CONFIG

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

def demo_config_usage():
    """演示如何使用配置管理类"""
    print("=== 配置管理类使用示例 ===")
    
    # 获取默认配置实例
    config = get_config()
    
    # 确保默认配置存在
    if not config.get_json(''):
        print("未找到配置，导入默认配置...")
        config.set_json('', DEFAULT_CONFIG)
        config.save_config()
    
    # 读取配置
    print("\n--- 读取配置示例 ---")
    
    # 读取整个配置
    all_config = config.get_json('')
    print(f"所有配置: {list(all_config.keys()) if all_config else '无'}")
    
    # 读取语音设置
    voice_settings = config.get_json('voice_settings', DEFAULT_CONFIG['voice_settings'])
    print(f"语音设置: {voice_settings}")
    
    # 读取低血量警告设置
    alert_settings = config.get_json('low_health_alert_settings', 
                                  DEFAULT_CONFIG['low_health_alert_settings'])
    print(f"低血量警告设置: {alert_settings}")
    
    # 读取单个设置
    rate = config.get_json('voice_settings.rate', 5)
    print(f"语音速率: {rate}")
    
    # 修改配置示例
    print("\n--- 修改配置示例 ---")
    
    # 修改语音速率
    old_rate = config.get_json('voice_settings.rate', 5)
    new_rate = 7 if old_rate == 5 else 5
    config.set_json('voice_settings.rate', new_rate)
    print(f"修改语音速率: {old_rate} -> {new_rate}")
    
    # 修改警告设置
    old_threshold = config.get_json('low_health_alert_settings.threshold', 30)
    new_threshold = 25 if old_threshold == 30 else 30
    config.set_json('low_health_alert_settings.threshold', new_threshold)
    print(f"修改低血量阈值: {old_threshold} -> {new_threshold}")
    
    # 保存配置
    config.save_config()
    print("配置已保存")
    
    # 增加新的配置段 - UI 设置
    ui_settings = {
        'theme': '跟随系统',
        'language': 'zh_CN',
        'auto_start': False
    }
    config.set_json('ui_settings', ui_settings)
    config.save_config()
    print(f"\n添加新配置段 'ui_settings': {ui_settings}")
    
    # 使用ini部分进行基本配置
    print("\n--- 使用INI配置示例 ---")
    config.set('Basic', 'version', '1.0.0')
    config.set('Basic', 'debug_mode', 'true')
    config.save_config()
    
    # 读取ini设置
    version = config.get('Basic', 'version', 'unknown')
    debug_mode = config.get('Basic', 'debug_mode', 'false', bool)
    print(f"版本: {version}, 调试模式: {debug_mode}")
    
    print("\n=== 演示完成 ===")

if __name__ == "__main__":
    demo_config_usage() 