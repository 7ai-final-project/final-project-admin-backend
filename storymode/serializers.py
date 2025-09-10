from rest_framework import serializers
from storymode.models import Story


class StorySerializer(serializers.ModelSerializer) :
    class Meta :
        model = Story
        fields = ['id', 'title', 'description', 'start_moment', 'is_display', 'is_deleted']