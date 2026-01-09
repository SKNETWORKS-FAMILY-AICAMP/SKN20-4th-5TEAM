from django.contrib import admin
from django.utils.html import format_html
from .models import Advertisement, DisasterVideo


@admin.register(Advertisement)
class AdvertisementAdmin(admin.ModelAdmin):
    """광고 관리자 페이지"""
    
    list_display = ['ad_kind', 'ad_id', 'title', 'is_active', 'display_order', 'image_preview', 'created_by', 'regist_date']
    list_filter = ['ad_kind', 'is_active', 'regist_date', 'created_by']
    search_fields = ['ad_id', 'title', 'description']
    list_editable = ['is_active', 'display_order']
    ordering = ['display_order', '-regist_date']
    date_hierarchy = 'regist_date'
    
    fieldsets = (
        ('기본 정보', {
            'fields': ('ad_kind', 'ad_id', 'title', 'description')
        }),
        ('이미지 정보', {
            'fields': ('image_path', 'image_file', 'link_url')
        }),
        ('표시 설정', {
            'fields': ('is_active', 'display_order')
        }),
        ('등록/수정 정보', {
            'fields': ('created_by', 'regist_date', 'modified_by', 'modify_date'),
            'classes': ('collapse',)
        }),
    )
    
    readonly_fields = ['ad_id', 'created_by', 'regist_date', 'modified_by', 'modify_date']
    
    def image_preview(self, obj):
        """이미지 미리보기"""
        if obj.image_file:
            return format_html('<img src="{}" width="50" height="50" style="object-fit: cover;" />', obj.image_file.url)
        return '-'
    image_preview.short_description = '미리보기'
    
    def save_model(self, request, obj, form, change):
        """저장 시 등록자/수정자 자동 설정"""
        if not change:  # 신규 생성
            obj.created_by = request.user
        obj.modified_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(DisasterVideo)
class DisasterVideoAdmin(admin.ModelAdmin):
    """재난 영상 관리자 페이지"""
    
    list_display = ['disaster_kind', 'title', 'is_active', 'video_preview', 'created_by', 'regist_date']
    list_filter = ['disaster_kind', 'is_active', 'regist_date', 'created_by']
    search_fields = ['disaster_id', 'title', 'description']
    list_editable = ['is_active']
    ordering = ['disaster_kind', '-regist_date']
    date_hierarchy = 'regist_date'
    # 20250109 아이콘 경로 추가 
    list_display = ('disaster_kind', 'icon_path', 'is_active')
    
    fieldsets = (
        ('기본 정보', {
            'fields': ('disaster_kind', 'disaster_id', 'title', 'description')
        }),
        ('영상 정보', {
            'fields': ('youtube_link', 'thumbnail_url'),
            'description': 'YouTube 임베드 URL 예시: https://www.youtube.com/embed/VIDEO_ID'
        }),
        ('설정', {
            'fields': ('is_active', 'icon_path')
        }),
        ('등록/수정 정보', {
            'fields': ('created_by', 'regist_date', 'modified_by', 'modify_date'),
            'classes': ('collapse',)
        }),
    )
    
    readonly_fields = ['disaster_id', 'created_by', 'regist_date', 'modified_by', 'modify_date']
    
    actions = ['activate_videos', 'deactivate_videos']
    
    def video_preview(self, obj):
        """영상 미리보기"""
        video_id = obj.get_youtube_video_id()
        if video_id:
            return format_html(
                '<a href="{}" target="_blank">🎬 보기</a>',
                obj.youtube_link
            )
        return '-'
    video_preview.short_description = '영상'
    
    def save_model(self, request, obj, form, change):
        """저장 시 등록자/수정자 자동 설정"""
        if not change:  # 신규 생성
            obj.created_by = request.user
        obj.modified_by = request.user
        super().save_model(request, obj, form, change)
    
    def activate_videos(self, request, queryset):
        """영상 활성화"""
        updated = queryset.update(is_active=True)
        self.message_user(request, f'{updated}개 영상이 활성화되었습니다.')
    activate_videos.short_description = '선택한 영상 활성화'
    
    def deactivate_videos(self, request, queryset):
        """영상 비활성화"""
        updated = queryset.update(is_active=False)
        self.message_user(request, f'{updated}개 영상이 비활성화되었습니다.')
    deactivate_videos.short_description = '선택한 영상 비활성화'
