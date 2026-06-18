#!/usr/bin/env bash
# Bootstrap SONIC Quest fork in WSL (run: wsl -d Ubuntu bash /mnt/c/File/vr/scripts/bootstrap_sonic_wsl.sh)
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
bash "$SCRIPT_DIR/configure_pypi_mirror.sh"

GROOT="${GROOT:-$HOME/projects/GR00T-WholeBodyControl}"
VR="/mnt/c/File/vr"
XRSDK_DIR="$GROOT/external_dependencies/XRoboToolkit-PC-Service-Pybind_X86_and_ARM64"
XRSDK_LIB="$XRSDK_DIR/lib/libPXREARobotSDK.so"

echo "==> WSL socket buffers"
sudo sysctl -w net.core.rmem_max=2097152 net.core.rmem_default=2097152 \
  net.core.wmem_max=2097152 net.core.wmem_default=2097152 2>/dev/null || true

echo "==> Apt deps"
sudo apt-get update -qq
sudo apt-get install -y git git-lfs build-essential curl python3 python3-venv python3-pip \
  libgl1 libegl1 libx11-6 android-tools-adb android-tools-fastboot

mkdir -p "$(dirname "$GROOT")"
if [[ ! -d "$GROOT/.git" ]]; then
  echo "==> Cloning TELEOPERATION_SONIC (Quest fork)"
  GIT_HTTP_VERSION=HTTP/1.1 git clone --depth 1 https://github.com/josue99999/TELEOPERATION_SONIC.git "$GROOT" || {
    echo "Clone failed — retry with: GIT_HTTP_VERSION=HTTP/1.1 git clone --depth 1 ..."
    exit 1
  }
fi

cd "$GROOT"
git lfs pull || true

if [[ ! -d .venv_teleop ]]; then
  echo "==> install_pico.sh (may take several minutes)"
  bash install_scripts/install_pico.sh
fi

if [[ ! -d .venv_sim ]]; then
  echo "==> install_mujoco_sim.sh"
  bash install_scripts/install_mujoco_sim.sh
fi

echo "==> sonic-bridge"
source .venv_teleop/bin/activate
pip install -q -e "$VR/sonic-bridge"

if [[ ! -f "$XRSDK_LIB" ]] || ! file "$XRSDK_LIB" | grep -q 'ELF'; then
  echo "==> XRoboToolkit SDK library is missing or not a valid ELF; rebuilding via setup_ubuntu.sh"
  bash "$XRSDK_DIR/setup_ubuntu.sh"
fi

echo "==> Synthetic reader smoke test"
python -m gear_sonic.utils.teleop.readers.quest_reader --synthetic --duration 3

echo ""
echo "Done. GROOT=$GROOT"
echo "Next: connect Quest -> test_quest_meta_quest.py --ip-address <QUEST_IP>"
