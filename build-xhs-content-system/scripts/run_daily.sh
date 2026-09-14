#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT=""
TARGET_DATE=""
CODEX_BIN="${CODEX_BIN:-/Applications/ChatGPT.app/Contents/Resources/codex}"
DRY_RUN=0

usage() {
  printf '%s\n' "Usage: run_daily.sh --project-root PATH [--date YYYY-MM-DD] [--dry-run]"
}

tomorrow() {
  if date -v+1d +%F >/dev/null 2>&1; then
    date -v+1d +%F
  else
    date -d tomorrow +%F
  fi
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --project-root|--project)
      PROJECT_ROOT="${2:-}"
      shift 2
      ;;
    --date)
      TARGET_DATE="${2:-}"
      shift 2
      ;;
    --dry-run)
      DRY_RUN=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      usage >&2
      exit 2
      ;;
  esac
done

if [[ -z "$PROJECT_ROOT" ]]; then
  echo "必须提供 --project-root" >&2
  exit 2
fi
PROJECT_ROOT="$(cd "$PROJECT_ROOT" && pwd)"
TARGET_DATE="${TARGET_DATE:-$(tomorrow)}"
if ! printf '%s' "$TARGET_DATE" | grep -Eq '^[0-9]{4}-[0-9]{2}-[0-9]{2}$'; then
  echo "日期格式错误：$TARGET_DATE" >&2
  exit 2
fi

CONFIG_FILE="$PROJECT_ROOT/project.yaml"
if [[ ! -f "$CONFIG_FILE" ]]; then
  echo "不是有效项目目录：$PROJECT_ROOT" >&2
  exit 1
fi

DAILY_SKILL_PATH="$(awk -F ':' '/^[[:space:]]+skill_path[[:space:]]*:/ {value=$2; gsub(/^[[:space:]\"]+|[[:space:]\"]+$/, "", value); print value; exit}' "$CONFIG_FILE")"
if [[ -z "$DAILY_SKILL_PATH" ]]; then
  echo "project.yaml 缺少 daily_producer.skill_path" >&2
  exit 1
fi
SKILL_DIR="$PROJECT_ROOT/$DAILY_SKILL_PATH"
if [[ ! -f "$SKILL_DIR/SKILL.md" ]]; then
  echo "项目专属每日生产 Skill 不存在：$SKILL_DIR" >&2
  exit 1
fi

TARGET_DIR="$PROJECT_ROOT/输出/$TARGET_DATE"
if [[ -d "$TARGET_DIR" ]] && [[ -n "$(find "$TARGET_DIR" -mindepth 1 -maxdepth 1 -print -quit)" ]]; then
  echo "停止：目标日期已有内容，不覆盖：$TARGET_DIR" >&2
  exit 1
fi

if [[ "$DRY_RUN" -eq 1 ]]; then
  printf 'READY\nProject: %s\nDate: %s\nSkill: %s\n' "$PROJECT_ROOT" "$TARGET_DATE" "$SKILL_DIR"
  exit 0
fi

if [[ ! -x "$CODEX_BIN" ]]; then
  CODEX_BIN="$(command -v codex || true)"
fi
if [[ -z "$CODEX_BIN" || ! -x "$CODEX_BIN" ]]; then
  echo "找不到 Codex CLI；可通过 CODEX_BIN 指定" >&2
  exit 1
fi

mkdir -p "$PROJECT_ROOT/自动化日志"
LOG_FILE="$PROJECT_ROOT/自动化日志/$TARGET_DATE.log"
LAST_MESSAGE_FILE="$PROJECT_ROOT/自动化日志/$TARGET_DATE-last-message.md"
PROMPT="读取项目专属 Skill：$SKILL_DIR/SKILL.md，并严格按其流程为 $TARGET_DATE 生成一条完整的小红书待审核内容。项目根目录：$PROJECT_ROOT。必须读取 project.yaml、项目方案、视觉规范、素材索引、数据复盘和最近14天输出；不得使用其他项目的信息，不得覆盖、复制素材或公开发布。完成后运行该 Skill 内的校验脚本。"

"$CODEX_BIN" --ask-for-approval never exec \
  --cd "$PROJECT_ROOT" \
  --skip-git-repo-check \
  --sandbox workspace-write \
  --ephemeral \
  --color never \
  --output-last-message "$LAST_MESSAGE_FILE" \
  "$PROMPT" >"$LOG_FILE" 2>&1

PYTHON_BIN="${XHS_PYTHON_BIN:-$(command -v python3)}"
"$PYTHON_BIN" "$SKILL_DIR/scripts/validate_daily_output.py" \
  --project-root "$PROJECT_ROOT" \
  --date "$TARGET_DATE" >>"$LOG_FILE" 2>&1

printf 'DONE: %s\nLog: %s\n' "$TARGET_DIR" "$LOG_FILE"
