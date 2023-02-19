from datetime import timedelta
from unittest.mock import patch

from freezegun import freeze_time
from django.core import mail
from mixer.backend.django import mixer
from elk.utils.testing import TestCase, create_customer, create_teacher
from market.models import Subscription
from market.tasks import send_reminder_about_forgotten_subscription
from products.models import Product1


@freeze_time('2032-12-01 12:00')
class ForgottenSubscriptionReminderTestCase(TestCase):
    fixtures = ('products', 'lessons')

    @classmethod
    def setUpTestData(cls):
        cls.product = Product1.objects.get(pk=1)
        cls.product.duration = timedelta(days=50)
        cls.product.save()

        cls.customer = create_customer()

    def setUp(self):
        self.s = Subscription(
            customer=self.customer,
            product=self.product,
            buy_price=150
        )
        self.s.save()

    @patch('market.models.signals.class_scheduled.send')
    def _schedule(self, c, date, *args, **kwargs):
        c.timeline = mixer.blend(
            'timeline.Entry',
            lesson_type=c.lesson_type,
            teacher=create_teacher(),
            start=date,
            **kwargs
        )
        c.save()

    def test_remind_of_forgotten_subscription(self):
        """
        Should send a reminder email to owners of forgotten subscriptions
        """
        classes = self.s.classes.all()
        self._schedule(
            classes[0],
            self.tzdatetime(2032, 12, 2, 12, 0),
            is_finished=True,
            end=self.tzdatetime(2032, 12, 2, 13, 0))

        with freeze_time('2032-12-15 12:00'):
            send_reminder_about_forgotten_subscription()
            self.assertEqual(len(mail.outbox), 1)

    def test_do_not_remind_if_user_has_planned_class(self):
        """
        Should not send a reminder email to subscribers if they have a planned class
        """
        classes = self.s.classes.all()
        self._schedule(classes[0], self.tzdatetime(2032, 12, 5, 13, 0))

        with freeze_time('2032-12-5 12:00'):
            send_reminder_about_forgotten_subscription()
            self.assertEqual(len(mail.outbox), 0)

    def test_do_not_remind_if_user_had_class_less_than_week_ago(self):
        """
        Should not send a reminder email to subscribers if they had a class less than a week ago
        """
        classes = self.s.classes.all()
        self._schedule(
            classes[0],
            self.tzdatetime(2032, 12, 4, 12, 0),
            is_finished=True,
            end=self.tzdatetime(2032, 12, 4, 13, 0)
        )

        with freeze_time('2032-12-5 12:00'):
            send_reminder_about_forgotten_subscription()
            self.assertEqual(len(mail.outbox), 0)

    def test_do_not_send_more_than_one_reminder(self):
        """
        Should not send multiple reminders to one subscriber
        """
        classes = self.s.classes.all()
        self._schedule(
            classes[0],
            self.tzdatetime(2032, 12, 2, 12, 0),
            is_finished=True,
            end=self.tzdatetime(2032, 12, 2, 13, 0))

        with freeze_time('2032-12-15 12:00'):
            for i in range(3):
                send_reminder_about_forgotten_subscription()
            self.assertEqual(len(mail.outbox), 1)

    def test_do_not_mark_subscription_as_forgotten_if_reminder_was_sent(self):
        """
        Should mark a subscription as forgotten if a reminder was sent to a subscriber
        """
        classes = self.s.classes.all()
        self._schedule(
            classes[0],
            self.tzdatetime(2032, 12, 4, 12, 0),
            is_finished=True,
            end=self.tzdatetime(2032, 12, 4, 13, 0)
        )
        self.s.update_first_lesson_date()
        self.s.reminder_sent = True
        self.s.save()

        self.assertEqual(Subscription.objects.forgotten().count(), 0)
