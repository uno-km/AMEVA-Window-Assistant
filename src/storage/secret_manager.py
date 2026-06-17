import os
import keyring
from cryptography.fernet import Fernet
import base64
import logging

logger = logging.getLogger(__name__)

SERVICE_NAME = "AMEVA_Secure_Vault"
USER_NAME = "AMEVA_Master_Key"

class SecretManager:
    """
    Manages encrypted secrets using Windows DPAPI (via keyring) and Fernet symmetric encryption.
    The Master Key is securely stored in the OS Credential Manager.
    """
    def __init__(self):
        self._key = self._get_or_create_master_key()
        self._fernet = Fernet(self._key)

    def _get_or_create_master_key(self) -> bytes:
        """Retrieve the master key from the OS Credential Manager, or create it if missing."""
        try:
            key_str = keyring.get_password(SERVICE_NAME, USER_NAME)
            if not key_str:
                logger.info("No Master Key found in OS. Generating a new one...")
                key = Fernet.generate_key()
                keyring.set_password(SERVICE_NAME, USER_NAME, key.decode('utf-8'))
                return key
            return key_str.encode('utf-8')
        except Exception as e:
            logger.error(f"Failed to access Windows DPAPI via keyring: {e}")
            raise

    def encrypt(self, plain_text: str) -> str:
        """Encrypt a plain text secret."""
        if not plain_text:
            return ""
        return self._fernet.encrypt(plain_text.encode('utf-8')).decode('utf-8')

    def decrypt(self, encrypted_text: str) -> str:
        """Decrypt an encrypted secret."""
        if not encrypted_text:
            return ""
        try:
            return self._fernet.decrypt(encrypted_text.encode('utf-8')).decode('utf-8')
        except Exception as e:
            logger.error(f"Failed to decrypt secret. The Master Key might have changed. Error: {e}")
            return ""
