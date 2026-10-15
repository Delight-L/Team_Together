"""Regional context only; preserves all existing work/review storage endpoints."""
from backend.api.common import check_city_access
from backend.db.region_insights import load_region_insights


def detail(request):
    city = request.text('city')
    check_city_access(request.user, city)
    return load_region_insights(city)
