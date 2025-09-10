import json
from openai import AzureOpenAI
from rest_framework import status
from azure.storage.blob import BlobServiceClient
from django.conf import settings
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from game.models import Genre, Mode, Difficulty, Scenario, Character
from game.serializers import GenreSerializer, ModeSerializer, DifficultySerializer, ScenarioSerializer, CharacterSerializer
from game.mixins import AuthMixin, CreateMixin, ListViewMixin, UpadteMixin, UpdataAllMixin


AZURE_BLOB_STORAGE_CONNECT_KEY = settings.AZURE_BLOB_STORAGE_CONNECT_KEY
AZURE_OPENAI_API_KEY = settings.AZURE_OPENAI_API_KEY
AZURE_OPENAI_ENDPOINT = settings.AZURE_OPENAI_ENDPOINT
AZURE_OPENAI_VERSION = settings.AZURE_OPENAI_VERSION
AZURE_OPENAI_DEPLOYMENT = settings.AZURE_OPENAI_DEPLOYMENT

# Azure OpenAI 클라이언트 초기화
def get_azure_openai_client() :
    try :
        return AzureOpenAI(
            api_key=AZURE_OPENAI_API_KEY,
            azure_endpoint=AZURE_OPENAI_ENDPOINT,
            api_version=AZURE_OPENAI_VERSION
        )
    except Exception as e :
        print(f'Azure OpenAI 클라이언트 초기화 실패 {e}')
        return None

# 장르 DB 저장
class GenreCreateView(AuthMixin, CreateMixin) :
    def post(self, request) :
        return super().post(request, Genre, GenreSerializer, 'name')

# 장르 DB 조회
class GenreListView(AuthMixin, ListViewMixin) :
    def get(self, request) :
        return super().get(request, Genre, GenreSerializer, 'genres')
    
# 장르 DB 업데이트
class GenreUpdateView(AuthMixin, UpadteMixin) :
    def put(self, request, genre_id) :
        return super().put(request, 'genre_id', Genre, GenreSerializer, genre_id)
    
# 장르 DB 전체 업데이트
class GenreUpdateAllView(AuthMixin, UpdataAllMixin) :
    def put(self, request) :
        return super().put(request, Genre)

# 모드 DB 저장
class ModeCreateView(AuthMixin, CreateMixin) :
    def post(self, request) :
        return super().post(request, Mode, ModeSerializer, 'name')

# 모드 DB 조회
class ModeListView(AuthMixin, ListViewMixin) :
    def get(self, request) :
        return super().get(request, Mode, ModeSerializer, 'modes')
    
# 모드 DB 업데이트
class ModeUpdateView(AuthMixin, UpadteMixin) :
    def put(self, request, mode_id) :
        return super().put(request, 'mode_id', Mode, ModeSerializer, mode_id)
    
# 모드 DB 전체 업데이트
class ModeUpdateAllView(AuthMixin, UpdataAllMixin) :
    def put(self, request) :
        return super().put(request, Mode)
    
# 난이도 DB 저장
class DifficultyCreateView(AuthMixin, CreateMixin) :
    def post(self, request) :
        return super().post(request, Difficulty, DifficultySerializer, 'name')

# 난이도 DB 조회
class DifficultyListView(AuthMixin, ListViewMixin) :
    def get(self, request) :
        return super().get(request, Difficulty, DifficultySerializer, 'difficulties')
    
# 난이도 DB 업데이트
class DifficultyUpdateView(AuthMixin, UpadteMixin) :
    def put(self, request, difficulty_id) :
        return super().put(request, 'difficulty_id', Difficulty, DifficultySerializer, difficulty_id)
    
# 난이도 DB 전체 업데이트
class DifficultyUpdateAllView(AuthMixin, UpdataAllMixin) :
    def put(self, request) :
        return super().put(request, Difficulty)
    
# 전달되는 파일을 Azure Blob Storage 에 업로드
class SenarioFileUploadView(AuthMixin) :
    def post(self, request) :
        file = request.FILES.get('file')

        if not file :
            return JsonResponse({
                'message' : '파일이 없습니다.'
            }, status=status.HTTP_400_BAD_REQUEST)

        # Azure Blob Storage 파일 업로드
        try :
            conn_str = AZURE_BLOB_STORAGE_CONNECT_KEY
            blob_service_client = BlobServiceClient.from_connection_string(conn_str=conn_str)
            
            container = 'scenarios'
            container_client = blob_service_client.get_container_client(container=container)

            blob_client = container_client.upload_blob(name=file.name, data=file.read(), overwrite=True)
            return JsonResponse({
                'message' : '파일 업로드 성공',
                'file_url' : blob_client.url,
                'blob_name' : file.name
            }, status=status.HTTP_201_CREATED)
        except Exception as e :
            print(f'파일 업로드 Exception: {e}')     
            return JsonResponse({
                'message' : '파일 업로드 실패'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)   

# Azure Blob Storage 에 업로드된 파일을 읽어서 DB 에 데이터 저장
class SenarioCreateView(AuthMixin) :
    def post(self, request) :
        scenario_name = request.data.get('scenario_name')
        blob_name = request.data.get('blob_name')

        if not scenario_name or not blob_name :
            return JsonResponse({
                'message' : '시나리오 이름 혹은 업로드 파일 url 이 필요합니다.'
            }, status=status.HTTP_400_BAD_REQUEST)

        # Azure Blob Storage 에서 파일 내용 가져오기
        scenario_text = ''
        try:
            print(f"📖 Azure Blob Storage에서 '{blob_name}' 파일을 다운로드합니다...")

            conn_str = AZURE_BLOB_STORAGE_CONNECT_KEY
            blob_service_client = BlobServiceClient.from_connection_string(conn_str=conn_str)
            
            container = 'scenarios'
            container_client = blob_service_client.get_container_client(container=container)
            blob_client = container_client.get_blob_client(blob=blob_name)
            scenario_text = blob_client.download_blob().readall().decode('utf-8')
            print('파일 다운로드 완료')
        except Exception as e :
            print(f"🛑 오류: Azure Blob Storage에서 파일을 다운로드하는 데 실패했습니다. 오류: {e}")
            return JsonResponse({
                'message' : '파일 다운로드 실패'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
                
        # API 키 정보를 읽어와서 Azure OpenAI에 연결 준비
        try:
            client = AzureOpenAI(
                api_key=AZURE_OPENAI_API_KEY,
                azure_endpoint=AZURE_OPENAI_ENDPOINT,
                api_version=AZURE_OPENAI_VERSION
            )
        except Exception as e:
            print(f"Azure OpenAI 클라이언트 초기화 실패. 오류: {e}")
            return JsonResponse({
                'message' : 'AI 서비스 연결 실패'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        system = {"role": "system", "content": "너는 스토리 분석가다. 캐릭터 창작에 도움이 되는 핵심만 간결히 요약해라."}
        user = {
            "role": "user",
            "content": f"""다음 JSON 스토리를 캐릭터 창작용으로 요약.
                    형식(JSON): {
                        {
                            "setting": "시대/장소/분위기",
                            "themes": ["주제1","주제2"],
                            "tone": "전체 톤",
                            "notable_characters": ["핵심 인물/집단 3~6개"],
                            "conflicts": ["갈등/과제 2~4개"],
                            "description": "한줄 요약"
                        }
                    }
                    스토리: {scenario_text}"""
        }

        # Azure OpenAI API 요청
        try:
            response = client.chat.completions.create(
                model=AZURE_OPENAI_DEPLOYMENT,
                messages=[system, user],
                temperature=0.7,
                top_p=0.95,
                max_tokens=2000,
                frequency_penalty=0,
                presence_penalty=0,
                response_format={"type": "json_object"} # 결과는 무조건 JSON 형식으로 받기
            )
        
            # AI의 응답 내용(JSON 텍스트)
            ai_response_content = response.choices[0].message.content
            print("AI가 응답을 완료했습니다!")

            # JSON 텍스트를 딕셔너리로 변환
            senario_json = json.loads(ai_response_content)
            print(senario_json)

            try :
                # 시나리오 DB 저장
                scenario, created = Scenario.objects.get_or_create(
                    title=scenario_name,
                    defaults={'description': senario_json.get('description','')}
                )

                serializer = ScenarioSerializer(scenario)

                if created :
                    message = '새로운 시나리오가 성공적으로 저장되었습니다.'
                    status_code = status.HTTP_201_CREATED
                    print("새로운 시나리오 DB 저장 성공!")
                else :
                    message = '이미 존재하는 시나리오입니다.'
                    status_code = status.HTTP_200_OK
                    print("기존 시나리오 존재!")

                return JsonResponse({
                    'message' : message,
                    'data' : serializer.data,
                }, status=status_code)
            except Exception as e :
                print(f"🛑 오류: AI 응답 데이터를 DB에 저장하는 데 실패했습니다. 오류: {e}")
                return JsonResponse({
                    'message' : 'AI 응답 데이터 DB 저장 실패',
                    'ai_response' : senario_json
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        except Exception as e:
            print(f"죄송합니다. AI를 호출하는 중에 오류가 발생했습니다: {e}")
            return JsonResponse({
                'message' : 'AI 처리 중 오류 발생',
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
# 시나리오 DB 조회
class ScenarioListView(AuthMixin, ListViewMixin) :
    def get(self, request) :
        return super().get(request, Scenario, ScenarioSerializer, 'scenarios')

# 시나리오 DB 업데이트
class ScenarioUpdateView(AuthMixin, UpadteMixin) :
    def put(self, request, scenario_id) :
        return super().put(request, 'scenario_id', Scenario, ScenarioSerializer, scenario_id)

# 시나리오 DB 전체 업데이트
class ScenarioUpdateAllView(AuthMixin, UpdataAllMixin) :
    def put(self, request) :
        return super().put(request, Scenario)

# 캐릭터 생성
class CharacterCreateView(AuthMixin) :
    def post(self, request) :
        scenario_id = request.data.get('scenario_id')
        description = request.data.get('description')

        if not scenario_id or not description :
            return JsonResponse({
                'message' : '시나리오 정보가 필요합니다.',
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # 시나리오 정보 조회
        try :
            scenario = Scenario.objects.get(id=scenario_id)
        except Exception as e :
            return JsonResponse({
                'message' : '시나리오 조회 실패'
            }, status=status.HTTP_404_NOT_FOUND)
        
        # API 키 정보를 읽어와서 Azure OpenAI에 연결 준비
        client = get_azure_openai_client()
        if not client :
            print(f"Azure OpenAI 클라이언트 초기화 실패. 오류: {e}")
            return JsonResponse({
                'message' : 'AI 서비스 연결 실패'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        system = {
            "role": "system",
            "content": "너는 창의적인 캐릭터 창작가다. 캐릭터 창작에 도움이 되는 핵심만 간결히 요약해라.",
        }
        
        user = {
            "role": "user",
            "content": f"""다음 시나리오 정보를 바탕으로 캐릭터 설명
                            형식(JSON): {
                                {
                                    "name": "캐릭터 이름",
                                    "role": "클래스/아키타입(탱커/정찰자/현자/외교가/트릭스터 등)",
                                    "stats": {"힘":1-10,"민첩":1-10,"지식":1-10,"의지":1-10,"매력":1-10,"운":1-10},
                                    "skills": ["대표 스킬1","대표 스킬2"],
                                    "starting_items": ["시작 아이템1","시작 아이템2"],
                                    "playstyle": "행동/대화 성향, 선택 경향, 말투 가이드"
                                }
                            }
                            시나리오: {scenario.description}
                        """
        }

        # Azure OpenAI API 요청
        try:
            response = client.chat.completions.create(
                model=AZURE_OPENAI_DEPLOYMENT,
                messages=[system, user],
                temperature=0.7,
                top_p=0.95,
                max_tokens=2000,
                frequency_penalty=0,
                presence_penalty=0,
                response_format={"type": "json_object"} # 결과는 무조건 JSON 형식으로 받기
            )
        
            # AI의 응답 내용(JSON 텍스트)
            ai_response_content = response.choices[0].message.content
            print("AI가 응답을 완료했습니다!", ai_response_content)

            # JSON 텍스트를 딕셔너리로 변환
            character_json = json.loads(ai_response_content)
            print(character_json)

            # 캐릭터 DB 저장
            try :
                character_role = character_json.get('role', '')
                character_playstyle = character_json.get('playstyle', '')

                character, created = Character.objects.get_or_create(
                    scenario=scenario,
                    name=character_json.get('name', ''),
                    defaults={
                        'description': f"역할: {character_role}\n플레이 스타일: {character_playstyle}",
                        'items': list(character_json.get('starting_items', [])),
                        'ability': {
                            'stats': character_json.get('stats', {}),
                            'skills': character_json.get('skills', []),
                        }
                    }
                )

                serializer = CharacterSerializer(character)

                if created :
                    message = '캐릭터가 성공적으로 저장되었습니다.'
                    status_code = status.HTTP_201_CREATED
                    print("캐릭터 DB 저장 성공!")
                else :
                    message = '이미 존재하는 캐릭터입니다.'
                    status_code = status.HTTP_200_OK
                    print("기존 캐릭터 존재!")

                return JsonResponse({
                    'message' : '성공',
                    'characters' : [serializer.data]
                }, status=status.HTTP_200_OK)
            except Exception as e :
                print(f"🛑 오류: AI 응답 데이터를 DB에 저장하는 데 실패했습니다. 오류: {e}")
                return JsonResponse({
                    'message' : 'AI 응답 데이터 DB 저장 실패',
                    'ai_response' : character_json
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        except Exception as e :
            print(f"Azure OpenAI API 요청 실패. 오류: {e}")
            return JsonResponse({
                'message': f'AI 캐릭터 생성 요청 실패: {e}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

# 캐릭터 DB 조회
class CharacterListView(AuthMixin) :
    def get(self, request, scenario_id) :
        scenario = get_object_or_404(Scenario, id=scenario_id)

        try :
            character = Character.objects.filter(
                scenario=scenario,
                is_display=True,
                is_deleted=False,
            )
        except Exception as e :
            return JsonResponse({
                'message' : '캐릭터 조회 실패'
            }, status=status.HTTP_404_NOT_FOUND)
        
        serializer = CharacterSerializer(character, many=True)
        return JsonResponse({
            'message' : '캐릭터 조회 성공',
            'characters' : serializer.data
        }, status=status.HTTP_200_OK)