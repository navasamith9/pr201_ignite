from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from scheduler.services import ensure_default_scheduler_data
from scheduler.permissions import can_book_rooms, is_faculty, is_scheduler_admin

def home(request):
    return render(request, 'home.html')


@login_required
def dashboard(request):
    # Until notification data is connected, this provides the dashboard with
    # useful recent campus updates and keeps the template ready for real data.
    recent_notifications = [
        {
            'icon': 'bi-calendar2-check',
            'tone': 'indigo',
            'title': 'LHTC session confirmed',
            'message': 'Your Physics Lab session is confirmed for tomorrow at 10:00 AM.',
            'time': '12 min ago',
            'unread': True,
        },
        {
            'icon': 'bi-bus-front',
            'tone': 'cyan',
            'title': 'Route 3 is arriving soon',
            'message': 'The North Gate shuttle will arrive at the Main Block in 6 minutes.',
            'time': '38 min ago',
            'unread': True,
        },
        {
            'icon': 'bi-cup-hot',
            'tone': 'orange',
            'title': 'Canteen menu updated',
            'message': 'Today’s lunch specials and availability are ready to view.',
            'time': '1 hr ago',
            'unread': False,
        },
        {
            'icon': 'bi-search',
            'tone': 'green',
            'title': 'Possible match found',
            'message': 'A black water bottle matching your report was added to Lost & Found.',
            'time': 'Yesterday',
            'unread': False,
        },
    ]
    return render(request, 'dashboard.html', {'recent_notifications': recent_notifications})


@login_required
def scheduler(request):
    """Render the LHTC Scheduler workspace for authenticated users."""
    ensure_default_scheduler_data()
    if is_scheduler_admin(request.user):
        scheduler_role = "admin"
    elif is_faculty(request.user):
        scheduler_role = "faculty"
    elif can_book_rooms(request.user):
        scheduler_role = "coordinator"
    else:
        scheduler_role = "student"
    return render(request, 'scheduler.html', {
        'scheduler_role': scheduler_role,
        'scheduler_can_book': can_book_rooms(request.user),
        'scheduler_is_admin': is_scheduler_admin(request.user),
    })
