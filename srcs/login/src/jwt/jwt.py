import os
import hashlib
import json
import hmac

from encoder import Base64Encoder


class JWT:
    class InvalidJwtTokenError(Exception):
        def __init__(self):
            super().__init__('Invalid JWT Token')

    def __init__(self, payload: dict) -> None:
        headers = {
            "alg": "HS256",
            "typ": "JWT"
        }
        self.headers = Base64Encoder.encode(json.dumps(headers).encode('utf-8'))
        self.payload = Base64Encoder.encode(json.dumps(payload).encode('utf-8'))
        self.__secret = os.getenv('JWT_SECRET')
        self.signature = self.create_signature(self.__secret)
        self.all = self.headers + b'.' + self.payload + b'.' + self.signature
        self.all = self.all.decode('utf-8')

    def __str__(self) -> str:
        return self.all

    def create_signature(self, secret: str) -> str:
        signature = hmac.new(secret.encode('utf-8'), self.headers + b'.' + self.payload, hashlib.sha256)
        signature = Base64Encoder.encode(signature.digest())
        return signature

    @staticmethod
    def decode_jwt(jwt_token: str):
        encoded_header, encoded_payload, encoded_signature = jwt_token.split('.')

        header = json.loads(Base64Encoder.decode(encoded_header).decode('utf-8'))
        payload = json.loads(Base64Encoder.decode(encoded_payload).decode('utf-8'))
        signature = Base64Encoder.decode(encoded_signature)
        secret = os.getenv('JWT_SECRET')

        expected_signature = hmac.new(
            secret.encode('utf-8'), encoded_header.encode('utf-8') + b'.'
            + encoded_payload.encode('utf-8'), hashlib.sha256
        )
        if not hmac.compare_digest(signature, expected_signature.digest()):
            raise JWT.InvalidJwtTokenError()

        return payload


"""
If you are using this to test my JWT class, please do not forget to export the 'JWT_TOKEN' environment var
"""

myjwt = JWT({
    "sub": "testing stuff",
    "name": "ft_transcendence user",
    "iat": 2024
})
token = str(myjwt)
print(token)
print(JWT.decode_jwt(token))
