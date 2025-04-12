import os
import numpy as np
import torch
import time
import threading
import queue
import soundfile as sf
from pathlib import Path
from typing import Optional, Union, List, Dict, Any, Callable, Tuple
from faster_whisper import WhisperModel

class STTManager:
    """
    語音轉文字管理器，支持流式處理和批量處理。
    基於faster_whisper實現，自動下載模型。
    """
    def __init__(
        self,
        model_dir: Optional[Union[str, Path]] = None,
        model_size: str = "medium",  # 可選: "tiny", "base", "small", "medium", "large-v1", "large-v2", "large-v3"
        device: str = "auto",  # "auto", "cpu", "cuda"
        compute_type: str = "float16",  # "float16", "float32", "int8"
        download_root: Optional[str] = None,
        stream_mode: bool = False,
        language: Optional[str] = None,  # 可選指定語言代碼，如"en", "zh", "ja"等
        translate: bool = False  # 是否翻譯為英文
    ):
        """
        初始化STT管理器
        
        Args:
            model_dir: 模型目錄，如果為None則使用默認路徑
            model_size: 模型大小
            device: 計算設備 ("auto", "cpu", "cuda")
            compute_type: 計算類型
            download_root: 模型下載目錄，如果為None，則使用model_dir
            stream_mode: 是否啟用串流模式
            language: 指定轉錄語言
            translate: 是否翻譯為英文
        """
        # 初始化模型路徑
        if model_dir is None:
            base_dir = Path(__file__).resolve().parent.parent.parent
            self.model_dir = base_dir / "src" / "models" / "model_data" / "stt_models"
        else:
            self.model_dir = Path(model_dir)
        
        # 設置下載目錄
        if download_root is None:
            download_root = str(self.model_dir)
        
        # 設置設備
        if device == "auto":
            self.device = "cuda" if torch.cuda.is_available() else "cpu"
        else:
            self.device = device
        
        # 保存參數
        self.model_size = model_size
        self.compute_type = compute_type
        self.stream_mode = stream_mode
        self.language = language
        self.translate = translate
        
        # 初始化模型
        self._load_model(download_root)
        
        # 初始化串流模式
        if stream_mode:
            self.stt_queue = queue.Queue()
            self.result_queue = queue.Queue()
            self.is_running = True
            self.stt_thread = threading.Thread(target=self._stt_worker, daemon=True)
            self.stt_thread.start()
    
    def _load_model(self, download_root: str) -> None:
        """
        加載STT模型
        
        Args:
            download_root: 模型下載目錄
        """
        try:
            print(f"加載STT模型: {self.model_size}, 設備: {self.device}, 計算類型: {self.compute_type}")
            self.model = WhisperModel(
                self.model_size,
                device=self.device,
                compute_type=self.compute_type,
                download_root=download_root
            )
            print("STT模型加載成功")
        except Exception as e:
            import traceback
            print(f"STT模型加載失敗: {e}")
            traceback.print_exc()
            raise RuntimeError(f"STT模型加載失敗: {str(e)}")
    
    def _stt_worker(self) -> None:
        """
        STT工作線程，處理隊列中的音頻文件
        """
        while self.is_running:
            try:
                # 從隊列獲取項目
                item = self.stt_queue.get(timeout=0.5)
                if item is None:
                    break
                
                # 解析項目（可能是音頻路徑或者音頻數據+回調）
                if isinstance(item, tuple) and len(item) >= 2:
                    audio_input, callback = item[0], item[1]
                    options = item[2] if len(item) > 2 and isinstance(item[2], dict) else {}
                else:
                    audio_input, callback, options = item, None, {}
                
                # 處理音頻
                result = self.transcribe(audio_input, **options)
                
                # 添加到結果隊列或調用回調
                if callback and callable(callback):
                    callback(result)
                else:
                    self.result_queue.put(result)
                    
            except queue.Empty:
                continue
            except Exception as e:
                print(f"STT處理錯誤: {e}")
                import traceback
                traceback.print_exc()
            finally:
                # 標記任務完成
                if 'item' in locals() and item is not None:
                    self.stt_queue.task_done()
    
    def transcribe(
        self,
        audio_input: Union[str, np.ndarray, Path],
        initial_prompt: Optional[str] = None,
        word_timestamps: bool = False,
        **kwargs
    ) -> Dict[str, Any]:
        """
        將音頻轉錄為文本
        
        Args:
            audio_input: 音頻文件路徑或音頻數據
            initial_prompt: 初始提示（可提高特定領域的準確性）
            word_timestamps: 是否生成單詞級時間戳
            **kwargs: 其他參數傳遞給faster_whisper的transcribe方法
        
        Returns:
            轉錄結果字典，包含文本和時間戳
        """
        if not isinstance(audio_input, (str, np.ndarray, Path)):
            raise ValueError(f"不支持的音頻輸入類型: {type(audio_input)}")
        
        try:
            print(f"開始轉錄: {audio_input if isinstance(audio_input, (str, Path)) else '音頻數據'}")
            start_time = time.time()
            
            # 準備轉錄選項
            transcribe_options = {
                "initial_prompt": initial_prompt,
                "word_timestamps": word_timestamps,
            }
            
            # 添加語言選項
            if self.language:
                transcribe_options["language"] = self.language
            
            # 添加翻譯選項
            if self.translate:
                transcribe_options["task"] = "translate"
            
            # 合併其他選項
            transcribe_options.update(kwargs)
            
            # 轉錄音頻
            segments, info = self.model.transcribe(audio_input, **transcribe_options)
            
            # 收集結果
            result = {
                "text": "",
                "segments": [],
                "language": info.language,
                "language_probability": info.language_probability
            }
            
            # 提取所有片段
            for segment in segments:
                result["text"] += segment.text + " "
                segment_info = {
                    "id": segment.id,
                    "seek": segment.seek,
                    "start": segment.start,
                    "end": segment.end,
                    "text": segment.text,
                    "tokens": segment.tokens,
                    "temperature": segment.temperature,
                    "avg_logprob": segment.avg_logprob,
                    "compression_ratio": segment.compression_ratio,
                    "no_speech_prob": segment.no_speech_prob
                }
                
                # 添加單詞時間戳（如果有）
                if hasattr(segment, "words") and segment.words:
                    segment_info["words"] = [
                        {
                            "word": word.word,
                            "start": word.start,
                            "end": word.end,
                            "probability": word.probability
                        } for word in segment.words
                    ]
                
                result["segments"].append(segment_info)
            
            result["text"] = result["text"].strip()
            
            end_time = time.time()
            print(f"轉錄完成，耗時: {end_time - start_time:.2f} 秒")
            print(f"轉錄文本: {result['text']}")
            
            return result
            
        except Exception as e:
            import traceback
            print(f"轉錄錯誤: {e}")
            traceback.print_exc()
            return {"error": str(e), "text": ""}
    
    def stream_audio(
        self,
        audio_input: Union[str, np.ndarray, Path],
        callback: Optional[Callable] = None,
        **options
    ) -> None:
        """
        將音頻文件加入串流處理隊列
        
        Args:
            audio_input: 音頻文件路徑或音頻數據
            callback: 回調函數，處理完成後調用
            **options: 轉錄選項
        """
        if not self.stream_mode:
            raise RuntimeError("必須在串流模式下使用stream_audio方法")
        
        # 添加到處理隊列
        self.stt_queue.put((audio_input, callback, options))
    
    def get_result(self, timeout: float = None) -> Optional[Dict[str, Any]]:
        """
        從結果隊列獲取轉錄結果
        
        Args:
            timeout: 超時時間，None表示無限等待
        
        Returns:
            轉錄結果或None（超時）
        """
        if not self.stream_mode:
            raise RuntimeError("必須在串流模式下使用get_result方法")
        
        try:
            return self.result_queue.get(timeout=timeout)
        except queue.Empty:
            return None
    
    def transcribe_file(
        self,
        audio_file: Union[str, Path],
        output_format: str = "txt",
        output_path: Optional[Union[str, Path]] = None,
        **options
    ) -> Dict[str, Any]:
        """
        轉錄音頻文件並可選保存結果
        
        Args:
            audio_file: 音頻文件路徑
            output_format: 輸出格式 ("txt", "json", "srt", "vtt")
            output_path: 輸出文件路徑，None表示不保存
            **options: 轉錄選項
        
        Returns:
            轉錄結果
        """
        # 確保文件存在
        if not isinstance(audio_file, (str, Path)) or not os.path.exists(str(audio_file)):
            raise FileNotFoundError(f"音頻文件不存在: {audio_file}")
        
        # 轉錄音頻
        result = self.transcribe(audio_file, **options)
        
        # 如果需要保存結果
        if output_path:
            self._save_result(result, output_format, output_path)
        
        return result
    
    def _save_result(
        self,
        result: Dict[str, Any],
        output_format: str,
        output_path: Union[str, Path]
    ) -> None:
        """
        保存轉錄結果
        
        Args:
            result: 轉錄結果
            output_format: 輸出格式
            output_path: 輸出文件路徑
        """
        try:
            output_path = Path(output_path)
            
            # 如果沒有指定擴展名，添加默認擴展名
            if not output_path.suffix:
                output_path = output_path.with_suffix(f".{output_format}")
            
            with open(output_path, "w", encoding="utf-8") as f:
                if output_format == "txt":
                    f.write(result["text"])
                elif output_format == "json":
                    import json
                    json.dump(result, f, ensure_ascii=False, indent=2)
                elif output_format == "srt":
                    f.write(self._to_srt(result))
                elif output_format == "vtt":
                    f.write(self._to_vtt(result))
                else:
                    raise ValueError(f"不支持的輸出格式: {output_format}")
            
            print(f"結果已保存至: {output_path}")
        
        except Exception as e:
            print(f"保存結果失敗: {e}")
    
    def _to_srt(self, result: Dict[str, Any]) -> str:
        """生成SRT格式的字幕"""
        srt_text = ""
        for i, segment in enumerate(result["segments"]):
            start = self._format_timestamp(segment["start"], srt=True)
            end = self._format_timestamp(segment["end"], srt=True)
            srt_text += f"{i+1}\n{start} --> {end}\n{segment['text']}\n\n"
        return srt_text
    
    def _to_vtt(self, result: Dict[str, Any]) -> str:
        """生成VTT格式的字幕"""
        vtt_text = "WEBVTT\n\n"
        for i, segment in enumerate(result["segments"]):
            start = self._format_timestamp(segment["start"])
            end = self._format_timestamp(segment["end"])
            vtt_text += f"{start} --> {end}\n{segment['text']}\n\n"
        return vtt_text
    
    def _format_timestamp(self, seconds: float, srt: bool = False) -> str:
        """格式化時間戳"""
        hours, remainder = divmod(seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        if srt:
            return f"{int(hours):02d}:{int(minutes):02d}:{int(seconds):02d},{int((seconds - int(seconds)) * 1000):03d}"
        else:
            return f"{int(hours):02d}:{int(minutes):02d}:{int(seconds):02d}.{int((seconds - int(seconds)) * 1000):03d}"
    
    def wait_until_done(self) -> None:
        """等待所有隊列中的項目處理完成"""
        if self.stream_mode:
            self.stt_queue.join()
    
    def shutdown(self) -> None:
        """關閉STT管理器"""
        if self.stream_mode and self.is_running:
            self.is_running = False
            self.stt_queue.put(None)
            if hasattr(self, 'stt_thread') and self.stt_thread.is_alive():
                self.stt_thread.join(timeout=2.0)
    
    def __del__(self):
        """析構函數"""
        self.shutdown()

# 測試代碼
if __name__ == "__main__":
    # 基本用法
    stt = STTManager()
    # 從當前目錄獲取測試音頻
    test_audio = Path(__file__).parent.parent.parent / "test_kokoro_full_output.wav"
    if test_audio.exists():
        result = stt.transcribe(str(test_audio))
        print(f"轉錄結果: {result['text']}")