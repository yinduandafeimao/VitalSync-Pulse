import os
import queue
import threading
import tempfile
import asyncio
import edge_tts
import pygame
from config_manager import ConfigManager

class VoiceManager:
    """语音管理类，负责处理语音合成和播放功能"""
    
    def __init__(self):
        """初始化语音管理器"""
        # 初始化语音参数
        self.voice_rate_param = '+0%'  # 默认语速
        self.voice_volume_param = '+0%'  # 默认音量
        
        # 初始化队列和活动语音字典
        self.speech_queue = queue.Queue()
        self.active_speech = {}
        
        # 启动工作线程
        self.worker_thread = None
        self.running = True
        self.initialize()
    
    def initialize(self):
        """初始化pygame混音器和工作线程"""
        try:
            # 初始化pygame mixer
            pygame.mixer.init()
            pygame.mixer.set_num_channels(16)  # 设置足够多的声道
            
            # 启动语音工作线程
            self.worker_thread = threading.Thread(target=self._speech_worker_loop, daemon=True)
            self.worker_thread.start()
            print("语音系统初始化成功")
            return True
        except pygame.error as e:
            print(f"pygame mixer 初始化失败: {e}")
            return False
    
    def shutdown(self):
        """关闭语音管理器，释放资源"""
        print("正在关闭语音管理器...")
        self.running = False
        
        # 向工作线程发送停止信号
        self.speech_queue.put(None)
        
        # 等待工作线程结束
        if self.worker_thread and self.worker_thread.is_alive():
            self.worker_thread.join(timeout=2)
            if self.worker_thread.is_alive():
                print("警告: 语音工作线程未能及时停止")
            else:
                print("语音工作线程已成功停止")
        
        # 清理活动语音和临时文件
        for channel, speech_info in list(self.active_speech.items()):
            filename = speech_info.get('filename')
            if filename and os.path.exists(filename):
                try:
                    os.remove(filename)
                    print(f"清理临时文件: {filename}")
                except Exception as e:
                    print(f"清理临时文件 {filename} 失败: {e}")
        
        # 退出pygame mixer
        pygame.mixer.quit()
        return True
    
    def play_speech(self, text, voice='zh-CN-XiaoxiaoNeural'):
        """将语音任务添加到队列中
        
        参数:
            text: 要播放的文本内容
            voice: 语音角色，默认为晓晓
        """
        if not text:
            return False
            
        # 创建任务元组 (文本, 语音角色, 语速, 音量)
        task = (text, voice, self.voice_rate_param, self.voice_volume_param)
        print(f"添加语音任务到队列: {text[:30]}... (voice={voice}, rate={self.voice_rate_param}, volume={self.voice_volume_param})")
        self.speech_queue.put(task)
        return True
    
    def _speech_worker_loop(self):
        """语音工作线程主循环"""
        print("语音工作线程已启动")
        while self.running:
            try:
                # 从队列获取任务，阻塞直到有任务或收到停止信号
                task = self.speech_queue.get()
                
                # 检查是否是停止信号
                if task is None:
                    print("语音工作线程收到停止信号")
                    self.speech_queue.task_done()
                    break
                    
                # 解包任务参数
                text, voice, rate, volume = task
                print(f"处理语音任务: {text[:30]}...")
                
                # 执行语音合成和播放
                self._execute_speech(text, voice, rate, volume)
                
                # 标记任务完成
                self.speech_queue.task_done()
                
            except Exception as e:
                print(f"语音工作线程发生错误: {e}")
                # 出现错误时也需要标记任务完成
                try:
                    self.speech_queue.task_done()
                except ValueError:
                    # 如果任务已经完成，会抛出ValueError
                    pass
        
        print("语音工作线程正常退出")
    
    def _execute_speech(self, text, voice='zh-CN-XiaoxiaoNeural', rate='+0%', volume='+0%'):
        """执行语音合成并播放
        
        参数:
            text: 要合成的文本
            voice: 语音角色
            rate: 语速参数
            volume: 音量参数
        """
        output_path = None
        temp_file = None
        sound = None
        channel = None
        
        try:
            # 创建临时文件
            temp_file = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
            output_path = temp_file.name
            temp_file.close()
            
            # 异步生成语音
            async def _generate_speech_async():
                try:
                    communicate = edge_tts.Communicate(text, voice=voice, rate=rate, volume=volume)
                    await communicate.save(output_path)
                    if os.path.exists(output_path):
                        return output_path
                    else:
                        print(f"错误: 语音文件 {output_path} 生成后不存在")
                        return None
                except edge_tts.NoAudioReceived:
                    print(f"edge-tts 错误: 没有收到音频数据。可能是无效的语音角色: {voice}")
                    return None
                except Exception as e:
                    print(f'edge-tts 语音合成异常: {e}')
                    return None
            
            # 同步执行异步生成函数
            generated_path = None
            try:
                generated_path = asyncio.run(_generate_speech_async())
            except RuntimeError as e:
                if "cannot run event loop while another loop is running" in str(e):
                    try:
                        loop = asyncio.get_event_loop()
                        generated_path = loop.run_until_complete(_generate_speech_async())
                    except Exception as inner_e:
                        print(f"使用现有事件循环运行失败: {inner_e}")
                else:
                    print(f"asyncio RuntimeError: {e}")
            except Exception as e:
                print(f"语音生成错误: {e}")
            
            # 加载和播放生成的语音
            if generated_path and os.path.exists(generated_path):
                if not pygame.mixer.get_init():
                    pygame.mixer.init()
                    pygame.mixer.set_num_channels(16)
                
                # 加载音频文件
                sound = pygame.mixer.Sound(generated_path)
                
                # 查找空闲声道
                channel = pygame.mixer.find_channel(True)  # force=True 强制获取一个声道
                if channel:
                    # 存储信息以便后续清理
                    self.active_speech[channel] = {'filename': generated_path, 'sound': sound}
                    
                    # 播放声音
                    channel.play(sound)
                    
                    # 不等待播放结束，直接返回
                    output_path = None  # 防止下面的清理代码尝试删除文件
                    return
                else:
                    print("错误: 无法找到空闲的声道")
            
            # 如果播放未成功启动，则清理临时文件
            output_path = generated_path
            
        finally:
            # 清理未成功播放的临时文件
            if output_path and os.path.exists(output_path):
                try:
                    os.remove(output_path)
                    print(f"已删除未使用的临时文件: {output_path}")
                except Exception as e:
                    print(f"删除临时文件 {output_path} 失败: {e}")
    
    def process_events(self):
        """处理Pygame事件和检查播放状态
        
        此函数应该由定时器定期调用
        """
        if not pygame.get_init() or not pygame.mixer.get_init():
            return
        
        # 处理已完成播放的声道
        finished_channels = []
        for channel, speech_info in list(self.active_speech.items()):
            if not channel.get_busy():
                filename = speech_info.get('filename')
                
                # 尝试删除临时文件
                if filename and os.path.exists(filename):
                    try:
                        os.remove(filename)
                        print(f"已删除临时文件: {filename}")
                    except Exception as e:
                        print(f"删除临时文件 {filename} 失败: {e}")
                
                # 标记声道为已完成
                finished_channels.append(channel)
        
        # 从活动语音字典中移除已完成的声道
        for channel in finished_channels:
            if channel in self.active_speech:
                del self.active_speech[channel]
        
        # 保持Pygame事件循环活跃
        pygame.event.pump()
    
    def update_rate(self, value):
        """更新语音速率
        
        参数:
            value: 速率值 (0-10)
        """
        # 转换为edge-tts速率参数: 0-10 -> -50% 到 +50%
        rate_percent = value * 10 - 50
        self.voice_rate_param = f"{rate_percent:+}%"
        
        # 保存设置
        self._save_voice_settings()
    
    def update_volume(self, value):
        """更新语音音量
        
        参数:
            value: 音量值 (0-100)
        """
        # 转换为edge-tts音量参数: 0-100 -> -50% 到 +50%
        volume_percent = value - 50
        self.voice_volume_param = f"{volume_percent:+}%"
        
        # 保存设置
        self._save_voice_settings()
    
    def _save_voice_settings(self):
        """保存语音设置到配置文件"""
        # 提取数值
        rate_value = int((int(self.voice_rate_param.strip('%+')) + 50) / 10)
        volume_value = int(self.voice_volume_param.strip('%+')) + 50
        
        # 保存到配置
        voice_settings = {
            'rate': rate_value,
            'volume': volume_value
        }
        
        # 更新配置文件
        ConfigManager.save_settings({'voice_settings': voice_settings})
    
    def load_voice_settings(self):
        """从配置文件加载语音设置"""
        try:
            # 加载配置
            config = ConfigManager.load_settings()
            voice_settings = config.get('voice_settings', {})
            
            # 设置语速
            rate_value = voice_settings.get('rate', 5)  # 默认值 5
            rate_percent = rate_value * 10 - 50
            self.voice_rate_param = f"{rate_percent:+}%"
            
            # 设置音量
            volume_value = voice_settings.get('volume', 80)  # 默认值 80
            volume_percent = volume_value - 50
            self.voice_volume_param = f"{volume_percent:+}%"
            
            return True
        except Exception as e:
            print(f"加载语音设置失败: {e}")
            # 设置默认值
            self.voice_rate_param = '+0%'
            self.voice_volume_param = '+30%'
            return False 