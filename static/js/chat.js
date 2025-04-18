class ChatApp {
    constructor() {
        this.ws = null;
        this.currentUser = null;
        this.typingTimeout = null;
        this.initializeElements();
        this.initializeEventListeners();
        this.initializeTheme();
        this.connect();
    }

    initializeElements() {
        this.messagesDiv = document.getElementById('messages');
        this.messageInput = document.getElementById('messageInput');
        this.sendButton = document.getElementById('sendButton');
        this.usersList = document.getElementById('usersList');
        this.statusSpan = document.getElementById('status');
        this.fileInput = document.getElementById('fileInput');
        this.emojiButton = document.getElementById('emojiButton');
        this.emojiModal = document.getElementById('emojiModal');
        this.fileModal = document.getElementById('fileModal');
        this.typingIndicator = document.getElementById('typingIndicator');
        this.onlineCount = document.getElementById('onlineCount');
        this.themeToggle = document.getElementById('themeToggle');
        this.previewImage = document.getElementById('previewImage');
        this.fileName = document.getElementById('fileName');
        this.fileSize = document.getElementById('fileSize');
    }

    initializeEventListeners() {
        this.sendButton.addEventListener('click', () => this.sendMessage());
        this.messageInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                this.sendMessage();
            }
        });
        this.messageInput.addEventListener('input', () => this.handleTyping());
        this.fileInput.addEventListener('change', (e) => this.handleFileUpload(e));
        this.emojiButton.addEventListener('click', () => this.toggleEmojiModal());
        this.themeToggle.addEventListener('click', () => this.toggleTheme());
        document.querySelectorAll('.close-button').forEach(button => {
            button.addEventListener('click', () => {
                this.emojiModal.style.display = 'none';
                this.fileModal.style.display = 'none';
            });
        });
        document.addEventListener('click', (e) => {
            if (e.target === this.emojiModal || e.target === this.fileModal) {
                this.emojiModal.style.display = 'none';
                this.fileModal.style.display = 'none';
            }
        });
    }

    initializeTheme() {
        const savedTheme = localStorage.getItem('theme') || 'light';
        document.documentElement.setAttribute('data-theme', savedTheme);
        this.updateThemeIcon(savedTheme);
    }

    toggleTheme() {
        const currentTheme = document.documentElement.getAttribute('data-theme');
        const newTheme = currentTheme === 'light' ? 'dark' : 'light';
        document.documentElement.setAttribute('data-theme', newTheme);
        localStorage.setItem('theme', newTheme);
        this.updateThemeIcon(newTheme);
    }

    updateThemeIcon(theme) {
        const icon = this.themeToggle.querySelector('i');
        icon.className = theme === 'light' ? 'fas fa-moon' : 'fas fa-sun';
    }

    async connect() {
        this.currentUser = prompt('لطفا نام کاربری خود را وارد کنید:');
        if (!this.currentUser) {
            alert('لطفا نام کاربری معتبر وارد کنید');
            return;
        }

        try {
            this.ws = new WebSocket(`ws://${window.location.host}/ws/${this.currentUser}`);

            this.ws.onopen = () => {
                this.statusSpan.innerHTML = '<i class="fas fa-circle"></i> متصل';
                this.statusSpan.style.color = 'var(--success-color)';
            };

            this.ws.onclose = () => {
                this.statusSpan.innerHTML = '<i class="fas fa-circle"></i> قطع ارتباط';
                this.statusSpan.style.color = 'var(--error-color)';
                setTimeout(() => this.connect(), 5000);
            };

            this.ws.onmessage = (event) => this.handleMessage(event);
        } catch (error) {
            console.error('Error connecting to WebSocket:', error);
            this.statusSpan.innerHTML = '<i class="fas fa-circle"></i> خطا در اتصال';
            this.statusSpan.style.color = 'var(--error-color)';
        }
    }

    handleMessage(event) {
        const data = JSON.parse(event.data);
        
        switch(data.type) {
            case 'user_list':
                this.updateUserList(data.users);
                break;
            case 'message':
                this.addMessage(data);
                break;
            case 'typing':
                this.showTypingIndicator(data.usernames);
                break;
            case 'user_joined':
                this.addSystemMessage(`${data.username} به چت پیوست`);
                break;
            case 'user_left':
                this.addSystemMessage(`${data.username} چت را ترک کرد`);
                break;
            case 'reaction':
                this.addReaction(data);
                break;
        }
    }

    updateUserList(users) {
        this.usersList.innerHTML = '';
        this.onlineCount.textContent = users.length;
        
        users.forEach(user => {
            const userDiv = document.createElement('div');
            userDiv.className = 'user';
            userDiv.innerHTML = `
                <div class="user-status ${user.online ? 'online' : 'offline'}"></div>
                <span>${user.username}</span>
            `;
            this.usersList.appendChild(userDiv);
        });
    }

    addMessage(data) {
        const messageDiv = document.createElement('div');
        messageDiv.className = `message ${data.sender === this.currentUser ? 'sent' : 'received'}`;
        messageDiv.setAttribute('data-message-id', data.id);
        
        let content = data.content;
        if (data.file_info) {
            content += `<div class="file-preview" onclick="chatApp.showFilePreview('${data.file_info.file_path}')">
                <img src="/uploads/${data.file_info.file_path}" alt="فایل ارسالی">
            </div>`;
        }

        messageDiv.innerHTML = `
            <div class="message-content">${content}</div>
            <div class="message-info">
                <span>${data.sender}</span>
                <span>${new Date(data.timestamp).toLocaleTimeString()}</span>
            </div>
            <div class="message-actions">
                <button onclick="chatApp.reactToMessage('${data.id}', '👍')">👍</button>
                <button onclick="chatApp.reactToMessage('${data.id}', '❤️')">❤️</button>
                <button onclick="chatApp.reactToMessage('${data.id}', '😂')">😂</button>
            </div>
        `;
        
        this.messagesDiv.appendChild(messageDiv);
        this.messagesDiv.scrollTop = this.messagesDiv.scrollHeight;
    }

    addSystemMessage(text) {
        const messageDiv = document.createElement('div');
        messageDiv.className = 'message system';
        messageDiv.textContent = text;
        this.messagesDiv.appendChild(messageDiv);
        this.messagesDiv.scrollTop = this.messagesDiv.scrollHeight;
    }

    showTypingIndicator(usernames) {
        if (usernames.length > 0) {
            this.typingIndicator.textContent = `${usernames.join('، ')} در حال تایپ است...`;
            this.typingIndicator.style.display = 'block';
        } else {
            this.typingIndicator.style.display = 'none';
        }
    }

    handleTyping() {
        this.ws.send(JSON.stringify({
            type: 'typing',
            username: this.currentUser
        }));

        clearTimeout(this.typingTimeout);
        this.typingTimeout = setTimeout(() => {
            this.ws.send(JSON.stringify({
                type: 'not_typing',
                username: this.currentUser
            }));
        }, 3000);
    }

    async sendMessage() {
        const content = this.messageInput.value.trim();
        if (content) {
            this.ws.send(JSON.stringify({
                type: 'message',
                content: content,
                sender: this.currentUser
            }));
            this.messageInput.value = '';
        }
    }

    async handleFileUpload(event) {
        const file = event.target.files[0];
        if (!file) return;

        const formData = new FormData();
        formData.append('file', file);

        try {
            const response = await fetch('/upload', {
                method: 'POST',
                body: formData
            });
            const result = await response.json();

            this.ws.send(JSON.stringify({
                type: 'message',
                content: file.name,
                sender: this.currentUser,
                message_type: 'file',
                file_info: result
            }));
        } catch (error) {
            console.error('Error uploading file:', error);
            alert('خطا در آپلود فایل');
        }
    }

    showFilePreview(filePath) {
        this.previewImage.src = `/uploads/${filePath}`;
        this.fileName.textContent = filePath.split('/').pop();
        this.fileModal.style.display = 'block';
    }

    toggleEmojiModal() {
        this.emojiModal.style.display = this.emojiModal.style.display === 'block' ? 'none' : 'block';
    }

    reactToMessage(messageId, reaction) {
        this.ws.send(JSON.stringify({
            type: 'reaction',
            messageId: messageId,
            reaction: reaction,
            sender: this.currentUser
        }));
    }

    addReaction(data) {
        const message = document.querySelector(`[data-message-id="${data.message_id}"]`);
        if (message) {
            const reactionsDiv = message.querySelector('.message-reactions') || 
                               document.createElement('div');
            reactionsDiv.className = 'message-reactions';
            
            const reactionSpan = document.createElement('span');
            reactionSpan.textContent = `${data.username}: ${data.reaction}`;
            reactionsDiv.appendChild(reactionSpan);
            
            message.appendChild(reactionsDiv);
        }
    }
}

// ایجاد نمونه از کلاس چت
const chatApp = new ChatApp(); 