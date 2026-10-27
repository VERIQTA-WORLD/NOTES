"""Render enforced Kyverno signature policy for all images in one lab namespace."""
import argparse,json,pathlib
p=argparse.ArgumentParser();p.add_argument('--key',default='.private/cosign.pub');a=p.parse_args()
key=pathlib.Path(a.key).read_text()
if 'BEGIN PUBLIC KEY' not in key:raise SystemExit('Cosign public key required')
policy={'apiVersion':'kyverno.io/v1','kind':'ClusterPolicy','metadata':{'name':'veriqta-signed-images'},'spec':{'validationFailureAction':'Enforce','failurePolicy':'Fail','background':False,'rules':[{'name':'require-approved-signature','match':{'any':[{'resources':{'kinds':['Pod'],'namespaces':['veriqta-trust']}}]},'verifyImages':[{'imageReferences':['*'],'mutateDigest':True,'verifyDigest':True,'required':True,'attestors':[{'count':1,'entries':[{'keys':{'publicKeys':key}}]}]}]}]}}
print(json.dumps(policy,indent=2))
