#!/bin/bash


echo "Updating and upgrading the system..."
sudo apt update && sudo apt upgrade -y


echo "Installing Git if not installed..."
sudo apt install git -y


echo "Installing Python and pip..."
sudo apt install python3 python3-pip -y


echo "Cloning the repository..."
git clone https://github.com/heroinsh/ByteChat.git

echo "change directory..."
cd ByteChat


echo "Installing dependencies..."
pip install -r requirements.txt


echo "Running the application..."
python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload

