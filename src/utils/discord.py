import typing as T

from discord import Webhook, RequestsWebhookAdapter

DISCORD_WEBHOOK_URL = {
    "HOLDERS": "https://discord.com/api/webhooks/959942813091495966/As3hppPILxEc4T73CIBe3dQKVyC5leVQIUKtTBlOyaRBZNPjSPmukN0KLYx_uJqw2xuz",
    "UPDATES": "https://discord.com/api/webhooks/959940948492701758/PWcjycFIJQHuddnWf661Dnen6bg4UXEAwvpzlYkmnrWQFEGZrX3gdbpVHpxysNylX6iV",
    "LOOT_SNIPE": "https://discord.com/api/webhooks/965347698796531772/FG7JJS1AaFkUrFutgmUew2Cq8Jw9eragMYcgxFAC1BD3vL9Eje1ylg7WUShLdORTplvI",
}


def get_discord_hook(discord: str) -> Webhook:
    return Webhook.from_url(DISCORD_WEBHOOK_URL[discord], adapter=RequestsWebhookAdapter())
