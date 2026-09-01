from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.http import JsonResponse, HttpResponse
from django.db.models import Count, Q
import csv, json, zipfile
import secrets
from django.core.validators import validate_email
from django.core.exceptions import ValidationError
from elections.models import Election, Candidate, Vote
from accounts.models import CustomUser
from .forms import ElectionForm, CandidateForm, VoterInviteForm, VoterImportForm
from .decorators import (
    admin_required,
    system_admin_required,
    election_officer_required,
    registrar_required,
    auditor_or_admin_required,
)
from .security import admin_rate_limit
from io import BytesIO, StringIO, TextIOWrapper
from django.core.management import call_command


@login_required
@admin_required
def dashboard(request):
    if request.user.role == 'registrar':
        return redirect('admin_panel:voter_list')

    total_voters = CustomUser.objects.filter(role='voter').count()
    voters_participated = Vote.objects.values('voter').distinct().count()
    voters_uncast = max(0, total_voters - voters_participated)
    turnout_percentage = round((voters_participated / total_voters * 100), 1) if total_voters > 0 else 0.0
    uncast_percentage = round((voters_uncast / total_voters * 100), 1) if total_voters > 0 else 0.0
    total_elections = Election.objects.count()
    active_elections = Election.objects.filter(status='active').count()
    total_votes = Vote.objects.count()

    recent_elections = Election.objects.order_by('-created_at')[:5]
    recent_votes = Vote.objects.select_related('voter', 'election', 'candidate').order_by('-cast_at')[:10]

    context = {
        'total_voters': total_voters,
        'voters_participated': voters_participated,
        'voters_uncast': voters_uncast,
        'turnout_percentage': turnout_percentage,
        'uncast_percentage': uncast_percentage,
        'total_elections': total_elections,
        'active_elections': active_elections,
        'total_votes': total_votes,
        'recent_elections': recent_elections,
        'recent_votes': recent_votes,
    }
    return render(request, 'admin_panel/dashboard.html', context)


@login_required
@auditor_or_admin_required
def comprehensive_dashboard(request):
    # Enhanced election statistics
    all_elections = Election.objects.all().prefetch_related('candidates', 'votes')
    election_stats = []
    
    for election in all_elections:
        candidates_data = []
        for candidate in election.candidates.all():
            candidates_data.append({
                'candidate': candidate,
                'name': candidate.name,
                'votes': candidate.vote_count,
                'percentage': candidate.vote_percentage,
                'photo': candidate.photo,
                'bio': candidate.bio,
            })
        candidates_data.sort(key=lambda x: x['votes'], reverse=True)
        
        election_stats.append({
            'election': election,
            'candidates': candidates_data,
            'total_votes': election.total_votes,
            'uncast_votes': election.uncast_votes,
            'uncast_rate': election.uncast_rate,
            'participation_rate': election.participation_rate,
            'total_eligible': election.total_eligible,
        })

    # Overall statistics
    total_voters = CustomUser.objects.filter(role='voter').count()
    voters_participated = Vote.objects.values('voter').distinct().count()
    voters_uncast = max(0, total_voters - voters_participated)
    turnout_percentage = round((voters_participated / total_voters * 100), 1) if total_voters > 0 else 0.0
    uncast_percentage = round((voters_uncast / total_voters * 100), 1) if total_voters > 0 else 0.0
    total_elections = Election.objects.count()
    active_elections = Election.objects.filter(status='active').count()
    total_votes = Vote.objects.count()

    context = {
        'election_stats': election_stats,
        'total_voters': total_voters,
        'voters_participated': voters_participated,
        'voters_uncast': voters_uncast,
        'turnout_percentage': turnout_percentage,
        'uncast_percentage': uncast_percentage,
        'total_elections': total_elections,
        'active_elections': active_elections,
        'total_votes': total_votes,
    }
    return render(request, 'admin_panel/comprehensive_dashboard.html', context)


@login_required
@admin_required
def election_list(request):
    status_filter = request.GET.get('status', '').strip()
    elections = Election.objects.annotate(vote_count=Count('votes'))
    
    if status_filter in ['active', 'completed', 'draft', 'cancelled']:
        elections = elections.filter(status=status_filter)
        
    elections = elections.order_by('-created_at')

    total_count = Election.objects.count()
    active_count = Election.objects.filter(status='active').count()
    completed_count = Election.objects.filter(status='completed').count()
    draft_count = Election.objects.filter(status='draft').count()

    context = {
        'elections': elections,
        'status_filter': status_filter,
        'total_count': total_count,
        'active_count': active_count,
        'completed_count': completed_count,
        'draft_count': draft_count,
    }
    return render(request, 'admin_panel/election_list.html', context)


@login_required
@election_officer_required
def election_create(request):
    if request.method == 'POST':
        form = ElectionForm(request.POST)
        if form.is_valid():
            election = form.save(commit=False)
            election.created_by = request.user
            election.save()
            form.save_m2m()
            # If no eligible voters were selected, assign all voters
            if election.eligible_voters.count() == 0:
                all_voters = CustomUser.objects.filter(role='voter')
                election.eligible_voters.set(all_voters)
            messages.success(request, f'Election "{election.title}" created successfully!')
            return redirect('admin_panel:election_manage', election_id=election.id)
        else:
            messages.error(request, 'Please fix the errors below.')
    else:
        form = ElectionForm()
    return render(request, 'admin_panel/election_form.html', {'form': form, 'title': 'Create Election'})


@login_required
@election_officer_required
def election_manage(request, election_id):
    election = get_object_or_404(Election, id=election_id)
    candidates = election.candidates.all()
    candidate_form = CandidateForm()

    if request.method == 'POST':
        action = request.POST.get('action')

        # Safeguard: disallow modifying candidates/settings when election is completed
        if election.status == 'completed' and action in ['update_election', 'add_candidate', 'delete_candidate']:
            messages.error(request, 'This election is marked as Completed. Changes to candidates or configuration are locked to preserve audit integrity. Re-open to Draft or Active if changes are needed.')
            return redirect('admin_panel:election_manage', election_id=election.id)

        if action == 'update_election':
            form = ElectionForm(request.POST, instance=election)
            if form.is_valid():
                form.save()
                messages.success(request, 'Election updated successfully!')
        elif action == 'add_candidate':
            candidate_form = CandidateForm(request.POST, request.FILES)
            if candidate_form.is_valid():
                candidate = candidate_form.save(commit=False)
                candidate.election = election
                candidate.save()
                messages.success(request, f'Candidate "{candidate.name}" added!')
        elif action == 'delete_candidate':
            candidate_id = request.POST.get('candidate_id')
            Candidate.objects.filter(id=candidate_id, election=election).delete()
            messages.success(request, 'Candidate removed.')
        elif action == 'toggle_status':
            new_status = request.POST.get('status')
            if new_status in ['draft', 'active', 'completed', 'cancelled']:
                election.status = new_status
                election.save()
                messages.success(request, f'Election status updated to {new_status}.')
        elif action == 'toggle_results':
            election.show_results = not election.show_results
            election.save()
            messages.success(request, 'Results visibility updated.')

        return redirect('admin_panel:election_manage', election_id=election.id)

    election_form = ElectionForm(instance=election)
    context = {
        'election': election,
        'candidates': candidates,
        'election_form': election_form,
        'candidate_form': candidate_form,
    }
    return render(request, 'admin_panel/election_manage.html', context)


@login_required
@election_officer_required
def extend_voting_time(request, election_id):
    election = get_object_or_404(Election, id=election_id)
    
    if request.method == 'POST':
        # Debug: Print POST data
        print(f"DEBUG: POST data = {request.POST}")
        print(f"DEBUG: election_id = {election_id}")
        
        try:
            # Get extension duration from form with validation
            hours_str = request.POST.get('hours', '0')
            days_str = request.POST.get('days', '0')
            
            print(f"DEBUG: hours_str = '{hours_str}', days_str = '{days_str}'")
            
            # Convert to integers with error handling
            hours = 0
            days = 0
            
            if hours_str and hours_str.strip():
                hours = int(hours_str)
                if hours < 0 or hours > 23:
                    raise ValueError("Hours must be between 0 and 23")
            
            if days_str and days_str.strip():
                days = int(days_str)
                if days < 0 or days > 30:
                    raise ValueError("Days must be between 0 and 30")
            
            # Check if any extension is requested
            if hours == 0 and days == 0:
                messages.error(request, 'Please specify at least some days or hours to extend.')
                return render(request, 'admin_panel/extend_voting.html', {'election': election})
            
            # Calculate new end date
            from datetime import timedelta
            extension = timedelta(hours=hours, days=days)
            election.end_date = election.end_date + extension
            election.save()
            
            messages.success(request, f'Voting time extended by {days} days and {hours} hours.')
            return redirect('admin_panel:election_manage', election_id=election.id)
            
        except (ValueError, TypeError) as e:
            print(f"DEBUG: Error occurred: {e}")
            messages.error(request, f'Invalid input: {str(e)}. Please enter valid numbers.')
            return render(request, 'admin_panel/extend_voting.html', {'election': election})
        except Exception as e:
            print(f"DEBUG: Unexpected error: {e}")
            messages.error(request, f'An error occurred: {str(e)}. Please try again.')
            return render(request, 'admin_panel/extend_voting.html', {'election': election})
    
    return render(request, 'admin_panel/extend_voting.html', {'election': election})


@login_required
@auditor_or_admin_required
def election_results(request, election_id):
    election = get_object_or_404(Election, id=election_id)
    candidates = election.candidates.all()
    total_votes = election.total_votes

    results_data = []
    for candidate in candidates:
        results_data.append({
            'candidate': candidate,
            'votes': candidate.vote_count,
            'percentage': candidate.vote_percentage,
        })
    results_data.sort(key=lambda x: x['votes'], reverse=True)

    if request.GET.get('export') == 'csv':
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="results_{election.id}.csv"'
        writer = csv.writer(response)
        writer.writerow(['Rank', 'Candidate', 'Votes', 'Percentage'])
        for i, r in enumerate(results_data, 1):
            writer.writerow([i, r['candidate'].name, r['votes'], f"{r['percentage']}%"])
        return response

    return render(request, 'admin_panel/election_results.html', {
        'election': election,
        'results_data': results_data,
        'total_votes': total_votes,
        'uncast_votes': election.uncast_votes,
        'uncast_rate': election.uncast_rate,
    })


@login_required
@admin_required
def voter_list(request):
    search = request.GET.get('search', '')
    status_filter = request.GET.get('status', '')

    voters = CustomUser.objects.filter(role='voter')
    if search:
        voters = voters.filter(
            Q(first_name__icontains=search) |
            Q(last_name__icontains=search) |
            Q(email__icontains=search)
        )

    voters_data = []
    for voter in voters:
        has_voted = voter.votes.exists()
        if status_filter == 'voted' and not has_voted:
            continue
        if status_filter == 'not_voted' and has_voted:
            continue
        voters_data.append({'voter': voter, 'has_voted': has_voted})

    if request.GET.get('export') == 'csv':
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="voters.csv"'
        writer = csv.writer(response)
        writer.writerow(['Name', 'Email', 'Username', 'Unique Code', 'Status', 'Date Joined'])
        for vd in voters_data:
            v = vd['voter']
            writer.writerow([
                v.get_full_name(),
                v.email or '',
                v.username,
                v.unique_code or 'No code',
                'Voted' if vd['has_voted'] else 'Not Voted',
                v.date_joined
            ])
        return response

    if request.GET.get('export') == 'codes':
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="voter_codes.csv"'
        writer = csv.writer(response)
        writer.writerow(['Username', 'Unique Code'])
        for vd in voters_data:
            v = vd['voter']
            if v.unique_code:  # Only export voters with unique codes
                writer.writerow([v.username, v.unique_code])
        return response

    return render(request, 'admin_panel/voter_list.html', {
        'voters_data': voters_data,
        'search': search,
        'status_filter': status_filter,
    })


@login_required
@registrar_required
def voter_invite(request):
    if request.method == 'POST':
        form = VoterInviteForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data['email'].strip().lower()
            first_name = form.cleaned_data['first_name'].strip()
            last_name = form.cleaned_data['last_name'].strip()
            unique_code = secrets.token_urlsafe(8).upper()

            user, created = CustomUser.objects.get_or_create(
                email=email,
                defaults={
                    'username': email,
                    'first_name': first_name,
                    'last_name': last_name,
                    'role': 'voter',
                    'unique_code': unique_code,
                }
            )
            if created:
                messages.success(request, f'Voter {email} added successfully! Login code: {user.unique_code}')
            else:
                if not user.unique_code:
                    user.unique_code = unique_code
                    user.save()
                messages.warning(request, f'User with email {email} already exists (Login code: {user.unique_code}).')
            return redirect('admin_panel:voter_list')
    else:
        form = VoterInviteForm()
    return render(request, 'admin_panel/voter_invite.html', {'form': form})


@login_required
@registrar_required
def voter_import(request):
    if request.method == 'POST':
        form = VoterImportForm(request.POST, request.FILES)
        if form.is_valid():
            csv_file = request.FILES['csv_file']
            
            try:
                # Read and decode the file
                decoded_file = csv_file.read().decode('utf-8')
                # Create a file-like object from the decoded string
                from io import StringIO
                io_string = StringIO(decoded_file)
                
                reader = csv.DictReader(io_string)
                imported_count = 0
                skipped_count = 0
                
                # Debug: Print headers
                print(f"CSV headers: {reader.fieldnames}")
                
                for row_num, row in enumerate(reader, 1):
                    print(f"Processing row {row_num}: {row}")
                    
                    name = (row.get('name') or row.get("STUDENT'S NAME") or '').strip()
                    index = (row.get('index') or row.get('INDEX NUMBER') or '').strip()
                    
                    print(f"Name: '{name}', Index: '{index}'")
                    
                    # Input validation
                    if not name:
                        print(f"Skipping row {row_num}: no name")
                        skipped_count += 1
                        continue
                    
                    # Validate name length and characters
                    if len(name) < 2 or len(name) > 100:
                        print(f"Skipping row {row_num}: invalid name length")
                        skipped_count += 1
                        continue
                    
                    # Validate index if provided
                    if index:
                        # Accept both numeric and alphanumeric indexes
                        if len(index) < 1:
                            print(f"Skipping row {row_num}: invalid index number")
                            skipped_count += 1
                            continue
                    
                    # Generate unique code
                    unique_code = secrets.token_urlsafe(8).upper()
                    print(f"Generated unique code: {unique_code}")
                    
                    # Create username from name and index
                    if index:
                        # Clean up index for username (remove special characters)
                        clean_index = index.replace('-', '').replace('_', '')
                        username = f"{name.replace(' ', '').lower()}{clean_index}"
                    else:
                        # If no index, just use name with numbers
                        username = name.replace(' ', '').lower()
                    
                    # Ensure unique username
                    base_username = username
                    counter = 1
                    while CustomUser.objects.filter(username=username).exists():
                        username = f"{base_username}{counter}"
                        counter += 1
                    
                    print(f"Username: {username}")
                    
                    # Create voter
                    try:
                        user, created = CustomUser.objects.get_or_create(
                            username=username,
                            defaults={
                                'first_name': name.split()[0] if ' ' in name else name,
                                'last_name': ' '.join(name.split()[1:]) if ' ' in name else '',
                                'role': 'voter',
                                'unique_code': unique_code,
                            }
                        )
                        print(f"User created: {created}, User ID: {user.id}")
                        if created:
                            imported_count += 1
                        else:
                            # Update existing user with unique code if they don't have one
                            if not user.unique_code:
                                user.unique_code = unique_code
                                user.save()
                                imported_count += 1
                            else:
                                print(f"User already exists with unique code: {user.unique_code}")
                                skipped_count += 1
                    except Exception as e:
                        print(f"Error creating user: {e}")
                        skipped_count += 1
                        continue
                
                print(f"Final counts - Imported: {imported_count}, Skipped: {skipped_count}")
                messages.success(request, f'Successfully imported {imported_count} voters. Skipped {skipped_count}.')
                return redirect('admin_panel:voter_list')
            except Exception as e:
                print(f"Error processing CSV: {e}")
                messages.error(request, f'Error processing CSV file: {e}')
    else:
        form = VoterImportForm()
    
    return render(request, 'admin_panel/voter_import.html', {'form': form})


@login_required
@auditor_or_admin_required
def export_election_audit_pack(request, election_id):
    """
    Generates a full audit & archive package as a downloadable ZIP.
    Contains official results, voter participation list, anonymized ballot receipts,
    and a complete election summary JSON.
    """
    election = get_object_or_404(Election, id=election_id)
    candidates = election.candidates.all()
    
    # 1. Official Results CSV
    results_io = StringIO()
    results_writer = csv.writer(results_io)
    results_writer.writerow(['Rank', 'Candidate Name', 'Votes Received', 'Vote Percentage', 'Bio'])
    
    results_data = []
    for candidate in candidates:
        results_data.append({
            'name': candidate.name,
            'bio': candidate.bio,
            'votes': candidate.vote_count,
            'percentage': candidate.vote_percentage,
        })
    results_data.sort(key=lambda x: x['votes'], reverse=True)
    
    for i, r in enumerate(results_data, 1):
        results_writer.writerow([i, r['name'], r['votes'], f"{r['percentage']}%", r['bio']])
        
    # 2. Voter Turnout CSV
    voter_io = StringIO()
    voter_writer = csv.writer(voter_io)
    voter_writer.writerow(['Voter Name', 'Username', 'Email', 'Voting Status', 'Registered Date'])
    for voter in election.eligible_voters.all().order_by('username'):
        has_voted = Vote.objects.filter(election=election, voter=voter).exists()
        voter_writer.writerow([
            voter.get_full_name() or voter.username,
            voter.username,
            voter.email or '',
            'Voted' if has_voted else 'Not Voted',
            voter.date_joined.strftime('%Y-%m-%d %H:%M:%S') if voter.date_joined else ''
        ])
        
    # 3. Ballot Receipts Audit CSV (Anonymized vote verification)
    receipts_io = StringIO()
    receipts_writer = csv.writer(receipts_io)
    receipts_writer.writerow(['Ballot Reference ID', 'Timestamp Cast (UTC)', 'IP Address (Audit)'])
    for vote in election.votes.all().order_by('cast_at'):
        receipts_writer.writerow([
            vote.reference_id,
            vote.cast_at.strftime('%Y-%m-%d %H:%M:%S'),
            vote.ip_address or 'N/A'
        ])
        
    # 4. Election Summary JSON
    summary_data = {
        'election_id': str(election.id),
        'title': election.title,
        'position': election.position,
        'status': election.status,
        'voting_type': election.get_voting_type_display(),
        'start_date': election.start_date.isoformat(),
        'end_date': election.end_date.isoformat(),
        'created_by': election.created_by.get_full_name() if election.created_by else 'N/A',
        'total_eligible_voters': election.total_eligible,
        'total_votes_cast': election.total_votes,
        'turnout_percentage': f"{election.participation_rate}%",
        'exported_at': timezone.now().isoformat(),
        'results': results_data,
    }
    
    # Pack into In-Memory ZIP file
    zip_buffer = BytesIO()
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        zip_file.writestr('official_results.csv', results_io.getvalue())
        zip_file.writestr('voter_turnout.csv', voter_io.getvalue())
        zip_file.writestr('ballot_receipts_audit.csv', receipts_io.getvalue())
        zip_file.writestr('election_summary.json', json.dumps(summary_data, indent=2))
        
    zip_buffer.seek(0)
    response = HttpResponse(zip_buffer.getvalue(), content_type='application/zip')
    sanitized_title = "".join(c for c in election.title if c.isalnum() or c in (' ', '_', '-')).rstrip().replace(' ', '_')
    response['Content-Disposition'] = f'attachment; filename="audit_pack_{sanitized_title}_{election.id}.zip"'
    return response


@login_required
@registrar_required
def reset_voter_codes(request):
    """
    Clears or regenerates unique login codes for voters between election cycles.
    """
    if request.method == 'POST':
        action_type = request.POST.get('reset_type', 'clear')  # 'clear' or 'regenerate'
        target = request.POST.get('target', 'all')  # 'all' or 'voted'
        
        voters = CustomUser.objects.filter(role='voter')
        if target == 'voted':
            voters = voters.filter(votes__isnull=False).distinct()
            
        count = voters.count()
        if action_type == 'clear':
            voters.update(unique_code=None)
            messages.success(request, f'Successfully cleared login codes for {count} voter(s).')
        elif action_type == 'regenerate':
            updated = 0
            for v in voters:
                v.unique_code = secrets.token_urlsafe(8).upper()
                v.save(update_fields=['unique_code'])
                updated += 1
            messages.success(request, f'Successfully generated fresh login codes for {updated} voter(s).')
            
        return redirect('admin_panel:voter_list')
    
    return redirect('admin_panel:voter_list')


@login_required
@system_admin_required
def system_maintenance(request):
    """
    Admin system maintenance and clean-up control center:
    - Download full database JSON backup
    - Clear expired Django sessions
    - Reset voter login codes
    - Total System Wipe / Clean Slate (Danger Zone)
    """
    total_elections = Election.objects.count()
    total_votes = Vote.objects.count()
    total_candidates = Candidate.objects.count()
    total_voters = CustomUser.objects.filter(role='voter').count()
    active_elections_count = Election.objects.filter(status='active').count()
    completed_elections_count = Election.objects.filter(status='completed').count()
    
    if request.method == 'POST':
        action = request.POST.get('action')
        
        if action == 'export_backup':
            # Export full database JSON dump
            buf = StringIO()
            call_command('dumpdata', '--natural-foreign', '--natural-primary', '-e', 'contenttypes', '-e', 'auth.Permission', indent=2, stdout=buf)
            
            response = HttpResponse(buf.getvalue(), content_type='application/json')
            timestamp = timezone.now().strftime('%Y%m%d_%H%M%S')
            response['Content-Disposition'] = f'attachment; filename="voteapp_backup_{timestamp}.json"'
            return response
            
        elif action == 'clear_sessions':
            call_command('clearsessions')
            messages.success(request, 'Expired user sessions have been purged successfully.')
            return redirect('admin_panel:system_maintenance')
            
        elif action == 'wipe_data':
            confirmation = request.POST.get('confirmation', '').strip()
            wipe_type = request.POST.get('wipe_type', 'votes_only')
            
            if confirmation != 'RESET':
                messages.error(request, 'Confirmation text mismatch. You must type "RESET" in capital letters to proceed.')
                return redirect('admin_panel:system_maintenance')
                
            if wipe_type == 'votes_only':
                deleted_votes, _ = Vote.objects.all().delete()
                messages.success(request, f'All ballot votes ({deleted_votes} records) have been wiped completely. Elections, candidates, and voters remain intact.')
            elif wipe_type == 'full_wipe':
                deleted_votes, _ = Vote.objects.all().delete()
                
                # Delete candidate photos from storage
                for c in Candidate.objects.all():
                    if c.photo:
                        try:
                            c.photo.delete(save=False)
                        except Exception:
                            pass
                deleted_candidates, _ = Candidate.objects.all().delete()
                deleted_elections, _ = Election.objects.all().delete()
                
                # Delete non-admin voter accounts
                deleted_voters, _ = CustomUser.objects.filter(role='voter', is_staff=False, is_superuser=False).delete()
                
                # Clear sessions
                call_command('clearsessions')
                
                messages.success(request, f'System wiped to clean slate: {deleted_votes} votes, {deleted_candidates} candidates, {deleted_elections} elections, and {deleted_voters} voter accounts deleted.')
                
            return redirect('admin_panel:system_maintenance')
            
    context = {
        'total_elections': total_elections,
        'total_votes': total_votes,
        'total_candidates': total_candidates,
        'total_voters': total_voters,
        'active_elections_count': active_elections_count,
        'completed_elections_count': completed_elections_count,
        'elections': Election.objects.all().order_by('-created_at')[:10],
    }
    return render(request, 'admin_panel/system_maintenance.html', context)


@login_required
@system_admin_required
def staff_list(request):
    """
    Allows System Administrators to view, invite, and assign roles to staff accounts
    (System Administrator, Electoral Commissioner, Voter Registrar, Election Auditor).
    """
    staff_users = CustomUser.objects.exclude(role='voter').order_by('role', 'username')
    voters = CustomUser.objects.filter(role='voter').order_by('username')
    
    if request.method == 'POST':
        action = request.POST.get('action')
        
        if action == 'update_role':
            user_id = request.POST.get('user_id')
            new_role = request.POST.get('role')
            target_user = get_object_or_404(CustomUser, id=user_id)
            
            # Prevent demoting own administrator account if it's the current user
            if target_user == request.user and new_role != 'admin':
                messages.error(request, 'You cannot demote your own System Administrator account.')
                return redirect('admin_panel:staff_list')
                
            if new_role in dict(CustomUser.ROLE_CHOICES):
                target_user.role = new_role
                target_user.is_staff = (new_role != 'voter')
                target_user.save()
                messages.success(request, f'Updated role for {target_user.get_full_name() or target_user.username} to {target_user.get_role_display()}.')
            else:
                messages.error(request, 'Invalid role selected.')
            return redirect('admin_panel:staff_list')
            
        elif action == 'add_staff':
            email = request.POST.get('email', '').strip().lower()
            first_name = request.POST.get('first_name', '').strip()
            last_name = request.POST.get('last_name', '').strip()
            role = request.POST.get('role', 'officer')
            password = request.POST.get('password', '').strip()
            
            if not email or not password:
                messages.error(request, 'Email and password are required to create a staff user.')
                return redirect('admin_panel:staff_list')
                
            if CustomUser.objects.filter(email__iexact=email).exists() or CustomUser.objects.filter(username__iexact=email).exists():
                messages.error(request, f'An account with email/username "{email}" already exists.')
                return redirect('admin_panel:staff_list')
                
            user = CustomUser.objects.create_user(
                username=email,
                email=email,
                first_name=first_name,
                last_name=last_name,
                role=role,
                is_staff=(role != 'voter')
            )
            user.set_password(password)
            user.save()
            messages.success(request, f'Staff member "{user.get_full_name() or email}" created as {user.get_role_display()}!')
            return redirect('admin_panel:staff_list')
            
    context = {
        'staff_users': staff_users,
        'voters': voters[:50],  # sample voters for role promotion
        'total_staff': staff_users.count(),
        'role_choices': CustomUser.ROLE_CHOICES,
    }
    return render(request, 'admin_panel/staff_list.html', context)


