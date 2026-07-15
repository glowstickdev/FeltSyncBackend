import requests


EXPO_PUSH_URL = 'https://exp.host/--/api/v2/push/send'
_BATCH_SIZE = 100


def send_expo_push(tokens: list, title: str, body: str, data: dict = None, category_id: str = None) -> dict:
    """
    POST batched push requests to Expo. Returns {sent, failed, skipped}.
    Deletes PushToken rows that come back DeviceNotRegistered.
    """
    from .models import PushToken

    valid = [t for t in tokens if t.startswith('ExponentPushToken[')]
    skipped = len(tokens) - len(valid)
    sent = failed = 0

    for i in range(0, len(valid), _BATCH_SIZE):
        batch = valid[i:i + _BATCH_SIZE]
        base = {
            'to': None,
            'title': title,
            'body': body,
            'data': data or {},
            'channelId': 'default',
            'sound': 'default',
            'priority': 'high',
        }
        if category_id:
            base['categoryId'] = category_id
        messages = [{**base, 'to': t} for t in batch]
        try:
            resp = requests.post(EXPO_PUSH_URL, json=messages, timeout=15)
            resp.raise_for_status()
            tickets = resp.json().get('data', [])
            for j, ticket in enumerate(tickets):
                if ticket.get('status') == 'error':
                    if ticket.get('details', {}).get('error') == 'DeviceNotRegistered':
                        PushToken.objects.filter(token=batch[j]).delete()
                    failed += 1
                else:
                    sent += 1
        except Exception:
            failed += len(batch)

    return {'sent': sent, 'failed': failed, 'skipped': skipped}
