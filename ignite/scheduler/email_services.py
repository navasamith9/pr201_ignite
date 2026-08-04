from django.conf import settings
from django.core.mail import send_mail


def send_event_invitation(event, recipients):
    """
    Sends an invitation email asking students to register
    for an event.

    During development, the email is printed in the terminal
    because we are using Django's console email backend.
    """

    # Remove users without email addresses
    recipient_emails = [
        user.email
        for user in recipients
        if user.email
    ]

    # If nobody has an email address, don't send anything
    if not recipient_emails:
        return 0

    subject = f"IGNITE - Registration Open: {event.title}"

    message = f"""
Hello,

You are invited to register for the following event.

Event: {event.title}
Type: {event.get_event_type_display()}
Purpose: {event.purpose}

Date: {event.event_date}
Time: {event.start_time} - {event.end_time}

Registration deadline:
{event.registration_deadline}

Please register before the deadline if you wish to attend.

Regards,
IGNITE
""".strip()

    return send_mail(
        subject=subject,
        message=message,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=recipient_emails,
        fail_silently=False,
    )

# ============================================================
# 2. REGISTRATION DEADLINE REMINDER
# ============================================================

def send_registration_reminder(event, recipients):
    """
    Reminds participants that event registration
    will close soon.
    """

    recipient_emails = [
        user.email
        for user in recipients
        if user.email
    ]

    if not recipient_emails:
        return 0

    subject = (
        f"IGNITE - Registration Reminder: {event.title}"
    )

    message = f"""
Hello,

This is a reminder that registration for the following
event will close soon.

Event: {event.title}

Date: {event.event_date}
Time: {event.start_time} - {event.end_time}

Registration deadline:
{event.registration_deadline}

Please register before the deadline if you wish to attend.

Regards,
IGNITE
""".strip()

    return send_mail(
        subject=subject,
        message=message,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=recipient_emails,
        fail_silently=False,
    )


# ============================================================
# 3. ROOM CHANGE NOTIFICATION
# ============================================================

def send_room_change_notification(
    event,
    recipients,
    old_room,
    new_room
):
    """
    Notifies registered participants when their event room
    changes.
    """

    recipient_emails = [
        user.email
        for user in recipients
        if user.email
    ]

    if not recipient_emails:
        return 0

    subject = (
        f"IGNITE - Room Changed: {event.title}"
    )

    old_room_name = (
        old_room.name
        if old_room
        else "Not assigned"
    )

    new_room_name = new_room.name

    message = f"""
Hello,

The lecture hall for your registered event has changed.

Event: {event.title}

Date: {event.event_date}
Time: {event.start_time} - {event.end_time}

Previous room:
{old_room_name}

New room:
{new_room_name}

Please attend the event in the new room.

Regards,
IGNITE
""".strip()

    return send_mail(
        subject=subject,
        message=message,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=recipient_emails,
        fail_silently=False,
    )


# ============================================================
# 4. FINAL EVENT REMINDER
# ============================================================

def send_event_reminder(event, recipients):
    """
    Sends the final event reminder to registered participants.
    """

    recipient_emails = [
        user.email
        for user in recipients
        if user.email
    ]

    if not recipient_emails:
        return 0

    subject = (
        f"IGNITE - Event Reminder: {event.title}"
    )

    room_name = (
        event.booked_room.name
        if event.booked_room
        else "To be announced"
    )

    message = f"""
Hello,

This is a reminder about your upcoming event.

Event: {event.title}

Date: {event.event_date}
Time: {event.start_time} - {event.end_time}

Room:
{room_name}

Please arrive on time.

Regards,
IGNITE
""".strip()

    return send_mail(
        subject=subject,
        message=message,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=recipient_emails,
        fail_silently=False,
    )

# ============================================================
# 5. EVENT CANCELLATION EMAIL
# ============================================================

def send_event_cancellation(event, recipients):
    """
    Sends an email to all registered participants
    when an event is cancelled.
    """

    recipient_emails = [
        user.email
        for user in recipients
        if user.email
    ]

    if not recipient_emails:
        return 0

    subject = f"IGNITE - Event Cancelled: {event.title}"

    message = f"""
Hello,

We regret to inform you that the following event has been cancelled.

Event:
{event.title}

Date:
{event.event_date}

Time:
{event.start_time} - {event.end_time}

Please ignore previous notifications regarding this event.

Regards,
IGNITE Team
""".strip()

    return send_mail(
        subject=subject,
        message=message,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=recipient_emails,
        fail_silently=False,
    )