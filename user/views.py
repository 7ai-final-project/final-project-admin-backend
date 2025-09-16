import json
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from .models import User

@csrf_exempt
def user_list_create(request):
    if request.method == 'GET':
        # ★★★ 1. 변경점: 'last_login' 대신 'joined_at'을 요청합니다. ★★★
        # 프론트엔드 코드는 'last_login'을 기대하므로, DB에서 가져온 'joined_at'의 이름을 'last_login'으로 바꿔서 보내줍니다.
        users_data = list(User.objects.all().values('id', 'name', 'email', 'joined_at'))
        for user in users_data:
            user['last_login'] = user.pop('joined_at') # 'joined_at' 키를 'last_login'으로 변경

        return JsonResponse({'users': users_data})

    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            name = data.get('name')
            email = data.get('email')

            if not name or not email:
                return JsonResponse({'error': '이름과 이메일은 필수입니다.'}, status=400)
            
            if User.objects.filter(email=email).exists():
                return JsonResponse({'error': '이미 존재하는 이메일입니다.'}, status=400)
            
            user = User.objects.create(name=name, email=email)
            
            response_data = {
                'id': user.id,
                'name': user.name,
                'email': user.email,
                # ★★★ 2. 변경점: 새로 만든 사용자 정보에도 'joined_at'을 'last_login'으로 바꿔서 보내줍니다. ★★★
                'last_login': user.joined_at
            }
            return JsonResponse(response_data, status=201)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)

    return JsonResponse({'error': '지원하지 않는 메소드입니다.'}, status=405)


@csrf_exempt
def user_detail_update_delete(request, user_id):
    # 이 부분은 'last_login'을 사용하지 않으므로 수정할 필요가 없습니다.
    try:
        user = User.objects.get(pk=user_id)
    except User.DoesNotExist:
        return JsonResponse({'error': '사용자를 찾을 수 없습니다.'}, status=404)

    if request.method == 'PUT':
        try:
            data = json.loads(request.body)
            user.name = data.get('name', user.name)
            user.email = data.get('email', user.email)
            user.save()
            return JsonResponse({'message': '사용자 정보가 성공적으로 업데이트되었습니다.'})
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)
    
    if request.method == 'DELETE':
        user.delete()
        return JsonResponse({'message': '사용자가 성공적으로 삭제되었습니다.'}, status=204)

    return JsonResponse({'error': '지원하지 않는 메소드입니다.'}, status=405)
 