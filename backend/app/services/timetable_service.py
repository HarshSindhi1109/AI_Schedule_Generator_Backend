from __future__ import annotations
import json
import logging
import math
import uuid
from uuid import UUID
from dataclasses import dataclass
from typing import Optional, Dict, Any, List, Tuple, Set
from collections import defaultdict
from sqlalchemy.orm import Session

from app.utils.redis_client import get_redis
from app.crud import courses as crud_courses
from app.crud import timetables as crud_timetables

# Configure logging
logger = logging.getLogger(__name__)

MAX_RETRIES = 10

DAY_RANK = {
    "Tuesday": 1, "Wednesday": 2, "Thursday": 3,
    "Monday": 4, "Friday": 5, "Saturday": 6
}

LECTURE_TIME_RANK = {
    "09:50-10:45": 6, "10:45-11:40": 5, "08:25-09:20": 4,
    "11:50-12:45": 3, "07:30-08:25": 2, "12:45-13:40": 1
}


@dataclass
class CourseNeed:
    course_name: str
    course_code: str
    credits: int
    faculty_name: str
    theory: bool
    practical: bool
    t_hours: int
    tu_hours: int
    p_hours: int
    num_sublabs: int
    division_names: List[str]
    constraints: List[Dict[str, str]]


def _to_slot_label(start: str, end: str) -> str:
    return f"{start}-{end}"


def _parse_faculty_constraints(raw: List[Dict[str, str]]) -> Dict[str, Set[str]]:
    allowed = defaultdict(set)
    for item in raw or []:
        if day := item.get("day"):
            if time := item.get("time"):
                allowed[day.capitalize()].add(time)
    return allowed


def _is_break(cell: Any) -> bool:
    return isinstance(cell, dict) and cell.get("type") in ("break", "Break")


def _slots_ok_for_lab(
        grid_day: Dict[str, List],
        slots: List[str],
        faculty: str,
        division: str,
        busy_faculty_day: Dict[str, set],
        busy_divisions_day: Dict[str, set]
) -> bool:
    for i, slot in enumerate(slots):
        if slot not in grid_day:
            return False

        if (faculty in busy_faculty_day.get(slot, set()) or
                division in busy_divisions_day.get(slot, set())):
            return False

        if grid_day.get(slot):
            for activity in grid_day[slot]:
                if _is_break(activity) or activity.get("type") in ("lecture", "lab"):
                    return False

        if i > 0:
            prev_slot_end = slots[i - 1].split('-')[1]
            current_slot_start = slot.split('-')[0]
            if prev_slot_end != current_slot_start:
                return False

    return True


def _slot_ok_for_lecture(
        grid_day: Dict[str, List],
        slot: str,
        faculty: str,
        busy_faculty_day: Dict[str, set],
        busy_divisions_day: Dict[str, set],
        lab_slots: Optional[List[Dict]] = None
) -> bool:
    if (grid_day.get(slot) or faculty in busy_faculty_day.get(slot, set()) or
            busy_divisions_day.get(slot)):
        return False

    if lab_slots:
        for slot_info in lab_slots:
            if slot in slot_info["slots"]:
                for lab_slot in slot_info["slots"]:
                    if grid_day.get(lab_slot):
                        for activity in grid_day[lab_slot]:
                            if isinstance(activity, dict) and activity.get("type") == "lab":
                                return False
    return True


def _within_faculty_allowed(day: str, slot: str, allowed: Dict[str, set]) -> bool:
    if not allowed or not (allowed_set := allowed.get(day)):
        return True
    return slot in allowed_set


def _soft_score(
        day: str,
        slot: str,
        course_name: str,
        course_credits: int,
        last_assigned_day: Dict[str, str]
) -> int:
    day_rank_map = {
        "Tuesday": 6, "Wednesday": 5, "Thursday": 4,
        "Monday": 3, "Friday": 2, "Saturday": 1
    } if course_credits >= 3 else {
        "Friday": 6, "Saturday": 5, "Monday": 4,
        "Thursday": 3, "Wednesday": 2, "Tuesday": 1
    }

    base = day_rank_map.get(day, 0) + LECTURE_TIME_RANK.get(slot, 0)

    if course_name == last_assigned_day.get("ALL"):
        base -= 10

    return base


def _collect_time_labels(layout: Dict[str, Any]) -> List[str]:
    return [_to_slot_label(ts["start"], ts["end"]) for ts in layout["time_slots"]]


def _course_needs_from_db_and_redis(
        db: Session,
        dept: str,
        sem: int,
        r
) -> List[CourseNeed]:
    logger.debug(f"Retrieving courses for dept='{dept}', sem={sem}")
    courses = crud_courses.get_courses_for_department_semester(db, dept, sem)
    logger.debug(f"Found {len(courses)} courses in database")

    rkey_fac = f"tt:{dept}:{sem}:faculty"
    try:
        fac_rows = json.loads(r.get(rkey_fac) or "[]")
    except json.JSONDecodeError:
        logger.error(f"Invalid JSON in faculty assignments")
        fac_rows = []

    logger.debug(f"Loaded {len(fac_rows)} faculty assignments from Redis")

    fac_map = defaultdict(list)
    for row in fac_rows:
        if "course_name" in row:
            fac_map[row["course_name"].strip().lower()].append(row)

    needs: List[CourseNeed] = []
    for c in courses:
        norm_name = c.course_name.strip().lower()
        for row in fac_map.get(norm_name, []):
            theory = bool(row.get("theory", False))
            practical = bool(row.get("practical", False))

            if not theory and not practical:
                continue

            needs.append(CourseNeed(
                course_name=c.course_name,
                course_code=c.course_code,
                credits=c.credits or 0,
                faculty_name=row["faculty_name"],
                theory=theory,
                practical=practical,
                t_hours=c.t_hrs if theory else 0,
                tu_hours=c.tu_hrs if practical else 0,
                p_hours=c.p_hrs if practical else 0,
                num_sublabs=int(row.get("number_of_sublabs", 0)) if practical else 0,
                division_names=row.get("division_names", []) if practical else [],
                constraints=row.get("constraints", []),
            ))

    return needs


def _expand_lab_requirements(c: CourseNeed, lab_minutes: int, slot_duration: int) -> List[Tuple[str, int, str]]:
    if not c.practical or not c.division_names:
        return []

    total_lab_hours = (c.tu_hours or 0) + (c.p_hours or 0)
    total_lab_minutes = total_lab_hours * 60
    lab_slot_len = max(1, lab_minutes // slot_duration)
    sessions_needed = max(math.ceil(total_lab_minutes / lab_minutes), len(c.division_names))

    return [
        (c.division_names[i % len(c.division_names)], lab_slot_len, "lab")
        for i in range(sessions_needed)
    ]


def _free_low_priority_slots(
        grid: Dict,
        busy_faculty: Dict,
        busy_divisions: Dict,
        max_free: int = 10
) -> int:
    freed = 0
    for day, day_schedule in grid.items():
        for slot, activities in day_schedule.items():
            if freed >= max_free:
                return freed

            if not activities:
                continue

            for activity in activities:
                if (_is_break(activity) or activity.get("protected", False) or
                        activity.get("credits", 0) >= 2):
                    continue

                if faculty := activity.get("faculty_name"):
                    busy_faculty[day][slot].discard(faculty)

                if division := activity.get("division"):
                    busy_divisions[day][slot].discard(division)

                grid[day][slot] = [a for a in activities if a != activity]
                freed += 1
                break

    return freed


def _generate_lab_slots(time_labels: List[str], lab_slot_len: int) -> List[Dict]:
    lab_slots = []
    for i in range(len(time_labels) - lab_slot_len + 1):
        slots_group = time_labels[i:i + lab_slot_len]

        is_consecutive = all(
            slots_group[j].split('-')[1] == slots_group[j + 1].split('-')[0]
            for j in range(len(slots_group) - 1)
        )

        if is_consecutive:
            start = slots_group[0].split('-')[0]
            end = slots_group[-1].split('-')[1]
            lab_slots.append({
                "slots": slots_group,
                "label": f"{start}-{end}"
            })

    return lab_slots


def _allocate_tasks(
        tasks: List[Dict],
        grid: Dict,
        busy_faculty: Dict,
        busy_divisions: Dict,
        time_labels: List[str],
        lab_slot_len: int,
        lecture_slot_len: int
) -> List[str]:
    conflicts = []
    last_course_per_day = defaultdict(dict)
    lab_allocations = defaultdict(lambda: defaultdict(int))
    subject_division_allocated = set()
    lecture_allocations = defaultdict(int)
    course_day_slots = defaultdict(set)

    lab_slots = _generate_lab_slots(time_labels, lab_slot_len)

    time_slot_adjacency = {
        slot: {time_labels[i - 1] if i > 0 else None,
               time_labels[i + 1] if i < len(time_labels) - 1 else None}
        for i, slot in enumerate(time_labels)
    }

    def _can_allocate_lab(day: str, slot_info: Dict, faculty: str, division: str) -> bool:
        return _slots_ok_for_lab(
            grid[day], slot_info["slots"], faculty, division,
            busy_faculty.get(day, {}), busy_divisions.get(day, {})
        )

    def is_consecutive_slot(course_name: str, day: str, slot: str) -> bool:
        return any(
            existing_day == day and slot in time_slot_adjacency.get(existing_slot, set())
            for existing_day, existing_slot in course_day_slots[course_name]
        )

    def can_place_lecture(course_name: str, day: str, slot: str, course: CourseNeed) -> bool:
        return (lecture_allocations[course_name] < course.t_hours and
                not is_consecutive_slot(course_name, day, slot) and
                last_course_per_day.get(day, {}).get("ALL") != course_name)

    def _get_available_lab_slots(day: str, division: str, faculty: str) -> List[Dict]:
        return [
            slot_info for slot_info in lab_slots
            if _can_allocate_lab(day, slot_info, faculty, division)
        ]

    def _prioritize_lab_days(division: str) -> List[str]:
        day_counts = defaultdict(int)
        for day, day_schedule in grid.items():
            for activities in day_schedule.values():
                for activity in activities:
                    if (isinstance(activity, dict) and activity.get("type") == "lab" and
                            activity.get("division") == division):
                        day_counts[day] += 1

        return sorted(grid.keys(), key=lambda d: (day_counts[d], DAY_RANK.get(d, 7)))

    # Process constrained tasks first
    constrained_tasks = [t for t in tasks if t["course"].constraints]
    unconstrained_tasks = [t for t in tasks if not t["course"].constraints]

    for task in constrained_tasks + unconstrained_tasks:
        c = task["course"]
        fac_allowed = _parse_faculty_constraints(c.constraints)
        division = task.get("division", "ALL")
        task_type = task["type"]
        placed = False

        if (task_type == "lab" and (c.course_name, division) in subject_division_allocated) or \
                (task_type == "lecture" and lecture_allocations[c.course_name] >= c.t_hours):
            continue

        # Handle constraints
        if c.constraints:
            for constraint in c.constraints:
                constraint_day = constraint["day"].capitalize()
                constraint_time = constraint["time"]
                constraint_type = constraint.get("type")

                if constraint_day not in grid:
                    continue

                if last_course_per_day.get(constraint_day, {}).get(division) == c.course_name:
                    continue

                # Lab constraints
                if task_type == "lab" and (not constraint_type or constraint_type == "lab"):
                    for slot_info in lab_slots:
                        if (slot_info["label"] == constraint_time and
                                _can_allocate_lab(constraint_day, slot_info, c.faculty_name, division) and
                                _within_faculty_allowed(constraint_day, constraint_time, fac_allowed)):

                            activity = {
                                "id": str(uuid.uuid4()),
                                "type": "lab",
                                "course_name": c.course_name,
                                "faculty_name": c.faculty_name,
                                "division": division,
                                "credits": c.credits,
                                "display": f"{division} - {c.course_name} - {c.faculty_name}"
                            }

                            for s in slot_info["slots"]:
                                grid[constraint_day].setdefault(s, []).append(activity)
                                busy_faculty[constraint_day][s].add(c.faculty_name)
                                busy_divisions[constraint_day][s].add(division)

                            last_course_per_day[constraint_day][division] = c.course_name
                            lab_allocations[c.course_name][division] += 1
                            subject_division_allocated.add((c.course_name, division))
                            placed = True
                            break
                    if placed:
                        break

                # Lecture constraints
                elif task_type == "lecture" and (not constraint_type or constraint_type == "lecture"):
                    if (_slot_ok_for_lecture(
                            grid[constraint_day], constraint_time, c.faculty_name,
                            busy_faculty.get(constraint_day, {}), busy_divisions.get(constraint_day, {}),
                            lab_slots
                    ) and _within_faculty_allowed(constraint_day, constraint_time, fac_allowed) and
                            can_place_lecture(c.course_name, constraint_day, constraint_time, c)):
                        activity = {
                            "id": str(uuid.uuid4()),
                            "type": "lecture",
                            "course_name": c.course_name,
                            "faculty_name": c.faculty_name,
                            "credits": c.credits,
                            "display": f"{c.course_name} - {c.faculty_name}"
                        }

                        grid[constraint_day].setdefault(constraint_time, []).append(activity)
                        busy_faculty[constraint_day][constraint_time].add(c.faculty_name)
                        busy_divisions[constraint_day][constraint_time].add("ALL")
                        last_course_per_day[constraint_day]["ALL"] = c.course_name
                        lecture_allocations[c.course_name] += 1
                        course_day_slots[c.course_name].add((constraint_day, constraint_time))
                        placed = True
                        break

        # Handle unconstrained placement
        if not placed and not c.constraints:
            if task_type == "lab":
                for day in _prioritize_lab_days(division):
                    if (last_course_per_day.get(day, {}).get(division) == c.course_name or
                            _day_has_too_many_labs(day, division, grid)):
                        continue

                    if available_slots := _get_available_lab_slots(day, division, c.faculty_name):
                        slot_info = available_slots[0]
                        activity = {
                            "id": str(uuid.uuid4()),
                            "type": "lab",
                            "course_name": c.course_name,
                            "faculty_name": c.faculty_name,
                            "division": division,
                            "credits": c.credits,
                            "display": f"{division} - {c.course_name} - {c.faculty_name}"
                        }

                        for s in slot_info["slots"]:
                            grid[day].setdefault(s, []).append(activity)
                            busy_faculty[day][s].add(c.faculty_name)
                            busy_divisions[day][s].add(division)

                        last_course_per_day[day][division] = c.course_name
                        lab_allocations[c.course_name][division] += 1
                        subject_division_allocated.add((c.course_name, division))
                        placed = True
                        break

            # Lectures without constraints
            else:
                candidates = []
                for day in sorted(grid.keys(), key=lambda d: DAY_RANK.get(d, 7)):
                    for slot in time_labels:
                        if not (_slot_ok_for_lecture(
                                grid[day], slot, c.faculty_name,
                                busy_faculty.get(day, {}), busy_divisions.get(day, {}), lab_slots
                        ) and can_place_lecture(c.course_name, day, slot, c)):
                            continue

                        score = _soft_score(day, slot, c.course_name, c.credits, last_course_per_day.get(day, {}))
                        candidates.append((score, day, slot))

                if candidates:
                    candidates.sort(reverse=True)
                    _, best_day, best_slot = candidates[0]
                    activity = {
                        "id": str(uuid.uuid4()),
                        "type": "lecture",
                        "course_name": c.course_name,
                        "faculty_name": c.faculty_name,
                        "credits": c.credits,
                        "display": f"{c.course_name} - {c.faculty_name}"
                    }

                    grid[best_day].setdefault(best_slot, []).append(activity)
                    busy_faculty[best_day][best_slot].add(c.faculty_name)
                    busy_divisions[best_day][best_slot].add("ALL")
                    last_course_per_day[best_day]["ALL"] = c.course_name
                    lecture_allocations[c.course_name] += 1
                    course_day_slots[c.course_name].add((best_day, best_slot))
                    placed = True

        if not placed:
            msg = f"Could not place {c.course_name} ({task_type}) for {c.faculty_name}"
            conflicts.append(msg)
            logger.error(msg)

    # Validate lecture allocations
    lecture_courses = {task["course"].course_name: task["course"]
                       for task in tasks if task["type"] == "lecture"}

    for course_name, c in lecture_courses.items():
        required, actual = c.t_hours, lecture_allocations[course_name]
        if actual < required:
            conflicts.append(
                f"Missing {required - actual} lecture(s) for {course_name} "
                f"(required: {required}, got: {actual})"
            )
            logger.warning(f"Course {course_name} needs {required} lectures but only got {actual}")

    return conflicts


def _day_has_too_many_labs(day: str, division: str, grid: Dict) -> bool:
    lab_count = 0
    for activities in grid.get(day, {}).values():
        for activity in activities:
            if (isinstance(activity, dict) and activity.get("division") == division and
                    activity.get("type") == "lab"):
                lab_count += 1
                if lab_count >= 2:
                    return True
    return False


def _optimize_saturday_schedule(grid: Dict, busy_faculty: Dict, busy_divisions: Dict) -> int:
    moved_count = 0

    if "Saturday" not in grid or "Friday" not in grid:
        return moved_count

    saturday_activities = {
        slot: acts for slot, acts in grid["Saturday"].items()
        if acts and not _is_break(acts)
    }

    for sat_slot, sat_acts in saturday_activities.items():
        if not sat_acts or _is_break(sat_acts):
            continue

        # Try to combine with existing Friday labs
        for fri_slot, fri_acts in grid["Friday"].items():
            if not fri_acts or _is_break(fri_acts):
                continue

            if (len(sat_slot.split('-')) == len(fri_slot.split('-')) and
                    any(act.get("type") == "lab" for act in sat_acts) and
                    any(act.get("type") == "lab" for act in fri_acts)):

                fri_faculties = {act.get("faculty_name") for act in fri_acts if isinstance(act, dict)}
                fri_divisions = {act.get("division") for act in fri_acts if isinstance(act, dict)}
                sat_faculties = {act.get("faculty_name") for act in sat_acts if isinstance(act, dict)}
                sat_divisions = {act.get("division") for act in sat_acts if isinstance(act, dict)}

                if not (fri_faculties & sat_faculties) and not (fri_divisions & sat_divisions):
                    grid["Friday"][fri_slot].extend(sat_acts)
                    grid["Saturday"][sat_slot] = None

                    for faculty in sat_faculties:
                        busy_faculty["Friday"].setdefault(fri_slot, set()).add(faculty)
                    for division in sat_divisions:
                        busy_divisions["Friday"].setdefault(fri_slot, set()).add(division)

                    moved_count += 1
                    break

        # Try to move to empty Friday slots
        if moved_count == 0:
            for fri_slot in grid["Friday"]:
                fri_acts = grid["Friday"][fri_slot]
                if fri_acts is not None and not _is_break(fri_acts) and fri_acts:
                    continue

                sat_faculties = {act.get("faculty_name") for act in sat_acts if isinstance(act, dict)}
                sat_divisions = {act.get("division") for act in sat_acts if isinstance(act, dict)}

                faculty_available = all(
                    faculty not in busy_faculty.get("Friday", {}).get(fri_slot, set())
                    for faculty in sat_faculties
                )

                division_available = all(
                    division not in busy_divisions.get("Friday", {}).get(fri_slot, set())
                    for division in sat_divisions
                )

                if faculty_available and division_available:
                    grid["Friday"][fri_slot] = sat_acts
                    grid["Saturday"][sat_slot] = None

                    for faculty in sat_faculties:
                        busy_faculty["Friday"].setdefault(fri_slot, set()).add(faculty)
                    for division in sat_divisions:
                        busy_divisions["Friday"].setdefault(fri_slot, set()).add(division)

                    moved_count += 1
                    break

    return moved_count


def simplify_grid(grid: Dict, time_labels: List[str], lab_slot_len: int) -> Dict:
    simplified = {}
    time_slot_order = {slot: idx for idx, slot in enumerate(time_labels)}

    # Generate lab slot candidates
    lab_slots = _generate_lab_slots(time_labels, lab_slot_len)

    for day, slots in grid.items():
        day_schedule = {}

        # Process lab slots
        for slot_info in lab_slots:
            combined_label = slot_info["label"]
            slot_group = slot_info["slots"]

            if all(
                    any(act.get("type") == "lab" for act in (slots.get(slot) or []))
                    for slot in slot_group
            ):
                all_lab_activities = []
                for slot in slot_group:
                    for activity in slots.get(slot) or []:
                        if (activity.get("type") == "lab" and not any(
                                a.get("course_name") == activity.get("course_name") and
                                a.get("faculty_name") == activity.get("faculty_name") and
                                a.get("division") == activity.get("division")
                                for a in all_lab_activities
                        )):
                            all_lab_activities.append(activity)

                if all_lab_activities:
                    grouped_activities = defaultdict(list)
                    for act in all_lab_activities:
                        key = f"{act.get('course_name')}-{act.get('faculty_name')}"
                        grouped_activities[key].append(act)

                    lab_entries = []
                    for activities in grouped_activities.values():
                        divisions = sorted(list({act.get("division") for act in activities}))
                        course_name = activities[0].get("course_name")
                        faculty_name = activities[0].get("faculty_name")
                        lab_entries.append(f"{', '.join(divisions)} - {course_name} - {faculty_name}")

                    day_schedule[combined_label] = lab_entries

                    for slot in slot_group:
                        if slot in slots and slots[slot] is not None:
                            slots[slot] = []

        # Process remaining slots
        all_slots = sorted(slots.keys(), key=lambda x: time_slot_order.get(x, float('inf')))

        for slot in all_slots:
            if slot in day_schedule:
                continue

            activities = slots[slot]
            if not activities:
                continue

            if any(_is_break(a) for a in activities):
                day_schedule[slot] = activities[0].get('name', 'Break')
            elif lecture_activities := [a for a in activities if a.get('type') == 'lecture']:
                day_schedule[slot] = lecture_activities[0].get('display', '')
            elif activities:
                day_schedule[slot] = [a.get('display', '') for a in activities]

        # Sort by start time
        simplified[day] = dict(sorted(
            day_schedule.items(),
            key=lambda x: x[0].split('-')[0] if '-' in x[0] else x[0]
        ))

    return simplified


def generate_timetable(db, dept, sem, user_id=None, persist_to_db=False) -> Dict[str, Any]:
    r = get_redis()
    rkey_layout = f"tt:{dept}:{sem}:layout"

    try:
        state = json.loads(r.get(rkey_layout) or "{}")
    except json.JSONDecodeError as e:
        logger.error(f"JSON decode error: {str(e)}")
        raise ValueError("Invalid JSON in timetable layout")

    layout = state.get("layout", {})
    grid = state.get("grid", {})

    # Check if time_slots exists in layout
    if "time_slots" not in layout:
        logger.error(f"Missing time_slots in layout for dept={dept}, sem={sem}")
        # Try to get time_slots from a default configuration or raise a more specific error
        raise ValueError("Timetable layout is incomplete. Please ensure the schedule form was submitted correctly.")

    time_labels = _collect_time_labels(layout)
    slot_duration = int(layout.get("slot_duration", 55))
    lab_minutes = int(layout.get("lab_minutes", 110))
    lab_slot_len = max(1, lab_minutes // slot_duration)

    # Initialize busy maps
    busy_faculty = defaultdict(lambda: defaultdict(set))
    busy_divisions = defaultdict(lambda: defaultdict(set))

    # Convert grid to list format
    for day, day_slots in grid.items():
        for slot, cell in day_slots.items():
            if cell is None:
                grid[day][slot] = []
            elif not isinstance(cell, list):
                grid[day][slot] = [cell] if _is_break(cell) else [cell]
                if faculty := cell.get("faculty_name"):
                    busy_faculty[day][slot].add(faculty)
                if division := cell.get("division"):
                    busy_divisions[day][slot].add(division)

    # Get course needs and create tasks
    needs = _course_needs_from_db_and_redis(db, dept, sem, r)
    logger.debug(f"Found {len(needs)} courses with faculty assignments")

    tasks = []
    for c in needs:
        # Lectures
        for _ in range(c.t_hours):
            tasks.append({"course": c, "type": "lecture", "block_len": 1})

        # Labs
        if c.practical:
            for div, block_len, _ in _expand_lab_requirements(c, lab_minutes, slot_duration):
                tasks.append({"course": c, "type": "lab", "block_len": block_len, "division": div})

    # Allocation with retries
    all_conflicts = []
    retry_count = 0

    for retry in range(MAX_RETRIES + 1):
        conflicts = _allocate_tasks(
            tasks, grid, busy_faculty, busy_divisions,
            time_labels, lab_slot_len, 1
        )

        if not conflicts:
            logger.info(f"Timetable generated successfully on attempt {retry + 1}")
            retry_count = retry
            break

        all_conflicts.extend(conflicts)
        if retry < MAX_RETRIES:
            freed = _free_low_priority_slots(grid, busy_faculty, busy_divisions, len(conflicts) * 2)
            logger.info(f"Retry {retry + 1}: Freed {freed} low-priority slots")
        else:
            logger.warning(f"Max retries reached with {len(conflicts)} conflicts")
            retry_count = MAX_RETRIES

    # Optimize Saturday schedule
    saturday_optimized = _optimize_saturday_schedule(grid, busy_faculty, busy_divisions)
    if saturday_optimized > 0:
        logger.info(f"Moved {saturday_optimized} activities from Saturday to Friday")

    # Cleanup empty slots
    for day in grid:
        for slot in list(grid[day].keys()):
            if not grid[day][slot]:
                grid[day][slot] = None

    # Save results
    r.set(rkey_layout, json.dumps({"layout": layout, "grid": grid}, ensure_ascii=False))

    # Convert sets to lists for JSON serialization
    def convert_sets(obj):
        if isinstance(obj, set):
            return list(obj)
        elif isinstance(obj, dict):
            return {k: convert_sets(v) for k, v in obj.items()}
        return obj

    r.set(f"tt:{dept}:{sem}:busy_faculty", json.dumps(convert_sets(busy_faculty)))
    r.set(f"tt:{dept}:{sem}:busy_divisions", json.dumps(convert_sets(busy_divisions)))

    simplified_grid = simplify_grid(grid, time_labels, lab_slot_len)

    result = {
        "grid": simplified_grid
    }

    if persist_to_db and user_id:
        # Save to database with user association
        crud_timetables.save_timetable_json(
            db=db,
            dept=dept,
            sem=sem,
            user_id=user_id,  # Pass the user_id
            timetable_json=result,
        )

    return result