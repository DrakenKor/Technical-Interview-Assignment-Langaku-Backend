from rest_framework import serializers
from .models import LearningLog
from django.utils import timezone


class LearningLogCreateSerializer(serializers.ModelSerializer):
    timestamp = serializers.DateTimeField(required=False)

    class Meta:
        model = LearningLog
        fields = ["word_count", "study_time_minutes", "timestamp"]

    def validate_word_count(self, value):
        if value <= 0:
            raise serializers.ValidationError("Word count must be positive")
        return value

    def validate_study_time_minutes(self, value):
        if value <= 0:
            raise serializers.ValidationError("Study time must be positive")
        return value

    def create(self, validated_data):
        if "timestamp" not in validated_data:
            validated_data["timestamp"] = timezone.now()

        validated_data["user"] = self.context["request"].user

        learning_log, created = LearningLog.objects.get_or_create(
            user=validated_data["user"],
            timestamp=validated_data["timestamp"],
            defaults={
                "word_count": validated_data["word_count"],
                "study_time_minutes": validated_data["study_time_minutes"],
            },
        )

        if not created:
            learning_log.word_count = validated_data["word_count"]
            learning_log.study_time_minutes = validated_data["study_time_minutes"]
            learning_log.save()

        return learning_log


class LearningLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = LearningLog
        fields = ["id", "word_count", "study_time_minutes", "timestamp", "created_at"]


class SummaryQuerySerializer(serializers.Serializer):
    from_time = serializers.DateTimeField(required=True, input_formats=["iso-8601"])
    to = serializers.DateTimeField(required=True, input_formats=["iso-8601"])
    granularity = serializers.ChoiceField(
        choices=["hour", "day", "month"], default="day"
    )
    moving_average_window = serializers.IntegerField(default=3, min_value=1)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Handle the 'from' parameter name issue since 'from' is a Python keyword
        if (
            hasattr(self, "initial_data")
            and self.initial_data
            and "from" in self.initial_data
        ):
            self.initial_data = self.initial_data.copy()
            self.initial_data["from_time"] = self.initial_data.pop("from")
