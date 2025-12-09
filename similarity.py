"""
유사도 계산 모듈
TTS 출력과 기대값을 비교하여 유사도 점수를 계산합니다.
네비게이션 AI 에이전트의 맥락 기반 판단을 지원합니다.
"""
from difflib import SequenceMatcher
import re


def calculate_similarity(text1: str, text2: str) -> float:
    """
    두 텍스트 간의 유사도를 계산합니다.
    
    Args:
        text1: 첫 번째 텍스트
        text2: 두 번째 텍스트
    
    Returns:
        0.0 ~ 1.0 사이의 유사도 점수
    """
    if not text1 and not text2:
        return 1.0
    if not text1 or not text2:
        return 0.0
    
    # 공백 제거 및 소문자 변환하여 비교
    text1_normalized = text1.strip().lower()
    text2_normalized = text2.strip().lower()
    
    if text1_normalized == text2_normalized:
        return 1.0
    
    # SequenceMatcher를 사용한 유사도 계산
    similarity = SequenceMatcher(None, text1_normalized, text2_normalized).ratio()
    return round(similarity, 4)


def extract_keywords(text: str) -> set:
    """
    텍스트에서 핵심 키워드를 추출합니다.
    
    Args:
        text: 분석할 텍스트
    
    Returns:
        키워드 집합
    """
    if not text:
        return set()
    
    # 일반적인 조사, 어미 제거를 위한 간단한 처리
    # 실제로는 더 정교한 형태소 분석이 필요할 수 있음
    text_lower = text.lower()
    
    # 주요 키워드 패턴 추출 (위치, 방향, 행동 등)
    keywords = set()
    
    # 위치 관련 키워드
    location_keywords = ['서울', '부산', '강남', '홍대', '명동', '이태원', '앞', '뒤', '왼쪽', '오른쪽', 
                        '직진', '우회전', '좌회전', '유턴', '고속도로', '터널', '다리', '사거리', '삼거리']
    for keyword in location_keywords:
        if keyword in text_lower:
            keywords.add(keyword)
    
    # 방향 관련 키워드
    direction_keywords = ['북', '남', '동', '서', '위', '아래', '앞', '뒤']
    for keyword in direction_keywords:
        if keyword in text_lower:
            keywords.add(keyword)
    
    # 행동 관련 키워드
    action_keywords = ['가다', '가세요', '가시면', '도착', '도착하', '찾', '보이', '나오', '나타나']
    for keyword in action_keywords:
        if keyword in text_lower:
            keywords.add(keyword)
    
    # 숫자 추출 (거리, 시간 등)
    numbers = re.findall(r'\d+', text)
    keywords.update(numbers)
    
    return keywords


def context_based_match(message: str, tts_actual: str, tts_expected: str) -> tuple[bool, str]:
    """
    메시지의 맥락을 고려하여 TTS 출력이 적절한지 판단합니다.
    
    Args:
        message: 사용자 입력 메시지
        tts_actual: 실제 TTS 출력
        tts_expected: 기대 TTS 값
    
    Returns:
        (is_pass: bool, reason: str) 튜플
    """
    if not tts_actual:
        return False, "TTS 출력이 없음"
    
    if not tts_expected:
        return False, "기대값이 없음"
    
    # 1. 기본 유사도 계산
    similarity = calculate_similarity(tts_actual, tts_expected)
    
    # 2. 키워드 기반 맥락 분석
    message_keywords = extract_keywords(message)
    tts_actual_keywords = extract_keywords(tts_actual)
    tts_expected_keywords = extract_keywords(tts_expected)
    
    # 메시지와 TTS 출력의 키워드 일치도
    message_tts_match = len(message_keywords & tts_actual_keywords) / max(len(message_keywords), 1)
    
    # 기대값과 실제값의 키워드 일치도
    expected_actual_match = len(tts_expected_keywords & tts_actual_keywords) / max(len(tts_expected_keywords), 1)
    
    # 3. 맥락 기반 판단
    # 유사도가 0.6 이상이거나, 키워드 일치도가 높으면 PASS
    context_score = (similarity * 0.5) + (message_tts_match * 0.25) + (expected_actual_match * 0.25)
    
    # 더 관대한 기준 적용 (네비게이션 AI 특성 고려)
    if similarity >= 0.6:
        return True, f"PASS (유사도: {similarity:.4f})"
    elif context_score >= 0.5:
        return True, f"PASS (맥락 일치: {context_score:.4f})"
    elif message_tts_match >= 0.4 and expected_actual_match >= 0.3:
        return True, f"PASS (키워드 일치: 메시지-출력={message_tts_match:.2f}, 기대-출력={expected_actual_match:.2f})"
    else:
        return False, f"FAIL (유사도: {similarity:.4f}, 맥락 점수: {context_score:.4f})"


def determine_pass_fail(message: str, tts_actual: str, tts_expected: str, use_context: bool = True) -> tuple[bool, str]:
    """
    TTS 출력과 기대값을 비교하여 Pass/Fail을 판정합니다.
    네비게이션 AI 에이전트의 특성을 고려한 맥락 기반 판단을 지원합니다.
    
    Args:
        message: 사용자 입력 메시지 (맥락 분석용)
        tts_actual: 실제 TTS 출력
        tts_expected: 기대 TTS 값
        use_context: 맥락 기반 판단 사용 여부 (기본값: True)
    
    Returns:
        (is_pass: bool, reason: str) 튜플
    """
    if use_context:
        return context_based_match(message, tts_actual, tts_expected)
    else:
        # 기존 방식 (엄격한 유사도 기준)
        similarity = calculate_similarity(tts_actual, tts_expected)
        is_pass = similarity >= 0.8
        
        if is_pass:
            reason = f"PASS (유사도: {similarity:.4f})"
        else:
            if not tts_actual:
                reason = "TTS 출력이 없음"
            elif not tts_expected:
                reason = "기대값이 없음"
            else:
                reason = f"FAIL (유사도 부족: {similarity:.4f})"
        
        return is_pass, reason



