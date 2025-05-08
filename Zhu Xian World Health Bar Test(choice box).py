# 导入所需的库
import cv2  # OpenCV库，用于图像处理
import numpy as np  # NumPy库，用于数组操作
import pyautogui  # 用于屏幕截图和鼠标操作
import keyboard  # 用于键盘事件监听
import time  # 用于时间相关操作
import json  # 用于JSON文件操作
import os  # 用于操作系统相关功能

def load_config():
    """从配置文件加载设置
    
    从config.json文件中读取血条位置坐标和颜色范围的配置信息。
    如果配置文件不存在或读取出错，将使用默认设置。
    
    全局变量:
        x1, y1: 血条左上角坐标
        x2, y2: 血条右下角坐标
        hp_color_lower: 血条颜色HSV下限
        hp_color_upper: 血条颜色HSV上限
    """
    global x1, y1, x2, y2, hp_color_lower, hp_color_upper
    try:
        with open('config.json', 'r') as f:
            config = json.load(f)  # 加载配置
            x1 = config['health_bar']['coordinates']['x1'] 
            y1 = config['health_bar']['coordinates']['y1']
            x2 = config['health_bar']['coordinates']['x2']
            y2 = config['health_bar']['coordinates']['y2']
            hp_color_lower = np.array(config['health_bar']['color']['lower']) # 转换为NumPy数组
            hp_color_upper = np.array(config['health_bar']['color']['upper']) # 转换为NumPy数组
    except FileNotFoundError: 
        print("未找到配置文件，使用默认设置")
    except Exception as e: 
        print(f"加载配置文件时出错: {str(e)}")

def save_config():
    """保存设置到配置文件
    
    将当前的血条位置坐标和颜色范围保存到config.json文件中。
    配置信息包括血条的坐标范围和HSV颜色范围。
    """
    config = {
        'health_bar': {
            'coordinates': {
                'x1': x1,
                'y1': y1,
                'x2': x2,
                'y2': y2
            },
            'color': {
                'lower': hp_color_lower.tolist(),
                'upper': hp_color_upper.tolist()
            }
        }
    }
    try:
        with open('config.json', 'w') as f:
            json.dump(config, f, indent=4)
        print("设置已保存到配置文件")
    except Exception as e:
        print(f"保存配置文件时出错: {str(e)}")

def get_mouse_position(position_type='start'):
    """获取并显示当前鼠标位置
    
    通过选择框界面获取血条的起始和结束坐标。用户可以通过拖动鼠标来选择血条区域。
    
    参数:
        position_type (str): 'start'表示获取起始位置，其他值表示获取结束位置
    """
    global x1, y1, x2, y2
    
    import sys
    from PySide6.QtWidgets import QApplication
    from PySide6.QtCore import QRect
    from 选择框 import TransparentSelectionBox
    
    def on_selection(rect: QRect):
        global x1, y1, x2, y2
        x1 = rect.x()
        y1 = rect.y()
        x2 = rect.x() + rect.width()
        y2 = rect.y() + rect.height()
        print(f"血条起始坐标设置为: ({x1}, {y1})")
        print(f"血条结束坐标设置为: ({x2}, {y2})")
        save_config()  # 保存新的坐标设置
    
    print("请使用鼠标拖动选择血条区域...")
    app = QApplication.instance() or QApplication(sys.argv)
    window = TransparentSelectionBox(on_selection)
    window.show()
    app.exec()

def get_color_at_position():
    """获取鼠标位置的HSV颜色值
    
    通过用户交互获取血条的颜色。用户需要将鼠标移动到血条上并按空格键确认。
    程序会获取该点的HSV颜色值，并设置一个合适的颜色范围用于后续的血条识别。
    """
    global hp_color_lower, hp_color_upper
    print("请将鼠标移动到血条颜色位置，按空格键获取颜色...")
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
            hp_color_lower = np.array([max(0, h-10), max(0, s-50), max(0, v-50)])
            hp_color_upper = np.array([min(180, h+10), min(255, s+50), min(255, v+50)])
            print(f"HSV颜色值: ({h}, {s}, {v})")
            print(f"设置HSV范围为: {hp_color_lower} - {hp_color_upper}")
            save_config()  # 保存新的颜色设置
            time.sleep(0.2)  # 防止重复触发
            break
        elif keyboard.is_pressed('esc'):
            print("退出颜色获取模式")
            break 

def get_hp_percentage(x1, y1, x2, y2, hp_color_lower, hp_color_upper):
    """获取指定区域内的血条百分比
    
    通过图像处理技术识别并计算血条的剩余百分比。
    
    参数:
        x1, y1 (int): 血条框左上角坐标
        x2, y2 (int): 血条框右下角坐标
        hp_color_lower (np.array): 血条颜色的HSV下限
        hp_color_upper (np.array): 血条颜色的HSV上限
    
    返回:
        float: 血量百分比（0-100）
    """
    # 验证坐标的有效性
    if x1 == x2 or y1 == y2:
        print("错误：起始坐标和结束坐标不能相同")
        return 0
    if x2 < x1 or y2 < y1:
        print("错误：结束坐标x轴、y轴必须大于起始坐标")
        return 0
        
    # 截取屏幕指定区域
    try:
        screenshot = pyautogui.screenshot(region=(x1, y1, x2-x1, y2-y1))
        frame = np.array(screenshot)
        
        # 转换为OpenCV格式
        frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
    
        # 转换到HSV色彩空间
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        
        # 创建血条颜色的掩码
        mask = cv2.inRange(hsv, hp_color_lower, hp_color_upper)
        
        # 从右向左扫描血条
        total_width = x2 - x1
        hp_end = 0
        
        for x in range(total_width-1, -1, -1):
            column = mask[:, x]
            if np.any(column > 0):
                hp_end = x + 1
                break
        
        # 计算血量百分比
        hp_percentage = (hp_end / total_width) * 100
        return hp_percentage
    except Exception as e:
        print(f"错误：处理图像时发生异常 - {str(e)}")
        return 0

# 全局变量初始化
x1, y1 = 100, 100  # 血条左上角默认坐标
x2, y2 = 300, 120  # 血条右下角默认坐标
hp_color_lower = np.array([43, 71, 121])  # 血条颜色HSV下限默认值
hp_color_upper = np.array([63, 171, 221])  # 血条颜色HSV上限默认值
script_running = False  # 控制脚本运行状态的标志

def main():
    """主函数
    
    程序的主循环，处理用户输入并执行相应的功能：
    - 'p'键：设置血条位置
    - 'c'键：设置血条颜色
    - 'r'键：启动/暂停脚本
    - 'q'键：退出程序
    """
    global script_running
    print("按 'p' 键设置血条位置，按 'c' 键设置血条颜色，按 'r' 键启动/暂停脚本，按 'q' 键退出程序")
    
    # 加载配置
    load_config()
    
    try:
        while True:
            if keyboard.is_pressed('p'):
                get_mouse_position()
            elif keyboard.is_pressed('c'):
                get_color_at_position()
            elif keyboard.is_pressed('r'):
                script_running = not script_running
                print("脚本已" + ("启动" if script_running else "暂停"))
                time.sleep(0.2)  # 防止重复触发
            elif keyboard.is_pressed('q'):
                print("程序已退出")
                break
                
            if script_running:
                hp = get_hp_percentage(x1, y1, x2, y2, hp_color_lower, hp_color_upper)
                print(f"当前血量: {hp:.1f}%")
            time.sleep(0.1)  # 减少CPU使用率
            
    except KeyboardInterrupt:
        print("程序已停止")

if __name__ == "__main__":
    main()