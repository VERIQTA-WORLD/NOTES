"""Render a table-scoped practice policy. Does not attach it to an identity."""
import argparse
import json
p=argparse.ArgumentParser(description=__doc__);p.add_argument('table_arn');a=p.parse_args()
if ':dynamodb:' not in a.table_arn or ':table/' not in a.table_arn:p.error('Provide the exact DynamoDB table ARN')
print(json.dumps({'Version':'2012-10-17','Statement':[{'Effect':'Allow','Action':['dynamodb:DescribeTable','dynamodb:PutItem','dynamodb:GetItem','dynamodb:UpdateItem','dynamodb:DeleteItem','dynamodb:Query','dynamodb:Scan'],'Resource':a.table_arn}]},indent=2))
