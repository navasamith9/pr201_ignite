from allauth.account.adapter import DefaultAccountAdapter
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from allauth.core.exceptions import ImmediateHttpResponse
from django.shortcuts import redirect
from django.contrib import messages

ALLOWED_DOMAIN = "iiitdmj.ac.in"   # change to your real domain
FACULTY_EMAILS = {
    "pkhanna@iiitdmj.ac.in",
    "sraban@iiitdmj.ac.in",
    "mkbajpai@iiitdmj.ac.in",
    "ayan@iiitdmj.ac.in",
    "ranjeet.kr@iiitdmj.ac.in",
    "neelam.dayal@iiitdmj.ac.in",
    "durgesh@iiitdmj.ac.in",
}


class InstituteAccountAdapter(DefaultAccountAdapter):
    def is_open_for_signup(self, request):
        return True  # signup happens only via Google, so this is fine


class InstituteSocialAccountAdapter(DefaultSocialAccountAdapter):
    def pre_social_login(self, request, sociallogin):
        email = sociallogin.account.extra_data.get('email', '')
        if not email.endswith(f'@{ALLOWED_DOMAIN}'):
            messages.error(request, "Only institute email addresses can sign in.")
            raise ImmediateHttpResponse(redirect('/'))

    def save_user(self, request, sociallogin, form=None):
        user = super().save_user(request, sociallogin, form)
        # Placeholder role logic — you'll likely replace this with
        # a lookup against a roster, or a naming convention in the email.
        if user.is_superuser or user.is_staff:
            user.role = user.Role.ADMIN
        elif user.email.lower() in FACULTY_EMAILS:
            user.role = user.Role.FACULTY
        else:
            user.role = user.Role.STUDENT
        user.save()
        return user

