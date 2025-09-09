import json
import os
from django.core.management.base import BaseCommand
from accounts.models import Admin

class Command(BaseCommand) :
    help = '관리자 생성'

    def add_arguments(self, parser):
        parser.add_argument(
            '--file',
            type=str,
            help='data/admins.json'
        )

    def handle(self, *args, **options):
        file_path = options['file']

        if not file_path or not os.path.exists(file_path) :
            self.stdout.write(self.style.ERROR('JSON 파일 경로 확인 필요'))
            return
        
        with open(file_path, 'r', encoding='utf-8') as file :
            admin_data = json.load(file)
        
        self.stdout.write(f'{len(admin_data)}명 관리자 정보 조회 성공')

        for admin in admin_data :
            name = admin.get('name')
            email = admin.get('email')
            password = admin.get('password')

            if not name or not email or not password :
                self.stdout.write(self.style.ERROR(f'누락된 값 있음: {admin}'))
                continue

            if Admin.objects.filter(name=name).exists() :
                self.stdout.write(self.style.ERROR(f'이미 존재하는 관리자: {admin}'))
                continue

            admin_user = Admin.objects.create_superuser(
                name=name,
                email=email,
                password=password
            )
            self.stdout.write(self.style.SUCCESS(f'관리자 생성 완료: {admin_user.name} ({admin_user.email})'))