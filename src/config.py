"""
AI英語教師應用程序配置
包含所有關於模型、API和服務器的配置參數
"""
import os
from pathlib import Path

# 基礎目錄
BASE_DIR = Path(__file__).resolve().parent.parent

# 服務器配置
SERVER_HOST = "0.0.0.0"
SERVER_PORT = 8000
DEBUG_MODE = True

# 靜態文件配置
STATIC_DIR = os.path.join(BASE_DIR, "static")

# 模型配置
MODEL_DATA_DIR = os.path.join(BASE_DIR, "src", "models", "model_data")
LLM_MODEL_DIR = os.path.join(MODEL_DATA_DIR, "llm_models")
STT_MODEL_DIR = os.path.join(MODEL_DATA_DIR, "stt_models")
TTS_MODEL_DIR = os.path.join(MODEL_DATA_DIR, "tts_models")

# LLM配置
LLM_MODEL_TYPE = "4b"
LLM_MODEL_NAME = "gemma-3-4b-it"
LLM_MAX_TOKENS = 100
LLM_TEMPERATURE = 0.7

# TTS配置
TTS_LANG_CODE = 'a'  # 美式英語
TTS_VOICE_FILE = 'af_heart.pt'
TTS_SPEED = 1.0
TTS_MIN_BUFFER_SIZE = 50
TTS_PLAY_LOCALLY = False

# STT配置
STT_DEFAULT_LANGUAGE = "en"
STT_SAMPLE_RATE = 16000

# 對話情境提示詞
SCENARIOS = {
    "general": """You are a friendly and casual English teacher. Respond naturally and conversationally, 
like a native speaker talking to a student. Keep responses simple, clear, and concise (around 2-3 sentences per answer).
Avoid using bullet points or numbered lists. Make your answers brief but helpful.""",
    
    "restaurant": """You are an English teacher helping a student practice ordering food in a restaurant. 
Act as a waiter and help them with restaurant vocabulary and phrases. Keep responses simple and natural.""",
    
    "shopping": """You are an English teacher helping a student practice shopping conversations. 
Act as a shop assistant and help them with shopping vocabulary and expressions. Keep responses simple and natural."""
}