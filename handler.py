import openai
import telebot
import apidata
import firebase_admin
import json
from firebase_admin import credentials
from firebase_admin import firestore
import time


class ChatGpt:
    def __init__(self, openai_key, user_id_context):
        self.openai_key = openai_key
        self.user_id_context = str(user_id_context)

        self.keyword_lists = {
            'coding': ['code', 'python'],
            'translation': ['translate', 'translator', 'translation', 'language'],
            'grammar correction': ['grammar', 'correct', 'correction'],
            'factual answering': ['what', 'when', 'where', 'who', 'which', 'why', 'how'],
        }

        self.temperature_values = {
            'default': 0.9,
            'coding': 0,
            'translation': 0,
            'grammar correction': 0,
            'factual answering': 0
        }

    def get_context(self, prompt, previous_tokens_count=0):
        # check if the app has already been initialized with the given app name
        if not firebase_admin._apps:
            # initialize Firebase app with service account key file
            cred = credentials.Certificate('rattington-firebase.json')
            app = firebase_admin.initialize_app(cred, name='my-app-name')
        else:
            # if the app is already initialized, get the app object with the given app name
            app = firebase_admin.get_app(name='my-app-name')

        # create a Firestore client with the app object
        db = firestore.client(app)

        # get the user's document from Firebase
        user_doc = db.collection('users').document(self.user_id_context).get()

        # check if the document exists before accessing its fields
        if user_doc.exists:
            user_dict = user_doc.to_dict()

            # create a new context list if it doesn't exist yet
            if not 'context' in user_dict:
                user_dict['context'] = []

            # append the prompt to the context
            user_dict['context'].append(prompt)

            # remove the oldest prompt if the context token limit exceeds a certain number
            token_limit = 1500
            total_tokens = previous_tokens_count

            if total_tokens > token_limit:
                for i in range(2):
                    user_dict['context'].pop(0)

            #while total_tokens > token_limit and len(user_dict['context']) > 0:
            #    oldest_sentence = user_dict['context'].pop(0)
            #    total_tokens -= len(oldest_sentence.split())

            # update the user's document in Firebase
            db.collection('users').document(self.user_id_context).set(user_dict)

            return ' '.join(user_dict['context'])

        else:
            # create a new document for the user if it doesn't exist yet
            user_dict = {'context': [prompt]}
            db.collection('users').document(self.user_id_context).set(user_dict)

            return prompt


    def get_temperature(self, prompt):
        for key, keywords in self.keyword_lists.items():
            for keyword in keywords:
                if keyword in prompt:
                    temperature = self.temperature_values.get(key, self.temperature_values['default'])
                    break
            else:
                continue
            break
        else:
            temperature = self.temperature_values['default']

        return temperature

    def generate_response(self, prompt):
        context = self.get_context(prompt)
        print(context)
        prompt = "\n".join([context + prompt])
        print(prompt)
        temperature = self.get_temperature(prompt)

        openai.api_key = self.openai_key
        response = openai.Completion.create(
            engine='text-davinci-003',
            prompt=prompt,
            temperature=temperature,
            max_tokens=1500,
        )
        print(response)
        full_text = response.choices[0].text.strip()

        previous_tokens_count = response.usage.total_tokens

        #total_tokens = self.get_context(full_text, previous_tokens_count)
        context = self.get_context(full_text, previous_tokens_count)
        print(full_text)
        return full_text


class TelegramBot:
    def __init__(self, tg_token, openai_key):
        self.bot = telebot.TeleBot(tg_token)
        self.openai_key = openai_key

        # Define the message handlers
        @self.bot.message_handler(commands=["start"])
        def start_message(message):
            self.bot.send_message(message.chat.id, "Hi! What's up? How can I help you? ")

        @self.bot.message_handler(content_types=["text"])
        def send_text(message):
            try:
                prompt = message.text
                print(prompt)
                user_id_context = message.from_user.id
                self.chat_gpt = ChatGpt(self.openai_key, user_id_context)
                reply = self.chat_gpt.generate_response(prompt)  # call generate_response on instance
                print(reply)
                #time.sleep(15)
                self.bot.send_message(message.chat.id, f"{reply}")
                print(prompt)


            except Exception as ex:
                print(ex)

                self.bot.send_message(message.chat.id, "Damn... Something went wrong... I can't reply right now")






def lambda_handler(event, context):
    update = telebot.types.Update.de_json(event['body'])
    print(f'event {event}')
    print(f'update {update}')
    openai_key = apidata.openai_key
    tg_token = apidata.tg_token
    bot = TelegramBot(tg_token, openai_key)

    # Process the webhook data
    bot.bot.process_new_updates([update])

    # Return a response for AWS Lambda
    return {"statusCode": 200, "body": "Hello from Lambda!"}

if __name__ == '__main__':
    openai_key = apidata.openai_key
    tg_token  = apidata.tg_token
    webhook_url = apidata.webhook_url

    bot = TelegramBot(tg_token, openai_key)

    #bot.bot.set_webhook(url=webhook_url)
    #bot.bot.remove_webhook()
    bot.bot.polling()

