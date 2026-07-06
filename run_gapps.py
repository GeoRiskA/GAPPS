from pathlib import Path
import sys
import os
import runpy


def main():
    project_root = Path(__file__).resolve().parent

    # Make sure the project root is visible to Python imports
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

    # Make relative paths behave as expected
    os.chdir(project_root)

    main_gui = project_root / "GAPPS_GUI_main.py"

    if not main_gui.exists():
        raise FileNotFoundError(f"Cannot find main GUI script: {main_gui}")

    runpy.run_path(str(main_gui), run_name="__main__")


if __name__ == "__main__":
    main()
