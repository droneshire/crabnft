MORALIS_HEADERS = {
    "authority": "qheky5jm92sj.usemoralis.com:2053",
    "accept": "*/*",
    "accept-language": "en-US,en;q=0.9",
    "content-type": "text/plain",
    "dnt": "1",
    "origin": "",  # must set to be the base URL
    "referer": "",  # must set to be the base URL
    "sec-ch-ua": '" Not A;Brand";v="99", "Chromium";v="101", "Google Chrome";v="101"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"Linux"',
    "sec-fetch-dest": "empty",
    "sec-fetch-mode": "cors",
    "sec-fetch-site": "cross-site",
    "user-agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/101.0.0.0 Safari/537.36",
}

WYNDBLAST_AUTHORIZATION_HEADER_KEY_FORMAT = "Bearer {}"
WYNDBLAST_DAILY_ACTIVITIES_HEADERS = {
    "authority": "api.wyndblast.com",
    "accept": "application/json, text/plain, */*",
    "accept-language": "en-US,en;q=0.9",
    "authorization": "",  # must use WYNDBLAST_AUTHORIZATION_HEADER_KEY_FORMAT.format(token)
    "dnt": "1",
    # "if-none-match": 'W/"2dc8-fr/ndnMMZm8unZlMPFzWpdz+fKk"',
    "origin": "https://dailyactivities.wyndblast.com",
    "referer": "https://dailyactivities.wyndblast.com/",
    "sec-ch-ua": '" Not A;Brand";v="99", "Chromium";v="101", "Google Chrome";v="101"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"Linux"',
    "sec-fetch-dest": "empty",
    "sec-fetch-mode": "cors",
    "sec-fetch-site": "same-site",
    "user-agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/101.0.0.0 Safari/537.36",
}

API_KEYS = {
    "pve": "wyndblast-pve-6860d846-8466-4faf-a29d-c6638bf3f9fa",
    "internal": "wb-pve-internal-2c5ae367-1754-4168-b39e-32fc20704557",
}

WYNDBLAST_PVE_HEADERS = {
    "authority": "wyndblast-pve-api-26nte4kk3a-ey.a.run.app",
    "accept": "*/*",
    "accept-language": "en-US,en;q=0.9",
    "authorization": "",  # must use WYNDBLAST_AUTHORIZATION_HEADER_KEY_FORMAT.format(token)
    "content-type": "application/json; charset: utf-8",
    "dnt": "1",
    "origin": "https://wyndblast-pve-mainnet.netlify.app",
    "referer": "https://wyndblast-pve-mainnet.netlify.app/",
    "sec-ch-ua": '"Google Chrome";v="107", "Chromium";v="107", "Not=A?Brand";v="24"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"Linux"',
    "sec-fetch-dest": "empty",
    "sec-fetch-mode": "cors",
    "sec-fetch-site": "cross-site",
    "user-agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/107.0.0.0 Safari/537.36",
    "x-api-key": "wyndblast-pve-6860d846-8466-4faf-a29d-c6638bf3f9fa",
}
