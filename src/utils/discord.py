import typing as T

from discord import Webhook, RequestsWebhookAdapter

DISCORD_WEBHOOK_URL = {
    "WHALES": "https://discord.com/api/webhooks/951028752257789972/WBDD5vLKziawAMRkluuLvx_eacNLItLdHHmL8PHKUj1p-q6COHks_11--Mt39l8K1T1I",
    "CARTEL": "https://discord.com/api/webhooks/959278986050023444/oImIbDv-7iAIUY1WGV-YWkCOCRbs6qltq-7HaUw-kz1IkV6vjQdXZDPf_5mmpz2Qgmyz",
}


def get_discord_hook(discord: str) -> Webhook:
    return Webhook.from_url(DISCORD_WEBHOOK_URL[discord], adapter=RequestsWebhookAdapter())
