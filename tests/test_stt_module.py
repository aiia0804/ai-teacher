import time
import sys
import os
from pathlib import Path

# 添加項目根目錄到Python路徑
sys.path.append(str(Path(__file__).resolve().parent))

# 導入STT模組
from src.models.stt import STTManager

def find_test_audio():
    """尋找測試用的音頻文件"""
    print("\n===== 尋找測試音頻 =====")
    
    # 從不同位置尋找測試音頻
    base_dir = Path(__file__).resolve().parent
    possible_locations = [
        base_dir / "test_voice.mp3",  # 項目根目錄
        # base_dir / "test_kokoro_output.wav",
        # base_dir / "test_output.wav",
        # base_dir / "test_simple_output.wav",
        # base_dir / "test_local_output.wav",
        # base_dir / "test_tts_output.wav",
    ]
    
    for audio_path in possible_locations:
        if audio_path.exists():
            print(f"找到測試音頻: {audio_path}")
            return audio_path
    
    print("找不到測試音頻文件")
    return None

def test_basic_transcription(audio_path):
    """測試基本的轉錄功能"""
    print("\n===== 測試基本轉錄功能 =====")
    
    if not audio_path:
        print("沒有測試音頻，跳過測試")
        return
    
    # 創建STT管理器
    print("初始化STT管理器...")
    stt = STTManager(model_size="small")  # 使用small模型加快測試
    
    # 轉錄音頻
    print(f"轉錄音頻: {audio_path}")
    start_time = time.time()
    result = stt.transcribe(str(audio_path))
    end_time = time.time()
    
    # 輸出結果
    print(f"轉錄耗時: {end_time - start_time:.2f} 秒")
    print(f"檢測到的語言: {result['language']} (置信度: {result['language_probability']:.2f})")
    print(f"轉錄結果: {result['text']}")
    
    # 保存結果
    test_dir = Path(__file__).resolve().parent
    output_path = test_dir / "transcription_result"
    
    print("保存轉錄結果為不同格式...")
    stt._save_result(result, "txt", output_path.with_suffix(".txt"))
    stt._save_result(result, "json", output_path.with_suffix(".json"))
    stt._save_result(result, "srt", output_path.with_suffix(".srt"))
    stt._save_result(result, "vtt", output_path.with_suffix(".vtt"))

def test_streaming_mode(audio_path):
    """測試串流模式"""
    print("\n===== 測試串流模式 =====")
    
    if not audio_path:
        print("沒有測試音頻，跳過測試")
        return
    
    # 創建串流模式的STT管理器
    print("初始化串流模式STT管理器...")
    stt = STTManager(model_size="small", stream_mode=True)
    
    # 用於跟踪結果的變量
    results = []
    
    # 回調函數
    def on_result(result):
        print(f"收到轉錄結果: {result['text'][:50]}...")
        results.append(result)
    
    # 添加多個音頻處理任務
    print("添加音頻處理任務...")
    start_time = time.time()
    
    # 多次處理同一個文件，模擬多個請求
    for i in range(3):
        print(f"添加任務 {i+1}")
        stt.stream_audio(str(audio_path), on_result)
        time.sleep(0.2)  # 短暫等待，模擬請求間隔
    
    # 等待處理完成
    print("等待所有任務完成...")
    stt.wait_until_done()
    
    end_time = time.time()
    print(f"全部處理完成，總耗時: {end_time - start_time:.2f} 秒")
    print(f"共收到 {len(results)} 個結果")
    
    # 關閉STT管理器
    stt.shutdown()

def test_multiple_languages():
    """測試多語言支持"""
    print("\n===== 測試多語言支持 =====")
    
    # 如果沒有測試音頻，創建一個空音頻
    dummy_audio = Path(__file__).resolve().parent / "dummy_audio.wav"
    
    if not dummy_audio.exists():
        import numpy as np
        import soundfile as sf
        # 創建5秒的靜音
        dummy_samples = np.zeros(5 * 16000, dtype=np.float32)
        sf.write(dummy_audio, dummy_samples, 16000)
        print(f"創建了空白測試音頻: {dummy_audio}")
    
    # 創建支持不同語言的STT管理器
    languages = ["en", "zh", "ja"]
    
    for lang in languages:
        print(f"\n測試 {lang} 語言支持")
        stt = STTManager(model_size="small", language=lang)
        print(f"已創建 {lang} 語言的STT管理器")
        
        # 輸出支持的語言
        print(f"模型支持的語言: {lang}")
        
        # 這裡只測試初始化
        del stt

def main():
    """主測試函數"""
    print("====== STT模組測試 ======")
    
    try:
        # 尋找測試音頻
        audio_path = find_test_audio()
        
        # 測試基本轉錄功能
        #test_basic_transcription(audio_path)
        
        # 測試串流模式
        #test_streaming_mode(audio_path)
        
        # 測試多語言支持
        test_multiple_languages()
        
        print("\n所有測試完成!")
    
    except Exception as e:
        print(f"測試過程中發生錯誤: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()