import os
import time
import threading
import queue
import re
import torch
from pathlib import Path
from typing import Optional, Union, List, Dict, Any, Callable, Tuple, Generator
from transformers import AutoTokenizer, BitsAndBytesConfig, Gemma3ForCausalLM, StoppingCriteria, StoppingCriteriaList

class StreamingStoppingCriteria(StoppingCriteria):
    """
    自定義停止條件，實現真正的逐token流式輸出
    """
    def __init__(
        self, 
        tokenizer, 
        callback: Callable[[str], None],
        eos_token_id: int, 
        max_new_tokens: int, 
        min_sentence_length: int = 8
    ):
        self.tokenizer = tokenizer
        self.callback = callback
        self.eos_token_id = eos_token_id
        self.max_new_tokens = max_new_tokens
        self.min_sentence_length = min_sentence_length
        self.token_count = 0
        self.current_sentence = ""
        
        # 過濾器
        self.emoji_pattern = re.compile("[\U0001F600-\U0001F64F\U0001F300-\U0001F5FF\U0001F680-\U0001F6FF\U0001F700-\U0001F77F]+", flags=re.UNICODE)
        self.markdown_pattern = re.compile(r"^\s*\d+\.\s+\*\*.*\*\*")
    
    def filter_output(self, text: str) -> str:
        """過濾輸出，移除表情符號和特殊格式"""
        text = self.emoji_pattern.sub("", text)
        text = self.markdown_pattern.sub("", text)
        return text
    
    def __call__(self, input_ids, scores, **kwargs):
        # 獲取最後一個token
        new_token = input_ids[:, -1]
        
        # 解碼token（跳過特殊標記）
        decoded_token = self.tokenizer.decode(new_token, skip_special_tokens=True)
        
        # 過濾token
        filtered_token = self.filter_output(decoded_token)
        
        if filtered_token:
            self.current_sentence += filtered_token
            print(filtered_token, end="", flush=True)  # 即時輸出
            
            # 調用回調函數
            self.callback(filtered_token)
            
            # 當遇到標點符號時，清空當前句子
            if filtered_token in [".", "!", "?", ",", ":", ";", "\n"] and len(self.current_sentence) >= self.min_sentence_length:
                self.current_sentence = ""
        
        # 如果遇到EOS token，停止生成
        if new_token[0].item() == self.eos_token_id:
            return True
        
        # 如果達到最大token數，停止生成
        self.token_count += 1
        return self.token_count >= self.max_new_tokens

class LLMManager:
    """
    語言模型管理器，基於Google Gemma 3模型，支持真正的流式生成
    """
    def __init__(
        self,
        model_dir: Optional[Union[str, Path]] = None,
        model_name: str = "google/gemma-3-1b-it",  # 模型名稱
        device: str = "auto",  # "auto", "cpu", "cuda"
        use_8bit: bool = True,  # 是否使用8位量化
        use_4bit: bool = False,  # 是否使用4位量化
        stream_mode: bool = False,  # 是否啟用串流模式
        temperature: float = 0.7,  # 生成溫度
        top_k: int = 50,  # Top-K採樣
        top_p: float = 0.9,  # Top-P採樣
        repetition_penalty: float = 1.0,  # 重複懲罰
        max_new_tokens: int = 200,  # 最大生成長度
        system_prompt: Optional[str] = None,  # 系統提示
        local_files_only: bool = False,  # 是否只使用本地文件
    ):
        """
        初始化LLM管理器
        
        Args:
            model_dir: 模型目錄，如果為None則使用默認路徑
            model_name: 模型名稱或路徑
            device: 計算設備 ("auto", "cpu", "cuda")
            use_8bit: 是否使用8位量化
            use_4bit: 是否使用4位量化
            stream_mode: 是否啟用串流模式
            temperature: 生成溫度
            top_k: Top-K採樣參數
            top_p: Top-P採樣參數
            repetition_penalty: 重複懲罰參數
            max_new_tokens: 最大生成長度
            system_prompt: 系統提示
            local_files_only: 是否只使用本地文件
        """
        # 初始化模型路徑
        if model_dir is None:
            base_dir = Path(__file__).resolve().parent.parent.parent
            self.model_dir = base_dir / "src" / "models" / "llm_models"
        else:
            self.model_dir = Path(model_dir)
        
        # 如果model_name是相對路徑，轉換為絕對路徑
        if not model_name.startswith("google/") and not os.path.isabs(model_name):
            self.model_path = str(self.model_dir / model_name)
        else:
            self.model_path = model_name
        
        # 設置設備
        if device == "auto":
            self.device = "cuda" if torch.cuda.is_available() else "cpu"
        else:
            self.device = device
        
        # 保存參數
        self.use_8bit = use_8bit
        self.use_4bit = use_4bit
        self.stream_mode = stream_mode
        self.temperature = temperature
        self.top_k = top_k
        self.top_p = top_p
        self.repetition_penalty = repetition_penalty
        self.max_new_tokens = max_new_tokens
        self.system_prompt = system_prompt
        self.local_files_only = local_files_only
        
        # 加載模型和分詞器
        self._load_model()
        
        # 初始化串流模式
        if stream_mode:
            self.llm_queue = queue.Queue()
            self.is_running = True
            self.llm_thread = threading.Thread(target=self._llm_worker, daemon=True)
            self.llm_thread.start()
    
    def _load_model(self) -> None:
        """加載模型和分詞器"""
        try:
            print(f"加載LLM模型: {self.model_path}, 設備: {self.device}")
            
            # 加載分詞器
            self.tokenizer = AutoTokenizer.from_pretrained(
                self.model_path,
                local_files_only=self.local_files_only
            )
            
            # 準備量化配置
            quantization_config = None
            if self.use_8bit:
                quantization_config = BitsAndBytesConfig(load_in_8bit=True)
            elif self.use_4bit:
                quantization_config = BitsAndBytesConfig(
                    load_in_4bit=True,
                    bnb_4bit_quant_type="nf4",
                    bnb_4bit_compute_dtype=torch.bfloat16
                )
            
            # 加載模型
            model_kwargs = {}
            if quantization_config:
                model_kwargs["quantization_config"] = quantization_config
            
            if self.device != "cpu" and torch.cuda.is_available():
                model_kwargs["device_map"] = "auto"
                torch_dtype = torch.bfloat16
            else:
                torch_dtype = torch.float32
            
            # 添加torch_dtype參數
            model_kwargs["torch_dtype"] = torch_dtype
            
            # 加載模型
            self.model = Gemma3ForCausalLM.from_pretrained(
                self.model_path,
                local_files_only=self.local_files_only,
                **model_kwargs
            ).eval()
            
            print("LLM模型加載成功")
            
        except Exception as e:
            import traceback
            print(f"LLM模型加載失敗: {e}")
            traceback.print_exc()
            raise RuntimeError(f"LLM模型加載失敗: {str(e)}")
    
    def _llm_worker(self) -> None:
        """LLM工作線程，處理隊列中的請求"""
        while self.is_running:
            try:
                # 從隊列獲取項目
                item = self.llm_queue.get(timeout=0.5)
                if item is None:
                    break
                
                # 解析項目
                if isinstance(item, tuple) and len(item) >= 2:
                    messages, callback = item[0], item[1]
                    options = item[2] if len(item) > 2 and isinstance(item[2], dict) else {}
                else:
                    messages, callback, options = item, None, {}
                
                # 處理請求
                if callback:
                    # 流式生成
                    self.generate_stream(messages, callback, **options)
                else:
                    # 生成完整響應
                    response = self.generate(messages, **options)
                    # 這裡可以添加響應處理邏輯
                
            except queue.Empty:
                continue
            except Exception as e:
                print(f"LLM處理錯誤: {e}")
                import traceback
                traceback.print_exc()
            finally:
                # 標記任務完成
                if 'item' in locals() and item is not None:
                    self.llm_queue.task_done()
    
    def prepare_messages(
        self, 
        messages: Union[str, List[Dict[str, Any]]],
    ) -> List[Dict[str, Any]]:
        """
        準備消息格式
        
        Args:
            messages: 消息列表或單個字符串消息
            
        Returns:
            格式化的消息列表
        """
        # 如果輸入是字符串，轉換為消息格式
        if isinstance(messages, str):
            # 構建消息列表
            formatted_messages = []
            
            # 添加系統提示（如果有）
            if self.system_prompt:
                formatted_messages.append({
                    "role": "system",
                    "content": [{"type": "text", "text": self.system_prompt}]
                })
            
            # 添加用戶消息
            formatted_messages.append({
                "role": "user",
                "content": [{"type": "text", "text": messages}]
            })
            
            return formatted_messages
        
        # 如果已經是列表格式，確保格式正確
        elif isinstance(messages, list):
            # 檢查是否需要添加系統提示
            has_system = any(msg.get("role") == "system" for msg in messages if isinstance(msg, dict))
            
            # 如果沒有系統提示但有設定系統提示，則添加
            if not has_system and self.system_prompt:
                system_msg = {
                    "role": "system",
                    "content": [{"type": "text", "text": self.system_prompt}]
                }
                messages = [system_msg] + messages
            
            # 標準化消息格式（簡單檢查/修復）
            for i, msg in enumerate(messages):
                if isinstance(msg, dict) and "content" in msg:
                    # 如果content是字符串，轉換為列表格式
                    if isinstance(msg["content"], str):
                        messages[i]["content"] = [{"type": "text", "text": msg["content"]}]
            
            return messages
        
        else:
            raise ValueError(f"不支持的消息格式: {type(messages)}")
    
    def generate(
        self,
        messages: Union[str, List[Dict[str, Any]]],
        temperature: Optional[float] = None,
        top_k: Optional[int] = None,
        top_p: Optional[float] = None,
        repetition_penalty: Optional[float] = None,
        max_new_tokens: Optional[int] = None,
    ) -> str:
        """
        生成文本響應
        
        Args:
            messages: 消息列表或單個字符串消息
            temperature: 生成溫度
            top_k: Top-K採樣參數
            top_p: Top-P採樣參數
            repetition_penalty: 重複懲罰參數
            max_new_tokens: 最大生成長度
            
        Returns:
            生成的響應文本
        """
        # 使用默認值
        temperature = temperature if temperature is not None else self.temperature
        top_k = top_k if top_k is not None else self.top_k
        top_p = top_p if top_p is not None else self.top_p
        repetition_penalty = repetition_penalty if repetition_penalty is not None else self.repetition_penalty
        max_new_tokens = max_new_tokens if max_new_tokens is not None else self.max_new_tokens
        
        # 準備消息
        formatted_messages = self.prepare_messages(messages)
        
        try:
            # 使用chat_template處理輸入
            inputs = self.tokenizer.apply_chat_template(
                formatted_messages,
                add_generation_prompt=True,
                tokenize=True,
                return_dict=True,
                return_tensors="pt"
            ).to(self.model.device)
            
            # 記錄輸入長度
            input_length = inputs["input_ids"].shape[-1]
            
            # 生成
            with torch.inference_mode():
                outputs = self.model.generate(
                    **inputs,
                    max_new_tokens=max_new_tokens,
                    do_sample=temperature > 0,
                    temperature=temperature,
                    top_k=top_k,
                    top_p=top_p,
                    repetition_penalty=repetition_penalty,
                    use_cache=True,
                    pad_token_id=self.tokenizer.eos_token_id
                )
                
                # 只保留新生成的部分
                generated_tokens = outputs[0][input_length:]
                generated_text = self.tokenizer.decode(generated_tokens, skip_special_tokens=True)
                
                return generated_text
                
        except Exception as e:
            import traceback
            print(f"生成錯誤: {e}")
            traceback.print_exc()
            return f"生成過程中發生錯誤: {str(e)}"
    
    def generate_stream(
        self,
        messages: Union[str, List[Dict[str, Any]]],
        callback: Callable[[str], None],
        temperature: Optional[float] = None,
        top_k: Optional[int] = None,
        top_p: Optional[float] = None,
        repetition_penalty: Optional[float] = None,
        max_new_tokens: Optional[int] = None,
        min_sentence_length: int = 8,
    ) -> None:
        """
        流式生成文本響應 - 真正的逐token生成並通過回調返回
        
        Args:
            messages: 消息列表或單個字符串消息
            callback: 回調函數，接收生成的文本片段
            temperature: 生成溫度
            top_k: Top-K採樣參數
            top_p: Top-P採樣參數
            repetition_penalty: 重複懲罰參數
            max_new_tokens: 最大生成長度
            min_sentence_length: 最小的句子長度
        """
        # 使用默認值
        temperature = temperature if temperature is not None else self.temperature
        top_k = top_k if top_k is not None else self.top_k
        top_p = top_p if top_p is not None else self.top_p
        repetition_penalty = repetition_penalty if repetition_penalty is not None else self.repetition_penalty
        max_new_tokens = max_new_tokens if max_new_tokens is not None else self.max_new_tokens
        
        # 準備消息
        formatted_messages = self.prepare_messages(messages)
        
        try:
            # 使用chat_template處理輸入
            inputs = self.tokenizer.apply_chat_template(
                formatted_messages,
                add_generation_prompt=True,
                tokenize=True,
                return_dict=True,
                return_tensors="pt"
            ).to(self.model.device)
            
            # 創建自定義停止條件，實現逐token流式輸出
            streaming_criteria = StreamingStoppingCriteria(
                tokenizer=self.tokenizer,
                callback=callback,
                eos_token_id=self.tokenizer.eos_token_id,
                max_new_tokens=max_new_tokens,
                min_sentence_length=min_sentence_length
            )
            
            # 使用自定義停止條件進行生成
            with torch.inference_mode():
                self.model.generate(
                    **inputs,
                    max_new_tokens=max_new_tokens,
                    do_sample=temperature > 0,
                    temperature=temperature,
                    top_k=top_k,
                    top_p=top_p,
                    repetition_penalty=repetition_penalty,
                    use_cache=True,
                    pad_token_id=self.tokenizer.eos_token_id,
                    stopping_criteria=StoppingCriteriaList([streaming_criteria])
                )
                
        except Exception as e:
            import traceback
            print(f"流式生成錯誤: {e}")
            traceback.print_exc()
            callback(f"生成過程中發生錯誤: {str(e)}")
    
    def stream_request(
        self, 
        messages: Union[str, List[Dict[str, Any]]],
        callback: Callable[[str], None],
        **options
    ) -> None:
        """
        將LLM請求加入串流處理隊列
        
        Args:
            messages: 消息列表或單個字符串消息
            callback: 回調函數，接收生成的文本片段
            **options: 生成選項
        """
        if not self.stream_mode:
            raise RuntimeError("必須在串流模式下使用stream_request方法")
        
        # 添加到處理隊列
        self.llm_queue.put((messages, callback, options))
    
    def wait_until_done(self) -> None:
        """等待所有隊列中的項目處理完成"""
        if self.stream_mode:
            self.llm_queue.join()
    
    def shutdown(self) -> None:
        """關閉LLM管理器"""
        if self.stream_mode and self.is_running:
            self.is_running = False
            self.llm_queue.put(None)  # 發送結束信號
            if hasattr(self, 'llm_thread') and self.llm_thread.is_alive():
                self.llm_thread.join(timeout=2.0)
    
    def clear_memory(self) -> None:
        """清除GPU內存"""
        if hasattr(self, 'model') and self.device == "cuda":
            del self.model
            torch.cuda.empty_cache()
            print("已清除GPU內存")
    
    def __del__(self):
        """析構函數"""
        self.shutdown()
        self.clear_memory()

# 默認的英語教師系統提示
DEFAULT_ENGLISH_TEACHER_PROMPT = """You are a friendly and casual English teacher. Respond naturally and conversationally, like a native speaker talking to a student. Keep responses simple, natural, and easy to understand."""

# 測試代碼
if __name__ == "__main__":
    # 基本用法
    llm = LLMManager(
        system_prompt=DEFAULT_ENGLISH_TEACHER_PROMPT,
        local_files_only=True  # 測試時使用本地文件
    )
    
    # 測試簡單對話
    print("\n=== 測試1: 標準生成 ===")
    response = llm.generate("I'm trying to practice my english speaking skills. Could you help me?")
    print(f"LLM回應: {response}")
    
    # 測試流式生成
    print("\n=== 測試2: 流式生成 ===")
    print("問題: Tell me the difference between 'affect' and 'effect'?")
    print("回答: ", end="", flush=True)
    
    # 收集生成的文本
    collected_text = []
    
    def collect_text(text):
        collected_text.append(text)
    
    # 使用流式生成
    llm.generate_stream("Tell me the difference between 'affect' and 'effect'?", collect_text)
    
    print("\n\n完整回應: " + "".join(collected_text))