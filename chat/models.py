from django.db import models
import uuid
from user.models import User
from game.models import GameRoom
 

# 채팅
class ChatMessage(models.Model) :
    MESSAGE_TYPE_CHOICES = [
        ('Lobby', 'lobby'),
        ('Play', 'play'),
    ]

    id = models.UUIDField(primary_key=True, editable=False, default=uuid.uuid4)
    gameroom = models.ForeignKey(GameRoom, on_delete=models.CASCADE, related_name="chatmessage")
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    message_type = models.CharField(max_length=50, choices=MESSAGE_TYPE_CHOICES)
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
 
    class Meta :
        managed = False 
        db_table = 'chatmessage'
 
    def __str__(self):
        return f"[{self.gameroom.name}] {self.user.name}: {self.message[:20]}"