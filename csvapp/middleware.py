from .themes import THEMES


class ThemeMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if 'text/html' not in response.get('Content-Type', ''):
            return response
        if not hasattr(response, 'content'):
            return response

        from .models import SiteSettings
        theme = SiteSettings.get().theme
        css = THEMES.get(theme, '')
        if not css:
            return response

        content = response.content.decode('utf-8')
        if '</head>' in content:
            content = content.replace('</head>', f'<style>{css}</style></head>', 1)
            response.content = content.encode('utf-8')
        return response
