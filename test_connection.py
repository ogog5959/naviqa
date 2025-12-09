#!/usr/bin/env python3
"""
네트워크 연결 테스트 스크립트
테스트 대상 서버에 접근 가능한지 확인합니다.
"""
import requests
import sys
from urllib.parse import urlparse

def test_connection(base_url):
    """서버 연결 테스트"""
    print(f"🔍 연결 테스트 시작: {base_url}")
    print("-" * 60)
    
    try:
        # URL 파싱
        parsed = urlparse(base_url)
        hostname = parsed.hostname
        
        print(f"📡 호스트명: {hostname}")
        print(f"🔗 전체 URL: {base_url}")
        print()
        
        # DNS 해석 테스트
        import socket
        try:
            ip = socket.gethostbyname(hostname)
            print(f"✅ DNS 해석 성공: {hostname} -> {ip}")
        except socket.gaierror as e:
            print(f"❌ DNS 해석 실패: {e}")
            print()
            print("💡 해결 방법:")
            print("   1. VPN 연결 확인")
            print("   2. 네트워크 설정 확인")
            print("   3. hosts 파일에 IP 추가 (임시 해결책)")
            return False
        
        print()
        
        # HTTP 연결 테스트
        print("🌐 HTTP 연결 테스트 중...")
        try:
            response = requests.get(base_url, timeout=10, verify=False)
            print(f"✅ HTTP 연결 성공!")
            print(f"   상태 코드: {response.status_code}")
            print(f"   응답 크기: {len(response.content)} bytes")
            return True
        except requests.exceptions.Timeout:
            print(f"❌ 연결 타임아웃 (10초 초과)")
            print()
            print("💡 해결 방법:")
            print("   1. VPN 연결 확인")
            print("   2. 방화벽 설정 확인")
            print("   3. 네트워크 관리자에게 문의")
            return False
        except requests.exceptions.ConnectionError as e:
            print(f"❌ 연결 실패: {e}")
            print()
            print("💡 해결 방법:")
            print("   1. VPN 연결 확인")
            print("   2. 프록시 설정 확인 (필요시)")
            print("   3. 네트워크 관리자에게 문의")
            return False
        except Exception as e:
            print(f"❌ 오류 발생: {e}")
            return False
            
    except Exception as e:
        print(f"❌ 테스트 중 오류: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_with_proxy(base_url, proxy_url=None):
    """프록시를 사용한 연결 테스트"""
    if not proxy_url:
        # 환경 변수에서 프록시 확인
        import os
        proxy_url = os.environ.get('HTTP_PROXY') or os.environ.get('HTTPS_PROXY')
    
    if proxy_url:
        print(f"🔧 프록시 사용: {proxy_url}")
        proxies = {
            'http': proxy_url,
            'https': proxy_url
        }
        try:
            response = requests.get(base_url, proxies=proxies, timeout=10, verify=False)
            print(f"✅ 프록시를 통한 연결 성공!")
            print(f"   상태 코드: {response.status_code}")
            return True
        except Exception as e:
            print(f"❌ 프록시 연결 실패: {e}")
            return False
    else:
        print("ℹ️  프록시 설정 없음")
        return False

if __name__ == "__main__":
    # 기본 URL
    base_url = "https://navi-agent-adk-api.dev.onkakao.net/streamlit/"
    
    # 명령줄 인자로 URL 지정 가능
    if len(sys.argv) > 1:
        base_url = sys.argv[1]
    
    print("=" * 60)
    print("🔍 네트워크 연결 테스트")
    print("=" * 60)
    print()
    
    # 일반 연결 테스트
    success = test_connection(base_url)
    
    if not success:
        print()
        print("-" * 60)
        print("🔧 프록시를 사용한 연결 테스트 시도...")
        print("-" * 60)
        test_with_proxy(base_url)
    
    print()
    print("=" * 60)
    if success:
        print("✅ 연결 테스트 완료 - 서버에 접근 가능합니다!")
    else:
        print("❌ 연결 테스트 실패 - 서버에 접근할 수 없습니다.")
    print("=" * 60)
