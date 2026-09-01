import json
import logging
import re
import urllib.request
import urllib.error
from django.conf import settings

logger = logging.getLogger('accounts.sms')


def normalize_phone_number(phone: str) -> str:
    """
    Normalizes a phone number for the Arkesel SMS Gateway.
    - Strips spaces, dashes, brackets, and leading '+'
    - Converts standard local Ghana numbers (e.g. 024XXXXXXX, 050XXXXXXX) to 233XXXXXXXXX
    - Returns clean numeric string in international format.
    """
    if not phone:
        return ""

    # Remove non-digit characters except leading '+'
    clean = re.sub(r'[^\d+]', '', str(phone).strip())

    # Strip leading '+'
    if clean.startswith('+'):
        clean = clean[1:]

    # Handle Ghanaian local numbers starting with '0' (e.g., 024, 054, 050, 055, 059, 020, 027, 026)
    if clean.startswith('0') and len(clean) == 10:
        clean = '233' + clean[1:]

    return clean


def send_single_sms(phone: str, message: str, sender_id: str = None) -> tuple[bool, str]:
    """
    Sends an SMS via the Arkesel SMS Gateway (v2 API).
    
    API Endpoint: https://sms.arkesel.com/api/v2/sms/send
    Returns: (success: bool, response_message: str)
    """
    normalized_phone = normalize_phone_number(phone)
    if not normalized_phone:
        return False, "Invalid or missing phone number."

    api_key = getattr(settings, 'ARKESEL_API_KEY', '') or ''
    sender = sender_id or getattr(settings, 'ARKESEL_SENDER_ID', 'VoteApp') or 'VoteApp'

    # If no API key is configured, operate in Mock/Development Mode
    if not api_key or api_key.startswith('your_') or getattr(settings, 'SMS_MOCK_MODE', False):
        logger.info(
            f"[SMS MOCK DELIVERY] Sender: {sender} | To: {normalized_phone} | Message: {message}"
        )
        return True, f"Simulated SMS sent to {normalized_phone} (Mock Mode: configure ARKESEL_API_KEY for live delivery)."

    url = "https://sms.arkesel.com/api/v2/sms/send"
    payload = {
        "sender": sender,
        "message": message,
        "recipients": [normalized_phone]
    }

    try:
        data = json.dumps(payload).encode('utf-8')
        req = urllib.request.Request(
            url,
            data=data,
            headers={
                "api-key": api_key,
                "Content-Type": "application/json",
                "User-Agent": "VoteApp-SMS/1.0"
            },
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=12) as response:
            res_body = response.read().decode('utf-8')
            res_json = json.loads(res_body)

            # Arkesel v2 returns {"status": "success", ...} or {"status": "error", ...}
            status = res_json.get('status', '').lower()
            if status in ['success', 'successful']:
                logger.info(f"Arkesel SMS sent successfully to {normalized_phone}")
                return True, f"SMS delivered successfully to {normalized_phone}."
            else:
                error_msg = res_json.get('message', 'SMS delivery failed.')
                logger.warning(f"Arkesel SMS rejected for {normalized_phone}: {error_msg}")
                return False, f"Arkesel error: {error_msg}"

    except urllib.error.HTTPError as e:
        error_content = e.read().decode('utf-8', errors='ignore')
        logger.error(f"Arkesel HTTP Error {e.code}: {error_content}")
        try:
            err_json = json.loads(error_content)
            msg = err_json.get('message', f"HTTP {e.code}")
        except Exception:
            msg = f"HTTP Error {e.code}"
        return False, f"SMS failed ({msg})"
    except urllib.error.URLError as e:
        logger.error(f"Arkesel Network/Connection Error: {e.reason}")
        return False, f"Network error connecting to Arkesel: {e.reason}"
    except Exception as e:
        logger.exception(f"Unexpected error sending SMS to {normalized_phone}")
        return False, f"Failed to dispatch SMS: {str(e)}"


def send_voter_code_sms(voter, site_url: str = None) -> tuple[bool, str]:
    """
    Sends a voter their unique login code via SMS.
    """
    if not voter.phone:
        return False, f"No phone number on record for {voter.get_full_name() or voter.username}."

    if not voter.unique_code:
        return False, f"No unique voter code generated for {voter.get_full_name() or voter.username}."

    url = site_url or getattr(settings, 'SITE_URL', 'https://voting-app-wvk6.onrender.com')
    login_url = f"{url.rstrip('/')}/accounts/login/"
    voter_name = voter.first_name or voter.username

    message = (
        f"Hello {voter_name}, your unique login code for VoteApp is: {voter.unique_code}. "
        f"Cast your ballot at {login_url}. Keep this code confidential."
    )

    return send_single_sms(voter.phone, message)


def send_bulk_voter_code_sms(voters_queryset, site_url: str = None) -> dict:
    """
    Sends unique login codes in bulk to a queryset/list of voters.
    Returns:
        dict: {'total': int, 'sent': int, 'skipped': int, 'failed': int, 'errors': list}
    """
    results = {
        'total': len(voters_queryset) if hasattr(voters_queryset, '__len__') else voters_queryset.count(),
        'sent': 0,
        'skipped': 0,
        'failed': 0,
        'errors': []
    }

    url = site_url or getattr(settings, 'SITE_URL', 'https://voting-app-wvk6.onrender.com')

    for voter in voters_queryset:
        if not voter.phone:
            results['skipped'] += 1
            continue

        if not voter.unique_code:
            results['skipped'] += 1
            continue

        success, msg = send_voter_code_sms(voter, site_url=url)
        if success:
            results['sent'] += 1
        else:
            results['failed'] += 1
            results['errors'].append(f"{voter.username} ({voter.phone}): {msg}")

    return results
