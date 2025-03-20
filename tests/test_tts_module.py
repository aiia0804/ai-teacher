import sys
import time
from pathlib import Path

# 添加項目根目錄到Python路徑
CURRENT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(CURRENT_DIR / "src"))

# 導入簡化版TTS模塊
from models.tts import TTSManager

def find_voice_files():
    """搜索並報告語音文件位置"""
    print("\n===== 尋找語音文件 =====")
    
    # 確定項目根目錄
    base_dir = Path(__file__).resolve().parent.parent
    model_dir = base_dir / "src" / "models" / "tts_models"
    voice_dir = model_dir / "voices"
    
    print(f"搜索語音目錄: {voice_dir}")
    
    # 搜索語音文件
    if voice_dir.exists():
        voice_files = list(voice_dir.glob("**/*.pt"))
        if voice_files:
            print("找到語音文件:")
            for i, file in enumerate(voice_files):
                print(f"  {i+1}. {file}")
            return model_dir, voice_files[0]
        else:
            print("找不到任何語音文件")
    else:
        print(f"語音目錄 {voice_dir} 不存在")
    
    return model_dir, None

def test_basic_tts(model_dir, voice_path=None):
    """測試基本TTS功能"""
    print("\n===== 測試基本TTS功能 =====")
    
    # 創建TTS管理器
    kwargs = {"model_dir": model_dir}
    
    # 如果提供了語音文件路徑，則使用它
    if voice_path:
        print(f"使用指定的語音文件: {voice_path}")
        kwargs["voice_file"] = str(voice_path.relative_to(model_dir))
    
    # 初始化TTS管理器
    print("初始化TTS管理器...")
    tts = TTSManager(**kwargs)
    
    # 生成測試音頻
    print("生成測試音頻...")
    test_text = "Hello, this is a test of the simplified TTS system."
    audio = tts.generate_audio(test_text, play=True)
    
    # 結果報告
    if len(audio) > 0:
        print(f"成功生成音頻，長度: {len(audio)} 樣本")
        tts.save_audio(test_text, "test_simplified_output.wav")
        print("已保存音頻到 'test_simplified_output.wav'")
    else:
        print("音頻生成失敗")

def test_same_text_as_kokoro_test(model_dir):
    """使用與test_kokoro.py相同的文本測試"""
    print("\n===== 使用與test_kokoro.py相同文本測試 =====")
    
    # 創建TTS管理器
    kwargs = {"model_dir": model_dir}
    kwargs["voice_file"] = 'am_adam.pt'
    
    # 初始化TTS管理器
    tts = TTSManager(**kwargs)
    
    # 使用與test_kokoro.py相同的文本
    test_text = "Well, I am not quite sure what do you mean. Could you try to be more specific?"
    
    # 生成音頻
    print(f"生成文本: '{test_text}'")
    start_time = time.time()
    audio = tts.generate_audio(test_text, play=True)
    end_time = time.time()
    
    # 結果報告
    print(f"音頻生成耗時: {end_time - start_time:.2f} 秒")
    
    if len(audio) > 0:
        print(f"成功生成音頻，長度: {len(audio)} 樣本")
        tts.save_audio(test_text, "test_kokoro_comparison.wav")
        print("已保存音頻到 'test_kokoro_comparison.wav'")
    else:
        print("音頻生成失敗")

def test_streaming_mode(model_dir, voice_path=None):
    """測試串流模式"""
    print("\n===== 測試串流模式 =====")
    
    # 創建TTS管理器
    kwargs = {
        "model_dir": model_dir,
        "stream_mode": True
    }
    if voice_path:
        kwargs["voice_file"] = 'am_adam.pt'
    
    # 初始化串流模式TTS管理器
    tts = TTSManager(**kwargs)
    
    # 準備測試句子
    sentences = [
        "Welcome to the English conversation practice.",
        "I'm your AI language tutor.",
        "Let's start by introducing ourselves."
    ]
    
    # 添加句子到隊列
    print("添加句子到隊列...")
    for i, sentence in enumerate(sentences):
        print(f"添加句子 {i+1}: {sentence}")
        tts.stream_text(sentence)
        time.sleep(0.5)  # 模擬處理延遲
    
    # 等待處理完成
    print("等待處理完成...")
    tts.wait_until_done()
    
    # 關閉TTS管理器
    tts.shutdown()
    print("串流模式測試完成")

def main():
    """主測試函數"""
    print("====== 簡化版TTS測試 ======")
    
    try:
        # 搜索語音文件
        model_dir, voice_path = find_voice_files()
        
        # 測試基本功能
        #test_basic_tts(model_dir, voice_path)
        
        # 使用與test_kokoro.py相同文本測試
        test_same_text_as_kokoro_test(model_dir)
        
        # 測試串流模式
        #test_streaming_mode(model_dir)
        
        print("\n所有測試完成!")
    
    except Exception as e:
        print(f"測試過程中發生錯誤: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()