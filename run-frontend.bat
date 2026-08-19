@echo off
cd /d "%~dp0frontend"
call npm.cmd install
call npm.cmd run dev
