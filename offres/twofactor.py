"""Double authentification par code temporel (TOTP, RFC 6238).

Compatible avec Google Authenticator, Authy, Aegis et toute application
d'authentification TOTP. **Aucune donnee ne transite par un tiers** : le
secret partage ne quitte ni le telephone ni le serveur.

Le secret est stocke chiffre dans la base (AES-GCM via `cryptography`), ce
qui evite qu'une copie de la base reveals les codes d'acces. La cle de
chiffrement derive de `SECRET_KEY` : la changer invalide les codes, donc
elle ne doit pas tourner en production sans prevoyir une migration.
"""

import base64
import hashlib
import hmac
import logging
import secrets
import struct
import time

from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)

TOTP_DIGITS = 6
TOTP_PERIOD = 30
TOTP_WINDOW = 1  # tolerance d'une periode avant et apres

ISSUER = 'Faso Job'


def _encryption_key():
    """Derive une cle AES de 32 octets depuis la cle du projet."""
    digest = hashlib.sha256(settings.SECRET_KEY.encode('utf-8')).digest()
    return base64.urlsafe_b64encode(digest)


def _cipher():
    from cryptography.fernet import Fernet

    return Fernet(_encryption_key())


def generate_secret():
    """Genere un secret TOTP partage, en base32."""
    return base64.b32encode(secrets.token_bytes(20)).decode('ascii').rstrip('=')


def encrypt_secret(secret):
    """Chiffre un secret pour stockage."""
    return _cipher().encrypt(secret.encode('utf-8')).decode('ascii')


def decrypt_secret(encrypted):
    """Dechiffre un secret stocke."""
    return _cipher().decrypt(encrypted.encode('ascii')).decode('utf-8')


def _hotp(secret, counter, digits=TOTP_DIGITS):
    """Calcul HOTP (RFC 4226)."""
    key = base64.b32decode(secret + '=' * ((8 - len(secret) % 8) % 8))
    digest = hmac.new(key, struct.pack('>Q', counter), hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    code = struct.unpack('>I', digest[offset:offset + 4])[0] & 0x7FFFFFFF
    return str(code % (10 ** digits)).zfill(digits)


def current_code(secret, at=None):
    """Code TOTP valide a l'instant donne."""
    moment = at if at is not None else time.time()
    counter = int(moment // TOTP_PERIOD)
    return _hotp(secret, counter)


def verify_code(secret, code, at=None):
    """Verifie un code en tolerant une periode avant et apres.

    Renvoie True si le code est valide.
    """
    candidate = (code or '').strip().replace(' ', '')
    if not candidate.isdigit() or len(candidate) != TOTP_DIGITS:
        return False

    moment = at if at is not None else time.time()
    counter = int(moment // TOTP_PERIOD)
    for drift in range(-TOTP_WINDOW, TOTP_WINDOW + 1):
        if hmac.compare_digest(_hotp(secret, counter + drift), candidate):
            return True
    return False


def provisioning_uri(secret, account):
    """_URI otpauth:// utilise par les applications d'authentification."""
    import urllib.parse

    label = urllib.parse.quote(f'{ISSUER}:{account}')
    issuer = urllib.parse.quote(ISSUER)
    return (
        f'otpauth://totp/{label}?secret={secret}&issuer={issuer}'
        f'&digits={TOTP_DIGITS}&period={TOTP_PERIOD}'
    )


def qr_code_svg(uri):
    """Rend le QR code au format SVG, sans dependance graphique."""
    import io

    import qrcode
    import qrcode.image.svg

    image = qrcode.make(uri, image_factory=qrcode.image.svg.SvgPathImage)
    buffer = io.BytesIO()
    image.save(buffer)
    return buffer.getvalue().decode('utf-8')


def generate_recovery_codes(count=8):
    """Genere des codes de secours lisibles, a usage unique."""
    codes = []
    for _ in range(count):
        raw = secrets.token_bytes(5)
        codes.append('-'.join(
            base64.b32encode(raw[:5]).decode('ascii').rstrip('='),
        ))
    return codes


def hash_code(code):
    """Hache un code de secours pour stockage."""
    normalized = (code or '').strip().upper().replace('-', '')
    return hashlib.sha256(normalized.encode('utf-8')).hexdigest()


def user_has_two_factor(user):
    """Indique si un compte est protege par la double authentification."""
    if not user or not user.is_authenticated:
        return False
    return getattr(user, 'two_factor_device', None) is not None


def is_verified_for_session(user, session):
    """Indique si le code a deja ete verifie dans cette session."""
    if not user or not user.is_authenticated:
        return False
    return session.get('two_factor_verified_user_id') == user.pk
