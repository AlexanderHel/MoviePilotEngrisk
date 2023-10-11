import base64
import hashlib
import hmac
import json
import os
from datetime import datetime, timedelta
from typing import Any, Union, Optional
import jwt
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad
from fastapi import HTTPException, status, Depends
from fastapi.security import OAuth2PasswordBearer
from passlib.context import CryptContext

from app import schemas
from app.core.config import settings
from cryptography.fernet import Fernet

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
ALGORITHM = "HS256"

# Token Accreditation
reusable_oauth2 = OAuth2PasswordBearer(
    tokenUrl=f"{settings.API_V1_STR}/login/access-token"
)


def create_access_token(
        subject: Union[str, Any], expires_delta: timedelta = None
) -> str:
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(
            minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
        )
    to_encode = {"exp": expire, "sub": str(subject)}
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def verify_token(token: str = Depends(reusable_oauth2)) -> schemas.TokenPayload:
    try:
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[ALGORITHM]
        )
        return schemas.TokenPayload(**payload)
    except (jwt.DecodeError, jwt.InvalidTokenError, jwt.ImmatureSignatureError):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="token Failed calibration",
        )


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


def decrypt(data: bytes, key: bytes) -> Optional[bytes]:
    """
    Decrypt binary data
    """
    fernet = Fernet(key)
    try:
        return fernet.decrypt(data)
    except Exception as e:
        print(str(e))
        return None


def encrypt_message(message: str, key: bytes):
    """
    Use the givenkey Encrypting messages， And returns the encrypted string
    """
    f = Fernet(key)
    encrypted_message = f.encrypt(message.encode())
    return encrypted_message.decode()


def hash_sha256(message):
    """
    Dohash (mathematical) operation
    """
    return hashlib.sha256(message.encode()).hexdigest()


def aes_decrypt(data, key):
    """
    AES Declassification
    """
    if not data:
        return ""
    data = base64.b64decode(data)
    iv = data[:16]
    encrypted = data[16:]
    #  UtilizationAES-256-CBC Declassification
    cipher = AES.new(key.encode('utf-8'), AES.MODE_CBC, iv)
    result = cipher.decrypt(encrypted)
    #  Remove fill
    padding = result[-1]
    if padding < 1 or padding > AES.block_size:
        return ""
    result = result[:-padding]
    return result.decode('utf-8')


def aes_encrypt(data, key):
    """
    AES Encrypted
    """
    if not data:
        return ""
    #  UtilizationAES-256-CBC Encrypted
    cipher = AES.new(key.encode('utf-8'), AES.MODE_CBC)
    #  Padding
    padding = AES.block_size - len(data) % AES.block_size
    data += chr(padding) * padding
    result = cipher.encrypt(data.encode('utf-8'))
    #  Utilizationbase64 Encodings
    return base64.b64encode(cipher.iv + result).decode('utf-8')


def nexusphp_encrypt(data_str: str, key):
    """
    NexusPHP Encrypted
    """
    #  Generating16 Byte-long random string
    iv = os.urandom(16)
    #  Evaluate a vector Base64  Encodings
    iv_base64 = base64.b64encode(iv)
    #  Encrypted data
    cipher = AES.new(key, AES.MODE_CBC, iv)
    ciphertext = cipher.encrypt(pad(data_str.encode(), AES.block_size))
    ciphertext_base64 = base64.b64encode(ciphertext)
    #  Sign the string representation of a vector
    mac = hmac.new(key, msg=iv_base64 + ciphertext_base64, digestmod=hashlib.sha256).hexdigest()
    #  Tectonic (geology) JSON  String (computer science)
    json_str = json.dumps({
        'iv': iv_base64.decode(),
        'value': ciphertext_base64.decode(),
        'mac': mac,
        'tag': ''
    })

    #  Treat (sb a certain way) JSON  String Base64  Encodings
    return base64.b64encode(json_str.encode()).decode()
