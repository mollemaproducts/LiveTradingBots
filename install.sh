echo Updating the server
sudo apt-get update

echo Installing pip
sudo apt install python3-pip -y

echo Making log dirs
mkdir logs

chmod 755 ./code/run_envelope.sh

echo Installing virtual environment and packages
cd code
sudo apt-get install python3-venv
python3 -m venv .venv
source .venv/bin/activate
pip install -r ../requirements.txt
cd ..
