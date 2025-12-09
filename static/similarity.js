/**
 * 유사도 계산 및 Pass/Fail 판정 (JavaScript 버전)
 */

/**
 * 두 텍스트의 유사도 계산 (SequenceMatcher 알고리즘)
 */
function calculateSimilarity(text1, text2) {
    if (!text1 || !text2) return 0.0;
    if (text1 === text2) return 1.0;
    
    // 간단한 유사도 계산 (Jaro-Winkler 유사)
    const longer = text1.length > text2.length ? text1 : text2;
    const shorter = text1.length > text2.length ? text2 : text1;
    
    if (longer.length === 0) return 1.0;
    
    // 공통 문자 찾기
    let matches = 0;
    const window = Math.floor(longer.length / 2) - 1;
    const shortMatches = new Array(shorter.length).fill(false);
    const longMatches = new Array(longer.length).fill(false);
    
    for (let i = 0; i < shorter.length; i++) {
        const start = Math.max(0, i - window);
        const end = Math.min(i + window + 1, longer.length);
        
        for (let j = start; j < end; j++) {
            if (longMatches[j] || shorter[i] !== longer[j]) continue;
            shortMatches[i] = true;
            longMatches[j] = true;
            matches++;
            break;
        }
    }
    
    if (matches === 0) return 0.0;
    
    // 순서 일치 계산
    let transpositions = 0;
    let k = 0;
    for (let i = 0; i < shorter.length; i++) {
        if (!shortMatches[i]) continue;
        while (!longMatches[k]) k++;
        if (shorter[i] !== longer[k]) transpositions++;
        k++;
    }
    
    const jaro = (
        matches / longer.length +
        matches / shorter.length +
        (matches - transpositions / 2) / matches
    ) / 3.0;
    
    // Winkler 보정
    let prefix = 0;
    for (let i = 0; i < Math.min(4, shorter.length); i++) {
        if (text1[i] === text2[i]) prefix++;
        else break;
    }
    
    return jaro + (0.1 * prefix * (1 - jaro));
}

/**
 * 키워드 추출
 */
function extractKeywords(text) {
    if (!text) return new Set();
    
    // 한글, 영문, 숫자만 추출
    const words = text.match(/[가-힣a-zA-Z0-9]+/g) || [];
    return new Set(words.map(w => w.toLowerCase()));
}

/**
 * 맥락 기반 매칭
 */
function contextBasedMatch(message, ttsActual, ttsExpected) {
    if (!ttsActual || !ttsExpected) {
        return { match: false, reason: 'TTS 데이터 없음' };
    }
    
    // 1. 완전 일치
    if (ttsActual.trim() === ttsExpected.trim()) {
        return { match: true, reason: '완전 일치' };
    }
    
    // 2. 유사도 계산
    const similarity = calculateSimilarity(ttsActual, ttsExpected);
    
    // 3. 키워드 기반 매칭
    const messageKeywords = extractKeywords(message);
    const actualKeywords = extractKeywords(ttsActual);
    const expectedKeywords = extractKeywords(ttsExpected);
    
    // 공통 키워드 비율
    const commonWithExpected = [...expectedKeywords].filter(k => actualKeywords.has(k)).length;
    const commonWithMessage = [...messageKeywords].filter(k => actualKeywords.has(k)).length;
    
    const keywordMatchRatio = expectedKeywords.size > 0 
        ? commonWithExpected / expectedKeywords.size 
        : 0;
    
    // 4. 판정 기준
    // - 유사도가 0.7 이상이면 PASS
    // - 또는 키워드 매칭이 60% 이상이고 유사도가 0.5 이상이면 PASS
    // - 또는 메시지 키워드가 실제 TTS에 포함되어 있고 유사도가 0.6 이상이면 PASS
    
    if (similarity >= 0.7) {
        return { match: true, reason: `유사도 높음 (${(similarity * 100).toFixed(1)}%)` };
    }
    
    if (keywordMatchRatio >= 0.6 && similarity >= 0.5) {
        return { match: true, reason: `키워드 매칭 및 유사도 양호 (${(similarity * 100).toFixed(1)}%)` };
    }
    
    if (commonWithMessage > 0 && similarity >= 0.6) {
        return { match: true, reason: `메시지 맥락 반영 및 유사도 양호 (${(similarity * 100).toFixed(1)}%)` };
    }
    
    return { 
        match: false, 
        reason: `유사도 부족 (${(similarity * 100).toFixed(1)}%), 키워드 매칭: ${(keywordMatchRatio * 100).toFixed(1)}%` 
    };
}

/**
 * Pass/Fail 판정
 */
function determinePassFail(message, ttsActual, ttsExpected, useContext = true) {
    if (useContext) {
        const result = contextBasedMatch(message, ttsActual, ttsExpected);
        return {
            isPass: result.match,
            reason: result.reason
        };
    } else {
        const similarity = calculateSimilarity(ttsActual, ttsExpected);
        return {
            isPass: similarity >= 0.8,
            reason: similarity >= 0.8 
                ? `유사도: ${(similarity * 100).toFixed(1)}%` 
                : `유사도 부족: ${(similarity * 100).toFixed(1)}%`
        };
    }
}

// 전역으로 export
if (typeof module !== 'undefined' && module.exports) {
    module.exports = {
        calculateSimilarity,
        extractKeywords,
        contextBasedMatch,
        determinePassFail
    };
}



