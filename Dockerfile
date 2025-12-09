# Python Streamlit 애플리케이션을 위한 프로덕션 Dockerfile
# k8s 배포 최적화 버전 - nginx 리버스 프록시 포함
# 프로젝트: navi-qa-cursor
FROM python:3.11-slim

# 메타데이터
LABEL maintainer="DevOps Team"
LABEL description="Navi QA 테스트 자동화 시스템 - Evaluation"

# 환경 변수 설정
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    STREAMLIT_SERVER_PORT=8501 \
    STREAMLIT_SERVER_ADDRESS=127.0.0.1 \
    STREAMLIT_BROWSER_GATHER_USAGE_STATS=false \
    STREAMLIT_SERVER_HEADLESS=true \
    PLAYWRIGHT_HEADLESS=true \
    CHROMIUM_PATH=/usr/bin/chromium \
    DEBIAN_FRONTEND=noninteractive

# 작업 디렉토리 설정 (프로젝트 이름: navi-qa-cursor)
WORKDIR /navi-qa-cursor

# 시스템 의존성 설치 (nginx, Playwright 및 기타 도구용)
# 캐시 최적화: 자주 변경되지 않는 시스템 패키지를 먼저 설치
RUN apt-get update && apt-get install -y --no-install-recommends \
    nginx \
    chromium \
    chromium-driver \
    curl \
    tzdata \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# nginx 디렉토리 미리 생성 (권한 문제 방지)
RUN mkdir -p /var/cache/nginx \
    && mkdir -p /var/log/nginx \
    && mkdir -p /var/run \
    && mkdir -p /run/nginx \
    && mkdir -p /etc/nginx/conf.d \
    && chmod -R 755 /var/cache/nginx \
    && chmod -R 755 /var/log/nginx \
    && chmod -R 755 /var/run \
    && chmod -R 755 /run/nginx

# 기본 nginx 설정 파일 제거 (충돌 방지)
RUN rm -f /etc/nginx/conf.d/default.conf

# nginx 설정 파일 복사
COPY nginx.conf /etc/nginx/nginx.conf

# Python 의존성 파일 복사 (캐시 최적화: 의존성 파일을 먼저 복사)
COPY requirements.txt /navi-qa-cursor/

# Python 패키지 설치 (캐시 최적화: 의존성이 변경되지 않으면 이 레이어 재사용)
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt && \
    pip install --no-cache-dir watchdog

# Playwright 브라우저 설치 (시스템 chromium 사용하므로 스킵 가능하지만 설치 시도)
# || true로 실패해도 계속 진행
RUN playwright install chromium || true

# 리소스 체크 스크립트 복사 (애플리케이션 파일보다 먼저 복사하여 캐시 최적화)
COPY check_resources.sh /navi-qa-cursor/
RUN chmod +x /navi-qa-cursor/check_resources.sh

# 애플리케이션 파일 복사 (가장 자주 변경되는 파일을 마지막에 복사)
COPY app.py /navi-qa-cursor/
COPY test_automation.py /navi-qa-cursor/
COPY similarity.py /navi-qa-cursor/
COPY health_check.py /navi-qa-cursor/
COPY static/ /navi-qa-cursor/static/

# 필요한 디렉토리 생성 및 권한 설정
# k8s read-only 파일시스템 호환을 위해 모든 필요한 디렉토리 미리 생성
RUN mkdir -p /tmp/streamlit && \
    mkdir -p /root/.cache/streamlit && \
    mkdir -p /root/.cache/ms-playwright && \
    chmod -R 777 /navi-qa-cursor && \
    chmod -R 777 /tmp/streamlit && \
    chmod -R 777 /root/.cache

# nginx 설정 테스트
RUN nginx -t

# 포트 노출 (nginx가 8080에서 실행)
EXPOSE 8080

# 헬스체크 (nginx를 통해 /health 엔드포인트 확인)
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8080/health || exit 1

# 시작 스크립트: 리소스 체크 → Streamlit 백그라운드 실행 → nginx 포그라운드 실행
CMD ["sh", "-c", "/navi-qa-cursor/check_resources.sh && streamlit run app.py --server.port=8501 --server.address=127.0.0.1 --server.headless=true --server.enableCORS=false --server.enableXsrfProtection=false & nginx -g 'daemon off;'"]
