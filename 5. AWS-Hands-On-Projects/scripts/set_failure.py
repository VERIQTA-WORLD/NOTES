"""Toggle the controlled failure flag on this handbook's project-05 function only."""
import argparse
import lab
p=argparse.ArgumentParser(description=__doc__)
g=p.add_mutually_exclusive_group(required=True);g.add_argument('--enable',action='store_true');g.add_argument('--disable',action='store_true');a=p.parse_args()
lab.check_identity();name=lab.output('05','FunctionName')
config=lab.aws(['lambda','get-function-configuration','--function-name',name])
variables=config.get('Environment',{}).get('Variables',{})
if set(variables)-{'LAB_FAIL'}:raise SystemExit('Unexpected environment variables; inspect the lab function before changing it')
value='true' if a.enable else 'false'
import json
lab.aws(['lambda','update-function-configuration','--function-name',name,'--environment',json.dumps({'Variables':{'LAB_FAIL':value}})])
lab.aws(['lambda','wait','function-updated','--function-name',name],parsed=False)
print('Veriqta project-05 controlled failure:',value)
