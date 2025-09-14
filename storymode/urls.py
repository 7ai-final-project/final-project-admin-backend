from django.urls import path
from storymode.views import StoryFileUploadView, StoryCreateView, StoryListView, StoryUpdateAllView, StoryUpdateView, MomentImageCreateView

urlpatterns = [
    path('upload/stories', StoryFileUploadView.as_view(), name="upload_story"),
    path('create/stories', StoryCreateView.as_view(), name="create_story"),
    path('list/stories', StoryListView.as_view(), name="list_story"),
    path('update/stories/all', StoryUpdateAllView.as_view(), name="update_all_story"),
    path('update/stories/<str:story_id>', StoryUpdateView.as_view(), name="update_story"),
    path('create/images/<str:moment_id>', MomentImageCreateView.as_view(), name="create_story_image"),
    # path('create/images/all', MomentImageCreateAllView.as_view(), name="create_all_story_image"),
]
