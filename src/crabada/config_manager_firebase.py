import copy
import deepdiff
import firebase_admin
import inflection
import json
import os
import time
import typing as T

from firebase_admin import firestore
from firebase_admin import credentials

from config_crabada import BETA_TEST_LIST, USERS, SMALL_TEAM_GAS_LIMIT
from crabada.game_stats import LifetimeGameStats, NULL_GAME_STATS
from crabada.crabada_web2_client import CrabadaWeb2Client
from crabada.teams import assign_crabs_to_groups, assign_teams_to_groups
from crabada.teams import (
    LOOTING_GROUP_NUM,
    MINING_GROUP_NUM,
    INACTIVE_GROUP_NUM,
)
from crabada.types import MineOption
from crabada.config_manager_crabada import CrabadaConfigManager
from utils import logger
from crabada.game_stats import CrabadaLifetimeGameStatsLogger
from utils.general import dict_keys_camel_to_snake, dict_keys_snake_to_camel
from utils.config_types import UserConfig
from utils.email import Email
from utils.user import get_alias_from_user


class StrategyActions:
    MINING = MineOption.MINE
    LOOTING = MineOption.LOOT
    INACTIVE = "INACTIVE"


class ConfigManagerFirebase(CrabadaConfigManager):
    MULTI_WALLET_KEYS = ["mining_teams", "looting_teams", "reinforcing_crabs"]

    def __init__(
        self,
        user: str,
        config: UserConfig,
        send_email_accounts: T.List[Email],
        encrypt_password: str,
        log_dir: str,
        crabada_w2: CrabadaWeb2Client,
        dry_run: bool = False,
        verbose: bool = False,
    ):
        super().__init__(
            user,
            config,
            send_email_accounts,
            encrypt_password,
            log_dir,
            crabada_w2,
            dry_run,
            verbose,
        )
        this_dir = os.path.dirname(os.path.realpath(__file__))
        creds_dir = os.path.dirname(this_dir)
        credentials_file = os.path.join(creds_dir, "firebase_credentials.json")
        if not firebase_admin._apps:
            auth = credentials.Certificate(credentials_file)
            firebase_admin.initialize_app(auth)
        self.db = firestore.client()
        self.users_ref = self.db.collection("users")
        self.user_doc = self._get_user_document(self.config)
        self.verbose = verbose

    def init(self) -> None:
        if self.user_doc is None:
            logger.print_warn(
                f"{self.user} does not have a firebase account! Using default config"
            )
        else:
            self.config = self._load_config()
        self._print_out_config()
        self._send_email_config_if_needed()
        self._save_config()

    def check_for_config_updates(self) -> bool:
        if self.user not in BETA_TEST_LIST:
            return False

        now = time.time()

        if now - self.last_config_update_time < self.CONFIG_UPDATE_TIME:
            return False

        self.last_config_update_time = now

        did_update = False
        try:
            did_update = self._read_and_update_config()
        except:
            logger.print_fail(
                f"Failed to read and translate updated config from database"
            )

        try:
            self._update_game_stats()
        except:
            logger.print_fail(f"Failed to upload game stats to database")

        return did_update

    def get_lifetime_stats(self) -> LifetimeGameStats:
        game_stats: LifetimeGameStats = copy.deepcopy(NULL_GAME_STATS)
        if self.user_doc is None:
            return game_stats

        db_config = self.user_doc.get().to_dict()

        try:
            db_stats = db_config["stats"]
            return dict_keys_camel_to_snake(db_stats)
        except:
            return game_stats

    def _update_game_stats(self) -> None:
        if self.user_doc is None:
            return

        log_dir = logger.get_logging_dir("crabada")
        stats = CrabadaLifetimeGameStatsLogger(self.user, log_dir, {})
        game_stats = copy.deepcopy(stats.get_game_stats())

        commission_tus = 0.0
        for _, commission in game_stats["commission_tus"].items():
            commission_tus += commission
        game_stats["commission_tus"] = commission_tus
        db_config = self.user_doc.get().to_dict()
        if "stats" not in db_config:
            db_config["stats"] = {}

        db_config["stats"] = dict_keys_snake_to_camel(game_stats)
        self.user_doc.set(json.loads(json.dumps(db_config)))

    def _read_and_update_config(self) -> bool:
        if self.user_doc is None:
            return False

        db_config = self.user_doc.get().to_dict()

        new_config: UserConfig = self._get_empty_new_config()

        logger.print_ok_blue(f"Checking database for preferences changes...")
        new_config["email"] = db_config["preferences"]["notifications"][
            "email"
        ]["email"]
        new_config["get_email_updates"] = db_config["preferences"][
            "notifications"
        ]["email"]["updatesEnabled"]
        if db_config["preferences"]["notifications"]["sms"]["phoneNumber"]:
            new_config["sms_number"] = (
                "+1"
                + db_config["preferences"]["notifications"]["sms"][
                    "phoneNumber"
                ]
            )

        logger.print_ok_blue(
            f"Checking database for strategy setting changes..."
        )
        new_config["game_specific_configs"]["should_reinforce"] = db_config[
            "strategy"
        ]["reinforceEnabled"]
        new_config["game_specific_configs"][
            "max_reinforcement_price_tus"
        ] = float(db_config["strategy"]["maxReinforcement"])
        new_config["max_gas_price_gwei"] = SMALL_TEAM_GAS_LIMIT

        logger.print_ok_blue(f"Checking database for team changes...")

        teams = self.crabada_w2.list_teams(self.config["address"])

        team_group_assignment = {}

        for team, details in db_config["strategy"]["teams"].items():
            team_id = int(team)

            if team_id not in [t["team_id"] for t in teams]:
                logger.print_warn(
                    f"Team not associated with user, not adding from database"
                )
                continue

            if (
                details["action"] == StrategyActions.MINING
                or details["action"] == "MINING"
            ):
                group_base = MINING_GROUP_NUM
                db_config["strategy"]["teams"][team][
                    "action"
                ] = StrategyActions.MINING
            elif (
                details["action"] == StrategyActions.LOOTING
                or details["action"] == "LOOTING"
            ):
                group_base = LOOTING_GROUP_NUM
                db_config["strategy"]["teams"][team][
                    "action"
                ] = StrategyActions.LOOTING
            elif details["action"] == StrategyActions.INACTIVE:
                logger.print_fail(f"Detected inactive team {team_id}!")
                group_base = INACTIVE_GROUP_NUM
                db_config["strategy"]["teams"][team][
                    "action"
                ] = StrategyActions.INACTIVE
            else:
                logger.print_fail(f"Unknown action from teams!")
                continue

            composition, mp = self._get_team_composition_and_mp(
                team_id, new_config
            )

            team_group_assignment[team_id] = (group_base, mp)

            db_config["strategy"]["teams"][team]["composition"] = composition

            if self.verbose:
                logger.print_normal(
                    f"Team: {team_id}, Composition: {composition}, Action: {details['action']}"
                )

        groups = set()
        for team, group in assign_teams_to_groups(
            team_group_assignment
        ).items():
            if group >= MINING_GROUP_NUM:
                groups.add(group)
                new_config["game_specific_configs"]["mining_teams"][
                    team
                ] = group
            elif group >= LOOTING_GROUP_NUM:
                new_config["game_specific_configs"]["looting_teams"][
                    team
                ] = group

            logger.print_normal(f"Assigning team {team} to group {group}")

        logger.print_ok_blue(
            f"Checking database for reinforcement crab changes..."
        )

        crabs = self.crabada_w2.get_crabs(self.config["address"])

        crab_assignment = {}
        for crab, details in db_config["strategy"]["reinforcingCrabs"].items():
            crab_id = int(crab)

            if crab_id not in [c["crabada_id"] for c in crabs]:
                logger.print_warn(
                    f"Crab {crab_id} not associated with user, not adding from database"
                )
                continue

            if (
                details["action"] == StrategyActions.MINING
                or details["action"] == "MINING"
            ):
                group_base = MINING_GROUP_NUM
                new_config["game_specific_configs"]["reinforcing_crabs"][
                    crab_id
                ] = group_base
                db_config["strategy"]["reinforcingCrabs"][crab][
                    "action"
                ] = StrategyActions.MINING
            elif (
                details["action"] == StrategyActions.LOOTING
                or details["action"] == "LOOTING"
            ):
                group_base = LOOTING_GROUP_NUM
                new_config["game_specific_configs"]["reinforcing_crabs"][
                    crab_id
                ] = group_base
                db_config["strategy"]["reinforcingCrabs"][crab][
                    "action"
                ] = StrategyActions.LOOTING
            elif details["action"] == StrategyActions.INACTIVE:
                logger.print_normal(f"Detected inactive crab")
                group_base = INACTIVE_GROUP_NUM
                db_config["strategy"]["reinforcingCrabs"][crab][
                    "action"
                ] = StrategyActions.INACTIVE
            else:
                logger.print_fail(f"Unknown action from reinforcingCrabs!")
                continue

            crab_class = self._get_crab_class(crab_id, new_config)

            crab_assignment[crab_id] = group_base
            db_config["strategy"]["reinforcingCrabs"][crab]["class"] = [
                crab_class.strip()
            ]

            if self.verbose:
                logger.print_normal(
                    f"Crab: {crab_id}, Composition: {crab_class}, Action: {details['action']}"
                )

        groups = sorted(list(groups))
        crabs = sorted([c for c in db_config["strategy"]["reinforcingCrabs"]])
        for crab, group in assign_crabs_to_groups(
            crab_assignment, groups
        ).items():
            new_config["game_specific_configs"]["reinforcing_crabs"][
                crab
            ] = group
            logger.print_normal(f"Assigning crab {crab} to group {group}")

        diff = deepdiff.DeepDiff(
            self.config,
            new_config,
            ignore_order=True,
            ignore_numeric_type_changes=True,
            ignore_order_func=True,
        )
        if diff:
            logger.print_ok_blue(
                f"Detected changes in config from firebase database"
            )
            logger.print_normal(f"{diff}")
            self.config = copy.deepcopy(new_config)
            logger.print_normal(f"Saving new config to disk")
            self._save_config()
            logger.print_normal(f"Updating firebase db")
            self.user_doc.set(json.loads(json.dumps(db_config)))
            logger.print_normal(f"Sending config update email")
            self._send_email_config()
            return True

        return False

    def _get_user_document(self, config: UserConfig) -> T.Optional[T.Any]:
        db_setup = {}
        for doc in self.users_ref.stream():
            db_setup[doc.id] = doc.to_dict()

        email = config["email"].lower()
        for db_email, db_config in db_setup.items():
            try:
                notification_email = db_config["preferences"]["notifications"][
                    "email"
                ]["email"].lower()
            except:
                continue

            if notification_email == email:
                email = db_email.lower()
                break

        if (
            config["email"].lower() in db_setup
            or notification_email == config["email"].lower()
        ):
            return self.users_ref.document(email)
        else:
            return None

    def _get_alias_configs(self) -> T.Dict[str, T.Any]:
        alias_configs = {}
        users = copy.deepcopy(USERS)
        for user, config in users.items():
            alias = get_alias_from_user(user)

            # mark users with multi wallet items
            for k, v in config.items():
                if k in self.MULTI_WALLET_KEYS:
                    for game_id, group in v.items():
                        config[k][game_id] = (group, user)

            # merge wallet configs if already have one multi-wallet entry
            if alias in alias_configs:
                for k in self.MULTI_WALLET_KEYS:
                    if k not in alias_configs[alias]:
                        continue
                    alias_configs[alias][k].update(config[k])
            else:
                alias_configs[alias] = config
        return alias_configs

    def update_user_from_crabada(
        self, local_user: str, erase_old_config: bool = True
    ) -> None:
        user = local_user
        config = USERS[local_user]

        doc = self._get_user_document(config)

        if doc is not None:
            logger.print_normal(
                f"Using previous preferences from database and {'erasing' if erase_old_config else 'not erasing'}"
            )
            db_config = doc.get().to_dict()
            db_config["strategy"] = {
                "reinforceEnabled": db_config["strategy"]["reinforceEnabled"],
                "reinforcingCrabs": {}
                if erase_old_config
                else db_config["strategy"]["reinforcingCrabs"],
                "teams": {}
                if erase_old_config
                else db_config["strategy"]["teams"],
                "maxReinforcement": db_config["strategy"]["maxReinforcement"],
                "maxGas": 0,
            }
        else:
            logger.print_normal(f"Creating new database")
            db_config = {}
            db_config["user"] = get_alias_from_user(user)
            db_config["preferences"] = {
                "notifications": {
                    "email": {
                        "updatesEnabled": config["get_email_updates"],
                        "email": config["email"].lower(),
                    },
                    "sms": {
                        "lootUpdatesEnabled": config["get_sms_updates_loots"],
                        "phoneNumber": config["sms_number"].lstrip("+1"),
                        "alertUpdatesEnabled": config["get_sms_updates"],
                    },
                }
            }
            db_config["strategy"] = {
                "reinforceEnabled": config["game_specific_configs"][
                    "should_reinforce"
                ],
                "reinforcingCrabs": {},
                "teams": {},
                "maxReinforcement": config["game_specific_configs"][
                    "max_reinforcement_price_tus"
                ],
                "maxGas": 0,
            }

        logger.print_ok(f"Found email: {config['email']}")

        teams = self.crabada_w2.list_teams(config["address"])
        for team in teams:
            team_id = team["team_id"]
            composition, _ = self._get_team_composition_and_mp(team_id, config)
            if any([c == "UNKNOWN" for c in composition]):
                continue
            db_config["strategy"]["teams"][str(team_id)] = {
                "action": StrategyActions.LOOTING,
                "composition": composition,
                "user": user,
            }

        crabs = self.crabada_w2.list_my_available_crabs_for_reinforcement(
            config["address"]
        )
        for crab in crabs:
            crab_id = crab["crabada_id"]
            crab_class = self.crab_classes.get(
                crab_id, self._get_crab_class(crab_id, config)
            )
            if crab_class == "UNKNOWN":
                continue
            db_config["strategy"]["reinforcingCrabs"][str(crab_id)] = {
                "action": StrategyActions.MINING,
                "class": [crab_class.strip()],
                "user": user,
            }

        if self.verbose:
            logger.print_normal(f"{json.dumps(db_config, indent=4)}")

        if doc is None:
            self.users_ref.document(config["email"].lower()).create(
                json.loads(json.dumps(db_config))
            )
        else:
            doc.set(json.loads(json.dumps(db_config)))

    def update_user_from_local_config(self, local_user: str) -> None:
        alias_configs = self._get_alias_configs()

        for alias, config in alias_configs.items():
            if get_alias_from_user(local_user) != alias:
                continue

            doc = self._get_user_document(config)

            if doc is not None:
                db_config = doc.get().to_dict()
                logger.print_normal(f"Skipping {alias} b/c already in DB")
                return
            else:
                db_config = {}

            logger.print_ok(f"Found email: {config['email']}")
            db_config["user"] = alias
            db_config["preferences"] = {
                "notifications": {
                    "email": {
                        "updatesEnabled": config["get_email_updates"],
                        "email": config["email"].lower(),
                    },
                    "sms": {
                        "lootUpdatesEnabled": config["get_sms_updates_loots"],
                        "phoneNumber": config["sms_number"].lstrip("+1"),
                        "alertUpdatesEnabled": config["get_sms_updates"],
                    },
                }
            }
            db_config["strategy"] = {
                "reinforceEnabled": config["game_specific_configs"][
                    "should_reinforce"
                ],
                "reinforcingCrabs": {},
                "teams": {},
                "maxReinforcement": config["game_specific_configs"][
                    "max_reinforcement_price_tus"
                ],
                "maxGas": 0,
            }

            for team, value in config["game_specific_configs"][
                "mining_teams"
            ].items():
                composition, _ = self._get_team_composition_and_mp(team, config)
                db_config["strategy"]["teams"][team] = {
                    "action": StrategyActions.MINING,
                    "composition": composition,
                    "user": value[1],
                }

            for team, value in config["game_specific_configs"][
                "looting_teams"
            ].items():
                composition, _ = self._get_team_composition_and_mp(team, config)
                db_config["strategy"]["teams"][team] = {
                    "action": StrategyActions.LOOTING,
                    "composition": composition,
                    "user": value[1],
                }

            for crab, value in config["game_specific_configs"][
                "reinforcing_crabs"
            ].items():
                action = (
                    StrategyActions.MINING
                    if value[0] < 10
                    else StrategyActions.LOOTING
                )
                crab_class = self.crab_classes.get(
                    crab, self._get_crab_class(crab, config)
                )
                db_config["strategy"]["reinforcingCrabs"][crab] = {
                    "action": action,
                    "class": [crab_class.strip()],
                    "user": value[1],
                }

            if self.verbose:
                logger.print_normal(f"{json.dumps(db_config, indent=4)}")

            if doc is None:
                self.users_ref.document(config["email"].lower()).create(
                    json.loads(json.dumps(db_config))
                )
            else:
                doc.set(json.loads(json.dumps(db_config)))
