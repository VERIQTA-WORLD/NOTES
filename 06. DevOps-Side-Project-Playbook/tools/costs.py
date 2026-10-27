"""Cost Explorer daily aggregation, normalized comparison, Markdown report."""
import argparse,csv,datetime,json
from decimal import Decimal
from pathlib import Path

def fetch(start,end,second):
    import boto3
    client=boto3.client('ce',region_name='us-east-1')
    params={'TimePeriod':{'Start':start,'End':end},'Granularity':'DAILY','Metrics':['UnblendedCost'],
      'GroupBy':[{'Type':'DIMENSION','Key':'SERVICE'}, {'Type':'TAG' if second.startswith('tag:') else 'DIMENSION','Key':second[4:] if second.startswith('tag:') else 'LINKED_ACCOUNT'}]}
    rows=[];estimated=set()
    while True:
        response=client.get_cost_and_usage(**params)
        for day in response['ResultsByTime']:
            date=day['TimePeriod']['Start']
            if day.get('Estimated'):estimated.add(date)
            for group in day['Groups']:
                metric=group['Metrics']['UnblendedCost']
                if metric['Unit']!='USD':raise ValueError('This report requires USD; do not mix currencies')
                rows.append({'date':date,'service':group['Keys'][0],'owner':group['Keys'][1], 'usd':metric['Amount']})
        token=response.get('NextPageToken')
        if not token:break
        params['NextPageToken']=token
    return rows,sorted(estimated)

def compare(rows,start,split,end):
    start,split,end=map(datetime.date.fromisoformat,(start,split,end))
    if not start<split<end:raise ValueError('Require start < split < end, using exclusive end')
    days=((split-start).days,(end-split).days);totals={}
    for row in rows:
        date=datetime.date.fromisoformat(row['date'])
        if not start<=date<end:continue
        key=(row['service'],row['owner']); values=totals.setdefault(key,[Decimal(0),Decimal(0)])
        values[int(date>=split)]+=Decimal(row['usd'])
    result=[]
    for (service,owner),(before,after) in totals.items():
        b,a=before/days[0],after/days[1]; delta=a-b
        pct=(delta/b*100) if b>0 else None
        flag=delta>=Decimal('1') and (pct is None or pct>=50)
        result.append({'service':service,'owner':owner,'baseline_per_day':b,'recent_per_day':a,'increase_per_day':delta,'percent':pct,'flag':flag})
    return sorted(result,key=lambda x:x['increase_per_day'],reverse=True)

def main():
    p=argparse.ArgumentParser();p.add_argument('--fixture');p.add_argument('--start',required=True);p.add_argument('--split',required=True);p.add_argument('--end',required=True)
    p.add_argument('--group',default='account');p.add_argument('--output',default='artifacts/costs');a=p.parse_args()
    if a.group!='account' and not a.group.startswith('tag:'):p.error('--group account or tag:Owner')
    rows=json.load(open(a.fixture)) if a.fixture else None
    estimated=[]
    if rows is None:rows,estimated=fetch(a.start,a.end,a.group)
    report=compare(rows,a.start,a.split,a.end)
    out=Path(a.output);out.mkdir(parents=True,exist_ok=True)
    fields=['service','owner','baseline_per_day','recent_per_day','increase_per_day','percent','flag']
    with (out/'ranking.csv').open('w',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=fields);writer.writeheader();writer.writerows(report)
    def money(n):return f'{n:.2f}'
    before=sum((r['baseline_per_day'] for r in report),Decimal(0));after=sum((r['recent_per_day'] for r in report),Decimal(0))
    lines=['# Veriqta cost investigation',f'\nUTC periods: [{a.start}, {a.split}) and [{a.split}, {a.end}).',
      f'\nDaily total: USD {money(before)} → {money(after)}. Change: '+(f'{(after-before)/before*100:.2f}%' if before>0 else 'new baseline')+'.',
      '\nEstimated dates: '+(', '.join(estimated) or 'none reported')+'.',
      '\n| Service | Account / tag | Baseline USD/day | Recent USD/day | Increase USD/day | Change | Review |',
      '|---|---|---:|---:|---:|---:|---|']
    for r in report:
        clean=lambda s:str(s).replace('|','/').replace('\n',' ')
        pct='new / nonpositive baseline' if r['percent'] is None else f"{r['percent']:.2f}%"
        lines.append(f"| {clean(r['service'])} | {clean(r['owner'])} | {money(r['baseline_per_day'])} | {money(r['recent_per_day'])} | {money(r['increase_per_day'])} | {pct} | {'investigate' if r['flag'] else 'ranked'} |")
    lines+=['\n## Investigation','Check usage type, resource inventory, traffic, deployments, allocation tags, discounts and credits. A cost increase alone does not establish its cause.',
      '\n## Notification draft','Owner: assign from inventory. Impact: use the ranked increases above. Next action: review the largest contributors and record approved recommendations.']
    (out/'report.md').write_text('\n'.join(lines)+'\n')
    print(out/'report.md')
if __name__=='__main__':main()
