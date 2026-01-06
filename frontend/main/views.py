from django.shortcuts import render
from django.conf import settings


def index(request):
    """메인 페이지 - 대피소 챗봇"""
    context = {
        'fastapi_url': settings.FASTAPI_BASE_URL,
        # 'naver_map_client_id': settings.NAVER_MAP_CLIENT_ID, # 2026-01-06: 카카오 지도로 전환
        'kakao_map_api_key': settings.KAKAO_MAP_API_KEY,
    }
    return render(request, 'shelter.html', context)