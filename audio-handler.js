/**
 * 音頻處理模塊 - 處理錄音和音頻播放
 */
class AudioHandler {
    constructor() {
        this.mediaRecorder = null;
        this.audioChunks = [];
        this.audioBlob = null;
        this.isRecording = false;
        this.stream = null;
        this.audioContext = null;
        this.SAMPLE_RATE = 16000;
        this.audioPermissionGranted = false;

        // 流式音頻相關
        this.streamingAudioChunks = [];
        this.isPlayingStreamingAudio = false;
        this.audioQueue = [];
    }

    /**
     * 請求音頻權限
     * @returns {Promise<boolean>} - 是否獲得權限
     */
    async requestPermission() {
        try {
            this.stream = await navigator.mediaDevices.getUserMedia({ audio: true });
            this.audioPermissionGranted = true;

            // 創建音頻上下文
            this.audioContext = new (window.AudioContext || window.webkitAudioContext)();

            return true;
        } catch (error) {
            console.error('無法獲取麥克風權限:', error);
            return false;
        }
    }

    /**
     * 開始錄音
     * @returns {Promise<boolean>} - 是否成功開始錄音
     */
    async startRecording() {
        if (!this.audioPermissionGranted) {
            const hasPermission = await this.requestPermission();
            if (!hasPermission) return false;
        }

        try {
            this.audioChunks = [];

            // 確保有流
            if (!this.stream) {
                this.stream = await navigator.mediaDevices.getUserMedia({ audio: true });
            }

            // 創建MediaRecorder
            this.mediaRecorder = new MediaRecorder(this.stream);

            // 設置數據可用時的回調
            this.mediaRecorder.ondataavailable = (event) => {
                if (event.data.size > 0) {
                    this.audioChunks.push(event.data);
                }
            };

            // 設置錄音停止時的回調
            this.mediaRecorder.onstop = () => {
                this.audioBlob = new Blob(this.audioChunks, { type: 'audio/webm' });
                this.isRecording = false;
            };

            // 開始錄音
            this.mediaRecorder.start();
            this.isRecording = true;

            return true;
        } catch (error) {
            console.error('開始錄音時出錯:', error);
            return false;
        }
    }

    /**
     * 停止錄音
     * @returns {Promise<Blob>} - 錄音數據
     */
    async stopRecording() {
        return new Promise((resolve, reject) => {
            if (!this.mediaRecorder || this.mediaRecorder.state === 'inactive') {
                reject(new Error('沒有進行中的錄音'));
                return;
            }

            this.mediaRecorder.onstop = () => {
                this.audioBlob = new Blob(this.audioChunks, { type: 'audio/webm' });
                this.isRecording = false;
                resolve(this.audioBlob);
            };

            this.mediaRecorder.stop();
        });
    }

    /**
     * 播放音頻
     * @param {Blob|string} audioData - 音頻數據或音頻URL
     * @returns {Promise<void>}
     */
    async playAudio(audioData) {
        try {
            const audioPlayer = document.getElementById('audio-player');

            if (!audioPlayer) {
                throw new Error('找不到音頻播放器元素');
            }

            // 處理不同類型的輸入
            if (audioData instanceof Blob) {
                audioPlayer.src = URL.createObjectURL(audioData);
            } else if (typeof audioData === 'string') {
                audioPlayer.src = audioData;
            } else {
                throw new Error('不支持的音頻數據類型');
            }

            document.getElementById('audio-player-container').style.display = 'block';

            // 嘗試播放
            try {
                await audioPlayer.play();
            } catch (playError) {
                console.warn('自動播放失敗，需要用戶交互:', playError);
            }
        } catch (error) {
            console.error('播放音頻時出錯:', error);
            throw error;
        }
    }

    /**
     * 自動播放音頻
     * @param {Blob} audioBlob - 音頻數據
     */
    autoplayAudio(audioBlob) {
        try {
            // 創建一個新的自動播放音頻元素
            const audioUrl = URL.createObjectURL(audioBlob);
            const audioElement = document.createElement('audio');
            audioElement.src = audioUrl;
            audioElement.autoplay = true;

            // 播放完成後清理
            audioElement.onended = () => {
                URL.revokeObjectURL(audioUrl);
                audioElement.remove();
            };

            // 添加到容器中
            const container = document.getElementById('auto-play-container');
            container.innerHTML = '';
            container.appendChild(audioElement);

            // 嘗試播放
            audioElement.play().catch(e => {
                console.warn('自動播放失敗，可能需要用戶交互:', e);
                // 顯示一個播放按鈕作為備選方案
                this.createPlayButton(audioUrl, container);
            });
        } catch (error) {
            console.error('自動播放音頻時出錯:', error);
        }
    }

    /**
     * 處理流式音頻數據
     * @param {string} audioBase64 - Base64編碼的音頻數據
     */
    handleStreamingAudioChunk(audioBase64) {
        try {
            // 檢查Base64數據是否有效
            if (!audioBase64 || audioBase64.trim() === '') {
                console.warn('收到空的Base64音頻數據');
                return;
            }

            // 直接將Base64音頻數據存儲到隊列中
            this.audioQueue.push(audioBase64);

            // 如果沒有在播放，開始播放
            if (!this.isPlayingStreamingAudio) {
                this.playNextAudioChunk();
            }
        } catch (error) {
            console.error('處理音頻流時出錯:', error);
        }
    }

    /**
     * 播放下一個音頻塊
     */
    async playNextAudioChunk() {
        if (this.audioQueue.length === 0) {
            this.isPlayingStreamingAudio = false;
            return;
        }

        this.isPlayingStreamingAudio = true;

        try {
            // 取出下一個Base64音頻數據
            const audioBase64 = this.audioQueue.shift();
            
            // 準備音頻數據 - 使用WAV格式
            const audioSrc = `data:audio/wav;base64,${audioBase64}`;
            
            // 創建音頻元素
            const audioElement = document.createElement('audio');
            audioElement.src = audioSrc;
            
            // 設置音頻屬性
            audioElement.controls = false;  // 不顯示控制項

            // 設置播放完成的回調
            audioElement.onended = () => {
                audioElement.remove();
                // 繼續播放下一個
                this.playNextAudioChunk();
            };

            // 發生錯誤時的回調
            audioElement.onerror = (e) => {
                console.error('音頻播放錯誤:', e);
                audioElement.remove();
                // 繼續嘗試下一個
                this.playNextAudioChunk();
            };

            // 將音頻元素添加到容器
            const container = document.getElementById('auto-play-container');
            container.appendChild(audioElement);

            // 調試信息
            console.log('開始播放WAV音頻片段，數據長度:', audioBase64.length);

            // 播放音頻
            await audioElement.play().catch(e => {
                console.warn('流式音頻播放失敗:', e);
                // 如果是自動播放被阻止的錯誤，試著創建一個播放按鈕
                if (e.name === 'NotAllowedError') {
                    console.log('自動播放被阻止，創建播放按鈕');
                    this.createPlayButton(audioSrc, container);
                }
                // 繼續下一個
                setTimeout(() => this.playNextAudioChunk(), 100);
            });
        } catch (error) {
            console.error('播放流式音頻時出錯:', error);
            // 如果出錯，嘗試下一個
            setTimeout(() => this.playNextAudioChunk(), 100);
        }
    }

    /**
     * 清空音頻隊列
     */
    clearAudioQueue() {
        this.audioQueue = [];
        this.isPlayingStreamingAudio = false;

        // 清空音頻容器
        const container = document.getElementById('auto-play-container');
        if (container) {
            container.innerHTML = '';
        }
    }

    /**
     * 創建播放按鈕（作為自動播放的備選方案）
     * @param {string} audioUrl - 音頻URL
     * @param {HTMLElement} container - 容器元素
     */
    createPlayButton(audioUrl, container) {
        const playButton = document.createElement('button');
        playButton.innerText = '點擊播放回應';
        playButton.className = 'btn secondary-btn';
        playButton.onclick = () => {
            const audio = new Audio(audioUrl);
            audio.play();
            playButton.disabled = true;
            playButton.innerText = '播放中...';
            audio.onended = () => {
                playButton.remove();
                URL.revokeObjectURL(audioUrl);
            };
        };

        container.appendChild(playButton);
    }

    /**
     * 獲取當前錄音數據
     * @returns {Blob|null} - 錄音數據
     */
    getAudioBlob() {
        return this.audioBlob;
    }

    /**
     * 清理資源
     */
    cleanup() {
        if (this.stream) {
            this.stream.getTracks().forEach(track => track.stop());
            this.stream = null;
        }

        this.mediaRecorder = null;
        this.audioChunks = [];
        this.audioBlob = null;
        this.isRecording = false;
    }
}

// 創建全局音頻處理器實例
const audioHandler = new AudioHandler();
