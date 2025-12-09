# Navi QA 테스트 자동화 시스템

Playwright 기반 웹 UI 자동화 테스트 시스템입니다. Streamlit 웹 인터페이스를 통해 엑셀 파일을 업로드하고, 자동으로 테스트를 실행하여 결과를 수집하고 분석합니다.

## 📋 목차

- [주요 기능](#주요-기능)
- [시스템 요구사항](#시스템-요구사항)
- [설치 방법](#설치-방법)
- [사용 방법](#사용-방법)
- [프로젝트 구조](#프로젝트-구조)
- [문제 해결](#문제-해결)
- [기술 스택](#기술-스택)

## ✨ 주요 기능

- 📊 **엑셀 파일 기반 테스트 케이스 관리**: 엑셀 파일로 테스트 케이스를 정의하고 업로드
- 🔄 **멀티턴 시나리오 지원 (Phase 1)**: `test_case_id` + `turn_number`로 여러 턴을 순차 실행
- 🤖 **Playwright 자동화**: 브라우저 자동 제어로 테스트 실행
- 📈 **실시간 진행 상황 표시**: 테스트 진행률, 경과 시간, 예상 남은 시간 표시
- 📊 **결과 분석 및 시각화**: Pass/Fail 판정, 유사도 점수, 상세 결과 표시
- 💾 **CSV 다운로드**: 테스트 결과를 CSV 파일로 다운로드
- 🔍 **네트워크 연결 테스트**: 서버 접근 가능 여부 사전 확인
- 🏥 **헬스체크 엔드포인트**: `/health` 엔드포인트 제공

## 🆕 변경사항 (멀티턴 Phase 1)

- `test_case_id`와 `turn_number` 컬럼을 추가해 멀티턴 시나리오를 순차 실행
- 같은 `test_case_id` 내에서는 첫 턴만 페이지 리셋/초기화, 이후 턴은 세션 유지
- 각 턴별 결과를 별도 행으로 저장 (`test_case_id`, `turn_number` 포함)
- UI에 시나리오 필터 추가 (멀티턴 결과를 필터링하여 확인 가능)
- `is_driving` 체크박스 자동 처리 개선 (비가시 상태 스크롤 및 강제 토글)

## 💻 시스템 요구사항

- **Python**: 3.11 이상
- **운영체제**: macOS, Windows, Linux
- **메모리**: 최소 4GB RAM (권장 8GB)
- **네트워크**: 인터넷 연결 (의존성 다운로드용)
- **VPN**: 테스트 대상 서버 접근을 위한 VPN 연결 (사내망인 경우)

## 🚀 설치 방법

### 방법 1: 자동 스크립트 사용 (추천)

```bash
# 실행 권한 부여 (처음 한 번만)
chmod +x run_local.sh

# 스크립트 실행
./run_local.sh
```

이 스크립트가 다음을 자동으로 수행합니다:
- 가상환경 생성
- 의존성 설치
- Playwright 브라우저 설치
- Streamlit 앱 실행

### 방법 2: 수동 설치

1. **가상환경 생성**
```bash
python3 -m venv venv
```

2. **가상환경 활성화**
```bash
# macOS/Linux
source venv/bin/activate

# Windows
venv\Scripts\activate
```

3. **의존성 설치**
```bash
pip install --upgrade pip
pip install -r requirements.txt
```

4. **Playwright 브라우저 설치**
```bash
playwright install chromium
```

## 📖 사용 방법

### 1. 앱 실행

```bash
streamlit run app.py
```

브라우저에서 자동으로 열리거나, 수동으로 `http://localhost:8501` 접속

### 2. 엑셀 파일 준비

테스트 케이스 엑셀 파일은 다음 컬럼을 포함해야 합니다:

| 컬럼명 | 타입 | 설명 | 예시 |
|--------|------|------|------|
| `test_case_id` | 문자열/숫자 | (멀티턴) 시나리오 ID | 1 |
| `turn_number` | 숫자 | (멀티턴) 턴 번호 (1,2,3…) | 1 |
| `user_id` | 문자열 | 사용자 ID | "user123" |
| `lat` | 숫자 | 위도 | 37.5665 |
| `lng` | 숫자 | 경도 | 126.9780 |
| `is_driving` | boolean/문자열 | 운전 여부 | true / "true" |
| `message` | 문자열 | 사용자 입력 메시지 | "안녕하세요" |
| `tts_expected` | 문자열 | 기대 TTS 출력 | "안녕하세요" |

> 멀티턴 시나리오 예시  
> ```
> test_case_id | turn_number | user_id | lat | lng | is_driving | message           | tts_expected
> 1            | 1           | u1      | ... | ... | TRUE       | 강남역 가고싶어     | 강남역 2호선 맞아?
> 1            | 2           | u1      | ... | ... | TRUE       | 응                 | 안내할게요
> 2            | 1           | u1      | ... | ... | TRUE       | 강남역 가고싶어     | 강남역 2호선 맞아?
> 2            | 2           | u1      | ... | ... | TRUE       | 아니               | 취소합니다.
> ```
> - 동일 턴에서 분기가 필요하면 `turn_number`를 2,3 등으로 나누어 넣어주세요. (현재는 같은 턴 번호의 중복을 허용하지 않습니다.)

### 3. 테스트 실행

1. **엑셀 파일 업로드**
   - 왼쪽 사이드바에서 "📤 테스트 케이스 파일 업로드" 클릭
   - 엑셀 파일 선택

2. **네트워크 설정 확인** (필요시)
   - "🔧 네트워크 설정" 확장
   - "🔍 네트워크 연결 테스트" 버튼 클릭
   - 연결 실패 시 IP 주소 직접 입력 또는 프록시 설정

3. **테스트 실행**
   - "▶️ 테스트 실행" 버튼 클릭
   - Playwright가 브라우저를 열고 자동으로 테스트 실행
   - 진행 상황이 실시간으로 표시됨

4. **결과 확인**
   - 테스트 완료 후 자동으로 결과 표시
   - Pass/Fail, 유사도 점수, 상세 정보 확인
   - "📥 CSV 다운로드" 버튼으로 결과 저장

## 📁 프로젝트 구조

```
navi-qa-cursor/
├── app.py                      # Streamlit 메인 애플리케이션
├── test_automation.py          # Playwright 자동화 모듈
├── similarity.py               # 유사도 계산 모듈
├── health_check.py             # 헬스체크 엔드포인트
├── requirements.txt             # Python 의존성
├── check_resources.sh          # 리소스 체크 스크립트
├── test_connection.py          # 네트워크 연결 테스트 스크립트
├── run_local.sh                # 로컬 실행 스크립트
├── static/                     # 정적 파일
│   ├── browser-automation.js   # 브라우저 자동화 스크립트
│   ├── auto-run.js            # 자동 실행 스크립트
│   └── similarity.js           # 유사도 계산 (JavaScript)
├── Dockerfile                  # Docker 빌드 파일
├── nginx.conf                  # nginx 설정 파일
├── .dockerignore               # Docker 빌드 제외 파일
├── README.md                   # 이 파일
├── README_LOCAL_SETUP.md       # 로컬 설정 상세 가이드
└── QUICK_START.md              # 빠른 시작 가이드
```

## 🔧 문제 해결

### 서버 연결 실패

**증상:**
- "❌ 네트워크 연결 실패: DNS 해석 불가"
- "❌ 연결 타임아웃"

**해결 방법:**

1. **연결 테스트 실행**
```bash
python3 test_connection.py
```

2. **VPN 연결 확인**
   - 사내망 접근을 위해 VPN 연결 필요
   - VPN 연결 후 다시 테스트

3. **IP 주소 직접 입력**
   - Streamlit UI → "🔧 네트워크 설정"
   - "테스트 대상 URL"에 IP 주소 입력
   - 예: `https://10.0.0.1/streamlit/`

4. **프록시 설정** (필요시)
   - Streamlit UI → "🔧 네트워크 설정" → "프록시 설정"
   - 프록시 서버 정보 입력

### Playwright 브라우저 설치 실패

```bash
# 시스템 Chromium 사용 (macOS)
brew install chromium

# Playwright 브라우저 재설치
playwright install chromium --force
```

### 메모리 부족

- Chromium은 메모리를 많이 사용합니다 (~200-300MB)
- 다른 애플리케이션을 종료하고 다시 시도

### 기타 오류

- 가상환경이 활성화되어 있는지 확인
- 모든 의존성이 설치되었는지 확인: `pip list`
- Python 버전 확인: `python3 --version` (3.11 이상 필요)

## 🛠 기술 스택

- **Python 3.11+**: 메인 프로그래밍 언어
- **Streamlit**: 웹 UI 프레임워크
- **Playwright**: 브라우저 자동화
- **Pandas**: 데이터 처리 및 분석
- **openpyxl**: 엑셀 파일 읽기/쓰기
- **NumPy**: 수치 계산
- **Flask**: 헬스체크 서버

## 📝 주요 기능 상세

### 테스트 자동화 프로세스

1. **초기화**: 최초 1회 Request Fields 입력 (user_id, lat, lng, is_driving)
2. **메시지 전송**: 각 테스트 케이스의 message를 순차적으로 전송
3. **결과 수집**: latency, response, raw JSON, TTS 추출
4. **비교 분석**: tts_expected와 실제 TTS 비교하여 유사도 계산
5. **판정**: 유사도 기반 Pass/Fail 판정

### 유사도 계산

- 문자열 유사도 알고리즘 사용
- 맥락 기반 판단 (사용자 메시지 고려)
- 임계값 기반 Pass/Fail 판정

## 🔒 보안 및 주의사항

- **VPN 연결**: 사내망 접근을 위해 VPN 필수
- **프록시 설정**: 사외망에서 접근 시 프록시 필요할 수 있음
- **민감한 정보**: 엑셀 파일에 민감한 정보가 포함되지 않도록 주의
- **네트워크**: 테스트 대상 서버 접근 권한 필요

## 📞 지원

문제가 발생하면:
1. `test_connection.py`로 연결 상태 확인
2. Streamlit UI의 "🔧 네트워크 설정"에서 연결 테스트
3. 로그 확인 (터미널 출력)
4. `README_LOCAL_SETUP.md` 참고

## 📄 라이선스

이 프로젝트는 내부 사용을 위한 것입니다.

---

**마지막 업데이트**: 2025-12-05
