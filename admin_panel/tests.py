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

    def test_electoral_commissioner_permissions(self):
        commissioner = CustomUser.objects.create_user(
            username='comm@test.com',
            email='comm@test.com',
            password='commpassword123',
            role='officer',
            is_staff=True
        )
        comm_client = Client()
        comm_client.login(username='comm@test.com', password='commpassword123')

        # Can manage elections & candidates
        manage_url = reverse('admin_panel:election_manage', args=[self.election.id])
        add_cand_resp = comm_client.post(manage_url, {
            'action': 'add_candidate',
            'name': 'Commissioner Candidate',
            'order': 1
        })
        self.assertEqual(add_cand_resp.status_code, 302)
        self.assertTrue(Candidate.objects.filter(name='Commissioner Candidate').exists())

        # Blocked from System Maintenance
        maint_resp = comm_client.get(reverse('admin_panel:system_maintenance'))
        self.assertEqual(maint_resp.status_code, 302)
        self.assertEqual(maint_resp.url, reverse('admin_panel:dashboard'))

        # Blocked from Staff Management
        staff_resp = comm_client.get(reverse('admin_panel:staff_list'))
        self.assertEqual(staff_resp.status_code, 302)
        self.assertEqual(staff_resp.url, reverse('admin_panel:dashboard'))

    def test_voter_registrar_permissions(self):
        registrar = CustomUser.objects.create_user(
            username='reg@test.com',
            email='reg@test.com',
            password='regpassword123',
            role='registrar',
            is_staff=True
        )
        reg_client = Client()
        reg_client.login(username='reg@test.com', password='regpassword123')

        # Can invite voter
        invite_resp = reg_client.post(reverse('admin_panel:voter_invite'), {
            'first_name': 'Reg',
            'last_name': 'Voter',
            'email': 'regvoter@test.com'
        })
        self.assertEqual(invite_resp.status_code, 302)
        self.assertTrue(CustomUser.objects.filter(email='regvoter@test.com').exists())

        # Blocked from creating election
        create_resp = reg_client.post(reverse('admin_panel:election_create'), {
            'title': 'Unauthorized Election',
            'position': 'President'
        })
        self.assertEqual(create_resp.status_code, 302)
        self.assertEqual(create_resp.url, reverse('admin_panel:dashboard'))
        self.assertFalse(Election.objects.filter(title='Unauthorized Election').exists())

        # Registrar hitting overview dashboard is automatically routed to voter list
        dash_resp = reg_client.get(reverse('admin_panel:dashboard'))
        self.assertEqual(dash_resp.status_code, 302)
        self.assertEqual(dash_resp.url, reverse('admin_panel:voter_list'))

        # Registrar blocked from comprehensive analytics
        comp_resp = reg_client.get(reverse('admin_panel:comprehensive_dashboard'))
        self.assertEqual(comp_resp.status_code, 302)
        self.assertEqual(comp_resp.url, reverse('admin_panel:voter_list'))

        # Registrar blocked from election results
        results_resp = reg_client.get(reverse('admin_panel:election_results', args=[self.election.id]))
        self.assertEqual(results_resp.status_code, 302)
        self.assertEqual(results_resp.url, reverse('admin_panel:voter_list'))


    def test_election_auditor_permissions(self):
        auditor = CustomUser.objects.create_user(
            username='aud@test.com',
            email='aud@test.com',
            password='audpassword123',
            role='auditor',
            is_staff=True
        )
        aud_client = Client()
        aud_client.login(username='aud@test.com', password='audpassword123')

        # Can view dashboards & export audit pack
        dash_resp = aud_client.get(reverse('admin_panel:dashboard'))
        self.assertEqual(dash_resp.status_code, 200)

        comp_resp = aud_client.get(reverse('admin_panel:comprehensive_dashboard'))
        self.assertEqual(comp_resp.status_code, 200)

        audit_pack_resp = aud_client.get(reverse('admin_panel:export_election_audit_pack', args=[self.election.id]))
        self.assertEqual(audit_pack_resp.status_code, 200)

        # Blocked from modifying elections or inviting voters
        invite_resp = aud_client.post(reverse('admin_panel:voter_invite'), {
            'first_name': 'Aud',
            'last_name': 'Voter',
            'email': 'audvoter@test.com'
        })
        self.assertEqual(invite_resp.status_code, 302)
        self.assertEqual(invite_resp.url, reverse('admin_panel:dashboard'))

    def test_staff_management_by_system_admin(self):
        staff_url = reverse('admin_panel:staff_list')
        get_resp = self.client.get(staff_url)
        self.assertEqual(get_resp.status_code, 200)
        self.assertTemplateUsed(get_resp, 'admin_panel/staff_list.html')

        # Add new staff member
        add_resp = self.client.post(staff_url, {
            'action': 'add_staff',
            'first_name': 'New',
            'last_name': 'Officer',
            'email': 'newofficer@test.com',
            'role': 'officer',
            'password': 'password123'
        })
        self.assertEqual(add_resp.status_code, 302)
        new_user = CustomUser.objects.get(email='newofficer@test.com')
        self.assertEqual(new_user.role, 'officer')

        # Update role
        update_resp = self.client.post(staff_url, {
            'action': 'update_role',
            'user_id': new_user.id,
            'role': 'auditor'
        })
        self.assertEqual(update_resp.status_code, 302)
        new_user.refresh_from_db()
        self.assertEqual(new_user.role, 'auditor')

        # Attempt self-demotion
        self_demote_resp = self.client.post(staff_url, {
            'action': 'update_role',
            'user_id': self.admin.id,
            'role': 'voter'
        })
        self.assertEqual(self_demote_resp.status_code, 302)
        self.admin.refresh_from_db()
        self.assertEqual(self.admin.role, 'admin')

    def test_voter_denied_admin_panel_access(self):
        voter_client = Client()
        voter_client.login(username='voter@test.com', password='voterpassword123')

        dash_resp = voter_client.get(reverse('admin_panel:dashboard'))
        self.assertEqual(dash_resp.status_code, 302)
        self.assertEqual(dash_resp.url, reverse('elections:dashboard'))

    def test_voter_invite_with_phone_and_sms(self):
        url = reverse('admin_panel:voter_invite')
        resp = self.client.post(url, {
            'first_name': 'Kwame',
            'last_name': 'Mensah',
            'email': 'kwame@test.com',
            'phone': '0241234567',
            'send_sms': 'on',
        })
        self.assertEqual(resp.status_code, 302)
        user = CustomUser.objects.get(email='kwame@test.com')
        self.assertEqual(user.phone, '0241234567')
        self.assertTrue(bool(user.unique_code))

    def test_voter_send_sms_endpoint(self):
        voter = CustomUser.objects.create_user(
            username='smsvoter@test.com',
            email='smsvoter@test.com',
            phone='0241234567',
            role='voter',
            unique_code='SMSVOTER1'
        )
        url = reverse('admin_panel:voter_send_sms', args=[voter.id])
        resp = self.client.post(url)
        self.assertEqual(resp.status_code, 302)
        self.assertRedirects(resp, reverse('admin_panel:voter_list'))

    def test_voter_bulk_send_sms_endpoint(self):
        url = reverse('admin_panel:voter_bulk_send_sms')
        resp = self.client.post(url, {'target': 'all'})
        self.assertEqual(resp.status_code, 302)
        self.assertRedirects(resp, reverse('admin_panel:voter_list'))

        resp_unvoted = self.client.post(url, {'target': 'unvoted'})
        self.assertEqual(resp_unvoted.status_code, 302)
        self.assertRedirects(resp_unvoted, reverse('admin_panel:voter_list'))

    def test_voter_import_with_phone_csv(self):
        csv_content = "name,index,phone\nAkosua Boateng,ENG2024001,0249876543\nKofi Annan,ENG2024002,0501122334"
        csv_file = SimpleUploadedFile("voters.csv", csv_content.encode('utf-8'), content_type="text/csv")
        
        url = reverse('admin_panel:voter_import')
        resp = self.client.post(url, {'csv_file': csv_file, 'send_sms': 'on'})
        self.assertEqual(resp.status_code, 302)

        user1 = CustomUser.objects.get(phone='0249876543')
        self.assertEqual(user1.first_name, 'Akosua')
        self.assertEqual(user1.role, 'voter')
        self.assertTrue(bool(user1.unique_code))

        user2 = CustomUser.objects.get(phone='0501122334')
        self.assertEqual(user2.first_name, 'Kofi')
        self.assertTrue(bool(user2.unique_code))



