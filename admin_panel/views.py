from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.http import JsonResponse, HttpResponse
from django.db.models import Count, Q
import csv, json
import secrets
from django.core.validators import validate_email
from django.core.exceptions import ValidationError
from elections.models import Election, Candidate, Vote
from accounts.models import CustomUser
from .forms import ElectionForm, CandidateForm, VoterInviteForm, VoterImportForm
from .decorators import admin_required
from .security import admin_rate_limit
from io import TextIOWrapper


@login_required
@admin_required
def dashboard(request):
    total_voters = CustomUser.objects.filter(role='voter').count()
    total_elections = Election.objects.count()
    active_elections = Election.objects.filter(status='active').count()
    total_votes = Vote.objects.count()

    recent_elections = Election.objects.order_by('-created_at')[:5]
    recent_votes = Vote.objects.select_related('voter', 'election', 'candidate').order_by('-cast_at')[:10]

    context = {
        'total_voters': total_voters,
        'total_elections': total_elections,
        'active_elections': active_elections,
        'total_votes': total_votes,
        'recent_elections': recent_elections,
        'recent_votes': recent_votes,
    }
    return render(request, 'admin_panel/dashboard.html', context)


@login_required
@admin_required
def comprehensive_dashboard(request):
    # Enhanced election statistics
    all_elections = Election.objects.all().prefetch_related('candidates', 'votes')
    election_stats = []
    
    for election in all_elections:
        candidates_data = []
        for candidate in election.candidates.all():
            candidates_data.append({
                'name': candidate.name,
                'votes': candidate.vote_count,
                'percentage': candidate.vote_percentage,
            })
        candidates_data.sort(key=lambda x: x['votes'], reverse=True)
        
        election_stats.append({
            'election': election,
            'candidates': candidates_data,
            'total_votes': election.total_votes,
            'participation_rate': election.participation_rate,
            'total_eligible': election.total_eligible,
        })

    # Overall statistics
    total_voters = CustomUser.objects.filter(role='voter').count()
    total_elections = Election.objects.count()
    active_elections = Election.objects.filter(status='active').count()
    total_votes = Vote.objects.count()

    context = {
        'election_stats': election_stats,
        'total_voters': total_voters,
        'total_elections': total_elections,
        'active_elections': active_elections,
        'total_votes': total_votes,
    }
    return render(request, 'admin_panel/comprehensive_dashboard.html', context)


@login_required
@admin_required
def election_list(request):
    elections = Election.objects.annotate(vote_count=Count('votes')).order_by('-created_at')
    return render(request, 'admin_panel/election_list.html', {'elections': elections})


@login_required
@admin_required
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
@admin_required
def election_manage(request, election_id):
    election = get_object_or_404(Election, id=election_id)
    candidates = election.candidates.all()
    candidate_form = CandidateForm()

    if request.method == 'POST':
        action = request.POST.get('action')

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
@admin_required
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
@admin_required
def voter_invite(request):
    if request.method == 'POST':
        form = VoterInviteForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data['email']
            first_name = form.cleaned_data['first_name']
            last_name = form.cleaned_data['last_name']

            user, created = CustomUser.objects.get_or_create(
                email=email,
                defaults={
                    'username': email,
                    'first_name': first_name,
                    'last_name': last_name,
                    'role': 'voter',
                }
            )
            if created:
                messages.success(request, f'Voter {email} added successfully!')
            else:
                messages.warning(request, f'User with email {email} already exists.')
            return redirect('admin_panel:voter_list')
    else:
        form = VoterInviteForm()
    return render(request, 'admin_panel/voter_invite.html', {'form': form})


@login_required
@admin_required
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
