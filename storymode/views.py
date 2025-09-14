import json
import requests
from openai import AzureOpenAI
from rest_framework import status
from django.conf import settings
from django.http import JsonResponse
from azure.storage.blob import BlobServiceClient, ContentSettings
from azure.core.exceptions import ResourceNotFoundError
from storymode.models import Story, StorymodeMoment, StorymodeChoice
from storymode.serializers import StorySerializer
from storymode.mixins import AuthMixin, UpdateMixin, UpdateAllMixin


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
        
    
# 전달되는 스토리 파일을 Azure Blob Storage 에 업로드
class StoryFileUploadView(AuthMixin) :
    def post(self, request) :
        file = request.FILES.get('file')

        if not file :
            return JsonResponse({
                'message' : '파일이 없습니다.'
            }, status=status.HTTP_400_BAD_REQUEST)

        # Azure Blob Storage 파일 업로드
        try :
            blob_util = AzureBlobStorageUtil(AppSettings.AZURE_BLOB_STORAGE_CONNECT_KEY_FOR_FILE)
            container_client = blob_util.get_or_create_container('stories')
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

# Azure Blob Storage 에 업로드된 스토리 파일을 읽어서 DB 에 데이터 저장
class StoryCreateView(AuthMixin) :
    def post(self, request) :
        story_name = request.data.get('story_name')
        blob_name = request.data.get('blob_name')

        if not story_name or not blob_name :
            return JsonResponse({
                'message' : '스토리 이름 혹은 업로드 파일 url 이 필요합니다.'
            }, status=status.HTTP_400_BAD_REQUEST)

        # 1. Azure Blob Storage 에서 파일 내용 가져오기
        story_text = ''
        try:
            print(f"📖 Azure Blob Storage에서 '{blob_name}' 파일을 다운로드합니다...")
            blob_util = AzureBlobStorageUtil(AppSettings.AZURE_BLOB_STORAGE_CONNECT_KEY_FOR_FILE)
            container_client = blob_util.get_or_create_container('stories')
            story_text = blob_util.download_blob_as_text(
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

        # 3. AI 프롬프트 구성 및 Azure OpenAI 요청
        PROMPT_TEMPLATE = """
        당신은 주어진 평면적인 이야기를 분석해서, 플레이어의 선택에 따라 이야기가 달라지는 '가지가 나뉘는 인터랙티브 게임(branching narrative)'의 데이터로 '재창조'하는 전문 게임 시나리오 작가입니다.

        [당신의 임무]
        아래 [입력 스토리]를 기반으로, 플레이어에게 흥미로운 선택의 순간을 제공하는 게임 시나리오용 JSON을 만드세요.

        [작업 규칙]
        1.  **title 생성:**
            *   `title` 키에는 이야기의 제목을 바탕으로 한 **'한글 title'**을 만들어주세요. (예: "의좋은 형제")
            *   `title_eng` 키에는 한글 title을 영어로 번역하고, 띄어쓰기를 하이픈(-)으로 연결한 **'영문 title'**를 만들어주세요. (예: "good-brothers")

        2.  **장면 나누기:** 이야기의 전통적인 구조(기승전결)를 참고하여 4~5개의 핵심 장면(Moment)으로 나누고, 각 장면에 고유한 영어 ID(예: MOMENT_START)를 붙여주세요.

        3.  **분기 생성:** 플레이어의 선택이 의미 있도록, 원작에 없더라도 선택의 결과로 이어질 '새로운 장면'이나 '짧은 엔딩'(좋은/나쁜/재미있는 엔딩 등)을 1~2개 이상 창의적으로 만들어내야 합니다. 단, 모든 새로운 분기는 원작의 핵심 교훈을 강화하거나, 등장인물의 성격을 더 깊이 탐구하는 방향으로 만들어져야 합니다.

        4.  **장면 묘사 원칙 (클리프행어):** 선택지가 있는 장면(엔딩이 아닌 장면)의 'description'은, 반드시 플레이어가 선택을 내리기 직전의 긴장감 넘치는 상황까지만 묘사해야 합니다. 선택의 결과를 미리 암시하거나 결론을 내리면 절대 안 됩니다.
            *   (예시): "주인공은 동굴 깊은 곳에서 거대한 무언가가 천천히 눈을 뜨는 것을 보았다." 처럼, "그래서 어떻게 됐을까?" 하고 궁금해하는 순간에 묘사를 멈춰야 합니다.

        5.  **논리적 일관성 검증 (인과관계):** 선택지는 '원인(Cause)', 이어지는 장면의 내용은 '결과(Effect)'입니다. 이 둘은 반드시 명확하고 설득력 있는 인과관계로 이어져야 합니다. '친구를 구하러 간다'는 선택지가 '혼자 보물을 발견하는' 장면으로 이어지는 것처럼, 논리적으로 말이 안 되는 연결은 절대 만들면 안 됩니다.

        6.  **완벽한 기술적 연결:** 각 'choices' 배열 안의 모든 선택지는, 반드시 'next_moment_id' 키를 통해 이 JSON 파일 내에 실제로 '정의된' 다른 장면 ID로 연결되어야 합니다. 이것은 매우 중요한 기술적 규칙입니다.

        7.  **엔딩 처리:** 이야기의 끝을 맺는 장면(엔딩)에는 'choices' 키 자체를 포함하지 마세요. 엔딩의 'description'은 최종적인 결과와 이야기가 주는 교훈을 요약해야 합니다.

        8.  **JSON 형식 준수:** 최종 결과는 반드시 아래 [출력 JSON 형식]과 똑같은 구조의 JSON 데이터로만 출력해야 합니다. 설명이나 다른 말을 절대 덧붙이지 마세요.

        [입력 스토리]
        ---
        {story_text}
        ---

        [출력 JSON 형식]
        {{
            "title": "이야기 제목",
            "title_eng" : "이야기 영어 제목",
            "description": "이야기의 전체적인 배경이나 주제 (2-3문장으로 요약)",
            "description_eng": "이야기의 전체적인 배경이나 주제 (2-3문장으로 요약)를 영어로 번역",
            "start_moment_id": "MOMENT_START",
            "moments": {{
                "MOMENT_START": {{
                    "description": "첫 번째 장면에 대한 핵심 목표 설명. (예: 주인공이 모험을 떠나게 되는 계기)",
                    "choices": [
                        {{ "action_type": "NEUTRAL", "next_moment_id": "MOMENT_CONFLICT" }}
                    ]
                }},
                "MOMENT_CONFLICT": {{
                    "description": "두 번째 장면에 대한 핵심 목표 설명. (예: 주인공이 첫 번째 시련이나 갈등에 부딪힘)",
                    "choices": [
                        {{ "action_type": "GOOD", "next_moment_id": "MOMENT_CLIMAX" }},
                        {{ "action_type": "BAD", "next_moment_id": "ENDING_BAD_A" }}
                    ]
                }},
                "MOMENT_CLIMAX": {{
                    "description": "이야기의 절정. 주인공이 중요한 결정을 내림.",
                    "choices": [
                        {{ "action_type": "GOOD", "next_moment_id": "ENDING_GOOD" }},
                        {{ "action_type": "NEUTRAL", "next_moment_id": "ENDING_BAD_A" }}
                    ]
                }},
                "ENDING_GOOD": {{
                    "description": "[해피 엔딩] 원작의 교훈을 따랐을 때의 긍정적인 결말."
                }},
                "ENDING_BAD_A": {{
                    "description": "[배드 엔딩] 다른 선택을 했을 때 이어지는 비극적인 결말."
                }}
            }}
        }}
        """

        final_prompt = PROMPT_TEMPLATE.format(story_text=story_text)
        print("AI에게 이야기 분석을 요청하고 있습니다... (시간이 조금 걸릴 수 있어요)")

        try :
            response = client.chat.completions.create(
                model=AppSettings.AZURE_OPENAI_DEPLOYMENT,
                messages=[{"role": "user", "content": final_prompt}],
                temperature=0.5,                        # 너무 제멋대로 만들지 않도록 온도를 약간 낮춥니다.
                response_format={"type": "json_object"} # "결과는 무조건 JSON 형식으로 줘!" 라는 강력한 옵션입니다.
            )
        
            ai_response_content = response.choices[0].message.content
            print("AI가 응답을 완료했습니다!")

            story_json = json.loads(ai_response_content)
            print(story_json)
        except Exception as e :
            print(f"🛑 오류: AI를 호출하는 중에 오류가 발생했습니다: {e}")
            return JsonResponse({
                'message': f'AI 처리 중 오류 발생: {e}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        # 4. AI 응답 데이터 DB 저장
        try :
            # Story 에 데이터 저장
            story_instance = Story.objects.create(
                title=story_json.get('title', story_name),
                title_eng=story_json.get('title_eng', ''),
                description=story_json.get('description', ''),
                description_eng=story_json.get('description_eng', '')
            )

            # StorymodeMoment 에 데이터 저장
            moment_id_to_instance = {}
            for moment_id, moment_data in story_json['moments'].items() :
                moment_instance = StorymodeMoment.objects.create(
                    story=story_instance,
                    title=moment_data.get('title', moment_id),
                    description=moment_data.get('description', '')
                )
                moment_id_to_instance[moment_id] = moment_instance

            # Story 의 start_moment 업데이트
            start_moment_id_from_ai = story_json.get('start_moment_id')
            if start_moment_id_from_ai and start_moment_id_from_ai in moment_id_to_instance :
                story_instance.start_moment = moment_id_to_instance[start_moment_id_from_ai]
                story_instance.save()
            else :
                print(f"경고: AI 응답에 start_moment_id가 없거나 유효하지 않습니다: {start_moment_id_from_ai}")

            # StorymodeChoice 에 데이터 저장
            for moment_id, moment_data in story_json['moments'].items() :
                current_moment_instance = moment_id_to_instance[moment_id]
                if 'choices' in moment_data :
                    for choice_data in moment_data['choices'] :
                        next_moment_id_from_ai  = choice_data.get('next_moment_id')

                        next_moment_instance = None
                        if next_moment_id_from_ai and next_moment_id_from_ai in moment_id_to_instance :
                            next_moment_instance = moment_id_to_instance[next_moment_id_from_ai]
                        
                        StorymodeChoice.objects.create(
                            moment=current_moment_instance,
                            next_moment=next_moment_instance,
                            action_type=choice_data.get('action_type')
                        )

            print("AI 응답 데이터 DB 저장 성공!")
            return JsonResponse({
                'message' : '인터랙티브 스토리 생성 및 저장 성공',
                'story_id' : str(story_instance.id),
                'data' : story_json
            }, status=status.HTTP_201_CREATED)
        except Exception as e :
            print(f"🛑 오류: AI 응답 데이터를 DB에 저장하는 데 실패했습니다. 오류: {e}")
            return JsonResponse({
                'message' : 'AI 응답 데이터 DB 저장 실패',
                'ai_response' : story_json
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

# 스토리 DB 조회
class StoryListView(AuthMixin) :
    def get(self, request) :
        try :
            stories = Story.objects.filter(is_display=True, is_deleted=False).prefetch_related('moments__choices')
            # stories = Story.objects.all().prefetch_related('moments__choices')

            story_list_data = []
            for story in stories :
                moments_data = {}
                for moment in story.moments.all() :
                    choices_data = []
                    for choice in moment.choices.all() :
                        # 선택지 정보
                        choices_data.append({
                            'action_type' : choice.action_type,
                            'next_moment_id' : str(choice.next_moment.id) if choice.next_moment else None
                        })
                    
                    # 분기점 정보
                    moments_data[str(moment.id)] = {
                        'title' : moment.title,
                        'description' : moment.description,
                        'choices_data' : choices_data,
                        'image_path' : moment.image_path
                    }
                
                # 스토리 정보
                story_list_data.append({
                    'id' : str(story.id),
                    'title' : story.title,
                    'title_eng' : story.title_eng,
                    'description' : story.description,
                    'description_eng' : story.description_eng,
                    'content' : json.dumps({
                        'start_moment_id' : str(story.start_moment.id) if story.start_moment else None,
                        'start_moment_title' : story.start_moment.title if story.start_moment else None,
                        'moments' : moments_data
                    }),
                    'is_display' : story.is_display,
                    'is_deleted' : story.is_deleted
                })
            
            return JsonResponse({
                'message' : '스토리 목록 조회 성공',
                'stories' : story_list_data
            }, status=status.HTTP_200_OK)
        except Exception as e :
            print(f"🛑 오류: 스토리 목록을 조회하는 데 실패했습니다. 오류: {e}")
            return JsonResponse({
                'message' : '스토리 목록 조회 실패'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

# 스토리 DB 업데이트
class StoryUpdateView(AuthMixin, UpdateMixin) :
    def put(self, request, story_id) :
        return super().put(request, 'story_id', Story, StorySerializer, story_id)

# 스토리 DB 전체 업데이트
class StoryUpdateAllView(AuthMixin, UpdateAllMixin) :
    def put(self, request) :
        return super().put(request, Story)

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
    def _generate_gpt_prompt(self, moment_description, moment_id=None) :
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
            raise Exception(f"GPT 프롬프트 생성 실패 (Moment ID: {moment_id if moment_id else 'N/A'}): {e}")
    
    # DALL-E 3를 사용하여 이미지 생성
    def _generate_dalle_image(self, dalle_prompt, moment_id=None) :
        dalle_client = get_azure_dalle_client(
            AppSettings.AZURE_OPENAI_DALLE_APIKEY,
            AppSettings.AZURE_OPENAI_DALLE_ENDPOINT,
            AppSettings.AZURE_OPENAI_DALLE_VERSION
        )
        print('dalle_client', dalle_client)

        if not dalle_client :
            raise Exception('AI 서비스 연결 실패: DALL-E 클라이언트 초기화 오류')

        try :
            print('여기')
            dalle_response = dalle_client.images.generate(
                model=AppSettings.AZURE_OPENAI_DALLE_DEPLOYMENT,
                prompt=dalle_prompt,
                n=1,
                size="1024x1024",
                style="vivid",
                quality="standard"
            )
            print('dalle_response', dalle_response)
            temp_image_url = dalle_response.data[0].url if dalle_response.data else None
            print('temp_image_url', temp_image_url)
            if not temp_image_url :
                raise Exception("DALL-E 3 이미지 생성 실패: 이미지 URL을 가져올 수 없습니다.")
            return temp_image_url
        except Exception as e :
            raise Exception(f"DALL-E 3 이미지 생성 실패 (Moment ID: {moment_id if moment_id else 'N/A'}): {e}")
    
    # 생성된 이미지를 Blob Storage 에 업로드
    def _upload_image_to_blob(self, blob_client, temp_image_url, moment_id=None) :
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
            raise Exception(f"생성된 이미지 다운로드 실패 (Moment ID: {moment_id if moment_id else 'N/A'}): {e}")
        except Exception as e :
            raise Exception(f"Blob Storage 업로드 실패 (Moment ID: {moment_id if moment_id else 'N/A'}): {e}")
    
    # StorymodeMoment DB의 image_path 업데이트
    def _update_moment_image_path(self, moment_id, image_path) :
        try :
            moment = StorymodeMoment.objects.get(id=moment_id)
            moment.image_path = image_path
            moment.save()
        except Exception as e :
            raise Exception(f"DB 업데이트 실패 (Moment ID: {moment_id}): {e}")


# 이미지 생성
class MomentImageCreateView(BaseImageView) :
    def put(self, request, moment_id) :
        story_title = request.data.get('story_title')
        moment_title = request.data.get('moment_title')
        moment_description = request.data.get('moment_description')

        if not all([moment_id, moment_title, moment_description, story_title]):
            return JsonResponse({
                "error": "필수 요청 파라미터(moment_id, moment_title, moment_description, story_title)가 누락되었습니다."
            }, status=status.HTTP_400_BAD_REQUEST)

        container_name = story_title.lower().replace(' ', '-')
        blob_name = f'{moment_title}.png'
        print('container_name', container_name)
        print('blob_name', blob_name)

        try :
            blob_util = AzureBlobStorageUtil(AppSettings.AZURE_BLOB_STORAGE_CONNECT_KEY_FOR_IMAGE)
            container_client = blob_util.get_or_create_container(container_name, public=True)
            blob_client = container_client.get_blob_client(blob=blob_name)
            print('blob_util', blob_util)
            print('container_client', container_client)
            print('blob_client', blob_client)
            
            existing_image_url = blob_util.check_blob_exists_and_get_url(blob_client)
            print('existing_image_url', existing_image_url)
            if existing_image_url:
                self._update_moment_image_path(moment_id, existing_image_url)
                return JsonResponse({
                    'message': '이미지 생성 완료 (기존 이미지 사용)',
                    'moment_id': moment_id,
                    'image_url': existing_image_url,
                }, status=status.HTTP_200_OK)
            
            dalle_prompt = self._generate_gpt_prompt(moment_description, moment_id)
            temp_image_url = self._generate_dalle_image(dalle_prompt, moment_id)
            final_image_url = self._upload_image_to_blob(blob_client, temp_image_url, moment_id)
            self._update_moment_image_path(moment_id, final_image_url)

            return JsonResponse({
                'message': '이미지 개별 생성 및 업로드 완료',
                'moment_id': moment_id,
                'image_url': final_image_url,
            }, status=status.HTTP_200_OK)
        except Exception as e:
            return self._handle_error_response(str(e))
    
# 이미지 일괄 생성
# class MomentImageCreateAllView(BaseImageView) : 
#     def put(self, request) :
#         story_id = request.data.get('story_id')
#         story_title = request.data.get('story_title')
#         moments_data = request.data.get('moments')

#         if not all([story_id, story_title, moments_data]):
#             return JsonResponse({
#                 "error": "필수 요청 파라미터(story_id, story_title, moments)가 누락되었습니다."
#             }, status=status.HTTP_400_BAD_REQUEST)

#         container_name = story_title.lower()
#         image_results = []

#         try:
#             blob_util = AzureBlobStorageUtil(AppSettings.AZURE_BLOB_STORAGE_CONNECT_KEY_FOR_IMAGE)
#             container_client = blob_util.get_or_create_container(container_name)
#             blob_client = container_client.get_blob_client(blob=blob_name)
#         except Exception as e:
#             return self._handle_error_response(str(e))
        
#         for moment_id, moment_details in moments_data.items():
#             moment_title = moment_details.get('title')
#             moment_description = moment_details.get('description')
            
#             if not all([moment_id, moment_title, moment_description]):
#                 print(f"WARNING: Moment ID {moment_id}: 필수 데이터(title, description)가 누락되었습니다. 건너뜁니다.")
#                 continue

#             blob_name = f'{moment_title.lower().replace(" ", "-")}.png'

#             try:
#                 existing_image_url = blob_util.check_blob_exists_and_get_url(blob_client)
#                 if existing_image_url:
#                     self._update_moment_image_path(moment_id, existing_image_url)
#                     image_results.append({
#                         'moment_id': moment_id,
#                         'image_url': existing_image_url,
#                         'status': 'existing'
#                     })
#                     continue
            
#                 dalle_prompt = self._generate_gpt_prompt(moment_description, moment_id)
#                 temp_image_url = self._generate_dalle_image(dalle_prompt, moment_id)
#                 final_image_url = self._upload_image_to_blob(blob_client, temp_image_url, moment_id)
#                 self._update_moment_image_path(moment_id, final_image_url)

#                 image_results.append({
#                     'moment_id': moment_id,
#                     'image_url': final_image_url,
#                     'status': 'created'
#                 })
#             except Exception as e:
#                 print(f"ERROR: Moment ID {moment_id} 이미지 처리 중 오류 발생: {e}. 다음 Moment로 진행합니다.")
#                 image_results.append({
#                     'moment_id': moment_id,
#                     'image_url': None,
#                     'status': 'failed',
#                     'error': str(e)
#                 })
#                 continue

#         return JsonResponse({
#             'message': '이미지 일괄 생성 및 업로드 처리 완료',
#             'story_id': story_id,
#             'image_results': image_results
#         }, status=status.HTTP_200_OK)