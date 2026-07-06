from app.controllers import (
    announcements,
    attendance,
    auth,
    bulletin,
    daily_log,
    notifications,
    schedule,
    users,
    weekly_vision,
)

routers = [
    (auth.router,           "/auth"),
    (users.router,          "/users"),
    (attendance.router,     "/attendance"),
    (schedule.router,       "/schedule"),
    (daily_log.router,      "/daily-log"),
    (bulletin.router,       "/bulletin"),
    (announcements.router,  "/announcements"),
    (notifications.router,  "/notifications"),
    (weekly_vision.router,  "/weekly-vision"),
]
