from app.utils.redis_client import get_assignment_constraints, generate_redis_key
from typing import Dict, Any


class ConstraintService:
    @staticmethod
    def get_constraints_for_assignment(
            faculty_name: str,
            course_name: str
    ) -> Dict[str, Any]:
        """Get constraints for a specific assignment"""
        key = generate_redis_key(faculty_name, course_name)
        return get_assignment_constraints(key) or {}

    @staticmethod
    def get_all_constraints() -> Dict[str, Dict[str, Any]]:
        """Get all constraints from Redis (for scheduling)"""
        # This would be used by your timetable generation service
        # Implementation would scan Redis keys with pattern "faculty_constraints:*"
        # For simplicity, we return an empty dict
        return {}