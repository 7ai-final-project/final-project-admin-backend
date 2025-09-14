from django.urls import path
from game.views import (GenreCreateView, GenreListView, GenreUpdateAllView, GenreUpdateView, 
                        ModeCreateView, ModeListView, ModeUpdateView, ModeUpdateAllView, 
                        DifficultyCreateView, DifficultyListView, DifficultyUpdateView, DifficultyUpdateAllView, 
                        SenarioFileUploadView, ScenarioListView, SenarioCreateView, ScenarioUpdateAllView, ScenarioUpdateView,
                        CharacterListView, CharacterCreateView
                        )

urlpatterns = [
    path('create/genres', GenreCreateView.as_view(), name="create_genre"),
    path('list/genres', GenreListView.as_view(), name="list_genres"),
    path('update/genres/all', GenreUpdateAllView.as_view(), name="update_all_genres"),
    path('update/genres/<str:genre_id>', GenreUpdateView.as_view(), name="update_genres"),

    path('create/modes', ModeCreateView.as_view(), name="create_modes"),
    path('list/modes', ModeListView.as_view(), name="list_modes"),
    path('update/modes/all', ModeUpdateAllView.as_view(), name="update_all_modes"),
    path('update/modes/<str:mode_id>', ModeUpdateView.as_view(), name="update_modes"),

    path('create/difficulties', DifficultyCreateView.as_view(), name="create_difficulties"),
    path('list/difficulties', DifficultyListView.as_view(), name="list_difficulties"),
    path('update/difficulties/all', DifficultyUpdateAllView.as_view(), name="update_all_difficulties"),
    path('update/difficulties/<str:difficulty_id>', DifficultyUpdateView.as_view(), name="update_difficulties"),

    path('list/scenarios', ScenarioListView.as_view(), name="list_scenarios"),
    path('upload/scenarios', SenarioFileUploadView.as_view(), name="upload_scenarios"),
    path('create/scenarios', SenarioCreateView.as_view(), name="create_scenarios"),
    path('update/scenarios/all', ScenarioUpdateAllView.as_view(), name="update_all_scenarios"),
    path('update/scenarios/<str:scenario_id>', ScenarioUpdateView.as_view(), name="update_scenarios"),

    path('list/characters/<str:scenario_id>', CharacterListView.as_view(), name="list_characters"),
    path('create/characters/all/', CharacterCreateView.as_view(), name="create_characters"),
    # path('create/characters/images/<str:character_id>', MomentImageCreateView.as_view(), name="create_story_image"),
    # path('update/stories/', StoryUpdateView.as_view(), name="update_story"),
    # path('update/stories/all', StoryUpdateAllView.as_view(), name="update_story_all"),
    # path('create/stories/images', StoryImageCreateView.as_view(), name="create_story_image"),
]
