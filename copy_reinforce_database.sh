#!/bin/bash

scp root@bot1:/home/crabada/crabnft/logs/crabada/sniper/* logs/crabada/sniper/
scp root@bot2:/home/crabada/crabnft/logs/crabada/sniper/* logs/crabada/sniper/
scp root@bot3:/home/crabada/crabnft/logs/crabada/sniper/* logs/crabada/sniper/

scp logs/crabada/sniper/* root@bot1:/home/crabada/crabnft/logs/crabada/sniper/
scp logs/crabada/sniper/* root@bot2:/home/crabada/crabnft/logs/crabada/sniper/
scp logs/crabada/sniper/* root@bot3:/home/crabada/crabnft/logs/crabada/sniper/

scp src/config_wyndblast.py  root@bot2:/home/crabada/crabnft/src/

scp src/config_crabada.py  root@bot1:/home/crabada/crabnft/src/
scp src/config_crabada.py  root@bot2:/home/crabada/crabnft/src/
scp src/config_crabada.py  root@bot3:/home/crabada/crabnft/src/
