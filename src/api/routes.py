"""
API路由處理模塊
包含所有API端點的實現
"""
import asyncio
import base64
import json
import logging
import os
import tempfile
import time
import traceback
from typing import Dict, List, Optional

import soundfile as sf
from fastapi import BackgroundTasks, HTTPException
from fastapi.responses import FileResponse, StreamingResponse

from src.config import SCENARIOS
from . import router
from .schemas import (AudioResponse, AudioToTextRequest, ChatRequest,
                      ChatResponse, ErrorResponse, PronunciationRequest,
                      TextToSpeechRequest)

# 管理器實例（將在主應用中初始化）
stt_manager = None
llm_manager = None
tts_manager = None

# 創建持久化音頻緩衝區，用於存儲生成的音頻數據
import queue
persistent_audio_buffer = queue.Queue(maxsize=20)  # 最多存儲20個音頻片段

# 對話歷史記錄
conversation_history = {}

# 配置日誌
logger = logging.getLogger("api")

# 摘要最大長度
SUMMARY_MAX_LENGTH = 100

# 函數用於生成對話摘要
async def generate_conversation_summary(messages: List[Dict[str, any]]) -> str:
    """
    使用LLM生成對話摘要
    
    Args:
        messages: 要摘要的對話消息列表
        
    Returns:
        摘要文本，控制在100個字符內
    """
    if not messages or len(messages) < 2:
        return ""
    
    # 提取對話內容
    conversation_text = ""
    for msg in messages:
        role = "User" if msg["role"] == "user" else "Teacher"
        
        # 處理不同的content結構
        content = ""
        if isinstance(msg["content"], str):
            content = msg["content"]
        elif isinstance(msg["content"], list):
            # 處理content是字典列表的情況
            for item in msg["content"]:
                if isinstance(item, dict) and "text" in item:
                    content += item["text"] + " "
        
        conversation_text += f"{role}: {content.strip()}\n"
    
    # 創建摘要提示
    summary_prompt = f"""Summarize the following English learning conversation in 100 characters or less. 
Focus ONLY on the key topics discussed and important language points:

{conversation_text}

Summary (100 chars max):"""
    
    # 使用LLM生成摘要
    try:
        summary = llm_manager.generate(summary_prompt, temperature=0.3, max_new_tokens=150)
        
        # 確保摘要不超過最大長度
        if len(summary) > SUMMARY_MAX_LENGTH:
            summary = summary[:SUMMARY_MAX_LENGTH-3] + "..."
            
        return summary
    except Exception as e:
        logger.error(f"生成摘要時出錯: {str(e)}")
        return f"Previous conversation about English learning (summary generation failed)"

# 函數用於優化對話歷史，保留重要部分，壓縮其他部分
async def optimize_conversation_history(history: List[Dict[str, any]]) -> List[Dict[str, any]]:
    """
    優化對話歷史，將早期對話壓縮為摘要
    
    Args:
        history: 完整的對話歷史
        
    Returns:
        優化後的對話歷史
    """

    # 保留最近兩輪對話（4條消息）
    recent_messages = history[-2:]
    
    # 需要摘要的早期對話
    earlier_messages = history[:-2]
    
    if not earlier_messages:
        return recent_messages
    
    # 記錄優化前後的token估計
    tokens_before = sum(len(str(msg)) for msg in history) / 2  # 粗略估計
    
    # 生成早期對話的摘要
    summary = await generate_conversation_summary(earlier_messages)
    
    if not summary:
        return recent_messages
    
    # 創建包含摘要的系統消息
    summary_message = {
        "role": "system",
        "content": f"Previous conversation summary: {summary}"
    }
    
    # 計算優化後的token估計
    optimized_history = [summary_message] + recent_messages
    tokens_after = sum(len(str(msg)) for msg in optimized_history) / 2  # 粗略估計
    
    # 記錄token減少情況
    reduction = tokens_before - tokens_after
    reduction_percent = (reduction / tokens_before) * 100 if tokens_before > 0 else 0
    logger.info(f"對話歷史優化: 從約 {tokens_before:.0f} tokens 減少到 {tokens_after:.0f} tokens (減少約 {reduction_percent:.1f}%)")
    
    # 返回包含摘要和最近對話的優化歷史
    return optimized_history

@router.get("/")
async def api_status():
    """API健康檢查"""
    return {"status": "online", "message": "英語對話AI教師API正常運行"}

@router.get('/tts-stream')
async def tts_stream():
    """
    TTS 流式傳輸端點 - 使用Server-Sent Events (SSE)提供實時音頻
    """
    async def generate():
        # 記錄客戶端連接
        logger.info("客戶端已連接到TTS流")
        
        # 獲取TTS管理器實例
        global tts_manager
        
        # 確保 TTS 管理器已初始化
        if tts_manager is None:
            logger.warning("TTS管理器尚未初始化")
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
            logger.info("持久化音頻緩衝區已清空")
        except Exception as e:
            logger.error(f"清空持久化音頻緩衝區出錯: {str(e)}")
        
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
                                
                            # 使用soundfile保存為WAV
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
                                logger.error(f"清理臨時文件出錯: {str(clean_err)}")
                            
                            # 發送完整的WAV文件（包括頭信息）
                            message = json.dumps({"audio": encoded_audio})
                            yield f"event: audio\ndata: {message}\n\n"
                            sent_audio_count += 1
                            logger.info(f"發送WAV音頻數據: 長度 {len(wav_data)} 字節 (總計: {sent_audio_count} 個片段)")
                            
                            # 重置空閒計數器
                            idle_count = 0
                            last_audio_time = time.time()
                        except Exception as conv_err:
                            logger.error(f"音頻轉換出錯: {str(conv_err)}")
                            logger.error(traceback.format_exc())
                        
                        # 在音頻片段之間添加短暫延遲，確保平滑播放
                        await asyncio.sleep(0.05)
                    else:
                        # 檢查是否應該結束流
                        current_time = time.time()
                        elapsed_since_last_audio = current_time - last_audio_time
                        
                        # 如果長時間沒有音頻且文本緩衝區為空，可能已經播放完所有內容
                        if not tts_manager.text_buffer and elapsed_since_last_audio > max_idle_time:
                            idle_count += 1
                            if idle_count > 5:  # 如果連續5次都沒有音頻，則結束流
                                logger.info(f"TTS流空閒超過 {max_idle_time} 秒且無文本，關閉連接")
                                break
                        
                        # 發送空數據以保持連接
                        yield "event: ping\ndata: {}\n\n"
                        await asyncio.sleep(0.1)
                except Exception as e:
                    logger.error(f"TTS獲取音頻出錯: {str(e)}")
                    await asyncio.sleep(0.5)  # 出錯時等待一段時間
        except Exception as e:
            logger.error(f"TTS流出錯: {str(e)}")
            logger.error(traceback.format_exc())
            yield f"event: error\ndata: {{\"error\": \"{str(e)}\"}}\n\n"
        finally:
            logger.info("服務器已關閉TTS流連接")
            yield "event: close\ndata: {\"status\": \"closed\"}\n\n"
    
    return StreamingResponse(generate(), media_type="text/event-stream")

@router.post("/stt")
async def speech_to_text(request: AudioToTextRequest):
    """將語音轉換為文本"""
    global stt_manager
    
    try:
        # 確保STT管理器已初始化
        if stt_manager is None:
            raise HTTPException(status_code=500, detail="STT manager not initialized")
        
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

@router.post("/llm")
async def chat(request: ChatRequest):
    """生成對話回應（使用流式生成並即時TTS）"""
    global llm_manager, conversation_history, tts_manager
    
    try:
        # 確保管理器已初始化
        if llm_manager is None or tts_manager is None:
            raise HTTPException(status_code=500, detail="LLM or TTS manager not initialized")
        
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
            # 保留系統消息（包括摘要）
            if msg["role"] == "system":
                processed_context.append(msg)
                continue
                
            # 處理用戶和助手消息
            if msg["role"] not in ["user", "assistant"]:
                continue  # 跳過其他非標準角色
                
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
            tts_manager.add_text(text_chunk)
            
            # 等待一下確保有足夠時間處理文本
            await asyncio.sleep(0.01)
        
        # 在生成完成後強制處理緩衝區中的最後文本
        tts_manager.force_process()
        
        # 等待一下確保所有音頻已經生成
        await asyncio.sleep(0.5)
        
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
            
        # 優化對話歷史，將早期對話生成摘要
        current_history = conversation_history[request.conversation_id]
        print(f"對話歷史: {current_history}")
        # 調試信息
        history_str = json.dumps(current_history, ensure_ascii=False)
        logger.info(f"優化前對話歷史長度: {len(history_str)} 字符")
        print(f"優化前對話歷史: {history_str[:200]}...")
    
        if len(current_history) > 4:  # 對話超過2輪時進行優化
            optimized_history = await optimize_conversation_history(current_history)
            conversation_history[request.conversation_id] = optimized_history
            
            # 調試信息
            optimized_str = json.dumps(optimized_history, ensure_ascii=False)
            logger.info(f"優化後對話歷史長度: {len(optimized_str)} 字符")
            logger.info(f"已優化對話歷史，從 {len(current_history)} 條消息減少到 {len(optimized_history)} 條")
            print(f"優化後對話歷史: {optimized_str[:200]}...")
        
        return ChatResponse(
            success=True,
            response=full_response,
            conversation_id=request.conversation_id
        )
    
    except Exception as e:
        logger.error(f"對話生成錯誤: {str(e)}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"處理失敗: {str(e)}")

@router.post("/tts")
async def text_to_speech(request: TextToSpeechRequest):
    """將文本轉換為語音"""
    global tts_manager
    
    try:
        # 確保TTS管理器已初始化
        if tts_manager is None:
            raise HTTPException(status_code=500, detail="TTS manager not initialized")
        
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
            # 清理臨時文件
            try:
                os.unlink(temp_file.name)
            except Exception as e:
                logger.error(f"清理臨時文件出錯: {str(e)}")
        
        return StreamingResponse(
            iterfile(),
            media_type="audio/wav"
        )
    
    except Exception as e:
        logger.error(f"文本轉語音錯誤: {str(e)}")
        raise HTTPException(status_code=500, detail=f"處理失敗: {str(e)}")

@router.post("/pronunciation")
async def evaluate_pronunciation(request: PronunciationRequest):
    """評估發音準確度"""
    global stt_manager
    
    try:
        # 確保STT管理器已初始化
        if stt_manager is None:
            raise HTTPException(status_code=500, detail="STT manager not initialized")
        
        # 解碼音頻數據
        audio_data = base64.b64decode(request.audio_base64)
        
        # 保存为临时文件
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".webm")
        temp_file.write(audio_data)
        temp_file.close()
        
        # 轉錄音頻
        logger.info(f"評估發音: {request.text[:30]}...")
        result = stt_manager.transcribe(temp_file.name)
        transcribed_text = result["text"]
        
        # 刪除臨時文件
        os.unlink(temp_file.name)
        
        # 簡單的相似度評估算法
        # 這裡可以改進為更複雜的發音評估
        import difflib
        similarity = difflib.SequenceMatcher(None, 
            transcribed_text.lower(), 
            request.text.lower()
        ).ratio()
        
        # 計算準確率（百分比）
        accuracy = round(similarity * 100)
        
        # 評級 (A+ to F)
        grade = "A+"
        if accuracy < 60:
            grade = "F"
        elif accuracy < 70:
            grade = "D"
        elif accuracy < 80:
            grade = "C"
        elif accuracy < 90:
            grade = "B"
        elif accuracy < 95:
            grade = "A"
        
        return {
            "success": True,
            "transcribed_text": transcribed_text,
            "expected_text": request.text,
            "accuracy": accuracy,
            "grade": grade,
            "feedback": _generate_pronunciation_feedback(accuracy, transcribed_text, request.text)
        }
    
    except Exception as e:
        logger.error(f"發音評估錯誤: {str(e)}")
        raise HTTPException(status_code=500, detail=f"處理失敗: {str(e)}")

def _generate_pronunciation_feedback(accuracy: int, transcribed: str, expected: str) -> str:
    """根據準確率生成發音反饋"""
    if accuracy >= 95:
        return "出色的發音！您的發音非常標準，繼續保持。"
    elif accuracy >= 90:
        return "很好的發音！只有輕微的差異，但整體非常好。"
    elif accuracy >= 80:
        return "良好的發音。有一些小問題，但大部分內容都正確。"
    elif accuracy >= 70:
        return "不錯的嘗試。您的發音有一些問題需要改進，但整體可以理解。"
    elif accuracy >= 60:
        return "需要改進。您的部分發音難以理解，建議練習關鍵詞。"
    else:
        return "需要更多練習。您的發音與預期有很大差異，建議放慢速度，逐個詞練習。"

@router.get("/scenarios")
async def list_scenarios():
    """獲取可用的對話情境"""
    return {
        "success": True,
        "scenarios": list(SCENARIOS.keys())
    }