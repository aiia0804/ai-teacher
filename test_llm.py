import os
#4b
from transformers import AutoProcessor, Gemma3ForConditionalGeneration, StoppingCriteria, StoppingCriteriaList
#1b
from transformers import AutoTokenizer, BitsAndBytesConfig, Gemma3ForCausalLM
from pathlib import Path
import torch
import threading
import sounddevice as sd
import soundfile as sf
from kokoro import KPipeline  # 你的 TTS 模型
import numpy as np
import soundfile as sf
import tempfile
import time
import queue
import torchaudio



BASE_DIR = Path(__file__).resolve().parent
MODEL_DIR = BASE_DIR / "src" / "models" / "llm_models" / "gemma-3-1b-it"

model_name = "google/gemma-3-1b-it"
model_path = str(MODEL_DIR)  # 自訂本地儲存位置
torch.cuda.empty_cache()  # 清除 CUDA 緩存

# # **第一次執行時下載並存放**
# tokenizer = AutoTokenizer.from_pretrained(model_path,  local_files_only=True)
# model = AutoModelForCausalLM.from_pretrained(
#     model_path, 
#     local_files_only=True,
#     device_map="auto",  # 自動選擇 GPU 或 CPU
#     torch_dtype=torch.float16  # 使用 FP16 來節省 VRAM
# )

# 測試對話訊息
messages = [
    {
        "role": "system",
        "content": [{"type": "text", "text": "You are a friendly and casual English teacher. Respond naturally and conversationally, like a native speaker talking to a student. Keep responses simple, natural, and easy to understand."}]
    },
    {
        "role": "user",
        "content": [
            {"type": "text", "text": "I'm trying to practice my english speaking skills. Could you help me?"}
        ]
    }
]

# 🔥 加載 LLM（Gemma 3 4B）
#processor = AutoProcessor.from_pretrained(model_path, local_files_only=True)
# model = Gemma3ForConditionalGeneration.from_pretrained(
#     model_path, local_files_only=True, torch_dtype=torch.bfloat16
# ).to("cuda").eval()

quantization_config = BitsAndBytesConfig(load_in_8bit=True)
# 🔥 加載 LLM（Gemma 3 1B）
model = Gemma3ForCausalLM.from_pretrained(
    model_path, quantization_config=quantization_config
).eval()
tokenizer = AutoTokenizer.from_pretrained(model_path)


# 🔥 加載 TTS（Kokoro）
TTS_MODEL_DIR = BASE_DIR / "src" / "models" / "tts_models"
pipeline = KPipeline(lang_code='a')
voice_path = os.path.join(TTS_MODEL_DIR, "voices/af_heart.pt")
voice_tensor = torch.load(voice_path, weights_only=True)

# 處理輸入 4B
# inputs = processor.apply_chat_template(
#     messages, add_generation_prompt=True, tokenize=True,
#     return_dict=True, return_tensors="pt"
# ).to(model.device, dtype=torch.bfloat16 )

# # 計算輸入長度（確保輸出時不包含輸入內容）
# input_len = inputs["input_ids"].shape[-1]

# 處理輸入 1B
inputs = tokenizer.apply_chat_template(
    messages,
    add_generation_prompt=True,
    tokenize=True,
    return_dict=True,
    return_tensors="pt",
).to(model.device).to(torch.bfloat16)

start_time = time.time()

# 推理
# with torch.inference_mode():
#     generation = model.generate(
#         **inputs,
#         max_new_tokens=100,  # ✅ 降低輸出長度，加快推理
#         temperature=0.7,  # ✅ 增加隨機性
#         top_k=50,  # ✅ 降低計算開銷
#         top_p=0.9,  # ✅ 採樣機制
#         do_sample=True,  # ✅ 啟用隨機抽樣
#         use_cache=True,  # ✅ 啟用 cache，加速 token 生成
#         stream=True
#     )
#     generation = generation[0][input_len:]  # 只保留新生成的部分


# 🚀 **使用 StoppingCriteria 來實現逐步輸出**
# class StreamStoppingCriteria(StoppingCriteria):
#     def __init__(self, max_new_tokens):
#         self.max_new_tokens = max_new_tokens
#         self.token_count = 0

#     def __call__(self, input_ids, scores, **kwargs):
#         new_token = input_ids[:, -1]
#         print(processor.decode(new_token, skip_special_tokens=True), end="", flush=True)
#         self.token_count += 1
#         return self.token_count >= self.max_new_tokens

# # 🚀 **讓 `generate()` 逐步輸出**
# with torch.inference_mode():
#     model.generate(
#         **inputs,
#         max_new_tokens=100,  # ✅ 設定最大輸出長度
#         temperature=0.7,  
#         top_k=50,  
#         top_p=0.9,  
#         do_sample=True,  
#         use_cache=True,  
#         stopping_criteria=StoppingCriteriaList([StreamStoppingCriteria(100)])  # 🚀 逐步輸出 Token
#     )

# 🚀 **TTS 逐個字發音**
# def play_tts(text):
#     global voice_tensor
#     if text.strip() == "":
#         return

#     try:
#         generator = pipeline(text, voice=voice_tensor, speed=1.0)
#         all_audio = []
#         for _, _, audio in generator:
#             all_audio.append(audio)

#         if all_audio:
#             full_audio = np.concatenate(all_audio)

#             # ✅ 直接播放音頻（不存檔案）
#             sd.play(full_audio, samplerate=24000)
#             sd.wait()  # ✅ 確保播放完畢

#     except Exception as e:
#         print(f"\nTTS 錯誤: {e}")
# 🚀 **TTS 讀取並播放音頻（確保排隊播放）**

# def remove_silence(audio, sr=24000):
#     """
#     使用 torchaudio 的 VAD (Voice Activity Detection) 來去除音頻靜音部分
#     """
#     # 轉換成 torch tensor，確保格式正確
#     audio_tensor = torch.tensor(audio, dtype=torch.float32)

#     # ✅ 使用 torchaudio.transforms.Vad() 去除靜音
#     vad = torchaudio.transforms.Vad(sample_rate=sr)

#     # **處理音頻，每次只保留有語音的部分**
#     trimmed_audio = vad(audio_tensor)

#     # 如果去除後沒有聲音，則返回原始音頻，避免過度刪除
#     return trimmed_audio.numpy() if len(trimmed_audio) > 0 else audio

tts_queue = queue.Queue()
sentence_array = []
def tts_worker():
    while True:
        sentence = tts_queue.get()  # 取出排隊的句子
        if sentence is None:
            break  # 如果是 `None`，代表結束

        try:
            #print(f"=====TTS sentense< {sentence} >======")
            sentence_array.append(sentence)
            generator = pipeline(sentence, voice=voice_tensor, speed=1.25)
            all_audio = []
            for _, _, audio in generator:
                all_audio.append(audio)

            if all_audio:
                full_audio = np.concatenate(all_audio)

                # ✅ 播放音頻（確保不被覆蓋）
                sd.play(full_audio, samplerate=24000)
                sd.wait()  # ✅ **等待播放完畢**

        except Exception as e:
            print(f"\nTTS 錯誤: {e}")

import re

# 🚀 **讓 LLM 逐字輸出，同時傳給 TTS**
class StreamStoppingCriteria(StoppingCriteria):
    def __init__(self, eos_token_id, max_new_tokens, min_sentence_length=40):
        self.max_new_tokens = max_new_tokens
        self.token_count = 0
        self.current_sentence = ""
        self.min_sentence_length = min_sentence_length  # ✅ **至少 8 個 token 才發送 TTS**
        self.eos_token_id = eos_token_id
        #self.valid_chars_pattern = re.compile(r"[A-Za-z0-9.,!?]")  # ✅ **正則表達式，過濾特殊符號**

        # 🚀 **Emoji & Markdown 過濾**
        self.emoji_pattern = re.compile("[\U0001F600-\U0001F64F\U0001F300-\U0001F5FF\U0001F680-\U0001F6FF\U0001F700-\U0001F77F]+", flags=re.UNICODE)
        self.markdown_pattern = re.compile(r"^\s*\d+\.\s+\*\*.*\*\*")  # 例如 "1. **Just chat:**"
        self.extra_spaces_pattern = re.compile(r"(?<!\s)([.,!?])")  # **確保標點符號前有空格**


    def filter_output(self, text):
        #"""過濾 emoji 和 markdown 風格的輸出"""
        text = self.emoji_pattern.sub("", text)  # 移除 emoji
        text = self.markdown_pattern.sub("", text)  # 移除 markdown 樣式
        #text = self.extra_spaces_pattern.sub(r" \1", text)  # 確保標點符號前有空格
        return text

    def __call__(self, input_ids, scores, **kwargs):
        new_token = input_ids[:, -1]
        #decoded_text = processor.decode(new_token, skip_special_tokens=True) 4B    
        decoded_text = tokenizer.decode(new_token, skip_special_tokens=True)

        # ✅ **過濾掉 emoji & markdown**
        filtered_text = self.filter_output(decoded_text)

        if filtered_text:
            self.current_sentence += filtered_text
            #print(filtered_text, end="", flush=True)  # ✅ **即時輸出**

        # ✅ 當遇到標點符號時，送給 TTS
        if filtered_text in [".", "!", "?", ","] and len(self.current_sentence) >= self.min_sentence_length:
            sentence = "".join(self.current_sentence).strip()
            self.current_sentence = []  # 清空目前累積的句子
            tts_queue.put(sentence)  # ✅ **將句子加入 TTS 佇列**
            print(sentence)

        # ✅ **如果遇到 `eos_token_id`，停止生成**
        if new_token == self.eos_token_id:
            return True  # 停止生成
            
        self.token_count += 1
        return self.token_count >= self.max_new_tokens


# 解碼並輸出結果
# decoded = processor.decode(generation, skip_special_tokens=True)
# ✅ **啟動 TTS 播放執行緒**
tts_thread = threading.Thread(target=tts_worker, daemon=True)
tts_thread.start()

# 🚀 **讓 LLM 逐步輸出並同步 TTS** 4B
# print("生成結果：", end="", flush=True)
# with torch.inference_mode():
#     model.generate(
#         **inputs,
#         max_new_tokens=200,  
#         temperature=0.7,  
#         top_k=50,  
#         top_p=0.9,  
#         do_sample=True,  
#         use_cache=True,  
#         stopping_criteria=StoppingCriteriaList([StreamStoppingCriteria(200)])  # 🚀 逐步輸出 Token
#     )



# 🚀 **讓 LLM 逐步輸出並同步 TTS** 1B


print("生成結果：", end="", flush=True)

with torch.inference_mode():
    outputs = model.generate(
        **inputs,
        max_new_tokens=70,  
        temperature=0.7,  
        top_k=50,  
        top_p=0.9,  
        do_sample=True,  
        use_cache=True,  
        stopping_criteria=StoppingCriteriaList([StreamStoppingCriteria(model.config.eos_token_id,60)])  # 🚀 逐步輸出 Token
    )


end_time = time.time()
elapsed_time = end_time - start_time
print(f"TEXT生成花費時間: {elapsed_time:.2f} 秒")

# ✅ **等待所有 TTS 播放完成**
tts_queue.put(None)  # 讓 TTS 執行緒結束
tts_thread.join()

print("TTS SENTENCE: ")
print(sentence_array)

# print(decoded)