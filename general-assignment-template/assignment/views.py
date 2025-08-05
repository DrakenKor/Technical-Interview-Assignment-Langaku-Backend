from rest_framework import status, viewsets
from rest_framework.decorators import api_view, action
from rest_framework.response import Response
from django.core.management import call_command
from django.db import connection
from .models import User
from .serializers import (
    LearningLogCreateSerializer,
    LearningLogSerializer,
    SummaryQuerySerializer,
)


@api_view(["POST"])
def initialize_data(request):
    try:
        file_name = request.data.get("file", "MOCK_DATA.json")
        print(f"Initializing data from {file_name}")
        call_command("init_data", file=file_name)
        return Response(
            {"message": f"Data initialized successfully from {file_name}"},
            status=status.HTTP_200_OK,
        )
    except Exception as e:
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(["POST"])
def create_learning_record(request):
    """
    POST /records - Create a learning log record with idempotence support
    """
    if not request.user.is_authenticated:
        return Response(
            {"error": "Authentication required"}, status=status.HTTP_401_UNAUTHORIZED
        )

    serializer = LearningLogCreateSerializer(
        data=request.data, context={"request": request}
    )
    if serializer.is_valid():
        learning_log = serializer.save()
        return Response(
            LearningLogSerializer(learning_log).data, status=status.HTTP_201_CREATED
        )
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


def calculate_moving_average(data, window):
    """
    Calculate Simple Moving Average for the given data and window size
    """
    if len(data) < window:
        return None

    return sum(data[-window:]) / window


class UserViewSet(viewsets.ViewSet):
    """
    ViewSet for user-related operations.
    """

    @action(detail=False, methods=["get"])
    def me(self, request):
        """
        Returns the username of the logged-in user.
        """
        if request.user.is_authenticated:
            return Response(
                {"username": request.user.username}, status=status.HTTP_200_OK
            )
        else:
            return Response(
                {"error": "User not authenticated"}, status=status.HTTP_401_UNAUTHORIZED
            )

    @action(detail=True, methods=["get"])
    def summary(self, request, pk=None):
        """
        GET /users/{id}/summary - Get aggregated learning data with moving averages
        """
        try:
            user = User.objects.get(pk=pk)
        except User.DoesNotExist:
            return Response(
                {"error": "User not found"}, status=status.HTTP_404_NOT_FOUND
            )

        query_serializer = SummaryQuerySerializer(data=request.query_params)

        if not query_serializer.is_valid():
            return Response(query_serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        from_time = query_serializer.validated_data["from_time"]
        to = query_serializer.validated_data["to"]
        granularity = query_serializer.validated_data["granularity"]
        window = query_serializer.validated_data["moving_average_window"]

        if from_time >= to:
            return Response(
                {"error": "from_time must be before to_time"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # PostgreSQL date truncation based on granularity
        trunc_format = {"hour": "hour", "day": "day", "month": "month"}[granularity]

        # Build aggregation query using raw SQL for PostgreSQL date_trunc
        query = """
            SELECT
                DATE_TRUNC(%s, timestamp) as period,
                SUM(word_count) as total_words,
                SUM(study_time_minutes) as total_time
            FROM assignment_learninglog
            WHERE user_id = %s
                AND timestamp >= %s
                AND timestamp <= %s
            GROUP BY DATE_TRUNC(%s, timestamp)
            ORDER BY period
        """

        with connection.cursor() as cursor:
            cursor.execute(query, [trunc_format, user.id, from_time, to, trunc_format])
            rows = cursor.fetchall()

        # Process results and calculate moving averages
        results = []
        word_counts = []
        study_times = []

        for row in rows:
            period, total_words, total_time = row
            word_counts.append(total_words or 0)
            study_times.append(total_time or 0)

            # Calculate moving averages
            word_ma = calculate_moving_average(word_counts, window)
            time_ma = calculate_moving_average(study_times, window)

            results.append(
                {
                    "period": period.isoformat(),
                    "total_words": total_words or 0,
                    "total_study_time_minutes": total_time or 0,
                    "moving_average_words": word_ma,
                    "moving_average_study_time_minutes": time_ma,
                }
            )

        return Response(
            {
                "user_id": user.id,
                "from": from_time.isoformat(),
                "to": to.isoformat(),
                "granularity": granularity,
                "moving_average_window": window,
                "data": results,
            }
        )
