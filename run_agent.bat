@echo off
REM Script để chạy SAGSIN Agent trên Windows

echo Checking virtual environment...
if not exist ".venv" (
    echo Creating virtual environment...
    python -m venv .venv
)

echo Activating virtual environment...
call .venv\Scripts\activate.bat

echo Installing dependencies...
pip install grpcio grpcio-tools psutil

REM Set environment variables (có thể customize)
if "%GRPC_TARGET%"=="" set GRPC_TARGET=localhost:50051
if "%NODE_ID%"=="" set NODE_ID=%COMPUTERNAME%
if "%INTERVAL_SEC%"=="" set INTERVAL_SEC=5.0

echo Starting SAGSIN Agent...
echo Target Server: %GRPC_TARGET%
echo Node ID: %NODE_ID%
echo Interval: %INTERVAL_SEC%s
echo ==================================

REM Chạy agent
python -m agent.agent

pause
