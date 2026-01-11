"""
Template for Redis operations testing in Python
"""
import pytest
import time
import redis
import json


class TestRedisOperations:
    """Test Redis operations"""

    @pytest.fixture
    def redis_client(self):
        """Setup Redis client"""
        client = redis.Redis(
            host=os.environ.get('REDIS_HOST', 'localhost'),
            port=int(os.environ.get('REDIS_PORT', 6379)),
            db=0,
            decode_responses=True
        )
        yield client
        # Cleanup
        client.flushdb()
        client.close()

    def test_set_and_get_string(self, redis_client):
        """Test setting and getting string values"""
        redis_client.set('test:key', 'test value')
        value = redis_client.get('test:key')
        assert value == 'test value'

    def test_set_with_expiration(self, redis_client):
        """Test setting value with expiration"""
        redis_client.setex('test:expiring', 2, 'expires soon')
        value = redis_client.get('test:expiring')
        assert value == 'expires soon'

        ttl = redis_client.ttl('test:expiring')
        assert 0 < ttl <= 2

    def test_get_nonexistent_key(self, redis_client):
        """Test getting non-existent key returns None"""
        value = redis_client.get('test:nonexistent')
        assert value is None

    def test_delete_key(self, redis_client):
        """Test deleting a key"""
        redis_client.set('test:todelete', 'delete me')
        deleted = redis_client.delete('test:todelete')
        assert deleted == 1

        value = redis_client.get('test:todelete')
        assert value is None

    def test_key_exists(self, redis_client):
        """Test checking if key exists"""
        redis_client.set('test:exists', 'I exist')
        exists = redis_client.exists('test:exists')
        assert exists == 1

        not_exists = redis_client.exists('test:notexists')
        assert not_exists == 0

    def test_hash_operations(self, redis_client):
        """Test hash field operations"""
        redis_client.hset('test:hash', 'field1', 'value1')
        redis_client.hset('test:hash', 'field2', 'value2')

        value1 = redis_client.hget('test:hash', 'field1')
        assert value1 == 'value1'

        all_fields = redis_client.hgetall('test:hash')
        assert all_fields == {
            'field1': 'value1',
            'field2': 'value2'
        }

    def test_hash_multiple_fields(self, redis_client):
        """Test setting multiple hash fields at once"""
        redis_client.hset('test:multihash', mapping={
            'field1': 'value1',
            'field2': 'value2',
            'field3': 'value3'
        })

        all_fields = redis_client.hgetall('test:multihash')
        assert len(all_fields) == 3

    def test_hash_delete_field(self, redis_client):
        """Test deleting hash field"""
        redis_client.hset('test:hash', 'field1', 'value1')
        redis_client.hdel('test:hash', 'field1')

        value = redis_client.hget('test:hash', 'field1')
        assert value is None

    def test_list_operations(self, redis_client):
        """Test list push and pop operations"""
        redis_client.rpush('test:list', 'item1', 'item2', 'item3')

        length = redis_client.llen('test:list')
        assert length == 3

        item = redis_client.lpop('test:list')
        assert item == 'item1'

    def test_list_range(self, redis_client):
        """Test getting list range"""
        redis_client.rpush('test:list', 'item1', 'item2', 'item3', 'item4')

        items = redis_client.lrange('test:list', 0, 2)
        assert items == ['item1', 'item2', 'item3']

    def test_set_operations(self, redis_client):
        """Test set add and check members"""
        redis_client.sadd('test:set', 'member1', 'member2', 'member3')

        is_member = redis_client.sismember('test:set', 'member1')
        assert is_member is True

        members = redis_client.smembers('test:set')
        assert 'member1' in members
        assert len(members) == 3

    def test_set_no_duplicates(self, redis_client):
        """Test set does not allow duplicates"""
        redis_client.sadd('test:set', 'member1', 'member1')

        count = redis_client.scard('test:set')
        assert count == 1

    def test_sorted_set_operations(self, redis_client):
        """Test sorted set operations"""
        redis_client.zadd('test:zset', {
            'one': 1,
            'two': 2,
            'three': 3
        })

        members = redis_client.zrange('test:zset', 0, -1)
        assert members == ['one', 'two', 'three']

    def test_sorted_set_by_score(self, redis_client):
        """Test getting sorted set members by score range"""
        redis_client.zadd('test:zset', {
            'one': 1,
            'two': 2,
            'three': 3,
            'four': 4
        })

        members = redis_client.zrangebyscore('test:zset', 2, 3)
        assert members == ['two', 'three']

    def test_sorted_set_rank(self, redis_client):
        """Test getting member rank in sorted set"""
        redis_client.zadd('test:zset', {
            'one': 1,
            'two': 2,
            'three': 3
        })

        rank = redis_client.zrank('test:zset', 'two')
        assert rank == 1  # 0-indexed

    def test_json_operations(self, redis_client):
        """Test JSON operations (requires RedisJSON module)"""
        data = {
            'name': 'Test Object',
            'value': 123,
            'nested': {
                'field': 'nested value'
            }
        }

        # Store as JSON string if RedisJSON not available
        redis_client.set('test:json', json.dumps(data))
        retrieved_json = redis_client.get('test:json')
        retrieved = json.loads(retrieved_json)
        assert retrieved == data

    def test_key_expiration(self, redis_client):
        """Test key expires after TTL"""
        redis_client.set('test:expiring', 'will expire')
        redis_client.expire('test:expiring', 1)

        # Wait for expiration
        time.sleep(1.1)

        value = redis_client.get('test:expiring')
        assert value is None

    def test_get_ttl(self, redis_client):
        """Test getting remaining TTL"""
        redis_client.setex('test:ttl', 10, 'expires in 10s')
        ttl = redis_client.ttl('test:ttl')
        assert 0 < ttl <= 10

    def test_pipeline_operations(self, redis_client):
        """Test Redis pipeline for batching commands"""
        pipe = redis_client.pipeline()
        pipe.set('test:key1', 'value1')
        pipe.set('test:key2', 'value2')
        pipe.get('test:key1')
        pipe.get('test:key2')
        results = pipe.execute()

        assert results[0] is True  # SET result
        assert results[1] is True  # SET result
        assert results[2] == 'value1'  # GET result
        assert results[3] == 'value2'  # GET result

    def test_transaction(self, redis_client):
        """Test Redis transaction with WATCH"""
        redis_client.set('test:counter', '0')

        pipe = redis_client.pipeline()
        pipe.watch('test:counter')
        pipe.multi()
        pipe.incr('test:counter')
        pipe.incr('test:counter')
        results = pipe.execute()

        value = redis_client.get('test:counter')
        assert value == '2'

    @pytest.mark.slow
    def test_pubsub_operations(self, redis_client):
        """Test pub/sub operations"""
        pubsub = redis_client.pubsub()
        pubsub.subscribe('test:channel')

        # Give subscription time to establish
        time.sleep(0.1)

        # Publish messages
        redis_client.publish('test:channel', 'Hello World')
        redis_client.publish('test:channel', 'Second Message')

        # Receive messages
        messages = []
        for i in range(3):  # First message is subscription confirmation
            message = pubsub.get_message(timeout=1)
            if message and message['type'] == 'message':
                messages.append(message['data'])

        assert 'Hello World' in messages
        assert 'Second Message' in messages

        pubsub.unsubscribe('test:channel')
        pubsub.close()
