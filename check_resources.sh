#!/bin/bash
echo "=== 리소스 체크 ==="
echo "CPU 제한: Request 100m, Limit 2"
echo "Memory 제한: Request 128Mi, Limit 1Gi"
echo ""
echo "⚠️  주의: Playwright + Chromium은 메모리를 많이 사용합니다."
echo "   - Chromium 기본 메모리: ~200-300MB"
echo "   - Playwright 프로세스: ~50-100MB"
echo "   - Python 애플리케이션: ~100-200MB"
echo "   - 총 예상 메모리: ~350-600MB"
echo ""
MEMORY_MB=$(free -m | awk 'NR==2{printf "%.0f", $3}')
if [ "$MEMORY_MB" -gt 900 ]; then
    echo "❌ 메모리 사용량이 900MB를 초과했습니다. (현재: ${MEMORY_MB}MB)"
    echo "   제작한 앱은 높은 스펙이 필요해요. frodo.1012에게 스펙업 요청을 해주세요"
    exit 1
fi
echo "✅ 리소스 체크 통과 (메모리 사용량: ${MEMORY_MB}MB)"


