from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db.models import Q
from django.shortcuts import redirect, render

from scheduler.services import ensure_default_scheduler_data
from scheduler.permissions import can_book_rooms, is_faculty, is_scheduler_admin


SERVICE_ADMIN_FIELDS = {
    'lhtc': ('is_lhtc_admin', 'LHTC administrator'),
    'phc': ('is_phc_admin', 'PHC administrator'),
    'bus': ('is_bus_admin', 'Bus administrator'),
    'canteen': ('is_canteen_admin', 'Canteen administrator'),
}


def is_global_admin(user):
    """Return whether a user may grant application-wide or service admin roles."""
    return bool(
        user
        and user.is_authenticated
        and (user.is_superuser or user.is_staff or user.role == user.Role.ADMIN)
    )


def home(request):
    """Render the campus home page and let administrators grant app access."""
    can_manage_admins = is_global_admin(request.user)

    if request.method == 'POST':
        if not can_manage_admins:
            raise PermissionDenied

        scope = request.POST.get('access_scope', 'global')
        if scope == 'revoke':
            try:
                account = get_user_model().objects.get(pk=request.POST.get('access_target_id'))
            except (get_user_model().DoesNotExist, TypeError, ValueError):
                messages.error(request, 'That administrator account could not be found.')
                return redirect('home')

            if account.is_superuser:
                messages.error(request, 'Superuser access cannot be changed from this page.')
                return redirect('home')

            service = request.POST.get('service_admin_role', '')
            if service == 'global':
                if account.pk == request.user.pk:
                    messages.error(request, 'You cannot revoke your own global administrator access.')
                    return redirect('home')
                if not is_global_admin(account):
                    messages.error(request, 'This account does not have global administrator access.')
                    return redirect('home')
                if account.is_global_admin_grant:
                    account.role = account.global_admin_previous_role or account.Role.STUDENT
                    account.is_staff = account.global_admin_previous_staff
                else:
                    # Legacy global administrators predate the reversible
                    # grant workflow.  Remove only the global app access.
                    if account.role == account.Role.ADMIN:
                        account.role = account.Role.STUDENT
                    account.is_staff = False
                account.is_global_admin_grant = False
                account.global_admin_previous_role = ''
                account.global_admin_previous_staff = False
                account.save(update_fields=[
                    'role', 'is_staff', 'is_global_admin_grant',
                    'global_admin_previous_role', 'global_admin_previous_staff',
                ])
                messages.success(request, f'Global administrator access revoked for {account.email or account.username}.')
            else:
                service_config = SERVICE_ADMIN_FIELDS.get(service)
                if service_config is None:
                    messages.error(request, 'Choose a valid service administrator role.')
                    return redirect('home')
                field_name, role_name = service_config
                if not getattr(account, field_name):
                    messages.error(request, f'{account.email or account.username} does not have {role_name} access.')
                    return redirect('home')
                setattr(account, field_name, False)
                account.save(update_fields=[field_name])
                messages.success(request, f'{role_name} access revoked for {account.email or account.username}.')
            return redirect('home')

        email = request.POST.get('admin_email', '').strip().lower()
        if not email:
            messages.error(request, 'Enter the institute email address to grant administrator access.')
            return redirect('home')

        account = get_user_model().objects.filter(email__iexact=email).first()
        if account is None:
            messages.error(request, 'That account has not signed in yet. Ask them to sign in once, then grant access.')
            return redirect('home')

        if scope == 'global':
            if is_global_admin(account):
                messages.info(request, f'{account.email or account.username} already has global administrator access.')
                return redirect('home')
            account.global_admin_previous_role = account.role
            account.global_admin_previous_staff = account.is_staff
            account.is_global_admin_grant = True
            account.role = account.Role.ADMIN
            # Some established Ignite tools use the application role, while
            # ticket verification and Django's staff-only checks use is_staff.
            account.is_staff = True
            account.save(update_fields=[
                'role', 'is_staff', 'is_global_admin_grant',
                'global_admin_previous_role', 'global_admin_previous_staff',
            ])
            messages.success(request, f'Administrator access granted to {account.email or account.username}.')
        elif scope == 'service':
            service = request.POST.get('service_admin_role', '')
            service_config = SERVICE_ADMIN_FIELDS.get(service)
            if service_config is None:
                messages.error(request, 'Choose a valid service administrator role.')
                return redirect('home')
            field_name, role_name = service_config
            setattr(account, field_name, True)
            account.save(update_fields=[field_name])
            messages.success(request, f'{role_name} access granted to {account.email or account.username}.')
        else:
            messages.error(request, 'Choose a valid administrator access type.')
        return redirect('home')

    user_model = get_user_model()
    global_admins = user_model.objects.filter(
        Q(role=user_model.Role.ADMIN) | Q(is_staff=True)
    ).order_by('email', 'username')
    service_admin_groups = [
        {
            'key': key,
            'name': role_name,
            'accounts': user_model.objects.filter(**{field_name: True}).order_by('email', 'username'),
        }
        for key, (field_name, role_name) in SERVICE_ADMIN_FIELDS.items()
    ]
    return render(request, 'home.html', {
        'can_manage_admins': can_manage_admins,
        'global_admins': global_admins,
        'service_admin_groups': service_admin_groups,
    })


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


def _scheduler_context(request):
    """Shared role data for every LHTC Scheduler page."""
    ensure_default_scheduler_data()
    if is_scheduler_admin(request.user):
        scheduler_role = "admin"
    elif is_faculty(request.user):
        scheduler_role = "faculty"
    elif can_book_rooms(request.user):
        scheduler_role = "coordinator"
    else:
        scheduler_role = "student"
    return {
        'scheduler_role': scheduler_role,
        'scheduler_calendar_scope': 'campus',
        'scheduler_is_student': request.user.role == request.user.Role.STUDENT,
        'scheduler_can_book': can_book_rooms(request.user),
        'scheduler_is_admin': is_scheduler_admin(request.user),
    }


def _require_scheduler_admin(request):
    if not is_scheduler_admin(request.user):
        raise PermissionDenied


@login_required
def scheduler(request):
    """Render the LHTC Scheduler navigation dashboard."""
    return render(request, 'scheduler.html', _scheduler_context(request))


@login_required
def scheduler_room_booking(request):
    if not can_book_rooms(request.user):
        raise PermissionDenied
    return render(request, 'scheduler/room_booking.html', _scheduler_context(request))


@login_required
def scheduler_activity(request):
    return render(request, 'scheduler/activity.html', _scheduler_context(request))


@login_required
def scheduler_campus_schedule(request):
    return render(request, 'scheduler/campus_schedule.html', _scheduler_context(request))


@login_required
def scheduler_add_room(request):
    _require_scheduler_admin(request)
    return render(request, 'scheduler/add_room.html', _scheduler_context(request))


@login_required
def scheduler_timetable_entries(request):
    _require_scheduler_admin(request)
    return render(request, 'scheduler/timetable_entries.html', _scheduler_context(request))


@login_required
def scheduler_grant_access(request):
    _require_scheduler_admin(request)
    return render(request, 'scheduler/grant_access.html', _scheduler_context(request))
