from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render

from .forms import FinderDetailsForm, FoundReportForm, LostReportForm
from .matching import find_lost_matches, image_similarity
from .models import FoundClaim, FoundItem, LostAndFoundNotification, LostItem


def _reporter_initial(user):
    return {"reporter_name": user.get_full_name() or user.username}


@login_required
def lost_page(request):
    """Create a lost report and search open lost reports by item or location."""
    query = request.GET.get("q", "").strip()
    reports = LostItem.objects.filter(status=LostItem.Status.OPEN)
    if query:
        reports = reports.filter(
            Q(item_name__icontains=query)
            | Q(lost_place__icontains=query)
            | Q(reporter_name__icontains=query)
        )

    if request.method == "POST":
        form = LostReportForm(request.POST, request.FILES)
        if form.is_valid():
            lost_item = form.save(commit=False)
            lost_item.owner = request.user
            lost_item.save()
            messages.success(request, "Your lost-item report is live. We will notify your account when someone shares finder details.")
            return redirect("lost_and_found:lost")
    else:
        form = LostReportForm(initial=_reporter_initial(request.user))

    notification_queryset = LostAndFoundNotification.objects.filter(recipient=request.user).select_related("lost_item", "claim")
    notification_queryset.filter(is_read=False).update(is_read=True)
    notifications = notification_queryset[:8]

    return render(
        request,
        "lost_and_found/lost_page.html",
        {
            "form": form,
            "reports": reports[:40],
            "query": query,
            "notifications": notifications,
        },
    )


@login_required
def found_page(request):
    """Upload a found photo and run the local visual match against lost photos."""
    if request.method == "POST":
        form = FoundReportForm(request.POST, request.FILES)
        if form.is_valid():
            found_item = form.save(commit=False)
            found_item.reporter = request.user
            found_item.save()
            return redirect("lost_and_found:found_matches", found_item_id=found_item.id)
    else:
        form = FoundReportForm(initial=_reporter_initial(request.user))
    return render(request, "lost_and_found/found_page.html", {"form": form})


@login_required
def found_matches(request, found_item_id):
    """Show only likely photo matches for a newly submitted found report."""
    found_item = get_object_or_404(FoundItem, pk=found_item_id)
    if found_item.reporter_id and found_item.reporter_id != request.user.id:
        raise PermissionDenied("Only the person who uploaded this item can view its matches.")

    matches = find_lost_matches(
        found_item.photo,
        LostItem.objects.filter(status=LostItem.Status.OPEN).select_related("owner"),
    )
    return render(
        request,
        "lost_and_found/found_matches.html",
        {"found_item": found_item, "matches": matches},
    )


@login_required
def claim_lost_item(request, lost_item_id, found_item_id=None):
    """Collect finder details and notify the account that created the report."""
    lost_item = get_object_or_404(LostItem, pk=lost_item_id)
    found_item = None
    similarity_score = 100

    if found_item_id is not None:
        found_item = get_object_or_404(FoundItem, pk=found_item_id)
        if found_item.reporter_id and found_item.reporter_id != request.user.id:
            raise PermissionDenied("Only the person who uploaded this item can confirm this match.")
        try:
            similarity_score = image_similarity(found_item.photo, lost_item.photo)
        except (OSError, ValueError):
            messages.error(request, "We could not re-check these photos. Please try the found upload again.")
            return redirect("lost_and_found:found")

    if request.method == "POST":
        form = FinderDetailsForm(request.POST)
        if form.is_valid():
            claim, created = FoundClaim.objects.get_or_create(
                lost_item=lost_item,
                found_item=found_item,
                defaults={
                    "finder_name": form.cleaned_data["finder_name"],
                    "finder_contact": form.cleaned_data["finder_contact"],
                    "similarity_score": similarity_score,
                },
            )
            if not created:
                messages.info(request, "Finder details for this match have already been submitted.")
                return redirect("lost_and_found:lost")

            lost_item.status = LostItem.Status.CONTACT_PENDING
            lost_item.save(update_fields=["status"])
            if lost_item.owner_id:
                LostAndFoundNotification.objects.create(
                    recipient=lost_item.owner,
                    lost_item=lost_item,
                    claim=claim,
                    title=f"Someone may have found your {lost_item.item_name}",
                    message=(
                        f"{claim.finder_name} shared their contact details: "
                        f"{claim.finder_contact}. Please contact them to confirm the item."
                    ),
                )
            messages.success(request, "Your details have been sent to the person who reported this item lost.")
            return redirect("lost_and_found:lost")
    else:
        form = FinderDetailsForm(initial={"finder_name": request.user.get_full_name() or request.user.username})

    return render(
        request,
        "lost_and_found/finder_details.html",
        {
            "form": form,
            "lost_item": lost_item,
            "found_item": found_item,
            "similarity_score": similarity_score,
        },
    )
