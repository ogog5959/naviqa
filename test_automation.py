"""
Playwright 기반 테스트 자동화 모듈
웹 UI에 접속하여 테스트를 수행하고 결과를 수집합니다.
"""
import time
import pandas as pd
from playwright.sync_api import sync_playwright, Page, TimeoutError as PlaywrightTimeoutError
from typing import Dict, Optional
from similarity import calculate_similarity, determine_pass_fail


class TestAutomation:
    """웹 UI 테스트 자동화 클래스"""
    
    def __init__(self, base_url: str = "https://navi-agent-adk-api.dev.onkakao.net/streamlit/"):
        """
        Args:
            base_url: 테스트 대상 웹 UI URL
        """
        self.base_url = base_url
        self.page: Optional[Page] = None
        self.playwright = None
        self.browser = None
        self.context = None
    
    def start_browser(self):
        """브라우저 시작"""
        import os
        print("🚀 브라우저 시작 중...")
        
        try:
            self.playwright = sync_playwright().start()
            print("✅ Playwright 시작 완료")
        except Exception as e:
            print(f"❌ Playwright 시작 실패: {e}")
            raise
        
        # 프로덕션 환경에서는 headless=True, 로컬 개발 환경에서는 headless=False
        chromium_path = os.environ.get('CHROMIUM_PATH', '/usr/bin/chromium')
        # 환경 변수가 명시적으로 설정되지 않았으면 False (로컬 개발)
        headless_env = os.environ.get('PLAYWRIGHT_HEADLESS', 'false')
        headless_mode = headless_env.lower() == 'true'
        
        # 프록시 설정 (사외망에서 사내망 접근용)
        proxy_config = None
        http_proxy = os.environ.get('HTTP_PROXY') or os.environ.get('http_proxy')
        https_proxy = os.environ.get('HTTPS_PROXY') or os.environ.get('https_proxy')
        
        if http_proxy or https_proxy:
            proxy_config = {
                'server': http_proxy or https_proxy,
            }
            # 프록시 인증 정보가 있으면 추가
            proxy_user = os.environ.get('PROXY_USER')
            proxy_pass = os.environ.get('PROXY_PASS')
            if proxy_user and proxy_pass:
                proxy_config['username'] = proxy_user
                proxy_config['password'] = proxy_pass
            
            print(f"🔧 프록시 설정: {proxy_config['server']}")
        
        print(f"🔧 브라우저 설정: headless={headless_mode}, chromium_path={chromium_path}")
        
        # 시스템 chromium이 있으면 사용, 없으면 Playwright 기본 브라우저 사용
        # 메모리 최적화를 위한 옵션 추가
        launch_options = {
            'headless': headless_mode,
            'slow_mo': 100,  # 디버깅을 위해 동작을 천천히
            'args': [
                '--no-sandbox',
                '--disable-setuid-sandbox',
                '--disable-dev-shm-usage',  # 메모리 최적화
                '--disable-gpu',
                '--disable-software-rasterizer',
                '--disable-extensions',
                '--disable-background-networking',
                '--disable-background-timer-throttling',
                '--disable-renderer-backgrounding',
                '--disable-backgrounding-occluded-windows',
                '--disable-ipc-flooding-protection',
                '--memory-pressure-off',  # 메모리 압력 감지 비활성화
                '--max_old_space_size=128',  # V8 메모리 제한
            ]
        }
        
        # 시스템 chromium 경로 확인 (여러 경로 시도)
        chromium_paths = [
            chromium_path,
            '/usr/bin/chromium',
            '/usr/bin/chromium-browser',
            '/usr/bin/google-chrome',
            '/usr/bin/google-chrome-stable'
        ]
        
        found_chromium = None
        for path in chromium_paths:
            if os.path.exists(path):
                found_chromium = path
                break
        
        if found_chromium:
            launch_options['executable_path'] = found_chromium
            print(f"✅ 시스템 Chromium 사용: {found_chromium}")
        else:
            print(f"⚠️ 시스템 Chromium 없음, Playwright 기본 브라우저 사용")
        
        try:
            self.browser = self.playwright.chromium.launch(**launch_options)
            print("✅ 브라우저 실행 완료")
        except Exception as e:
            print(f"❌ 브라우저 실행 실패: {e}")
            raise
        
        try:
            # 메모리 최적화를 위한 컨텍스트 옵션 (256MB 제한 환경 대응)
            context_options = {
                'viewport': {'width': 1280, 'height': 720},  # 작은 뷰포트로 메모리 절약
                'ignore_https_errors': True,
                'java_script_enabled': True,
                'bypass_csp': True,
            }
            
            # 프록시 설정이 있으면 컨텍스트에 추가
            if proxy_config:
                context_options['proxy'] = proxy_config
            self.context = self.browser.new_context(**context_options)
            # 클립보드 복사 감지를 위한 초기 스크립트 주입
            try:
                self.context.add_init_script(
                    """
                    (() => {
                        try {
                            window.__NAVIQA_COPIES__ = [];
                            const origWriteText = navigator.clipboard.writeText.bind(navigator.clipboard);
                            navigator.clipboard.writeText = async (text) => {
                                try {
                                    window.__NAVIQA_COPIES__.push(text);
                                } catch (e) {
                                    // ignore
                                }
                                try {
                                    return await origWriteText(text);
                                } catch (e) {
                                    // 원래 clipboard 동작 실패해도 테스트는 계속
                                    return;
                                }
                            };
                        } catch (e) {
                            // 브라우저 환경에 따라 navigator.clipboard가 없을 수 있음
                        }
                    })();
                    """
                )
                print("✅ 클립보드 감지 스크립트 주입 완료")
            except Exception as e:
                print(f"⚠️ 클립보드 감지 스크립트 주입 실패 (계속 진행): {e}")
            self.page = self.context.new_page()
            print(f"🌐 페이지 접속 중: {self.base_url}")
            
            # 네트워크 연결 확인 (DNS 해석 실패 시 명확한 에러 메시지)
            try:
                print(f"🌐 페이지 접속 시도: {self.base_url}")
                print(f"   프록시 설정: {proxy_config['server'] if proxy_config else '없음'}")
                
                self.page.goto(self.base_url, timeout=60000)  # 타임아웃 60초로 증가
                self.page.wait_for_load_state("networkidle", timeout=60000)
                time.sleep(1)
                print("✅ 페이지 로드 완료")
            except Exception as goto_error:
                error_msg = str(goto_error)
                error_type = type(goto_error).__name__
                
                # 더 자세한 에러 분석
                if "ERR_NAME_NOT_RESOLVED" in error_msg or "net::ERR_NAME_NOT_RESOLVED" in error_msg:
                    detailed_error = (
                        f"❌ 네트워크 연결 실패: DNS 해석 불가\n"
                        f"   URL: {self.base_url}\n"
                        f"   에러 타입: {error_type}\n"
                        f"   원인: 서버가 VPN 또는 사내망에 연결되어 있지 않거나 DNS 설정이 없습니다.\n"
                        f"   해결 방법:\n"
                        f"   1. 배포 환경이 VPN에 연결되어 있는지 확인\n"
                        f"   2. 사내망 접근 권한이 있는지 확인\n"
                        f"   3. DNS 설정 확인 (hosts 파일 또는 DNS 서버)\n"
                        f"   4. 네트워크 관리자에게 문의\n"
                        f"   원본 에러: {error_msg}"
                    )
                    print(detailed_error)
                    raise ConnectionError(detailed_error) from goto_error
                elif "timeout" in error_msg.lower() or "Timeout" in error_msg:
                    detailed_error = (
                        f"❌ 네트워크 연결 실패: 타임아웃\n"
                        f"   URL: {self.base_url}\n"
                        f"   에러 타입: {error_type}\n"
                        f"   원인: 서버에 연결할 수 없거나 응답이 너무 느립니다.\n"
                        f"   해결 방법:\n"
                        f"   1. VPN 연결 상태 확인\n"
                        f"   2. 방화벽 설정 확인\n"
                        f"   3. 네트워크 관리자에게 문의\n"
                        f"   원본 에러: {error_msg}"
                    )
                    print(detailed_error)
                    raise ConnectionError(detailed_error) from goto_error
                elif "ERR_CONNECTION_REFUSED" in error_msg or "net::ERR_CONNECTION_REFUSED" in error_msg:
                    detailed_error = (
                        f"❌ 네트워크 연결 실패: 연결 거부\n"
                        f"   URL: {self.base_url}\n"
                        f"   에러 타입: {error_type}\n"
                        f"   원인: 서버가 연결을 거부했습니다.\n"
                        f"   해결 방법:\n"
                        f"   1. URL이 올바른지 확인\n"
                        f"   2. 서버가 실행 중인지 확인\n"
                        f"   3. 방화벽 설정 확인\n"
                        f"   원본 에러: {error_msg}"
                    )
                    print(detailed_error)
                    raise ConnectionError(detailed_error) from goto_error
                else:
                    detailed_error = (
                        f"❌ 페이지 로드 실패\n"
                        f"   URL: {self.base_url}\n"
                        f"   에러 타입: {error_type}\n"
                        f"   원본 에러: {error_msg}\n"
                        f"   해결 방법:\n"
                        f"   1. VPN 연결 확인\n"
                        f"   2. 네트워크 연결 확인\n"
                        f"   3. 서버 상태 확인"
                    )
                    print(detailed_error)
                    raise ConnectionError(detailed_error) from goto_error
        except ConnectionError:
            # ConnectionError는 그대로 전파
            raise
        except Exception as e:
            print(f"❌ 브라우저 컨텍스트 생성 실패: {e}")
            raise
    
    def close_browser(self):
        """브라우저 종료"""
        if self.browser:
            self.browser.close()
        if self.playwright:
            self.playwright.stop()
    
    def fill_input(self, label: str, value: str):
        """
        aria-label을 사용하여 입력 필드에 값을 입력합니다.
        
        Args:
            label: aria-label 값
            value: 입력할 값
        """
        try:
            input_locator = self.page.locator(f'input[aria-label="{label}"]')
            input_locator.wait_for(state="visible", timeout=5000)
            input_locator.fill(str(value))
        except Exception as e:
            print(f"입력 필드 '{label}' 채우기 실패: {e}")
    
    def toggle_checkbox(self, label: str, target_value: bool):
        """
        여러 방법으로 체크박스를 찾아 토글합니다.
        
        Args:
            label: 체크박스 레이블 (aria-label, name, 또는 주변 텍스트)
            target_value: 체크 여부
        """
        try:
            print(f"  🔍 체크박스 찾기: '{label}', 목표값: {target_value}")
            checkbox = None
            
            # 방법 1: aria-label로 찾기
            checkbox_locator = self.page.locator(f'input[aria-label="{label}"][type="checkbox"]')
            if checkbox_locator.count() > 0:
                checkbox = checkbox_locator.first
                print(f"  ✅ 체크박스 찾음 (aria-label): {label}")
            
            # 방법 2: name 속성으로 찾기
            if not checkbox or checkbox_locator.count() == 0:
                checkbox_locator = self.page.locator(f'input[name="{label}"][type="checkbox"]')
                if checkbox_locator.count() > 0:
                    checkbox = checkbox_locator.first
                    print(f"  ✅ 체크박스 찾음 (name): {label}")
            
            # 방법 3: label 텍스트로 찾기
            if not checkbox or checkbox_locator.count() == 0:
                # label 요소에서 찾기
                labels = self.page.locator('label')
                for i in range(labels.count()):
                    label_element = labels.nth(i)
                    label_text = label_element.inner_text().lower()
                    if label.lower() in label_text or label.replace('_', ' ').lower() in label_text:
                        # label의 for 속성으로 input 찾기
                        for_id = label_element.get_attribute('for')
                        if for_id:
                            checkbox_locator = self.page.locator(f'input#{for_id}[type="checkbox"]')
                            if checkbox_locator.count() > 0:
                                checkbox = checkbox_locator.first
                                print(f"  ✅ 체크박스 찾음 (label for): {label}")
                                break
                        
                        # label 부모 요소에서 체크박스 찾기
                        if not checkbox or checkbox_locator.count() == 0:
                            parent = label_element.locator('..')
                            checkbox_locator = parent.locator('input[type="checkbox"]')
                            if checkbox_locator.count() > 0:
                                checkbox = checkbox_locator.first
                                print(f"  ✅ 체크박스 찾음 (label parent): {label}")
                                break
            
            # 방법 4: 모든 체크박스를 순회하며 주변 텍스트로 찾기
            if not checkbox or checkbox_locator.count() == 0:
                all_checkboxes = self.page.locator('input[type="checkbox"]')
                for i in range(all_checkboxes.count()):
                    cb = all_checkboxes.nth(i)
                    # 체크박스 주변 텍스트 확인
                    try:
                        # 부모 요소에서 텍스트 확인
                        parent = cb.locator('..')
                        parent_text = parent.inner_text().lower()
                        if label.lower() in parent_text or label.replace('_', ' ').lower() in parent_text:
                            checkbox = cb
                            print(f"  ✅ 체크박스 찾음 (주변 텍스트): {label}")
                            break
                    except:
                        continue
            
            if not checkbox or checkbox_locator.count() == 0:
                # 디버깅: 모든 체크박스 정보 출력
                all_checkboxes = self.page.locator('input[type="checkbox"]')
                print(f"  ⚠️ 체크박스를 찾을 수 없습니다: {label}")
                print(f"  📋 페이지의 체크박스 개수: {all_checkboxes.count()}")
                for i in range(min(all_checkboxes.count(), 5)):  # 최대 5개만 출력
                    try:
                        cb = all_checkboxes.nth(i)
                        aria_label = cb.get_attribute('aria-label') or 'N/A'
                        name = cb.get_attribute('name') or 'N/A'
                        parent_text = cb.locator('..').inner_text()[:50] or 'N/A'
                        print(f"    체크박스 {i+1}: aria-label='{aria_label}', name='{name}', 주변텍스트='{parent_text}'")
                    except:
                        pass
                raise Exception(f"체크박스를 찾을 수 없습니다: {label}")
            
            # 체크박스 상태 확인 및 토글
            # Streamlit 체크박스는 React로 관리되므로 특별한 처리가 필요
            try:
                current_checked = checkbox.is_checked()
                print(f"  📊 현재 체크 상태: {current_checked}, 목표 상태: {target_value}")
                
                if current_checked != target_value:
                    # 방법 1: 체크박스를 뷰포트로 스크롤하여 보이게 만들기
                    print(f"  🔧 체크박스를 뷰포트로 스크롤 시도...")
                    try:
                        # 여러 방법으로 스크롤 시도
                        # 방법 1-1: scroll_into_view_if_needed
                        checkbox.scroll_into_view_if_needed()
                        time.sleep(0.3)
                        
                        # 방법 1-2: JavaScript로 직접 스크롤
                        checkbox.evaluate("""
                            (element) => {
                                // 요소의 위치 계산
                                const rect = element.getBoundingClientRect();
                                const elementTop = rect.top + window.pageYOffset;
                                const elementCenter = elementTop + (rect.height / 2);
                                
                                // 뷰포트 중앙으로 스크롤
                                const viewportHeight = window.innerHeight;
                                const scrollTo = elementCenter - (viewportHeight / 2);
                                
                                window.scrollTo({
                                    top: scrollTo,
                                    behavior: 'smooth'
                                });
                                
                                // 부모 요소들도 스크롤
                                let parent = element.parentElement;
                                while (parent && parent !== document.body) {
                                    if (parent.scrollIntoView) {
                                        parent.scrollIntoView({ behavior: 'smooth', block: 'center' });
                                    }
                                    parent = parent.parentElement;
                                }
                            }
                        """)
                        time.sleep(0.5)  # 스크롤 완료 대기
                        
                        # 방법 1-3: 페이지 전체를 스크롤하면서 체크박스 찾기
                        # 체크박스가 여전히 보이지 않으면 페이지를 위에서 아래로 스크롤
                        for scroll_attempt in range(3):
                            is_visible = checkbox.is_visible(timeout=1000)
                            if is_visible:
                                print(f"  ✅ 체크박스가 보입니다 (시도 {scroll_attempt + 1})")
                                break
                            
                            # 페이지를 조금씩 스크롤
                            self.page.evaluate(f"""
                                () => {{
                                    window.scrollBy(0, {300 * (scroll_attempt + 1)});
                                }}
                            """)
                            time.sleep(0.3)
                        
                        # 체크박스를 다시 찾기 (스크롤 후 DOM이 변경되었을 수 있음)
                        checkbox = self.page.locator(f'input[aria-label="{label}"][type="checkbox"]').first
                        
                    except Exception as scroll_error:
                        print(f"  ⚠️ 스크롤 중 오류 (계속 진행): {scroll_error}")
                    
                    # 방법 2: 체크박스를 보이게 만들고 실제 checked 속성 변경
                    print(f"  🔧 JavaScript로 체크박스 강제 설정 시도...")
                    checkbox.evaluate(f"""
                        (element) => {{
                            // 1. 체크박스를 강제로 보이게 만들기
                            element.style.display = 'block';
                            element.style.visibility = 'visible';
                            element.style.opacity = '1';
                            element.style.position = 'static';
                            element.style.height = 'auto';
                            element.style.width = 'auto';
                            
                            // 2. 부모 요소들도 보이게 만들기
                            let parent = element.parentElement;
                            let depth = 0;
                            while (parent && depth < 10) {{
                                parent.style.display = 'block';
                                parent.style.visibility = 'visible';
                                parent.style.opacity = '1';
                                parent.style.overflow = 'visible';
                                parent = parent.parentElement;
                                depth++;
                            }}
                            
                            // 3. 실제 checked 속성 변경 (가장 중요!)
                            // Object.defineProperty를 사용하여 React가 감지하도록
                            const descriptor = Object.getOwnPropertyDescriptor(
                                HTMLInputElement.prototype, 
                                'checked'
                            );
                            
                            // 기존 setter를 사용하여 변경
                            if (descriptor && descriptor.set) {{
                                descriptor.set.call(element, {str(target_value).lower()});
                            }} else {{
                                element.checked = {str(target_value).lower()};
                            }}
                            
                            // 4. aria-checked 속성도 업데이트
                            element.setAttribute('aria-checked', {str(target_value).lower()});
                            
                            // 5. value 속성도 설정
                            if ({str(target_value).lower()}) {{
                                element.setAttribute('value', 'true');
                                element.value = 'true';
                            }} else {{
                                element.removeAttribute('value');
                                element.value = '';
                            }}
                            
                            // 6. 모든 관련 이벤트 발생 (순서 중요!)
                            // input 이벤트
                            const inputEvent = new Event('input', {{
                                bubbles: true,
                                cancelable: true
                            }});
                            element.dispatchEvent(inputEvent);
                            
                            // change 이벤트
                            const changeEvent = new Event('change', {{
                                bubbles: true,
                                cancelable: true
                            }});
                            element.dispatchEvent(changeEvent);
                            
                            // click 이벤트
                            const clickEvent = new MouseEvent('click', {{
                                bubbles: true,
                                cancelable: true,
                                view: window,
                                button: 0,
                                buttons: 1
                            }});
                            element.dispatchEvent(clickEvent);
                            
                            // focus 이벤트
                            element.focus();
                            const focusEvent = new Event('focus', {{
                                bubbles: true
                            }});
                            element.dispatchEvent(focusEvent);
                            
                            // blur 이벤트
                            element.blur();
                            const blurEvent = new Event('blur', {{
                                bubbles: true
                            }});
                            element.dispatchEvent(blurEvent);
                            
                            // 7. Streamlit이 사용하는 커스텀 이벤트
                            try {{
                                const streamlitEvent = new CustomEvent('streamlit:setComponentValue', {{
                                    detail: {{ value: {str(target_value).lower()} }},
                                    bubbles: true,
                                    cancelable: true
                                }});
                                element.dispatchEvent(streamlitEvent);
                            }} catch (e) {{
                                // 커스텀 이벤트가 지원되지 않는 경우 무시
                            }}
                        }}
                    """)
                    time.sleep(0.5)
                    
                    # 방법 3: 실제 클릭도 시도 (보이는 경우)
                    try:
                        # 체크박스가 이제 보이는지 확인하고 클릭
                        is_visible = checkbox.is_visible(timeout=2000)
                        if is_visible:
                            print(f"  🔧 체크박스가 보이므로 실제 클릭 시도...")
                            checkbox.click(force=False)  # 실제 클릭
                            time.sleep(0.3)
                            print(f"  ✅ 실제 클릭 완료")
                        else:
                            print(f"  🔧 체크박스가 보이지 않으므로 Force 클릭 시도...")
                            checkbox.click(force=True)  # 강제 클릭
                            time.sleep(0.3)
                            print(f"  ✅ Force 클릭 완료")
                    except Exception as click_error:
                        print(f"  ℹ️ 실제 클릭은 스킵 (이미 JavaScript로 설정됨): {click_error}")
                    
                    # 최종 확인
                    time.sleep(0.3)
                    final_checked = checkbox.is_checked()
                    final_aria_checked = checkbox.get_attribute('aria-checked')
                    print(f"  📊 최종 체크 상태: checked={final_checked}, aria-checked={final_aria_checked}, 목표: {target_value}")
                    
                    if final_checked == target_value:
                        print(f"  ✅ 체크박스 토글 성공: {target_value}")
                    else:
                        print(f"  ⚠️ 체크박스 상태가 여전히 불일치: 예상={target_value}, 실제={final_checked}")
                        # 최후의 수단: force 클릭
                        try:
                            print(f"  🔧 Force 클릭으로 최종 시도...")
                            checkbox.click(force=True)
                            time.sleep(0.5)
                            final_checked3 = checkbox.is_checked()
                            if final_checked3 == target_value:
                                print(f"  ✅ Force 클릭 후 성공: {target_value}")
                            else:
                                print(f"  ❌ 모든 방법 실패: 예상={target_value}, 실제={final_checked3}")
                        except Exception as e:
                            print(f"  ❌ Force 클릭도 실패: {e}")
                else:
                    print(f"  ℹ️ 체크박스가 이미 목표 상태입니다: {target_value}")
            except Exception as e:
                print(f"  ❌ 체크박스 토글 중 오류: {e}")
                import traceback
                traceback.print_exc()
                
        except Exception as e:
            print(f"  ❌ 체크박스 '{label}' 토글 실패: {e}")
            import traceback
            traceback.print_exc()
    
    def initialize_chat(self, user_id: str, lat: float, lng: float, is_driving: bool):
        """
        최초 1회 채팅 초기화 (Request Fields 입력 및 save & start chat 클릭)
        
        Args:
            user_id: 사용자 ID
            lat: 위도
            lng: 경도
            is_driving: 운전 여부
        """
        try:
            # aria-label을 사용하여 입력 필드 채우기
            self.fill_input('user_id', user_id)
            time.sleep(0.3)
            
            self.fill_input('lat', lat)
            time.sleep(0.3)
            
            self.fill_input('lng', lng)
            time.sleep(0.3)
            
            # is_driving 체크박스 토글
            self.toggle_checkbox('is_driving', is_driving)
            time.sleep(0.3)
            
            # "Save & Start Chat" 버튼 클릭
            save_button = self.page.locator('button:has-text("Save & Start Chat")')
            if save_button.count() > 0:
                save_button.click()
                time.sleep(1.5)  # 채팅 초기화 대기
            
        except Exception as e:
            print(f"채팅 초기화 중 오류 발생: {e}")
            # 오류가 발생해도 계속 진행
    
    def extract_expander_content(self, title_text: str) -> str:
        """
        Expander에서 내용을 추출합니다.
        Node.js 코드의 extractExpanderContent 함수를 Python으로 변환한 버전입니다.
        
        Args:
            title_text: Expander의 제목 텍스트
        
        Returns:
            추출된 내용
        """
        try:
            # 1) expander 블록 찾기 (titleText를 포함한 expander) - XPath 사용
            expander_xpath = f'xpath=//div[@data-testid="stExpander" and contains(., "{title_text}")]'
            expander = self.page.locator(expander_xpath)
            
            if expander.count() == 0:
                return ''
            
            # 2) 만약 접혀있다면 아이콘 클릭
            try:
                icon_locator = expander.locator('xpath=.//span[@data-testid="stIconMaterial"]')
                if icon_locator.count() > 0:
                    icon_text = icon_locator.first.inner_text().strip()
                    if icon_text == 'keyboard_arrow_right':
                        icon_locator.first.click()
                        time.sleep(0.5)  # 렌더 대기
            except Exception:
                pass
            
            # 3) 내용 추출 우선순위
            
            # a) code block
            try:
                code_block = expander.locator('xpath=.//pre//code')
                if code_block.count() > 0:
                    code_block.first.wait_for(state="visible", timeout=5000)
                    txt = code_block.first.inner_text()
                    if txt and txt.strip():
                        return txt
            except Exception:
                pass
            
            # b) react-json-view (stJson)
            try:
                react_json = expander.locator('xpath=.//div[contains(@class,"react-json-view")]')
                if react_json.count() > 0:
                    react_json.first.wait_for(state="visible", timeout=5000)
                    txt = react_json.first.inner_text()
                    if txt and txt.strip():
                        return txt
            except Exception:
                pass
            
            # c) markdown container
            try:
                md = expander.locator('xpath=.//div[contains(@data-testid,"stMarkdownContainer")]')
                if md.count() > 0:
                    md.first.wait_for(state="visible", timeout=5000)
                    txt = md.first.inner_text()
                    if txt and txt.strip():
                        return txt
            except Exception:
                pass
            
            # d) expander 상세 영역 전체
            try:
                details = expander.locator('xpath=.//div[@data-testid="stExpanderDetails"]')
                if details.count() > 0:
                    details.first.wait_for(state="visible", timeout=5000)
                    txt = details.first.inner_text()
                    if txt and txt.strip():
                        return txt
            except Exception:
                pass
            
            return ''
        
        except Exception as e:
            print(f"Expander 내용 추출 중 오류 ({title_text}): {e}")
            return ''
    
    def extract_latency(self) -> str:
        """
        latency를 추출합니다.
        
        Returns:
            latency 문자열 (예: "Response received in 123ms")
        """
        try:
            # "Response received" 텍스트가 포함된 마크다운 컨테이너 찾기
            latency_locator = self.page.locator('div[data-testid="stMarkdownContainer"]:has-text("Response received")')
            if latency_locator.count() > 0:
                return latency_locator.first.inner_text()
        except Exception:
            pass
        
        try:
            # 대체: 숫자와 "ms"가 포함된 텍스트 찾기
            any_ms = self.page.locator('text=/\\d+\\s*ms/')
            if any_ms.count() > 0:
                return any_ms.first.inner_text()
        except Exception:
            pass
        
        return ''
    
    def extract_tts_from_raw_json(self, raw_json: str) -> str:
        """
        Raw JSON에서 TTS 필드를 추출합니다.
        
        Args:
            raw_json: Raw JSON 문자열
        
        Returns:
            TTS 출력 텍스트
        """
        if not raw_json or not raw_json.strip():
            return ''
        
        try:
            import json
            import re
            
            # 방법 1: 정규식으로 "tts" 필드 추출 (문자열 값)
            tts_match = re.search(r'"tts"\s*:\s*"([^"]+)"', raw_json, re.IGNORECASE)
            if tts_match:
                return tts_match.group(1)
            
            # 방법 2: JSON 파싱 시도
            try:
                # JSON 문자열 정리 (앞뒤 공백 제거)
                json_str = raw_json.strip()
                
                # JSON 파싱
                if json_str.startswith('{') or json_str.startswith('['):
                    json_data = json.loads(json_str)
                    
                    # 재귀적으로 tts 필드 찾기
                    def find_tts(obj):
                        if isinstance(obj, dict):
                            # 직접 tts 키 확인
                            if 'tts' in obj:
                                return str(obj['tts'])
                            if 'TTS' in obj:
                                return str(obj['TTS'])
                            # 중첩된 객체에서 재귀적으로 찾기
                            for value in obj.values():
                                result = find_tts(value)
                                if result:
                                    return result
                        elif isinstance(obj, list):
                            for item in obj:
                                result = find_tts(item)
                                if result:
                                    return result
                        return None
                    
                    tts_value = find_tts(json_data)
                    if tts_value:
                        return tts_value
            except (json.JSONDecodeError, ValueError) as e:
                # JSON 파싱 실패 시 정규식으로 재시도
                pass
            
            # 방법 3: 더 유연한 정규식 (이스케이프된 따옴표 처리)
            tts_match = re.search(r'"tts"\s*:\s*"((?:[^"\\]|\\.)*)"', raw_json, re.IGNORECASE)
            if tts_match:
                # 이스케이프 문자 처리
                tts_value = tts_match.group(1).replace('\\"', '"').replace('\\n', '\n').replace('\\t', '\t')
                return tts_value
            
        except Exception as e:
            print(f"Raw JSON에서 TTS 추출 중 오류: {e}")
        
        return ''
    
    def extract_action_fields_from_raw_json(self, raw_json: str) -> tuple:
        """
        Raw JSON에서 action_name, action_data, next_step 필드를 추출합니다.
        react-json-view 형식도 처리합니다.
        
        Args:
            raw_json: Raw JSON 문자열 (일반 JSON 또는 react-json-view 형식)
        
        Returns:
            (action_name, action_data, next_step) 튜플
        """
        action_name = ''
        action_data = ''
        next_step = ''
        
        if not raw_json or not raw_json.strip():
            return (action_name, action_data, next_step)
        
        try:
            import json
            import re
            import sys
            
            # 디버깅: 입력된 raw_json 형식 확인
            print(f"  🔍 extract_action_fields_from_raw_json 입력: 길이={len(raw_json)}, 처음 300자=\n{raw_json[:300]}", flush=True)
            
            # JSON 문자열 정리 (앞뒤 공백 제거)
            json_str = raw_json.strip()
            
            # react-json-view 형식인지 확인 (예: "0:{" 패턴)
            if re.search(r'\d+:\{', json_str):
                # react-json-view 형식을 정규 JSON으로 변환
                # "0:{" -> "{" (배열 인덱스 제거)
                json_str = re.sub(r'\d+:\{', '{', json_str)
                # 마지막 "}" 전에 있는 숫자 제거 (배열 끝)
                json_str = re.sub(r'\}\s*\d+\s*\]', '}]', json_str)
                # 불필요한 줄바꿈과 공백 정리
                json_str = re.sub(r'\n\s*', ' ', json_str)
            
            # JSON 파싱 시도
            if json_str.startswith('{') or json_str.startswith('['):
                try:
                    json_data = json.loads(json_str)
                    
                    # next_step 추출
                    if isinstance(json_data, dict):
                        if 'next_step' in json_data:
                            next_step = str(json_data['next_step'])
                        
                        # action 배열 추출
                        if 'action' in json_data:
                            action_value = json_data['action']
                            if isinstance(action_value, list) and len(action_value) > 0:
                                # 첫 번째 action 요소에서 name과 data 추출
                                first_action = action_value[0]
                                if isinstance(first_action, dict):
                                    if 'name' in first_action:
                                        action_name = str(first_action['name'])
                                    if 'data' in first_action:
                                        # data는 문자열이므로 그대로 저장
                                        action_data = str(first_action['data'])
                except (json.JSONDecodeError, ValueError):
                    # JSON 파싱 실패 - 정규식으로 추출 시도
                    pass
            
            # JSON 파싱 실패했거나 필드가 누락된 경우 정규식으로 직접 추출 시도
            # (react-json-view 형식 등 비표준 형식 처리)
            # 원본 raw_json을 사용 (json_str은 변환된 버전일 수 있음)
            
            # next_step 추출 (아직 추출 안 된 경우) - 우선순위 높게 처리
            if not next_step:
                # "next_step":" 패턴 찾기
                next_step_pattern = '"next_step"'
                next_step_idx = raw_json.find(next_step_pattern)
                
                print(f"  🔍 next_step 추출 시도: next_step_idx={next_step_idx}", flush=True)
                
                if next_step_idx != -1:
                    # "next_step" 다음 부분
                    after_next_step = raw_json[next_step_idx + len(next_step_pattern):]
                    print(f"  🔍 after_next_step[:50]: {after_next_step[:50]}", flush=True)
                    
                    # 콜론 찾기
                    colon_idx = after_next_step.find(':')
                    print(f"  🔍 colon_idx: {colon_idx}", flush=True)
                    
                    if colon_idx != -1:
                        after_colon = after_next_step[colon_idx + 1:].lstrip()
                        print(f"  🔍 after_colon[:30]: {after_colon[:30]}", flush=True)
                        
                        # 여는 따옴표 찾기
                        if after_colon and after_colon[0] == '"':
                            # 따옴표 다음부터 시작
                            string_start = 1
                            remaining = after_colon[string_start:]
                            print(f"  🔍 remaining[:20]: {remaining[:20]}", flush=True)
                            
                            # 닫는 따옴표 찾기 (next_step은 간단한 값이므로 이스케이프 없을 가능성 높음)
                            end_quote = remaining.find('"')
                            print(f"  🔍 end_quote: {end_quote}", flush=True)
                            
                            if end_quote != -1:
                                next_step = remaining[:end_quote].strip()
                                print(f"  ✅ next_step 추출 성공 (수동 파싱): '{next_step}'", flush=True)
                            else:
                                # 닫는 따옴표가 없으면 줄바꿈이나 } 전까지
                                end_chars = ['"', '\n', '}', ']', ',']
                                min_idx = len(remaining)
                                for char in end_chars:
                                    idx = remaining.find(char)
                                    if idx != -1 and idx < min_idx:
                                        min_idx = idx
                                if min_idx < len(remaining):
                                    next_step = remaining[:min_idx].strip()
                                    print(f"  ✅ next_step 추출 성공 (대체 방법): '{next_step}'", flush=True)
                        else:
                            print(f"  ⚠️ after_colon이 따옴표로 시작하지 않음: {after_colon[:20]}", flush=True)
                    else:
                        print(f"  ⚠️ 콜론을 찾지 못함", flush=True)
                else:
                    print(f"  ⚠️ next_step 패턴을 찾지 못함", flush=True)
                
                # 수동 파싱 실패 시 정규식으로 재시도
                if not next_step:
                    patterns = [
                        r'"next_step"\s*:\s*"([^"]+)"',  # 따옴표로 감싸진 경우
                        r'"next_step"\s*:\s*([A-Z]+)',    # 따옴표 없이 대문자만
                        r'next_step[":\s]+"?([^",}\]]+)"?',  # 더 유연한 패턴
                    ]
                    for pattern in patterns:
                        next_step_match = re.search(pattern, raw_json, re.IGNORECASE)
                        if next_step_match:
                            next_step = next_step_match.group(1).strip('"').strip()
                            if next_step:
                                print(f"  ✅ next_step 추출 성공 (정규식, 패턴: {pattern[:30]}): '{next_step}'", flush=True)
                                break
                
                if not next_step:
                    # 디버깅: raw_json에서 next_step 부분 찾기
                    debug_start = max(0, next_step_idx - 50) if next_step_idx != -1 else len(raw_json) - 100
                    debug_end = min(len(raw_json), next_step_idx + 100) if next_step_idx != -1 else len(raw_json)
                    print(f"  ⚠️ next_step 추출 실패 - raw_json 일부: {raw_json[debug_start:debug_end]}", flush=True)
            
            # action name 추출 (배열 첫 번째 요소, react-json-view 형식 고려)
            if not action_name:
                # 패턴 1: "action":[0:{"name":"deepLink" (react-json-view 형식)
                action_name_match = re.search(r'"action"\s*:\s*\[\s*\d+\s*:\s*\{\s*"name"\s*:\s*"([^"]+)"', raw_json, re.IGNORECASE | re.DOTALL)
                if action_name_match:
                    action_name = action_name_match.group(1)
                else:
                    # 패턴 2: "action":[{"name":"deepLink" (일반 JSON 형식)
                    action_name_match = re.search(r'"action"\s*:\s*\[\s*\{\s*"name"\s*:\s*"([^"]+)"', raw_json, re.IGNORECASE | re.DOTALL)
                    if action_name_match:
                        action_name = action_name_match.group(1)
            
            # action data 추출 (긴 문자열, 중괄호 포함 가능)
            if not action_data:
                # "data":" 패턴 찾기
                data_pattern = '"data"'
                data_idx = raw_json.find(data_pattern)
                
                if data_idx != -1:
                    # "data" 다음 부분
                    search_start = data_idx + len(data_pattern)
                    remaining_text = raw_json[search_start:]
                    
                    # 콜론과 따옴표 찾기
                    colon_idx = remaining_text.find(':')
                    if colon_idx != -1:
                        after_colon = remaining_text[colon_idx + 1:].lstrip()
                        # 여는 따옴표 찾기
                        if after_colon and after_colon[0] == '"':
                            # 따옴표 다음부터 시작 (문자열 시작)
                            string_start = 1
                            string_content = after_colon[string_start:]
                            
                            # action_data는 항상 }}로 끝나므로, }} 다음의 "를 찾기
                            # }}" 패턴 찾기
                            end_pattern = '}}"'
                            end_idx = string_content.find(end_pattern)
                            if end_idx != -1:
                                # }}" 앞까지가 action_data
                                action_data = string_content[:end_idx + 2]  # }} 포함
                                # 이스케이프 시퀀스 처리
                                action_data = action_data.replace('\\"', '"').replace('\\n', '\n').replace('\\t', '\t').replace('\\\\', '\\')
                                print(f"  ✅ action_data 추출 성공 (}} 패턴): 길이={len(action_data)}", flush=True)
                            else:
                                # }} 패턴이 없으면 중괄호 균형을 맞춰서 닫는 따옴표 찾기
                                # action_data는 JSON 문자열이므로 중괄호가 균형을 이뤄야 함
                                brace_count = 0
                                i = 0
                                found_end = False
                                
                                while i < len(string_content):
                                    # 이스케이프 문자 확인
                                    if string_content[i] == '\\' and i + 1 < len(string_content):
                                        # 이스케이프된 문자는 건너뛰기
                                        i += 2
                                        continue
                                    
                                    # 중괄호 카운트
                                    if string_content[i] == '{':
                                        brace_count += 1
                                    elif string_content[i] == '}':
                                        brace_count -= 1
                                        # 모든 중괄호가 닫혔고, 다음에 "가 오면 끝
                                        if brace_count == 0:
                                            # } 다음의 " 찾기
                                            after_brace = string_content[i + 1:].lstrip()
                                            if after_brace and after_brace[0] == '"':
                                                # } 다음의 "까지가 action_data (} 포함)
                                                action_data = string_content[:i + 1]
                                                # 이스케이프 시퀀스 처리
                                                action_data = action_data.replace('\\"', '"').replace('\\n', '\n').replace('\\t', '\t').replace('\\\\', '\\')
                                                print(f"  ✅ action_data 추출 성공 (중괄호 균형): 길이={len(action_data)}", flush=True)
                                                found_end = True
                                                break
                                    
                                    i += 1
                                
                                # 중괄호 균형 방법이 실패하면 이스케이프를 고려하여 닫는 따옴표 찾기
                                if not found_end:
                                    i = 0
                                    while i < len(string_content):
                                        if string_content[i] == '\\' and i + 1 < len(string_content):
                                            if string_content[i + 1] == '"':
                                                i += 2
                                            else:
                                                i += 1
                                        elif string_content[i] == '"':
                                            action_data = string_content[:i]
                                            action_data = action_data.replace('\\"', '"').replace('\\n', '\n').replace('\\t', '\t').replace('\\\\', '\\')
                                            print(f"  ✅ action_data 추출 성공 (이스케이프 고려): 길이={len(action_data)}", flush=True)
                                            found_end = True
                                            break
                                        else:
                                            i += 1
                                    
                                    if not found_end:
                                        print(f"  ⚠️ action_data 닫는 따옴표를 찾지 못함", flush=True)
                
                # 수동 파싱 실패 시 정규식으로 재시도
                if not action_data:
                    pattern = r'"data"\s*:\s*"((?:[^"\\]|\\.)*)"'
                    action_data_match = re.search(pattern, raw_json, re.IGNORECASE | re.DOTALL)
                    if action_data_match:
                        action_data = action_data_match.group(1)
                        action_data = action_data.replace('\\"', '"').replace('\\n', '\n').replace('\\t', '\t').replace('\\\\', '\\')
                        print(f"  ✅ action_data 추출 성공 (정규식): 길이={len(action_data)}", flush=True)
                
                if not action_data:
                    print(f"  ⚠️ action_data 추출 실패", flush=True)
            
        except (json.JSONDecodeError, ValueError) as e:
            # JSON 파싱 실패해도 정규식 추출은 시도했으므로 계속 진행
            pass
        except Exception as e:
            import sys
            print(f"  ⚠️ Raw JSON에서 action 필드 추출 중 예상치 못한 오류: {e}", flush=True)
            sys.stdout.flush()
        
        return (action_name, action_data, next_step)
    
    def extract_action_fields_from_response_structured(self, response_structured: str) -> tuple:
        """
        Response (structured)에서 action_name, action_data, next_step 필드를 추출합니다.
        
        Args:
            response_structured: Response (structured) 문자열
        
        Returns:
            (action_name, action_data, next_step) 튜플
        """
        action_name = ''
        action_data = ''
        next_step = ''
        
        if not response_structured or not response_structured.strip():
            return (action_name, action_data, next_step)
        
        try:
            import re
            import sys
            
            # 디버깅: 입력된 response_structured 형식 확인
            print(f"  🔍 extract_action_fields_from_response_structured 입력: 길이={len(response_structured)}, 처음 300자=\n{response_structured[:300]}", flush=True)
            
            # next_step 추출
            # response_structured에는 next_step이 없을 수 있으므로 raw_json에서 추출한 값 사용
            # 여기서는 response_structured에 next_step이 있는 경우만 추출
            if not next_step:
                # 패턴: "next_step: END" 또는 "next_step": "END" 등
                next_step_patterns = [
                    r'next_step[:\s]+"?([^",}\n]+)"?',
                    r'"next_step"[:\s]+"?([^",}\n]+)"?',
                    r'next_step[:\s]+([A-Z]+)',  # END 같은 대문자 값
                ]
                for pattern in next_step_patterns:
                    next_step_match = re.search(pattern, response_structured, re.IGNORECASE)
                    if next_step_match:
                        next_step = next_step_match.group(1).strip('"').strip()
                        if next_step:
                            print(f"  ✅ response_structured에서 next_step 추출 성공: '{next_step}'", flush=True)
                            break
            
            # action name 추출
            # 패턴: "name": "deepLink" 또는 name: deepLink 등
            action_name_patterns = [
                r'"name"[:\s]+"([^"]+)"',
                r'name[:\s]+"([^"]+)"',
                r'name[:\s]+([a-zA-Z]+)',  # deepLink 같은 값
            ]
            for pattern in action_name_patterns:
                action_name_match = re.search(pattern, response_structured, re.IGNORECASE | re.DOTALL)
                if action_name_match:
                    action_name = action_name_match.group(1).strip()
                    if action_name:
                        print(f"  ✅ response_structured에서 action_name 추출 성공: '{action_name}'", flush=True)
                        break
            
            # action data 추출 (긴 문자열, 중괄호 포함)
            # response_structured에서도 수동 파싱 시도
            if not action_data:
                # "data":" 이후부터 시작
                data_start_pattern = r'"data"[:\s]+"'
                data_start_match = re.search(data_start_pattern, response_structured, re.IGNORECASE)
                
                if data_start_match:
                    start_pos = data_start_match.end()
                    remaining = response_structured[start_pos:]
                    
                    # action_data는 항상 }}로 끝나므로, }} 다음의 "를 찾기
                    end_pattern = '}}"'
                    end_idx = remaining.find(end_pattern)
                    if end_idx != -1:
                        # }}" 앞까지가 action_data
                        action_data = remaining[:end_idx + 2]  # }} 포함
                        action_data = action_data.replace('\\"', '"').replace('\\n', '\n').replace('\\t', '\t').replace('\\\\', '\\')
                        print(f"  ✅ response_structured에서 action_data 추출 성공 (}} 패턴): 길이={len(action_data)}", flush=True)
                    else:
                        # }} 패턴이 없으면 중괄호 균형을 맞춰서 닫는 따옴표 찾기
                        brace_count = 0
                        i = 0
                        found_end = False
                        
                        while i < len(remaining):
                            if remaining[i] == '\\' and i + 1 < len(remaining):
                                i += 2
                                continue
                            
                            if remaining[i] == '{':
                                brace_count += 1
                            elif remaining[i] == '}':
                                brace_count -= 1
                                if brace_count == 0:
                                    after_brace = remaining[i + 1:].lstrip()
                                    if after_brace and after_brace[0] == '"':
                                        action_data = remaining[:i + 1]
                                        action_data = action_data.replace('\\"', '"').replace('\\n', '\n').replace('\\t', '\t').replace('\\\\', '\\')
                                        print(f"  ✅ response_structured에서 action_data 추출 성공 (중괄호 균형): 길이={len(action_data)}", flush=True)
                                        found_end = True
                                        break
                            
                            i += 1
                        
                        if not found_end:
                            i = 0
                            while i < len(remaining):
                                if remaining[i] == '\\' and i + 1 < len(remaining):
                                    if remaining[i + 1] == '"':
                                        i += 2
                                    else:
                                        i += 1
                                elif remaining[i] == '"':
                                    action_data = remaining[:i]
                                    action_data = action_data.replace('\\"', '"').replace('\\n', '\n').replace('\\t', '\t').replace('\\\\', '\\')
                                    print(f"  ✅ response_structured에서 action_data 추출 성공 (이스케이프 고려): 길이={len(action_data)}", flush=True)
                                    found_end = True
                                    break
                                else:
                                    i += 1
                            
                            if not found_end:
                                print(f"  ⚠️ response_structured에서 action_data 닫는 따옴표를 찾지 못함", flush=True)
                
                # 정규식으로 재시도
                if not action_data:
                    action_data_patterns = [
                        r'"data"[:\s]+"((?:[^"\\]|\\.)*)"',  # 이스케이프 고려
                        r'data[:\s]+"((?:[^"\\]|\\.)*)"',
                    ]
                    for pattern in action_data_patterns:
                        action_data_match = re.search(pattern, response_structured, re.IGNORECASE | re.DOTALL)
                        if action_data_match:
                            action_data = action_data_match.group(1)
                            action_data = action_data.replace('\\"', '"').replace('\\n', '\n').replace('\\t', '\t').replace('\\\\', '\\')
                            if action_data:
                                print(f"  ✅ response_structured에서 action_data 추출 성공 (정규식): 길이={len(action_data)}", flush=True)
                                break
            
        except Exception as e:
            import sys
            print(f"  ⚠️ response_structured에서 action 필드 추출 중 오류: {e}", flush=True)
            import traceback
            traceback.print_exc()
            sys.stdout.flush()
        
        return (action_name, action_data, next_step)
    
    def extract_tts(self) -> str:
        """
        TTS 출력을 추출합니다. (레거시 메서드, 호환성 유지)
        
        Returns:
            TTS 출력 텍스트
        """
        # Raw JSON에서 먼저 추출 시도
        raw_json = self.extract_expander_content('Raw JSON')
        if raw_json:
            tts = self.extract_tts_from_raw_json(raw_json)
            if tts:
                return tts
        
        # 대체: "TTS" 제목을 가진 expander 찾기
        tts_content = self.extract_expander_content('TTS')
        if tts_content:
            return tts_content
        
        return ''
    
    def send_message_and_collect_results(self, message: str, message_index: int = 0) -> Dict:
        """
        메시지를 전송하고 결과를 수집합니다.
        
        Args:
            message: 전송할 메시지
            message_index: 메시지 인덱스 (디버깅용)
        
        Returns:
            결과 딕셔너리 (latency, response_structured, raw_json, tts)
        """
        results = {
            'latency': '',
            'response_structured': '',
            'raw_json': '',
            'tts': ''
        }
        
        try:
            print(f"  📤 메시지 {message_index + 1} 전송 시작: {message[:50]}...")
            
            # 이전 응답이 완전히 끝날 때까지 대기 (latency 최대 7초 고려)
            print(f"  ⏳ 이전 응답 완료 대기 중...")
            # 불필요한 대기 시간을 줄이기 위해 기본 대기를 2초 → 1초로 축소
            time.sleep(1)

            # Text Input 탭 활성화 (있을 경우)
            try:
                text_input_tab = self.page.locator('button:has-text("Text Input")')
                if text_input_tab.count() > 0:
                    tab = text_input_tab.first
                    print('  ✅ Text Input 탭 찾음: button:has-text("Text Input")')
                    try:
                        aria_pressed = (tab.get_attribute("aria-pressed") or "").lower()
                        kind_attr = (tab.get_attribute("kind") or "").lower()
                        is_active = aria_pressed == "true" or "primary" in kind_attr
                    except Exception:
                        is_active = False

                    if not is_active:
                        print("  ⚙️ Text Input 탭이 비활성화 상태, 클릭하여 활성화")
                        tab.click()
                        time.sleep(0.5)
                    else:
                        print("  ✅ Text Input 탭이 이미 활성화됨")
            except Exception as e:
                print(f"  ⚠️ Text Input 탭 처리 중 오류 (계속 진행): {e}")
            
            # 메시지 입력창 찾기 (더 정확하게, 여러 방법 시도)
            message_input = None
            max_input_retries = 5
            
            for retry in range(max_input_retries):
                try:
                    # 방법 1: 한국어 placeholder (예: "메시지", "메시지를 입력")
                    message_input = self.page.locator(
                        'textarea[placeholder*="메시지" i], textarea[placeholder*="메시지를 입력" i]'
                    )
                    if message_input.count() > 0:
                        print(f'  ✅ 메시지 입력창 찾음 (placeholder*="메시지", 시도 {retry + 1})')
                        break
                    
                    # 방법 2: 한국어/영어 aria-label
                    message_input = self.page.locator(
                        'textarea[aria-label*="메시지" i], '
                        'textarea[aria-label*="message" i], '
                        'textarea[aria-label="Your Message"]'
                    )
                    if message_input.count() > 0:
                        print(f'  ✅ 메시지 입력창 찾음 (aria-label, 시도 {retry + 1})')
                        break
                    
                    # 방법 3: Text Input 영역 내부 textarea 우선 탐색
                    text_input_panels = self.page.locator(
                        'section[aria-label="Text Input"], div[aria-label="Text Input"]'
                    )
                    if text_input_panels.count() > 0:
                        panel = text_input_panels.last
                        panel_textareas = panel.locator('textarea')
                        if panel_textareas.count() > 0:
                            message_input = panel_textareas.last
                            print(f"  ✅ 메시지 입력창 찾음 (Text Input 패널 내부, 시도 {retry + 1})")
                            break

                    # 방법 4: label 텍스트로 찾기
                    labels = self.page.locator('label')
                    for i in range(labels.count()):
                        try:
                            label_el = labels.nth(i)
                            text = (label_el.inner_text() or "").strip()
                            if not text:
                                continue
                            lower = text.lower()
                            if "message" in lower or "메시지" in lower:
                                candidate = label_el.locator("textarea")
                                if candidate.count() == 0:
                                    parent = label_el.locator("..")
                                    candidate = parent.locator("textarea")
                                if candidate.count() > 0:
                                    message_input = candidate
                                    print(f"  ✅ 메시지 입력창 찾음 (label 기반, 시도 {retry + 1})")
                                    break
                        except Exception:
                            continue
                    if message_input and message_input.count() > 0:
                        break

                    # 방법 5: 모든 textarea 중 rows 속성이 가장 큰 것 선택 (채팅창일 가능성 높음)
                    all_textareas = self.page.locator("textarea")
                    if all_textareas.count() > 0:
                        max_rows = -1
                        selected_textarea = None
                        for i in range(all_textareas.count()):
                            ta = all_textareas.nth(i)
                            try:
                                rows_attr = ta.get_attribute("rows")
                                rows = int(rows_attr) if rows_attr is not None else 0
                                if rows >= max_rows:
                                    max_rows = rows
                                    selected_textarea = ta
                            except Exception:
                                continue
                        if selected_textarea:
                            message_input = selected_textarea
                            print(
                                f"  ✅ 메시지 입력창 찾음 (가장 큰 textarea, rows={max_rows}, 시도 {retry + 1})"
                            )
                        break
                    
                    if retry < max_input_retries - 1:
                        print(f"  ⚠️ 메시지 입력창 찾기 실패, 재시도 중... (시도 {retry + 1}/{max_input_retries})")
                        time.sleep(1)
                        
                except Exception as e:
                    print(f"  ⚠️ 입력창 찾기 오류 (시도 {retry + 1}): {e}")
                    if retry < max_input_retries - 1:
                        time.sleep(1)
            
            if message_input is None or message_input.count() == 0:
                print(f"  ❌ 메시지 입력창을 찾을 수 없습니다 (최대 시도 횟수 초과)")
                results['error'] = "메시지 입력창을 찾을 수 없음"
                return results
            
            # 입력 필드가 활성화될 때까지 대기
            print(f"  ⏳ 입력 필드 활성화 대기 중...")
            try:
                message_input.first.wait_for(state="visible", timeout=5000)
                message_input.first.wait_for(state="attached", timeout=5000)
            except Exception as e:
                print(f"  ⚠️ 입력 필드 활성화 대기 중 오류: {e}")
            
            # 기존 내용 클리어 후 새 메시지 입력 (더 확실하게)
            print(f"  ✏️ 메시지 입력 중...")
            try:
                # 클릭하여 포커스
                message_input.first.click()
                time.sleep(0.3)
                
                # 전체 선택 후 삭제 (더 확실한 클리어)
                message_input.first.press('Control+a')  # Mac/Linux
                time.sleep(0.2)
                message_input.first.press('Meta+a')  # Mac 대체
                time.sleep(0.2)
                message_input.first.fill('')  # 클리어
                time.sleep(0.3)
                
                # 새 메시지 입력
                message_input.first.fill(str(message))
                time.sleep(0.5)
                
                # 입력 확인
                current_value = message_input.first.input_value()
                if current_value != str(message):
                    print(f"  ⚠️ 입력값 불일치, 재입력 시도...")
                    message_input.first.fill('')
                    time.sleep(0.2)
                    message_input.first.fill(str(message))
                    time.sleep(0.5)
                
                print(f"  ✅ 메시지 입력 완료: '{current_value[:50]}...'")
                
            except Exception as e:
                print(f"  ❌ 메시지 입력 중 오류: {e}")
                # 대체 방법: type 사용
                try:
                    message_input.first.fill('')
                    message_input.first.type(str(message), delay=50)
                    time.sleep(0.5)
                    print(f"  ✅ 메시지 입력 완료 (type 방법)")
                except Exception as e2:
                    print(f"  ❌ 메시지 입력 실패: {e2}")
                    results['error'] = f"메시지 입력 실패: {str(e2)}"
                    return results
            
            # "Send Text" / "Send Message" 버튼 클릭
            # 새 응답이 생겼는지 확인하기 위해 현재 stJson 개수를 기록
            try:
                prev_json_count = self.page.locator('div[data-testid="stJson"]').count()
            except Exception:
                prev_json_count = 0
            send_button = None
            send_button_texts = ["Send Text", "Send Message", "Send"]

            for button_text in send_button_texts:
                candidate = self.page.locator(f'button:has-text("{button_text}")')
                if candidate.count() > 0:
                    send_button = candidate
                    print(f'  ✅ {button_text} 버튼 찾음')
                    break

            if send_button and send_button.count() > 0:
                try:
                    # 버튼이 보이는지 확인하고 클릭
                    send_button.first.wait_for(state="visible", timeout=3000)
                    send_button.first.click()
                    print(f"  ✅ Send 버튼 클릭 완료")
                except Exception as e:
                    print(f"  ⚠️ Send 버튼 클릭 실패, Enter 키로 전송 시도: {e}")
                    try:
                        message_input.first.press("Enter")
                        print(f"  ✅ Enter 키로 전송")
                    except Exception as e2:
                        print(f"  ⚠️ Enter 키 전송도 실패: {e2}")
            else:
                # 버튼을 찾지 못한 경우 Enter 키로 전송 시도
                print(f"  ⚠️ Send 버튼을 찾을 수 없음, Enter 키로 전송 시도")
                try:
                    message_input.first.press("Enter")
                    print(f"  ✅ Enter 키로 전송")
                except Exception as e:
                    print(f"  ⚠️ Enter 키 전송 실패: {e}")
            
            # 응답이 완전히 로드될 때까지 대기
            # - 이전과 달리 "Response received" 텍스트나 Expander를 기다리지 않고
            #   새 stJson 블록이 생성될 때까지 최대 8초 동안만 폴링한다.
            print(f"  ⏳ 응답 대기 중... (최대 8초, 새 JSON 생성까지)")
            max_wait_sec = 8
            start_wait = time.time()
            new_json_detected = False
            while time.time() - start_wait < max_wait_sec:
                try:
                    current_count = self.page.locator('div[data-testid="stJson"]').count()
                except Exception:
                    current_count = prev_json_count
                if current_count > prev_json_count:
                    print(f"  ✅ 새 stJson 생성 확인 (이전={prev_json_count}, 현재={current_count})")
                    new_json_detected = True
                    break
                time.sleep(0.5)
            if not new_json_detected:
                print(f"  ⚠️ 새 stJson 생성 확인 실패 (타임아웃, 계속 진행)")
            # 렌더링이 약간 더 안정되도록 짧은 추가 대기
            time.sleep(0.5)
            
            # 4. 스크롤을 맨 아래로 (최신 응답 확인)
            self.page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            time.sleep(1)
            
            # 4-1. 클립보드 기반 Raw JSON 추출 시도
            try:
                print(
                    "  🔍 클립보드 기반 Raw JSON 추출 시도 "
                    "(react-json-view 전용, 현재 메시지 User 턴과 매칭 시도)..."
                )
                # 멀티턴에서도 각 턴의 최신 응답과 싱크를 맞추기 위해
                # 1) 현재 보낸 message 텍스트를 포함하는 User: ... 마크다운을 찾고
                # 2) 그 User 블록 이후에 나오는 stJson 중 첫 번째 하나를 찾는다.
                # 3) 해당 stJson 내부의 copy 아이콘만 클릭한다.
                clicked = self.page.evaluate(
                    """
                    (messageText) => {
                        try {
                            // 1) User: ... 마크다운들 수집
                            const mdContainers = Array.from(
                                document.querySelectorAll('div[data-testid="stMarkdownContainer"]')
                            );
                            const userBlocks = mdContainers.filter(el => {
                                const text = (el.innerText || '').trim();
                                return text.startsWith('User:');
                            });
                            if (!userBlocks.length) {
                                return { ok: false, reason: 'no_user_markdown' };
                            }

                            // 1-1) messageText 를 포함하는 User 를 우선적으로 찾고,
                            //      없으면 마지막 User 를 사용
                            let targetUser = null;
                            for (let i = userBlocks.length - 1; i >= 0; i--) {
                                const text = (userBlocks[i].innerText || '').trim();
                                if (text.includes(messageText)) {
                                    targetUser = userBlocks[i];
                                    break;
                                }
                            }
                            if (!targetUser) {
                                targetUser = userBlocks[userBlocks.length - 1];
                            }

                            // 2) targetUser 이후에 나오는 stJson 중 첫 번째 찾기
                            let cursor = targetUser;
                            let targetJson = null;
                            while (cursor && !targetJson) {
                                cursor = cursor.parentElement || cursor.nextElementSibling;
                                if (!cursor) break;

                                // 같은 VerticalBlock 안에 있는 경우를 우선 탐색
                                const inBlock = cursor.querySelector
                                    ? cursor.querySelector('div[data-testid="stJson"]')
                                    : null;
                                if (inBlock) {
                                    targetJson = inBlock;
                                    break;
                                }
                            }

                            // fallback: 페이지 전체에서 targetUser 아래쪽에 있는 stJson 중
                            //           가장 가까운 것을 선택
                            if (!targetJson) {
                                const userRect = targetUser.getBoundingClientRect();
                                const jsonBlocks = Array.from(
                                    document.querySelectorAll('div[data-testid="stJson"]')
                                );
                                if (!jsonBlocks.length) {
                                    return { ok: false, reason: 'no_stJson' };
                                }
                                let bestJson = null;
                                let bestDelta = Number.POSITIVE_INFINITY;
                                for (const jb of jsonBlocks) {
                                    const rect = jb.getBoundingClientRect();
                                    const delta = rect.top - userRect.top;
                                    if (delta >= 0 && delta < bestDelta) {
                                        bestDelta = delta;
                                        bestJson = jb;
                                    }
                                }
                                targetJson = bestJson || jsonBlocks[jsonBlocks.length - 1];
                            }

                            if (!targetJson) {
                                return { ok: false, reason: 'no_targetJson' };
                            }

                            // 3) 해당 stJson 내부의 react-json-view copy 컨테이너만 대상으로
                            const containers = Array.from(
                                targetJson.querySelectorAll('.react-json-view .copy-to-clipboard-container')
                            );
                            if (!containers.length) {
                                return { ok: false, reason: 'no_containers_in_targetJson' };
                            }

                            const target = containers[containers.length - 1];
                            // 숨겨져 있어도 강제로 보이게 설정
                            target.style.display = 'inline';
                            target.style.visibility = 'visible';
                            target.style.opacity = '1';

                            const icon = target.querySelector('.copy-icon') || target;
                            if (icon instanceof HTMLElement) {
                                icon.click();
                                return { ok: true, reason: 'clicked' };
                            }
                            return { ok: false, reason: 'icon_not_clickable' };
                        } catch (e) {
                            return { ok: false, reason: 'exception:' + String(e) };
                        }
                    }
                    """,
                    message,
                )
                if isinstance(clicked, dict) and clicked.get("ok"):
                    print(
                        "  ✅ react-json-view copy 아이콘 클릭 성공 "
                        f"(JS, User 기준 매칭, reason={clicked.get('reason')})"
                    )
                    time.sleep(0.5)
                else:
                    print(f"  ⚠️ react-json-view copy 아이콘 클릭 실패 (clicked={clicked})")

                # window.__NAVIQA_COPIES__에서 마지막 값 읽기
                clipboard_text = self.page.evaluate(
                    "(() => (window.__NAVIQA_COPIES__ && window.__NAVIQA_COPIES__.length"
                    " ? window.__NAVIQA_COPIES__[window.__NAVIQA_COPIES__.length - 1]"
                    " : null))()"
                )
                if clipboard_text:
                    import json

                    results["raw_json"] = clipboard_text
                    print(f"  ✅ 클립보드 JSON 추출 성공 (길이: {len(clipboard_text)})")

                    # TTS를 JSON에서 직접 추출 시도
                    try:
                        parsed = json.loads(clipboard_text)
                        if isinstance(parsed, dict) and "tts" in parsed and isinstance(parsed["tts"], str):
                            results["tts"] = parsed["tts"]
                            print(f"  ✅ 클립보드 JSON에서 TTS 추출 성공: {results['tts'][:50]}...")
                    except Exception as e:
                        print(f"  ⚠️ 클립보드 JSON 파싱 실패 (계속 진행): {e}")
                else:
                    print(f"  ⚠️ 클립보드에 캡처된 JSON이 없음")
            except Exception as e:
                print(f"  ⚠️ 클립보드 기반 Raw JSON 추출 중 오류 (계속 진행): {e}")
            
            print(f"  📥 결과 추출 시작...")
            
            # 결과 추출 (여러 번 시도) - 기본 시도 1회 + 추가 1회까지만 재시도
            max_retries = 2
            for retry in range(max_retries):
                try:
                    results['latency'] = self.extract_latency()
                    # 클립보드에서 이미 Raw JSON을 가져오지 못한 경우에만 DOM에서 추출
                    if not results['response_structured']:
                        results['response_structured'] = self.extract_expander_content('Response (structured)')
                    if not results['raw_json']:
                        results['raw_json'] = self.extract_expander_content('Raw JSON')
                    if not results['tts'] and results['raw_json']:
                        results['tts'] = self.extract_tts_from_raw_json(results['raw_json'])
                    
                    # 결과가 있는지 확인
                    if results['raw_json'] or results['response_structured']:
                        print(f"  ✅ 결과 추출 성공 (시도 {retry + 1}/{max_retries})")
                        break
                    else:
                        print(f"  ⚠️ 결과가 비어있음, 재시도 중... (시도 {retry + 1}/{max_retries})")
                        # 재시도 간격도 2초 → 1초로 축소
                        time.sleep(1)
                except Exception as e:
                    print(f"  ⚠️ 결과 추출 오류 (시도 {retry + 1}/{max_retries}): {e}")
                    if retry < max_retries - 1:
                        time.sleep(1)
            
            print(f"  📊 추출된 결과: latency={results['latency'][:30] if results['latency'] else 'N/A'}, raw_json_len={len(results['raw_json'])}, tts_len={len(results['tts'])}")
            
            # 다음 테스트를 위한 대기 (입력 필드가 다시 활성화될 때까지)
            print(f"  ⏳ 다음 테스트 준비 대기 중... (1.5초)")
            time.sleep(1.5)
            
        except Exception as e:
            import traceback
            error_trace = traceback.format_exc()
            print(f"  ❌ 메시지 전송 및 결과 수집 중 오류 발생: {e}")
            print(f"  {error_trace}")
            results['error'] = str(e)
        
        return results
    
    def _get_column_value(self, df_row, col_name, default=''):
        """컬럼명 대소문자 구분 없이 값을 가져옵니다."""
        for key in df_row.index:
            if key.lower() == col_name.lower():
                return df_row[key]
        return df_row.get(col_name, default)
    
    def _initialize_chat_for_row(self, row):
        """행 데이터에서 채팅을 초기화합니다."""
        # is_driving 값 처리
        is_driving_value = self._get_column_value(row, 'is_driving', False)
        if isinstance(is_driving_value, str):
            is_driving_value = is_driving_value.upper() == 'TRUE'
        elif isinstance(is_driving_value, (int, float)):
            is_driving_value = bool(is_driving_value)
        else:
            is_driving_value = bool(is_driving_value)
        
        self.initialize_chat(
            user_id=str(self._get_column_value(row, 'user_id', '')),
            lat=float(self._get_column_value(row, 'lat', 0)),
            lng=float(self._get_column_value(row, 'lng', 0)),
            is_driving=is_driving_value
        )
    
    def _execute_turn(self, row, turn_number, test_case_id=None):
        """한 턴을 실행하고 결과를 반환합니다."""
        from similarity import calculate_similarity, determine_pass_fail
        from evaluator import evaluate_comprehensive
        
        try:
            # 메시지 전송 및 결과 수집
            message_value = self._get_column_value(row, 'message', '')
            test_results = self.send_message_and_collect_results(str(message_value), 0)
            
            # Raw JSON에서 TTS 추출
            tts_from_raw_json = self.extract_tts_from_raw_json(test_results['raw_json'])
            
            # Raw JSON에서 action 필드 추출
            # 디버깅: raw_json 실제 내용 확인
            raw_json_content = test_results.get('raw_json', '')
            print(f"  🔍 Raw JSON 전체 내용 ({len(raw_json_content)}자):\n{raw_json_content}", flush=True)
            
            # raw_json에서 먼저 추출 시도
            action_name, action_data, next_step = self.extract_action_fields_from_raw_json(test_results['raw_json'])
            import sys
            
            # raw_json에서 추출 실패한 경우 response_structured에서 시도
            if not action_name or not action_data or not next_step:
                print(f"  ⚠️ raw_json에서 일부 필드 추출 실패, response_structured에서 시도...", flush=True)
                response_structured_content = test_results.get('response_structured', '')
                print(f"  🔍 Response (structured) 전체 내용 ({len(response_structured_content)}자):\n{response_structured_content}", flush=True)
                
                rs_action_name, rs_action_data, rs_next_step = self.extract_action_fields_from_response_structured(response_structured_content)
                
                # response_structured에서 추출한 값으로 보완
                if not action_name and rs_action_name:
                    action_name = rs_action_name
                    print(f"  ✅ response_structured에서 action_name 보완: '{action_name}'", flush=True)
                if not action_data and rs_action_data:
                    action_data = rs_action_data
                    print(f"  ✅ response_structured에서 action_data 보완: 길이={len(action_data)}", flush=True)
                if not next_step and rs_next_step:
                    next_step = rs_next_step
                    print(f"  ✅ response_structured에서 next_step 보완: '{next_step}'", flush=True)
            
            print(f"  📋 최종 추출된 action 필드: action_name='{action_name}', action_data 길이={len(action_data)}, next_step='{next_step}'", flush=True)
            sys.stdout.flush()
            
            # 기대값 컬럼 읽기 - row에서 직접 가져오기
            import pandas as pd
            
            # 디버깅: row의 모든 컬럼명 출력
            print(f"  🔍 row.index 전체: {list(row.index)}", flush=True)
            
            # tts_expected (선택적)
            tts_expected_raw = self._get_column_value(row, 'tts_expected', '')
            if pd.isna(tts_expected_raw):
                tts_expected = ''
            else:
                tts_expected = str(tts_expected_raw).strip()
            
            # action_name_expected - row에서 직접 접근 (여러 방법 시도)
            action_name_expected = ''
            # 방법 1: _get_column_value 사용
            action_name_expected_raw = self._get_column_value(row, 'action_name_expected', '')
            if action_name_expected_raw and not pd.isna(action_name_expected_raw):
                action_name_expected = str(action_name_expected_raw).strip()
            else:
                # 방법 2: row.index 순회
                for col in row.index:
                    if col.lower() == 'action_name_expected':
                        val = row[col]
                        if val and not pd.isna(val):
                            action_name_expected = str(val).strip()
                            print(f"  ✅ action_name_expected 찾음 (row.index): '{action_name_expected}'", flush=True)
                        break
                # 방법 3: 직접 접근 시도
                if not action_name_expected and 'action_name_expected' in row.index:
                    val = row['action_name_expected']
                    if val and not pd.isna(val):
                        action_name_expected = str(val).strip()
                        print(f"  ✅ action_name_expected 찾음 (직접 접근): '{action_name_expected}'", flush=True)
            
            # action_data_expected
            action_data_expected = ''
            action_data_expected_raw = self._get_column_value(row, 'action_data_expected', '')
            if action_data_expected_raw and not pd.isna(action_data_expected_raw):
                action_data_expected = str(action_data_expected_raw).strip()
            
            # next_step_expected
            next_step_expected = ''
            next_step_expected_raw = self._get_column_value(row, 'next_step_expected', '')
            if next_step_expected_raw and not pd.isna(next_step_expected_raw):
                next_step_expected = str(next_step_expected_raw).strip()
            
            # 디버깅: 읽은 값 확인
            print(f"  🔍 기대값 읽기 결과: tts_expected='{tts_expected}', action_name_expected='{action_name_expected}', action_data_expected='{action_data_expected[:50] if action_data_expected else ''}', next_step_expected='{next_step_expected}'", flush=True)
            
            # 종합 평가 수행
            evaluation_result = evaluate_comprehensive(
                raw_json=test_results.get('raw_json', ''),
                tts_actual=tts_from_raw_json,
                tts_expected=tts_expected,
                action_name=action_name or '',
                action_name_expected=action_name_expected,
                action_data=action_data or '',
                action_data_expected=action_data_expected,
                next_step=next_step or '',
                next_step_expected=next_step_expected,
            )
            
            verdict = evaluation_result['verdict']
            fail_reason = evaluation_result['fail_reason']
            scores = evaluation_result['scores']
            
            print(f"  📊 평가 결과: verdict={verdict}, fail_reason={fail_reason[:100] if fail_reason else ''}", flush=True)
            print(f"  📊 점수: tts={scores['tts']:.2f}, action_name={scores['action_name']:.2f}, action_data={scores['action_data']:.2f}, next_step={scores['next_step']:.2f}", flush=True)
            
            # 기존 similarity 계산도 유지 (하위 호환성)
            user_message = str(message_value)
            similarity = calculate_similarity(tts_from_raw_json, tts_expected)
            
            # latency에서 숫자만 추출 (ms 단위)
            latency_ms = None
            if test_results['latency']:
                import re
                latency_match = re.search(r'(\d+)\s*ms', test_results['latency'])
                if latency_match:
                    latency_ms = float(latency_match.group(1))
            
            # is_driving 값 처리
            is_driving_value = self._get_column_value(row, 'is_driving', False)
            if isinstance(is_driving_value, str):
                is_driving_value = is_driving_value.upper() == 'TRUE'
            elif isinstance(is_driving_value, (int, float)):
                is_driving_value = bool(is_driving_value)
            else:
                is_driving_value = bool(is_driving_value)
            
            # 결과 저장
            import json as json_module
            # 디버깅: 저장 전 값 확인
            print(f"  💾 저장할 기대값: action_name_expected='{action_name_expected}', action_data_expected='{action_data_expected[:50] if action_data_expected else ''}', next_step_expected='{next_step_expected}'", flush=True)
            
            result_row = {
                'test_case_id': test_case_id if test_case_id is not None else '',
                'turn_number': turn_number if turn_number is not None else '',
                'user_id': str(self._get_column_value(row, 'user_id', '')),
                'lng': self._get_column_value(row, 'lng', ''),
                'lat': self._get_column_value(row, 'lat', ''),
                'is_driving': is_driving_value,
                'message': str(message_value),
                'tts_expected': tts_expected if tts_expected else '',
                'action_name_expected': action_name_expected if action_name_expected else '',  # 빈 문자열로 확실히 저장
                'action_data_expected': action_data_expected if action_data_expected else '',
                'next_step_expected': next_step_expected if next_step_expected else '',
                'latency': latency_ms,
                'latency_text': test_results['latency'],
                'response_structured': test_results['response_structured'],
                'raw_json': test_results['raw_json'],
                'tts_actual': tts_from_raw_json,
                'action_name': action_name,
                'action_data': action_data,
                'next_step': next_step,
                'verdict': verdict,  # PASS/PARTIAL_PASS/FAIL
                'pass/fail': verdict,  # 하위 호환성을 위해 유지
                'similarity_score': similarity,
                'fail_reason': fail_reason,
                'scores': json_module.dumps(scores)  # JSON 문자열로 저장
            }
            return result_row
            
        except Exception as e:
            # 오류 발생 시
            # is_driving 값 처리
            is_driving_value = self._get_column_value(row, 'is_driving', False)
            if isinstance(is_driving_value, str):
                is_driving_value = is_driving_value.upper() == 'TRUE'
            elif isinstance(is_driving_value, (int, float)):
                is_driving_value = bool(is_driving_value)
            else:
                is_driving_value = bool(is_driving_value)
            
            import json as json_module
            return {
                'test_case_id': test_case_id if test_case_id is not None else '',
                'turn_number': turn_number if turn_number is not None else '',
                'user_id': str(self._get_column_value(row, 'user_id', '')),
                'lng': self._get_column_value(row, 'lng', ''),
                'lat': self._get_column_value(row, 'lat', ''),
                'is_driving': is_driving_value,
                'message': str(self._get_column_value(row, 'message', '')),
                'tts_expected': str(self._get_column_value(row, 'tts_expected', '')) if self._get_column_value(row, 'tts_expected', '') else '',
                'action_name_expected': '',  # 오류 시 빈 문자열
                'action_data_expected': '',
                'next_step_expected': '',
                'latency': None,
                'latency_text': '',
                'response_structured': '',
                'raw_json': '',
                'tts_actual': '',
                'action_name': '',
                'action_data': '',
                'next_step': '',
                'verdict': 'FAIL',
                'pass/fail': 'FAIL',  # 하위 호환성
                'similarity_score': 0.0,
                'fail_reason': f'테스트 실행 오류: {str(e)}',
                'scores': json_module.dumps({'tts': 0.0, 'action_name': 0.0, 'action_data': 0.0, 'next_step': 0.0})
            }
    
    def reset_page(self):
        """
        페이지를 리셋하여 새로운 세션을 시작합니다.
        """
        try:
            print("🔄 페이지 리셋 중...")
            # 페이지를 새로 로드하여 세션 초기화
            self.page.goto(self.base_url, timeout=60000)
            self.page.wait_for_load_state("networkidle", timeout=60000)
            time.sleep(2)  # 페이지 로드 후 안정화 대기
            print("✅ 페이지 리셋 완료")
        except Exception as e:
            print(f"⚠️ 페이지 리셋 중 오류 (계속 진행): {e}")
            # 오류가 발생해도 계속 진행

    def run_tests(self, test_cases: pd.DataFrame, progress_callback=None) -> pd.DataFrame:
        """
        모든 테스트 케이스를 실행합니다.
        멀티턴 시나리오를 지원합니다 (test_case_id + turn_number).
        
        Args:
            test_cases: 테스트 케이스가 담긴 DataFrame
            progress_callback: 진행 상황 콜백 함수 (current, total, elapsed_time, estimated_remaining)
        
        Returns:
            결과가 포함된 DataFrame
        """
        results = []
        import time as time_module
        
        # 컬럼명 대소문자 구분 없이 확인
        df_columns_lower = {col.lower(): col for col in test_cases.columns}
        has_test_case_id = 'test_case_id' in df_columns_lower
        has_turn_number = 'turn_number' in df_columns_lower
        
        # 멀티턴 시나리오인지 확인
        is_multi_turn = has_test_case_id and has_turn_number
        
        if is_multi_turn:
            # test_case_id별로 그룹화
            test_case_id_col = df_columns_lower['test_case_id']
            turn_number_col = df_columns_lower['turn_number']
            
            # test_case_id별로 정렬 (turn_number 순서대로)
            test_cases = test_cases.sort_values([test_case_id_col, turn_number_col])
            test_case_groups = test_cases.groupby(test_case_id_col)
            
            total_scenarios = len(test_case_groups)
            total_turns = len(test_cases)
            print(f"📊 멀티턴 시나리오 테스트 시작: 총 {total_scenarios}개 시나리오, {total_turns}개 턴")
        else:
            # 기존 방식 (단일 턴)
            total_cases = len(test_cases)
            print(f"📊 단일 턴 테스트 시작: 총 {total_cases}개 케이스")
        
        start_time = time_module.time()
        
        try:
            self.start_browser()
            print("✅ 브라우저 준비 완료, 테스트 시작")
            
            if is_multi_turn:
                # 멀티턴 시나리오 실행
                scenario_num = 0
                for test_case_id, group in test_case_groups:
                    scenario_num += 1
                    scenario_start_time = time_module.time()
                    
                    # 시나리오의 턴들을 turn_number 순서대로 정렬
                    scenario_turns = group.sort_values(turn_number_col)
                    total_turns_in_scenario = len(scenario_turns)
                    
                    print(f"\n{'='*60}")
                    print(f"시나리오 {scenario_num}/{total_scenarios}: test_case_id={test_case_id} ({total_turns_in_scenario}턴)")
                    print(f"{'='*60}")
                    
                    # 각 시나리오의 첫 번째 턴에서만 페이지 리셋 및 초기화
                    is_initialized = False
                    
                    for turn_idx, (turn_row_idx, turn_row) in enumerate(scenario_turns.iterrows()):
                        turn_number = turn_row[turn_number_col]
                        turn_num = turn_idx + 1
                        
                        # 진행 상황 업데이트
                        if progress_callback:
                            elapsed_time = time_module.time() - start_time
                            completed_turns = sum(len(g) for i, (_, g) in enumerate(test_case_groups) if i < scenario_num - 1) + turn_num
                            if completed_turns > 1:
                                avg_time_per_turn = elapsed_time / completed_turns
                                estimated_remaining = avg_time_per_turn * (total_turns - completed_turns)
                            else:
                                estimated_remaining = None
                            
                            progress_callback(
                                current=completed_turns,
                                total=total_turns,
                                elapsed_time=elapsed_time,
                                estimated_remaining=estimated_remaining
                            )
                        
                        print(f"\n  ┌─ Turn {turn_number} ({turn_num}/{total_turns_in_scenario})")
                        
                        # 첫 번째 턴에서만 페이지 리셋 및 초기화
                        # 같은 test_case_id 내에서는 세션 유지 (페이지 리셋 및 초기화 안 함)
                        if not is_initialized:
                            # 새로운 시나리오 시작 시에만 페이지 리셋
                            if scenario_num > 1:
                                print("  🔄 새로운 시나리오 시작 - 페이지 리셋")
                                self.reset_page()
                            
                            # 채팅 초기화 (첫 번째 턴에서만)
                            print("  🔧 채팅 초기화 중...")
                            self._initialize_chat_for_row(turn_row)
                            is_initialized = True
                            print("  ✅ 채팅 초기화 완료")
                            time.sleep(2)
                        else:
                            # 같은 시나리오 내의 후속 턴 - 세션 유지, 초기화 없음
                            print(f"  ℹ️ 같은 시나리오 내 후속 턴 - 세션 유지 (초기화 없음)")
                        
                        # 턴 실행 (기존 대화 세션에서 계속)
                        turn_result = self._execute_turn(turn_row, turn_number, test_case_id)
                        results.append(turn_result)
                        
                        verdict = turn_result.get('verdict', turn_result.get('pass/fail', 'FAIL'))
                        print(f"  └─ Turn {turn_number} 완료: {verdict}")
                    
                    scenario_elapsed = time_module.time() - scenario_start_time
                    print(f"\n✅ 시나리오 {scenario_num} 완료 (소요: {scenario_elapsed:.1f}초)")
                
            else:
                # 기존 방식 (단일 턴)
                for idx, row in test_cases.iterrows():
                    case_num = idx + 1
                    case_start_time = time_module.time()
                    
                    # 진행 상황 업데이트
                    if progress_callback:
                        elapsed_time = time_module.time() - start_time
                        if case_num > 1:
                            avg_time_per_case = elapsed_time / (case_num - 1)
                            estimated_remaining = avg_time_per_case * (total_cases - case_num)
                        else:
                            estimated_remaining = None
                        
                        progress_callback(
                            current=case_num,
                            total=total_cases,
                            elapsed_time=elapsed_time,
                            estimated_remaining=estimated_remaining
                        )
                    try:
                        print(f"\n{'='*60}")
                        print(f"테스트 케이스 {idx + 1}/{len(test_cases)}")
                        print(f"{'='*60}")
                        
                        # 각 테스트 케이스마다 페이지 리셋 (첫 번째 케이스 제외)
                        if idx > 0:
                            self.reset_page()
                        
                        # 각 테스트 케이스마다 채팅 초기화
                        print("🔧 채팅 초기화 중...")
                        self._initialize_chat_for_row(row)
                        print("✅ 채팅 초기화 완료")
                        time.sleep(2)  # 초기화 후 안정화 대기
                        
                        # 턴 실행 (단일 턴이므로 turn_number는 None)
                        turn_result = self._execute_turn(row, turn_number=None, test_case_id=None)
                        results.append(turn_result)
                        
                        case_elapsed = time_module.time() - case_start_time
                        message_display = str(self._get_column_value(row, 'message', ''))[:50]
                        pass_fail = turn_result.get('verdict', turn_result.get('pass/fail', 'FAIL'))
                        print(f"({case_num}/{total_cases}) 완료: {message_display}... - {pass_fail} (소요: {case_elapsed:.1f}초)")
                        
                        # 최종 진행 상황 업데이트
                        if progress_callback:
                            elapsed_time = time_module.time() - start_time
                            if case_num < total_cases:
                                avg_time_per_case = elapsed_time / case_num
                                estimated_remaining = avg_time_per_case * (total_cases - case_num)
                            else:
                                estimated_remaining = 0
                            
                            progress_callback(
                                current=case_num,
                                total=total_cases,
                                elapsed_time=elapsed_time,
                                estimated_remaining=estimated_remaining
                            )
                        
                    except Exception as e:
                        # 테스트 케이스 실행 중 오류 발생
                        print(f"테스트 케이스 {idx+1} 실행 중 오류: {e}")
                        
                        # is_driving 값 처리
                        is_driving_value = self._get_column_value(row, 'is_driving', False)
                        if isinstance(is_driving_value, str):
                            is_driving_value = is_driving_value.upper() == 'TRUE'
                        elif isinstance(is_driving_value, (int, float)):
                            is_driving_value = bool(is_driving_value)
                        else:
                            is_driving_value = bool(is_driving_value)
                        
                        result_row = {
                            'test_case_id': '',
                            'turn_number': '',
                            'user_id': str(self._get_column_value(row, 'user_id', '')),
                            'lng': self._get_column_value(row, 'lng', ''),
                            'lat': self._get_column_value(row, 'lat', ''),
                            'is_driving': is_driving_value,
                            'message': str(self._get_column_value(row, 'message', '')),
                            'tts_expected': str(self._get_column_value(row, 'tts_expected', '')),
                            'latency': None,
                            'latency_text': '',
                            'response_structured': '',
                            'raw_json': '',
                            'tts_actual': '',
                            'action_name': '',
                            'action_data': '',
                            'next_step': '',
                            'verdict': 'FAIL',
                            'pass/fail': 'FAIL',  # 하위 호환성
                            'similarity_score': 0.0,
                            'fail_reason': f'테스트 실행 오류: {str(e)}',
                            'scores': json_module.dumps({'tts': 0.0, 'action_name': 0.0, 'action_data': 0.0, 'next_step': 0.0})
                        }
                        results.append(result_row)
        
        finally:
            self.close_browser()
        
        return pd.DataFrame(results)

