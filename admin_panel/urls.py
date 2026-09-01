from django.urls import path
from . import views

app_name = 'admin_panel'

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('comprehensive/', views.comprehensive_dashboard, name='comprehensive_dashboard'),
    path('elections/', views.election_list, name='election_list'),
    path('elections/create/', views.election_create, name='election_create'),
    path('elections/<uuid:election_id>/manage/', views.election_manage, name='election_manage'),
    path('elections/<uuid:election_id>/extend/', views.extend_voting_time, name='extend_voting_time'),
    path('elections/<uuid:election_id>/results/', views.election_results, name='election_results'),
    path('elections/<uuid:election_id>/audit-pack/', views.export_election_audit_pack, name='export_election_audit_pack'),
    path('voters/', views.voter_list, name='voter_list'),
    path('voters/invite/', views.voter_invite, name='voter_invite'),
    path('voters/import/', views.voter_import, name='voter_import'),
    path('voters/reset-codes/', views.reset_voter_codes, name='reset_voter_codes'),
    path('staff/', views.staff_list, name='staff_list'),
    path('maintenance/', views.system_maintenance, name='system_maintenance'),
]

