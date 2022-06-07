MORALIS_USER_AUTH_HEADERS = {
    "authority": "qheky5jm92sj.usemoralis.com:2053",
    "accept": "*/*",
    "accept-language": "en-US,en;q=0.9",
    "content-type": "text/plain",
    "dnt": "1",
    "origin": "https://dailyactivities.wyndblast.com",
    "referer": "https://dailyactivities.wyndblast.com/",
    "sec-ch-ua": '" Not A;Brand";v="99", "Chromium";v="101", "Google Chrome";v="101"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"Linux"',
    "sec-fetch-dest": "empty",
    "sec-fetch-mode": "cors",
    "sec-fetch-site": "cross-site",
    "user-agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/101.0.0.0 Safari/537.36",
}

MORALIS_SERVER_TIME_HEADERS = {
    "authority": "qheky5jm92sj.usemoralis.com:2053",
    "accept": "*/*",
    "accept-language": "en-US,en;q=0.9",
    "content-type": "text/plain",
    "dnt": "1",
    "origin": "https://dailyactivities.wyndblast.com",
    "referer": "https://dailyactivities.wyndblast.com/",
    "sec-ch-ua": '" Not A;Brand";v="99", "Chromium";v="101", "Google Chrome";v="101"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"Linux"',
    "sec-fetch-dest": "empty",
    "sec-fetch-mode": "cors",
    "sec-fetch-site": "cross-site",
    "user-agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/101.0.0.0 Safari/537.36",
}


WYNDBLAST_AUTHORIZATION_HEADER_KEY_FORMAT = "Bearer {}"
WYNDBLAST_HEADERS = {
    "authority": "api.wyndblast.com",
    "accept": "application/json, text/plain, */*",
    "accept-language": "en-US,en;q=0.9",
    "authorization": "",  # must provide WYNDBLAST_AUTH_FORMAT.format(session_token here)
    "dnt": "1",
    "if-none-match": 'W/"b3-7e/mJ/RrKHuO4gb+4YM2j3UbTW8"',
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
