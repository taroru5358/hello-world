#!/usr/bin/env bash
# Organization 所有リポジトリにマージキュー用の ruleset を作成する。
# 使い方: scripts/setup-merge-queue.sh [OWNER/REPO] [必須チェック名]
set -euo pipefail

repo="${1:-$(gh repo view --json nameWithOwner -q .nameWithOwner)}"
check_name="${2:-demo-ci}"

owner_type="$(gh api "repos/${repo}" --jq '.owner.type')"
if [[ "${owner_type}" != "Organization" ]]; then
  echo "ERROR: ${repo} は ${owner_type} アカウント所有です。" >&2
  echo "マージキューは Organization 所有リポジトリでのみ利用できます。" >&2
  exit 1
fi

payload="$(mktemp)"
trap 'rm -f "${payload}"' EXIT

cat > "${payload}" <<JSON
{
  "name": "main merge queue",
  "target": "branch",
  "enforcement": "active",
  "conditions": {
    "ref_name": {
      "include": ["~DEFAULT_BRANCH"],
      "exclude": []
    }
  },
  "rules": [
    {
      "type": "merge_queue",
      "parameters": {
        "merge_method": "SQUASH",
        "grouping_strategy": "ALLGREEN",
        "max_entries_to_build": 5,
        "max_entries_to_merge": 5,
        "min_entries_to_merge": 1,
        "min_entries_to_merge_wait_minutes": 0,
        "check_response_timeout_minutes": 60
      }
    },
    {
      "type": "required_status_checks",
      "parameters": {
        "required_status_checks": [
          { "context": "${check_name}" }
        ],
        "strict_required_status_checks_policy": false
      }
    }
  ]
}
JSON

existing_id="$(
  gh api "repos/${repo}/rulesets" \
    --jq '.[] | select(.name == "main merge queue") | .id' \
    | head -n 1
)"

if [[ -n "${existing_id}" ]]; then
  echo "既存の ruleset ${existing_id} を更新します..."
  gh api "repos/${repo}/rulesets/${existing_id}" -X PUT --input "${payload}"
else
  echo "ruleset を新規作成します..."
  gh api "repos/${repo}/rulesets" -X POST --input "${payload}"
fi

echo
echo "設定後の確認: gh ruleset list --repo ${repo}"
