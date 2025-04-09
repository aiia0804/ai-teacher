import gradio as gr
import requests
import os
from functools import lru_cache
import time # 僅用於生成唯一文件名，避免衝突

# --- 常量和音頻下載 ---
AUDIO_DIR = "audio_gradio_queue"
os.makedirs(AUDIO_DIR, exist_ok=True)

SAMPLE_AUDIO_URLS = [
    {"name": "Sample 3s", "url": "https://samplelib.com/lib/preview/mp3/sample-3s.mp3"},
    {"name": "Sample 6s", "url": "https://samplelib.com/lib/preview/mp3/sample-6s.mp3"},
    {"name": "Sample 9s", "url": "https://samplelib.com/lib/preview/mp3/sample-9s.mp3"},
    {"name": "Sample 12s", "url": "https://samplelib.com/lib/preview/mp3/sample-12s.mp3"}, # 多加一個
]

@lru_cache(maxsize=1)
def download_sample_audio():
    """下載並緩存所有示例音頻文件，返回包含路徑和名稱的字典列表。"""
    print("Downloading sample audio...")
    audio_files_info = []
    downloaded_any = False
    for i, item in enumerate(SAMPLE_AUDIO_URLS):
        # 使用時間戳確保文件名稍微獨特，防止緩存問題（雖然 lru_cache 應該處理）
        timestamp = int(time.time() * 1000)
        file_name = f"sample_{i}_{timestamp}.mp3"
        file_path = os.path.join(AUDIO_DIR, file_name)
        try:
            # 即使有緩存，每次啟動時簡單下載以確保文件存在
            # (對於少量小文件，開銷不大)
            response = requests.get(item["url"], timeout=15)
            response.raise_for_status()
            with open(file_path, "wb") as f:
                f.write(response.content)
            audio_files_info.append({"name": item["name"], "path": file_path})
            downloaded_any = True
            print(f"Downloaded: {item['name']} to {file_path}")
        except Exception as e:
            print(f"Error downloading {item['name']} ({item['url']}): {e}")

    if not downloaded_any:
        print("Warning: Failed to download any sample audio.")
    return audio_files_info

# --- Gradio 輔助函數 ---

def get_queue_display_text(audio_queue):
    """生成用於顯示的隊列文本。"""
    if not audio_queue:
        return "播放隊列為空。"
    display_text = "隊列中 (下一個最先):\n"
    # 顯示部分隊列，避免過長
    max_display = 5
    for i, item in enumerate(audio_queue[:max_display]):
         # 從完整路徑中提取基礎文件名用於顯示
         base_name = os.path.basename(item.get("path", "未知路徑")) if isinstance(item, dict) else os.path.basename(item)
         display_text += f"{i+1}. {item.get('name', base_name)}\n" # 優先顯示 name
    if len(audio_queue) > max_display:
        display_text += f"... (還有 {len(audio_queue) - max_display} 個)"
    return display_text

# --- Gradio 應用邏輯 ---

# 1. 下載音頻文件
available_audio = download_sample_audio()

# 2. 定義 Gradio Blocks 界面
with gr.Blocks(title="Gradio Auto-Play Audio Queue", theme=gr.themes.Soft()) as demo:
    gr.Markdown("# Gradio 音頻自動播放隊列")
    gr.Markdown("點擊按鈕將音頻添加到隊列。播放器會嘗試自動播放隊列中的下一個音頻。")
    gr.Markdown(f"Gradio Version: {gr.__version__}")

    # 使用 gr.State 來保存隊列 (存儲包含名稱和路徑的字典)
    audio_queue_state = gr.State([])
    # 使用 gr.State 來跟蹤播放器是否"認為"自己正在播放（用於決定是否啟動下一個）
    # 注意：這不是完美的狀態跟蹤，因為我們無法從後端知道播放何時真正結束
    player_busy_state = gr.State(False)

    with gr.Row():
        with gr.Column(scale=1):
            gr.Markdown("### 添加音頻到隊列")
            # 為每個可用的音頻創建按鈕
            add_buttons = []
            if available_audio:
                for i, audio_info in enumerate(available_audio):
                    btn = gr.Button(f"添加: {audio_info['name']}", variant="secondary")
                    add_buttons.append(btn)
            else:
                gr.Warning("未能加載任何示例音頻，無法添加。")

            gr.Markdown("---")
            queue_display = gr.Textbox(label="播放隊列", lines=6, interactive=False, value="播放隊列為空。")

        with gr.Column(scale=2):
            gr.Markdown("### 音頻播放器")
            # streaming=False 因為我們是播放本地文件
            # interactive=True 允許用戶控制（如果自動播放失敗）
            # autoplay=False 初始不自動播放
            audio_player = gr.Audio(label="當前播放", type="filepath", autoplay=False, interactive=True, streaming=False)
            player_status = gr.Textbox(label="播放器狀態", value="空閒", interactive=False)


    # --- 事件處理函數 ---

    def add_to_queue_and_maybe_play(btn_index, current_queue, player_is_busy):
        """
        當按鈕被點擊時：
        1. 將對應的音頻信息添加到隊列 state。
        2. 更新隊列顯示。
        3. 如果播放器不忙，則觸發播放下一個。
        """
        if btn_index >= len(available_audio):
            print(f"Error: Invalid button index {btn_index}")
            return current_queue, get_queue_display_text(current_queue), player_is_busy # 返回未更改的狀態

        audio_info_to_add = available_audio[btn_index]
        print(f"Adding to queue: {audio_info_to_add['name']}")

        # 添加到隊列末尾
        current_queue.append(audio_info_to_add)
        queue_display_text = get_queue_display_text(current_queue)

        # 更新隊列狀態和顯示文本
        # 注意：我們還不能在這裡直接觸發播放，因為 play_next 需要知道更新後的隊列
        # 我們返回 player_is_busy 的當前值，play_next 會在 .then() 中被調用
        return current_queue, queue_display_text, player_is_busy


    def play_next_in_queue(current_queue, player_is_busy):
        """
        檢查隊列並嘗試播放下一首。
        由 add_to_queue_and_maybe_play().then() 或 audio_player.change().then() 調用。
        """
        print(f"play_next_in_queue called. Busy: {player_is_busy}, Queue size: {len(current_queue)}")

        if player_is_busy:
            print("Player is busy, not starting next track yet.")
            # 只更新顯示和狀態，不改變播放器
            return current_queue, player_is_busy, gr.update(), get_queue_display_text(current_queue), "播放中..."

        if not current_queue:
            print("Queue is empty, clearing player.")
            # 清空播放器，標記為不忙
            return current_queue, False, gr.update(value=None, label="空閒"), get_queue_display_text(current_queue), "空閒"

        # 從隊列頭部取出下一個音頻
        next_audio_info = current_queue.pop(0)
        next_audio_path = next_audio_info.get("path")
        next_audio_name = next_audio_info.get("name", os.path.basename(next_audio_path or "未知"))

        if not next_audio_path or not os.path.exists(next_audio_path):
            print(f"Error: Audio file not found or path missing for {next_audio_name}. Skipping.")
            # 文件不存在，標記為不忙，嘗試播放列表中的下一個（遞歸調用，但要小心無限循環，加個保護）
            # 這裡簡單處理：標記不忙，讓下一次事件觸發 play_next
            error_message = f"錯誤：找不到文件 {next_audio_name}"
            # 這裡不立即遞歸調用 play_next，避免潛在的無限循環
            # 等待下一次按鈕點擊或播放結束（如果能檢測到的話）再觸發
            return current_queue, False, gr.update(value=None, label=error_message), get_queue_display_text(current_queue), error_message


        print(f"Attempting to play next: {next_audio_name} from {next_audio_path}")
        queue_display_text = get_queue_display_text(current_queue) # 更新顯示文本（移除了當前播放的）

        # 更新播放器，設置 autoplay=True (效果依賴瀏覽器)
        # 同時標記播放器為"忙碌"
        # 返回更新後的所有狀態和組件值
        return (
            current_queue,                 # 更新後的隊列 state
            True,                          # 更新後的 player_busy state
            gr.update(value=next_audio_path, label=f"正在播放: {next_audio_name}", autoplay=True), # *** 使用 gr.update() ***
            queue_display_text,            # 更新隊列顯示文本框
            f"嘗試播放: {next_audio_name}" # 更新狀態文本框
        )

    # --- 綁定事件 ---
    if available_audio:
        for i, btn in enumerate(add_buttons):
            # 點擊添加按鈕後的操作鏈：
            # 1. 調用 add_to_queue_and_maybe_play 更新隊列和顯示
            # 2. 使用 .then() 在步驟 1 完成後，調用 play_next_in_queue 嘗試播放
            btn.click(
                fn=add_to_queue_and_maybe_play,
                inputs=[gr.State(i), audio_queue_state, player_busy_state], # 傳入按鈕索引和當前狀態
                outputs=[audio_queue_state, queue_display, player_busy_state] # 更新隊列狀態和顯示
            ).then(
                fn=play_next_in_queue,
                inputs=[audio_queue_state, player_busy_state], # 傳入更新後的隊列狀態和繁忙狀態
                outputs=[audio_queue_state, player_busy_state, audio_player, queue_display, player_status] # 更新所有相關組件和狀態
            )

    # --- (實驗性) 嘗試在播放器 '停止/改變' 時觸發播放下一個 ---
    # 這可能在用戶手動停止或音頻自然結束（但不保證能可靠觸發）時工作
    # `.change()` 通常在用戶上傳新文件時觸發，可能不適用於播放結束
    # `.stop()` 事件似乎更能代表停止，但可能需要 Gradio 較新版本
    # `.play()` 事件在播放開始時觸發
    # `.pause()` 事件在暫停時觸發
    # 我們這裡用 `.stop()` 試試，如果不行，可能需要用戶手動觸發下一個
    # 注意：如果 autoplay 成功，這個 stop 可能在預期之前觸發？需要測試。

    # 如果你想在播放停止（手動或可能自動結束）後嘗試播放下一個：
    def handle_player_stop(current_queue):
        print("handle_player_stop triggered.")
        # 當播放停止時，我們認為播放器不再忙碌，並嘗試播放下一個
        # 返回 False 來更新 player_busy_state
        return False # 只更新 busy 狀態，後續的 .then 會處理播放

    # 鏈：播放器停止 -> 更新 busy 狀態 -> 嘗試播放下一個
    # audio_player.stop( # 或者 .change() / .pause() 取決於哪個事件更接近“結束”
    #     fn=handle_player_stop,
    #     inputs=[], # 不需要輸入，只是觸發
    #     outputs=[player_busy_state] # 更新 busy 狀態為 False
    # ).then(
    #     fn=play_next_in_queue,
    #     inputs=[audio_queue_state, player_busy_state], # 傳入隊列和更新後的 busy 狀態
    #     outputs=[audio_queue_state, player_busy_state, audio_player, queue_display, player_status]
    # )
    # !! 上面的 .stop().then() 在實踐中可能不可靠，先註釋掉 !!
    # !! 主要依賴於添加按鈕後的 .then() 來啟動播放流程 !!

    gr.Markdown("---")
    gr.Markdown("""
    **工作原理:**
    1.  使用 `gr.State` 保存音頻文件路徑隊列 (`audio_queue_state`) 和一個表示播放器是否“忙碌”的標誌 (`player_busy_state`)。
    2.  點擊 "添加" 按鈕會觸發 `add_to_queue_and_maybe_play` 函數：
        *   將對應的音頻信息添加到 `audio_queue_state`。
        *   更新界面上的隊列顯示文本。
    3.  使用 `.then()` 方法，在 `add_to_queue_and_maybe_play` 完成後，立即調用 `play_next_in_queue` 函數。
    4.  `play_next_in_queue` 函數：
        *   檢查 `player_busy_state` 是否為 `False` 且隊列不為空。
        *   如果是，它會從隊列中取出第一個音頻。
        *   更新 `audio_queue_state`（移除已取出的）。
        *   更新 `player_busy_state` 為 `True`。
        *   更新 `gr.Audio` 組件，加載新的音頻文件路徑，並**嘗試**設置 `autoplay=True`。
        *   更新隊列顯示和狀態文本。
    5.  **關於自動播放:** 由於瀏覽器的限制，`autoplay=True` 在通過代碼更新 `gr.Audio` 時**可能不會生效**。如果音頻沒有自動播放，你需要手動點擊 `gr.Audio` 組件上的播放按鈕。
    6.  **播放結束檢測:** Gradio 目前沒有提供可靠的方式讓 Python 後端知道 `gr.Audio` 何時播放完成。因此，當一首音頻播放完畢後，需要再次點擊 "添加" 按鈕（即使是添加同一首）或其他觸發機制來啟動下一首的播放。
    """)

# --- 運行 Gradio 應用 ---
if __name__ == "__main__":
    print("Starting Gradio Audio Queue App...")
    demo.launch()