import os
import numpy as np
import torch
import sounddevice as sd
import soundfile as sf
import threading
import queue
import time
from pathlib import Path
from typing import Optional, Union, List, Tuple, Generator, Dict, Any
from kokoro import KPipeline

class TTSManager:
    """
    文字轉語音管理器，允許自動下載模型但使用本地語音文件。
    """
    def __init__(
        self, 
        model_dir: Optional[Union[str, Path]] = None,
        voice_file: str = "voices/af_heart.pt",
        lang_code: str = 'a',  # 'a' 表示美式英語
        speed: float = 1.0,
        sample_rate: int = 24000,
        use_cuda: bool = True,
        stream_mode: bool = False
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
            stream_mode: 是否使用串流模式
        """
        # 初始化模型路徑
        if model_dir is None:
            base_dir = Path(__file__).resolve().parent.parent.parent
            self.model_dir = base_dir / "src" / "models" / "tts_models"
        else:
            self.model_dir = Path(model_dir)
            
        # 設置語音文件路徑
        print(voice_file)
        self.voice_file = voice_file
        self.voice_path = os.path.join(self.model_dir, "voices/" + voice_file)
        
        # 設置其他參數
        self.lang_code = lang_code
        self.speed = speed
        self.sample_rate = sample_rate
        self.use_cuda = use_cuda and torch.cuda.is_available()
        self.stream_mode = stream_mode
        
        # 檢查語音文件是否存在
        self._check_voice_file()
        
        # 加載模型
        self._load_model()
        
        # 初始化串流模式
        if stream_mode:
            self.tts_queue = queue.Queue()
            self.is_running = True
            self.tts_thread = threading.Thread(target=self._tts_worker, daemon=True)
            self.tts_thread.start()
    
    def _check_voice_file(self):
        """檢查語音文件是否存在"""
        # 檢查語音文件
        if not os.path.exists(self.voice_path):
            print(f"警告: 找不到語音文件 {self.voice_path}")
            # 搜索其他可能的語音文件
            voice_dir = self.model_dir / "voices"
            if voice_dir.exists():
                potential_voices = list(voice_dir.glob("**/*.pt"))
                if potential_voices:
                    print(f"找到可能的語音文件: {[str(p) for p in potential_voices]}")
                    # 使用第一個找到的語音文件
                    self.voice_path = str(potential_voices[0])
                    print(f"將使用: {self.voice_path}")
                else:
                    print("找不到任何語音文件")
            else:
                print(f"語音目錄 {voice_dir} 不存在")
                # 嘗試創建目錄
                try:
                    voice_dir.mkdir(parents=True, exist_ok=True)
                    print(f"已創建語音目錄: {voice_dir}")
                except Exception as e:
                    print(f"創建語音目錄失敗: {e}")
        else:
            print(f"找到語音文件: {self.voice_path}")
    
    def _load_model(self):
        """加載KPipeline和語音模型"""
        try:
            # 確定設備
            device = "cuda" if self.use_cuda and torch.cuda.is_available() else "cpu"
            print(f"使用設備: {device}")
            
            # 初始化KPipeline (允許自動下載模型)
            print(f"初始化KPipeline，lang_code={self.lang_code}")
            self.pipeline = KPipeline(lang_code=self.lang_code)
            
            # 加載語音模型
            if os.path.exists(self.voice_path):
                print(f"加載語音文件: {self.voice_path}")
                self.voice_tensor = torch.load(self.voice_path, weights_only=True)
                print("成功加載語音模型!")
            else:
                raise FileNotFoundError(f"找不到語音文件: {self.voice_path}")
                
        except Exception as e:
            import traceback
            traceback.print_exc()
            raise RuntimeError(f"TTS模型加載失敗: {str(e)}")
    
    def _tts_worker(self):
        """TTS工作線程"""
        while self.is_running:
            try:
                # 從隊列獲取項目
                item = self.tts_queue.get(timeout=0.5)
                if item is None:
                    break
                
                # 處理項目
                if isinstance(item, tuple):
                    text, callback = item
                else:
                    text, callback = item, None
                
                # 生成並播放音頻
                audio_data = self.generate_audio(text, play=True)
                
                # 調用回調函數
                if callback and callable(callback):
                    callback(audio_data)
                    
            except queue.Empty:
                continue
            except Exception as e:
                print(f"TTS處理錯誤: {str(e)}")
            finally:
                if 'item' in locals() and item is not None:
                    self.tts_queue.task_done()
    
    def generate_audio(self, text: str, play: bool = False) -> np.ndarray:
        """生成語音音頻"""
        if not text or text.strip() == "":
            return np.array([])
            
        try:
            print(f"生成文本: '{text}'")
            
            # 生成語音
            start_time = time.time()
            #voice_tensor = torch.load(self.voice_path, weights_only=True)

            # 嘗試使用參數調用
            try:
                generator = self.pipeline(text, voice=self.voice_tensor, speed=self.speed)
            except TypeError as te:
                print(f"Pipeline調用出錯: {te}，嘗試替代方式")
                # 嘗試不使用命名參數
                generator = self.pipeline(text, self.voice_tensor, self.speed)
            
            # 收集音頻片段
            all_audio = []
            try:
                for i, (graphemes, phonemes, audio) in enumerate(generator):
                    all_audio.append(audio)

            except Exception as iter_e:
                print(f"迭代語音生成器時出錯: {iter_e}")
                import traceback
                traceback.print_exc()
            
            # 合併音頻
            if not all_audio:
                print("未生成任何音頻片段")
                return np.array([])
                
            full_audio = np.concatenate(all_audio)
            
            end_time = time.time()
            print(f"音頻生成花費時間: {end_time - start_time:.2f} 秒")
            
            # 播放音頻
            if play:
                sd.play(full_audio, samplerate=self.sample_rate)
                sd.wait()
                
            return full_audio
                
        except Exception as e:
            import traceback
            print(f"語音生成錯誤: {str(e)}")
            traceback.print_exc()
            return np.array([])
    
    def save_audio(self, text: str, file_path: str) -> bool:
        """生成並保存音頻"""
        audio_data = self.generate_audio(text, play=False)
        if len(audio_data) > 0:
            try:
                sf.write(file_path, audio_data, self.sample_rate)
                print(f"音頻已保存至: {file_path}")
                return True
            except Exception as e:
                print(f"保存音頻錯誤: {str(e)}")
                return False
        return False
    
    def stream_text(self, text: str, callback=None):
        """將文本加入串流處理隊列"""
        if not self.stream_mode:
            raise RuntimeError("必須在串流模式下使用stream_text方法")
            
        if text and text.strip():
            if callback:
                self.tts_queue.put((text, callback))
            else:
                self.tts_queue.put(text)
    
    def wait_until_done(self):
        """等待所有隊列中的項目處理完成"""
        if self.stream_mode:
            self.tts_queue.join()
    
    def shutdown(self):
        """關閉TTS管理器"""
        if self.stream_mode and self.is_running:
            self.is_running = False
            self.tts_queue.put(None)
            if self.tts_thread.is_alive():
                self.tts_thread.join(timeout=2.0)

    def __del__(self):
        """析構函數"""
        self.shutdown()

# 測試代碼
if __name__ == "__main__":
    tts = TTSManager()
    tts.generate_audio("Hello, this is a test of the TTS system.", play=True)