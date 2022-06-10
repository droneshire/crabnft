import getpass

from config_wyndblast import USERS
from utils import logger
from utils.security import decrypt_secret
from wyndblast.daily_activities import DailyActivitiesGame
from wyndblast.wyndblast_web2_client import WyndblastWeb2Client

encrypt_password = getpass.getpass(prompt="Enter decryption password: ")

for user, info in USERS.items():
    logger.print_normal(f"\nStarting for user {user}...")

    private_key = decrypt_secret(encrypt_password, info["private_key"])

    wynd_w2 = WyndblastWeb2Client(private_key, info["address"])
    wynd_w2.authorize_user()
    wynd_w2.update_account()
    daily_activities = DailyActivitiesGame(wynd_w2)
    daily_activities.run_activity()
