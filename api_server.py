from fastapi import FastAPI, UploadFile, File, Form, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, FileResponse
from fastapi.staticfiles import StaticFiles
import uvicorn
import asyncio
from typing import List, Optional, Dict, Any
import tempfile
import os
from pydantic import BaseModel
import base64
import logging
import sys
import json
from pathlib import Path
import time
import soundfile as sf
import queue
from starlette.responses import Response
import numpy as np

# 配置日誌
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("api_server.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("api_server")

# 導入模型管理器
BASE_DIR = Path(__file__).resolve().parent
sys.path.append(str(BASE_DIR))

from src.models.stt import STTManager
from src.models.llm import LLMManager
from src.models.tts import TTSManager

app = FastAPI(title="英語對話AI教師API")

# 允許CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 允許所有來源，生產環境中應該限制
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ------------ 模型定義 ------------ #
class AudioToTextRequest(BaseModel):
    audio_base64: str
    language: Optional[str] = "en"

class TextToSpeechRequest(BaseModel):
    text: str
    voice: Optional[str] = "af_heart.pt"
    speed: Optional[float] = 1.0

class ChatRequest(BaseModel):
    message: str
    conversation_id: Optional[str] = None
    context: Optional[List[Dict[str, Any]]] = None
    scenario: Optional[str] = None

class PronunciationRequest(BaseModel):
    audio_base64: str
    text: str

# ------------ 模型初始化 ------------ #
# 全局變量
# 模型管理器
stt_manager = None
llm_manager = None
tts_manager = None

# 創建持久化音頻緩衝區，用於存儲生成的音頻數據
persistent_audio_buffer = queue.Queue(maxsize=20)  # 最多存儲20個音頻片段

# 對話歷史記錄
conversation_history = {}

# 情境提示詞模板
SCENARIOS = {
    "general": """You are a friendly and casual English teacher. Respond naturally and conversationally, 
like a native speaker talking to a student. Keep responses simple, clear, and concise (around 2-3 sentences per answer).
Avoid using bullet points or numbered lists. Make your answers brief but helpful."""
    # "restaurant": "You are an English teacher helping a student practice ordering food in a restaurant. Act as a waiter and help them with restaurant vocabulary and phrases. Keep responses simple and natural.",
    # "shopping": "You are an English teacher helping a student practice shopping conversations. Act as a shop assistant and help them with shopping vocabulary and expressions. Keep responses simple and natural.",
    # "travel": "You are an English teacher helping a student practice travel-related conversations. Act as a helpful local or travel agent and teach them useful travel phrases. Keep responses simple and natural."
}

# ------------ API路由 ------------ #

@app.get('/api/tts-stream')
async def tts_stream():
    """
    TTS 流式傳輸端點
    """
    async def generate():
        print("客戶端已連接到TTS流")
        
        # 獲取TTS管理器實例
        global tts_manager
        
        # 確保 TTS 管理器已初始化
        if tts_manager is None:
            print("警告: TTS管理器尚未初始化")
            yield "event: error\ndata: {\"error\": \"TTS manager not initialized\"}\n\n"
            return
        
        # 發送事件流頭部
        yield "event: connected\ndata: {\"status\": \"connected\"}\n\n"
        
        # 記錄已發送的音頻片段數
        sent_audio_count = 0
        last_audio_time = time.time()
        
        # 清空持久化緩衝區，確保不會播放舊的音頻
        try:
            while not persistent_audio_buffer.empty():
                persistent_audio_buffer.get_nowait()
            print("持久化音頻緩衝區已清空")
        except Exception as e:
            print(f"清空持久化音頻緩衝區出錯: {str(e)}")
        
        try:
            # 持續從TTS管理器獲取音頻並發送
            idle_count = 0
            max_idle_time = 10  # 最大空閒時間（秒）
            
            while True:
                try:
                    audio_data = tts_manager.get_next_audio(timeout=0.5)
                    
                    if audio_data is not None and len(audio_data) > 0:
                        try:
                            # 創建臨時WAV文件
                            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_wav:
                                temp_wav_path = temp_wav.name
                                
                            # 使用soundfile保存為WAV（與test_kokoro.py相同的方法）
                            sf.write(temp_wav_path, audio_data, tts_manager.sample_rate)
                            
                            # 讀取WAV文件
                            with open(temp_wav_path, 'rb') as wav_file:
                                wav_data = wav_file.read()
                                
                            # 使用Base64編碼WAV數據
                            encoded_audio = base64.b64encode(wav_data).decode('utf-8')
                            
                            # 清理臨時文件
                            try:
                                os.remove(temp_wav_path)
                            except Exception as clean_err:
                                print(f"清理臨時文件出錯: {str(clean_err)}")
                            
                            # 發送完整的WAV文件（包括頭信息）
                            message = json.dumps({"audio": encoded_audio})
                            yield f"event: audio\ndata: {message}\n\n"
                            sent_audio_count += 1
                            print(f"發送WAV音頻數據: 長度 {len(wav_data)} 字節 (總計: {sent_audio_count} 個片段)")
                            
                            # 重置空閒計數器
                            idle_count = 0
                            last_audio_time = time.time()
                        except Exception as conv_err:
                            print(f"音頻轉換出錯: {str(conv_err)}")
                            import traceback
                            print(traceback.format_exc())
                        
                        # 在音頻片段之間添加短暫延遲，確保平滑播放
                        await asyncio.sleep(0.05)
                    else:
                        # 檢查是否應該結束流
                        current_time = time.time()
                        elapsed_since_last_audio = current_time - last_audio_time
                        
                        # 如果長時間沒有音頻且文本緩衝區為空，可能已經播放完所有內容
                        if not tts_manager.text_buffer and elapsed_since_last_audio > max_idle_time:
                            idle_count += 1
                            if idle_count > 5:  # 如果連續10次都沒有音頻，則結束流
                                print(f"TTS流空閒超過 {max_idle_time} 秒且無文本，關閉連接")
                                break
                        
                        # 發送空數據以保持連接
                        yield "event: ping\ndata: {}\n\n"
                        await asyncio.sleep(0.1)
                except Exception as e:
                    print(f"TTS獲取音頻出錯: {str(e)}")
                    await asyncio.sleep(0.5)  # 出錯時等待一段時間
        except Exception as e:
            print(f"TTS流出錯: {str(e)}")
            import traceback
            print(traceback.format_exc())
            yield f"event: error\ndata: {{\"error\": \"{str(e)}\"}}\n\n"
        finally:
            print("服務器已關閉TTS流連接")
            yield "event: close\ndata: {\"status\": \"closed\"}\n\n"
    
    return StreamingResponse(generate(), media_type="text/event-stream")

@app.get("/")
async def root():
    """提供前端HTML頁面"""
    return FileResponse("static/index.html")

@app.post("/api/stt")
async def speech_to_text(request: AudioToTextRequest):
    """將語音轉換為文本"""
    global stt_manager
    
    try:
        # 解碼音頻數據
        audio_data = base64.b64decode(request.audio_base64)

        # 保存为临时文件
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".webm")
        temp_file.write(audio_data)
        temp_file.close()
        
        # 轉錄音頻
        logger.info(f"轉錄語音文件: {temp_file.name}")
        result = stt_manager.transcribe(
            temp_file.name,
            language=request.language
        )
        
        # 刪除臨時文件
        os.unlink(temp_file.name)
        
        return {
            "success": True,
            "text": result["text"],
            "language": result.get("language", request.language)
        }
    
    except Exception as e:
        logger.error(f"語音轉文字錯誤: {str(e)}")
        raise HTTPException(status_code=500, detail=f"處理失敗: {str(e)}")

@app.post("/api/llm")
async def chat(request: ChatRequest):
    """生成對話回應（使用流式生成並即時TTS）"""
    global llm_manager, conversation_history, tts_manager
    
    try:
        # 清空TTS緩衝區，確保不會播放舊的內容
        tts_manager.text_buffer = ""
        while not tts_manager.audio_queue.empty():
            try:
                tts_manager.audio_queue.get_nowait()
                tts_manager.audio_queue.task_done()
            except:
                pass
        
        # 獲取或創建對話歷史
        if request.conversation_id not in conversation_history:
            conversation_history[request.conversation_id] = []
        
        # 使用提供的上下文或已有的歷史記錄
        context = request.context if request.context else conversation_history[request.conversation_id]
        
        # 準備消息
        messages = []
        
        # 添加情境提示詞
        scenario = request.scenario if request.scenario and request.scenario in SCENARIOS else "general"
        system_prompt = SCENARIOS[scenario]
        messages.append({"role": "system", "content": system_prompt})
        
        # 整理上下文確保交替的 user/assistant 格式
        processed_context = []
        last_role = None
        
        for msg in context:
            if msg["role"] not in ["user", "assistant"]:
                continue  # 跳過非user或assistant的角色
                
            # 如果與上一條訊息角色相同，合併訊息
            if msg["role"] == last_role and last_role is not None and processed_context:
                if isinstance(processed_context[-1]["content"], str):
                    processed_context[-1]["content"] += "\n" + msg["content"]
                else:
                    # 處理可能的複雜內容結構
                    processed_context[-1]["content"] = str(processed_context[-1]["content"]) + "\n" + str(msg["content"])
            else:
                processed_context.append(msg)
                last_role = msg["role"]
        
        # 確保交替順序，如果最後一條不是 assistant，則添加空assistant回應
        if processed_context and processed_context[-1]["role"] == "assistant" and request.message:
            # 添加新消息
            messages.extend(processed_context)
            user_message = {"role": "user", "content": request.message}
            messages.append(user_message)
        elif processed_context and processed_context[-1]["role"] == "user" and request.message:
            # 最後一條是user，合併請求消息
            processed_context[-1]["content"] += "\n" + request.message
            messages.extend(processed_context)
            user_message = processed_context[-1]  # 用於後續更新對話歷史
        elif not processed_context:
            # 空對話歷史，直接添加用戶消息
            user_message = {"role": "user", "content": request.message}
            messages.append(user_message)
        else:
            # 添加上下文和新消息
            messages.extend(processed_context)
            user_message = {"role": "user", "content": request.message}
            messages.append(user_message)
        
        # 使用流式生成，並即時發送到TTS
        logger.info(f"流式生成對話回應並即時TTS，情境: {scenario}")
        
        full_response = ""
        for text_chunk in llm_manager.generate_stream(messages):
            # 累積響應
            full_response += text_chunk
            
            # 提交到TTS進行處理（非阻塞）
            # 注意：這裡您需要確保TTS管理器能處理小片段文本
            tts_manager.add_text(text_chunk)
            
            # 等待一下確保有足夠時間處理文本
            await asyncio.sleep(0.01)
        
        # 在生成完成後強制處理緩衝區中的最後文本
        # 但不等待播放完成，避免阻塞
        tts_manager.force_process()
        
        # 等待一下確保所有音頻已經生成
        time.sleep(0.5)
        
        # 更新對話歷史 - 確保正確的順序
        if context and context[-1]["role"] == "user":
            # 如果最後一條是用戶消息，添加AI回應
            conversation_history[request.conversation_id] = context + [
                {"role": "assistant", "content": full_response}
            ]
        else:
            # 添加用戶消息和AI回應
            conversation_history[request.conversation_id] = context + [
                {"role": "user", "content": request.message},
                {"role": "assistant", "content": full_response}
            ]
        
        return {
            "success": True,
            "response": full_response,
            "conversation_id": request.conversation_id
        }
    
    except Exception as e:
        logger.error(f"對話生成錯誤: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"處理失敗: {str(e)}")

@app.post("/api/tts")
async def text_to_speech(request: TextToSpeechRequest):
    """將文本轉換為語音"""
    global tts_manager
    
    try:
        # 直接生成音頻數據而不是保存到文件
        logger.info(f"生成語音: {request.text[:30]}...")
        audio_data = tts_manager.generate_audio(request.text)
        
        if len(audio_data) == 0:
            raise Exception("生成語音失敗")
        
        # 創建臨時文件保存音頻（僅用於流式傳輸）
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".wav")
        temp_file.close()
        
        # 保存音頻數據到臨時文件
        sf.write(temp_file.name, audio_data, tts_manager.sample_rate)
        
        # 返回音頻文件
        def iterfile():
            with open(temp_file.name, "rb") as f:
                yield from f
            os.unlink(temp_file.name)
        
        return StreamingResponse(
            iterfile(),
            media_type="audio/wav"
        )
    
    except Exception as e:
        logger.error(f"文本轉語音錯誤: {str(e)}")
        raise HTTPException(status_code=500, detail=f"處理失敗: {str(e)}")

@app.post("/api/stream_llm")
async def stream_llm(request: ChatRequest):
    """流式生成對話回應（SSE）"""
    global llm_manager, conversation_history
    
    try:
        # 獲取或創建對話歷史
        if request.conversation_id not in conversation_history:
            conversation_history[request.conversation_id] = []
        
        # 使用提供的上下文或已有的歷史記錄
        context = request.context if request.context else conversation_history[request.conversation_id]
        
        # 準備消息
        messages = []
        
        # 添加情境提示詞
        scenario = request.scenario if request.scenario and request.scenario in SCENARIOS else "general"
        system_prompt = SCENARIOS[scenario]
        messages.append({"role": "system", "content": system_prompt})
        
        # 整理上下文確保交替的 user/assistant 格式
        processed_context = []
        last_role = None
        
        for msg in context:
            if msg["role"] not in ["user", "assistant"]:
                continue  # 跳過非user或assistant的角色
                
            # 如果與上一條訊息角色相同，合併訊息
            if msg["role"] == last_role and last_role is not None and processed_context:
                if isinstance(processed_context[-1]["content"], str):
                    processed_context[-1]["content"] += "\n" + msg["content"]
                else:
                    # 處理可能的複雜內容結構
                    processed_context[-1]["content"] = str(processed_context[-1]["content"]) + "\n" + str(msg["content"])
            else:
                processed_context.append(msg)
                last_role = msg["role"]
        
        # 確保交替順序，如果最後一條不是 assistant，則添加空assistant回應
        if processed_context and processed_context[-1]["role"] == "assistant" and request.message:
            # 添加新消息
            messages.extend(processed_context)
            user_message = {"role": "user", "content": request.message}
            messages.append(user_message)
        elif processed_context and processed_context[-1]["role"] == "user" and request.message:
            # 最後一條是user，合併請求消息
            processed_context[-1]["content"] += "\n" + request.message
            messages.extend(processed_context)
        elif not processed_context:
            # 空對話歷史，直接添加用戶消息
            user_message = {"role": "user", "content": request.message}
            messages.append(user_message)
        else:
            # 添加上下文和新消息
            messages.extend(processed_context)
            user_message = {"role": "user", "content": request.message}
            messages.append(user_message)
        
        # 初始化 SSE 響應
        async def event_generator():
            full_response = ""
            try:
                # 生成流式回應
                logger.info(f"生成流式對話回應，情境: {scenario}")
                for text_chunk in llm_manager.generate_stream(messages):
                    # 發送文本塊
                    #print(f"[API Server]生成文本塊: {text_chunk}")
                    full_response += text_chunk
                    yield f"data: {json.dumps({'chunk': text_chunk, 'done': False})}\n\n"
                    await asyncio.sleep(0.01)  # 避免過快發送
                
                # 發送完成信號
                yield f"data: {json.dumps({'chunk': '', 'done': True, 'full_response': full_response})}\n\n"
                
                # 更新對話歷史 - 確保正確的順序
                if context and context[-1]["role"] == "user":
                    # 如果最後一條是用戶消息，添加AI回應
                    conversation_history[request.conversation_id] = context + [
                        {"role": "assistant", "content": full_response}
                    ]
                else:
                    # 添加用戶消息和AI回應
                    conversation_history[request.conversation_id] = context + [
                        {"role": "user", "content": request.message},
                        {"role": "assistant", "content": full_response}
                    ]
            
            except Exception as e:
                logger.error(f"流式生成錯誤: {str(e)}")
                yield f"data: {json.dumps({'error': str(e)})}\n\n"
        
        return StreamingResponse(event_generator(), media_type="text/event-stream")
    
    except Exception as e:
        logger.error(f"流式生成初始化錯誤: {str(e)}")
        raise HTTPException(status_code=500, detail=f"處理失敗: {str(e)}")

@app.post("/api/pronunciation")
async def evaluate_pronunciation(request: PronunciationRequest):
    """評估發音準確度"""
    global stt_manager
    
    try:
        # 解碼音頻數據
        audio_data = base64.b64decode(request.audio_base64)
        
        # 創建臨時文件保存音頻
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".wav")
        temp_file.write(audio_data)
        temp_file.close()
        
        # 轉錄音頻
        logger.info(f"評估發音: {request.text}")
        result = stt_manager.transcribe(
            temp_file.name,
            language="en"
        )
        
        # 刪除臨時文件
        os.unlink(temp_file.name)
        
        # 比較原文和轉錄文本
        original_text = request.text.lower().strip()
        transcribed_text = result["text"].lower().strip()
        
        # 簡單的相似度計算（此處可以更複雜）
        from difflib import SequenceMatcher
        similarity = SequenceMatcher(None, original_text, transcribed_text).ratio() * 100
        
        # 生成評估結果
        feedback = ""
        if similarity > 90:
            feedback = "Excellent pronunciation! Well done."
        elif similarity > 70:
            feedback = "Good pronunciation, but there's room for improvement."
        elif similarity > 50:
            feedback = "Fair pronunciation. Keep practicing."
        else:
            feedback = "You need more practice. Try again more slowly."
        
        return {
            "success": True,
            "original_text": original_text,
            "transcribed_text": transcribed_text,
            "similarity": similarity,
            "feedback": feedback
        }
    
    except Exception as e:
        logger.error(f"發音評估錯誤: {str(e)}")
        raise HTTPException(status_code=500, detail=f"處理失敗: {str(e)}")

@app.get("/api/scenarios")
async def list_scenarios():
    """獲取可用的對話情境"""
    return {
        "success": True,
        "scenarios": {k: v.split(".")[0] for k, v in SCENARIOS.items()}
    }

# ------------ 啟動和關閉事件 ------------ #

@app.on_event("startup")
async def startup_event():
    """初始化模型"""
    global stt_manager, llm_manager, tts_manager
    
    try:
        logger.info("初始化STT模型...")
        stt_manager = STTManager(
            model_size="medium",
            device="cuda"
        )
        
        logger.info("初始化LLM模型...")
        llm_manager = LLMManager(
            model_type="4b",
            model_name="gemma-3-4b-it",
            local_files_only=True,
            max_new_tokens=100,
            system_prompt=SCENARIOS["general"],
            temperature=0.7
        )
        
        logger.info("初始化TTS模型...")
        tts_manager = TTSManager(
            lang_code='a',  # 美式英語
            speed=1.0,
            voice_file='af_heart.pt',
            play_locally=False,  # 不在後端播放音頻
            min_buffer_size=50  # 降低緩衝區大小以更快處理文本
        )
        
        logger.info("所有模型初始化完成")
    
    except Exception as e:
        logger.error(f"模型初始化失敗: {str(e)}")
        raise

@app.on_event("shutdown")
async def shutdown_event():
    """關閉模型"""
    global stt_manager, llm_manager, tts_manager
    
    logger.info("關閉模型...")
    if stt_manager:
        stt_manager.shutdown()
    
    if llm_manager:
        llm_manager.shutdown()
    
    if tts_manager:
        tts_manager.shutdown()
    
    logger.info("模型已關閉")

# ------------ 主程序 ------------ #

# 靜態文件配置
app.mount("/static", StaticFiles(directory="static"), name="static")
app.mount("/", StaticFiles(directory="static", html=True), name="static_html")

if __name__ == "__main__":
    # 啟動服務器
    uvicorn.run("api_server:app", host="0.0.0.0", port=8000, reload=False)