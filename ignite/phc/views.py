from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.db import IntegrityError, transaction
from django.db.models import Count, Max, Q
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST
from .models import AuditLog, ConsultationQueue, DoctorNotificationSubscription, DoctorProfile, PHCAnnouncement, PHCNotification, PHCSettings


def is_admin(user): return user.is_authenticated and (user.is_staff or user.role == 'admin')
def doctor_for(user):
    try: return user.doctor_profile
    except DoctorProfile.DoesNotExist: raise Http404()
def log(user, action, obj=''): AuditLog.objects.create(user=user, action=action, relevant_object=str(obj))
def active_announcements(): return PHCAnnouncement.objects.filter(active=True).filter(Q(expires_at__isnull=True) | Q(expires_at__gt=timezone.now()))

@login_required
def home(request):
    doctors = DoctorProfile.objects.filter(active=True).select_related('user').annotate(waiting_count=Count('queue_entries', filter=Q(queue_entries__status='waiting')))
    mine = {e.doctor_id: e for e in ConsultationQueue.objects.filter(student=request.user, status__in=['waiting', 'called']).select_related('doctor')}
    subscriptions = set(DoctorNotificationSubscription.objects.filter(student=request.user, active=True).values_list('doctor_id', flat=True))
    return render(request, 'phc/home.html', {'doctors': doctors, 'my_entries': mine, 'subscriptions': subscriptions, 'announcements': active_announcements(), 'settings': PHCSettings.get_solo()})

@login_required
def doctor_detail(request, doctor_id):
    doctor = get_object_or_404(DoctorProfile.objects.select_related('user'), pk=doctor_id, active=True)
    schedules = doctor.schedules.all()
    entry = ConsultationQueue.objects.filter(student=request.user, doctor=doctor, status__in=['waiting', 'called']).first()
    subscribed = DoctorNotificationSubscription.objects.filter(student=request.user, doctor=doctor, active=True).exists()
    return render(request, 'phc/doctor_detail.html', {'doctor': doctor, 'schedules': schedules, 'entry': entry, 'subscribed': subscribed, 'settings': PHCSettings.get_solo()})

@login_required
def queue(request):
    entries = ConsultationQueue.objects.filter(student=request.user, status__in=['waiting', 'called']).select_related('doctor__user')
    return render(request, 'phc/queue.html', {'entries': entries})

@login_required
def notifications(request):
    notes = PHCNotification.objects.filter(student=request.user)
    notes.filter(read_at__isnull=True).update(read_at=timezone.now())
    subscriptions = DoctorNotificationSubscription.objects.filter(student=request.user, active=True).select_related('doctor__user')
    return render(request, 'phc/notifications.html', {'notes': notes, 'subscriptions': subscriptions})

@login_required
@require_POST
def subscribe(request, doctor_id):
    doctor = get_object_or_404(DoctorProfile, pk=doctor_id, active=True)
    subscription, _ = DoctorNotificationSubscription.objects.get_or_create(student=request.user, doctor=doctor)
    subscription.active, subscription.notified_at = True, None
    subscription.save(update_fields=['active', 'notified_at'])
    messages.success(request, f'We will notify you when {doctor} is available.')
    return redirect(request.POST.get('next') or 'phc:home')

@login_required
@require_POST
def unsubscribe(request, doctor_id):
    DoctorNotificationSubscription.objects.filter(student=request.user, doctor_id=doctor_id).update(active=False)
    messages.info(request, 'Availability notification cancelled.')
    return redirect(request.POST.get('next') or 'phc:notifications')

@login_required
@require_POST
def join_queue(request, doctor_id):
    # Lock doctor and account before calculating token: concurrent joins receive unique tokens.
    try:
        with transaction.atomic():
            doctor = DoctorProfile.objects.select_for_update().get(pk=doctor_id, active=True)
            type(request.user).objects.select_for_update().get(pk=request.user.pk)
            if not doctor.is_joinable:
                messages.error(request, 'This doctor is not accepting patients right now.')
                return redirect('phc:home')
            if ConsultationQueue.objects.filter(student=request.user, doctor=doctor, status__in=['waiting', 'called']).exists():
                messages.info(request, 'You already have an active entry for this doctor.')
                return redirect('phc:queue')
            token = (ConsultationQueue.objects.filter(doctor=doctor).aggregate(latest=Max('token_number'))['latest'] or 0) + 1
            entry = ConsultationQueue.objects.create(student=request.user, doctor=doctor, token_number=token)
            log(request.user, 'Joined consultation queue', entry.pk)
    except DoctorProfile.DoesNotExist:
        raise Http404()
    except IntegrityError:
        messages.warning(request, 'Your queue entry was just created in another request.')
    else:
        messages.success(request, f'Joined {doctor}. Your token is {entry.token_number}.')
    return redirect('phc:queue')

@login_required
@require_POST
def leave_queue(request, entry_id):
    entry = get_object_or_404(ConsultationQueue, pk=entry_id, student=request.user, status__in=['waiting', 'called'])
    entry.status = ConsultationQueue.Status.CANCELLED
    entry.completed_at = timezone.now()
    entry.save(update_fields=['status', 'completed_at'])
    log(request.user, 'Left consultation queue', entry.pk)
    messages.info(request, 'You have left the queue.')
    return redirect('phc:queue')

@login_required
def doctor_dashboard(request):
    doctor = doctor_for(request.user)
    entries = doctor.queue_entries.filter(status__in=['waiting', 'called']).select_related('student')
    return render(request, 'phc/doctor_dashboard.html', {'doctor': doctor, 'entries': entries, 'waiting_count': entries.filter(status='waiting').count()})

@login_required
@require_POST
def update_status(request):
    doctor = doctor_for(request.user)
    status = request.POST.get('status')
    if status not in DoctorProfile.Status.values: raise Http404()
    was_available = doctor.status == DoctorProfile.Status.AVAILABLE
    doctor.status, doctor.expected_availability = status, request.POST.get('expected_availability', '').strip()
    doctor.accepting_patients = request.POST.get('accepting_patients') == 'on'
    doctor.save()
    if not was_available and status == DoctorProfile.Status.AVAILABLE:
        subscriptions = DoctorNotificationSubscription.objects.filter(doctor=doctor, active=True).select_related('student')
        for sub in subscriptions:
            PHCNotification.objects.create(student=sub.student, message=f'{doctor} is now available at the PHC. You can join the consultation queue.')
        subscriptions.update(active=False, notified_at=timezone.now())
    log(request.user, f'Changed availability to {status}', doctor.pk)
    messages.success(request, 'Availability updated.')
    return redirect('phc:doctor_dashboard')

@login_required
@require_POST
def queue_action(request, entry_id):
    doctor = doctor_for(request.user)
    entry = get_object_or_404(ConsultationQueue, pk=entry_id, doctor=doctor, status__in=['waiting', 'called'])
    action = request.POST.get('action')
    mapping = {'call': 'called', 'complete': 'completed', 'skip': 'skipped', 'cancel': 'cancelled'}
    if action not in mapping: raise Http404()
    entry.status = mapping[action]
    if action == 'call': entry.called_at = timezone.now()
    elif action in ('complete', 'skip', 'cancel'): entry.completed_at = timezone.now()
    entry.save()
    log(request.user, f'Queue entry {action}', entry.pk)
    return redirect('phc:doctor_dashboard')

@user_passes_test(is_admin)
def admin_dashboard(request):
    doctors = DoctorProfile.objects.all().select_related('user')
    return render(request, 'phc/admin_dashboard.html', {'doctors': doctors, 'available': doctors.filter(status='available', active=True).count(), 'waiting': ConsultationQueue.objects.filter(status='waiting').count(), 'subscriptions': DoctorNotificationSubscription.objects.filter(active=True).count(), 'settings': PHCSettings.get_solo()})
