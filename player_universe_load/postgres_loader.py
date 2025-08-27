import json
from datetime import datetime
from typing import Dict, Union, Optional

import psycopg2


class PostgresLoader:
    def __init__(self, connection_string: str):
        """
        Initialize with database connection string

        Args:
            connection_string: Full PostgreSQL connection string
        """
        self.connection_string = connection_string
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
        """Get a PostgreSQL connection using connection string"""
        conn = psycopg2.connect(self.connection_string)
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
            model_fields = getattr(model_class, "__fields__", None)
            if model_fields:
                # Pydantic v1 style
                for field_name, field_info in model_fields.items():
                    field_type = field_info.annotation
                    pg_type = self.get_postgres_type(field_type)

                    # Make all fields nullable for data compatibility
                    null_constraint = ""

                    columns.append(f"{field_name} {pg_type}{null_constraint}")
            else:
                # Pydantic v2 style
                model_schema = model_class.model_json_schema()
                properties = model_schema.get("properties", {})
                # We'll make all fields nullable to handle the data we have
                
                for field_name, field_props in properties.items():
                    field_type_name = field_props.get("type", "string")
                    if field_type_name == "integer":
                        pg_type = "INTEGER"
                    elif field_type_name == "number":
                        pg_type = "NUMERIC"
                    elif field_type_name == "boolean":
                        pg_type = "BOOLEAN"
                    elif field_type_name == "object":
                        pg_type = "JSONB"
                    elif field_type_name == "array":
                        pg_type = "JSONB"
                    else:
                        pg_type = "VARCHAR(255)"
                    
                    # Make all fields nullable
                    null_constraint = ""
                    
                    columns.append(f"{field_name} {pg_type}{null_constraint}")

            # We'll keep the id_espn field as is, but make it the primary key
            primary_key_field = "id_espn"  # Using ESPN ID as primary key
            
            # Update the column definition to include PRIMARY KEY
            for i, col in enumerate(columns):
                if col.startswith(primary_key_field + " "):
                    columns[i] = col + " PRIMARY KEY"
                    break
            
            # Create table
            create_sql = f"""
                CREATE TABLE {table_name} (
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
            
        # Check for retired players and filter them out
        valid_data = []
        for record in data:
            if record.get("status") != "retired":
                valid_data.append(record)
                
        print(f"Found {len(data)} total records, {len(valid_data)} non-retired records")
        data = valid_data

        conn = self.get_connection()
        cursor = conn.cursor()

        try:
            # Get field names from model
            model_fields = getattr(model_class, "__fields__", None)
            if model_fields:
                # Pydantic v1 style
                field_names = list(model_fields.keys())
            else:
                # Pydantic v2 style
                model_schema = model_class.model_json_schema()
                field_names = list(model_schema.get("properties", {}).keys())
            
            # Replace id_espn with id_espn_pk for the primary key
            db_field_names = []
            for field in field_names:
                if field == "id_espn":
                    db_field_names.append("id_espn_pk")
                else:
                    db_field_names.append(field)
            
            placeholders = ", ".join(["%s"] * len(field_names))

            insert_sql = f"""
            INSERT INTO {table_name} ({", ".join(db_field_names)})
            VALUES ({placeholders})
            """

            # Prepare values for insertion
            values_list = []
            for record in data:
                # Extract values, handling missing fields gracefully
                values = []
                for field_name in field_names:
                    value = record.get(field_name)

                    # Handle nested structures
                    if isinstance(value, (dict, list)):
                        value = json.dumps(value)
                    
                    # Convert empty strings to None for database consistency
                    if value == "":
                        value = None

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
