#!/usr/bin/env bash
# PostToolUse hook: src/forge3d/ 안의 Python 파일이 수정될 때 실행
# 1. 외부 물리엔진 import 감지
# 2. 물리 코어에서 render import 감지

FILE="${CLAUDE_TOOL_INPUT_FILE_PATH:-}"

[[ -z "$FILE" ]] && exit 0
[[ "$FILE" != *.py ]] && exit 0
[[ "$FILE" != */src/forge3d/* ]] && exit 0

# 1. 외부 물리엔진 감지 (validation/ 제외)
if [[ "$FILE" != */validation/* ]]; then
    if grep -qE "^\s*(import|from)\s+(pybullet|mujoco|bullet|ode|dart|isaac|brax)" "$FILE" 2>/dev/null; then
        echo "⛔ GUARD: 외부 물리엔진 import 감지: $FILE" >&2
        echo "   src/forge3d/ 안에서 pybullet/mujoco 사용 금지 (CLAUDE.md §0)" >&2
        exit 2
    fi
fi

# 2. 물리 코어에서 render import 감지
PHYSICS_CORE_DIRS="math/ dynamics/ collision/ contact/ model/ sim/"
for dir in $PHYSICS_CORE_DIRS; do
    if [[ "$FILE" == */forge3d/${dir}* ]]; then
        if grep -qE "from forge3d\.render|import forge3d\.render" "$FILE" 2>/dev/null; then
            echo "⛔ GUARD: 물리 코어에서 렌더러 import 감지: $FILE" >&2
            echo "   물리↔렌더 분리 원칙 위반 (CLAUDE.md §0b)" >&2
            exit 2
        fi
        break
    fi
done

exit 0
