from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from csvapp.models import EventPushLog, EventRSVP, PokerEvent, PushToken
from csvapp.push import send_expo_push


class Command(BaseCommand):
    help = 'Send scheduled event push notifications (headcount nudge + day-of reminder)'

    def handle(self, *args, **options):
        today = timezone.localdate()

        for event in PokerEvent.objects.filter(event_date__date=today + timedelta(days=3)):
            self._headcount_nudge(event, today)

        for event in PokerEvent.objects.filter(event_date__date=today):
            self._day_of_reminder(event, today)

    def _headcount_nudge(self, event, today):
        if EventPushLog.objects.filter(
            event=event, kind=EventPushLog.KIND_HEADCOUNT, sent_date=today
        ).exists():
            return

        # Audience: users with push tokens who have NOT responded yes or no
        exclude_emails = set(
            EventRSVP.objects
            .filter(event=event, response__in=['yes', 'no'])
            .values_list('user_identifier', flat=True)
        )
        tokens = list(
            PushToken.objects
            .exclude(user__email__in=exclude_emails)
            .values_list('token', flat=True)
        )

        if tokens:
            result = send_expo_push(
                tokens,
                title=event.title,
                body='Please confirm your RSVP — need a final headcount.',
                data={'type': 'rsvp_prompt', 'event_id': event.id},
                category_id='rsvp_prompt',
            )
            self.stdout.write(f'Headcount nudge "{event.title}": {result}')

        EventPushLog.objects.create(
            event=event, kind=EventPushLog.KIND_HEADCOUNT, sent_date=today
        )

    def _day_of_reminder(self, event, today):
        if EventPushLog.objects.filter(
            event=event, kind=EventPushLog.KIND_DAY_OF, sent_date=today
        ).exists():
            return

        yes_emails = set(
            EventRSVP.objects
            .filter(event=event, response='yes')
            .values_list('user_identifier', flat=True)
        )
        tokens = list(
            PushToken.objects
            .filter(user__email__in=yes_emails)
            .values_list('token', flat=True)
        )

        if tokens:
            result = send_expo_push(
                tokens,
                title=event.title,
                body='Game tonight — see you there!',
                data={'kind': 'event_day_of', 'eventId': event.id},
            )
            self.stdout.write(f'Day-of reminder "{event.title}": {result}')

        EventPushLog.objects.create(
            event=event, kind=EventPushLog.KIND_DAY_OF, sent_date=today
        )
