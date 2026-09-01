import uuid
from django.db import models
from django.utils import timezone
from accounts.models import CustomUser


class Election(models.Model):
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('active', 'Active'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ]
    VOTING_TYPE_CHOICES = [
        ('single', 'Single Choice'),
        ('multiple', 'Multiple Choice'),
        ('ranked', 'Ranked Choice'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    position = models.CharField(max_length=200)
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default='draft')
    voting_type = models.CharField(max_length=10, choices=VOTING_TYPE_CHOICES, default='single')
    start_date = models.DateTimeField()
    end_date = models.DateTimeField()
    created_by = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True, related_name='created_elections')
    eligible_voters = models.ManyToManyField(CustomUser, related_name='eligible_elections', blank=True)
    show_results = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.title} ({self.position})"

    @property
    def is_active(self):
        now = timezone.now()
        return self.status == 'active' and self.start_date <= now <= self.end_date

    @property
    def has_ended(self):
        return timezone.now() > self.end_date

    @property
    def total_votes(self):
        return self.votes.count()

    @property
    def total_eligible(self):
        return self.eligible_voters.count()

    @property
    def participation_rate(self):
        total = self.total_eligible
        if total == 0:
            return 0
        return round((self.total_votes / total) * 100, 1)

    @property
    def uncast_votes(self):
        """Returns the number of eligible voters who have not yet voted in this election."""
        total = self.total_eligible
        return max(0, total - self.total_votes)

    @property
    def uncast_rate(self):
        """Returns the percentage of uncast ballots in this election."""
        total = self.total_eligible
        if total == 0:
            return 0
        return round((self.uncast_votes / total) * 100, 1)


class Candidate(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    election = models.ForeignKey(Election, on_delete=models.CASCADE, related_name='candidates')
    name = models.CharField(max_length=200)
    bio = models.TextField(blank=True)
    photo = models.ImageField(upload_to='voter_candidate/', blank=True, null=True)
    order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['order', 'name']

    def __str__(self):
        return f"{self.name} — {self.election.position}"

    @property
    def vote_count(self):
        return self.votes.count()

    @property
    def vote_percentage(self):
        total = self.election.total_votes
        if total == 0:
            return 0
        return round((self.vote_count / total) * 100, 1)


class Vote(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    election = models.ForeignKey(Election, on_delete=models.CASCADE, related_name='votes')
    voter = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='votes')
    candidate = models.ForeignKey(Candidate, on_delete=models.CASCADE, related_name='votes')
    reference_id = models.CharField(max_length=20, unique=True)
    cast_at = models.DateTimeField(auto_now_add=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)

    class Meta:
        unique_together = ('election', 'voter')
        ordering = ['-cast_at']

    def __str__(self):
        return f"Vote #{self.reference_id} in {self.election.title}"

    def save(self, *args, **kwargs):
        if not self.reference_id:
            import random, string
            self.reference_id = ''.join(random.choices(string.ascii_uppercase + string.digits, k=12))
        super().save(*args, **kwargs)
