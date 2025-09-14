from rest_framework import status
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.authentication import JWTAuthentication
from django.shortcuts import get_object_or_404
from django.http import JsonResponse


class AuthMixin(APIView):
    # 인증된 사용자만 접근 가능
    permission_classes = [IsAuthenticated]
    # JWT 인증 방식 사용
    authentication_classes = [JWTAuthentication]

class CreateMixin :
    def post(self, request, model, serializer_class, name_field) :
        name = request.data.get(name_field)
        if not name :
            return JsonResponse({
                'message': f'{name_field}이(가) 필요합니다.'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            instance, created = model.objects.get_or_create(name=name)
            serializer = serializer_class(instance)

            if created:
                message = f'새로운 {model.__name__}이(가) 성공적으로 저장되었습니다.'
                status_code = status.HTTP_201_CREATED
                print(f'새로운 {model.__name__} DB 저장 성공!')
            else:
                message = f'이미 존재하는 {model.__name__}입니다.'
                status_code = status.HTTP_200_OK
                print(f'기존 {model.__name__} 존재!')

            return JsonResponse({
                'message': message, 
                'data': serializer.data
                }, 
            status=status_code)
        except Exception as e:
            print(f'죄송합니다. DB 저장에 오류가 발생했습니다')
            return JsonResponse({
                'message': f'DB 저장 중 오류 발생: {e}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
class ListViewMixin :
    def get(self, request, model, serializer_class, list_name):
        try:
            # instances = model.objects.all()
            instances = model.objects.filter(is_display=True, is_deleted=False)
            serializer = serializer_class(instances, many=True)
            return JsonResponse({
                'message': f'{model.__name__} 목록 조회 성공',
                list_name: serializer.data
            }, status=status.HTTP_200_OK)
        except Exception as e:
            print(f'🛑 오류: {model.__name__} 목록을 조회하는 데 실패했습니다. 오류')
            return JsonResponse({
                'message': f'{model.__name__} 목록 조회 실패: {e}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
class UpdateMixin :
    def put(self, request, pk_name, model, serializer_class, instance_id):
        instance = get_object_or_404(model, pk=instance_id)
        updated_any_field = False
        
        # name 필드 처리
        name = request.data.get('name')
        if name is not None:
            instance.name = name
            updated_any_field = True

        # is_display 필드 처리
        is_display = request.data.get('is_display')
        if is_display is not None:
            instance.is_display = is_display
            updated_any_field = True
        
        # is_deleted 필드 처리
        is_deleted = request.data.get('is_deleted')
        if is_deleted is not None:
            instance.is_deleted = is_deleted
            updated_any_field = True
        
        if not updated_any_field :
            return JsonResponse({
                'message': '업데이트할 필드가 필요합니다.'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # 업데이트
        instance.save()
        serializer = serializer_class(instance)
        return JsonResponse({
            'message': '업데이트 성공', 
            'data': serializer.data
        }, status=status.HTTP_200_OK)

class UpdateAllMixin :
    def put(self, request, model) :
        update_fields = {}

        # is_display 필드 처리
        is_display = request.data.get('is_display')
        if is_display is not None :
            update_fields['is_display'] = is_display
        
        # is_deleted 필드 처리
        is_deleted = request.data.get('is_deleted')
        if is_deleted is not None :
            update_fields['is_deleted'] = is_deleted
        
        if not update_fields :
            return JsonResponse({
                'message': '업데이트할 필드가 필요합니다.'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # 업데이트
        model.objects.all().update(**update_fields)
        return JsonResponse({
            'message': '업데이트 성공'
        }, status=status.HTTP_200_OK)