"""
헬스체크 엔드포인트
Streamlit 앱과 함께 실행되어 /health 엔드포인트를 제공합니다.
"""
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading
import os


class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/health':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(b'{"status": "healthy"}')
        else:
            self.send_response(404)
            self.end_headers()
    
    def log_message(self, format, *args):
        # 헬스체크 로그는 출력하지 않음
        pass


def run_health_server(port=8081):
    """헬스체크 서버를 별도 포트에서 실행"""
    try:
        server = HTTPServer(('0.0.0.0', port), HealthCheckHandler)
        server.serve_forever()
    except OSError:
        # 포트가 이미 사용 중이면 무시 (Streamlit이 같은 포트 사용)
        pass


def start_health_check():
    """백그라운드 스레드에서 헬스체크 서버 시작"""
    thread = threading.Thread(target=run_health_server, daemon=True)
    thread.start()


if __name__ == '__main__':
    # 직접 실행 시 헬스체크 서버 시작
    port = int(os.environ.get('HEALTH_CHECK_PORT', '8081'))
    run_health_server(port)



