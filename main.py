import sys
import os

import pathlib
# Ensure the 'src' package is resolvable so running from here works exactly like running inside src
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent / "src"))

from ui.ide_app import IDEApp

def main():
    app = IDEApp()
    app.mainloop()

if __name__ == "__main__":
    main()
