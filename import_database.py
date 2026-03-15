"""
Import MySQL database from SQL backup files
Run this script on the new laptop to restore the database
"""
import pymysql
import os
import re

def import_database():
    try:
        # Connect to database (make sure database exists first!)
        conn = pymysql.connect(
            host=os.getenv('MYSQL_HOST', 'localhost'),
            user=os.getenv('MYSQL_USER', 'root'),
            password=os.getenv('MYSQL_PASSWORD', 'mysql'),
            database=os.getenv('MYSQL_DB', 'university'),
            port=int(os.getenv('MYSQL_PORT', '3306'))
        )
        
        print("Connected to database. Importing...")
        
        # Read and execute SQL file
        with open('university_backup.sql', 'r', encoding='utf-8') as f:
            sql_content = f.read()
        
        # Split by semicolons and execute each statement
        statements = [s.strip() for s in sql_content.split(';') if s.strip()]
        
        with conn.cursor() as cur:
            for statement in statements:
                if statement:
                    try:
                        cur.execute(statement)
                    except Exception as e:
                        # Ignore errors for table creation if table already exists
                        if 'already exists' not in str(e).lower():
                            print(f"Warning: {e}")
        
        conn.commit()
        print("✅ Database import complete!")
        
        # Verify
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM professors")
            prof_count = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM classes")
            class_count = cur.fetchone()[0]
            print(f"\nVerification:")
            print(f"  - Professors: {prof_count}")
            print(f"  - Classes: {class_count}")
        
        conn.close()
        
    except FileNotFoundError:
        print("❌ Error: university_backup.sql not found!")
        print("Make sure the backup file is in the same directory.")
    except Exception as e:
        print(f"Error importing database: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    print("Make sure you have:")
    print("  1. Created the 'university' database")
    print("  2. Placed university_backup.sql in this directory")
    print("\nPress Enter to continue...")
    input()
    import_database()

