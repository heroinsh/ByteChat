# ByteChat

ByteChat is a fast and secure chatroom designed specifically for developers. It supports user authentication with login and registration features, offering a user-friendly and professional interface. With the ability to change display names, it's fully responsive and optimized for a seamless experience.

## Features

- **Public Chatroom**: Real-time communication in a public space.
- **User Authentication**: Secure login and registration.
- **Change Display Name**: Modify your display name at any time.
- **Secure**: Safety and privacy are prioritized.
- **Real-time Notifications**: Get notifications with sound for online/offline users.
- **Responsive Interface**: A sleek, user-friendly, and responsive design.
- **Emojis Support**: Currently supports sending emojis but will have built-in emoji support in future versions.
- **Private Messages**: Ability to send private messages (coming soon).
- **Profile Avatar**: Set your own profile picture (coming soon).
- **Password Change**: Securely change your password (coming soon).

## Upcoming Features

- **File Upload**: Send and receive files within the chat.
- **Invitation Links**: Send personal invites to others.
- **Profile Customization**: Set and update your avatar and profile settings.

## Installation

# Automatic (recommended for Ubuntu 22.04)
You can directly download and run the `setup.sh` script using `curl`:

```
curl -O https://raw.githubusercontent.com/heroinsh/ByteChat/main/setup.sh
chmod +x setup.sh
./setup.sh
```
manual
1. Clone this repository:
   ```
   git clone https://github.com/heroinsh/ByteChat.git
   cd ByteChat
   ```
Install the required dependencies:

```
pip install -r requirements.txt
```
Run the application:

```
python -m uvicorn main:app --reload
```
Open your browser and navigate to http://127.0.0.1:8000 to start using the chat.

License
Distributed under the  CC BY-NC License. See LICENSE for more information.

"Pain or pleasure doesn't last, but the pride or shame of your work does." — Vito
