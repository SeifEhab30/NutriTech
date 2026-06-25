import React, { useState, useEffect, useRef } from 'react';
import styles from './Chatbot.module.css';
import { askChatbot } from "../api/chatApi";
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import rehypeRaw from 'rehype-raw';

const Chatbot = () => {
    const [messages, setMessages] = useState([]);
    const [input, setInput] = useState('');
    const [history, setHistory] = useState([]);
    const [typing, setTyping] = useState(false);
    const [isSending, setIsSending] = useState(false);

    const messagesEndRef = useRef(null);
    const textareaRef = useRef(null);
    const isMounted = useRef(false);

    const scrollToBottom = () => {
        messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
    };

    useEffect(() => {
        scrollToBottom();
    }, [messages, typing]);

    useEffect(() => {
        if (!isMounted.current) {
            addMessage(
                "assistant",
                `👋 Hi! I'm NutriTech.

I can help with:
• Nutrition info (try: oats 150g)
• Food alternatives (try: alternatives to chicken)

What would you like?`
            );
            isMounted.current = true;
        }
        textareaRef.current?.focus();
    }, []);

    const addMessage = (role, text) => {
        setMessages(prev => [...prev, { role, text }]);
    };

    const autoResize = () => {
        const textarea = textareaRef.current;
        textarea.style.height = 'auto';
        textarea.style.height = Math.min(textarea.scrollHeight, 150) + 'px';
    };

    const sendMessage = async () => {
        const text = input.trim();
        if (!text || isSending) return;

        // prior turns (before this message) -> conversation memory
        const priorHistory = history;

        addMessage("user", text);
        setHistory(prev => [...prev, { role: "user", content: text }]);
        setInput('');

        setIsSending(true);
        setTyping(true);

        try {
            const reply = await askChatbot(text, priorHistory);

            setTyping(false);

            addMessage("assistant", reply || "No response");
            setHistory(prev => [...prev, { role: "assistant", content: reply || "" }]);

        } catch (e) {
            setTyping(false);
            addMessage("assistant", "❌ Connection error. Is the backend running?");
            console.error(e);
        } finally {
            setIsSending(false);
            textareaRef.current?.focus();
        }
    };

    const handleKeyDown = (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendMessage();
        }
    };

    return (
        <div className={styles.chatbotPage}>
            <div className={styles.container}>
                <div className={styles.header}>
                    <h1 className={styles.title}>🥗 NutriTech</h1>
                </div>

                <div className={styles.chatContainer}>
                    <div className={styles.messages}>
                        {messages.map((msg, index) => (
                            <div key={index} className={`${styles.message} ${styles[msg.role]}`}>
                                <div className={styles.messageContent}>
                                    <ReactMarkdown
                                        remarkPlugins={[remarkGfm]}
                                        rehypePlugins={[rehypeRaw]}
                                    >
                                        {msg.text}
                                    </ReactMarkdown>
                                </div>
                            </div>
                        ))}

                        {typing && (
                            <div className={styles.typing}>
                                <span></span>
                                <span></span>
                                <span></span>
                            </div>
                        )}

                        <div ref={messagesEndRef} />
                    </div>

                    <div className={styles.inputArea}>
                        <div className={styles.inputWrapper}>
                            <textarea
                                ref={textareaRef}
                                className={styles.textarea}
                                value={input}
                                onChange={(e) => setInput(e.target.value)}
                                onInput={autoResize}
                                onKeyDown={handleKeyDown}
                                placeholder="Ask me anything..."
                                rows="1"
                            />

                            <button
                                className={styles.sendBtn}
                                onClick={sendMessage}
                                disabled={isSending}
                            >
                                Send
                            </button>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    );
};

export default Chatbot;