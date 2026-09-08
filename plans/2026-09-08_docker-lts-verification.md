# Dockerfile LTS切れ検証計画

## 目的・背景
- hello-worldはGHAS検証用だがDockerfileがなく、Dependabot設定はpipのみ
- DependabotのdockerエコシステムがベースイメージのLTS切れ・EOLを検知できるか検証する
- 事前調査の結論: Dependabotはタグ追従PRのみでEOL警告なし。検知はTrivy等の役割。対比で実証する

## 実装方針
- わざとEOL済みベースを使用: `FROM python:3.8-slim`
  * Python 3.8は2024-10-07にEOL、ベースOS Debian 11 bullseyeも2026-08末でLTS終了
  * Pythonアプリなので自然な選択。ビルド成功を優先し`pip install`は実行しない
- Dependabotにdockerエントリ追加: version updatesのPRが出るか観察
- TrivyでEOLゲート追加: `--exit-on-eol`相当でCI失敗させ、Dependabotとの役割分担を示す
- 既存のpip設定・CodeQLには触れない

## 影響ファイル
- `Dockerfile` (新規)
- `.github/dependabot.yml` (dockerエントリ追加)
- `.github/workflows/trivy-eol.yml` (新規)
- `plans/2026-09-08_docker-lts-verification.md` (本ファイル)

## 実装ステップ
1. Dockerfile新規作成 (EOLベース、コメントにEOL日記載)
2. dependabot.ymlにdocker設定追加 (weekly)
3. trivy-eol.yml追加 (build→scan、SARIFをCode Scanningにも送る)
4. `docker build`疎通 + `actionlint`相当のYAML目視確認
5. コミット・push (privateリポジトリ、main単独運用)

## リスクと対策
- 古いrequirementsのpip install失敗でbuild失敗→今回はRUN pipを入れず回避
- Trivyのexit-on-eolフラグ名変更→公式ドキュメントで確認してから確定
- 意図的脆弱イメージの取り扱い→README警告の範囲内、public化しない(private維持)

## 完了条件
- mainに3ファイル反映
- ActionsでTrivyがEOL検出して失敗すること
- DependabotがEOL警告を出さない(タグ追従PRのみ/なし)ことを確認

## 変更履歴
- 2026-09-08: 初版作成
- 2026-09-08: ベースをpython:3.8-slim→python:3.8-slim-bullseyeに変更。理由: 素タグはbookworm再ビルドでOSがEOLにならず、Trivy --exit-on-eolが反応しなかった (実測debian 12.7)。bullseyeピンでdebian 11.11のEOL検出を確認。
