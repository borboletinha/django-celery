from elk.celery import app as celery
from market.models import Subscription
from market.signals import remind_student_about_subscription


@celery.task
def send_reminder_about_forgotten_subscription():
    """
    Gets all forgotten subscriptions, sends a notification to each subscriber,
    updates the "notification_sent" field on a subscription instance
    """
    for subscription in Subscription.objects.forgotten():
        forgotten_subscription.send(sender=send_reminder_about_forgotten_subscription, instance=subscription)
        subscription.notification_sent = True
        subscription.save()
