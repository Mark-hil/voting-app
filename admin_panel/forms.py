from datetime import datetime
from django import forms
from django.utils import timezone
from django.core.validators import FileExtensionValidator
from elections.models import Election, Candidate
from accounts.models import CustomUser


class ElectionForm(forms.ModelForm):
    start_date = forms.DateField(
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-input'}),
    )
    TIME_CHOICES = [
        ('08:00', '8:00 AM'),
        ('08:30', '8:30 AM'),
        ('09:00', '9:00 AM'),
        ('09:30', '9:30 AM'),
        ('10:00', '10:00 AM'),
        ('10:30', '10:30 AM'),
        ('11:00', '11:00 AM'),
        ('11:30', '11:30 AM'),
        ('12:00', '12:00 PM'),
        ('12:30', '12:30 PM'),
        ('13:00', '1:00 PM'),
        ('13:30', '1:30 PM'),
        ('14:00', '2:00 PM'),
        ('14:30', '2:30 PM'),
        ('15:00', '3:00 PM'),
        ('15:30', '3:30 PM'),
        ('16:00', '4:00 PM'),
        ('16:30', '4:30 PM'),
        ('17:00', '5:00 PM'),
        ('17:30', '5:30 PM'),
        ('18:00', '6:00 PM'),
        ('18:30', '6:30 PM'),
        ('19:00', '7:00 PM'),
        ('19:30', '7:30 PM'),
        ('20:00', '8:00 PM'),
        ('20:30', '8:30 PM'),
        ('21:00', '9:00 PM'),
        ('21:30', '9:30 PM'),
    ]

    start_time = forms.ChoiceField(
        choices=TIME_CHOICES,
        widget=forms.Select(attrs={'class': 'form-input'}),
    )
    end_date = forms.DateField(
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-input'}),
    )
    end_time = forms.ChoiceField(
        choices=TIME_CHOICES,
        widget=forms.Select(attrs={'class': 'form-input'}),
    )

    class Meta:
        model = Election
        fields = ['title', 'position', 'description', 'voting_type', 'start_date', 'end_date', 'eligible_voters', 'show_results']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'e.g. 2024 Board Election'}),
            'position': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'e.g. President, Secretary'}),
            'description': forms.Textarea(attrs={'class': 'form-input', 'rows': 3}),
            'voting_type': forms.Select(attrs={'class': 'form-input'}),
            'eligible_voters': forms.SelectMultiple(attrs={'class': 'form-input', 'size': 6}),
            'show_results': forms.CheckboxInput(attrs={'class': 'form-checkbox'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['eligible_voters'].queryset = CustomUser.objects.filter(role='voter')
        self.fields['eligible_voters'].required = False
        
        self.fields['start_date'].required = True
        self.fields['end_date'].required = True

        if self.instance and self.instance.pk:
            if self.instance.start_date:
                self.initial['start_date'] = self.instance.start_date.strftime('%Y-%m-%d')
                time_str = self.instance.start_date.strftime('%H:%M')
                choice_keys = [c[0] for c in self.TIME_CHOICES]
                if time_str not in choice_keys:
                    self.fields['start_time'].choices = sorted(self.TIME_CHOICES + [(time_str, time_str)], key=lambda x: x[0])
                self.initial['start_time'] = time_str
            if self.instance.end_date:
                self.initial['end_date'] = self.instance.end_date.strftime('%Y-%m-%d')
                time_str = self.instance.end_date.strftime('%H:%M')
                choice_keys = [c[0] for c in self.TIME_CHOICES]
                if time_str not in choice_keys:
                    self.fields['end_time'].choices = sorted(self.TIME_CHOICES + [(time_str, time_str)], key=lambda x: x[0])
                self.initial['end_time'] = time_str

    def clean(self):
        cleaned_data = super().clean()
        start_date = cleaned_data.get('start_date')
        start_time = cleaned_data.get('start_time')
        end_date = cleaned_data.get('end_date')
        end_time = cleaned_data.get('end_time')

        if start_date and start_time:
            time_obj = datetime.strptime(start_time, '%H:%M').time()
            naive_start = datetime.combine(start_date, time_obj)
            cleaned_data['start_date'] = timezone.make_aware(naive_start, timezone.utc)

        if end_date and end_time:
            time_obj = datetime.strptime(end_time, '%H:%M').time()
            naive_end = datetime.combine(end_date, time_obj)
            cleaned_data['end_date'] = timezone.make_aware(naive_end, timezone.utc)

        start = cleaned_data.get('start_date')
        end = cleaned_data.get('end_date')
        if start and end and end <= start:
            raise forms.ValidationError('End date must be after start date.')
        return cleaned_data



class CandidateForm(forms.ModelForm):
    class Meta:
        model = Candidate
        fields = ['name', 'bio', 'photo', 'order']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Candidate full name'}),
            'bio': forms.Textarea(attrs={'class': 'form-input', 'rows': 2, 'placeholder': 'Brief bio or qualifications'}),
            'order': forms.NumberInput(attrs={'class': 'form-input', 'min': 0}),
        }


class VoterInviteForm(forms.Form):
    first_name = forms.CharField(
        max_length=50,
        widget=forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'First Name'})
    )
    last_name = forms.CharField(
        max_length=50,
        widget=forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Last Name'})
    )
    email = forms.EmailField(
        widget=forms.EmailInput(attrs={'class': 'form-input', 'placeholder': 'voter@example.com'})
    )
    phone = forms.CharField(
        max_length=20,
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'e.g. 024XXXXXXX or +233...'})
    )
    send_sms = forms.BooleanField(
        required=False,
        initial=True,
        label="Send Login Code via SMS immediately",
        widget=forms.CheckboxInput(attrs={'class': 'form-checkbox'})
    )


class VoterImportForm(forms.Form):
    csv_file = forms.FileField(
        label='CSV File',
        help_text='Upload a CSV file with columns: name, index, phone (optional) OR "STUDENT\'S NAME", "INDEX NUMBER", "PHONE NUMBER"',
        widget=forms.FileInput(attrs={'class': 'form-input', 'accept': '.csv'}),
        validators=[
            FileExtensionValidator(allowed_extensions=['csv'])
        ]
    )
    send_sms = forms.BooleanField(
        required=False,
        initial=False,
        label="Send unique login codes via SMS to imported voters with valid phone numbers",
        widget=forms.CheckboxInput(attrs={'class': 'form-checkbox'})
    )
