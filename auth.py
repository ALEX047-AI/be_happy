"""
Модуль аутентификации и шифровани.

- Хранит учетные данные пользователей в data/users.json  (username -> salt + password hash).
- Профиль и дневник каждого пользователя хранятся в data/users/<username>/  как зашифрованные блоки Fernet.
- Ключ шифрования получается из пароля с помощью PBKDF2 и никогда не записывается на диск.

Чтобы установить:
    pip install cryptography
"""

import os
import json
import base64
import hashlib
import secrets

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes

_KDF_ITERATIONS = 480_000


#  Помощники низшего уровня

def _derive_fernet_key(password: str, salt: bytes) -> bytes:
    """Получить 32-байтный ключ Fernet из *password* + *salt*."""
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=_KDF_ITERATIONS,
    )
    return base64.urlsafe_b64encode(kdf.derive(password.encode("utf-8")))


def _hash_password(password: str, salt: bytes) -> str:
    """Возвращает hex-encoded PBKDF2-SHA256 hash для хранения в users.json."""
    return hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt, _KDF_ITERATIONS
    ).hex()


#  Менеджер пользователей

class UserManager:
    """Управляет учетными записями пользователей и зашифрованными файлами данных для каждого пользователя."""

    PROFILE_ENC = "profile.enc"
    DIARY_ENC = "diary.enc"

    def __init__(self, data_dir: str = "data"):
        self.data_dir = data_dir
        self.users_file = os.path.join(data_dir, "users.json")
        self.users_data_dir = os.path.join(data_dir, "users")

        self._users: dict = self._load_users()
        self._current_user: str | None = None
        self._fernet: Fernet | None = None

#  постоянный список пользователей

    def _load_users(self) -> dict:
        if os.path.exists(self.users_file):
            try:
                with open(self.users_file, "r", encoding="utf-8") as fh:
                    return json.load(fh)
            except Exception:
                return {}
        return {}

    def _save_users(self):
        os.makedirs(os.path.dirname(self.users_file) or ".", exist_ok=True)
        with open(self.users_file, "w", encoding="utf-8") as fh:
            json.dump(self._users, fh, indent=2)

    #  публичный API: регистрация / авторизация

    def has_users(self) -> bool:
        return bool(self._users)

    def get_usernames(self) -> list[str]:
        return list(self._users.keys())

    def register(self, username: str, password: str) -> tuple[bool, str]:
        """Создать новый аккаунт. Возвращает (ok, message)."""
        username = username.strip()
        if not username:
            return False, "empty_username"
        if username in self._users:
            return False, "user_exists"
        if len(password) < 4:
            return False, "password_too_short"

        salt = secrets.token_bytes(16)
        self._users[username] = {
            "salt": base64.b64encode(salt).decode(),
            "password_hash": _hash_password(password, salt),
        }
        self._save_users()

        user_dir = os.path.join(self.users_data_dir, username)
        os.makedirs(user_dir, exist_ok=True)
        return True, "ok"

    def authenticate(self, username: str, password: str) -> bool:
        """Проверить учетные данные и установливает в памяти ключ шифрования."""
        username = username.strip()
        if username not in self._users:
            return False
        rec = self._users[username]
        salt = base64.b64decode(rec["salt"])
        if _hash_password(password, salt) != rec["password_hash"]:
            return False
        # всё хорошо -> сохранить ключ Fernet в оперативной памяти
        key = _derive_fernet_key(password, salt)
        self._fernet = Fernet(key)
        self._current_user = username
        return True

    def sign_out(self):
        """Забывает ключ шифрования."""
        self._current_user = None
        self._fernet = None

    @property
    def is_signed_in(self) -> bool:
        return self._current_user is not None

    @property
    def current_user(self) -> str | None:
        return self._current_user

    #  зашифрованные JSON-помощники

    def _user_dir(self) -> str:
        d = os.path.join(self.users_data_dir, self._current_user)  # type: ignore[arg-type]
        os.makedirs(d, exist_ok=True)
        return d

    def load_encrypted_json(self, filename: str, default):
        """Расшифровать filename внутри папки текущего пользователя -> Python объект."""
        if not self._fernet or not self._current_user:
            return default
        filepath = os.path.join(self._user_dir(), filename)
        if not os.path.exists(filepath):
            return default
        try:
            with open(filepath, "rb") as fh:
                encrypted = fh.read()
            decrypted = self._fernet.decrypt(encrypted)
            return json.loads(decrypted.decode("utf-8"))
        except (InvalidToken, Exception):
            return default

    def save_encrypted_json(self, filename: str, data) -> bool:
        """Зашифровывает data и записывает в файл filename внутри папки текущего пользователя."""
        if not self._fernet or not self._current_user:
            return False
        filepath = os.path.join(self._user_dir(), filename)
        try:
            raw = json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")
            encrypted = self._fernet.encrypt(raw)
            with open(filepath, "wb") as fh:
                fh.write(encrypted)
            return True
        except Exception:
            return False

    # удобные ярлыки, используемые в приложении
    def load_profile(self, default=None):
        return self.load_encrypted_json(self.PROFILE_ENC, default if default is not None else {})

    def save_profile(self, data) -> bool:
        return self.save_encrypted_json(self.PROFILE_ENC, data)

    def load_diary(self, default=None):
        return self.load_encrypted_json(self.DIARY_ENC, default if default is not None else {})

    def save_diary(self, data) -> bool:
        return self.save_encrypted_json(self.DIARY_ENC, data)
