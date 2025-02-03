# Rare-Achievements
Finds a steam user's rarest achievements. Fetches Steam API key from AWS Secrets Manager

##Setup
This project fetches an API key from AWS Secrets Manager, so be sure you have a Steam API key and an AWS account. 

Once you have an API key, create a new secret in Secrets Manager. From there, place the secret name and region in a .env folder. It should look like this

```
SECRET_NAME=<your secret name>
AWS_REGION=<region name>
```

From there, create a user in AWS IAM with the SecretsManagerReadWrite permission. Create an access key for this user

In the AWS CLI in your project, run `aws configure`. Input your access key and secret access key for the user you created, as well as your region. Anything else is fine left blank. 
