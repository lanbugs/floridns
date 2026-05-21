from fastapi import APIRouter

from app.api.endpoints import accounts, admin, audit, auth, dyndns, records, search, settings, stats, templates, users, zone_history, zone_settings, zones

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(admin.router)
api_router.include_router(zones.router)
api_router.include_router(records.router)
api_router.include_router(zone_history.router)
api_router.include_router(zone_settings.router)
api_router.include_router(users.router)
api_router.include_router(audit.router)
api_router.include_router(stats.router)
api_router.include_router(search.router)
api_router.include_router(settings.router)
api_router.include_router(accounts.router)
api_router.include_router(templates.router)
api_router.include_router(dyndns.router)
