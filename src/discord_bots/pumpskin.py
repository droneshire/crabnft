import typing as T


from discord_bots.behavior import OnMessage
from web3_utils.avalanche_c_web3_client import AvalancheCWeb3Client
from pumpskin.pumpskin_web3_client import PumpskinCollectionWeb3Client
from pumpskin.types import StakedPumpskin

from config_admin import ADMIN_ADDRESS


class GetPumpkinLevel(OnMessage):
    HOTKEY = f"!pumpskinlvl"

    @classmethod
    def response(cls, message: str) -> str:
        if not message.startswith(cls.HOTKEY):
            return ""

        try:
            token_id = int(message.strip().split(cls.HOTKEY)[1])
        except ValueError:
            return ""

        try:
            w3: PumpskinCollectionWeb3Client = (
                PumpskinCollectionWeb3Client()
                .set_credentials(ADMIN_ADDRESS, "")
                .set_node_uri(AvalancheCWeb3Client.NODE_URL)
                .set_dry_run(False)
            )

            pumpskin_info: StakedPumpskin = w3.get_staked_pumpskin_info(token_id)
            ml = int(pumpskin_info["kg"] / 100)
            return f"\U0001F383 **Pumpskin {token_id}**: ` ML {ml} `"
        except:
            return f"Unknown level for Pumpskin \U0001F937"
