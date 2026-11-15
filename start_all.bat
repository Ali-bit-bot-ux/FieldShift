@echo off
title FieldShift Launcher
chcp 65001 >nul
cd /d "D:\legion\Projects\FieldShift"

echo ===================================================
echo           FIELDSHIFT: CROP ROTATION PLANNER
echo ===================================================
echo [1/2] Запуск Python FastAPI бэкенда на порту 8000...
start "FieldShift Backend (FastAPI)" cmd /k "cd /d D:\legion\Projects\FieldShift && uvicorn modules.fieldshift_api:app --host 127.0.0.1 --port 8000"

echo [2/2] Запуск Next.js веб-интерфейса на порту 3001...
start "FieldShift Web UI (Next.js)" cmd /k "cd /d D:\legion\Projects\FieldShift\web && npm run dev"

timeout /t 3 >nul

echo.
echo ===================================================
echo СЕРВЕРЫ УСПЕШНО ЗАПУЩЕНЫ!
echo.
echo -> Веб-приложение: http://localhost:3001
echo -> API Документация (Swagger): http://localhost:8000/docs
echo ===================================================
echo Открываю браузер...
start http://localhost:3001
pause

