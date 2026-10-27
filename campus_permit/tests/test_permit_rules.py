"""車證核心規則單元測試。執行前請依 README 建立 .env 並安裝相依套件。"""
from datetime import datetime
from app.routers.permits import add_one_year, current_status
from app.schemas import VehicleIn
from app.models import PermitApplication

def test_one_calendar_year_normal_date():
    assert add_one_year(datetime(2026, 10, 27)).date().isoformat() == "2027-10-27"

def test_one_calendar_year_leap_day():
    assert add_one_year(datetime(2024, 2, 29)).date().isoformat() == "2025-02-28"

def test_license_plate_normalized():
    v = VehicleIn(license_plate=" abc-1234 ", vehicle_type="car")
    assert v.license_plate == "ABC-1234"

def test_approved_permit_expires_dynamically():
    p = PermitApplication(status="approved", valid_until=datetime(2026, 1, 1))
    assert current_status(p, datetime(2026, 1, 1)) == "expired"
    assert current_status(p, datetime(2025, 12, 31)) == "approved"
