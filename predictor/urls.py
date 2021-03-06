from django.urls import path

from . import views


app_name = 'predictor'

# TODO: add static just for one app
urlpatterns = [
    path('', views.index, name='index'),
    path('auth', views.auth, name='auth'),
    path('register', views.register_page, name='register'),
    path('restore', views.restore, name='restore'),
    path('research', views.research_page, name='research')
]
