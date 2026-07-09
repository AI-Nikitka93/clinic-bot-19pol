from sqladmin import ModelView, BaseView, expose
from sqlalchemy import select, func
from app.core.database import AsyncSessionLocal
from app.models import User, Source, Specialty, Doctor, Ticket, Subscription, HistoryLog

class DashboardView(BaseView):
    name = "Dashboard"
    icon = "fa-solid fa-chart-line"

    @expose("/", methods=["GET"])
    async def dashboard_page(self, request):
        async with AsyncSessionLocal() as session:
            users_count = await session.scalar(select(func.count(User.id)))
            subs_count = await session.scalar(select(func.count(Subscription.id)))
            tickets_count = await session.scalar(select(func.count(Ticket.id)))

        return self.templates.TemplateResponse(
            request,
            "dashboard.html",
            context={
                "users_count": users_count,
                "subs_count": subs_count,
                "tickets_count": tickets_count
            }
        )

class UserAdmin(ModelView, model=User):
    column_list = [User.id, User.telegram_id, User.username, User.created_at]
    name = "User"
    name_plural = "Users"
    icon = "fa-solid fa-user"

class SourceAdmin(ModelView, model=Source):
    column_list = [Source.id, Source.name, Source.base_url, Source.is_active]
    name = "Source"
    name_plural = "Sources"
    icon = "fa-solid fa-globe"

class SpecialtyAdmin(ModelView, model=Specialty):
    column_list = [Specialty.id, Specialty.name, Specialty.source_id]
    name = "Specialty"
    name_plural = "Specialties"
    icon = "fa-solid fa-stethoscope"

class DoctorAdmin(ModelView, model=Doctor):
    column_list = [Doctor.id, Doctor.full_name, Doctor.specialty_id]
    name = "Doctor"
    name_plural = "Doctors"
    icon = "fa-solid fa-user-md"

class TicketAdmin(ModelView, model=Ticket):
    column_list = [Ticket.id, Ticket.doctor_id, Ticket.date, Ticket.time, Ticket.status]
    name = "Ticket"
    name_plural = "Tickets"
    icon = "fa-solid fa-ticket"

class SubscriptionAdmin(ModelView, model=Subscription):
    column_list = [Subscription.id, Subscription.user_id, Subscription.specialty_id, Subscription.doctor_id]
    name = "Subscription"
    name_plural = "Subscriptions"
    icon = "fa-solid fa-bell"

class HistoryLogAdmin(ModelView, model=HistoryLog):
    column_list = [HistoryLog.id, HistoryLog.entity_type, HistoryLog.event_type, HistoryLog.timestamp]
    name = "History Log"
    name_plural = "History Logs"
    icon = "fa-solid fa-history"
