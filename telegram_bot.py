import asyncio
import re
import time
from collections import defaultdict
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from bot_instance import generate_with_service

# Configuration
TELEGRAM_BOT_TOKEN = "8514379496:AAEdzVEEtpfI8BhAjK4h3GdkljhBZi-U1ko"  # Your bot token

# Global variables for rate limiting
TRIGGER_WORD_COOLDOWN = 1  # 5 minutes in seconds
user_cooldowns = {}  # user_id -> last_trigger_time

# Add Telegram user IDs that can bypass cooldown
BYPASS_USER_IDS = []  # Example: [123456789, 987654321]

RACIST_WORDS = ['india', 'indian', 'curry', 'jew', 'jewish', 'israel', 'kike', 'kosher', 'haiti', 'goy', 'jeet', 'mick',
                'jigaboo', 'hindi', 'hindu', 'mumbai', 'israeli', 'hamas', 'nigger', 'nigga', 'mexican',
                'mexico', 'jewish', 'italy', 'italian', 'puerto rico', 'puerto rican', 'puerto', 'rican', 'rico',
                'ireland', 'irish', 'arab', 'muslim', 'libya', 'libyan', 'argentina', 'argentinian', 'ethiopian',
                'ethiopia', 'hitler', 'stalin', 'kkk', 'klux', 'klan']

SEX_WORDS = ['fuck', 'fucking', 'fucker', 'pussy', 'vagina', 'naked', 'fag', 'homo', 'homosexual', 'gay', 'hooker',
             'queer', 'tranny', 'transvestite', 'transexual', 'crossdresser', 'tart', 'tits', 'titties', 'striptease',
             'strip', 'cunt', 'minge', 'tuff', 'muff', 'lesbian', 'lesbians', 'dyke', 'dick', 'ass', 'asshole', 'hard',
             'straight', 'brothel', 'whorehouse', 'furry', 'rape', 'pedophiles', 'masturbate', 'jerk', 'cock', 'cum',
             'faggot', 'escort', 'suck', 'butt', 'sniff', 'sniffer', 'epstein','trump']

ALL_TRIGGERS = RACIST_WORDS + SEX_WORDS
EXCEPTIONS = []  # Add any words to exclude


def can_bypass_cooldown(user_id):
    """Check if user can bypass cooldown (specified user IDs)"""
    return user_id in BYPASS_USER_IDS


def is_cooldown_active(user_id):
    """Check if trigger word cooldown is still active for specific user"""
    current_time = time.time()
    if user_id in user_cooldowns:
        return (current_time - user_cooldowns[user_id]) < TRIGGER_WORD_COOLDOWN
    return False


def update_cooldown(user_id):
    """Update the last response time for trigger words for specific user"""
    user_cooldowns[user_id] = time.time()


def trigger_counter(trigger_words):
    '''Counts if sex triggers in message > racist triggers to enable sex joke prompt'''
    racist_counter = 0
    sex_counter = 0
    for word in trigger_words:
        if word in RACIST_WORDS:
            racist_counter += 1
        else:
            sex_counter += 1
    return sex_counter > racist_counter


def trigger_counter_reply(trigger_words):
    '''Counts if sex triggers in message >= racist triggers to enable sex joke prompt'''
    racist_counter = 0
    sex_counter = 0
    for word in trigger_words:
        if word in RACIST_WORDS:
            racist_counter += 1
        else:
            sex_counter += 1
    return sex_counter >= racist_counter


def generate_prompt(trigger_words, message):
    '''Generates a JSON-like prompt for joke generation based on trigger words'''
    print('regular prompt')
    instruction = None
    base_input = None

    if len(message.split()) <= 15:
        print(f"Message content: {message}")
        if trigger_counter(trigger_words):
            base_input = f"Tell me a sex joke about {message}"
            instruction = "You are a joker. You use first principles thinking to generate contextual and funny yet offensive sex-related jokes based on stereotypes or situations."
        else:
            base_input = f"Tell me a racist joke about {message}"
            instruction = "You are a joker. You use first principles thinking to generate contextual and funny yet offensive racist jokes based on racial stereotypes."

    elif len(message.split()) > 10:
        if len(trigger_words) < 5:
            if any(word in ALL_TRIGGERS for word in trigger_words):
                if trigger_counter(trigger_words):
                    base_input = f"Tell me a sex joke about {' '.join(trigger_words)}"
                    instruction = "You are a joker. You use first principles thinking to generate contextual and funny yet offensive racist jokes based on racial stereotypes."
                else:
                    base_input = f"Tell me a racist joke about {' '.join(trigger_words)}"
                    instruction = "You are a joker. You use first principles thinking to generate contextual and funny yet offensive racist jokes based on racial stereotypes."
        else:
            if trigger_counter(trigger_words):
                base_input = f"Tell me a sex joke about {' '.join(trigger_words[:4])}"
                instruction = "You are a joker. You use first principles thinking to generate contextual and funny yet offensive racist jokes based on racial stereotypes."
            else:
                base_input = f"Tell me a racist joke about {' '.join(trigger_words[:4])}"
                instruction = "You are a joker. You use first principles thinking to generate contextual and funny yet offensive racist jokes based on racial stereotypes."

    return f"""{{ 
        "instruction": "{instruction}",
        "input": "{base_input}",
        "response": \""""


def generate_mention_prompt(trigger_words, message):
    print('mention prompt')

    # Remove bot mention from message
    parts = message.split()
    if len(parts) > 1:
        formatted_message = ' '.join(parts[1:]).strip()
    else:
        formatted_message = ''

    print(f'formatted message: {formatted_message}')

    instruction = None
    base_input = None

    if trigger_counter_reply(trigger_words):
        base_input = f"Tell me a sex joke about {formatted_message}"
        instruction = "You are a joker. You use first principles thinking to generate contextual and funny yet offensive sex-related jokes based on stereotypes or situations."
    else:
        base_input = f"Tell me a racist joke about {formatted_message}"
        instruction = "You are a joker. You use first principles thinking to generate contextual and funny yet offensive racist jokes based on racial stereotypes."

    return f"""{{ 
        "instruction": "{instruction}",
        "input": "{base_input}",
        "response": \""""


def generate_reply_prompt(trigger_words, message):
    print('reply prompt')

    instruction = None
    base_input = None

    if trigger_counter_reply(trigger_words):
        base_input = f"Tell me a sex joke about {message}"
        instruction = "You are a joker. You use first principles thinking to generate contextual and funny yet offensive sex-related jokes based on stereotypes or situations."
    else:
        base_input = f"Tell me a racist joke about {message}"
        instruction = "You are a joker. You use first principles thinking to generate contextual and funny yet offensive racist jokes based on racial stereotypes."

    return f"""{{ 
        "instruction": "{instruction}",
        "input": "{base_input}",
        "response": \""""


def normalize_string(s):
    """Normalize a string by converting to lowercase, removing punctuation, etc."""
    s = s.lower().strip()
    s = re.sub(r'[^\w\s]', '', s)
    s = re.sub(r'\s+', ' ', s)
    return s


def format_joke(joke):
    if joke.endswith('\n'):
        joke = joke[:-1]

    pre_formatted_joke = joke.split()
    if pre_formatted_joke:
        last_word = pre_formatted_joke[-1]
        print(last_word)
        if last_word and last_word[-1].isalpha():
            print('no punctuation!')
            last_word += '.'
            pre_formatted_joke[-1] = last_word

    corrected_joke = ' '.join(pre_formatted_joke)
    if corrected_joke:
        corrected_joke = corrected_joke[0].upper() + corrected_joke[1:]

    print(f"Last word: {last_word if pre_formatted_joke else 'N/A'}")
    return corrected_joke


def generate_valid_joke(prompt_func, trigger_words, message, max_attempts=7):
    """Generates a valid joke, retrying up to max_attempts"""
    attempt = 0
    cleaned_message = re.sub(r"[<>()*~`\[\]{}|\\_^@#%$&+=]", '', message.lower())

    while attempt < max_attempts:
        try:
            prompt = prompt_func(trigger_words, cleaned_message)
            print(f"Using prompt: {prompt}")

            response = generate_with_service(
                prompt=prompt,
                max_tokens=250,
                temperature=0.9
            )

            if response is None:
                print(f"Service call failed (attempt {attempt + 1})")
                attempt += 1
                continue

            print(f"Raw model output (attempt {attempt + 1}): '{response}'")

            cleaned_message_validation = re.sub(r"[<>()*~`\[\]{}|_^@#%$&+=.,!?;:'\"“”‘'\-—–…]", '',
                                                re.sub(r'@\w+', '', message).lower()).strip()

            bot_cleaned = re.sub(r"[<>()*~`\[\]{}|_^@#%$&+=.,!?;:'\"“”‘'\-—–…]", '', response.lower()).strip()

            user_set = set(cleaned_message_validation.split())
            bot_set = set(bot_cleaned.split())
            print(user_set)
            print(bot_set)

            normalized_user_message = normalize_string(message)
            normalized_bot_response = normalize_string(response)
            input_field = prompt.split('"input": "')[1].split('",')[0] if '"input": "' in prompt else ""
            instruction_field = prompt.split('"instruction": "')[1].split('",')[
                0] if '"instruction": "' in prompt else ""
            normalized_instruction_field = normalize_string(instruction_field)

            is_invalid = (
                    cleaned_message_validation == bot_cleaned or
                    response.endswith('\\') or
                    response.endswith(' \\') or
                    response.endswith('\\ ') or
                    response.endswith(',') or
                    response.endswith('\\n') or
                    response.endswith(':') or
                    re.search(r'[\\,]\s*$', response) or
                    re.search(r'\b(tell\s+(me\s+)?a\s+joke|joke\s+about|racist\s+joke|sex\s+joke)\b', response, re.I) or
                    normalized_instruction_field in normalized_bot_response or
                    normalized_bot_response == normalized_user_message or
                    re.search(r'(you are|first principles|based on.*stereotypes)', response, re.I) or
                    re.search(r'(you are|first principles|based on.*stereotypes)', bot_cleaned, re.I) or
                    not response.strip()
            )

            if not is_invalid:
                cleaned_response = response.strip('"').strip()
                return format_joke(cleaned_response)
            else:
                print(f"Invalid response detected: '{response}' (attempt {attempt + 1})")
                attempt += 1
                if attempt == max_attempts:
                    return None

        except Exception as e:
            print(f"Joke generation error: {e}")
            return None

    return None


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send a message when the command /start is issued - only works in groups"""
    # Only respond in groups
    if update.message.chat.type in ['group', 'supergroup']:
        await update.message.reply_text(
            'Hi! I\'m a joke bot for this group. Mention me, reply to me, or use trigger words to get a joke!'
        )
    else:
        # Ignore DMs
        print(f"Received /start in DM, ignoring...")


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send a message when the command /help is issued - only works in groups"""
    if update.message.chat.type in ['group', 'supergroup']:
        await update.message.reply_text(
            'How to use me in this group:\n'
            '- Mention me with @daniel_carver_bot followed by your message\n'
            '- Reply to one of my messages\n'
            '- Use trigger words in your message (racist or sex-related words)\n\n'
            'Note: Trigger word responses are rate-limited to once per 5 minutes per user.'
        )
    else:
        print(f"Received /help in DM, ignoring...")


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle incoming messages - ONLY in group chats"""
    message = update.message

    # CRITICAL: ONLY process messages from groups/supergroups
    if message.chat.type not in ['group', 'supergroup']:
        print(f"Ignoring message from non-group chat: {message.chat.type}")
        return

    if not message or not message.text:
        return

    print(f"GROUP MESSAGE received: {message.text.split()}")
    print(f"From user: {message.from_user.username or message.from_user.id}")
    print(f"Chat type: {message.chat.type}")
    print(f"Chat title: {message.chat.title}")  # This shows the group name

    # Ignore messages from the bot itself
    if message.from_user.id == context.bot.id:
        return

    # Check for URLs
    if re.search(r'https?://[\w.-]+(?:/[\w./?=-]*)?', message.text):
        return

    # Ignore commands (messages starting with /)
    if message.text.startswith('/'):
        return

    # Check for exceptions
    if any(word in EXCEPTIONS for word in message.text.split()):
        print('caught exception')
        return

    # Clean the message
    filtered_message = re.sub(r"[.,!?;:'\"“”‘''><]", '', message.text.lower())
    print(f"Filtered message: {filtered_message.split()}")

    trigger_words = [word for word in filtered_message.split() if word in ALL_TRIGGERS]
    print(f"Trigger words detected: {trigger_words}")

    # Get bot username for mention detection
    bot_username = context.bot.username
    bot_mention = f"@{bot_username}".lower()

    # Check if bot is mentioned anywhere in the message
    is_mentioned = bot_mention in message.text.lower()

    # Handle replies to bot
    is_reply_to_bot = (message.reply_to_message and
                       message.reply_to_message.from_user.id == context.bot.id)

    # UNLIMITED: Bot mentions
    if is_mentioned:
        print(f"Bot mentioned in group {message.chat.title}!")
        response = generate_valid_joke(generate_mention_prompt, trigger_words, message.text)
        if response:
            await message.reply_text(response)
        else:
            print("Failed to generate joke for mention")

    # UNLIMITED: Replies to bot
    elif is_reply_to_bot:
        print(f'Bot reply in group {message.chat.title}')
        response = generate_valid_joke(generate_reply_prompt, trigger_words, message.text)
        if response:
            await message.reply_text(response)
        else:
            print("Failed to generate joke for reply")

    # RATE LIMITED: Trigger words in group chat
    elif trigger_words:
        user_id = message.from_user.id
        if is_cooldown_active(user_id) and not can_bypass_cooldown(user_id):
            print(f"Trigger word cooldown active for user {user_id} in group. Skipping response.")
            # Don't send cooldown messages in group to avoid spam
            return

        response = generate_valid_joke(generate_prompt, trigger_words, message.text)
        if response:
            await message.reply_text(response)
            update_cooldown(user_id)
        else:
            print("Failed to generate joke for trigger words")

    else:
        print(f'No trigger words detected in group message: {message.text}')


async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle errors."""
    print(f"Update {update} caused error {context.error}")


async def post_init(application: Application):
    """Set bot info after initialization."""
    bot_info = await application.bot.get_me()
    print(f"Bot info set - Username: @{bot_info.username}, Name: {bot_info.first_name}")
    print(f"Bot is ready to work in GROUPS only!")
    print(f"Add me to your group: https://t.me/{bot_info.username}?startgroup=true")


def main():
    """Start the bot."""
    # Create the Application
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).post_init(post_init).build()

    # Register handlers
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # Register error handler
    application.add_error_handler(error_handler)

    # Start the Bot
    print("Bot is starting...")
    print("NOTE: This bot will ONLY respond in group chats, not in DMs!")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == '__main__':
    main()