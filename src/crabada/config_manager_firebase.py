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
from crabada.types import MineOption
from crabada.config_manager import ConfigManager
from utils import logger
from utils.config_types import UserConfig
from utils.email import Email, send_email
from utils.user import BETA_TEST_LIST


class ConfigManagerFirebase(ConfigManager):
    LOOTING_GROUP_NUM = 10

    def __init__(
        self,
        user: str,
        config: UserConfig,
        send_email_accounts: T.List[Email],
        encrypt_password: str,
        dry_run: bool = False,
    ):
        super().__init__(user, config, send_email_accounts, encrypt_password, dry_run)
        this_dir = os.path.dirname(os.path.realpath(__file__))
        creds_dir = os.path.dirname(this_dir)
        credentials_file = os.path.join(creds_dir, "firebase_credentials.json")
        if not firebase_admin._apps:
            auth = credentials.Certificate(credentials_file)
            firebase_admin.initialize_app(auth)
        self.db = firestore.client()
        self.users_ref = self.db.collection("users")
        self.user_doc = self._get_user_document(self.config)

    def init(self) -> None:
        self._print_out_config()
        self._send_email_config_if_needed()
        self._save_config()

    def check_for_config_updates(self) -> None:
        if self.user not in BETA_TEST_LIST:
            return

        db_config = self.user_doc.get().to_dict()

        new_config: UserConfig = self._get_empty_new_config()

        logger.print_ok_blue(f"Checking database for preferences changes...")
        new_config["email"] = db_config["preferences"]["notifications"]["email"]["email"]
        new_config["get_email_updates"] = db_config["preferences"]["notifications"]["email"][
            "updatesEnabled"
        ]
        new_config["sms_number"] = (
            "+1" + db_config["preferences"]["notifications"]["sms"]["phoneNumber"]
        )

        logger.print_ok_blue(f"Checking database for strategy setting changes...")
        new_config["should_reinforce"] = db_config["strategy"]["reinforceEnabled"]
        new_config["max_gas_price_gwei"] = db_config["strategy"]["maxGas"]
        new_config["max_reinforcement_price_tus"] = db_config["strategy"]["maxReinforcement"]

        count = {
            "teams": {
                MineOption.MINE: 0,
                MineOption.LOOT: 0,
            },
            "crabs": {
                MineOption.MINE: 0,
                MineOption.LOOT: 0,
            },
        }

        logger.print_ok_blue(f"Checking database for team changes...")

        for team, details in db_config["strategy"]["teams"].items():
            team_id = int(team)
            if details["action"] == "MINING":
                group = int((count["teams"][MineOption.MINE] + 6) / 6)
                count["teams"][MineOption.MINE] += 1
                new_config["mining_teams"][team_id] = group
            elif details["action"] == "LOOTING":
                count["teams"][MineOption.LOOT] += 1
                group = self.LOOTING_GROUP_NUM
                new_config["looting_teams"][team_id] = group
            else:
                logger.print_fail(f"Unknown action from teams!")

            logger.print_normal(
                f"Team: {team_id}, Composition: {', '.join(details['composition'])}, Group: {group}"
            )

        logger.print_ok_blue(f"Checking database for reinforcement crab changes...")

        group = 1
        for crab_id, details in db_config["strategy"]["reinforcingCrabs"].items():
            if details["action"] == "MINING":
                # assign 2 crabs for every group
                if count["crabs"][MineOption.MINE] % 2 == 0:
                    group += 1
                count["crabs"][MineOption.MINE] += 1
                new_config["reinforcing_crabs"][crab_id] = group
            elif details["action"] == "LOOTING":
                count["crabs"][MineOption.LOOT] += 1
                new_config["reinforcing_crabs"][crab_id] = self.LOOTING_GROUP_NUM
            else:
                logger.print_fail(f"Unknown action from reinforcingCrabs!")

        diff = deepdiff.DeepDiff(self.config, new_config, ignore_order=True)
        if diff:
            logger.print_ok_blue(f"Detected changes in config from firebase database")
            logger.print_normal(f"{diff}")
            self.config = copy.deepcopy(new_config)
            logger.print_normal(f"Saving new config to disk")
            self._save_config()

    def _get_user_document(self, config: UserConfig) -> T.Optional[T.Any]:
        db_setup = {}
        for doc in self.users_ref.stream():
            db_setup[doc.id] = doc.to_dict()

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
            return self.users_ref.document(email)
        else:
            return None

    def update_all_users_from_local_config(self) -> None:
        for user, config in USERS.items():
            doc = self._get_user_document(config)
            if doc is not None:
                db_config = doc.get().to_dict()
                logger.print_ok(f"Found email: {config['email']}")
                db_config["preferences"] = {
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
                db_config["strategy"] = {
                    "reinforceEnabled": config["should_reinforce"],
                    "reinforcingCrabs": {},
                    "teams": {},
                    "maxReinforcement": config["max_reinforcement_price_tus"],
                    "maxGas": config["max_gas_price_gwei"],
                }

                for team, _ in config["mining_teams"].items():
                    composition = self._get_team_composition(team, config)
                    db_config["strategy"]["teams"][team] = {
                        "action": "MINING",
                        "composition": [c.strip() for c in composition.split(",")],
                    }

                for team, _ in config["looting_teams"].items():
                    composition = self._get_team_composition(team, config)
                    db_config["strategy"]["teams"][team] = {
                        "action": "LOOTING",
                        "composition": [c.strip() for c in composition.split(",")],
                    }

                for crab, group in config["reinforcing_crabs"].items():
                    action = "MINING" if group < 10 else "LOOTING"
                    crab_class = self.crab_classes.get(crab, self._get_crab_class(crab, config))
                    db_config["strategy"]["reinforcingCrabs"][crab] = {
                        "action": action,
                        "class": [crab_class.strip()],
                    }

                logger.print_normal(f"{json.dumps(db_config, indent=4)}")
                doc.set(json.loads(json.dumps(db_config)))
