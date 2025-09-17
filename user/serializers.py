from user.models import User
from rest_framework import serializers

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'name', 'nickname', 'email', 'social_type', 'last_login', 'is_active', 'is_deleted']