#!/usr/bin/env python3
"""
Compatibility shim so `python main.py` keeps working from a repo checkout.

The application itself lives in nodeice_board/main.py and is also available
as the `nodeice-board` console script after `pip install -e .`.
"""

from nodeice_board.main import main

if __name__ == "__main__":
    main()
