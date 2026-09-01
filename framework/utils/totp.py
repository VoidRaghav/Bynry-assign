import pyotp


def code_for(secret):
    if not secret:
        raise ValueError("a 2FA challenge appeared but no TOTP secret is configured for this user")
    return pyotp.TOTP(secret).now()
