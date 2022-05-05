CONFIG_TEMPLATE = {
    "CAPTAINJACK": config_types.UserConfig(
        group=2,
        crabada_key="s3aKO4eZk7TKFaNF7aA9vp/D34pGovjy3y4ydBUbeXOEY9ysk0VT5+RCzMNuWiYinsA1al/go5E6ARuY6ZxLjEFROVVjsEWxMcY2pOCJ2Bhv0krdM2551pqueZ2WEFrL",
        address=Address("0x5bE5271E323EE93E5bFF7248Ee2FF4Cb03681291"),
        mining_teams={
            40827: 1,
        },
        looting_teams={},
        reinforcing_crabs={},
        breed_crabs=[],
        mining_strategy="PreferOwnMpCrabsAndDelayReinforcement",
        looting_strategy="PreferOwnBpCrabsAndDelayReinforcement",
        max_gas_price_gwei=SMALL_TEAM_GAS_LIMIT,
        max_reinforcement_price_tus=24.0,
        commission_percent_per_mine={
            "0x8191eFdc4b4A1250481624a908C6cB349A60590e": 10.0,
        },
        sms_number="",
        email="Jack3blake@gmail.com",
        discord_handle="CaptainJack",
        get_sms_updates=False,
        get_sms_updates_loots=False,
        get_sms_updates_alerts=False,
        get_email_updates=True,
        should_reinforce=True,
    ),
}
