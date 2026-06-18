#!/usr/bin/env bash
# Export G1 STL (gear_sonic URDF meshes) → Unity OBJ in both Unity project folders.
set -euo pipefail
python3 "$(dirname "$0")/export_g1_meshes_to_unity.py" "$@"
