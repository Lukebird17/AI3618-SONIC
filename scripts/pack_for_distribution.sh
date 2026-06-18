#!/usr/bin/env bash
# 打包 vr 项目发给同学（排除大文件与 Unity 缓存）
set -euo pipefail

VR_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT="${1:-$HOME/AI3618-Quest-VR-Teleop.zip}"
STAGING="$(mktemp -d)"
trap 'rm -rf "$STAGING"' EXIT

NAME="AI3618-Quest-VR-Teleop"
mkdir -p "$STAGING/$NAME"

echo "Staging from $VR_ROOT ..."

rsync -a \
  --exclude='TensorRT-*.tar.gz' \
  --exclude='main.zip' \
  --exclude='reference.zip' \
  --exclude='quest-mirror-unity-old/' \
  --exclude='unitree_lfs/' \
  --exclude='**/Library/' \
  --exclude='**/Builds/' \
  --exclude='**/Temp/' \
  --exclude='**/Logs/' \
  --exclude='**/obj/' \
  --exclude='**/__pycache__/' \
  --exclude='**/*.egg-info/' \
  --exclude='**/.DS_Store' \
  --exclude='recordings/session_*.jsonl' \
  "$VR_ROOT/" "$STAGING/$NAME/"

# 保留一条较小的示例录制供演示（≤5MB 里取最大的一条）
SAMPLE=""
while IFS= read -r f; do
  SAMPLE="$f"
done < <(find "$VR_ROOT/sonic-bridge/recordings" -maxdepth 1 -name 'session_*.jsonl' -size -5M -printf '%s %p\n' 2>/dev/null | sort -n | tail -1 | cut -d' ' -f2-)
if [[ -n "$SAMPLE" && -f "$SAMPLE" ]]; then
  mkdir -p "$STAGING/$NAME/sonic-bridge/recordings"
  cp "$SAMPLE" "$STAGING/$NAME/sonic-bridge/recordings/"
  echo "Included sample recording: $(basename "$SAMPLE")"
fi

cd "$STAGING"
rm -f "$OUT"
zip -r "$OUT" "$NAME" -x "*.git/*"
echo ""
echo "Created: $OUT"
ls -lh "$OUT"
