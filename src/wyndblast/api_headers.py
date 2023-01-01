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
    "pve": "wyndblast-pve-407d11fc-0ec3-42af-adb1-a26c8b5074e5",
    "internal": "wb-pve-internal-0e97b9a3-f32c-4eb3-8ba1-eac0cedc1128",
    "marketplace": "public-1747ea40-6cca-4d25-887f-bc5301ab05df",
}

WYNDBLAST_PVE_HEADERS = {
    "authority": "wyndblast-pve-api-26nte4kk3a-ey.a.run.app",
    "accept": "*/*",
    "accept-language": "en-US,en;q=0.9",
    "authorization": "",  # must use WYNDBLAST_AUTHORIZATION_HEADER_KEY_FORMAT.format(token)
    "cache-control": "no-cache",
    "content-type": "application/json; charset: utf-8",
    "dnt": "1",
    "origin": "https://battle.wyndblast.com",
    "pragma": "no-cache",
    "referer": "https://battle.wyndblast.com/",
    "sec-ch-ua": '"Google Chrome";v="107", "Chromium";v="107", "Not=A?Brand";v="24"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"Linux"',
    "sec-fetch-dest": "empty",
    "sec-fetch-mode": "cors",
    "sec-fetch-site": "cross-site",
    "user-agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36",
    "x-api-key": "wyndblast-pve-407d11fc-0ec3-42af-adb1-a26c8b5074e5",
}

GOOGLE_STORAGE_X_CLIENT_DATA_KEYS = {
    "pve": "CIm2yQEIorbJAQipncoBCOvjygEIk6HLAQi1gs0BCMeGzQEY++zMAQ=="
}

WYNDBLAST_PVE_GOOGLESTORAGE_HEADERS = {
    "authority": "storage.googleapis.com",
    "accept": "*/*",
    "accept-language": "en-US,en;q=0.9",
    "cache-control": "no-cache",
    "content-type": "application/json; charset: utf-8",
    "dnt": "1",
    "origin": "https://battle.wyndblast.com",
    "pragma": "no-cache",
    "referer": "https://battle.wyndblast.com/",
    "sec-ch-ua": '"Not?A_Brand";v="8", "Chromium";v="108", "Google Chrome";v="108"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"Linux"',
    "sec-fetch-dest": "empty",
    "sec-fetch-mode": "cors",
    "sec-fetch-site": "cross-site",
    "user-agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36",
    "x-client-data": "",  # must use GOOGLE_STORAGE_X_CLIENT_DATA.format(key)
}
