# GitHub Actions キャッシュ活用の有無による Web テスト実行時間の比較

- 作成日: 2026-11-16
- 作成者モデル: Claude Opus 5.5 (claude-opus-5-5)
- 対象: `bench/web-app/`、`.github/workflows/cache-benchmark.yml`、`scripts/bench/`

## 目的・背景

Web アプリのテスト（lint / 型チェック / unit test / build / E2E）を GitHub Actions で回すとき、
2026-11 時点のキャッシュ機能をフルに使った場合と使わない場合で、どれだけ実行時間が変わるかを実測する。
結果は非エンジニアにも読める HTML にまとめ、Actions Artifact として保存し、リポジトリ About にその URL を置く。

## リサーチ結果（一次ソース）

| 項目 | 内容 | 出典 |
|---|---|---|
| actions/cache | 最新 v6.1.0（2026-06-26）。v5 以降 node24 runtime、cache service v2 | github.com/actions/cache/releases |
| actions/setup-node | 最新 v7.1.0。**v5.0.0 から `package.json` の `packageManager` があると自動でキャッシュが有効**。無効化は `package-manager-cache: false` | github.com/actions/setup-node/releases/tag/v5.0.0 |
| 容量 | リポジトリ既定 10 GB（超過分は課金で拡張可）。7 日アクセスなしで削除。超過時は古い順に追い出し | docs.github.com dependency-caching |
| レート | 保存 200 件/分、復元 1500 件/分 | 同上 |
| スコープ | 自ブランチ → default branch の順に探索。兄弟ブランチ不可 | 同上 |
| Playwright | 公式は「ブラウザバイナリのキャッシュは非推奨（復元時間がダウンロードと同程度、Linux の OS 依存は キャッシュ不可）」 | playwright.dev/docs/ci |

## 比較する構成（variant）

| variant | 内容 |
|---|---|
| `none` | キャッシュ一切なし。`package-manager-cache: false`、`npm ci`、`playwright install --with-deps` |
| `setup-node` | 定番の最小構成。`setup-node` の `cache: npm`（~/.npm のみ）。他は none と同じ |
| `full` | フル活用。~/.npm に加えて `node_modules`（hit 時 `npm ci` を省略）、Playwright ブラウザ（hit 時は `install-deps` のみ）、ESLint `--cache`、tsc `incremental`、Vitest cache |

## 実装方針

- トリガーは `workflow_dispatch` のみ（inputs: `iterations` 1〜5）。Ubuntu のみ、Node 24 の単一バージョン
- 計測の公平性
  - キャッシュキーに `run_id` を含め、run ごとに独立させる（前回 run の残骸に左右されない）
  - `prime` job（full の cold run）でキャッシュを作成 → 各 variant を `iterations` 回ずつ matrix 並列で計測
  - `cleanup` job が当該 run のキャッシュを `gh cache delete` で削除（容量 10 GB を圧迫しない）
- 時間の取得: `report` job が GitHub API（jobs / steps の started_at・completed_at）から取得。各 job の step 名を共通化して工程別に比較
- レポート: Python 標準ライブラリのみで単一 HTML を生成（外部 CDN なし、SVG で棒グラフ）→ `upload-artifact`（retention 90 日）
- About: report の artifact URL（`https://github.com/<owner>/<repo>/actions/runs/<id>/artifacts/<artifact_id>`）を `gh repo edit --homepage` で設定（ローカルから手動実行）

## クレデンシャル対策

- 使うのは `GITHUB_TOKEN` のみ。job ごとに最小 `permissions`（計測: `contents: read`、report: `actions: read`、cleanup: `actions: write`）
- `actions/checkout` は `persist-credentials: false`
- HTML には時間・キャッシュ hit 情報・run URL のみ。トークンやヘッダは出力しない
- 第三者 Action は commit SHA で固定

## 影響ファイル

- `bench/web-app/**`（新規）
- `.github/workflows/cache-benchmark.yml`（新規）
- `scripts/bench/make_report.py`（新規）
- `docs/github/actions-cache-benchmark.md`（新規・説明）

## リスクと対策

- 1 回の計測はランナー個体差でぶれる → iterations で複数回、中央値で比較
- default branch にないと workflow_dispatch できない → PR で main へ取り込む
- Copilot review ruleset が PR に付く → マージを阻害しない想定

## 完了条件

- workflow が成功し、HTML artifact が生成される
- HTML を Chrome で開いて表示確認（スクリーンショット・コンソールエラーなし）
- About に artifact URL を設定
- 個人ID・クレデンシャルが HTML / リポジトリ差分に含まれないことを確認
