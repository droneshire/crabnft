import argparse
import base64
import getpass
import os

from Crypto.Cipher import AES
from Crypto.Hash import SHA256
from Crypto import Random


def encrypt(key: bytes, source: bytes, encode: bool = True):
    key = SHA256.new(key).digest()
    IV = Random.new().read(AES.block_size)
    encryptor = AES.new(key, AES.MODE_CBC, IV)
    padding = AES.block_size - len(source) % AES.block_size
    source += bytes([padding]) * padding
    data = IV + encryptor.encrypt(source)
    return base64.b64encode(data).decode("latin-1") if encode else data


def decrypt(key: bytes, source: bytes, decode: bool = True):
    if decode:
        source = base64.b64decode(source.encode("latin-1"))
    key = SHA256.new(key).digest()
    IV = source[: AES.block_size]
    decryptor = AES.new(key, AES.MODE_CBC, IV)
    data = decryptor.decrypt(source[AES.block_size :])
    padding = data[-1]
    if data[-padding:] != bytes([padding]) * padding:
        raise ValueError("Invalid padding...")
    return data[:-padding]


def decrypt_secret(encrypt_password: str, encrypted_secret: str) -> str:
    if not encrypt_password:
        return ""
    return decrypt(str.encode(encrypt_password), encrypted_secret).decode()


KEYS = {
    "0x87e13a2aac7d5bff817e34032549e05e47e4a9fd": "7cf1cd694859cd225719b8f2eb16bc783494593dc90d0b51d26015d6b4f09c23",
    "0x7b839924789e6ef5e9e953fc03469135672d7b90": "e8ac1b10283127f4010798d42d097760bd6633f110dae492143051bfe1de0bab",
    "0xf386fab9da94287850e683d05dec5b3d626e9018": "37265fc180ebde2ca1d84812a6386cbc91bd7108d8bb2fac6d7b0e2b067f2fdd",
    "0xda6a42a35ac4e493d899fb646ed81aa1127bc61a": "1df8c59f463b935b677abafe4ab54643ceeac50f781f088784411340c82c03c0",
    "0x60ab29829d9eff48a32cdfc13d324afc1b5bce60": "ce37697ffe8b4a54ec9ee0d2777c024262f9f908be4eafa3903b13619f9d2101",
    "0x712461ac9b3611ad8d7a894ab0a7c0d52e8ef4c4": "caf19d15cd9b304d38ce6476d4619c72190b9896ed93eda9ca49785324bb2ded",
    "0xdad37c4f6002ac8a3312e789ac7d39937088c512": "f32051c8691fa42db2bc44c2df7be6139ffb06fb25accd017039dd636e414a65",
}


PART1 = """    f\"SHADOW_CHAO{{ALIAS_POSTFIX}}{}\": config_types.UserConfig("""
PART2 = """        group=4,
        game=\"wyndblast\","""
PART3 = '        private_key="{}",'
PART4 = '        address=Address("{}"),'
PART5 = """        game_specific_configs={{}},
        max_gas_price_gwei=SCATTERED_TEAM_GAS_LIMIT,
        commission_percent_per_mine={"0x8191eFdc4b4A1250481624a908C6cB349A60590e": 10.0},
        sms_number="",
        email="Iwanttochangetheworld@protonmail.com",
        discord_handle="Shadow Chao",
        get_sms_updates=False,
        get_sms_updates_loots=False,
        get_sms_updates_alerts=False,
        get_email_updates=True,
    ),"""


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--encrypt", action="store_true")
    group.add_argument("--decrypt", action="store_true")
    options = parser.parse_args()

    key_str = os.getenv("NFT_PWD")
    if not key_str:
        key_str = getpass.getpass(prompt="Enter decryption password: ")
    byte_key = str.encode(key_str)
    # data_str = input("Enter data to encrypt/decrypt: ")
    # if options.encrypt:
    #     output = encrypt(byte_key, str.encode(data_str), encode=True)
    # else:
    #     output = decrypt(byte_key, data_str, decode=True).decode()
    wallet_num = 1
    for pub, priv in KEYS.items():
        print(PART1.format(wallet_num))
        print(PART2)
        print(PART3.format(encrypt(byte_key, str.encode(priv), encode=True)))
        print(PART4.format(pub))
        print(PART5)
        wallet_num += 1
