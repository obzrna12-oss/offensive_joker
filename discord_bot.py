import asyncio
import re
import discord
from discord.ext import commands
import ollama
from bot_instance import generate_with_service
import time
from collections import defaultdict

intents = discord.Intents.default()
intents.members = True
intents.message_content = True
client = commands.Bot(command_prefix='!', intents=intents)

# Global variables for rate limiting
TRIGGER_WORD_COOLDOWN = 300  # 5 minutes in seconds
# CHANGED: Per-user cooldown instead of global
user_cooldowns = {}  # user_id -> last_trigger_time

bypass_roles = ["guidance counselor", "test role"]  # Roles that can bypass the cooldown

RACIST_WORDS = ['india', 'indian', 'curry', 'jew', 'jewish', 'israel', 'kike', 'kosher', 'haiti', 'goy', 'jeet', 'mick',
                'jigaboo', 'hindi', 'hindu', 'mumbai', 'israeli', 'hamas', 'nigger', 'nigga', 'mexican',
                'mexico', 'jewish','italy','italian','puerto rico','puerto rican','puerto','rican','rico',
                'ireland', 'irish','arab','muslim','libya','libyan','argentina','argentinian','ethiopian','ethiopia','kkk','klux','klan']

SEX_WORDS = ['fuck', 'fucking', 'pussy', 'vagina', 'naked', 'fag', 'homo', 'homosexual', 'gay', 'hooker', 'queer',
             'tranny',
             'transvestite', 'transexual', 'crossdresser', 'tart', 'tits', 'titties', 'striptease', 'strip', 'cunt',
             'minge', 'tuff', 'muff', 'lesbian', 'lesbians', 'dyke', 'dick', 'ass', 'asshole', 'hard', 'straight',
             'brothel', 'whorehouse', 'furry', 'rape', 'pedophiles', 'masturbate', 'jerk', 'cock', 'cum','faggot','escort','suck','epstein']

ALL_TRIGGERS = RACIST_WORDS + SEX_WORDS

pol_ = ['!img', '!quote', '!pol']
EXCEPTIONS = pol_

BOT_NAMES = ['MOTHER','MOTHUR']


def can_bypass_cooldown(user, guild):
    """
    Check if user can bypass cooldown (server owner or specified role)
    """
    # if user == guild.owner:
    #     return True

    user_roles = [role.name for role in user.roles]
    return any(role in bypass_roles for role in user_roles)


# CHANGED: Updated cooldown functions to be per-user
def is_cooldown_active(user_id):
    """
    Check if trigger word cooldown is still active for specific user
    """
    current_time = time.time()
    if user_id in user_cooldowns:
        return (current_time - user_cooldowns[user_id]) < TRIGGER_WORD_COOLDOWN
    return False


def update_cooldown(user_id):
    """
    Update the last response time for trigger words for specific user
    """
    user_cooldowns[user_id] = time.time()


def trigger_counter(trigger_words):
    '''
    Counts if sex triggers in message > racist triggers to enable sex joke prompt
    :param trigger_words: List of trigger words
    :return: bool
    '''
    racist_counter = 0
    sex_counter = 0
    for word in trigger_words:
        if word in RACIST_WORDS:
            racist_counter += 1
        else:
            sex_counter += 1
    return sex_counter > racist_counter


def trigger_counter_reply(trigger_words):
    '''
    Counts if sex triggers in message > racist triggers to enable sex joke prompt
    :param trigger_words: List of trigger words
    :return: bool
    '''
    racist_counter = 0
    sex_counter = 0
    for word in trigger_words:
        if word in RACIST_WORDS:
            racist_counter += 1
        else:
            sex_counter += 1
    return sex_counter >= racist_counter

def word_overlap_ratio(a: str, b: str) -> float:
    """Simple Jaccard similarity on words"""
    if not a or not b:
        return 0.0
    a_words = set(a.split())
    b_words = set(b.split())
    if not a_words or not b_words:
        return 0.0
    return len(a_words & b_words) / len(a_words | b_words)


def generate_prompt(trigger_words, message):
    '''
    Generates a JSON-like prompt for joke generation based on trigger words
    :param trigger_words: List of trigger words
    :param message: Discord message object
    :return: JSON-like prompt string
    '''

    print('regular prompt')
    instruction = None
    base_input = None
    # if not rigger word let's feed the message.content
    if not trigger_words:
        first_word = message.lower() if message.lower() in ALL_TRIGGERS else "sex"
    else:
        first_word = trigger_words[0]

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

    formatted_message = ' '.join(message.split()[1:]).strip()
    print(f'formatted message: {formatted_message}')

    '''
    Generates a JSON-like prompt for joke generation based on trigger words
    :param trigger_words: List of trigger words
    :param message: Discord message object
    :return: JSON-like prompt string
    '''
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

    '''
    Generates a JSON-like prompt for joke generation based on trigger words
    :param trigger_words: List of trigger words
    :param message: Discord message object
    :return: JSON-like prompt string
    '''
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


def generate_evaluated_prompt(trigger_words, message=None):
    print('eval prompt')

    '''
    Generates a JSON-like prompt for joke generation based on trigger words
    :param trigger_words: List of trigger words
    :param message: Discord message object
    :return: JSON-like prompt string
    '''

    base_input = f"Tell me a sex joke about {message}"
    instruction = "You are a joker. You use first principles thinking to generate contextual and funny yet offensive sex-related jokes based on stereotypes or situations."

    return f"""{{ 
        "instruction": "{instruction}",
        "input": "{base_input}",
        "response": \""""


def normalize_string(s):
    """
    Normalize a string by converting to lowercase, removing punctuation/emojis,
    normalizing whitespace, and stripping leading/trailing spaces.
    """
    s = s.lower().strip()  # Convert to lowercase and remove leading/trailing whitespace
    s = re.sub(r'[^\w\s]', '', s)  # Remove punctuation, emojis, and special characters
    s = re.sub(r'\s+', ' ', s)  # Replace multiple spaces with a single space
    return s


def format_joke(joke):

    if joke.endswith('\n'):
        joke = joke[:-1]

    pre_formatted_joke = joke.split()
    last_word = pre_formatted_joke[-1]
    print(last_word)
    if last_word[-1].isalpha():
        print('no puctuation!')
        last_word += '.'  # Add a period
        pre_formatted_joke[-1] = last_word

    corrected_joke = ' '.join(pre_formatted_joke)
    corrected_joke = corrected_joke[0].upper() + corrected_joke[1:]

    print(f"Last word: {last_word}")  # Debugging print
    return corrected_joke


def generate_valid_joke(prompt_func, trigger_words, message, max_attempts=7):
    """
    Generates a valid joke, retrying up to max_attempts if the output contains
    the input field, instruction, or exact user input repetition.
    :param prompt_func: Function to generate the prompt
    :param trigger_words: List of trigger words
    :param message: Discord message object or content string (for YouTube module)
    :param max_attempts: Maximum number of generation attempts
    :return: Tuple of (response, error_message); response is None if all attempts fail

    """
    attempt = 0
    cleaned_message = re.sub(r"[<>()*~`\[\]{}|\\_^@#%$&+=]", '', message.lower()) #added to remove < > and special chaacters before processing
    while attempt < max_attempts:
        try:
            prompt = prompt_func(trigger_words, cleaned_message)
            print(f"Using prompt: {prompt}")

            # Replace the direct llm call with service call
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

            # Extract content based on whether message is a Discord message object or string
            message_content = message

            # cleaned_message_validation = re.sub(r"[<>()*~`\[\]{}|_^@#%$&+=.,!?;:'\"“”‘’\-—–…]", '',
            #                                     re.sub(r'<@!?\d+>', '', message).lower())
            # bot_cleaned = re.sub(r"[<>()*~`\[\]{}|_^@#%$&+=.,!?;:'\"“”‘’\-—–…]", '', response.lower())
            # Add .strip() to remove trailing/leading spaces
            cleaned_message_validation = re.sub(r"[<>()*~`\[\]{}|_^@#%$&+=.,!?;:'\"“”‘'\-—–…]", '',
                                                re.sub(r'<@!?\d+>', '', message).lower()).strip()

            bot_cleaned = re.sub(r"[<>()*~`\[\]{}|_^@#%$&+=.,!?;:'\"“”‘'\-—–…]", '', response.lower()).strip()

            user_set = set(cleaned_message_validation.split())
            bot_set = set(bot_cleaned.split())
            print(user_set)
            print(bot_set)
            common_words = user_set & bot_set

            # Normalize strings for comparison
            normalized_user_message = normalize_string(message_content)
            normalized_bot_response = normalize_string(response)
            input_field = prompt.split('"input": "')[1].split('",')[0] if '"input": "' in prompt else ""
            instruction_field = prompt.split('"instruction": "')[1].split('",')[
                0] if '"instruction": "' in prompt else ""
            normalized_input_field = normalize_string(input_field)
            normalized_instruction_field = normalize_string(instruction_field)
            print(f'Response:{response}')

            overlap = word_overlap_ratio(message, response)

            # Check for invalid conditions
            is_invalid = (
                    cleaned_message_validation == bot_cleaned or
                    overlap > 0.95 or
                    response.endswith('\\') or
                    response.endswith(' \\') or
                    response.endswith(' \\') or
                    response.endswith('\\ ') or
                    response.endswith(',') or
                    response.endswith('\\n') or
                    response.endswith(':') or
                    re.search(r'[\\,]\s*$', response) or
                    re.search(r'\b(tell\s+(me\s+)?a\s+joke|joke\s+about|racist\s+joke|sex\s+joke)\b', response, re.I) or
                    #normalized_input_field in normalized_bot_response or  # Full input field
                    normalized_instruction_field in normalized_bot_response or  # Full instruction
                    normalized_bot_response == normalized_user_message or
                    re.search(r'(you are|first principles|based on.*stereotypes)', response, re.I) or
                    re.search(r'(you are|first principles|based on.*stereotypes)', bot_cleaned, re.I) or
                    # Exact user input repetition
                    not response.strip()  # Empty response
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


@client.event
async def on_message(message):
    print(message.content.split()[0])
    print(f"Message received: {message.content.split()}")

    is_reply_to_bot = message.reference and message.reference.resolved.author == client.user

    if isinstance(message.channel, discord.DMChannel):
        print(f'Dm received: {message.content}')
        return

    if message.author == client.user:
        return

    if re.search(r'https?://[\w.-]+(?:/[\w./?=-]*)?', message.content):
        return

    if message.content.startswith('!'):
        return

    if any(word in EXCEPTIONS for word in message.content.split()):
        print('caught clause 2')
        return

    if any(word.startswith('!') and len(word) <= 4 for word in message.content.split()):
        print('caught clause 3')
        return

    # filtered_message = re.sub(r"[.,!?;:'\"“”‘']", '', message.content.lower())
    filtered_message = re.sub(r"[.,!?;:'\"“”‘''><]", '', message.content.lower())
    print(f"Filtered message: {filtered_message.split()}")

    trigger_words = [word for word in filtered_message.split() if word in ALL_TRIGGERS]
    print(f"Trigger words detected: {trigger_words}")

    # Handle bot mentions - UNLIMITED
    # or client.user in message.mentions:
    if message.content.split()[0].rstrip(',.?!') in BOT_NAMES or client.user in message.mentions and not is_reply_to_bot:
        response = generate_valid_joke(generate_mention_prompt, trigger_words, message.content)
        if response:
            await message.reply(response)
        else:
            print("Failed to generate joke")

    # Handle replies to bot - UNLIMITED
    elif is_reply_to_bot:
        print('bot reply')
        response = generate_valid_joke(generate_reply_prompt, trigger_words, message.content)
        if response:
            await message.reply(response)
        else:
            print("Failed to generate joke")

    # Handle trigger words - RATE LIMITED
    elif trigger_words:
        # CHANGED: Check per-user cooldown instead of global cooldown
        if is_cooldown_active(message.author.id) and not can_bypass_cooldown(message.author, message.guild):
            print(f"Trigger word cooldown active for user {message.author}. Skipping response.")
            return

        response = generate_valid_joke(generate_prompt, trigger_words, message.content)
        if response:
            await message.reply(response)
            # CHANGED: Update per-user cooldown instead of global cooldown
            update_cooldown(message.author.id)
        else:
            print("Failed to generate joke")

    else:  # if no trigger words were found we will still let llama guard evaluate it
        print(f'No trigger words detected: {message.content}')


client.run('MTM1NDQ5NjgyMTU1MTk1NjE4MA.G2X3LM.q69XTITGZlDQZJ9wGH1pix-h2MUfFvv55T5h3k')