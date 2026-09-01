import uuid
from datetime import timedelta
from django.test import TestCase, Client
from django.utils import timezone
from django.urls import reverse
from accounts.models import CustomUser
from elections.models import Election, Candidate, Vote


class ElectionsModelAndViewsTests(TestCase):
    def setUp(self):
        self.now = timezone.now()
        self.admin = CustomUser.objects.create_superuser(
            username='admin@test.com',
            email='admin@test.com',
            password='adminpassword123',
            role='admin'
        )
        self.voter = CustomUser.objects.create_user(
            username='voter@test.com',
            email='voter@test.com',
            password='voterpassword123',
            role='voter',
            unique_code='VOTER001'
        )
        self.election_active = Election.objects.create(
            title='President Election',
            position='President',
            status='active',
            voting_type='single',
            start_date=self.now - timedelta(hours=1),
            end_date=self.now + timedelta(hours=2),
            created_by=self.admin,
            show_results=True
        )
        self.election_active.eligible_voters.add(self.voter)

        self.candidate1 = Candidate.objects.create(
            election=self.election_active,
            name='Candidate Alice',
            order=1
        )
        self.candidate2 = Candidate.objects.create(
            election=self.election_active,
            name='Candidate Bob',
            order=2
        )

        self.client = Client()

    def test_election_properties(self):
        self.assertTrue(self.election_active.is_active)
        self.assertFalse(self.election_active.has_ended)
        self.assertEqual(self.election_active.total_votes, 0)
        self.assertEqual(self.election_active.total_eligible, 1)

    def test_ballot_and_voting_flow(self):
        self.client.login(username='voter@test.com', password='voterpassword123')

        # Load ballot page
        response = self.client.get(reverse('elections:ballot', args=[self.election_active.id]))
        self.assertEqual(response.status_code, 200)

        # Cast vote
        post_response = self.client.post(
            reverse('elections:ballot', args=[self.election_active.id]),
            {'candidate': self.candidate1.id}
        )
        self.assertEqual(post_response.status_code, 302)
        self.assertEqual(Vote.objects.count(), 1)
        vote = Vote.objects.first()
        self.assertEqual(vote.candidate, self.candidate1)
        self.assertTrue(bool(vote.reference_id))

        # Attempt duplicate vote
        dup_response = self.client.post(
            reverse('elections:ballot', args=[self.election_active.id]),
            {'candidate': self.candidate2.id}
        )
        self.assertEqual(Vote.objects.count(), 1)

    def test_results_access_for_voter_with_show_results_true(self):
        self.client.login(username='voter@test.com', password='voterpassword123')
        response = self.client.get(reverse('elections:results', args=[self.election_active.id]))
        self.assertEqual(response.status_code, 200)

        # CSV export
        csv_response = self.client.get(reverse('elections:results', args=[self.election_active.id]) + '?export=csv')
        self.assertEqual(csv_response.status_code, 200)
        self.assertEqual(csv_response['Content-Type'], 'text/csv')

    def test_results_access_for_voter_with_show_results_false(self):
        self.election_active.show_results = False
        self.election_active.save()

        self.client.login(username='voter@test.com', password='voterpassword123')
        response = self.client.get(reverse('elections:results', args=[self.election_active.id]))
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse('elections:dashboard'))
