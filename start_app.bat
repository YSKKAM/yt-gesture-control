@echo off
title YouTube Gesture Control
color 0A
echo ======================================================
echo           Starting YouTube Gesture Control
echo ======================================================
echo.
cd /d "c:\mera soda\vscode\playpause"
python -m app.main
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo ======================================================
    echo App closed or encountered an error.
    echo ======================================================
    pause
)
