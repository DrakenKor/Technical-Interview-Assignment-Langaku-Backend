# Daily Aggregator - Learning Logs API

A Django REST API that aggregates learning logs and returns summaries with moving averages for different time periods and granularities.

## Features

- **Log Registration**: Store learning word count and study time with automatic timestamps
- **Idempotence**: Duplicate submissions for same user/timestamp are handled gracefully
- **Flexible Aggregation**: Support for hourly, daily, and monthly time buckets
- **Moving Averages**: Simple Moving Average (SMA) calculations with configurable window sizes
- **Performance Optimized**: PostgreSQL with proper indexing for concurrent reads/writes

## Initial Setup

### Prerequisites

- Python 3.12+
- PostgreSQL 15+
- uv package manager (recommended)

### Installation

1. **Install dependencies**:

   ```bash
   uv sync --all-groups
   ```

2. **Run migrations**:

   ```bash
   uv run manage.py migrate
   ```

### Run docker development environment
The docker environment runs two containers:
  * db: postgres 16 on port 5432
  * web: the Django API server on port 8000
```bash
docker compose up -d
```

The API will be available at `http://localhost:8000`

### Run tests

```bash
docker compose exec web uv run poe test
```

### Lint and format code

```bash
uv run poe lint
uv run poe format
```

## API Endpoints

### 1. Create Learning Record

- **POST** `/records/`
- Creates learning log with word count and study time
- Supports idempotence via user+timestamp unique constraint

### 2. Get User Summary

- **GET** `/api/v1/users/{id}/summary/`
- Returns aggregated data with moving averages
- Query parameters: `from`, `to`, `granularity`, `moving_average_window`

### 3. User Info

- **GET** `/api/v1/users/me/`
- Returns current user information

See [API_DOCUMENTATION.md](API_DOCUMENTATION.md) for detailed API documentation.

## Algorithm Explanation

### Data Aggregation Strategy

The system uses a **time-bucketing approach** with PostgreSQL's `DATE_TRUNC` function:

```sql
SELECT
    DATE_TRUNC('day', timestamp) as period,
    SUM(word_count) as total_words,
    SUM(study_time_minutes) as total_time
FROM assignment_learninglog
WHERE user_id = ? AND timestamp BETWEEN ? AND ?
GROUP BY DATE_TRUNC('day', timestamp)
ORDER BY period
```

**Why this approach?**

- **Efficiency**: Single query aggregates all data for the time range
- **Flexibility**: PostgreSQL's DATE_TRUNC supports hour/day/month granularities natively
- **Scalability**: Leverages database indexes for optimal performance

### Moving Average Calculation

**Simple Moving Average (SMA) Formula:**

```
SMA(n) = (X₁ + X₂ + ... + Xₙ) / n
```

**Implementation Logic:**

```python
def calculate_moving_average(data, window):
    if len(data) < window:
        return None  # Return null for insufficient data points
    return sum(data[-window:]) / window  # Use last 'window' values
```

**Example with window=3:**

```
Data:     [100, 200, 300, 400, 500]
Period 1: SMA = null (< 3 points)
Period 2: SMA = null (< 3 points)
Period 3: SMA = (100+200+300)/3 = 200
Period 4: SMA = (200+300+400)/3 = 300
Period 5: SMA = (300+400+500)/3 = 400
```

### Idempotence Handling

Uses Django's `get_or_create()` with unique constraint on `(user_id, timestamp)`:

```python
learning_log, created = LearningLog.objects.get_or_create(
    user=user,
    timestamp=timestamp,
    defaults={'word_count': count, 'study_time_minutes': time}
)

if not created:  # Update existing record
    learning_log.word_count = count
    learning_log.study_time_minutes = time
    learning_log.save()
```

## Performance Optimizations

### Database Indexes

```python
class Meta:
    indexes = [
        models.Index(fields=['user', 'timestamp']),  # Composite index
        models.Index(fields=['timestamp']),           # Time-range queries
    ]
```

### Concurrency Support

- **Read/Write Parallelism**: PostgreSQL ACID compliance
- **Unique Constraints**: Prevent duplicate data at database level
- **Connection Pooling**: Django's built-in database connection management

## Future Accuracy Improvements

### 1. Advanced Moving Average Algorithms

**Current**: Simple Moving Average (SMA)

```python
# Equal weight to all values in window
SMA = sum(last_n_values) / n
```

**Improvement**: Exponential Moving Average (EMA)

```python
# More weight to recent values
EMA = α * current_value + (1 - α) * previous_EMA
# where α = smoothing factor (e.g., 0.3)
```

**Benefits**:

- More responsive to recent changes
- Better trend detection
- Reduces lag in volatile data

### 2. Outlier Detection and Data Cleaning

**Problem**: Extreme values skew averages (e.g., 10,000 words in one session)

**Solution**: Statistical outlier detection

```python
def detect_outliers(data, threshold=2.0):
    mean = statistics.mean(data)
    std_dev = statistics.stdev(data)
    return [x for x in data if abs(x - mean) <= threshold * std_dev]
```

**Implementation**:

- Apply Interquartile Range (IQR) or Z-score filtering
- Flag suspicious data points for manual review
- Option to exclude/weight outliers in calculations

### 3. Adaptive Window Sizing

**Current**: Fixed window size for all users and time periods

**Improvement**: Dynamic window adjustment based on:

```python
def calculate_adaptive_window(user_data, base_window=7):
    variance = calculate_variance(user_data)
    consistency_score = calculate_consistency(user_data)

    # More consistent users = smaller window (faster response)
    # More volatile users = larger window (smoother average)

    if consistency_score > 0.8:
        return max(base_window // 2, 3)  # Minimum 3
    elif variance > threshold:
        return min(base_window * 2, 30)   # Maximum 30
    return base_window
```

**Benefits**:

- Personalized accuracy for different learning patterns
- Better trend detection for consistent learners
- Noise reduction for inconsistent learners

### Additional Improvement Ideas

- **Seasonal Adjustment**: Account for weekly/monthly learning patterns
- **Weighted Averages**: Give more importance to recent learning sessions
- **Confidence Intervals**: Provide uncertainty bounds around averages
- **Predictive Analytics**: Forecast future learning trends using historical data

## Architecture Decisions

### Why PostgreSQL over SQLite?

- **DATE_TRUNC support**: Native time bucketing functions
- **Concurrency**: Better handling of simultaneous read/write operations
- **Indexing**: Advanced index types for time-series data
- **Scalability**: Production-ready for large datasets

### Why Raw SQL for Aggregation?

- **Performance**: Single query vs multiple Python operations
- **Precision**: Database-level date/time calculations
- **Scalability**: Leverages PostgreSQL query optimization

### Why Simple Moving Average?

- **Simplicity**: Easy to understand and implement
- **Interpretability**: Clear meaning for users
- **Performance**: Efficient calculation
- **Standard**: Widely used in analytics

## Testing

The project includes comprehensive tests covering:

- **API Endpoints**: All success and error scenarios
- **Idempotence**: Duplicate submission handling
- **Moving Averages**: Mathematical accuracy
- **Edge Cases**: Invalid data, missing users, time ranges
- **Model Validation**: Database constraints and field validation

Run tests with detailed coverage:

```bash
uv run poe test --verbose --cov=assignment
```
