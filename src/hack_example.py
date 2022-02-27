import json
import threading
import traceback
import time
import requests

from typing import Literal, TypedDict, List

from web3 import Web3
import time

KEY = ""
PUB_ADDRESS = ""
MAX_REINFORCEMENT_PRICE_TUS = 25.1
GAS_PRICE = 35
ATTACK_TIME_SECONDS = 60 * 30 # 30 mins

w3 = Web3(Web3.HTTPProvider('https://api.avax.network/ext/bc/C/rpc'))

ReqHeaderDict = {
    "Origin": "https://google.com",
    "Accept": "application/json, text/plain, */*",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/96.0.4664.110 Safari/537.36",
    "Accept-Encoding": "gzip, deflate",
    "Content-Type": "application/json; charset=utf-8",
}


def getTeamsByAddr(accAddr):
    url = ("https://idle-api.crabada.com/public/idle/teams?user_address={}").format(accAddr)
    try:
        r = requests.get(url, timeout=(20), headers=ReqHeaderDict)
    except Exception as e:
        print("getTeamsByAddr - request failed : " + str(e))
        return None

    if r.status_code != 200:
        print("{} Team, status:{}, text:{}".format(accAddr, r.status_code, r.text))
        return None
    jd = r.json()

    if jd["error_code"] is not None:
        print("Team error_code: " + str(jd))
        return None

    return jd["result"]["data"]


def getGamesByAddr(addr):
    url = ("https://idle-api.crabada.com/public/idle/mines?status=open&user_address={}").format(addr)
    try:
        r = requests.get(url, timeout=(10), headers=ReqHeaderDict)
    except Exception as e:
        print("getGamesByAddr - requests failed : " + str(e))
        return []

    if r.status_code != 200:
        print("getGamesByAddr - request failed, status:{}, text:{}".format(r.status_code, r.text))
        return []

    jd = r.json()

    if jd["error_code"] is not None:
        print("getGamesByAddr - error_code invalid : " + str(jd))
        return []

    return jd["result"]["data"]


def waitForReceipt(signed_txid, timeout, interval):
    t0 = time.time()
    while True:
        try:
            receipt = w3.eth.getTransactionReceipt(signed_txid)
            if receipt is not None:
                break
            print("Waiting for transaction response {}".format(signed_txid))
            delta = time.time() - t0
            if (delta > timeout):
                break
            time.sleep(interval)
        except KeyboardInterrupt:
            break
        except:
            pass
    return receipt

def sendTx(addr, private, data, tx_type, dry_run=False):
    print(data)
    if dry_run:
        print("Skipping tx since dry run...")
        return
    recieve_add = Web3.toChecksumAddress(addr)
    game_add = Web3.toChecksumAddress('0x82a85407bd612f52577909f4a58bfc6873f14da8')
    nonce = w3.eth.getTransactionCount(recieve_add)
    gasprice = int(Web3.toWei(GAS_PRICE, 'Gwei'))
    signed_txn = w3.eth.account.signTransaction(dict(
        nonce=nonce,
        gasPrice=gasprice,
        gas=550000,
        to=game_add,
        value=Web3.toWei(0, 'ether'),
        data=data,
        chainId=43114
    ), private)
    signed = w3.eth.sendRawTransaction(signed_txn.rawTransaction)
    print("Tx sent...")
    signed_txid = Web3.toHex(signed)
    timeout = 10
    interval = 1
    receipt = waitForReceipt(signed_txid, timeout, interval)

def startGame(addr, private, team):
    team_id_str = hex(team).replace('0x', '')
    teamid = "0" * (64 - len(team_id_str)) + team_id_str
    data = '0xe5ed1d59' + teamid[-64:]
    print("Starting game for team {}...".format(team))
    sendTx(addr, private, data, 'start')

def endGame(addr, private, game):
    game_id_str = hex(game).replace('0x', '')
    gameid = "0" * (64 - len(game_id_str)) + game_id_str
    data = '0x2d6ef310' + gameid[-64:]
    print("Ending GameId: {}  ...".format(game))
    sendTx(addr, private, data, 'end')

def lend(addr, private, miner):
    while True:
        try:
            LENDING_URL = "https://idle-api.crabada.com/public/idle/crabadas/lending?orderBy=mine_point&order=desc&page=1&limit=100"
            r = requests.get(LENDING_URL)
            if r.status_code == 200:
                break
            time.sleep(2)
        except:
            print("failed response from {}".format(LENDING_URL))
            pass

    data = r.json()

    affordable_crabs = [ c for c in data['result']['data'] if Web3.fromWei(c["price"], "ether") < MAX_REINFORCEMENT_PRICE_TUS]
    sorted_affordable_crabs = sorted(affordable_crabs, key=lambda c: (-c['mine_point'], c['price']))
    if len(sorted_affordable_crabs) == 0:
        print("Could not find any affordable crabs to reinforce with!")
        return

    # grab the 2th most affordable crab so we minimize chance of failure
    cra = sorted_affordable_crabs[1]
    numstr = '0000000000000000000000000000000000000000000000000000000000000000'
    craid = numstr + hex(cra['crabada_id']).replace('0x','')
    gameid = numstr + hex(miner['game_id']).replace('0x','')
    price = numstr + hex(Web3.toWei(cra['price'], "ether")).replace('0x','')
    data = '0x08873bfb' + gameid[-64:] + craid[-64:] + price[-64:]
    sendTx(addr, private, data, 'reinforce')
    print('Found reinforcement crab #{} ({} TUS) BP: {} MP: {}'.format(cra['crabada_id'], Web3.fromWei(cra["price"], "ether"), cra['battle_point'], cra["mine_point"]))

class GameStats(TypedDict):
    total_tus : float
    total_cra : float
    wins : int
    losses : int

def monitor():
    game_stats = GameStats()

    game_stats["total_tus"] = 0
    game_stats["total_cra"] = 0
    game_stats["wins"] = 0
    game_stats["losses"] = 0

    while True:
        key = KEY
        address = PUB_ADDRESS
        teams = getTeamsByAddr(address)
        games = getGamesByAddr(address)
        gameObj = {}
        for game in games:
            gameObj[str(game['game_id'])] = game
        print("Crabada address {} teams:".format(address))
        print(time.strftime('%A, %Y-%m-%d %H:%M:%S', time.localtime(time.time())))
        for team in teams:
            print("TeamID: {}\t\tGameID: {}".format(team['team_id'], team['game_id']))
            if team['game_id'] is not None:
                if team['game_type'] != 'mining':
                    continue
                nowtime = time.time()
                nowgame = gameObj[str(team['game_id'])]
                if nowtime > team['mine_end_time']:
                    if nowgame["winner_team_id"] == team['team_id']:
                        game_stats["wins"] += 1
                    else:
                        game_stats["losses"] += 1
                    game_stats["total_tus"] += Web3.fromWei(nowgame["miner_tus_reward"], "ether")
                    game_stats["total_cra"] += Web3.fromWei(nowgame["miner_cra_reward"], "ether")
                    try:
                        endGame(address, key, team['game_id'])
                    except:
                        pass
                else:
                    length = len(nowgame['process'])
                    # print(json.dumps(nowgame, indent=4, sort_keys=True))
                    if nowgame["winner_team_id"] is None and length > 1 and length < 6:
                        if nowgame['process'][length-1]['action'] == 'attack' or nowgame['process'][length-1]['action'] == 'reinforce-attack':
                            if nowtime - nowgame['process'][length-1]['transaction_time'] < ATTACK_TIME_SECONDS:
                                lend(address, key, nowgame)
                            else:
                                print("\tToo late to reinforce: {}   ".format(nowgame['game_id']))
                    else:
                        print("\t-> Game waiting to end...")
            else:
                try:
                    startGame(address, key, team['team_id'])
                except:
                    pass
            time.sleep(1)

        print("=" * 30)
        for k, v in game_stats.items():
            print("{}: {}".format(k.upper(), v))
        print("=" * 30)
        print("\n\n")
        time.sleep(60 * 1)


if __name__ == "__main__":
    while True:
        try:
            print("==================Crabada Bot====================")
            monitor()
        except Exception as e:
            traceback.print_exc()
            print("Bot failed, retrying in 5 seconds...\n" + str(e))
            break
        time.sleep(5)
