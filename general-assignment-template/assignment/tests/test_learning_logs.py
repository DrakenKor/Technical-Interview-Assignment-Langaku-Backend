import pytest
from django.test import TestCase
from django.utils import timezone
from datetime import timedelta
from rest_framework import status
from rest_framework.test import APITestCase, APIClient
from assignment.models import User, LearningLog


@pytest.mark.django_db
class TestLearningLogAPI(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="testuser", password="testpass")
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def test_create_learning_record_success(self):
        """Test successful creation of learning record"""
        data = {"word_count": 100, "study_time_minutes": 30}
        response = self.client.post("/records/", data, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["word_count"], 100)
        self.assertEqual(response.data["study_time_minutes"], 30)

        # Check record was created in database
        log = LearningLog.objects.get(user=self.user)
        self.assertEqual(log.word_count, 100)
        self.assertEqual(log.study_time_minutes, 30)

    def test_create_learning_record_with_timestamp(self):
        """Test creation with explicit timestamp"""
        timestamp = timezone.now() - timedelta(hours=1)
        data = {
            "word_count": 50,
            "study_time_minutes": 20,
            "timestamp": timestamp.isoformat(),
        }
        response = self.client.post("/records/", data, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        log = LearningLog.objects.get(user=self.user)
        self.assertEqual(
            log.timestamp.replace(microsecond=0), timestamp.replace(microsecond=0)
        )

    def test_create_learning_record_idempotence(self):
        """Test idempotence - duplicate timestamp should update existing record"""
        timestamp = timezone.now()

        # First request
        data = {
            "word_count": 100,
            "study_time_minutes": 30,
            "timestamp": timestamp.isoformat(),
        }
        response1 = self.client.post("/records/", data, format="json")
        self.assertEqual(response1.status_code, status.HTTP_201_CREATED)

        # Second request with same timestamp but different values
        data["word_count"] = 200
        data["study_time_minutes"] = 60
        response2 = self.client.post("/records/", data, format="json")
        self.assertEqual(response2.status_code, status.HTTP_201_CREATED)

        # Should have only one record with updated values
        self.assertEqual(LearningLog.objects.filter(user=self.user).count(), 1)
        log = LearningLog.objects.get(user=self.user)
        self.assertEqual(log.word_count, 200)
        self.assertEqual(log.study_time_minutes, 60)

    def test_create_learning_record_validation_errors(self):
        """Test validation errors for invalid data"""
        # Test negative word count
        data = {"word_count": -10, "study_time_minutes": 30}
        response = self.client.post("/records/", data, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        # Test negative study time
        data = {"word_count": 100, "study_time_minutes": -5}
        response = self.client.post("/records/", data, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        # Test missing required fields
        data = {"word_count": 100}
        response = self.client.post("/records/", data, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_get_user_summary_basic(self):
        """Test basic user summary functionality"""
        # Create test data
        base_time = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)

        LearningLog.objects.create(
            user=self.user, word_count=100, study_time_minutes=30, timestamp=base_time
        )
        LearningLog.objects.create(
            user=self.user,
            word_count=150,
            study_time_minutes=45,
            timestamp=base_time + timedelta(days=1),
        )

        # Test daily summary
        response = self.client.get(
            f"/api/v1/users/{self.user.id}/summary/",
            {
                "from_time": (base_time - timedelta(days=1)).isoformat(),
                "to": (base_time + timedelta(days=2)).isoformat(),
                "granularity": "day",
            },
        )

        # Debug output
        if response.status_code != status.HTTP_200_OK:
            print(f"Response status: {response.status_code}")
            print(f"Response data: {response.data}")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["data"]), 2)
        self.assertEqual(response.data["data"][0]["total_words"], 100)
        self.assertEqual(response.data["data"][1]["total_words"], 150)

    def test_get_user_summary_moving_averages(self):
        """Test moving average calculations"""
        base_time = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)

        # Create 5 days of data
        for i in range(5):
            LearningLog.objects.create(
                user=self.user,
                word_count=(i + 1) * 100,  # 100, 200, 300, 400, 500
                study_time_minutes=(i + 1) * 10,  # 10, 20, 30, 40, 50
                timestamp=base_time + timedelta(days=i),
            )

        response = self.client.get(
            f"/api/v1/users/{self.user.id}/summary/",
            {
                "from_time": (base_time - timedelta(days=1)).isoformat(),
                "to": (base_time + timedelta(days=6)).isoformat(),
                "granularity": "day",
                "moving_average_window": 3,
            },
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.data["data"]

        # First two entries should have null moving averages (< window size)
        self.assertIsNone(data[0]["moving_average_words"])
        self.assertIsNone(data[1]["moving_average_words"])

        # Third entry should have moving average of first 3 values: (100+200+300)/3 = 200
        self.assertEqual(data[2]["moving_average_words"], 200)

        # Fourth entry: (200+300+400)/3 = 300
        self.assertEqual(data[3]["moving_average_words"], 300)

    def test_get_user_summary_different_granularities(self):
        """Test different time granularities"""
        base_time = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)

        # Create hourly data
        for i in range(24):
            LearningLog.objects.create(
                user=self.user,
                word_count=10,
                study_time_minutes=5,
                timestamp=base_time + timedelta(hours=i),
            )

        # Test hourly granularity
        response = self.client.get(
            f"/api/v1/users/{self.user.id}/summary/",
            {
                "from_time": base_time.isoformat(),
                "to": (base_time + timedelta(days=1)).isoformat(),
                "granularity": "hour",
            },
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["data"]), 24)

    def test_get_user_summary_validation_errors(self):
        """Test validation errors for summary endpoint"""
        # Test missing parameters
        response = self.client.get(f"/api/v1/users/{self.user.id}/summary/")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        # Test from > to
        base_time = timezone.now()
        response = self.client.get(
            f"/api/v1/users/{self.user.id}/summary/",
            {
                "from_time": base_time.isoformat(),
                "to": (base_time - timedelta(days=1)).isoformat(),
                "granularity": "day",
            },
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        # Test invalid granularity
        response = self.client.get(
            f"/api/v1/users/{self.user.id}/summary/",
            {
                "from_time": (base_time - timedelta(days=1)).isoformat(),
                "to": base_time.isoformat(),
                "granularity": "invalid",
            },
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_get_user_summary_nonexistent_user(self):
        """Test summary for non-existent user"""
        response = self.client.get(
            "/api/v1/users/99999/summary/",
            {
                "from_time": timezone.now().isoformat(),
                "to": (timezone.now() + timedelta(days=1)).isoformat(),
                "granularity": "day",
            },
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_create_learning_record_idempotence_without_timestamp(self):
        """Test idempotence for duplicate requests WITHOUT timestamps - THIS SHOULD FAIL"""
        data = {"word_count": 100, "study_time_minutes": 30}

        # First request without timestamp
        response1 = self.client.post("/records/", data, format="json")
        self.assertEqual(response1.status_code, status.HTTP_201_CREATED)

        # Second identical request without timestamp
        response2 = self.client.post("/records/", data, format="json")
        self.assertEqual(response2.status_code, status.HTTP_201_CREATED)


        record_count = LearningLog.objects.filter(user=self.user).count()
        print(f"Record count after duplicate submission: {record_count}")


        try:
            self.assertEqual(record_count, 1, "Idempotence violated: should have only 1 record")
            print("Idempotence working correctly")
        except AssertionError as e:
            print(f"Idempotence BROKEN: {e}")

            logs = LearningLog.objects.filter(user=self.user).order_by('timestamp')
            for i, log in enumerate(logs):
                print(f"Record {i+1}: timestamp = {log.timestamp}")

    def test_unauthenticated_access(self):
        """Test that unauthenticated users cannot access endpoints"""
        self.client.force_authenticate(user=None)

        response = self.client.post(
            "/records/", {"word_count": 100, "study_time_minutes": 30}
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


@pytest.mark.django_db
class TestLearningLogModel(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="testuser")

    def test_learning_log_creation(self):
        """Test basic model creation"""
        log = LearningLog.objects.create(
            user=self.user, word_count=100, study_time_minutes=30
        )

        self.assertEqual(log.user, self.user)
        self.assertEqual(log.word_count, 100)
        self.assertEqual(log.study_time_minutes, 30)
        self.assertIsNotNone(log.timestamp)

    def test_unique_constraint(self):
        """Test unique constraint on user+timestamp"""
        timestamp = timezone.now()

        LearningLog.objects.create(
            user=self.user, word_count=100, study_time_minutes=30, timestamp=timestamp
        )

        # Creating another log with same user+timestamp should raise error
        with self.assertRaises(Exception):  # IntegrityError
            LearningLog.objects.create(
                user=self.user,
                word_count=200,
                study_time_minutes=60,
                timestamp=timestamp,
            )

    def test_string_representation(self):
        """Test model string representation"""
        log = LearningLog.objects.create(
            user=self.user, word_count=100, study_time_minutes=30
        )

        expected = f"User {self.user.id} - 100 words, 30min at {log.timestamp}"
        self.assertEqual(str(log), expected)
