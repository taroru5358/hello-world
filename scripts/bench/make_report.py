#!/usr/bin/env python3
"""cache-benchmark.yml の結果から HTML レポートを作る（標準ライブラリのみ）。

入力:
  --jobs  GitHub API の jobs を 1 行 1 JSON にしたファイル
  --meta  各計測 job が出力したメタ情報 JSON のディレクトリ
出力:
  --out      単一 HTML（外部リソースなし）
  --summary  GITHUB_STEP_SUMMARY 用 Markdown

トークンなどの秘密情報は入力にも出力にも含めない。
"""

from __future__ import annotations

import argparse
import html
import json
import os
import statistics
from datetime import UTC, datetime
from pathlib import Path

APPS = ["small", "large"]
APP_LABEL = {"small": "小さなアプリ", "large": "大きなアプリ"}
APP_DESC = {
    "small": "React + Vite の Todo アプリ。ソース数ファイル、テスト 3 件。",
    "large": "MUI・react-router・TanStack Query・zod・Storybook などを入れ、"
    "300 機能分のソース（スキーマ・ロジック・テスト・MUI コンポーネント）を生成したアプリ。"
    "Lint は型情報つき（recommendedTypeChecked）。",
}
VARIANTS = ["none", "setup-node", "full"]
VARIANT_LABEL = {
    "none": "キャッシュなし",
    "setup-node": "setup-node の cache: npm だけ",
    "full": "フル活用",
}
VARIANT_DESC = {
    "none": "毎回まっさらな状態から実行する。setup-node の自動キャッシュも明示的に無効化。",
    "setup-node": "よく見かける最小構成。npm のダウンロードキャッシュ（~/.npm）だけを復元し、npm ci は毎回実行する。"
    "Docker と Trivy はキャッシュなし。",
    "full": "node_modules を丸ごと復元して npm ci を省略（ESLint・tsc・Vitest のキャッシュも同梱）。"
    "Playwright のブラウザ本体、Docker の BuildKit レイヤー（type=gha）、Trivy の脆弱性 DB もキャッシュする。",
}

# (key, 表示名, 色) — 色は明暗どちらでも判別できるよう彩度・明度を揃えたもの
PHASES = [
    ("prepare", "準備（job 起動・checkout・Node・Buildx）", "#8c96a8"),
    ("generate", "ソース生成・1 ファイル変更", "#a1887f"),
    ("restore", "キャッシュ復元", "#2f9e8f"),
    ("deps", "依存インストール", "#d9822b"),
    ("browsers", "ブラウザ準備", "#c4504a"),
    ("lint", "Lint", "#6a5acd"),
    ("typecheck", "型チェック", "#3d7dd8"),
    ("unit", "Unit test", "#4caf50"),
    ("build", "Build", "#b8860b"),
    ("e2e", "E2E", "#c2185b"),
    ("docker", "Docker ビルド", "#0277bd"),
    ("trivy", "Trivy スキャン", "#7b1fa2"),
    ("save", "キャッシュ保存", "#00838f"),
    ("other", "その他", "#b0b0b0"),
]
PHASE_LABEL = {k: label for k, label, _ in PHASES}

# キャッシュ対象ごとの比較。工程の時間に、そのキャッシュの復元・保存にかかった時間を足して比べる
CACHES = [
    (
        "deps",
        "npm 依存（node_modules・~/.npm）",
        "依存インストール ＋ 復元・保存",
    ),
    (
        "lint_tc",
        "ESLint・TypeScript のキャッシュ",
        "Lint ＋ 型チェック（キャッシュは node_modules に同梱）",
    ),
    ("unit", "Vitest のキャッシュ", "Unit test（キャッシュは実行順の最適化のみ）"),
    ("browsers", "Playwright ブラウザ", "ブラウザ準備 ＋ 復元・保存"),
    (
        "docker",
        "Docker ビルド（BuildKit type=gha）",
        "Docker ビルド（キャッシュの取得・書き出し込み）",
    ),
    ("trivy", "Trivy 脆弱性 DB", "Trivy スキャン（DB の取得・保存込み）"),
]


def phase_of(step: str) -> str:
    if step in ("Docker build", "Post Docker build"):
        return "docker"
    if step in ("Trivy scan", "Post Trivy scan"):
        return "trivy"
    if step.startswith(("Post Restore cache", "Post Setup Node")):
        return "save"
    if step.startswith("Restore cache"):
        return "restore"
    if step in ("Generate sources", "Simulate small change"):
        return "generate"
    if step in (
        "Set up job",
        "Checkout",
        "Resolve Playwright version",
    ) or step.startswith(
        ("Setup Node", "Setup Docker Buildx", "Post Setup Docker Buildx")
    ):
        return "prepare"
    return {
        "Install dependencies": "deps",
        "Install Playwright browsers": "browsers",
        "Lint": "lint",
        "Typecheck": "typecheck",
        "Unit test": "unit",
        "Build": "build",
        "E2E": "e2e",
    }.get(step, "other")


def cache_of(step: str) -> str | None:
    """キャッシュ別比較でどの行に数えるか。"""
    if step in (
        "Install dependencies",
        "Setup Node (cache npm)",
        "Post Setup Node (cache npm)",
    ) or (step.endswith(("cache node_modules", "cache npm"))):
        return "deps"
    if step in ("Lint", "Typecheck"):
        return "lint_tc"
    if step == "Unit test":
        return "unit"
    if step == "Install Playwright browsers" or step.endswith(
        "cache Playwright browsers"
    ):
        return "browsers"
    if step in ("Docker build", "Post Docker build"):
        return "docker"
    if step in ("Trivy scan", "Post Trivy scan"):
        return "trivy"
    return None


def ts(s: str | None) -> datetime | None:
    return datetime.fromisoformat(s) if s else None


def secs(a: str | None, b: str | None) -> float | None:
    x, y = ts(a), ts(b)
    return (y - x).total_seconds() if x and y else None


def median(xs: list[float]) -> float | None:
    return statistics.median(xs) if xs else None


def fmt(s: float | None) -> str:
    if s is None:
        return "—"
    s = round(s)
    return f"{s // 60}分{s % 60:02d}秒" if s >= 60 else f"{s}秒"


def load(jobs_path: Path, meta_dir: Path) -> list[dict]:
    metas = {}
    for p in sorted(meta_dir.glob("*.json")) if meta_dir.exists() else []:
        m = json.loads(p.read_text())
        metas[m["job"]] = m
    rows = []
    for line in jobs_path.read_text().splitlines():
        if not line.strip():
            continue
        j = json.loads(line)
        m = metas.get(j["name"].split(" / ")[-1])
        if not m:
            continue  # reset / report / cleanup などの集計対象外 job
        phases = {k: 0.0 for k, _, _ in PHASES}
        caches = {k: 0.0 for k, _, _ in CACHES}
        for st in j.get("steps", []):
            d = secs(st.get("started_at"), st.get("completed_at"))
            if d is None or st.get("conclusion") == "skipped":
                continue
            phases[phase_of(st["name"])] += d
            c = cache_of(st["name"])
            if c:
                caches[c] += d
        rows.append(
            {
                **m,
                "app": m.get("app", "small"),
                "conclusion": j.get("conclusion"),
                "url": j.get("html_url", ""),
                "total": secs(j.get("started_at"), j.get("completed_at")),
                "phases": phases,
                "caches": caches,
            }
        )
    rows.sort(
        key=lambda r: (
            APPS.index(r["app"]),
            VARIANTS.index(r["variant"]),
            r["phase"] != "cold",
            r["iteration"],
        )
    )
    return rows


def aggregate(rows: list[dict]) -> dict:
    agg = {}
    for app in APPS:
        for v in VARIANTS:
            for ph in ("cold", "warm"):
                rs = [
                    r
                    for r in rows
                    if r["app"] == app
                    and r["variant"] == v
                    and r["phase"] == ph
                    and r["conclusion"] == "success"
                    and r["total"] is not None
                ]
                if not rs:
                    continue
                agg[(app, v, ph)] = {
                    "n": len(rs),
                    "total": median([r["total"] for r in rs]),
                    "min": min(r["total"] for r in rs),
                    "max": max(r["total"] for r in rs),
                    "phases": {
                        k: median([r["phases"][k] for r in rs]) or 0.0
                        for k, _, _ in PHASES
                    },
                    "caches": {
                        k: median([r["caches"][k] for r in rs]) or 0.0
                        for k, _, _ in CACHES
                    },
                    "caches_min": {
                        k: min(r["caches"][k] for r in rs) for k, _, _ in CACHES
                    },
                    "caches_max": {
                        k: max(r["caches"][k] for r in rs) for k, _, _ in CACHES
                    },
                    "packages": rs[0].get("packages"),
                }
    return agg


def bar_chart(agg: dict, app: str) -> str:
    """工程別の積み上げ横棒グラフ（SVG）。"""
    bars = []
    for v in VARIANTS:
        for ph in ("warm", "cold"):
            if (app, v, ph) in agg:
                label = VARIANT_LABEL[v] + ("（初回）" if ph == "cold" else "")
                bars.append((label, agg[(app, v, ph)], ph))
    if not bars:
        return "<p>計測データがありません。</p>"
    max_total = max(sum(a["phases"].values()) for _, a, _ in bars)
    left, width, bar_h, gap = 280, 540, 26, 18
    height = len(bars) * (bar_h + gap) + 30
    scale = width / max_total if max_total else 0
    out = [
        f'<svg viewBox="0 0 {left + width + 90} {height}" role="img" aria-labelledby="chart-{app}" class="chart">',
        f'<title id="chart-{app}">{APP_LABEL[app]}: 構成ごとの工程別実行時間（中央値）</title>',
    ]
    step = 60 if max_total > 300 else 30 if max_total > 120 else 10
    t = 0
    while t <= max_total:
        x = left + t * scale
        out.append(
            f'<line x1="{x:.1f}" y1="0" x2="{x:.1f}" y2="{height - 22}" class="grid"/>'
        )
        out.append(
            f'<text x="{x:.1f}" y="{height - 6}" class="tick" text-anchor="middle">{t}s</text>'
        )
        t += step
    for i, (label, a, ph) in enumerate(bars):
        y = i * (bar_h + gap) + 6
        cls = "lbl cold" if ph == "cold" else "lbl"
        out.append(
            f'<text x="{left - 10}" y="{y + bar_h / 2 + 5}" text-anchor="end" class="{cls}">{html.escape(label)}</text>'
        )
        x = left
        for k, name, color in PHASES:
            w = a["phases"][k] * scale
            if w <= 0:
                continue
            op = ' opacity="0.55"' if ph == "cold" else ""
            out.append(
                f'<rect x="{x:.1f}" y="{y}" width="{w:.1f}" height="{bar_h}" fill="{color}"{op}>'
                f"<title>{html.escape(name)}: {a['phases'][k]:.0f}秒</title></rect>"
            )
            x += w
        out.append(
            f'<text x="{x + 6:.1f}" y="{y + bar_h / 2 + 5}" class="val">{fmt(sum(a["phases"].values()))}</text>'
        )
    out.append("</svg>")
    return "\n".join(out)


def legend() -> str:
    items = "".join(
        f'<li><span class="sw" style="background:{c}"></span>{html.escape(n)}</li>'
        for _, n, c in PHASES
    )
    return f'<ul class="legend">{items}</ul>'


def hit_badge(v: str) -> str:
    if v == "true":
        return '<span class="badge hit">hit</span>'
    if v == "false":
        return '<span class="badge miss">miss</span>'
    return '<span class="badge na">—</span>'


def overlap(a: dict, b: dict) -> bool:
    if min(a["n"], b["n"]) < 2:
        return True  # 1 回だけでは範囲が分からないので、差を断定しない
    return not (a["max"] < b["min"] or b["max"] < a["min"])


def cache_table(agg: dict, app: str) -> str:
    none, full = agg.get((app, "none", "warm")), agg.get((app, "full", "warm"))
    if not (none and full):
        return "<p>比較に必要なデータがありません。</p>"
    rows = []
    for k, name, what in CACHES:
        a, b = none["caches"][k], full["caches"][k]
        d = a - b
        pct = d / a * 100 if a else 0
        clear = (
            full["caches_max"][k] < none["caches_min"][k]
            or none["caches_max"][k] < full["caches_min"][k]
        )
        if min(none["n"], full["n"]) < 2:
            judge = "回数不足（2 回以上で判定）"
        else:
            judge = "はっきり差あり" if clear else "ばらつきの範囲"
        cls = "good" if d >= 1 else "bad" if d <= -1 else ""
        sign = "−" if d >= 0 else "＋"
        rows.append(
            f"<tr><th scope='row'>{html.escape(name)}<div class='what'>{html.escape(what)}</div></th>"
            f"<td class='num'>{fmt(a)}</td><td class='num'>{fmt(b)}</td>"
            f"<td class='num {cls}'>{sign}{fmt(abs(d))}</td>"
            f"<td class='num {cls}'>{pct:.0f}%</td>"
            f"<td>{judge}</td></tr>"
        )
    return (
        "<div class='table-wrap'><table class='cache'>"
        "<thead><tr><th scope='col'>キャッシュ対象（計った範囲）</th><th scope='col' class='num'>なし</th>"
        "<th scope='col' class='num'>あり</th><th scope='col' class='num'>差</th>"
        "<th scope='col' class='num'>削減率</th><th scope='col'>判定</th></tr></thead>"
        f"<tbody>{''.join(rows)}</tbody></table></div>"
    )


def takeaways(agg: dict, app: str) -> list[str]:
    """計測値から読み取れることを文章にする（値から機械的に組み立てる）。"""
    out: list[str] = []
    none, sn, full = (agg.get((app, v, "warm")) for v in VARIANTS)
    if not (none and full):
        return out
    d = none["total"] - full["total"]
    out.append(
        f"フル活用はキャッシュなしより {fmt(abs(d))}（{abs(d) / none['total'] * 100:.0f}%）{'短い' if d >= 0 else '長い'}。"
        + (
            "各回の範囲は重なっておらず、はっきりした差。"
            if not overlap(none, full)
            else "ただし各回の範囲は重なっており、ばらつきと同程度の差でもある。"
        )
    )
    if sn:
        d2 = sn["total"] - full["total"]
        out.append(
            f"setup-node の cache: npm だけの構成と比べると、フル活用は {fmt(abs(d2))} {'短い' if d2 >= 0 else '長い'}"
            + (
                "（範囲の重なりなし）。"
                if not overlap(sn, full)
                else "（範囲は重なる）。"
            )
        )
    gains = sorted(
        ((none["caches"][k] - full["caches"][k], k, n) for k, n, _ in CACHES),
        reverse=True,
    )
    top = [f"{n}（−{fmt(g)}）" for g, _, n in gains if g >= 1][:3]
    if top:
        out.append("効果が大きかったキャッシュ: " + "、".join(top) + "。")
    worse = [f"{n}（＋{fmt(-g)}）" for g, _, n in gains if g <= -1]
    if worse:
        out.append(
            "逆に、キャッシュありの方が長かったもの（復元・保存のコストか、ばらつき）: "
            + "、".join(worse)
            + "。"
        )
    out.append(
        f"Playwright のブラウザ準備は、ブラウザ本体をキャッシュしても {fmt(full['caches']['browsers'])} かかる"
        f"（なしは {fmt(none['caches']['browsers'])}）。残りは apt による OS 依存パッケージのインストールで、キャッシュできない。"
    )
    cold = agg.get((app, "full", "cold"))
    if cold:
        out.append(
            f"キャッシュがまだ無い初回のフル活用は {fmt(cold['total'])}。lockfile・Dockerfile の前半・Trivy の日付が変わった直後はこの時間に戻る。"
        )
    return out


def cross_app(agg: dict) -> list[str]:
    out = []
    for app in APPS:
        none, full = agg.get((app, "none", "warm")), agg.get((app, "full", "warm"))
        if none and full:
            pk = none.get("packages")
            out.append(
                f"{APP_LABEL[app]}（依存 {pk} 個）: キャッシュなし {fmt(none['total'])} → フル活用 {fmt(full['total'])}"
                f"（{(none['total'] - full['total']) / none['total'] * 100:.0f}% 短縮）"
            )
    return out


def app_section(agg: dict, app: str) -> str:
    none_w = agg.get((app, "none", "warm"), {}).get("total")
    cards = []
    for v in VARIANTS:
        a = agg.get((app, v, "warm"))
        if not a:
            continue
        diff = ""
        if none_w and v != "none":
            pct = (none_w - a["total"]) / none_w * 100
            word = "短い" if pct >= 0 else "長い"
            diff = (
                f'<p class="delta">キャッシュなしより <strong>{fmt(abs(none_w - a["total"]))}</strong> {word}'
                f"（{abs(pct):.0f}% {'削減' if pct >= 0 else '増加'}）</p>"
            )
        cards.append(
            f'<div class="card v-{v}"><h4>{html.escape(VARIANT_LABEL[v])}</h4>'
            f'<p class="big">{fmt(a["total"])}</p>'
            f'<p class="sub">中央値（{a["n"]} 回、{fmt(a["min"])}〜{fmt(a["max"])}）</p>{diff}</div>'
        )
    phase_rows = []
    for k, name, color in PHASES:
        cells = "".join(
            f'<td class="num">{fmt(agg[(app, v, "warm")]["phases"][k]) if (app, v, "warm") in agg else "—"}</td>'
            for v in VARIANTS
        )
        phase_rows.append(
            f'<tr><th scope="row"><span class="sw" style="background:{color}"></span>{html.escape(name)}</th>{cells}</tr>'
        )
    take = "".join(f"<li>{html.escape(t)}</li>" for t in takeaways(agg, app))
    pk = next((agg[k].get("packages") for k in agg if k[0] == app), None)
    return f"""
<section aria-labelledby="h-{app}" class="app">
<h2 id="h-{app}">{APP_LABEL[app]}（依存 {pk} 個）</h2>
<p class="desc">{html.escape(APP_DESC[app])}</p>
<h3>job 全体の時間（キャッシュが温まった状態・1 ファイル変更あり）</h3>
<div class="cards">{"".join(cards)}</div>
<h3>この計測からわかること</h3>
<ul>{take}</ul>
<h3>キャッシュ対象ごとの効果（キャッシュなし vs フル活用、中央値）</h3>
{cache_table(agg, app)}
<h3>工程別の内訳</h3>
<p>棒は工程ごとの所要時間（中央値）を積み上げたもの。「（初回）」の薄い棒は、キャッシュがまだ無い状態でキャッシュを作る側の実行です。</p>
{bar_chart(agg, app)}
<details><summary>工程別の数値（warm・中央値）</summary>
<div class="table-wrap"><table>
<thead><tr><th scope="col">工程</th>{"".join(f'<th scope="col" class="num">{html.escape(VARIANT_LABEL[v])}</th>' for v in VARIANTS)}</tr></thead>
<tbody>{"".join(phase_rows)}</tbody>
</table></div></details>
</section>"""


def render(rows: list[dict], agg: dict, ctx: dict) -> str:
    job_rows = []
    for r in rows:
        h = r["cache_hit"]
        rnd = (
            "初回（cold）" if r["phase"] == "cold" else f"計測 {r['iteration']}（warm）"
        )
        job_rows.append(
            "<tr>"
            f"<td>{html.escape(APP_LABEL[r['app']])}</td>"
            f"<td>{html.escape(VARIANT_LABEL[r['variant']])}</td>"
            f"<td>{rnd}</td>"
            f'<td class="num">{fmt(r["total"])}</td>'
            f'<td class="num">{fmt(r["caches"]["deps"])}</td>'
            f'<td class="num">{fmt(r["caches"]["docker"])}</td>'
            f'<td class="num">{fmt(r["caches"]["trivy"])}</td>'
            f"<td>{hit_badge(h.get('setup_node_npm', ''))}</td>"
            f"<td>{hit_badge(h.get('node_modules', ''))}</td>"
            f"<td>{hit_badge(h.get('playwright', ''))}</td>"
            f"<td>{html.escape(r['conclusion'] or '')}</td>"
            f'<td><a href="{html.escape(r["url"])}">ログ</a></td>'
            "</tr>"
        )
    first = rows[0] if rows else {}
    variant_desc = "".join(
        f"<dt>{html.escape(VARIANT_LABEL[v])}（<code>{v}</code>）</dt><dd>{html.escape(VARIANT_DESC[v])}</dd>"
        for v in VARIANTS
    )
    overview = "".join(f"<li>{html.escape(t)}</li>" for t in cross_app(agg))
    run_url = f"{ctx['server']}/{ctx['repo']}/actions/runs/{ctx['run_id']}"
    sections = "".join(
        app_section(agg, app) for app in APPS if any(k[0] == app for k in agg)
    )
    return f"""<!doctype html>
<html lang="ja">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex">
<title>GitHub Actions のキャッシュで Web アプリの CI はどれだけ速くなるか</title>
<style>
:root {{ color-scheme: light dark; --bg:#fbfbfd; --fg:#1d1f24; --muted:#5b6170; --card:#fff; --line:#dfe2e8; --accent:#2f6fde; --good:#137a3f; --bad:#b3261e; }}
@media (prefers-color-scheme: dark) {{ :root {{ --bg:#14161a; --fg:#e8eaef; --muted:#a3a9b6; --card:#1d2026; --line:#323642; --accent:#7aa7ff; --good:#5fd38d; --bad:#ff8a80; }} }}
* {{ box-sizing: border-box; }}
body {{ margin:0; background:var(--bg); color:var(--fg); font: 16px/1.75 system-ui, -apple-system, "Hiragino Sans", "Noto Sans JP", sans-serif; }}
main {{ max-width: 1000px; margin: 0 auto; padding: 32px 20px 80px; }}
h1 {{ font-size: 1.7rem; line-height:1.4; margin: 0 0 .3em; }}
h2 {{ font-size: 1.35rem; margin: 2.6em 0 .4em; padding-bottom:.3em; border-bottom: 2px solid var(--line); }}
h3 {{ font-size: 1.05rem; margin: 1.8em 0 .5em; }}
.meta, .desc {{ color: var(--muted); font-size: .9rem; }}
.overview {{ background: var(--card); border:1px solid var(--line); border-radius: 12px; padding: 12px 20px; font-size: 1.05rem; }}
.cards {{ display:grid; grid-template-columns: repeat(auto-fit, minmax(240px,1fr)); gap: 14px; }}
.card {{ background:var(--card); border:1px solid var(--line); border-radius: 12px; padding: 16px 18px; border-top: 5px solid var(--muted); }}
.card.v-full {{ border-top-color: #2f9e8f; }} .card.v-setup-node {{ border-top-color: #3d7dd8; }} .card.v-none {{ border-top-color: #c4504a; }}
.card h4 {{ margin:0; font-size: 1rem; }}
.big {{ font-size: 2.2rem; font-weight: 700; margin: .1em 0 0; font-variant-numeric: tabular-nums; }}
.sub, .delta {{ margin: 0; font-size: .88rem; color: var(--muted); }}
.delta strong {{ color: var(--fg); }}
.chart {{ width: 100%; height: auto; background: var(--card); border:1px solid var(--line); border-radius: 12px; padding: 10px; }}
.chart .grid {{ stroke: var(--line); }} .chart .tick, .chart .val {{ fill: var(--muted); font-size: 12px; }}
.chart .lbl {{ fill: var(--fg); font-size: 13px; }} .chart .lbl.cold {{ fill: var(--muted); }}
.legend {{ list-style:none; padding:0; display:flex; flex-wrap:wrap; gap: 6px 16px; font-size: .85rem; color: var(--muted); }}
.sw {{ display:inline-block; width: .9em; height: .9em; border-radius: 3px; margin-right: .4em; vertical-align: -1px; }}
.table-wrap {{ overflow-x:auto; }}
table {{ border-collapse: collapse; width: 100%; font-size: .9rem; background: var(--card); }}
th, td {{ border-bottom: 1px solid var(--line); padding: 6px 10px; text-align: left; white-space: nowrap; }}
table.cache th[scope=row] {{ white-space: normal; }}
.what {{ font-weight: normal; font-size: .78rem; color: var(--muted); }}
thead th {{ font-weight: 600; color: var(--muted); }}
td.num {{ text-align: right; font-variant-numeric: tabular-nums; }}
td.good {{ color: var(--good); font-weight: 600; }} td.bad {{ color: var(--bad); font-weight: 600; }}
.badge {{ font-size:.75rem; padding: 1px 8px; border-radius: 999px; }}
.badge.hit {{ background:#d4f4e4; color:#0d5c36; }} .badge.miss {{ background:#fde2d8; color:#8a2b0b; }} .badge.na {{ color: var(--muted); }}
details {{ margin-top: 1em; }} summary {{ cursor: pointer; color: var(--accent); }}
dt {{ font-weight: 600; margin-top: .6em; }} dd {{ margin: 0 0 0 1em; }}
.note {{ background: var(--card); border-left: 4px solid var(--accent); padding: 10px 16px; border-radius: 6px; }}
a {{ color: var(--accent); }}
code {{ font-size: .9em; }}
</style>
</head>
<body>
<main>
<h1>GitHub Actions のキャッシュで Web アプリの CI はどれだけ速くなるか</h1>
<p class="meta">計測日時 {html.escape(ctx["generated"])} ／ Node {html.escape(first.get("node_version", ""))} ／ Playwright {html.escape(first.get("playwright_version", ""))} ／ ランナー {html.escape(first.get("image", ""))} ／ 各構成 {html.escape(ctx["iterations"])} 回計測 ／ <a href="{html.escape(run_url)}">ワークフロー実行</a></p>

<section aria-labelledby="h-overview">
<h2 id="h-overview">ひとことで</h2>
<ul class="overview">{overview}</ul>
<p>CI の中身（どちらのアプリも同じ）: 依存インストール → Lint（ESLint）→ 型チェック（TypeScript）→ Unit test（Vitest）→ Build（Vite）→ E2E（Playwright / Chromium）→ Docker イメージのビルド → Trivy でイメージをスキャン。
キャッシュが温まった計測では、実際の差分 CI に近づけるため、ソースを 1 ファイルだけ変更してから実行しています。</p>
<h3>比較した 3 つの構成</h3>
<dl>{variant_desc}</dl>
<h3>グラフの色</h3>
{legend()}
</section>
{sections}

<section aria-labelledby="h-jobs">
<h2 id="h-jobs">すべての実行</h2>
<div class="table-wrap"><table>
<thead><tr><th scope="col">アプリ</th><th scope="col">構成</th><th scope="col">回</th><th scope="col" class="num">合計</th><th scope="col" class="num">npm 依存</th><th scope="col" class="num">Docker</th><th scope="col" class="num">Trivy</th><th scope="col">setup-node npm</th><th scope="col">node_modules</th><th scope="col">Playwright</th><th scope="col">結果</th><th scope="col">ログ</th></tr></thead>
<tbody>{"".join(job_rows)}</tbody>
</table></div>
</section>

<section aria-labelledby="h-read">
<h2 id="h-read">読み方と注意点</h2>
<ul>
<li>時間は GitHub API が返す job・step の開始／終了時刻（秒単位）から計算しています。ランナーの個体差や、外部（npm レジストリ・Docker Hub・Trivy DB の配布元）の速度で数秒〜数十秒ぶれるため、複数回の中央値で比べています。「判定」は、各回の最小〜最大の範囲が重ならないときだけ「はっきり差あり」としています。</li>
<li>キャッシュ別の表は、工程そのものの時間に、そのキャッシュの復元・保存にかかった時間を足して比べています（例: npm 依存 = node_modules の復元 ＋ npm ci ＋ 保存）。ESLint・TypeScript・Vitest のキャッシュは node_modules と一緒に保存しているので、その復元時間は npm 依存の行に含まれます。</li>
<li>「フル活用」のキャッシュキーにはワークフロー実行 ID を含め、毎回作り直しています。trivy-action の内蔵キャッシュ（キーは <code>cache-trivy-日付</code>）と BuildKit のキャッシュは実行をまたいで共有されるため、実行の最初と最後に削除しています。</li>
<li>Docker のキャッシュは <code>docker/build-push-action</code> の <code>cache-from</code> / <code>cache-to: type=gha,mode=max</code>。Dockerfile は lockfile だけを先にコピーして <code>npm ci</code> し、そのあとでソースをコピーする構成なので、ソースを 1 ファイル変えても <code>npm ci</code> のレイヤーは再利用されます。</li>
<li>Trivy のキャッシュは速さだけでなく、脆弱性 DB のダウンロードのレート制限（TOOMANYREQUESTS）を避けるためにも trivy-action の README で推奨されています。</li>
<li>Playwright 公式は「ブラウザ本体のキャッシュは推奨しない（復元時間がダウンロードと同程度で、Linux の OS 依存パッケージはキャッシュできない）」としています。</li>
<li>actions/setup-node は v5 から、package.json に <code>packageManager</code> があると自動でキャッシュを有効にします。「キャッシュなし」では <code>package-manager-cache: false</code> で明示的に切っています。</li>
</ul>
<div class="note">
<p><strong>2026 年 11 月時点の Actions キャッシュの仕様（公式ドキュメントより）</strong></p>
<ul>
<li>リポジトリあたり既定 10 GB。超えた分は課金で拡張できる。7 日間使われなかったエントリは削除される。</li>
<li>復元できるのは自ブランチと default branch（PR なら base branch）のキャッシュ。兄弟ブランチのキャッシュは使えない。</li>
<li>保存は 1 分あたり 200 件、復元は 1500 件まで。</li>
<li>使用した Action（いずれも commit SHA で固定）: actions/cache v6.1.0、actions/setup-node v7.1.0、actions/checkout v7.0.1、actions/upload-artifact v7.0.2、docker/setup-buildx-action v4.4.1、docker/build-push-action v7.4.0、aquasecurity/trivy-action v0.36.0。</li>
</ul>
</div>
<p>出典: <a href="https://docs.github.com/en/actions/reference/workflows-and-actions/dependency-caching">GitHub Docs: Dependency caching reference</a> ／ <a href="https://github.com/actions/setup-node/releases/tag/v5.0.0">actions/setup-node v5.0.0</a> ／ <a href="https://playwright.dev/docs/ci">Playwright: Continuous Integration</a> ／ <a href="https://docs.docker.com/build/cache/backends/gha/">Docker Docs: GitHub Actions cache</a> ／ <a href="https://github.com/aquasecurity/trivy-action">aquasecurity/trivy-action</a></p>
</section>
</main>
</body>
</html>
"""


def summary_md(agg: dict) -> str:
    lines = [
        "## Cache Benchmark",
        "",
        "| アプリ | 構成 | warm 中央値 | cold |",
        "|---|---|---:|---:|",
    ]
    for app in APPS:
        for v in VARIANTS:
            w, c = agg.get((app, v, "warm")), agg.get((app, v, "cold"))
            if w or c:
                lines.append(
                    f"| {APP_LABEL[app]} | {VARIANT_LABEL[v]} | {fmt(w['total'] if w else None)} | {fmt(c['total'] if c else None)} |"
                )
    return "\n".join(lines) + "\n"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--jobs", type=Path, required=True)
    ap.add_argument("--meta", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--summary", type=Path, required=True)
    a = ap.parse_args()
    rows = load(a.jobs, a.meta)
    agg = aggregate(rows)
    ctx = {
        "repo": os.environ.get("REPO", ""),
        "run_id": os.environ.get("RUN_ID", ""),
        "server": os.environ.get("SERVER_URL", "https://github.com"),
        "iterations": os.environ.get("ITERATIONS", "?"),
        "generated": datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC"),
    }
    a.out.write_text(render(rows, agg, ctx), encoding="utf-8")
    a.summary.write_text(summary_md(agg), encoding="utf-8")
    print(
        f"jobs={len(rows)} apps={sorted({r['app'] for r in rows})} variants={sorted({r['variant'] for r in rows})}"
    )


if __name__ == "__main__":
    main()
