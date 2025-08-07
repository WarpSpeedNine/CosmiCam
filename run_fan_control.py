#!/usr/bin/env python3
"""Script to run the fan control service."""

from src.hardware.fan_control import run_fan_control

if __name__ == "__main__":
    run_fan_control()
