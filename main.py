import sys
import os

# Ensure the 'src' package is resolvable so running from here works exactly like running inside src
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from ide_app import IDEApp

def main():
    app = IDEApp()
    app.mainloop()

if __name__ == "__main__":
    main()
