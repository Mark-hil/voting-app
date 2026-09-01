from django.test import TestCase, Client
from django.urls import reverse
from accounts.models import CustomUser
from accounts.forms import LoginForm, RegisterForm


class AccountsModelTests(TestCase):
    def test_custom_user_creation(self):
        user = CustomUser.objects.create_user(
            username='voter1@test.com',
            email='voter1@test.com',
            password='password123',
            role='voter',
            unique_code='VOTER001'
        )
        self.assertEqual(user.role, 'voter')
        self.assertFalse(user.is_admin_user())
        self.assertFalse(user.is_system_admin())
        self.assertFalse(user.can_manage_elections())
        self.assertFalse(user.can_manage_voters())
        self.assertFalse(user.can_view_analytics())
        self.assertFalse(user.can_access_maintenance())
        self.assertEqual(user.get_role_badge_class(), 'voter')
        self.assertEqual(user.unique_code, 'VOTER001')

    def test_admin_user(self):
        admin = CustomUser.objects.create_superuser(
            username='admin@test.com',
            email='admin@test.com',
            password='adminpassword',
            role='admin'
        )
        self.assertTrue(admin.is_admin_user())
        self.assertTrue(admin.is_system_admin())
        self.assertTrue(admin.can_manage_elections())
        self.assertTrue(admin.can_manage_voters())
        self.assertTrue(admin.can_view_analytics())
        self.assertTrue(admin.can_access_maintenance())
        self.assertEqual(admin.get_role_badge_class(), 'admin')

    def test_electoral_commissioner_user(self):
        officer = CustomUser.objects.create_user(
            username='officer@test.com',
            email='officer@test.com',
            password='officerpassword',
            role='officer',
            is_staff=True
        )
        self.assertTrue(officer.is_admin_user())
        self.assertFalse(officer.is_system_admin())
        self.assertTrue(officer.can_manage_elections())
        self.assertFalse(officer.can_manage_voters())
        self.assertTrue(officer.can_view_analytics())
        self.assertFalse(officer.can_access_maintenance())
        self.assertEqual(officer.get_role_badge_class(), 'officer')

    def test_voter_registrar_user(self):
        registrar = CustomUser.objects.create_user(
            username='registrar@test.com',
            email='registrar@test.com',
            password='registrarpassword',
            role='registrar',
            is_staff=True
        )
        self.assertTrue(registrar.is_admin_user())
        self.assertFalse(registrar.is_system_admin())
        self.assertFalse(registrar.can_manage_elections())
        self.assertTrue(registrar.can_manage_voters())
        self.assertFalse(registrar.can_view_analytics())
        self.assertFalse(registrar.can_access_maintenance())
        self.assertEqual(registrar.get_role_badge_class(), 'registrar')

    def test_election_auditor_user(self):
        auditor = CustomUser.objects.create_user(
            username='auditor@test.com',
            email='auditor@test.com',
            password='auditorpassword',
            role='auditor',
            is_staff=True
        )
        self.assertTrue(auditor.is_admin_user())
        self.assertFalse(auditor.is_system_admin())
        self.assertFalse(auditor.can_manage_elections())
        self.assertFalse(auditor.can_manage_voters())
        self.assertTrue(auditor.can_view_analytics())
        self.assertFalse(auditor.can_access_maintenance())
        self.assertEqual(auditor.get_role_badge_class(), 'auditor')



class LoginFormTests(TestCase):
    def setUp(self):
        self.admin = CustomUser.objects.create_superuser(
            username='admin@test.com',
            email='admin@test.com',
            password='adminpassword123',
            role='admin'
        )
        self.voter_code = CustomUser.objects.create_user(
            username='voter_code',
            email='voter_code@test.com',
            role='voter',
            unique_code='CODE1234'
        )
        self.voter_pw = CustomUser.objects.create_user(
            username='voter_pw@test.com',
            email='voter_pw@test.com',
            password='voterpassword123',
            role='voter'
        )

    def test_admin_login_with_password(self):
        form = LoginForm(data={'username': 'admin@test.com', 'unique_code': 'adminpassword123'})
        self.assertTrue(form.is_valid())
        self.assertEqual(form.user, self.admin)

    def test_voter_login_with_unique_code(self):
        form = LoginForm(data={'username': 'voter_code', 'unique_code': 'code1234'})
        self.assertTrue(form.is_valid())
        self.assertEqual(form.user, self.voter_code)

    def test_voter_login_with_password(self):
        form = LoginForm(data={'username': 'voter_pw@test.com', 'unique_code': 'voterpassword123'})
        self.assertTrue(form.is_valid())
        self.assertEqual(form.user, self.voter_pw)

    def test_invalid_login(self):
        form = LoginForm(data={'username': 'voter_code', 'unique_code': 'WRONGCODE'})
        self.assertFalse(form.is_valid())


class RegisterFormTests(TestCase):
    def test_register_creates_user_with_unique_code(self):
        form_data = {
            'first_name': 'New',
            'last_name': 'Voter',
            'email': 'newvoter@test.com',
            'password1': 'StrongPass123!@#',
            'password2': 'StrongPass123!@#',
        }
        form = RegisterForm(data=form_data)
        self.assertTrue(form.is_valid(), form.errors)
        user = form.save()
        self.assertEqual(user.email, 'newvoter@test.com')
        self.assertEqual(user.role, 'voter')
        self.assertTrue(bool(user.unique_code))
        self.assertTrue(user.check_password('StrongPass123!@#'))
