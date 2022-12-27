CONFIG_TEMPLATE = {
    "": config_types.UserConfig(
        group=4,
        game="crabada",
        private_key="",
        address=Address(""),
        game_specific_configs={
            "mining_teams": {},
            "looting_teams": {},
            "reinforcing_crabs": {},
            "mining_strategy": "PreferOwnMpCrabsAndDelayReinforcement",
            "looting_strategy": "PreferOwnBpCrabsAndDelayReinforcement",
            "max_reinforcement_price_tus": 24.0,
            "should_reinforce": True,
            "authorization": "",
        },
        max_gas_price_gwei=SMALL_TEAM_GAS_LIMIT,
        commission_percent_per_mine={
            "0xBe8CFD634Ab8D91BA391D3A22D3E1D452c0A43cb": 10.0,
        },
        sms_number="",
        email="",
        discord_handle="",
        get_sms_updates=False,
        get_sms_updates_loots=False,
        get_sms_updates_alerts=False,
        get_email_updates=True,
    ),
}
