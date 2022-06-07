import getpass

from config import USERS
from utils import logger
from utils.security import decrypt_secret
from wyndblast.wyndblast_web2_client import WyndblastWeb2Client

test_user = USERS["ROSS"]

logger.print_normal(f"Starting...")

encrypt_password = getpass.getpass(prompt="Enter decryption password: ")
private_key = decrypt_secret(encrypt_password, test_user["private_key"])

wynd_w2 = WyndblastWeb2Client(private_key, test_user["address"])
wynd_w2.authorize_user()
wynd_w2.update_account()
