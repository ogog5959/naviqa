"""
종합 평가 모듈
실제값과 기대값을 비교하여 PASS/PARTIAL_PASS/FAIL을 판정합니다.
확장 가능한 구조로 구현되어 향후 복잡한 평가 로직 추가가 가능합니다.
"""
import json
import re
from typing import Dict, Optional, Tuple
from similarity import calculate_similarity


def check_hard_fails(raw_json: str, tts_actual: str) -> Optional[str]:
    """
    하드 FAIL 가드레일 체크
    
    Args:
        raw_json: raw JSON 문자열
        tts_actual: 실제 TTS 출력
    
    Returns:
        None (PASS) 또는 fail_reason 문자열 (FAIL)
    """
    # 1. raw_json에 error 존재 확인
    if raw_json:
        error_patterns = [
            r'"error"',
            r'"status"\s*:\s*5\d{2}',  # HTTP 500대 에러
            r'"statusCode"\s*:\s*5\d{2}',
            r'HTTP\s+ERROR\s+5\d{2}',
        ]
        for pattern in error_patterns:
            if re.search(pattern, raw_json, re.IGNORECASE):
                return f"HARD_FAIL_ERROR_IN_RESPONSE: {pattern}"
    
    # 2. tts_actual이 비어있는지 확인
    if not tts_actual or not tts_actual.strip():
        return "HARD_FAIL_EMPTY_TTS: TTS 출력이 없음"
    
    # 3. tts_actual에 실패 문구 포함 확인
    failure_keywords = [
        "응답 생성에 실패했습니다",
        "생성에 실패",
        "오류가 발생했습니다",
        "에러가 발생했습니다",
        "처리할 수 없습니다",
    ]
    tts_lower = tts_actual.lower()
    for keyword in failure_keywords:
        if keyword in tts_lower:
            return f"HARD_FAIL_FAILURE_MESSAGE: '{keyword}' 포함"
    
    return None


def evaluate_tts(tts_actual: str, tts_expected: str) -> Tuple[float, str]:
    """
    TTS 평가
    
    Args:
        tts_actual: 실제 TTS 출력
        tts_expected: 기대 TTS 값 (선택적)
    
    Returns:
        (score: float, reason: str) 튜플
        score: 0.0 ~ 1.0
    """
    if not tts_expected or tts_expected.strip() == '':
        # 기대값이 없으면 평가하지 않음 (선택적 필드)
        return 1.0, "TTS 기대값 없음 (평가 생략)"
    
    if not tts_actual:
        return 0.0, "TTS 실제값 없음"
    
    similarity = calculate_similarity(tts_actual, tts_expected)
    
    if similarity >= 0.8:
        return similarity, "TTS GOOD"
    elif similarity >= 0.55:
        return similarity, "TTS OK (표현차)"
    else:
        return similarity, "TTS MISMATCH"


def evaluate_action_name(action_name: str, action_name_expected: str) -> Tuple[float, str]:
    """
    action_name 평가
    
    Args:
        action_name: 실제 action_name
        action_name_expected: 기대 action_name
    
    Returns:
        (score: float, reason: str) 튜플
        score: 0.0 (불일치) 또는 1.0 (일치)
    """
    if not action_name_expected:
        # 기대값이 없으면 평가하지 않음
        return 1.0, "action_name 기대값 없음 (평가 생략)"
    
    if not action_name:
        return 0.0, "action_name 실제값 없음"
    
    # 정확 일치 확인
    if action_name.strip() == action_name_expected.strip():
        return 1.0, "action_name 일치"
    else:
        return 0.0, f"action_name 불일치: 기대={action_name_expected}, 실제={action_name}"


def evaluate_action_data(action_data: str, action_data_expected: str) -> Tuple[float, str]:
    """
    action_data 평가
    
    Args:
        action_data: 실제 action_data
        action_data_expected: 기대 action_data
    
    Returns:
        (score: float, reason: str) 튜플
        score: 0.0 ~ 1.0 (부분 일치 가능)
    """
    if not action_data_expected:
        # 기대값이 없으면 평가하지 않음
        return 1.0, "action_data 기대값 없음 (평가 생략)"
    
    if not action_data:
        return 0.0, "action_data 실제값 없음"
    
    # 정확 일치 확인
    if action_data.strip() == action_data_expected.strip():
        return 1.0, "action_data 일치"
    
    # JSON 파싱 시도 (deepLink payload 비교)
    try:
        # action_data가 deepLink URL인 경우 파싱
        if "kakaonavi://agent?data=" in action_data:
            # data= 뒤의 부분 추출
            data_match = re.search(r'data=([^"]+)', action_data)
            if data_match:
                actual_payload_str = data_match.group(1)
                try:
                    actual_payload = json.loads(actual_payload_str)
                except:
                    actual_payload = None
            else:
                actual_payload = None
        else:
            # 일반 JSON 문자열인 경우
            try:
                actual_payload = json.loads(action_data)
            except:
                actual_payload = None
        
        # 기대값도 동일하게 파싱
        if "kakaonavi://agent?data=" in action_data_expected:
            data_match = re.search(r'data=([^"]+)', action_data_expected)
            if data_match:
                expected_payload_str = data_match.group(1)
                try:
                    expected_payload = json.loads(expected_payload_str)
                except:
                    expected_payload = None
            else:
                expected_payload = None
        else:
            try:
                expected_payload = json.loads(action_data_expected)
            except:
                expected_payload = None
        
        # JSON 파싱 성공 시 핵심 필드 비교
        if actual_payload and expected_payload:
            # action 필드 비교
            actual_action = actual_payload.get("action")
            expected_action = expected_payload.get("action")
            
            if actual_action == expected_action:
                # args의 핵심 필드 비교
                actual_args = actual_payload.get("args", {})
                expected_args = expected_payload.get("args", {})
                
                # destPoi 비교
                actual_dest = actual_args.get("destPoi")
                expected_dest = expected_args.get("destPoi")
                
                if actual_dest and expected_dest:
                    # poiId 우선 비교
                    if actual_dest.get("poiId") == expected_dest.get("poiId"):
                        return 0.9, "action_data 핵심 필드 일치 (poiId)"
                    # poiName 비교
                    elif actual_dest.get("poiName") == expected_dest.get("poiName"):
                        return 0.8, "action_data 핵심 필드 일치 (poiName)"
                    else:
                        return 0.5, "action_data 부분 일치"
                
                return 0.7, "action_data 구조 일치"
        
    except Exception as e:
        pass
    
    # JSON 파싱 실패 시 문자열 유사도로 평가
    similarity = calculate_similarity(action_data, action_data_expected)
    if similarity >= 0.8:
        return similarity, "action_data 유사 (문자열 비교)"
    else:
        return similarity, "action_data 불일치"


def evaluate_next_step(next_step: str, next_step_expected: str) -> Tuple[float, str]:
    """
    next_step 평가
    
    Args:
        next_step: 실제 next_step
        next_step_expected: 기대 next_step
    
    Returns:
        (score: float, reason: str) 튜플
        score: 0.0 (불일치) 또는 1.0 (일치)
    """
    if not next_step_expected:
        # 기대값이 없으면 평가하지 않음
        return 1.0, "next_step 기대값 없음 (평가 생략)"
    
    if not next_step:
        return 0.0, "next_step 실제값 없음"
    
    # 정확 일치 확인
    next_step_normalized = next_step.strip().upper()
    expected_normalized = next_step_expected.strip().upper()
    
    if next_step_normalized == expected_normalized:
        return 1.0, "next_step 일치"
    else:
        # 특수 케이스: expected END / actual QUESTION → PARTIAL 가능
        if expected_normalized == "END" and next_step_normalized == "QUESTION":
            return 0.5, "next_step PARTIAL: 기대=END, 실제=QUESTION (추가 확인)"
        # expected QUESTION / actual END → FAIL
        elif expected_normalized == "QUESTION" and next_step_normalized == "END":
            return 0.0, "next_step FAIL: 기대=QUESTION, 실제=END (질문해야 하는데 종료)"
        else:
            return 0.0, f"next_step 불일치: 기대={next_step_expected}, 실제={next_step}"


def evaluate_comprehensive(
    raw_json: str,
    tts_actual: str,
    tts_expected: str,
    action_name: str,
    action_name_expected: str,
    action_data: str,
    action_data_expected: str,
    next_step: str,
    next_step_expected: str,
) -> Dict:
    """
    종합 평가 수행
    
    Args:
        raw_json: raw JSON 문자열
        tts_actual: 실제 TTS 출력
        tts_expected: 기대 TTS 값
        action_name: 실제 action_name
        action_name_expected: 기대 action_name
        action_data: 실제 action_data
        action_data_expected: 기대 action_data
        next_step: 실제 next_step
        next_step_expected: 기대 next_step
    
    Returns:
        {
            'verdict': 'PASS' | 'PARTIAL_PASS' | 'FAIL',
            'fail_reason': str,
            'scores': {
                'tts': float,
                'action_name': float,
                'action_data': float,
                'next_step': float
            }
        }
    """
    # 1. 하드 FAIL 체크
    hard_fail_reason = check_hard_fails(raw_json, tts_actual)
    if hard_fail_reason:
        return {
            'verdict': 'FAIL',
            'fail_reason': hard_fail_reason,
            'scores': {
                'tts': 0.0,
                'action_name': 0.0,
                'action_data': 0.0,
                'next_step': 0.0
            }
        }
    
    # 2. 각 축별 평가
    tts_score, tts_reason = evaluate_tts(tts_actual, tts_expected)
    action_name_score, action_name_reason = evaluate_action_name(action_name, action_name_expected)
    action_data_score, action_data_reason = evaluate_action_data(action_data, action_data_expected)
    next_step_score, next_step_reason = evaluate_next_step(next_step, next_step_expected)
    
    scores = {
        'tts': tts_score,
        'action_name': action_name_score,
        'action_data': action_data_score,
        'next_step': next_step_score
    }
    
    # 3. 최종 verdict 결정
    # 평가 대상이 있는 축만 고려
    evaluated_axes = []
    if tts_expected:
        evaluated_axes.append(('tts', tts_score))
    if action_name_expected:
        evaluated_axes.append(('action_name', action_name_score))
    if action_data_expected:
        evaluated_axes.append(('action_data', action_data_score))
    if next_step_expected:
        evaluated_axes.append(('next_step', next_step_score))
    
    if not evaluated_axes:
        # 평가할 축이 없으면 PASS
        return {
            'verdict': 'PASS',
            'fail_reason': '평가 기준 없음',
            'scores': scores
        }
    
    # 모든 축이 1.0이면 PASS
    all_pass = all(score >= 1.0 for _, score in evaluated_axes)
    if all_pass:
        return {
            'verdict': 'PASS',
            'fail_reason': '',
            'scores': scores
        }
    
    # 주요 축이 FAIL (0.0)이면 FAIL
    # 주요 축: action_name, next_step
    critical_axes = ['action_name', 'next_step']
    has_critical_fail = any(
        axis in [a for a, _ in evaluated_axes] and scores[axis] == 0.0
        for axis in critical_axes
    )
    
    if has_critical_fail:
        fail_reasons = []
        if action_name_expected and action_name_score == 0.0:
            fail_reasons.append(f"action_name: {action_name_reason}")
        if next_step_expected and next_step_score == 0.0:
            fail_reasons.append(f"next_step: {next_step_reason}")
        if action_data_expected and action_data_score < 0.5:
            fail_reasons.append(f"action_data: {action_data_reason}")
        if tts_expected and tts_score < 0.55:
            fail_reasons.append(f"tts: {tts_reason}")
        
        return {
            'verdict': 'FAIL',
            'fail_reason': '; '.join(fail_reasons) if fail_reasons else '주요 축 실패',
            'scores': scores
        }
    
    # 일부 축이 PARTIAL (0.5~0.99)이거나 TTS만 낮으면 PARTIAL_PASS
    has_partial = any(0.5 <= score < 1.0 for _, score in evaluated_axes)
    tts_only_low = (
        tts_expected and tts_score < 0.55 and
        all(scores.get(axis, 1.0) >= 0.8 for axis in ['action_name', 'action_data', 'next_step'] if axis in scores)
    )
    
    if has_partial or tts_only_low:
        fail_reasons = []
        if tts_expected and tts_score < 0.8:
            fail_reasons.append(f"tts: {tts_reason}")
        if action_name_expected and 0.5 <= action_name_score < 1.0:
            fail_reasons.append(f"action_name: {action_name_reason}")
        if action_data_expected and 0.5 <= action_data_score < 1.0:
            fail_reasons.append(f"action_data: {action_data_reason}")
        if next_step_expected and 0.5 <= next_step_score < 1.0:
            fail_reasons.append(f"next_step: {next_step_reason}")
        
        return {
            'verdict': 'PARTIAL_PASS',
            'fail_reason': '; '.join(fail_reasons) if fail_reasons else '부분 일치',
            'scores': scores
        }
    
    # 그 외는 FAIL
    fail_reasons = []
    for axis, score in evaluated_axes:
        if score < 1.0:
            if axis == 'tts':
                fail_reasons.append(f"tts: {tts_reason}")
            elif axis == 'action_name':
                fail_reasons.append(f"action_name: {action_name_reason}")
            elif axis == 'action_data':
                fail_reasons.append(f"action_data: {action_data_reason}")
            elif axis == 'next_step':
                fail_reasons.append(f"next_step: {next_step_reason}")
    
    return {
        'verdict': 'FAIL',
        'fail_reason': '; '.join(fail_reasons) if fail_reasons else '평가 실패',
        'scores': scores
    }
