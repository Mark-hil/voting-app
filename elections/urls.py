from django.urls import path
from . import views

app_name = 'elections'

urlpatterns = [
    path('dashboard/', views.dashboard, name='dashboard'),
    path('<uuid:election_id>/ballot/', views.ballot, name='ballot'),
    path('confirmation/<uuid:vote_id>/', views.confirmation, name='confirmation'),
    path('<uuid:election_id>/results/', views.results, name='results'),
]
