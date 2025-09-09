from rest_framework import status
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework.views import APIView
from django.http import JsonResponse
from django.contrib.auth import authenticate
from accounts.models import Admin
from accounts.serializers import AdminSerializers

# 로그인
class LoginView(APIView) :
    permission_classes = [AllowAny]

    def post(self, request) :
        name = request.data.get('name')
        password = request.data.get('password')
        print(f'name : {name}')
        print(f'password : {password}')

        if not name or not password :
            return JsonResponse({
                'message' : '아이디 또는 패스워드를 입력해주세요.'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # 사용자 인증
        admin = authenticate(request, username=name, password=password)
        # 인증 완료 시,
        if admin is not None : 
            # 로그인
            token = RefreshToken.for_user(admin)

            # 사용자 정보 직렬화
            serializer = AdminSerializers(admin)

            return JsonResponse({
                'message' : '로그인 성공',
                'admin' : serializer.data,
                'access_token' : str(token.access_token),
                'refresh_token' : str(token),
            }, status=status.HTTP_200_OK)
        else :
            # 인증 실패
            return JsonResponse({
                'message' : '아이디 또는 패스워드가 올바르지 않습니다.'
            }, status=status.HTTP_401_UNAUTHORIZED)

# 로그아웃
class LogoutView(APIView) :
    # 인증된 사용자만 접근 가능
    permission_classes = [IsAuthenticated]
    # JWT 인증 방식 사용
    authentication_classes = [JWTAuthentication]

    def post(self, request) :
        try :
            refresh_token = request.data.get('refresh_token')
            token = RefreshToken(refresh_token)
            token.blacklist()

            return JsonResponse({
                'message' : '로그아웃 성공'
            }, status=status.HTTP_200_OK)
        except Exception as e :
            return JsonResponse({
                'message' : '잘못된 Refresh Token 입니다.'
            }, status=status.HTTP_400_BAD_REQUEST)
        

# 관리자 정보 조회
class AdminInfoView(APIView) :
    # 인증된 사용자만 접근 가능
    permission_classes = [IsAuthenticated]
    # JWT 인증 방식 사용
    authentication_classes = [JWTAuthentication]

    def get(self, request) :
        admin = request.user
        print('admin', admin)
        if admin.is_authenticated :
            serializer = AdminSerializers(admin)
            return JsonResponse({
                'admin' : serializer.data
            }, status=status.HTTP_200_OK)
        
        return JsonResponse({
            'error' : 'Unauthorized'
        }, status=status.HTTP_401_UNAUTHORIZED)

