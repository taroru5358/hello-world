"""
脆弱性を含むPythonアプリケーション - GHAS検証用
警告: この実装は検証・学習目的のみです。本番環境では使用しないでください。
"""
import os
import sys
import pickle
import sqlite3
from pathlib import Path


# ==================== SQL Injection ====================
def get_user_by_name(username: str):
    """
    脆弱性: SQL Injection
    ユーザー入力を直接SQLクエリに埋め込んでいる
    """
    conn = sqlite3.connect(':memory:')
    cursor = conn.cursor()

    # 脆弱なクエリ構築
    query = f"SELECT * FROM users WHERE username = '{username}'"
    cursor.execute(query)

    return cursor.fetchall()


def search_products(search_term: str):
    """
    脆弱性: SQL Injection
    パラメータ化クエリを使わずにユーザー入力を直接埋め込む
    """
    conn = sqlite3.connect(':memory:')
    cursor = conn.cursor()

    # 脆弱なクエリ
    sql = "SELECT * FROM products WHERE name LIKE '%" + search_term + "%'"
    cursor.execute(sql)

    return cursor.fetchall()


# ==================== Command Injection ====================
def execute_system_command(user_input: str):
    """
    脆弱性: Command Injection
    ユーザー入力をシェルコマンドに直接渡している
    """
    os.system(f"ls -la {user_input}")


def ping_host(hostname: str):
    """
    脆弱性: Command Injection
    ホスト名をpingコマンドに直接渡している
    """
    result = os.system(f"ping -c 1 {hostname}")
    return result == 0


# ==================== Path Traversal ====================
def read_file(filename: str):
    """
    脆弱性: Path Traversal
    ユーザー入力のパスを検証せずに使用している
    """
    filepath = f"/var/www/uploads/{filename}"

    with open(filepath, 'r') as f:
        return f.read()


def get_config_file(config_name: str):
    """
    脆弱性: Path Traversal
    ../ を使ったディレクトリの上位階層へのアクセスが可能
    """
    config_dir = "/app/config/"
    full_path = config_dir + config_name

    with open(full_path, 'r') as f:
        return f.read()


# ==================== Hardcoded Credentials ====================
class DatabaseConnection:
    """
    脆弱性: Hardcoded Credentials
    コード内にハードコードされたデータベース認証情報
    """
    def __init__(self):
        self.host = "db.example.com"
        self.user = "admin"
        self.password = "SecurePassword123!"  # ハードコードされたパスワード
        self.database = "production_db"

    def connect(self):
        # 接続処理...
        pass


# ==================== Insecure Deserialization ====================
def deserialize_user_data(data: bytes):
    """
    脆弱性: Insecure Deserialization
    untrusted なデータを pickle.loads() で直接デシリアライズ
    任意コード実行の可能性がある
    """
    user_object = pickle.loads(data)
    return user_object


def load_session_data(session_bytes: bytes):
    """
    脆弱性: Insecure Deserialization
    セッションデータをpickleで復元するが、入力を検証していない
    """
    try:
        session_data = pickle.loads(session_bytes)
        return session_data
    except Exception as e:
        print(f"Error loading session: {e}")
        return None


# ==================== Weak Cryptography ====================
import hashlib

def hash_password_insecure(password: str):
    """
    脆弱性: Weak Cryptography
    SHA-1でハッシュ化（脆弱なハッシュ関数）
    salting も使用していない
    """
    return hashlib.sha1(password.encode()).hexdigest()


# ==================== Information Disclosure ====================
def get_error_details(exception: Exception):
    """
    脆弱性: Information Disclosure
    例外の詳細をそのままユーザーに返している
    スタックトレースが露出する可能性
    """
    error_details = {
        'error': str(exception),
        'type': type(exception).__name__,
        'traceback': sys.exc_info()
    }
    return error_details


# ==================== Insecure Random ====================
import random

def generate_reset_token():
    """
    脆弱性: Insecure Random
    random モジュールは暗号学的に安全でない
    """
    token = ''.join(random.choice('0123456789abcdef') for _ in range(32))
    return token


# ==================== Use After Free ====================
def unsafe_reference():
    """
    脆弱性の可能性: リソースの不適切な管理
    """
    f = open('/tmp/temp_file.txt', 'w')
    f.write('data')
    # ファイルを閉じずに返す
    return f


def main():
    """メイン処理"""
    print("Vulnerable App - GHAS Detection Test")

    # テスト用の呼び出し
    try:
        get_user_by_name("' OR '1'='1")
        execute_system_command("../../../etc/passwd")
        ping_host("8.8.8.8; cat /etc/passwd")
    except Exception as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    main()
