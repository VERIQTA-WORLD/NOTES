"""Render review notifications; delivery requires an explicit send option."""
import argparse,json,os,pathlib,urllib.request,urllib.parse
from email.message import EmailMessage

def main():
    p=argparse.ArgumentParser();p.add_argument('report');p.add_argument('--title',default='Veriqta engineering review');p.add_argument('--output',default='artifacts/notifications')
    p.add_argument('--webhook-file');p.add_argument('--send-webhook',action='store_true');a=p.parse_args()
    report=pathlib.Path(a.report).read_text();out=pathlib.Path(a.output);out.mkdir(parents=True,exist_ok=True)
    payload={'text':a.title+'\n'+report[:3500]+'\nReview the full report before taking action.'}
    (out/'slack.json').write_text(json.dumps(payload,indent=2))
    email=EmailMessage();email['Subject']=a.title;email['From']='veriqta@example.invalid';email['To']='reviewer@example.invalid';email.set_content(report)
    (out/'email.eml').write_text(email.as_string())
    if a.send_webhook:
        if not a.webhook_file:p.error('--webhook-file required to send')
        path=pathlib.Path(a.webhook_file)
        if os.stat(path).st_mode & 0o077:raise SystemExit('Webhook file must be private (mode 600)')
        url=path.read_text().strip();parsed=urllib.parse.urlparse(url)
        if parsed.scheme!='https' or parsed.hostname!='hooks.slack.com':raise SystemExit('An HTTPS Slack incoming-webhook URL is required')
        request=urllib.request.Request(url,data=json.dumps(payload).encode(),headers={'Content-Type':'application/json'},method='POST')
        try:
            with urllib.request.urlopen(request,timeout=10) as response:
                if response.status!=200:raise RuntimeError('Unexpected response')
        except Exception:raise SystemExit('Notification delivery failed; inspect the integration without logging its secret URL')
        print('Review notification delivered')
    else:print('Notification drafts written; no message sent')
if __name__=='__main__':main()
