from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required, user_passes_test
from django.db import IntegrityError, transaction
from django.db.models import Count, Max, Q
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST
from .forms import AnnouncementForm, DoctorProfileForm, DoctorScheduleForm, PHCSettingsForm
from .models import AuditLog, ConsultationQueue, DoctorNotificationSubscription, DoctorProfile, PHCAnnouncement, PHCNotification, PHCSettings


def is_admin(user):
    return user.is_authenticated and (
        user.is_superuser
        or user.is_staff
        or user.role == 'admin'
        or user.is_phc_admin
    )
def matched_doctor_for(user):
    """Resolve the doctor profile using the admin-approved email as the source of truth."""
    if not user.email:
        return None
    with transaction.atomic():
        # An account can have only one doctor profile. Remove a previous test
        # mapping if the admin has moved this email to a different doctor.
        DoctorProfile.objects.select_for_update().filter(user_id=user.pk).exclude(
            email__iexact=user.email
        ).update(user=None)
        doctor = DoctorProfile.objects.select_for_update().filter(email__iexact=user.email).first()
        if doctor and doctor.user_id != user.pk:
            # Email is the explicit admin assignment. It supersedes a stale
            # login link left behind when a doctor profile was edited.
            doctor.user = user
            doctor.save(update_fields=['user'])
        return doctor


def is_student(user):
    return user.is_authenticated and user.role == user.Role.STUDENT and not DoctorProfile.objects.filter(email__iexact=user.email).exists()


def doctor_for(user):
    doctor = matched_doctor_for(user)
    if not doctor:
        raise Http404()
    return doctor
def log(user, action, obj=''): AuditLog.objects.create(user=user, action=action, relevant_object=str(obj))
def active_announcements(): return PHCAnnouncement.objects.filter(active=True).filter(Q(expires_at__isnull=True) | Q(expires_at__gt=timezone.now()))

@login_required
def home(request):
    # The PHC landing URL is role-aware, like the scheduler workspace.
    if is_admin(request.user):
        return redirect('phc:admin_dashboard')
    if matched_doctor_for(request.user):
        return redirect('phc:doctor_dashboard')
    doctors = DoctorProfile.objects.select_related('user').annotate(waiting_count=Count('queue_entries', filter=Q(queue_entries__status='waiting')))
    mine = {e.doctor_id: e for e in ConsultationQueue.objects.filter(student=request.user, status__in=['waiting', 'called']).select_related('doctor')}
    subscriptions = set(DoctorNotificationSubscription.objects.filter(student=request.user, active=True).values_list('doctor_id', flat=True))
    return render(request, 'phc/home.html', {
        'doctors': doctors,
        'my_entries': mine,
        'subscriptions': subscriptions,
        'announcements': active_announcements(),
        'settings': PHCSettings.get_solo(),
        'unread_notification_count': PHCNotification.objects.filter(student=request.user, read_at__isnull=True).count(),
    })

@user_passes_test(is_student)
def doctor_detail(request, doctor_id):
    doctor = get_object_or_404(DoctorProfile.objects.select_related('user'), pk=doctor_id)
    schedules = doctor.schedules.all()
    entry = ConsultationQueue.objects.filter(student=request.user, doctor=doctor, status__in=['waiting', 'called']).first()
    subscribed = DoctorNotificationSubscription.objects.filter(student=request.user, doctor=doctor, active=True).exists()
    return render(request, 'phc/doctor_detail.html', {'doctor': doctor, 'schedules': schedules, 'entry': entry, 'subscribed': subscribed, 'settings': PHCSettings.get_solo()})

@user_passes_test(is_student)
def queue(request):
    entries = ConsultationQueue.objects.filter(student=request.user, status__in=['waiting', 'called']).select_related('doctor__user')
    return render(request, 'phc/queue.html', {'entries': entries})

@user_passes_test(is_student)
def notifications(request):
    notes = PHCNotification.objects.filter(student=request.user)
    notes.filter(read_at__isnull=True).update(read_at=timezone.now())
    subscriptions = DoctorNotificationSubscription.objects.filter(student=request.user, active=True).select_related('doctor__user')
    return render(request, 'phc/notifications.html', {'notes': notes, 'subscriptions': subscriptions})

@user_passes_test(is_student)
@require_POST
def subscribe(request, doctor_id):
    doctor = get_object_or_404(DoctorProfile, pk=doctor_id)
    subscription, _ = DoctorNotificationSubscription.objects.get_or_create(student=request.user, doctor=doctor)
    subscription.active, subscription.notified_at = True, None
    subscription.save(update_fields=['active', 'notified_at'])
    messages.success(request, f'We will notify you when {doctor} is available.')
    return redirect(request.POST.get('next') or 'phc:home')

@user_passes_test(is_student)
@require_POST
def unsubscribe(request, doctor_id):
    DoctorNotificationSubscription.objects.filter(student=request.user, doctor_id=doctor_id).update(active=False)
    messages.info(request, 'Availability notification cancelled.')
    return redirect(request.POST.get('next') or 'phc:notifications')

@user_passes_test(is_student)
@require_POST
def join_queue(request, doctor_id):
    # Lock doctor and account before calculating token: concurrent joins receive unique tokens.
    try:
        with transaction.atomic():
            doctor = DoctorProfile.objects.select_for_update().get(pk=doctor_id)
            get_user_model().objects.select_for_update().get(pk=request.user.pk)
            if not doctor.is_joinable:
                messages.error(request, 'This doctor is not accepting patients right now.')
                return redirect('phc:home')
            if ConsultationQueue.objects.filter(student=request.user, doctor=doctor, status__in=['waiting', 'called']).exists():
                messages.info(request, 'You already have an active entry for this doctor.')
                return redirect('phc:queue')
            token = (ConsultationQueue.objects.filter(
                doctor=doctor, status__in=['waiting', 'called']
            ).aggregate(latest=Max('token_number'))['latest'] or 0) + 1
            entry = ConsultationQueue.objects.create(student=request.user, doctor=doctor, token_number=token)
            log(request.user, 'Joined consultation queue', entry.pk)
    except DoctorProfile.DoesNotExist:
        raise Http404()
    except IntegrityError:
        messages.warning(request, 'Your queue entry was just created in another request.')
    else:
        messages.success(request, f'Joined {doctor}. Your token is {entry.token_number}.')
    return redirect('phc:queue')

@user_passes_test(is_student)
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
    doctor = matched_doctor_for(request.user)
    if not doctor:
        messages.error(request, 'Your account is not linked to a doctor profile. Ask the PHC admin to add your exact institute email.')
        return redirect('phc:home')
    entries = doctor.queue_entries.filter(status__in=['waiting', 'called']).select_related('student').order_by('token_number')
    return render(request, 'phc/doctor_dashboard.html', {
        'doctor': doctor,
        'entries': entries,
        'waiting_count': entries.filter(status='waiting').count(),
        'called_entry': entries.filter(status='called').first(),
        'announcements': active_announcements(),
        'settings': PHCSettings.get_solo(),
    })

@login_required
@require_POST
def update_status(request):
    doctor = doctor_for(request.user)
    status = request.POST.get('status')
    if status not in (DoctorProfile.Status.AVAILABLE, DoctorProfile.Status.UNAVAILABLE):
        raise Http404()
    was_available = doctor.status == DoctorProfile.Status.AVAILABLE
    doctor.status = status
    doctor.accepting_patients = status == DoctorProfile.Status.AVAILABLE
    if status == DoctorProfile.Status.AVAILABLE:
        doctor.expected_availability = ''
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
    """Doctors can call the next patient, then complete that consultation."""
    doctor = doctor_for(request.user)
    action = request.POST.get('action')
    if action not in ('call', 'complete'):
        raise Http404()

    with transaction.atomic():
        # Use the same doctor lock as queue joins so compaction cannot race
        # with another student receiving a new token.
        doctor = DoctorProfile.objects.select_for_update().get(pk=doctor.pk)
        entry = get_object_or_404(
            ConsultationQueue.objects.select_for_update(),
            pk=entry_id,
            doctor=doctor,
            status__in=['waiting', 'called'],
        )
        if action == 'call':
            next_waiting = ConsultationQueue.objects.select_for_update().filter(
                doctor=doctor, status=ConsultationQueue.Status.WAITING
            ).order_by('token_number').first()
            already_called = ConsultationQueue.objects.filter(
                doctor=doctor, status=ConsultationQueue.Status.CALLED
            ).exists()
            if entry != next_waiting or already_called:
                messages.error(request, 'Please complete the current consultation before calling the next patient.')
                return redirect('phc:doctor_dashboard')
            entry.status = ConsultationQueue.Status.CALLED
            entry.called_at = timezone.now()
            entry.save(update_fields=['status', 'called_at'])
            PHCNotification.objects.create(
                student=entry.student,
                message=f'It is your turn to see {doctor} at the PHC.',
            )
            log(request.user, 'Called next patient', entry.pk)
            messages.success(request, f'Called {entry.student.get_full_name() or entry.student.username}.')
        else:
            if entry.status != ConsultationQueue.Status.CALLED:
                messages.error(request, 'Only a called appointment can be completed.')
                return redirect('phc:doctor_dashboard')
            completed_token = entry.token_number
            entry.status = ConsultationQueue.Status.COMPLETED
            entry.completed_at = timezone.now()
            # Release this token before compacting the remaining active queue.
            entry.token_number = None
            entry.save(update_fields=['status', 'completed_at', 'token_number'])
            remaining_entries = ConsultationQueue.objects.filter(
                doctor=doctor,
                status__in=['waiting', 'called'],
                token_number__gt=completed_token,
            ).order_by('token_number')
            # Update in ascending order to preserve the database unique token
            # constraint at every step (2→1, then 3→2, and so on).
            for remaining in remaining_entries:
                remaining.token_number -= 1
                remaining.save(update_fields=['token_number'])
            log(request.user, 'Completed consultation', entry.pk)
            messages.success(request, 'Consultation marked completed.')
    return redirect('phc:doctor_dashboard')

@user_passes_test(is_admin)
def admin_dashboard(request):
    doctors = DoctorProfile.objects.all().select_related('user')
    return render(request, 'phc/admin_dashboard.html', {'doctors': doctors, 'available': doctors.filter(status='available').count(), 'waiting': ConsultationQueue.objects.filter(status='waiting').count(), 'subscriptions': DoctorNotificationSubscription.objects.filter(active=True).count(), 'settings': PHCSettings.get_solo()})


@user_passes_test(is_admin)
def admin_doctors(request):
    return render(request, 'phc/admin_doctors.html', {'doctors': DoctorProfile.objects.select_related('user').all()})


@user_passes_test(is_admin)
def admin_doctor_edit(request, doctor_id=None):
    doctor = get_object_or_404(DoctorProfile, pk=doctor_id) if doctor_id else None
    form = DoctorProfileForm(request.POST or None, instance=doctor)
    if request.method == 'POST' and form.is_valid():
        doctor = form.save()
        log(request.user, 'Created doctor profile' if doctor_id is None else 'Updated doctor profile', doctor.pk)
        messages.success(request, 'Doctor profile saved.')
        return redirect('phc:admin_doctors')
    return render(request, 'phc/admin_form.html', {'form': form, 'title': 'Add doctor' if doctor is None else f'Edit {doctor}', 'cancel_url': 'phc:admin_doctors'})


@user_passes_test(is_admin)
def admin_schedules(request):
    form = DoctorScheduleForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        schedule = form.save()
        log(request.user, 'Created doctor schedule', schedule.pk)
        messages.success(request, 'Consultation time added.')
        return redirect('phc:admin_schedules')
    return render(request, 'phc/admin_schedules.html', {'form': form, 'schedules': DoctorProfile.objects.prefetch_related('schedules').all()})


@user_passes_test(is_admin)
def admin_announcements(request):
    form = AnnouncementForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        announcement = form.save(commit=False)
        announcement.created_by = request.user
        announcement.save()
        log(request.user, 'Published PHC announcement', announcement.pk)
        messages.success(request, 'Announcement published.')
        return redirect('phc:admin_announcements')
    return render(request, 'phc/admin_announcements.html', {'form': form, 'announcements': PHCAnnouncement.objects.all()})


@user_passes_test(is_admin)
def admin_settings(request):
    settings = PHCSettings.get_solo()
    form = PHCSettingsForm(request.POST or None, instance=settings)
    if request.method == 'POST' and form.is_valid():
        form.save()
        log(request.user, 'Updated PHC emergency and contact information')
        messages.success(request, 'PHC settings saved.')
        return redirect('phc:admin_settings')
    return render(request, 'phc/admin_form.html', {'form': form, 'title': 'PHC contact and emergency information', 'cancel_url': 'phc:admin_dashboard'})


@user_passes_test(is_admin)
def admin_queue(request):
    entries = ConsultationQueue.objects.filter(status__in=['waiting', 'called']).select_related('student', 'doctor')
    return render(request, 'phc/admin_queue.html', {'entries': entries})


@user_passes_test(is_admin)
@require_POST
def admin_queue_remove(request, entry_id):
    entry = get_object_or_404(ConsultationQueue, pk=entry_id, status__in=['waiting', 'called'])
    entry.status = ConsultationQueue.Status.CANCELLED
    entry.completed_at = timezone.now()
    entry.save(update_fields=['status', 'completed_at'])
    log(request.user, 'Admin cancelled queue entry', entry.pk)
    messages.info(request, 'Queue entry removed.')
    return redirect('phc:admin_queue')
