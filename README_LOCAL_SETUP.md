# 로컬 실행 가이드

## 빠른 시작

### 방법 1: 자동 스크립트 사용 (추천)

```bash
./run_local.sh
```

### 방법 2: 수동 실행

1. **가상환경 생성 및 활성화**
```bash
python3 -m venv venv
source venv/bin/activate  # Mac/Linux
# 또는
venv\Scripts\activate  # Windows
```

2. **의존성 설치**
```bash
pip install --upgrade pip
pip install -r requirements.txt
```

3. **Playwright 브라우저 설치**
```bash
playwright install chromium
```

4. **Streamlit 앱 실행**
```bash
streamlit run app.py
```

## 사용 방법

1. **엑셀 파일 준비**
   - 필수 컬럼: `user_id`, `lat`, `lng`, `is_driving`, `message`, `tts_expected`
   - 각 행이 하나의 테스트 케이스

2. **테스트 실행**
   - Streamlit 웹 UI에서 엑셀 파일 업로드
   - "▶️ 테스트 실행" 버튼 클릭
   - Playwright가 자동으로 브라우저를 열고 테스트 실행
   - 진행 상황이 실시간으로 표시됨

3. **결과 확인**
   - 테스트 완료 후 자동으로 결과 표시
   - Pass/Fail, 유사도 점수, 상세 정보 확인 가능
   - CSV 다운로드 가능

## 네트워크 설정

### 사내망 접근
- VPN 연결 확인
- 테스트 대상 URL: `https://navi-agent-adk-api.dev.onkakao.net/streamlit/`

### 프록시 설정 (필요시)
```bash
export HTTP_PROXY=http://proxy.example.com:8080
export HTTPS_PROXY=http://proxy.example.com:8080
```

## 문제 해결

### 서버 연결 실패 (가장 흔한 문제)

**증상:**
- "❌ 네트워크 연결 실패: DNS 해석 불가"
- "❌ 연결 타임아웃"
- "❌ 연결 거부"

**해결 방법:**

1. **연결 테스트 스크립트 실행**
```bash
python3 test_connection.py
```

2. **VPN 연결 확인**
   - 사내망에 접근하려면 VPN이 필요합니다
   - VPN이 연결되어 있는지 확인하세요

3. **Streamlit UI에서 연결 테스트**
   - Streamlit 앱 실행 후
   - 왼쪽 사이드바 → "🔧 네트워크 설정" 확장
   - "🔍 네트워크 연결 테스트" 버튼 클릭

4. **IP 주소 직접 입력 (DNS 해석 실패 시)**
   - Streamlit UI의 "테스트 대상 URL"에 IP 주소 직접 입력
   - 예: `https://10.0.0.1/streamlit/`
   - 또는 `http://10.0.0.1:8080/streamlit/`

5. **프록시 설정 (필요시)**
   - Streamlit UI의 "프록시 설정" 섹션에서 설정
   - 또는 환경 변수로 설정:
   ```bash
   export HTTP_PROXY=http://proxy.example.com:8080
   export HTTPS_PROXY=http://proxy.example.com:8080
   ```

6. **hosts 파일에 IP 매핑 추가 (임시 해결책)**
   ```bash
   # Mac/Linux
   sudo nano /etc/hosts
   
   # 추가할 내용 (예시)
   # 10.0.0.1  navi-agent-adk-api.dev.onkakao.net
   ```

### Playwright 브라우저 설치 실패
```bash
# 시스템 Chromium 사용 (Mac)
brew install chromium

# 또는 Playwright 브라우저 재설치
playwright install chromium --force
```

### 메모리 부족
- Chromium은 메모리를 많이 사용합니다
- 다른 애플리케이션을 종료하고 다시 시도

## 시스템 요구사항

- Python 3.11 이상
- Mac/Windows/Linux
- 최소 4GB RAM (권장 8GB)
- 인터넷 연결 (의존성 다운로드용)

