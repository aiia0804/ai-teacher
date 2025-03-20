import os
import numpy as np
from kokoro import KPipeline
import soundfile as sf
import torch
import time

import sounddevice as sd
import soundfile as sf

# 初始化 Kokoro 管道
# 'a' 表示美式英語, 'b' 表示英式英語
# 設定本地模型與 config 路徑
MODEL_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "src", "models", "tts_models"))

# print(torch.__config__.show())
# print(f"CUDA 是否可用: {torch.cuda.is_available()}")
# print(f"CUDA 版本: {torch.version.cuda}")
# print(f"cuDNN 版本: {torch.backends.cudnn.version()}")
# print(f"PyTorch 版本: {torch.__version__}")


# # 檢查 CUDA 是否可用
# print(f"CUDA 是否可用: {torch.cuda.is_available()}")
# if torch.cuda.is_available():
#     print(f"CUDA 設備數量: {torch.cuda.device_count()}")
#     print(f"當前 CUDA 設備: {torch.cuda.current_device()}")
#     print(f"CUDA 設備名稱: {torch.cuda.get_device_name(0)}")

# 創建一個測試張量並檢查它的設備
x = torch.randn(3, 3)
print(f"張量 x 的設備: {x.device}")  # 如果顯示 'cpu'，表示不是在 GPU 上

# 將張量移到 GPU (如果可用)
if torch.cuda.is_available():
    x = x.to('cuda')
    print(f"移至 GPU 後，張量 x 的設備: {x.device}")


# 初始化 Kokoro，指定本地模型與 config.json
pipeline = KPipeline(lang_code='a')

# 測試文本
text = "Well, I am not quite sure what do you mean. Could you try to be more specific?"
# 生成語音
    # 直接從文件加載語音模型
voice_path = os.path.join(MODEL_DIR, "voices/af_heart.pt")  # 假設您有這個文件
voice_tensor = torch.load(voice_path, weights_only=True)
if os.path.exists(voice_path):
    generator = pipeline(
        text,
        voice=voice_tensor,
        speed=1.0
        )
else:
    print("failed")
    exit
# 處理生成的音頻

all_audio = []
start_time = time.time()

for i, (graphemes, phonemes, audio) in enumerate(generator):
    print(f"Generated audio segment {i+1}")
    print(f"Text: {graphemes}")
    print(f"Phonemes: {phonemes}")
    
    # 收集所有音頻數據
    all_audio.append(audio)

# 合併所有音頻片段
full_audio = np.concatenate(all_audio)

# 保存成一個完整的文件
audio_file = 'test_kokoro_full_output.wav'
sf.write(audio_file, full_audio, 24000)
end_time = time.time()
elapsed_time = end_time - start_time
print(f"音頻生成花費時間: {elapsed_time:.2f} 秒")
print("語音生成成功，已保存音頻文件")


# 讀取 WAV 檔
audio_file = "test_kokoro_full_output.wav"
data, samplerate = sf.read(audio_file)

# 播放音檔
sd.play(data, samplerate)
sd.wait()  # 等待播放完成