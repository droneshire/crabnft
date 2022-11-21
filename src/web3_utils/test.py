import os
import json
import time
from web3.middleware import geth_poa_middleware
from web3 import Web3

user_address = Web3.toChecksumAddress("0x8191efdc4b4a1250481624a908c6cb349a60590e")
token_address = Web3.toChecksumAddress("0x325a9463e93ab79bf0302353c99ef70f43f33637")
contract_address = Web3.toChecksumAddress("0x60aE616a2155Ee3d9A68541Ba4544862310933d4")
this_dir = os.path.dirname(os.path.realpath(__file__))
abi_file = os.path.join(os.path.dirname(this_dir), "web3_utils", "abi", "abi-trader-joe.json")

with open(abi_file) as infile:
    abi = json.load(infile)

node_uri = "https://api.avax.network/ext/bc/C/rpc"
w3 = Web3(Web3.HTTPProvider(node_uri))
w3.middleware_onion.inject(geth_poa_middleware, layer=0)
contract = w3.eth.contract(address=contract_address, abi=abi)

print("Calling function addLiquidityAVAX()...")

deadline = int(time.time() + (1 * 60.0))
print(
    contract.encodeABI(
        fn_name="addLiquidityAVAX",
        args=[
            token_address,
            0xD5DEE67ADC47C5E57,
            0xD4CD2553D89E74444,
            0xFE8F8AE58C5488,
            user_address,
            deadline,
        ],
    )
)
