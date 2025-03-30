from fastapi import FastAPI, UploadFile, File, Form, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
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

# 配置日誌
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
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
# 這些變數將在啟動服務時初始化
stt_manager = None
llm_manager = None
tts_manager = None

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

@app.get("/")
async def root():
    """API健康檢查"""
    return {"status": "online", "message": "英語對話AI教師API正常運行"}

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
        
        # 生成完成後，等待TTS完成播放
        tts_manager.wait_until_done()
        
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
        # 創建臨時文件保存音頻
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".wav")
        temp_file.close()
        
        # 生成語音
        logger.info(f"生成語音: {request.text[:30]}...")
        success = tts_manager.save_audio(
            request.text,
            temp_file.name
        )
        
        if not success:
            raise Exception("生成語音失敗")
        
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
            voice_file= 'af_heart.pt'
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

if __name__ == "__main__":
    # 啟動服務器
    uvicorn.run("api_server:app", host="0.0.0.0", port=8000, reload=False)