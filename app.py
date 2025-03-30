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

# 初始化會話狀態
if "messages" not in st.session_state:
    st.session_state.messages = []
if "conversation_id" not in st.session_state:
    st.session_state.conversation_id = str(uuid.uuid4())
if "audio_bytes" not in st.session_state:
    st.session_state.audio_bytes = None
if "transcript" not in st.session_state:
    st.session_state.transcript = ""
if "realtime_response" not in st.session_state:
    st.session_state.realtime_response = ""
if "processed_audio" not in st.session_state:
    st.session_state.processed_audio = False
if "play_requested" not in st.session_state:
    st.session_state.play_requested = False
if "recorder_key_counter" not in st.session_state:
    st.session_state.recorder_key_counter = 0 

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

def play_audio_bytes(audio_bytes: bytes):
    """
    播放音頻字節數據 - 使用 HTML 播放器
    
    Args:
        audio_bytes: 音頻數據的二進制內容
    """
    try:
        # 使用 HTML audio 標籤直接播放
        audio_b64 = base64.b64encode(audio_bytes).decode('utf-8')
        audio_html = f"""
        <audio controls autoplay>
          <source src="data:audio/webm;base64,{audio_b64}" type="audio/webm">
          您的瀏覽器不支持音頻播放。
        </audio>
        """
        st.markdown(audio_html, unsafe_allow_html=True)
    
    except Exception as e:
        st.error(f"播放音頻錯誤: {str(e)}")

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

def chat_with_llm(message: str) -> Optional[str]:
    """
    與LLM模型進行對話 - API端點已經處理了TTS，並支持SSE來獲取實時回應
    
    Args:
        message: 用戶消息
        scenario: 對話情境
        
    Returns:
        模型回應
    """
    try:
        # 準備請求數據
        payload = {
            "message": message,
            "conversation_id": st.session_state.conversation_id,
            "context": [{"role": m["role"], "content": m["content"]} for m in st.session_state.messages],
            #"scenario": scenario
        }
        
        # 清空實時回應
        st.session_state.realtime_response = ""
        
        # 使用SSE獲取流式回應
        response_placeholder = st.empty()
        
        with st.spinner("AI正在思考並生成回應..."):
            # 嘗試使用SSE流式獲取回應
            try:
                import sseclient
                url = f"{API_URL}/api/stream_llm"
                headers = {"Content-Type": "application/json"}
                response = requests.post(url, json=payload, headers=headers, stream=True)

                response = requests.post(f"{API_URL}/api/llm", json=payload)
                response.raise_for_status()
                result = response.json()
                return result.get("response", "")

                # if response.status_code == 200:
                #     client = sseclient.SSEClient(response)
                #     full_response = ""
                
                # for event in client.events():
                #     print(event.data)
                #     try:
                #         data = json.loads(event.data)
                #         chunk = data.get("chunk", "")
                #         done = data.get("done", False)
                        
                #         if "error" in data:
                #             st.error(f"流式生成錯誤: {data['error']}")
                #             break
                        
                #         # 累積回應
                #         full_response += chunk
                #         st.session_state.realtime_response = full_response
                        
                #         # 實時更新顯示
                #         #esponse_placeholder.markdown(f"<div class='realtime-response'>{full_response}</div>", unsafe_allow_html=True)
                        
                #         if done:
                #             return full_response
                #     except json.JSONDecodeError:
                #         continue
                
                # # return full_response
                # else:
                #     # 如果SSE失敗，退回到標準API
                #     response = requests.post(f"{API_URL}/api/llm", json=payload)
                #     response.raise_for_status()
                #     result = response.json()
                #     return result.get("response", "")
            
            except Exception as sse_error:
                st.warning(f"流式回應失敗，使用標準API: {sse_error}")
                # 退回到標準API
                response = requests.post(f"{API_URL}/api/llm", json=payload)
                response.raise_for_status()
                result = response.json()
                return result.get("response", "")
        
    except Exception as e:
        st.error(f"與LLM對話錯誤: {str(e)}")
        return None

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
    role_name = "You" if role == "user" else "AI Teacher"
    safe_content = content.replace("</div>", "")
    message_html = f"""
    <div class="chat-message {role.replace('assistant', 'bot')}">
        <div class="message">
            <strong>{role_name}:</strong> {safe_content}
        </div>
    </div>
    """
    st.markdown(message_html, unsafe_allow_html=True)

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
    if not st.session_state.transcript:
        st.warning("請先錄音或輸入文本")
        return
    
    # 添加用戶消息
    user_message = st.session_state.transcript
    
    # 檢查最後一條消息是否也是用戶消息，如果是則不重複添加
    if not st.session_state.messages or st.session_state.messages[-1]["role"] != "user":
        st.session_state.messages.append({"role": "user", "content": user_message})
    
    # 獲取LLM回應 (後端已處理TTS)
    #bot_response = chat_with_llm(user_message, st.session_state.scenario)
    bot_response = chat_with_llm(user_message)

    if bot_response:
        # 添加AI回應
        st.session_state.messages.append({"role": "assistant", "content": bot_response})
    
    # 清空當前輸入
    st.session_state.transcript = ""
    st.session_state.processed_audio = False
    # 重新加載頁面以更新UI
    st.experimental_rerun()

def check_pronunciation():
    """檢查發音準確度"""
    if not st.session_state.audio_bytes or not st.session_state.transcript:
        st.warning("請先錄音並確保有轉錄文本")
        return
    
    # 獲取發音評估結果
    with st.spinner("評估發音中..."):
        result = evaluate_pronunciation(st.session_state.audio_bytes, st.session_state.transcript)
    
    if result:
        # 顯示發音反饋
        display_pronunciation_feedback(result)
        
        # 重置音頻數據（但保留文本以便再次練習）
        st.session_state.audio_bytes = None

def reset_conversation():
    """重置對話"""
    st.session_state.messages = []
    st.session_state.conversation_id = str(uuid.uuid4())
    st.session_state.transcript = ""
    st.session_state.audio_bytes = None
    st.experimental_rerun()

def on_scenario_change():
    """情境變更時重置對話"""
    reset_conversation()

# 主程序
def main():
    
    # 標題
    st.markdown(
        """
        <div class="title-container">
            <img src="https://via.placeholder.com/150?text=AI" alt="AI Teacher Logo">
            <h1 class="main-header">英語對話AI教師</h1>
        </div>
        """, 
        unsafe_allow_html=True
    )
    
    # 側邊欄
    with st.sidebar:
        st.header("設置")
        
        # 情境選擇 - 確保key是唯一的
        # scenarios = get_available_scenarios()
        # scenario_options = {k: v for k, v in scenarios.items()}
        
        # # 生成一個唯一的key
        # scenario_key = f"scenario_select_{int(time.time())}"
        
        # selected_scenario = st.selectbox(
        #     "選擇對話情境",
        #     options=list(scenario_options.keys()),
        #     format_func=lambda x: scenario_options[x],
        #     index=list(scenario_options.keys()).index(st.session_state.scenario) if st.session_state.scenario in scenario_options else 0,
        #     key=scenario_key,  # 使用唯一key
        #     on_change=on_scenario_change
        # )
        
        # # 只有當選擇變更時才更新會話狀態
        # if selected_scenario != st.session_state.scenario:
        #     st.session_state.scenario = selected_scenario
        


        # 錄音時間設置 - 同樣使用唯一key
        # duration_key = "duration_slider"
        # duration_value = st.slider(
        #     "最大錄音時間（秒）",
        #     min_value=10,
        #     max_value=60,
        #     value=st.session_state.max_recording_duration,
        #     step=5,
        #     key=duration_key
        # )
        # # 只有當值變更時才更新會話狀態
        # if duration_value != st.session_state.max_recording_duration:
        #     st.session_state.max_recording_duration = duration_value
        #     st.experimental_rerun()

        
        st.markdown("---")
        
        # 功能說明
        st.subheader("使用方法")
        st.markdown("""
        1. 選擇對話情境
        2. 點擊「開始錄音」按鈕說話
        3. 錄音完成後會自動轉錄並發送
        4. 可以使用「檢查發音」功能評估你的發音
        5. 使用「重置對話」開始新的對話
        """)
        
        st.markdown("---")
        
        # 重置按鈕 - 使用唯一key
        reset_key = f"reset_button_{int(time.time())}"
        if st.button("重置對話", type="primary", key=reset_key):
            reset_conversation()
    
    # 主界面分為兩列
    col1, col2 = st.columns([3, 1])
    
    # 對話歷史（左側）
    with col1:
        st.subheader("對話")
        
        chat_container = st.container()
        with chat_container:
            # 顯示對話歷史
            for message in st.session_state.messages:
                chat_message(message["role"], message["content"])
            
            # 顯示當前錄音/轉錄
            if st.session_state.transcript and not st.session_state.is_recording:
                st.markdown("#### 你的輸入:")
                
                # 使用唯一key
                textarea_key = f"transcript_editor_{int(time.time())}"
                edited_text = st.text_area(
                    "編輯文本 (如需要)",
                    value=st.session_state.transcript,
                    height=100,
                    key=textarea_key
                )
                
                # 只有當文本變更時才更新會話狀態
                if edited_text != st.session_state.transcript:
                    st.session_state.transcript = edited_text
            
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
            print('1')
            # 檢查是否有新的錄音數據
            if audio_data and audio_data['bytes'] is not None:
                # 如果尚未處理
                print('2')
                print(st.session_state.processed_audio)
                if not st.session_state.processed_audio:
                    st.write("正在處理錄音...")
                    print('3')

                    st.session_state.audio_bytes = audio_data['bytes']
                    # 標記為已處理
                    st.session_state.processed_audio = True
                    transcript = speech_to_text(st.session_state.audio_bytes)
                    if transcript:
                        st.session_state.transcript = transcript
                        st.success("轉錄成功！")
                        # 自動提交
                        st.session_state.recorder_key_counter += 1
                        submit_message()


            # 播放和檢查按鈕 - 使用唯一key
            col_play, col_check = st.columns(2)
            
            with col_play:
                play_button = st.button(
                    "播放錄音",
                    type="secondary",
                    disabled=not st.session_state.audio_bytes,
                    use_container_width=True,
                    key="play_button_fixed"
                )
                
                # 檢測按鈕點擊並設置標記
                if play_button:
                    st.session_state.play_requested = True
                
                # 檢查是否請求播放
                if st.session_state.play_requested and st.session_state.audio_bytes:
                    play_audio_bytes(st.session_state.audio_bytes)
                    st.session_state.play_requested = False
            
            # 發音檢查按鈕
            with col_check:
                pron_key = f"pronunciation_button_{int(time.time())}"
                pronunciation_button = st.button(
                    "檢查發音",
                    type="secondary",
                    disabled=not st.session_state.audio_bytes or not st.session_state.transcript,
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
                disabled=not st.session_state.transcript,
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
