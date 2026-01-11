// Template for Redis operations testing

const redis = require('redis');

describe('Redis Operations', () => {
  let client;

  beforeAll(async () => {
    // Setup Redis connection
    client = redis.createClient({
      socket: {
        host: process.env.REDIS_HOST || 'localhost',
        port: process.env.REDIS_PORT || 6379
      }
    });

    await client.connect();
  });

  afterAll(async () => {
    await client.quit();
  });

  afterEach(async () => {
    // Clean up test data after each test
    await client.flushDb();
  });

  describe('String operations', () => {
    it('should set and get a string value', async () => {
      await client.set('test:key', 'test value');
      const value = await client.get('test:key');
      expect(value).toBe('test value');
    });

    it('should set a value with expiration', async () => {
      await client.setEx('test:expiring', 2, 'expires soon');
      const value = await client.get('test:expiring');
      expect(value).toBe('expires soon');

      const ttl = await client.ttl('test:expiring');
      expect(ttl).toBeGreaterThan(0);
      expect(ttl).toBeLessThanOrEqual(2);
    });

    it('should return null for non-existent key', async () => {
      const value = await client.get('test:nonexistent');
      expect(value).toBeNull();
    });

    it('should delete a key', async () => {
      await client.set('test:todelete', 'delete me');
      const deleted = await client.del('test:todelete');
      expect(deleted).toBe(1);

      const value = await client.get('test:todelete');
      expect(value).toBeNull();
    });

    it('should check if key exists', async () => {
      await client.set('test:exists', 'I exist');
      const exists = await client.exists('test:exists');
      expect(exists).toBe(1);

      const notExists = await client.exists('test:notexists');
      expect(notExists).toBe(0);
    });
  });

  describe('Hash operations', () => {
    it('should set and get hash fields', async () => {
      await client.hSet('test:hash', 'field1', 'value1');
      await client.hSet('test:hash', 'field2', 'value2');

      const value1 = await client.hGet('test:hash', 'field1');
      expect(value1).toBe('value1');

      const all = await client.hGetAll('test:hash');
      expect(all).toEqual({
        field1: 'value1',
        field2: 'value2'
      });
    });

    it('should set multiple hash fields at once', async () => {
      await client.hSet('test:multihash', {
        field1: 'value1',
        field2: 'value2',
        field3: 'value3'
      });

      const all = await client.hGetAll('test:multihash');
      expect(Object.keys(all)).toHaveLength(3);
    });

    it('should delete hash field', async () => {
      await client.hSet('test:hash', 'field1', 'value1');
      await client.hDel('test:hash', 'field1');

      const value = await client.hGet('test:hash', 'field1');
      expect(value).toBeNull();
    });
  });

  describe('List operations', () => {
    it('should push and pop list items', async () => {
      await client.rPush('test:list', 'item1');
      await client.rPush('test:list', 'item2');
      await client.rPush('test:list', 'item3');

      const length = await client.lLen('test:list');
      expect(length).toBe(3);

      const item = await client.lPop('test:list');
      expect(item).toBe('item1');
    });

    it('should get list range', async () => {
      await client.rPush('test:list', ['item1', 'item2', 'item3', 'item4']);

      const items = await client.lRange('test:list', 0, 2);
      expect(items).toEqual(['item1', 'item2', 'item3']);
    });
  });

  describe('Set operations', () => {
    it('should add and check set members', async () => {
      await client.sAdd('test:set', 'member1');
      await client.sAdd('test:set', 'member2');
      await client.sAdd('test:set', 'member3');

      const isMember = await client.sIsMember('test:set', 'member1');
      expect(isMember).toBe(true);

      const members = await client.sMembers('test:set');
      expect(members).toContain('member1');
      expect(members).toHaveLength(3);
    });

    it('should not add duplicate set members', async () => {
      await client.sAdd('test:set', 'member1');
      await client.sAdd('test:set', 'member1');

      const count = await client.sCard('test:set');
      expect(count).toBe(1);
    });
  });

  describe('Sorted Set operations', () => {
    it('should add and retrieve sorted set members', async () => {
      await client.zAdd('test:zset', [
        { score: 1, value: 'one' },
        { score: 2, value: 'two' },
        { score: 3, value: 'three' }
      ]);

      const members = await client.zRange('test:zset', 0, -1);
      expect(members).toEqual(['one', 'two', 'three']);
    });

    it('should get members by score range', async () => {
      await client.zAdd('test:zset', [
        { score: 1, value: 'one' },
        { score: 2, value: 'two' },
        { score: 3, value: 'three' },
        { score: 4, value: 'four' }
      ]);

      const members = await client.zRangeByScore('test:zset', 2, 3);
      expect(members).toEqual(['two', 'three']);
    });

    it('should get member rank', async () => {
      await client.zAdd('test:zset', [
        { score: 1, value: 'one' },
        { score: 2, value: 'two' },
        { score: 3, value: 'three' }
      ]);

      const rank = await client.zRank('test:zset', 'two');
      expect(rank).toBe(1); // 0-indexed
    });
  });

  describe('JSON operations (RedisJSON)', () => {
    it('should set and get JSON value', async () => {
      const data = {
        name: 'Test Object',
        value: 123,
        nested: {
          field: 'nested value'
        }
      };

      await client.json.set('test:json', '$', data);
      const retrieved = await client.json.get('test:json');
      expect(retrieved).toEqual(data);
    });

    it('should update JSON field', async () => {
      await client.json.set('test:json', '$', { count: 0 });
      await client.json.numIncrBy('test:json', '$.count', 5);

      const result = await client.json.get('test:json');
      expect(result.count).toBe(5);
    });
  });

  describe('Key expiration', () => {
    it('should expire key after TTL', async () => {
      await client.set('test:expiring', 'will expire');
      await client.expire('test:expiring', 1);

      // Wait for expiration
      await new Promise(resolve => setTimeout(resolve, 1100));

      const value = await client.get('test:expiring');
      expect(value).toBeNull();
    });

    it('should get remaining TTL', async () => {
      await client.setEx('test:ttl', 10, 'expires in 10s');
      const ttl = await client.ttl('test:ttl');
      expect(ttl).toBeGreaterThan(0);
      expect(ttl).toBeLessThanOrEqual(10);
    });
  });

  describe('Pub/Sub operations', () => {
    it('should publish and subscribe to channels', async () => {
      const subscriber = client.duplicate();
      await subscriber.connect();

      const messages = [];
      await subscriber.subscribe('test:channel', (message) => {
        messages.push(message);
      });

      await client.publish('test:channel', 'Hello World');
      await client.publish('test:channel', 'Second Message');

      // Wait for messages to be received
      await new Promise(resolve => setTimeout(resolve, 100));

      expect(messages).toContain('Hello World');
      expect(messages).toContain('Second Message');

      await subscriber.unsubscribe('test:channel');
      await subscriber.quit();
    });
  });
});
