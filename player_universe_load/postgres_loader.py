import json
from datetime import datetime
from typing import Dict, Union

import psycopg2


class PostgresLoader:
    def __init__(self, db_params: Dict[str, str]):
        """
        Initialize with database connection parameters

        Args:
            db_params: Dictionary containing connection parameters:
                       host, dbname, user, password, port
        """
        self.db_params = db_params
        self.type_mapping = {
            str: "VARCHAR(255)",
            int: "INTEGER",
            float: "NUMERIC",
            bool: "BOOLEAN",
            dict: "JSONB",
            list: "JSONB",
            datetime: "TIMESTAMP",
        }

    def get_connection(self):
        """Get a PostgreSQL connection using the correct psycopg2 method"""
        # For psycopg2 >= 2.9.10, connection parameters should be provided as keyword arguments
        conn = psycopg2.connect(
            host=self.db_params.get("host"),
            dbname=self.db_params.get("dbname"),
            user=self.db_params.get("user"),
            password=self.db_params.get("password"),
            port=self.db_params.get("port", "5432"),
        )
        return conn

    def get_postgres_type(self, python_type) -> str:
        """Convert Python type to PostgreSQL type"""
        # Handle Optional types (in Python 3.8+)
        if hasattr(python_type, "__origin__"):
            if python_type.__origin__ is Union:
                # Check if it's Optional (Union with NoneType)
                args = python_type.__args__
                if len(args) == 2 and type(None) in args:
                    # Extract the actual type (the non-None one)
                    actual_type = args[0] if args[1] is type(None) else args[1]
                    return self.type_mapping.get(actual_type, "TEXT")

        return self.type_mapping.get(python_type, "TEXT")

    def create_table_from_pydantic_model(self, model_class, table_name: str):
        """Create table schema from Pydantic model"""
        conn = self.get_connection()
        cursor = conn.cursor()

        try:
            # Check if table exists
            cursor.execute(f"""
                    SELECT EXISTS (
                        SELECT 1 FROM information_schema.tables
                        WHERE table_name = '{table_name}'
                    )
                """)

            result = cursor.fetchone()
            if result and result[0]:
                print(f"Table {table_name} already exists")
                return

            # Generate column definitions from Pydantic model
            columns = []

            # Get field info from Pydantic model
            for field_name, field_info in model_class.__fields__.items():
                field_type = field_info.annotation
                pg_type = self.get_postgres_type(field_type)

                # Add NULL/NOT NULL constraint
                null_constraint = "" if field_info.required is False else " NOT NULL"

                columns.append(f"{field_name} {pg_type}{null_constraint}")

            # Create table
            create_sql = f"""
                CREATE TABLE {table_name} (
                    id SERIAL PRIMARY KEY,
                    {",\n                ".join(columns)},
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """

            print(f"Creating table with SQL:\n{create_sql}")
            cursor.execute(create_sql)
            conn.commit()

        except Exception as e:
            conn.rollback()
            print(f"Error creating table: {e}")
            raise
        finally:
            cursor.close()
            conn.close()

    def load_validated_json(self, json_file_path: str, model_class, table_name: str):
        """Load pre-validated JSON into PostgreSQL"""
        # Create table based on the model
        self.create_table_from_pydantic_model(model_class, table_name)

        # Read the JSON data
        with open(json_file_path, "r") as file:
            data = json.load(file)

        if not data:
            print("No data to load")
            return

        conn = self.get_connection()
        cursor = conn.cursor()

        try:
            # Get field names from model
            field_names = list(model_class.__fields__.keys())
            placeholders = ", ".join(["%s"] * len(field_names))

            insert_sql = f"""
            INSERT INTO {table_name} ({", ".join(field_names)})
            VALUES ({placeholders})
            """

            # Prepare values for insertion
            values_list = []
            for record in data:
                # Since data is already validated, we can directly extract values
                values = []
                for field_name in field_names:
                    value = record.get(field_name)

                    # Handle nested structures
                    if isinstance(value, (dict, list)):
                        value = json.dumps(value)

                    values.append(value)

                values_list.append(tuple(values))

            # Batch insert
            cursor.executemany(insert_sql, values_list)
            conn.commit()

            print(f"Successfully loaded {len(values_list)} records into {table_name}")

        except Exception as e:
            conn.rollback()
            print(f"Error loading data: {e}")
            raise
        finally:
            cursor.close()
            conn.close()

    def execute_with_retry(self, sql: str, params=None, max_retries=3):
        """Execute SQL with retry logic for better resilience"""
        retries = 0
        last_error = BaseException()

        while retries < max_retries:
            conn = None
            cursor = None
            try:
                conn = self.get_connection()
                cursor = conn.cursor()
                cursor.execute(sql, params)
                conn.commit()
                return cursor.fetchall()
            except Exception as e:
                last_error = e
                retries += 1
                print(f"Retry {retries}/{max_retries} due to: {e}")
            finally:
                if cursor is not None:
                    cursor.close()
                if conn is not None:
                    conn.close()

        raise last_error
