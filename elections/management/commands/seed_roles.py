from django.core.management.base import BaseCommand
from accounts.models import CustomUser


class Command(BaseCommand):
    help = 'Seed only role-based staff accounts (Admin, Commissioner, Registrar, Auditor) without demo voters or elections'

    def handle(self, *args, **options):
        self.stdout.write('Seeding administrative and staff roles...')

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
            admin.is_staff = True
            admin.is_superuser = True
            admin.save()
            self.stdout.write(self.style.SUCCESS('✓ System Admin: admin@voteapp.com (Updated/Verified)'))

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
        self.stdout.write(self.style.SUCCESS('✓ Election Auditor: auditor@voteapp.com / auditor123'))

        self.stdout.write(self.style.SUCCESS('\n✅ All RBAC staff roles seeded successfully! (No demo voters or elections created)'))
        self.stdout.write('\nStaff Login Credentials:')
        self.stdout.write('  1. System Admin:           admin@voteapp.com        / admin123     → /admin-panel/')
        self.stdout.write('  2. Electoral Commissioner: commissioner@voteapp.com / officer123   → /admin-panel/')
        self.stdout.write('  3. Voter Registrar:        registrar@voteapp.com    / registrar123 → /admin-panel/')
        self.stdout.write('  4. Election Auditor:       auditor@voteapp.com      / auditor123   → /admin-panel/')
