"""
Streamlit 기반 테스트 자동화 웹 애플리케이션
엑셀 파일을 업로드하여 자동화 테스트를 수행하고 결과를 시각화합니다.
"""
import streamlit as st
import pandas as pd
import time
import os
import sys
import json
import base64
from pathlib import Path
from typing import Optional

# 헬스체크 엔드포인트를 위한 백그라운드 서버 시작
try:
    from health_check import start_health_check
    start_health_check()
except Exception:
    pass  # 헬스체크 서버 시작 실패해도 앱은 계속 실행

# Playwright 테스트 자동화 모듈 import
from test_automation import TestAutomation

# 페이지 설정
st.set_page_config(
    page_title="Evaluation",
    page_icon="🧪",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Pretendard 폰트 및 Material Icons 로드 (HTML head에 직접 삽입)
st.markdown("""
<link rel="preconnect" href="https://cdn.jsdelivr.net">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" as="style" crossorigin href="https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/static/pretendard-dynamic-subset.min.css" />
<link href="https://fonts.googleapis.com/icon?family=Material+Icons" rel="stylesheet">
""", unsafe_allow_html=True)

# 커스텀 CSS (카카오 스타일)
st.markdown("""
<style>
    /* Pretendard 웹폰트 로드 (백업용 @import) */
    @import url('https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/static/pretendard-dynamic-subset.min.css');
    
    /* 전체 폰트 설정 및 크기 조정 (카카오 스타일) */
    * {
        font-family: 'Pretendard', -apple-system, BlinkMacSystemFont, system-ui, Roboto, 'Helvetica Neue', 'Segoe UI', 'Apple SD Gothic Neo', 'Noto Sans KR', 'Malgun Gothic', 'Apple Color Emoji', 'Segoe UI Emoji', 'Segoe UI Symbol', sans-serif !important;
        font-size: 13px !important;
    }
    
    /* Streamlit 기본 요소에도 폰트 적용 */
    html, body, [class*="css"] {
        font-family: 'Pretendard', -apple-system, BlinkMacSystemFont, system-ui, Roboto, 'Helvetica Neue', 'Segoe UI', 'Apple SD Gothic Neo', 'Noto Sans KR', 'Malgun Gothic', 'Apple Color Emoji', 'Segoe UI Emoji', 'Segoe UI Symbol', sans-serif !important;
        font-size: 13px !important;
    }
    
    /* 입력 필드에도 폰트 적용 */
    input, textarea, select, button {
        font-family: 'Pretendard', -apple-system, BlinkMacSystemFont, system-ui, Roboto, 'Helvetica Neue', 'Segoe UI', 'Apple SD Gothic Neo', 'Noto Sans KR', 'Malgun Gothic', 'Apple Color Emoji', 'Segoe UI Emoji', 'Segoe UI Symbol', sans-serif !important;
        font-size: 13px !important;
    }
    
    /* Streamlit의 모든 텍스트 요소에 적용 */
    p, span, div, label, a, li, td, th {
        font-family: 'Pretendard', -apple-system, BlinkMacSystemFont, system-ui, Roboto, 'Helvetica Neue', 'Segoe UI', 'Apple SD Gothic Neo', 'Noto Sans KR', 'Malgun Gothic', 'Apple Color Emoji', 'Segoe UI Emoji', 'Segoe UI Symbol', sans-serif !important;
        font-size: 13px !important;
    }
    
    /* 제목 크기 조정 */
    h1 { font-size: 1.5rem !important; }
    h2 { font-size: 1.3rem !important; }
    h3 { font-size: 1.1rem !important; }
    h4 { font-size: 1rem !important; }
    h5 { font-size: 0.9rem !important; }
    h6 { font-size: 0.85rem !important; }
    
    .main-header {
        font-size: 1.8rem;
        font-weight: 700;
        color: #000000;
        margin-bottom: 0.8rem;
        font-family: 'Pretendard', -apple-system, BlinkMacSystemFont, system-ui, sans-serif !important;
    }
    .warning-box {
        padding: 0.8rem;
        border-radius: 8px;
        background-color: #FFF9E6;
        border-left: 3px solid #FEE500;
        margin-bottom: 1rem;
        font-family: 'Pretendard', sans-serif !important;
        font-size: 13px !important;
        box-shadow: 0 1px 3px rgba(0,0,0,0.1);
    }
    .info-box {
        padding: 0.8rem;
        border-radius: 8px;
        background-color: #F5F5F5;
        border-left: 3px solid #000000;
        margin-bottom: 0.8rem;
        font-family: 'Pretendard', sans-serif !important;
        font-size: 13px !important;
        box-shadow: 0 1px 3px rgba(0,0,0,0.05);
    }
    .metric-card {
        background-color: #f8f9fa;
        padding: 1rem;
        border-radius: 0.5rem;
        border: 1px solid #dee2e6;
        font-family: 'Pretendard', sans-serif !important;
    }
    .test-case-card {
        background-color: #ffffff;
        padding: 1.5rem;
        border-radius: 0.5rem;
        border: 1px solid #dee2e6;
        margin-bottom: 1rem;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        font-family: 'Pretendard', sans-serif !important;
    }
    .pass-badge {
        background-color: #E8F5E9;
        color: #2E7D32;
        padding: 0.2rem 0.6rem;
        border-radius: 12px;
        font-weight: 600;
        font-size: 12px !important;
        font-family: 'Pretendard', sans-serif !important;
    }
    .fail-badge {
        background-color: #FFEBEE;
        color: #C62828;
        padding: 0.2rem 0.6rem;
        border-radius: 12px;
        font-weight: 600;
        font-size: 12px !important;
        font-family: 'Pretendard', sans-serif !important;
    }
    
    /* Material Icons 폰트 로드 */
    @import url('https://fonts.googleapis.com/icon?family=Material+Icons');
    
    /* Material Icons 폰트 적용 */
    .material-icons,
    [class*="material-icons"],
    [data-testid="stIconMaterial"] {
        font-family: 'Material Icons' !important;
        font-weight: normal !important;
        font-style: normal !important;
        font-size: 24px !important;
        line-height: 1 !important;
        letter-spacing: normal !important;
        text-transform: none !important;
        display: inline-block !important;
        white-space: nowrap !important;
        word-wrap: normal !important;
        direction: ltr !important;
        -webkit-font-feature-settings: 'liga' !important;
        -webkit-font-smoothing: antialiased !important;
    }
    
    /* 카카오 스타일 버튼 */
    button[kind="primary"] {
        background-color: #FEE500 !important;
        color: #000000 !important;
        border-radius: 8px !important;
        font-weight: 600 !important;
        font-size: 13px !important;
        padding: 0.5rem 1rem !important;
        border: none !important;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1) !important;
    }
    
    button[kind="primary"]:hover {
        background-color: #FDD835 !important;
        box-shadow: 0 3px 6px rgba(0,0,0,0.15) !important;
    }
    
    /* 카카오 스타일 입력 필드 */
    input, textarea, select {
        border-radius: 8px !important;
        border: 1px solid #E0E0E0 !important;
        font-size: 13px !important;
    }
    
    input:focus, textarea:focus, select:focus {
        border-color: #000000 !important;
        box-shadow: 0 0 0 2px rgba(0,0,0,0.1) !important;
    }
    
    /* 테이블 스타일 개선 */
    table {
        font-size: 12px !important;
    }
    
    th, td {
        padding: 0.5rem !important;
        font-size: 12px !important;
    }
</style>
""", unsafe_allow_html=True)

# 메인 헤더
st.markdown("""
<div class="main-header">🧪 Evaluation</div>
""", unsafe_allow_html=True)

st.markdown("""
<div class="warning-box">
    <strong>⚠️ 주의사항</strong><br>
    이 시스템은 <strong>VPN 또는 사내망</strong>에서만 접근 가능합니다.<br>
    사외망에서 실행하는 경우 프록시 설정이 필요할 수 있습니다.
</div>
""", unsafe_allow_html=True)

st.markdown("---")

# 세션 상태 초기화
if 'test_results' not in st.session_state:
    st.session_state.test_results = None
if 'test_in_progress' not in st.session_state:
    st.session_state.test_in_progress = False
if 'test_progress' not in st.session_state:
    st.session_state.test_progress = {'current': 0, 'total': 0}
if 'search_query' not in st.session_state:
    st.session_state.search_query = ''
if 'selected_columns' not in st.session_state:
    st.session_state.selected_columns = None
if 'test_file_data' not in st.session_state:
    st.session_state.test_file_data = None
if 'proxy_config' not in st.session_state:
    st.session_state.proxy_config = {
        'server': os.environ.get('HTTP_PROXY', ''),
        'user': os.environ.get('PROXY_USER', ''),
        'pass': os.environ.get('PROXY_PASS', '')
    }
if 'base_url' not in st.session_state:
    st.session_state.base_url = os.environ.get('TEST_BASE_URL', 'https://navi-agent-adk-api.dev.onkakao.net/streamlit/')


def validate_excel_file(df: pd.DataFrame) -> tuple[bool, str]:
    """
    엑셀 파일의 필수 컬럼을 검증합니다.
    대소문자 구분 없이 검증합니다.
    멀티턴 시나리오를 지원합니다 (test_case_id, turn_number).
    
    Args:
        df: 업로드된 DataFrame
    
    Returns:
        (is_valid: bool, error_message: str)
    """
    required_columns = ['user_id', 'lat', 'lng', 'is_driving', 'message', 'tts_expected']
    df_columns_lower = {col.lower(): col for col in df.columns}
    missing_columns = []
    
    for req_col in required_columns:
        if req_col.lower() not in df_columns_lower:
            missing_columns.append(req_col)
    
    if missing_columns:
        return False, f"필수 컬럼이 없습니다: {', '.join(missing_columns)}"
    
    if df.empty:
        return False, "테스트 케이스가 없습니다."
    
    # 멀티턴 시나리오 검증 (test_case_id와 turn_number가 모두 있는 경우)
    has_test_case_id = 'test_case_id' in df_columns_lower or 'TEST_CASE_ID' in df.columns
    has_turn_number = 'turn_number' in df_columns_lower or 'TURN_NUMBER' in df.columns
    
    if has_test_case_id and has_turn_number:
        # test_case_id별로 turn_number가 1부터 순차적으로 있는지 확인
        test_case_id_col = df_columns_lower.get('test_case_id') or 'TEST_CASE_ID'
        turn_number_col = df_columns_lower.get('turn_number') or 'TURN_NUMBER'
        
        for test_case_id in df[test_case_id_col].unique():
            case_turns = df[df[test_case_id_col] == test_case_id][turn_number_col].sort_values()
            expected_turns = list(range(1, len(case_turns) + 1))
            if not case_turns.tolist() == expected_turns:
                return False, f"test_case_id '{test_case_id}'의 turn_number가 순차적이지 않습니다. (1, 2, 3, ... 순서여야 함)"
    
    return True, ""


def format_time(seconds):
    """초를 읽기 쉬운 시간 형식으로 변환"""
    if seconds is None:
        return "계산 중..."
    if seconds < 60:
        return f"{int(seconds)}초"
    elif seconds < 3600:
        minutes = int(seconds // 60)
        secs = int(seconds % 60)
        return f"{minutes}분 {secs}초"
    else:
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        return f"{hours}시간 {minutes}분"


# 사이드바: 엑셀 파일 업로드
with st.sidebar:
    st.markdown("### 📁 테스트 파일 업로드")
    
    st.markdown("""
    <div class="info-box">
        <strong>📋 사용 방법</strong><br>
        1. 엑셀 파일 업로드<br>
        2. "테스트 실행" 버튼 클릭<br>
        3. 브라우저에서 자동 테스트 수행 (Python 설치 불필요!)<br>
        4. 결과 자동 수집 및 시각화<br><br>
        <strong>🌐 네트워크 설정:</strong> 테스트 대상 URL을 설정하세요 (IP 주소 직접 입력 가능)
    </div>
    """, unsafe_allow_html=True)
    
    st.markdown("---")
    
    # 네트워크 연결 테스트 및 프록시 설정
    with st.expander("🔧 네트워크 설정", expanded=True):
        st.info("💡 DNS 해석이 안 될 때는 IP 주소를 직접 입력하세요. (예: https://10.0.0.1/streamlit/)")
        
        # 테스트 대상 URL 설정
        st.markdown("**테스트 대상 URL 설정**")
        default_url = st.session_state.base_url
        test_url = st.text_input(
            "테스트 대상 URL", 
            value=default_url, 
            help="DNS 해석이 안 되면 IP 주소를 직접 입력하세요. 예: https://10.0.0.1/streamlit/",
            key="base_url_input"
        )
        
        if st.button("💾 URL 저장", use_container_width=True):
            st.session_state.base_url = test_url
            os.environ['TEST_BASE_URL'] = test_url
            st.success(f"✅ URL이 저장되었습니다: {test_url}")
        
        st.markdown(f"**현재 설정:** `{st.session_state.base_url}`")
        st.markdown("---")
        
        # 네트워크 연결 테스트 버튼
        if st.button("🔍 네트워크 연결 테스트", use_container_width=True):
            with st.spinner("연결 테스트 중..."):
                try:
                    import requests
                    import urllib3
                    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
                    # 현재 설정된 URL 사용
                    current_url = st.session_state.base_url
                    response = requests.get(current_url, timeout=10, verify=False)  # SSL 검증 비활성화 (사내망용)
                    if response.status_code == 200:
                        st.success(f"✅ 연결 성공! (상태 코드: {response.status_code})")
                    else:
                        st.warning(f"⚠️ 연결되었지만 상태 코드가 {response.status_code}입니다.")
                except requests.exceptions.Timeout:
                    st.error("❌ 타임아웃: 서버에 연결할 수 없습니다. VPN 연결을 확인하세요.")
                except requests.exceptions.ConnectionError as e:
                    error_msg = str(e)
                    if "NameResolutionError" in error_msg or "Failed to resolve" in error_msg:
                        st.error(f"❌ DNS 해석 실패: {error_msg}\n\n💡 **해결 방법:**\n1. IP 주소를 직접 입력하세요 (예: https://10.0.0.1/streamlit/)\n2. hosts 파일에 IP 매핑 추가 (배포 환경 관리자에게 요청)\n3. VPN 연결 확인")
                    else:
                        st.error(f"❌ 연결 실패: {error_msg}\n\n💡 해결 방법:\n1. VPN 연결 확인\n2. 사내망 접근 권한 확인\n3. 네트워크 관리자에게 문의")
                except Exception as e:
                    st.error(f"❌ 오류 발생: {str(e)}")
        
        st.markdown("---")
        st.markdown("**프록시 설정 (프록시가 필요한 경우에만)**")
        proxy_server = st.text_input("프록시 서버 (선택)", value=st.session_state.proxy_config.get('server', ''), help="예: http://proxy.example.com:8080")
        proxy_user = st.text_input("프록시 사용자명 (선택)", value=st.session_state.proxy_config.get('user', ''))
        proxy_pass = st.text_input("프록시 비밀번호 (선택)", type="password", value=st.session_state.proxy_config.get('pass', ''))
        
        if st.button("💾 프록시 설정 저장", use_container_width=True):
            st.session_state.proxy_config = {
                'server': proxy_server,
                'user': proxy_user,
                'pass': proxy_pass
            }
            if proxy_server:
                os.environ['HTTP_PROXY'] = proxy_server
                os.environ['HTTPS_PROXY'] = proxy_server
                if proxy_user:
                    os.environ['PROXY_USER'] = proxy_user
                if proxy_pass:
                    os.environ['PROXY_PASS'] = proxy_pass
                st.success("✅ 프록시 설정이 저장되었습니다.")
            else:
                # 프록시 제거
                os.environ.pop('HTTP_PROXY', None)
                os.environ.pop('HTTPS_PROXY', None)
                os.environ.pop('PROXY_USER', None)
                os.environ.pop('PROXY_PASS', None)
                st.info("ℹ️ 프록시 설정이 제거되었습니다.")
    
    st.markdown("---")
    
    # 엑셀 파일 업로드
    uploaded_file = st.file_uploader(
        "엑셀 파일을 선택하세요",
        type=['xlsx', 'xls'],
        help="필수 컬럼: user_id, lat, lng, is_driving, message, tts_expected\n멀티턴 시나리오: test_case_id, turn_number 추가"
    )
    
    if uploaded_file is not None:
        try:
            # 엑셀 파일 읽기
            df = pd.read_excel(uploaded_file)
            
            # user_id를 문자열로 변환
            if 'user_id' in df.columns:
                df['user_id'] = df['user_id'].astype(str)
            
            st.success(f"✅ 파일 로드 완료: {len(df)}개 테스트 케이스")
            
            # 파일 미리보기
            with st.expander("📋 테스트 케이스 미리보기", expanded=False):
                st.dataframe(df.head(10), use_container_width=True, height=200)
            
            # 파일 검증
            is_valid, error_message = validate_excel_file(df)
            
            if not is_valid:
                st.error(f"❌ {error_message}")
            else:
                # 테스트 실행 버튼
                if st.button("▶️ 테스트 실행", type="primary", disabled=st.session_state.test_in_progress, use_container_width=True):
                    st.session_state.test_in_progress = True
                    st.session_state.test_results = None
                    st.session_state.test_cases_df = df
                    st.rerun()
        
        except Exception as e:
            st.error(f"❌ 파일 읽기 오류: {str(e)}")
    
    st.markdown("---")
    st.markdown("### 📖 상세 안내")
    st.markdown("""
    **동작 방식:**
    1. 엑셀 파일 업로드
    2. Playwright로 자동 테스트 수행
    3. 결과 자동 수집 및 시각화
    
    **네트워크:**
    - 사내망: 자동 접근
    - 사외망: 프록시 설정 필요
    """)


# 메인 영역
if st.session_state.test_in_progress and 'test_cases_df' in st.session_state:
    # 테스트 실행 중 - Playwright로 직접 실행
    test_cases_df = st.session_state.test_cases_df
    base_url = st.session_state.base_url
    
    st.info("⏳ Playwright로 테스트 실행 중...")
    
    # 테스트 케이스 개수 표시
    test_cases_count = len(test_cases_df)
    st.info(f"📊 **총 {test_cases_count}개의 테스트 케이스** 실행 예정")
    
    # 진행 상황 표시
    progress_bar = st.progress(0)
    status_text = st.empty()
    status_text.text("테스트 준비 중...")
    
    # Playwright 테스트 실행
    try:
        # 진행 상황 콜백 함수
        def update_progress(current, total, elapsed_time, estimated_remaining):
            progress = current / total
            progress_bar.progress(progress)
            
            elapsed_str = format_time(elapsed_time)
            if estimated_remaining:
                remaining_str = format_time(estimated_remaining)
                status_text.text(f"테스트 진행 중: {current}/{total} ({elapsed_str} 경과, 약 {remaining_str} 남음)")
            else:
                status_text.text(f"테스트 진행 중: {current}/{total} ({elapsed_str} 경과)")
        
        # TestAutomation 인스턴스 생성 및 실행
        automation = TestAutomation(base_url=base_url)
        status_text.text("브라우저 시작 중...")
        
        # 테스트 실행
        results_df = automation.run_tests(test_cases_df, progress_callback=update_progress)
        
        # 결과 저장
        st.session_state.test_results = results_df
        st.session_state.test_in_progress = False
        if 'test_cases_df' in st.session_state:
            del st.session_state.test_cases_df
        
        progress_bar.progress(1.0)
        status_text.text("✅ 테스트 완료!")
        st.success("✅ 테스트 완료! 결과를 확인하세요.")
        st.rerun()
        
    except ConnectionError as e:
        st.error(f"❌ 네트워크 연결 실패:\n{str(e)}")
        st.info("💡 **해결 방법:**\n- VPN 연결 확인\n- 네트워크 설정 확인\n- 로컬 환경에서 실행 시도")
        st.session_state.test_in_progress = False
    except Exception as e:
        import traceback
        error_trace = traceback.format_exc()
        st.error(f"❌ 테스트 실행 중 오류 발생:\n{str(e)}")
        with st.expander("🔍 상세 오류 정보"):
            st.code(error_trace)
        st.session_state.test_in_progress = False

elif st.session_state.test_results is not None:
    results_df = st.session_state.test_results
    
    # 헤더 영역
    col_header1, col_header2 = st.columns([3, 1])
    with col_header1:
        st.header("📊 테스트 결과")
    with col_header2:
        # CSV 저장 시 필요한 컬럼만 필터링
        columns_to_save = [
            'test_case_id', 'turn_number', 'user_id', 'lat', 'lng', 'is_driving',
            'message', 'tts_expected', 'latency', 'tts_actual',
            'action_name', 'action_data', 'next_step'
        ]
        
        # 디버깅: 실제 존재하는 컬럼 확인
        import sys
        print(f"🔍 results_df 컬럼 목록: {list(results_df.columns)}", flush=True)
        print(f"🔍 필요한 컬럼 목록: {columns_to_save}", flush=True)
        sys.stdout.flush()
        
        # 존재하는 컬럼만 선택
        available_columns = [col for col in columns_to_save if col in results_df.columns]
        missing_columns = [col for col in columns_to_save if col not in results_df.columns]
        
        print(f"✅ 사용 가능한 컬럼: {available_columns}", flush=True)
        print(f"❌ 누락된 컬럼: {missing_columns}", flush=True)
        sys.stdout.flush()
        
        # 누락된 컬럼이 있으면 경고 표시
        if missing_columns:
            st.warning(f"⚠️ CSV에 누락된 컬럼: {missing_columns}")
        
        filtered_df = results_df[available_columns]
        
        csv = filtered_df.to_csv(index=False).encode('utf-8-sig')
        st.download_button(
            label="📥 CSV 다운로드",
            data=csv,
            file_name=f"evaluation_results_{time.strftime('%Y%m%d_%H%M%S')}.csv",
            mime="text/csv"
        )
    
    st.markdown("---")
    
    # 요약 통계
    total_cases = len(results_df)
    pass_count = len(results_df[results_df['pass/fail'] == 'PASS'])
    fail_count = len(results_df[results_df['pass/fail'] == 'FAIL'])
    pass_rate = (pass_count / total_cases * 100) if total_cases > 0 else 0
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("총 테스트 케이스", total_cases)
    with col2:
        st.metric("PASS", pass_count, delta=f"{pass_rate:.1f}%")
    with col3:
        st.metric("FAIL", fail_count, delta=f"{100-pass_rate:.1f}%")
    with col4:
        avg_similarity = results_df['similarity_score'].mean() if 'similarity_score' in results_df.columns else 0
        st.metric("평균 유사도", f"{avg_similarity:.2f}")
    
    st.markdown("---")
    
    # 필터 및 검색
    col_filter1, col_filter2, col_filter3 = st.columns([2, 1, 1])
    with col_filter1:
        search_query = st.text_input("🔍 검색", value=st.session_state.search_query, placeholder="user_id, message, tts_expected 등으로 검색...")
        st.session_state.search_query = search_query
    with col_filter2:
        pass_fail_filter = st.selectbox("필터", ["전체", "PASS", "FAIL"], key="pass_fail_filter")
    with col_filter3:
        # 멀티턴 시나리오인지 확인
        has_multi_turn = 'test_case_id' in results_df.columns and 'turn_number' in results_df.columns
        if has_multi_turn:
            scenario_filter = st.selectbox("시나리오", ["전체"] + sorted(results_df['test_case_id'].dropna().unique().tolist()), key="scenario_filter")
        else:
            scenario_filter = "전체"
    
    # 검색 및 필터 적용
    filtered_df = results_df.copy()
    if search_query:
        mask = (
            filtered_df['user_id'].astype(str).str.contains(search_query, case=False, na=False) |
            filtered_df['message'].astype(str).str.contains(search_query, case=False, na=False) |
            filtered_df['tts_expected'].astype(str).str.contains(search_query, case=False, na=False) |
            filtered_df.get('tts_actual', pd.Series()).astype(str).str.contains(search_query, case=False, na=False)
        )
        filtered_df = filtered_df[mask]
    
    if pass_fail_filter != "전체":
        filtered_df = filtered_df[filtered_df['pass/fail'] == pass_fail_filter]
    
    # 시나리오 필터 적용 (멀티턴 시나리오인 경우)
    if has_multi_turn and scenario_filter != "전체":
        filtered_df = filtered_df[filtered_df['test_case_id'] == scenario_filter]
    
    st.markdown(f"**검색 결과: {len(filtered_df)}개**")
    
    # 결과 테이블 (멀티턴 시나리오 지원)
    display_columns = ['test_case_id', 'turn_number', 'user_id', 'lng', 'lat', 'message', 'tts_expected', 'latency', 'tts_actual', 'similarity_score', 'pass/fail', 'fail_reason']
    # 빈 컬럼 제거
    available_columns = [col for col in display_columns if col in filtered_df.columns and filtered_df[col].notna().any()]
    
    st.dataframe(
        filtered_df[available_columns],
        use_container_width=True,
        height=600
    )
    
    st.markdown("---")
    
    # 상세 정보 (각 행 클릭 시)
    if len(filtered_df) > 0:
        st.markdown("### 📝 상세 정보")
        selected_index = st.selectbox("테스트 케이스 선택", range(len(filtered_df)), format_func=lambda x: f"케이스 {x+1}: {filtered_df.iloc[x]['message'][:50]}...")
        
        if selected_index is not None:
            original_row = filtered_df.iloc[selected_index]
            
            col_detail1, col_detail2 = st.columns(2)
            with col_detail1:
                st.markdown("**입력 정보**")
                st.json({
                    'user_id': str(original_row.get('user_id', '')),
                    'lat': original_row.get('lat', ''),
                    'lng': original_row.get('lng', ''),
                    'is_driving': original_row.get('is_driving', ''),
                    'message': original_row.get('message', ''),
                    'tts_expected': original_row.get('tts_expected', '')
                })
            with col_detail2:
                st.markdown("**결과 정보**")
                st.json({
                    'pass/fail': original_row.get('pass/fail', ''),
                    'similarity_score': original_row.get('similarity_score', ''),
                    'latency': original_row.get('latency', ''),
                    'fail_reason': original_row.get('fail_reason', '')
                })
            
            with st.expander("📝 TTS 비교", expanded=False):
                col_tts1, col_tts2 = st.columns(2)
                with col_tts1:
                    st.markdown("**기대값**")
                    st.text_area("", original_row.get('tts_expected', ''), height=100, key=f"expected_{selected_index}", disabled=True)
                with col_tts2:
                    st.markdown("**실제값**")
                    st.text_area("", original_row.get('tts_actual', ''), height=100, key=f"actual_{selected_index}", disabled=True)
            
            with st.expander("📊 Response (structured)", expanded=False):
                st.text_area("", original_row.get('response_structured', ''), height=150, key=f"response_{selected_index}", disabled=True)
            
            with st.expander("🔍 Raw JSON", expanded=False):
                st.text_area("", original_row.get('raw_json', ''), height=200, key=f"json_{selected_index}", disabled=True)

else:
    # 초기 화면
    st.markdown("""
    <div class="info-box">
        <h3>👈 시작하기</h3>
        <p>왼쪽 사이드바에서 엑셀 파일을 업로드하고 테스트를 실행하세요.</p>
    </div>
    """, unsafe_allow_html=True)
    
    st.markdown("### ⚠️ 주의사항")
    st.warning("""
    - 이 시스템은 **VPN 또는 사내망에서만 접근 가능**합니다.
    - 테스트는 **브라우저에서 직접 실행**되므로 Python 설치가 필요 없습니다.
    - 테스트 실행 시 새 브라우저 창이 열립니다. 팝업 차단을 해제해주세요.
    - 테스트 완료 후 결과 JSON 파일이 자동으로 다운로드됩니다.
    """)

