from time import sleep
import boto3
from botocore.exceptions import ClientError
import yaml
import urllib.request
import random
import string

def random_string():
  str = string.ascii_lowercase+string.digits
  return ''.join(random.choice(str) for i in range(6))

with open("./config.yaml", 'r') as stream:
  try:
      instance_config=yaml.safe_load(stream)
  except yaml.YAMLError as exc:
      print(exc)
      raise

ec2 = boto3.resource('ec2',
                    'us-east-1',
                    aws_access_key_id=instance_config['aws_access_key_id_value'],
                    aws_secret_access_key=instance_config['aws_secret_access_key_value'])
ec2_client = boto3.client('ec2',
                    'us-east-1',
                    aws_access_key_id=instance_config['aws_access_key_id_value'],
                    aws_secret_access_key=instance_config['aws_secret_access_key_value'])
ssm = boto3.client('ssm',
                  'us-east-1',
                  aws_access_key_id=instance_config['aws_access_key_id_value'],
                  aws_secret_access_key=instance_config['aws_secret_access_key_value'])

def create_ec2_key(key_name, key_file=None):
  try:
    key_pair = ec2.create_key_pair(KeyName=key_name)
    if key_file is not None:
      with open(key_file, 'w') as file:
        file.write(key_pair.key_material)
  except ClientError as exc:
    print(exc)
    raise
  else:
    return key_pair

def create_ec2_sec_grp(name, desc, ssh_ip):
  try:
    vpc = list(ec2.vpcs.filter(Filters=[{'Name': 'isDefault', 'Values': ['true']}]))[0]
  except ClientError as exc:
    print(exc)
    raise
  except IndexError as idx_exc:
    print("No default VPC listed.")
    raise

  try:
    sec_grp = vpc.create_security_group(
      GroupName=f'{name}-{random_string()}', Description=desc
    )
  except ClientError as exc:
    print(exc)
    raise

  try:
    ip_permissions = [{
      'IpProtocol': 'tcp', 'FromPort': 22, 'ToPort': 22,
      'IpRanges': [{'CidrIp': f'{ssh_ip}/32'}]
    }]
    sec_grp.authorize_ingress(IpPermissions=ip_permissions)
  except ClientError as exc:
    print(exc)
    raise
  else:
    return sec_grp

def get_ami_id(ami_type, ami_arch, ami_storage):
  ami_params = ssm.get_parameters_by_path(
      Path='/aws/service/ami-amazon-linux-latest')
  amzn2_amis = [ap for ap in ami_params['Parameters'] if
                all(query in ap['Name'] for query
                    in (ami_type, ami_arch, ami_storage))]
  if len(amzn2_amis) > 0:
      ami_image_id = amzn2_amis[0]['Value']
  elif len(ami_params) > 0:
      ami_image_id = ami_params['Parameters'][0]['Value']
  else:
      raise RuntimeError(
          "Couldn't find any AMIs. Try a different path or find one in the "
          "AWS Management Console.")
  return ami_image_id

def create_instance_profile():
  iam = boto3.resource('iam',
                  'us-east-1',
                  aws_access_key_id=instance_config['aws_access_key_id_value'],
                  aws_secret_access_key=instance_config['aws_secret_access_key_value'])
  ssm_role = iam.create_role(RoleName='ssm',
                           AssumeRolePolicyDocument="""{
    "Version":"2012-10-17",
    "Statement":[
       {
          "Effect":"Allow",
          "Principal":{
             "Service": ["ssm.amazonaws.com", "ec2.amazonaws.com"]
          },
          "Action":"sts:AssumeRole"
       }]}""")
  ssm_arn = 'arn:aws:iam::aws:policy/service-role/AmazonEC2RoleforSSM'
  ssm_role.attach_policy(PolicyArn=ssm_arn)
  
  instance_profile = iam.create_instance_profile(
    InstanceProfileName='ec2-ssm-instance-profile'
  )
  instance_profile.add_role(RoleName=ssm_role.name)

  return instance_profile

def create_ec2_instance(current_ip, ami_id, instance_params):
  key_pair = create_ec2_key("ec2-key-pair", "ec2-key-pair.pem")
  sec_grp = create_ec2_sec_grp(f"test-ec2-secgrp-{random_string()}", "Security group to allow SSH", current_ip)
  instance_profile = create_instance_profile()
  print("Sleeping for 10 sec to see if the instance profile has time to create.")
  sleep(10)
  print("Ok, I'm awake now...")
  user_data = f"""
    #cloud-config
    bootcmd:
      - test -z "$(blkid {instance_params['volumes'][0]['device']})" && mkfs -t {instance_params['volumes'][0]['type']} {instance_params['volumes'][0]['device']}
      - test -z "$(blkid {instance_params['volumes'][1]['device']})" && mkfs -t {instance_params['volumes'][1]['type']} {instance_params['volumes'][1]['device']}
      - mkdir -p {instance_params['volumes'][0]['mount']}
      - mkdir -p {instance_params['volumes'][1]['mount']}

    mounts:
      - [ "{instance_params['volumes'][0]['device']}", "{instance_params['volumes'][0]['mount']}", "{instance_params['volumes'][0]['type']}", "defaults,nofail", "0", "2" ]
      - [ "{instance_params['volumes'][1]['device']}", "{instance_params['volumes'][1]['mount']}", "{instance_params['volumes'][1]['type']}", "defaults,nofail", "0", "2" ]

    users:
      - default
      - name: {instance_params['users'][0]['login']}
        homedir: /home/{instance_params['users'][0]['login']}
        shell: /bin/bash
        ssh_authorized_keys:
          - {instance_params['users'][0]['ssh_key']}
        sudo: ALL=(ALL) NOPASSWD:ALL
      - name: {instance_params['users'][1]['login']}
        homedir: /home/{instance_params['users'][1]['login']}
        shell: /bin/bash
        ssh_authorized_keys:
          - {instance_params['users'][1]['ssh_key']}
        sudo: ALL=(ALL) NOPASSWD:ALL
        
    runcmd:
      - mkdir -p /run/mydir
      - sudo yum install -y https://s3.amazonaws.com/ec2-downloads-windows/SSMAgent/latest/linux_amd64/amazon-ssm-agent.rpm
      - sudo start amazon-ssm-agent"""
  instance = ec2.create_instances(
    ImageId=ami_id,
    UserData=user_data,
    InstanceType=instance_params['instance_type'],
    IamInstanceProfile={
      "Name": instance_profile.name
    },
    KeyName=key_pair.key_name,
    SecurityGroups=[sec_grp.group_name],
    MinCount=instance_params['min_count'],
    MaxCount=instance_params['max_count'],
    BlockDeviceMappings=[{"DeviceName": instance_params['volumes'][0]['device'], 
                          "Ebs": {"VolumeSize": instance_params['volumes'][0]['size_gb']}},
                         {"DeviceName": instance_params['volumes'][1]['device'],
                          "Ebs": {"VolumeSize": instance_params['volumes'][1]['size_gb']}}]
  )[0]

  return instance

def main():
  instance_params = instance_config['server']
  current_ip_address = urllib.request.urlopen('http://checkip.amazonaws.com')\
        .read().decode('utf-8').strip()
  ami_image_id = get_ami_id(instance_params['ami_type'], instance_params['architecture'], 'gp2')
  ec2_instance = create_ec2_instance(current_ip_address, ami_image_id, instance_params)
  print("Now I need to wait for the Instance to be in a good status to proceed.")
 
  ec2_client.get_waiter('instance_status_ok').wait(InstanceIds=[ec2_instance.instance_id])

  print("It looks like the instance has been created.")
  ec2_instance.load()
  message = f"""
  Now that the instance is created you can use the below commands to access it.
  Commands:
  1. To SSH as user1:
    - 'ssh -i user1 user1@{ec2_instance.public_dns_name}'
  2. To SSH as user2:
    - 'ssh -i user2 user2@{ec2_instance.public_dns_name}'
  
  Note* Make sure you run the command 'chmod 400 <private key file> before trying to SSH.
  """
  print(message)
  # ssh_cmd = f'ssh -i {user_name} user1@ec2-54-91-101-96.compute-1.amazonaws.com'

if __name__ == "__main__":
  main()