// Template for database operations testing (PostgreSQL)

const { Client } = require('pg');

describe('Database Operations', () => {
  let client;

  beforeAll(async () => {
    // Setup database connection
    client = new Client({
      host: process.env.POSTGRES_HOST || 'localhost',
      port: process.env.POSTGRES_PORT || 5432,
      database: process.env.POSTGRES_DB || 'cortex_test',
      user: process.env.POSTGRES_USER || 'cortex_test',
      password: process.env.POSTGRES_PASSWORD || 'cortex_test_password'
    });

    await client.connect();

    // Setup test tables
    await client.query(`
      CREATE TABLE IF NOT EXISTS test_items (
        id SERIAL PRIMARY KEY,
        name VARCHAR(255) NOT NULL,
        description TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
      );
    `);
  });

  afterAll(async () => {
    // Cleanup test tables
    await client.query('DROP TABLE IF EXISTS test_items;');
    await client.end();
  });

  afterEach(async () => {
    // Clean up test data after each test
    await client.query('TRUNCATE test_items RESTART IDENTITY CASCADE;');
  });

  describe('INSERT operations', () => {
    it('should insert a new record', async () => {
      const result = await client.query(
        'INSERT INTO test_items (name, description) VALUES ($1, $2) RETURNING *',
        ['Test Item', 'Test Description']
      );

      expect(result.rows).toHaveLength(1);
      expect(result.rows[0]).toHaveProperty('id');
      expect(result.rows[0].name).toBe('Test Item');
    });

    it('should fail to insert with missing required fields', async () => {
      await expect(
        client.query('INSERT INTO test_items (description) VALUES ($1)', ['No name'])
      ).rejects.toThrow();
    });

    it('should insert multiple records', async () => {
      const items = [
        ['Item 1', 'Description 1'],
        ['Item 2', 'Description 2'],
        ['Item 3', 'Description 3']
      ];

      for (const [name, description] of items) {
        await client.query(
          'INSERT INTO test_items (name, description) VALUES ($1, $2)',
          [name, description]
        );
      }

      const result = await client.query('SELECT COUNT(*) FROM test_items');
      expect(parseInt(result.rows[0].count)).toBe(3);
    });
  });

  describe('SELECT operations', () => {
    beforeEach(async () => {
      // Insert test data
      await client.query(
        'INSERT INTO test_items (name, description) VALUES ($1, $2)',
        ['Test Item', 'Test Description']
      );
    });

    it('should retrieve all records', async () => {
      const result = await client.query('SELECT * FROM test_items');
      expect(result.rows.length).toBeGreaterThan(0);
    });

    it('should retrieve a specific record by id', async () => {
      const insertResult = await client.query(
        'INSERT INTO test_items (name, description) VALUES ($1, $2) RETURNING id',
        ['Specific Item', 'Specific Description']
      );
      const id = insertResult.rows[0].id;

      const result = await client.query(
        'SELECT * FROM test_items WHERE id = $1',
        [id]
      );

      expect(result.rows).toHaveLength(1);
      expect(result.rows[0].name).toBe('Specific Item');
    });

    it('should filter records with WHERE clause', async () => {
      await client.query(
        'INSERT INTO test_items (name, description) VALUES ($1, $2)',
        ['Filtered Item', 'Filtered Description']
      );

      const result = await client.query(
        'SELECT * FROM test_items WHERE name LIKE $1',
        ['%Filtered%']
      );

      expect(result.rows.length).toBeGreaterThan(0);
      expect(result.rows[0].name).toContain('Filtered');
    });
  });

  describe('UPDATE operations', () => {
    let testItemId;

    beforeEach(async () => {
      const result = await client.query(
        'INSERT INTO test_items (name, description) VALUES ($1, $2) RETURNING id',
        ['Original Name', 'Original Description']
      );
      testItemId = result.rows[0].id;
    });

    it('should update a record', async () => {
      await client.query(
        'UPDATE test_items SET name = $1, updated_at = CURRENT_TIMESTAMP WHERE id = $2',
        ['Updated Name', testItemId]
      );

      const result = await client.query(
        'SELECT * FROM test_items WHERE id = $1',
        [testItemId]
      );

      expect(result.rows[0].name).toBe('Updated Name');
    });

    it('should return 0 rows affected for non-existent record', async () => {
      const result = await client.query(
        'UPDATE test_items SET name = $1 WHERE id = $2',
        ['Updated Name', 99999]
      );

      expect(result.rowCount).toBe(0);
    });
  });

  describe('DELETE operations', () => {
    let testItemId;

    beforeEach(async () => {
      const result = await client.query(
        'INSERT INTO test_items (name, description) VALUES ($1, $2) RETURNING id',
        ['To Be Deleted', 'Will be removed']
      );
      testItemId = result.rows[0].id;
    });

    it('should delete a record', async () => {
      await client.query('DELETE FROM test_items WHERE id = $1', [testItemId]);

      const result = await client.query(
        'SELECT * FROM test_items WHERE id = $1',
        [testItemId]
      );

      expect(result.rows).toHaveLength(0);
    });

    it('should delete multiple records', async () => {
      await client.query(
        'INSERT INTO test_items (name, description) VALUES ($1, $2), ($3, $4)',
        ['Item 1', 'Desc 1', 'Item 2', 'Desc 2']
      );

      await client.query('DELETE FROM test_items WHERE name LIKE $1', ['Item%']);

      const result = await client.query(
        'SELECT * FROM test_items WHERE name LIKE $1',
        ['Item%']
      );

      expect(result.rows).toHaveLength(0);
    });
  });

  describe('Transaction operations', () => {
    it('should commit successful transaction', async () => {
      await client.query('BEGIN');

      try {
        await client.query(
          'INSERT INTO test_items (name, description) VALUES ($1, $2)',
          ['Transaction Item 1', 'Desc 1']
        );
        await client.query(
          'INSERT INTO test_items (name, description) VALUES ($1, $2)',
          ['Transaction Item 2', 'Desc 2']
        );

        await client.query('COMMIT');

        const result = await client.query('SELECT COUNT(*) FROM test_items');
        expect(parseInt(result.rows[0].count)).toBe(2);
      } catch (error) {
        await client.query('ROLLBACK');
        throw error;
      }
    });

    it('should rollback failed transaction', async () => {
      await client.query('BEGIN');

      try {
        await client.query(
          'INSERT INTO test_items (name, description) VALUES ($1, $2)',
          ['Transaction Item', 'Desc']
        );

        // This should fail (no name column value)
        await client.query(
          'INSERT INTO test_items (description) VALUES ($1)',
          ['Should fail']
        );

        await client.query('COMMIT');
      } catch (error) {
        await client.query('ROLLBACK');

        // Verify rollback
        const result = await client.query('SELECT COUNT(*) FROM test_items');
        expect(parseInt(result.rows[0].count)).toBe(0);
      }
    });
  });
});
