#!/bin/zsh
# GAPPS launcher (macOS)
# Uses the virtual environment .venv of the GAPPS folder (pip installation) if it exists,
# otherwise the conda environment "gapps" (installation with environment.yml).
ENV_NAME="gapps"
GAPPS_DIR="$(cd "$(dirname "$0")" && pwd)"

# 1) pip installation: .venv inside the GAPPS folder
if [ -x "$GAPPS_DIR/.venv/bin/python" ]; then
  exec "$GAPPS_DIR/.venv/bin/python" "$GAPPS_DIR/run_gapps.py"
fi

# 2) conda installation in a usual location: activate the environment (GDAL/PROJ need it)
for base in "$HOME/miniforge3" "$HOME/mambaforge" "$HOME/miniconda3" "$HOME/anaconda3" \
            "$HOME/opt/miniforge3" "$HOME/opt/miniconda3" "$HOME/opt/anaconda3" \
            "/opt/homebrew/Caskroom/miniforge/base" "/usr/local/Caskroom/miniforge/base" \
            "/opt/miniforge3" "/opt/miniconda3" "/opt/anaconda3"; do
  if [ -x "$base/envs/$ENV_NAME/bin/python" ] && [ -f "$base/bin/activate" ]; then
    source "$base/bin/activate" "$base/envs/$ENV_NAME"
    exec python "$GAPPS_DIR/run_gapps.py"
  fi
done

# 3) conda elsewhere (on the PATH)
if command -v conda >/dev/null 2>&1; then
  exec conda run --no-capture-output -n "$ENV_NAME" python "$GAPPS_DIR/run_gapps.py"
fi

echo "GAPPS: no Python environment found."
echo "Expected: .venv in the GAPPS folder (pip installation) or the conda environment '$ENV_NAME'"
echo "(conda env create -f environment.yml). See README.md, 'Installation of GAPPS'."
read -k1 "?Press a key to close."
exit 1
