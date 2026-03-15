"""
Export MySQL database to SQL file
Run this script to backup your database before migrating
"""
import pymysql
import os

def export_database():
    try:
        # Connect to database
        conn = pymysql.connect(
            host=os.getenv('MYSQL_HOST', 'localhost'),
            user=os.getenv('MYSQL_USER', 'root'),
            password=os.getenv('MYSQL_PASSWORD', 'mysql'),
            database=os.getenv('MYSQL_DB', 'university'),
            port=int(os.getenv('MYSQL_PORT', '3306'))
        )
        
        print("Connected to database. Exporting...")
        
        # Export professors table
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM professors")
            professors = cur.fetchall()
            
            with open('professors_backup.sql', 'w', encoding='utf-8') as f:
                f.write("-- Professors table backup\n")
                f.write("CREATE TABLE IF NOT EXISTS `professors` (\n")
                f.write("  `id` varchar(64) NOT NULL,\n")
                f.write("  `name` varchar(255) NOT NULL,\n")
                f.write("  `password_hash` varchar(255) NOT NULL,\n")
                f.write("  PRIMARY KEY (`id`)\n")
                f.write(") ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;\n\n")
                f.write("DELETE FROM `professors`;\n\n")
                
                for prof in professors:
                    f.write(f"INSERT INTO `professors` (`id`, `name`, `password_hash`) VALUES "
                           f"('{prof[0]}', '{prof[1].replace(chr(39), chr(39)+chr(39))}', '{prof[2]}');\n")
        
        print("✓ Professors table exported to professors_backup.sql")
        
        # Export classes table
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM classes")
            classes = cur.fetchall()
            
            with open('classes_backup.sql', 'w', encoding='utf-8') as f:
                f.write("-- Classes table backup\n")
                f.write("CREATE TABLE IF NOT EXISTS `classes` (\n")
                f.write("  `id` varchar(64) NOT NULL,\n")
                f.write("  `professor_id` varchar(64) NOT NULL,\n")
                f.write("  `name` varchar(255) NOT NULL,\n")
                f.write("  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,\n")
                f.write("  PRIMARY KEY (`id`),\n")
                f.write("  KEY `professor_id` (`professor_id`)\n")
                f.write(") ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;\n\n")
                f.write("DELETE FROM `classes`;\n\n")
                
                for cls in classes:
                    name_escaped = cls[2].replace("'", "''").replace("\\", "\\\\")
                    f.write(f"INSERT INTO `classes` (`id`, `professor_id`, `name`) VALUES "
                           f"('{cls[0]}', '{cls[1]}', '{name_escaped}');\n")
        
        print("✓ Classes table exported to classes_backup.sql")
        
        # Create combined backup
        with open('university_backup.sql', 'w', encoding='utf-8') as f:
            with open('professors_backup.sql', 'r', encoding='utf-8') as pf:
                f.write(pf.read())
            f.write("\n")
            with open('classes_backup.sql', 'r', encoding='utf-8') as cf:
                f.write(cf.read())
        
        print("✓ Combined backup created: university_backup.sql")
        print("\n✅ Database export complete!")
        print("\nFiles created:")
        print("  - professors_backup.sql")
        print("  - classes_backup.sql")
        print("  - university_backup.sql")
        print("\nCopy these files along with your project files to the new laptop.")
        
        conn.close()
        
    except Exception as e:
        print(f"Error exporting database: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    export_database()

