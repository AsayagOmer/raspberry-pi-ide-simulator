import sys
import os

import pathlib
# Ensure the 'src' package is resolvable so running from here works exactly like running inside src
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent / "src"))

import ui.ide_app # type: ignore

def main():
    app: ui.ide_app.IDEApp = ui.ide_app.IDEApp()
    app.mainloop()

if __name__ == "__main__":
    main()
