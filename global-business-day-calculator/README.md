# Smart Business Day Calculator v2.0 - Hybrid Library Approach

A modern web application for calculating business days across different global calendars with support for custom weekends, holidays, and makeup work days.

## 🌟 What's New in v2.0

**Major architectural redesign** replacing static JSON files with the Python `holidays` library:

- **200+ Calendars Automatically**: Access holidays for 200+ countries and subdivisions via the Python `holidays` library
- **Hybrid Approach**: Combines library data with custom overrides in a single `custom_rules.json` file
- **Dynamic Updates**: No need to manually update holiday data - the library handles it
- **Easier Maintenance**: Single override file instead of 15+ separate calendar JSON files
- **Backward Compatible API**: Frontend works seamlessly with v2.0

## 🚀 Features

### Core Capabilities
- **Calculate Business Days Between Dates**: Count business days in a date range (exclusive start, inclusive end)
- **Project Future Dates**: Find the date that is N business days from a start date
- **Custom Weekend Rules**: Define any days as weekends (e.g., Friday-Saturday for Middle East)
- **Holiday Support**: Automatic holidays from library + custom holidays
- **Makeup Days**: Weekend days that count as business days (critical for China, etc.)

### Hybrid Calendar System
1. **Base Holiday Data**: Loaded automatically from Python `holidays` library for 200+ regions
2. **Custom Overrides**: Supplement or override via `custom_rules.json`:
   - Custom weekend definitions
   - Additional holidays beyond library data
   - Makeup work days (weekends that become business days)

## 📦 Installation

### Quick Start with Docker (Recommended)

#### Prerequisites
- Docker and Docker Compose installed

#### Run with Docker Compose

```bash
# Build and start the service
docker-compose up -d

# View logs
docker-compose logs -f

# Stop the service
docker-compose down
```

The application will be available at `http://localhost:8080`

#### Run with Docker

```bash
# Build the image
docker build -t business-day-calculator .

# Run the container
docker run -p 8080:8080 -v $(pwd)/custom_rules.json:/app/custom_rules.json business-day-calculator
```

### Local Development Setup

#### Prerequisites
- Python 3.11+
- Modern web browser

#### Backend Setup

```bash
# Install dependencies
pip install -r requirements.txt

# Run the development server
python app.py
```

The API will start on `http://127.0.0.1:8080`

> **Note for macOS users**: Port 5000 may be occupied by AirPlay Receiver. This app uses port 8080 by default.

#### Frontend Setup

Simply open `index.html` in your web browser at `http://localhost:8080` (served by Flask)

## 🧪 Testing

Run the comprehensive test suite:

```bash
# Run all tests
pytest test_app.py -v

# Run specific test
pytest test_app.py::test_makeup_day_on_weekend -v
```

The test suite includes:
- Core business logic tests (7 tests)
- Hybrid rules engine tests (4 tests)
- API endpoint tests (5 tests)

## 📚 API Documentation

### Endpoints

#### GET `/api/calendars`

Returns comprehensive list of all available calendars from both the holidays library and custom rules.

**Response:**
```json
[
  {"id": "US", "name": "United States"},
  {"id": "US-NY", "name": "United States - New York"},
  {"id": "CN", "name": "China"},
  {"id": "X-CORP", "name": "INTERNAL - My Company Calendar"}
]
```

#### GET `/api/calendar/<calendar_id>`

Returns full calendar configuration for a specific calendar (holidays from library + custom overrides).

**Example:** `GET /api/calendar/US-NY`

**Response:**
```json
{
  "weekend_days": [5, 6],
  "holidays": [
    "2024-01-01",
    "2024-07-04",
    "2024-12-25"
  ],
  "makeup_days": []
}
```

#### POST `/api/calculate`

Perform business day calculation based on provided rules.

**Request Body:**
```json
{
  "operation": "days_between",
  "start_date": "2024-10-14",
  "end_date": "2024-10-18",
  "calendar_rules": {
    "weekend_days": [5, 6],
    "holidays": ["2024-10-16"],
    "makeup_days": []
  }
}
```

**Response (days_between):**
```json
{
  "business_days": 3,
  "start_date": "2024-10-14",
  "end_date": "2024-10-18"
}
```

**Response (get_future_date):**
```json
{
  "future_date": "2024-10-22",
  "start_date": "2024-10-14",
  "business_days": 5
}
```

## ⚙️ Custom Rules Configuration

The `custom_rules.json` file allows you to supplement or override the holidays library data.

### File Structure

```json
{
  "CALENDAR-ID": {
    "display_name": "Display Name",
    "weekend_days": [5, 6],
    "holidays": ["2024-12-24", "2024-12-31"],
    "makeup_days": ["2024-02-04"]
  }
}
```

### Fields

| Field | Type | Description |
|-------|------|-------------|
| `display_name` | string | Human-readable calendar name |
| `weekend_days` | array | Day numbers (0=Monday, 6=Sunday) |
| `holidays` | array | Additional holidays in YYYY-MM-DD format |
| `makeup_days` | array | Weekend days that count as work days |

### Example Use Cases

#### 1. Custom Company Calendar

Create a purely custom calendar not in the holidays library:

```json
{
  "X-CORP": {
    "display_name": "INTERNAL - My Company Calendar",
    "weekend_days": [5, 6],
    "holidays": [
      "2024-12-24",
      "2024-12-31",
      "2025-12-24",
      "2025-12-31"
    ],
    "makeup_days": []
  }
}
```

#### 2. China with Makeup Days

China has a unique policy where holidays on weekdays are "made up" by working on weekends:

```json
{
  "CN": {
    "display_name": "China (National)",
    "holidays": [],
    "makeup_days": [
      "2024-02-04",
      "2024-02-18",
      "2024-04-28",
      "2024-05-11",
      "2024-09-29",
      "2024-10-12",
      "2025-01-26",
      "2025-02-08"
    ]
  }
}
```

#### 3. Override Weekend for India Subdivisions

Override the default weekend for Indian states:

```json
{
  "IN-KA": {
    "display_name": "India - Karnataka (Custom Week)",
    "weekend_days": [5, 6]
  }
}
```

### How the Hybrid System Works

The `get_calendar_rules()` function is the "brain" of the hybrid approach:

1. **Initialize Defaults**: Start with weekend [5, 6] (Saturday, Sunday)
2. **Load Library Data**: Fetch holidays from Python `holidays` library for the calendar
3. **Merge Custom Rules**: Apply overrides from `custom_rules.json`:
   - Replace weekend if specified
   - Add custom holidays (only if non-empty list)
   - Add makeup days
4. **Return Merged Result**: Combined rules ready for calculations

**Important**: An empty `holidays` array in custom_rules.json does NOT clear library holidays - it's ignored. Only non-empty arrays add holidays.

## 🧮 Business Day Logic

### Calculation Convention

- **Days Between**: Exclusive start, inclusive end `(start, end]`
  - Example: Monday to Wednesday = 2 business days (Tuesday, Wednesday)

- **Future Date**: N business days AFTER start date
  - Example: Start Monday + 3 days = Thursday

### Is Business Day?

A day is a business day if:
1. It's in `makeup_days` (HIGHEST PRIORITY), OR
2. It's NOT a weekend AND NOT a holiday

**Critical Rule**: Makeup days override all other rules. If a Saturday is in `makeup_days`, it counts as a business day even though it's a weekend.

## 🏗️ Project Structure

```
global-business-day-calculator/
├── app.py                 # Flask backend with hybrid library logic
├── test_app.py            # Comprehensive test suite (16 tests)
├── custom_rules.json      # Single file for all custom overrides
├── index.html             # Modern Tailwind CSS frontend
├── requirements.txt       # Python dependencies
├── Dockerfile             # Docker image definition
├── docker-compose.yml     # Docker Compose configuration
├── .dockerignore          # Docker build exclusions
├── README.md              # This file
└── calendars/             # (v1.0 legacy - deprecated in v2.0)
```

## 🚀 Deployment

### Production Deployment with Docker

The application is production-ready with:
- ✅ Gunicorn WSGI server (2 workers, 120s timeout)
- ✅ Health checks for container orchestration
- ✅ Volume mounting for `custom_rules.json` persistence
- ✅ Auto-restart on failure
- ✅ Optimized Docker image with layer caching

### Deploy to Cloud Platforms

#### AWS ECS / Fargate
```bash
# Build and tag
docker build -t business-day-calculator:latest .

# Tag for ECR
docker tag business-day-calculator:latest your-account.dkr.ecr.region.amazonaws.com/business-day-calculator:latest

# Push to ECR
docker push your-account.dkr.ecr.region.amazonaws.com/business-day-calculator:latest
```

#### Google Cloud Run
```bash
# Build and push to GCR
gcloud builds submit --tag gcr.io/your-project/business-day-calculator

# Deploy
gcloud run deploy business-day-calculator \
  --image gcr.io/your-project/business-day-calculator \
  --platform managed \
  --port 8080
```

#### Azure Container Instances
```bash
# Build and push to ACR
az acr build --registry your-registry --image business-day-calculator:latest .

# Deploy
az container create \
  --resource-group your-rg \
  --name business-day-calculator \
  --image your-registry.azurecr.io/business-day-calculator:latest \
  --ports 8080
```

#### DigitalOcean App Platform / Heroku
Both platforms support Docker deployment via Dockerfile.

## 🔧 Development

### Running Tests

```bash
# Run all tests with verbose output
pytest test_app.py -v

# Run specific test category
pytest test_app.py -k "calendar_rules" -v

# Run with coverage
pytest test_app.py --cov=app --cov-report=html
```

### Adding New Custom Calendar

1. Open `custom_rules.json`
2. Add new calendar entry with unique ID
3. Restart the Flask server
4. Calendar will appear in the dropdown

Example:

```json
{
  "X-MY-CAL": {
    "display_name": "My Custom Calendar",
    "weekend_days": [4, 5],
    "holidays": ["2024-01-15", "2024-06-20"],
    "makeup_days": []
  }
}
```

### Debugging

Enable Flask debug mode (already enabled in development):

```python
app.run(debug=True, host='0.0.0.0', port=8080)
```

Check logs:
- Backend: Terminal output from `python app.py`
- Frontend: Browser console (F12)

## 📖 Migration from v1.0

If you have a v1.0 installation:

1. **Backup**: Save your `calendars/*.json` files
2. **Consolidate**: Merge any custom calendars into new `custom_rules.json`
3. **Install**: Run `pip install holidays` to add new dependency
4. **Test**: Run `pytest test_app.py -v` to verify everything works
5. **Cleanup**: Old `calendars/*.json` files are no longer needed

Key changes:
- 15 static JSON files → Python `holidays` library + 1 `custom_rules.json`
- Manual holiday updates → Automatic updates via library
- API endpoints remain the same (backward compatible)

## 🤝 Contributing

This is a personal project, but suggestions are welcome! Areas for contribution:

- Additional test cases for edge cases
- Performance optimizations
- Additional calendar examples in documentation
- UI/UX improvements

## 📄 License

This project is open source and available for educational and commercial use.

## 🙏 Acknowledgments

- Python `holidays` library for providing comprehensive holiday data
- Flask for the web framework
- Tailwind CSS for the modern UI

## 📞 Support

For issues or questions:
1. Check the test suite in `test_app.py` for examples
2. Review the API documentation above
3. Inspect browser console for frontend errors
4. Check Flask logs for backend errors

---

Built with ❤️ following The Zen of Python principles:
- Explicit is better than implicit
- Flat is better than nested
- Readability counts
