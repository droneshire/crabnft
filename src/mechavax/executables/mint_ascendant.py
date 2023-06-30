import getpass
import json
import os
import requests
import typing as T

from config_mechavax import (
    GUILD_WALLET_ADDRESS,
    GUILD_WALLET_PRIVATE_KEY
)
from mechavax.mechavax_web3client import MechContractWeb3Client
from utils.security import decrypt_secret
from utils import logger
from web3_utils.avalanche_c_web3_client import AvalancheCWeb3Client

HEADERS = {
    'authority': 'api.thegraph.com',
    'accept': 'application/graphql+json, application/json',
    'accept-language': 'en-US,en;q=0.9',
    'content-type': 'application/json',
    'dnt': '1',
    'origin': 'https://mechavax.com',
    'referer': 'https://mechavax.com/',
    'sec-ch-ua': '"Not.A/Brand";v="8", "Chromium";v="114", "Google Chrome";v="114"',
    'sec-ch-ua-mobile': '?0',
    'sec-ch-ua-platform': '"Linux"',
    'sec-fetch-dest': 'empty',
    'sec-fetch-mode': 'cors',
    'sec-fetch-site': 'cross-site',
    'user-agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36',
}

JSON_DATA = {
    'query': 'query meches($id: String) {\n  meches(\n    first: 1000\n    where: {mechOwner_: {id: $id}}\n    orderBy: id\n    orderDirection: desc\n  ) {\n    id\n    idx\n    tokenID\n    createdAt\n    __typename\n  }\n}',
    'operationName': 'meches',
    'variables': {
        'id': '',
    },
}

BLOCKLIST_MECH_IDS = [
    4490,
]

def get_credentials() -> T.Tuple[str, str]:
    encrypt_password = os.getenv("NFT_PWD")
    if not encrypt_password:
        encrypt_password = getpass.getpass(prompt="Enter decryption password: ")

    logger.print_bold("Decrypting credentials...")
    private_key = decrypt_secret(encrypt_password, GUILD_WALLET_PRIVATE_KEY)
    return GUILD_WALLET_ADDRESS, private_key


ADDRESS, PRIVATE_KEY = get_credentials()

def main():
    headers = HEADERS
    json_data = JSON_DATA
    json_data['variables']['id'] = GUILD_WALLET_ADDRESS.lower()
    response = requests.post('https://api.thegraph.com/subgraphs/name/0xboots/mechavax', headers=headers, json=json_data).json()
    logger.print_bold(f"Total meches minted: {len(response['data']['meches'])}")

    mech_ids = []
    for mech in response['data']['meches']:
        if int(mech['tokenID']) in BLOCKLIST_MECH_IDS:
            logger.print_warn(f"Skipping mech {mech['tokenID']}")
            continue
        mech_ids.append(int(mech['tokenID']))
    string_list = ",".join([str(i) for i in sorted(mech_ids)])
    string_list = f"[{string_list}]"
    logger.print_normal(f"{string_list}")

    logger.print_bold(f"Total meches to mint: {len(mech_ids)}")

    w3_mech: MechContractWeb3Client = (
        MechContractWeb3Client()
        .set_credentials(ADDRESS, PRIVATE_KEY)
        .set_node_uri(AvalancheCWeb3Client.NODE_URL)
        .set_contract()
        .set_dry_run(False)
    )
    w3_mech.mint_legendary(mech_ids)


if __name__ == '__main__':
    main()
