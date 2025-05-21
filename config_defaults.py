# 应用程序默认配置
# 用于初始化配置文件和提供默认值

# 语音设置默认值
VOICE_SETTINGS = {
    'rate': 5,
    'volume': 80,
    'selected_voice': 'zh-CN-XiaoxiaoNeural'
}

# 语音警告设置
VOICE_ALERT_SETTINGS = {
    'enabled': False,
    'threshold': 30.0,
    'cooldown': 5.0,
    'warning_text': '{name}血量过低，仅剩{health}%',
    'team_danger_enabled': False,
    'team_danger_threshold': 2,
    'team_danger_text': '警告，团队状态危险，{count}名队友血量过低'
}

# 血条颜色默认设置
DEFAULT_HP_COLOR = {
    # 这些值会被转换为numpy数组，这里只保存默认值
    # 实际使用时会转换为numpy的uint8数组
    'lower': [0, 0, 160],  # BGR格式
    'upper': [80, 80, 255]  # BGR格式
}

# 自动选择设置
AUTO_SELECT_SETTINGS = {
    'enabled': False,
    'health_threshold': 30.0,
    'cooldown_time': 3.0,
    'priority_roles': ['奶妈', '治疗'],
    'priority_profession': ''
}

# 快捷键设置
HOTKEY_SETTINGS = {
    'start_monitoring': 'f9',
    'stop_monitoring': 'f10'
}

# UI设置
UI_SETTINGS = {
    'theme': 'auto',
    'language': 'zh_CN',
    'sampling_rate': 500
}

# 所有默认配置
DEFAULT_CONFIG = {
    'voice_settings': VOICE_SETTINGS,
    'low_health_alert_settings': VOICE_ALERT_SETTINGS,
    'default_hp_color': DEFAULT_HP_COLOR,
    'auto_select': AUTO_SELECT_SETTINGS,
    'hotkeys': HOTKEY_SETTINGS,
    'ui_settings': UI_SETTINGS
} 