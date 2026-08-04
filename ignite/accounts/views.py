from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect


@login_required
def post_login_redirect(request):
    role = request.user.role
    if role == request.user.Role.STUDENT:
        return redirect('/')       # swap for student dashboard later
    elif role == request.user.Role.FACULTY:
        return redirect('/')       # swap for faculty dashboard later
    return redirect('/')