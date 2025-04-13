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
        this.lastInteractionTime = Date.now();
        this.interactionTimeout = 60000; // 1分鐘後考慮可能需要重新獲取權限

        // 流式音頻相關
        this.streamingAudioChunks = [];
        this.isPlayingStreamingAudio = false;
        this.audioQueue = [];
        
        // 監聽用戶交互事件以保持音頻權限
        this._setupInteractionListeners();
    }

    /**
     * 設置用戶交互事件監聽器，用於維持音頻播放權限
     * 特別是為Safari設計
     */
    _setupInteractionListeners() {
        const interactionEvents = ['click', 'touchstart', 'keydown'];
        
        // 對於每個交互事件，更新最後交互時間並嘗試預激活音頻
        interactionEvents.forEach(eventType => {
            document.addEventListener(eventType, () => {
                this.lastInteractionTime = Date.now();
                this._tryActivateAudio();
            }, { passive: true });
        });
    }

    /**
     * 嘗試預激活音頻上下文，為後續播放做準備
     * 專門針對Safari的限制設計
     */
    _tryActivateAudio() {
        // 創建一個短暫的靜音音頻並播放
        // 這能夠在用戶交互時"激活"音頻權限
        try {
            if (!this.audioContext) {
                this.audioContext = new (window.AudioContext || window.webkitAudioContext)();
            }
            
            // 創建一個微小的靜音音頻緩衝區
            const silentBuffer = this.audioContext.createBuffer(1, 1, 22050);
            const source = this.audioContext.createBufferSource();
            source.buffer = silentBuffer;
            source.connect(this.audioContext.destination);
            source.start(0);
            source.stop(0.001);
            
            console.log('音頻上下文預激活成功');
        } catch (e) {
            console.warn('音頻預激活失敗:', e);
        }
    }

    /**
     * 檢查音頻權限是否可能已過期
     * @returns {boolean} - 是否需要重新獲取權限
     */
    _isPermissionLikelyExpired() {
        return Date.now() - this.lastInteractionTime > this.interactionTimeout;
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
            // 在播放前檢查權限是否可能過期
            if (this._isPermissionLikelyExpired()) {
                console.log('音頻權限可能已過期，尋求用戶交互...');
                this._showInteractionRequiredMessage();
                return;
            }

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
                
                // 處理權限錯誤
                if (e.target && e.target.error && e.target.error.name === 'NotAllowedError') {
                    console.warn('播放被阻止，需要用戶交互');
                    this.audioQueue = []; // 清空隊列避免多次錯誤
                    this._showInteractionRequiredMessage();
                    return;
                }
                
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
                // 如果是自動播放被阻止的錯誤，處理特別情況
                if (e.name === 'NotAllowedError') {
                    console.log('自動播放被阻止，需要用戶交互');
                    // 清空隊列避免重複錯誤
                    this.audioQueue = [];
                    this._showInteractionRequiredMessage();
                } else {
                    // 繼續下一個
                    setTimeout(() => this.playNextAudioChunk(), 100);
                }
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
     * 顯示需要用戶交互的提示信息
     * @private
     */
    _showInteractionRequiredMessage() {
        const container = document.getElementById('auto-play-container');
        if (!container) return;
        
        // 清空當前容器
        container.innerHTML = '';
        
        // 創建交互提示按鈕
        const interactionButton = document.createElement('button');
        interactionButton.innerText = '點擊這裡啟用音頻';
        interactionButton.className = 'btn primary-btn';
        interactionButton.style.marginTop = '10px';
        
        // 添加點擊事件
        interactionButton.onclick = () => {
            // 更新交互時間
            this.lastInteractionTime = Date.now();
            
            // 嘗試激活音頻
            this._tryActivateAudio();
            
            // 移除按鈕
            interactionButton.remove();
            
            // 嘗試恢復音頻播放
            setTimeout(() => {
                this.isPlayingStreamingAudio = false;
                if (this.audioQueue.length > 0) {
                    this.playNextAudioChunk();
                }
            }, 100);
        };
        
        // 添加到容器
        container.appendChild(interactionButton);
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
