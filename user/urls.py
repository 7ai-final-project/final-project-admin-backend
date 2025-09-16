from django.urls import path
from user.views import UserListView, UserUpdateView, UserUpdateAllView, UserStorySessionListView, MultimodeSessionListView

urlpatterns = [
    path('list', UserListView.as_view(), name='list_users'),
    path('update/all', UserUpdateAllView.as_view(), name="update_all_users"),
    path('update/<str:user_id>', UserUpdateView.as_view(), name="update_users"),
    path('list/storymode/<str:user_id>', UserStorySessionListView.as_view(), name="list_users_storymode_infos"),
    path('list/multimode/<str:user_id>', MultimodeSessionListView.as_view(), name="list_users_multimode_infos"),
]