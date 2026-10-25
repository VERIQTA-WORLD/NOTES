"""Optional Slack/Telegram delivery. Preview is the default; credentials stay in environment."""
import argparse
import json
import os
from urllib.parse import urlsplit
from urllib.request import Request,urlopen
from urllib.error import HTTPError,URLError
import cookbook as cb

def payload(channel,text):
    if channel=='slack':
        url=os.environ.get('SLACK_WEBHOOK_URL','')
        if not url.startswith('https://hooks.slack.com/services/'):raise ValueError('Set a Slack incoming webhook URL')
        return url,{'text':text}
    token=os.environ.get('TELEGRAM_BOT_TOKEN','');chat=os.environ.get('TELEGRAM_CHAT_ID','')
    if not token or not chat:raise ValueError('Set Telegram token and chat ID')
    if any(c not in '0123456789:abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ_-' for c in token):raise ValueError('Invalid bot token format')
    return 'https://api.telegram.org/bot'+token+'/sendMessage',{'chat_id':chat,'text':text}
def main():
    os.umask(0o077)
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('channel',choices=['slack','telegram']);p.add_argument('--text',default='Veriqta scheduled-job notification test');p.add_argument('--deliver',action='store_true');a=p.parse_args()
    if not a.deliver:
        cb.save(cb.BASE/'outbox'/('veriqta-'+a.channel+'-'+cb.stamp()+'.json'),{'channel':a.channel,'text':a.text})
        print('Preview saved; nothing sent');return
    url,data=payload(a.channel,a.text)
    # Do not log URLs or exception text: bot tokens/webhook secrets are part of the URL.
    try:
        with urlopen(Request(url,data=json.dumps(data).encode(),headers={'Content-Type':'application/json'}),timeout=10) as response:
            raw=response.read(65536)
            if response.status!=200:raise ValueError('Notification endpoint rejected request')
        if a.channel=='telegram' and not json.loads(raw).get('ok'):raise ValueError('Telegram rejected request')
        print('Notification accepted; confirm receipt in the destination')
    except (HTTPError,URLError,TimeoutError,OSError,ValueError):raise SystemExit('Notification delivery failed; check protected provider configuration')
if __name__=='__main__':main()
