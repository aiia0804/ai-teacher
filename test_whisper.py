from faster_whisper import WhisperModel
import time
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

# 指定模型的下載目錄
MODEL_DIR = BASE_DIR / "src" / "models" / "stt_models"
# 選擇模型大小
model_size = "medium"  # 可選 "tiny", "base", "small", "medium", "large-v1", "large-v2", "large-v3"

# 加載模型並指定下載目錄
model = WhisperModel(model_size, device="cuda", compute_type="float16", download_root=str(MODEL_DIR))

# 指定測試音頻檔案路徑
audio_path = BASE_DIR / "test_kokoro_full_output.wav"

start_time = time.time()

# 轉錄語音
print("正在轉錄音頻...")
segments, info = model.transcribe(audio_path)

end_time = time.time()
elapsed_time = end_time - start_time
print(f"TEXT生成花費時間: {elapsed_time:.2f} 秒")

# 輸出轉錄文本
print("轉錄結果:")
for segment in segments:
    print(segment.text)
