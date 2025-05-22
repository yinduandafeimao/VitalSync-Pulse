"""
技能循环界面集成脚本

该脚本用于将技能循环界面集成到VitalSync主UI中。
按照以下步骤使用此脚本：
1. 确保已安装所有依赖库
2. 确保skill_cycle.py和skill_cycle_ui.py在同一目录下
3. 将本脚本放在和fluent_ui.py同一目录下
4. 在fluent_ui.py所在目录执行此脚本

集成步骤:
1. 在fluent_ui.py中添加导入语句
2. 在MainWindow的__init__方法中添加技能循环界面实例
3. 添加initSkillCycleInterface()方法
4. 在initNavigation()方法中添加技能循环界面到导航栏
"""

import os
import re

# 要修改的文件路径
target_file = 'fluent_ui.py'

# 备份原始文件
backup_file = f'{target_file}.bak'
if not os.path.exists(backup_file):
    with open(target_file, 'r', encoding='utf-8') as src:
        with open(backup_file, 'w', encoding='utf-8') as dst:
            dst.write(src.read())
    print(f'已创建备份文件: {backup_file}')

# 读取文件内容
with open(target_file, 'r', encoding='utf-8') as f:
    content = f.read()

# 步骤1: 添加导入语句
import_statement = 'from skill_cycle_ui import SkillCycleInterface  # 导入技能循环界面'
if 'from skill_cycle_ui import SkillCycleInterface' not in content:
    # 在导入部分的结尾添加导入语句
    import_pattern = r'from PyQt5\.QtWidgets import \([^)]+\)'
    content = re.sub(import_pattern, lambda m: m.group(0) + '\n' + import_statement, content)
    print('已添加导入语句')

# 步骤2: 在MainWindow的__init__方法中添加技能循环界面实例
init_pattern = r'(self\.voiceSettingsInterface = QWidget\(\)[^\n]*\n\s+self\.voiceSettingsInterface\.setObjectName\("voiceSettingsInterface"\))'
skill_cycle_instance = '''
        # 技能循环界面实例
        self.skillCycleInterface = QWidget()
        self.skillCycleInterface.setObjectName("skillCycleInterface")'''
if 'self.skillCycleInterface = QWidget()' not in content:
    content = re.sub(init_pattern, lambda m: m.group(0) + skill_cycle_instance, content)
    print('已添加技能循环界面实例')

# 步骤3: 在界面初始化部分添加对技能循环界面的初始化
init_ui_pattern = r'(self\.initVoiceSettingsInterface\(\) # 新增：调用语音设置界面初始化)'
init_skill_cycle = '''
        self.initSkillCycleInterface()  # 初始化技能循环界面'''
if 'self.initSkillCycleInterface()' not in content:
    content = re.sub(init_ui_pattern, lambda m: m.group(0) + init_skill_cycle, content)
    print('已添加界面初始化代码')

# 步骤4: 在initNavigation方法中添加技能循环界面到导航栏
nav_pattern = r'(self\.addSubInterface\(self\.voiceSettingsInterface, FIF\.MICROPHONE, \'语音设置\'\) # 使用 FIF\.MICROPHONE 图标)'
add_to_nav = '''
        self.addSubInterface(self.skillCycleInterface, FIF.GAME, '技能循环')  # 使用 FIF.GAME 图标'''
if 'self.addSubInterface(self.skillCycleInterface, FIF.GAME' not in content:
    content = re.sub(nav_pattern, lambda m: m.group(0) + add_to_nav, content)
    print('已添加导航栏代码')

# 步骤5: 添加initSkillCycleInterface方法
# 寻找类似的init方法后面的位置
method_pattern = r'(def initVoiceSettingsInterface\(self\):[\s\S]+?)(\n\s+def )'
skill_cycle_method = '''

    def initSkillCycleInterface(self):
        """初始化技能循环界面"""
        # 创建布局
        layout = QVBoxLayout(self.skillCycleInterface)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # 创建技能循环界面实例并添加到布局
        skill_cycle_widget = SkillCycleInterface(self)
        layout.addWidget(skill_cycle_widget)
        
    '''
if 'def initSkillCycleInterface(self):' not in content:
    content = re.sub(method_pattern, lambda m: m.group(1) + skill_cycle_method + m.group(2), content)
    print('已添加initSkillCycleInterface方法')

# 写入修改后的内容
with open(target_file, 'w', encoding='utf-8') as f:
    f.write(content)

print('技能循环界面已成功集成到主UI!')
print('请重启应用程序以查看更改。') 