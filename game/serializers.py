from rest_framework import serializers
from game.models import Genre, Mode, Difficulty, Scenario, Character


class GenreSerializer(serializers.ModelSerializer) :
    class Meta :
        model = Genre
        fields = ['id', 'name', 'is_display', 'is_deleted']

class ModeSerializer(serializers.ModelSerializer) :
    class Meta :
        model = Mode
        fields = ['id', 'name', 'is_display', 'is_deleted']

class DifficultySerializer(serializers.ModelSerializer) :
    class Meta :
        model = Difficulty
        fields = ['id', 'name', 'is_display', 'is_deleted']

class ScenarioSerializer(serializers.ModelSerializer):
    class Meta:
        model = Scenario
        fields = ['id', 'title', 'title_eng', 'description', 'description_eng', 'image_path', 'is_display', 'is_deleted']

class CharacterSerializer(serializers.ModelSerializer):
    class Meta:
        model = Character
        fields = ['id', 'name', 'name_eng', 'role', 'role_eng', 'description', 'description_eng', 'items', 'ability', 'image_path', 'is_display', 'is_deleted']