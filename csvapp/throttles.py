from rest_framework.throttling import AnonRateThrottle


class LoginRateThrottle(AnonRateThrottle):
    scope = 'auth_login'


class RegisterRateThrottle(AnonRateThrottle):
    scope = 'auth_register'


class SocialAuthRateThrottle(AnonRateThrottle):
    scope = 'auth_social'


class RefreshRateThrottle(AnonRateThrottle):
    scope = 'auth_refresh'
