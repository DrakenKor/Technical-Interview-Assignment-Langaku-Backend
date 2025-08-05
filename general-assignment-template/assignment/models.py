from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils import timezone


class User(AbstractUser):
    """
    Custom User model that extends the default Django User model.
    This can be used to add additional fields or methods in the future.
    """

    pass


class LearningLog(models.Model):
    """
    Model to store learning logs with word count and study time.
    Supports idempotence through unique constraints on user/timestamp.
    """

    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="learning_logs"
    )
    word_count = models.PositiveIntegerField()
    study_time_minutes = models.PositiveIntegerField()
    timestamp = models.DateTimeField(default=timezone.now, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ["user", "timestamp"]
        indexes = [
            models.Index(fields=["user", "timestamp"]),
            models.Index(fields=["timestamp"]),
        ]
        ordering = ["-timestamp"]

    def __str__(self):
        return f"User {self.user.id} - {self.word_count} words, {self.study_time_minutes}min at {self.timestamp}"
