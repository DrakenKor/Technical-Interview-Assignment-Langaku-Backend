# Daily Aggregator API Documentation

## Overview

The Daily Aggregator API provides endpoints for storing learning logs and retrieving aggregated summaries with moving averages. The API supports different time granularities (hourly, daily, monthly) and provides Simple Moving Average (SMA) calculations.

## Base URL

```
http://localhost:8000
```

## Authentication

All endpoints require user authentication. The system uses Django's built-in authentication with a mock login middleware for testing.

## Endpoints

### 1. Create Learning Record

**POST** `/records/`

Creates a new learning log record with idempotence support.

#### Request Body

```json
{
  "word_count": 100,
  "study_time_minutes": 30,
  "timestamp": "2024-01-15T10:00:00Z"  // Optional - server timestamp if omitted
}
```

#### Parameters

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `word_count` | integer | Yes | Number of words learned (must be positive) |
| `study_time_minutes` | integer | Yes | Study time in minutes (must be positive) |
| `timestamp` | string (ISO-8601) | No | Learning timestamp (UTC). Server time used if omitted |

#### Response

**Success (201 Created)**
```json
{
  "id": 1,
  "word_count": 100,
  "study_time_minutes": 30,
  "timestamp": "2024-01-15T10:00:00Z",
  "created_at": "2024-01-15T10:05:00Z"
}
```

**Error (400 Bad Request)**
```json
{
  "word_count": ["Word count must be positive"],
  "study_time_minutes": ["This field is required"]
}
```

#### Idempotence

Records with the same `user` and `timestamp` will be updated rather than creating duplicates, ensuring idempotence for duplicate submissions.

---

### 2. Get User Summary

**GET** `/api/v1/users/{user_id}/summary/`

Retrieves aggregated learning data with moving averages for a specific time period and granularity.

#### Path Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `user_id` | integer | ID of the user |

#### Query Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `from` | string (ISO-8601) | Yes | - | Start time (UTC) |
| `to` | string (ISO-8601) | Yes | - | End time (UTC) |
| `granularity` | string | No | `day` | Time bucket granularity: `hour`, `day`, or `month` |
| `moving_average_window` | integer | No | 3 | Window size for moving average calculation (min: 1) |

#### Example Request

```
GET /api/v1/users/1/summary/?from=2024-01-01T00:00:00Z&to=2024-01-31T23:59:59Z&granularity=day&moving_average_window=7
```

#### Response

**Success (200 OK)**
```json
{
  "user_id": 1,
  "from_time": "2024-01-01T00:00:00Z",
  "to": "2024-01-31T23:59:59Z",
  "granularity": "day",
  "moving_average_window": 7,
  "data": [
    {
      "period": "2024-01-01T00:00:00Z",
      "total_words": 150,
      "total_study_time_minutes": 45,
      "moving_average_words": null,  // null for first n periods where n < window
      "moving_average_study_time_minutes": null
    },
    {
      "period": "2024-01-02T00:00:00Z",
      "total_words": 200,
      "total_study_time_minutes": 60,
      "moving_average_words": null,
      "moving_average_study_time_minutes": null
    },
    {
      "period": "2024-01-07T00:00:00Z",
      "total_words": 180,
      "total_study_time_minutes": 50,
      "moving_average_words": 175.7,  // 7-day moving average
      "moving_average_study_time_minutes": 52.1
    }
  ]
}
```

**Error Responses**

*User Not Found (404)*
```json
{
  "error": "User not found"
}
```

*Invalid Parameters (400)*
```json
{
  "from_time": ["This field is required"],
  "granularity": ["\"invalid\" is not a valid choice."]
}
```

*Invalid Time Range (400)*
```json
{
  "error": "from_time timestamp must be before to timestamp"
}
```

---

### 3. Get Current User Info

**GET** `/api/v1/users/me/`

Returns information about the currently authenticated user.

#### Response

**Success (200 OK)**
```json
{
  "username": "john_doe"
}
```

**Error (401 Unauthorized)**
```json
{
  "error": "User not authenticated"
}
```

---

## Data Aggregation Algorithm

### Time Bucketing

Data is aggregated using PostgreSQL's `DATE_TRUNC` function to group records into time buckets:

- **Hour**: Groups by hour (e.g., 2024-01-15 10:00:00)
- **Day**: Groups by day (e.g., 2024-01-15 00:00:00)
- **Month**: Groups by month (e.g., 2024-01-01 00:00:00)

### Aggregation Formula

For each time bucket:
```
total_words = SUM(word_count) for all records in bucket
total_study_time = SUM(study_time_minutes) for all records in bucket
```

### Simple Moving Average (SMA)

Moving averages are calculated using a sliding window approach:

```
SMA(n) = (value[i] + value[i-1] + ... + value[i-n+1]) / n
```

Where:
- `n` = moving_average_window size
- Returns `null` for the first `n-1` data points
- Uses only the most recent `n` values in the time series

**Example**: For window size 3 and values [100, 200, 300, 400]:
- Period 1: SMA = null (< 3 values)
- Period 2: SMA = null (< 3 values)
- Period 3: SMA = (100 + 200 + 300) / 3 = 200
- Period 4: SMA = (200 + 300 + 400) / 3 = 300

---

## Performance Considerations

### Database Indexes

The system includes optimized database indexes for performance:

```sql
-- Composite index for user + timestamp queries
CREATE INDEX assignment_learninglog_user_timestamp_idx ON assignment_learninglog (user_id, timestamp);

-- Single timestamp index for time-range queries
CREATE INDEX assignment_learninglog_timestamp_idx ON assignment_learninglog (timestamp);
```

### Concurrency

- **Read/Write Parallel Support**: The API supports concurrent reads and writes
- **Idempotence**: Duplicate submissions are handled via `get_or_create` with unique constraints
- **PostgreSQL**: Uses PostgreSQL for ACID compliance and efficient date/time operations

---

## Error Handling

### HTTP Status Codes

| Code | Description |
|------|-------------|
| 200 | OK - Request successful |
| 201 | Created - Resource created successfully |
| 400 | Bad Request - Invalid parameters or validation errors |
| 401 | Unauthorized - Authentication required |
| 404 | Not Found - Resource not found |
| 500 | Internal Server Error - Server error |

### Error Response Format

All error responses follow a consistent format:

```json
{
  "error": "Error description"
}
```

Or for validation errors:

```json
{
  "field_name": ["Error message for this field"],
  "another_field": ["Another error message"]
}
```

---

## Example Usage

### Creating Learning Records

```bash
# Create a record with current timestamp
curl -X POST http://localhost:8000/records/ \
  -H "Content-Type: application/json" \
  -d '{
    "word_count": 150,
    "study_time_minutes": 45
  }'

# Create a record with specific timestamp
curl -X POST http://localhost:8000/records/ \
  -H "Content-Type: application/json" \
  -d '{
    "word_count": 200,
    "study_time_minutes": 60,
    "timestamp": "2024-01-15T14:30:00Z"
  }'
```

### Retrieving Summaries

```bash
# Daily summary for January 2024 with 7-day moving average
curl "http://localhost:8000/api/v1/users/1/summary/?from=2024-01-01T00:00:00Z&to=2024-01-31T23:59:59Z&granularity=day&moving_average_window=7"

# Hourly summary for a single day
curl "http://localhost:8000/api/v1/users/1/summary/?from=2024-01-15T00:00:00Z&to=2024-01-15T23:59:59Z&granularity=hour"

# Monthly summary for a year with 3-month moving average
curl "http://localhost:8000/api/v1/users/1/summary/?from=2024-01-01T00:00:00Z&to=2024-12-31T23:59:59Z&granularity=month&moving_average_window=3"
```