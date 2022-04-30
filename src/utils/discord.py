import typing as T

from discord import Webhook, RequestsWebhookAdapter

DISCORD_WEBHOOK_URL = {
    "HOLDERS": "https://discord.com/api/webhooks/959942813091495966/As3hppPILxEc4T73CIBe3dQKVyC5leVQIUKtTBlOyaRBZNPjSPmukN0KLYx_uJqw2xuz",
    "UPDATES": "https://discord.com/api/webhooks/959940948492701758/PWcjycFIJQHuddnWf661Dnen6bg4UXEAwvpzlYkmnrWQFEGZrX3gdbpVHpxysNylX6iV",
    "LOOT_SNIPE": "https://discord.com/api/webhooks/965347698796531772/FG7JJS1AaFkUrFutgmUew2Cq8Jw9eragMYcgxFAC1BD3vL9Eje1ylg7WUShLdORTplvI",
    "LOW_MR_LOOT_SNIPE": "https://discord.com/api/webhooks/967646138570248222/uGB8At-fTN-ORWwnRcky4Wb0u311qjNBpDMgHLtuwGUm3PkApu-8VU8Rt25Z9f4SYvSP",
    # paid subscriptions
    "HEYA_SUBSCRIPTION": "https://discord.com/api/webhooks/969388295253553192/QZ3XqguHVi3DEQRLiMUMqjLyaspLxfb1gfqtKizYF6rW_azim9D0dhs0eXZzXlJf8bvw",
}


def get_discord_hook(discord: str) -> Webhook:
    return Webhook.from_url(DISCORD_WEBHOOK_URL[discord], adapter=RequestsWebhookAdapter())
