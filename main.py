# main.py
"""
Entry point for the Tie List processing tool.
Run this file:  python main.py
"""

from gui.app import TieDataApp


def main():
    app = TieDataApp()
    app.mainloop()


if __name__ == "__main__":
    main()
