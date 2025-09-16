# C:\Users\USER\Desktop\final\final-project-admin-backend\user\urls.py

from django.urls import path
from . import views  # user 앱의 views.py를 import 합니다.

urlpatterns = [
    # 사용자 목록 조회 (GET) / 사용자 추가 (POST)
    # 최종 URL: /api/users/
    path('users/', views.user_list_create, name='user-list-create'),

    # 특정 사용자 조회 (GET), 수정 (PUT), 삭제 (DELETE)
    # 최종 URL: /api/users/1/
    path('users/<int:user_id>/', views.user_detail_update_delete, name='user-detail-update-delete'),
]