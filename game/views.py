import time
import json
import requests
import urllib.parse
from openai import AzureOpenAI
from rest_framework import status
from django.conf import settings
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.db.models import Count
from azure.storage.blob import BlobServiceClient, ContentSettings
from azure.core.exceptions import ResourceNotFoundError
from game.models import Genre, Mode, Difficulty, Scenario, Character, GameRoomSelectScenario, SinglemodeSession, MultimodeSession
from game.serializers import GenreSerializer, ModeSerializer, DifficultySerializer, ScenarioSerializer, CharacterSerializer
from game.mixins import AuthMixin, CreateMixin, ListViewMixin, UpdateMixin, UpdateAllMixin


# 환경 설정
class AppSettings :
    # Azure Blob Storage
    AZURE_BLOB_STORAGE_CONNECT_KEY_FOR_FILE = settings.AZURE_BLOB_STORAGE_CONNECT_KEY_FOR_FILE
    AZURE_BLOB_STORAGE_CONNECT_KEY_FOR_IMAGE = settings.AZURE_BLOB_STORAGE_CONNECT_KEY_FOR_IMAGE

    # Azure OpenAI
    AZURE_OPENAI_API_KEY = settings.AZURE_OPENAI_API_KEY
    AZURE_OPENAI_ENDPOINT = settings.AZURE_OPENAI_ENDPOINT
    AZURE_OPENAI_VERSION = settings.AZURE_OPENAI_VERSION
    AZURE_OPENAI_DEPLOYMENT = settings.AZURE_OPENAI_DEPLOYMENT

    # Azure OpenAI DALL-E
    AZURE_OPENAI_DALLE_APIKEY = settings.AZURE_OPENAI_DALLE_APIKEY
    AZURE_OPENAI_DALLE_ENDPOINT = settings.AZURE_OPENAI_DALLE_ENDPOINT
    AZURE_OPENAI_DALLE_VERSION = settings.AZURE_OPENAI_DALLE_VERSION
    AZURE_OPENAI_DALLE_DEPLOYMENT = settings.AZURE_OPENAI_DALLE_DEPLOYMENT
    
# Azure OpenAI 클라이언트 초기화
def get_azure_openai_client(api_key, endpoint, api_version) :
    if not all([api_key, endpoint]):
        print("ERROR: Azure OpenAI API KEY 또는 ENDPOINT가 설정되지 않았습니다.")
        return None

    try :
        return AzureOpenAI(
            api_key=api_key,
            azure_endpoint=endpoint,
            api_version=api_version
        )
    except Exception as e :
        print(f'Azure OpenAI 클라이언트 초기화 실패 {e}')
        return None
    
# DALL-E 클라이언트 초기화
def get_azure_dalle_client(api_key, endpoint, api_version) :
    return get_azure_openai_client(api_key, endpoint, api_version)

# Azure Blob Storage 클라이언트
def get_blob_service_client(connection_string) :
    if not connection_string :
        raise ValueError("ERROR: Azure Blob Storage 연결 문자열이 설정되지 않았습니다.")
    
    try :
        return BlobServiceClient.from_connection_string(connection_string)
    except Exception as e :
        raise Exception(f'Azure Blob Storage 클라이언트 초기화 실패: {e}')

# Azure Blob Storage 유틸
class AzureBlobStorageUtil :
    def __init__(self, connection_string) :
        self.blob_service_client = get_blob_service_client(connection_string) 
    
    # Azure Blob Storage 컨테이너를 가져오거나 생성, 공개 접근 정책 설정
    def get_or_create_container(self, container_name, public=False) :
        try :
            container_client = self.blob_service_client.get_container_client(container_name)
            try :
                container_client.get_container_properties()
                print(f"\n>> 컨테이너 '{container_name}'가 이미 존재합니다. 재사용합니다.\n")
            except ResourceNotFoundError :
                container_client.create_container()
                print(f"\n>> 신규 컨테이너 '{container_name}' 생성 완료.\n")

            # 컨테이너의 공개 접근 정책을 'blob'으로 설정 (익명 읽기 가능)
            if public :
                container_client.set_container_access_policy(signed_identifiers={}, public_access='blob')
            return container_client
        except Exception as e :
            raise Exception(f'ERROR: Azure Blob Storage 컨테이너 처리 실패: {e}')

    # Azure Blob Storage 에 데이터가 존재하는 확인하고 URL 반환
    def check_blob_exists_and_get_url(self, blob_client) :
        try:
            blob_client.get_blob_properties()
            print(f"\n>> 이미 존재하는 데이터: {blob_client.url}\n")
            return blob_client.url
        except ResourceNotFoundError :
            return None
        except Exception as e :
            raise Exception(f"ERROR: Blob 존재 여부 확인 중 오류 발생: {e}")
    
    # Azure Blob Storage 에 데이터 업로드
    def upload_blob(self, container_client, blob_name, data, content_type='application/octet-stream', overwrite=True) :
        blob_client = container_client.get_blob_client(blob=blob_name)
        try :
            content_settings_obj = ContentSettings(content_type=content_type)
            blob_client.upload_blob(data, overwrite=overwrite, content_settings=content_settings_obj)
            return blob_client.url
        except Exception as e :
            raise Exception(f"ERROR: Blob 업로드 실패 ({blob_name}): {e}")
    
    # Azure Blob Strorage 에서 파일 다운로드
    def download_blob_as_text(self, container_client, blob_name) :
        blob_client = container_client.get_blob_client(blob=blob_name)
        try :
            download_stream = blob_client.download_blob()
            return download_stream.readall().decode('utf-8')
        except Exception as e :
            raise Exception(f"ERROR: Blob 다운로드 실패 ({blob_name}): {e}")

# 장르 DB 저장
class GenreCreateView(AuthMixin, CreateMixin) :
    def post(self, request) :
        return super().post(request, Genre, GenreSerializer, 'name')

# 장르 DB 조회
class GenreListView(AuthMixin, ListViewMixin) :
    def get(self, request) :
        return super().get(request, Genre, GenreSerializer, 'genres')
    
# 장르 DB 업데이트
class GenreUpdateView(AuthMixin, UpdateMixin) :
    def put(self, request, genre_id) :
        return super().put(request, 'genre_id', Genre, GenreSerializer, genre_id)
    
# 장르 DB 전체 업데이트
class GenreUpdateAllView(AuthMixin, UpdateAllMixin) :
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
class ModeUpdateView(AuthMixin, UpdateMixin) :
    def put(self, request, mode_id) :
        return super().put(request, 'mode_id', Mode, ModeSerializer, mode_id)
    
# 모드 DB 전체 업데이트
class ModeUpdateAllView(AuthMixin, UpdateAllMixin) :
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
class DifficultyUpdateView(AuthMixin, UpdateMixin) :
    def put(self, request, difficulty_id) :
        return super().put(request, 'difficulty_id', Difficulty, DifficultySerializer, difficulty_id)
    
# 난이도 DB 전체 업데이트
class DifficultyUpdateAllView(AuthMixin, UpdateAllMixin) :
    def put(self, request) :
        return super().put(request, Difficulty)
    
# 전달되는 시나리오 파일을 Azure Blob Storage 에 업로드
class SenarioFileUploadView(AuthMixin) :
    def post(self, request) :
        file = request.FILES.get('file')

        if not file :
            return JsonResponse({
                'message' : '파일이 없습니다.'
            }, status=status.HTTP_400_BAD_REQUEST)

        # Azure Blob Storage 파일 업로드
        try :
            blob_util = AzureBlobStorageUtil(AppSettings.AZURE_BLOB_STORAGE_CONNECT_KEY_FOR_FILE)
            container_client = blob_util.get_or_create_container('scenarios')
            file_url = blob_util.upload_blob(
                container_client=container_client,
                blob_name=file.name,
                data=file.read(),
                content_type=file.content_type,
                overwrite=True
            )

            return JsonResponse({
                'message' : '파일 업로드 성공',
                'file_url' : file_url,
                'blob_name' : file.name
            }, status=status.HTTP_201_CREATED)
        except Exception as e :
            print(f'파일 업로드 Exception: {e}')     
            return JsonResponse({
                'message' : '파일 업로드 실패'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)   

# Azure Blob Storage 에 업로드된 시나리오 파일을 읽어서 DB 에 데이터 저장
class SenarioCreateView(AuthMixin) :
    def post(self, request) :
        scenario_name = request.data.get('scenario_name')
        blob_name = request.data.get('blob_name')

        if not scenario_name or not blob_name :
            return JsonResponse({
                'message' : '시나리오 이름 혹은 업로드 파일 url 이 필요합니다.'
            }, status=status.HTTP_400_BAD_REQUEST)

        # 1. Azure Blob Storage 에서 파일 내용 가져오기
        scenario_text = ''
        try:
            print(f"📖 Azure Blob Storage에서 '{blob_name}' 파일을 다운로드합니다...")
            blob_util = AzureBlobStorageUtil(AppSettings.AZURE_BLOB_STORAGE_CONNECT_KEY_FOR_FILE)
            container_client = blob_util.get_or_create_container('scenarios')
            scenario_text = blob_util.download_blob_as_text(
                container_client=container_client,
                blob_name=blob_name
            )
            print('파일 다운로드 완료')
        except Exception as e :
            print(f"🛑 오류: Azure Blob Storage에서 파일을 다운로드하는 데 실패했습니다. 오류: {e}")
            return JsonResponse({
                'message' : '파일 다운로드 실패'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
        # 2. Azure OpenAI 클라이언트 초기화
        client = get_azure_openai_client(
            AppSettings.AZURE_OPENAI_API_KEY,
            AppSettings.AZURE_OPENAI_ENDPOINT,
            AppSettings.AZURE_OPENAI_VERSION
        )

        if not client :
            return JsonResponse({
                'message': 'AI 서비스 연결 실패: OpenAI 클라이언트 초기화 오류'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        # 3. AI 시스템 메시지 및 Azure OpenAI 요청
        system = {"role": "system", "content": "너는 스토리 분석가다. 캐릭터 창작에 도움이 되는 핵심만 간결히 요약해라."}
        user = {
            "role": "user",
            "content": f"""다음 JSON 스토리를 캐릭터 창작용으로 요약.
                    형식(JSON): {
                        {
                            "title" : "스토리 제목",
                            "title_eng" : "스토리 영어 제목",
                            "setting": "시대/장소/분위기",
                            "themes": ["주제1","주제2"],
                            "tone": "전체 톤",
                            "notable_characters": ["핵심 인물/집단 2~6개"],
                            "conflicts": ["갈등/과제 2~4개"],
                            "description": "한줄 요약",
                            "description_eng": "한줄 요약을 영어로 번역"
                        }
                    }
                    스토리: {scenario_text}"""
        }

        # Azure OpenAI API 요청
        try:
            response = client.chat.completions.create(
                model=AppSettings.AZURE_OPENAI_DEPLOYMENT,
                messages=[system, user],
                temperature=0.7,
                top_p=0.95,
                max_tokens=2000,
                frequency_penalty=0,
                presence_penalty=0,
                response_format={"type": "json_object"} # 결과는 무조건 JSON 형식으로 받기
            )
        
            ai_response_content = response.choices[0].message.content
            print("AI가 응답을 완료했습니다!")

            senario_json = json.loads(ai_response_content)
            print(senario_json)
        except Exception as e :
            print(f"🛑 오류: AI를 호출하는 중에 오류가 발생했습니다: {e}")
            return JsonResponse({
                'message': f'AI 처리 중 오류 발생: {e}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        # 4. AI 응답 데이터 DB 저장
        try :
            # Scenario DB 저장
            scenario, created = Scenario.objects.get_or_create(
                title=scenario_name,
                title_eng=senario_json.get('title_eng',''),
                description=senario_json.get('description',''),
                description_eng=senario_json.get('description_eng',''),
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
        
# 시나리오 DB 조회
class ScenarioListView(AuthMixin, ListViewMixin) :
    def get(self, request) :
        return super().get(request, Scenario, ScenarioSerializer, 'scenarios')

# 시나리오 DB 업데이트
class ScenarioUpdateView(AuthMixin, UpdateMixin) :
    def put(self, request, scenario_id) :
        return super().put(request, 'scenario_id', Scenario, ScenarioSerializer, scenario_id)

# 시나리오 DB 전체 업데이트
class ScenarioUpdateAllView(AuthMixin, UpdateAllMixin) :
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
        
        # 1. 시나리오 DB 정보 조회
        try :
            scenario = Scenario.objects.get(id=scenario_id)
        except Exception as e :
            return JsonResponse({
                'message' : '시나리오 조회 실패'
            }, status=status.HTTP_404_NOT_FOUND)

        # 2. Azure OpenAI 클라이언트 초기화
        client = get_azure_openai_client(
            AppSettings.AZURE_OPENAI_API_KEY,
            AppSettings.AZURE_OPENAI_ENDPOINT,
            AppSettings.AZURE_OPENAI_VERSION
        )

        if not client :
            return JsonResponse({
                'message': 'AI 서비스 연결 실패: OpenAI 클라이언트 초기화 오류'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
        # 3. AI 시스템 메시지 및 Azure OpenAI 요청
        system = {
            "role": "system",
            "content": "너는 창의적인 스토리 작가이자 캐릭터 창조자다. 주어진 시나리오를 바탕으로 3~5명의 핵심 플레이어블 캐릭터들을 생성한다. 반드시 지정된 JSON 형식에 맞춰 응답해야 한다.",
        }
        
        user = {
            "role": "user",
            "content": f"""다음 시나리오 정보를 바탕으로 3~5명의 플레이어블 캐릭터 목록을 생성해줘. 응답 형식은 반드시 'characters'라는 키를 가진 JSON 객체여야 하며, 그 값은 캐릭터 객체들의 배열(리스트)이어야 한다.
                            형식(JSON): {{
                                "name": "캐릭터 이름",
                                "name_eng": "캐릭터 영어 이름",
                                "role": "클래스/아키타입(탱커/정찰자/현자/외교가/트릭스터 등)",
                                "role_eng": "클래스/아키타입(탱커/정찰자/현자/외교가/트릭스터 등)를 영어로 번역",
                                "playstyle": "행동/대화 성향, 선택 경향, 말투 가이드",
                                "playstyle_eng": "행동/대화 성향, 선택 경향, 말투 가이드를 영어로 번역",
                                "stats": {{"힘":1-10,"민첩":1-10,"지식":1-10,"의지":1-10,"매력":1-10,"운":1-10}},
                                "skills": [
                                    {{
                                        "name":"대표 스킬1",
                                        "description":"스킬1 설명",
                                    }},
                                    {{
                                        "name":"대표 스킬2",
                                        "description":"스킬2 설명",
                                    }}
                                ],
                                "starting_items": [
                                    {{
                                        "name":"시작 아이템1",
                                        "description":"아이템1 설명",
                                    }},
                                    {{
                                        "name":"시작 아이템2",
                                        "description":"아이템2 설명",
                                    }}
                                ]
                            }}
                            시나리오: {scenario.description}
                        """
        }

        # Azure OpenAI API 요청
        try:
            response = client.chat.completions.create(
                model=AppSettings.AZURE_OPENAI_DEPLOYMENT,
                messages=[system, user],
                temperature=0.7,
                top_p=0.95,
                max_tokens=2000,
                frequency_penalty=0,
                presence_penalty=0,
                response_format={"type": "json_object"} # 결과는 무조건 JSON 형식으로 받기
            )
        
            ai_response_content = response.choices[0].message.content
            print("AI가 응답을 완료했습니다!")

            characters_json = json.loads(ai_response_content)
            print(characters_json)

            characters_data = characters_json.get('characters', [])
            if not characters_data : 
                return JsonResponse({
                    'message': f'AI 가 캐릭터 데이터를 생성하지 못했습니다.'
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        except Exception as e :
            print(f"🛑 오류: AI를 호출하는 중에 오류가 발생했습니다: {e}")
            return JsonResponse({
                'message': f'AI 처리 중 오류 발생: {e}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        # AI 응답 데이터 DB 저장
        try :
            # 캐릭터 DB 저장
            created_characters = []
            for characters in characters_data:
                character, created = Character.objects.get_or_create(
                    scenario=scenario,
                    name=characters.get('name', ''),
                    name_eng=characters.get('name_eng', ''),
                    role=characters.get('role', ''),
                    role_eng=characters.get('role_eng', ''),
                    description=characters.get('playstyle', ''),
                    description_eng=characters.get('playstyle_eng', ''),
                    defaults={
                        'items': list(characters.get('starting_items', [])),
                        'ability': {
                            'stats': characters.get('stats', {}),
                            'skills': characters.get('skills', []),
                        }
                    }
                )
                created_characters.append(character)

            serializer = CharacterSerializer(created_characters, many=True)

            if created :
                message = '캐릭터가 성공적으로 저장되었습니다.'
                status_code = status.HTTP_201_CREATED
                print("캐릭터 DB 저장 성공!")
            else :
                message = '이미 존재하는 캐릭터입니다.'
                status_code = status.HTTP_200_OK
                print("기존 캐릭터 존재!")

            return JsonResponse({
                'message' : message,
                'characters' : [serializer.data]
            }, status=status_code)
        except Exception as e :
            print(f"🛑 오류: AI 응답 데이터를 DB에 저장하는 데 실패했습니다. 오류: {e}")
            return JsonResponse({
                'message' : 'AI 응답 데이터 DB 저장 실패',
                'ai_response' : characters_data
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

# 캐릭터 DB 조회
class CharacterListView(AuthMixin) :
    def get(self, request, scenario_id) :
        scenario = get_object_or_404(Scenario, id=scenario_id)

        try :
            character = Character.objects.filter(
                scenario=scenario,
                # is_display=True,
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

# 캐릭터 DB 업데이트
class CharacterUpdateView(AuthMixin, UpdateMixin) :
    def put(self, request, character_id) :
        return super().put(request, 'character_id', Character, CharacterSerializer, character_id)

# 이미지 공통 로직 View
class BaseImageView(AuthMixin) :
    STYLE_DESCRIPTION = "Simple and clean 8-bit pixel art,dark background,focus on character,only upper body,like mug shot,only one person/object,wearing hanbok, minimalist, retro video game asset, clear outlines, Korean fairy tale theme. No Japanese or Chinese elements."

    # 에러 응답
    def _handle_error_response(self, message, status_code=status.HTTP_500_INTERNAL_SERVER_ERROR):
        return JsonResponse({
            'message': message
        }, status=status_code)

    # GPT 를 사용하여 캐릭터 정보 생성
    def _generate_characters_info(self, character_name, character_role, character_description) :
        gpt_client = get_azure_openai_client(
            AppSettings.AZURE_OPENAI_API_KEY,
            AppSettings.AZURE_OPENAI_ENDPOINT,
            AppSettings.AZURE_OPENAI_VERSION
        )
        
        if not gpt_client :
            raise Exception('AI 서비스 연결 실패: OpenAI 클라이언트 초기화 오류')

        character_list_str = "\n".join([
            f"- {character_name}: {character_role}, {character_description}"
        ])
        print(f">> 이미지 생성을 위한 캐릭터 정보:\n{character_list_str}")

        summary_prompt = f"""
        Please summarize the following list of characters into a single, concise descriptive sentence for an image generation prompt. Focus on their key roles and appearances.
        Example output: "A brave warrior named Aragorn, a wise wizard Gandalf, and a small hobbit Frodo."

        Character List:
        {character_list_str}
        """
        
        try :
            response = gpt_client.chat.completions.create(
                model=AppSettings.AZURE_OPENAI_DEPLOYMENT,
                messages=[{"role": "user", "content": summary_prompt}],
                temperature=0.5,
                max_tokens=150
            )
            generated_character_info = response.choices[0].message.content.strip()
            print(f">> AI가 생성한 동적 캐릭터 정보: {generated_character_info}\n")
            return generated_character_info
        except Exception as e:
            print(f"🛑 오류: 동적 캐릭터 정보 생성 실패: {e}. 기본 정보를 사용합니다.")
            return "A group of adventurers."
        
    # GPT 를 사용하여 DALL-E 프롬프트 생성
    def _generate_gpt_prompt(self, character_info) :
        gpt_client = get_azure_openai_client(
            AppSettings.AZURE_OPENAI_API_KEY,
            AppSettings.AZURE_OPENAI_ENDPOINT,
            AppSettings.AZURE_OPENAI_VERSION
        )
        
        if not gpt_client :
            raise Exception('AI 서비스 연결 실패: OpenAI 클라이언트 초기화 오류')

        gpt_prompt = f"""
        You are an expert prompt writer for an 8-bit pixel art image generator.background must be simple and dark. Your task is to convert a scene description into a single, visually detailed paragraph for the DALL-E model.
        
        **Consistent Rules (Apply to all images):**
        - **Relevant Characters:** {character_info}
        - **Art Style:** {self.STYLE_DESCRIPTION}

        Combine all of this information into a single descriptive paragraph. Focus on visual details like character actions, expressions, and background elements. Do not use markdown or lists.
        """

        try :
            gpt_response = gpt_client.chat.completions.create(
                model=AppSettings.AZURE_OPENAI_DEPLOYMENT,
                messages=[{"role": "user", "content": gpt_prompt}],
                temperature=0.7,
                max_tokens=250
            )
            dalle_prompt = gpt_response.choices[0].message.content.strip()
            print(f">> 생성된 DALL-E 프롬프트: {dalle_prompt}")
            return dalle_prompt
        except Exception as e :
            raise Exception(f"GPT 프롬프트 생성 실패: {e}")
    
    # DALL-E 3를 사용하여 이미지 생성
    def _generate_dalle_image(self, dalle_prompt, character_id=None) :
        dalle_client = get_azure_dalle_client(
            AppSettings.AZURE_OPENAI_DALLE_APIKEY,
            AppSettings.AZURE_OPENAI_DALLE_ENDPOINT,
            AppSettings.AZURE_OPENAI_DALLE_VERSION
        )

        if not dalle_client :
            raise Exception('AI 서비스 연결 실패: DALL-E 클라이언트 초기화 오류')

        try :
            dalle_response = dalle_client.images.generate(
                model=AppSettings.AZURE_OPENAI_DALLE_DEPLOYMENT,
                prompt=dalle_prompt,
                n=1,
                size="1024x1024",
                style="vivid",
                quality="standard"
            )
            temp_image_url = dalle_response.data[0].url if dalle_response.data else None
            if not temp_image_url :
                raise Exception("DALL-E 3 이미지 생성 실패: 이미지 URL을 가져올 수 없습니다.")
            return temp_image_url
        except Exception as e :
            raise Exception(f"DALL-E 3 이미지 생성 실패 (Character ID: {character_id if character_id else 'N/A'}): {e}")
    
    # 생성된 이미지를 Blob Storage 에 업로드
    def _upload_image_to_blob(self, blob_client, temp_image_url, character_id=None) :
        print(f">> 이미지를 Blob Storage에 업로드합니다. (Blob: {blob_client.blob_name})")
        try :
            image_response = requests.get(temp_image_url, stream=True)
            image_response.raise_for_status() # 200 OK가 아닌 경우 예외 발생

            content_settings_obj = ContentSettings(content_type='image/png')
            blob_client.upload_blob(image_response.content, overwrite=True, content_settings=content_settings_obj)
            final_image_url = blob_client.url
            print(f">> 업로드 성공! 최종 URL: {final_image_url}\n")
            return final_image_url
        except requests.exceptions.RequestException as e :
            raise Exception(f"생성된 이미지 다운로드 실패 (Character ID: {character_id if character_id else 'N/A'}): {e}")
        except Exception as e :
            raise Exception(f"Blob Storage 업로드 실패 (Character ID: {character_id if character_id else 'N/A'}): {e}")
        
    # Character DB의 image_path 업데이트
    def _update_character_image_path(self, character_id, image_path) :
        try :
            character = Character.objects.get(id=character_id)
            character.image_path = image_path
            character.save()
        except Exception as e :
            raise Exception(f"DB 업데이트 실패 (Character ID: {character_id}): {e}")

# 캐릭터 이미지 생성
class CharacterImageCreateView(BaseImageView) :
    def put(self, request, character_id) :
        scenario_title = request.data.get('scenario_title')
        character_name = request.data.get('character_name')
        character_role = request.data.get('character_role')
        character_description = request.data.get('character_description')

        if not all([character_id, scenario_title, character_name, character_role, character_description]):
            return JsonResponse({
                "error": "필수 요청 파라미터(character_id, scenario_title, character_name, character_role, character_description)가 누락되었습니다."
            }, status=status.HTTP_400_BAD_REQUEST)

        container_name = scenario_title.lower().replace(' ', '-')
        blob_name = f'{character_name}.png'

        try :
            blob_util = AzureBlobStorageUtil(AppSettings.AZURE_BLOB_STORAGE_CONNECT_KEY_FOR_IMAGE)
            container_client = blob_util.get_or_create_container(container_name, public=True)
            blob_client = container_client.get_blob_client(blob=blob_name)
            
            existing_image_url = blob_util.check_blob_exists_and_get_url(blob_client)
            if existing_image_url:
                # 타임스탬프를 붙여서 캐시 무효화
                timestamp = int(time.time())
                existing_image_url_with_timestamp = f'{existing_image_url}?t={timestamp}'
                self._update_character_image_path(character_id, existing_image_url_with_timestamp)
                return JsonResponse({
                    'message': '이미지 생성 완료 (기존 이미지 사용)',
                    'character_id': character_id,
                    'image_url': existing_image_url,
                }, status=status.HTTP_200_OK)
            
            generated_character_info = self._generate_characters_info(character_name, character_role, character_description)
            dalle_prompt = self._generate_gpt_prompt(generated_character_info)
            temp_image_url = self._generate_dalle_image(dalle_prompt, character_id)
            final_image_url = self._upload_image_to_blob(blob_client, temp_image_url, character_id)

            # 타임스탬프를 붙여서 캐시 무효화
            timestamp = int(time.time())
            final_image_url_with_timestamp  = f'{final_image_url}?t={timestamp}'
            self._update_character_image_path(character_id, final_image_url_with_timestamp)

            return JsonResponse({
                'message': '이미지 개별 생성 및 업로드 완료',
                'character_id': character_id,
                'image_url': final_image_url,
            }, status=status.HTTP_200_OK)
        except Exception as e:
            return self._handle_error_response(str(e))

# 이미지 삭제
class CharacterImageDeleteView(BaseImageView) :
    def delete(self, request, character_id) :
        if not character_id :
            return JsonResponse({
                "error": "필수 요청 파라미터 character_id 가 누락되었습니다."
            }, status=status.HTTP_400_BAD_REQUEST)

        try :
            character = Character.objects.get(id=character_id)
            
            # image_path가 없는 경우 즉시 성공 응답
            if not character.image_path:
                return JsonResponse({
                    'message': '해당 Character 삭제할 이미지가 없습니다.',
                    'character_id': character_id,
                }, status=status.HTTP_200_OK)

            # URL 디코딩 및 쿼리 스트링 제거
            image_url = character.image_path
            parsed_url = urllib.parse.urlparse(image_url)
            path_parts = parsed_url.path[1:].split('/', 1) 

            if len(path_parts) < 2:
                raise Exception(f"유효하지 않은 이미지 URL 형식 (컨테이너 또는 Blob 이름 누락): {image_url}")

            container_name = path_parts[0]
            blob_name = path_parts[1]

            blob_util = AzureBlobStorageUtil(AppSettings.AZURE_BLOB_STORAGE_CONNECT_KEY_FOR_IMAGE)
            container_client = blob_util.get_or_create_container(container_name, public=True)
            blob_client = container_client.get_blob_client(blob=blob_name)
            
            # Azure Blob Storage에서 이미지 삭제 시도
            try:
                if blob_client.exists():
                    blob_client.delete_blob()
                    print(f"Azure Blob Storage에서 이미지 삭제 완료: {blob_name}")
                else:
                    print(f"Azure Blob Storage에 이미지가 존재하지 않아 삭제를 건너뛰었습니다: {blob_name}")
            except ResourceNotFoundError:
                print(f"Azure Blob Storage에서 Blob '{blob_name}'을(를) 찾을 수 없어 삭제를 건너뛰었습니다.")
            except Exception as blob_delete_e:
                print(f"Azure Blob Storage 이미지 삭제 실패 (Blob: {blob_name}): {blob_delete_e}")
                return self._handle_error_response(
                    f"Azure Blob Storage 이미지 삭제 실패: {blob_delete_e}",
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
                )

            # Blob 삭제가 성공했거나, Blob이 없었을 경우에만 DB 업데이트 진행
            character.image_path = None
            character.save()
            print(f"DB에서 Character ID {character_id}의 image_path 삭제 완료")

            return JsonResponse({
                'message': '이미지 삭제 및 DB 업데이트 완료',
                'character_id': character_id,
            }, status=status.HTTP_200_OK)
        except Character.DoesNotExist:
            return self._handle_error_response(
                f"Moment ID {character_id}를 찾을 수 없습니다.",
                status_code=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            # 기타 예외 (URL 파싱 오류 등) 발생 시
            print(f"이미지 삭제 중 오류 발생: {e}")
            return self._handle_error_response(str(e))
        
# 싱글/멀티모드 게임 통계
class GameStatisticsView(AuthMixin):
    def get(self, request):
        try:
            # 싱글모드에서 가장 많이 선택된 시나리오
            most_selected_scenario_single = SinglemodeSession.objects.filter(
                scenario__is_deleted=False, 
                scenario__is_display=True
            ).values('scenario__title').annotate(count=Count('scenario')).order_by('-count').first()
            scenario_name_single = most_selected_scenario_single['scenario__title'] if most_selected_scenario_single else None

            # 싱글모드에서 가장 많이 선택된 장르
            most_selected_genre_single = SinglemodeSession.objects.filter(
                genre__is_deleted=False, 
                genre__is_display=True
            ).values('genre__name').annotate(count=Count('genre')).order_by('-count').first()
            genre_name_single = most_selected_genre_single['genre__name'] if most_selected_genre_single else None

            # 싱글모드에서 가장 많이 선택된 난이도
            most_selected_difficulty_single = SinglemodeSession.objects.filter(
                difficulty__is_deleted=False, 
                difficulty__is_display=True
            ).values('difficulty__name').annotate(count=Count('difficulty')).order_by('-count').first()
            difficulty_name_single = most_selected_difficulty_single['difficulty__name'] if most_selected_difficulty_single else None

            # 싱글모드에서 가장 많이 선택된 캐릭터
            most_selected_character_single = SinglemodeSession.objects.filter(
                character__is_deleted=False, 
                character__is_display=True
            ).values('character__name').annotate(count=Count('character')).order_by('-count').first()
            character_name_single = most_selected_character_single['character__name'] if most_selected_character_single else None

            # 멀티모드에서 가장 많이 선택된 시나리오
            most_selected_scenario_multi = GameRoomSelectScenario.objects.filter(
                scenario__is_deleted=False, 
                scenario__is_display=True
            ).values('scenario__title').annotate(count=Count('scenario')).order_by('-count').first()
            scenario_name_multi = most_selected_scenario_multi['scenario__title'] if most_selected_scenario_multi else None

            # 멀티모드에서 가장 많이 선택된 장르
            most_selected_genre_multi = GameRoomSelectScenario.objects.filter(
                genre__is_deleted=False, 
                genre__is_display=True
            ).values('genre__name').annotate(count=Count('genre')).order_by('-count').first()
            genre_name_multi = most_selected_genre_multi['genre__name'] if most_selected_genre_multi else None

            # 멀티모드에서 가장 많이 선택된 난이도
            most_selected_difficulty_multi = GameRoomSelectScenario.objects.filter(
                difficulty__is_deleted=False, 
                difficulty__is_display=True
            ).values('difficulty__name').annotate(count=Count('difficulty')).order_by('-count').first()
            difficulty_name_multi = most_selected_difficulty_multi['difficulty__name'] if most_selected_difficulty_multi else None

            # 멀티모드에서 가장 많이 선택된 캐릭터
            most_selected_character_multi = MultimodeSession.objects.filter(
                character__is_deleted=False, 
                character__is_display=True
            ).values('character__name').annotate(count=Count('character')).order_by('-count').first()
            character_name_multi = most_selected_character_multi['character__name'] if most_selected_character_multi else None

            data = {
                'multimode_statistics': {
                    'most_selected_scenario': scenario_name_multi,
                    'most_selected_genre': genre_name_multi,
                    'most_selected_difficulty': difficulty_name_multi,
                    'most_selected_character': character_name_multi,
                },
                'singlemode_statistics': {
                    'most_selected_scenario': scenario_name_single,
                    'most_selected_genre': genre_name_single,
                    'most_selected_difficulty': difficulty_name_single,
                    'most_selected_character': character_name_single,
                }
            }

            return JsonResponse({
                'message': '통계 정보 조회 완료',
                'most_selected_data': data,
            }, status=status.HTTP_200_OK)
        except Exception as e:
            return JsonResponse({
                'message' : 'DB 조회 실패',
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)