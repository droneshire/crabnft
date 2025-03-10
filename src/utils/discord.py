import typing as T

from discord import SyncWebhook

DISCORD_WEBHOOK_URL = {
    "CRABADA_HOLDERS": "https://discord.com/api/webhooks/988288028143403008/kG9V_OHQEA9Cj6n_OaqFrp48Y7NllBkKZs8c58r6uUYSZlqIPtPm3n18jzCpwNpZjfl5",
    "CRABADA_UPDATES": "https://discord.com/api/webhooks/988288028143403008/kG9V_OHQEA9Cj6n_OaqFrp48Y7NllBkKZs8c58r6uUYSZlqIPtPm3n18jzCpwNpZjfl5",
    "CRABADA_ACTIVITY": "https://discord.com/api/webhooks/995581922912772107/WxWRhmM8nN5zNHyeXOHI1Br9MV_7yOFjeigjuHQSOB-5p3NAOhR07vBvu9xXvQnEs1-N",
    "LOOT_SNIPE": "https://discord.com/api/webhooks/965347698796531772/FG7JJS1AaFkUrFutgmUew2Cq8Jw9eragMYcgxFAC1BD3vL9Eje1ylg7WUShLdORTplvI",
    "LOW_MR_LOOT_SNIPE": "https://discord.com/api/webhooks/967646138570248222/uGB8At-fTN-ORWwnRcky4Wb0u311qjNBpDMgHLtuwGUm3PkApu-8VU8Rt25Z9f4SYvSP",
    "WYNDBLAST_UPDATES": "https://discord.com/api/webhooks/988288614343512074/AiVdp_uL_sLTJRO05xhU6E6DEF6aQR1cB65ZO9SjQlzMHlDNTGoHKXv6ucyBErvM1UX6",
    "WYNDBLAST_ACTIVITY": "https://discord.com/api/webhooks/1017484506397159506/uGjNtG68Zkq5nCzDmzJ-MuT2N8X2-W0QrQqmhlamqmPSkZbvgcf_H3jxZVvx3em6P_l8",
    "WYNDBLAST_PVE_ACTIVITY": "https://discord.com/api/webhooks/1044839682678198294/_JpZxtl1S7PRmvQswnuMdngbzxacMPESHw4pR0l4XLRYqJOFcqVTMW_kZHXwtuhdhJ2Y",
    "PUMPSKIN_ACTIVITY": "https://discord.com/api/webhooks/1028476865607901254/LFh2xkGWQqiOHaR1gwhdYIEbKPc9iJmXMknnJIyy3jIawv1XR-yr-XjwnYGVYkOWoAEx",
    "PUMPSKIN_UPDATES": "https://discord.com/api/webhooks/1028501975219847198/otDCjM8kR0K0oiJHSI3_ZuBq5aJ88cKchxNAKNbuWlYAb2tXMmrxzC8DwrUF-6e6K7ed",
    "PUMPSKIN_MARKET": "https://discord.com/api/webhooks/1035833369314983967/DfepvsK-M32izIfjTSxV4mU5q72E7WbkL43TWSOnx6n8jRXCCHF5oJHhYdNPfhAJQaCO",
    "PAT_UPDATES": "https://discord.com/api/webhooks/1037603856529502251/O9uAcnWiupaHvBMmmL2tQF1ewbOGaW-rGGOWcncCxmLSWT6uD6Sulpptr_KHs5hnBNNH",
    "PAT_ACTIVITY": "https://discord.com/api/webhooks/1037618937413771285/5ZFxRUYYaliSuPJ9TCvP6_3wULuwK-8mhk1liT6TuA-wDtxYw_YKDYJZ6eFC2jMCZkjw",
    "DEEP_ALPHA_MINT_MINER": "https://discord.com/api/webhooks/1052828382733291520/LtcJ23VRBdGV9agx8B4qN4SX4A_Fs8yTE1P3P7kQPzHzNrsJAV_7aGaCbu-te0CIWPUa",
    "MECHAVAX_BOT": "https://discordapp.com/api/webhooks/1069503958911037492/tPdv7-1-kSMMm-uFoGhgrBnlVOQ92MTYUD27F51gn0WrJ7xtjjenXQRGLfbWCuF5bdcE",
    "MECHAVAX_MINT": "https://discord.com/api/webhooks/1114670541161365566/8bL1SzWjXO1prJKkJBDloSyb3yFi9_Qa_G5Ib5I1jSKVNU3QaEJBFENR0UDprNPLysla",
    # paid subscriptions
    "HEYA_SUBSCRIPTION": "https://discord.com/api/webhooks/969388295253553192/QZ3XqguHVi3DEQRLiMUMqjLyaspLxfb1gfqtKizYF6rW_azim9D0dhs0eXZzXlJf8bvw",
}


def get_discord_hook(discord: str) -> SyncWebhook:
    return SyncWebhook.from_url(DISCORD_WEBHOOK_URL[discord])
