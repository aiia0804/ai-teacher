import time
import sys
import os
from pathlib import Path

# 添加項目根目錄到Python路徑
sys.path.append(str(Path(__file__).resolve().parent))

# 導入流式LLM模組
from src.models.llm import LLMManager, DEFAULT_ENGLISH_TEACHER_PROMPT

def find_model_path():
    """搜索可能的模型路徑"""
    print("\n===== 尋找模型路徑 =====")
    
    # 從不同位置尋找模型
    base_dir = Path(__file__).resolve().parent
    llm_models_dir = base_dir / "src" / "models" / "llm_models"
    
    potential_paths = [
        llm_models_dir / "gemma-3-1b-it",
        base_dir / "models" / "gemma-3-1b-it"
    ]
    
    for path in potential_paths:
        if path.exists() and (path / "tokenizer_config.json").exists():
            print(f"找到模型: {path}")
            return path
    
    print("找不到本地模型，將使用模型名稱")
    return "google/gemma-3-1b-it"

def test_token_streaming(model_path):
    """測試真正的逐token流式生成"""
    print("\n===== 測試真正的逐token流式生成 =====")
    
    # 使用本地模型優先
    use_local = isinstance(model_path, Path)
    
    # 初始化LLM管理器
    print("初始化LLM管理器...")
    llm = LLMManager(
        model_name=str(model_path) if use_local else model_path,
        system_prompt=DEFAULT_ENGLISH_TEACHER_PROMPT,
        local_files_only=use_local,
        max_new_tokens=100
    )
    
    # 測試問題
    test_question = "Give me 3 tips for improving my English pronunciation."
    
    print(f"測試問題: '{test_question}'")
    print("回答: ", end="", flush=True)
    
    # 保存生成的文本
    collected_text = []
    
    # 回調函數
    def collect_token(token):
        collected_text.append(token)
    
    # 開始流式生成
    start_time = time.time()
    llm.generate_stream(test_question, collect_token)
    end_time = time.time()
    
    print("\n")  # 確保下一行輸出在新行
    print(f"生成完成，耗時: {end_time - start_time:.2f} 秒")
    print(f"收集的token數量: {len(collected_text)}")
    
    # 清理資源
    llm.clear_memory()
    del llm

def test_stream_mode_with_true_streaming(model_path):
    """測試串流模式結合真正的流式生成"""
    print("\n===== 測試串流模式結合真正的流式生成 =====")
    
    # 使用本地模型優先
    use_local = isinstance(model_path, Path)
    
    # 初始化串流模式LLM管理器
    print("初始化串流模式LLM管理器...")
    llm = LLMManager(
        model_name=str(model_path) if use_local else model_path,
        system_prompt=DEFAULT_ENGLISH_TEACHER_PROMPT,
        local_files_only=use_local,
        stream_mode=True,
        max_new_tokens=100
    )
    
    # 測試問題
    test_questions = [
        "What's the difference between 'in time' and 'on time'?",
        "How can I improve my English vocabulary?"
    ]
    
    # 回調函數
    def token_callback(token):
        print(token, end="", flush=True)
    
    # 提交請求
    start_time = time.time()
    
    for i, question in enumerate(test_questions):
        print(f"\n\n問題 {i+1}: '{question}'")
        print(f"回答 {i+1}: ", end="", flush=True)
        
        # 以串流模式提交請求
        llm.generate_stream(question, token_callback)
        # 短暫等待，讓上一個請求開始處理
        time.sleep(0.5)
    
    # 等待所有請求處理完成
    print("\n\n等待所有請求處理完成...")
    llm.wait_until_done()
    
    end_time = time.time()
    print(f"所有請求處理完成，總耗時: {end_time - start_time:.2f} 秒")
    
    # 關閉LLM管理器
    llm.shutdown()
    llm.clear_memory()
    del llm

def test_multiple_questions(model_path):
    """測試多個問題的處理"""
    print("\n===== 測試多個問題的處理 =====")
    
    # 使用本地模型優先
    use_local = isinstance(model_path, Path)
    
    # 初始化LLM管理器
    print("初始化LLM管理器...")
    llm = LLMManager(
        model_name=str(model_path) if use_local else model_path,
        system_prompt=DEFAULT_ENGLISH_TEACHER_PROMPT,
        local_files_only=use_local,
        max_new_tokens=50  # 設置較小的max_new_tokens以加快測試
    )
    
    # 準備多個問題
    questions = [
        "What is your name?",
        "How do I say 'thank you' in different ways?",
        "Can you give me a simple English sentence?"
    ]
    
    # 測試每個問題
    for i, question in enumerate(questions):
        print(f"\n問題 {i+1}: '{question}'")
        print(f"回答 {i+1}: ", end="", flush=True)
        
        # 定義一個回調函數
        def token_callback(token):
            print(token, end="", flush=True)
        
        # 使用流式生成
        llm.generate_stream(question, token_callback)
        
    # 清理資源
    llm.clear_memory()
    del llm

def main():
    """主測試函數"""
    print("====== 真正流式生成的LLM測試 ======")
    
    try:
        # 尋找模型路徑
        model_path = find_model_path()
        
        # 測試逐token流式生成
        #test_token_streaming(model_path)
        
        # 測試串流模式結合真正的流式生成
        test_stream_mode_with_true_streaming(model_path)
        
        # 測試多個問題
        #test_multiple_questions(model_path)
        
        print("\n所有測試完成!")
    
    except Exception as e:
        print(f"測試過程中發生錯誤: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()