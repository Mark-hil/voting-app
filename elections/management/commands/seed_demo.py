from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from accounts.models import CustomUser
from elections.models import Election, Candidate


class Command(BaseCommand):
    help = 'Seed demo data: admin, voters, and sample elections'

    def handle(self, *args, **kwargs):
        self.stdout.write('Seeding demo data...')

        # Admin
        if not CustomUser.objects.filter(email='admin@voteapp.com').exists():
            admin = CustomUser.objects.create_superuser(
                username='admin@voteapp.com',
                email='admin@voteapp.com',
                password='admin123',
                first_name='Admin',
                last_name='User',
                role='admin',
            )
            self.stdout.write(self.style.SUCCESS('✓ Admin: admin@voteapp.com / admin123'))
        else:
            admin = CustomUser.objects.get(email='admin@voteapp.com')
            self.stdout.write('  Admin already exists.')

        # Voters
        voters = []
        voter_data = [
            ('alice@example.com', 'Alice', 'Johnson'),
            ('bob@example.com', 'Bob', 'Smith'),
            ('carol@example.com', 'Carol', 'Williams'),
            ('dave@example.com', 'Dave', 'Brown'),
        ]
        for email, first, last in voter_data:
            user, created = CustomUser.objects.get_or_create(
                email=email,
                defaults={
                    'username': email,
                    'first_name': first,
                    'last_name': last,
                    'role': 'voter',
                }
            )
            if created:
                user.set_password('voter123')
                user.save()
                self.stdout.write(self.style.SUCCESS(f'✓ Voter: {email} / voter123'))
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
                'created_by': admin,
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
                'created_by': admin,
                'show_results': False,
            }
        )
        if created:
            election2.eligible_voters.set(voters)
            Candidate.objects.create(election=election2, name='Chris Lee', bio='Experienced administrator with 5 years in governance.', order=1)
            Candidate.objects.create(election=election2, name='Pat Morgan', bio='Communication specialist and former board observer.', order=2)
            self.stdout.write(self.style.SUCCESS('✓ Election 2 created (Upcoming — Secretary)'))

        self.stdout.write(self.style.SUCCESS('\n✅ Demo data seeded successfully!'))
        self.stdout.write('\nLogin credentials:')
        self.stdout.write('  Admin:  admin@voteapp.com / admin123  → /admin-panel/')
        self.stdout.write('  Voter:  alice@example.com / voter123  → /elections/dashboard/')
