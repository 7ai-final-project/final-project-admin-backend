import json
from openai import AzureOpenAI
from rest_framework import status
from django.conf import settings
from django.http import JsonResponse
from azure.storage.blob import BlobServiceClient
from storymode.models import Story, StorymodeMoment, StorymodeChoice
from storymode.serializers import StorySerializer
from storymode.mixins import AuthMixin, UpadteMixin, UpdataAllMixin


AZURE_BLOB_STORAGE_CONNECT_KEY = settings.AZURE_BLOB_STORAGE_CONNECT_KEY
AZURE_OPENAI_API_KEY = settings.AZURE_OPENAI_API_KEY
AZURE_OPENAI_ENDPOINT = settings.AZURE_OPENAI_ENDPOINT
AZURE_OPENAI_VERSION = settings.AZURE_OPENAI_VERSION
AZURE_OPENAI_DEPLOYMENT = settings.AZURE_OPENAI_DEPLOYMENT
    
# 전달되는 파일을 Azure Blob Storage 에 업로드
class StoryFileUploadView(AuthMixin) :
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
            
            container = 'stories'
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
class StoryCreateView(AuthMixin) :
    def post(self, request) :
        story_name = request.data.get('story_name')
        blob_name = request.data.get('blob_name')

        if not story_name or not blob_name :
            return JsonResponse({
                'message' : '스토리 이름 혹은 업로드 파일 url 이 필요합니다.'
            }, status=status.HTTP_400_BAD_REQUEST)

        # Azure Blob Storage 에서 파일 내용 가져오기
        story_text = ''
        try:
            print(f"📖 Azure Blob Storage에서 '{blob_name}' 파일을 다운로드합니다...")

            conn_str = AZURE_BLOB_STORAGE_CONNECT_KEY
            blob_service_client = BlobServiceClient.from_connection_string(conn_str=conn_str)
            
            container = 'stories'
            container_client = blob_service_client.get_container_client(container=container)
            blob_client = container_client.get_blob_client(blob=blob_name)
            story_text = blob_client.download_blob().readall().decode('utf-8')
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


        # 프롬프트에 실제 이야기 텍스트를 채워넣기
        PROMPT_TEMPLATE = """
        당신은 주어진 이야기를 분석해서, 플레이어가 선택하며 즐길 수 있는 '인터랙티브 게임'의 데이터로 바꿔주는 전문 게임 작가입니다.

        [당신의 임무]
        아래 [입력 스토리]를 읽고, 이야기의 흐름에 따라 4~5개의 중요한 장면(Moment)으로 나누어 게임 시나리오를 만드세요.

        [작업 규칙]
        1.  **장면 나누기:** 이야기의 시작, 위기, 절정, 결말 등을 고려하여 장면을 나누고, 각 장면에 고유한 영어 ID(예: MOMENT_START)를 붙여주세요.
        2.  **구조화:** 각 장면은 'description' 키에 설명을 담아야 합니다.
        3.  **선택지 구조:** 각 장면의 'choices'는 객체(Object)들의 배열(Array)이어야 합니다. 각 객체는 'action_type'과 다음 장면을 가리키는 'next_moment_id' 키를 반드시 포함해야 합니다.
        4.  **엔딩 처리:** 이야기의 끝을 맺는 장면(엔딩)에는 'choices' 키 자체를 포함하지 마세요.
        5.  **JSON 형식 준수:** 최종 결과는 반드시 아래 [출력 JSON 형식]과 똑같은 구조의 JSON 데이터로만 출력해야 합니다. 다른 말은 절대 덧붙이지 마세요.

        [입력 스토리]
        ---
        {story_text}
        ---

        [출력 JSON 형식]
        {{
        "title": "이야기 제목",
        "description": "이야기의 전체적인 배경이나 주제 (2-3문장으로 요약)",
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
                {{ "action_type": "BAD", "next_moment_id": "ENDING_A" }}
            ]
            }},
            "ENDING_A": {{
            "description": "[배드 엔딩] 비극적인 결말에 대한 핵심 목표 설명."
            }}
        }}
        }}
        """

        final_prompt = PROMPT_TEMPLATE.format(story_text=story_text)
        print("AI에게 이야기 분석을 요청하고 있습니다... (시간이 조금 걸릴 수 있어요)")

        # Azure OpenAI API 요청
        try:
            response = client.chat.completions.create(
                model=AZURE_OPENAI_DEPLOYMENT,
                messages=[{"role": "user", "content": final_prompt}],
                temperature=0.5,                        # 너무 제멋대로 만들지 않도록 온도를 약간 낮춥니다.
                response_format={"type": "json_object"} # "결과는 무조건 JSON 형식으로 줘!" 라는 강력한 옵션입니다.
            )
        
            # AI의 응답 내용(JSON 텍스트)
            ai_response_content = response.choices[0].message.content
            print("AI가 응답을 완료했습니다!")

            # JSON 텍스트를 딕셔너리로 변환
            story_json = json.loads(ai_response_content)
            print(story_json)

            # DB 저장
            try :
                # 1. Story 에 데이터 저장
                story_instance = Story.objects.create(
                    title=story_json.get('title', story_name),
                    description=story_json.get('description', '')
                )

                # 2. StorymodeMoment 에 데이터 저장
                moment_id_to_instance = {}
                for moment_id, moment_data in story_json['moments'].items() :
                    moment_instance = StorymodeMoment.objects.create(
                        story=story_instance,
                        title=moment_data.get('title', moment_id),
                        description=moment_data.get('description', '')
                    )
                    moment_id_to_instance[moment_id] = moment_instance

                # 3. Story 의 start_moment 업데이트
                start_moment_id_from_ai = story_json.get('start_moment_id')
                if start_moment_id_from_ai and start_moment_id_from_ai in moment_id_to_instance :
                    story_instance.start_moment = moment_id_to_instance[start_moment_id_from_ai]
                    story_instance.save()
                else :
                    print(f"경고: AI 응답에 start_moment_id가 없거나 유효하지 않습니다: {start_moment_id_from_ai}")

                # 4. StorymodeChoice 에 데이터 저장
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

        except Exception as e:
            print(f"죄송합니다. AI를 호출하는 중에 오류가 발생했습니다: {e}")
            return JsonResponse({
                'message' : 'AI 처리 중 오류 발생',
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
                        # 'image_path' : moment.image_path
                    }
                
                # 스토리 정보
                story_list_data.append({
                    'id' : str(story.id),
                    'title' : story.title,
                    'description' : story.description,
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
class StoryUpdateView(AuthMixin, UpadteMixin) :
    def put(self, request, story_id) :
        return super().put(request, 'story_id', Story, StorySerializer, story_id)

# 스토리 DB 전체 업데이트
class StoryUpdateAllView(AuthMixin, UpdataAllMixin) :
    def put(self, request) :
        return super().put(request, Story)