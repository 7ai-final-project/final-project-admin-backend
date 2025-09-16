from rest_framework import status
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.core.exceptions import ObjectDoesNotExist
from user.models import User
from user.serializers import UserSerializer
from user.mixins import AuthMixin, ListViewMixin, UpdateMixin, UpdateAllMixin
from storymode.models import StorymodeSession
from game.models import GameRoomSelectScenario, MultimodeSession


# 사용자 DB 조회
class UserListView(AuthMixin, ListViewMixin):
    def get(self, request) :
        return super().get(request, User, UserSerializer, 'users')

# 사용자 DB 업데이트
class UserUpdateView(AuthMixin, UpdateMixin) :
    def put(self, request, user_id) :
        return super().put(request, 'user_id', User, UserSerializer, user_id)

# 사용자 DB 전체 업데이트
class UserUpdateAllView(AuthMixin, UpdateAllMixin) :
    def put(self, request) :
        return super().put(request, User)

# 사용자 스토리 세션 정보 조회
class UserStorySessionListView(AuthMixin) :
    def get(self, request, user_id) :
        try :
            user = get_object_or_404(User, id=user_id)
            
            sessions = StorymodeSession.objects.filter(user=user).select_related(
                'story', 'current_moment'
            ).prefetch_related(
                'current_moment__choices__next_moment'
            ).order_by('-updated_at')

            sessions_data = []
            for session in sessions:
                moment = session.current_moment
                choices_data = []

                if moment:
                    for choice in moment.choices.all():
                        choices_data.append({
                            'id': choice.id,
                            'action_type': choice.action_type,
                            'next_moment': {
                                'id': choice.next_moment.id if choice.next_moment else None,
                                'title': choice.next_moment.title if choice.next_moment else '스토리 종료',
                            }
                        })

                session_detail_data = {
                    'session_id': session.id,
                    'story': {
                        'id': session.story.id,
                        'title': session.story.title,
                        'image_path': session.story.image_path if session.story.image_path else None,
                    },
                    'current_moment': {
                        'id': moment.id if moment else None,
                        'title': moment.title if moment else '스토리 시작 전',
                        'description': moment.description if moment else '현재 진행중인 분기점이 없습니다.',
                        'is_ending': moment.is_ending() if moment else False,
                        'choices': choices_data,
                    },
                    'progress': session.get_progress_percentage(),
                    'status': session.status,
                    'history': session.history,
                    'start_at': session.start_at.isoformat() if session.start_at else None,
                    'end_at': session.end_at.isoformat() if session.end_at else None,
                    'updated_at': session.updated_at.isoformat() if session.updated_at else None,
                }
                sessions_data.append(session_detail_data)
            
            return JsonResponse({
                'message' : '스토리 세션 정보 조회 성공',
                'storySessions' : sessions_data
            }, status=status.HTTP_200_OK)
        except Exception as e :
            return JsonResponse({
                'message': f'스토리 세션 정보를 불러오는 중 오류가 발생했습니다: {e}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
# 사용자 멀티모드 세션 정보 조회
class MultimodeSessionListView(AuthMixin) :
    def get(self, request, user_id) :
        try :
            user = get_object_or_404(User, id=user_id)

            sessions = MultimodeSession.objects.filter(user=user).select_related(
                'user', 'gameroom', 'scenario', 'character'
            ).order_by('-started_at')

            sessions_data = []
            for session in sessions:
                selected_scenario_info = None
                try:
                    selected_scenario_info = GameRoomSelectScenario.objects.select_related(
                        'genre', 'difficulty', 'mode'
                    ).get(gameroom=session.gameroom, scenario=session.scenario)
                except ObjectDoesNotExist:
                    pass

                session_detail_data = {
                    'id': str(session.id),
                    'user': {
                        'id': str(session.user.id),
                        'name': session.user.name,
                    },
                    'gameroom': {
                        'id': str(session.gameroom.id),
                        'name': session.gameroom.name,
                        'description': session.gameroom.description,
                        'status': session.gameroom.status,
                        'room_type': session.gameroom.room_type,
                        'owner_id': str(session.gameroom.owner.id),
                        'max_players': session.gameroom.max_players,
                    },
                    'scenario': {
                        'id': str(session.scenario.id),
                        'title': session.scenario.title,
                        'description': session.scenario.description,
                        'image_path': session.scenario.image_path,
                    },
                    'genre': {
                        'id': str(selected_scenario_info.genre.id),
                        'name': selected_scenario_info.genre.name,
                    }
                    if selected_scenario_info and selected_scenario_info.genre else None,
                    'difficulty': {
                        'id': str(selected_scenario_info.difficulty.id),
                        'name': selected_scenario_info.difficulty.name,
                    }
                    if selected_scenario_info and selected_scenario_info.difficulty else None,
                    'mode': {
                        'id': str(selected_scenario_info.mode.id),
                        'name': selected_scenario_info.mode.name,
                    }
                    if selected_scenario_info and selected_scenario_info.mode else None,
                    'character': {
                        'id': str(session.character.id),
                        'name': session.character.name,
                        'role': session.character.role,
                        'description': session.character.description,
                        'image_path': session.character.image_path,
                        'items': session.character.items,
                        'ability': session.character.ability,
                    }
                    if session.character else None,
                    'choice_history': session.choice_history,
                    'character_history': session.character_history,
                    'started_at': session.started_at.isoformat(),
                    'ended_at': session.ended_at.isoformat() if session.ended_at else None,
                    'status': session.status,
                }
                sessions_data.append(session_detail_data)

            return JsonResponse({
                'message' : '멀티모드 세션 정보 조회 성공',
                'multiSessions': sessions_data
            }, status=status.HTTP_200_OK)
        except Exception as e:
            return JsonResponse({
                'message': f'멀티모드 세션 정보를 불러오는 중 오류가 발생했습니다: {e}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)