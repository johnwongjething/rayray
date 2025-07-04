from cryptography.fernet import Fernet
import os

# Load or generate encryption key
ENCRYPTION_KEY = os.getenv('ENCRYPTION_KEY')
if not ENCRYPTION_KEY:
    ENCRYPTION_KEY = Fernet.generate_key()
    print(f"Generated new encryption key: {ENCRYPTION_KEY.decode()}")
else:
    if isinstance(ENCRYPTION_KEY, str):
        ENCRYPTION_KEY = ENCRYPTION_KEY.encode()

fernet = Fernet(ENCRYPTION_KEY)

def encrypt_payment_url(url: str) -> str:
    """
    Encrypt a payment URL using Fernet.
    Returns the encrypted token as a string.
    """
    if not url:
        return url
    try:
        token = fernet.encrypt(url.encode()).decode()
        return token
    except Exception as e:
        print(f"Encryption error: {e}")
        return url

def decrypt_payment_url(token: str) -> str:
    """
    Decrypt a Fernet-encrypted payment URL token.
    Returns the original URL as a string.
    """
    if not token:
        return token
    try:
        url = fernet.decrypt(token.encode()).decode()
        return url
    except Exception as e:
        print(f"Decryption error: {e}")
        return token