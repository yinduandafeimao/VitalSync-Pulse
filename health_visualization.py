import cv2
import numpy as np
import pyautogui
from PyQt5.QtCore import Qt, pyqtSignal, QObject
from PyQt5.QtWidgets import QFrame, QLabel, QHBoxLayout, QVBoxLayout
from PyQt5.QtGui import QColor

class HealthVisualization(QObject):
    """血条可视化类，负责处理血条数据的可视化显示"""
    
    # 定义信号
    update_ui_signal = pyqtSignal(list)  # 血量数据更新信号
    
    def __init__(self, parent=None):
        """初始化血条可视化管理器"""
        super().__init__(parent)
        self.health_bars_frame = None
        self.scale_factor = 3
        self.max_width = 300
        self.team_members = []  # 添加队友列表属性
        
    def set_team_members(self, team_members):
        """设置队友列表
        
        参数:
            team_members: 队友列表
        """
        self.team_members = team_members
        
    def set_health_bars_frame(self, frame):
        """设置血条显示框架
        
        参数:
            frame: QFrame对象，用于显示血条
        """
        self.health_bars_frame = frame
    
    def init_health_bars_ui(self, team_members):
        """初始化血条UI显示
        
        参数:
            team_members: 队友列表
        """
        if not self.health_bars_frame:
            return False
        
        # 更新队友列表    
        self.team_members = team_members
            
        # 清除现有布局中的所有组件
        current_layout = self.health_bars_frame.layout()
        if current_layout is not None:
            while current_layout.count():
                item = current_layout.takeAt(0)
                widget = item.widget()
                if widget:
                    widget.deleteLater()
        else:
            # 如果布局不存在，则创建一个新的
            new_layout = QVBoxLayout(self.health_bars_frame)
            new_layout.setSpacing(12)
            new_layout.setContentsMargins(15, 15, 15, 15)
            self.health_bars_frame.setLayout(new_layout)
        
        # 按血条位置y1, x1排序队员
        sorted_members = sorted(team_members, key=lambda m: (m.y1, m.x1))
        
        # 为每个队友添加健康条
        for i, member in enumerate(sorted_members):
            self.add_health_bar_card(i, member.name, member.profession)
            
        # 如果没有队友，显示提示信息
        if not team_members and self.health_bars_frame.layout() is not None:
            noMemberLabel = QLabel("没有队友信息。请在队员识别页面添加队友。")
            noMemberLabel.setAlignment(Qt.AlignCenter)
            self.health_bars_frame.layout().addWidget(noMemberLabel)
        
        # 强制更新框架
        self.health_bars_frame.update()
        return True
    
    def add_health_bar_card(self, index, name, profession):
        """添加血条卡片
        
        参数:
            index: 队友索引
            name: 队友名称
            profession: 队友职业
        """
        # 创建水平布局，每一行一个队员
        memberCard = QFrame()
        memberCard.setObjectName(f"member_card_{index}")
        memberCard.setFixedHeight(60)
        memberCard.setStyleSheet("background-color: transparent;")
        memberLayout = QHBoxLayout(memberCard)
        memberLayout.setContentsMargins(5, 0, 5, 0)
        memberLayout.setSpacing(10)
        
        # 队员名称
        nameLabel = QLabel(name)
        nameLabel.setObjectName(f"name_label_{index}")
        nameLabel.setStyleSheet("font-size: 14px; font-weight: bold;")
        nameLabel.setFixedWidth(80)
        
        # 职业名称
        roleLabel = QLabel(str(profession))
        roleLabel.setStyleSheet("color: #666; font-size: 12px;")
        roleLabel.setFixedWidth(60)
        roleLabel.setToolTip(str(profession))
        
        # 血条容器
        healthBarContainer = QFrame()
        healthBarContainer.setFixedHeight(25)
        healthBarContainer.setStyleSheet("background-color: #333; border-radius: 5px;")
        healthBarContainer.setMaximumWidth(self.max_width)
        healthBarContainerLayout = QHBoxLayout(healthBarContainer)
        healthBarContainerLayout.setContentsMargins(2, 2, 2, 2)
        healthBarContainerLayout.setSpacing(0)
        
        # 血条
        healthBar = QFrame()
        healthBar.setObjectName(f"health_bar_{index}")
        healthBar.setFixedHeight(21)
        
        # 根据索引设置不同的颜色和默认百分比
        color = "#2ecc71"  # 默认绿色
        default_percentage = 90
        if index % 4 == 1:
            default_percentage = 70
        elif index % 4 == 2:
            default_percentage = 50
            color = "#f39c12"  # 黄色
        elif index % 4 == 3:
            default_percentage = 30
            color = "#e74c3c"  # 红色
        
        # 计算血条宽度
        bar_width = min(int(default_percentage * self.scale_factor), self.max_width)
        
        healthBar.setStyleSheet(f"background-color: {color}; border-radius: 3px;")
        healthBar.setFixedWidth(bar_width)
        
        healthBarContainerLayout.addWidget(healthBar)
        healthBarContainerLayout.addStretch(1)
        
        # 血量百分比
        valueLabel = QLabel(f"{default_percentage}%")
        valueLabel.setObjectName(f"value_label_{index}")
        valueLabel.setStyleSheet(f"color: {color}; font-weight: bold; font-size: 15px;")
        valueLabel.setAlignment(Qt.AlignCenter)
        valueLabel.setFixedWidth(60)
        
        # 调试标签
        debugLabel = QLabel(f"dbg:ok")
        debugLabel.setObjectName(f"debug_label_{index}")
        debugLabel.setStyleSheet("color: #999; font-size: 8px;")
        debugLabel.setFixedWidth(50)
        
        # 添加到卡片布局
        memberLayout.addWidget(nameLabel)
        memberLayout.addWidget(roleLabel)
        memberLayout.addWidget(healthBarContainer)
        memberLayout.addWidget(valueLabel)
        memberLayout.addWidget(debugLabel)
        
        # 添加到主布局
        self.health_bars_frame.layout().addWidget(memberCard)
        
        # 添加分隔线（除了最后一个）
        if index < len(self.team_members) - 1:
            separator = QFrame()
            separator.setFrameShape(QFrame.HLine)
            separator.setFrameShadow(QFrame.Sunken)
            separator.setStyleSheet("background-color: #e0e0e0;")
            separator.setFixedHeight(1)
            self.health_bars_frame.layout().addWidget(separator)
    
    def update_health_display(self, health_data):
        """更新血量显示
        
        参数:
            health_data: 包含队友血量信息的列表 [(名称, 血量百分比, 是否存活),...]
        """
        if not self.health_bars_frame:
            return
            
        # 将 health_data 转为字典以便按名称查找
        health_data_map = {item[0]: (item[1], item[2]) for item in health_data}
        
        # 如果 health_data 为空，清空或重置UI
        if not health_data:
            # 遍历所有血条元素，设置为零值
            for ui_idx in range(self.health_bars_frame.layout().count()):
                item = self.health_bars_frame.layout().itemAt(ui_idx)
                widget = item.widget()
                if widget and isinstance(widget, QFrame) and widget.objectName().startswith("member_card_"):
                    idx = int(widget.objectName().split("_")[-1])
                    
                    health_bar = widget.findChild(QFrame, f"health_bar_{idx}")
                    value_label = widget.findChild(QLabel, f"value_label_{idx}")
                    debug_label = widget.findChild(QLabel, f"debug_label_{idx}")
                    name_label = widget.findChild(QLabel, f"name_label_{idx}")
                    
                    if health_bar:
                        health_bar.setFixedWidth(0)
                        health_bar.setStyleSheet("background-color: #555; border-radius: 3px;")
                    if value_label:
                        value_label.setText("0.0%")
                        value_label.setStyleSheet("color: #777; font-weight: bold; font-size: 15px;")
                    if debug_label:
                        debug_label.setText("dbg: --")
                    if name_label:
                        name_label.setStyleSheet("font-size: 14px; font-weight: bold;")
            
            self.health_bars_frame.update()
            return
        
        # 更新每个队友的血条显示
        for ui_idx in range(self.health_bars_frame.layout().count()):
            item = self.health_bars_frame.layout().itemAt(ui_idx)
            widget = item.widget()
            if not widget or not isinstance(widget, QFrame) or not widget.objectName().startswith("member_card_"):
                continue
                
            idx = int(widget.objectName().split("_")[-1])
            
            # 获取名称标签和名称
            name_label = widget.findChild(QLabel, f"name_label_{idx}")
            if not name_label:
                continue
                
            current_member_name = name_label.text()
            
            # 其他UI元素
            health_bar = widget.findChild(QFrame, f"health_bar_{idx}")
            value_label = widget.findChild(QLabel, f"value_label_{idx}")
            debug_label = widget.findChild(QLabel, f"debug_label_{idx}")
            
            # 检查当前队友是否在传入的 health_data 中
            if current_member_name not in health_data_map:
                # 设置为N/A状态
                if health_bar:
                    health_bar.setFixedWidth(0)
                    health_bar.setStyleSheet("background-color: #555; border-radius: 3px;")
                if value_label:
                    value_label.setText("N/A")
                    value_label.setStyleSheet("color: #777; font-weight: bold; font-size: 15px;")
                if name_label:
                    name_label.setStyleSheet("color: #777777; font-size: 14px; font-weight: bold;")
                if debug_label:
                    debug_label.setText("dbg: N/A")
                continue
            
            # 解包健康数据
            health_percentage, is_alive = health_data_map[current_member_name]
            
            # 更新调试标签
            if debug_label:
                debug_label.setText(f"内存:{health_percentage:.1f}%")
            
            # 根据存活状态和血量设置颜色
            final_color = "#2ecc71"  # 默认健康绿色
            if not is_alive:
                final_color = "#777777"  # 灰色表示离线/死亡
                health_percentage = 0.0
            elif health_percentage <= 30:
                final_color = "#e74c3c"  # 红色表示危险
            elif health_percentage <= 60:
                final_color = "#f39c12"  # 黄色表示警告
            
            # 计算血条宽度
            new_width = min(int(health_percentage * self.scale_factor), self.max_width)
            if new_width < 0:
                new_width = 0
            
            # 更新血条
            if health_bar:
                current_stylesheet = health_bar.styleSheet()
                new_stylesheet = f"background-color: {final_color}; border-radius: 3px;"
                current_bar_width = health_bar.width()
                
                if abs(current_bar_width - new_width) > 1e-9 or current_stylesheet != new_stylesheet:
                    health_bar.setStyleSheet(new_stylesheet)
                    health_bar.setFixedWidth(new_width)
                    
                    # 更新布局
                    parent_widget = health_bar.parentWidget()
                    if parent_widget and parent_widget.layout():
                        parent_widget.layout().invalidate()
                        parent_widget.updateGeometry()
                    if widget:
                        widget.update()
            
            # 更新值标签
            if value_label:
                value_label.setText(f"{health_percentage:.1f}%")
                value_label.setStyleSheet(f"color: {final_color}; font-weight: bold; font-size: 15px;")
            
            # 更新名称标签
            if name_label:
                if not is_alive:
                    name_label.setStyleSheet("color: #777777; font-size: 14px; font-weight: bold;")
                else:
                    name_label.setStyleSheet("font-size: 14px; font-weight: bold;")
            
            # 更新各个元素
            if health_bar: health_bar.update()
            if value_label: value_label.update()
            if name_label: name_label.update()
            if debug_label: debug_label.update()
        
        # 更新整个框架
        self.health_bars_frame.update()
    
    def get_color_at_position(self, x, y):
        """获取屏幕指定位置的颜色
        
        参数:
            x: 横坐标
            y: 纵坐标
            
        返回:
            tuple: RGB颜色元组
        """
        try:
            screenshot = pyautogui.screenshot()
            pixel_color = screenshot.getpixel((x, y))
            return pixel_color[:3]  # 返回RGB值
        except Exception as e:
            print(f"获取屏幕颜色失败: {e}")
            return (0, 0, 0)
    
    def capture_health_bar_color(self, x, y):
        """捕获血条颜色并计算阈值
        
        参数:
            x: 横坐标
            y: 纵坐标
            
        返回:
            tuple: (color_lower, color_upper) 颜色阈值下限和上限
        """
        try:
            # 获取RGB颜色
            rgb_tuple = self.get_color_at_position(x, y)
            
            # 转换为BGR
            bgr_values = (rgb_tuple[2], rgb_tuple[1], rgb_tuple[0])  # B, G, R
            
            # 创建颜色阈值
            color_lower = np.array([max(0, c - 30) for c in bgr_values], dtype=np.uint8)
            color_upper = np.array([min(255, c + 30) for c in bgr_values], dtype=np.uint8)
            
            return (color_lower, color_upper)
        except Exception as e:
            print(f"捕获血条颜色失败: {e}")
            return (np.array([0, 0, 0], dtype=np.uint8), np.array([255, 255, 255], dtype=np.uint8))
    
    def capture_health_bar_screenshot(self, x1, y1, x2, y2):
        """截取血条区域的屏幕截图
        
        参数:
            x1: 左上角x坐标
            y1: 左上角y坐标
            x2: 右下角x坐标
            y2: 右下角y坐标
            
        返回:
            numpy.ndarray: 截图图像(BGR格式)
        """
        try:
            # 获取屏幕截图
            width = x2 - x1
            height = y2 - y1
            screenshot = pyautogui.screenshot(region=(x1, y1, width, height))
            
            # 转换为BGR格式
            img_np = np.array(screenshot)
            img_bgr = cv2.cvtColor(img_np, cv2.COLOR_RGB2BGR)
            
            return img_bgr
        except Exception as e:
            print(f"截取血条截图失败: {e}")
            return None
    
    def calculate_health_percentage(self, img, color_lower, color_upper):
        """计算血条的血量百分比
        
        参数:
            img: 血条区域图像(BGR格式)
            color_lower: 血条颜色阈值下限
            color_upper: 血条颜色阈值上限
            
        返回:
            float: 血量百分比(0-100)
        """
        try:
            # 创建颜色掩码
            mask = cv2.inRange(img, color_lower, color_upper)
            
            # 计算掩码中非零像素的数量
            non_zero_pixels = cv2.countNonZero(mask)
            
            # 计算总像素数
            total_pixels = img.shape[0] * img.shape[1]
            
            # 计算比例
            if total_pixels > 0:
                percentage = (non_zero_pixels / total_pixels) * 100
            else:
                percentage = 0
            
            return percentage
        except Exception as e:
            print(f"计算血量百分比失败: {e}")
            return 0.0 