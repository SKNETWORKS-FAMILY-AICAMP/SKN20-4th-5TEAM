from django.shortcuts import render
from django.conf import settings
from .models import DisasterVideo, Advertisement

def index(request):
    """메인 페이지 - 대피소 챗봇"""
    videos = DisasterVideo.objects.filter(is_active=True)
    # [2026-01-09 수정] 활성화된 광고 목록 추가
    ads = Advertisement.objects.filter(is_active=True).order_by('display_order')
    context = {
        'fastapi_url': settings.FASTAPI_BASE_URL,
        'kakao_map_api_key': settings.KAKAO_MAP_API_KEY,
        'disaster_videos': videos,
        'advertisements': ads,
    }
    return render(request, 'shelter.html', context)