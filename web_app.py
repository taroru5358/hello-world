"""
脆弱なFlask Webアプリケーション - GHAS検証用
警告: この実装は検証・学習目的のみです。本番環境では使用しないでください。
"""
from flask import Flask, render_template_string, request, session, redirect
import sqlite3
import os

app = Flask(__name__)
app.secret_key = "insecure-secret-key-12345"  # 脆弱なシークレットキー


# ==================== Cross-Site Scripting (XSS) ====================
@app.route('/greet', methods=['GET', 'POST'])
def greet():
    """
    脆弱性: Stored/Reflected XSS
    ユーザー入力をエスケープせずにHTMLに埋め込んでいる
    """
    name = request.args.get('name', 'Guest')

    # 危険な操作: user_input を直接HTMLに埋め込む
    html = f"""
    <html>
        <body>
            <h1>こんにちは、{name}さん！</h1>
            <p>あなたの入力: {name}</p>
        </body>
    </html>
    """

    return render_template_string(html)


@app.route('/search', methods=['GET'])
def search():
    """
    脆弱性: Reflected XSS
    検索クエリをそのままページに表示
    """
    query = request.args.get('q', '')

    # 脆弱な実装
    html = f"""
    <html>
        <body>
            <h1>検索結果</h1>
            <p>'{query}' の検索結果:</p>
            <ul>
                <li>結果1</li>
                <li>結果2</li>
            </ul>
        </body>
    </html>
    """

    return render_template_string(html)


@app.route('/comment', methods=['POST'])
def post_comment():
    """
    脆弱性: Stored XSS
    ユーザーのコメントをデータベースに保存し、
    後で他のユーザーに表示する際にエスケープしていない
    """
    comment = request.form.get('comment', '')
    user_id = request.form.get('user_id', '')

    # コメントをデータベースに保存
    conn = sqlite3.connect(':memory:')
    cursor = conn.cursor()

    # 脆弱なSQLとXSS
    sql = f"INSERT INTO comments (user_id, content) VALUES ('{user_id}', '{comment}')"
    cursor.execute(sql)
    conn.commit()

    return "コメントを投稿しました"


@app.route('/display_comment/<comment_id>')
def display_comment(comment_id):
    """
    脆弱性: Stored XSS + IDOR (Insecure Direct Object Reference)
    権限チェックなしでコメントを取得し、エスケープせずに表示
    """
    conn = sqlite3.connect(':memory:')
    cursor = conn.cursor()

    # 権限チェックなし
    sql = f"SELECT content FROM comments WHERE id = {comment_id}"
    cursor.execute(sql)
    result = cursor.fetchone()

    if result:
        content = result[0]
        # エスケープなしで出力
        html = f"""
        <html>
            <body>
                <h1>コメント</h1>
                <p>{content}</p>
            </body>
        </html>
        """
        return render_template_string(html)
    else:
        return "コメントが見つかりません"


# ==================== CSRF (Cross-Site Request Forgery) ====================
@app.route('/transfer', methods=['POST'])
def transfer_money():
    """
    脆弱性: CSRF (Cross-Site Request Forgery)
    CSRF トークンの検証がない
    """
    to_account = request.form.get('to_account')
    amount = request.form.get('amount')
    user_id = session.get('user_id')

    # CSRF保護なし

    # お金を転送する処理
    return f"${amount} を {to_account} に転送しました"


@app.route('/delete-account', methods=['POST'])
def delete_account():
    """
    脆弱性: CSRF
    確認トークンやメール確認なしでアカウント削除
    """
    user_id = session.get('user_id')

    # 直接削除（CSRF保護なし）
    conn = sqlite3.connect(':memory:')
    cursor = conn.cursor()
    cursor.execute(f"DELETE FROM users WHERE id = {user_id}")
    conn.commit()

    return "アカウントを削除しました"


# ==================== Insecure Direct Object Reference (IDOR) ====================
@app.route('/user/<user_id>')
def get_user_profile(user_id):
    """
    脆弱性: IDOR (Insecure Direct Object Reference)
    user_id をそのまま使って、権限チェックなしでユーザー情報を取得
    """
    # 権限チェックなし
    conn = sqlite3.connect(':memory:')
    cursor = conn.cursor()

    # 直接ユーザーIDで検索（認可チェックなし）
    sql = f"SELECT id, name, email, phone FROM users WHERE id = {user_id}"
    cursor.execute(sql)
    user = cursor.fetchone()

    if user:
        return {
            'id': user[0],
            'name': user[1],
            'email': user[2],
            'phone': user[3]
        }
    else:
        return "ユーザーが見つかりません"


@app.route('/order/<order_id>')
def get_order_details(order_id):
    """
    脆弱性: IDOR
    認証されたユーザーなら誰でも他人の注文情報にアクセス可能
    """
    # セッションユーザーの確認のみ（所有者確認なし）
    if 'user_id' not in session:
        return "ログインしてください", 401

    conn = sqlite3.connect(':memory:')
    cursor = conn.cursor()

    # order_id だけで検索（所有者確認なし）
    sql = f"SELECT * FROM orders WHERE id = {order_id}"
    cursor.execute(sql)
    order = cursor.fetchone()

    if order:
        return {"order": order}
    else:
        return "注文が見つかりません"


# ==================== Insecure Deserialization in Templates ====================
@app.route('/load-profile', methods=['POST'])
def load_profile():
    """
    脆弱性: Insecure Template Usage
    テンプレート内で unsafe な操作
    """
    profile_data = request.form.get('profile')

    # ユーザー入力を直接テンプレートに埋め込む
    html = f"""
    <html>
        <body>
            <h1>プロフィール</h1>
            {profile_data}
        </body>
    </html>
    """

    return render_template_string(html)


# ==================== Weak Authentication ====================
@app.route('/login', methods=['POST'])
def login():
    """
    脆弱性: Weak Authentication
    パスワードをプレーンテキストで検証
    """
    username = request.form.get('username')
    password = request.form.get('password')

    # パスワードをプレーンテキストで比較（脆弱）
    conn = sqlite3.connect(':memory:')
    cursor = conn.cursor()

    sql = f"SELECT * FROM users WHERE username = '{username}' AND password = '{password}'"
    cursor.execute(sql)
    user = cursor.fetchone()

    if user:
        session['user_id'] = user[0]
        session['username'] = user[1]
        return "ログインしました"
    else:
        return "ログイン失敗"


# ==================== Insecure File Upload ====================
@app.route('/upload', methods=['POST'])
def upload_file():
    """
    脆弱性: Insecure File Upload
    ファイル名を検証せず、実行可能ファイルのアップロードを許可
    """
    if 'file' not in request.files:
        return "ファイルがありません"

    file = request.files['file']

    # ファイル名を検証しない危険
    filename = file.filename
    upload_dir = '/app/uploads/'

    # 脆弱な実装：ファイル名をそのまま使用
    file.save(os.path.join(upload_dir, filename))

    return f"ファイル {filename} をアップロードしました"


# ==================== Information Disclosure ====================
@app.route('/debug-info')
def debug_info():
    """
    脆弱性: Information Disclosure
    内部情報（環境変数、システム情報）を露出
    """
    info = {
        'python_version': os.sys.version,
        'environment': dict(os.environ),
        'app_config': app.config,
    }
    return info


# ==================== SQL Injection in Web App ====================
@app.route('/filter-products')
def filter_products():
    """
    脆弱性: SQL Injection (Web版)
    """
    category = request.args.get('category', '')
    price_min = request.args.get('price_min', '0')

    conn = sqlite3.connect(':memory:')
    cursor = conn.cursor()

    # 脆弱なクエリ
    sql = f"SELECT * FROM products WHERE category = '{category}' AND price >= {price_min}"
    cursor.execute(sql)

    products = cursor.fetchall()
    return {'products': products}


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
