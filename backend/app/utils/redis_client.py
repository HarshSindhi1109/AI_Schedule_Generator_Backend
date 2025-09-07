import redis
import os
#from app.config import settings
from typing import Dict, Any, Optional
import json

redis_client = redis.Redis(
    host=os.getenv("REDIS_HOST", "localhost"),
    port=int(os.getenv("REDIS_PORT", 6379)),
    password=os.getenv("REDIS_PASSWORD", None),
    decode_responses=True
)

def get_redis():
    """Return the Redis client instance"""
    return redis_client

def store_assignment_constraints(key: str, constraints: Dict[str, Any]):
    """Store constraints in Redis with JSON serialization"""
    redis_client.set(key, json.dumps(constraints))

def get_assignment_constraints(key: str) -> Optional[Dict[str, Any]]:
    """Retrieve constraints from Redis"""
    data = redis_client.get(key)
    return json.loads(data) if data else None

def generate_redis_key(faculty_name: str, course_name: str) -> str:
    """Generate unique key for Redis storage"""
    return f"faculty_constraints:{faculty_name}:{course_name}"

# New functions for timetable service
def store_timetable_data(key: str, data: Any):
    """Generic method to store timetable-related data"""
    redis_client.set(key, json.dumps(data))

def get_timetable_data(key: str) -> Optional[Any]:
    """Generic method to retrieve timetable-related data"""
    data = redis_client.get(key)
    return json.loads(data) if data else None