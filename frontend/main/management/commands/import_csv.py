import csv
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from main.models import Advertisement, DisasterVideo

User = get_user_model()


class Command(BaseCommand):
    help = 'CSV 파일에서 데이터 임포트 (ID 자동 생성)'

    def add_arguments(self, parser):
        parser.add_argument('--ads', type=str, help='광고 CSV 파일 경로')
        parser.add_argument('--videos', type=str, help='재난영상 CSV 파일 경로')
        parser.add_argument('--clear', action='store_true', help='기존 데이터 삭제 후 임포트')
        parser.add_argument('--user', type=str, default='admin', help='등록자 username (기본값: admin)')

    def handle(self, *args, **options):
        # 등록자 사용자 확인
        try:
            user = User.objects.get(username=options['user'])
            self.stdout.write(self.style.SUCCESS(f'등록자: {user.username}'))
        except User.DoesNotExist:
            self.stdout.write(self.style.ERROR(f'사용자를 찾을 수 없습니다: {options["user"]}'))
            self.stdout.write(self.style.WARNING('먼저 관리자 계정을 생성하세요: python manage.py createsuperuser'))
            return
        
        if options['clear']:
            if options['ads']:
                deleted_ads = Advertisement.objects.all().delete()[0]
                self.stdout.write(self.style.WARNING(f'기존 광고 {deleted_ads}개 삭제됨'))
            if options['videos']:
                deleted_videos = DisasterVideo.objects.all().delete()[0]
                self.stdout.write(self.style.WARNING(f'기존 영상 {deleted_videos}개 삭제됨'))
        
        if options['ads']:
            self.import_advertisements(options['ads'], user)
        
        if options['videos']:
            self.import_disaster_videos(options['videos'], user)

    def detect_encoding(self, file_path):
        """파일 인코딩 자동 감지"""
        encodings = ['utf-8-sig', 'utf-8', 'cp949', 'euc-kr', 'latin1']
        
        for encoding in encodings:
            try:
                with open(file_path, 'r', encoding=encoding) as f:
                    f.read()
                self.stdout.write(self.style.SUCCESS(f'  인코딩 감지: {encoding}'))
                return encoding
            except (UnicodeDecodeError, LookupError):
                continue
        
        self.stdout.write(self.style.WARNING('  인코딩을 감지하지 못했습니다. UTF-8 사용'))
        return 'utf-8'

    def import_advertisements(self, file_path, user):
        """광고 데이터 임포트"""
        self.stdout.write(self.style.MIGRATE_HEADING(f'\n광고 데이터 임포트 시작: {file_path}'))
        
        try:
            # 인코딩 자동 감지
            encoding = self.detect_encoding(file_path)
            
            with open(file_path, 'r', encoding=encoding) as f:
                # BOM 제거를 위해 utf-8-sig 사용
                reader = csv.DictReader(f)
                
                # 필드명에서 BOM 및 공백 제거
                fieldnames = [name.strip().replace('\ufeff', '') for name in reader.fieldnames]
                
                count_created = 0
                count_updated = 0
                
                for row in reader:
                    # 필드명 정규화
                    normalized_row = {k.strip().replace('\ufeff', ''): v.strip() for k, v in row.items()}
                    
                    ad_kind = normalized_row.get('AD_Kind', '')
                    image_path = normalized_row.get('Image_Path', '')
                    
                    if not ad_kind or not image_path:
                        self.stdout.write(self.style.WARNING(
                            f'건너뜀: 필수 필드 누락 - AD_Kind={ad_kind}, Image_Path={image_path}'
                        ))
                        continue
                    
                    # 같은 image_path가 있는지 확인
                    existing = Advertisement.objects.filter(image_path=image_path).first()
                    
                    if existing:
                        # 업데이트
                        existing.ad_kind = ad_kind
                        existing.modified_by = user
                        existing.save()
                        count_updated += 1
                        self.stdout.write(f'  ✓ 업데이트: {existing.ad_id} ({ad_kind})')
                    else:
                        # 신규 생성
                        ad = Advertisement.objects.create(
                            ad_kind=ad_kind,
                            image_path=image_path,
                            created_by=user,
                            modified_by=user,
                        )
                        count_created += 1
                        self.stdout.write(f'  ✓ 생성: {ad.ad_id} ({ad_kind})')
                
                self.stdout.write(self.style.SUCCESS(
                    f'\n광고 임포트 완료: 생성 {count_created}개, 업데이트 {count_updated}개'
                ))
        
        except FileNotFoundError:
            self.stdout.write(self.style.ERROR(f'파일을 찾을 수 없습니다: {file_path}'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'에러 발생: {str(e)}'))
            import traceback
            self.stdout.write(self.style.ERROR(traceback.format_exc()))

    def import_disaster_videos(self, file_path, user):
        """재난 영상 데이터 임포트"""
        self.stdout.write(self.style.MIGRATE_HEADING(f'\n재난 영상 데이터 임포트 시작: {file_path}'))
        
        try:
            # 인코딩 자동 감지
            encoding = self.detect_encoding(file_path)
            
            with open(file_path, 'r', encoding=encoding) as f:
                # BOM 제거를 위해 utf-8-sig 사용
                reader = csv.DictReader(f)
                
                # 필드명에서 BOM 및 공백 제거
                fieldnames = [name.strip().replace('\ufeff', '') for name in reader.fieldnames]
                
                count_created = 0
                count_updated = 0
                
                for row in reader:
                    # 필드명 정규화
                    normalized_row = {k.strip().replace('\ufeff', ''): v.strip() for k, v in row.items()}
                    
                    disaster_kind = normalized_row.get('disaster_kind', '')
                    youtube_link = normalized_row.get('youtube_link', '')
                    
                    if not disaster_kind or not youtube_link:
                        self.stdout.write(self.style.WARNING(
                            f'건너뜀: 필수 필드 누락 - disaster_kind={disaster_kind}, youtube_link={youtube_link}'
                        ))
                        continue
                    
                    # 같은 youtube_link가 있는지 확인
                    existing = DisasterVideo.objects.filter(youtube_link=youtube_link).first()
                    
                    if existing:
                        # 업데이트
                        existing.disaster_kind = disaster_kind
                        existing.modified_by = user
                        existing.save()
                        count_updated += 1
                        self.stdout.write(f'  ✓ 업데이트: {existing.disaster_id} ({disaster_kind})')
                    else:
                        # 신규 생성
                        video = DisasterVideo.objects.create(
                            disaster_kind=disaster_kind,
                            youtube_link=youtube_link,
                            created_by=user,
                            modified_by=user,
                        )
                        count_created += 1
                        self.stdout.write(f'  ✓ 생성: {video.disaster_id} ({disaster_kind})')
                
                self.stdout.write(self.style.SUCCESS(
                    f'\n재난 영상 임포트 완료: 생성 {count_created}개, 업데이트 {count_updated}개'
                ))
        
        except FileNotFoundError:
            self.stdout.write(self.style.ERROR(f'파일을 찾을 수 없습니다: {file_path}'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'에러 발생: {str(e)}'))
            import traceback
            self.stdout.write(self.style.ERROR(traceback.format_exc()))