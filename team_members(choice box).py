# 导入所需的库
import cv2
import numpy as np
import pyautogui
import keyboard
import time
import json
import os
import sys
import importlib.util
from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import QRect
from 选择框 import FluentSelectionBox, show_selection_box, TransparentSelectionBox
from prettytable import PrettyTable  # 导入PrettyTable库用于美化输出

# 动态导入带空格的模块
module_name = "Zhu Xian World Health Bar Test(choice box)"
module_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Zhu Xian World Health Bar Test(choice box).py")
spec = importlib.util.spec_from_file_location(module_name, module_path)
health_bar_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(health_bar_module)

# 从模块中获取需要的函数
get_hp_percentage = health_bar_module.get_hp_percentage

class TeamMember:
    """小队成员类
    
    表示游戏中的一个小队成员，包含职业、血量和存活状态等属性。
    每个小队成员有自己的血条位置和颜色设置。
    
    属性:
        name (str): 成员名称
        profession (str): 职业名称
        health_percentage (float): 当前血量百分比
        is_alive (bool): 存活状态
        x1, y1 (int): 血条左上角坐标
        x2, y2 (int): 血条右下角坐标
        hp_color_lower (np.array): 血条颜色HSV下限
        hp_color_upper (np.array): 血条颜色HSV上限
    """
    
    def __init__(self, name, profession):
        """初始化小队成员
        
        参数:
            name (str): 成员名称
            profession (str): 职业名称
        """
        self.name = name
        self.profession = profession
        self.health_percentage = 100.0
        self.is_alive = True
        
        # 血条位置和颜色默认值
        self.x1 = 100
        self.y1 = 100
        self.x2 = 300
        self.y2 = 120
        self.hp_color_lower = np.array([43, 71, 121])
        self.hp_color_upper = np.array([63, 171, 221])
        
        # 配置文件路径
        self.config_dir = os.path.dirname(os.path.abspath(__file__))
        self.config_file = os.path.join(self.config_dir, f"{name}_config.json")
        
        # 确保配置文件目录存在
        os.makedirs(self.config_dir, exist_ok=True)
        
        # 尝试加载配置
        self.load_config()
    
    def load_config(self):
        """从配置文件加载设置
        
        从成员专属的配置文件中读取血条位置坐标和颜色范围的配置信息。
        如果配置文件不存在或读取出错，将使用默认设置。
        """
        try:
            if not os.path.exists(self.config_file):
                print(f"未找到{self.name}的配置文件，将使用默认设置并创建新的配置文件")
                self.save_config()
                return
                
            with open(self.config_file, 'r', encoding='utf-8') as f:
                config = json.load(f)
                
                # 验证配置文件的完整性
                if not all(key in config.get('health_bar', {}) for key in ['coordinates', 'color']):
                    raise ValueError("配置文件格式不正确")
                    
                coords = config['health_bar']['coordinates']
                if not all(key in coords for key in ['x1', 'y1', 'x2', 'y2']):
                    raise ValueError("坐标配置不完整")
                    
                color = config['health_bar']['color']
                if not all(key in color for key in ['lower', 'upper']):
                    raise ValueError("颜色配置不完整")
                
                # 更新配置
                self.x1 = coords['x1']
                self.y1 = coords['y1']
                self.x2 = coords['x2']
                self.y2 = coords['y2']
                self.hp_color_lower = np.array(color['lower'])
                self.hp_color_upper = np.array(color['upper'])
                
        except json.JSONDecodeError:
            print(f"解析{self.name}的配置文件时出错，文件格式不正确。使用默认设置")
            self.save_config()
        except ValueError as e:
            print(f"加载{self.name}的配置文件时出错: {str(e)}。使用默认设置")
            self.save_config()
        except Exception as e:
            print(f"加载{self.name}配置文件时出错: {str(e)}。使用默认设置")
            self.save_config()
    
    def save_config(self):
        """保存设置到配置文件
        
        将当前的血条位置坐标和颜色范围保存到成员专属的配置文件中。
        配置信息包括血条的坐标范围和HSV颜色范围。
        如果配置文件目录不存在，会自动创建。
        """
        config = {
            'profession': self.profession,  # 添加职业信息
            'health_bar': {
                'coordinates': {
                    'x1': self.x1,
                    'y1': self.y1,
                    'x2': self.x2,
                    'y2': self.y2
                },
                'color': {
                    'lower': self.hp_color_lower.tolist(),
                    'upper': self.hp_color_upper.tolist()
                }
            }
        }
        try:
            # 确保配置文件目录存在
            os.makedirs(os.path.dirname(self.config_file), exist_ok=True)
            
            # 使用临时文件来保存配置，以防写入过程中出错导致配置文件损坏
            temp_file = self.config_file + '.tmp'
            with open(temp_file, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=4)
            
            # 如果写入成功，则替换原配置文件
            if os.path.exists(self.config_file):
                os.remove(self.config_file)
            os.rename(temp_file, self.config_file)
            
            print(f"{self.name}的设置已成功保存到配置文件")
        except PermissionError:
            print(f"保存{self.name}配置文件时出错: 没有写入权限")
        except OSError as e:
            print(f"保存{self.name}配置文件时出错: 文件系统错误 - {str(e)}")
        except Exception as e:
            print(f"保存{self.name}配置文件时出错: {str(e)}")
            # 如果临时文件存在，清理它
            if os.path.exists(temp_file):
                try:
                    os.remove(temp_file)
                except:
                    pass
    
    def set_health_bar_position(self):
        """设置血条位置
        
        通过选择框界面获取血条的起始和结束坐标。
        用户可以通过拖动鼠标来选择血条区域。
        """
        print(f"设置{self.name}的血条位置...")
        print("请使用鼠标拖动选择血条区域...")
        
        def on_selection(rect):
            self.x1 = rect.x()
            self.y1 = rect.y()
            self.x2 = rect.x() + rect.width()
            self.y2 = rect.y() + rect.height()
            print(f"{self.name}血条起始坐标设置为: ({self.x1}, {self.y1})")
            print(f"{self.name}血条结束坐标设置为: ({self.x2}, {self.y2})")
            self.save_config()  # 保存新的坐标设置
        
        # 显示选择框并等待用户操作
        result = show_selection_box(on_selection)
        
        # 根据用户操作返回不同的结果
        return result
    
    def set_health_bar_color(self):
        """设置血条颜色
        
        通过用户交互获取血条的颜色。
        用户需要将鼠标移动到血条上并按空格键确认。
        程序会获取该点的HSV颜色值，并设置一个合适的颜色范围用于后续的血条识别。
        """
        print(f"设置{self.name}的血条颜色...")
        print(f"请将鼠标移动到{self.name}血条颜色位置，按空格键获取颜色...")
        while True:
            if keyboard.is_pressed('space'):
                x, y = pyautogui.position()
                # 截取鼠标位置的屏幕
                screenshot = pyautogui.screenshot(region=(x, y, 1, 1))
                frame = np.array(screenshot)
                # 转换为OpenCV格式
                frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
                # 转换到HSV色彩空间
                hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
                # 获取HSV值
                h, s, v = hsv[0, 0]
                # 设置HSV范围（允许一定的颜色变化）
                self.hp_color_lower = np.array([max(0, h-10), max(0, s-50), max(0, v-50)])
                self.hp_color_upper = np.array([min(180, h+10), min(255, s+50), min(255, v+50)])
                print(f"{self.name}的HSV颜色值: ({h}, {s}, {v})")
                print(f"设置{self.name}的HSV范围为: {self.hp_color_lower} - {self.hp_color_upper}")
                self.save_config()  # 保存新的颜色设置
                time.sleep(0.2)  # 防止重复触发
                break
            elif keyboard.is_pressed('esc'):
                print(f"退出{self.name}颜色获取模式")
                break
    
    def update_health(self):
        """更新血量信息
        
        检测当前血条状态，更新血量百分比和存活状态。
        如果检测不到血条，则认为成员已死亡。
        
        返回:
            float: 当前血量百分比
        """
        try:
            # 添加调试输出
            print(f"正在更新 {self.name} 的血量信息")
            print(f"血条位置: ({self.x1}, {self.y1}) - ({self.x2}, {self.y2})")
            print(f"血条颜色范围: {self.hp_color_lower} - {self.hp_color_upper}")
            
            # 使用导入的get_hp_percentage函数获取血量百分比
            hp = get_hp_percentage(self.x1, self.y1, self.x2, self.y2, 
                                  self.hp_color_lower, self.hp_color_upper)
            
            # 检查返回结果
            if isinstance(hp, (int, float)):
                # 只有在结果是合理的数字时才更新
                old_hp = self.health_percentage
                self.health_percentage = hp
                # 如果血量为0，则认为成员已死亡
                old_alive = self.is_alive
                self.is_alive = hp > 0
                
                # 添加血量变化日志
                print(f"{self.name} 血量变化: {old_hp:.1f}% -> {hp:.1f}% | 状态: {'存活' if self.is_alive else '死亡'}")
                
                # 如果有明显变化，记录日志
                if abs(old_hp - hp) > 1 or old_alive != self.is_alive:
                    print(f"[重要] {self.name} 血量或状态发生明显变化!")
                
                return hp
            else:
                print(f"错误: {self.name} 获取到的血量值类型不正确: {type(hp)}")
                return self.health_percentage  # 返回上一次的血量值
        except Exception as e:
            print(f"更新{self.name}血量时出错: {str(e)}")
            import traceback
            traceback.print_exc()  # 打印堆栈跟踪
            # 发生错误时保持原状态
            return self.health_percentage
    
    def __str__(self):
        """返回成员信息的字符串表示"""
        status = "存活" if self.is_alive else "死亡"
        # 使用简单字符串格式，方便在表格中显示
        return f"{self.name} ({self.profession}): 血量 {self.health_percentage:.1f}%, 状态: {status}"


class Team:
    """小队类
    
    管理多个小队成员，提供批量操作和状态监控功能。
    
    属性:
        members (list): 小队成员列表
    """
    
    def __init__(self):
        """初始化小队
        
        在创建小队实例时，自动扫描当前目录下的所有配置文件，
        根据文件名解析队员信息并添加到小队列表中。
        """
        self.members = []
        
        # 获取当前目录路径
        current_dir = os.path.dirname(os.path.abspath(__file__))
        
        # 扫描当前目录下的所有文件
        for filename in os.listdir(current_dir):
            # 检查是否是队员配置文件，排除系统配置文件
            if filename.endswith('_config.json') and filename != 'hotkeys_config.json':
                try:
                    # 排除一些常见的系统配置文件名
                    if filename.startswith(('hotkeys', 'settings', 'config', 'system')):
                        print(f'跳过系统配置文件: {filename}')
                        continue
                        
                    # 从文件名中提取队员名称
                    member_name = filename[:-12]  # 移除'_config.json'
                    
                    # 读取配置文件获取职业信息
                    config_path = os.path.join(current_dir, filename)
                    with open(config_path, 'r', encoding='utf-8') as f:
                        config = json.load(f)
                        
                        # 检查配置文件是否包含必要字段（确认是队友配置）
                        if 'profession' not in config or 'health_bar' not in config:
                            print(f'文件 {filename} 不是有效的队友配置文件，跳过加载')
                            continue
                        
                        # 获取职业信息
                        profession = config.get('profession', '未知')
                        
                        # 添加队员到小队列表
                        self.add_member(member_name, profession)
                        print(f'已从配置文件加载队员: {member_name} ({profession})')
                        
                except Exception as e:
                    print(f'加载配置文件 {filename} 时出错: {str(e)}')
                    continue
    
    def add_member(self, name, profession):
        """添加小队成员
        
        参数:
            name (str): 成员名称
            profession (str): 职业名称
            
        返回:
            TeamMember: 新创建的成员对象
        """
        member = TeamMember(name, profession)
        self.members.append(member)
        print(f"已添加队员: {name} ({profession})")
        return member
    
    def update_all_health(self):
        """更新所有成员的血量信息
        
        返回:
            list: 所有成员的血量信息列表
        """
        results = []
        for member in self.members:
            hp = member.update_health()
            results.append((member.name, hp, member.is_alive))
        return results
    
    def get_alive_members(self):
        """获取所有存活的成员
        
        返回:
            list: 存活成员列表
        """
        return [member for member in self.members if member.is_alive]
    
    def get_dead_members(self):
        """获取所有死亡的成员
        
        返回:
            list: 死亡成员列表
        """
        return [member for member in self.members if not member.is_alive]
    
    def show_config(self):
        """显示所有队友的配置信息
        
        显示每个队友的名称、职业、血条位置坐标和血条颜色范围。
        这个功能可以帮助用户查看和验证所有队友的设置是否正确。
        使用PrettyTable美化输出。
        """
        if not self.members:
            print("小队中没有成员")
            return
        
        print("===== 队友配置信息 =====")
        
        # 创建PrettyTable对象
        table = PrettyTable()
        # 设置表格列名
        table.field_names = ["队员名称", "职业", "血条位置", "HSV颜色下限", "HSV颜色上限"]
        # 设置表格对齐方式
        table.align = "l"  # 左对齐
        
        # 添加队员信息到表格
        for member in self.members:
            position = f"({member.x1}, {member.y1}) - ({member.x2}, {member.y2})"
            table.add_row([
                member.name,
                member.profession,
                position,
                str(member.hp_color_lower),
                str(member.hp_color_upper)
            ])
        
        # 打印表格
        print(table)
    
    def __str__(self):
        """返回小队信息的字符串表示，使用PrettyTable美化输出"""
        if not self.members:
            return "小队中没有成员"
        
        # 创建PrettyTable对象
        table = PrettyTable()
        # 设置表格列名
        table.field_names = ["队员名称", "职业", "血量", "状态"]
        # 设置表格对齐方式
        table.align = "l"  # 左对齐
        # 设置表格边框样式
        table.border = True
        
        # 添加队员信息到表格
        for member in self.members:
            status = "存活" if member.is_alive else "死亡"
            table.add_row([
                member.name,
                member.profession,
                f"{member.health_percentage:.1f}%",
                status
            ])
        
        # 获取存活队员数量
        alive_count = len(self.get_alive_members())
        
        # 返回格式化后的表格字符串
        result = str(table)
        result += f"\n\n存活: {alive_count}/{len(self.members)}"
        return result


def main():
    """主函数
    
    程序的主循环，处理用户输入并执行相应的功能。
    """
    print("===== 诛仙世界小队成员监控系统 =====\n")
    print("按 'a' 键添加队员")
    print("按 'p' 键设置队员血条位置")
    print("按 'c' 键设置队员血条颜色")
    print("按 's' 键显示队友配置信息")
    print("按 'r' 键启动/暂停监控")
    print("按 'q' 键退出程序\n")
    
    team = Team()
    script_running = False
    
    try:
        while True:
            if keyboard.is_pressed('a'):
                # 添加新队员
                print("\n添加新队员:")
                name = input("请输入队员名称: ")
                profession = input("请输入队员职业: ")
                team.add_member(name, profession)
                time.sleep(0.2)  # 防止重复触发
                
            elif keyboard.is_pressed('p'):
                # 设置队员血条位置
                if not team.members:
                    print("请先添加队员")
                else:
                    print("\n选择要设置血条位置的队员:")
                    for i, member in enumerate(team.members):
                        print(f"{i+1}. {member.name} ({member.profession})")
                    try:
                        choice = int(input("请输入队员编号: ")) - 1
                        if 0 <= choice < len(team.members):
                            team.members[choice].set_health_bar_position()
                        else:
                            print("无效的队员编号")
                    except ValueError:
                        print("请输入有效的数字")
                time.sleep(0.2)  # 防止重复触发
                
            elif keyboard.is_pressed('c'):
                # 设置队员血条颜色
                if not team.members:
                    print("请先添加队员")
                else:
                    print("\n选择要设置血条颜色的队员:")
                    for i, member in enumerate(team.members):
                        print(f"{i+1}. {member.name} ({member.profession})")
                    try:
                        choice = int(input("请输入队员编号: ")) - 1
                        if 0 <= choice < len(team.members):
                            team.members[choice].set_health_bar_color()
                        else:
                            print("无效的队员编号")
                    except ValueError:
                        print("请输入有效的数字")
                time.sleep(0.2)  # 防止重复触发
                
            elif keyboard.is_pressed('r'):
                # 启动/暂停监控
                script_running = not script_running
                print("监控已" + ("启动" if script_running else "暂停"))
                time.sleep(0.2)  # 防止重复触发
                
            elif keyboard.is_pressed('s'):
                # 显示队友配置信息
                team.show_config()
                time.sleep(0.2)  # 防止重复触发
                
            elif keyboard.is_pressed('q'):
                # 退出程序
                print("程序已退出")
                break
                
            if script_running and team.members:
                # 更新并显示所有队员的状态
                team.update_all_health()
                os.system('cls' if os.name == 'nt' else 'clear')  # 清屏
                print("===== 诛仙世界小队成员监控系统 =====\n")
                print(team)  # 使用美化后的表格输出
                print("\n按 'r' 键暂停监控，按 'q' 键退出程序")
            
            time.sleep(0.1)  # 减少CPU使用率
            
    except KeyboardInterrupt:
        print("程序已停止")


if __name__ == "__main__":
    main()