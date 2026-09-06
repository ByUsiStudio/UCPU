@echo off
pyinstaller cpu.py --name ucpu --add-binary "ucpu/ucpu_native.dll:."
