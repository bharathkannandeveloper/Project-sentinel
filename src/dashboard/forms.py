from allauth.account.forms import SignupForm
from django import forms
from .models import UserProfile

class SentinelSignupForm(SignupForm):
    full_name = forms.CharField(max_length=255, label='Full Name', widget=forms.TextInput(attrs={'placeholder': 'Enter your full name'}))
    phone_number = forms.CharField(max_length=20, label='Phone Number', required=True, widget=forms.TextInput(attrs={'placeholder': '+91 99999 99999'}))

    def save(self, request):
        user = super(SentinelSignupForm, self).save(request)
        
        # Save profile data - profile is auto-created by signal, but we fetch it to update
        if hasattr(user, 'profile'):
            profile = user.profile
            profile.full_name = self.cleaned_data['full_name']
            profile.phone_number = self.cleaned_data['phone_number']
            profile.save()
        
        return user
