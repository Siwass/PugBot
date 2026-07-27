from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import Template

DEFAULT_TEMPLATES = (
    {
        "name": "📺 Новый ролик",
        "text": (
            "🔥 Уже на канале!\n\n"
            "👇 Смотреть:"
        ),
        "buttons": None,
    },
    {
        "name": "⚡ Shorts",
        "text": "⚡ Новый Shorts на канале!",
        "buttons": None,
    },
    {
        "name": "📰 Новости",
        "text": "📰 Кратко о главном:",
        "buttons": None,
    },
)


class TemplateRepository:

    def __init__(self, session: AsyncSession):
        self.session = session

    async def list_for_user(self, user_id: int) -> list[Template]:
        result = await self.session.execute(
            select(Template)
            .where(Template.user_id == user_id)
            .order_by(Template.is_system.desc(), Template.created_at.asc())
        )
        return list(result.scalars().all())

    async def get_by_id(self, template_id: int) -> Template | None:
        result = await self.session.execute(
            select(Template).where(Template.id == template_id)
        )
        return result.scalar_one_or_none()

    async def ensure_defaults(self, user_id: int) -> list[Template]:
        existing = await self.list_for_user(user_id)
        if existing:
            return existing

        for item in DEFAULT_TEMPLATES:
            template = Template(
                user_id=user_id,
                name=item["name"],
                text=item["text"],
                buttons=item["buttons"],
                is_system=True,
            )
            self.session.add(template)

        await self.session.commit()
        return await self.list_for_user(user_id)

    async def create(
        self,
        *,
        user_id: int,
        name: str,
        text: str,
        buttons: str | None = None,
        is_system: bool = False,
    ) -> Template:
        template = Template(
            user_id=user_id,
            name=name,
            text=text,
            buttons=buttons,
            is_system=is_system,
        )
        self.session.add(template)
        await self.session.commit()
        await self.session.refresh(template)
        return template

    async def delete(self, template_id: int, user_id: int) -> bool:
        template = await self.get_by_id(template_id)
        if not template or template.user_id != user_id:
            return False
        if template.is_system:
            return False
        await self.session.delete(template)
        await self.session.commit()
        return True
