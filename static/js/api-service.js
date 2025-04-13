/**
 * API 服務模塊 - 處理所有與後端的通信
 */
class ApiService {
    constructor() {
        this.API_URL = '/api';
        this.conversationId = this.generateUUID();
        this.messages = [];
        this.ttsStream = null;
        this.onTtsAudioChunk = null; // 接收TTS音頻塊的回調函數
        this.isTtsStreamActive = false;
    }

    /**
     * 生成UUID作為對話ID
     */
    generateUUID() {
        return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function(c) {
            const r = Math.random() * 16 | 0,
                  v = c == 'x' ? r : (r & 0x3 | 0x8);
            return v.toString(16);
        });
    }

    /**
     * 將音頻轉換為文本
     * @param {Blob} audioBlob - 錄音數據
     * @returns {Promise<string>} - 轉錄文本
     */
    async speechToText(audioBlob) {
        try {
            // 轉換Blob為Base64
            const base64Audio = await this.blobToBase64(audioBlob);

            const response = await fetch(`${this.API_URL}/stt`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    audio_base64: base64Audio,
                    language: 'en'
                })
            });

            if (!response.ok) {
                throw new Error(`轉錄請求失敗: ${response.status}`);
            }

            const result = await response.json();

            if (result.success) {
                return result.text || '';
            } else {
                throw new Error('轉錄失敗');
            }
        } catch (error) {
            console.error('語音轉文本錯誤:', error);
            throw error;
        }
    }

    /**
     * 與LLM模型進行對話
     * @param {string} message - 用戶消息
     * @returns {Promise<string>} - 模型回應
     */
    async chatWithLLM(message) {
        try {
            // 準備請求數據 - 不再發送本地消息歷史，讓後端使用自己的優化歷史
            const payload = {
                message: message,
                conversation_id: this.conversationId,
                scenario: 'general'
            };

            const response = await fetch(`${this.API_URL}/llm`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(payload)
            });

            if (!response.ok) {
                throw new Error(`對話請求失敗: ${response.status}`);
            }

            const result = await response.json();
            return result.response || '';

        } catch (error) {
            console.error('對話錯誤:', error);
            throw error;
        }
    }

    /**
     * 流式接收TTS音頻數據
     * @param {Function} onAudioChunk - 接收音頻塊的回調函數
     * @returns {Promise<void>}
     */
    async startTtsStream(onAudioChunk) {
        // 停止之前的流
        this.stopTtsStream();

        try {
            this.onTtsAudioChunk = onAudioChunk;
            this.isTtsStreamActive = true;

            console.log('開始TTS流接收');

            // 使用EventSource進行SSE連接
            const url = `${this.API_URL}/tts-stream`;

            // 使用fetch和ReadableStream處理SSE
            const response = await fetch(url, {
                method: 'GET',
                headers: {
                    'Accept': 'text/event-stream'
                }
            });

            if (!response.ok) {
                throw new Error(`連接到TTS流失敗: HTTP ${response.status}`);
            }

            const reader = response.body.getReader();
            this.ttsStream = reader;

            // 處理SSE數據
            this.processStream(reader);

            return true;
        } catch (error) {
            console.error('啟動TTS流時出錯:', error);
            this.isTtsStreamActive = false;
            return false;
        }
    }

    /**
     * 處理SSE流數據
     * @param {ReadableStreamDefaultReader} reader - 流讀取器
     */
    async processStream(reader) {
        let buffer = "";
        let decoder = new TextDecoder();
        let reconnectAttempts = 0;
        const maxReconnectAttempts = 3;

        try {
            while (this.isTtsStreamActive) {
                try {
                    const { value, done } = await reader.read();

                    if (done) {
                        console.log('TTS流已關閉');
                        break;
                    }

                    // 將二進制數據轉換為文本
                    buffer += decoder.decode(value, { stream: true });

                    // 解析SSE事件
                    while (buffer.includes("\n\n")) {
                        const [event, remaining] = buffer.split("\n\n", 2);
                        buffer = remaining;

                        const lines = event.split("\n");
                        let eventType = null;
                        let data = null;

                        for (const line of lines) {
                            if (line.startsWith("event: ")) {
                                eventType = line.substring(7);
                            } else if (line.startsWith("data: ")) {
                                data = line.substring(6);
                            }
                        }

                        if (eventType === "audio" && data) {
                            try {
                                // 解析JSON數據
                                const jsonData = JSON.parse(data);
                                const audioBase64 = jsonData.audio;

                                if (audioBase64 && this.onTtsAudioChunk) {
                                    // 驗證Base64數據
                                    if (typeof audioBase64 === 'string' && audioBase64.trim() !== '') {
                                        // 調用回調函數處理音頻數據
                                        this.onTtsAudioChunk(audioBase64);
                                        // 重置重連嘗試次數
                                        reconnectAttempts = 0;
                                    } else {
                                        console.warn('收到無效的Base64音頻數據');
                                    }
                                }
                            } catch (e) {
                                console.error('解析音頻數據時出錯:', e);
                            }
                        } else if (eventType === "close") {
                            console.log('服務器已關閉TTS流連接');
                            this.isTtsStreamActive = false;
                            break;
                        }
                    }
                } catch (readError) {
                    console.error('讀取TTS流時出錯:', readError);
                    
                    // 嘗試重新連接
                    if (reconnectAttempts < maxReconnectAttempts) {
                        reconnectAttempts++;
                        console.log(`嘗試重新連接TTS流 (${reconnectAttempts}/${maxReconnectAttempts})...`);
                        await new Promise(resolve => setTimeout(resolve, 1000));
                        continue;
                    } else {
                        console.error(`重連TTS流失敗，已達到最大嘗試次數 (${maxReconnectAttempts})`);
                        break;
                    }
                }
            }
        } catch (error) {
            console.error('處理TTS流時出錯:', error);
        } finally {
            this.isTtsStreamActive = false;
            // 清理資源
            if (this.onTtsAudioChunk) {
                // 通知音頻處理器停止播放
                console.log('通知音頻處理器清理資源');
                // 這裡可以發送一個特殊信號給音頻處理器
            }
        }
    }

    /**
     * 停止TTS流
     */
    stopTtsStream() {
        if (this.ttsStream) {
            console.log('正在停止TTS流');
            this.isTtsStreamActive = false;
            this.ttsStream.cancel();
            this.ttsStream = null;
        }
    }

    /**
     * 將文本轉換為語音 (單次請求版本)
     * @param {string} text - 要轉換的文本
     * @returns {Promise<Blob>} - 音頻數據
     */
    async textToSpeech(text) {
        try {
            // 準備請求數據
            const payload = {
                text: text,
                voice: 'af_heart.pt',
                speed: 1.0
            };

            const response = await fetch(`${this.API_URL}/tts`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(payload)
            });

            if (!response.ok) {
                throw new Error(`TTS請求失敗: ${response.status}`);
            }

            // 返回音頻Blob
            return await response.blob();

        } catch (error) {
            console.error('文本轉語音錯誤:', error);
            throw error;
        }
    }

    /**
     * 評估發音準確度
     * @param {Blob} audioBlob - 錄音數據
     * @param {string} text - 參考文本
     * @returns {Promise<Object>} - 評估結果
     */
    async evaluatePronunciation(audioBlob, text) {
        try {
            // 轉換Blob為Base64
            const base64Audio = await this.blobToBase64(audioBlob);

            const response = await fetch(`${this.API_URL}/pronunciation`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    audio_base64: base64Audio,
                    text: text
                })
            });

            if (!response.ok) {
                throw new Error(`發音評估請求失敗: ${response.status}`);
            }

            return await response.json();

        } catch (error) {
            console.error('發音評估錯誤:', error);
            throw error;
        }
    }

    /**
     * 獲取可用的對話情境
     * @returns {Promise<Object>} - 情境字典
     */
    async getAvailableScenarios() {
        try {
            const response = await fetch(`${this.API_URL}/scenarios`);

            if (!response.ok) {
                throw new Error(`獲取情境請求失敗: ${response.status}`);
            }

            return await response.json();

        } catch (error) {
            console.error('獲取情境錯誤:', error);
            return { 'general': '一般對話' };  // 提供默認值
        }
    }

    /**
     * 將Blob轉換為Base64
     * @param {Blob} blob - 二進制數據
     * @returns {Promise<string>} - Base64字符串
     */
    async blobToBase64(blob) {
        return new Promise((resolve, reject) => {
            const reader = new FileReader();
            reader.onloadend = () => {
                // 移除數據URL前綴 (e.g., "data:audio/webm;base64,")
                const base64String = reader.result.split(',')[1];
                resolve(base64String);
            };
            reader.onerror = reject;
            reader.readAsDataURL(blob);
        });
    }

    /**
     * 添加消息到歷史記錄
     * @param {string} role - 消息角色 (user/assistant)
     * @param {string} content - 消息內容
     */
    addMessage(role, content) {
        this.messages.push({ role, content });
    }

    /**
     * 重置對話
     */
    resetConversation() {
        this.conversationId = this.generateUUID();
        this.messages = [];
    }
}

// 創建全局API服務實例
const apiService = new ApiService();
