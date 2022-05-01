#!/bin/bash

CRABADA_DIR=/home/crabada
REPO_DIR=$CRABADA_DIR/crabnft
EMAIL="ryeager12@gmail.com"

apt -y update
apt -y install git python3-pip python3-testresources python3.8-venv

ssh-keygen -t ed25519 -C $EMAIL -f /root/.ssh/id_ed25519 -q -N ""

TMP_GITHUB_KEY=/tmp/githubKey
ssh-keyscan github.com >> $TMP_GITHUB_KEY
ssh-keygen -lf $TMP_GITHUB_KEY
echo $TMP_GITHUB_KEY >> ~/.ssh/known_hosts
ssh-add ~/.ssh/id_ed25519

mkdir -p $CRABADA_DIR
cd $CRABADA_DIR

# add deploy keys
git clone git@github.com:rossyeager/crabnft.git $REPO_DIR

python3 -m pip install --user virtualenv

cd $REPO_DIR
python3 -m venv env
source env/bin/activate
pip install wheel
pip install -r requirements.txt

mkdir -p $REPO_DIR/logs/bot
mkdir -p $REPO_DIR/logs/sniper

# copy logs dir
# copy config

# tmux new -s mining-bot
cd $REPO_DIR/src
