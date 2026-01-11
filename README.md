# GitHub Advanced Security (GHAS) 検証用リポジトリ

## 概要

このリポジトリは **GitHub Advanced Security (GHAS)** の機能を検証・学習するために、意図的にセキュリティ脆弱性を含むサンプルコードを提供しています。

## ⚠️ 警告

**このコードは本番環境では絶対に使用しないでください。**
- このリポジトリはGHASの検証目的のみです
- コード内には既知のセキュリティ脆弱性が含まれています
- 学習・研究・デモンストレーション目的のためだけに使用してください

## GHAS検証対象

このリポジトリは以下のGHAS機能を検証するように構成されています：

### 1. Code Scanning (CodeQL)
**目的**: セキュリティ脆弱性の自動検出

含まれている脆弱性パターン:
- SQL Injection
- Command Injection
- Cross-Site Scripting (XSS)
- Cross-Site Request Forgery (CSRF)
- Path Traversal
- Insecure Deserialization
- Hardcoded Credentials
- Weak Cryptography
- Insecure Direct Object Reference (IDOR)

**関連ファイル**:
- `vulnerable_app.py` - バックエンドの脆弱なコード
- `web_app.py` - Flaskベースの脆弱なWebアプリケーション

### 2. Secret Scanning
**目的**: API キーやトークンなどの機密情報の検出

含まれているダミー情報:
- AWS Access Keys
- GitHub Personal Access Tokens
- Stripe API Keys
- Slack Bot Tokens
- Google OAuth credentials
- Database credentials
- Private keys

**関連ファイル**:
- `.env.example` - ダミーシークレットの例
- `config.py` - ハードコードされたダミーAPI キー

### 3. Dependency Review (Dependabot)
**目的**: 依存パッケージの脆弱性検出

含まれている脆弱な依存関係:
- Flask 0.12.2 (複数のセキュリティ脆弱性)
- requests 2.6.0 (古いバージョン)
- Pillow 6.0.0 (CVE脆弱性あり)
- PyYAML 3.12 (任意コード実行の脆弱性)
- Django 1.11.0 (セキュリティ問題)
- その他多数

**関連ファイル**:
- `requirements.txt` - 脆弱な依存関係リスト

## GHAS機能の確認方法

### Code Scanning アラートの確認
1. GitHubリポジトリの **Security** タブをクリック
2. 左メニューの **Code scanning alerts** を確認
3. 検出された脆弱性のリストと詳細な説明を確認

### Secret Scanning アラートの確認
1. **Security** タブの **Secret scanning** をクリック
2. 検出されたシークレットのリストを確認
3. 各シークレットの種類と場所を確認

### Dependabot アラートの確認
1. **Security** タブの **Dependabot alerts** をクリック
2. 脆弱な依存関係のリストを確認
3. 更新提案を確認（自動PRが作成される場合もあります）

### GitHub Actions ワークフロー実行
1. **Actions** タブをクリック
2. **CodeQL Analysis** ワークフローの実行状況を確認
3. ワークフローログで脆弱性スキャンのプロセスを確認

## ファイル構成

```
.
├── README.md                           # このファイル
├── .gitignore                          # Python標準の除外設定
├── .env.example                        # ダミーシークレット（Secret Scanningテスト用）
├── config.py                           # ハードコードされたシークレット
├── vulnerable_app.py                   # CLI/バックエンド脆弱性コード
├── web_app.py                          # Flask Webアプリの脆弱性コード
├── requirements.txt                    # 脆弱な依存関係
├── .github/
│   ├── dependabot.yml                  # Dependabot設定
│   └── workflows/
│       └── codeql-analysis.yml         # CodeQL分析ワークフロー
└── plans/
    └── 2026-01-11_GHAS検証セットアップ.md  # 実装計画書
```

## セットアップ手順

このリポジトリをクローン・フォークした場合:

1. GitHub設定でCode Securityを有効化
   - Settings > Code security and analysis
   - Dependabot alerts: ON
   - Secret scanning: ON

2. Actions を確認
   - コード変更をpushするとCodeQLが自動実行

3. Security タブでアラートを確認

## 学習用コンテンツ

各脆弱性についての詳細は以下を参照:
- [OWASP Top 10](https://owasp.org/www-project-top-ten/)
- [CWE (Common Weakness Enumeration)](https://cwe.mitre.org/)
- [GitHub Security Documentation](https://docs.github.com/en/code-security)

## ライセンス

MIT License（参考用）

## 免責事項

このコードは教育目的のサンプルです。以下をご承知ください：

- 本番環境での使用は厳禁
- セキュリティ脆弱性が意図的に含まれています
- すべてのダミーシークレットは無効です
- 本来のコード品質基準を満たしていません
