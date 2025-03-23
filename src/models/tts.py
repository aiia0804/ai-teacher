import os
import numpy as np
import torch
import sounddevice as sd
import soundfile as sf
import threading
import queue
import time
import re
from pathlib import Path
from typing import Optional, Union, List, Tuple, Generator, Dict, Any
from kokoro import KPipeline

class TTSManager:
    """
    文字轉語音管理器，實現智能緩衝處理，提供更流暢的語音輸出體驗。
    """
    def __init__(
        self, 
        model_dir: Optional[Union[str, Path]] = None,
        voice_file: str = "af_heart.pt",
        lang_code: str = 'a',  # 'a' 表示美式英語
        speed: float = 1.0,
        sample_rate: int = 24000,
        use_cuda: bool = True,
        min_buffer_size: int = 50,  # 最小緩衝區大小（字符數）
        punctuation_pattern: str = r'[.!?]'  # 標點符號模式
        #TODO: add punctuation_pattern to handle other langue.
    ):
        """
        初始化TTS管理器
        
        Args:
            model_dir: TTS模型目錄，用於語音文件
            voice_file: 語音文件名
            lang_code: 語言代碼
            speed: 語音速度
            sample_rate: 音頻採樣率
            use_cuda: 是否使用CUDA
            min_buffer_size: 觸發TTS生成的最小字符數
            punctuation_pattern: 觸發TTS生成的標點符號模式
        """
        # 初始化模型路徑
        if model_dir is None:
            base_dir = Path(__file__).resolve().parent.parent.parent
            self.model_dir = base_dir / "src" / "models" / "tts_models"
        else:
            self.model_dir = Path(model_dir)
            
        # 設置語音文件路徑 - 簡化路徑處理邏輯
        self.voice_file = voice_file
        voices_dir = self.model_dir / "voices"
        self.voice_path = voices_dir / voice_file
        if not os.path.exists(self.voice_path) and not self.voice_path.name.endswith(".pt"):
            self.voice_path = voices_dir / f"{voice_file}.pt"
        
        # 設置其他參數
        self.lang_code = lang_code
        self.speed = speed
        self.sample_rate = sample_rate
        self.use_cuda = use_cuda and torch.cuda.is_available()
        
        # 設置緩衝區參數
        self.min_buffer_size = min_buffer_size
        self.punctuation_pattern = re.compile(punctuation_pattern)
        
        # 檢查語音文件是否存在
        self._check_voice_file()
        
        # 加載模型
        self._load_model()
        
        # 初始化緩衝區和隊列
        self.text_buffer = ""
        self.audio_queue = queue.Queue()
        
        # 初始化線程
        self.is_running = True
        self.generator_thread = threading.Thread(target=self._generator_worker, daemon=True)
        self.player_thread = threading.Thread(target=self._player_worker, daemon=True)
        
        # 啟動線程
        self.generator_thread.start()
        self.player_thread.start()
        
        print("TTS管理器初始化完成，使用緩衝區策略進行流暢語音輸出")
    
    def _check_voice_file(self):
        """檢查語音文件是否存在，若不存在則嘗試查找替代"""
        if not os.path.exists(self.voice_path):
            print(f"警告: 找不到語音文件 {self.voice_path}")
            # 搜索其他可能的語音文件
            voice_dir = self.model_dir / "voices"
            if not voice_dir.exists():
                voice_dir.mkdir(parents=True, exist_ok=True)
                print(f"已創建語音目錄: {voice_dir}")
                
            potential_voices = list(voice_dir.glob("**/*.pt"))
            if potential_voices:
                print(f"找到可能的語音文件: {[p.name for p in potential_voices]}")
                # 使用第一個找到的語音文件
                self.voice_path = potential_voices[0]
                print(f"將使用: {self.voice_path}")
            else:
                print("找不到任何語音文件，TTS功能可能無法正常工作")
        else:
            print(f"找到語音文件: {self.voice_path}")
    
    def _load_model(self):
        """加載KPipeline和語音模型"""
        try:
            # 確定設備
            device = "cuda" if self.use_cuda and torch.cuda.is_available() else "cpu"
            print(f"TTS使用設備: {device}")
            
            # 初始化KPipeline
            print(f"初始化KPipeline，lang_code={self.lang_code}")
            self.pipeline = KPipeline(lang_code=self.lang_code)
            
            # 加載語音模型
            if os.path.exists(self.voice_path):
                print(f"加載語音文件: {self.voice_path}")
                self.voice_tensor = torch.load(self.voice_path, weights_only=True)
                
                # 測試pipeline調用方式，確定正確的API調用方式
                try:
                    # 使用簡短的測試文本
                    test_text = "Test."
                    _ = next(self.pipeline(test_text, voice=self.voice_tensor, speed=self.speed))
                    self.use_named_params = True
                    print("使用命名參數調用pipeline")
                except (TypeError, StopIteration) as e:
                    try:
                        _ = next(self.pipeline(test_text, self.voice_tensor, self.speed))
                        self.use_named_params = False
                        print("使用位置參數調用pipeline")
                    except Exception as e2:
                        print(f"無法確定pipeline調用方式: {e2}")
                        self.use_named_params = True  # 默認使用命名參數
                
                print("TTS模型加載成功!")
            else:
                raise FileNotFoundError(f"找不到語音文件: {self.voice_path}")
                
        except Exception as e:
            import traceback
            traceback.print_exc()
            raise RuntimeError(f"TTS模型加載失敗: {str(e)}")
    
    def _generator_worker(self):
        """
        生成線程：將緩衝區中的文本轉換為語音，並將語音放入播放隊列
        """
        while self.is_running:
            # 檢查是否有足夠的文本可以處理
            should_process, text_to_process = self._should_process_buffer()
            if should_process and text_to_process:
                try:
                    self.text_buffer = self.text_buffer[len(text_to_process):]       
                    print(f"⏳ 生成語音: '{text_to_process}'")
                    
                    # 生成語音
                    start_time = time.time()
                    audio_data = self._generate_audio_internal(text_to_process)
                    
                    if len(audio_data) > 0:
                        # 將生成的音頻放入播放隊列
                        self.audio_queue.put(audio_data)
                        
                        generation_time = time.time() - start_time
                        print(f"✅ 語音生成完成，耗時: {generation_time:.2f}秒，文本長度: {len(text_to_process)}字符")
                    else:
                        print("❌ 未能生成有效的音頻")
                        
                except Exception as e:
                    print(f"❌ 語音生成錯誤: {str(e)}")
                    import traceback
                    traceback.print_exc()
            
            # 短暫休眠以減少CPU使用
            time.sleep(0.05)
    
    def _player_worker(self):
        """
        播放線程：從播放隊列中獲取音頻並播放
        """
        while self.is_running:
            try:
                # 從隊列獲取音頻數據（設置超時以便可以檢查是否應該退出）
                audio_data = self.audio_queue.get(timeout=0.5)
                
                # 播放音頻
                print("🔊 開始播放音頻...")
                sd.play(audio_data, samplerate=self.sample_rate)
                sd.wait()  # 等待播放完成
                print("✅ 音頻播放完成")
                
                # 標記任務完成
                self.audio_queue.task_done()
                
            except queue.Empty:
                # 隊列為空，繼續等待
                continue
            except Exception as e:
                print(f"❌ 音頻播放錯誤: {str(e)}")
                
                # 嘗試清除任何正在播放的音頻
                try:
                    sd.stop()
                except:
                    pass
                
                # 標記任務完成以避免死鎖
                if 'audio_data' in locals():
                    self.audio_queue.task_done()
    
    def _should_process_buffer(self):
        """
        判斷是否應該處理緩衝區中的文本，並只返回完整句子
        """
        if not self.text_buffer or len(self.text_buffer) < self.min_buffer_size:
            return False, ""
        
        # 查找最後一個句子結束標點的位置
        matches = list(self.punctuation_pattern.finditer(self.text_buffer))
        if not matches:
            return False, ""
            
        # 獲取最後一個標點符號的位置
        last_match = matches[-1]
        end_pos = last_match.end()
        
        # 只處理到最後一個標點符號的文本
        return True, self.text_buffer[:end_pos]
    
    def _generate_audio_internal(self, text: str) -> np.ndarray:
        """
        內部方法：生成音頻數據
        
        Args:
            text: 要轉換為語音的文本
            
        Returns:
            生成的音頻數據，如果生成失敗則返回空數組
        """
        if not text or text.strip() == "":
            return np.array([])
        
        try:
            # 使用確定的方式調用pipeline
            if self.use_named_params:
                generator = self.pipeline(text, voice=self.voice_tensor, speed=self.speed)
            else:
                generator = self.pipeline(text, self.voice_tensor, self.speed)
            
            # 收集音頻片段
            all_audio = []
            for _, _, audio in generator:
                all_audio.append(audio)
            
            # 合併音頻
            if not all_audio:
                return np.array([])
                
            full_audio = np.concatenate(all_audio)
            return full_audio
                
        except Exception as e:
            print(f"生成音頻時出錯: {str(e)}")
            return np.array([])
        
    def _filter_special_tokens(self, text):
        """過濾特殊標記、URL和Markdown格式符號"""
        # 過濾特殊標記
        text = re.sub(r'<[^>]+>', '', text)
        
        # 過濾URL
        text = re.sub(r'https?://\S+', '', text)
        
        # 過濾Markdown格式符號（保留文本內容）
        text = re.sub(r'\*\*(.*?)\*\*', r'\1', text)  # 移除粗體標記 **text**
        text = re.sub(r'\*(.*?)\*', r'\1', text)      # 移除斜體標記 *text*
        text = re.sub(r'__(.*?)__', r'\1', text)      # 移除下劃線標記 __text__
        text = re.sub(r'_(.*?)_', r'\1', text)        # 移除斜體標記 _text_
        
        # # 清理多餘空格和換行
        # text = re.sub(r'\s+', ' ', text).strip()
        
        #過濾文本，移除emoji和特殊格式
        emoji_pattern = re.compile("[\U0001F600-\U0001F64F\U0001F300-\U0001F5FF\U0001F680-\U0001F6FF\U0001F700-\U0001F77F]+", flags=re.UNICODE)
        text = emoji_pattern.sub("", text)
        return text
    
    def add_text(self, text: str) -> None:
        """
        添加文本到緩衝區
        
        Args:
            text: 要添加的文本
        """
        if not text:
            return
            
        cleaned_text = self._filter_special_tokens(text)
        #cleaned_text = text
        if not cleaned_text:
            return
        # 添加到緩衝區
        self.text_buffer += cleaned_text
        
        # 如果緩衝區已經很大，強制處理
        if len(self.text_buffer) > self.min_buffer_size * 3:
            print(f"⚠️ 緩衝區已達到 {len(self.text_buffer)} 字符，強制處理")
            temp_buffer = self.text_buffer
            self.text_buffer = ""
            
            # 生成音頻並添加到隊列
            try:
                audio_data = self._generate_audio_internal(temp_buffer)
                if len(audio_data) > 0:
                    self.audio_queue.put(audio_data)
            except Exception as e:
                print(f"❌ 強制處理緩衝區時出錯: {str(e)}")
    
    def force_process(self) -> None:
        """強制處理當前緩衝區中的所有文本"""
        if not self.text_buffer:
            return
            
        print(f"🔄 強制處理緩衝區中的 {len(self.text_buffer)} 字符文本")
        temp_buffer = self.text_buffer
        self.text_buffer = ""
        
        # 生成音頻並添加到隊列
        try:
            audio_data = self._generate_audio_internal(temp_buffer)
            if len(audio_data) > 0:
                self.audio_queue.put(audio_data)
        except Exception as e:
            print(f"❌ 強制處理緩衝區時出錯: {str(e)}")
    
    def save_audio(self, text: str, file_path: str) -> bool:
        """
        生成並保存音頻到文件
        
        Args:
            text: 要轉換為語音的文本
            file_path: 保存音頻的文件路徑
            
        Returns:
            保存是否成功
        """
        audio_data = self._generate_audio_internal(text)
        if len(audio_data) > 0:
            try:
                sf.write(file_path, audio_data, self.sample_rate)
                print(f"✅ 音頻已保存至: {file_path}")
                return True
            except Exception as e:
                print(f"❌ 保存音頻錯誤: {str(e)}")
                return False
        return False
    
    def wait_until_done(self) -> None:
        """等待所有隊列中的項目處理完成"""
        # 強制處理緩衝區中的剩餘文本
        self.force_process()
        
        # 等待音頻隊列清空
        self.audio_queue.join()
        print("✅ 所有語音處理任務已完成")
    
    def shutdown(self) -> None:
        """關閉TTS管理器"""
        print("🛑 關閉TTS管理器...")
        self.is_running = False
        
        # 等待線程結束
        if hasattr(self, 'generator_thread') and self.generator_thread.is_alive():
            self.generator_thread.join(timeout=2.0)
            
        if hasattr(self, 'player_thread') and self.player_thread.is_alive():
            self.player_thread.join(timeout=2.0)
            
        # 停止任何正在播放的音頻
        try:
            sd.stop()
        except:
            pass
            
        print("✅ TTS管理器已關閉")

    def __del__(self):
        """析構函數"""
        self.shutdown()


# 測試代碼
if __name__ == "__main__":
    tts = TTSManager()
    
    print("\n=== 測試1: 分段添加文本 ===")
    # 模擬分段接收文本
    texts = [
        "Hello, I am your AI English teacher. ",
        "Today we're going to practice conversation skills. ",
        "Let's start with a simple greeting. ",
        "How would you say hello to someone you meet for the first time?"
    ]
    
    for i, text in enumerate(texts):
        print(f"添加第 {i+1} 段文本: '{text}'")
        tts.add_text(text)
        time.sleep(0.5)  # 模擬文本生成的時間間隔
    
    # 確保所有文本都被處理
    tts.wait_until_done()
    
    print("\n=== 測試2: 保存音頻文件 ===")
    test_text = "This is a test of the TTS system. The audio will be saved to a file."
    tts.save_audio(test_text, "test_tts_output.wav")
    
    # 關閉TTS管理器
    tts.shutdown()