from django.shortcuts import render
from django.conf import settings
from .models import DisasterVideo

def index(request):
    """메인 페이지 - 대피소 챗봇"""
    videos = DisasterVideo.objects.filter(is_active=True)
    context = {
        'fastapi_url': settings.FASTAPI_BASE_URL,
        # 'naver_map_client_id': settings.NAVER_MAP_CLIENT_ID, # 2026-01-06: 카카오 지도로 전환
        'kakao_map_api_key': settings.KAKAO_MAP_API_KEY,
        'disaster_videos': videos,  # 이 이름으로 템플릿에 전달됩니다.
    }
    return render(request, 'shelter.html', context)