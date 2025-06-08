import os
import mysql.connector
import boto3
import json
import logging
from time import sleep
from aws_lambda_powertools import Logger
from mysql.connector import errorcode
from typing import Dict, Any

# Initialize logger
logger = Logger(service="db-initializer", level=os.getenv("LOG_LEVEL", "INFO"))


class DatabaseInitializationError(Exception):
    """Custom exception for database initialization failures"""
    pass


def get_db_connection(secret_arn: str, endpoint: str, db_name: str) -> mysql.connector.connection.MySQLConnection:
    """
    Establish database connection with retry logic
    """
    secrets_client = boto3.client('secretsmanager')
    max_attempts = 5
    attempt = 0
    wait_seconds = 5

    while attempt < max_attempts:
        try:
            secret = secrets_client.get_secret_value(SecretId=secret_arn)
            creds = json.loads(secret['SecretString'])

            conn = mysql.connector.connect(
                host=endpoint,
                user=creds['username'],
                password=creds['password'],
                database=db_name,
                connection_timeout=10,
                connect_timeout=10,
                autocommit=False
            )

            logger.info("Successfully connected to database")
            return conn

        except mysql.connector.Error as err:
            attempt += 1
            if err.errno == errorcode.CR_CONN_HOST_ERROR and attempt < max_attempts:
                logger.warning(f"Connection attempt {attempt} failed. Retrying in {wait_seconds} seconds...")
                sleep(wait_seconds)
                wait_seconds *= 2  # Exponential backoff
            else:
                logger.error(f"Database connection failed: {str(err)}")
                raise DatabaseInitializationError(f"Failed to connect to database: {str(err)}")
        except Exception as err:
            logger.error(f"Unexpected error connecting to database: {str(err)}")
            raise DatabaseInitializationError(f"Unexpected error: {str(err)}")


def execute_sql_script(conn: mysql.connector.connection.MySQLConnection, script_path: str):
    """
    Execute SQL script with transaction handling
    """
    cursor = None
    try:
        cursor = conn.cursor()

        with open(script_path, "r") as f:
            sql_commands = [cmd.strip() for cmd in f.read().split(";") if cmd.strip()]

            for command in sql_commands:
                try:
                    logger.debug(f"Executing command: {command[:100]}...")  # Log first 100 chars
                    cursor.execute(command)
                except mysql.connector.Error as err:
                    logger.error(f"Error executing command: {command[:100]}... Error: {str(err)}")
                    conn.rollback()
                    raise DatabaseInitializationError(f"SQL execution failed: {str(err)}")

        conn.commit()
        logger.info("Successfully executed SQL script")

    except Exception as err:
        logger.error(f"Error during SQL execution: {str(err)}")
        if conn:
            conn.rollback()
        raise DatabaseInitializationError(f"Script execution failed: {str(err)}")
    finally:
        if cursor:
            cursor.close()


@logger.inject_lambda_context(log_event=True)
def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Lambda function handler for database initialization
    """
    request_type = event["RequestType"]
    logger.info(f"Recieved event: {request_type} ")

    try:
        # Validate environment variables
        required_env_vars = ["DB_SECRET_ARN", "DB_ENDPOINT", "DB_NAME"]
        for var in required_env_vars:
            if var not in os.environ:
                raise DatabaseInitializationError(f"Missing required environment variable: {var}")

        secret_arn = os.environ["DB_SECRET_ARN"]
        endpoint = os.environ["DB_ENDPOINT"]
        db_name = os.environ["DB_NAME"]

        logger.info(f"Initializing database {db_name} at {endpoint}")

        # Connect to database
        conn = get_db_connection(secret_arn, endpoint, db_name)

        try:
            # Execute SQL script
            execute_sql_script(conn, "script.sql")

            return {
                "statusCode": 200,
                "body": json.dumps({
                    "message": "Database initialized successfully",
                    "database": db_name
                })
            }

        finally:
            if conn and conn.is_connected():
                conn.close()

    except DatabaseInitializationError as err:
        logger.error(f"Database initialization failed: {str(err)}")
        return {
            "statusCode": 500,
            "body": json.dumps({
                "message": "Database initialization failed",
                "error": str(err)
            })
        }
    except Exception as err:
        logger.error(f"Unexpected error: {str(err)}")
        return {
            "statusCode": 500,
            "body": json.dumps({
                "message": "Unexpected error during initialization",
                "error": str(err)
            })
        }