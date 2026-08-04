from django.contrib.auth.decorators import login_required
from django.shortcuts import render

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
