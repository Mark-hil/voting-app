from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from accounts.models import CustomUser
from elections.models import Election, Candidate


class Command(BaseCommand):
    help = 'Seed demo data: admin, voters, and sample elections'

    def handle(self, *args, **kwargs):
        self.stdout.write('Seeding demo data with RBAC roles...')

        # 1. System Administrator
        if not CustomUser.objects.filter(email='admin@voteapp.com').exists():
            admin = CustomUser.objects.create_superuser(
                username='admin@voteapp.com',
                email='admin@voteapp.com',
                password='admin123',
                first_name='Admin',
                last_name='System',
                role='admin',
            )
            self.stdout.write(self.style.SUCCESS('✓ System Admin: admin@voteapp.com / admin123'))
        else:
            admin = CustomUser.objects.get(email='admin@voteapp.com')
            admin.role = 'admin'
            admin.save()
            self.stdout.write('  Admin already exists.')

        # 2. Electoral Commissioner
        commissioner, created = CustomUser.objects.get_or_create(
            email='commissioner@voteapp.com',
            defaults={
                'username': 'commissioner@voteapp.com',
                'first_name': 'Electoral',
                'last_name': 'Commissioner',
                'role': 'officer',
                'is_staff': True,
            }
        )
        commissioner.role = 'officer'
        commissioner.is_staff = True
        commissioner.set_password('officer123')
        commissioner.save()
        if created:
            self.stdout.write(self.style.SUCCESS('✓ Electoral Commissioner: commissioner@voteapp.com / officer123'))

        # 3. Voter Registrar
        registrar, created = CustomUser.objects.get_or_create(
            email='registrar@voteapp.com',
            defaults={
                'username': 'registrar@voteapp.com',
                'first_name': 'Voter',
                'last_name': 'Registrar',
                'role': 'registrar',
                'is_staff': True,
            }
        )
        registrar.role = 'registrar'
        registrar.is_staff = True
        registrar.set_password('registrar123')
        registrar.save()
        if created:
            self.stdout.write(self.style.SUCCESS('✓ Voter Registrar: registrar@voteapp.com / registrar123'))

        # 4. Election Auditor
        auditor, created = CustomUser.objects.get_or_create(
            email='auditor@voteapp.com',
            defaults={
                'username': 'auditor@voteapp.com',
                'first_name': 'Election',
                'last_name': 'Auditor',
                'role': 'auditor',
                'is_staff': True,
            }
        )
        auditor.role = 'auditor'
        auditor.is_staff = True
        auditor.set_password('auditor123')
        auditor.save()
        if created:
            self.stdout.write(self.style.SUCCESS('✓ Election Auditor: auditor@voteapp.com / auditor123'))

        # 5. Voters
        voters = []
        voter_data = [
            ('alice@example.com', 'Alice', 'Johnson', 'ALICE123'),
            ('bob@example.com', 'Bob', 'Smith', 'BOB12345'),
            ('carol@example.com', 'Carol', 'Williams', 'CAROL123'),
            ('dave@example.com', 'Dave', 'Brown', 'DAVE1234'),
        ]
        for email, first, last, code in voter_data:
            user, created = CustomUser.objects.get_or_create(
                email=email,
                defaults={
                    'username': email,
                    'first_name': first,
                    'last_name': last,
                    'role': 'voter',
                    'unique_code': code,
                }
            )
            user.set_password('voter123')
            if not user.unique_code:
                user.unique_code = code
            user.save()
            if created:
                self.stdout.write(self.style.SUCCESS(f'✓ Voter: {email} / voter123 (Code: {user.unique_code})'))
            voters.append(user)

        # Election 1 — Active
        now = timezone.now()
        election1, created = Election.objects.get_or_create(
            title='2024 Board President Election',
            defaults={
                'position': 'President',
                'description': 'Vote for our next board president.',
                'status': 'active',
                'voting_type': 'single',
                'start_date': now - timedelta(hours=2),
                'end_date': now + timedelta(days=3),
                'created_by': commissioner,
                'show_results': True,
            }
        )
        if created:
            election1.eligible_voters.set(voters)
            Candidate.objects.create(election=election1, name='Jane Doe', bio='10 years of leadership experience in community development and strategic planning.', order=1)
            Candidate.objects.create(election=election1, name='John Smith', bio='Former treasurer with a background in finance and nonprofit management.', order=2)
            Candidate.objects.create(election=election1, name='Maria Garcia', bio='Tech entrepreneur and advocate for digital inclusion.', order=3)
            self.stdout.write(self.style.SUCCESS('✓ Election 1 created (Active — Board President)'))

        # Election 2 — Upcoming
        election2, created = Election.objects.get_or_create(
            title='Secretary General Vote',
            defaults={
                'position': 'Secretary General',
                'description': 'Elect the Secretary General for the upcoming term.',
                'status': 'active',
                'voting_type': 'single',
                'start_date': now + timedelta(days=2),
                'end_date': now + timedelta(days=7),
                'created_by': commissioner,
                'show_results': False,
            }
        )
        if created:
            election2.eligible_voters.set(voters)
            Candidate.objects.create(election=election2, name='Chris Lee', bio='Experienced administrator with 5 years in governance.', order=1)
            Candidate.objects.create(election=election2, name='Pat Morgan', bio='Communication specialist and former board observer.', order=2)
            self.stdout.write(self.style.SUCCESS('✓ Election 2 created (Upcoming — Secretary)'))

        self.stdout.write(self.style.SUCCESS('\n✅ Demo data seeded successfully with all roles!'))
        self.stdout.write('\nRole-Based Login Credentials:')
        self.stdout.write('  1. System Admin:           admin@voteapp.com        / admin123     → /admin-panel/ (Full Access & Maintenance)')
        self.stdout.write('  2. Electoral Commissioner: commissioner@voteapp.com / officer123   → /admin-panel/ (Manage Elections & Candidates)')
        self.stdout.write('  3. Voter Registrar:        registrar@voteapp.com    / registrar123 → /admin-panel/ (Manage Voters & CSVs)')
        self.stdout.write('  4. Election Auditor:       auditor@voteapp.com      / auditor123   → /admin-panel/ (Read-only Audits & ZIP Packs)')
        self.stdout.write('  5. Voter:                  alice@example.com        / voter123     → /elections/dashboard/ (Cast Ballot)')

