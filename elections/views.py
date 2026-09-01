from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.http import HttpResponse
from django.db.models import Q
import csv
from .models import Election, Candidate, Vote


@login_required
def dashboard(request):
    user = request.user
    now = timezone.now()

    # Elections the user is eligible to vote in
    eligible_elections = Election.objects.filter(
        eligible_voters=user
    ).exclude(status='draft')

    active_elections = eligible_elections.filter(status='active', start_date__lte=now, end_date__gte=now)
    upcoming_elections = eligible_elections.filter(status='active', start_date__gt=now)
    completed_elections = eligible_elections.filter(Q(status='completed') | Q(end_date__lt=now))

    # Votes cast by this user
    user_votes = Vote.objects.filter(voter=user).select_related('election', 'candidate')
    voted_election_ids = set(user_votes.values_list('election_id', flat=True))

    context = {
        'active_elections': active_elections,
        'upcoming_elections': upcoming_elections,
        'completed_elections': completed_elections,
        'user_votes': user_votes,
        'voted_election_ids': voted_election_ids,
        'now': now,
    }
    return render(request, 'elections/dashboard.html', context)


@login_required
def ballot(request, election_id):
    user = request.user
    election = get_object_or_404(Election, id=election_id)

    # Security checks
    if not election.eligible_voters.filter(id=user.id).exists():
        messages.error(request, 'You are not eligible to vote in this election.')
        return redirect('elections:dashboard')

    if not election.is_active:
        messages.error(request, 'This election is not currently active.')
        return redirect('elections:dashboard')

    if Vote.objects.filter(election=election, voter=user).exists():
        messages.warning(request, 'You have already voted in this election.')
        return redirect('elections:dashboard')

    candidates = election.candidates.all()

    if request.method == 'POST':
        candidate_id = request.POST.get('candidate')
        if not candidate_id:
            messages.error(request, 'Please select a candidate before submitting.')
            return render(request, 'elections/ballot.html', {'election': election, 'candidates': candidates})

        candidate = get_object_or_404(Candidate, id=candidate_id, election=election)

        # Double-check no vote already exists (race condition guard)
        vote, created = Vote.objects.get_or_create(
            election=election,
            voter=user,
            defaults={
                'candidate': candidate,
                'ip_address': get_client_ip(request),
            }
        )

        if created:
            messages.success(request, 'Your vote has been submitted successfully!')
            return redirect('elections:confirmation', vote_id=vote.id)
        else:
            messages.error(request, 'You have already voted in this election.')
            return redirect('elections:dashboard')

    return render(request, 'elections/ballot.html', {
        'election': election,
        'candidates': candidates,
    })


@login_required
def confirmation(request, vote_id):
    vote = get_object_or_404(Vote, id=vote_id, voter=request.user)
    return render(request, 'elections/confirmation.html', {'vote': vote})


@login_required
def results(request, election_id):
    election = get_object_or_404(Election, id=election_id)
    user = request.user

    # Admin always has access; voters need eligibility and published results or ended election
    if not user.is_admin_user():
        if not election.eligible_voters.filter(id=user.id).exists():
            messages.error(request, 'You are not eligible to view results for this election.')
            return redirect('elections:dashboard')

        if not election.show_results and not election.has_ended and election.status != 'completed':
            messages.info(request, 'Results for this election have not been published yet.')
            return redirect('elections:dashboard')

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

    return render(request, 'elections/results.html', {
        'election': election,
        'results_data': results_data,
        'total_votes': total_votes,
    })


def get_client_ip(request):
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        return x_forwarded_for.split(',')[0]
    return request.META.get('REMOTE_ADDR')
