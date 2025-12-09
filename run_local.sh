#!/bin/bash
# 로컬에서 Streamlit 앱 실행 스크립트

echo "🚀 Navi QA 테스트 자동화 시스템 시작"
echo ""

# Python 가상환경 확인
if [ ! -d "venv" ]; then
    echo "📦 가상환경 생성 중..."
    python3 -m venv venv
fi

# 가상환경 활성화
echo "🔧 가상환경 활성화..."
source venv/bin/activate

# 의존성 설치
echo "📥 의존성 설치 중..."
pip install --upgrade pip
pip install -r requirements.txt

# Playwright 브라우저 설치
echo "🌐 Playwright 브라우저 설치 중..."
playwright install chromium

echo ""
echo "✅ 준비 완료!"
echo ""
echo "🌐 Streamlit 앱을 시작합니다..."
echo "   브라우저에서 자동으로 열립니다."
echo ""

# Streamlit 실행
streamlit run app.py --server.port=8501 --server.address=localhost

