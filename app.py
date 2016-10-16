from flask import Flask, request
import json
import requests
import os

app = Flask(__name__)

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
