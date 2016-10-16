from flask import Flask, request
import json
import requests
import os

app = Flask(__name__)

def fetch_quizlet(deck_id):
    client_id = os.environ['QUIZLET_CLIENT_ID']
    payload = {'client_id': client_id, 'whitespace': 1}
    r = requests.get("https://api.quizlet.com/2.0/sets/{}".format(deck_id),
            params=payload)

    if r.status != 200:
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

    def perform_import(self, set_id):
        if self.decks[set_id]:
            return 'This deck has already been imported.'
        deck = fetch_quizlet(set_id)
        if not deck:
            return 'Could not find a valid Quizlet deck.'
        self.decks[set_id] = deck
        return 'Imported deck {} succcessfully.'.format(set_id)

    def start_session(self, user, deck_id):
        """Starts a session."""
        if self.sessions[user]:
            # invalid operation
            return 'A session is currently in progress.'

        self.sessions[user] = {
            'deck': deck_id,
        }

    def stop_session(self, user):
        if user not in self.sessions:
            return 'You are not currently in a session.'
        del self.sessions[user]
        return 'Thanks for playing!'

    def list(self):
        """Lists the decks available."""
        return 'Decks available: {}'.format([
            'Deck {}: {} ({} cards)'.format(deck['id'], deck['title'], len(deck['cards']))
            for deck in self.decks
        ])

state = ApplicationState()

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
                payload = m['postback']['payload']
                if payload == 'answer':
                    send_answer(m['sender']['id'])
            if 'message' in m:
                # send_message(m['sender']['id'], m['message']['text'])
                send_question(m['sender']['id'])
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

@app.route("/quizlet/<int:set_id>")
def get_quizlet(set_id):
    client_id = os.environ['QUORA_CLIENT_ID']
    payload = {'client_id': client_id, 'whitespace': 1}
    r = requests.get("https://api.quizlet.com/2.0/sets/{}".format(set_id),
            params=payload)

    if r.status_code == 200:
        data = json.loads(r.text)
        title = data['title']
        cards = data['terms']
        #db.put...
        return "Got {} flashcards!".format(title), 200

    else:
        return "Something went wrong", 500


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

def send_answer(recipient_id):
    message_data = {
        'recipient': {'id': recipient_id},
        'message': {
            "attachment": {
                "type": "template",
                "payload": {
                    "template_type": "generic",
                    "elements": [
                        {
                            "title": "I am an answer.",
                            "buttons": [
                                {
                                    "type": "postback",
                                    "title": "Wrong",
                                    "payload": "wrong",
                                },
                                {
                                    "type": "postback",
                                    "title": "Right",
                                    "payload": "right",
                                },
                                {
                                    "type": "postback",
                                    "title": "Too easy",
                                    "payload": "easy",
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
        print('Sent "%s" to %s' % (recipient_id, message_data))
    else:
        print('FAILED to send "%s" to %s' % (recipient_id, message_data))
        print('REASON: %s' % r.text)

if __name__ == "__main__":
    app.run()
