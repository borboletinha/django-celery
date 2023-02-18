from elk.celery import app as celery
from market.models import Subscription
from market.signals import subscription_not_used_for_week


@celery.task
def send_reminder_about_forgotten_subscription():
    """
    Gets all forgotten subscriptions, sends a notification to each subscriber,
    updates the "reminder_sent" field on a subscription instance
    """
    for subscription in Subscription.objects.forgotten():
        subscription_not_used_for_week.send(sender=send_reminder_about_forgotten_subscription, instance=subscription)
        subscription.reminder_sent = True
        subscription.save()
