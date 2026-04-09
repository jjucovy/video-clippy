from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r'videos', views.VideoViewSet)
router.register(r'clips', views.ClipViewSet)
router.register(r'people', views.PersonViewSet)
router.register(r'pieces', views.PieceViewSet)
router.register(r'companies', views.CompanyViewSet)
router.register(r'venues', views.VenueViewSet)
router.register(r'performances', views.PerformanceViewSet)
router.register(r'performance-performers', views.PerformancePerformerViewSet)
router.register(r'clip-performers', views.ClipPerformerViewSet)
router.register(r'custom-fields', views.CustomFieldViewSet)
router.register(r'custom-field-values', views.CustomFieldValueViewSet)

urlpatterns = [
    path('', views.homepage, name='homepage'),
    path('api/', include(router.urls)),
]
