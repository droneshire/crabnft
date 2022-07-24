#!/bin/bash

CRABADA_DIR=/home/crabada
REPO_DIR=$CRABADA_DIR/crabnft
# DROPBOX_DIR=/root/Dropbox/crabada_bot
EMAIL="ryeager12@gmail.com"
GROUP_NUM=1

wait_for_input() {
    echo "Press any key to continue"
    while [ true ] ; do
        read -t 3 -n 1
        if [ $? = 0 ] ; then
            exit ;
        else
            echo "waiting for the keypress"
        fi
    done
}


# echo "deb [arch=i386,amd64] http://linux.dropbox.com/ubuntu disco main" >> /etc/apt/sources.list.d/dropbox.list
# sudo apt-key adv --keyserver keyserver.ubuntu.com --recv-keys 1C61A2656FB57B7E4DE0F4C1FC918B335044912E
# apt -y update
# apt -y install dropbox

apt -y update
apt -y install git python3-pip python3-testresources python3.8-venv python3-gpg

ssh-keygen -t ed25519 -C $EMAIL -f /root/.ssh/id_ed25519 -q -N ""

TMP_GITHUB_KEY=/tmp/githubKey
ssh-keyscan github.com >> $TMP_GITHUB_KEY
ssh-keygen -lf $TMP_GITHUB_KEY
echo $TMP_GITHUB_KEY >> ~/.ssh/known_hosts
ssh-add ~/.ssh/id_ed25519

mkdir -p $CRABADA_DIR
cd $CRABADA_DIR

# add deploy keys to github
wait_for_input

git clone git@github.com:rossyeager/crabnft.git $REPO_DIR

python3 -m pip install --user virtualenv

cd $REPO_DIR
python3 -m venv env
source env/bin/activate

pip install wheel
pip install -r requirements.txt

# dropbox start -i

# # will need to approve the device here

# mkdir -p $DROPBOX_DIR/logs
# ln -s $DROPBOX_DIR/logs $REPO_DIR/logs

# copy logs dir if needed (should be in dropbox)
# copy config and credentials files
wait_for_input

tmux new -s mining-bot
cd $REPO_DIR
