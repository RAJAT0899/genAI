class Chatbox {
    constructor() {
        this.args = {
            openButton: document.querySelector('.chatbox__button'),
            chatBox: document.querySelector('.chatbox__support'),
            sendButton: document.querySelector('.send__button'),
            loadingIndicator: document.querySelector('.loading-indicator')
        }
        this.state = false;
        this.messages = [];
        this.websiteText = '';

        // Determine the base URL dynamically
        this.baseUrl = window.location.hostname === 'localhost' ? 'http://127.0.0.1:5000' : window.location.origin;
    }

    display() {
        const { openButton, chatBox, sendButton } = this.args;
        openButton.addEventListener('click', () => this.toggleState(chatBox));
        sendButton.addEventListener('click', () => this.onSendButton(chatBox));
        const inputField = chatBox.querySelector('input');
        inputField.addEventListener("keyup", (event) => {
            if (event.key === "Enter") {
                this.onSendButton(chatBox);
            }
        });

        // Fetch website text on page load
        this.fetchWebsiteText();
    }

    toggleState(chatbox) {
        this.state = !this.state;
        if (this.state) {
            chatbox.classList.add('chatbox--active');
        } else {
            chatbox.classList.remove('chatbox--active');
        }
    }

    fetchWebsiteText() {
        fetch(`${this.baseUrl}/scrape_website`)
            .then(response => response.json())
            .then(data => {
                this.websiteText = data.website_text;
            })
            .catch(error => {
                console.error('Error:', error);
            });
    }

    async appendMessage(chatbox, message, isStreaming = false) {
        const chatmessage = chatbox.querySelector('.chatbox__messages');

        if (isStreaming) {
            const messageElement = document.createElement('div');
            messageElement.className = 'messages__item messages__item--operator';
            messageElement.innerHTML = '<span class="loading-dots">Bot is typing</span>';
            chatmessage.appendChild(messageElement);
            chatmessage.scrollTop = chatmessage.scrollHeight;
            return messageElement;
        }

        const messageBlocks = message.message.split('\n\n');
        for (const block of messageBlocks) {
            const messageElement = document.createElement('div');
            messageElement.className = message.name === "Bot" ? 'messages__item messages__item--operator' : 'messages__item messages__item--visitor';
            if (message.name === "Bot") {
                await this.typeMessage(messageElement, block);
            } else {
                messageElement.textContent = block;
            }
            chatmessage.appendChild(messageElement);
            chatmessage.scrollTop = chatmessage.scrollHeight;
        }
    }

    async typeMessage(element, message) {
        const lines = message.split('\n').map(line => {
            if (line.startsWith('* ')) {
                return '• ' + line.substring(2); // Convert * to • for bullet points
            }
            return line;
        });

        let currentLineIndex = 0;
        let currentCharIndex = 0;

        return new Promise(resolve => {
            const typingInterval = setInterval(() => {
                if (currentLineIndex < lines.length) {
                    if (currentCharIndex < lines[currentLineIndex].length) {
                        if (currentCharIndex === 0) {
                            if (currentLineIndex > 0) {
                                element.innerHTML += '<br>';
                            }
                            const lineElement = document.createElement('span');
                            lineElement.className = 'message-line';
                            element.appendChild(lineElement);
                        }
                        const currentLine = element.lastChild;
                        currentLine.textContent += lines[currentLineIndex][currentCharIndex];
                        currentCharIndex++;
                    } else {
                        currentLineIndex++;
                        currentCharIndex = 0;
                    }
                } else {
                    clearInterval(typingInterval);
                    resolve();
                }
            }, 20);
        });
    }

    async onSendButton(chatbox) {
        const textField = chatbox.querySelector('input');
        const sendButton = chatbox.querySelector('.send__button');
        const userMessage = textField.value.trim();
        if (userMessage === "") {
            return;
        }
        const userMsgObject = { name: "User", message: userMessage };
        this.messages.push(userMsgObject);
        await this.appendMessage(chatbox, userMsgObject); // Update UI with user message immediately

        // Display loading dots
        const loadingDotsElement = await this.appendMessage(chatbox, { name: "Bot" }, true);

        fetch(`${this.baseUrl}/predict`, {
            method: 'POST',
            body: JSON.stringify({ message: userMessage, website_text: this.websiteText }),
            headers: {
                'Content-Type': 'application/json'
            },
        })
            .then(response => response.json())
            .then(async data => {
                let botMessage = data.answer;
                const followUpQuestions = data.follow_up_questions;
                loadingDotsElement.innerHTML = ''; // Clear the loading dots

                // Clean up the bot message if it starts with **
                botMessage = this.cleanBotMessage(botMessage);

                // Stream the bot response
                await this.typeMessage(loadingDotsElement, botMessage);

                // Display follow-up questions
                for (const question of followUpQuestions) {
                    const followUpMsgObject = { name: "Bot", message: question };
                    this.messages.push(followUpMsgObject);
                    await this.appendMessage(chatbox, followUpMsgObject);
                }

                // Check if the response contains a comparison table
                if (botMessage.includes('comparison between')) {
                    // Handle the comparison table display
                    this.displayComparisonTable(botMessage);
                }

                // Clear input field after sending message
                textField.value = '';
            })
            .catch(error => {
                console.error('Error:', error);
                textField.value = '';
                loadingDotsElement.innerHTML = ''; // Clear the loading dots in case of error
            });
    }

    cleanBotMessage(message) {
        // Remove all occurrences of ** around text
        return message.replace(/\*\*(.*?)\*\*/g, '$1').trim();
    }

    delay(ms) {
        return new Promise(resolve => setTimeout(resolve, ms));
    }

    displayComparisonTable(table) {
        const comparisonBox = document.querySelector('.comparison-box');
        comparisonBox.innerHTML = '<pre>' + table + '</pre>';
    }
}

const chatbox = new Chatbox();
chatbox.display();
