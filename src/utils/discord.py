import typing as T

from discord import Webhook, RequestsWebhookAdapter

DISCORD_WEBHOOK_URL = "https://discord.com/api/webhooks/951028752257789972/WBDD5vLKziawAMRkluuLvx_eacNLItLdHHmL8PHKUj1p-q6COHks_11--Mt39l8K1T1I"


def get_discord_hook() -> Webhook:
    return Webhook.from_url(DISCORD_WEBHOOK_URL, adapter=RequestsWebhookAdapter())
