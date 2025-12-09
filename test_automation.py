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
            time.sleep(2)  # 기본 대기
            
            # 메시지 입력창 찾기 (더 정확하게, 여러 방법 시도)
            message_input = None
            max_input_retries = 5
            
            for retry in range(max_input_retries):
                try:
                    # 방법 1: aria-label로 찾기
                    message_input = self.page.locator('textarea[aria-label="Your Message"]')
                    if message_input.count() > 0:
                        print(f"  ✅ 메시지 입력창 찾음 (aria-label, 시도 {retry + 1})")
                        break
                    
                    # 방법 2: 모든 textarea 중 마지막 것 (가장 최근)
                    all_textareas = self.page.locator('textarea')
                    if all_textareas.count() > 0:
                        message_input = all_textareas.last
                        print(f"  ✅ 메시지 입력창 찾음 (마지막 textarea, 시도 {retry + 1})")
                        break
                    
                    # 방법 3: placeholder로 찾기
                    message_input = self.page.locator('textarea[placeholder*="message" i], textarea[placeholder*="Message" i]')
                    if message_input.count() > 0:
                        print(f"  ✅ 메시지 입력창 찾음 (placeholder, 시도 {retry + 1})")
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
            
            # "Send Message" 버튼 클릭
            send_button = self.page.locator('button:has-text("Send Message")')
            if send_button.count() > 0:
                send_button.first.click()
                print(f"  ✅ Send 버튼 클릭")
            else:
                # Enter 키로 전송 시도
                message_input.first.press('Enter')
                print(f"  ✅ Enter 키로 전송")
            
            # 응답이 완전히 로드될 때까지 대기 (latency 최대 7초 + 여유시간 고려)
            print(f"  ⏳ 응답 대기 중... (latency 최대 7초 고려)")
            
            # 1. latency 표시 대기 (최대 15초 = 7초 latency + 8초 여유)
            try:
                self.page.wait_for_selector(
                    'div[data-testid="stMarkdownContainer"]:has-text("Response received")',
                    timeout=15000
                )
                print(f"  ✅ Response received 표시 확인")
            except PlaywrightTimeoutError:
                print(f"  ⚠️ Response received 표시 타임아웃 (계속 진행)")
            
            # 2. Raw JSON expander가 나타날 때까지 대기 (추가 확인, 최대 10초)
            try:
                self.page.wait_for_selector(
                    'div[data-testid="stExpander"]:has-text("Raw JSON")',
                    timeout=10000,
                    state="visible"
                )
                print(f"  ✅ Raw JSON expander 확인")
            except PlaywrightTimeoutError:
                print(f"  ⚠️ Raw JSON expander 타임아웃 (계속 진행)")
            
            # 3. 충분한 렌더링 대기 (latency 7초 + 추가 처리 시간 고려)
            print(f"  ⏳ 응답 렌더링 대기 중... (8초)")
            time.sleep(8)  # latency 최대 7초 + 렌더링 시간 고려
            
            # 4. 스크롤을 맨 아래로 (최신 응답 확인)
            self.page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            time.sleep(1)
            
            print(f"  📥 결과 추출 시작...")
            
            # 결과 추출 (여러 번 시도)
            max_retries = 3
            for retry in range(max_retries):
                try:
                    results['latency'] = self.extract_latency()
                    results['response_structured'] = self.extract_expander_content('Response (structured)')
                    results['raw_json'] = self.extract_expander_content('Raw JSON')
                    results['tts'] = self.extract_tts_from_raw_json(results['raw_json'])
                    
                    # 결과가 있는지 확인
                    if results['raw_json'] or results['response_structured']:
                        print(f"  ✅ 결과 추출 성공 (시도 {retry + 1}/{max_retries})")
                        break
                    else:
                        print(f"  ⚠️ 결과가 비어있음, 재시도 중... (시도 {retry + 1}/{max_retries})")
                        time.sleep(2)
                except Exception as e:
                    print(f"  ⚠️ 결과 추출 오류 (시도 {retry + 1}/{max_retries}): {e}")
                    if retry < max_retries - 1:
                        time.sleep(2)
            
            print(f"  📊 추출된 결과: latency={results['latency'][:30] if results['latency'] else 'N/A'}, raw_json_len={len(results['raw_json'])}, tts_len={len(results['tts'])}")
            
            # 다음 테스트를 위한 대기 (입력 필드가 다시 활성화될 때까지)
            print(f"  ⏳ 다음 테스트 준비 대기 중... (3초)")
            time.sleep(3)
            
        except Exception as e:
            import traceback
            error_trace = traceback.format_exc()
            print(f"  ❌ 메시지 전송 및 결과 수집 중 오류 발생: {e}")
            print(f"  {error_trace}")
            results['error'] = str(e)
        
        return results
    
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
        
        Args:
            test_cases: 테스트 케이스가 담긴 DataFrame
            progress_callback: 진행 상황 콜백 함수 (current, total, elapsed_time, estimated_remaining)
        
        Returns:
            결과가 포함된 DataFrame
        """
        results = []
        import time as time_module
        
        total_cases = len(test_cases)
        start_time = time_module.time()
        
        print(f"📊 테스트 시작: 총 {total_cases}개 케이스")
        
        try:
            self.start_browser()
            print("✅ 브라우저 준비 완료, 테스트 시작")
            
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
                    
                    # 컬럼명 대소문자 구분 없이 값을 가져오는 헬퍼 함수
                    def get_column_value(df_row, col_name, default=''):
                        """컬럼명 대소문자 구분 없이 값을 가져옵니다."""
                        for key in df_row.index:
                            if key.lower() == col_name.lower():
                                return df_row[key]
                        return df_row.get(col_name, default)
                    
                    # is_driving 값 처리 (컬럼명 대소문자 구분 없이 처리)
                    # 'is_driving', 'IS_DRIVING' 등 모두 지원
                    is_driving_value = get_column_value(row, 'is_driving', False)
                    
                    # 값이 문자열인 경우 'TRUE', 'true', 'True' 등을 처리
                    if isinstance(is_driving_value, str):
                        is_driving_value = is_driving_value.upper() == 'TRUE'
                    # 값이 숫자인 경우 (1 = True, 0 = False)
                    elif isinstance(is_driving_value, (int, float)):
                        is_driving_value = bool(is_driving_value)
                    # 이미 boolean인 경우 그대로 사용
                    else:
                        is_driving_value = bool(is_driving_value)
                    
                    self.initialize_chat(
                        user_id=str(get_column_value(row, 'user_id', '')),
                        lat=float(get_column_value(row, 'lat', 0)),
                        lng=float(get_column_value(row, 'lng', 0)),
                        is_driving=is_driving_value
                    )
                    print("✅ 채팅 초기화 완료")
                    time.sleep(2)  # 초기화 후 안정화 대기
                    
                    # 메시지 전송 및 결과 수집 (인덱스 전달)
                    # 컬럼명 대소문자 구분 없이 처리
                    message_value = get_column_value(row, 'message')
                    test_results = self.send_message_and_collect_results(str(message_value), idx)
                    
                    # Raw JSON에서 TTS 추출 (비교용)
                    tts_from_raw_json = self.extract_tts_from_raw_json(test_results['raw_json'])
                    
                    # TTS 비교 및 Pass/Fail 판정 (raw_json의 tts와 tts_expected 비교)
                    # 맥락 기반 판단을 위해 message도 전달
                    tts_expected = str(get_column_value(row, 'tts_expected', ''))
                    user_message = str(get_column_value(row, 'message', ''))
                    similarity = calculate_similarity(tts_from_raw_json, tts_expected)
                    is_pass, reason = determine_pass_fail(user_message, tts_from_raw_json, tts_expected, use_context=True)
                    
                    # latency에서 숫자만 추출 (ms 단위)
                    latency_ms = None
                    if test_results['latency']:
                        import re
                        latency_match = re.search(r'(\d+)\s*ms', test_results['latency'])
                        if latency_match:
                            latency_ms = float(latency_match.group(1))
                    
                    # 결과 저장 (컬럼명 대소문자 구분 없이 처리)
                    result_row = {
                        'user_id': str(get_column_value(row, 'user_id', '')),  # np.int64 등 숫자 타입을 문자열로 변환
                        'lng': get_column_value(row, 'lng', ''),
                        'lat': get_column_value(row, 'lat', ''),
                        'message': get_column_value(row, 'message', ''),
                        'tts_expected': tts_expected,
                        'latency': latency_ms,
                        'latency_text': test_results['latency'],
                        'response_structured': test_results['response_structured'],
                        'raw_json': test_results['raw_json'],
                        'tts_actual': tts_from_raw_json,  # raw_json에서 추출한 TTS 사용
                        'pass/fail': 'PASS' if is_pass else 'FAIL',
                        'similarity_score': similarity,
                        'fail_reason': reason if not is_pass else ''
                    }
                    results.append(result_row)
                    
                    case_elapsed = time_module.time() - case_start_time
                    message_display = str(get_column_value(row, 'message'))[:50]
                    print(f"({case_num}/{total_cases}) 완료: {message_display}... - {'PASS' if is_pass else 'FAIL'} (소요: {case_elapsed:.1f}초)")
                    
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
                    # 컬럼명 대소문자 구분 없이 처리 (get_column_value는 위에서 정의됨)
                    result_row = {
                        'user_id': str(get_column_value(row, 'user_id', '')),  # np.int64 등 숫자 타입을 문자열로 변환
                        'lng': get_column_value(row, 'lng', ''),
                        'lat': get_column_value(row, 'lat', ''),
                        'message': get_column_value(row, 'message', ''),
                        'tts_expected': get_column_value(row, 'tts_expected', ''),
                        'latency': None,
                        'latency_text': '',
                        'response_structured': '',
                        'raw_json': '',
                        'tts_actual': '',
                        'pass/fail': 'FAIL',
                        'similarity_score': 0.0,
                        'fail_reason': f'테스트 실행 오류: {str(e)}'
                    }
                    results.append(result_row)
        
        finally:
            self.close_browser()
        
        return pd.DataFrame(results)

