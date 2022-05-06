import copy
import deepdiff
import firebase_admin
import json
import os
import time
import typing as T

from firebase_admin import firestore
from firebase_admin import credentials

from config import USERS
from crabada.config_manager import ConfigManager
from utils import logger
from utils.config_types import UserConfig
from utils.email import Email, send_email


class ConfigManagerFirebase(ConfigManager):
    def __init__(
        self,
        user: str,
        config: UserConfig,
        send_email_accounts: T.List[Email],
        dry_run: bool = False,
    ):
        super().__init__(user, config, send_email_accounts, dry_run)
        this_dir = os.path.dirname(os.path.realpath(__file__))
        creds_dir = os.path.dirname(this_dir)
        credentials_file = os.path.join(creds_dir, "firebase_credentials.json")
        auth = credentials.Certificate(credentials_file)
        self.app = firebase_admin.initialize_app(auth)
        self.db = firestore.client()
        self.users_ref = self.db.collection("users")
        self.user_doc = self._get_user_document()

    def init(self) -> None:
        self._print_out_config()

        if self.user_doc is None:
            self._load_config()

        self._send_email_config_if_needed()
        self._save_config()
        self._update_config_from_database()

    # def check_for_config_updates(self) -> None:

    # def _read_database(self) -> None:

    def _get_user_document(self) -> T.Optional[T.Any]:
        db_setup = {}
        for doc in self.users_ref.stream():
            db_setup[doc.id] = doc.to_dict()

        email = self.config["email"].lower()
        for db_email, db_config in db_setup.items():
            try:
                notification_email = db_config["preferences"]["notifications"]["email"][
                    "email"
                ].lower()
            except:
                continue

            if notification_email == email:
                email = db_email.lower()
                break

        if self.config["email"].lower() in db_setup or notification_email == self.config["email"].lower():
            return self.users_ref.document(email)
        else:
            return None


    def update_all_users_from_local_config(self) -> None:
        db_setup = {}
        for doc in self.users_ref.stream():
            db_setup[doc.id] = doc.to_dict()

        for user, config in USERS.items():
            email = config["email"].lower()
            for db_email, db_config in db_setup.items():
                try:
                    notification_email = db_config["preferences"]["notifications"]["email"][
                        "email"
                    ].lower()
                except:
                    continue

                if notification_email == email:
                    email = db_email.lower()
                    break

            if config["email"].lower() in db_setup or notification_email == config["email"].lower():
                logger.print_ok(f"Found email: {email}")
                db_setup[email]["preferences"] = {
                    "notifications": {
                        "email": {
                            "updatesEnabled": config["get_email_updates"],
                            "email": config["email"],
                        },
                        "sms": {
                            "lootUpdatesEnabled": config["get_sms_updates_loots"],
                            "phoneNumber": config["sms_number"].lstrip("+1"),
                            "alertUpdatesEnabled": config["get_sms_updates"],
                        },
                    }
                }
                db_setup[email]["strategy"] = {
                    "reinforceEnabled": config["should_reinforce"],
                    "reinforcingCrabs": {},
                    "teams": {},
                    "maxReinforcement": config["max_reinforcement_price_tus"],
                    "maxGas": config["max_gas_price_gwei"],
                }

                for team, _ in config["mining_teams"].items():
                    composition = self._get_team_composition(team, config)
                    db_setup[email]["strategy"]["teams"][team] = {
                        "action": "MINING",
                        "composition": [c.strip() for c in composition.split(",")],
                    }

                for team, _ in config["looting_teams"].items():
                    composition = self._get_team_composition(team, config)
                    db_setup[email]["strategy"]["teams"][team] = {
                        "action": "LOOTING",
                        "composition": [c.strip() for c in composition.split(",")],
                    }

                for crab, group in config["reinforcing_crabs"].items():
                    action = "MINING" if group < 10 else "LOOTING"
                    crab_class = self.crab_classes.get(crab, self._get_crab_class(crab))
                    db_setup[email]["strategy"]["reinforcingCrabs"][crab] = {
                        "action": action,
                        "class": [crab_class.strip()],
                    }

                logger.print_normal(f"{json.dumps(db_setup[email], indent=4)}")
                self.users_ref.document(email).set(json.loads(json.dumps(db_setup[email])))
