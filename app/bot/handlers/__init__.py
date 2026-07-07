from aiogram import Router

from app.bot.handlers import donate, inline, menu, pause, quiz, settings, start, stats

router = Router(name="root")
router.include_router(start.router)
router.include_router(menu.router)
router.include_router(quiz.router)
router.include_router(stats.router)
router.include_router(settings.router)
router.include_router(inline.router)
router.include_router(donate.router)
router.include_router(pause.router)
