#!/usr/bin/env python3
"""
Setup script for Player Universe Load package
"""
from setuptools import setup, find_packages

setup(
    name="player_universe_load",
    version="0.1.0",
    description="Load player universe data into PostgreSQL",
    packages=find_packages(),
    install_requires=[
        "psycopg2>=2.9.10",
        "pydantic>=2.0.0",
    ],
    python_requires=">=3.11",
    entry_points={
        "console_scripts": [
            "player-universe-load=scripts.__main__:main",
        ],
    },
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Programming Language :: Python :: 3.13",
    ],
)