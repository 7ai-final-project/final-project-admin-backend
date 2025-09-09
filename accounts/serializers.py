from rest_framework import serializers
from accounts.models import Admin

class AdminSerializers(serializers.ModelSerializer) :
    class Meta:
        model = Admin
        fields = ['id', 'name', 'email', 'is_superuser', 'is_staff']
        read_only_fields = ['id', 'name', 'email', 'is_superuser', 'is_staff']