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
        punctuation_pattern: str = r'[.!?,;:\n]',  # 標點符號模式
        play_locally: bool = False  # 是否在本地播放音頻
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
            self.model_dir = base_dir / "src" / "models" / "model_data" / "tts_models"
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
        self.play_locally = play_locally
        
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
        # 對全局持久化音頻緩衝區的引用
        try:
            # 嘗試從重構後的模塊導入
            from src.api.routes import persistent_audio_buffer
        except ImportError:
            # 作為備選，創建一個本地的緩衝區（如果無法導入）
            import queue
            persistent_audio_buffer = queue.Queue(maxsize=20)
            print("警告：使用本地持久化音頻緩衝區")
        
        while self.is_running:
            try:
                # 檢查緩衝區是否應該處理
                text_to_process = self._should_process_buffer()
                
                if text_to_process:
                    print(f"🔄 處理緩衝區文本: '{text_to_process[:30]}...'")
                    
                    # 生成音頻
                    audio_data = self._generate_audio_internal(text_to_process)
                    
                    if len(audio_data) > 0:
                        # 將音頻放入播放隊列
                        self.audio_queue.put(audio_data.copy())  # 使用copy避免引用問題
                        
                        # 同時將音頻放入持久化緩衝區
                        if persistent_audio_buffer is not None:
                            try:
                                # 如果緩衝區已滿，先移除舊的數據
                                if persistent_audio_buffer.full():
                                    try:
                                        persistent_audio_buffer.get_nowait()
                                    except:
                                        pass
                                persistent_audio_buffer.put(audio_data.copy())
                                print(f"✅ 音頻已添加到持久化緩衝區，緩衝區大小: {persistent_audio_buffer.qsize()}")
                            except Exception as e:
                                print(f"❌ 添加到持久化緩衝區出錯: {str(e)}")
                        
                        print(f"✅ 音頻生成完成，長度: {len(audio_data)} 樣本，隊列大小: {self.audio_queue.qsize()}")
                    else:
                        print("⚠️ 生成的音頻為空")
                
                # 短暫休眠以減少CPU使用率
                time.sleep(0.1)
                
            except Exception as e:
                print(f"❌ 音頻生成錯誤: {str(e)}")
                import traceback
                print(traceback.format_exc())
                time.sleep(0.5)  # 出錯時稍微延長休眠時間
    
    def _player_worker(self):
        """
        播放線程：從播放隊列中取出音頻並播放
        """
        if not self.play_locally:
            print("本地播放已禁用，播放線程將退出")
            return
            
        import sounddevice as sd
        
        # 設置播放參數
        sd.default.samplerate = self.sample_rate
        sd.default.channels = 1
        
        print(f"音頻播放線程已啟動，采樣率: {self.sample_rate} Hz")
        
        # 設置等待結束的計時器
        last_audio_time = time.time()
        wait_timeout = 3.0  # 等待結束的時間（秒）
        
        while self.is_running:
            try:
                # 從隊列中取出音頻數據
                audio_data = self.get_next_audio(timeout=0.5)  # 設置較短的逾時時間
                
                if audio_data is not None and len(audio_data) > 0:
                    # 更新最後一次收到音頻的時間
                    last_audio_time = time.time()
                    
                    # 播放音頻
                    print(f"播放音頻: {len(audio_data)} 樣本, 采樣率: {self.sample_rate}")
                    sd.play(audio_data, self.sample_rate)
                    sd.wait()  # 等待播放完成
                    print("音頻播放完成")
                    
                    # 播放完成後等待一小段時間，確保句子之間有自然的停頓
                    time.sleep(0.1)
                else:
                    # 檢查是否應該結束播放
                    current_time = time.time()
                    elapsed_since_last_audio = current_time - last_audio_time
                    
                    # 如果文本緩衝區為空且已經超過等待逾時時間，則可能已經播放完所有音頻
                    if not self.text_buffer and elapsed_since_last_audio > wait_timeout:
                        # 檢查緩衝區是否為空，但不結束播放線程
                        print(f"等待音頻逾時 ({elapsed_since_last_audio:.1f} 秒)，緩衝區為空，等待新的文本")
                        time.sleep(0.5)  # 等待更長時間
                    else:
                        # 如果沒有音頻數據，等待一段時間
                        time.sleep(0.1)
            
            except Exception as e:
                print(f"播放音頻時出錯: {str(e)}")
                time.sleep(0.5)  # 出錯時稍微延長休眠時間
        
        print("音頻播放線程結束")
    
    def _should_process_buffer(self) -> Optional[str]:
        """
        檢查緩衝區是否應該被處理
        返回應處理的文本，或None表示不應處理
        """
        # 檢查緩衝區是否為空
        if not self.text_buffer:
            return None
            
        # 檢查是否檢測到句子結束標點
        sentence_end_marks = ['.', '!', '?', ':', ';']
        
        # 1. 如果緩衝區中有完整句子（以標點結尾），優先處理完整句子
        for mark in sentence_end_marks:
            index = self.text_buffer.rfind(mark)
            if index > 0 and len(self.text_buffer) > self.min_buffer_size: # 找到了句子結尾標點
                # 提取到這個標點為止的所有文本（包含標點）
                text_to_process = self.text_buffer[:index+1].strip()
                # 保留剩餘文本在緩衝區中
                self.text_buffer = self.text_buffer[index+1:].strip()
                print(f"檢測到完整句子，提取處理: '{text_to_process}'，保留在緩衝區: '{self.text_buffer}'")
                return text_to_process
        
        # 2. 如果緩衝區超過最小大小，但沒有完整句子，則需要判斷是否適合處理
        # if len(self.text_buffer) > self.min_buffer_size:
        #     # 查找最後一個空格，作為可能的斷句點
        #     last_space_index = self.text_buffer.rfind(' ')
            
        #     # 如果找到空格，並且有足夠的內容
        #     if last_space_index > 0 and last_space_index > self.min_buffer_size / 2:
        #         # 提取到最後一個空格為止的所有文本
        #         text_to_process = self.text_buffer[:last_space_index].strip()
        #         # 保留剩餘文本在緩衝區中
        #         self.text_buffer = self.text_buffer[last_space_index:].strip()
        #         print(f"緩衝區達到閾值，以空格為界處理: '{text_to_process}'，保留在緩衝區: '{self.text_buffer}'")
        #         return text_to_process
        #     else:
        #         # 緩衝區很大，但沒有找到合適的斷句點，此時需要全部處理
        #         text_to_process = self.text_buffer.strip()
        #         self.text_buffer = ""
        #         print(f"緩衝區達到閾值，無合適斷句點，處理全部: '{text_to_process}'")
        #         return text_to_process
                
        # 緩衝區尚未達到處理閾值
        return None
    
    def _filter_special_tokens(self, text: str) -> str:
        """過濾特殊標記、URL和Markdown格式符號"""
        if not text:
            return ""
            
        # 過濾特殊標記
        text = re.sub(r'<[^>]+>', '', text)
        
        # 過濾 URL
        text = re.sub(r'https?://\S+|www\.\S+', '', text)
        
        # 過濾 Markdown 格式符號
        text = re.sub(r'\*\*|__|~~|```|\[|\]|\(|\)|#|>|\|', '', text)
        
        # 過濾 emoji
        emoji_pattern = re.compile("[\U0001F600-\U0001F64F\U0001F300-\U0001F5FF\U0001F680-\U0001F6FF\U0001F700-\U0001F77F]+", flags=re.UNICODE)
        text = emoji_pattern.sub("", text)
        
        return text
        
    def _preprocess_text(self, text: str) -> str:
        """預處理文本，移除特殊標記並清理格式"""
        if not text:
            return ""
            
        # 過濾特殊標記、URL和Markdown格式
        text = self._filter_special_tokens(text)
        
        # 在處理前保存原始的文本，用於偵錯
        original_text = text
        
        # 保護所有撇號相關的結構，不只是"單個字母+撇號+單個字母"的形式
        # 包括：I'm, you're, don't, can't, he's等多種縮寫形式
        protected_text = text
        # 處理像it's, that's這樣的縮寫
        protected_text = re.sub(r"(\w+)'(\w+)", r"\1_APOSTROPHE_\2", protected_text)
        # 處理像I'm, I'll這樣的縮寫
        protected_text = re.sub(r"(\w+)'(\w+)", r"\1_APOSTROPHE_\2", protected_text)
        # 處理像don't, can't這樣的縮寫
        protected_text = re.sub(r"(\w+)'(\w+)", r"\1_APOSTROPHE_\2", protected_text)
        
        # 保護破折號和其他可能被誤處理的符號
        protected_text = protected_text.replace("–", "_ENDASH_")
        protected_text = protected_text.replace("—", "_EMDASH_")
        protected_text = protected_text.replace("-", "_HYPHEN_")
        
        # 保護標點符號，避免在標點前後添加多餘空格
        for punct in [',', '.', '!', '?', ':', ';']:
            protected_text = protected_text.replace(punct, f"_PUNCT_{punct}_")
        
        # 移除多餘的空格（用單個空格替換所有連續空格）
        protected_text = re.sub(r'\s+', ' ', protected_text)
        
        # 恢復所有保護的標記
        # 先恢復標點，確保標點前無空格
        for punct in [',', '.', '!', '?', ':', ';']:
            protected_text = protected_text.replace(f" _PUNCT_{punct}_", f"{punct}")  # 移除標點前的空格
            protected_text = protected_text.replace(f"_PUNCT_{punct}_", f"{punct}")   # 處理其他情況
        
        # 恢復所有縮寫詞中的撇號
        result_text = protected_text.replace("_APOSTROPHE_", "'")
        
        # 恢復破折號和連字符
        result_text = result_text.replace("_ENDASH_", "–")
        result_text = result_text.replace("_EMDASH_", "—")
        result_text = result_text.replace("_HYPHEN_", "-")
        
        # 移除前後空格
        result_text = result_text.strip()
        
        # 如果處理後的文本與原始文本有明顯差異，記錄一下以便調試
        if result_text.replace(" ", "") != original_text.replace(" ", ""):
            print(f"文本預處理前: '{original_text}'")
            print(f"文本預處理後: '{result_text}'")
        
        return result_text
    
    def _generate_audio_internal(self, text: str) -> np.ndarray:
        """
        內部方法：生成音頻數據
        
        Args:
            text: 要合成的文本
            
        Returns:
            音頻數據或空數組
        """
        if not text or not text.strip():
            print("⚠️ 收到空文本，跳過音頻生成")
            return np.array([])
            
        try:
            # 預處理文本
            processed_text = self._preprocess_text(text)
            if not processed_text or not processed_text.strip():
                print("⚠️ 預處理後文本為空，跳過音頻生成")
                return np.array([])
            
            # 移除強制添加句號的邏輯，保留文本原狀
            print(f"開始為文本生成音頻: '{processed_text[:50]}'{'...' if len(processed_text) > 50 else ''}")
            
            # 使用KPipeline生成音頻
            with torch.no_grad():
                # 使用在_load_model中測試確定的調用方式
                all_audio = []
                
                if hasattr(self, 'use_named_params') and self.use_named_params:
                    # 使用命名參數調用
                    print("使用命名參數調用pipeline")
                    generator = self.pipeline(processed_text, voice=self.voice_tensor, speed=self.speed)
                else:
                    # 使用位置參數調用
                    print("使用位置參數調用pipeline")
                    generator = self.pipeline(processed_text, self.voice_tensor, self.speed)
                
                # 收集音頻
                for _, _, audio in generator:
                    all_audio.append(audio)
                
                # 合併音頻
                if not all_audio:
                    print("生成的音頻片段為空")
                    return np.array([])
                    
                # 合併所有音頻片段
                audio_array = np.concatenate(all_audio)
                
                # 確保音頻數據有效
                if audio_array.size == 0:
                    print("⚠️ 生成的音頻數據為空")
                    return np.array([])
                    
                print(f"✅ 音頻生成成功，長度: {len(audio_array)} 樣本")
                return audio_array
                
        except Exception as e:
            print(f"❌ 音頻生成出錯: {str(e)}")
            import traceback
            traceback.print_exc()
            return np.array([])
            
    def clear_buffer(self) -> None:
        """清空所有緩衝區和音頻階列"""
        # 清空文本緩衝區
        self.text_buffer = ""
            
        # 清空音頻階列
        try:
            while not self.audio_queue.empty():
                self.audio_queue.get_nowait()
                self.audio_queue.task_done()
        except Exception as e:
            print(f"清空音頻階列出錯: {str(e)}")
            
        print("所有緩衝區和階列已清空")
        
    def add_text(self, text: str) -> None:
        """
        添加文本到緩衝區中進行處理
            
        Args:
            text: 要添加的文本
        """
        if not text:
            return
            
        # 添加文本到緩衝區
        self.text_buffer += text
        print(f"添加文本到緩衝區: '{text}' (緩衝區當前大小: {len(self.text_buffer)} 字符)")
        
        # 確保文本結尾有適當的空格，以避免句子連在一起
        # if not self.text_buffer.endswith((' ', '\n', '.', '!', '?', ',', ';', ':')):
        #     self.text_buffer += ' '
        
        # 檢查是否有句子結束標點
        if any(p in text for p in ['.', '!', '?']):
            print("檢測到句子結束標記，立即處理緩衝區")
            # 強制處理緩衝區
            self.force_process()
    
    def force_process(self) -> None:
        """強制處理當前緩衝區中的文本，不管緩衝區大小"""
        # 從routes導入持久化緩衝區
        try:
            from src.api.routes import persistent_audio_buffer
        except ImportError:
            # 作為備選，創建一個本地的緩衝區（如果無法導入）
            import queue
            persistent_audio_buffer = queue.Queue(maxsize=20)
            print("警告：使用本地持久化音頻緩衝區")
            
        if len(self.text_buffer) > 0:
            text_to_process = self.text_buffer
            self.text_buffer = ""
            
            # 移除強制添加句號的邏輯，保留文本原樣
            print(f"🔄 強制處理緩衝區中的 {len(text_to_process)} 字符文本: '{text_to_process}'")
            
            # 生成音頻並添加到隊列
            try:
                audio_data = self._generate_audio_internal(text_to_process)
                if len(audio_data) > 0:
                    self.audio_queue.put(audio_data.copy())  # 使用copy避免引用問題
                    
                    # 同時將音頻放入持久化緩衝區
                    if persistent_audio_buffer is not None:
                        try:
                            # 如果緩衝區已滿，先移除舊的數據
                            if persistent_audio_buffer.full():
                                try:
                                    persistent_audio_buffer.get_nowait()
                                except:
                                    pass
                            persistent_audio_buffer.put(audio_data.copy())
                            print(f"✅ 音頻已添加到持久化緩衝區，緩衝區大小: {persistent_audio_buffer.qsize()}")
                        except Exception as e:
                            print(f"❌ 添加到持久化緩衝區出錯: {str(e)}")
                    
                    print(f"✅ 強制處理完成，音頻長度: {len(audio_data)} 樣本，隊列大小: {self.audio_queue.qsize()}")
                else:
                    print("⚠️ 強制處理生成的音頻為空")
            except Exception as e:
                print(f"❌ 強制處理緩衝區時出錯: {str(e)}")
                import traceback
                print(traceback.format_exc())
    
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
    
    def generate_audio(self, text: str) -> np.ndarray:
        """
        生成音頻數據但不播放或保存
        
        Args:
            text: 要轉換為語音的文本
            
        Returns:
            生成的音頻數據，如果生成失敗則返回空數組
        """
        return self._generate_audio_internal(text)
    
    def get_next_audio(self, timeout: float = 0.5) -> Optional[np.ndarray]:
        """
        從音頻隊列中取出下一個音頻段
        
        Args:
            timeout: 等待音頻數據的最大時間（秒）
            
        Returns:
            音頻數據或None（如果隊列為空）
        """
        try:
            # 如果隊列為空但緩衝區有文本，則強制處理緩衝區
            if self.audio_queue.empty() and self.text_buffer:
                # 檢查緩衝區中是否有完整句子
                has_complete_sentence = any(p in self.text_buffer for p in ['.', '!', '?'])
                
                if has_complete_sentence and len(self.text_buffer) > self.min_buffer_size:
                    print(f"音頻隊列為空，但緩衝區有 {len(self.text_buffer)} 字符，強制處理")
                    self.force_process()
                    
                    # 強制處理後再次檢查隊列
                    if not self.audio_queue.empty():
                        return self.audio_queue.get(timeout=timeout)
                
            # 嘗試從隊列中取出音頻數據
            if not self.audio_queue.empty():
                audio_data = self.audio_queue.get(timeout=timeout)
                
                # 確保音頻數據不為空
                if audio_data is not None and len(audio_data) > 0:
                    return audio_data
                else:
                    print("取出的音頻數據為空，繼續等待")
                    return None
            else:
                # 如果隊列為空但有持續的文本輸入，則不要印出太多日誌
                if not self.text_buffer:
                    print("音頻隊列已空，等待數據...")
                return None
                
            audio_data = self.audio_queue.get(timeout=timeout)
            self.audio_queue.task_done()
            if audio_data is not None:
                print(f"成功獲取音頻，長度: {len(audio_data)} 樣本")
                return audio_data
            return None
        except queue.Empty:
            return None
    
    def wait_until_done(self) -> None:
        """等待所有隊列中的項目處理完成"""
        # 強制處理緩衝區中的剩餘文本
        self.force_process()
        
        # 等待音頻隊列清空
        try:
            self.audio_queue.join(timeout=5.0)  # 添加超時以避免無限等待
            print("✅ 所有語音處理任務已完成")
        except Exception as e:
            print(f"⚠️ 等待語音處理完成時出錯: {str(e)}")
            # 清空隊列以避免死鎖
            try:
                while not self.audio_queue.empty():
                    self.audio_queue.get_nowait()
                    self.audio_queue.task_done()
            except:
                pass
    
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

    def cleanup(self) -> None:
        """
        清理TTS管理器的資源，停止線程並釋放模型記憶體
        應在應用程序關閉時調用
        """
        print("開始清理TTS管理器資源...")
        
        # 停止工作線程
        self.is_running = False
        if self.generator_thread and self.generator_thread.is_alive():
            print("等待生成線程停止...")
            # 添加一個小段文本以解除任何可能的阻塞
            self.add_text("cleanup")
            self.generator_thread.join(timeout=5)
            if self.generator_thread.is_alive():
                print("警告：生成線程未能在超時時間內停止")
        
        # 清空隊列
        try:
            while not self.audio_queue.empty():
                self.audio_queue.get_nowait()
                self.audio_queue.task_done()
        except:
            pass
        
        # 清空文本緩衝區
        self.text_buffer = ""
        
        # 釋放模型（如果可能）
        if hasattr(self, 'pipeline') and self.pipeline is not None:
            print("釋放TTS模型資源...")
            try:
                # 嘗試使用常見的模型釋放方法
                if hasattr(self.pipeline, 'to'):
                    self.pipeline.to('cpu')
                
                # 釋放CUDA緩存
                if torch.cuda.is_available():
                    torch.cuda.empty_cache()
                
                # 設置為None以幫助垃圾回收
                self.pipeline = None
                self.voice_tensor = None
            except Exception as e:
                print(f"釋放TTS模型資源時出錯: {str(e)}")
        
        print("TTS管理器資源清理完成")

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