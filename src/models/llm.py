import os
import time
import threading
import queue
import re
import torch
from pathlib import Path
from typing import Optional, Union, List, Dict, Any, Callable, Generator
from transformers import BitsAndBytesConfig

class LLMManager:
    """
    語言模型管理器，基於Google Gemma 3模型，支持真正的流式生成
    """
    def __init__(
        self,
        model_dir: Optional[Union[str, Path]] = None,
        model_name: str = "google/gemma-3-1b-it",  # 模型名稱
        model_type: str = "1b",  # 模型類型: "1b" 或 "4b"
        device: str = "auto",  # "auto", "cpu", "cuda"
        use_8bit: bool = True,  # 是否使用8位量化
        use_4bit: bool = False,  # 是否使用4位量化
        stream_mode: bool = False,  # 是否啟用串流模式
        temperature: float = 0.8,  # 生成溫度
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
            base_dir = Path(__file__).resolve().parent
            self.model_dir = base_dir / "model_data" / "llm_models"
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
        self.model_type = model_type.lower()
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
    
    # def _load_model(self) -> None:
    #     """加載模型和分詞器"""
    #     try:
    #         print(f"加載LLM模型: {self.model_path}, 設備: {self.device}")
            
    #         # 加載分詞器
    #         self.tokenizer = AutoTokenizer.from_pretrained(
    #             self.model_path,
    #             local_files_only=self.local_files_only
    #         )
            
    #         # 準備量化配置
    #         quantization_config = None
    #         if self.use_8bit:
    #             quantization_config = BitsAndBytesConfig(load_in_8bit=True)
    #         elif self.use_4bit:
    #             quantization_config = BitsAndBytesConfig(
    #                 load_in_4bit=True,
    #                 bnb_4bit_quant_type="nf4",
    #                 bnb_4bit_compute_dtype=torch.bfloat16
    #             )
            
    #         # 加載模型
    #         model_kwargs = {}
    #         if quantization_config:
    #             model_kwargs["quantization_config"] = quantization_config
            
    #         if self.device != "cpu" and torch.cuda.is_available():
    #             model_kwargs["device_map"] = "auto"
    #             torch_dtype = torch.bfloat16
    #         else:
    #             torch_dtype = torch.float32
            
    #         # 添加torch_dtype參數
    #         model_kwargs["torch_dtype"] = torch_dtype
            
    #         # 加載模型
    #         self.model = Gemma3ForCausalLM.from_pretrained(
    #             self.model_path,
    #             local_files_only=self.local_files_only,
    #             **model_kwargs
    #         ).eval()
            
    #         print("LLM模型加載成功")
            
    #     except Exception as e:
    #         import traceback
    #         print(f"LLM模型加載失敗: {e}")
    #         traceback.print_exc()
    #         raise RuntimeError(f"LLM模型加載失敗: {str(e)}")

    def _load_model(self) -> None:
        """根據模型類型加載相應的模型和分詞器/處理器"""
        try:
            print(f"加載LLM模型: {self.model_path}, 類型: {self.model_type}, 設備: {self.device}")
            
            # 根據模型類型加載不同的組件
            if self.model_type == "4b":
                # 4B模型使用AutoProcessor和Gemma3ForConditionalGeneration
                from transformers import AutoProcessor, Gemma3ForConditionalGeneration
                
                self.processor = AutoProcessor.from_pretrained(
                    self.model_path,
                    local_files_only=self.local_files_only
                )
                self.tokenizer = self.processor  # 為了兼容性，保留tokenizer引用
                
                # 準備模型參數
                model_kwargs = {}
                if self.device != "cpu" and torch.cuda.is_available():
                    model_kwargs["device_map"] = "auto"
                    model_kwargs["torch_dtype"] = torch.bfloat16
                
                self.model = Gemma3ForConditionalGeneration.from_pretrained(
                    self.model_path,
                    local_files_only=self.local_files_only,
                    **model_kwargs
                ).eval()
            else:
                # 1B模型使用AutoTokenizer和Gemma3ForCausalLM
                from transformers import AutoTokenizer, Gemma3ForCausalLM
                
                self.tokenizer = AutoTokenizer.from_pretrained(
                    self.model_path,
                    local_files_only=self.local_files_only
                )
                self.processor = self.tokenizer  # 為了兼容性，保留processor引用
                
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
                
                # 準備模型參數
                model_kwargs = {}
                if quantization_config:
                    model_kwargs["quantization_config"] = quantization_config
                
                if self.device != "cpu" and torch.cuda.is_available():
                    model_kwargs["device_map"] = "auto"
                    model_kwargs["torch_dtype"] = torch.bfloat16
                else:
                    model_kwargs["torch_dtype"] = torch.float32
                
                self.model = Gemma3ForCausalLM.from_pretrained(
                    self.model_path,
                    local_files_only=self.local_files_only,
                    **model_kwargs
                ).eval()
            
            print(f"{self.model_type.upper()} LLM模型加載成功")

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
    
    def _filter_text(self, text: str) -> str:
        """過濾文本，移除emoji和特殊格式"""
        # 過濾emoji
        emoji_pattern = re.compile("[\U0001F600-\U0001F64F\U0001F300-\U0001F5FF\U0001F680-\U0001F6FF\U0001F700-\U0001F77F]+", flags=re.UNICODE)
        text = emoji_pattern.sub("", text)
        
        # 過濾markdown格式
        markdown_pattern = re.compile(r"^\s*\d+\.\s+\*\*.*\*\*")
        text = markdown_pattern.sub("", text)
        
        # 過濾Markdown強調標記（保留文本內容）
        text = re.sub(r'\*\*(.*?)\*\*', r'\1', text)  # 移除粗體標記 **text**
        text = re.sub(r'\*(.*?)\*', r'\1', text)      # 移除斜體標記 *text*
        
        return text
    
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
                    use_cache=True
                )
                
                # 只保留新生成的部分
                generated_tokens = outputs[0][input_length:]
                generated_text = self.tokenizer.decode(generated_tokens, skip_special_tokens=True)
                
                # 清理輸出
                generated_text = self._clean_output(generated_text)
                
                return generated_text
                
        except Exception as e:
            import traceback
            print(f"生成錯誤: {e}")
            traceback.print_exc()
            return f"生成過程中發生錯誤: {str(e)}"
    
    def _clean_output(self, text: str) -> str:
        """清理輸出，移除特殊標記和URL"""
        # 移除特殊標記
        text = re.sub(r'<[^>]*>', '', text)
        
        # 移除URL
        text = re.sub(r'https?://\S+', '', text)
        
        # 移除星號標記（保留文本內容）
        text = re.sub(r'\*\*?(.*?)\*\*?', r'\1', text)
        
        # 移除其他可能的特殊標記
        text = re.sub(r'\[\d+\]', '', text)  # 引用標記
        
        # 清理多餘空格
        text = re.sub(r'\s+', ' ', text).strip()
        
        return text
    
    def generate_stream(
        self,
        messages: Union[str, List[Dict[str, Any]]],
        callback: Optional[Callable[[str], None]] = None,
        temperature: Optional[float] = None,
        top_k: Optional[int] = None,
        top_p: Optional[float] = None,
        repetition_penalty: Optional[float] = None,
        max_new_tokens: Optional[int] = None,
        min_sentence_length: int = 8,
    ) -> Generator[str, None, None]:
        """流式生成文本響應 - 支持1B和4B模型"""
        # 記錄開始時間和性能指標
        start_time = time.time()
        token_counter = 0
        self.newline_counter = 0  # 初始化換行符計數器
        
        # 使用默認值
        temperature = temperature if temperature is not None else self.temperature
        top_k = top_k if top_k is not None else self.top_k
        top_p = top_p if top_p is not None else self.top_p
        repetition_penalty = repetition_penalty if repetition_penalty is not None else self.repetition_penalty
        max_new_tokens = max_new_tokens if max_new_tokens is not None else self.max_new_tokens
        
        # 準備消息
        formatted_messages = self.prepare_messages(messages)
        
        try:
            # 記錄初始GPU內存使用
            initial_gpu_memory = 0
            if torch.cuda.is_available():
                torch.cuda.empty_cache()  # 清理緩存
                initial_gpu_memory = torch.cuda.memory_allocated() / (1024 ** 2)  # MB
                print(f"初始GPU內存使用: {initial_gpu_memory:.2f} MB")
            
            # 記錄輸入消息長度
            msg_str = str(formatted_messages)
            input_msg_length = len(msg_str)
            print(f"輸入消息長度: {input_msg_length} 字符")
            
            # 根據模型類型使用不同的處理方法
            if self.model_type == "4b":
                # 4B模型處理
                inputs = self.processor.apply_chat_template(
                    formatted_messages,
                    add_generation_prompt=True,
                    tokenize=True,
                    return_dict=True,
                    return_tensors="pt"
                ).to(self.model.device, dtype=torch.bfloat16)
            else:
                # 1B模型處理
                inputs = self.tokenizer.apply_chat_template(
                    formatted_messages,
                    add_generation_prompt=True,
                    tokenize=True,
                    return_dict=True,
                    return_tensors="pt"
                ).to(self.model.device)
            
            # 記錄輸入token數
            input_tokens = inputs["input_ids"].shape[-1]
            print(f"輸入token數: {input_tokens}")
            
            # 記錄模板處理後的GPU內存
            if torch.cuda.is_available():
                template_gpu_memory = torch.cuda.memory_allocated() / (1024 ** 2)
                print(f"處理模板後GPU內存: {template_gpu_memory:.2f} MB (增加 {template_gpu_memory-initial_gpu_memory:.2f} MB)")
            
            # 創建句子緩衝區和累積文本
            empty_token_count = 0

            should_stop = False  # 標記是否應該停止生成
            
            # 使用inference_mode生成
            with torch.inference_mode():
                # 為了獲取每個token，我們使用更低層次的接口
                input_ids = inputs["input_ids"]
                
                # 開始生成
                for i in range(max_new_tokens):
                    if should_stop:
                        break
                    
                    # 每生成10個token記錄一次時間，用於監控生成速度趨勢
                    if i > 0 and i % 10 == 0:
                        current_time = time.time()
                        elapsed = current_time - start_time
                        tokens_per_second = i / elapsed if elapsed > 0 else 0
                        print(f"已生成 {i} tokens，當前速度: {tokens_per_second:.2f} tokens/秒")
                        
                    # 獲取logits
                    outputs = self.model(input_ids)
                    next_token_logits = outputs.logits[:, -1, :]
                    
                    # 應用採樣參數選擇下一個token
                    next_token = self._sample_token(next_token_logits, temperature, top_k, top_p, repetition_penalty, input_ids)
                    
                    # 如果是EOS token，結束生成
                    # if next_token == self.tokenizer.eos_token_id:
                    #     break
                    
                    # 添加到輸入序列
                    input_ids = torch.cat([input_ids, torch.tensor([[next_token]], device=self.device)], dim=1)
                    
                    # 根據模型類型解碼token
                    if self.model_type == "4b":
                        token_text = self.processor.decode([next_token], skip_special_tokens=True)
                    else:
                        token_text = self.tokenizer.decode([next_token], skip_special_tokens=True)
                    
                    # 過濾token
                    filtered_token = token_text
                    
                    # 計數連續換行符
                    if filtered_token == "\n" or filtered_token == "\\n":
                        self.newline_counter += 1
                        print(f"檢測到換行符: {self.newline_counter}")
                        # 如果連續換行符超過5個，提前終止
                        if self.newline_counter >= 5:
                            print(f"\n[提前終止] 檢測到連續{self.newline_counter}個換行符")
                            should_stop = True
                            break
                    else:
                        self.newline_counter = 0  # 重置計數器
                    
                    if filtered_token: 
                        empty_token_count = 0
                        token_counter += 1  # 累計實際生成的token數
                    else:
                        empty_token_count += 1
                        # 如果連續空token數量超過限制，提前終止
                        if empty_token_count >= 5:
                            print(f"\n[提前終止] 檢測到連續{empty_token_count}個空token")
                            should_stop = True
                            break
                    
                    # 跳過空token
                    if not filtered_token:
                        continue
                
                    if callback:
                        callback(filtered_token)
                    yield filtered_token
                    
            # 記錄結束時間和計算性能指標
            end_time = time.time()
            total_time = end_time - start_time
            
            # 輸出性能報告
            print("\n========== LLM生成性能報告 ==========")
            print(f"總生成時間: {total_time:.2f} 秒")
            print(f"輸入token數: {input_tokens}")
            print(f"輸出token數: {token_counter}")
            if total_time > 0:
                print(f"生成速度: {token_counter / total_time:.2f} tokens/秒")
            
            # 顯示GPU內存使用情況
            if torch.cuda.is_available():
                final_gpu_memory = torch.cuda.memory_allocated() / (1024 ** 2)
                print(f"GPU內存使用: {final_gpu_memory:.2f} MB")
                print(f"GPU內存增加: {final_gpu_memory - initial_gpu_memory:.2f} MB")
                print(f"GPU缓存总量: {torch.cuda.memory_reserved() / (1024 ** 2):.2f} MB")
            
            # 如果花費時間超過一定閾值，給出警告
            if total_time > 5 and token_counter < 50:
                print(f"警告: 生成速度較慢! 可能需要考慮縮短對話上下文或優化處理流程。")
            
            print("======================================")
                    
        except Exception as e:
            # 記錄錯誤時的時間，以計算總時間
            end_time = time.time()
            total_time = end_time - start_time
            print(f"\n[錯誤] 生成在 {total_time:.2f} 秒後失敗")
            
            import traceback
            print(f"流式生成錯誤: {e}")
            traceback.print_exc()
            if callback:
                callback(f"生成過程中發生錯誤: {str(e)}")
            yield f"生成過程中發生錯誤: {str(e)}"
            
    def _sample_token(self, logits, temperature, top_k, top_p, repetition_penalty, input_ids):
        """令牌採樣邏輯，抽取為單獨方法以提高可讀性"""
        if temperature > 0:
            # 添加溫度縮放
            logits = logits / temperature
            
            # 應用Top-K過濾
            if top_k > 0:
                indices_to_remove = torch.topk(logits, k=top_k)[0][:, -1, None]
                logits[logits < indices_to_remove] = float('-inf')
            
            # 應用Top-P過濾
            if 0 < top_p < 1.0:
                sorted_logits, sorted_indices = torch.sort(logits, descending=True)
                cumulative_probs = torch.cumsum(torch.softmax(sorted_logits, dim=-1), dim=-1)
                
                sorted_indices_to_remove = cumulative_probs > top_p
                sorted_indices_to_remove[..., 1:] = sorted_indices_to_remove[..., :-1].clone()
                sorted_indices_to_remove[..., 0] = 0
                
                indices_to_remove = sorted_indices[sorted_indices_to_remove]
                logits[0, indices_to_remove] = float('-inf')
            
            # 應用重複懲罰
            if repetition_penalty > 1.0:
                for i in range(input_ids.shape[1]):
                    logits[0, input_ids[0, i]] /= repetition_penalty
            
            # 採樣下一個token
            probs = torch.softmax(logits, dim=-1)
            next_token = torch.multinomial(probs, num_samples=1).item()
        else:   
            # 貪婪解碼
            next_token = torch.argmax(logits, dim=-1).item()
        
        return next_token

    # def _is_sentence_complete(self, token, buffer, min_length):
    #     """檢查是否完成一個句子"""
    #     return (any(mark in token for mark in [".", "!", "?"]) and len(buffer) >= min_length) or \
    #         (any(mark in token for mark in [",", ";", ":"]) and len(buffer) >= min_length)

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
DEFAULT_ENGLISH_TEACHER_PROMPT = """You are a friendly and casual English teacher. Respond naturally and conversationally, 
like a native speaker talking to a student. Keep responses simple, clear, and concise (around 2-3 sentences per answer).
Avoid using bullet points or numbered lists. Make your answers brief but helpful."""

# 測試代碼
if __name__ == "__main__":
    # 基本用法
    llm = LLMManager(
        system_prompt=DEFAULT_ENGLISH_TEACHER_PROMPT,
        local_files_only=True,  # 測試時使用本地文件
        temperature=0.4,        # 降低溫度提高穩定性
        top_k=30,               # 限制詞彙選擇範圍
        top_p=0.7               # 適中的採樣概率
    )
    
    # 測試簡單對話
    print("\n=== 測試1: 標準生成 ===")
    response = llm.generate("I'm trying to practice my english speaking skills. Could you help me?")
    print(f"LLM回應: {response}")
    
    # 測試流式生成
    print("\n=== 測試2: 流式生成 ===")
    print("問題: How can I improve my English reading skills?")
    print("回答: ", end="", flush=True)
    
    # 收集生成的文本
    collected_text = []
    
    def collect_text(text):
        collected_text.append(text)
    
    # 使用流式生成
    for text_chunk in llm.generate_stream("How can I improve my English reading skills?", collect_text):
        # 直接傳遞給TTS處理（實際應用中）
        pass
    
    print("\n\n完整回應: " + "".join(collected_text))