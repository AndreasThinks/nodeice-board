"""
Optional RGB LED matrix display for Nodeice Board.

Shows board activity live on a HUB75 RGB LED matrix panel (designed for a
32x32 panel on an Adafruit RGB Matrix Bonnet, but any size the
rpi-rgb-led-matrix library supports will work).

This package is deliberately decoupled from the main application: it only
reads the SQLite database, so it runs as its own process/service and can
crash, restart, or be absent without affecting the notice board itself.

Rendering works against either backend:
- ``rgbmatrix``          - the real hardware (hzeller/rpi-rgb-led-matrix)
- ``RGBMatrixEmulator``  - a pip-installable, API-compatible emulator for
                           development on a desktop
"""
