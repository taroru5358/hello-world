# GHAS検証用: わざとEOL済みベースを使用 (LTS切れ検知の対比検証用)
# - Python 3.8 は 2024-10-07 に EOL (endoflife.date/python)
# - bullseye にピン留めする理由: 素の python:3.8-slim は bookworm に
#   再ビルドされており OS が EOL にならない (2026-09-08 実測で debian 12.7 を検出)。
#   bullseye 指定で Debian 11.11 が Trivy --exit-on-eol に引っかかることを確認済み。
# - Dependabot docker はタグ追従PRのみで EOL 警告を出さないことを検証する
# - EOL 検知は Trivy --exit-on-eol が担当 (.github/workflows/trivy-eol.yml)
# 警告: 本番環境では絶対に使用しないこと
FROM python:3.13-slim-bullseye

WORKDIR /app

COPY requirements.txt ./

# わざと pip install しない: 古い依存 (Flask 0.12.2 等) のビルド失敗を避け、
# ベースOSのEOL検出に集中するため。アプリ動作検証は対象外。
COPY . .

EXPOSE 5000

CMD ["python", "web_app.py"]
