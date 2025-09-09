from django.db import models
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
import uuid


class AdminManager(BaseUserManager) :
    def _create_user(self, name, email, password, **extra_fields) :
        if not email :
            raise ValueError('이메일 필수')
        if not name :
            raise ValueError('이름 필수')

        email = self.normalize_email(email)
        admin_user = self.model(
            name=name,
            email=email,
            is_active=True,
            is_staff=True,
            **extra_fields)
        admin_user.set_password(password)
        admin_user.save(using=self._db)
        return admin_user
    
    def create_user(self, name, email, password=None, **extra_fields) :
        return self._create_user(name, email, password, **extra_fields)
    
    def create_superuser(self, name, email, password=None, **extra_fields) :
        extra_fields.setdefault('is_superuser', True)
        return self._create_user(name, email, password, **extra_fields)


# 관리자
class Admin(AbstractBaseUser, PermissionsMixin) : 
    id = models.UUIDField(primary_key=True, unique=True, default=uuid.uuid4)
    name = models.CharField(max_length=50, unique=True)
    email = models.EmailField(max_length=254, unique=True)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=True)
    joined_at = models.DateTimeField(auto_now_add=True)
    login_at = models.DateTimeField(auto_now=True)
    is_deleted = models.BooleanField(default=False)

    objects = AdminManager()

    USERNAME_FIELD = 'name'         # 로그인 시, 사용할 필드
    REQUIRED_FIELDS = ['email']     # createsuperuser 실행 시, 필수로 입력받을 필드

    class Meta :
        db_table = 'admin'
        verbose_name = '관리자'
        verbose_name_plural = '관리자'

    def __str__(self) :
        return f'{self.name} ({self.email})'
