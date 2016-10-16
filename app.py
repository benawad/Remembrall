from flask import Flask, request
import json
import requests
import os

app = Flask(__name__)

def set_to_element(st):
    return {
        "title": st['title'],
        "item_url": "https://quizlet.com%s" % st['url'],
        # "image_url":"https://petersfancybrownhats.com/company_image.png",
        "subtitle": "%s cards created by %s" % (st['term_count'], st['created_by']),
        "buttons": [
            {
                "type": "postback",
                "title": "Import",
                "payload": "import %s" % st['id']
            }
        ]
    }

def search_quizlet(recipient_id, q):
    client_id = os.environ['QUIZLET_CLIENT_ID']
    payload = {'client_id': client_id, 'whitespace': 1}
    r = requests.get("https://api.quizlet.com/2.0/search/sets?q=%s" % q, params=payload)

    if r.status_code != 200:
        send_message(recipient_id, "Could not find any search results. Try another query")

    data = json.loads(r.text)
    list_thumbnails(recipient_id, list(map(set_to_element, data['sets'][:5])))


def fetch_quizlet(deck_id):
    client_id = os.environ['QUIZLET_CLIENT_ID']
    payload = {'client_id': client_id, 'whitespace': 1}
    r = requests.get("https://api.quizlet.com/2.0/sets/{}".format(deck_id),
            params=payload)

    if r.status_code != 200:
        return None

    data = json.loads(r.text)
    title = data['title']
    cards = data['terms']
    return {
        'id': deck_id,
        'title': title,
        'cards': cards,
    }

class ApplicationState(object):

    def __init__(self):
        self.decks = {}
        self.sessions = {}
        self.buckets = {}

    def help(self):
        return """
        Available commands:
        - import <quizlet id>
        - quiz <quizlet id>
        - list
        - stop
        """

    def perform_import(self, set_id):
        if set_id in self.decks:
            return 'This deck has already been imported.'
        deck = fetch_quizlet(set_id)
        if not deck:
            return 'Could not find a valid Quizlet deck.'
        self.decks[set_id] = deck
        return 'Imported deck {} succcessfully.'.format(set_id)

    def start_session(self, user, deck_id):
        """Starts a session."""
        if user in self.sessions:
            # invalid operation
            return 'A session is currently in progress.'

        deck = fetch_quizlet(deck_id)
        if not deck:
            return "Could not find a valid Quizlet deck."
        self.decks[deck_id] = deck

        self.sessions[user] = {
            'deck': deck_id,
        }
        self._rotate_buckets(user, deck_id)
        return "Let's play a game! {}".format(self.next_question(user))

    def next_question(self, user):
        """Asks the next question."""
        if not self.sessions[user]:
            return "You aren't currently in a session. Type 'quiz <set>' to start."

        deck_id = self.sessions[user]['deck']
        current_buckets = self._fetch_buckets(user, deck_id)
        now = current_buckets['now']
        if not now:
            return "You've answered all of the questions! " + self.stop_session()

        self.sessions[user]['is_answering'] = True

        # ask question
        return str(now[0])


    def is_answering(self, user):
        return user in self.sessions and self.sessions[user]['is_answering']


    def answer_question(self, user):
        if not self.sessions[user]:
            return "You aren't currently in a session. Type 'quiz <set>' to start."

        deck_id = self.sessions[user]['deck']
        self.sessions[user]['is_answering'] = False
        current_buckets = self._fetch_buckets(user, deck_id)
        now = current_buckets['now']

        return "The answer is {}. Did you get it right?".format(str(now[0]))

    def bucket(self, user, response):
        if not self.sessions[user]:
            return "You aren't currently in a session. Type 'quiz <set>' to start."

        deck_id = self.sessions[user]['deck']
        current_buckets = self._fetch_buckets(user, deck_id)
        now = current_buckets['now']

        # rebucket
        q = now[0]
        current_buckets['now'] = now[1:]

        resp = ""

        if response == 'easy':
            resp += "Awesome! I won't quiz you on this for a while."
            current_buckets['easy'].append(q)
        elif response == 'medium':
            resp += "Great! I'll quiz you again on that a bit later."
            current_buckets['medium'].append(q)
        elif response == 'hard':
            resp += "Good job! This is a tough one, so I'll quiz you on that soon."
            current_buckets['hard'].append(q)
        elif response == 'no':
            resp += "Uh oh. I'll quiz you on that again later this game."
            current_buckets['now'].append(q)

        return "{} Next question: {}".format(resp, self.next_question(user))


    def stop_session(self, user):
        if user not in self.sessions:
            return 'You are not currently in a session.'
        del self.sessions[user]
        return 'Thanks for playing!'

    def list(self):
        """Lists the decks available."""
        return 'Decks available: {}'.format([
            'Deck {}: {} ({} cards)'.format(deck['id'], deck['title'], len(deck['cards']))
            for key, deck in self.decks.items()
        ].join('\n'))


    def _rotate_buckets(self, user, deck_id):
        """Updates the now bucket if empty."""
        buckets = self._fetch_buckets(user, deck_id)
        while not buckets['now']:
            buckets['now'] = buckets['hard']
            buckets['hard'] = buckets['medium']
            buckets['medium'] = buckets['easy']


    def _fetch_buckets(self, user, deck_id):
        """Fetches buckets of a user and deck."""
        if not user in self.buckets:
            self.buckets[user] = {}
        user_buckets = self.buckets[user]
        if not deck_id in user_buckets:
            if not deck_id in self.decks:
                raise ValueError("Deck not found for fetch_buckets.")
            cards = self.decks[deck_id]['cards'][:]
            if not cards:
                raise ValueError("Empty deck.")
            user_buckets[deck_id] = {
                'now': cards,
                'hard': [],
                'medium': [],
                'easy': [],
            }
        return user_buckets[deck_id]


class Router(object):

    def __init__(self):
        self.state = ApplicationState()

    def handle_postback(self, sender, payload):
        send_message(sender, self.state.bucket(sender, payload))

    def handle_message(self, sender, message):
        if message.startswith('quiz'):
            send_message(sender, self.state.start_session(sender, message))
        elif message.startswith('import'):
            send_message(sender, self.state.perform_import(message[7:]))
        elif message.startswith('help'):
            send_message(sender, self.state.help())
        elif message.startswith('list'):
            send_message(sender, self.state.list())
        elif self.state.is_answering(sender):
            self.send_answer(sender, self.state.answer_question(sender))
        else:
            send_message(sender, "I'm not sure how to respond to that. Say 'help' for help.")


    def send_answer(self, sender, answer):
        message_data = {
            'recipient': {'id': sender},
            'message': {
                "attachment": {
                    "type": "template",
                    "payload": {
                        "template_type": "generic",
                        "elements": [
                            {
                                "title": answer,
                                "buttons": [
                                    {
                                        "type": "postback",
                                        "title": "Yes (easy)",
                                        "payload": "easy",
                                    },
                                    {
                                        "type": "postback",
                                        "title": "Yes (medium)",
                                        "payload": "medium",
                                    },
                                    {
                                        "type": "postback",
                                        "title": "Yes (hard)",
                                        "payload": "hard",
                                    },
                                    {
                                        "type": "postback",
                                        "title": "No",
                                        "payload": "no",
                                    },
                                ]
                            }
                        ]
                    }
                }
            }
        }
        headers = {'Content-Type': 'application/json'}
        params = {'access_token': os.environ['PAGE_ACCESS_TOKEN']}
        r = requests.post("https://graph.facebook.com/v2.6/me/messages",
                        params=params, headers=headers, data=json.dumps(message_data))
        if r.status_code == 200:
            print('Sent "%s" to %s' % (sender, message_data))
        else:
            print('FAILED to send "%s" to %s' % (sender, message_data))
            print('REASON: %s' % r.text)



router = Router()


@app.route("/")
def hello():
    return 'Hello!'

@app.route("/webhook", methods=['POST', 'GET'])
def verify():
    if request.method == 'POST':
        data = request.get_json()
        # loop through unread messages
        for m in data['entry'][0]['messaging']:
            if 'postback' in m:
                router.handle_postback(m['sender']['id'], m['postback']['payload'])
            if 'message' in m:
                if "text" in m['message']:
                    router.handle_message(m['sender']['id'], m['message']['text'])
                # send_message(m['sender']['id'], m['message']['text'])
                # send_question(m['sender']['id'])
                # search_quizlet(m['sender']['id'], m['message']['text'])
        return "ok!", 200
    else:
        token = request.args.get('hub.verify_token', '')
        mode = request.args.get('hub.mode', '')
        challenge = request.args.get('hub.challenge', '')
        correct_token = os.environ['VERIFY_TOKEN']

        if token == correct_token and mode == 'subscribe':
            return challenge, 200
        else:
            return "Something went wrong :(", 403



def send_message(recipient_id, message):
    message_data = {
            'recipient': {'id' : recipient_id},
            'message': {'text' : message}
            }
    headers = {'Content-Type': 'application/json'}
    params = {'access_token': os.environ['PAGE_ACCESS_TOKEN']}
    r = requests.post("https://graph.facebook.com/v2.6/me/messages", params=params, headers=headers, data=json.dumps(message_data))
    if r.status_code == 200:
        print('Sent "%s" to %s' % (recipient_id, message))
    else:
        print('FAILED to send "%s" to %s' % (recipient_id, message))
        print('REASON: %s' % r.text)

def send_question(recipient_id):
    message_data = {
        'recipient': {'id': recipient_id},
        'message': {
            "attachment": {
                "type": "template",
                "payload": {
                    "template_type": "generic",
                    "elements": [
                        {
                            "title": "I am a question.",
                            "buttons": [
                                {
                                    "type": "postback",
                                    "title": "Answer",
                                    "payload": "answer",
                                }
                            ]
                        }
                    ]
                }
            }
        }
    }
    headers = {'Content-Type': 'application/json'}
    params = {'access_token': os.environ['PAGE_ACCESS_TOKEN']}
    r = requests.post("https://graph.facebook.com/v2.6/me/messages",
                      params=params, headers=headers, data=json.dumps(message_data))
    if r.status_code == 200:
        print('Sent "%s" to %s' % (recipient_id, message_data))
    else:
        print('FAILED to send "%s" to %s' % (recipient_id, message_data))
        print('REASON: %s' % r.text)


def list_thumbnails(recipient_id, elements):
    message_data = {
        'recipient': {'id': recipient_id},
        'message': {
            "attachment": {
                "type": "template",
                "payload": {
                    "template_type": "generic",
                    "elements": elements
                }
            }
        }
    }
    headers = {'Content-Type': 'application/json'}
    params = {'access_token': os.environ['PAGE_ACCESS_TOKEN']}
    r = requests.post("https://graph.facebook.com/v2.6/me/messages",
                      params=params, headers=headers, data=json.dumps(message_data))
    if r.status_code == 200:
        print('Sent "%s" to %s' % (recipient_id, message_data))
    else:
        print('FAILED to send "%s" to %s' % (recipient_id, message_data))
        print('REASON: %s' % r.text)


if __name__ == "__main__":
    app.run()
