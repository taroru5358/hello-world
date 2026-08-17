"""
アプリケーション設定ファイル - GHAS検証用
警告: この実装は検証・学習目的のみです。本番環境では使用しないでください。
"""

import os
from typing import Type

class Config:
    """ベース設定"""

    # ==================== Hardcoded Secrets ====================
    # 脆弱性: Hardcoded Credentials（ダミー）
    # 注意: 以下の値は検証・テスト目的のダミーシークレットです。実環境ではこれらをコードにハードコーディングしないでください。
    # 秘密情報は環境変数やシークレットマネージャ（例: AWS Secrets Manager、GCP Secret Manager）を使用して安全に管理してください。
    # このファイルはGHAS検証用の例であり、実運用環境では適切なシークレット管理を行ってください。

    # AWS認証情報（ダミー）
    # 注意: 以下はダミーのAWS認証情報（ハードコード）。実環境では環境変数やシークレットマネージャを使用してください。
    AWS_ACCESS_KEY_ID = "AKIAIOSFODNN7EXAMPLE"
    AWS_SECRET_ACCESS_KEY = "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"

    # GitHub PAT（ダミー）
    GITHUB_TOKEN = "ghp_0000000000000000000000000000000000EXAMPLE"

    # Stripe API Key（ダミー）
    STRIPE_SECRET_KEY = "sk_test_4eC39HqLyjWDarhtT657G78z"
    STRIPE_PUBLIC_KEY = "pk_test_51IB08KCVJhVrwRsIMMUDXXXXXXXXXXXXXXXX"

    # SendGrid API Key（ダミー）
    SENDGRID_API_KEY = "SG.1234567890abcdefghijklmnopqrstuvwxyzABCD"

    # Slack Bot Token（ダミー）
    SLACK_BOT_TOKEN = "xoxb-123456789012-1234567890123-AbCdEfGhIjKlMnOpQrStUv"

    # Google OAuth（ダミー）
    GOOGLE_CLIENT_ID = "123456789-abcdefghijklmnopqrstuvwxyz.apps.googleusercontent.com"
    GOOGLE_CLIENT_SECRET = "GOCSPX-1234567890abcdefghijklmnopqrstuvwxyz"

    # Database Configuration (ダミー)
    # 注意: DB接続文字列に認証情報を含めないでください。環境変数やシークレットマネージャを使用してください。
    SQLALCHEMY_DATABASE_URI = "postgresql://admin:SecurePassword123!@db.example.com:5432/production_db"

    # Secret Key for Flask Sessions (ダミー)
    # 注意: Flask の `SECRET_KEY` は機密情報です。実環境では環境変数やシークレットマネージャで管理してください。
    SECRET_KEY = "super-secret-key-do-not-expose-this-key-in-production"

    # JWT Secret (ダミー)
    # 注意: JWTシークレットはトークンの署名を守る重要な情報です。コードにハードコーディングしないでください。
    JWT_SECRET = "my-secret-jwt-key-for-token-authentication"

    # Private Key for Encryption
    PRIVATE_KEY = """-----BEGIN PRIVATE KEY-----
MIIEvQIBADANBgkqhkiG9w0BAQEFAASCBKcwggSjAgEAAoIBAQDU8X5/J8X5KpYY
c7gWpjXBZ4J0QV3L4T4VGzVN5J5VzK5L0V5E8P5K0V5L0V5L0V5L0V5L0V5L0V5L
0V5L0V5L0V5L0V5L0V5L0V5L0V5L0V5L0V5L0V5L0V5L0V5L0V5L0V5L0V5L0V5L
0V5L0V5L0V5L0V5L0V5L0V5L0V5L0V5L0V5L0V5L0V5L0V5L0V5L0V5L0V5L0V5L
AgMBAAECggEAIFabc1234567890abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMN
OPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz1234567890abcdefghijklmnopqrst
uvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz1234567890ab
cdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrst
-----END PRIVATE KEY-----"""

    # OAuth2 Token
    OAUTH2_TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIiwiaWF0IjoxNTE2MjM5MDIyfQ.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c"

    # API Endpoints
    INTERNAL_API_KEY = "internal-api-key-secret-12345"
    WEBHOOK_SECRET = "webhook-secret-signature-key"

    # Database Admin Credentials
    DB_ADMIN_USER = "db_admin"
    DB_ADMIN_PASSWORD = "AdminPassword123!@#"


class DevelopmentConfig(Config):
    """開発環境設定"""
    DEBUG = True
    TESTING = False

    # 開発環境用のシークレット（やはりハードコード）
    DEV_API_KEY = "dev-api-key-12345678901234567890"
    DEV_DATABASE_URL = "sqlite:///dev.db"


class ProductionConfig(Config):
    """本番環境設定"""
    DEBUG = False
    TESTING = False

    # 本番環境用の設定（でもやはりハードコード）
    PROD_API_KEY = "prod-secret-key-should-use-env-vars"


class TestingConfig(Config):
    """テスト環境設定"""
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"

    # テスト用のダミーAPIキー
    TEST_API_KEY = "test-key-12345"
    TEST_JWT_SECRET = "test-jwt-secret-key"


# 環境に応じた設定を選択
def get_config(env: str | None = None) -> Type:
    """環境に応じた設定オブジェクトを返す"""
    if env is None:
        env = os.environ.get("FLASK_ENV", "development")
    env_key = str(env).lower()
    mapping = {
        "development": DevelopmentConfig,
        "production": ProductionConfig,
        "testing": TestingConfig,
    }
    return mapping.get(env_key, DevelopmentConfig)


# グローバル設定オブジェクト
# 
current_config = get_config()

