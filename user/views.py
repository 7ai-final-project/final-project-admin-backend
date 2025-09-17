from rest_framework import status
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.core.exceptions import ObjectDoesNotExist
from user.models import User
from user.serializers import UserSerializer
from user.mixins import AuthMixin, ListViewMixin, UpdateMixin, UpdateAllMixin
from storymode.models import StorymodeSession
from game.models import GameRoomSelectScenario, SinglemodeSession, MultimodeSession


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

# 싱글/멀티모드 게임 세션 공통 로직 View
class BaseGameView(AuthMixin) :
    def _serialize_user_data(self, user) :
        return {
            'id': str(user.id),
            'name': user.name,
        }

    def _serialize_scenario_data(self, scenario) :
        return {
            'id': str(scenario.id),
            'title': scenario.title,
            'description': scenario.description,
            'image_path': scenario.image_path if scenario.image_path else None,
        }

    def _serialize_character_data(self, character) :
        if not character :
            return None
        return {
            'id': str(character.id),
            'name': character.name,
            'role': character.role,
            'description': character.description,
            'image_path': character.image_path if character.image_path else None,
            'items': character.items,
            'ability': character.ability,
        }

    def _serialize_optional_object(self, obj) :
        if not obj :
            return None
        return {
            'id': str(obj.id),
            'name': obj.name,
        }

    def _serialize_common_session_fields(self, session):
        return {
            'id': str(session.id),
            'user': self._serialize_user_data(session.user),
            'scenario': self._serialize_scenario_data(session.scenario),
            'genre': None,
            'difficulty': None,
            'mode': None, 
            'character': self._serialize_character_data(session.character),
            'choice_history': session.choice_history,
            'character_history': session.character_history,
            'started_at': session.started_at.isoformat(),
            'ended_at': session.ended_at.isoformat() if session.ended_at else None,
            'status': session.status,
        }

    # 싱글모드 세션 데이터 직렬화
    def _serialize_session_data(self, session) :
        common_data = self._serialize_common_session_fields(session)
        common_data.update({
            'genre': self._serialize_optional_object(session.genre),
            'difficulty': self._serialize_optional_object(session.difficulty),
            'mode': self._serialize_optional_object(session.mode),
        })
        return common_data

    # 멀티모드 세션 데이터 직렬화
    def _serialize_multimode_session_data(self, session) :
        common_data = self._serialize_common_session_fields(session)

        genre_data = None
        difficulty_data = None
        mode_data = None

        try:
            selected_scenario_info = GameRoomSelectScenario.objects.select_related(
                'genre', 'difficulty', 'mode'
            ).get(gameroom=session.gameroom, scenario=session.scenario)

            genre_data = self._serialize_optional_object(selected_scenario_info.genre)
            difficulty_data = self._serialize_optional_object(selected_scenario_info.difficulty)
            mode_data = self._serialize_optional_object(selected_scenario_info.mode)

        except ObjectDoesNotExist:
            pass

        common_data.update({
            'gameroom': {
                'id': str(session.gameroom.id),
                'name': session.gameroom.name,
                'description': session.gameroom.description,
                'status': session.gameroom.status,
                'room_type': session.gameroom.room_type,
                'owner_id': str(session.gameroom.owner.id),
                'max_players': session.gameroom.max_players,
            },
            'genre': genre_data,
            'difficulty': difficulty_data,
            'mode': mode_data,
        })

        return common_data

# 사용자 싱글모드 세션 정보 조회
class SinglemodeSessionListView(BaseGameView) :
    def get(self, request, user_id) :
        try:
            user = get_object_or_404(User, id=user_id)

            sessions = SinglemodeSession.objects.filter(user=user).select_related(
                'user', 'scenario', 'character', 'genre', 'difficulty', 'mode'
            ).order_by('-started_at')

            sessions_data = [self._serialize_session_data(session) for session in sessions]

            return JsonResponse({
                'message': '싱글모드 세션 정보 조회 성공',
                'singleSessions': sessions_data
            }, status=status.HTTP_200_OK)
        except Exception as e:
            return JsonResponse({
                'message': f'싱글모드 세션 정보를 불러오는 중 오류가 발생했습니다: {e}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

# 사용자 멀티모드 세션 정보 조회
class MultimodeSessionListView(BaseGameView) :
    def get(self, request, user_id) :
        try:
            user = get_object_or_404(User, id=user_id)

            sessions = MultimodeSession.objects.filter(user=user).select_related(
                'user', 'gameroom', 'scenario', 'character'
            ).order_by('-started_at')

            sessions_data = [self._serialize_multimode_session_data(session) for session in sessions]

            return JsonResponse({
                'message': '멀티모드 세션 정보 조회 성공',
                'multiSessions': sessions_data
            }, status=status.HTTP_200_OK)
        except Exception as e:
            return JsonResponse({
                'message': f'멀티모드 세션 정보를 불러오는 중 오류가 발생했습니다: {e}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)