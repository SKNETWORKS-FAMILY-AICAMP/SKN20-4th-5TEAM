import uuid
from django.db import models
from django.conf import settings
from django.core.validators import MinValueValidator


def generate_ad_id():
    """광고 ID 자동 생성 (UUID 기반, 50자 제한)"""
    return f"ad_{uuid.uuid4().hex}"[:50]


def generate_disaster_id():
    """재난 ID 자동 생성 (UUID 기반, 50자 제한)"""
    return f"disaster_{uuid.uuid4().hex}"[:50]


class Advertisement(models.Model):
    """광고 관리 (CSV 데이터 기반)"""
    
    ad_kind = models.CharField(
        max_length=100,
        verbose_name="광고 종류",
        db_column='AD_Kind',
        help_text="예: 심리상담, 실종아동, SK AI캠프, 자원봉사 등"
    )
    ad_id = models.CharField(
        max_length=50,
        unique=True,
        default=generate_ad_id,
        verbose_name="광고 ID",
        db_column='AD_id',
        help_text="UUID 기반 자동 생성 (50자)"
    )
    image_path = models.CharField(
        max_length=500,
        verbose_name="이미지 경로",
        db_column='Image_Path',
        help_text="예: C:\\Users\\ansck\\Desktop\\Project\\4rh-project\\data\\ad_images\\distermind.jpg"
    )
    
    @property
    def image_filename(self):
        """[2026-01-09 수정] 절대 경로에서 파일명 추출"""
        if self.image_path:
            import os
            return os.path.basename(self.image_path)
        return ""

    image_file = models.ImageField(
        upload_to='advertisements/',
        blank=True,
        null=True,
        verbose_name="이미지 파일",
        help_text="직접 업로드할 경우 사용"
    )
    title = models.CharField(
        max_length=200,
        blank=True,
        verbose_name="광고 제목"
    )
    description = models.TextField(
        blank=True,
        verbose_name="광고 설명"
    )
    link_url = models.URLField(
        blank=True,
        null=True,
        verbose_name="링크 URL"
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name="활성화 여부"
    )
    display_order = models.IntegerField(
        default=0,
        verbose_name="표시 순서",
        validators=[MinValueValidator(0)]
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_advertisements',
        verbose_name="등록자",
        db_column='regist_id'
    )
    regist_date = models.DateTimeField(
        auto_now_add=True,
        verbose_name="등록일",
        db_column='regist_date'
    )
    modified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='modified_advertisements',
        verbose_name="수정자",
        db_column='modifier_id'
    )
    modify_date = models.DateTimeField(
        auto_now=True,
        verbose_name="수정일",
        db_column='modify_date'
    )
    
    class Meta:
        db_table = 'advertisements'
        verbose_name = '광고'
        verbose_name_plural = '광고 목록'
        ordering = ['display_order', '-regist_date']
        indexes = [
            models.Index(fields=['ad_kind', 'is_active']),
        ]
    
    def __str__(self):
        return f"[{self.ad_kind}] {self.ad_id}"


class DisasterVideo(models.Model):
    """재난 영상 관리 (CSV 데이터 기반)"""
    
    DISASTER_KIND_CHOICES = [
        ('지진', '지진'),
        ('홍수', '홍수'),
        ('산사태', '산사태'),
        ('호우', '호우'),
        ('해일', '해일'),
        ('태풍', '태풍'),
        ('화산재', '화산재'),
        ('화산폭발', '화산폭발'),
        ('댐붕괴', '댐붕괴'),
        ('화재', '화재'),
        ('폭발', '폭발'),
        ('원전사고', '원전사고'),
        ('산불', '산불'),
    ]
    
    disaster_kind = models.CharField(
        max_length=50,
        choices=DISASTER_KIND_CHOICES,
        verbose_name="재난 종류",
        db_column='disaster_kind',
        db_index=True
    )
    disaster_id = models.CharField(
        max_length=50,
        unique=True,
        default=generate_disaster_id,
        verbose_name="재난 ID",
        db_column='disaster_id',
        help_text="UUID 기반 자동 생성 (50자)"
    )
    youtube_link = models.URLField(
        verbose_name="YouTube 임베드 링크",
        db_column='youtube_link',
        help_text="YouTube 임베드 URL"
    )
    title = models.CharField(
        max_length=200,
        blank=True,
        verbose_name="영상 제목"
    )
    description = models.TextField(
        blank=True,
        verbose_name="영상 설명"
    )
    thumbnail_url = models.URLField(
        blank=True,
        null=True,
        verbose_name="썸네일 URL"
    )
    duration = models.CharField(
        max_length=20,
        blank=True,
        verbose_name="영상 길이"
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name="활성화 여부"
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_disaster_videos',
        verbose_name="등록자",
        db_column='regist_id'
    )
    regist_date = models.DateTimeField(
        auto_now_add=True,
        verbose_name="등록일",
        db_column='regist_date'
    )
    modified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='modified_disaster_videos',
        verbose_name="수정자",
        db_column='modifier_id'
    )
    modify_date = models.DateTimeField(
        auto_now=True,
        verbose_name="수정일",
        db_column='modify_date'
    )
    # 20250109 카테고리 아이콘 경로(icon_path, icon_file_name) 추가
    icon_path = models.CharField(
        max_length=500,
        verbose_name="이미지 경로",
        null=True,
        blank=True,
        db_column='icon_path',
        help_text="예: images/flood_icon.png (static 폴더 기준 상대경로)"
    )

    icon_file_name = models.CharField(
        max_length=500,
        verbose_name="이미지 파일명",
        null=True,
        blank=True,
        db_column='icon_file_name',
        help_text="예: flood_icon.png (static 폴더 기준 상대경로)"
    )
    
    class Meta:
        db_table = 'disaster_videos'
        verbose_name = '재난 영상'
        verbose_name_plural = '재난 영상 목록'
        ordering = ['disaster_kind', '-regist_date']
        indexes = [
            models.Index(fields=['disaster_kind', 'is_active']),
        ]
    
    def __str__(self):
        return f"[{self.disaster_kind}] {self.title or self.youtube_link[:50]}"
    
    def get_youtube_embed_url(self):
        """YouTube 임베드 URL 반환 (iframe에 직접 사용)"""
        return self.youtube_link
    
    def get_youtube_video_id(self):
        """YouTube 비디오 ID 추출 (썸네일/API 호출용)"""
        if 'embed/' in self.youtube_link:
            return self.youtube_link.split('embed/')[-1].split('?')[0]
        return None
    
    def get_thumbnail_url(self):
        """썸네일 URL 자동 생성"""
        if self.thumbnail_url:
            return self.thumbnail_url
        video_id = self.get_youtube_video_id()
        if video_id:
            return f"https://img.youtube.com/vi/{video_id}/maxresdefault.jpg"
        return None

    @property
    def automatic_icon_path(self):
        """[2026-01-09 추가] 카테고리별 아이콘 자동 매핑 (DB 입력 불필요)"""
        # 한글 카테고리 -> 영문 파일명 매핑
        ICON_MAP = {
            '지진': 'earthquake_icon.png',
            '홍수': 'flood_icon.png',
            '산사태': 'landslide_icon.png',
            '호우': 'rain_icon.png',
            '해일': 'tsunami_icon.png',
            '태풍': 'typhoon_icon.png',
            '화산재': 'ash_icon.png',
            '화산폭발': 'eruption_icon.png',
            '댐붕괴': 'dam_icon.png',
            '화재': 'fire_icon.png',
            '폭발': 'explosion_icon.png',
            '원전사고': 'nuclear_icon.png',
            '산불': 'forest_fire_icon.png',
        }
        
        filename = ICON_MAP.get(self.disaster_kind)
        if filename:
            return f"images/category_icon/{filename}"
        
        # 매핑된 게 없으면 DB에 저장된 icon_path 사용 (Fallback)
        return self.icon_path
