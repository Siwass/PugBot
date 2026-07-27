from aiogram import Router

from .create import router as create_router
from .text import router as text_router
from .media import router as media_router
from .buttons import router as buttons_router
from .preview import router as preview_router
from .schedule import router as schedule_router
from .schedule_wizard import router as schedule_wizard_router
from .publish import router as publish_router
from .edit import router as edit_router
from .drafts import router as drafts_router
from .confirm_publish import router as confirm_publish_router
from .delete import router as delete_router
from .queue import router as queue_router
from .queue_actions import router as queue_actions_router
from .formatting import router as formatting_router
from .tags import router as tags_router
from .templates import router as templates_router
from .history import router as history_router
from .duplicate import router as duplicate_router
from .published import router as published_router


router = Router()

router.include_router(create_router)
router.include_router(templates_router)
router.include_router(text_router)
router.include_router(media_router)
router.include_router(buttons_router)

# 🎨 Оформление текста
router.include_router(formatting_router)
router.include_router(tags_router)

# Preview должен идти раньше schedule
router.include_router(preview_router)
router.include_router(schedule_wizard_router)
router.include_router(schedule_router)

router.include_router(publish_router)
router.include_router(edit_router)
router.include_router(drafts_router)
router.include_router(history_router)
router.include_router(published_router)
router.include_router(duplicate_router)
router.include_router(confirm_publish_router)
router.include_router(delete_router)

router.include_router(queue_router)
router.include_router(queue_actions_router)
