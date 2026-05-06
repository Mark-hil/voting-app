from django.contrib import admin
from .models import Election, Candidate, Vote


class CandidateInline(admin.TabularInline):
    model = Candidate
    extra = 1
    fields = ('name', 'bio', 'photo', 'order')


@admin.register(Election)
class ElectionAdmin(admin.ModelAdmin):
    list_display = ('title', 'position', 'status', 'start_date', 'end_date', 'total_votes')
    list_filter = ('status', 'voting_type')
    search_fields = ('title', 'position')
    inlines = [CandidateInline]
    filter_horizontal = ('eligible_voters',)
    readonly_fields = ('created_at', 'updated_at')


@admin.register(Candidate)
class CandidateAdmin(admin.ModelAdmin):
    list_display = ('name', 'election', 'vote_count', 'order')
    list_filter = ('election',)
    search_fields = ('name', 'election__title')


@admin.register(Vote)
class VoteAdmin(admin.ModelAdmin):
    list_display = ('reference_id', 'election', 'voter', 'candidate', 'cast_at')
    list_filter = ('election',)
    search_fields = ('reference_id', 'voter__email')
    readonly_fields = ('id', 'reference_id', 'cast_at', 'ip_address')
