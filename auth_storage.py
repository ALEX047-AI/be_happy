from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import threading
from dataclasses import dataclass
from typing import Any

try:
    from cryptography.fernet import Fernet, InvalidToken
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    _CRYPTO_OK = True
    _CRYPTO_IMPORT_ERROR = None
except Exception as _e:   # pragma: no cover - зависит от среды выполнения
    Fernet = None
    InvalidToken = Exception
    PBKDF2HMAC = None
    hashes = None
    _CRYPTO_OK = False
    _CRYPTO_IMPORT_ERROR = _e


class AuthError(Exception):
    pass


class CryptoUnavailable(AuthError):
    pass


class InvalidCredentials(AuthError):
    pass


class UserAlreadyExists(AuthError):
    pass


class UserNotFound(AuthError):
    pass


class NotSignedIn(AuthError):
    pass


@dataclass
class SessionInfo:
    username: str
    normalized_username: str
    user_id: str


class AuthStorage:
    """
    Лёгкая система аутентификации + хранилище зашифрованных данных в формате JSON.

    - В файле пользователей хранятся только хэши паролей и метаданные для вывода ключа
    - Профиль и дневник шифруются с помощью ключа Fernet, выведенного из пароля пользователя
    - Пароль в виде обычного текста никогда не записывается на диск
    """

    USERS_FILE_VERSION = 1
    DATA_FILE_VERSION = 1

    # Проверка пароля через KDF (stdlib, без дополнительных зависимостей)
    SCRYPT_N = 2 ** 14
    SCRYPT_R = 8
    SCRYPT_P = 1
    SCRYPT_DKLEN = 32

    # Генерация ключа шифрования (один стабильный на сессию пользователя)
    ENC_PBKDF2_ITERATIONS = 480_000
    ENC_KEY_LEN = 32

    def __init__(self, data_dir: str = "data"):
        self.data_dir = data_dir
        self.auth_dir = os.path.join(self.data_dir, "auth")
        self.users_dir = os.path.join(self.data_dir, "users")
        self.users_file = os.path.join(self.auth_dir, "users.json")
        self._lock = threading.RLock()
        self._session: SessionInfo | None = None
        self._fernet: Fernet | None = None
        self._ensure_dirs()

    def _ensure_crypto(self) -> None:
        if not _CRYPTO_OK:
            raise CryptoUnavailable(
                "Пакет 'cryptography' необходим для зашифрованного хранилища. "
                "Установите его с помощью: pip install cryptography"
            ) from _CRYPTO_IMPORT_ERROR

    def _ensure_dirs(self) -> None:
        os.makedirs(self.data_dir, exist_ok=True)
        os.makedirs(self.auth_dir, exist_ok=True)
        os.makedirs(self.users_dir, exist_ok=True)

    @staticmethod
    def normalize_username(username: str) -> str:
        value = (username or "").strip()
        return " ".join(value.split()).casefold()

    @staticmethod
    def _b64e(data: bytes) -> str:
        return base64.b64encode(data).decode("ascii")

    @staticmethod
    def _b64d(data: str) -> bytes:
        return base64.b64decode(data.encode("ascii"))

    def _read_users_doc(self) -> dict[str, Any]:
        self._ensure_dirs()
        if not os.path.exists(self.users_file):
            return {"version": self.USERS_FILE_VERSION, "users": {}}
        try:
            with open(self.users_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, dict):
                raise ValueError("users.json должен содержать JSON объект")
            data.setdefault("version", self.USERS_FILE_VERSION)
            data.setdefault("users", {})
            if not isinstance(data["users"], dict):
                data["users"] = {}
            return data
        except Exception:
            # не перезаписываtn нечитаемый файл
            raise AuthError(f"Не удалось прочитать файл пользователей: {self.users_file}")

    def _write_users_doc(self, doc: dict[str, Any]) -> None:
        self._ensure_dirs()
        tmp = f"{self.users_file}.tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(doc, f, ensure_ascii=False, indent=2)
        os.replace(tmp, self.users_file)

    def has_any_user(self) -> bool:
        with self._lock:
            doc = self._read_users_doc()
            return bool(doc.get("users"))

    def current_user(self) -> str | None:
        return self._session.username if self._session else None

    def is_signed_in(self) -> bool:
        return self._session is not None and self._fernet is not None

    def _user_id(self, normalized_username: str) -> str:
        return hashlib.sha256(normalized_username.encode("utf-8")).hexdigest()[:24]

    def _user_entry(self, username: str) -> tuple[str, dict[str, Any] | None, dict[str, Any]]:
        norm = self.normalize_username(username)
        doc = self._read_users_doc()
        return norm, doc.get("users", {}).get(norm), doc

    def _user_folder(self, user_id: str) -> str:
        return os.path.join(self.users_dir, user_id)

    def _profile_path(self, user_id: str) -> str:
        return os.path.join(self._user_folder(user_id), "profile.enc")

    def _diary_path(self, user_id: str) -> str:
        return os.path.join(self._user_folder(user_id), "diary.enc")

    def user_exists(self, username: str) -> bool:
        with self._lock:
            _, entry, _ = self._user_entry(username)
            return entry is not None

    def legacy_plaintext_exists(self, profile_path: str, diary_path: str) -> bool:
        return os.path.exists(profile_path) or os.path.exists(diary_path)

    def _hash_password(self, password: str, salt: bytes) -> bytes:
        pwd = (password or "").encode("utf-8")
        return hashlib.scrypt(
            pwd,
            salt=salt,
            n=self.SCRYPT_N,
            r=self.SCRYPT_R,
            p=self.SCRYPT_P,
            dklen=self.SCRYPT_DKLEN,
        )

    def _derive_fernet_key(self, password: str, enc_salt: bytes, iterations: int) -> bytes:
        self._ensure_crypto()
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=self.ENC_KEY_LEN,
            salt=enc_salt,
            iterations=int(iterations),
        )
        key = kdf.derive((password or "").encode("utf-8"))
        return base64.urlsafe_b64encode(key)

    def _entry_to_fernet(self, entry: dict[str, Any], password: str) -> Fernet:
        enc = entry.get("enc", {})
        enc_salt = self._b64d(enc["salt"])
        iterations = int(enc.get("iterations", self.ENC_PBKDF2_ITERATIONS))
        key = self._derive_fernet_key(password, enc_salt, iterations)
        return Fernet(key)

    def register_user(
        self,
        username: str,
        password: str,
        *,
        profile_data: Any | None = None,
        diary_data: Any | None = None,
    ) -> None:
        with self._lock:
            self._ensure_crypto()
            username = (username or "").strip()
            if not username:
                raise AuthError("Имя пользователя не может быть пустым")
            if not password:
                raise AuthError("Пароль не может быть пустым")

            norm = self.normalize_username(username)
            doc = self._read_users_doc()
            users = doc.setdefault("users", {})
            if norm in users:
                raise UserAlreadyExists(username)

            pwd_salt = os.urandom(16)
            enc_salt = os.urandom(16)
            pwd_hash = self._hash_password(password, pwd_salt)
            user_id = self._user_id(norm)

            entry = {
                "username": username,
                "user_id": user_id,
                "pwd": {
                    "algo": "scrypt",
                    "salt": self._b64e(pwd_salt),
                    "hash": self._b64e(pwd_hash),
                    "n": self.SCRYPT_N,
                    "r": self.SCRYPT_R,
                    "p": self.SCRYPT_P,
                    "dklen": self.SCRYPT_DKLEN,
                },
                "enc": {
                    "algo": "fernet-pbkdf2-sha256",
                    "salt": self._b64e(enc_salt),
                    "iterations": self.ENC_PBKDF2_ITERATIONS,
                },
            }
            users[norm] = entry
            self._write_users_doc(doc)

            os.makedirs(self._user_folder(user_id), exist_ok=True)
            fernet = self._entry_to_fernet(entry, password)
            self._write_encrypted_json(self._profile_path(user_id), profile_data if profile_data is not None else {}, fernet)
            self._write_encrypted_json(self._diary_path(user_id), diary_data if diary_data is not None else {}, fernet)

    def sign_in(self, username: str, password: str) -> None:
        with self._lock:
            self._ensure_crypto()
            norm, entry, _doc = self._user_entry(username)
            if entry is None:
                raise UserNotFound(username)

            pwd = entry.get("pwd", {})
            salt = self._b64d(pwd["salt"])
            expected = self._b64d(pwd["hash"])
            actual = hashlib.scrypt(
                (password or "").encode("utf-8"),
                salt=salt,
                n=int(pwd.get("n", self.SCRYPT_N)),
                r=int(pwd.get("r", self.SCRYPT_R)),
                p=int(pwd.get("p", self.SCRYPT_P)),
                dklen=int(pwd.get("dklen", self.SCRYPT_DKLEN)),
            )
            if not hmac.compare_digest(actual, expected):
                raise InvalidCredentials("Неверное имя пользователя или пароль")

            self._fernet = self._entry_to_fernet(entry, password)
            self._session = SessionInfo(
                username=entry.get("username", username),
                normalized_username=norm,
                user_id=entry["user_id"],
            )

    def sign_out(self) -> None:
        with self._lock:
            self._fernet = None
            self._session = None

    def _require_session(self) -> tuple[SessionInfo, Fernet]:
        if self._session is None or self._fernet is None:
            raise NotSignedIn("Нет пользователя, который сейчас вошел в систему")
        return self._session, self._fernet

    def _write_encrypted_json(self, path: str, data: Any, fernet: Fernet) -> None:
        payload = json.dumps(data, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        token = fernet.encrypt(payload).decode("ascii")
        doc = {
            "version": self.DATA_FILE_VERSION,
            "algo": "fernet",
            "token": token,
        }
        os.makedirs(os.path.dirname(path), exist_ok=True)
        tmp = f"{path}.tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(doc, f, ensure_ascii=False, indent=2)
        os.replace(tmp, path)

    def _read_encrypted_json(self, path: str, default: Any, fernet: Fernet) -> Any:
        if not os.path.exists(path):
            return default
        try:
            with open(path, "r", encoding="utf-8") as f:
                doc = json.load(f)
            token = doc["token"].encode("ascii")
            raw = fernet.decrypt(token)
            return json.loads(raw.decode("utf-8"))
        except InvalidToken as e:
            raise InvalidCredentials("Неверное имя пользователя или пароль") from e
        except Exception as e:
            raise AuthError(f"Не удалось расшифровать файл: {path}") from e

    def load_profile(self, default: Any | None = None) -> Any:
        default = {} if default is None else default
        with self._lock:
            session, fernet = self._require_session()
            return self._read_encrypted_json(self._profile_path(session.user_id), default, fernet)

    def save_profile(self, profile_data: Any) -> None:
        with self._lock:
            session, fernet = self._require_session()
            self._write_encrypted_json(self._profile_path(session.user_id), profile_data, fernet)

    def load_diary(self, default: Any | None = None) -> Any:
        default = {} if default is None else default
        with self._lock:
            session, fernet = self._require_session()
            return self._read_encrypted_json(self._diary_path(session.user_id), default, fernet)

    def save_diary(self, diary_data: Any) -> None:
        with self._lock:
            session, fernet = self._require_session()
            self._write_encrypted_json(self._diary_path(session.user_id), diary_data, fernet)


# Общий синглтон, используемый приложением
_auth_data_dir = os.environ.get("TD_APP_DATA_DIR", "data")
auth_manager = AuthStorage(data_dir=_auth_data_dir)
