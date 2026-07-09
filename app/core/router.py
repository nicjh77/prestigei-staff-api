from app.controllers import (
    announcements,
    attendance,
    auth,
    daily_log,
    holidays,
    notice,
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
    (holidays.router,       "/holidays"),
    (daily_log.router,      "/daily-log"),
    (notice.router,         "/notices"),
    (announcements.router,  "/announcements"),
    (notifications.router,  "/notifications"),
    (weekly_vision.router,  "/weekly-vision"),
]
