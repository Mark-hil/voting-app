from django.urls import path
from . import views

app_name = 'admin_panel'

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('comprehensive/', views.comprehensive_dashboard, name='comprehensive_dashboard'),
    path('elections/', views.election_list, name='election_list'),
    path('elections/create/', views.election_create, name='election_create'),
    path('elections/<uuid:election_id>/manage/', views.election_manage, name='election_manage'),
    path('elections/<uuid:election_id>/results/', views.election_results, name='election_results'),
    path('voters/', views.voter_list, name='voter_list'),
    path('voters/invite/', views.voter_invite, name='voter_invite'),
    path('voters/import/', views.voter_import, name='voter_import'),
]
