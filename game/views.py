import json
import requests
from openai import AzureOpenAI
from rest_framework import status
from django.conf import settings
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from azure.storage.blob import BlobServiceClient, ContentSettings
from azure.core.exceptions import ResourceNotFoundError
from game.models import Genre, Mode, Difficulty, Scenario, Character
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
                            "notable_characters": ["핵심 인물/집단 3~6개"],
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
            "content": "너는 창의적인 캐릭터 창작가다. 캐릭터 창작에 도움이 되는 핵심만 간결히 요약해라.",
        }
        
        user = {
            "role": "user",
            "content": f"""다음 시나리오 정보를 바탕으로 캐릭터 설명
                            형식(JSON): {
                                {
                                    "name": "캐릭터 이름",
                                    "name_eng": "캐릭터 영어 이름",
                                    "role": "클래스/아키타입(탱커/정찰자/현자/외교가/트릭스터 등)",
                                    "role_eng": "클래스/아키타입(탱커/정찰자/현자/외교가/트릭스터 등)를 영어로 번역",
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

            character_json = json.loads(ai_response_content)
            print(character_json)
        except Exception as e :
            print(f"🛑 오류: AI를 호출하는 중에 오류가 발생했습니다: {e}")
            return JsonResponse({
                'message': f'AI 처리 중 오류 발생: {e}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        # AI 응답 데이터 DB 저장
        try :
            # 캐릭터 DB 저장
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
                'message' : message,
                'characters' : [serializer.data]
            }, status=status.status_code)
        except Exception as e :
            print(f"🛑 오류: AI 응답 데이터를 DB에 저장하는 데 실패했습니다. 오류: {e}")
            return JsonResponse({
                'message' : 'AI 응답 데이터 DB 저장 실패',
                'ai_response' : character_json
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

# 이미지 공통 로직 View
class BaseImageView(AuthMixin) :
    # CHARACTERS_INFO = "Haesik (a girl in traditional yellow and red Hanbok), Dalsik (her younger brother in white and gray Hanbok), and a large, slightly foolish Tiger. Or a woodcutter and a ghost from a well."
    STYLE_DESCRIPTION = "Simple and clean 8-bit pixel art, minimalist, retro video game asset, clear outlines, Korean fairy tale theme. No Japanese or Chinese elements."

    # 에러 응답
    def _handle_error_response(self, message, status_code=status.HTTP_500_INTERNAL_SERVER_ERROR):
        return JsonResponse({
            'message': message
        }, status=status_code)

    # GPT 를 사용하여 DALL-E 프롬프트 생성
    def _generate_gpt_prompt(self, moment_description, character_id=None) :
        gpt_client = get_azure_openai_client(
            AppSettings.AZURE_OPENAI_API_KEY,
            AppSettings.AZURE_OPENAI_ENDPOINT,
            AppSettings.AZURE_OPENAI_VERSION
        )
        
        if not gpt_client :
            raise Exception('AI 서비스 연결 실패: OpenAI 클라이언트 초기화 오류')

        # - **Relevant Characters:** {self.CHARACTERS_INFO}
        gpt_prompt = f"""
        You are an expert prompt writer for an 8-bit pixel art image generator. Your task is to convert a scene description into a single, visually detailed paragraph for the DALL-E model.
        **Consistent Rules (Apply to all images):**
        - **Art Style:** {self.STYLE_DESCRIPTION}
        **Current Scene Description to Convert:**
        - "{moment_description}"
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
            raise Exception(f"GPT 프롬프트 생성 실패 (Moment ID: {character_id if character_id else 'N/A'}): {e}")
    
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
        character_description = request.data.get('character_description')

        if not character_id :
            return JsonResponse({
                "error": "character_id 가 누락되었습니다."
            }, status=status.HTTP_400_BAD_REQUEST)

        container_name = scenario_title.lower().replace(' ', '-')
        blob_name = f'{character_name}.png'

        try :
            blob_util = AzureBlobStorageUtil(AppSettings.AZURE_BLOB_STORAGE_CONNECT_KEY_FOR_IMAGE)
            container_client = blob_util.get_or_create_container(container_name, public=True)
            blob_client = container_client.get_blob_client(blob=blob_name)
            
            existing_image_url = blob_util.check_blob_exists_and_get_url(blob_client)
            print('existing_image_url', existing_image_url)
            if existing_image_url:
                self._update_character_image_path(character_id, existing_image_url)
                return JsonResponse({
                    'message': '이미지 생성 완료 (기존 이미지 사용)',
                    'character_id': character_id,
                    'image_url': existing_image_url,
                }, status=status.HTTP_200_OK)
            
            dalle_prompt = self._generate_gpt_prompt(character_description, character_id)
            temp_image_url = self._generate_dalle_image(dalle_prompt, character_id)
            final_image_url = self._upload_image_to_blob(blob_client, temp_image_url, character_id)
            self._update_character_image_path(character_id, final_image_url)

            return JsonResponse({
                'message': '이미지 개별 생성 및 업로드 완료',
                'character_id': character_id,
                'image_url': final_image_url,
            }, status=status.HTTP_200_OK)
        except Exception as e:
            return self._handle_error_response(str(e))