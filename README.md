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

## インストール

```bash
# リポジトリのクローン
git clone https://github.com/yourusername/ai-teacher.git
cd ai-teacher

# 依存関係のインストール
pip install -r requirements.txt

# アプリケーションの実行
python main.py
```

## プロジェクト構造

```
ai-teacher/
├── README.md
├── requirements.txt
├── main.py                # アプリケーションのエントリーポイント
├── src/
│   ├── config.py          # 設定ファイル
│   ├── api/               # API関連コード
│   │   ├── __init__.py    # APIパッケージ初期化
│   │   ├── routes.py      # APIルート処理
│   │   └── schemas.py     # データモデル定義
│   └── models/            # モデル実装
│       ├── llm.py         # 言語モデル管理
│       ├── stt.py         # 音声認識
│       ├── tts.py         # 音声合成
│       └── model_data/    # モデルデータ（gitignore）
└── static/                # 静的ファイル
```

## 技術スタック

- **バックエンド**: FastAPI, Python 3.8+
- **AI/ML**: PyTorch, Transformers, カスタム音声処理
- **フロントエンド**: HTML5, JavaScript

## ライセンス

MITライセンス

---

## English / 英語 / 英语

# AI English Teacher

An AI-powered English learning application utilizing modern web technologies to provide efficient language learning experiences through text, audio, and conversation.

## Features

- **Interactive AI**: Engage in natural English conversations for practice
- **Speech-to-Text (STT)**: Recognize user's speech and convert to text
- **Text-to-Speech (TTS)**: Convert AI-generated text into natural English voice
- **Pronunciation Assessment**: Evaluate English pronunciation accuracy and provide feedback
- **Scenario-based Learning**: Practice conversations in real-world scenarios like restaurants, shopping

## Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/ai-teacher.git
cd ai-teacher

# Install dependencies
pip install -r requirements.txt

# Run the application
python main.py
```

## Project Structure

```
ai-teacher/
├── README.md
├── requirements.txt
├── main.py                # Application entry point
├── src/
│   ├── config.py          # Configuration file
│   ├── api/               # API-related code
│   │   ├── __init__.py    # API package initialization
│   │   ├── routes.py      # API route handlers
│   │   └── schemas.py     # Data models
│   └── models/            # Model implementations
│       ├── llm.py         # Language model management
│       ├── stt.py         # Speech recognition
│       ├── tts.py         # Text-to-speech synthesis
│       └── model_data/    # Model data (gitignored)
└── static/                # Static files
```

## Technology Stack

- **Backend**: FastAPI, Python 3.8+
- **AI/ML**: PyTorch, Transformers, Custom audio processing
- **Frontend**: HTML5, JavaScript

## License

MIT License

---

## 中文 / Chinese / 中国語

# AI英语教师

一个结合现代Web技术的AI驱动英语学习应用，通过文本、音频和对话提供高效的语言学习体验。

## 功能特点

- **交互式AI**：进行自然英语对话练习
- **语音转文字 (STT)**：识别用户语音并转换为文本
- **文字转语音 (TTS)**：将AI生成的文本转换为自然英语语音
- **发音评估**：评估英语发音准确度并提供反馈
- **场景化学习**：在餐厅、购物等真实场景中练习对话

## 安装方法

```bash
# 克隆仓库
git clone https://github.com/yourusername/ai-teacher.git
cd ai-teacher

# 安装依赖
pip install -r requirements.txt

# 运行应用
python main.py
```

## 项目结构

```
ai-teacher/
├── README.md
├── requirements.txt
├── main.py                # 应用程序入口点
├── src/
│   ├── config.py          # 配置文件
│   ├── api/               # API相关代码
│   │   ├── __init__.py    # API包初始化
│   │   ├── routes.py      # API路由处理
│   │   └── schemas.py     # 数据模型定义
│   └── models/            # 模型实现
│       ├── llm.py         # 语言模型管理
│       ├── stt.py         # 语音识别
│       ├── tts.py         # 文本转语音
│       └── model_data/    # 模型数据（已gitignore）
└── static/                # 静态文件
```

## 技术栈

- **后端**：FastAPI, Python 3.8+
- **AI/ML**：PyTorch, Transformers, 自定义音频处理
- **前端**：HTML5, JavaScript

## 许可证

MIT许可证
