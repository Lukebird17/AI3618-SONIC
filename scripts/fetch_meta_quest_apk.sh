#!/usr/bin/env bash
# meta_quest_teleop pip install leaves Git-LFS pointer stubs (132 bytes), not real APKs.
# Downloads teleop-rail-orig.apk via GitHub LFS API and links it as teleop-debug.apk.
set -euo pipefail

OID="ea9883294ae6465f09d581d6c50f2939fff00890e4b3ead8316caae83df26341"
SIZE="7500599"
LFS_REPO="https://github.com/BrikHMP18/meta_quest_teleop.git"

if [[ -z "${VIRTUAL_ENV:-}" ]]; then
  echo "[fetch_meta_quest_apk] Activate .venv_teleop first." >&2
  exit 1
fi

APK_DIR="$(python - <<'PY'
import meta_quest_teleop, os
print(os.path.join(os.path.dirname(meta_quest_teleop.__file__), "APK"))
PY
)"

mkdir -p "$APK_DIR"
TMP="$(mktemp)"

echo "[fetch_meta_quest_apk] Resolving Git LFS download URL ..."
URL="$(curl -fsSL -X POST \
  -H "Accept: application/vnd.git-lfs+json" \
  -H "Content-Type: application/vnd.git-lfs+json" \
  "${LFS_REPO}/info/lfs/objects/batch" \
  -d "{\"operation\":\"download\",\"transfers\":[\"basic\"],\"objects\":[{\"oid\":\"${OID}\",\"size\":${SIZE}}]}" \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['objects'][0]['actions']['download']['href'])")"

echo "[fetch_meta_quest_apk] Downloading teleop-rail-orig.apk (~7.5MB) ..."
curl -fsSL -o "$TMP" "$URL"

ACTUAL_SHA="$(sha256sum "$TMP" | awk '{print $1}')"
if [[ "$ACTUAL_SHA" != "$OID" ]]; then
  echo "[fetch_meta_quest_apk] SHA-256 mismatch: got ${ACTUAL_SHA}, expected ${OID}" >&2
  exit 1
fi

cp "$TMP" "${APK_DIR}/teleop-rail-orig.apk"
cp "$TMP" "${APK_DIR}/teleop-debug.apk"
rm -f "$TMP"

echo "[fetch_meta_quest_apk] OK: ${APK_DIR}/teleop-debug.apk (${SIZE} bytes, sha256 verified)"
