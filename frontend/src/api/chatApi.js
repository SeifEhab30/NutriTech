import { getToken } from "./authApi";
import { BASE_URL } from "./config";

export async function askChatbot(message, history = []) {
  const token = getToken();
  const res = await fetch(`${BASE_URL}/chat/ask`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify({ message, history }),
  });

  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || "Server error");
  }

  const data = await res.json();
  return data.reply;
}