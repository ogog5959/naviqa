/**
 * 브라우저 자동화 스크립트
 * 사용자의 브라우저에서 직접 실행되어 테스트를 수행합니다.
 */
class BrowserAutomation {
    constructor(baseUrl) {
        this.baseUrl = baseUrl || 'https://navi-agent-adk-api.dev.onkakao.net/streamlit/';
        this.isInitialized = false;
        this.currentTestIndex = 0;
        this.results = [];
    }

    /**
     * 테스트 케이스 실행
     */
    async runTests(testCases, progressCallback) {
        this.results = [];
        this.currentTestIndex = 0;
        this.isInitialized = false;

        try {
            // 현재 페이지가 이미 테스트 대상 페이지인지 확인
            // (iframe 내부에서 실행되는 경우)
            await this.waitForCurrentPageLoad();
            
            // 각 테스트 케이스 실행
            for (let i = 0; i < testCases.length; i++) {
                this.currentTestIndex = i;
                const testCase = testCases[i];

                if (progressCallback) {
                    progressCallback(i + 1, testCases.length, `테스트 케이스 ${i + 1}/${testCases.length} 실행 중...`);
                }

                // 최초 1회만 초기화
                if (!this.isInitialized) {
                    await this.initializeChat(testCase);
                    this.isInitialized = true;
                    await this.sleep(2000); // 초기화 후 안정화 대기
                }

                // 메시지 전송 및 결과 수집
                const result = await this.sendMessageAndCollectResults(testCase, i);
                this.results.push(result);

                // 다음 테스트를 위한 대기
                await this.sleep(1000);
            }

            // 테스트 완료 후 결과 반환
            return {
                success: true,
                results: this.results
            };
        } catch (error) {
            return {
                success: false,
                error: error.message,
                results: this.results
            };
        }
    }
    
    /**
     * 현재 페이지가 로드될 때까지 대기
     */
    waitForCurrentPageLoad() {
        return new Promise((resolve, reject) => {
            // 이미 로드된 경우
            if (document.readyState === 'complete') {
                setTimeout(resolve, 1000); // 추가 안정화 대기
                return;
            }
            
            // 로드 이벤트 대기
            window.addEventListener('load', () => {
                setTimeout(resolve, 1000); // 추가 안정화 대기
            });
            
            // 타임아웃
            setTimeout(() => {
                if (document.readyState === 'complete') {
                    resolve();
                } else {
                    reject(new Error('페이지 로드 타임아웃'));
                }
            }, 30000);
        });
    }


    /**
     * 채팅 초기화
     */
    async initializeChat(testCase) {
        try {
            console.log('채팅 초기화 시작', testCase);
            
            // 페이지가 완전히 로드될 때까지 대기
            await this.waitForPageReady();
            await this.sleep(2000); // 더 긴 대기 시간
            
            console.log('user_id 입력 시도:', testCase.user_id);
            // user_id 입력 (재시도 포함)
            await this.fillInputWithRetry('user_id', String(testCase.user_id), 5);
            await this.sleep(1000);

            console.log('lat 입력 시도:', testCase.lat);
            // lat 입력
            await this.fillInputWithRetry('lat', String(testCase.lat), 5);
            await this.sleep(1000);

            console.log('lng 입력 시도:', testCase.lng);
            // lng 입력
            await this.fillInputWithRetry('lng', String(testCase.lng), 5);
            await this.sleep(1000);

            console.log('is_driving 체크박스 시도:', testCase.is_driving);
            // is_driving 체크박스
            const isDriving = testCase.is_driving === true || 
                             String(testCase.is_driving).toLowerCase() === 'true';
            await this.toggleCheckboxWithRetry('is_driving', isDriving, 5);
            await this.sleep(1000);

            console.log('Save & Start Chat 버튼 클릭 시도');
            // "Save & Start Chat" 버튼 클릭
            await this.clickButton('Save & Start Chat');
            await this.sleep(3000); // 더 긴 대기 시간
            console.log('채팅 초기화 완료');
        } catch (error) {
            console.error('채팅 초기화 오류:', error);
            throw new Error(`채팅 초기화 실패: ${error.message}`);
        }
    }
    
    /**
     * 페이지가 준비될 때까지 대기
     */
    async waitForPageReady() {
        return new Promise((resolve, reject) => {
            let attempts = 0;
            const maxAttempts = 100; // 10초 대기
            
            const checkReady = () => {
                attempts++;
                try {
                    if (document && document.readyState === 'complete') {
                        // 입력 필드가 있는지 확인
                        const inputs = document.querySelectorAll('input');
                        console.log(`페이지 준비 확인 (시도 ${attempts}/${maxAttempts}): 입력 필드 ${inputs.length}개 발견`);
                        if (inputs.length > 0) {
                            // 추가로 body가 있는지 확인
                            if (document.body) {
                                console.log('페이지 준비 완료');
                                resolve();
                                return;
                            }
                        }
                    }
                    
                    if (attempts >= maxAttempts) {
                        console.error('페이지 로드 타임아웃');
                        reject(new Error('페이지 로드 타임아웃: 입력 필드를 찾을 수 없습니다'));
                        return;
                    }
                    
                    setTimeout(checkReady, 100);
                } catch (e) {
                    if (attempts >= maxAttempts) {
                        console.error('페이지 접근 실패:', e);
                        reject(new Error(`페이지 접근 실패: ${e.message}`));
                        return;
                    }
                    setTimeout(checkReady, 100);
                }
            };
            
            checkReady();
        });
    }
    
    /**
     * 재시도 로직이 포함된 입력 필드 채우기
     */
    async fillInputWithRetry(label, value, maxRetries = 3) {
        let lastError = null;
        for (let i = 0; i < maxRetries; i++) {
            try {
                await this.fillInput(label, value);
                return; // 성공
            } catch (error) {
                lastError = error;
                if (i < maxRetries - 1) {
                    await this.sleep(500); // 재시도 전 대기
                }
            }
        }
        throw lastError;
    }
    
    /**
     * 재시도 로직이 포함된 체크박스 토글
     */
    async toggleCheckboxWithRetry(label, checked, maxRetries = 3) {
        let lastError = null;
        for (let i = 0; i < maxRetries; i++) {
            try {
                await this.toggleCheckbox(label, checked);
                return; // 성공
            } catch (error) {
                lastError = error;
                if (i < maxRetries - 1) {
                    await this.sleep(500); // 재시도 전 대기
                }
            }
        }
        throw lastError;
    }

    /**
     * 입력 필드 채우기
     */
    async fillInput(label, value) {
        try {
            let input = null;
            
            // 방법 1: aria-label로 찾기
            input = document.querySelector(`input[aria-label="${label}"]`);
            
            // 방법 2: aria-label이 없으면 name 속성으로 찾기
            if (!input) {
                input = document.querySelector(`input[name="${label}"]`);
            }
            
            // 방법 3: label 텍스트로 찾기 (Streamlit의 경우)
            if (!input) {
                const labels = Array.from(document.querySelectorAll('label'));
                const labelElement = labels.find(l => {
                    const text = l.textContent || '';
                    return text.toLowerCase().includes(label.toLowerCase()) || 
                           text.toLowerCase().includes(label.replace('_', ' ').toLowerCase());
                });
                if (labelElement) {
                    // label의 for 속성으로 input 찾기
                    const forId = labelElement.getAttribute('for');
                    if (forId) {
                        input = document.querySelector(`input#${forId}`);
                    }
                    // for가 없으면 label 다음 형제 요소 찾기
                    if (!input) {
                        input = labelElement.nextElementSibling?.querySelector('input');
                    }
                    // label의 부모 요소에서 input 찾기
                    if (!input) {
                        input = labelElement.parentElement?.querySelector('input');
                    }
                }
            }
            
            // 방법 4: placeholder로 찾기
            if (!input) {
                input = document.querySelector(`input[placeholder*="${label}"]`);
            }
            
            // 방법 5: 모든 input을 순회하며 주변 텍스트로 찾기
            if (!input) {
                const allInputs = Array.from(document.querySelectorAll('input[type="text"], input[type="number"]'));
                for (const inp of allInputs) {
                    // 부모 요소에서 label 텍스트 확인
                    const parent = inp.closest('div[data-testid="stTextInput"], div[data-baseweb="input"]');
                    if (parent) {
                        const parentText = parent.textContent || '';
                        if (parentText.toLowerCase().includes(label.toLowerCase()) ||
                            parentText.toLowerCase().includes(label.replace('_', ' ').toLowerCase())) {
                            input = inp;
                            break;
                        }
                    }
                }
            }
            
            // 방법 6: Streamlit의 특정 구조로 찾기 (data-testid 사용)
            if (!input) {
                // Streamlit은 보통 input을 특정 구조로 감싸므로, 모든 input을 확인
                const allInputs = Array.from(document.querySelectorAll('input'));
                for (const inp of allInputs) {
                    // 위로 올라가면서 label이나 텍스트 찾기
                    let element = inp;
                    for (let i = 0; i < 5 && element; i++) {
                        element = element.parentElement;
                        if (element) {
                            const text = element.textContent || '';
                            if (text.toLowerCase().includes(label.toLowerCase()) ||
                                text.toLowerCase().includes(label.replace('_', ' ').toLowerCase())) {
                                input = inp;
                                break;
                            }
                        }
                    }
                    if (input) break;
                }
            }
            
            if (!input) {
                // 디버깅: 모든 input 필드 정보 출력
                const allInputs = Array.from(document.querySelectorAll('input'));
                const inputInfo = allInputs.map(inp => {
                    const parent = inp.closest('div');
                    return {
                        type: inp.type,
                        name: inp.name,
                        id: inp.id,
                        ariaLabel: inp.getAttribute('aria-label'),
                        placeholder: inp.placeholder,
                        parentText: parent ? (parent.textContent || '').substring(0, 100) : ''
                    };
                });
                console.error(`입력 필드 찾기 실패: ${label}`, inputInfo);
                throw new Error(`입력 필드를 찾을 수 없습니다: ${label}. 사용 가능한 필드: ${JSON.stringify(inputInfo.map(i => i.ariaLabel || i.name || i.parentText.substring(0, 30)))}`);
            }
            
            input.focus();
            await this.sleep(100);
            input.value = value;
            input.dispatchEvent(new Event('input', { bubbles: true }));
            input.dispatchEvent(new Event('change', { bubbles: true }));
            input.dispatchEvent(new KeyboardEvent('keydown', { bubbles: true, key: 'Enter' }));
            input.dispatchEvent(new KeyboardEvent('keyup', { bubbles: true, key: 'Enter' }));
            await this.sleep(200);
        } catch (error) {
            throw new Error(`입력 필드 채우기 실패 (${label}): ${error.message}`);
        }
    }

    /**
     * 체크박스 토글
     */
    async toggleCheckbox(label, checked) {
        try {
            let checkbox = null;
            
            // 방법 1: aria-label로 찾기
            checkbox = document.querySelector(`input[aria-label="${label}"][type="checkbox"]`);
            
            // 방법 2: name 속성으로 찾기
            if (!checkbox) {
                checkbox = document.querySelector(`input[name="${label}"][type="checkbox"]`);
            }
            
            // 방법 3: label 텍스트로 찾기
            if (!checkbox) {
                const labels = Array.from(document.querySelectorAll('label'));
                const labelElement = labels.find(l => {
                    const text = l.textContent || '';
                    return text.toLowerCase().includes(label.toLowerCase()) || 
                           text.toLowerCase().includes(label.replace('_', ' ').toLowerCase());
                });
                if (labelElement) {
                    const forId = labelElement.getAttribute('for');
                    if (forId) {
                        checkbox = document.querySelector(`input#${forId}[type="checkbox"]`);
                    }
                    if (!checkbox) {
                        checkbox = labelElement.parentElement?.querySelector('input[type="checkbox"]');
                    }
                }
            }
            
            // 방법 4: 모든 체크박스를 순회하며 주변 텍스트로 찾기
            if (!checkbox) {
                const allCheckboxes = Array.from(document.querySelectorAll('input[type="checkbox"]'));
                for (const cb of allCheckboxes) {
                    const parent = cb.closest('div');
                    if (parent) {
                        const parentText = parent.textContent || '';
                        if (parentText.toLowerCase().includes(label.toLowerCase()) ||
                            parentText.toLowerCase().includes(label.replace('_', ' ').toLowerCase())) {
                            checkbox = cb;
                            break;
                        }
                    }
                }
            }
            
            if (!checkbox) {
                throw new Error(`체크박스를 찾을 수 없습니다: ${label}`);
            }
            
            if (checkbox.checked !== checked) {
                checkbox.click();
                await this.sleep(200);
            }
        } catch (error) {
            throw new Error(`체크박스 토글 실패 (${label}): ${error.message}`);
        }
    }

    /**
     * 버튼 클릭
     */
    async clickButton(buttonText) {
        try {
            const buttons = Array.from(document.querySelectorAll('button'));
            const button = buttons.find(btn => btn.textContent.trim().includes(buttonText));
            if (!button) {
                throw new Error(`버튼을 찾을 수 없습니다: ${buttonText}`);
            }
            button.click();
            await this.sleep(500);
        } catch (error) {
            throw new Error(`버튼 클릭 실패 (${buttonText}): ${error.message}`);
        }
    }

    /**
     * 메시지 전송 및 결과 수집
     */
    async sendMessageAndCollectResults(testCase, index) {
        try {
            // 메시지 입력
            const messageInput = document.querySelector('input[aria-label*="message"], textarea[aria-label*="message"]');
            if (!messageInput) {
                throw new Error('메시지 입력 필드를 찾을 수 없습니다');
            }

            // 입력 필드 초기화
            messageInput.focus();
            messageInput.value = '';
            messageInput.dispatchEvent(new Event('input', { bubbles: true }));

            // 새 메시지 입력
            await this.sleep(500);
            messageInput.value = String(testCase.message);
            messageInput.dispatchEvent(new Event('input', { bubbles: true }));
            messageInput.dispatchEvent(new Event('change', { bubbles: true }));
            await this.sleep(500);

            // "Send Message" 버튼 클릭
            await this.clickButton('Send Message');

            // 응답 대기 (최대 10초)
            await this.sleep(3000); // 초기 대기

            // 결과 수집
            const latency = await this.extractLatency();
            const responseFull = await this.extractResponseFull();
            const rawJson = await this.extractRawJson();
            const tts = await this.extractTTS(rawJson);

            // 유사도 계산 및 Pass/Fail 판정
            const similarity = this.calculateSimilarity(tts, String(testCase.tts_expected || ''));
            const passFail = this.determinePassFail(
                String(testCase.message),
                tts,
                String(testCase.tts_expected || ''),
                true
            );

            return {
                user_id: String(testCase.user_id),
                lng: parseFloat(testCase.lng),
                lat: parseFloat(testCase.lat),
                message: String(testCase.message),
                tts_expected: String(testCase.tts_expected || ''),
                latency: latency,
                response_full: responseFull,
                raw_json: rawJson,
                tts_actual: tts,
                similarity_score: similarity,
                'pass/fail': passFail.isPass ? 'PASS' : 'FAIL',
                fail_reason: passFail.isPass ? null : passFail.reason
            };
        } catch (error) {
            return {
                user_id: String(testCase.user_id || ''),
                lng: parseFloat(testCase.lng || 0),
                lat: parseFloat(testCase.lat || 0),
                message: String(testCase.message || ''),
                tts_expected: String(testCase.tts_expected || ''),
                latency: null,
                response_full: '',
                raw_json: '',
                tts_actual: '',
                similarity_score: 0.0,
                'pass/fail': 'FAIL',
                fail_reason: `오류: ${error.message}`,
                error: error.message
            };
        }
    }

    /**
     * 유사도 계산 (간단한 버전)
     */
    calculateSimilarity(text1, text2) {
        if (!text1 || !text2) return 0.0;
        if (text1 === text2) return 1.0;
        
        const longer = text1.length > text2.length ? text1 : text2;
        const shorter = text1.length > text2.length ? text2 : text1;
        
        if (longer.length === 0) return 1.0;
        
        // 공통 문자 기반 유사도
        let matches = 0;
        for (let i = 0; i < shorter.length; i++) {
            if (longer.includes(shorter[i])) matches++;
        }
        
        return matches / longer.length;
    }

    /**
     * Pass/Fail 판정 (간단한 버전)
     */
    determinePassFail(message, ttsActual, ttsExpected, useContext) {
        const similarity = this.calculateSimilarity(ttsActual, ttsExpected);
        
        if (similarity >= 0.7) {
            return { isPass: true, reason: `유사도: ${(similarity * 100).toFixed(1)}%` };
        }
        
        // 키워드 기반 매칭
        const keywords = (ttsExpected.match(/[가-힣a-zA-Z0-9]+/g) || []).map(w => w.toLowerCase());
        const actualWords = (ttsActual.match(/[가-힣a-zA-Z0-9]+/g) || []).map(w => w.toLowerCase());
        const matchedKeywords = keywords.filter(k => actualWords.includes(k));
        
        if (matchedKeywords.length / keywords.length >= 0.6 && similarity >= 0.5) {
            return { isPass: true, reason: `키워드 매칭 및 유사도: ${(similarity * 100).toFixed(1)}%` };
        }
        
        return { isPass: false, reason: `유사도 부족: ${(similarity * 100).toFixed(1)}%` };
    }

    /**
     * Latency 추출
     */
    async extractLatency() {
        try {
            const markdownElements = document.querySelectorAll('[data-testid="stMarkdownContainer"]');
            for (const el of markdownElements) {
                const text = el.textContent || '';
                if (text.includes('Response received')) {
                    // 숫자 추출 (ms 단위)
                    const match = text.match(/(\d+(?:\.\d+)?)\s*ms/i);
                    if (match) {
                        return parseFloat(match[1]);
                    }
                }
            }
            return null;
        } catch (error) {
            return null;
        }
    }

    /**
     * 전체 응답 추출
     */
    async extractResponseFull() {
        try {
            const markdownElements = document.querySelectorAll('[data-testid="stMarkdownContainer"]');
            const responses = [];
            for (const el of markdownElements) {
                const text = el.textContent || '';
                if (text.trim()) {
                    responses.push(text.trim());
                }
            }
            return responses.join('\n\n');
        } catch (error) {
            return '';
        }
    }

    /**
     * Raw JSON 추출
     */
    async extractRawJson() {
        try {
            // "Raw JSON" expander 찾기
            const expanders = document.querySelectorAll('[data-testid="stExpander"]');
            for (const expander of expanders) {
                const header = expander.querySelector('summary, button');
                if (header && header.textContent.includes('Raw JSON')) {
                    // Expander 열기
                    if (expander.getAttribute('open') === null) {
                        header.click();
                        await this.sleep(1000);
                    }

                    // JSON 내용 찾기
                    const codeBlock = expander.querySelector('code, pre');
                    if (codeBlock) {
                        return codeBlock.textContent || '';
                    }
                }
            }
            return '';
        } catch (error) {
            return '';
        }
    }

    /**
     * TTS 추출 (raw_json에서)
     */
    async extractTTS(rawJson) {
        try {
            if (rawJson) {
                const jsonData = JSON.parse(rawJson);
                return jsonData.tts || '';
            }
            return '';
        } catch (error) {
            return '';
        }
    }

    /**
     * 유틸리티: 대기
     */
    sleep(ms) {
        return new Promise(resolve => setTimeout(resolve, ms));
    }
}

// 전역으로 export
if (typeof module !== 'undefined' && module.exports) {
    module.exports = BrowserAutomation;
}

