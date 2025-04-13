/**
 * 多語言支持模塊
 * 支持中文、日文和英文
 */

const i18n = {
    // 中文(繁體)
    'zh-TW': {
        // 頁面標題
        'app_title': '英語對話AI教師',
        
        // 側邊欄
        'settings': '設置',
        'instructions': '使用方法',
        'instruction_1': '點擊「開始錄音」按鈕說話',
        'instruction_2': '錄音完成後會自動轉錄並發送',
        'instruction_3': '可以使用「檢查發音」功能評估你的發音',
        'instruction_4': '使用「重置對話」開始新的對話',
        
        // 控制面板
        'record_button': '開始錄音',
        'recording': '錄音中...',
        'send_button': '手動送出',
        'loading': '載入中...',
        'recording_permission': '請允許麥克風權限以開始錄音',
        
        // 選擇器
        'select_scenario': '選擇對話場景:',
        'select_voice': '選擇語音:',
        'scenario_hint': '選擇一個情境來練習特定場合的英語對話',
        'voice_hint': '選擇您想聽的AI英語教師的口音和聲音',
        
        // 場景選項
        'general': '一般對話',
        'restaurant': '餐廳點餐',
        'shopping': '購物情境',
        'airport_customs': '機場海關',
        'hotel_checkin': '旅館入住',
        'doctor_visit': '看醫生',
        'job_interview': '工作面試',
        'public_transport': '公共交通',
        
        // 語音選項
        'voice_us_female': '標準美式女性 (默認)',
        'voice_us_male_cool': '帥氣美式男性',
        'voice_us_male': '標準美式男性',
        'voice_uk_female': '標準英式女性',
        'voice_uk_male': '標準英式男性',
        'voice_us_female_soft': '悄悄話美式女性',
        
        // 按鈕
        'reset_button': '重置對話',
        'language_select': '選擇語言:',
        
        // 歡迎消息
        'welcome_message': '您好！我是您的英語對話AI教師。請說些什麼，我會幫助您練習英語口語。'
    },
    
    // 日文
    'ja': {
        // 頁面標題
        'app_title': '英会話AIティーチャー',
        
        // 側邊欄
        'settings': '設定',
        'instructions': '使用方法',
        'instruction_1': '「録音開始」ボタンをクリックして話す',
        'instruction_2': '録音が完了すると自動的に文字起こしして送信します',
        'instruction_3': '「発音チェック」機能で発音を評価できます',
        'instruction_4': '「会話リセット」で新しい会話を始めます',
        
        // 控制面板
        'record_button': '録音開始',
        'recording': '録音中...',
        'send_button': '手動送信',
        'loading': '読み込み中...',
        'recording_permission': 'マイクの使用許可を与えて録音を開始してください',
        
        // 選擇器
        'select_scenario': '会話シナリオを選択:',
        'select_voice': '音声を選択:',
        'scenario_hint': '特定の場面での英会話練習のためにシナリオを選んでください',
        'voice_hint': 'AI英語教師の声やアクセントを選択してください',
        
        // 場景選項
        'general': '一般会話',
        'restaurant': 'レストランでの注文',
        'shopping': 'ショッピング',
        'airport_customs': '空港の税関',
        'hotel_checkin': 'ホテルチェックイン',
        'doctor_visit': '医者の診察',
        'job_interview': '就職面接',
        'public_transport': '公共交通機関',
        
        // 語音選項
        'voice_us_female': '標準アメリカ英語（女性・デフォルト）',
        'voice_us_male_cool': 'クールなアメリカ英語（男性）',
        'voice_us_male': '標準アメリカ英語（男性）',
        'voice_uk_female': '標準イギリス英語（女性）',
        'voice_uk_male': '標準イギリス英語（男性）',
        'voice_us_female_soft': '優しいアメリカ英語（女性）',
        
        // 按鈕
        'reset_button': '会話リセット',
        'language_select': '言語選択:',
        
        // 歡迎消息
        'welcome_message': 'こんにちは！私はあなたの英会話AIティーチャーです。何か話しかけてください、英語の会話練習をお手伝いします。'
    },
    
    // 英文
    'en': {
        // 頁面標題
        'app_title': 'English Conversation AI Teacher',
        
        // 側邊欄
        'settings': 'Settings',
        'instructions': 'How to Use',
        'instruction_1': 'Click "Start Recording" button to speak',
        'instruction_2': 'After recording, it will automatically transcribe and send',
        'instruction_3': 'Use "Check Pronunciation" to evaluate your pronunciation',
        'instruction_4': 'Use "Reset Conversation" to start a new conversation',
        
        // 控制面板
        'record_button': 'Start Recording',
        'recording': 'Recording...',
        'send_button': 'Send Manually',
        'loading': 'Loading...',
        'recording_permission': 'Please allow microphone permission to start recording',
        
        // 選擇器
        'select_scenario': 'Select Conversation Scenario:',
        'select_voice': 'Select Voice:',
        'scenario_hint': 'Choose a scenario to practice English in specific situations',
        'voice_hint': 'Choose the accent and voice of your AI English teacher',
        
        // 場景選項
        'general': 'General Conversation',
        'restaurant': 'Restaurant Ordering',
        'shopping': 'Shopping Scenario',
        'airport_customs': 'Airport Customs',
        'hotel_checkin': 'Hotel Check-in',
        'doctor_visit': 'Doctor Visit',
        'job_interview': 'Job Interview',
        'public_transport': 'Public Transportation',
        
        // 語音選項
        'voice_us_female': 'Standard American Female (Default)',
        'voice_us_male_cool': 'Cool American Male',
        'voice_us_male': 'Standard American Male',
        'voice_uk_female': 'Standard British Female',
        'voice_uk_male': 'Standard British Male',
        'voice_us_female_soft': 'Soft-spoken American Female',
        
        // 按鈕
        'reset_button': 'Reset Conversation',
        'language_select': 'Select Language:',
        
        // 歡迎消息
        'welcome_message': 'Hello! I am your English Conversation AI Teacher. Please say something, and I will help you practice your English speaking skills.'
    }
};

// 默認語言
let currentLanguage = 'zh-TW';

// 獲取翻譯文本
function t(key) {
    if (i18n[currentLanguage] && i18n[currentLanguage][key]) {
        return i18n[currentLanguage][key];
    }
    // 如果找不到翻譯，返回英文版本，如果英文版本也沒有，返回鍵名
    return i18n['en'][key] || key;
}

// 更新頁面上的所有文本
function updatePageLanguage() {
    document.title = t('app_title');
    
    // 更新具有 data-i18n 屬性的所有元素
    document.querySelectorAll('[data-i18n]').forEach(element => {
        const key = element.getAttribute('data-i18n');
        
        // 根據元素類型設置內容
        if (element.tagName === 'INPUT' && element.type === 'button') {
            element.value = t(key);
        } else if (element.tagName === 'OPTION') {
            element.textContent = t(key);
        } else {
            element.textContent = t(key);
        }
    });
    
    // 更新按鈕和特殊元素
    const recordButton = document.getElementById('record-button');
    if (recordButton) {
        if (recordButton.classList.contains('recording')) {
            recordButton.textContent = t('recording');
        } else {
            recordButton.textContent = t('record_button');
        }
    }
    
    // 保存當前語言到本地存儲
    localStorage.setItem('preferred_language', currentLanguage);
}

// 設置語言
function setLanguage(lang) {
    if (i18n[lang]) {
        currentLanguage = lang;
        updatePageLanguage();
    }
}

// 在頁面加載時加載之前保存的語言偏好
function initLanguage() {
    const savedLanguage = localStorage.getItem('preferred_language');
    if (savedLanguage && i18n[savedLanguage]) {
        currentLanguage = savedLanguage;
    }
    updatePageLanguage();
}

// 導出功能
window.i18n = {
    t: t,
    setLanguage: setLanguage,
    currentLanguage: () => currentLanguage,
    supportedLanguages: Object.keys(i18n),
    initLanguage: initLanguage
};
