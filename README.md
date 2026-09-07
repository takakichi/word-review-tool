# Word文書 自動レビュー支援ツール

指定したWord文書（`.docx`）のページだけを抽出し、ローカルPCまたは社内LAN上の
OllamaでレビューするStreamlitアプリです。レビュー観点、LLMへの指示、実際の送信
プロンプト、ページ番号付きの指摘を画面で確認できます。

本プログラムは、Codexで作成されたものです。

## 主な機能

- Microsoft WordによるDOCX→PDF変換と実ページ数の取得
- 開始・終了ページを指定したテキスト抽出
- 8種類のレビュー観点と自由入力の追加観点
- ページ・段落・文字数を考慮したチャンク分割
- レビュー指示プロンプトとチャンク別の実送信プロンプトの表示
- Ollamaのモデル一覧取得とJSON形式でのレビュー要求
- Pydanticによるレスポンス検証（不正JSONの生レスポンスも確認可能）
- 重要度フィルター、Markdown/JSONダウンロード
- 一時DOCX/PDFの自動削除

## 前提条件

- Windows 10またはWindows 11
- Python 3.10以上
- デスクトップ版Microsoft Word（PDF変換に必須）
- OllamaがローカルPCまたは許可した社内LANホストで稼働していること
- Ollama APIへHTTP接続できること

Word OnlineやLibreOfficeによる変換は、このPoCの対象外です。スキャン画像のみの
ページに対するOCRも行いません。

## セットアップ

PowerShellでこのディレクトリへ移動し、次を実行します。

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
```

Ollamaへ利用するモデルを用意します（例）。

```powershell
ollama serve
ollama pull qwen3:8b
```

別のターミナルでアプリを起動します。

```powershell
streamlit run app.py
```

ブラウザが自動で開かない場合は、Streamlitが表示したローカルURLへアクセスします。

## 設定

`.env.example`を`.env`へコピーして編集します。`.env`はGit管理対象外です。

| 変数 | 既定値 | 説明 |
|---|---:|---|
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama APIの初期URL |
| `OLLAMA_MODEL` | 空 | モデル入力欄の初期値 |
| `OLLAMA_TIMEOUT_SECONDS` | `120` | 1チャンクあたりのタイムアウト（秒） |
| `OLLAMA_ALLOWED_HOSTS` | `localhost,127.0.0.1,::1` | 接続を許可するホスト名/IP（カンマ区切り） |
| `REVIEW_CHUNK_SIZE` | `6000` | 1チャンクの最大文字数 |

社内LAN上のOllamaを使う場合は、接続先を明示的に許可します。

```dotenv
OLLAMA_BASE_URL=http://ollama.internal.example:11434
OLLAMA_ALLOWED_HOSTS=localhost,127.0.0.1,::1,ollama.internal.example
```

文書の誤送信を避けるため、許可リスト外のホストには接続しません。URLへ認証情報を
埋め込む方式にも対応していません。

## 使用方法

1. 左側のアップローダーへ`.docx`をドラッグ＆ドロップします。
2. Word変換後に表示される総ページ数を確認し、開始・終了ページを指定します。
3. Ollama URLを確認し、「モデル一覧を取得／更新」を押してモデルを選びます。
   一覧取得が失敗しても、モデル名は手入力できます。
4. レビュー観点を選択し、必要なら自由入力の観点とチャンク上限を変更します。
5. 「A. レビュー指示プロンプト」と「B. 実際のLLM送信プロンプト」を確認します。
6. 「レビューを実行」を押します。
7. 右側で指摘を確認し、MarkdownまたはJSONをダウンロードします。

ページ番号はWordをPDFへ変換した後の実ページ番号です。Word上の見かけのページ番号
（セクションごとの番号設定など）とは異なる場合があります。

## セキュリティ上の注意

- アプリはレビュー本文を、許可されたOllama API以外へ送信しません。
- アップロードDOCXと変換PDFは`TemporaryDirectory`内だけに作成され、処理後に削除
  されます。UIのセッション中は、変換済みPDFバイト列をメモリに保持します。
- 文書本文、完全なプロンプト、LLM生レスポンスを通常ログへ出力しません。
- LLMの不正JSONだけは、利用者が原因を確認できるよう画面内に表示します。
- 社内LANのOllama通信を暗号化する必要がある場合は、組織内のHTTPSリバース
  プロキシ等を利用してください。
- Streamlit自体の公開、認証、アクセス制御はPoCの対象外です。外部公開しないでください。

## テスト

WordやOllamaへの実通信を行わない単体テストを実行できます。

```powershell
pytest
python -m compileall .
```

テスト対象は、ページ範囲検証、プロンプト生成、チャンク分割、JSON解析、Markdown
生成です。通信クライアントとレビュー統括処理は分離しており、追加テストでモック可能です。

## ディレクトリ構成

```text
word-review-tool/
├─ app.py
├─ config/       # 環境設定、レビュー観点の一元定義
├─ models/       # Pydanticモデル
├─ services/     # Word/PDF、Ollama、プロンプト、レビュー処理
├─ utils/        # チャンク分割、Markdown生成
├─ tests/        # 外部通信不要の単体テスト
├─ requirements.txt
└─ README.md
```

## 制約事項

- Wordへのコメント書き込み、OCR、履歴DB、認証、複数文書の一括処理は未実装です。
- PDFからの抽出順序はPDF内部のテキスト配置に依存します。複雑な段組みやテキスト
  ボックスでは、Word上の見た目と順序が異なることがあります。
- チャンクをまたぐ矛盾は、各チャンクを個別に送信するため検出できない場合があります。
- LLMが有効なJSONを返すことは保証されません。失敗チャンクは画面で確認できます。
- Ollamaモデルのコンテキスト長に合わせてチャンク上限を調整してください。
- Streamlitプロセスが強制終了された場合、OSの一時領域にファイルが残る可能性は
  ゼロではありません。通常終了・例外時は自動削除されます。

## トラブルシューティング

### Word変換に失敗する

- デスクトップ版Microsoft Wordが起動できるか確認します。
- 対象DOCXをWordで直接開き、修復ダイアログや保護ビューを解消します。
- Wordのモーダルダイアログが背面で待機していないか確認します。
- PythonとWordの実行ユーザーを同じにします。Windowsサービス上の無人実行は非推奨です。

### モデル一覧を取得できない

- `ollama serve`が動作しているか確認します。
- `http://localhost:11434/api/tags`へ接続できるか確認します。
- 社内ホストの場合は`OLLAMA_ALLOWED_HOSTS`へホスト名/IPを追加し、アプリを再起動します。
- OSやプロキシ設定にかかわらず、このアプリのOllama通信は環境プロキシを使用しません。

### モデルが存在しない

`ollama list`で名前を確認し、必要なら`ollama pull <model>`を実行します。タグを含む
正確なモデル名を選択または入力してください。

### 対象ページにテキストがない

画像スキャンの文書、図形内だけに文字がある文書、特殊な埋め込み形式では抽出できない
場合があります。このPoCにはOCR機能がありません。

### タイムアウトする

`.env`の`OLLAMA_TIMEOUT_SECONDS`を増やすか、画面のチャンク上限を小さくします。

