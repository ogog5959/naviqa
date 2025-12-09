/**
 * 테스트 대상 페이지에서 자동 실행하는 스크립트
 * 이 스크립트는 테스트 대상 페이지에 직접 주입됩니다
 */
(function() {
    console.log('자동화 스크립트 로드됨 - 현재 URL:', window.location.href);
    
    function runAutomation() {
        try {
            console.log('runAutomation 함수 호출됨');
            const shouldRun = localStorage.getItem('automation_shouldRun');
            console.log('shouldRun 확인:', shouldRun);
            
            if (shouldRun !== 'true') {
                console.log('자동화 실행 안 함 - shouldRun이 true가 아님');
                return;
            }
            
            console.log('자동화 실행 시작');
            const testCasesData = JSON.parse(localStorage.getItem('automation_testCases') || '[]');
            const baseUrlValue = localStorage.getItem('automation_baseUrl') || '';
            const jsCodeBase64 = localStorage.getItem('automation_jsCode') || '';
            
            console.log('📊 데이터 확인:', {
                testCasesCount: testCasesData.length,
                baseUrl: baseUrlValue,
                hasJsCode: !!jsCodeBase64
            });
            
            // 테스트 케이스 개수를 명확히 표시
            console.log(`✅ 테스트 케이스 ${testCasesData.length}개가 로드되었습니다.`);
            if (testCasesData.length > 0) {
                console.log('📋 첫 번째 테스트 케이스:', testCasesData[0]);
            }
            
            if (!testCasesData.length || !baseUrlValue || !jsCodeBase64) {
                console.error('필요한 데이터가 없습니다');
                alert('❌ 자동화 데이터가 없습니다. 다시 시도해주세요.');
                return;
            }
            
            // 이미 주입되었는지 확인
            if (document.getElementById('automation-script-injected')) {
                console.log('스크립트가 이미 주입됨');
                return;
            }
            
            // JavaScript 코드 로드
            const script = document.createElement('script');
            script.id = 'automation-script-injected';
            
            // BrowserAutomation 클래스 로드
            const automationScript = atob(jsCodeBase64);
            const testCasesJson = JSON.stringify(testCasesData);
            const baseUrlValueStr = baseUrlValue.replace(/"/g, '\\"');
            const testScript = automationScript + 
                '(async function() {' +
                '    console.log("BrowserAutomation 초기화 시작");' +
                '    if (typeof BrowserAutomation === "undefined") {' +
                '        console.error("BrowserAutomation 클래스가 정의되지 않음");' +
                '        alert("❌ BrowserAutomation 클래스를 찾을 수 없습니다.");' +
                '        return;' +
                '    }' +
                '    const automation = new BrowserAutomation();' +
                '    automation.baseUrl = "' + baseUrlValueStr + '";' +
                '    const testCases = ' + testCasesJson + ';' +
                '    console.log("테스트 케이스:", testCases.length, "개");' +
                '    console.log("baseUrl:", automation.baseUrl);' +
                '    function updateProgress(current, total, message) {' +
                '        console.log(message + " (" + current + "/" + total + ")");' +
                '    }' +
                '    try {' +
                '        console.log("페이지 준비 대기 중...");' +
                '        await new Promise(resolve => {' +
                '            if (document.readyState === "complete") {' +
                '                setTimeout(resolve, 5000);' +
                '            } else {' +
                '                window.addEventListener("load", () => {' +
                '                    setTimeout(resolve, 5000);' +
                '                });' +
                '            }' +
                '        });' +
                '        console.log("테스트 시작");' +
                '        const result = await automation.runTests(testCases, updateProgress);' +
                '        if (result.success) {' +
                '            console.log("테스트 성공!");' +
                '            const blob = new Blob([JSON.stringify(result.results)], {type: "application/json"});' +
                '            const url = URL.createObjectURL(blob);' +
                '            const a = document.createElement("a");' +
                '            a.href = url;' +
                '            a.download = "test_results.json";' +
                '            a.click();' +
                '            alert("✅ 테스트 완료! 결과 파일이 다운로드되었습니다.");' +
                '            localStorage.removeItem("automation_shouldRun");' +
                '        } else {' +
                '            console.error("테스트 실패:", result.error);' +
                '            alert("❌ 테스트 실패: " + result.error);' +
                '        }' +
                '    } catch (error) {' +
                '        console.error("테스트 오류:", error);' +
                '        alert("❌ 오류: " + error.message);' +
                '    }' +
                '})();';
            
            script.textContent = testScript;
            document.body.appendChild(script);
            console.log('스크립트 주입 완료');
        } catch(error) {
            console.error('자동화 실행 오류:', error);
            alert('❌ 자동화 실행 오류: ' + error.message);
        }
    }
    
    // 여러 시점에서 실행 시도
    if (document.readyState === 'complete') {
        console.log('문서 이미 로드됨 - 5초 후 실행');
        setTimeout(runAutomation, 5000);
    } else {
        console.log('문서 로드 대기 중...');
        window.addEventListener('load', function() {
            console.log('load 이벤트 발생 - 5초 후 실행');
            setTimeout(runAutomation, 5000);
        });
    }
    
    // DOMContentLoaded에서도 시도
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', function() {
            console.log('DOMContentLoaded 이벤트 발생 - 5초 후 실행');
            setTimeout(runAutomation, 5000);
        });
    } else {
        setTimeout(runAutomation, 5000);
    }
    
    // 추가 시도 (10초 후, 15초 후)
    setTimeout(runAutomation, 10000);
    setTimeout(runAutomation, 15000);
})();


