import streamlit as st
import requests
import base64
import time
import os

st.title("音頻自動播放測試")

# 顯示Streamlit版本
st.write(f"Streamlit 版本: {st.__version__}")

# 創建臨時目錄
temp_dir = "temp_audio"
os.makedirs(temp_dir, exist_ok=True)

# 下載測試音頻
@st.cache_data
def get_test_audios():
    audio_urls = [
        "https://samplelib.com/lib/preview/mp3/sample-3s.mp3",
        "https://samplelib.com/lib/preview/mp3/sample-6s.mp3", 
        "https://samplelib.com/lib/preview/mp3/sample-9s.mp3"
    ]
    
    audio_files = []
    for i, url in enumerate(audio_urls):
        try:
            response = requests.get(url)
            response.raise_for_status()
            
            # 獲取音頻bytes
            audio_files.append(response.content)
            
        except Exception as e:
            st.error(f"下載音頻 {i+1} 失敗: {str(e)}")
    
    return audio_files

# 測試說明
st.markdown("""
## 最簡單的測試:
1. 點擊下方按鈕
2. 系統會將三個音頻合併為一個HTML音頻元素
3. 這樣可以確保音頻能連續播放
""")

# 按鈕測試
if st.button("播放合併音頻", type="primary"):
    with st.spinner("準備音頻中..."):
        # 獲取所有音頻
        audio_files = get_test_audios()
    
    if len(audio_files) == 3:
        # 為每個音頻創建base64編碼
        audio_b64_list = [base64.b64encode(audio).decode("utf-8") for audio in audio_files]
        
        # 顯示狀態
        st.info("音頻已加載，應該會自動開始播放")
        
        # 創建一個合併的HTML元素
        html_code = f"""
        <div style="margin: 20px 0;">
            <h3>自動播放測試</h3>
            <p id="audio-status">加載中...</p>
            
            <!-- 第一個可見的音頻元素 -->
            <audio id="combined-player" controls autoplay>
                <source src="data:audio/mp3;base64,{audio_b64_list[0]}" type="audio/mp3">
            </audio>
            
            <script>
                // 獲取DOM元素
                const player = document.getElementById('combined-player');
                const statusText = document.getElementById('audio-status');
                
                // 音頻列表
                const audioList = [
                    "data:audio/mp3;base64,{audio_b64_list[0]}",
                    "data:audio/mp3;base64,{audio_b64_list[1]}",
                    "data:audio/mp3;base64,{audio_b64_list[2]}"
                ];
                
                // 當前音頻索引
                let currentIndex = 0;
                
                // 播放音頻
                function playCurrentAudio() {{
                    statusText.textContent = `正在播放音頻 ${{currentIndex + 1}}/3`;
                    player.src = audioList[currentIndex];
                    player.play().catch(e => {{
                        statusText.textContent = `播放失敗: ${{e.message}}`;
                        console.error('播放失敗:', e);
                    }});
                }}
                
                // 當音頻播放結束時播放下一個
                player.addEventListener('ended', function() {{
                    currentIndex++;
                    if (currentIndex < audioList.length) {{
                        playCurrentAudio();
                    }} else {{
                        statusText.textContent = "所有音頻播放完畢";
                    }}
                }});
                
                // 嘗試播放第一個音頻
                playCurrentAudio();
            </script>
        </div>
        """
        
        # 顯示HTML
        st.markdown(html_code, unsafe_allow_html=True)
    else:
        st.error("無法下載所有測試音頻")

# 簡單的單個音頻測試
st.markdown("---")
st.subheader("單個音頻自動播放測試")

if st.button("測試單個音頻自動播放"):
    # 獲取一個音頻
    audio_files = get_test_audios()
    if audio_files:
        # 顯示原生音頻元素
        st.audio(audio_files[0], format="audio/mp3", autoplay=True)