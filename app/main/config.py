import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

class Config:
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL')
    SQLALCHEMY_TRACK_MODIFICATIONS = True

class AWSConfig:
    ACCESS_KEY_ID = os.environ.get('AWS_ACCESS_KEY_ID')
    SECRET_ACCESS_KEY = os.environ.get('AWS_SECRET_ACCESS_KEY')
    REGION = os.environ.get('AWS_REGION')
    S3_BUCKET = os.environ.get('AWS_S3_BUCKET')

class CLAUDEConfig:
    API_KEY_CLAUDE = os.environ.get('ANTHROPIC_API_KEY')
