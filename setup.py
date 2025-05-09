#!/usr/bin/env python3
"""
Setup script for Nodeice Board.
This is a fallback for systems that might have issues with pyproject.toml.
"""

from setuptools import setup, find_packages

setup(
    name="nodeice-board",
    version="0.1.0",
    description="Meshtastic-based notice board application",
    packages=["nodeice_board"],
    python_requires=">=3.9",
    install_requires=[
        "meshtastic>=2.6.2",
        "pypubsub>=4.0.3",
        "pyyaml>=6.0",
        "pillow>=9.0.0",  # Added for LED matrix image support
    ],
    entry_points={
        "console_scripts": [
            "nodeice-board=main:main",
        ],
    },
)
