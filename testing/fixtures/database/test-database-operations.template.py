"""
Template for database operations testing (PostgreSQL) in Python
"""
import pytest
import psycopg2
from psycopg2.extras import RealDictCursor


class TestDatabaseOperations:
    """Test PostgreSQL database operations"""

    @pytest.fixture(scope='class')
    def db_connection(self):
        """Setup database connection"""
        conn = psycopg2.connect(
            host=os.environ.get('POSTGRES_HOST', 'localhost'),
            port=os.environ.get('POSTGRES_PORT', 5432),
            database=os.environ.get('POSTGRES_DB', 'cortex_test'),
            user=os.environ.get('POSTGRES_USER', 'cortex_test'),
            password=os.environ.get('POSTGRES_PASSWORD', 'cortex_test_password')
        )

        # Setup test tables
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS test_items (
                    id SERIAL PRIMARY KEY,
                    name VARCHAR(255) NOT NULL,
                    description TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
            conn.commit()

        yield conn

        # Cleanup
        with conn.cursor() as cur:
            cur.execute('DROP TABLE IF EXISTS test_items;')
            conn.commit()
        conn.close()

    @pytest.fixture(autouse=True)
    def cleanup_data(self, db_connection):
        """Clean up test data after each test"""
        yield
        with db_connection.cursor() as cur:
            cur.execute('TRUNCATE test_items RESTART IDENTITY CASCADE;')
            db_connection.commit()

    def test_insert_record(self, db_connection):
        """Test inserting a new record"""
        with db_connection.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                "INSERT INTO test_items (name, description) VALUES (%s, %s) RETURNING *",
                ('Test Item', 'Test Description')
            )
            result = cur.fetchone()
            db_connection.commit()

        assert result is not None
        assert result['id'] is not None
        assert result['name'] == 'Test Item'
        assert result['description'] == 'Test Description'

    def test_insert_missing_required_field(self, db_connection):
        """Test insert fails with missing required field"""
        with pytest.raises(psycopg2.Error):
            with db_connection.cursor() as cur:
                cur.execute(
                    "INSERT INTO test_items (description) VALUES (%s)",
                    ('No name',)
                )
                db_connection.commit()
        db_connection.rollback()

    def test_insert_multiple_records(self, db_connection):
        """Test inserting multiple records"""
        items = [
            ('Item 1', 'Description 1'),
            ('Item 2', 'Description 2'),
            ('Item 3', 'Description 3')
        ]

        with db_connection.cursor() as cur:
            for name, description in items:
                cur.execute(
                    "INSERT INTO test_items (name, description) VALUES (%s, %s)",
                    (name, description)
                )
            db_connection.commit()

            cur.execute('SELECT COUNT(*) FROM test_items')
            count = cur.fetchone()[0]

        assert count == 3

    def test_select_all_records(self, db_connection):
        """Test retrieving all records"""
        # Insert test data
        with db_connection.cursor() as cur:
            cur.execute(
                "INSERT INTO test_items (name, description) VALUES (%s, %s)",
                ('Test Item', 'Test Description')
            )
            db_connection.commit()

            cur.execute('SELECT * FROM test_items')
            results = cur.fetchall()

        assert len(results) > 0

    def test_select_by_id(self, db_connection):
        """Test retrieving a specific record by id"""
        with db_connection.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                "INSERT INTO test_items (name, description) VALUES (%s, %s) RETURNING id",
                ('Specific Item', 'Specific Description')
            )
            item_id = cur.fetchone()['id']
            db_connection.commit()

            cur.execute('SELECT * FROM test_items WHERE id = %s', (item_id,))
            result = cur.fetchone()

        assert result is not None
        assert result['name'] == 'Specific Item'

    def test_select_with_filter(self, db_connection):
        """Test filtering records with WHERE clause"""
        with db_connection.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                "INSERT INTO test_items (name, description) VALUES (%s, %s)",
                ('Filtered Item', 'Filtered Description')
            )
            db_connection.commit()

            cur.execute("SELECT * FROM test_items WHERE name LIKE %s", ('%Filtered%',))
            results = cur.fetchall()

        assert len(results) > 0
        assert 'Filtered' in results[0]['name']

    def test_update_record(self, db_connection):
        """Test updating a record"""
        with db_connection.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                "INSERT INTO test_items (name, description) VALUES (%s, %s) RETURNING id",
                ('Original Name', 'Original Description')
            )
            item_id = cur.fetchone()['id']
            db_connection.commit()

            cur.execute(
                "UPDATE test_items SET name = %s, updated_at = CURRENT_TIMESTAMP WHERE id = %s",
                ('Updated Name', item_id)
            )
            db_connection.commit()

            cur.execute('SELECT * FROM test_items WHERE id = %s', (item_id,))
            result = cur.fetchone()

        assert result['name'] == 'Updated Name'

    def test_update_nonexistent_record(self, db_connection):
        """Test updating non-existent record returns 0 rows"""
        with db_connection.cursor() as cur:
            cur.execute(
                "UPDATE test_items SET name = %s WHERE id = %s",
                ('Updated Name', 99999)
            )
            db_connection.commit()
            assert cur.rowcount == 0

    def test_delete_record(self, db_connection):
        """Test deleting a record"""
        with db_connection.cursor() as cur:
            cur.execute(
                "INSERT INTO test_items (name, description) VALUES (%s, %s) RETURNING id",
                ('To Be Deleted', 'Will be removed')
            )
            item_id = cur.fetchone()[0]
            db_connection.commit()

            cur.execute('DELETE FROM test_items WHERE id = %s', (item_id,))
            db_connection.commit()

            cur.execute('SELECT * FROM test_items WHERE id = %s', (item_id,))
            result = cur.fetchone()

        assert result is None

    def test_transaction_commit(self, db_connection):
        """Test successful transaction commit"""
        try:
            with db_connection.cursor() as cur:
                cur.execute(
                    "INSERT INTO test_items (name, description) VALUES (%s, %s)",
                    ('Transaction Item 1', 'Desc 1')
                )
                cur.execute(
                    "INSERT INTO test_items (name, description) VALUES (%s, %s)",
                    ('Transaction Item 2', 'Desc 2')
                )
                db_connection.commit()

                cur.execute('SELECT COUNT(*) FROM test_items')
                count = cur.fetchone()[0]

            assert count == 2
        except Exception as e:
            db_connection.rollback()
            raise e

    def test_transaction_rollback(self, db_connection):
        """Test transaction rollback on error"""
        try:
            with db_connection.cursor() as cur:
                cur.execute(
                    "INSERT INTO test_items (name, description) VALUES (%s, %s)",
                    ('Transaction Item', 'Desc')
                )

                # This should fail (missing required field)
                cur.execute(
                    "INSERT INTO test_items (description) VALUES (%s)",
                    ('Should fail',)
                )
                db_connection.commit()
        except psycopg2.Error:
            db_connection.rollback()

            # Verify rollback
            with db_connection.cursor() as cur:
                cur.execute('SELECT COUNT(*) FROM test_items')
                count = cur.fetchone()[0]
            assert count == 0
