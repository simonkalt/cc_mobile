#!/usr/bin/env bash
# Ensure project-root .venv is usable (bin/activate present). Recreate if missing or broken.
# Usage: source scripts/ensure_venv.sh && ensure_project_venv /path/to/cc_mobile

ensure_project_venv() {
  local project_dir="${1:?project directory required}"
  local venv_dir="$project_dir/.venv"

  if [ -f "$venv_dir/bin/activate" ]; then
    return 0
  fi

  if [ -d "$venv_dir" ]; then
    echo "⚠️  Virtual environment is broken (missing $venv_dir/bin/activate). Recreating..."
    rm -rf "$venv_dir"
  else
    echo "📦 Creating virtual environment..."
  fi

  if ! python3 -m venv "$venv_dir"; then
    echo "❌ Failed to create venv. Install: sudo apt install python3-venv"
    return 1
  fi

  if [ ! -f "$venv_dir/bin/activate" ]; then
    echo "❌ venv created but bin/activate still missing. Check python3-venv and disk space."
    return 1
  fi

  # shellcheck source=/dev/null
  source "$venv_dir/bin/activate"

  if [ ! -f "$venv_dir/bin/python" ] && [ -f "$venv_dir/bin/python3" ]; then
    ln -sf python3 "$venv_dir/bin/python"
  fi

  echo "📦 Installing/upgrading pip and requirements (may take a minute)..."
  pip install --upgrade pip setuptools wheel --quiet
  pip install -r "$project_dir/requirements.txt" --quiet

  echo "✓ Virtual environment ready at $venv_dir"
  return 0
}
