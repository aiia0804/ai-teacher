/**
 * 主應用程序模塊 - 處理UI和業務邏輯
 */
document.addEventListener('DOMContentLoaded', () => {
    // 初始化變數
    let transcript = '';
    let isTranscribing = false;
    let currentScenario = 'general';
    let currentVoice = 'af_heart.pt';

    // 獲取UI元素
    const recordButton = document.getElementById('record-button');
    const playButton = document.getElementById('play-button');
    const submitButton = document.getElementById('submit-button');
    const pronunciationButton = document.getElementById('pronunciation-button');
    const resetButton = document.getElementById('reset-button');
    const recordingStatus = document.getElementById('recording-status');
    const chatContainer = document.getElementById('chat-container');
    const transcriptContainer = document.getElementById('transcript-container');
    const transcriptEditor = document.getElementById('transcript-editor');
    const realtimeResponse = document.getElementById('realtime-response');
    const pronunciationFeedback = document.getElementById('pronunciation-feedback');
    const scenarioSelect = document.getElementById('scenario-select');
    const voiceSelect = document.getElementById('voice-select');

    // 初始化音頻環境
    initAudioEnvironment();

    // 設置事件監聽器
    setupEventListeners();

    /**
     * 初始化音頻環境
     */
    function initAudioEnvironment() {
        // 創建一個靜音音頻來激活音頻上下文
        const silentAudio = new Audio();
        silentAudio.src = 'data:audio/mpeg;base64,SUQzBAAAAAABEVRYWFgAAAAtAAADY29tbWVudABCaWdTb3VuZEJhbmsuY29tIC8gTGFTb25vdGhlcXVlLm9yZwBURU5DAAAAHQAAA1N3aXRjaCBQbHVzIMKpIE5DSCBTb2Z0d2FyZQBUSVQyAAAABgAAAzIyMzUAVFNTRQAAAA8AAANMYXZmNTcuODMuMTAwAAAAAAAAAAAAAAD/80DEAAAAA0gAAAAATEFNRTMuMTAwVVVVVVVVVVVVVUxBTUUzLjEwMFVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVf/zQsRbAAADSAAAAABVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVf/zQMSkAAADSAAAAABVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVV';

        // 嘗試播放以激活音頻上下文
        const playPromise = silentAudio.play();
        
        if (playPromise !== undefined) {
            playPromise.catch(e => {
                console.log('Silent audio play error (ignorable):', e);
                // 如果自動播放被阻止，可以在這裡顯示提示，要求用戶交互以啟用音頻
                const audioContainer = document.getElementById('auto-play-container');
                if (audioContainer) {
                    const unlockButton = document.createElement('button');
                    unlockButton.textContent = '點擊啟用音頻';
                    unlockButton.className = 'btn btn-primary mb-3';
                    unlockButton.onclick = () => {
                        silentAudio.play().then(() => {
                            console.log('音頻上下文已解鎖');
                            unlockButton.remove();
                        }).catch(err => {
                            console.error('無法解鎖音頻上下文:', err);
                        });
                    };
                    audioContainer.appendChild(unlockButton);
                }
            });
        }

        // 設置音頻自動播放監視器
        setupAutoPlayObserver();
    }

    /**
     * 設置音頻自動播放監視器
     */
    function setupAutoPlayObserver() {
        // 監聽新增的音頻元素
        const observer = new MutationObserver(mutations => {
            mutations.forEach(mutation => {
                if (mutation.addedNodes) {
                    mutation.addedNodes.forEach(node => {
                        if (node.nodeName === 'AUDIO' ||
                            (node.nodeType === 1 && node.querySelector('audio'))) {
                            // 直接尋找音頻元素或其容器中的音頻元素
                            const audioElement = node.nodeName === 'AUDIO' ?
                                                node : node.querySelector('audio');
                            if (audioElement) {
                                console.log('新檢測到音頻元素，嘗試自動播放');
                                
                                // 確保音頻元素已完全加載
                                if (audioElement.readyState >= 2) {
                                    tryPlayAudio(audioElement);
                                } else {
                                    // 如果音頻尚未加載，等待canplay事件
                                    audioElement.addEventListener('canplay', () => {
                                        tryPlayAudio(audioElement);
                                    }, { once: true });
                                    
                                    // 設置超時，以防音頻加載失敗
                                    setTimeout(() => {
                                        if (audioElement.readyState < 2) {
                                            console.warn('音頻加載超時，嘗試強制播放');
                                            tryPlayAudio(audioElement);
                                        }
                                    }, 1000);
                                }
                            }
                        }
                    });
                }
            });
        });
        
        // 嘗試播放音頻的輔助函數
        function tryPlayAudio(audioElement) {
            const playPromise = audioElement.play();
            if (playPromise !== undefined) {
                playPromise.catch(e => {
                    console.error('自動播放失敗:', e);
                    // 如果自動播放失敗，可以在這裡添加備用方案
                });
            }
        }

        // 監視整個文檔以捕獲新添加的音頻元素
        observer.observe(document.body, { childList: true, subtree: true });
    }

    /**
     * 設置事件監聽器
     */
    function setupEventListeners() {
        // 錄音按鈕
        recordButton.addEventListener('click', async () => {
            if (!audioHandler.isRecording) {
                const started = await audioHandler.startRecording();
                if (started) {
                    recordButton.classList.add('recording');
                    recordButton.innerHTML = '<i class="fas fa-stop"></i> 停止錄音';
                    recordingStatus.textContent = '正在錄音...';
                }
            } else {
                recordingStatus.textContent = '處理錄音中...';
                try {
                    const audioBlob = await audioHandler.stopRecording();
                    recordButton.classList.remove('recording');
                    recordButton.innerHTML = '<i class="fas fa-microphone"></i> 開始錄音';
                    recordingStatus.textContent = '錄音完成，正在轉錄...';

                    // 轉錄音頻
                    transcribeAudio(audioBlob);
                } catch (error) {
                    recordingStatus.textContent = '錄音失敗: ' + error.message;
                    resetRecordingUI();
                }
            }
        });

        // 播放按鈕
        playButton.addEventListener('click', () => {
            const audioBlob = audioHandler.getAudioBlob();
            if (audioBlob) {
                audioHandler.playAudio(audioBlob);
            }
        });

        // 提交按鈕
        submitButton.addEventListener('click', () => {
            submitMessage();
        });

        // 發音檢查按鈕
        pronunciationButton.addEventListener('click', () => {
            checkPronunciation();
        });

        // 重置按鈕
        resetButton.addEventListener('click', () => {
            resetConversation();
        });

        // 轉錄文本編輯器變更
        transcriptEditor.addEventListener('input', () => {
            transcript = transcriptEditor.value;
            updateButtonStates();
        });

        // 場景選擇
        if (scenarioSelect) {
            scenarioSelect.addEventListener('change', function() {
                currentScenario = this.value;
                console.log(`設置場景: ${currentScenario}`);
            });
        }
        
        // 語音選擇
        if (voiceSelect) {
            voiceSelect.addEventListener('change', function() {
                currentVoice = this.value;
                console.log(`設置語音: ${currentVoice}`);
            });
        }
    }

    /**
     * 重置錄音UI
     */
    function resetRecordingUI() {
        recordButton.classList.remove('recording');
        recordButton.innerHTML = '<i class="fas fa-microphone"></i> 開始錄音';
        recordingStatus.textContent = '';
    }

    /**
     * 轉錄音頻
     * @param {Blob} audioBlob - 錄音數據
     */
    async function transcribeAudio(audioBlob) {
        if (isTranscribing) return;

        try {
            isTranscribing = true;

            // 更新UI
            playButton.disabled = false;

            // 發送到API進行轉錄
            const text = await apiService.speechToText(audioBlob);

            if (text) {
                transcript = text;
                transcriptEditor.value = text;
                transcriptContainer.style.display = 'block';
                recordingStatus.textContent = '轉錄成功！';

                // 啟用按鈕
                updateButtonStates();

                // 自動提交消息
                submitMessage();
            } else {
                recordingStatus.textContent = '未能識別任何語音，請重新嘗試';
            }
        } catch (error) {
            console.error('轉錄音頻時出錯:', error);
            recordingStatus.textContent = '轉錄失敗: ' + error.message;
        } finally {
            isTranscribing = false;
        }
    }

    /**
     * 更新按鈕狀態
     */
    function updateButtonStates() {
        const hasAudioAndTranscript = audioHandler.getAudioBlob() && transcript;
        submitButton.disabled = !transcript;
        pronunciationButton.disabled = !hasAudioAndTranscript;
    }

    /**
     * 提交消息並獲取回應
     */
    async function submitMessage() {
        if (!transcript) return;

        try {
            // 顯示用戶消息
            displayMessage('user', transcript);

            // 添加到歷史記錄
            apiService.addMessage('user', transcript);

            // 清空輸入
            transcriptContainer.style.display = 'none';

            // 清空之前的音頻隊列
            audioHandler.clearAudioQueue();

            // 啟動TTS流接收
            console.log('啟動TTS流');
            await apiService.startTtsStream((audioBase64) => {
                // 設置回調函數處理每個音頻塊
                audioHandler.handleStreamingAudioChunk(audioBase64);
            });

            // 顯示加載中
            const loadingId = 'loading-' + Date.now();
            displayLoadingMessage(loadingId);

            // 獲取所選場景
            console.log(`使用場景: ${currentScenario}`);
            console.log(`使用語音: ${currentVoice}`);

            // 發送到API（包含場景信息和語音信息）
            const response = await apiService.chatWithLLM(transcript, currentScenario, currentVoice);

            // 移除加載消息
            removeLoadingMessage(loadingId);

            // 顯示回應
            displayMessage('bot', response);

            // 添加到歷史記錄
            apiService.addMessage('assistant', response);

            // 重置轉錄
            transcript = '';
            transcriptEditor.value = '';

            // 更新按鈕狀態
            updateButtonStates();

            // 注意：在此不會嘗試調用textToSpeech()
            // 因為音頻已經通過流式傳輸並播放

        } catch (error) {
            console.error('提交消息時出錯:', error);
            alert('提交消息時出錯: ' + error.message);

            // 停止TTS流
            apiService.stopTtsStream();
        }
    }

    /**
     * 檢查發音準確度
     */
    async function checkPronunciation() {
        const audioBlob = audioHandler.getAudioBlob();
        if (!audioBlob || !transcript) return;

        try {
            // 顯示加載中
            pronunciationFeedback.innerHTML = '<p>正在評估發音...</p>';
            pronunciationFeedback.style.display = 'block';

            // 發送到API進行評估
            const result = await apiService.evaluatePronunciation(audioBlob, transcript);

            // 顯示評估結果
            displayPronunciationFeedback(result);

        } catch (error) {
            console.error('檢查發音時出錯:', error);
            pronunciationFeedback.innerHTML = `<p>發音評估失敗: ${error.message}</p>`;
        }
    }

    /**
     * 顯示發音評估反饋
     * @param {Object} result - 評估結果
     */
    function displayPronunciationFeedback(result) {
        if (!result || !result.success) {
            pronunciationFeedback.innerHTML = '<p>無法獲取發音評估結果</p>';
            return;
        }

        const score = result.score || 0;
        const scoreText = (score * 100).toFixed(1);
        const scoreClass = score >= 0.8 ? 'good' : (score >= 0.6 ? 'average' : 'poor');

        let detailsHtml = '';
        if (result.details && result.details.length > 0) {
            detailsHtml = '<div class="pronunciation-details"><h4>詳細評估:</h4><ul>';
            result.details.forEach(detail => {
                detailsHtml += `<li>${detail}</li>`;
            });
            detailsHtml += '</ul></div>';
        }

        // 建議改進
        let suggestionsHtml = '';
        if (result.suggestions && result.suggestions.length > 0) {
            suggestionsHtml = '<div class="pronunciation-suggestions"><h4>改進建議:</h4><ul>';
            result.suggestions.forEach(suggestion => {
                suggestionsHtml += `<li>${suggestion}</li>`;
            });
            suggestionsHtml += '</ul></div>';
        }

        pronunciationFeedback.innerHTML = `
            <h3>發音評估結果</h3>
            <div class="pronunciation-score ${scoreClass}">
                準確度: ${scoreText}%
            </div>
            ${detailsHtml}
            ${suggestionsHtml}
        `;

        pronunciationFeedback.style.display = 'block';
    }

    /**
     * 顯示消息
     * @param {string} role - 角色 (user/bot)
     * @param {string} content - 消息內容
     */
    function displayMessage(role, content) {
        const messageDiv = document.createElement('div');
        messageDiv.className = `chat-message ${role}`;

        // 格式化消息內容（支持基本的Markdown）
        const formattedContent = formatMessage(content);

        messageDiv.innerHTML = formattedContent;
        chatContainer.appendChild(messageDiv);

        // 滾動到底部
        chatContainer.scrollTop = chatContainer.scrollHeight;
    }

    /**
     * 顯示加載消息
     * @param {string} id - 消息ID
     */
    function displayLoadingMessage(id) {
        const loadingDiv = document.createElement('div');
        loadingDiv.className = 'chat-message bot loading';
        loadingDiv.id = id;
        loadingDiv.innerHTML = '<span class="loading-dots"><span>.</span><span>.</span><span>.</span></span>';
        chatContainer.appendChild(loadingDiv);
        chatContainer.scrollTop = chatContainer.scrollHeight;
    }

    /**
     * 移除加載消息
     * @param {string} id - 消息ID
     */
    function removeLoadingMessage(id) {
        const loadingElement = document.getElementById(id);
        if (loadingElement) {
            loadingElement.remove();
        }
    }

    /**
     * 格式化消息（基本的Markdown支持）
     * @param {string} text - 原始文本
     * @returns {string} - 格式化後的HTML
     */
    function formatMessage(text) {
        // 將換行符轉換為<br>
        let formatted = text.replace(/\n/g, '<br>');

        // 粗體
        formatted = formatted.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');

        // 斜體
        formatted = formatted.replace(/\*(.*?)\*/g, '<em>$1</em>');

        // 代碼
        formatted = formatted.replace(/`(.*?)`/g, '<code>$1</code>');

        return formatted;
    }

    /**
     * 重置對話
     */
    function resetConversation() {
        // 停止任何進行中的TTS流
        apiService.stopTtsStream();

        // 清空音頻隊列
        audioHandler.clearAudioQueue();

        // 重置API服務
        apiService.resetConversation();

        // 清空聊天容器
        chatContainer.innerHTML = '';

        // 重置UI
        transcript = '';
        transcriptEditor.value = '';
        transcriptContainer.style.display = 'none';
        pronunciationFeedback.style.display = 'none';

        // 更新按鈕狀態
        updateButtonStates();

        // 添加歡迎消息
        displayMessage('bot', '您好！我是您的英語對話AI教師。請說些什麼，我會幫助您練習英語口語。');
    }

    // 初始顯示歡迎消息
    displayMessage('bot', '您好！我是您的英語對話AI教師。請說些什麼，我會幫助您練習英語口語。');
});
