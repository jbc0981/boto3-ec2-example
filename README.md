# AWS Boto3 EC2 Example

## Purpose
This is an example of how to use the AWS SDK for Python to create an EC2 instance in AWS. The script accomplishes three overall tasks:
1. Deploy the EC2 Instance
  * Creates a key pair for the instance and saves it to your local machine.
  * Creates a security group to include and ingress rule to allow SSH to the instance from your local IP.
2. Uses cloud-config to add two users to the instance and the ssh keys needed to allow them access over SSH.
3. Uses cloud-config to create two volumes, map them to the instance, and mount them to be able to be access from in the instance.

## ⚠ Important

- The instance that is created is a public instance that gets an elastic IP associated with it. the security group rules do not allow any ingress to the instance other than SSH from the local IP.
- The included ssh keys [user1](user1) / [user1.pub](user1.pub) and [user2](user2) / [user2.pub](user2.pub) are included in the repo for testing purposes, but best practices dictate to never include ssh keys in source control.
- The AWS Credentials (AWS_ACCESS_KEY and AWS_SECRET_ACCESS_KEY) will need to be set in the [config.yaml](config.yaml) in order for the script to be able to execute.
- Running this code might result in charges to your AWS account.

## Running the code

### Prerequisites

- You must have an AWS account, and have your default credentials and AWS Region
  configured as described in the [AWS Tools and SDKs Shared Configuration and
  Credentials Reference Guide](https://docs.aws.amazon.com/credref/latest/refdocs/creds-config-files.html).
- Python 3.7 or later
- Boto3 1.11.10 or later

### Commands

Your python environment will need to be ready to use the python modules referenced in the script.

```
pip3 install -r requirements.txt
```

Once this is completed run the below command.

```
python3 main.py
```