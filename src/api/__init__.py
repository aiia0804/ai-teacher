"""
API包初始化
設置API路由和模型實例
"""
from fastapi import APIRouter

# 創建主路由
router = APIRouter()

# 在導入時導出路由器對象
__all__ = ['router']

# 導入路由模塊（這會注冊所有API端點）
from . import routes