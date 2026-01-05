from django.shortcuts import render
from django.conf import settings


def index(request):
    """메인 페이지 - 대피소 챗봇"""
    context = {
        'fastapi_url': settings.FASTAPI_BASE_URL,
        'naver_map_client_id': settings.NAVER_MAP_CLIENT_ID,
    }
    return render(request, 'shelter.html', context)