import uuid
from django.db import models


# 사용자
class User(models.Model) :
    id = models.UUIDField(primary_key=True, editable=False, default=uuid.uuid4)
    email = models.EmailField(max_length=255, unique=True)
    name = models.CharField(max_length=50)
    joined_at = models.DateTimeField(auto_now_add=True)
    login_at = models.DateTimeField(auto_now=True)
    social_id = models.CharField(max_length=255)
    social_type = models.CharField(max_length=50)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    is_deleted = models.BooleanField(default=False)

    class Meta:
        managed = False 
        db_table = 'user'

    def __str__(self) :
        return self.email
