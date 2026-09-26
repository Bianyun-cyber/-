#!/bin/bash
# 跑一个字母的完整流水线：抽取 → finalize(分配id) → 质检(qa)
# 用法: bash scripts/run_letter.sh a 05
L=$1
SRC=${2:-05}
cd /home/admin/.openclaw/workspace/scene-master
if [ "$SRC" = "05" ]; then
  python3 scripts/extract.py --letter "$L" --all --write --workers 8
else
  python3 scripts/extract07.py --letter "$L" --all --write --workers 8
fi
python3 scripts/finalize.py
python3 scripts/qa.py --letter "$L"