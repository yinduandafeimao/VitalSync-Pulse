# 配置管理系统集成指南

本文档说明如何将ConfigManager配置管理系统集成到VitalSync项目中，实现统一的配置管理。

## 1. 文件结构

配置管理系统由以下几个文件组成:

- `config_manager.py` - 核心配置管理类
- `config_defaults.py` - 默认配置值定义
- `config_usage_demo.py` - 使用示例

在项目中会生成以下配置文件:

- `main_config.ini` - 通用配置文件(INI格式)
- `main_config.json` - 复杂数据结构配置(JSON格式)
- 还可以创建其他命名空间的配置文件，如`hotkeys_config.json`等

## 2. 集成步骤

### 2.1 导入必要的模块

在需要使用配置的文件开头导入:

```python
from config_manager import get_config
from config_defaults import DEFAULT_CONFIG
```

### 2.2 加载配置

使用`get_config()`获取配置实例并确保配置文件存在:

```python
def load_settings(self):
    """加载应用程序设置"""
    config_manager = get_config()
    
    try:
        # 确保默认配置存在
        if not config_manager.get_json(''):
            # 导入默认配置
            config_manager.set_json('', DEFAULT_CONFIG)
            config_manager.save_config()
            logging.info("已创建默认配置文件")
        
        # 从配置中读取和应用设置
        voice_settings = config_manager.get_json('voice_settings', DEFAULT_CONFIG['voice_settings'])
        rate_value = voice_settings.get('rate', 5)
        # 应用设置到UI...
```

### 2.3 保存配置

使用配置管理器保存设置而非直接写入文件:

```python
def save_settings(self):
    """保存应用程序设置"""
    config_manager = get_config()
    
    try:
        # 获取当前语音设置值
        rate_value = self.voiceSpeedSlider.value()
        volume_value = self.volumeSlider.value()
        selected_voice_name = self.voiceTypeCombo.currentText()
        
        # 更新配置
        voice_settings = {
            'rate': rate_value,
            'volume': volume_value,
            'selected_voice': selected_voice_name
        }
        config_manager.set_json('voice_settings', voice_settings)
        
        # 保存配置到文件
        config_manager.save_config()
        logging.info("设置已保存")
    except Exception as e:
        logging.error(f"保存配置失败: {e}")
```

### 2.4 替换特定配置文件的管理

对于项目中多个特定配置文件，如热键配置、队友配置等，可以使用不同的命名空间:

```python
# 获取热键配置
hotkey_config = ConfigManager.get_instance('hotkeys')

# 加载热键配置
def load_hotkey_config(self):
    config = ConfigManager.get_instance('hotkeys')
    start_key = config.get_json('start_monitoring', 'f9')
    stop_key = config.get_json('stop_monitoring', 'f10')
    # 应用设置...
```

### 2.5 集成日志系统

确保项目有合适的日志配置:

```python
import logging

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("vitalsync.log"),
        logging.StreamHandler()
    ]
)
```

## 3. 主要修改点

以下是项目中需要主要修改的地方:

1. `MainWindow.load_settings()` - 使用ConfigManager替换直接文件读取
2. `MainWindow.save_settings()` - 使用ConfigManager替换直接文件写入
3. `HealthMonitor.load_hotkey_config()` - 使用专用命名空间配置
4. `MainWindow.save_default_colors()` - 使用ConfigManager的JSON能力
5. 其他分散的配置保存代码 - 统一到ConfigManager管理

## 4. 优势与好处

- **统一管理**: 所有配置集中管理，避免分散的文件操作
- **默认值支持**: 内置默认值机制，避免重复的默认值检查
- **类型转换**: 自动进行类型转换，简化读取代码
- **错误处理**: 统一的错误处理和日志机制
- **分层结构**: 支持点分隔路径访问嵌套配置
- **格式兼容**: 同时支持INI和JSON格式，适应不同类型配置
- **可扩展**: 通过命名空间支持多个相互独立的配置文件

## 5. 使用示例

运行`config_usage_demo.py`查看详细的使用示例:

```
python config_usage_demo.py
```

该示例演示了基本的配置读写、嵌套访问、默认值等功能。 