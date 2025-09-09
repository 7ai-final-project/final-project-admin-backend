from django.urls import path
from accounts.views import LoginView, LogoutView, AdminInfoView

urlpatterns = [
    path('login', LoginView.as_view(), name="login"),
    path('logout', LogoutView.as_view(), name="logout"),
    path('admin/me', AdminInfoView.as_view(), name="admin-info"),
]
