import os
import csv
import json
import secrets
from datetime import datetime
from django.core.management.base import BaseCommand
from django.core.management import call_command
from django.utils import timezone
from elections.models import Election, Candidate, Vote
from accounts.models import CustomUser


class Command(BaseCommand):
    help = 'Post-election maintenance & cleanup utility: archive elections, reset voter codes, clear sessions, or wipe data.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--archive',
            type=str,
            help='Archive a specific election by UUID (exports results and voter audit data to archives/ directory).'
        )
        parser.add_argument(
            '--reset-voter-codes',
            action='store_true',
            help='Clear single-use voter login codes to prevent reuse.'
        )
        parser.add_argument(
            '--regenerate-codes',
            action='store_true',
            help='Regenerate fresh login codes for all registered voters.'
        )
        parser.add_argument(
            '--clear-sessions',
            action='store_true',
            help='Purge expired user sessions from the database.'
        )
        parser.add_argument(
            '--wipe-votes',
            action='store_true',
            help='Delete all vote and ballot records while keeping elections and candidates.'
        )
        parser.add_argument(
            '--wipe-all',
            action='store_true',
            help='Complete system wipe: deletes all votes, candidates, elections, and non-admin voters.'
        )
        parser.add_argument(
            '--backup',
            action='store_true',
            help='Export a complete JSON database snapshot to backups/ folder before any modifications.'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Simulate maintenance actions without modifying the database or disk.'
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        if dry_run:
            self.stdout.write(self.style.WARNING('[DRY RUN MODE ENABLED - No changes will be committed]\n'))

        # 1. Database Backup
        if options['backup'] or options['wipe_all'] or options['wipe_votes']:
            os.makedirs('backups', exist_ok=True)
            timestamp = timezone.now().strftime('%Y%m%d_%H%M%S')
            backup_path = os.path.join('backups', f'election_backup_{timestamp}.json')
            
            if not dry_run:
                with open(backup_path, 'w', encoding='utf-8') as f:
                    call_command('dumpdata', '--natural-foreign', '--natural-primary', '-e', 'contenttypes', '-e', 'auth.Permission', indent=2, stdout=f)
                self.stdout.write(self.style.SUCCESS(f'✓ Database backup saved to: {backup_path}'))
            else:
                self.stdout.write(f'[DRY RUN] Would create database backup at: {backup_path}')

        # 2. Archive Specific Election
        if options['archive']:
            election_id = options['archive'].strip()
            try:
                election = Election.objects.get(id=election_id)
                self.archive_election(election, dry_run)
            except Election.DoesNotExist:
                self.stdout.write(self.style.ERROR(f'✗ Election with ID "{election_id}" not found.'))

        # 3. Clear Stale Sessions
        if options['clear_sessions'] or options['wipe_all']:
            if not dry_run:
                call_command('clearsessions')
                self.stdout.write(self.style.SUCCESS('✓ Expired sessions cleared from database.'))
            else:
                self.stdout.write('[DRY RUN] Would run django clearsessions to purge expired sessions.')

        # 4. Reset Voter Codes
        if options['reset_voter_codes'] and not options['regenerate_codes']:
            voters = CustomUser.objects.filter(role='voter')
            count = voters.count()
            if not dry_run:
                voters.update(unique_code=None)
                self.stdout.write(self.style.SUCCESS(f'✓ Cleared login codes for {count} voters.'))
            else:
                self.stdout.write(f'[DRY RUN] Would clear login codes for {count} voters.')

        if options['regenerate_codes']:
            voters = CustomUser.objects.filter(role='voter')
            count = voters.count()
            if not dry_run:
                for v in voters:
                    v.unique_code = secrets.token_urlsafe(8).upper()
                    v.save(update_fields=['unique_code'])
                self.stdout.write(self.style.SUCCESS(f'✓ Regenerated fresh login codes for {count} voters.'))
            else:
                self.stdout.write(f'[DRY RUN] Would regenerate fresh login codes for {count} voters.')

        # 5. Wipe Votes Only
        if options['wipe_votes'] and not options['wipe_all']:
            total_votes = Vote.objects.count()
            if not dry_run:
                Vote.objects.all().delete()
                self.stdout.write(self.style.SUCCESS(f'✓ Deleted all {total_votes} votes and ballots.'))
            else:
                self.stdout.write(f'[DRY RUN] Would delete all {total_votes} vote records.')

        # 6. Complete System Wipe
        if options['wipe_all']:
            total_votes = Vote.objects.count()
            total_candidates = Candidate.objects.count()
            total_elections = Election.objects.count()
            non_admin_voters = CustomUser.objects.filter(role='voter', is_staff=False, is_superuser=False).count()

            if not dry_run:
                Vote.objects.all().delete()
                for c in Candidate.objects.all():
                    if c.photo:
                        try:
                            c.photo.delete(save=False)
                        except Exception:
                            pass
                Candidate.objects.all().delete()
                Election.objects.all().delete()
                CustomUser.objects.filter(role='voter', is_staff=False, is_superuser=False).delete()
                call_command('clearsessions')
                self.stdout.write(self.style.SUCCESS(
                    f'✓ Complete system wipe finished: {total_votes} votes, {total_candidates} candidates, {total_elections} elections, and {non_admin_voters} non-admin voters deleted.'
                ))
            else:
                self.stdout.write(self.style.WARNING(
                    f'[DRY RUN] Would delete: {total_votes} votes, {total_candidates} candidates, {total_elections} elections, and {non_admin_voters} voter accounts.'
                ))

        if not any([options['archive'], options['reset_voter_codes'], options['regenerate_codes'], options['clear_sessions'], options['wipe_votes'], options['wipe_all'], options['backup']]):
            self.stdout.write(self.style.WARNING('No maintenance options specified. Use --help to view available commands:'))
            self.stdout.write('  --archive <uuid>      : Archive election data')
            self.stdout.write('  --reset-voter-codes   : Invalidate old single-use codes')
            self.stdout.write('  --regenerate-codes    : Generate new login codes for next election')
            self.stdout.write('  --clear-sessions      : Purge expired sessions')
            self.stdout.write('  --wipe-votes          : Clear all cast ballots')
            self.stdout.write('  --wipe-all            : Total clean slate reset')
            self.stdout.write('  --dry-run             : Preview without executing')

    def archive_election(self, election, dry_run):
        archive_dir = os.path.join('archives', f'election_{election.id}')
        
        if dry_run:
            self.stdout.write(f'[DRY RUN] Would export archive for "{election.title}" to: {archive_dir}/')
            return

        os.makedirs(archive_dir, exist_ok=True)
        
        # 1. Export results CSV
        results_path = os.path.join(archive_dir, 'official_results.csv')
        candidates = election.candidates.all()
        results_data = []
        for candidate in candidates:
            results_data.append({
                'name': candidate.name,
                'bio': candidate.bio,
                'votes': candidate.vote_count,
                'percentage': candidate.vote_percentage,
            })
        results_data.sort(key=lambda x: x['votes'], reverse=True)

        with open(results_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['Rank', 'Candidate Name', 'Votes Received', 'Vote Percentage', 'Bio'])
            for i, r in enumerate(results_data, 1):
                writer.writerow([i, r['name'], r['votes'], f"{r['percentage']}%", r['bio']])

        # 2. Export Voter Turnout CSV
        voters_path = os.path.join(archive_dir, 'voter_turnout.csv')
        with open(voters_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['Voter Name', 'Username', 'Email', 'Voting Status', 'Registered Date'])
            for voter in election.eligible_voters.all().order_by('username'):
                has_voted = Vote.objects.filter(election=election, voter=voter).exists()
                writer.writerow([
                    voter.get_full_name() or voter.username,
                    voter.username,
                    voter.email or '',
                    'Voted' if has_voted else 'Not Voted',
                    voter.date_joined.strftime('%Y-%m-%d %H:%M:%S') if voter.date_joined else ''
                ])

        # 3. Export Ballot Receipts Audit CSV
        receipts_path = os.path.join(archive_dir, 'ballot_receipts_audit.csv')
        with open(receipts_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['Ballot Reference ID', 'Timestamp Cast (UTC)', 'IP Address (Audit)'])
            for vote in election.votes.all().order_by('cast_at'):
                writer.writerow([
                    vote.reference_id,
                    vote.cast_at.strftime('%Y-%m-%d %H:%M:%S'),
                    vote.ip_address or 'N/A'
                ])

        # 4. Summary JSON
        summary_path = os.path.join(archive_dir, 'election_summary.json')
        summary_data = {
            'election_id': str(election.id),
            'title': election.title,
            'position': election.position,
            'status': 'completed',
            'voting_type': election.get_voting_type_display(),
            'start_date': election.start_date.isoformat(),
            'end_date': election.end_date.isoformat(),
            'total_eligible_voters': election.total_eligible,
            'total_votes_cast': election.total_votes,
            'turnout_percentage': f"{election.participation_rate}%",
            'archived_at': timezone.now().isoformat(),
            'results': results_data,
        }
        with open(summary_path, 'w', encoding='utf-8') as f:
            json.dump(summary_data, f, indent=2)

        # Mark election completed and results public
        election.status = 'completed'
        election.show_results = True
        election.save(update_fields=['status', 'show_results'])

        self.stdout.write(self.style.SUCCESS(f'✓ Election "{election.title}" archived successfully in: {archive_dir}/'))
