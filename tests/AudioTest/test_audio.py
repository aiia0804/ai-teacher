import streamlit as st
import base64
import requests
import os
import time
import json
from io import BytesIO
import streamlit.components.v1 as components

# --- (頁面配置、創建目錄、獲取音頻函數 不變) ---
st.set_page_config(
    page_title="Streamlit 音頻播放測試",
    page_icon="🔊",
    layout="wide",
    initial_sidebar_state="expanded")
os.makedirs("audio", exist_ok=True)
@st.cache_data
def get_sample_audio():
    # ... (你的音頻下載邏輯) ...
    urls = [
        "https://samplelib.com/lib/preview/mp3/sample-3s.mp3",
        "https://samplelib.com/lib/preview/mp3/sample-6s.mp3",
        "https://samplelib.com/lib/preview/mp3/sample-9s.mp3"
    ]
    audio_files = []
    for i, url in enumerate(urls):
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            file_path = f"audio/sample_{i+1}.mp3"
            with open(file_path, "wb") as f:
                f.write(response.content)
            audio_files.append(file_path)
        except Exception as e:
            st.error(f"下載音頻 {url} 失敗: {e}")
    return audio_files

# --- (標題、側邊欄 不變) ---
st.title("Streamlit 音頻自動播放測試 (外部JS)")
st.markdown(f"Streamlit 版本: {st.__version__}")
with st.sidebar:
    # ... (你的側邊欄代碼) ...
    test_type = "HTML/JS 播放器測試 (推薦)" # 直接設置方便測試

# --- HTML/JS 播放器測試 ---
if test_type == "HTML/JS 播放器測試 (推薦)":
    st.header("HTML/JS 播放器測試 (使用外部 player.js)")

    st.info("""
    **運作方式**:
    1.  頁面加載時，讀取 `player.js` 文件內容並與播放器 HTML 一起注入。
    2.  `player.js` 初始化，獲取頁面元素，並設置事件監聽器和一個定時器。
    3.  點擊 Streamlit 的「添加音頻」按鈕，將音頻數據存儲在 `st.session_state` 中。
    4.  頁面重新渲染時，Python 檢測到 `session_state` 中有數據，將數據（JSON 格式）渲染到一個**隱藏的 `<div>` 元素**中。
    5.  `player.js` 中的定時器輪詢檢測到隱藏 `<div>` 中有數據，解析數據並將音頻添加到 JavaScript 內部隊列。
    6.  隱藏 `<div>` 的內容被清空，等待下一次數據傳遞。
    7.  使用者點擊播放器內的「▶️ 開始播放隊列」按鈕來啟動播放。
    """)

    # --- Session State 初始化 ---
    if 'audio_to_send' not in st.session_state:
        st.session_state.audio_to_send = [] # 用於存儲待發送給 JS 的數據

    # --- 獲取音頻文件 ---
    audio_files = get_sample_audio()

    # --- 添加按鈕邏輯 ---
    st.write("使用下面的按鈕將音頻添加到播放器的隊列中：")
    col1, col2, col3, col_all = st.columns(4)

    def add_audio_to_send_queue(index, name):
        if audio_files and index < len(audio_files):
            try:
                with open(audio_files[index], "rb") as f:
                    audio_bytes = f.read()
                    audio_b64 = base64.b64encode(audio_bytes).decode('utf-8')
                # 添加到 session_state 隊列
                st.session_state.audio_to_send.append({
                    "src": f"data:audio/mp3;base64,{audio_b64}",
                    "name": name
                })
                st.success(f"'{name}' 已準備好發送到 JavaScript。")
            except Exception as e:
                st.error(f"處理音頻 {index+1} 時出錯: {e}")
        else:
            st.warning(f"無法找到音頻文件索引 {index}。")

    # --- 按鈕定義 ---
    with col1:
        if st.button(f"添加音頻 1 ({os.path.basename(audio_files[0]) if audio_files else 'N/A'})", key="add_audio1"):
            add_audio_to_send_queue(0, f"示例音頻 1 ({os.path.basename(audio_files[0]) if audio_files else 'N/A'})")
    with col2:
        if st.button(f"添加音頻 2 ({os.path.basename(audio_files[1]) if len(audio_files)>1 else 'N/A'})", key="add_audio2"):
            add_audio_to_send_queue(1, f"示例音頻 2 ({os.path.basename(audio_files[1]) if len(audio_files)>1 else 'N/A'})")
    with col3:
        if st.button(f"添加音頻 3 ({os.path.basename(audio_files[2]) if len(audio_files)>2 else 'N/A'})", key="add_audio3"):
            add_audio_to_send_queue(2, f"示例音頻 3 ({os.path.basename(audio_files[2]) if len(audio_files)>2 else 'N/A'})")
    with col_all:
        if st.button("添加所有音頻", key="add_all"):
            if audio_files:
                for i, file in enumerate(audio_files):
                    add_audio_to_send_queue(i, f"示例音頻 {i+1} ({os.path.basename(file)})")
            else:
                st.warning("未能成功下載任何音頻文件。")

    st.markdown("---")

    # --- 讀取外部 JS 文件 ---
    js_code = ""
    try:
        with open("player.js", "r", encoding="utf-8") as f:
            js_code = f.read()
        st.write("成功讀取 player.js") # 調試信息
    except FileNotFoundError:
        st.error("錯誤：找不到 player.js 文件！請確保它與 app.py 在同一目錄或正確的路徑下。")
    except Exception as e:
        st.error(f"讀取 player.js 時發生錯誤: {e}")

    # --- 準備通信數據 ---
    comm_data_payload = None
    if st.session_state.audio_to_send:
        st.write(f"準備將 {len(st.session_state.audio_to_send)} 個音頻數據放入通信元素。") # 調試信息
        # 構建成 JS 需要的格式
        comm_data_payload = {
            "type": "ADD_AUDIO_BATCH",
            "payload": st.session_state.audio_to_send
        }
    comm_data_json = json.dumps(comm_data_payload) if comm_data_payload else ""


    # --- 播放器 HTML 結構 (包含通信 div 和 JS 注入) ---
    player_html = f"""
    <div style="margin: 20px 0; padding: 15px; border-radius: 10px; background-color: #f0f2f6; border: 1px solid #ddd;">
        <h3 style="color: #333;">持久音頻播放器 (外部 JS)</h3>
        <audio id="persistent-player" controls style="width:100%"></audio>
        <div style="margin-top: 15px; display: flex; align-items: center; gap: 15px;">
            <button id="start-queue-button" style="padding: 8px 15px; background-color: #007bff; color: white; border: none; border-radius: 5px; cursor: pointer;">
                ▶️ 開始播放隊列
            </button>
            <p id="player-status" style="margin: 0; color:#555; font-size: 0.9em;">等待操作...</p>
        </div>
        <div style="margin-top: 10px;">
            <h4 style="color: #333; font-size: 1em; margin-bottom: 5px;">播放隊列:</h4>
            <ul id="queue-list" style="list-style: none; padding-left: 0; max-height: 150px; overflow-y: auto; background-color: #fff; border: 1px solid #eee; border-radius: 5px; padding: 10px;">
                <li id="empty-queue-message">隊列為空</li>
            </ul>
        </div>

        <!-- 隱藏的通信 DIV，用於將數據從 Python 傳遞給 JS -->
        <div id="streamlit-comm" style="display:none;">{comm_data_json}</div>

        <!-- 注入外部 JS 代碼 -->
        <script>
            {js_code}
        </script>
    </div>
    """

    # --- 渲染組件 ---
    print('in')
    components.html(player_html, height=350)

    # --- 清空 session state (在數據渲染到 HTML 後) ---
    if st.session_state.audio_to_send:
        st.write("清空 session state 中的 audio_to_send") # 調試信息
        st.session_state.audio_to_send = []

    # --- 說明文字 ---
    st.markdown("""
    ### 如何運作 (外部 JS 版本)
    1.  Python 讀取 `player.js` 文件。
    2.  Python 將播放器的 HTML 結構和 `player.js` 的內容一起通過 `components.html` 渲染出來。
    3.  如果 `session_state` 中有待發送的音頻數據，這些數據會被序列化成 JSON 並直接放入 HTML 中一個隱藏的 `div#streamlit-comm` 元素裡。
    4.  瀏覽器加載 HTML，執行 `<script>` 標籤中的 `player.js` 代碼。
    5.  `player.js` 初始化，找到所有需要的 HTML 元素（包括隱藏的 `div#streamlit-comm`）。
    6.  `player.js` 立即檢查 `div#streamlit-comm` 中是否有初始數據，如果有就處理它（添加到內部隊列）並清空該 div。
    7.  `player.js` 啟動一個定時器 (`setInterval`)，定期檢查 `div#streamlit-comm` 是否又有新的內容（來自後續的 Streamlit 重新渲染）。
    8.  當使用者點擊 Streamlit 按鈕 -> Python 更新 `session_state` -> Streamlit 重新渲染 -> 新數據放入 `div#streamlit-comm` -> JS 定時器檢測到數據 -> JS 處理數據 -> JS 清空 `div`。
    9.  播放由 iframe 內的播放按鈕觸發。
    """)

# --- (頁腳 不變) ---
st.markdown("---")
st.caption("Streamlit 音頻測試環境 | 基於 Docker")