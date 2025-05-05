import logging
import boto3
from botocore.exceptions import ClientError

from app.main.config import AWSConfig


def upload_file(file_content, path):
    """
    Upload a file to an S3 bucket

    :param file_content: Content of the file as bytes
    :param path: S3 object path
    :return: True if file was uploaded, else False
    """
    try:
        s3_resource = boto3.resource(
            's3',
            aws_access_key_id=AWSConfig.ACCESS_KEY_ID,
            aws_secret_access_key=AWSConfig.SECRET_ACCESS_KEY,
            region_name=AWSConfig.REGION,
            # Use a custom endpoint URL that includes the region
            endpoint_url=f"https://s3.{AWSConfig.REGION}.amazonaws.com"
        )

        bucket = s3_resource.Bucket(AWSConfig.S3_BUCKET)
        bucket.Object(path).put(Body=file_content)
        return True
    except ClientError as e:
        logging.error(f"Error uploading file to S3: {e}")
        return False


def create_presigned_url(object_name, expiration=3600):
    """
    Generate a presigned URL to share an S3 object

    :param object_name: S3 object name
    :param expiration: Time in seconds for the presigned URL to remain valid
    :return: Presigned URL as string. If error, returns None.
    """
    try:
        s3_client = boto3.client(
            's3',
            region_name=AWSConfig.REGION,
            aws_access_key_id=AWSConfig.ACCESS_KEY_ID,
            aws_secret_access_key=AWSConfig.SECRET_ACCESS_KEY,
            # Use a custom endpoint URL that includes the region
            endpoint_url=f"https://s3.{AWSConfig.REGION}.amazonaws.com"
        )

        response = s3_client.generate_presigned_url(
            'get_object',
            Params={
                'Bucket': AWSConfig.S3_BUCKET,
                'Key': object_name
            },
            ExpiresIn=expiration
        )
        return response
    except ClientError as e:
        logging.error(f"Error creating presigned URL: {e}")
        return None