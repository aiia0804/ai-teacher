# AI英語教師 / AI English Teacher / AI英语教师

## 日本語 / Japanese / 日语

# AI英語教師

モダンなウェブ技術を活用したAI駆動の英語学習アプリケーションです。テキスト、音声、対話を通じて効率的な言語学習体験を提供します。

## 機能

- **対話型AI**: 自然な英会話練習のためのインタラクティブな対話システム  
- **音声認識 (STT)**: ユーザーの発音を認識し、テキストに変換  
- **テキスト音声合成 (TTS)**: AIが生成したテキストを自然な英語の音声に変換  
- **発音評価**: 英語発音の精度を評価し、フィードバックを提供  
- **シナリオベース学習**: レストラン、買い物などの実際のシナリオでの会話練習  

## デモ動画

[▶️ デモビデオを見る](https://youtu.be/uHYGd2isyJA?si=qx57u3euTivb_ebO)

## プロジェクト構造

```
ai-teacher/
├── README.md
├── requirements.txt
├── main.py
├── src/
│   ├── config.py
│   ├── api/
│   │   ├── __init__.py
│   │   ├── routes.py
│   │   └── schemas.py
│   └── models/
│       ├── llm.py
│       ├── stt.py
│       ├── tts.py
│       └── model_data/
└── static/
```

## 技術スタック

- **バックエンド**: FastAPI, Python 3.8+  
- **AI/ML**: PyTorch, Transformers, カスタム音声処理  
- **使用モデル**:  
  - LLM → Gemma 3 4B  
  - TTS → KOKORO  
  - STT → Whisper (medium)


---

## English / 英語 / 英语

# AI English Teacher

An AI-powered English learning application that offers an efficient language learning experience through text, audio, and conversations.

## Features

- **Interactive AI**: Practice natural English conversations  
- **Speech-to-Text (STT)**: Convert spoken input into text  
- **Text-to-Speech (TTS)**: Read generated text in natural English voice  
- **Pronunciation Assessment**: Feedback on pronunciation accuracy  
- **Scenario-based Learning**: Practice real-life situations (e.g., restaurants, shopping)  

## Demo Video

[▶️ Watch Demo Video](https://youtu.be/uHYGd2isyJA?si=qx57u3euTivb_ebO)

## Project Structure

```
ai-teacher/
├── README.md
├── requirements.txt
├── main.py
├── src/
│   ├── config.py
│   ├── api/
│   │   ├── __init__.py
│   │   ├── routes.py
│   │   └── schemas.py
│   └── models/
│       ├── llm.py
│       ├── stt.py
│       ├── tts.py
│       └── model_data/
└── static/
```

## Technology Stack

- **Backend**: FastAPI, Python 3.8+  
- **AI/ML**: PyTorch, Transformers, Custom audio processing  
- **Models Used**:  
  - LLM → Gemma 3 4B  
  - TTS → KOKORO  
  - STT → Whisper (medium)


---

## 中文 / Chinese / 中国語

# AI英语教师

一个结合现代AI技术的英语学习应用，通过文字、语音和对话提供高效的语言学习体验。

## 功能特点

- **交互式AI**：自然的英语对话练习  
- **语音转文字 (STT)**：将语音识别为文本  
- **文字转语音 (TTS)**：将生成的文本转换成自然语音  
- **发音评估**：提供发音准确度反馈  
- **情景对话练习**：餐厅、购物等真实情境模拟  

## 演示视频

[▶️ 点击观看演示视频](https://youtu.be/uHYGd2isyJA?si=qx57u3euTivb_ebO)

## 项目结构

```
ai-teacher/
├── README.md
├── requirements.txt
├── main.py
├── src/
│   ├── config.py
│   ├── api/
│   │   ├── __init__.py
│   │   ├── routes.py
│   │   └── schemas.py
│   └── models/
│       ├── llm.py
│       ├── stt.py
│       ├── tts.py
│       └── model_data/
└── static/
```

## 技术栈

- **后端**：FastAPI, Python 3.8+  
- **AI/ML**：PyTorch, Transformers, 自定义音频处理  
- **所用模型**：  
  - LLM → Gemma 3 4B  
  - TTS → KOKORO  
  - STT → Whisper (medium)

