import typing as T

from discord import Webhook, RequestsWebhookAdapter

DISCORD_WEBHOOK_URL = {
    "CRABADA_HOLDERS": "https://discord.com/api/webhooks/988288028143403008/kG9V_OHQEA9Cj6n_OaqFrp48Y7NllBkKZs8c58r6uUYSZlqIPtPm3n18jzCpwNpZjfl5",
    "CRABADA_UPDATES": "https://discord.com/api/webhooks/988288028143403008/kG9V_OHQEA9Cj6n_OaqFrp48Y7NllBkKZs8c58r6uUYSZlqIPtPm3n18jzCpwNpZjfl5",
    "CRABADA_ACTIVITY": "https://discord.com/api/webhooks/995581922912772107/WxWRhmM8nN5zNHyeXOHI1Br9MV_7yOFjeigjuHQSOB-5p3NAOhR07vBvu9xXvQnEs1-N",
    "LOOT_SNIPE": "https://discord.com/api/webhooks/965347698796531772/FG7JJS1AaFkUrFutgmUew2Cq8Jw9eragMYcgxFAC1BD3vL9Eje1ylg7WUShLdORTplvI",
    "LOW_MR_LOOT_SNIPE": "https://discord.com/api/webhooks/967646138570248222/uGB8At-fTN-ORWwnRcky4Wb0u311qjNBpDMgHLtuwGUm3PkApu-8VU8Rt25Z9f4SYvSP",
    "WYNDBLAST_UPDATES": "https://discord.com/api/webhooks/988288614343512074/AiVdp_uL_sLTJRO05xhU6E6DEF6aQR1cB65ZO9SjQlzMHlDNTGoHKXv6ucyBErvM1UX6",
    "WYNDBLAST_ACTIVITY": "https://discord.com/api/webhooks/1017484506397159506/uGjNtG68Zkq5nCzDmzJ-MuT2N8X2-W0QrQqmhlamqmPSkZbvgcf_H3jxZVvx3em6P_l8",
    "PUMPSKIN_ACTIVITY": "https://discord.com/api/webhooks/1028476865607901254/LFh2xkGWQqiOHaR1gwhdYIEbKPc9iJmXMknnJIyy3jIawv1XR-yr-XjwnYGVYkOWoAEx",
    # paid subscriptions
    "HEYA_SUBSCRIPTION": "https://discord.com/api/webhooks/969388295253553192/QZ3XqguHVi3DEQRLiMUMqjLyaspLxfb1gfqtKizYF6rW_azim9D0dhs0eXZzXlJf8bvw",
}


def get_discord_hook(discord: str) -> Webhook:
    return Webhook.from_url(DISCORD_WEBHOOK_URL[discord], adapter=RequestsWebhookAdapter())
