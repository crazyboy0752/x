import logging
import json
import re
import os
import requests
from telegram import Update
from telegram.ext import Application, MessageHandler, CommandHandler, filters, CallbackContext

# 配置日志记录
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
    filename="bot.log",  # 日志文件
    filemode="a",
)
logger = logging.getLogger(__name__)

# API 配置
XAI_API_URL = "https://api.x.ai/v1/chat/completions"
XAI_API_KEY = "  "

# 对话历史配置
MAX_HISTORY = 30
CONVERSATION_FILE = "conversations.json"  # 存储对话历史的文件

# 加载或初始化对话历史
if os.path.exists(CONVERSATION_FILE):
    with open(CONVERSATION_FILE, "r", encoding="utf-8") as file:
        user_conversations = json.load(file)
        logger.info("Loaded existing conversations from file.")
else:
    user_conversations = {}
    logger.info("No existing conversations found. Starting fresh.")

# 保存对话历史到文件
def save_conversations():
    with open(CONVERSATION_FILE, "w", encoding="utf-8") as file:
        json.dump(user_conversations, file, ensure_ascii=False, indent=4)
    logger.info("Conversations saved to file.")

# 与 x.ai 交互
def chat_with_xai(user_id: str, user_message: str) -> str:
    # 初始化用户的对话历史
    if user_id not in user_conversations:
        user_conversations[user_id] = [
            {"role": "system", "content": "You are a helpful assistant."}
        ]
    
    # 添加用户消息到对话上下文
    user_conversations[user_id].append({"role": "user", "content": user_message})
    
    # 保留最近 MAX_HISTORY 条消息
    if len(user_conversations[user_id]) > MAX_HISTORY:
        user_conversations[user_id] = user_conversations[user_id][-MAX_HISTORY:]
    
    # 构建请求数据
    payload = {
        "messages": user_conversations[user_id],
        "model": "grok-beta",
        "stream": False,
        "temperature": 0.7,
    }
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {XAI_API_KEY}",
    }
    
    try:
        # 调用 x.ai API
        response = requests.post(XAI_API_URL, headers=headers, json=payload)
        response.raise_for_status()
        response_data = response.json()
        
        # 获取机器人回复
        bot_response = response_data.get("choices", [{}])[0].get("message", {}).get("content", "Sorry, I didn't understand.")
        
        # 将机器人回复添加到对话上下文
        user_conversations[user_id].append({"role": "assistant", "content": bot_response})
        
        # 保存更新后的对话历史
        save_conversations()
        
        logger.info(f"User {user_id} - API response: {bot_response}")
        return bot_response
    
    except Exception as e:
        logger.error(f"Error for user {user_id}: {e}")
        return f"Error: {e}"
        


# 转义 MarkdownV2 的特殊字符
def escape_markdown_v2(text: str) -> str:
    """
    转义 Telegram MarkdownV2 格式的特殊字符。
    """
    # Telegram MarkdownV2 需要转义的字符
    special_chars = r'_*[]()~`>#+-=|{}.!'
    escaped_text = re.sub(f'([{re.escape(special_chars)}])', r'\\\1', text)
    return escaped_text


# 处理普通消息
async def handle_message(update: Update, context: CallbackContext):
    user_id = str(update.effective_user.id)
    user_message = update.message.text
    logger.info(f"User {user_id} sent: {user_message}")

    # 获取回复
    response = chat_with_xai(user_id, user_message)
    
    # 转义回复内容的 MarkdownV2 特殊字符
    escaped_response = escape_markdown_v2(response)
    
    try:
        # 回复用户，启用 MarkdownV2 格式
        await update.message.reply_text(escaped_response, parse_mode="MarkdownV2")
    except Exception as e:
        # 捕获错误并记录日志
        logger.error(f"Failed to send message to user {user_id}: {e}")
        await update.message.reply_text(
            "⚠️ *An error occurred while processing your message.*",
            parse_mode="MarkdownV2",
        )


# 重置对话历史
async def reset_conversation(update: Update, context: CallbackContext):
    user_id = str(update.effective_user.id)
    user_conversations[user_id] = [{"role": "system", "content": "You are a helpful assistant."}]
    save_conversations()
    await update.message.reply_text("*Conversation has been reset.*", parse_mode="Markdown")
    logger.info(f"User {user_id} reset their conversation.")

# 启动机器人
def main():
    TELEGRAM_BOT_TOKEN = "   "  # 替换为你的 Telegram 机器人 Token
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    # 添加消息处理器
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_handler(CommandHandler("reset", reset_conversation))

    logger.info("Bot started.")
    application.run_polling()

if __name__ == "__main__":
    main()
