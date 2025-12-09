# 빠른 시작 가이드

## 1단계: 환경 준비

```bash
# 프로젝트 디렉토리로 이동
cd /Users/henry.up/Desktop/navi-qa-cursor

# 가상환경 생성 및 활성화
python3 -m venv venv
source venv/bin/activate

# 의존성 설치
pip install --upgrade pip
pip install -r requirements.txt

# Playwright 브라우저 설치
playwright install chromium
```

## 2단계: 연결 확인

**중요: VPN 연결이 필요합니다!**

```bash
# 연결 테스트
python3 test_connection.py
```

연결이 실패하면:
1. VPN 연결 확인
2. Streamlit UI에서 IP 주소 직접 입력 시도

## 3단계: 앱 실행

```bash
streamlit run app.py
```

또는 자동 스크립트 사용:
```bash
./run_local.sh
```

## 4단계: 테스트 실행

1. 브라우저에서 Streamlit 앱 열림 (보통 `http://localhost:8501`)
2. 왼쪽 사이드바에서 엑셀 파일 업로드
3. "🔧 네트워크 설정"에서 연결 테스트
4. "▶️ 테스트 실행" 버튼 클릭
5. Playwright가 자동으로 브라우저를 열고 테스트 실행

## 연결 문제 해결

### DNS 해석 실패
- Streamlit UI → "네트워크 설정" → IP 주소 직접 입력
- 예: `https://10.0.0.1/streamlit/`

### 타임아웃
- VPN 연결 확인
- 방화벽 설정 확인

### 연결 거부
- URL이 올바른지 확인
- 서버가 실행 중인지 확인

## 도움말

더 자세한 내용은 `README_LOCAL_SETUP.md`를 참고하세요.
