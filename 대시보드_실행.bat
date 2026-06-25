@echo off
chcp 65001 >nul
echo ============================================
echo   3차원 측정데이터 AI 대시보드
echo ============================================
echo.
echo [1/2] 필요한 라이브러리 설치 확인...
pip install -r requirements.txt
echo.
echo [2/2] 서버 시작 - 브라우저에서 http://127.0.0.1:5000 접속
echo  (종료하려면 이 창에서 Ctrl + C)
echo.
REM ---- AI(H-chat) 연동 시 아래 4줄 앞의 REM 을 지우고 값만 채우세요 ----
REM set LLM_PROVIDER=custom
REM set LLM_API_URL=https://사내-hchat-주소/v1/chat/completions
REM set LLM_API_KEY=발급키
REM set LLM_MODEL=모델명
python app.py
pause
