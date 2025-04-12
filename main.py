"""
AI英語教師應用程序入口點
整合FastAPI、靜態文件和模型管理器
"""
import logging
import os
import sys
from pathlib import Path

import uvicorn
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

# 導入配置
from src.config import (DEBUG_MODE, SERVER_HOST, SERVER_PORT, STATIC_DIR,
                       LLM_MODEL_DIR, STT_MODEL_DIR, TTS_MODEL_DIR,
                       LLM_MODEL_TYPE, LLM_MODEL_NAME, TTS_LANG_CODE,
                       TTS_VOICE_FILE, TTS_SPEED, TTS_MIN_BUFFER_SIZE)

# 導入模型管理器類
from src.models.llm import LLMManager
from src.models.stt import STTManager
from src.models.tts import TTSManager

# 導入API路由（不要從routes導入管理器實例以避免循環導入）
from src.api import router as api_router

# 設置日誌
log_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
log_file = os.path.join(Path(__file__).resolve().parent, "api_server.log")

logging.basicConfig(
    level=logging.INFO,
    format=log_format,
    handlers=[
        logging.FileHandler(log_file),
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger("main")

# 全局管理器實例
llm_manager = None 
stt_manager = None
tts_manager = None

# 初始化標誌，防止多次初始化
_managers_initialized = False

def initialize_managers():
    """初始化所有模型管理器（只會執行一次）"""
    global llm_manager, stt_manager, tts_manager, _managers_initialized
    
    # 如果已經初始化過，直接返回
    if _managers_initialized:
        logger.info("模型管理器已經初始化，跳過...")
        return
    
    try:
        # 初始化TTS管理器
        logger.info("初始化TTS管理器...")
        tts_manager = TTSManager(
            lang_code=TTS_LANG_CODE,
            voice_file=TTS_VOICE_FILE,
            speed=TTS_SPEED,
            min_buffer_size=TTS_MIN_BUFFER_SIZE,
            model_dir=TTS_MODEL_DIR
        )
        
        # 初始化STT管理器
        logger.info("初始化STT管理器...")
        stt_manager = STTManager(model_dir=STT_MODEL_DIR)
        
        # 初始化LLM管理器
        logger.info("初始化LLM管理器...")
        llm_manager = LLMManager(
            model_type=LLM_MODEL_TYPE,
            model_name=LLM_MODEL_NAME,
            model_dir=LLM_MODEL_DIR
        )
        
        # 設置初始化標誌
        _managers_initialized = True
        
        # 將實例提供給routes模塊（避免循環導入）
        import src.api.routes
        src.api.routes.tts_manager = tts_manager
        src.api.routes.stt_manager = stt_manager
        src.api.routes.llm_manager = llm_manager
        
        logger.info("所有模型管理器初始化完成")
    except Exception as e:
        logger.error(f"初始化模型管理器時出錯: {str(e)}", exc_info=True)
        raise

def create_app() -> FastAPI:
    """創建並設置FastAPI應用程序"""
    # 創建FastAPI應用
    app = FastAPI(
        title="AI英語教師API",
        description="用於提供英語對話、STT和TTS功能的API",
        version="1.0.0",
        debug=DEBUG_MODE
    )
    
    # 添加CORS中間件
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"]
    )
    
    # 添加非同步啟動事件
    @app.on_event("startup")
    async def startup_event():
        logger.info("服務器啟動中...")
        # 在這裡初始化模型管理器，確保只初始化一次
        initialize_managers()
        logger.info(f"使用以下模型目錄: LLM={LLM_MODEL_DIR}, STT={STT_MODEL_DIR}, TTS={TTS_MODEL_DIR}")
    
    # 添加非同步關閉事件
    @app.on_event("shutdown")
    async def shutdown_event():
        logger.info("服務器正在關閉...")
        global llm_manager, stt_manager, tts_manager
        
        # 釋放資源
        if tts_manager:
            logger.info("釋放TTS管理器資源...")
            tts_manager.cleanup()
        
        if stt_manager:
            logger.info("釋放STT管理器資源...")
            # 如果STT管理器有cleanup方法，調用它
            if hasattr(stt_manager, 'cleanup'):
                stt_manager.cleanup()
        
        if llm_manager:
            logger.info("釋放LLM管理器資源...")
            # 如果LLM管理器有cleanup方法，調用它
            if hasattr(llm_manager, 'cleanup'):
                llm_manager.cleanup()
    
    # 全局異常處理器
    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        logger.error(f"全局異常: {str(exc)}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": "服務器內部錯誤", "detail": str(exc)}
        )
    
    # 掛載API路由
    app.include_router(api_router, prefix="/api")
    
    # 掛載靜態文件
    if os.path.exists(STATIC_DIR):
        app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")
        logger.info(f"已掛載靜態文件: {STATIC_DIR}")
    else:
        logger.warning(f"靜態文件目錄不存在: {STATIC_DIR}")
    
    return app

# 創建FastAPI應用
app = create_app()

if __name__ == "__main__":
    """主入口點，用於直接運行應用"""
    try:
        logger.info(f"啟動服務器 - 地址: {SERVER_HOST}:{SERVER_PORT}")
        uvicorn.run(
            "main:app",
            host=SERVER_HOST,
            port=SERVER_PORT,
            reload=DEBUG_MODE,
            workers=1
        )
    except KeyboardInterrupt:
        logger.info("收到鍵盤中斷，服務器關閉")
    except Exception as e:
        logger.error(f"服務器運行時出錯: {str(e)}", exc_info=True)