import sys
import os
import cv2
import numpy as np
import json
from typing import Tuple, Optional
from PySide6.QtWidgets import QApplication, QWidget, QVBoxLayout, QPushButton, QLabel, QFileDialog, QInputDialog, QHBoxLayout, QScrollArea
from PySide6.QtCore import Qt, QEventLoop, QRect
from PySide6.QtGui import QImage, QPixmap
from 选择框 import TransparentSelectionBox
from paddleocr import PaddleOCR
import pyautogui

class TeammateRecognition:
    def __init__(self):
        self.profession_icons_dir = 'profession_icons'
        self.ensure_profession_icons_dir()
        self.init_ocr()
        # 待识别队友列表，每个元素包含区域坐标和截图
        self.pending_teammates = []
        
        # 图像处理参数
        self.contrast = 1.2    # 默认对比度增强因子
        self.brightness = 10   # 默认亮度增强因子
        self.num_samples = 3   # 默认采样次数

    def init_ocr(self):
        """初始化OCR引擎"""
        try:
            # 优化OCR配置参数，专注于中文识别
            self.ocr = PaddleOCR(
                use_angle_cls=True,      # 启用文字角度分类器
                lang='ch',               # 使用中文模型
                use_gpu=False,           # 关闭GPU
                rec_char_dict_path=None, # 使用默认中文字典
                det_db_thresh=0.3,       # 降低检测阈值，提高小字体检测能力
                rec_batch_num=1,         # 每次识别一个文本块
                show_log=False           # 关闭日志显示
            )
        except Exception as e:
            print(f"OCR初始化失败: {str(e)}")
            raise

    def ensure_profession_icons_dir(self):
        """确保职业图标目录存在"""
        if not os.path.exists(self.profession_icons_dir):
            os.makedirs(self.profession_icons_dir)

    def load_profession_icons(self) -> dict:
        """加载所有职业图标模板"""
        icons = {}
        try:
            # 检查目录是否存在
            if not os.path.exists(self.profession_icons_dir):
                print(f"错误: 职业图标目录 '{self.profession_icons_dir}' 不存在")
                return icons
            
            # 检查目录是否为空
            files = os.listdir(self.profession_icons_dir)
            if not files:
                print(f"警告: 职业图标目录 '{self.profession_icons_dir}' 为空")
                return icons
            
            # 统计有效图标文件数量
            valid_files = [f for f in files if f.lower().endswith(('.png', '.jpg', '.jpeg'))]
            if not valid_files:
                print(f"警告: 职业图标目录 '{self.profession_icons_dir}' 中没有有效的图片文件")
                return icons
            
            print(f"开始加载 {len(valid_files)} 个职业图标...")
            
            # 加载图标文件
            for filename in valid_files:
                try:
                    # 使用UTF-8编码处理文件路径
                    icon_path = os.path.join(self.profession_icons_dir, filename)
                    icon_name = os.path.splitext(filename)[0]
                    
                    # 检查文件是否存在且可读
                    if not os.path.isfile(icon_path):
                        print(f"错误: 职业图标文件 '{filename}' 不存在或不是文件")
                        continue
                    
                    # 使用完整路径读取图标文件
                    icon = cv2.imdecode(np.fromfile(icon_path, dtype=np.uint8), cv2.IMREAD_COLOR)
                    if icon is None:
                        print(f"错误: 无法读取职业图标文件 '{filename}'，可能是文件损坏或格式不支持")
                        continue
                    
                    icons[icon_name] = icon
                    print(f"成功加载职业图标: {icon_name} (尺寸: {icon.shape})")
                    
                except Exception as e:
                    print(f"错误: 加载职业图标 '{filename}' 时出错: {str(e)}")
                    continue
                    
            print(f"职业图标加载完成，共加载 {len(icons)} 个有效图标")
            
        except Exception as e:
            print(f"错误: 加载职业图标时发生未知错误: {str(e)}")
            
        return icons

    def preprocess_image(self, image: np.ndarray, for_ocr: bool = False) -> np.ndarray:
        """图像预处理，提高图像质量
        Image preprocessing to improve image quality
        
        Args:
            image: 输入图像 (BGR格式) / Input image (BGR format)
            for_ocr: 是否为OCR进行特定预处理 / Whether to perform specific preprocessing for OCR
            
        Returns:
            处理后的图像 / Processed image
        """
        try:
            # 检查图像是否为空
            if image is None or image.size == 0:
                print("错误: 输入图像为空或无效 / Error: Input image is empty or invalid")
                return image

            # 确保是BGR格式
            if len(image.shape) == 3 and image.shape[2] == 4:
                image = cv2.cvtColor(image, cv2.COLOR_BGRA2BGR)
            elif len(image.shape) != 3 or image.shape[2] != 3:
                print(f"错误: 输入图像格式不正确，期望BGR但得到 shape {image.shape} / Error: Incorrect input image format, expected BGR but got shape {image.shape}")
                return image

            # 使用不同的处理方式，取决于目标用途
            if for_ocr:
                # 文字识别专用处理
                # 1. 转换为RGB (PaddleOCR推荐RGB格式)
                rgb_img = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
                
                # 2. 适度调整对比度和亮度
                alpha = self.contrast  # 使用设置的对比度因子
                beta = self.brightness # 使用设置的亮度
                adjusted = cv2.convertScaleAbs(rgb_img, alpha=alpha, beta=beta)
                
                # 3. 适度降噪
                denoised = cv2.fastNlMeansDenoisingColored(adjusted, None, 10, 10, 7, 21)
                
                # 不再进行二值化，让OCR引擎处理原始彩色图像
                return denoised
            else:
                # 图标匹配专用处理 (转为灰度)
                gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
                
                # 使用CLAHE增强对比度
                clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
                adjusted = clahe.apply(gray)
                
                # 适度锐化
                kernel = np.array([[-1,-1,-1],
                                 [-1, 9,-1],
                                 [-1,-1,-1]])
                sharpened = cv2.filter2D(adjusted, -1, kernel)
                
                # 轻度降噪
                denoised = cv2.fastNlMeansDenoising(sharpened, None, h=10, templateWindowSize=7, searchWindowSize=21)
                
                return denoised

        except Exception as e:
            print(f"图像预处理错误: {str(e)} / Image preprocessing error: {str(e)}")
            # 出错时尽量返回原始图像
            return image

    def match_profession_icon(self, screenshot: np.ndarray, icons: dict) -> Optional[str]:
        """匹配职业图标
        Match profession icon
        """
        best_match = None
        highest_score = 0.70  # 稍微降低最低匹配阈值，增加匹配成功率
        match_results = {}  # 存储所有匹配结果 / Store all matching results

        try:
            # 检查截图是否为空 / Check if the screenshot is empty
            if screenshot is None or screenshot.size == 0:
                print("错误: 截图为空或无效 / Error: Screenshot is empty or invalid")
                return None

            # 确保截图是BGR格式 / Ensure screenshot is in BGR format
            if len(screenshot.shape) == 3 and screenshot.shape[2] == 4:
                screenshot_bgr = cv2.cvtColor(screenshot, cv2.COLOR_BGRA2BGR)
            elif len(screenshot.shape) == 3 and screenshot.shape[2] == 3:
                screenshot_bgr = screenshot # Already BGR
            else:
                print(f"错误: 截图格式不正确，期望BGR或BGRA但得到 shape {screenshot.shape} / Error: Incorrect screenshot format, expected BGR or BGRA but got shape {screenshot.shape}")
                return None

            if not icons:
                print("错误: 没有加载任何职业图标模板 / Error: No profession icon templates loaded")
                return None
                
            # 预处理截图为灰度图 (不用于OCR) / Preprocess screenshot to grayscale (not for OCR)
            # 使用 for_ocr=False 调用更新后的 preprocess_image / Call updated preprocess_image with for_ocr=False
            processed_screenshot_gray = self.preprocess_image(screenshot_bgr, for_ocr=False)
            if processed_screenshot_gray is None or processed_screenshot_gray.size == 0:
                print("错误: 截图预处理失败 / Error: Screenshot preprocessing failed")
                return None
            # 确保预处理后是灰度图 / Ensure it's grayscale after preprocessing
            if len(processed_screenshot_gray.shape) != 2:
                 print(f"错误: 预处理后的截图不是灰度图, shape: {processed_screenshot_gray.shape} / Error: Preprocessed screenshot is not grayscale, shape: {processed_screenshot_gray.shape}")
                 return None
            
            # 创建多种尺寸的截图用于匹配 / Create multiple sizes of the screenshot for matching
            scales = [0.8, 0.9, 1.0, 1.1, 1.2]  # 缩放比例 / Scaling factors
            scaled_screenshots = []
            
            for scale in scales:
                try:
                    if scale != 1.0:
                        width = int(processed_screenshot_gray.shape[1] * scale)
                        height = int(processed_screenshot_gray.shape[0] * scale)
                        # 确保尺寸大于0 / Ensure dimensions are greater than 0
                        if width <= 0 or height <= 0:
                            continue
                        scaled = cv2.resize(processed_screenshot_gray, (width, height), interpolation=cv2.INTER_AREA if scale < 1.0 else cv2.INTER_LINEAR)
                        scaled_screenshots.append((scaled, scale))
                    else:
                        scaled_screenshots.append((processed_screenshot_gray, scale))
                except Exception as resize_err:
                    print(f"缩放截图时出错 (scale={scale}): {resize_err} / Error resizing screenshot (scale={scale}): {resize_err}")

            if not scaled_screenshots:
                print("错误: 未能成功生成任何缩放后的截图 / Error: Failed to generate any scaled screenshots")
                return None

            # 预处理图标模板为灰度图 / Preprocess icon templates to grayscale
            processed_icons_gray = {}
            for profession, template_bgr in icons.items():
                if template_bgr is None or template_bgr.size == 0:
                    print(f"警告: 无法加载或模板为空 {profession} / Warning: Cannot load or template is empty {profession}")
                    continue
                if len(template_bgr.shape) != 3 or template_bgr.shape[2] != 3:
                    print(f"警告: 职业图标 {profession} 不是BGR格式，跳过 / Warning: Profession icon {profession} is not BGR format, skipping")
                    continue
                # 转换为灰度图 / Convert to grayscale
                template_gray = cv2.cvtColor(template_bgr, cv2.COLOR_BGR2GRAY)
                # 可选：对模板应用轻微降噪 / Optional: Apply light denoising to template
                # template_gray = cv2.fastNlMeansDenoising(template_gray, None, h=5, templateWindowSize=7, searchWindowSize=21)
                processed_icons_gray[profession] = template_gray

            if not processed_icons_gray:
                print("错误: 未能成功预处理任何图标模板 / Error: Failed to preprocess any icon templates")
                return None

            # --- 开始匹配 --- / --- Start Matching --- 
            for profession, template_gray in processed_icons_gray.items():
                try:
                    # 获取模板尺寸 / Get template dimensions
                    th, tw = template_gray.shape[:2]
                    if th <= 0 or tw <= 0:
                        print(f"警告: 灰度职业图标 {profession} 尺寸无效，跳过 / Warning: Grayscale profession icon {profession} has invalid dimensions, skipping")
                        continue

                    current_best_score_for_icon = 0

                    # 在不同尺寸的截图上进行模板匹配 / Perform template matching on different sized screenshots
                    for scaled_screenshot, scale in scaled_screenshots:
                        # 确保截图尺寸大于模板尺寸 / Ensure screenshot dimensions are larger than template dimensions
                        h, w = scaled_screenshot.shape[:2]
                        if h < th or w < tw:
                            continue

                        # 执行模板匹配 / Execute template matching
                        try:
                            # 使用归一化相关系数匹配 / Use normalized correlation coefficient matching
                            res = cv2.matchTemplate(scaled_screenshot, template_gray, cv2.TM_CCOEFF_NORMED)
                            min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(res)
                            score = max_val
                            # 更新当前图标的最佳匹配分数 / Update best match score for the current icon
                            if score > current_best_score_for_icon:
                                current_best_score_for_icon = score
                        except cv2.error as cv2_err:
                             # 处理OpenCV特定错误，例如尺寸不匹配 / Handle OpenCV specific errors, e.g., size mismatch
                             print(f"OpenCV匹配错误 (图标: {profession}, 截图尺寸: {w}x{h}, 模板尺寸: {tw}x{th}, scale: {scale}): {cv2_err}")
                             continue # 跳过这个尺寸的匹配 / Skip matching for this size

                    # 存储当前图标的最佳匹配分数 / Store the best match score for the current icon
                    match_results[profession] = current_best_score_for_icon

                    # 更新全局最佳匹配 / Update global best match
                    if current_best_score_for_icon > highest_score:
                        highest_score = current_best_score_for_icon
                        best_match = profession

                except Exception as e:
                    print(f"错误: 匹配灰度职业图标 '{profession}' 时出错: {str(e)} / Error matching grayscale profession icon '{profession}': {str(e)}")
                    continue

            # 调试信息：打印所有图标的匹配分数 / Debug info: Print match scores for all icons
            # print("所有图标匹配分数 / All icon match scores:", match_results)

            if best_match:
                print(f"最佳匹配图标: {best_match} (分数 / Score: {highest_score:.4f})")
            else:
                # 查找分数最高的图标，即使低于阈值，用于调试 / Find the highest scoring icon even if below threshold, for debugging
                if match_results:
                     max_prof = max(match_results, key=match_results.get)
                     max_score_val = match_results[max_prof]
                     print(f"未能找到足够置信度的匹配图标 (最高分 / Highest score: {max_prof} @ {max_score_val:.4f}, 阈值 / Threshold: {highest_score})")
                else:
                     print(f"未能找到足够置信度的匹配图标 (无匹配结果) / Failed to find sufficiently confident match (no match results)")

        except Exception as e:
            print(f"错误: 匹配职业图标时发生未知错误: {str(e)} / Error: Unknown error occurred during icon matching: {str(e)}")
            import traceback
            traceback.print_exc()

        return best_match

    def create_selection_box(self):
        """创建屏幕区域选择框"""
        from 选择框 import TransparentSelectionBox
        return TransparentSelectionBox()

    def extract_name(self, screenshot: np.ndarray) -> str:
        """提取玩家名称
        Extract player name using OCR
        """
        name = '未识别' # Default value
        try:
            # 检查截图 / Check screenshot
            if screenshot is None or screenshot.size == 0:
                print("错误: 输入截图无效 / Error: Invalid input screenshot")
                return name
                
            # 确保是BGR格式 / Ensure BGR format
            if len(screenshot.shape) == 3 and screenshot.shape[2] == 4:
                screenshot_bgr = cv2.cvtColor(screenshot, cv2.COLOR_BGRA2BGR)
            elif len(screenshot.shape) == 3 and screenshot.shape[2] == 3:
                screenshot_bgr = screenshot
            else:
                print(f"错误: 输入截图格式不正确，期望BGR或BGRA但得到 shape {screenshot.shape} / Error: Incorrect input screenshot format, expected BGR or BGRA but got shape {screenshot.shape}")
                return name

            # 转换为RGB格式(PaddleOCR使用RGB格式)
            rgb_image = cv2.cvtColor(screenshot_bgr, cv2.COLOR_BGR2RGB)
            
            print("开始OCR文字识别... / Starting OCR text recognition...")
            try:
                # 添加重试机制 / Add retry mechanism
                ocr_results = None
                for attempt in range(3): # 增加到3次重试
                    try:
                        # 直接传入RGB图像，不做任何预处理
                        ocr_results = self.ocr.ocr(rgb_image, cls=True)
                        
                        # 检查结果是否有效 
                        if ocr_results and isinstance(ocr_results, list):
                            # PaddleOCR可能返回空列表，这也是一种有效结果(表示未识别到文字)
                            if not ocr_results:
                                print(f"OCR尝试 {attempt + 1} 未识别到任何文字，稍后重试... / OCR attempt {attempt + 1} did not recognize any text, retrying...")
                                continue
                                
                            # 检查第一个元素是否为None
                            if ocr_results[0] is not None:
                                break # 成功获取结果，跳出重试
                            
                        print(f"OCR尝试 {attempt + 1} 返回无效结果，稍后重试... / OCR attempt {attempt + 1} returned invalid results, retrying...")
                    except Exception as ocr_attempt_err:
                        print(f"OCR尝试 {attempt + 1} 出错: {str(ocr_attempt_err)}，稍后重试...")
                        
                    # 短暂等待后重试
                    import time
                    time.sleep(0.5)
                
                # 处理OCR结果
                if ocr_results and isinstance(ocr_results, list) and ocr_results[0] is not None:
                    lines = ocr_results[0]
                    if lines: # 确保 lines 不为空列表
                        # 过滤掉长度过短或置信度过低的文本
                        valid_lines = []
                        for line in lines:
                            # 增加更严格的检查
                            if line and isinstance(line, list) and len(line) == 2 and isinstance(line[1], (tuple, list)) and len(line[1]) == 2:
                                text, confidence = line[1]
                                # 过滤条件：文本是字符串，置信度是数字，文本长度大于1，置信度大于阈值
                                if isinstance(text, str) and isinstance(confidence, (float, int)) and len(text.strip()) > 1 and confidence > 0.5: # 降低阈值
                                    valid_lines.append(line)
                                    print(f"识别文本: {text}, 置信度: {confidence}")
                            else:
                                 print(f"跳过格式错误的OCR行: {line} / Skipping incorrectly formatted OCR line: {line}")

                        if valid_lines:
                            # 检查文本内容，分为包含汉字的和纯数字/字母的两组
                            import re
                            chinese_lines = []
                            non_chinese_lines = []
                            
                            for line in valid_lines:
                                text = line[1][0].strip()
                                # 检查是否包含汉字
                                if re.search(r'[\u4e00-\u9fff]', text):
                                    chinese_lines.append(line)
                                else:
                                    non_chinese_lines.append(line)
                            
                            # 优先选择汉字文本，如果有多个汉字文本，选择置信度最高的
                            if chinese_lines:
                                print("发现汉字文本，优先采用")
                                best_line = max(chinese_lines, key=lambda line: line[1][1])
                            else:
                                print("未发现汉字文本，使用非汉字文本")
                                best_line = max(valid_lines, key=lambda line: line[1][1])
                            
                            detected_name = best_line[1][0].strip()
                            confidence = best_line[1][1]
                            
                            # 清理名称中的非预期字符
                            import re
                            # 允许中文、英文、数字、下划线
                            cleaned_name = re.sub(r'[^\u4e00-\u9fa5a-zA-Z0-9_]', '', detected_name)
                            if cleaned_name: # 确保清理后名称不为空
                                name = cleaned_name
                                print(f"OCR识别到的名称: {name} (置信度 / Confidence: {confidence:.2f})")
                            else:
                                print(f"名称 '{detected_name}' 清理后为空，忽略 / Name '{detected_name}' became empty after cleaning, ignoring")
                        else:
                            print(f"OCR未找到满足条件的有效文本行 / OCR did not find valid text lines meeting criteria. Raw lines: {lines}")
                    else:
                        print("OCR未能识别到有效名称文本行 (lines为空列表) / OCR failed to recognize valid name text lines (lines is empty list)")
                else:
                    # 区分是OCR没返回结果，还是返回了无效结构
                    if ocr_results is None:
                        print("OCR调用失败或重试后仍未返回结果 / OCR call failed or did not return results after retries")
                    else:
                         print(f"OCR返回无效结果结构 / OCR returned invalid result structure: {ocr_results}")
            except Exception as ocr_err:
                print(f"执行OCR时出错: {ocr_err} / Error executing OCR: {ocr_err}")
                import traceback
                traceback.print_exc()

            return name

        except Exception as e:
            print(f"提取名称时出错: {str(e)} / Error extracting name: {str(e)}")
            import traceback
            traceback.print_exc()
            return name # 返回默认值 '未识别' / Return default value '未识别'

    def filter_text(self, text, valid_texts=None):
        """过滤和处理OCR识别的文本
        Filter and process OCR recognized text
        """
        if valid_texts is None:
            valid_texts = []
            
        # 保留中文和英文字母
        filtered_text = ''.join(char for char in text if ('\u4e00' <= char <= '\u9fff') or char.isalpha())
        if filtered_text and len(filtered_text) >= 2:  # 至少2个字符才是有效名称
            if filtered_text not in valid_texts:  # 避免重复
                valid_texts.append(filtered_text)
                print(f"提取文本: {filtered_text}")

        # 返回第一个非空的文本
        if valid_texts:
            print(f"最终识别结果: {valid_texts[0]}")
            return valid_texts[0]

        print("警告: 未找到有效的中英文文本")
        return '未识别'

    def capture_screen(self, x, y, width, height):
        """截取屏幕指定区域
        
        参数:
            x, y: 左上角坐标
            width, height: 区域宽高
            
        返回:
            截取的图像，BGR格式的numpy数组
        """
        try:
            # 确保坐标合法
            screen_width, screen_height = pyautogui.size()
            if x < 0 or y < 0 or x + width > screen_width or y + height > screen_height:
                print(f"警告: 截图区域 ({x}, {y}, {width}, {height}) 超出屏幕范围 ({screen_width}, {screen_height})")
                # 调整为有效范围
                x = max(0, min(x, screen_width - 1))
                y = max(0, min(y, screen_height - 1))
                width = min(width, screen_width - x)
                height = min(height, screen_height - y)
                print(f"已调整为: ({x}, {y}, {width}, {height})")
            
            # 使用pyautogui截图
            screenshot = pyautogui.screenshot(region=(x, y, width, height))
            
            # 检查截图是否成功
            if screenshot is None or screenshot.size == 0:
                print(f"截图失败: 获取到空图像")
                return None
            
            # 转换为numpy数组并转为BGR格式(OpenCV格式)
            frame = np.array(screenshot)
            if len(frame.shape) == 3 and frame.shape[2] == 4:  # RGBA格式
                frame = cv2.cvtColor(frame, cv2.COLOR_RGBA2BGR)
            elif len(frame.shape) == 3 and frame.shape[2] == 3:  # RGB格式
                frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
            
            return frame
        
        except Exception as e:
            print(f"截图出错: {str(e)}")
            import traceback
            traceback.print_exc()
            return None

    def capture_regions(self):
        """捕获所有待识别区域的截图"""
        try:
            # 临时隐藏选择框的边框(如果正在使用选择框截图)
            if hasattr(self, 'selection_box') and self.selection_box:
                self.selection_box.start_capture()
            
            # 告诉用户正在截图
            print("正在捕获屏幕区域...")
            
            # 原有的截图代码
            # ...
            
            # 截图完成后恢复选择框边框
            if hasattr(self, 'selection_box') and self.selection_box:
                self.selection_box.end_capture()
            
            return True
        except Exception as e:
            print(f"捕获区域时出错: {str(e)}")
            # 确保恢复选择框
            if hasattr(self, 'selection_box') and self.selection_box:
                self.selection_box.end_capture()
            return False

class RecognitionUI(QWidget):
    def __init__(self):
        super().__init__()
        self.initUI()
        self.init_recognition()
        # 待识别队友列表
        self.pending_teammates = []
        
    def exec_(self):
        """显示窗口并等待关闭"""
        self.show()
        # 创建事件循环
        loop = QEventLoop()
        # 当窗口关闭时退出事件循环
        self.destroyed.connect(loop.quit)
        # 执行事件循环，等待窗口关闭
        loop.exec()

    def init_recognition(self):
        """初始化识别模块"""
        try:
            self.result_label.setText('正在加载OCR模型，请稍候...')
            QApplication.processEvents()
            self.recognition = TeammateRecognition()
            self.result_label.setText('请选择要识别的区域')
            self.select_btn.setEnabled(True)
        except Exception as e:
            self.result_label.setText(f'OCR初始化失败: {str(e)}\n请检查网络连接并重启程序')
            self.select_btn.setEnabled(False)

    def initUI(self):
        self.setWindowTitle('队友识别工具')
        layout = QVBoxLayout()

        # 创建按钮布局
        button_layout = QHBoxLayout()

        # 添加识别按钮
        self.select_btn = QPushButton('添加待识别队友', self)
        self.select_btn.setEnabled(False)  # 初始禁用按钮
        self.select_btn.clicked.connect(self.start_selection)
        button_layout.addWidget(self.select_btn)

        # 添加批量识别按钮
        self.batch_recognize_btn = QPushButton('批量识别队友', self)
        self.batch_recognize_btn.setEnabled(False)  # 初始禁用按钮
        self.batch_recognize_btn.clicked.connect(self.batch_recognize_teammates)
        button_layout.addWidget(self.batch_recognize_btn)

        # 添加截图图标按钮
        self.capture_icon_btn = QPushButton('截取职业图标', self)
        self.capture_icon_btn.clicked.connect(self.start_icon_capture)
        button_layout.addWidget(self.capture_icon_btn)

        layout.addLayout(button_layout)

        # 添加待识别队友列表区域
        self.pending_list_label = QLabel('待识别队友列表：', self)
        layout.addWidget(self.pending_list_label)
        
        # 创建滚动区域来显示待识别队友列表
        self.pending_scroll = QScrollArea()
        self.pending_scroll.setWidgetResizable(True)
        self.pending_widget = QWidget()
        self.pending_layout = QVBoxLayout(self.pending_widget)
        self.pending_scroll.setWidget(self.pending_widget)
        self.pending_scroll.setMaximumHeight(100)  # 限制高度
        layout.addWidget(self.pending_scroll)

        # 添加结果显示标签
        self.result_label = QLabel('请添加待识别队友', self)
        self.result_label.setAlignment(Qt.AlignCenter)
        self.result_label.setWordWrap(True)  # 允许文本换行
        layout.addWidget(self.result_label)

        self.setLayout(layout)
        self.resize(400, 400)

    def start_selection(self):
        """开始选择待识别队友区域"""
        self.hide()
        self.selection_box = TransparentSelectionBox(self.on_selection_complete)
        self.selection_box.show()

    def start_icon_capture(self):
        """开始截取职业图标"""
        self.hide()
        self.selection_box = TransparentSelectionBox(self.on_icon_capture_complete)
        self.selection_box.show()

    def on_icon_capture_complete(self, rect: QRect):
        """完成职业图标截取"""
        self.show()
        # 截取选定区域的截图
        screen = QApplication.primaryScreen()
        screenshot = screen.grabWindow(0, rect.x(), rect.y(), rect.width(), rect.height())

        # 获取职业名称
        profession_name, ok = QInputDialog.getText(self, '保存职业图标', '请输入职业名称：')
        if ok and profession_name:
            # 保存图标
            icon_path = os.path.join(self.recognition.profession_icons_dir, f'{profession_name}.png')
            screenshot.save(icon_path)
            self.result_label.setText(f'职业图标已保存：{profession_name}')
        else:
            self.result_label.setText('已取消保存职业图标')

    def on_selection_complete(self, rect: QRect):
        """完成区域选择后，将区域添加到待识别队友列表"""
        self.show()
        try:
            # 获取选择区域的截图
            self.result_label.setText('正在处理截图...')
            QApplication.processEvents()
            
            # 使用选择框的get_selected_image方法获取截图
            img_array = self.selection_box.get_selected_image()
            
            if img_array is None:
                self.result_label.setText('错误: 截图获取失败')
                return
            
            # 添加到待识别队友列表
            teammate_index = len(self.pending_teammates) + 1
            self.pending_teammates.append({
                'index': teammate_index,
                'rect': rect,
                'image': img_array,
                'recognized': False
            })
            
            # 更新待识别队友列表显示
            self.update_pending_list()
            
            # 启用批量识别按钮
            self.batch_recognize_btn.setEnabled(True)
            
            # 显示提示信息
            self.result_label.setText(f'已添加待识别队友 #{teammate_index}\n'
                                     f'区域坐标: ({rect.x()}, {rect.y()}, {rect.width()}, {rect.height()})\n\n'
                                     f'当前共有 {len(self.pending_teammates)} 个待识别队友\n'
                                     f'点击"批量识别队友"按钮开始识别')
            
        except Exception as e:
            error_text = f'添加待识别队友时出错:\n{str(e)}\n\n请重试或检查程序配置'
            self.result_label.setText(error_text)
    
    def update_pending_list(self):
        """更新待识别队友列表显示"""
        # 清空现有列表
        while self.pending_layout.count():
            item = self.pending_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        # 添加待识别队友信息
        for teammate in self.pending_teammates:
            status = "已识别" if teammate.get('recognized', False) else "待识别"
            rect = teammate['rect']
            label = QLabel(f"队友 #{teammate['index']} - {status} - 区域: ({rect.x()}, {rect.y()}, {rect.width()}, {rect.height()})")
            self.pending_layout.addWidget(label)
        
        # 如果没有待识别队友，显示提示信息
        if not self.pending_teammates:
            self.pending_layout.addWidget(QLabel("暂无待识别队友，请点击'添加待识别队友'按钮"))
    
    def batch_recognize_teammates(self):
        """批量识别待识别队友，使用多次采样和投票机制提高精度"""
        if not self.pending_teammates:
            self.result_label.setText("没有待识别队友")
            return
        
        # 统计未识别的队友数量
        unrecognized = [t for t in self.pending_teammates if not t.get('recognized', False)]
        if not unrecognized:
            self.result_label.setText("所有队友已识别完成")
            return
        
        self.result_label.setText(f"开始批量识别 {len(unrecognized)} 个队友...")
        QApplication.processEvents()
        
        # 加载职业图标（只需加载一次）
        self.result_label.setText('正在加载职业图标...')
        QApplication.processEvents()
        profession_icons = self.recognition.load_profession_icons()
        
        results = []
        success_count = 0
        
        # 使用TeammateRecognition类中设置的采样次数
        num_samples = self.recognition.num_samples  # 使用用户设置的采样次数
        
        # 逐个识别队友
        for teammate in self.pending_teammates:
            if teammate.get('recognized', False):
                continue  # 跳过已识别的队友
            
            try:
                img_array = teammate['image']
                index = teammate['index']
                rect = teammate['rect']
                
                self.result_label.setText(f'正在识别队友 #{index}...')
                QApplication.processEvents()
                
                # 多次采样识别
                profession_votes = {}  # 职业投票结果
                name_votes = {}        # 名称投票结果
                
                # 创建多个采样图像
                sample_images = []
                
                # 原始图像
                sample_images.append(img_array)
                
                # 重新截取屏幕区域（如果可能）
                try:
                    for i in range(num_samples - 1):
                        # 使用选择框的get_selected_image方法获取新的截图
                        screen = QApplication.primaryScreen()
                        screenshot = screen.grabWindow(0, rect.x(), rect.y(), rect.width(), rect.height())
                        if not screenshot.isNull():
                            # 转换为OpenCV格式
                            img = screenshot.toImage()
                            buffer = img.bits().tobytes()
                            new_img_array = np.frombuffer(buffer, dtype=np.uint8).reshape((img.height(), img.width(), 4))
                            # 转换为BGR格式
                            new_img_array = cv2.cvtColor(new_img_array, cv2.COLOR_RGBA2BGR)
                            sample_images.append(new_img_array)
                except Exception as e:
                    print(f"获取额外采样图像失败: {str(e)}")
                
                # 对每个采样图像进行识别
                for i, sample_img in enumerate(sample_images):
                    self.result_label.setText(f'正在识别队友 #{index} (采样 {i+1}/{len(sample_images)})...')
                    QApplication.processEvents()
                    
                    # 识别职业
                    profession = self.recognition.match_profession_icon(sample_img, profession_icons)
                    if profession:
                        profession_votes[profession] = profession_votes.get(profession, 0) + 1
                    
                    # 识别名称 - 直接将原始图像传递给extract_name，不进行额外的预处理
                    name = self.recognition.extract_name(sample_img)
                    if name and name != '未识别':
                        name_votes[name] = name_votes.get(name, 0) + 1
                
                # 根据投票结果确定最终识别结果
                final_profession = None
                if profession_votes:
                    final_profession = max(profession_votes.items(), key=lambda x: x[1])[0]
                
                final_name = '未识别'
                if name_votes:
                    # 优先选择汉字名称，即使其投票数较少
                    import re
                    chinese_names = {name: votes for name, votes in name_votes.items() 
                                    if re.search(r'[\u4e00-\u9fff]', name)}
                    
                    if chinese_names:
                        # 如果有汉字名称，选择投票数最高的汉字名称
                        final_name = max(chinese_names.items(), key=lambda x: x[1])[0]
                        print(f"选择汉字名称: {final_name} (票数: {chinese_names[final_name]})")
                    else:
                        # 如果没有汉字名称，选择投票数最高的名称
                        final_name = max(name_votes.items(), key=lambda x: x[1])[0]
                        print(f"无汉字名称可用，选择: {final_name} (票数: {name_votes[final_name]})")
                
                # 记录识别结果
                teammate['recognized'] = True
                teammate['name'] = final_name
                teammate['profession'] = final_profession
                
                # 保存配置文件
                if final_name != '未识别':
                    self.save_teammate_config(final_name, final_profession, teammate['rect'])
                    success_count += 1
                    results.append(f"队友 #{index}: 名称={final_name}, 职业={final_profession or '未识别'}")
                    # 显示投票详情
                    vote_details = f"  - 名称投票: {name_votes}\n  - 职业投票: {profession_votes}"
                    results.append(vote_details)
                else:
                    results.append(f"队友 #{index}: 识别失败，未能识别名称")
                
            except Exception as e:
                results.append(f"队友 #{index}: 识别出错 - {str(e)}")
                print(f"识别队友 #{index} 时出错: {str(e)}")
        
        # 更新待识别队友列表显示
        self.update_pending_list()
        
        # 显示识别结果
        result_text = f"批量识别完成，成功识别 {success_count}/{len(unrecognized)} 个队友\n\n识别结果:\n"
        result_text += "\n".join(results)
        self.result_label.setText(result_text)
    
    def save_teammate_config(self, name, profession, rect):
        """保存队友配置文件"""
        try:
            # 为队员创建单独的配置文件
            config_dir = os.path.dirname(os.path.abspath(__file__))
            config_file = os.path.join(config_dir, f"{name}_config.json")
            
            # 创建配置数据结构，使用选择区域作为默认血条位置
            config_data = {
                'profession': profession or '未识别',
                'health_bar': {
                    'coordinates': {
                        'x1': rect.x(),
                        'y1': rect.y(),
                        'x2': rect.x() + rect.width(),
                        'y2': rect.y() + rect.height()
                    },
                    'color': {
                        'lower': [43, 71, 121],
                        'upper': [63, 171, 221]
                    }
                }
            }
            
            # 如果文件已存在，读取现有配置中的坐标和颜色信息
            if os.path.exists(config_file) and os.path.getsize(config_file) > 0:
                try:
                    with open(config_file, 'r', encoding='utf-8') as f:
                        existing_config = json.load(f)
                        # 保留现有的血条坐标和颜色设置
                        if 'health_bar' in existing_config:
                            if 'coordinates' in existing_config['health_bar']:
                                config_data['health_bar']['coordinates'] = existing_config['health_bar']['coordinates']
                            if 'color' in existing_config['health_bar']:
                                config_data['health_bar']['color'] = existing_config['health_bar']['color']
                except json.JSONDecodeError:
                    print(f'配置文件 {config_file} 格式错误，将使用默认设置')
            
            # 使用临时文件保存配置
            temp_file = config_file + '.tmp'
            with open(temp_file, 'w', encoding='utf-8') as f:
                json.dump(config_data, f, ensure_ascii=False, indent=4)
            
            # 如果写入成功，替换原配置文件
            if os.path.exists(config_file):
                os.remove(config_file)
            os.rename(temp_file, config_file)
            
            print(f'已将识别结果保存到配置文件: {config_file}')
            return True
                
        except Exception as e:
            print(f'保存配置文件时出错: {str(e)}')
            # 如果临时文件存在，清理它
            if 'temp_file' in locals() and os.path.exists(temp_file):
                try:
                    os.remove(temp_file)
                except:
                    pass
            return False

def main():
    app = QApplication(sys.argv)
    window = RecognitionUI()
    window.show()
    sys.exit(app.exec())

if __name__ == '__main__':
    main()