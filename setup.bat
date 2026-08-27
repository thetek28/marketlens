@echo off
echo Setting up MarketLens virtual environment...
python -m venv venv
"%~dp0venv\Scripts\pip.exe" install -r requirements.txt
"%~dp0venv\Scripts\pip.exe" install pytest
echo.
echo Setup complete! Run: run_gui.bat
