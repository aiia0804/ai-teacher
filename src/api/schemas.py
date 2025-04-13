"""
API數據模型定義
使用Pydantic模型處理請求和響應的數據驗證
"""
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any, Union

class AudioToTextRequest(BaseModel):
    """語音轉文本請求模型"""
    audio_base64: str = Field(..., description="Base64編碼的音頻數據")
    language: Optional[str] = Field("en", description="語言代碼，默認為英語")

class TextToSpeechRequest(BaseModel):
    """文本轉語音請求模型"""
    text: str = Field(..., description="要轉換為語音的文本")
    voice: Optional[str] = Field("af_heart.pt", description="語音模型文件")
    speed: Optional[float] = Field(1.0, description="語音速度，1.0為正常速度")

class PronunciationRequest(BaseModel):
    """發音評估請求模型"""
    audio_base64: str = Field(..., description="Base64編碼的音頻數據")
    text: str = Field(..., description="用於比較的文本")

class ChatMessage(BaseModel):
    """對話消息模型"""
    role: str = Field(..., description="消息角色，user或assistant")
    content: str = Field(..., description="消息內容")

class ChatRequest(BaseModel):
    """對話請求模型"""
    message: str = Field(..., description="用戶消息")
    conversation_id: Optional[str] = Field(None, description="對話ID，用於維護對話歷史")
    context: Optional[List[Dict[str, Any]]] = Field(None, description="對話上下文")
    scenario: Optional[str] = Field(None, description="對話情境，如general、restaurant等")
    voice: Optional[str] = Field("af_heart.pt", description="語音模型文件名，如af_heart.pt")

class ChatResponse(BaseModel):
    """對話響應模型"""
    success: bool = Field(..., description="請求是否成功")
    response: str = Field(..., description="模型回應")
    conversation_id: str = Field(..., description="對話ID")

class AudioResponse(BaseModel):
    """音頻響應模型（用於Base64返回時）"""
    success: bool = Field(..., description="請求是否成功")
    audio: str = Field(..., description="Base64編碼的音頻數據")

class ErrorResponse(BaseModel):
    """錯誤響應模型"""
    success: bool = Field(False, description="請求失敗")
    error: str = Field(..., description="錯誤信息")
    detail: Optional[str] = Field(None, description="詳細錯誤信息")