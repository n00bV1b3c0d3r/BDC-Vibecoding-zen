"""
Smart Business Day Calculator API v2.0 - Hybrid Library Approach

This application combines the power of the `holidays` library with custom override
capabilities through custom_rules.json. It follows The Zen of Python principles:
- Explicit is better than implicit
- Flat is better than nested
- Readability counts

Core features:
- Auto-loads holiday data from the `holidays` library for 200+ countries/regions
- Allows custom weekend definitions, additional holidays, and makeup days
- Calculate business days between two dates
- Project future dates based on business days
- Support custom weekend rules and holidays
- Handle makeup days (critical for regions like China)
"""

import os
import json
import holidays
import pycountry
from datetime import datetime, timedelta
from flask import Flask, request, jsonify
from flask_cors import CORS


# ============================================================================
# Flask Application Setup
# ============================================================================

app = Flask(__name__, static_folder='.')
CORS(app)  # Allow all cross-origin requests

CUSTOM_RULES_FILE = os.path.join(os.path.dirname(__file__), 'custom_rules.json')

# Global cache for custom rules
custom_rules = {}


# ============================================================================
# Helper Functions - Data Loading
# ============================================================================

def load_custom_rules():
    """
    Load custom calendar rules from custom_rules.json.

    Returns:
        dict: Custom rules configuration
    """
    global custom_rules

    if not os.path.exists(CUSTOM_RULES_FILE):
        # Create default file if it doesn't exist
        initialize_custom_rules_file()

    try:
        with open(CUSTOM_RULES_FILE, 'r') as f:
            custom_rules = json.load(f)
        app.logger.info(f"Loaded {len(custom_rules)} custom calendar configurations")
    except (json.JSONDecodeError, IOError) as e:
        app.logger.error(f"Error loading custom_rules.json: {e}")
        custom_rules = {}

    return custom_rules


def initialize_custom_rules_file():
    """
    Create a sample custom_rules.json file if it doesn't exist.
    """
    sample_rules = {
        "IN-KA": {
            "display_name": "India - Karnataka (Custom Week)",
            "weekend_days": [5, 6]
        },
        "IN-AP": {
            "display_name": "India - Andhra Pradesh (Custom Week)",
            "weekend_days": [5, 6]
        },
        "CN": {
            "display_name": "China (National)",
            "holidays": [],
            "makeup_days": [
                "2024-02-04", "2024-02-18", "2024-04-28",
                "2024-05-11", "2024-09-29", "2024-10-12",
                "2025-01-26", "2025-02-08"
            ]
        },
        "X-CORP": {
            "display_name": "INTERNAL - My Company Calendar",
            "weekend_days": [5, 6],
            "holidays": ["2024-12-24", "2024-12-31", "2025-12-24", "2025-12-31"],
            "makeup_days": []
        }
    }

    with open(CUSTOM_RULES_FILE, 'w') as f:
        json.dump(sample_rules, f, indent=2)

    app.logger.info(f"Created sample custom_rules.json at {CUSTOM_RULES_FILE}")


def get_available_calendars_from_library():
    """
    Get all available calendars from the holidays library.

    Returns:
        list: List of {"id": "...", "name": "..."} objects
    """
    calendars = []
    seen_countries = {}  # Track country names to avoid duplicates

    # Get all supported countries from holidays library
    supported_countries = holidays.list_supported_countries()

    for country_code in supported_countries:
        try:
            # Get country name from pycountry for proper names
            country_name = None

            # Try to get proper country name from pycountry
            if len(country_code) == 2:
                country_obj = pycountry.countries.get(alpha_2=country_code)
                if country_obj:
                    country_name = country_obj.name
            elif len(country_code) == 3:
                country_obj = pycountry.countries.get(alpha_3=country_code)
                if country_obj:
                    country_name = country_obj.name

            # Fallback to holidays library country code
            if not country_name:
                holiday_obj = holidays.country_holidays(country_code)
                country_name = holiday_obj.country

            # Skip if we've already added this country (prefer 2-letter codes)
            if country_name in seen_countries:
                continue

            # Add main country
            calendars.append({
                "id": country_code,
                "name": country_name
            })
            seen_countries[country_name] = country_code

            # Check for geographical subdivisions (states, provinces, etc.)
            holiday_class = holidays.country_holidays(country_code).__class__
            if hasattr(holiday_class, 'subdivisions') and holiday_class.subdivisions:
                # Get national holidays for comparison
                try:
                    national_holidays = holidays.country_holidays(country_code, years=[2024, 2025])
                    national_holiday_set = set(national_holidays.keys())
                except Exception:
                    national_holiday_set = set()

                for subdiv in holiday_class.subdivisions:
                    try:
                        # Skip if subdiv is empty or too long (likely not a state code)
                        if not subdiv or len(subdiv) > 20:
                            continue

                        # Check if subdivision holidays differ from national
                        subdiv_holidays = holidays.country_holidays(country_code, subdiv=subdiv, years=[2024, 2025])
                        subdiv_holiday_set = set(subdiv_holidays.keys())

                        # Only include if different from national calendar
                        if subdiv_holiday_set == national_holiday_set:
                            continue

                        # Try to get proper subdivision name from pycountry
                        subdiv_display = subdiv
                        try:
                            subdiv_obj = pycountry.subdivisions.get(code=f"{country_code}-{subdiv}")
                            if subdiv_obj:
                                subdiv_display = subdiv_obj.name
                        except (KeyError, AttributeError):
                            pass

                        subdiv_name = f"{country_name} ({subdiv_display})"
                        calendars.append({
                            "id": f"{country_code}-{subdiv}",
                            "name": subdiv_name
                        })
                    except Exception:
                        pass
        except Exception as e:
            app.logger.debug(f"Could not load calendar for {country_code}: {e}")
            continue

    return calendars


def merge_calendar_rules(calendar_rules_list):
    """
    Merge multiple calendar rules into one (for international teams).

    Uses UNION approach: A day is a non-business day if it's a holiday or weekend
    in ANY of the calendars. This is the most restrictive approach, respecting
    all team members' holidays.

    Args:
        calendar_rules_list: List of calendar rule dicts

    Returns:
        dict: Merged rules with union of holidays, weekends, and makeup days
    """
    if not calendar_rules_list:
        return {"weekend_days": [], "holidays": [], "makeup_days": []}

    if len(calendar_rules_list) == 1:
        return calendar_rules_list[0]

    # Merge using sets for efficient union
    all_weekend_days = set()
    all_holidays = set()
    all_makeup_days = set()

    for rules in calendar_rules_list:
        all_weekend_days.update(rules.get("weekend_days", []))
        all_holidays.update(rules.get("holidays", []))
        all_makeup_days.update(rules.get("makeup_days", []))

    return {
        "weekend_days": sorted(list(all_weekend_days)),
        "holidays": sorted(list(all_holidays)),
        "makeup_days": sorted(list(all_makeup_days))
    }


def get_calendar_rules(calendar_id, years=[2024, 2025]):
    """
    Get calendar rules by merging holidays library data with custom overrides.

    This is the "brain" of the hybrid approach:
    1. Start with defaults (weekend: Sat/Sun, no holidays, no makeup days)
    2. Load base holidays from holidays library (if available)
    3. Merge with custom_rules.json overrides

    Args:
        calendar_id: Calendar identifier (e.g., "US", "US-NY", "CN", "X-CORP")
        years: List of years to fetch holidays for

    Returns:
        dict: Merged calendar rules with weekend_days, holidays, makeup_days

    Raises:
        ValueError: If calendar_id is invalid and not in custom rules
    """
    # Step 1: Initialize defaults
    rules = {
        "weekend_days": [5, 6],  # Saturday, Sunday
        "holidays": set(),
        "makeup_days": set()
    }

    # Step 2: Try to load from holidays library
    try:
        # Parse calendar_id to extract country and subdivision
        if '-' in calendar_id:
            # This is a subdivision (e.g., "US-NY", "IN-KA")
            parts = calendar_id.split('-', 1)
            country_code = parts[0]
            subdiv = parts[1]

            # Get holidays from library
            for year in years:
                holiday_obj = holidays.country_holidays(country_code, subdiv=subdiv, years=year)
                for date_obj, name in holiday_obj.items():
                    rules["holidays"].add(date_obj.strftime("%Y-%m-%d"))
        else:
            # This is a country-level calendar (e.g., "US", "CN")
            for year in years:
                holiday_obj = holidays.country_holidays(calendar_id, years=year)
                for date_obj, name in holiday_obj.items():
                    rules["holidays"].add(date_obj.strftime("%Y-%m-%d"))
    except Exception as e:
        # Calendar might not exist in holidays library, check custom rules
        if calendar_id not in custom_rules:
            raise ValueError(f"Calendar '{calendar_id}' not found in holidays library or custom rules")
        app.logger.debug(f"Calendar '{calendar_id}' not in holidays library: {e}")

    # Step 3: Merge with custom rules (if they exist)
    if calendar_id in custom_rules:
        custom = custom_rules[calendar_id]

        # Override weekend if specified
        if "weekend_days" in custom:
            rules["weekend_days"] = custom["weekend_days"]

        # Add custom holidays (only if the list is non-empty)
        if "holidays" in custom and len(custom["holidays"]) > 0:
            for holiday_str in custom["holidays"]:
                rules["holidays"].add(holiday_str)

        # Add makeup days
        if "makeup_days" in custom:
            for makeup_str in custom["makeup_days"]:
                rules["makeup_days"].add(makeup_str)

    # Step 4: Convert sets to sorted lists for JSON serialization
    rules["holidays"] = sorted(list(rules["holidays"]))
    rules["makeup_days"] = sorted(list(rules["makeup_days"]))

    return rules


# ============================================================================
# Helper Functions - Business Day Logic
# ============================================================================

def is_business_day(date, weekend_days_set, holidays_set, makeup_days_set):
    """
    Determine if a given date is a business day.

    CRITICAL RULE: Makeup days take precedence over all other rules.
    A day is a business day if:
    1. It's in makeup_days_set (CHECKED FIRST)
    2. OR (it's not a weekend AND not a holiday)

    Args:
        date: datetime object
        weekend_days_set: Set of weekend day numbers (0=Monday, 6=Sunday)
        holidays_set: Set of holiday dates
        makeup_days_set: Set of makeup work days

    Returns:
        bool: True if business day, False otherwise
    """
    # Rule 1: Makeup days are ALWAYS business days
    if date in makeup_days_set:
        return True

    # Rule 2: Not a weekend AND not a holiday
    is_weekend = date.weekday() in weekend_days_set
    is_holiday = date in holidays_set

    return not is_weekend and not is_holiday


def calculate_days_between(start_date, end_date, weekend_days_set,
                          holidays_set, makeup_days_set):
    """
    Calculate the number of business days between two dates.

    Convention: Exclusive start, inclusive end (start, end].
    This means we count business days AFTER start_date up to and including end_date.

    Args:
        start_date: datetime object (exclusive - not counted)
        end_date: datetime object (inclusive - counted)
        weekend_days_set: Set of weekend day numbers
        holidays_set: Set of holiday dates
        makeup_days_set: Set of makeup work days

    Returns:
        int: Number of business days
    """
    business_days = 0
    current_date = start_date + timedelta(days=1)

    while current_date <= end_date:
        if is_business_day(current_date, weekend_days_set,
                          holidays_set, makeup_days_set):
            business_days += 1
        current_date += timedelta(days=1)

    return business_days


def get_future_business_date(start_date, business_days, weekend_days_set,
                             holidays_set, makeup_days_set):
    """
    Calculate the future date that is N business days from start date.

    Args:
        start_date: datetime object
        business_days: Number of business days to add
        weekend_days_set: Set of weekend day numbers
        holidays_set: Set of holiday dates
        makeup_days_set: Set of makeup work days

    Returns:
        datetime: The future date
    """
    current_date = start_date
    days_counted = 0

    while days_counted < business_days:
        current_date += timedelta(days=1)

        if is_business_day(current_date, weekend_days_set,
                          holidays_set, makeup_days_set):
            days_counted += 1

    return current_date


def perform_calculation(operation, start_date, calendar_rules,
                       end_date=None, business_days=None):
    """
    Pure business logic function for calculations (testable without Flask).

    Args:
        operation: 'days_between' or 'get_future_date'
        start_date: Date string in YYYY-MM-DD format
        calendar_rules: Dict with weekend_days, holidays, makeup_days
        end_date: Date string (for days_between operation)
        business_days: Integer (for get_future_date operation)

    Returns:
        dict: Result with business_days or future_date key

    Raises:
        ValueError: For invalid inputs
    """
    # Parse start date
    try:
        start_dt = datetime.strptime(start_date, "%Y-%m-%d")
    except ValueError:
        raise ValueError(f"Invalid start_date format: {start_date}")

    # Extract rules and convert to sets for O(1) lookup
    weekend_days_set = set(calendar_rules.get('weekend_days', []))
    holidays_set = set()
    makeup_days_set = set()

    # Parse holiday dates
    for holiday_str in calendar_rules.get('holidays', []):
        try:
            holiday_dt = datetime.strptime(holiday_str, "%Y-%m-%d")
            holidays_set.add(holiday_dt)
        except ValueError:
            # Skip invalid holiday dates
            continue

    # Parse makeup day dates
    for makeup_str in calendar_rules.get('makeup_days', []):
        try:
            makeup_dt = datetime.strptime(makeup_str, "%Y-%m-%d")
            makeup_days_set.add(makeup_dt)
        except ValueError:
            # Skip invalid makeup dates
            continue

    # Perform operation
    if operation == 'days_between':
        if not end_date:
            raise ValueError("end_date is required for days_between operation")

        try:
            end_dt = datetime.strptime(end_date, "%Y-%m-%d")
        except ValueError:
            raise ValueError(f"Invalid end_date format: {end_date}")

        if end_dt <= start_dt:
            raise ValueError("end_date must be after start_date")

        result_count = calculate_days_between(
            start_dt, end_dt, weekend_days_set, holidays_set, makeup_days_set
        )

        return {
            'business_days': result_count,
            'start_date': start_date,
            'end_date': end_date
        }

    elif operation == 'get_future_date':
        if business_days is None:
            raise ValueError("business_days is required for get_future_date operation")

        if not isinstance(business_days, int) or business_days < 0:
            raise ValueError("business_days must be a non-negative integer")

        future_dt = get_future_business_date(
            start_dt, business_days, weekend_days_set, holidays_set, makeup_days_set
        )

        return {
            'future_date': future_dt.strftime("%Y-%m-%d"),
            'start_date': start_date,
            'business_days': business_days
        }

    else:
        raise ValueError(f"Invalid operation: {operation}")


# ============================================================================
# API Endpoints
# ============================================================================

@app.route('/')
def index():
    """
    Serve the main index.html page
    """
    return app.send_static_file('index.html')


@app.route('/api/calendars', methods=['GET'])
def list_calendars():
    """
    GET /api/calendars

    Returns comprehensive list of all available calendars from both
    the holidays library and custom_rules.json.

    Response:
        200: [{"id": "US", "name": "United States"}, ...]
    """
    calendars = []

    # Add calendars from holidays library
    library_calendars = get_available_calendars_from_library()
    calendars.extend(library_calendars)

    # Add purely custom calendars from custom_rules.json
    for calendar_id, config in custom_rules.items():
        # Check if this calendar is NOT already in the library list
        existing_ids = [cal["id"] for cal in calendars]
        if calendar_id not in existing_ids:
            display_name = config.get("display_name", calendar_id)
            calendars.append({
                "id": calendar_id,
                "name": display_name
            })

    # Sort by name
    calendars.sort(key=lambda x: x["name"])

    return jsonify(calendars), 200


@app.route('/api/calendar/<string:calendar_id>', methods=['GET'])
def get_calendar(calendar_id):
    """
    GET /api/calendar/<calendar_id>

    Returns full calendar configuration (holidays from library + custom overrides).

    Response:
        200: {"weekend_days": [...], "holidays": [...], "makeup_days": [...]}
        404: {"error": "Calendar not found"}
    """
    try:
        # Get years from query params or default to current year + next year
        current_year = datetime.now().year
        years = [current_year, current_year + 1]

        calendar_data = get_calendar_rules(calendar_id, years=years)
        return jsonify(calendar_data), 200
    except ValueError as e:
        return jsonify({'error': str(e)}), 404


@app.route('/api/calculate', methods=['POST'])
def calculate():
    """
    POST /api/calculate

    Perform business day calculation based on provided rules.

    Request Body:
        {
            "operation": "days_between" | "get_future_date",
            "start_date": "YYYY-MM-DD",
            "end_date": "YYYY-MM-DD",  // for days_between
            "business_days": 15,        // for get_future_date

            // Option 1: Provide calendar rules directly
            "calendar_rules": {
                "weekend_days": [5, 6],
                "holidays": ["2024-10-14"],
                "makeup_days": ["2024-10-12"]
            }

            // Option 2: Provide calendar IDs (for multi-calendar support)
            "calendar_ids": ["US", "UK", "DE"]
        }

    Response:
        200: {"business_days": 22, ...} or {"future_date": "2024-10-22", ...}
        400: {"error": "error message"}
    """
    if not request.json:
        return jsonify({'error': 'Request body must be JSON'}), 400

    data = request.json

    # Validate required fields
    operation = data.get('operation')
    start_date = data.get('start_date')
    calendar_rules = data.get('calendar_rules')
    calendar_ids = data.get('calendar_ids')

    if not operation:
        return jsonify({'error': 'operation is required'}), 400

    if not start_date:
        return jsonify({'error': 'start_date is required'}), 400

    # Either calendar_rules OR calendar_ids must be provided
    if not calendar_rules and not calendar_ids:
        return jsonify({'error': 'calendar_rules or calendar_ids is required'}), 400

    # If calendar_ids provided, merge them into calendar_rules
    if calendar_ids:
        try:
            current_year = datetime.now().year
            years = [current_year, current_year + 1]

            # Fetch rules for each calendar
            rules_list = []
            for cal_id in calendar_ids:
                rules = get_calendar_rules(cal_id, years=years)
                rules_list.append(rules)

            # Merge all calendars
            calendar_rules = merge_calendar_rules(rules_list)
        except ValueError as e:
            return jsonify({'error': f'Invalid calendar ID: {str(e)}'}), 400

    # Extract operation-specific fields
    end_date = data.get('end_date')
    business_days = data.get('business_days')

    # Perform calculation
    try:
        result = perform_calculation(
            operation=operation,
            start_date=start_date,
            end_date=end_date,
            business_days=business_days,
            calendar_rules=calendar_rules
        )

        # Include the merged calendar rules in the response for display
        result['calendar_rules'] = calendar_rules

        return jsonify(result), 200

    except ValueError as e:
        return jsonify({'error': str(e)}), 400


# ============================================================================
# Application Initialization
# ============================================================================

if __name__ == '__main__':
    # Load custom rules on startup
    load_custom_rules()

    # Start Flask development server
    print("=" * 60)
    print("Smart Business Day Calculator API v2.0 - Hybrid Library")
    print("=" * 60)
    print(f"Custom rules file: {CUSTOM_RULES_FILE}")
    print(f"Custom calendars loaded: {len(custom_rules)}")
    print()
    print("API Endpoints:")
    print("  GET  /api/calendars")
    print("  GET  /api/calendar/<calendar_id>")
    print("  POST /api/calculate")
    print()
    print("Server running on http://127.0.0.1:8080")
    print("Press CTRL+C to quit")
    print("=" * 60)
    print()

    app.run(debug=True, host='0.0.0.0', port=8080)
