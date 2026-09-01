import json
from datetime import timedelta
from django.test import TestCase, Client
from django.utils import timezone
from django.urls import reverse
from django.core.files.uploadedfile import SimpleUploadedFile
from accounts.models import CustomUser
from elections.models import Election, Candidate
from admin_panel.forms import ElectionForm


class AdminPanelTests(TestCase):
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
        self.election = Election.objects.create(
            title='Board Election',
            position='Chairman',
            status='active',
            voting_type='single',
            start_date=self.now - timedelta(days=1),
            end_date=self.now + timedelta(days=2),
            created_by=self.admin
        )
        self.client = Client()
        self.client.login(username='admin@test.com', password='adminpassword123')

    def test_extend_voting_time_get_and_post(self):
        url = reverse('admin_panel:extend_voting_time', args=[self.election.id])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'admin_panel/extend_voting.html')

        old_end_date = self.election.end_date
        post_response = self.client.post(url, {'days': '2', 'hours': '5'})
        self.assertEqual(post_response.status_code, 302)

        self.election.refresh_from_db()
        self.assertEqual(self.election.end_date, old_end_date + timedelta(days=2, hours=5))

    def test_election_form_initial_and_save(self):
        form = ElectionForm(instance=self.election)
        self.assertEqual(form.initial['start_date'], self.election.start_date.strftime('%Y-%m-%d'))
        self.assertEqual(form.initial['start_time'], self.election.start_date.strftime('%H:%M'))
        self.assertEqual(form.initial['end_date'], self.election.end_date.strftime('%Y-%m-%d'))
        self.assertEqual(form.initial['end_time'], self.election.end_date.strftime('%H:%M'))

    def test_voter_invite_generates_code(self):
        url = reverse('admin_panel:voter_invite')
        response = self.client.post(url, {
            'first_name': 'Invited',
            'last_name': 'User',
            'email': 'invited@test.com'
        })
        self.assertEqual(response.status_code, 302)
        invited_user = CustomUser.objects.get(email='invited@test.com')
        self.assertTrue(bool(invited_user.unique_code))
        self.assertEqual(invited_user.role, 'voter')

    def test_voter_import_csv(self):
        url = reverse('admin_panel:voter_import')
        csv_content = b"STUDENT'S NAME,INDEX NUMBER\nJohn Smith,NMCSMRGN230001\nJane Doe,NMCSMRGN230002\n"
        csv_file = SimpleUploadedFile("test.csv", csv_content, content_type="text/csv")
        response = self.client.post(url, {'csv_file': csv_file})
        self.assertEqual(response.status_code, 302)

        imported_voters = CustomUser.objects.filter(role='voter', username__icontains='nmcsmrgn')
        self.assertEqual(imported_voters.count(), 2)
        for voter in imported_voters:
            self.assertTrue(bool(voter.unique_code))

    def test_export_election_audit_pack_zip(self):
        import zipfile
        from io import BytesIO
        from elections.models import Vote

        candidate = Candidate.objects.create(election=self.election, name='Candidate A', order=1)
        self.election.eligible_voters.add(self.voter)
        Vote.objects.create(election=self.election, voter=self.voter, candidate=candidate)

        url = reverse('admin_panel:export_election_audit_pack', args=[self.election.id])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/zip')

        # Verify ZIP contains all 4 audit components
        zip_file = zipfile.ZipFile(BytesIO(response.content))
        file_list = zip_file.namelist()
        self.assertIn('official_results.csv', file_list)
        self.assertIn('voter_turnout.csv', file_list)
        self.assertIn('ballot_receipts_audit.csv', file_list)
        self.assertIn('election_summary.json', file_list)

        summary_content = json.loads(zip_file.read('election_summary.json').decode('utf-8'))
        self.assertEqual(summary_content['title'], 'Board Election')
        self.assertEqual(summary_content['total_votes_cast'], 1)

    def test_reset_voter_codes(self):
        url = reverse('admin_panel:reset_voter_codes')

        # Test clear
        response = self.client.post(url, {'reset_type': 'clear', 'target': 'all'})
        self.assertEqual(response.status_code, 302)
        self.voter.refresh_from_db()
        self.assertIsNone(self.voter.unique_code)

        # Test regenerate
        response = self.client.post(url, {'reset_type': 'regenerate', 'target': 'all'})
        self.assertEqual(response.status_code, 302)
        self.voter.refresh_from_db()
        self.assertTrue(bool(self.voter.unique_code))

    def test_election_manage_safeguard_when_completed(self):
        self.election.status = 'completed'
        self.election.save()

        url = reverse('admin_panel:election_manage', args=[self.election.id])
        # Attempt to add candidate when completed
        response = self.client.post(url, {
            'action': 'add_candidate',
            'name': 'Late Candidate',
            'order': 2
        })
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Candidate.objects.filter(name='Late Candidate').exists())

    def test_system_maintenance_views_and_wipe(self):
        url = reverse('admin_panel:system_maintenance')
        
        # Test GET view
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'admin_panel/system_maintenance.html')

        # Test Backup export
        backup_response = self.client.post(url, {'action': 'export_backup'})
        self.assertEqual(backup_response.status_code, 200)
        self.assertEqual(backup_response['Content-Type'], 'application/json')

        # Test Wipe confirmation failure
        fail_response = self.client.post(url, {'action': 'wipe_data', 'wipe_type': 'votes_only', 'confirmation': 'WRONG'})
        self.assertEqual(fail_response.status_code, 302)

        # Test Wipe Votes Only
        candidate = Candidate.objects.create(election=self.election, name='Candidate A')
        from elections.models import Vote
        Vote.objects.create(election=self.election, voter=self.voter, candidate=candidate)
        self.assertEqual(Vote.objects.count(), 1)

        wipe_response = self.client.post(url, {'action': 'wipe_data', 'wipe_type': 'votes_only', 'confirmation': 'RESET'})
        self.assertEqual(wipe_response.status_code, 302)
        self.assertEqual(Vote.objects.count(), 0)
        self.assertTrue(Election.objects.filter(id=self.election.id).exists())

    def test_post_election_cleanup_management_command(self):
        from django.core.management import call_command
        from io import StringIO
        out = StringIO()

        # Run dry run
        call_command('post_election_cleanup', '--dry-run', '--archive', str(self.election.id), '--clear-sessions', stdout=out)
        self.assertIn('[DRY RUN MODE ENABLED', out.getvalue())

        # Run live archive
        out_live = StringIO()
        call_command('post_election_cleanup', '--archive', str(self.election.id), '--reset-voter-codes', stdout=out_live)
        self.assertIn('archived successfully', out_live.getvalue())

        self.election.refresh_from_db()
        self.assertEqual(self.election.status, 'completed')
        self.assertTrue(self.election.show_results)

