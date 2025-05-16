import os
import sys
import cv2
import json
import time
import threading
import pygame
from PyQt5.QtCore import Qt, QTimer, QBuffer, QPoint, QSize, QRect, QUrl
from PyQt5.QtWidgets import QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QDialog, QApplication
from PyQt5.QtGui import QIcon, QColor, QFont

# 导入Fluent组件库
from qfluentwidgets import (FluentWindow, NavigationItemPosition, InfoBar, 
                           InfoBarPosition, NavigationInterface, setThemeColor,
                           FluentIcon as FIF, MessageBox, setTheme)

# 导入自定义模块
from config_manager import ConfigManager
from team_manager import TeamManager
from voice_manager import VoiceManager
from health_visualization import HealthVisualization

# 导入血条校准模块
from health_bar_calibration import HealthBarCalibration, quick_calibration

# 导入血条监控模块
from health_monitor import HealthMonitor

# 导入界面控制器
from ui_controller import UIController

# 定义配置文件名
CONFIG_FILE = 'config.json'

class MainWindow(FluentWindow):
    """主窗口类，应用程序的主界面"""
    
    def __init__(self):
        """初始化主窗口"""
        super().__init__()
        
        # 初始化 pygame mixer
        try:
            pygame.mixer.init()
            pygame.mixer.set_num_channels(16)  # 设置足够多的声道
        except pygame.error as e:
            print(f"Pygame mixer 初始化失败: {e}")
            InfoBar.error(
                title='音频初始化失败',
                content='无法初始化音频播放组件 (pygame.mixer)，语音播报功能将不可用。',
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=5000,
                parent=self
            )
        
        # 设置窗口标题和大小
        self.setWindowTitle('VitalSync')
        self.resize(1200, 700)
        
        # 设置应用强调色
        setThemeColor(QColor(0, 168, 174))
        
        # 启用亚克力效果
        self.navigationInterface.setAcrylicEnabled(True)
        
        # 创建各个管理器实例
        self.init_managers()
        
        # 创建界面
        self.init_interfaces()
        
        # 初始化导航
        self.init_navigation()
        
        # 加载设置
        self.load_settings()
        
        # 加载队友
        self.team_manager.load_teammates()
        
        # 显示提示信息
        InfoBar.success(
            title='初始化完成',
            content='系统已准备就绪',
            orient=Qt.Horizontal,
            isClosable=True,
            position=InfoBarPosition.TOP,
            duration=2000,
            parent=self
        )
        
        # 设置定时器处理 Pygame 事件
        self.pygame_event_timer = QTimer(self)
        self.pygame_event_timer.timeout.connect(self.voice_manager.process_events)
        self.pygame_event_timer.start(100)  # 每 100ms 检查一次
    
    def init_managers(self):
        """初始化各个管理器"""
        # 初始化团队管理器
        self.team_manager = TeamManager()
        
        # 初始化语音管理器
        self.voice_manager = VoiceManager()
        
        # 初始化血条可视化
        self.health_visualization = HealthVisualization(self)
        
        # 初始化健康监控
        self.health_monitor = HealthMonitor(self.team_manager.team)
        # 连接监控信号
        self.health_monitor.signals.update_signal.connect(self.update_health_display)
        self.health_monitor.signals.status_signal.connect(self.update_monitor_status)
        
        # 初始化UI控制器
        self.ui_controller = UIController(self)
    
    def init_interfaces(self):
        """初始化各个界面"""
        # 创建界面容器
        self.teamRecognitionInterface = QWidget()
        self.teamRecognitionInterface.setObjectName("teamRecognitionInterface")
        
        self.healthMonitorInterface = QWidget()
        self.healthMonitorInterface.setObjectName("healthMonitorInterface")
        
        self.assistInterface = QWidget()
        self.assistInterface.setObjectName("assistInterface")
        
        self.settingsInterface = QWidget()
        self.settingsInterface.setObjectName("settingsInterface")
        
        self.voiceSettingsInterface = QWidget()
        self.voiceSettingsInterface.setObjectName("voiceSettingsInterface")
        
        # 设置队员识别界面
        self.ui_controller.setup_team_recognition_interface(self.teamRecognitionInterface)
        
        # 设置血条监控界面并获取血条框架引用
        health_bars_frame = self.ui_controller.setup_health_monitor_interface(
            self.healthMonitorInterface, self.health_monitor)
        
        # 将血条框架传递给健康可视化管理器
        self.health_visualization.set_health_bars_frame(health_bars_frame)
        
        # 设置队员列表
        self.health_visualization.set_team_members(self.team_manager.team.members)
        
        # 初始化血条UI
        self.health_visualization.init_health_bars_ui(self.team_manager.team.members)
    
    def init_navigation(self):
        """初始化导航栏"""
        # 添加子界面
        self.addSubInterface(self.teamRecognitionInterface, FIF.PEOPLE, '队员识别')
        self.addSubInterface(self.healthMonitorInterface, FIF.HEART, '血条监控')
        self.addSubInterface(self.assistInterface, FIF.IOT, '辅助功能')
        self.addSubInterface(self.voiceSettingsInterface, FIF.MICROPHONE, '语音设置')
        
        # 添加底部界面
        self.addSubInterface(
            self.settingsInterface, 
            FIF.SETTING, 
            '系统设置',
            NavigationItemPosition.BOTTOM
        )
    
    def load_settings(self):
        """加载应用程序设置"""
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                config = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            print(f"配置文件 {CONFIG_FILE} 未找到或格式错误，使用默认设置。")
            return
        except Exception as e:
            print(f"加载配置文件时发生未知错误: {e}，使用默认设置。")
            return

        # 加载语音设置
        if 'voice_settings' in config:
            voice_settings = config.get('voice_settings', {})
            rate_value = voice_settings.get('rate', 5)
            volume_value = voice_settings.get('volume', 80)
            self.voice_rate_param = f'+{rate_value * 10 - 50}%'
            self.voice_volume_param = f'+{volume_value - 50}%'
            
            # 更新UI控制器中的设置
            self.ui_controller.update_voice_settings(rate_value, volume_value)
        
        # 加载语音警告设置
        if 'low_health_alert_settings' in config:
            self.ui_controller.load_alert_settings(config.get('low_health_alert_settings', {}))
        
        print(f"设置已从 {CONFIG_FILE} 加载。")

    def save_settings(self):
        """保存应用程序设置"""
        config = {}
        # 尝试读取现有配置，以保留其他可能存在的设置
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                config = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            pass  # 如果文件不存在或无效，则创建一个新的配置

        # 从UI控制器获取语音设置
        voice_settings = self.ui_controller.get_voice_settings()
        if voice_settings:
            config['voice_settings'] = voice_settings
        
        # 获取语音警告设置
        alert_settings = self.ui_controller.get_alert_settings()
        if alert_settings:
            config['low_health_alert_settings'] = alert_settings

        # 写回配置文件
        try:
            with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=4, ensure_ascii=False)
        except Exception as e:
            print(f"保存配置文件时发生错误: {e}")
            InfoBar.error(
                title='保存设置失败',
                content=f'无法写入配置文件 {CONFIG_FILE}，请检查权限。',
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP_RIGHT,
                duration=3000,
                parent=self
            )

    def closeEvent(self, event):
        """窗口关闭事件，确保在关闭时释放资源并保存设置"""
        # 保存最终设置
        self.save_settings()

        # 停止截图相关的定时器
        if self._icon_capture_show_selection_timer and self._icon_capture_show_selection_timer.isActive():
            self._icon_capture_show_selection_timer.stop()
        if self._icon_capture_do_grab_timer and self._icon_capture_do_grab_timer.isActive():
            self._icon_capture_do_grab_timer.stop()

        # 停止健康监控
        if hasattr(self, 'health_monitor'):
            self.health_monitor.release_resources()
            
        # 停止语音工作线程
        print("向语音工作线程发送停止信号...")
        self.speech_queue.put(None)  # 发送停止信号
        self.speech_worker_thread.join(timeout=2)  # 等待最多2秒
        
        # 退出 pygame mixer
        pygame.mixer.quit()

        # 关闭程序时清空队员配置
        print("关闭程序：正在尝试清空所有队员配置...")
        try:
            current_dir = os.path.dirname(os.path.abspath(__file__))
            if self.team and hasattr(self.team, 'members'):
                members_to_delete = list(self.team.members)  # 迭代副本
                deleted_config_files_count = 0
                for member in members_to_delete:
                    if hasattr(member, 'name'):
                        config_filename = f'{member.name}_config.json'
                        config_path = os.path.join(current_dir, config_filename)
                        if os.path.exists(config_path):
                            try:
                                os.remove(config_path)
                                print(f"已删除配置文件: {config_path}")
                                deleted_config_files_count += 1
                            except Exception as e_remove:
                                print(f"删除配置文件 {config_path} 失败: {e_remove}")
                
                if deleted_config_files_count > 0:
                    print(f"共删除了 {deleted_config_files_count} 个队员的配置文件。")
                
                # 清空队伍列表
                self.team.members = []
                print("内存中的队员列表已清空。")

                # 更新健康监控中的队伍引用
                if hasattr(self, 'health_monitor') and self.health_monitor:
                    self.health_monitor.team = self.team
            else:
                print("没有队伍或队员列表无法访问，跳过清空配置。")
        except Exception as e:
            print(f"清空队员配置过程中发生错误: {str(e)}")

        # 调用父类方法
        super().closeEvent(event)

    # 队友管理方法
    def addTeammate(self, name, profession="未知"):
        """添加队友"""
        print(f"\n添加新队友: {name}, 职业: {profession}")
        
        # 使用Team类添加队友
        new_member = self.team.add_member(name, profession)
        
        # 使用全局默认颜色设置(如果有的话)
        if self.default_hp_color_lower is not None and self.default_hp_color_upper is not None:
            import numpy as np
            new_member.hp_color_lower = np.copy(self.default_hp_color_lower)
            new_member.hp_color_upper = np.copy(self.default_hp_color_upper)
            new_member.save_config()  # 保存颜色设置到队员配置文件
        
        # 更新健康监控
        self.health_monitor.team = self.team
        
        # 更新UI
        self.ui_controller.update_teammate_preview(self.team)
        self.ui_controller.init_health_bars_ui(self.team)
        
        # 显示成功提示
        self.ui_controller.show_info_message(
            title='添加成功',
            content=f'队友 {name} ({profession}) 已添加',
            parent=self
        )
        
        # 提示设置血条位置
        confirm_dialog = MessageBox(
            "设置血条位置",
            f"是否立即为 {name} 设置血条位置？",
            self
        )
        confirm_dialog.yesButton.setText("确定")
        confirm_dialog.cancelButton.setText("取消")
        
        if confirm_dialog.exec():
            # 使用选择框设置血条位置
            self.set_health_bar_position(new_member)
        
        return new_member

    def removeTeammate(self, index):
        """移除队友"""
        if not self.team.members or index < 0 or index >= len(self.team.members):
            self.ui_controller.show_warning_message(
                title='无队友',
                content='当前无可移除的队友',
                parent=self
            )
            return
        
        selected_member = self.team.members[index]
        try:
            # 删除配置文件
            config_file = f"{selected_member.name}_config.json"
            config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), config_file)
            if os.path.exists(config_path):
                os.remove(config_path)
            
            # 从队伍中移除队员
            self.team.members.pop(index)
            
            # 更新UI
            self.ui_controller.update_teammate_preview(self.team)
            self.ui_controller.init_health_bars_ui(self.team)
            
            # 更新健康监控
            self.health_monitor.team = self.team
            
            self.ui_controller.show_info_message(
                title='移除成功',
                content=f'队友 {selected_member.name} 已移除',
                parent=self
            )
        except Exception as e:
            self.ui_controller.show_error_message(
                title='移除失败',
                content=f'错误: {str(e)}',
                parent=self
            )

    def loadTeammate(self):
        """加载所有队友配置"""
        print('loadTeammate called')
        try:
            self.team = Team()  # 重新创建Team实例以加载所有配置
            self.health_monitor.team = self.team
            
            # 更新UI
            self.ui_controller.update_teammate_preview(self.team)
            self.ui_controller.init_health_bars_ui(self.team)
            
            self.ui_controller.show_info_message(
                title='加载成功',
                content=f'已加载 {len(self.team.members)} 个队友',
                parent=self
            )
        except Exception as e:
            self.ui_controller.show_error_message(
                title='加载失败',
                content=f'错误: {str(e)}',
                parent=self
            )

    def clearAllTeammates(self):
        """清除所有队友"""
        if not self.team.members:
            self.ui_controller.show_warning_message(
                title='无队友',
                content='当前没有队友可供清除',
                parent=self
            )
            return
            
        # 创建确认对话框
        confirm_dialog = MessageBox(
            "确认清除",
            "确定要清除所有队友吗？该操作不可恢复。",
            self
        )
        confirm_dialog.yesButton.setText("确定")
        confirm_dialog.cancelButton.setText("取消")
        
        if confirm_dialog.exec():
            try:
                # 删除所有队友配置文件
                deleted_count = 0
                for member in self.team.members:
                    config_file = f"{member.name}_config.json"
                    config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), config_file)
                    if os.path.exists(config_path):
                        os.remove(config_path)
                        deleted_count += 1
                
                # 清空队友列表
                self.team.members = []
                
                # 更新UI
                self.ui_controller.update_teammate_preview(self.team)
                self.ui_controller.init_health_bars_ui(self.team)
                
                # 更新健康监控
                self.health_monitor.team = self.team
                
                self.ui_controller.show_info_message(
                    title='清除成功',
                    content=f'已清除 {deleted_count} 个队友',
                    parent=self
                )
            except Exception as e:
                self.ui_controller.show_error_message(
                    title='清除失败',
                    content=f'错误: {str(e)}',
                    parent=self
                )

    # 血条监控方法
    def update_health_display(self, health_data):
        """更新血量显示 - 从健康监控器接收数据后转发给可视化模块"""
        self.health_visualization.update_health_display(health_data)
        
        # 处理血量警告
        if hasattr(self, 'ui_controller'):
            self.ui_controller.check_health_warnings(health_data, self)

    def update_monitor_status(self, status_message):
        """更新监控状态信息"""
        self.ui_controller.update_monitor_status(status_message)

    def update_health_threshold(self, value, label=None):
        """更新自动点击低血量队友的血条阈值"""
        if hasattr(self, 'health_monitor'):
            self.health_monitor.health_threshold = value
            if label:
                label.setText(f'血条阈值: {value}%')
            self.update_monitor_status(f'自动点击阈值已更新为 {value}%')
            # 保存到配置
            if hasattr(self.health_monitor, 'save_auto_select_config'):
                self.health_monitor.save_auto_select_config()

    def update_sampling_rate(self, value):
        """更新监控采样率"""
        if hasattr(self, 'health_monitor'):
            # 转换为更新间隔（秒）
            interval = 1.0 / value if value > 0 else 0.1
            self.health_monitor.update_interval = interval
            self.update_monitor_status(f"采样率已更新: {value} fps (更新间隔: {interval:.2f}秒)")

    def toggle_auto_click_low_health(self, checked):
        """切换自动点击低血量队友功能"""
        if hasattr(self, 'health_monitor'):
            self.health_monitor.auto_select_enabled = checked
            if hasattr(self.health_monitor, 'save_auto_select_config'):
                self.health_monitor.save_auto_select_config()
            status_message = f"自动点击低血量队友功能已{'启用' if checked else '禁用'}"
            self.update_monitor_status(status_message)
            print(status_message)

    def update_priority_profession(self, profession):
        """更新优先职业设置"""
        if hasattr(self, 'health_monitor'):
            # 将"无优先"选项转换为None
            priority = None if profession == "无优先" else profession
            
            # 更新健康监控对象的优先职业
            self.health_monitor.priority_profession = priority
            
            # 保存设置
            self.save_priority_profession_setting()
            
            # 更新状态显示
            status = f"已设置优先职业: {profession}" if priority else "已取消职业优先选择"
            self.update_monitor_status(status)

    def save_priority_profession_setting(self):
        """保存优先职业设置到配置文件"""
        try:
            # 获取自动选择配置文件路径
            config_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "auto_select_config.json")
            
            # 读取现有配置
            if os.path.exists(config_file):
                with open(config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
            else:
                config = {}
            
            # 更新配置
            config['priority_profession'] = self.health_monitor.priority_profession
            
            # 保存配置
            with open(config_file, 'w', encoding='utf-8') as f:
                json.dump(config, f, ensure_ascii=False, indent=4)
                
        except Exception as e:
            print(f"保存优先职业设置失败: {e}")
            self.ui_controller.show_error_message(
                title='保存失败',
                content=f'无法保存优先职业设置: {str(e)}',
                parent=self
            )

    # 健康条位置和颜色设置
    def set_health_bar_position(self, member):
        """设置队员血条位置"""
        from u9009u62e9u6846 import show_selection_box
        
        # 定义选择完成回调
        def on_selection(rect):
            member.x1 = rect.x()
            member.y1 = rect.y()
            member.x2 = rect.x() + rect.width()
            member.y2 = rect.y() + rect.height()
            print(f"{member.name}血条起始坐标设置为: ({member.x1}, {member.y1})")
            print(f"{member.name}血条结束坐标设置为: ({member.x2}, {member.y2})")
            member.save_config()  # 保存新的坐标设置
            
            # 更新UI
            self.ui_controller.update_teammate_preview(self.team)
        
        # 显示选择框
        result = show_selection_box(on_selection)
        return result

    def load_default_colors(self):
        """从配置文件加载默认血条颜色设置"""
        try:
            config_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "default_color_config.json")
            if not os.path.exists(config_file):
                return  # 如果配置文件不存在，使用 None 作为默认值
                
            with open(config_file, 'r', encoding='utf-8') as f:
                config = json.load(f)
                
            if 'default_hp_color' in config:
                import numpy as np
                self.default_hp_color_lower = np.array(config['default_hp_color']['lower'], dtype=np.uint8)
                self.default_hp_color_upper = np.array(config['default_hp_color']['upper'], dtype=np.uint8)
                print(f"已加载默认血条颜色设置")
        except Exception as e:
            print(f"加载默认血条颜色设置失败: {e}")
    
    def save_default_colors(self):
        """保存默认血条颜色设置到配置文件"""
        if self.default_hp_color_lower is None or self.default_hp_color_upper is None:
            return

        try:
            config_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "default_color_config.json")
            config = {
                'default_hp_color': {
                    'lower': self.default_hp_color_lower.tolist(),
                    'upper': self.default_hp_color_upper.tolist()
                }
            }
            with open(config_file, 'w', encoding='utf-8') as f:
                json.dump(config, f, ensure_ascii=False, indent=4)
            print(f"默认血条颜色设置已保存到 {config_file}")
        except Exception as e:
            print(f"保存默认血条颜色设置失败: {e}")
    
    # 语音处理方法
    def _speech_worker_loop(self):
        """语音播报工作线程的主循环"""
        print("语音工作线程已启动。")
        import edge_tts
        import tempfile
        import os
        
        while True:
            try:
                task = self.speech_queue.get()  # 阻塞直到获取任务
                if task is None:  # 收到停止信号
                    print("语音工作线程收到停止信号，准备退出。")
                    self.speech_queue.task_done()
                    break
                
                text, voice, rate, volume = task
                print(f"语音工作线程处理任务: {text[:30]}...")
                
                # 创建唯一的临时文件
                temp_file = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
                output_path = temp_file.name
                temp_file.close()

                # 异步生成语音文件
                async def _generate_speech_async():
                    try:
                        communicate = edge_tts.Communicate(text, voice=voice, rate=rate, volume=volume)
                        await communicate.save(output_path)
                        return output_path
                    except Exception as e:
                        print(f'语音合成时发生异常: {e}')
                        return None

                # 同步执行异步生成
                try:
                    generated_path = asyncio.run(_generate_speech_async())
                except RuntimeError as e:
                    if "cannot run event loop while another loop is running" in str(e):
                        try:
                            loop = asyncio.get_event_loop()
                            generated_path = loop.run_until_complete(_generate_speech_async())
                        except Exception as inner_e:
                            print(f"现有事件循环运行失败: {inner_e}")
                            generated_path = None
                    else:
                        print(f"asyncio RuntimeError: {e}")
                        generated_path = None
                except Exception as e:
                    print(f"语音生成未知错误: {e}")
                    generated_path = None

                # 加载和播放 (如果生成成功)
                if generated_path and os.path.exists(generated_path):
                    try:
                        if not pygame.mixer.get_init():
                            pygame.mixer.init()
                            pygame.mixer.set_num_channels(16)

                        # 加载为 Sound 对象
                        sound = pygame.mixer.Sound(generated_path)
                        
                        # 查找一个空闲的 Channel
                        channel = pygame.mixer.find_channel(True)
                        if channel:
                            # 存储信息以便后续清理
                            self.active_speech[channel] = {'filename': generated_path, 'sound': sound}
                            
                            # 播放声音
                            channel.play(sound)
                        else:
                            print(f"错误: 无法找到空闲的 Pygame 声道!")
                            # 清理
                            if os.path.exists(generated_path):
                                try:
                                    os.remove(generated_path)
                                except:
                                    pass
                    except Exception as e:
                        print(f"播放过程中发生未知错误: {e}")
                        # 清理
                        if os.path.exists(generated_path):
                            try:
                                os.remove(generated_path)
                            except:
                                pass
                elif generated_path:
                    print(f"生成的语音文件不存在: {generated_path}")
                
                self.speech_queue.task_done()
            except Exception as e:
                print(f"语音工作线程发生错误: {e}")
                if 'task' in locals() and task is not None:
                    try:
                        self.speech_queue.task_done()
                    except ValueError:
                        pass 
        print("语音工作线程已退出。")

    def _process_pygame_events(self):
        """处理 Pygame 事件队列和检查播放结束状态"""
        if not pygame.get_init() or not pygame.mixer.get_init():
            return

        finished_channels = []
        for channel, speech_info in list(self.active_speech.items()):
            if not channel.get_busy():
                filename = speech_info.get('filename')
                
                # 尝试删除文件
                if filename and os.path.exists(filename):
                    try:
                        os.remove(filename)
                    except Exception as e:
                        print(f"删除临时文件 {filename} 时发生错误: {e}")
                
                finished_channels.append(channel)

        # 从 active_speech 字典中移除已完成的声道
        for channel in finished_channels:
            if channel in self.active_speech:
                del self.active_speech[channel]

        # 保持 Pygame 内部事件处理正常进行
        pygame.event.pump()

    def play_speech_threaded(self, text, voice='zh-CN-XiaoxiaoNeural'):
        """将语音任务放入队列，由工作线程处理"""
        # 从实例属性获取当前的速率和音量参数
        rate = self.voice_rate_param
        volume = self.voice_volume_param
        
        # 创建任务元组
        task = (text, voice, rate, volume)
        print(f"加入语音任务到队列: {text[:30]}... (voice={voice}, rate={rate}, volume={volume})")
        self.speech_queue.put(task)

    def get_selected_voice(self, combo):
        """根据下拉框选择返回 edge-tts 语音名"""
        mapping = {
            # 标准普通话
            '晓晓 (普通话女)': 'zh-CN-XiaoxiaoNeural',
            '云希 (普通话男)': 'zh-CN-YunxiNeural',
            '晓伊 (普通话女)': 'zh-CN-XiaoyiNeural',
            '云健 (普通话男)': 'zh-CN-YunjianNeural',
            # 台湾普通话
            '晓臻 (台湾女)':   'zh-TW-HsiaoChenNeural',
            '雲哲 (台湾男)':   'zh-TW-YunJheNeural',
            # 香港粤语
            '晓佳 (香港女)':   'zh-HK-HiuGaaiNeural',
            '雲龍 (香港男)':   'zh-HK-WanLungNeural',
        }
        text = combo.currentText()
        return mapping.get(text, 'zh-CN-XiaoxiaoNeural') 

def main():
    """程序入口点"""
    # 设置高DPI支持 - 在创建应用程序之前进行设置
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
    
    app = QApplication(sys.argv)
    
    # 设置全局样式
    app.setStyleSheet("""
    QWidget {
        font-family: "Microsoft YaHei", sans-serif;
    }

    QFrame#cardFrame {
        border: 1px solid rgba(0, 0, 0, 0.1);
        border-radius: 10px;
        background-color: rgba(255, 255, 255, 0.95);
    }

    QLabel {
        font-size: 13px;
        color: #333333;
    }

    QPushButton {
        padding: 8px 16px;
        border-radius: 6px;
        font-weight: 500;
    }

    QLineEdit {
        padding: 8px;
        border-radius: 5px;
        border: 1px solid #e0e0e0;
        background-color: #fafafa;
    }

    QComboBox {
        padding: 8px;
        border-radius: 5px;
        border: 1px solid #e0e0e0;
        background-color: #fafafa;
    }
    """)
    
    # 设置字体
    font = QFont("Microsoft YaHei UI", 9)
    app.setFont(font)
    
    # 设置主题
    setTheme(Theme.AUTO)
    
    # 创建主窗口
    window = MainWindow()
    window.show()
    
    exit_code = app.exec_()

    # 确保 pygame 在退出时正确清理
    pygame.quit()

    sys.exit(exit_code)

if __name__ == "__main__":
    main() 