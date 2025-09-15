from rest_framework import serializers
from storymode.models import Story


class StorySerializer(serializers.ModelSerializer) :
    class Meta :
        model = Story
        fields = ['id', 'title', 'title_eng', 'description', 'description_eng', 'start_moment', 'image_path', 'is_display', 'is_deleted']