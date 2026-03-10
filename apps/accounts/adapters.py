"""
Custom allauth account adapter.
Saves the roles selected during signup into the user's UserProfile.
"""

from allauth.account.adapter import DefaultAccountAdapter


class AccountAdapter(DefaultAccountAdapter):
    def save_user(self, request, user, form, commit=True):
        """
        Called by allauth after the User instance is created.
        We use this hook to save M2M roles into the auto-created UserProfile.
        """
        user = super().save_user(request, user, form, commit=commit)

        # The UserProfile is already created by the post_save signal.
        # Now attach the roles the user chose on the signup form.
        roles = form.cleaned_data.get("roles", [])
        if roles:
            profile = getattr(user, "profile", None)
            if profile is not None:
                profile.roles.set(roles)

        return user
