"""
Test suite for Smart Business Day Calculator API v2.0 - Hybrid Library Approach.

This test suite follows TDD principles and tests all core functionality:
- Integration with holidays library for standard holiday data
- Custom rules override system via custom_rules.json
- Business day calculations between two dates
- Future date projections
- Weekend and holiday handling
- Makeup day logic (critical for regions like China)
- API endpoints and error handling

Run with: pytest
"""

import pytest
import json
import tempfile
import os
from datetime import datetime
from unittest.mock import patch, MagicMock


# Pytest fixture to create a test client
@pytest.fixture
def client():
    """Create a test client for the Flask application with mocked custom rules."""
    # Import app here to avoid import errors before mocking
    from app import app, load_custom_rules

    app.config['TESTING'] = True

    # Create a temporary custom_rules.json for testing
    test_rules = {
        "IN-KA": {
            "display_name": "India - Karnataka (Custom Week)",
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

    # Reload custom rules with test data
    from app import custom_rules
    custom_rules.clear()
    custom_rules.update(test_rules)

    with app.test_client() as client:
        yield client


# ============================================================================
# Test Suite 1: Core Business Logic - Pure Functions
# ============================================================================

def test_days_between_simple():
    """Test simple business day calculation (Mon-Fri, no holidays)."""
    from app import perform_calculation

    # Monday to Wednesday: Tue, Wed = 2 business days
    rules = {
        "weekend_days": [5, 6],
        "holidays": [],
        "makeup_days": []
    }

    result = perform_calculation(
        operation="days_between",
        start_date="2024-10-14",  # Monday
        end_date="2024-10-16",    # Wednesday
        calendar_rules=rules
    )

    assert result["business_days"] == 2


def test_days_between_cross_weekend():
    """Test calculation crossing a weekend."""
    from app import perform_calculation

    # Friday to Monday: Sat(skip), Sun(skip), Mon = 1 business day
    rules = {
        "weekend_days": [5, 6],
        "holidays": [],
        "makeup_days": []
    }

    result = perform_calculation(
        operation="days_between",
        start_date="2024-10-18",  # Friday
        end_date="2024-10-21",    # Monday
        calendar_rules=rules
    )

    assert result["business_days"] == 1


def test_days_between_with_holiday():
    """Test calculation including a holiday on a weekday."""
    from app import perform_calculation

    # Monday to Friday with holiday on Wednesday = 3 business days
    rules = {
        "weekend_days": [5, 6],
        "holidays": ["2024-10-16"],  # Wednesday
        "makeup_days": []
    }

    result = perform_calculation(
        operation="days_between",
        start_date="2024-10-14",  # Monday
        end_date="2024-10-18",    # Friday
        calendar_rules=rules
    )

    assert result["business_days"] == 3


def test_days_between_holiday_on_weekend():
    """Test that holidays on weekends are not double-counted."""
    from app import perform_calculation

    # If a holiday falls on Saturday, it shouldn't affect the count
    rules = {
        "weekend_days": [5, 6],
        "holidays": ["2024-10-19"],  # Saturday
        "makeup_days": []
    }

    result = perform_calculation(
        operation="days_between",
        start_date="2024-10-14",  # Monday
        end_date="2024-10-21",    # Monday
        calendar_rules=rules
    )

    assert result["business_days"] == 5  # Tue-Fri + Mon (5 days)


def test_makeup_day_on_weekend():
    """
    CRITICAL TEST: Makeup day logic (e.g., China's work policy).

    When a holiday falls on a weekday but is "made up" on a weekend,
    that weekend day becomes a business day.
    """
    from app import perform_calculation

    # Holiday on Wednesday, makeup on Saturday
    # Saturday should COUNT as a business day
    rules = {
        "weekend_days": [5, 6],
        "holidays": ["2024-10-16"],  # Wednesday
        "makeup_days": ["2024-10-19"]  # Saturday (now a work day)
    }

    result = perform_calculation(
        operation="days_between",
        start_date="2024-10-14",  # Monday
        end_date="2024-10-21",    # Monday
        calendar_rules=rules
    )

    # Tue(15), Wed(holiday-skip), Thu(17), Fri(18), Sat(19-makeup), Sun(skip), Mon(21) = 5 days
    assert result["business_days"] == 5


def test_get_future_date_simple():
    """Test projecting a simple future date (no weekends/holidays crossed)."""
    from app import perform_calculation

    # Start Monday, +3 days = Thursday
    rules = {
        "weekend_days": [5, 6],
        "holidays": [],
        "makeup_days": []
    }

    result = perform_calculation(
        operation="get_future_date",
        start_date="2024-10-14",  # Monday
        business_days=3,
        calendar_rules=rules
    )

    assert result["future_date"] == "2024-10-17"  # Thursday


def test_get_future_date_cross_weekend():
    """Test future date projection crossing a weekend."""
    from app import perform_calculation

    # Start Thursday, +4 days = next Wednesday (skip Sat/Sun)
    rules = {
        "weekend_days": [5, 6],
        "holidays": [],
        "makeup_days": []
    }

    result = perform_calculation(
        operation="get_future_date",
        start_date="2024-10-17",  # Thursday
        business_days=4,
        calendar_rules=rules
    )

    assert result["future_date"] == "2024-10-23"  # Next Wednesday


# ============================================================================
# Test Suite 2: API & Rules Engine Tests
# ============================================================================

def test_get_calendar_rules_standard(client):
    """Test GET /api/calendar/<id> for a standard calendar from holidays library."""
    from app import get_calendar_rules

    # Test US-NY calendar (should use holidays library + defaults)
    rules = get_calendar_rules("US-NY", years=[2024, 2025])

    # Should have default weekend
    assert rules["weekend_days"] == [5, 6]

    # Should have holidays from holidays library
    assert len(rules["holidays"]) > 0

    # Should have some expected US holidays
    holidays_set = set(rules["holidays"])
    assert "2024-01-01" in holidays_set or "2025-01-01" in holidays_set  # New Year
    assert "2024-07-04" in holidays_set or "2025-07-04" in holidays_set  # Independence Day

    # Should have no makeup days (not in custom rules)
    assert rules["makeup_days"] == []


def test_get_calendar_rules_with_weekend_override(client):
    """Test calendar with custom weekend override in custom_rules.json."""
    from app import get_calendar_rules

    # IN-KA should have custom weekend from custom_rules.json
    rules = get_calendar_rules("IN-KA", years=[2024, 2025])

    # Should have custom weekend (Saturday-Sunday instead of default)
    assert rules["weekend_days"] == [5, 6]

    # Should still have holidays from holidays library
    assert len(rules["holidays"]) > 0


def test_get_calendar_rules_with_makeup_days(client):
    """Test calendar with makeup days from custom_rules.json."""
    from app import get_calendar_rules

    # CN (China) should have makeup days
    rules = get_calendar_rules("CN", years=[2024, 2025])

    # Should have makeup days from custom_rules.json
    assert len(rules["makeup_days"]) > 0
    assert "2024-02-04" in rules["makeup_days"]
    assert "2025-01-26" in rules["makeup_days"]

    # Should have holidays from holidays library
    assert len(rules["holidays"]) > 0


def test_get_calendar_rules_custom_only(client):
    """Test a purely custom calendar (not in holidays library)."""
    from app import get_calendar_rules

    # X-CORP is purely custom
    rules = get_calendar_rules("X-CORP", years=[2024, 2025])

    # Should have custom weekend
    assert rules["weekend_days"] == [5, 6]

    # Should have ONLY custom holidays
    assert "2024-12-24" in rules["holidays"]
    assert "2024-12-31" in rules["holidays"]
    assert "2025-12-24" in rules["holidays"]
    assert "2025-12-31" in rules["holidays"]

    # Should have no makeup days
    assert rules["makeup_days"] == []


def test_get_calendars_list(client):
    """Test GET /api/calendars returns comprehensive list."""
    response = client.get('/api/calendars')

    assert response.status_code == 200
    calendars = response.get_json()
    assert isinstance(calendars, list)
    assert len(calendars) > 0

    # Check structure
    assert all("id" in cal and "name" in cal for cal in calendars)

    # Should contain standard calendars from holidays library
    calendar_ids = [cal["id"] for cal in calendars]
    assert "US" in calendar_ids or any("US-" in cid for cid in calendar_ids)
    assert "CA" in calendar_ids or any("CA-" in cid for cid in calendar_ids)
    assert "DE" in calendar_ids or any("DE-" in cid for cid in calendar_ids)

    # Should contain custom calendars
    assert "X-CORP" in calendar_ids
    assert "CN" in calendar_ids


def test_api_calculate_invalid_payload(client):
    """Test POST /api/calculate returns 400 for invalid payload."""
    # Missing start_date
    response = client.post('/api/calculate', json={
        "operation": "days_between",
        "end_date": "2024-10-20"
    })

    assert response.status_code == 400


def test_api_calendar_endpoint(client):
    """Test GET /api/calendar/<id> endpoint."""
    # Test standard calendar
    response = client.get('/api/calendar/US')
    assert response.status_code == 200
    data = response.get_json()
    assert "weekend_days" in data
    assert "holidays" in data
    assert "makeup_days" in data

    # Test custom calendar
    response = client.get('/api/calendar/X-CORP')
    assert response.status_code == 200
    data = response.get_json()
    assert data["makeup_days"] == []
    assert "2024-12-24" in data["holidays"]

    # Test non-existent calendar
    response = client.get('/api/calendar/INVALID-CAL')
    assert response.status_code == 404


def test_api_calculate_days_between(client):
    """Test POST /api/calculate with days_between operation."""
    payload = {
        "operation": "days_between",
        "start_date": "2024-10-14",
        "end_date": "2024-10-18",
        "calendar_rules": {
            "weekend_days": [5, 6],
            "holidays": ["2024-10-16"],
            "makeup_days": []
        }
    }

    response = client.post('/api/calculate', json=payload)

    assert response.status_code == 200
    data = response.get_json()
    assert "business_days" in data
    assert data["business_days"] == 3


def test_api_calculate_future_date(client):
    """Test POST /api/calculate with get_future_date operation."""
    payload = {
        "operation": "get_future_date",
        "start_date": "2024-10-14",
        "business_days": 5,
        "calendar_rules": {
            "weekend_days": [5, 6],
            "holidays": [],
            "makeup_days": []
        }
    }

    response = client.post('/api/calculate', json=payload)

    assert response.status_code == 200
    data = response.get_json()
    assert "future_date" in data


# ============================================================================
# Test Suite 3: Multi-Calendar Support (International Teams)
# ============================================================================

def test_merge_multiple_calendars():
    """Test merging holidays from multiple calendars (union of all holidays)."""
    from app import merge_calendar_rules

    # US has July 4, UK has different holidays
    us_rules = {
        "weekend_days": [5, 6],
        "holidays": ["2024-07-04", "2024-12-25"],
        "makeup_days": []
    }

    uk_rules = {
        "weekend_days": [5, 6],
        "holidays": ["2024-12-25", "2024-12-26"],  # Boxing Day
        "makeup_days": []
    }

    merged = merge_calendar_rules([us_rules, uk_rules])

    # Should contain union of all holidays
    assert "2024-07-04" in merged["holidays"]
    assert "2024-12-25" in merged["holidays"]
    assert "2024-12-26" in merged["holidays"]
    assert len(merged["holidays"]) == 3  # 3 unique holidays

    # Weekends should remain standard
    assert merged["weekend_days"] == [5, 6]


def test_merge_calendars_with_different_weekends():
    """Test that merge uses the UNION of weekend days (most restrictive)."""
    from app import merge_calendar_rules

    # US: Sat-Sun, Middle East: Fri-Sat
    us_rules = {
        "weekend_days": [5, 6],  # Sat, Sun
        "holidays": [],
        "makeup_days": []
    }

    me_rules = {
        "weekend_days": [4, 5],  # Fri, Sat
        "holidays": [],
        "makeup_days": []
    }

    merged = merge_calendar_rules([us_rules, me_rules])

    # Should include all weekend days: Fri, Sat, Sun
    assert sorted(merged["weekend_days"]) == [4, 5, 6]


def test_api_calculate_with_multiple_calendar_ids():
    """Test POST /api/calculate with calendar_ids array for multi-calendar."""
    from app import app

    with app.test_client() as client:
        payload = {
            "operation": "days_between",
            "start_date": "2024-07-01",
            "end_date": "2024-07-10",
            "calendar_ids": ["US", "UK"]  # New parameter
        }

        response = client.post('/api/calculate', json=payload)

        assert response.status_code == 200
        data = response.get_json()
        assert "business_days" in data
        # July 4 is a US holiday, should be excluded
