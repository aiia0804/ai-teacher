import streamlit as st
from streamlit_mic_recorder import mic_recorder
import requests
import json
import base64
import time
import io
import tempfile
import os
from typing import Dict, List, Optional, Any
import uuid
import sounddevice as sd
import soundfile as sf
import numpy as np
from pydub import AudioSegment
from pydub.playback import play
import queue
import wave
from PIL import Image
import streamlit.components.v1 as components
import threading
import asyncio
import requests

# 配置 Streamlit 頁面
st.set_page_config(
    page_title="英語對話AI教師",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 全局變數
API_URL = "http://localhost:8000"  # API 服務器URL
SAMPLE_RATE = 16000  # 錄音採樣率
DURATION = 10  # 錄音最大時間（秒）
MAX_TRANSCRIPT_LENGTH = 100  # 顯示的最大轉錄文本長度

def init_session_state():
    # 初始化對話歷史
    if "messages" not in st.session_state:
        st.session_state["messages"] = []
    
    # 初始化錄音狀態
    if "is_recording" not in st.session_state:
        st.session_state["is_recording"] = False
    
    # 初始化音頻播放列表
    if "audio_to_play" not in st.session_state:
        st.session_state["audio_to_play"] = []
        
    # 初始化音頻播放標記
    if "audio_bytes_to_play" not in st.session_state:
        st.session_state["audio_bytes_to_play"] = None
        
    # 初始化音頻播放計數器（用於強制重新渲染）
    if "audio_play_counter" not in st.session_state:
        st.session_state["audio_play_counter"] = 0
        
    # 初始化會話狀態
    if "conversation_id" not in st.session_state:
        st.session_state["conversation_id"] = str(uuid.uuid4())
    if "audio_bytes" not in st.session_state:
        st.session_state["audio_bytes"] = None
    if "transcript" not in st.session_state:
        st.session_state["transcript"] = ""
    if "realtime_response" not in st.session_state:
        st.session_state["realtime_response"] = ""
    if "processed_audio" not in st.session_state:
        st.session_state["processed_audio"] = False
    if "play_requested" not in st.session_state:
        st.session_state["play_requested"] = False
    if "audio_stream_active" not in st.session_state:
        st.session_state["audio_stream_active"] = False
    if "recorder_key_counter" not in st.session_state:
        st.session_state["recorder_key_counter"] = 0
    if "audio_permission_granted" not in st.session_state:
        st.session_state["audio_permission_granted"] = False

init_session_state()

audio_files_list = []

def get_theme_specific_css():
    theme = "lights"
    # 根據主題返回對應的 CSS
    if theme == "light":
        return """
        <style>
            color: #262730 !important;
            /* 亮色模式下的字體顏色 */
            .main-header { color: #4169E1 !important; }
            .chat-message {padding: 1.5rem; border-radius: 0.5rem; margin-bottom: 1rem; display: flex;}
            .chat-message.user { background-color: #f0f2f6; color: #262730;}
            .chat-message.bot {background-color: #e6f3ff; color: #262730;}
            .feedback-box { background-color: #f0f2f6; }
            .stSelectbox label, .stSelectbox div[data-baseweb="select"] {
            }
            div[data-baseweb="popover"] {
                background-color: #ffffff !important;
            }
        </style>
        """
    else:  # dark mode
        return """
        <style>
            /* 暗色模式下的字體顏色 */
            color: #FAFAFA !important;
            .main-header { color: #4D9FF5 !important; }
            .chat-message {padding: 1.5rem; border-radius: 0.5rem; margin-bottom: 1rem; display: flex;}
            .chat-message.user { background-color: #2D2D2D; color: #FAFAFA;}
            .chat-message.bot { background-color: #22252A; color: #FAFAFA;}
            .feedback-box { background-color: #2D2D2D; }
            .stSelectbox label, .stSelectbox div[data-baseweb="select"] {
            }
            div[data-baseweb="popover"] {
                background-color: #333333 !important;
            }
        </style>
        """

def autoplay_audio(audio_file):
    """
    自動播放音頻文件 - 使用Streamlit的音頻播放器
    
    Args:
        audio_file: 音頻文件路徑或音頻字節數據
    """
    try:
        print(f"嘗試播放音頻文件: {audio_file}")
        
        # 如果是文件路徑，則讀取文件內容
        if isinstance(audio_file, str) and os.path.exists(audio_file):
            with open(audio_file, "rb") as f:
                audio_bytes = f.read()
        else:
            # 假設已經是字節數據
            audio_bytes = audio_file
            
        # 使用base64編碼並創建帶有autoplay屬性的audio標籤
        audio_b64 = base64.b64encode(audio_bytes).decode('utf-8')
        audio_html = f"""
        <audio controls autoplay="true">
          <source src="data:audio/wav;base64,{audio_b64}" type="audio/wav">
          您的瀏覽器不支持音頻播放。
        </audio>
        """
        return audio_html
        
    except Exception as e:
        print(f"播放音頻錯誤: {str(e)}")
        import traceback
        print(traceback.format_exc())
        return None

# 將音頻文件添加到播放佇列
# 這個函數可以在任何線程中調用
# 但只會將音頻路徑添加到列表中，不會直接播放
# 實際播放會在主線程中進行

# 全局音頻播放列表
# 存儲需要播放的音頻文件路徑
# 主線程會定期檢查這個列表並播放新的音頻
# 這樣可以避免在後台線程中調用Streamlit函數

if "audio_to_play" not in st.session_state:
    st.session_state["audio_to_play"] = []

def speech_to_text(audio_bytes: bytes) -> Optional[str]:
    """
    將音頻轉換為文本
    
    Args:
        audio_bytes: 音頻數據的二進制內容
        
    Returns:
        轉錄文本
    """
    try:
        #print(audio_bytes)
        # 檢查音頻數據
        if not audio_bytes:
            st.error("無效的音頻數據")
            return None

        audio_base64 = base64.b64encode(audio_bytes).decode('utf-8')
        payload = {
            "audio_base64": audio_base64,
            "language": "en"
        }
        
        # 發送請求

        response = requests.post(f"{API_URL}/api/stt", json=payload, timeout=30)
        response.raise_for_status()
        result = response.json()
        
        if result.get("success", False):
            transcribed_text = result.get("text", "")
            if not transcribed_text:
                st.warning("未能識別任何語音，請重新嘗試")
                return None
            return transcribed_text
        else:
            st.error("轉錄失敗")
            return None
    
    except Exception as e:
        st.error(f"語音轉文本錯誤: {str(e)}")
        return None

def chat_with_llm(message: str) -> str:
    """
    與LLM模型進行對話 - API端點已經處理了TTS，並支持SSE來獲取實時回應
    
    Args:
        message: 用戶消息
        
    Returns:
        模型回應
    """
    try:
        # 停止任何正在進行的音頻流
        stop_tts_stream()
        
        # 等待一下確保音頻流已經停止
        time.sleep(0.5)
        
        # 啟動新的TTS流式接收
        start_tts_stream()
        
        # 準備請求數據
        payload = {
            "message": message,
            "conversation_id": st.session_state["conversation_id"],
            "context": st.session_state["messages"],
            "scenario": "general"
        }
        
        print(f"發送請求到LLM API: {message[:30]}...")
        
        # 使用標準API而不是流式生成
        response = requests.post(f"{API_URL}/api/llm", json=payload)
        response.raise_for_status()
        result = response.json()
        
        print(f"收到LLM回應，長度: {len(result.get('response', ''))} 字符")
        
        # 等待一段時間讓音頻流開始
        time.sleep(1.0)
        
        return result.get("response", "")
        
        # 使用SSE獲取實時回應
        with requests.post(
            f"{API_URL}/api/stream_llm",
            json=payload,
            stream=True,
            headers={"Accept": "text/event-stream"}
        ) as response:
            response.raise_for_status()
            
            # 重置實時回應
            st.session_state["realtime_response"] = ""
            full_response = ""
            
            # 處理SSE事件
            for line in response.iter_lines():
                if line:
                    line = line.decode('utf-8')
                    if line.startswith('data:'):
                        # 提取數據
                        data = line[5:].strip()
                        if data == "[DONE]":
                            break
                            
                        try:
                            # 解析JSON數據
                            event_data = json.loads(data)
                            if 'text' in event_data:
                                # 更新實時回應
                                text_chunk = event_data['text']
                                full_response += text_chunk
                                st.session_state["realtime_response"] = full_response
                        except json.JSONDecodeError:
                            # 如果不是JSON，直接添加
                            full_response += data
                            st.session_state["realtime_response"] = full_response
            
            # 返回完整回應
            return full_response
    
    except Exception as e:
        st.error(f"對話錯誤: {str(e)}")
        return f"抱歉，出現了錯誤: {str(e)}"

def text_to_speech(text: str) -> Optional[bytes]:
    """
    將文本轉換為語音
    
    Args:
        text: 要轉換的文本
        
    Returns:
        音頻數據的二進制內容
    """
    try:
        # 準備請求數據
        payload = {
            "text": text,
            "voice": "af_heart.pt",
            "speed": 1.0
        }
        
        # 發送請求
        response = requests.post(f"{API_URL}/api/tts", json=payload)
        response.raise_for_status()
        
        # 返回音頻數據
        return response.content
    
    except Exception as e:
        st.error(f"文本轉語音錯誤: {str(e)}")
        return None

# 創建全局變量以在線程之間共享狀態
is_connected_to_tts = False  # TTS流連接狀態
is_playing = False  # 音頻播放狀態
stop_event = threading.Event()  # 停止事件
audio_stream_threads = []  # 音頻流線程
audio_queue = queue.Queue()  # 音頻隊列

def start_tts_stream():
    """
    啟動TTS流式傳輸
    """
    global audio_queue, is_connected_to_tts, is_playing, stop_event, audio_stream_threads
    
    # 停止任何現有的音頻流
    stop_tts_stream()
    
    # 重置狀態
    stop_event.clear()
    audio_queue = queue.Queue()
    
    # 啟動接收線程
    receive_thread = threading.Thread(target=handle_tts_stream)
    receive_thread.daemon = True
    receive_thread.start()
    audio_stream_threads.append(receive_thread)
    
    # 啟動播放線程
    play_thread = threading.Thread(target=audio_player)
    play_thread.daemon = True
    play_thread.start()
    audio_stream_threads.append(play_thread)
    
    print("音頻流已啟動")

def stop_tts_stream():
    """
    停止TTS流式接收
    """
    global is_connected_to_tts, stop_event, audio_stream_threads, audio_queue
    
    # 設置停止標記
    stop_event.set()
    is_connected_to_tts = False
    st.session_state["audio_stream_active"] = False
    
    # 停止正在播放的音頻
    try:
        sd.stop()
    except:
        pass
    
    # 清空音頻隊列
    try:
        while not audio_queue.empty():
            audio_queue.get_nowait()
    except Exception:
        pass
    
    # 等待線程結束
    for thread in audio_stream_threads:
        if thread.is_alive():
            thread.join(timeout=0.5)
    
    # 清空線程列表
    audio_stream_threads.clear()

def handle_tts_stream():
    """處理TTS流式傳輸"""
    global audio_queue, is_connected_to_tts
    
    print("開始接收TTS流")
    is_connected_to_tts = True
    
    # 設置重試參數
    max_retries = 3
    retry_count = 0
    retry_delay = 1  # 初始重試延遲（秒）
    
    while retry_count < max_retries:
        try:
            # 創建一個新的會話以追蹤流數據
            import requests
            import json
            
            # 開始流式要求
            url = "http://localhost:8000/api/tts-stream"
            headers = {"Accept": "text/event-stream"}
            
            # 使用要求庫的流式功能
            response = requests.get(url, headers=headers, stream=True)
            
            # 確保連接成功
            if response.status_code != 200:
                print(f"連接到TTS流失敗: HTTP {response.status_code}")
                retry_count += 1
                time.sleep(retry_delay)
                retry_delay *= 2  # 指數延遲增加
                continue
            
            # 重置重試計數器
            retry_count = 0
            
            # 計算收到的片段數
            chunk_count = 0
            
            # 手動解析SSE流
            buffer = ""
            
            for chunk in response.iter_content(chunk_size=1024):
                if chunk:
                    # 將二進制轉換為文本
                    buffer += chunk.decode('utf-8')
                    
                    # 尋找完整的SSE事件
                    while "\n\n" in buffer:
                        event, buffer = buffer.split("\n\n", 1)
                        lines = event.split("\n")
                        
                        event_type = None
                        data = None
                        
                        for line in lines:
                            if line.startswith("event: "):
                                event_type = line[7:]
                            elif line.startswith("data: "):
                                data = line[6:]
                        
                        if event_type == "audio" and data:
                            try:
                                # 解析JSON數據
                                json_data = json.loads(data)
                                audio_base64 = json_data.get("audio")
                                
                                if audio_base64:
                                    # 將音頻數據放入隊列
                                    audio_queue.put(audio_base64)
                                    chunk_count += 1
                                    print(f"接收到音頻數據: {len(audio_base64)} 字節 (總計: {chunk_count} 個片段)")
                            except json.JSONDecodeError as e:
                                print(f"JSON解析錯誤: {str(e)}")
                            except Exception as e:
                                print(f"處理音頻數據出錯: {str(e)}")
                                import traceback
                                print(traceback.format_exc())
                        
                        elif event_type == "close":
                            print("服務器已關閉TTS流連接")
                            break
            
            # 如果到達這裡，表示連接已結束，但沒有錯誤
            break
        
        except requests.exceptions.ConnectionError as e:
            print(f"TTS流連接錯誤: {str(e)}")
            retry_count += 1
            print(f"嘗試重新連接 ({retry_count}/{max_retries})")
            time.sleep(retry_delay)
            retry_delay *= 2  # 指數延遲增加
        
        except Exception as e:
            print(f"TTS流處理出錯: {str(e)}")
            import traceback
            print(traceback.format_exc())
            break
    
    is_connected_to_tts = False
    print("結束接收TTS流")

# 創建一個目錄來存儲音頻文件
# 使用相對於應用程序的目錄，而不是臨時目錄
# 這樣我們可以通過網絡服務器提供檔案
# 定義音頻文件目錄
AUDIO_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static", "audio")

# 確保音頻目錄存在
def ensure_audio_directory():
    """確保音頻目錄存在，如果不存在則創建它"""
    if not os.path.exists(AUDIO_DIR):
        os.makedirs(AUDIO_DIR, exist_ok=True)
        print(f"Created audio directory: {AUDIO_DIR}")
    return AUDIO_DIR

# 掃描音頻文件
def scan_audio_files():
    """掃描音頻目錄中的所有音頻文件並更新列表"""
    global audio_files_list
    
    # 確保音頻目錄存在
    audio_dir = ensure_audio_directory()
    
    # 如果列表為空，則掃描目錄
    if not audio_files_list:
        # 從音頻目錄中讀取所有WAV文件
        if os.path.exists(audio_dir):
            wav_files = [f for f in os.listdir(audio_dir) if f.endswith('.wav')]
            print(f"Found {len(wav_files)} WAV files in {audio_dir}")
            
            # 按修改時間排序文件，最新的在前面
            wav_files.sort(key=lambda f: os.path.getmtime(os.path.join(audio_dir, f)), reverse=True)
            
            # 將文件添加到列表中
            for wav_file in wav_files:
                file_path = os.path.join(audio_dir, wav_file)
                # 確保文件存在且大小大於0
                if os.path.exists(file_path) and os.path.getsize(file_path) > 0:
                    audio_files_list.append({
                        'path': file_path,
                        'url': f'/static/audio/{wav_file}',
                        'timestamp': os.path.getmtime(file_path),
                        'format': 'audio/wav'
                    })
    
    return audio_files_list

# 初始化音頻文件列表
audio_files_list = scan_audio_files()

def audio_player():
    """音頻播放線程 - 將音頻數據存儲為文件供網頁播放"""
    global is_playing, audio_queue, stop_event, is_connected_to_tts, audio_files_list
    
    # 導入必要的庫
    import numpy as np
    import base64
    import io
    import time
    import wave
    
    print("音頻播放線程已啟動 - 將音頻存儲為文件供網頁播放")
    
    # 設置音頻參數
    sample_rate = 24000  # 預設采樣率
    
    # 設置空隊列計數器
    empty_count = 0
    max_empty_count = 50  # 最多等待50次空隊列
    
    try:
        while not stop_event.is_set():
            if not audio_queue.empty():
                # 從隊列中取出音頻數據
                audio_data = audio_queue.get()
                
                # 重置空隊列計數器
                empty_count = 0
                
                try:
                    # 解碼音頻數據
                    audio_bytes = base64.b64decode(audio_data)
                    
                    print(f"準備處理音頻: {len(audio_bytes)} 字節")
                    
                    # 直接將字節轉換為 NumPy 數組
                    audio_np = np.frombuffer(audio_bytes, dtype=np.float32)
                    
                    # 確保數組不為空
                    if len(audio_np) > 0:
                        # 直接使用WAV格式，避免轉換問題
                        audio_filename = f"audio_{int(time.time())}_{uuid.uuid4().hex[:8]}.wav"
                        audio_path = os.path.join(AUDIO_DIR, audio_filename)
                        
                        # 將NumPy數組轉換為WAV格式並存儲為文件
                        with wave.open(audio_path, 'wb') as wav_file:
                            wav_file.setnchannels(1)  # 單聲道
                            wav_file.setsampwidth(4)  # 32位/8 = 4字節
                            wav_file.setframerate(sample_rate)
                            
                            # 將float32轉換為int32
                            # 先將範圍從[-1, 1]縮放到[-2^31, 2^31-1]
                            scaled = np.int32(audio_np * 2147483647)
                            wav_file.writeframes(scaled.tobytes())
                        
                        # 更新全局音頻文件路徑
                        is_playing = True
                        print(f"已處理音頻並存儲為WAV文件: {audio_path}")
                        
                        # 將音頻文件路徑添加到全局列表中
                        # 使用相對路徑，方便後續通過網絡訪問
                        relative_path = f"/static/audio/{audio_filename}"
                        
                        # 添加到全局列表
                        audio_files_list.append({
                            'path': audio_path,
                            'url': relative_path,
                            'timestamp': time.time(),
                            'format': 'audio/wav'
                        })
                        
                        # 將音頻文件讀取為二進制數據並保存到會話狀態
                        try:
                            # 讀取音頻文件
                            with open(audio_path, "rb") as f:
                                audio_bytes = f.read()
                                
                            # 保存到會話狀態，讓主線程可以播放
                            st.session_state["audio_bytes_to_play"] = audio_bytes
                            # 增加計數器以強制重新渲染
                            st.session_state["audio_play_counter"] += 1
                            
                            print(f"已將音頻數據保存到會話狀態，等待主線程播放: {audio_path}")
                            
                            # 強制Streamlit重新運行以播放音頻
                            # 注意：這裡不能直接調用st.experimental_rerun()，因為在線程中不能調用Streamlit函數
                        except Exception as e:
                            print(f"處理音頻數據出錯: {str(e)}")
                            import traceback
                            print(traceback.format_exc())
                        
                        is_playing = False
                        print(f"音頻文件已添加到播放列表，當前列表長度: {len(audio_files_list)}")
                    else:
                        print("音頻數據為空，跳過處理")
                    
                except Exception as e:
                    print(f"播放音頻出錯: {str(e)}")
                    import traceback
                    print(traceback.format_exc())
                    is_playing = False
            else:
                # 如果隊列為空，等待一段時間
                empty_count += 1
                
                # 如果連續多次空隊列，且音頻流已停止，則退出
                if empty_count > max_empty_count and not is_connected_to_tts:
                    print(f"連續 {max_empty_count} 次空隊列且音頻流已停止，結束播放線程")
                    break
                
                time.sleep(0.1)
    except Exception as e:
        print(f"音頻播放線程出錯: {str(e)}")
        import traceback
        print(traceback.format_exc())
    finally:
        is_playing = False
        print("音頻播放線程結束")

def evaluate_pronunciation(audio_bytes: bytes, text: str) -> Optional[Dict[str, Any]]:
    """
    評估發音準確度
    
    Args:
        audio_bytes: 音頻數據的二進制內容
        text: 參考文本
        
    Returns:
        評估結果
    """
    try:
        # 準備請求數據
        audio_base64 = base64.b64encode(audio_bytes).decode('utf-8')
        payload = {
            "audio_base64": audio_base64,
            "text": text
        }
        
        # 發送請求
        response = requests.post(f"{API_URL}/api/pronunciation", json=payload)
        response.raise_for_status()
        result = response.json()
        
        if result.get("success", False):
            return result
        else:
            st.error("發音評估失敗")
            return None
    
    except Exception as e:
        st.error(f"發音評估錯誤: {str(e)}")
        return None

def get_available_scenarios() -> Dict[str, str]:
    """
    獲取可用的對話情境
    
    Returns:
        情境字典 {id: description}
    """
    try:
        response = requests.get(f"{API_URL}/api/scenarios")
        response.raise_for_status()
        result = response.json()
        
        if result.get("success", False):
            return result.get("scenarios", {})
        else:
            return {"general": "General English Conversation"}
    
    except Exception as e:
        st.warning(f"無法獲取情境列表: {str(e)}")
        return {"general": "General English Conversation"}

def chat_message(role: str, content: str):
    """
    顯示聊天消息
    
    Args:
        role: 消息角色 (user/assistant)
        content: 消息內容
    """
    role_class = "user" if role == "user" else "bot"
    avatar = "👤" if role == "user" else "🤖"
    
    # 使用HTML和CSS來美化消息顯示
    st.markdown(
        f"<div class='chat-message {role_class}'>"
        f"<div style='display: flex; align-items: flex-start;'>"
        f"<div style='font-size: 1.5em; margin-right: 10px;'>{avatar}</div>"
        f"<div>{content}</div>"
        f"</div></div>",
        unsafe_allow_html=True
    )

def display_pronunciation_feedback(result: Dict[str, Any]):
    """
    顯示發音評估反饋
    
    Args:
        result: 評估結果
    """
    similarity = result.get("similarity", 0)
    feedback = result.get("feedback", "")
    original_text = result.get("original_text", "")
    transcribed_text = result.get("transcribed_text", "")
    
    # 根據相似度選擇樣式
    score_class = ""
    if similarity > 90:
        score_class = "excellent"
    elif similarity > 70:
        score_class = "good"
    elif similarity > 50:
        score_class = "fair"
    else:
        score_class = "poor"
    
    st.markdown(f"""
    <div class="feedback-box">
        <h3>Pronunciation Feedback</h3>
        <div class="pronunciation-score {score_class}">
            Score: {similarity:.1f}%
        </div>
        <p><strong>Your text:</strong> {original_text}</p>
        <p><strong>What AI heard:</strong> {transcribed_text}</p>
        <p><strong>Feedback:</strong> {feedback}</p>
    </div>
    """, unsafe_allow_html=True)
    st.experimental_rerun()

def submit_message():
    """提交消息並獲取回應 - TTS現在在後端處理"""
    if not st.session_state["transcript"]:
        return
        
    # 停止任何正在進行的音頻流
    stop_tts_stream()
    
    # 獲取用戶消息
    user_message = st.session_state["transcript"]
    
    # 添加用戶消息到聊天歷史
    st.session_state["messages"].append({"role": "user", "content": user_message})
    
    # 顯示用戶消息
    chat_message("user", user_message)
    
    # 清空輸入框
    st.session_state["transcript"] = ""
    st.session_state["audio_bytes"] = None
    st.session_state["processed_audio"] = False
    
    # 獲取AI回應
    with st.spinner("AI思考中..."):
        ai_response = chat_with_llm(user_message)
    
    # 添加AI回應到聊天歷史
    st.session_state["messages"].append({"role": "assistant", "content": ai_response})
    
    # 顯示AI回應
    chat_message("assistant", ai_response)
    
    # 重置實時回應
    st.session_state["realtime_response"] = ""
    
    # 添加自動播放容器（簡化版）
    st.markdown('<div id="auto-play-container"></div>', unsafe_allow_html=True)
    
    # 強制重新渲染頁面以顯示新的對話
    st.experimental_rerun()

def check_pronunciation():
    """檢查發音準確度"""
    if not st.session_state["audio_bytes"] or not st.session_state["transcript"]:
        st.warning("請先錄音並確保有轉錄文本")
        return
    
    # 評估發音
    with st.spinner("正在評估發音..."):
        result = evaluate_pronunciation(
            st.session_state["audio_bytes"],
            st.session_state["transcript"]
        )
    
    if result:
        # 顯示評估結果
        display_pronunciation_feedback(result)
        
        # 重置音頻數據（但保留文本以便再次練習）
        st.session_state["audio_bytes"] = None

def reset_conversation():
    """重置對話"""
    # 停止任何正在進行的音頻流
    stop_tts_stream()
    
    # 重置會話狀態
    st.session_state["messages"] = []
    st.session_state["conversation_id"] = str(uuid.uuid4())
    st.session_state["audio_bytes"] = None
    st.session_state["transcript"] = ""
    st.session_state["realtime_response"] = ""
    
    print("對話已重置")

def on_scenario_change():
    """情境變更時重置對話"""
    reset_conversation()

# 創建一個自動更新的HTML音頻播放器
def create_audio_player():
    """創建一個自動更新的HTML音頻播放器"""
    # 創建一個唯一的ID來識別音頻元素
    audio_id = f"audio-player-{int(time.time())}"
    
    # 創建一個自動更新的JavaScript代碼
    js_code = f"""
    <div id="audio-container-{audio_id}"></div>
    <script>
        // 定義一個函數來檢查新的音頻數據
        function checkForNewAudio() {{
            fetch('/api/check-audio')
                .then(response => response.json())
                .then(data => {{
                    if (data.has_audio) {{
                        // 如果有新的音頻，創建一個新的音頻元素並播放
                        const audioContainer = document.getElementById('audio-container-{audio_id}');
                        const audioElement = document.createElement('audio');
                        audioElement.controls = true;
                        audioElement.autoplay = true;
                        audioElement.src = data.audio_url;
                        
                        // 清除之前的音頻元素
                        audioContainer.innerHTML = '';
                        audioContainer.appendChild(audioElement);
                    }}
                }})
                .catch(error => console.error('Error checking for audio:', error));
        }}
        
        // 每秒檢查一次新的音頻
        setInterval(checkForNewAudio, 1000);
    </script>
    """
    
    # 使用Streamlit的components模塊將JavaScript代碼嵌入頁面
    components.html(js_code, height=100)

# 創建一個路由來提供音頻文件
def serve_audio_file(file_path):
    """提供音頻文件下載"""
    if os.path.exists(file_path):
        with open(file_path, "rb") as f:
            audio_bytes = f.read()
        return audio_bytes
    return None

# 設置音頻權限和播放按鈕
def setup_audio_permissions():
    """設置音頻權限提示並顯示啟用按鈕"""
    # 確保會話狀態已初始化
    if "audio_permission_granted" not in st.session_state:
        st.session_state["audio_permission_granted"] = False
    
    # 如果音頻權限尚未授予
    if not st.session_state["audio_permission_granted"]:
        # 使用Streamlit的原生按鈕來啟用音頻
        if st.button("啟用音頻播放", type="primary", key="enable_audio_native"):
            # 直接設置權限狀態為已授予
            st.session_state["audio_permission_granted"] = True
            # 顯示成功消息
            st.success("音頻播放已啟用！你現在可以聽到AI教師的聲音。")
            # 使用適用於你的Streamlit版本的重新載入方法
            st.experimental_rerun()
        
        # 顯示說明
        st.info("要聽到AI教師的聲音，請點擊上方的按鈕來啟用音頻播放。")
    else:
        # 顯示成功消息
        st.success("音頻播放已啟用！你現在可以聽到AI教師的聲音。")
        
        # 使用JavaScript設置權限狀態
        js_code = """
        <script>
            window.audioPermissionGranted = true;
            console.log('Audio permission granted via session state');
            
            // 創建一個事件通知權限已授予
            if (typeof document.audioPermissionEvent === 'undefined') {
                document.audioPermissionEvent = new Event('audioPermissionGranted');
                document.dispatchEvent(document.audioPermissionEvent);
                console.log('Audio permission event dispatched');
            }
        </script>
        """
        st.markdown(js_code, unsafe_allow_html=True)

# 設置靜態文件服務
def setup_static_file_serving():
    """設置靜態文件服務，使音頻文件可以通過網絡訪問"""
    # 在HTML中嵌入一個音頻播放器和播放按鈕
    audio_player_html = """
    <div id="audio-player-container" style="margin-top: 10px;">
        <audio id="audio-player" controls style="width: 100%; display: none;"></audio>
        <div id="audio-controls" style="margin-top: 10px; display: none;">
            <button id="play-latest-audio" style="background-color: #4CAF50; color: white; border: none; padding: 8px 16px; border-radius: 4px; cursor: pointer; margin-right: 10px;">
                <span style="font-size: 16px;">▶</span> Play Latest Audio
            </button>
            <span id="audio-status" style="color: #666;"></span>
        </div>
    </div>
    
    <script>
        // 創建一個全局變量來記錄最新的音頻 URL
        if (!window.latestAudioUrl) {
            window.latestAudioUrl = '';
        }
        
        // 創建一個函數來播放音頻
        window.playAudio = function(audioUrl) {
            const player = document.getElementById('audio-player');
            const controls = document.getElementById('audio-controls');
            const status = document.getElementById('audio-status');
            
            // 更新最新的音頻 URL
            window.latestAudioUrl = audioUrl;
            
            // 顯示播放器和控制鈕
            player.style.display = 'block';
            controls.style.display = 'block';
            
            // 嘗試播放
            player.src = audioUrl;
            player.play().then(() => {
                console.log('Playing audio:', audioUrl);
                status.textContent = 'Playing...';
            }).catch(error => {
                console.error('Failed to play audio:', error);
                status.textContent = 'Click Play button to listen';
            });
            // 更新狀態
            status.textContent = 'New audio available';
            
            // 如果已經授權，嘗試自動播放
            if (window.audioPermissionGranted) {
                player.src = audioUrl;
                player.play().then(() => {
                    console.log('Playing audio:', audioUrl);
                    status.textContent = 'Playing...';
                }).catch(error => {
                    console.error('Failed to play audio:', error);
                    status.textContent = 'Click Play button to listen';
                });
            } else {
                status.textContent = 'Enable audio above, then click Play';
            }
            
            console.log('Audio URL set:', audioUrl);
        };
        
        // 監聽播放按鈕點擊事件
        document.addEventListener('DOMContentLoaded', function() {
            document.getElementById('play-latest-audio').addEventListener('click', function() {
                const player = document.getElementById('audio-player');
                const status = document.getElementById('audio-status');
                
                if (window.latestAudioUrl) {
                    player.src = window.latestAudioUrl;
                    player.play().then(() => {
                        console.log('Playing audio on button click:', window.latestAudioUrl);
                        status.textContent = 'Playing...';
                    }).catch(error => {
                        console.error('Failed to play audio on button click:', error);
                        status.textContent = 'Failed to play. Try again.';
                    });
                } else {
                    status.textContent = 'No audio available yet';
                }
            });
        });
        
        // 監聽音頻權限授予事件
        document.addEventListener('audioPermissionGranted', function() {
            const controls = document.getElementById('audio-controls');
            controls.style.display = 'block';
            window.audioPermissionGranted = true;
        });
    </script>
    """
    
    # 嵌入音頻播放器
    st.markdown(audio_player_html, unsafe_allow_html=True)

# 顯示所有可用的音頻文件
def display_available_audio_files():
    """顯示最新的音頻文件（簡化版）"""
    global audio_files_list
    
    # 重新掃描音頻文件
    audio_files_list = scan_audio_files()
    
    print(f"Audio files list now has {len(audio_files_list)} items")
    
    # 添加自動播放容器
    st.markdown('<div id="auto-play-container"></div>', unsafe_allow_html=True)
    
    # 只顯示最新的音頻文件（如果有）
    if audio_files_list:
        latest_audio = audio_files_list[-1]
        audio_path = latest_audio['path']
        
        if os.path.exists(audio_path):
            try:
                file_size = os.path.getsize(audio_path)
                if file_size > 0:
                    print(f"Latest audio file: {audio_path} (size: {file_size} bytes)")
                    # 不需要顯示音頻播放器，因為我們使用自動播放功能
            except Exception as e:
                print(f"Error checking audio file {audio_path}: {str(e)}")

# 檢查並播放音頻函數 - 簡化版
def check_and_play_audio():
    """檢查全局音頻文件列表 - 簡化版本"""
    global audio_files_list
    
    # 重新掃描音頻文件
    audio_files_list = scan_audio_files()
    
    # 只打印日誌信息
    if audio_files_list:
        print(f"Audio files available: {len(audio_files_list)}")
    
    return True
    # 返回 False 表示沒有音頻被播放
    return False

# 創建一個自動更新的音頻播放器
def create_auto_refresh_audio_player():
    """創建一個自動更新的音頻播放器"""
    # 創建一個唯一的ID來識別音頻元素
    if "audio_player_id" not in st.session_state:
        st.session_state["audio_player_id"] = f"audio-player-{int(time.time())}"
    
    # 創建一個自動更新的HTML元素
    audio_player_html = f"""
    <div id="audio-container-{st.session_state['audio_player_id']}"></div>
    <script>
        // 定義一個函數來檢查新的音頻文件
        function checkForNewAudio() {{
            // 如果有新的音頻文件，就創建一個新的音頻元素並播放
            var audioContainer = document.getElementById('audio-container-{st.session_state['audio_player_id']}');
            
            // 檢查是否有新的音頻文件
            if (window.latestAudioUrl && window.latestAudioUrl !== window.lastPlayedAudioUrl) {{
                // 創建一個新的音頻元素
                var audioElement = document.createElement('audio');
                audioElement.controls = true;
                audioElement.autoplay = true;
                audioElement.src = window.latestAudioUrl;
                
                // 清除之前的音頻元素
                audioContainer.innerHTML = '';
                audioContainer.appendChild(audioElement);
                
                // 更新最後播放的音頻 URL
                window.lastPlayedAudioUrl = window.latestAudioUrl;
                
                console.log('Playing new audio:', window.latestAudioUrl);
            }}
        }}
        
        // 初始化變量
        if (!window.lastPlayedAudioUrl) {{
            window.lastPlayedAudioUrl = '';
        }}
        
        // 每秒檢查一次新的音頻
        setInterval(checkForNewAudio, 500);
    </script>
    """
    
    # 使用Streamlit的components模塊將HTML代碼嵌入頁面
    components.html(audio_player_html, height=80)

# 創建一個路由來提供音頻文件
def serve_audio_files():
    """設置路由來提供音頻文件"""
    # 創建一個路由來提供音頻文件
    audio_route = st.markdown("""
    <script>
    // 設置一個路由來提供音頻文件
    if (!window.audioRoutesInitialized) {
        window.audioRoutesInitialized = true;
        
        // 創建一個自定義的音頻播放器
        const audioPlayer = document.createElement('audio');
        audioPlayer.id = 'global-audio-player';
        audioPlayer.controls = true;
        audioPlayer.style.display = 'none';
        document.body.appendChild(audioPlayer);
        
        // 創建一個全局函數來播放音頻
        window.playAudio = function(url) {
            console.log('Playing audio:', url);
            const player = document.getElementById('global-audio-player');
            player.src = url;
            player.play();
        };
    }
    </script>
    """, unsafe_allow_html=True)

# 設置靜態文件服務器
def setup_static_file_server():
    """設置靜態文件服務器以提供音頻文件訪問"""
    # 將靜態目錄診斷信息添加到頁面
    st.markdown(f"""
    <div style="display: none;" id="static-file-info">
        <p>Static directory: {AUDIO_DIR}</p>
        <p>Audio files count: {len(os.listdir(AUDIO_DIR)) if os.path.exists(AUDIO_DIR) else 0}</p>
    </div>
    """, unsafe_allow_html=True)
    
    # 創建一個路由來提供音頻文件
    # 注意：這裡我們使用JavaScript來創建一個簡單的路由處理程序
    js_code = f"""
    <script>
        // 創建一個全局變量來記錄音頻文件路徑
        window.audioFilePaths = {{}};  // 將在播放時填充
        
        // 創建一個函數來加載音頻文件
        window.loadAudioFile = function(audioPath) {{
            // 創建一個新的音頻元素
            const audioElement = document.createElement('audio');
            audioElement.controls = true;
            audioElement.autoplay = true;
            audioElement.src = audioPath;
            
            // 添加到文檔中
            const container = document.getElementById('audio-container');
            if (container) {{
                container.innerHTML = '';
                container.appendChild(audioElement);
            }} else {{
                const newContainer = document.createElement('div');
                newContainer.id = 'audio-container';
                newContainer.style.display = 'none';
                document.body.appendChild(newContainer);
                newContainer.appendChild(audioElement);
            }}
            
            return audioElement;
        }};
        
        // 創建一個函數來播放音頻
        window.playAudioFile = function(audioFileName) {{
            const audioPath = '/static/audio/' + audioFileName;
            const audioElement = window.loadAudioFile(audioPath);
            return audioElement;
        }};
    </script>
    """
    st.markdown(js_code, unsafe_allow_html=True)

# 主程序
def main():
    # 設置頁面標題和布局
    st.title("英語對話AI教師 🎓")
    st.markdown(get_theme_specific_css(), unsafe_allow_html=True)
    
    # 確保音頻目錄存在
    ensure_audio_directory()
    
    # 創建音頻自動播放容器
    st.markdown('<div id="auto-play-container"></div>', unsafe_allow_html=True)
    
    # 創建音頻播放容器
    audio_container = st.container()
    
    # 檢查是否有音頻需要播放
    if "audio_bytes_to_play" in st.session_state and st.session_state["audio_bytes_to_play"] is not None:
        try:
            # 使用Streamlit的原生音頻組件播放
            with audio_container:
                st.audio(st.session_state["audio_bytes_to_play"], format="audio/wav", autoplay=True)
                print(f"已播放音頻，計數器: {st.session_state['audio_play_counter']}")
            
            # 播放後清除，避免重複播放
            st.session_state["audio_bytes_to_play"] = None
        except Exception as e:
            print(f"播放音頻出錯: {str(e)}")
            import traceback
            print(traceback.format_exc())
    
    # 側邊欄
    with st.sidebar:
        st.header("設置")
        
        # 功能說明
        st.subheader("使用方法")
        st.markdown("""
        1. 點擊「開始錄音」按鈕說話
        2. 錄音完成後會自動轉錄並發送
        3. 可以使用「檢查發音」功能評估你的發音
        4. 使用「重置對話」開始新的對話
        """)
        
        st.markdown("---")
        
        # 重置按鈕
        reset_key = f"reset_button_{int(time.time())}"
        if st.button("重置對話", type="primary", key=reset_key):
            reset_conversation()
    
    # 創建兩列布局
    col1, col2 = st.columns([7, 3])
    
    # 聊天區域（左側）
    with col1:
        st.subheader("對話區域")
        
        # 顯示聊天歷史
        chat_container = st.container()
        with chat_container:
            # 顯示之前的消息
            for message in st.session_state["messages"]:
                chat_message(message["role"], message["content"])
            
            # 顯示輸入區域
            st.markdown("---")
            
            # 文本輸入框 - 可以編輯轉錄文本
            if st.session_state["transcript"]:
                edited_text = st.text_area(
                    "編輯或確認轉錄文本:", 
                    value=st.session_state["transcript"],
                    height=100,
                    key="transcript_editor"
                )
                if edited_text != st.session_state["transcript"]:
                    st.session_state["transcript"] = edited_text
            
            # 顯示實時回應 TODO make sure the real time reply work then resume this
            #if st.session_state.realtime_response:
                #st.markdown(f"<div class='realtime-response'>{st.session_state.realtime_response}</div>", unsafe_allow_html=True)
    
    # 控制面板（右側）
    with col2:
        st.subheader("控制面板")
        
        control_container = st.container()
        with control_container:
            # 使用 mic_recorder 組件
            micro_key = f"recorder_{st.session_state.recorder_key_counter}"
            audio_data = mic_recorder(
                key=micro_key,
                start_prompt="開始錄音",
                stop_prompt="停止錄音",
                use_container_width=True,
                format="webm"
            )
            # 檢查是否有新的錄音數據
            if audio_data and audio_data['bytes'] is not None:
                # 如果尚未處理
                if not st.session_state["processed_audio"]:
                    st.write("正在處理錄音...")
                    
                    # 設置音頻權限標記 - 這是關鍵步驟，因為用戶已經點擊停止錄音按鈕
                    st.session_state["audio_permission_granted"] = True
                    
                    # 激活音頻上下文並設置自動播放功能
                    st.markdown("""
                    <script>
                        (function() {
                            // 播放一個靜音音頻來激活音頻上下文
                            const silentAudio = new Audio();
                            silentAudio.src = 'data:audio/mpeg;base64,SUQzBAAAAAABEVRYWFgAAAAtAAADY29tbWVudABCaWdTb3VuZEJhbmsuY29tIC8gTGFTb25vdGhlcXVlLm9yZwBURU5DAAAAHQAAA1N3aXRjaCBQbHVzIMKpIE5DSCBTb2Z0d2FyZQBUSVQyAAAABgAAAzIyMzUAVFNTRQAAAA8AAANMYXZmNTcuODMuMTAwAAAAAAAAAAAAAAD/80DEAAAAA0gAAAAATEFNRTMuMTAwVVVVVVVVVVVVVUxBTUUzLjEwMFVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVf/zQsRbAAADSAAAAABVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVf/zQMSkAAADSAAAAABVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVV';
                            silentAudio.play().catch(e => console.log('Silent audio play error (ignorable):', e));
                            
                            // 設置全局標記
                            window.audioPermissionGranted = true;
                            console.log('Audio permission granted from recording interaction');
                            
                            // 設置監聽器來處理新增的音頻元素
                            const setupAutoPlayObserver = function() {
                                // 監聽新增的音頻元素
                                const observer = new MutationObserver(function(mutations) {
                                    mutations.forEach(function(mutation) {
                                        if (mutation.addedNodes) {
                                            mutation.addedNodes.forEach(function(node) {
                                                if (node.nodeName === 'AUDIO' || 
                                                   (node.nodeType === 1 && node.querySelector('audio'))) {
                                                    // 直接尋找音頻元素或其容器中的音頻元素
                                                    const audioElement = node.nodeName === 'AUDIO' ? 
                                                                       node : node.querySelector('audio');
                                                    if (audioElement) {
                                                        console.log('New audio element detected, attempting autoplay');
                                                        setTimeout(() => {
                                                            audioElement.play().catch(e => {
                                                                console.error('Autoplay failed:', e);
                                                            });
                                                        }, 500); // 稍後再嘗試播放，確保元素已完全加載
                                                    }
                                                }
                                            });
                                        }
                                    });
                                });
                                
                                // 監視整個文檔以捕獲新添加的音頻元素
                                observer.observe(document.body, { childList: true, subtree: true });
                                console.log('Audio autoplay observer enabled');
                                return observer;
                            };
                            
                            // 啟動監聽器
                            const observer = setupAutoPlayObserver();
                            
                            // 將監聽器存儲為全局變量，以避免垃圾回收
                            window.audioObserver = observer;
                        })();
                    </script>
                    """, unsafe_allow_html=True)
                    
                    st.session_state["audio_bytes"] = audio_data['bytes']
                    # 標記為已處理
                    st.session_state["processed_audio"] = True
                    transcript = speech_to_text(st.session_state["audio_bytes"])
                    if transcript:
                        st.session_state["transcript"] = transcript
                        st.success("轉錄成功！")
                        # 自動提交
                        st.session_state["recorder_key_counter"] += 1
                        submit_message()


            # 播放和檢查按鈕 - 使用唯一key
            col_play, col_check = st.columns(2)
            
            with col_play:
                play_button = st.button(
                    "播放錄音",
                    type="secondary",
                    disabled=not st.session_state["audio_bytes"],
                    use_container_width=True,
                    key="play_button_fixed"
                )
                
                # 檢測按鈕點擊並設置標記
                if play_button:
                    st.session_state["play_requested"] = True
                
                # 檢查是否請求播放
                if st.session_state["play_requested"] and st.session_state["audio_bytes"]:
                    # 直接使用Streamlit的audio組件播放
                    st.audio(st.session_state["audio_bytes"], format="audio/webm", autoplay=True)
                    st.session_state["play_requested"] = False
            
            # 發音檢查按鈕
            with col_check:
                pron_key = f"pronunciation_button_{int(time.time())}"
                pronunciation_button = st.button(
                    "檢查發音",
                    type="secondary",
                    disabled=not st.session_state["audio_bytes"] or not st.session_state["transcript"],
                    use_container_width=True,
                    key=pron_key
                )
                
                if pronunciation_button:
                    check_pronunciation()
            
            # 手動送出按鈕
            submit_key = f"submit_button_{int(time.time())}"
            submit_button = st.button(
                "手動送出",
                type="primary",
                disabled=not st.session_state["transcript"],
                use_container_width=True,
                key=submit_key
            )
            
            if submit_button:
                submit_message()
            
            # 顯示情境說明
            st.markdown("---")
            #st.markdown(f"**當前情境:** {scenario_options[st.session_state.scenario]}")
            st.markdown("與AI老師對話，練習你的英語口語能力！")

if __name__ == "__main__":
    main()
